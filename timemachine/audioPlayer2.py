"""
litestream
Copyright (C) 2025  spertilo.net

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

import socket, time, gc
from machine import Pin, I2S, Timer
import micropython
import time
from errno import EINPROGRESS
import select
import ssl

try:
    import AudioDecoder
except ImportError:
    import AACDecoder

if not "AAC_Decoder" in dir(AudioDecoder):
    raise ImportError("Firmware is out of date")

# Constants
format_MP3 = const(0)
format_Vorbis = const(1)
format_AAC = const(2)

read_phase_idle = const(0)
read_phase_start = const(1)
read_phase_read = const(2)
read_phase_end = const(3)

decode_phase_idle = const(0)
decode_phase_trackstart = const(1)
decode_phase_readinfo = const(2)
decode_phase_decoding = const(3)

play_phase_idle = const(0)
play_phase_start = const(1)
play_phase_playing = const(2)
play_phase_end = const(3)

audioplayer_state_Stopped = const(0)
audioplayer_state_Playing = const(1)
audioplayer_state_Paused = const(2)

sck_pin = Pin(13)  # Serial clock output
ws_pin = Pin(14)  # Word clock output
sd_pin = Pin(17)  # Serial data output
mute_pin = Pin(3, Pin.OUT, value=1)  # XSMT on DAC chip


@micropython.native
class TSPacketParser:
    TS_PACKET_SIZE = 188
    PAYLOAD_SIZE = 184

    def __init__(self, log_func=None):
        self.log_func = log_func
        self.pmt_pids = []
        self.pes_data_length = None
        self.aac_pid = None

    def log(self, msg):
        if self.log_func:
            self.log_func(msg)

    def reset(self):
        self.log("Parser reset")
        self.pmt_pids = []
        self.pes_data_length = None
        self.aac_pid = None

    def parse_packet(self, packet, output_buffer):
        if packet is None or output_buffer is None:
            self.reset()
            return 0

        if len(packet) != self.TS_PACKET_SIZE or len(output_buffer) < self.TS_PACKET_SIZE:
            self.log("Input packet must be 188 bytes, output buffer must be at least 188 bytes")
            return 0

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

        pls = 4

        if afc & 0x2:
            adaptation_field_length = packet[pls]
            self.log(f"Adaptation Field Length: {adaptation_field_length}")
            pls += 1 + adaptation_field_length

        if pls >= self.TS_PACKET_SIZE:
            self.log("Index exceeds packet size after adaptation field")
            return 0

        if pusi:
            if pid == 0x0000 or pid in self.pmt_pids:
                pointer_field = packet[pls]
                self.log(f"Pointer Field: {pointer_field}")
                pls += 1 + pointer_field
            else:
                self.log("PUSI set in PES packet, payload starts immediately")

        if pls >= self.TS_PACKET_SIZE:
            self.log("Index exceeds packet size after PUSI handling")
            return 0

        self.log(f"Index after adjustments: {pls}")

        if pid == 0x0000:
            self.process_pat(packet, pls)
        elif pid in self.pmt_pids:
            self.process_pmt(packet, pls)
        elif pid == self.aac_pid:
            return self.process_aac(packet, pls, output_buffer, pusi)
        else:
            self.log(f"Unhandled PID: 0x{pid:04X}")
            return 0

        return 0

    def process_pat(self, packet, index):
        self.log("Processing PAT")
        if index + 3 >= self.TS_PACKET_SIZE:
            self.log("Not enough data for PAT header")
            return

        section_length = ((packet[index + 1] & 0x0F) << 8) | packet[index + 2]
        self.log(f"Section Length: {section_length}")

        end_index = index + 3 + section_length - 4
        index += 8

        while index + 3 <= end_index and index + 3 < self.TS_PACKET_SIZE:
            program_number = (packet[index] << 8) | packet[index + 1]
            program_map_pid = ((packet[index + 2] & 0x1F) << 8) | packet[index + 3]
            self.log(f"Program Number: {program_number}, PMT PID: 0x{program_map_pid:04X}")

            if program_number != 0:
                if program_map_pid not in self.pmt_pids:
                    self.pmt_pids.append(program_map_pid)

            index += 4

    def process_pmt(self, packet, index):
        self.log("Processing PMT")
        if index + 11 >= self.TS_PACKET_SIZE:
            self.log("Not enough data for PMT header")
            return

        section_length = ((packet[index + 1] & 0x0F) << 8) | packet[index + 2]
        program_info_length = ((packet[index + 10] & 0x0F) << 8) | packet[index + 11]
        self.log(f"Section Length: {section_length}")
        self.log(f"Program Info Length: {program_info_length}")

        index += 12 + program_info_length
        end_index = index + section_length - program_info_length - 13

        while index + 4 <= end_index and index + 4 < self.TS_PACKET_SIZE:
            stream_type = packet[index]
            elementary_pid = ((packet[index + 1] & 0x1F) << 8) | packet[index + 2]
            es_info_length = ((packet[index + 3] & 0x0F) << 8) | packet[index + 4]
            self.log(f"Stream Type: 0x{stream_type:02X}, Elementary PID: 0x{elementary_pid:04X}")

            if stream_type in (0x0F, 0x11):
                self.log("AAC PID found")
                self.aac_pid = elementary_pid

            index += 5 + es_info_length

    def process_aac(self, packet, index, output_buffer, pusi):
        self.log(f"Processing AAC data at index {index}")

        if pusi:
            if index + 3 > len(packet):
                self.log("Not enough data to check PES start code")
                return 0

            if packet[index : index + 3] == b"\x00\x00\x01":
                stream_id = packet[index + 3]
                self.log(f"Stream ID: 0x{stream_id:02X}")

                if 0xC0 <= stream_id <= 0xDF:
                    pes_packet_length = (packet[index + 4] << 8) | packet[index + 5]
                    pes_header_data_length = packet[index + 8]
                    start_of_data = index + 9 + pes_header_data_length

                    if start_of_data >= len(packet):
                        self.log("Not enough data for PES payload")
                        self.pes_data_length = None
                        return 0

                    payload = packet[start_of_data:]
                    if len(payload) >= 3 and payload[0:3] == b"ID3":
                        self.log("ID3 tag detected in PES payload")
                        id3_size = self.parse_id3_tag(payload)
                        if id3_size < 0:
                            self.log("Invalid ID3 tag size")
                            return 0
                        start_of_data += id3_size
                        if start_of_data >= len(packet):
                            self.log("No AAC data after ID3 tag")
                            return 0
                        payload = packet[start_of_data:]
                    else:
                        self.log("No ID3 tag detected")

                    if pes_packet_length != 0:
                        self.pes_data_length = pes_packet_length - (start_of_data - index - 6)
                    else:
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
        if len(data) < 10:
            self.log("ID3 tag too short to parse header")
            return -1

        if data[0:3].tobytes() != b"ID3":
            self.log("ID3 tag identifier not found")
            return -1

        id3_size_bytes = data[6:10]
        id3_size = self.synchsafe_to_int(id3_size_bytes)
        self.log(f"ID3 tag size: {id3_size} bytes")

        total_id3_size = 10 + id3_size
        return total_id3_size

    def synchsafe_to_int(self, data):
        value = 0
        for byte in data:
            value = (value << 7) | (byte & 0x7F)
        return value


class TrackReader:
    def __init__(self, context, callbacks, debug=0):
        self.context = context
        self.callbacks = callbacks
        self.DEBUG = debug
        self.sock = None

        # A buffer used to read data from the network. 16kB matches the size of the WiFi buffer
        self.ReadBufferSize = 16 * 1024
        self.ReadBufferBytes = bytearray(self.ReadBufferSize)
        self.ReadBufferMV = memoryview(self.ReadBufferBytes)

        self.reset()

    def reset(self):
        self.trackReader = self.start_track()

        self.read_phase = read_phase_idle
        self.TrackLength = 0
        self.hash_being_read = None

        if self.sock is not None:
            self.sock.close()
            self.sock = None

        # The number of bytes of the current track that we have read from the network
        # This is compared against the length of the track returned from the server in the Content-Range or content-length header to determine end-of-track read
        # This is potentially different to which track we are currently playing. We could be reading ahead of decoding and playing by one or more tracks
        self.current_track_bytes_read = 0

    def start(self):
        self.read_phase = read_phase_start

    def isRunning(self):
        return self.read_phase != read_phase_idle

    def read_chunk(self):
        if self.read_phase == read_phase_idle:
            return

        elif self.read_phase == read_phase_start:
            # if len(self.context.playlist) == 0:
            #    return

            try:
                next(self.trackReader)
            except StopIteration:
                pass

        # Have we read to the end of the track?
        elif self.read_phase == read_phase_end:
            self.end_track()

        elif self.read_phase == read_phase_read:
            # If there is no socket then we have already read to the end of the playlist
            if self.sock is None:
                return 0

            # If no free space in the input buffer return, otherwise add any data available from the network
            if (InBufferBytesAvailable := self.context.InBufferSize - self.context.InBuffer.any()) == 0:
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
                    self.context.InBuffer.write(self.ReadBufferMV[0:data])

                # Have we read to the end of the track?
                if self.current_track_bytes_read == self.TrackLength:  # self.context.TrackInfo[-1][0]:
                    self.read_phase = read_phase_end

                # Peer closed socket. This is usually because we are in a long pause, and our socket closes
                if data == 0:
                    print("Peer close")
                    raise RuntimeError("Peer closed socket")

            # The user probably paused too long and the underlying socket got closed
            # In this case we re-start playing the current track at the offset that we got up to before the pause. Uses the HTTP Range header to request data at an offset
            except Exception as e:
                print("Socket Exception:", e, " Restarting track at offset", self.current_track_bytes_read)
                self.callbacks["messages"](f"read_chunk: long pause {self.hash_being_read}")

                # Start reading the current track again, but at the offset where we were up to
                # self.start_track(self.current_track_bytes_read)

    def end_track(self):
        # self.DEBUG and print(f"Bytes read: {self.current_track_bytes_read}")
        print(f"Track {self.hash_being_read} read end", end=" - ")
        gc.collect()

        if len(self.context.playlist) > 0:
            # We can read the header of the next track now
            print("reading next track")
            self.callbacks["messages"](f"read_chunk: Finished reading track {self.hash_being_read}")
            self.read_phase = read_phase_start
            self.trackReader = self.start_track()
        else:
            # We have no more data to read from the network, but we have to let the decoder run out, and then let the play loop run out
            print("finished reading playlist")
            self.callbacks["messages"](f"read_chunk: Finished reading playlist")
            self.sock.close()
            self.sock = None
            self.read_phase = read_phase_idle

    def start_track(self, offset=0):
        track_length = 0
        self.current_track_bytes_read = offset

        url, hash = self.context.playlist.pop(0)
        self.hash_being_read = hash
        host, port, path = self.parse_url(url.encode())

        # We might have a socket already from the previous track
        if self.sock:
            self.sock.close()
            self.sock = None

        print(f"Track {self.hash_being_read} read start")
        self.callbacks["messages"](f"read_chunk: Start reading track {self.hash_being_read}")

        while True:
            # Load up the output buffer before the expensive SSL connect
            for _ in range(5):
                yield

            # Establish a socket connection to the server
            conn = socket.socket()

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
            # We keep looping and yielding until all the data has been sent (which is after the SSL handshake is complete)
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

            # Did we get a redirect? If so, we need to re-connect to the new host and port
            if b"HTTP/1.1 301" in response_headers or b"HTTP/1.1 302" in response_headers:
                print("Redirect", end=" - ")
                self.sock.close()
                del self.sock
                self.sock = None
                redirect_location = None

                for line in response_headers.split(b"\r\n"):
                    if line.startswith(b"Location:"):
                        redirect_location = line.split(b": ", 1)[1]
                        break

                if redirect_location:
                    # Extract the new host, port, and path from the redirect location
                    host, port, path = self.parse_url(redirect_location)
                    assert port > 0, "Invalid URL prefix"
            else:
                break

        # Make sure we know the length of the track and got a valid response from the server. If not, skip this track.
        if track_length == 0 or (b"HTTP/1.1 200" not in response_headers and b"HTTP/1.1 206" not in response_headers):
            print("Bad URL:", url)
            print("Headers:", response_headers)
            print("TrackLength:", track_length)
            self.current_track_bytes_read = 0
            self.read_phase = read_phase_end
            return

        # Store the end-of-track and format marker for this track (except if we are restarting a track)
        if offset == 0:
            if path.lower().endswith(".ts") or path.lower().endswith(".aac"):
                self.context.decoder.Add_to_Decode_List(track_length, format_AAC, hash)
            else:
                raise RuntimeError("Unsupported audio type")

        # Now we can start reading the track
        self.DEBUG and print("Track length:", track_length)
        self.TrackLength = track_length
        self.read_phase = read_phase_read

    def parse_url(self, location):
        parts = location.decode().split("://", 1)
        port = 80 if parts[0] == "http" else 443 if parts[0] == "https" else 0
        url = parts[1].split("/", 1)
        host = url[0]
        path = url[1] if url[1].startswith("/") else "/" + url[1]
        return host, port, path


@micropython.native
class TrackDecoder:
    def __init__(self, context, callbacks, debug=0):
        self.context = context
        self.callbacks = callbacks
        self.DEBUG = debug
        self.AACDecoder = AudioDecoder.AAC_Decoder()
        self.TSParser = TSPacketParser()
        self.ParserInBytes = bytearray(188)
        self.ParserInMV = memoryview(self.ParserInBytes)
        self.ParserOutBytes = bytearray(188)
        self.ParserOutMV = memoryview(self.ParserOutBytes)

        # A buffer used to store decoded audio data, allowing us to adjust volume,  before writing it to the OutBuffer
        self.AudioBufferSize = 4 * 1024
        self.AudioBufferBytes = bytearray(self.AudioBufferSize)
        self.AudioBufferMV = memoryview(self.AudioBufferBytes)
        self.reset()

    def reset(self):
        self.decode_phase = decode_phase_idle

        # The number of bytes the decoder has read from the parser for this track
        self.current_track_bytes_decoder_in = 0

        # The number of bytes of decoded audio data the decoder has written to the OutBuffer for this track
        self.current_track_bytes_decoder_out = 0

        # The number of bytes the parser has read from the input buffer for this track. Used to detect the end of track by the decoder
        self.current_track_bytes_parsed_in = 0

        # The number of bytes that the parser has parsed for this track
        self.current_track_bytes_parsed_out = 0

        # DecodeInfo is a list of track lengths and their corresponding audio type (vorbis or MP3).
        # This tells the decoder when to move onto the next track, and also which decoder to use.
        self.DecodeInfo = []

        # Clear any data that has already been sent to the decoder
        self.AACDecoder.close()

        # ParsedDecodeInfo contains the length of the parsed data for the decoder to decode. It is different to DecodeInfo as a .ts file
        # will have more bytes to read than there is audio data to decode
        self.ParsedDecodeInfo = []

        # We don't want the parser running in the gap between finishing parsing a track and finishing decoding a track
        self.ParserRunning = False

        self.TSParser.reset()

        # Used for statistics during debugging
        self.consecutive_zeros = 0

    def Add_to_Decode_List(self, TrackLength, TrackType, hash):
        self.DecodeInfo.append((TrackLength, TrackType, hash))

    def isRunning(self):
        return self.decode_phase != decode_phase_idle

    def start(self):
        self.decode_phase = decode_phase_trackstart

    def decode_chunk(self, timeout=10):
        if self.decode_phase == decode_phase_idle:
            return self.context.OutBuffer.any()

        # There could still be data in the decoder, so an empty inbuffer doesn't mean we have no data to decode => check both
        if self.context.InBuffer.any() == 0 and self.AACDecoder.write_used() == 0:
            # print("Decoder starved")
            return self.context.OutBuffer.any()

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

        # This phase looks for the sync word in the parsed data
        if self.decode_phase == decode_phase_trackstart:
            # Ensure DecodeInfo is not empty
            if not self.DecodeInfo:
                print("Warning: DecodeInfo is empty during trackstart phase")
                self.callbacks["messages"]("decode_chunk: Decode error")
                self.decode_phase = decode_phase_idle
                return self.context.OutBuffer.any()

            print(f"Track {self.DecodeInfo[0][2]} decode start")
            self.callbacks["messages"](f"decode_chunk: Start decoding track {self.DecodeInfo[0][2]}")

            if self.DecodeInfo[0][1] == format_AAC:
                # De-allocate buffers from previous decoder instances
                self.AACDecoder.AAC_Close()

                # Init (allocate memory) and Start (look for sync word) the correct decoder
                if self.AACDecoder.AAC_Init():
                    self.DEBUG and print("AAC decoder Init success")
                else:
                    raise RuntimeError("AAC decoder Init failed")

                self.current_track_bytes_decoder_in = 0
                self.current_track_bytes_decoder_out = 0
                self.current_track_bytes_parsed_in = 0
                self.current_track_bytes_parsed_out = 0
                self.TSParser.reset()
                self.ParserRunning = True

                # Parse the .ts file in 188 byte chunks if there is enough space to write to the decoder until we see the sync word
                while self.AACDecoder.write_free() >= 188 and self.context.InBuffer.any() >= 188:
                    # Read the data from the InBuffer into the parser
                    self.context.InBuffer.readinto(self.ParserInMV, 188)
                    parsedLength = self.TSParser.parse_packet(self.ParserInMV, self.ParserOutMV)
                    self.current_track_bytes_parsed_in += 188

                    # There are some tracks that don't have valid data. If we get to the end of the track without finding the sync work, skip this track
                    if self.current_track_bytes_parsed_in >= self.DecodeInfo[0][0]:
                        print(f"Track {self.DecodeInfo[0][2]} decode end - no Sync word")
                        self.callbacks["messages"](f"decode_chunk: Finished decoding track {self.DecodeInfo[0][2]}")
                        self.DecodeInfo.pop(0)
                        self.AACDecoder.close()  # Clear out any data that we already loaded into the decoder
                        self.decode_phase = decode_phase_trackstart

                        return self.context.OutBuffer.any()

                    # Write the parsed data to the decoder
                    if parsedLength > 0:
                        assert self.AACDecoder.write(self.ParserOutMV, parsedLength) == parsedLength
                        self.current_track_bytes_parsed_out += parsedLength

                    FoundSyncWordAt = self.AACDecoder.AAC_Start()

                    if FoundSyncWordAt >= 0:
                        self.DEBUG and print("Decoder Start success. Sync word at", FoundSyncWordAt)
                        # self.context.InBuffer.read(FoundSyncWordAt) # Look at this later, don't think it will work
                        self.decode_phase = decode_phase_readinfo
                        break
                    else:
                        pass  # No sync word yet, keep looking

        # This phase looks for the Track Info in the parsed data
        if self.decode_phase == decode_phase_readinfo:
            while self.AACDecoder.write_free() >= 188 and self.context.InBuffer.any() >= 188:
                # Read the data from the InBuffer into the parser
                self.context.InBuffer.readinto(self.ParserInMV, 188)
                parsedLength = self.TSParser.parse_packet(self.ParserInMV, self.ParserOutMV)
                self.current_track_bytes_parsed_in += 188

                # Sometimes we see a track with no audio data in it, just the Track Info. Skip this track
                if self.current_track_bytes_parsed_in == self.DecodeInfo[0][0]:
                    print(f"Track {self.DecodeInfo[0][2]} decode end - no Audio Data")
                    self.callbacks["messages"](f"decode_chunk: Finished decoding track {self.DecodeInfo[0][2]}")
                    self.DecodeInfo.pop(0)
                    self.AACDecoder.close()  # Clear out any data that we already loaded into the decoder
                    self.decode_phase = decode_phase_trackstart
                    break

                if parsedLength > 0:
                    assert self.AACDecoder.write(self.ParserOutMV, parsedLength) == parsedLength
                    self.current_track_bytes_parsed_out += parsedLength

                # Decode what we have so far
                Result, BytesDecoded, AudioSamples, BiB = self.AACDecoder.AAC_Decode()
                self.current_track_bytes_decoder_in += BytesDecoded

                # Try and read the track info
                channels, sample_rate, bits_per_sample, bit_rate = self.AACDecoder.AAC_GetInfo()

                # Make sure we got valid data back from GetInfo()
                print(f"Channels: {channels} Sample Rate: {sample_rate} Bits per Sample: {bits_per_sample} Bitrate: {bit_rate}")

                if channels != 0:
                    # We don't know the parsed track length yet, so set it to False at this point
                    self.ParsedDecodeInfo.append([False, format_AAC, self.DecodeInfo[0][2]])

                    # Store the track info so that the player can init the I2S device at the beginning of the track
                    self.context.player.Add_to_Play_List(channels, sample_rate, bits_per_sample, self.DecodeInfo[0][2])

                    self.decode_phase = decode_phase_decoding
                    break

        # This phase looks decodes the audio data in the parsed data
        if self.decode_phase == decode_phase_decoding:
            counter = 0  # For debugging. See how many times we run the loop before timeout

            # Keep decoding until timeout, end of playlist decoding, or error
            while True:
                # Do we have at least 8192 bytes available for the decoder to write to? If not we return and wait for the player to free up some space.
                # 8192 comes from the max number of samples returned from decoding a chunk being 2048 samples x 2 bytes per 16-bit sample x 2 channels = 8192 bytes
                if (self.context.OutBufferSize - self.context.OutBuffer.any()) < 8192:
                    break_reason = 1
                    break

                # Don't stay in the loop too long or we affect the responsiveness of the main app
                if time.ticks_diff(time.ticks_ms(), TimeStart) > timeout:
                    break_reason = 2
                    break

                counter += 1

                # Check if ParsedDecodeInfo is empty
                if not self.ParsedDecodeInfo:
                    print("Warning: ParsedDecodeInfo is empty during decoding")
                    break_reason = 5
                    break

                ### Decode AAC ###
                if self.ParsedDecodeInfo[0][1] == format_AAC:
                    # Parse the .ts file in 188 byte chunks until we have filled up the decoder or there is nothing left to parse
                    # Do this here rather than in the read loop as when the player is running it should only do a few parses here,
                    # whereas if we do it while reading it will parse a big chunk, affecting responsiveness
                    while self.ParserRunning and self.AACDecoder.write_free() >= 188 and self.context.InBuffer.any() >= 188:
                        self.context.InBuffer.readinto(self.ParserInMV, 188)
                        parsedLength = self.TSParser.parse_packet(self.ParserInMV, self.ParserOutMV)
                        self.current_track_bytes_parsed_in += 188

                        # Write the parsed data to the decoder
                        if parsedLength > 0:
                            assert self.AACDecoder.write(self.ParserOutMV, parsedLength) == parsedLength
                            self.current_track_bytes_parsed_out += parsedLength

                        if len(self.DecodeInfo) > 0:  # Do we need this check?
                            # Have we finished parsing this track? If so, update the parsed length
                            if self.current_track_bytes_parsed_in == self.DecodeInfo[0][0]:
                                # self.DEBUG and print("Finished Parsing")
                                self.ParsedDecodeInfo[-1][0] = self.current_track_bytes_parsed_out
                                self.current_track_bytes_parsed_out = 0
                                self.current_track_bytes_parsed_in = 0
                                self.TSParser.reset()
                                self.DecodeInfo.pop(0)
                                self.ParserRunning = False
                                break
                            elif self.current_track_bytes_parsed_in > self.DecodeInfo[0][0]:
                                print(
                                    f"Bytes parsed > track length! {self.current_track_bytes_parsed_in} > {self.DecodeInfo[0][0]}"
                                )
                                print(f"DecodeInfo: {self.DecodeInfo} ParsedDecodeInfo: {self.ParsedDecodeInfo}")
                                self.callbacks["messages"]("decode_chunk: Decode error")
                                raise RuntimeError("Bytes parsed > track length")  # temporary, for debugging

                    # InBuffer Dry
                    if self.AACDecoder.write_used() == 0:
                        break_reason = 3
                        break

                    # Call the C module to do the actual decoding. BiB is Bytes In Buffer of the decoder - used for debugging
                    Result, BytesDecoded, AudioSamples, BiB = self.AACDecoder.AAC_Decode()

                    if Result in (0, 100, 110):
                        self.current_track_bytes_decoder_in += BytesDecoded

                        if Result in (0, 110):
                            self.current_track_bytes_decoder_out += AudioSamples * 2
                            assert (
                                self.context.OutBuffer.write(
                                    self.AudioBufferMV, self.AACDecoder.readinto(self.AudioBufferMV, AudioSamples * 2)
                                )
                                == AudioSamples * 2
                            ), f"Buffer underrun: {AudioSamples}"
                            # self.context.OutBuffer.write(
                            #    self.AudioBufferMV, self.AACDecoder.readinto(self.AudioBufferMV, AudioSamples * 2)
                            # )

                    # We get this if there is not enough data in the decoder to decode the next packet, so we need to wait until the reader gets some more data
                    elif Result == -13:
                        print("Decoder dry")
                        break_reason = 6
                        break

                    elif Result == -6:
                        print("Corrupted packet")
                        raise RuntimeError("Corrupted packet")

                    else:
                        print("Decode Packet failed. Error:", Result)
                        raise RuntimeError("Decode Packet failed")

                # Check if we have a parsed length of the track (only populated when we have finished parsing the track) and if so, have we decoded to the end of the current track?
                if len(self.ParsedDecodeInfo) > 0:
                    if self.current_track_bytes_decoder_in == self.ParsedDecodeInfo[0][0]:
                        print(f"Track {self.ParsedDecodeInfo[0][2]} decode end", end=" - ")
                        self.callbacks["messages"](f"decode_chunk: Finished decoding track {self.ParsedDecodeInfo[0][2]}")
                        self.current_track_bytes_decoder_in = 0
                        self.decode_phase = decode_phase_trackstart

                        # Update the player with the length of decoded audio for this track
                        self.context.player.Update_Track_Length(self.current_track_bytes_decoder_out)
                        self.ParsedDecodeInfo.pop(0)

                        # if len(self.playlist) > 0: doesn't work here as the read loop may have read the whole playlist while we're still decoding n tracks behind it
                        if len(self.DecodeInfo) == 0 and len(self.context.playlist) == 0:
                            # We have finished decoding the whole playlist. Now we just need to wait for the player to finish
                            print("finished decoding playlist")
                            self.callbacks["messages"](f"decode_chunk: Finished decoding playlist")
                            self.decode_phase = decode_phase_idle

                            # This frees up all the buffers that the decoder allocated, and resets their state
                            self.AACDecoder.AAC_Close()
                        else:
                            print("decoding next track")

                        break

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

        return self.context.OutBuffer.any()


class TrackPlayer:
    def __init__(self, context, callbacks, debug=0):
        self.context = context
        self.callbacks = callbacks
        self.DEBUG = debug
        self.volume = 0

        # Size of the chunks of decoded audio that we will send to I2S
        self.ChunkSize = 70 * 1024
        self.ChunkBuffer = bytearray(self.ChunkSize)
        self.ChunkBufferMV = memoryview(self.ChunkBuffer)

        self.reset()

    def reset(self):
        self.play_phase = play_phase_idle

        self.I2SAvailable = True

        # PlayInfo is filled out when the decoder starts a new track, and tells us the format of the track (rate, bits, channels, length)
        self.PlayInfo = []

        # The number of bytes played for the current track. Used to detect the end of track
        self.current_track_bytes_played = 0

        if hasattr(self, "audio_out"):
            self.audio_out.deinit()
            del self.audio_out

        # Make rate=1 so that it doesn't match in play_chunk() and gets inited properly in the first call to play_chunk()
        self.audio_out = I2S(
            0, sck=sck_pin, ws=ws_pin, sd=sd_pin, mode=I2S.TX, bits=16, format=I2S.STEREO, rate=44100, ibuf=self.ChunkSize
        )

        self.audio_out.irq(self.i2s_callback)

    def Add_to_Play_List(self, channels, sample_rate, bits_per_sample, hash):
        # We don't know the length of this track until the decoder has finished decoding it, so set the length to False initially
        self.PlayInfo.append([channels, sample_rate, bits_per_sample, False, hash])

    def Update_Track_Length(self, TrackLength):
        # We use the Track length to detect end-of-track and re-init the I2S device at the right spot (required in case the bitrate changes between songs)
        if TrackLength == 0:
            print("Warning: Zero track length")
        self.PlayInfo[-1][3] = TrackLength

    def isRunning(self):
        return self.play_phase != play_phase_idle

    def start(self):
        self.play_phase = play_phase_start

    def stop(self):
        self.play_phase = play_phase_idle

    def play_chunk(self):
        if not self.I2SAvailable or self.play_phase == play_phase_idle:
            return

        # Are we at the beginning of a track, and the decoder has given us some format info.
        # If so, init the I2S device (Note that the sample_rate may vary between tracks)
        if self.play_phase == play_phase_start and len(self.PlayInfo) > 0:
            self.current_track_bytes_played = 0
            self.callbacks["messages"](f"play_chunk: Start playing track {self.PlayInfo[0][4]}")
            print(f"Track {self.PlayInfo[0][4]} play start")

            # The I2S object returns the following: I2S(id=0, sck=13, ws=14, sd=17, mode=5, bits=16, format=1, rate=44100, ibuf=71680)
            # Check if it is the same as the already initialised device. If so, do nothing. If not, init it to the new values
            current_bits = int(str(self.audio_out).split(",")[5].split("=")[1])
            current_channels = 2 if int(str(self.audio_out).split(",")[6].split("=")[1]) == I2S.STEREO else 1
            current_rate = int(str(self.audio_out).split(",")[7].split("=")[1])

            # PlayInfo[] has channels, sample_rate, bits_per_sample, length
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

            self.play_phase = play_phase_playing

        # Make sure this is before the play_phase_playing check so that it doesn't fall through to this
        if self.play_phase == play_phase_end:
            print(f"Track {self.PlayInfo[0][4]} play end", end=" - ")
            self.callbacks["messages"](f"play_chunk: Finished playing track {self.PlayInfo[0][4]}")

            # Remove the info for this track
            self.PlayInfo.pop(0)

            if (
                len(self.context.playlist) == 0
                and len(self.PlayInfo) == 0
                and self.context.InBuffer.any() == 0
                and self.context.OutBuffer.any() == 0
            ):
                print("finished playing playlist")

                # Stop the I2S device
                self.audio_out.deinit()
                self.callbacks["messages"](f"play_chunk: Finished playing playlist")
                self.play_phase = play_phase_idle
            else:
                print("playing next track")
                self.play_phase = play_phase_start

        if self.play_phase == play_phase_playing:
            # Play what we have, up to the chunk size
            BytesToPlay = min(self.context.OutBuffer.any(), self.ChunkSize)

            # Do we have a length for this track yet? (We only get this after the decoder has finished decoding it)
            if len(self.PlayInfo) > 0 and self.PlayInfo[0][3] != False:
                # If so, have we played all of the decoded bytes for this track?
                if self.current_track_bytes_played + BytesToPlay >= self.PlayInfo[0][3]:
                    # Adjust the bytes to play to only be the remaining bytes for this track
                    BytesToPlay = self.PlayInfo[0][3] - self.current_track_bytes_played

                    self.play_phase = play_phase_end

            # The output buffer can get starved if the network is slow, or if we slow the decoder too much (e.g. by writing too much debug output)
            # In this case we need to stop the player and wait for the decoder to fill up the InBuffer again
            if BytesToPlay == 0:
                print("Player starved")
                self.play_phase = play_phase_idle
                return

            # Adjust the volume
            self.context.OutBuffer.readinto(self.ChunkBufferMV, BytesToPlay)
            outbytes = memoryview(self.ChunkBufferMV[0:BytesToPlay])
            self.audio_out.shift(buf=outbytes, bits=16, shift=self.volume)

            # Play the data in the buffer
            self.I2SAvailable = False
            numout = self.audio_out.write(outbytes)
            assert numout == BytesToPlay, f"I2S write error - {numout} != {BytesToPlay}"

            self.current_track_bytes_played += BytesToPlay

    @micropython.native
    def i2s_callback(self, t):
        self.I2SAvailable = True


class AudioPlayer:
    def __init__(self, callbacks={}, debug=0):
        self.callbacks = callbacks
        if "messages" not in callbacks.keys():
            self.callbacks["messages"] = lambda m: m

        self.DEBUG = debug
        self.pumptimer = Timer(0)
        self.reader = TrackReader(self, callbacks, debug)
        self.decoder = TrackDecoder(self, callbacks, debug)
        self.player = TrackPlayer(self, callbacks, debug)

        self.init_buffers()
        self.reset_player()

    def init_buffers(self):
        # A ringbuffer to hold packets from the network
        # As an example, a 96000 bps bitrate is 12kB per second, so a ten second buffer should be about 120kB
        # Note that the RingIO buffer uses one byte internally to track the ring, so we add one to the size to account for this
        self.InBufferSize = 160 * 1024
        InBufferBytes = bytearray(self.InBufferSize + 1)
        InBufferMV = memoryview(InBufferBytes)
        self.InBuffer = micropython.RingIO(InBufferMV)

        # A ringbuffer to hold decoded audio samples
        # 44,100 Hz takes 176,400 bytes per second (16 bit samples, stereo). e.g. 1MB will hold 5.9 seconds, 700kB will hold 4 seconds
        # Note that the RingIO buffer uses one byte internally to track the ring, so we add one to the size to account for this
        self.OutBufferSize = 700 * 1024
        OutBufferBytes = bytearray(self.OutBufferSize + 1)
        OutBufferMV = memoryview(OutBufferBytes)
        self.OutBuffer = micropython.RingIO(OutBufferMV)

    @property
    def playlist(self):
        return self._playlist

    @playlist.setter
    def playlist(self, value):
        self._playlist = value

        if not self.reader.isRunning() and self.audioplayer_state != audioplayer_state_Stopped:
            self.reader.start()

    def start_timer(self):
        self.pumptimer = Timer(0)
        self.pumptimer.init(period=10, mode=Timer.ONE_SHOT, callback=self.do_pump)

    def reset_player(self):
        self.DEBUG and print("Resetting Player")
        if hasattr(self, "pumptimer") and self.pumptimer:
            try:
                self.pumptimer.deinit()
            except:
                pass

        self.reader.reset()
        self.decoder.reset()
        self.player.reset()
        self.audioplayer_state = audioplayer_state_Stopped
        self.init_vars()
        self.start_timer()

        try:
            self.decoder.AACDecoder.close()
        except AttributeError as e:
            raise AttributeError("Firmware is out of date")
        self.decoder.AACDecoder.AAC_Close()

        print(self)

    def init_vars(self):
        self.volume = 0
        self.sock = None
        self.song_transition = None
        self.mute_pin = mute_pin

        self._playlist = []
        self.InBuffer.close()
        self.OutBuffer.close()

    def __repr__(self):
        if self.audioplayer_state == audioplayer_state_Playing:
            status = "Playing"
        elif self.audioplayer_state == audioplayer_state_Paused:
            status = "Paused"
        elif self.audioplayer_state == audioplayer_state_Stopped:
            status = "Stopped"
        else:
            status = " !?! "

        retstring = f"{status} -- {[l if i==0 else l[1] for i,l in enumerate(self.playlist[:10])]}" + (
            f" ... {len(self.playlist) - 10} more" if len(self.playlist) > 10 else ""
        )

        if self.audioplayer_state != audioplayer_state_Stopped:
            retstring += f"\n    -- "
            retstring += f" Read {self.reader.current_track_bytes_read}"
            retstring += f" ParsedIn {self.decoder.current_track_bytes_parsed_in}"
            retstring += f" ParsedOut {self.decoder.current_track_bytes_parsed_out}"
            retstring += f" DecodedIn {self.decoder.current_track_bytes_decoder_in}"
            retstring += f" DecodedOut {self.decoder.current_track_bytes_decoder_out}"
            retstring += f" Played {self.player.current_track_bytes_played}"
            retstring += f" DecodeInfo {self.decoder.DecodeInfo}"
            retstring += f" ParsedDecodeInfo {self.decoder.ParsedDecodeInfo}"
            retstring += f" PlayInfo {self.player.PlayInfo}"
        return retstring

    def ntracks(self):
        return len(self.playlist)

    # Set volume from 1 (quietest) to 11 (loudest)
    def set_volume(self, vol):
        assert vol >= 1 and vol <= 11, "Invalid Volume value"
        self.player.volume = vol - 11

    def get_volume(self):
        return self.player.volume + 11

    def mute_audio(self):
        self.mute_pin(0)

    def unmute_audio(self):
        self.mute_pin(1)

    def play(self):
        # Do not unmute here or you will hear a tiny bit of the previous track when ffwd/rewinding
        if self.audioplayer_state == audioplayer_state_Stopped:
            self.reader.start()
            self.audioplayer_state = audioplayer_state_Playing
        elif self.audioplayer_state == audioplayer_state_Playing:
            pass
        elif self.audioplayer_state == audioplayer_state_Paused:
            self.audioplayer_state = audioplayer_state_Playing

        self.unmute_audio()

    def pause(self):
        if self.audioplayer_state == audioplayer_state_Playing:
            self.mute_audio()
            self.player.stop()
            self.audioplayer_state = audioplayer_state_Paused

    def stop(self):
        self.mute_audio()
        self.reset_player()

        if self.audioplayer_state == audioplayer_state_Stopped:
            return False

        self.audioplayer_state = audioplayer_state_Stopped

        return True

    def advance_track(self, increment=1):
        pass

    def is_paused(self):
        return self.audioplayer_state == audioplayer_state_Paused

    def is_stopped(self):
        return self.audioplayer_state == audioplayer_state_Stopped

    def is_playing(self):
        return self.audioplayer_state == audioplayer_state_Playing

    def do_pump(self, _):
        # Read the next chunk of data from the network
        self.reader.read_chunk()

        # Start the decode loop once we have more than 940 bytes (5 x .ts packets) in the InBuffer. No point starting decoding too early or the decoder can fail with insufficient data
        if not self.decoder.isRunning() and self.InBuffer.any() > 940 and self.audioplayer_state == audioplayer_state_Playing:
            self.decoder.start()

        self.decoder.decode_chunk()

        # Start the play loop if we have more than 1 second of output samples buffered (2 channels, 2 bytes per sample)
        if (
            not self.player.isRunning()
            and self.OutBuffer.any() / 44100 / 2 / 2 > 1
            and self.audioplayer_state == audioplayer_state_Playing
        ):
            self.player.start()

        self.player.play_chunk()

        self.pumptimer.init(period=10, mode=Timer.ONE_SHOT, callback=self.do_pump)
