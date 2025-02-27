"""
litestream
Copyright (C) 2024  spertilo.net

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""

import re, socket, time, gc
from machine import Pin, I2S, Timer
import micropython
from errno import EINPROGRESS
import select
import ssl

try:
    import AudioDecoder

except ImportError:
    import AACDecoder


if not "AAC_Decoder" in dir(AudioDecoder):
    raise ImportError("Firmware is out of date")

# Use const() so that micropython inlines these and saves a lookup
play_state_Stopped = const(0)
play_state_Playing = const(1)
play_state_Paused = const(2)

format_MP3 = const(0)
format_Vorbis = const(1)
format_AAC = const(2)

decode_phase_trackstart = const(0)
decode_phase_inheader = const(1)
decode_phase_readinfo = const(2)
decode_phase_decoding = const(3)

read_phase_start = const(0)
read_phase_end = const(1)
read_phase_read = const(2)

sck_pin = Pin(13)  # Serial clock output
ws_pin = Pin(14)  # Word clock output
sd_pin = Pin(17)  # Serial data output
mute_pin = Pin(3, Pin.OUT, value=1)  # XSMT on DAC chip

# --------------------------------------------------------------------------------------------------------
# 0. Byte SyncByte  | 0 | 1 | 0 | 0 | 0 | 1 | 1 | 1 | always bit pattern of 0x47
# 1. Byte           |PUSI|TP|   |PID|PID|PID|PID|PID|
# 2. Byte           |PID|PID|PID|PID|PID|PID|PID|PID|
# 3. Byte           |TSC|TSC|AFC|AFC|CC |CC |CC |CC |
# 4.-187. Byte      |Payload data if AFC==01 or 11  |
# ---------------------------------------------------------------------------------------------------------
#
# PUSI Payload unit start indicator, set when this packet contains the first byte of a new payload unit.
#      The first byte of the payload will indicate where this new payload unit starts.
# TP   Transport priority, set when the current packet has a higher priority than other packets with the same PID.
# PID  Packet Identifier, describing the payload data.
# TSC  Transport scrambling control, '00' = Not scrambled.
# AFC  Adaptation field control, 01 – no adaptation field, payload only, 10 – adaptation field only, no payload,
#                                11 – adaptation field followed by payload, 00 – RESERVED for future use
# CC   Continuity counter, Sequence number of payload packets (0x00 to 0x0F) within each stream (except PID 8191)
#
# A Program Association Table (PAT, 0x0000) contains info about Program Map Tables (PMT, 0x0002), and these map the
# streams (audio (typically 0x1C0-0x1D0), video, etc.) within the program to their respective PIDs


class TSPacketParser:
    # A parser for MPEG Transport Stream (TS) packets.

    TS_PACKET_SIZE = 188
    PAYLOAD_SIZE = 184

    def __init__(self, log_func=None):
        # Initialize the TSPacketParser.
        # param log_func: A callable for logging messages. Optional.
        self.log_func = log_func
        self.pmt_pids = []
        self.pes_data_length = None
        self.aac_pid = None

    def log(self, msg):
        # Log a message using the provided logging function
        if self.log_func:
            self.log_func(msg)

    def reset(self):
        # Reset the parser's internal state
        self.log("Parser reset")
        self.pmt_pids = []
        self.pes_data_length = None
        self.aac_pid = None

    def parse_packet(self, packet, output_buffer):
        # Parse a TS packet from `packet` and write extracted AAC data to `output_buffer`
        # param packet: A 188-byte memoryview representing the TS packet.
        # param output_buffer: A memoryview where extracted data will be written.
        # return: The length of data written to `output_buffer`.

        if packet is None or output_buffer is None:
            self.reset()
            return 0

        if len(packet) != self.TS_PACKET_SIZE or len(output_buffer) < self.TS_PACKET_SIZE:
            self.log("Input packet must be 188 bytes, output buffer must be at least 188 bytes")
            return 0

        # Ensure packet is a memoryview
        if not isinstance(packet, memoryview):
            packet = memoryview(packet)

        if packet[0] != 0x47:
            self.log(f"Sync byte not found, first bytes are {bytes(packet[:4])}")
            return 0

        pid = ((packet[1] & 0x1F) << 8) | packet[2]
        pusi = (packet[1] & 0x40) >> 6
        afc = (packet[3] & 0x30) >> 4

        self.log(f"PID: 0x{pid:04X} ({pid})")
        self.log(f"PUSI: {pusi}")
        self.log(f"AFC: {afc}")

        # Initialize payload start index. Start after the TS packet header (4 bytes)
        pls = 4

        # Handle Adaptation Field if present
        if afc & 0x2:
            # Adaptation field is present
            adaptation_field_length = packet[pls]
            self.log(f"Adaptation Field Length: {adaptation_field_length}")

            # Move past adaptation field
            pls += 1 + adaptation_field_length

        if pls >= self.TS_PACKET_SIZE:
            self.log("Index exceeds packet size after adaptation field")
            return 0

        # Handle PUSI (Payload Unit Start Indicator)
        if pusi:
            if pid == 0x0000 or pid in self.pmt_pids:
                # PSI packets (PAT or PMT) contain a pointer field
                pointer_field = packet[pls]
                self.log(f"Pointer Field: {pointer_field}")
                # Move past pointer field and any padding
                pls += 1 + pointer_field
            else:
                # PES packets (e.g., AAC data) do not contain a pointer field
                self.log("PUSI set in PES packet, payload starts immediately")
                # No adjustment needed

        if pls >= self.TS_PACKET_SIZE:
            self.log("Index exceeds packet size after PUSI handling")
            return 0

        self.log(f"Index after adjustments: {pls}")

        # Process packet based on PID
        if pid == 0x0000:
            # PAT packet
            self.process_pat(packet, pls)
        elif pid in self.pmt_pids:
            # PMT packet
            self.process_pmt(packet, pls)
        elif pid == self.aac_pid:
            # AAC audio packet
            return self.process_aac(packet, pls, output_buffer, pusi)
        else:
            self.log(f"Unhandled PID: 0x{pid:04X}")
            return 0

        return 0

    def process_pat(self, packet, index):
        # Process the Program Association Table (PAT)
        self.log("Processing PAT")
        if index + 3 >= self.TS_PACKET_SIZE:
            self.log("Not enough data for PAT header")
            return

        section_length = ((packet[index + 1] & 0x0F) << 8) | packet[index + 2]
        self.log(f"Section Length: {section_length}")

        # Exclude CRC (4 bytes)
        end_index = index + 3 + section_length - 4

        # Move to the first program info after PAT header
        index += 8

        while index + 3 <= end_index and index + 3 < self.TS_PACKET_SIZE:
            program_number = (packet[index] << 8) | packet[index + 1]
            program_map_pid = ((packet[index + 2] & 0x1F) << 8) | packet[index + 3]
            self.log(f"Program Number: {program_number}, PMT PID: 0x{program_map_pid:04X}")

            if program_number != 0:
                if program_map_pid not in self.pmt_pids:
                    self.pmt_pids.append(program_map_pid)

            # Move to the next program info
            index += 4

    def process_pmt(self, packet, index):
        # Process the Program Map Table (PMT)
        self.log("Processing PMT")
        if index + 11 >= self.TS_PACKET_SIZE:
            self.log("Not enough data for PMT header")
            return

        section_length = ((packet[index + 1] & 0x0F) << 8) | packet[index + 2]
        program_info_length = ((packet[index + 10] & 0x0F) << 8) | packet[index + 11]
        self.log(f"Section Length: {section_length}")
        self.log(f"Program Info Length: {program_info_length}")

        # Move to the first stream info
        index += 12 + program_info_length

        # Exclude CRC and headers
        end_index = index + section_length - program_info_length - 13

        while index + 4 <= end_index and index + 4 < self.TS_PACKET_SIZE:
            stream_type = packet[index]
            elementary_pid = ((packet[index + 1] & 0x1F) << 8) | packet[index + 2]
            es_info_length = ((packet[index + 3] & 0x0F) << 8) | packet[index + 4]
            self.log(f"Stream Type: 0x{stream_type:02X}, Elementary PID: 0x{elementary_pid:04X}")

            # AAC Audio
            if stream_type in (0x0F, 0x11):
                self.log("AAC PID found")
                self.aac_pid = elementary_pid

            # Move to the next stream info
            index += 5 + es_info_length

    def process_aac(self, packet, index, output_buffer, pusi):
        # Extract AAC data from the packet and write it to output_buffer.
        self.log(f"Processing AAC data at index {index}")

        if pusi:
            # Start of a new PES packet
            if index + 3 > len(packet):
                self.log("Not enough data to check PES start code")
                return 0

            if packet[index : index + 3] == b"\x00\x00\x01":
                stream_id = packet[index + 3]
                self.log(f"Stream ID: 0x{stream_id:02X}")

                if 0xC0 <= stream_id <= 0xDF:
                    # Audio stream ID
                    pes_packet_length = (packet[index + 4] << 8) | packet[index + 5]
                    pes_header_data_length = packet[index + 8]
                    start_of_data = index + 9 + pes_header_data_length

                    if start_of_data >= len(packet):
                        self.log("Not enough data for PES payload")
                        self.pes_data_length = None
                        return 0

                    # Check for ID3 tag
                    payload = packet[start_of_data:]
                    if len(payload) >= 3 and payload[0:3] == b"ID3":
                        self.log("ID3 tag detected in PES payload")
                        id3_size = self.parse_id3_tag(payload)
                        if id3_size < 0:
                            self.log("Invalid ID3 tag size")
                            return 0
                        # Skip over the ID3 tag
                        start_of_data += id3_size
                        if start_of_data >= len(packet):
                            self.log("No AAC data after ID3 tag")
                            return 0
                        payload = packet[start_of_data:]
                    else:
                        self.log("No ID3 tag detected")

                    # Update the expected remaining PES data length
                    if pes_packet_length != 0:
                        self.pes_data_length = pes_packet_length - (start_of_data - index - 6)
                    else:
                        # Unspecified length
                        self.pes_data_length = None

                    copy_length = len(payload)
                    output_buffer[:copy_length] = payload

                    self.log(f"Extracted {copy_length} bytes of AAC data (new PES packet)")
                    return copy_length
                else:
                    self.log("Non-audio stream detected")
                    self.pes_data_length = None
                    return 0
            else:
                self.log(f"PES start code not found at index {index}, data: {bytes(packet[index:index + 3])}")
                self.pes_data_length = None
                return 0
        else:
            # Continuation of a PES packet
            if self.pes_data_length is not None:
                data = packet[index:]
                copy_length = len(data)

                if self.pes_data_length is not None:
                    if self.pes_data_length <= 0:
                        self.log("No more data expected for current PES packet")
                        self.pes_data_length = None
                        return 0
                    if copy_length > self.pes_data_length:
                        copy_length = self.pes_data_length

                    self.pes_data_length -= copy_length
                    if self.pes_data_length == 0:
                        self.pes_data_length = None

                output_buffer[:copy_length] = data[:copy_length]
                self.log(f"Continuing PES packet, copied {copy_length} bytes")
                return copy_length
            else:
                self.log("No PES packet in progress, and PUSI=0")
                return 0

    def parse_id3_tag(self, data):
        # Parses the ID3 tag to determine its size.
        # param data: A memoryview starting with 'ID3'
        # return: The total size of the ID3 tag including header.

        if len(data) < 10:
            self.log("ID3 tag too short to parse header")
            return -1  # Invalid ID3 tag

        # Verify the 'ID3' identifier
        if data[0:3].tobytes() != b"ID3":
            self.log("ID3 tag identifier not found")
            return -1

        # ID3v2 header is 10 bytes
        # Bytes 6-9 contain the tag size as a synchsafe integer
        id3_size_bytes = data[6:10]
        id3_size = self.synchsafe_to_int(id3_size_bytes)
        self.log(f"ID3 tag size: {id3_size} bytes")

        # Total size is header (10 bytes) plus the size from the header
        total_id3_size = 10 + id3_size
        return total_id3_size

    def synchsafe_to_int(self, data):
        # Converts a 4-byte synchsafe integer to a regular integer
        value = 0
        for byte in data:
            value = (value << 7) | (byte & 0x7F)
        return value


####################### End of TSParser #######################


class AudioPlayer:
    def __init__(self, callbacks={}, debug=0):
        self.callbacks = callbacks
        if "display" not in self.callbacks.keys():
            self.callbacks["display"] = lambda x, y: None
        if "messages" not in self.callbacks.keys():
            self.callbacks["messages"] = lambda m: m
        self.DEBUG = debug
        # self.AACDecoder = AudioDecoder.AAC_Decoder()
        self.reset_player()

    def reset_player(self, reset_head=True):
        self.DEBUG and print("Resetting Player")
        # self.callbacks["messages"](f"reset_player")

        self.PlayLoopRunning = False
        self.ReadLoopRunning = False
        self.DecodeLoopRunning = False
        self.decode_phase = decode_phase_trackstart
        self.read_phase = read_phase_start
        self.I2SAvailable = True
        self.ID3Tag_size = 0
        self.PLAY_STATE = play_state_Stopped

        if reset_head:
            self.callbacks["messages"](f"reset_head")
            if hasattr(self, "pumptimer"):
                self.pumptimer.deinit()
                print("sleeping after deinit")
                time.sleep(2)
            if hasattr(self, "AACDecoder"):
                del self.AACDecoder
                gc.collect()
            self.AACDecoder = AudioDecoder.AAC_Decoder()
            self._init_vars()
            self._init_buffers()
            self._init_i2s_player()
            self.start_timer()

        # Clear the buffers
        self.InBuffer.read()
        self.OutBuffer.read()

        # This frees up all the buffers that the decoders allocated, and resets their state
        # self.MP3Decoder.MP3_Close()
        # self.VorbisDecoder.Vorbis_Close()
        self.AACDecoder.AAC_Close()

        # If this is an SSL socket, this also closes the underlying "real" socket
        if self.sock is not None:
            self.sock.close()
            self.sock = None

        print(self)

    def _init_vars(self):

        self.PLAY_STATE = play_state_Stopped
        self.volume = 0
        self.sock = None
        self.song_transition = None
        self.mute_pin = mute_pin
        self.trackReader = None

        # The index of the current track in the playlist that we are playing (actually this is which track we are currently decoding - playback lags by the size of the OutBuffer)
        self.hash_being_read = self.hash_being_played = self.hash_being_decoded = None
        self.playlist = []
        self.decode_stack = []
        self.play_stack = []

        # TrackInfo is a list of track lengths and their corresponding audio type (vorbis or MP3). This tells the decoder when to move onto the next track, and also which decoder to use.
        self.TrackInfo = []

        # DecodeInfo contains the length of the data for the decoder to decode. It is different to Trackinfo as a .ts file will have more bytes to read than there is audio data to decode
        self.DecodeInfo = []

        # PlayInfo is filled out when the decoder starts a new track, and tells the play loop the format of the track (rate, bits, channels)
        self.PlayInfo = []

        # PlayLength is filled out when we finish decoding a track, and tells the play loop how many decoded bytes are in the track
        self.PlayLength = []

        # The number of bytes of the current track that we have read from the network
        # This is compared against the length of the track returned from the server in the Content-Range header to determine end-of-track read
        # (this is potentially different to which track we are currently playing. We could be reading ahead of decoding and playing by one or more tracks)
        self.current_track_bytes_read = 0

        # The number of bytes that the parser has parsed for this track
        self.current_track_bytes_parsed_out = 0

        # The number of bytes the parser has read from the input buffer for this track. Used to detect the end of track by the decoder
        self.current_track_bytes_parsed_in = 0

        # The number of bytes the decoder has read from the parser for this track
        self.current_track_bytes_decoder_in = 0

        # The number of bytes of decoded audio data the decoder has written to the OutBuffer for this track
        self.current_track_bytes_decoded_out = 0

        # The number of bytes played for the current track. Used to detect the end of track by the play loop by comparing against current_track_bytes_decoded_out
        self.current_track_bytes_played = 0

        # Used for statistics during debugging
        self.consecutive_zeros = 0

    def _init_buffers(self):
        # Size of the chunks of decoded audio that we will send to I2S
        self.ChunkSize = 70 * 1024
        self.ChunkBuffer = bytearray(self.ChunkSize)
        self.ChunkBufferMV = memoryview(self.ChunkBuffer)

        # A buffer used to read data from the network
        self.ReadBufferSize = 16 * 1024
        ReadBufferBytes = bytearray(self.ReadBufferSize)
        self.ReadBufferMV = memoryview(ReadBufferBytes)

        # A buffer used to store decoded audio data before writing it to the OutBuffer
        self.AudioBufferSize = 2048 * 2
        AudioBufferBytes = bytearray(self.AudioBufferSize)
        self.AudioBufferMV = memoryview(AudioBufferBytes)

        # An array to hold packets from the network. As an example, a 96000 bps bitrate is 12kB per second, so a ten second buffer should be about 120kB
        # Note that the RingIO buffer uses one byte internally to track the ring, so we add one to the size to account for this
        self.InBufferSize = 160 * 1024
        InBufferBytes = bytearray(self.InBufferSize + 1)
        InBufferMV = memoryview(InBufferBytes)
        self.InBuffer = micropython.RingIO(InBufferMV)

        # An array to hold decoded audio samples. 44,100kHz takes 176,400 bytes per second (16 bit samples, stereo). e.g. 1MB will hold 5.9 seconds, 700kB will hold 4 seconds
        self.OutBufferSize = 700 * 1024
        OutBufferBytes = bytearray(self.OutBufferSize + 1)
        OutBufferMV = memoryview(OutBufferBytes)
        self.OutBuffer = micropython.RingIO(OutBufferMV)

        ParserInBytes = bytearray(188)
        self.ParserInMV = memoryview(ParserInBytes)

        ParserOutBytes = bytearray(188)
        self.ParserOutMV = memoryview(ParserOutBytes)

        self.TSParser = TSPacketParser()  # log_func=print)

    def _init_i2s_player(self):
        # Create the IS2 output device. Make the rate a silly value so that it won't match when we check in play_chunk
        if hasattr(self, "audio_out"):
            self.audio_out.deinit()

        self.audio_out = I2S(
            0,
            sck=sck_pin,
            ws=ws_pin,
            sd=sd_pin,
            mode=I2S.TX,
            bits=16,
            format=I2S.STEREO,
            rate=1,
            ibuf=self.ChunkSize,
        )

    def __repr__(self):
        if self.PLAY_STATE == play_state_Playing:
            status = "Playing"
        elif self.PLAY_STATE == play_state_Paused:
            status = "Paused"
        elif self.PLAY_STATE == play_state_Stopped:
            status = "Stopped"
        else:
            status = " !?! "

        retstring = f"{status} -- {[l if i==0 else l[1] for i,l in enumerate(self.playlist[:10])]}" + (
            f" ... {len(self.playlist) - 10} more" if len(self.playlist) > 10 else ""
        )

        if self.PLAY_STATE != play_state_Stopped:
            retstring += f"\n    -- "
            retstring += f" Read {self.current_track_bytes_read}"
            retstring += f" Parsed {self.current_track_bytes_parsed_in}"
            retstring += f" Decoded {self.current_track_bytes_decoder_in}"
            retstring += f" Played {self.current_track_bytes_played}"
            retstring += f" Out {self.current_track_bytes_decoded_out}"
            retstring += f" TrackInfo {self.TrackInfo}"
            retstring += f" DecodeInfo {self.DecodeInfo}"
            retstring += f" PlayInfo {self.PlayInfo}"
            retstring += f" PlayLength {self.PlayLength}"
            retstring += f" decode_stack {self.decode_stack}"
            retstring += f" play_stack {self.play_stack}"
        return retstring

    def ntracks(self):
        return len(self.playlist)

    # Set volume from 1 (quietest) to 11 (loudest)
    def set_volume(self, vol):
        assert vol >= 1 and vol <= 11, "Invalid Volume value"
        self.volume = vol - 11

    def get_volume(self):
        return self.volume + 11

    def mute_audio(self):
        self.mute_pin(0)

    def unmute_audio(self):
        self.mute_pin(1)

    def play(self):
        # Do not unmute here or you will hear a tiny bit of the previous track when ffwd/rewinding
        if self.PLAY_STATE == play_state_Stopped:
            self.DEBUG and print("Track read start")
            self.callbacks["messages"]("play: Start reading track")
            self.read_phase = read_phase_start
            self.trackReader = self.start_track()
            self.ReadLoopRunning = True
            self.PLAY_STATE = play_state_Playing

        elif self.PLAY_STATE == play_state_Playing:
            self.callbacks["messages"](f"Playing URL {self.hash_being_read}")

        elif self.PLAY_STATE == play_state_Paused:
            self.callbacks["messages"](f"Un-pausing URL {self.hash_being_read}")
            self.PLAY_STATE = play_state_Playing

            # Kick off the playback loop
            self.play_chunk()

        self.unmute_audio()

    def pause(self):
        if self.PLAY_STATE == play_state_Playing:
            self.mute_audio()
            self.callbacks["messages"](f"Pausing URL {self.hash_being_read}")
            self.PLAY_STATE = play_state_Paused

    def rewind(self):
        self.DEBUG and print("in rewind")
        self.advance_track(-1)

    def ffwd(self):
        self.DEBUG and print("in ffwd")
        self.advance_track()

    def stop(self, reset_head=True):
        self.mute_audio()
        self.reset_player(reset_head)

        if self.PLAY_STATE == play_state_Stopped:
            return False
        self.PLAY_STATE = play_state_Stopped

        return True

    def advance_track(self, increment=1):
        pass
        """
        if self.current_track is None:
            return

        if not 0 <= (self.current_track + increment) < self.ntracks():
            if self.PLAY_STATE == play_state_Playing:
                self.stop()
            return

        self.stop(reset_head=False)
        self.current_track += increment
        self.next_track = self.set_next_track()
        self.callbacks["messages"](f"advance track: current_track = {self.hash_being_read}")
        print(self)
        """

    def is_paused(self):
        return self.PLAY_STATE == play_state_Paused

    def is_stopped(self):
        return self.PLAY_STATE == play_state_Stopped

    def is_playing(self):
        return self.PLAY_STATE == play_state_Playing

    def parse_url(self, location):
        parts = location.decode().split("://", 1)
        port = 80 if parts[0] == "http" else 443 if parts[0] == "https" else 0
        url = parts[1].split("/", 1)
        host = url[0]
        path = url[1] if url[1].startswith("/") else "/" + url[1]
        return host, port, path

    #    def start_track(self, trackno, offset=0, port=80):
    def start_track(self, offset=0, port=80):
        #        if trackno is None:
        #            return

        track_length = 0
        self.current_track_bytes_read = offset
        # url, hash = self.playlist[trackno]  # do a .pop() here, then we don't need to keep track of the track number
        url, hash = self.playlist.pop(0)
        self.hash_being_read = hash
        self.decode_stack.append(hash)
        self.play_stack.append(hash)
        host, port, path = self.parse_url(url.encode())
        assert port > 0, "Invalid URL prefix"

        # We might have a socket already from the previous track
        if self.sock is not None:
            self.sock.close()
            del self.sock
            self.sock = None

        # Load up the outbuffer before we fetch a new file
        yield
        yield
        yield
        yield
        yield

        # Establish a socket connection to the server
        conn = socket.socket()
        self.callbacks["messages"](f"start_track: Start reading track {hash}")
        print(f"Getting {path} from {host}, Port:{port}, Offset {offset}")
        addr = socket.getaddrinfo(host, port)[0][-1]

        # Tell the socket to return straight away (async)
        conn.setblocking(False)

        # Connect the socket.
        # We need to set the socket to non-blocking before connecting or it can block for some time if the connection is SSL
        # However, by design we will get a EINPROGRESS error, so catch it.
        try:
            conn.connect(addr)
        except OSError as er:
            if er.errno != EINPROGRESS:
                raise RuntimeError("Socket connect error")

        # If this is an SSL connection, wrap the socket in an SSLContext.
        # This provides a "virtual socket" on top of the real socket and handles all the encryption/decryption
        # For non-SSL, just use the socket as-is
        if port == 443:
            ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
            self.sock = ctx.wrap_socket(conn, server_hostname=host, do_handshake_on_connect=False)
            self.sock.setblocking(False)
        else:
            self.sock = conn

        yield

        # Request the file with optional offset (Use an offset if we're re-requesting the same file after a long pause)
        data = bytes(f"GET {path} HTTP/1.1\r\nHost: {host}\r\nRange: bytes={offset}-\r\n\r\n", "utf8")

        # Write the data to the async socket. Use a poller with a 10ms timeout
        # Because this is an async socket it will return straight away, allowing the SSL handshake to happen under the covers
        # We keep looping until all the data has been sent (which is after the SSL handshake is complete)
        poller = select.poll()
        poller.register(self.sock, select.POLLOUT)

        while data:
            poller.poll(10)
            n = self.sock.write(data)
            yield

            if n is not None:
                data = data[n:]

        poller.unregister(self.sock)

        # Read the response headers
        response_headers = b""
        while True:
            header = self.sock.readline()
            yield

            if header is not None:
                response_headers += header.decode("utf-8")

                # Save the length of the track. We use this to keep track of when we have finished reading a track rather than relying on EOF
                # EOF is indistinguishable from the host closing a socket when we pause too long
                if header.lower().startswith(b"content-range:"):
                    track_length = int(header.split(b"/", 1)[1])

                if header.lower().startswith(b"content-length:"):
                    track_length = int(header.split(b":")[1])
                    self.DEBUG and print(f"track length is {track_length} from {header}")

            if header == b"\r\n":
                break

        # Check if the response is a redirect. If so, kill the socket and re-open it on the redirected host/path
        while b"HTTP/1.1 301" in response_headers or b"HTTP/1.1 302" in response_headers:
            self.DEBUG and print("Got Redirect")
            redirect_location = None

            for line in response_headers.split(b"\r\n"):
                if line.startswith(b"Location:"):
                    redirect_location = line.split(b": ", 1)[1]
                    break

            if redirect_location:
                # Extract the new host, port, and path from the redirect location
                host, port, path = self.parse_url(redirect_location)
                assert port > 0, "Invalid URL prefix"

                self.sock.close()
                del self.sock
                self.sock = None

                # Load up the outbuffer before we fetch the new file
                yield
                yield
                yield
                yield
                yield

                # Establish a new socket connection to the server
                conn = socket.socket()
                print(f"Redirecting to {path} from {host}, Port:{port}, Offset {offset}")
                addr = socket.getaddrinfo(host, port)[0][-1]

                # Tell the socket to return straight away (async)
                conn.setblocking(False)

                # Connect the socket.
                # We need to set the socket to non-blocking before connecting or it can block for some time if the connection is SSL
                # However, by design we will get a EINPROGRESS error, so catch it.
                try:
                    conn.connect(addr)
                except OSError as er:
                    if er.errno != EINPROGRESS:
                        raise RuntimeError("Socket connect error")

                # If this is an SSL connection, wrap the socket in an SSLContext.
                if port == 443:
                    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
                    self.sock = ctx.wrap_socket(conn, server_hostname=host, do_handshake_on_connect=False)
                    self.sock.setblocking(False)
                else:
                    self.sock = conn

                yield

                # Request the file with optional offset (Use an offset if we're re-requesting the same file after a long pause)
                data = bytes(f"GET {path} HTTP/1.1\r\nHost: {host}\r\nRange: bytes={offset}-\r\n\r\n", "utf8")

                # Write the data to the async socket. Use a poller with a 10ms timeout
                # Because this is an async socket it will return straight away, allowing the SSL handshake to happen under the covers
                # We keep looping until all the data has been sent (which is after the SSL handshake is complete)
                poller = select.poll()
                poller.register(self.sock, select.POLLOUT)
                while data:
                    poller.poll(10)
                    n = self.sock.write(data)
                    yield

                    if n is not None:
                        data = data[n:]

                poller.unregister(self.sock)

                # Read the response headers
                response_headers = b""
                while True:
                    header = self.sock.readline()
                    yield

                    if header is not None:
                        response_headers += header.decode("utf-8")

                        # Save the length of the track. We use this to keep track of when we have finished reading a track rather than relying on EOF
                        # EOF is indistinguishable from the host closing a socket when we pause too long
                        if header.lower().startswith(b"content-range:"):
                            track_length = int(header.split(b"/", 1)[1])

                        if header.lower().startswith(b"content-length:"):
                            track_length = int(header.split(b":", 1)[1])

                    if header == b"\r\n":
                        break

        # Make sure we know the length of the track and got a valid response from the server. If not, skip this track.
        if track_length == 0 or (b"HTTP/1.1 200" not in response_headers and b"HTTP/1.1 206" not in response_headers):
            print("Bad URL:", url)
            print("Headers:", response_headers)
            print("TrackLength:", track_length)
            self.current_track_bytes_read = 0
            # Track read failed - cleanup
            self.read_phase = read_phase_end
            return

        # Store the end-of-track and format marker for this track (except if we are restarting a track)
        if offset == 0:
            if path.lower().endswith(".mp3"):
                self.TrackInfo.append((track_length, format_MP3))
            elif path.lower().endswith(".ogg"):
                self.TrackInfo.append((track_length, format_Vorbis))
            elif path.lower().endswith(".ts"):
                self.TrackInfo.append((track_length, format_AAC))
            elif path.lower().endswith(".aac"):
                self.TrackInfo.append((track_length, format_AAC))
            else:
                raise RuntimeError("Unsupported audio type")

        # Now we can start reading the track
        self.read_phase = read_phase_read

    def end_track(self):
        self.DEBUG and print("Track read end")
        gc.collect()
        self.DEBUG and print(f"Bytes read: {self.current_track_bytes_read}")

        if len(self.playlist) > 0:
            # We can read the header of the next track now
            self.DEBUG and print("Track read start")
            self.trackReader = self.start_track()
            self.callbacks["messages"](f"end_track: Finished reading track {self.hash_being_read}")
        else:
            # We have no more data to read from the network, but we have to let the decoder run out, and then let the play loop run out
            self.DEBUG and print("Finished reading playlist")
            self.callbacks["messages"](f"end_track: Finished reading all tracks")
            self.sock.close()
            del self.sock
            self.sock = None
            self.ReadLoopRunning = False

    def read_chunk(self):
        if self.read_phase == read_phase_start:
            try:
                next(self.trackReader)
            except StopIteration:
                pass

        elif self.read_phase == read_phase_end:
            self.end_track()
            self.read_phase = read_phase_start

        elif self.read_phase == read_phase_read:
            # If there is no socket then we have already read to the end of the playlist
            if self.sock is None:
                return 0

            # If no free space in the input buffer return, otherwise add any data available from the network
            if (InBufferBytesAvailable := self.InBufferSize - self.InBuffer.any()) == 0:
                return 0

            data = None

            # We can get an exception here if we pause too long and the underlying socket gets closed
            try:
                # Read data into the InBuffer if there new data available. The readinto() will return None if there is no data available, or 0 if the socket is closed
                # Only read a maximum of as many bytes as will fit into the InBuffer or the ReadBuffer
                data = self.sock.readinto(self.ReadBufferMV, min(self.ReadBufferSize, InBufferBytesAvailable))

                if data is not None:
                    # Keep track of how many bytes of the current file we have read.
                    # We will need this if the user pauses for too long and we need to request the current track from the server again
                    self.current_track_bytes_read += data
                    self.InBuffer.write(self.ReadBufferMV[0:data])
                    # print("Read:", data, self.ParseBuffer.any() )

                    # Start the decode loop once we have about 4kB in the InBuffer. No point starting decoding too early or the decoder can fail with insufficient data
                    if self.InBuffer.any() > 4096:
                        self.DecodeLoopRunning = True
                else:
                    pass

                # Have we read to the end of the track?
                if self.current_track_bytes_read == self.TrackInfo[-1][0]:
                    self.read_phase = read_phase_end

                # Peer closed socket. This is usually because we are in a long pause, and our socket closes
                if data == 0:
                    print("Peer close")
                    # Note: The exception raised below will be caught by the 'except' below
                    raise RuntimeError("Peer closed socket")

            except Exception as e:
                # The user probably paused too long and the underlying socket got closed
                # In this case we re-start playing the current track at the offset that we got up to before the pause. Uses the HTTP Range header to request data at an offset
                print("Socket Exception:", e, " Restarting track at offset", self.current_track_bytes_read)

                # Start reading the current track again, but at the offset where we were up to
                self.start_track(self.current_track_bytes_read)

    @micropython.native
    def decode_chunk(self, timeout=10):
        TimeStart = time.ticks_ms()
        break_reason = 0
        break_reasons = {
            0: "Unknown",
            1: "Out Buffer Full",
            2: "Timeout",
            3: "InBuffer Dry",
            4: "Finished Decoding",
            5: "No Track Info",
            6: "Decoder Dry",
        }

        # No data to decode
        if (
            self.InBuffer.any() == 0 and self.AACDecoder.write_used() == 0
        ):  # There could still be data in the decoder, so an empty inbuffer doesn't mean we have no data to decode => check both
            # return self.OutBuffer.buffer_level()
            return self.OutBuffer.any()

        if self.decode_phase == decode_phase_trackstart:
            # We're at the start of a new track.
            # temp - move back into IF below when you figure out how to remove ID3 tags
            self.hash_being_decoded = self.decode_stack.pop(0)
            self.DEBUG and print(f"Track {self.hash_being_decoded} decode start")
            self.callbacks["messages"](f"decode_chunk: Start decoding track {self.hash_being_decoded}")
            self.current_track_bytes_decoded_out = 0

            # Work out the size of the ID3 tag (if any) at the beginning
            """if self.ID3Tag_size == 0:
                print(f"Track {self.current_track} decode start")
                self.current_track_bytes_parsed_in = 0
                self.current_track_bytes_decoded_out = 0
                readpos = self.InBuffer.get_readPos()

                # If there is an ID3 tag at the beginning then work out the size
                if (
                    self.InBuffer.Bytes[readpos] == ord(b"I")
                    and self.InBuffer.Bytes[readpos + 1] == ord(b"D")
                    and self.InBuffer.Bytes[readpos + 2] == ord(b"3")
                ):
                    self.ID3Tag_size = 0

                    for i in range(4):
                        self.ID3Tag_size += self.InBuffer.Bytes[readpos + i + 6] << (3 - i) * 7

                    self.ID3Tag_size = self.ID3Tag_size + 10
                    print(f"ID3 tag size: {self.ID3Tag_size}")

            # Skip past the tag. There may not be enough bytes in the InBuffer to skip all of the tag
            bytesToSkip = min(self.ID3Tag_size, self.InBuffer.get_read_available())
            print(f"Skipping {bytesToSkip} bytes")
            self.InBuffer.bytes_wasRead(bytesToSkip)
            self.current_track_bytes_parsed_in += bytesToSkip
            self.ID3Tag_size = self.ID3Tag_size - bytesToSkip

            # There are not enough bytes in the buffer to skip all of them. Catch them next time we enter audio_pump
            if self.ID3Tag_size > 0:
                #return self.OutBuffer.buffer_level()
                return self.OutBuffer.any()
            else:
                self.decode_phase = decode_phase_inheader"""
            self.decode_phase = decode_phase_inheader

        if self.decode_phase == decode_phase_inheader:
            # De-allocate buffers from previous decoder instances
            # self.MP3Decoder.MP3_Close()
            # self.VorbisDecoder.Vorbis_Close()
            self.AACDecoder.AAC_Close()

            # Init (allocate memory) and Start (look for sync word) the correct decoder
            if self.TrackInfo[0][1] == format_AAC:

                if self.AACDecoder.AAC_Init():
                    self.DEBUG and print("AAC decoder Init success")
                else:
                    raise RuntimeError("AAC decoder Init failed")

                bytesToRead = min(self.InBuffer.any(), self.AACDecoder.write_free())
                self.DEBUG and print(f"Decoder free:{self.AACDecoder.write_free()} InBuffer:{self.InBuffer.any()}")

                # Parse the first part of the track if there is enough space to write to the decoder.
                while self.AACDecoder.write_free() >= 188 and self.InBuffer.any() >= 188:
                    # Parse the .ts file in 188 byte chunks. Do this here rather than in the read loop as when the player is running it should only do a few parses here,
                    # whereas if we do it while reading it will parse a big chunk, affecting responsiveness
                    # self.DEBUG and print("Parsing:", end="")

                    self.InBuffer.readinto(self.ParserInMV, 188)
                    parsedLength = self.TSParser.parse_packet(self.ParserInMV, self.ParserOutMV)
                    self.current_track_bytes_parsed_in += 188

                    # Write the parsed data to the decoder
                    if parsedLength > 0:
                        assert self.AACDecoder.write(self.ParserOutMV, parsedLength) == parsedLength
                        self.current_track_bytes_parsed_out += parsedLength

                    # self.DEBUG and print("Parsed:", parsedLength, self.current_track_bytes_parsed_in, self.current_track_bytes_parsed_out)

                    # Just read the first few packets here - enough to get the sync word
                    if self.current_track_bytes_parsed_out >= 512:
                        break

                FoundSyncWordAt = self.AACDecoder.AAC_Start()

            if FoundSyncWordAt >= 0:
                self.DEBUG and print("Decoder Start success. Sync word at", FoundSyncWordAt)

                # If the sync word is not at zero for whatever reason, discard the bytes before it
                self.InBuffer.read(FoundSyncWordAt)  # Look at this later, don't think it will work
                self.decode_phase = decode_phase_readinfo
            else:
                raise RuntimeError("Decoder Start failed")

        # Just for debugging. See how many times we run the loop before timeout
        counter = 0

        while True:
            # As we call this from start_track() we can get here before the TrackInfo is populated, so just exit in that case
            # We should see this at the beginning of the first track, but not between tracks
            if len(self.TrackInfo) == 0:
                break_reason = 5
                break

            # Do we have at least 8192 bytes available for the decoder to write to? If not we return and wait for the play loop to free up some space.
            # 8192 comes from the max number of samples returned from decoding a chunk being 2048 samples x 2 bytes per 16-bit sample x 2 channels = 8192 bytes
            # if self.OutBuffer.get_write_available() < 5000:  # Note: this can change write_pos
            if (self.OutBufferSize - self.OutBuffer.any()) < 8192:
                break_reason = 1
                break

            # Don't stay in the loop too long or we affect the responsiveness of the main app
            if time.ticks_diff(time.ticks_ms(), TimeStart) > timeout:
                break_reason = 2
                break

            counter += 1

            pos = self.InBuffer.any()

            # print(f"Decoding: {pos}", end=' ')
            ts = time.ticks_ms()

            ### AAC ###
            if self.TrackInfo[0][1] == format_AAC:

                while self.AACDecoder.write_free() >= 188 and self.InBuffer.any() >= 188:

                    # Parse the .ts file in 188 byte chunks. Do this here rather than in the read loop as when the player is running it should only do a few parses here,
                    # whereas if we do it while reading it will parse a big chunk, affecting responsiveness
                    # print("Parsing:", end='')

                    self.InBuffer.readinto(self.ParserInMV, 188)
                    parsedLength = self.TSParser.parse_packet(self.ParserInMV, self.ParserOutMV)
                    self.current_track_bytes_parsed_in += 188

                    # Write the parsed data to the decoder
                    if parsedLength > 0:
                        assert self.AACDecoder.write(self.ParserOutMV, parsedLength) == parsedLength
                        self.current_track_bytes_parsed_out += parsedLength

                    # self.DEBUG and print("Parsed:", parsedLength, self.current_track_bytes_parsed_in, self.current_track_bytes_parsed_out)

                    if len(self.TrackInfo) > 0:
                        # Have we finished parsing this track?
                        if self.current_track_bytes_parsed_in == self.TrackInfo[0][0]:
                            print("Finished Parsing")
                            print(f"TrackInfo: {self.TrackInfo}")
                            print(f"DecodeInfo: {self.DecodeInfo}")
                            self.DecodeInfo.append(0)
                            self.DecodeInfo[-1] = self.current_track_bytes_parsed_out
                            self.current_track_bytes_parsed_out = 0
                            self.current_track_bytes_parsed_in = 0
                            self.TSParser.reset()
                            break
                        elif self.current_track_bytes_parsed_in > self.TrackInfo[0][0]:  # This should never happen
                            print(f"Bytes parsed > track length! {self.current_track_bytes_parsed_in} > {self.TrackInfo[0][0]}")
                            print(f"TrackInfo: {self.TrackInfo}")
                            print(f"DecodeInfo: {self.DecodeInfo}")
                            raise RuntimeError("Bytes parsed > track length")  # temporary, for debugging

                if self.AACDecoder.write_used() == 0:
                    break_reason = 3
                    break

                # Decode the data in the decoder
                # t1 = time.ticks_ms()
                Result, BytesDecoded, AudioSamples, BiB = self.AACDecoder.AAC_Decode()
                # t2 = time.ticks_ms()
                # print(time.ticks_diff(t2, t1))
                # print(f"Decoded: {BytesDecoded}. Ret:{Result}. Samples:{AudioSamples}. BiB: {BiB}. Total:{self.current_track_bytes_decoder_in}")

                if Result == 0 or Result == 100 or Result == 110:
                    self.current_track_bytes_decoder_in += BytesDecoded

                    if Result == 0 or Result == 110:
                        self.current_track_bytes_decoded_out += AudioSamples * 2

                        # Read the decoded data from the decoder and write it into the OutBuffer
                        self.OutBuffer.write(self.AudioBufferMV, self.AACDecoder.readinto(self.AudioBufferMV, AudioSamples * 2))

                # We get this if there is not enough data in the decoder to decode the next packet, so we need to wait until the readloop gets some more data
                elif Result == -13:
                    break_reason = 6
                    break

                # We have a corrupted packet
                elif Result == -6:
                    # print(pos, end=":")
                    # print(self.InBuffer.Buffer[pos:].hex())

                    # Not sure what we should do here. Maybe we could handle it?
                    # print("Corrupted packet")
                    raise RuntimeError("Corrupted packet")
                    # pass

                else:
                    print("Decode Packet failed. Error:", Result)
                    # print(pos, end=":")
                    # print(self.InBuffer.Buffer[pos:].hex())
                    raise RuntimeError("Decode Packet failed")

                # If we're at the beginning of the track, get info about this stream
                if self.decode_phase == decode_phase_readinfo:
                    channels, sample_rate, bits_per_sample, bit_rate = self.AACDecoder.AAC_GetInfo()

            # Make sure we got valid data back from GetInfo()
            if self.decode_phase == decode_phase_readinfo and channels != 0:
                self.DEBUG and print("Channels:", channels)
                self.DEBUG and print("Sample Rate:", sample_rate)
                self.DEBUG and print("Bits per Sample:", bits_per_sample)
                self.DEBUG and print("Bitrate:", bit_rate)

                # Store the track info so that the play loop can init the I2S device at the beginning of the track
                self.PlayInfo.append((channels, sample_rate, bits_per_sample))
                self.decode_phase = decode_phase_decoding

            # Check if we have a parsed length of the track (only populated when we have finished parsing the track) and if so, have we decoded to the end of the current track?
            if len(self.DecodeInfo) > 0:
                if self.current_track_bytes_decoder_in == self.DecodeInfo[0]:  # We have finished decoding the current track.
                    self.DEBUG and print(f"Track decode end")
                    self.callbacks["messages"](f"decode_chunk: Finished decoding track {self.hash_being_decoded}")
                    self.TrackInfo.pop(0)
                    self.current_track_bytes_decoder_in = 0

                    # Save the length of decoded audio for this track. Play_chunk() will check this to re-init the I2S device at the right spot (required in case the bitrate changes between songs)
                    self.PlayLength.append(self.current_track_bytes_decoded_out)
                    self.DecodeInfo.pop(0)

                    if self.InBuffer.any() > 0:  # if len(self.playlist) > 0:
                        self.decode_phase = decode_phase_trackstart

                    # We have finished decoding the whole playlist. Now we just need to wait for the play loop to run out
                    else:
                        if len(self.playlist) > 0:
                            raise RuntimeError("Finished decoding the playlist -- but playlist is not empty")
                        self.DEBUG and print("Finished decoding playlist")
                        self.callbacks["messages"](f"decode_chunk: Finished decoding playlist")
                        self.DecodeLoopRunning = False

                        # This frees up all the buffers that the decoders allocated, and resets their state
                        # self.MP3Decoder.MP3_Close()
                        # self.VorbisDecoder.Vorbis_Close()
                        self.AACDecoder.AAC_Close()
                        # Don't call stop() here or the end of the song will be cut off
                    break

            # If we have more than 1 second of output samples buffered (2 channels, 2 bytes per sample), start playing them.
            # Don't check self.OutBuffer.get_read_available here
            # if self.PlayLoopRunning == False and self.OutBuffer.get_bytes_in_buffer() / 44100 / 2 / 2 > 1:
            if not self.PlayLoopRunning and self.OutBuffer.any() / 44100 / 2 / 2 > 1:
                self.DEBUG and print("************ Initiate Play Loop ************")

                # Start the playback loop by playing the first chunk
                self.I2SAvailable = True
                self.PlayLoopRunning = True  # So that we don't call this again
                self.play_chunk()

        if (self.DEBUG > 1) and ((counter > 0) or (break_reason != 1)):
            print(f"Time {time.ticks_ms()}. Decoded {counter} chunks in ", end="")
            print(f"{time.ticks_diff(time.ticks_ms(), TimeStart)} ms. {break_reasons[break_reason]}", end="")
            if self.consecutive_zeros > 0:
                print(f" after {self.consecutive_zeros} Buffer Fulls")
                self.consecutive_zeros = 0
            else:
                print("")
        else:
            self.consecutive_zeros += 1

        # return self.OutBuffer.buffer_level()
        return self.OutBuffer.any()

    @micropython.native
    def play_chunk(self):
        if not self.PlayLoopRunning or (self.PLAY_STATE != play_state_Playing) or (not self.I2SAvailable):
            return

        self.I2SAvailable = False

        # Are we at the beginning of a track, and the decoder has given us some format info. If so, init the I2S device (Note that the sample_rate may vary between tracks)
        if self.current_track_bytes_played == 0 and len(self.PlayInfo) > 0:
            self.hash_being_played = self.play_stack.pop(0)
            self.callbacks["messages"](f"play_chunk: Start playing track {self.hash_being_played}")
            self.DEBUG and print("Track play start")

            # The I2S object returns the following: I2S(id=0, sck=13, ws=14, sd=17, mode=5, bits=16, format=1, rate=44100, ibuf=71680)
            # Check if it is the same as the already initialised device. If so, do nothing. If not, init it to the new values
            current_bits = int(str(self.audio_out).split(",")[5].split("=")[1])
            current_channels = 2 if int(str(self.audio_out).split(",")[6].split("=")[1]) == I2S.STEREO else 1
            current_rate = int(str(self.audio_out).split(",")[7].split("=")[1])

            # PlayInfo[] has channels, sample_rate, bits_per_sample
            if (
                current_bits != self.PlayInfo[0][2]
                or current_channels != self.PlayInfo[0][0]
                or current_rate != self.PlayInfo[0][1]
            ):
                print(
                    f"Init I2S device. Bits:{self.PlayInfo[0][2]}, Channels:{self.PlayInfo[0][0]}, Rate:{self.PlayInfo[0][1]}"
                )
                self.audio_out.init(
                    sck=sck_pin,
                    ws=ws_pin,
                    sd=sd_pin,
                    mode=I2S.TX,
                    bits=self.PlayInfo[0][2],
                    format=I2S.STEREO if self.PlayInfo[0][0] == 2 else I2S.MONO,
                    rate=self.PlayInfo[0][1],
                    ibuf=self.ChunkSize,
                )

                # Make the I2S device asyncronous by defining a callback
                self.audio_out.irq(self.i2s_callback)

            # Remove the info for this track
            self.PlayInfo.pop(0)

        # Play what we have, up to the chunk size
        BytesToPlay = min(self.OutBuffer.any(), self.ChunkSize)

        # Do we have a length for this track yet? (We only get this after the decoder has finished decoding it)
        if len(self.PlayLength) > 0:
            # If so, have we played all of the decoded bytes for this track?
            if self.current_track_bytes_played + BytesToPlay >= self.PlayLength[0]:
                self.DEBUG and print("Track play end")
                self.callbacks["messages"](f"play_chunk: Finished playing track {self.hash_being_played}")
                # Play the remaining bytes for this track, and remove the info for this track
                BytesToPlay = self.PlayLength[0] - self.current_track_bytes_played
                self.PlayLength.pop(0)

                # Need to check both whether the decode loop is running AND whether we have some PlayLength info
                # We can't just check whether the decode loop is running, as the decode loop can finish with 2 or more tracks still to play
                # We can't check just whether we have some PlayLength info, as at the beginning of the tracklist the decode loop might only be half way through decoding track 2 when track 1 finishes playing
                # So, the double-check here catches the edge case at the beginning AND at the end of the playlist
                if not self.DecodeLoopRunning and len(self.PlayLength) == 0:
                    self.PlayLoopRunning = False
                    self.DEBUG and print("Finished playing playlist")
                    self.callbacks["messages"]("play_chunk: Finished playing playlist")
                    # Don't stop() here as we need to let the play loop run out

                # Add the negative so that when the BytesToPlay gets added at the end of this function that current_track_bytes_played will then be zero
                self.current_track_bytes_played = -BytesToPlay

                # We have a zero length track, so we don't need to play anything
                if BytesToPlay == 0:
                    self.I2SAvailable = True
                    return

        # We can get zero bytes to play if the buffer is starved
        if BytesToPlay == 0:
            # The output buffer can get starved if the network is slow,
            # or if we slow the decoding loop too much (e.g. by writing too much debug output)
            print("Play buffer starved")

            # Clear this flag to let the decoder re-start the playback loop when the decoder has generated enough data
            self.PlayLoopRunning = False

            self.I2SAvailable = True
            return

        self.OutBuffer.readinto(self.ChunkBufferMV, BytesToPlay)
        outbytes = memoryview(self.ChunkBufferMV[0:BytesToPlay])

        # Set the volume
        self.audio_out.shift(buf=outbytes, bits=16, shift=self.volume)

        # Write the PCM data to the I2S device. Returns straight away
        numout = self.audio_out.write(outbytes)

        assert numout == BytesToPlay, "I2S write error"

        self.current_track_bytes_played += BytesToPlay

        # If this is the last chunk of the playlist, let the I2S DMA run out and then stop() so that the screensaver works properly
        if not self.PlayLoopRunning:
            # 1500ms is enough for one chunk to play
            time.sleep_ms(1500)
            self.stop()

    @micropython.native
    def i2s_callback(self, t):
        self.I2SAvailable = True

    ###############################################################################################################################################

    @micropython.native
    def audio_pump(self):
        return 5000

    def do_pump(self, _):
        self.pumptimer.deinit()

        buffer_level_in = self.InBuffer.any()
        buffer_level_out = self.OutBuffer.any()

        # if self.is_stopped():
        #    return min(buffer_level_in, buffer_level_out)

        # Read the next chunk of audio data
        if self.ReadLoopRunning:
            self.read_chunk()

        # Decode the next chunk of audio data
        if self.DecodeLoopRunning:
            buffer_level_out = self.decode_chunk()

        # Play the next chunk of audio data
        if self.PlayLoopRunning:
            self.play_chunk()

        buffer_level_in = self.InBuffer.any()

        self.pumptimer.init(period=10, mode=Timer.PERIODIC, callback=self.do_pump)

    def start_timer(self):
        self.pumptimer = Timer(0)
        self.pumptimer.init(period=10, mode=Timer.PERIODIC, callback=self.do_pump)
