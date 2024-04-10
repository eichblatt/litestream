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
from machine import Pin, I2S
from errno import EINPROGRESS
import select
import ssl

try:
    import AudioDecoder

    # VorbisDecoder = AudioDecoder.VorbisDecoder()
    # MP3Decoder = AudioDecoder.MP3Decoder()
except ImportError:
    import MP3Decoder, VorbisDecoder

    # import VorbisPlayer as VorbisDecoder
    # import MP3Player as MP3Decoder

# Use const() so that micropython inlines these and saves a lookup
play_state_Stopped = const(0)
play_state_Playing = const(1)
play_state_Paused = const(2)

format_MP3 = const(0)
format_Vorbis = const(1)

decode_phase_trackstart = const(0)
decode_phase_inheader = const(1)
decode_phase_readinfo = const(2)
decode_phase_decoding = const(3)

sck_pin = Pin(13)  # Serial clock output
ws_pin = Pin(14)  # Word clock output
sd_pin = Pin(17)  # Serial data output
mute_pin = Pin(3, Pin.OUT, value=1)  # XSMT on DAC chip

# ---------------------------------------------     InRingBuffer     ------------------------------------------ #
#
# For the buffer between the network and the decoder we use a Ring Buffer with an exta "overflow" area at the beginning.
# If the space between readPos and the end of the buffer is less than OverflowSize then we copy data from the end
# of the buffer to the overflow area so that the mp3/Vorbis frame is always completed.
#
# Notes:
# 1) We only write to the main buffer area. The buffer object copies data to the overflow area when required.
# 2) When there are x bytes of data in the overflow area, we limit the write to x bytes less than the main buffer so
#       that the total data available is always <= BufferSize
# 3) Calling get_read_available() can change the readPos if it copies data to the overflow area
# 4) After every read and write you must call bytes_wasRead() or bytes_wasWritten() respectively to update the read
#       and write pointers
#
#
#   0                          OverflowSize              readPos                   writePos          BufferSize + OverflowSize
#   |                               |<-----freeSpace------->|<------dataLength------->|<-------freeSpace------->|
#   V                               V                       V                         V                         V
#   -------------------------------------------------------------------------------------------------------------
#   |     <-- OverflowSize -->      |                        <-- BufferSize -->                                 |
#   -------------------------------------------------------------------------------------------------------------
#
#
#   0                          OverflowSize                       writePos                readPos    BufferSize + OverflowSize
#   |                               |<---------dataLength----------->|<------freeSpace------>|<---dataLength--->|
#   V                               V                                V                       V                  V
#   -------------------------------------------------------------------------------------------------------------
#   |     <-- OverflowSize -->      |                        <-- BufferSize -->                                 |
#   -------------------------------------------------------------------------------------------------------------
#


class InRingBuffer:
    def __init__(self, RingBufferSize, OverflowSize):
        self.Bytes = bytearray(RingBufferSize + OverflowSize)  # An array to hold the Audio data of the stream
        self.BufferSize = RingBufferSize
        self.OverflowSize = OverflowSize
        self.Buffer = memoryview(self.Bytes)
        self.InitBuffer()

    def InitBuffer(self):
        self.BytesInBuffer = 0
        self._readPos = self.OverflowSize  # The next byte we will read
        self._writePos = self.OverflowSize  # The next byte we will write

    def __repr__(self):
        retstr = f"Size: {self.BufferSize} + {self.OverflowSize}, readPos:{self._readPos}, writePos:{self._writePos}"
        retstr += f" Bytes in buffer: {self.get_bytes_in_buffer()}. Write available:{self.get_write_available()}"
        return retstr

    # Returns the pointer to where we can write to
    def get_writePos(self):
        return self._writePos

    # Returns the number of bytes in the buffer
    def get_bytes_in_buffer(self):
        return self.BytesInBuffer

    # How many bytes can we add to the buffer before filling it
    def get_write_available(self):
        if self._writePos > self._readPos:
            # If the read_pos is within the overflow area return the num bytes in there, else zero
            BytesInOverflow = max(self.OverflowSize - self._readPos, 0)
            return self.BufferSize + self.OverflowSize - self._writePos - BytesInOverflow
        elif self._writePos < self._readPos:
            return self._readPos - self._writePos
        else:  # readPos == writePos, so buffer is either empty or full
            if self.BytesInBuffer > 0:  # The buffer is full
                return 0
            else:  # The buffer is empty
                return self.BufferSize + self.OverflowSize - self._writePos

    # Tell the buffer how many bytes we just wrote. Must call this after every write to the buffer
    def bytes_wasWritten(self, count):
        self.BytesInBuffer += count
        assert self.BytesInBuffer <= self.BufferSize, "InBuffer Overflow"
        self._writePos = self.OverflowSize + ((self._writePos - self.OverflowSize + count) % self.BufferSize)

    # Returns the pointer to where we can read from
    def get_readPos(self):
        return self._readPos

    # How many bytes can we read from the buffer before it is empty. If there are less than "OverflowSize" bytes
    # available at the end of the buffer, move the bytes at the end of the buffer into the overflow area.
    # Note this function can change the readPos
    def get_read_available(self):
        if self._writePos > self._readPos:
            return self._writePos - self._readPos
        else:  # self._writePos <= self._readPos:
            if self.BytesInBuffer == 0:  # Buffer is empty
                return 0
            else:  # Buffer has data
                # The data left to read is larger than the overflow buffer, so just return the bytes left to read
                if self.BufferSize + self.OverflowSize - self._readPos > self.OverflowSize:
                    return self.BufferSize + self.OverflowSize - self._readPos
                else:  # The data left to read is smaller than the overflow buffer, so move it to the overflow buffer and update the readPos
                    bytesToMove = self.BufferSize + self.OverflowSize - self._readPos
                    if bytesToMove > 0:
                        # Move the last bytes into the overflow area
                        self.Buffer[(self.OverflowSize - bytesToMove) : self.OverflowSize] = self.Buffer[-bytesToMove:]
                    self._readPos = self.OverflowSize - bytesToMove
                    return bytesToMove + self._writePos - self.OverflowSize

    # Tell the buffer how many bytes we just read.  Must call this after every read from the buffer
    def bytes_wasRead(self, count):
        self.BytesInBuffer -= count
        assert self.BytesInBuffer >= 0, "InBuffer Underflow"
        self._readPos = self._readPos + count

    def buffer_level(self):
        return self.BytesInBuffer / self.BufferSize

    ####################### End of InRingBuffer #######################


# ---------------------------------------------     OutRingBuffer     ------------------------------------------ #
#
# For the buffer between the decoder and the I2S output we use a Ring Buffer. Because the decoder must always be able to write one full frame
# (1024 samples = 4096 bytes at 16 bit stereo) we only return get_write_available if we have at least 4096 bytes available.
# If there are less than 4096 bytes available, then the writer has to wait until the reader has freed up enough space (done in the I2S callback)
# Because this means we won't always fill the buffer before wrapping, we keep track of a "high water mark" (_endPos) to let the reader know how
# far to read before it wraps
#
# Notes:
# If read_pos is near the end of outBuffer then get_read_available() only shows a little bit of data even though the write pointer
# has wrapped and written lots more.
# Therefore, be careful about checking get_read_available() as an indicator of buffer fullness - use get_bytes_in_buffer() instead
#
#   0              readPos                 writePos                                                        BufferSize
#   |<---freeSpace--->|<------dataLength----->|<-----------------------freeSpace------------------------------->|
#   V                 V                       V                                                                 V
#   -------------------------------------------------------------------------------------------------------------
#   |                                               <-- BufferSize -->                                          |
#   -------------------------------------------------------------------------------------------------------------
#
#
#   0                             writePos                readPos                                 endPos   BufferSize
#   |<----------dataLength---------->|<------freeSpace------>|<-------------dataLength------------->|           |
#   V                                V                       V                                      V           V
#   -------------------------------------------------------------------------------------------------------------
#   |                                               <-- BufferSize -->                                          |
#   -------------------------------------------------------------------------------------------------------------
#


class OutRingBuffer:
    def __init__(self, RingBufferSize):
        self.Bytes = bytearray(RingBufferSize)  # An array to hold the decoded audio data
        self.BufferSize = RingBufferSize
        self.Buffer = memoryview(self.Bytes)
        self.InitBuffer()

    def InitBuffer(self):
        self.BytesInBuffer = 0
        self._readPos = 0  # The next byte we will read
        self._writePos = 0  # The next byte we will write
        self._endPos = 0  # The last byte of the buffer that we have written

    def __repr__(self):
        retstr = f"Size: {self.BufferSize}, readPos:{self._readPos}, writePos:{self._writePos}"
        retstr += f" Bytes in buffer: {self.get_bytes_in_buffer()}. Write available:{self.get_write_available()}"
        return retstr

    def get_writePos(self):  # Returns the pointer to where we can write to
        return self._writePos

    # How many bytes can we add to the buffer before filling it. Note this function can change the writePos
    def get_write_available(self):
        if self._writePos > self._readPos:  # We are writing ahead of the read pointer
            if self.BufferSize - self._writePos < 5000:  # Not enough space to write 5000 contiguous bytes, so wrap around
                self._writePos = 0
                return self._readPos  # We wrapped, so can write up to readpos
            else:  # There is enough room to write 5000 bytes, so we can write up to the end of the buffer as we are ahead of the read pointer
                return self.BufferSize - self._writePos
        elif self._writePos < self._readPos:  # We are writing behind the read pointer
            return self._readPos - self._writePos  # We can write up to the read pointer as we are behind the read pointer
        else:  # readPos == writePos, so buffer is either empty or full
            if self.BytesInBuffer > 0:  # The buffer is full
                return 0  # No bytes available to write
            else:  # The buffer is empty, but we are not necessarily writing at the beginning
                return self.BufferSize - self._writePos  # We can write up to the end of the buffer

    # Tell the buffer how many bytes we just wrote. Must call this after every write to the buffer
    def bytes_wasWritten(self, count):
        if self._writePos < self._readPos:
            assert self._writePos + count <= self._readPos, "OutRingBuffer Overwrite"
        self.BytesInBuffer += count
        assert self.BytesInBuffer <= self.BufferSize, "OutRingBuffer Overflow"
        self._writePos += count  # The caller must call get_write_available before calling this, so we should never overwrite the end of the buffer
        assert self._writePos <= self.BufferSize, "OutRingbuffer Overflow2"  # We wrote past the end of the buffer

        if self._writePos > self._endPos:  # Update the high water mark of the buffer
            self._endPos = self._writePos

    # Returns the pointer to where we can read from
    def get_readPos(self):
        return self._readPos

    # Returns the number of bytes in the buffer
    def get_bytes_in_buffer(self):
        return self.BytesInBuffer

    # How many bytes can we read from the buffer before it is empty
    def get_read_available(self):
        if self._readPos > self._writePos:  # We are reading ahead of the write pointer
            return self._endPos - self._readPos  # We can read all the way to the high water mark
        elif self._readPos < self._writePos:  # We are reading behind the write pointer
            return self._writePos - self._readPos  # We can read up to the write pointer
        else:  # readPos == writePos, so buffer is either empty or full
            if self.BytesInBuffer > 0:  # The buffer is full
                return self._endPos - self._readPos  # We can read up to the high water mark
            else:  # The buffer is empty, but we are not necessarily reading from at the beginning
                return 0  # No bytes available to read

    # Tell the buffer how many bytes we just read. Must call this after every read from the buffer
    def bytes_wasRead(self, count):
        if self._readPos < self._writePos:
            assert self._readPos + count <= self._writePos, "OutBuffer Overread"
        self.BytesInBuffer -= count
        assert self.BytesInBuffer >= 0, "OutRingBuffer Underflow"
        self._readPos += count  # The caller must call get_read_available before calling this, so we should never overwrite the end of the buffer
        assert self._readPos <= self._endPos, "OutRingbuffer Underflow2"  # We should never read past the high water mark

        # We have read to the high water mark so wrap back around to the beginning of the buffer and reset the high water mark
        if self._readPos == self._endPos:
            if self._readPos != self._writePos:  # If the reader caught up to the writer, then don't wrap in this case
                self._readPos = 0  # Otherwise wrap
                self._endPos = self._writePos  # The new high water mark is where the current writepos is

    def buffer_level(self):
        return self.BytesInBuffer / self.BufferSize


####################### End of OutRingBuffer #######################


class AudioPlayer:
    def __init__(self, callbacks={}, debug=False):
        self.callbacks = callbacks
        if not "display" in self.callbacks.keys():
            self.callbacks["display"] = lambda x, y: None
        self.DEBUG = debug
        self.PLAY_STATE = play_state_Stopped
        self.sock = None
        self.volume = 0
        self.playlist_started = False
        self.song_transition = None

        self.VorbisDecoder = AudioDecoder.VorbisDecoder()
        self.MP3Decoder = AudioDecoder.MP3Decoder()

        self.playlist = self.tracklist = []
        self.ntracks = 0
        self.mute_pin = mute_pin

        # The index of the current track in the playlist that we are playing (actually this is which track we are currently decoding - playback lags by the size of the OutBuffer)
        self.current_track = self.next_track = self.track_being_read = None

        # Size of the chunks of decoded audio that we will send to I2S
        self.ChunkSize = 70 * 1024

        # Create the IS2 output device. Make the rate a silly value so that it won't match when we check in play_chunk
        self.audio_out = I2S(
            0, sck=sck_pin, ws=ws_pin, sd=sd_pin, mode=I2S.TX, bits=16, format=I2S.STEREO, rate=1, ibuf=self.ChunkSize
        )

        # An array to hold packets from the network. As an example, a 96000 bps bitrate is 12kB per second, so a ten second buffer should be about 120kB
        InBufferSize = 160 * 1024

        # Maximum segment size is 512 bytes, so use 600 to be sure
        InOverflowBufferSize = 5000
        self.InBuffer = InRingBuffer(InBufferSize, InOverflowBufferSize)

        # An array to hold decoded audio samples. 44,100kHz takes 176,400 bytes per second (16 bit samples, stereo). e.g. 1MB will hold 5.9 seconds, 700kB will hold 4 seconds
        OutBufferSize = 700 * 1024
        self.OutBuffer = OutRingBuffer(OutBufferSize)

        self.reset_player()

    def reset_player(self, reset_head=True):
        self.DEBUG and print("Resetting Player")

        self.PlayLoopRunning = False
        self.ReadLoopRunning = False
        self.DecodeLoopRunning = False
        self.playlist_started = False
        self.decode_phase = decode_phase_trackstart
        self.I2SAvailable = True
        self.ID3Tag_size = 0
        self.PLAY_STATE = play_state_Stopped

        if reset_head:
            if self.ntracks > 0:
                self.current_track = 0
                self.next_track = 1 if self.ntracks > 1 else None
                self.callbacks["display"](*self.track_names())

        # A list of track lengths and their corresponding audio type (vorbis or MP3). This tells the decoder when to move onto the next track, and also which decoder to use.
        self.TrackInfo = []

        # PlayInfo is filled out when the decoder starts a new track, and tells the play loop the format of the track (rate, bits, channels)
        # PlayLength is filled out when we finish decoding a track, and tells the play loop how many decoded bytes are in the track
        self.PlayInfo = []
        self.PlayLength = []

        # The number of bytes of the current track that we have read from the network
        # This is compared against the length of the track returned from the server in the Content-Range header to determine end-of-track read
        # (this is potentially different to which track we are currently playing. We could be reading ahead of decoding and playing by one or more tracks)
        self.current_track_bytes_read = 0

        # The number of bytes the decoder has read from the input buffer. Used to detect the end of track by the decoder
        self.current_track_bytes_decoded_in = 0

        # The number many bytes of decoded audio data we have written to the OutBuffer for this track
        self.current_track_bytes_decoded_out = 0

        # The number of bytes played for the current track. Used to detect the end of track by the play loop by comparing against current_track_bytes_decoded_out
        self.current_track_bytes_played = 0

        self.InBuffer.InitBuffer()
        self.OutBuffer.InitBuffer()

        # This frees up all the buffers that the decoders allocated, and resets their state
        self.MP3Decoder.MP3_Close()
        self.VorbisDecoder.Vorbis_Close()

        if self.sock is not None:
            self.sock.close()
            self.sock = None

        self.consecutive_zeros = 0
        print(self)

    def __repr__(self):
        if not self.playlist_started:
            return "Playlist not started"
        tstat = self.track_status()
        bytes = tstat["bytes_read"]
        length = tstat["length"]
        ratio = bytes / max(length, 1)
        if self.PLAY_STATE == play_state_Playing:
            status = "Playing"
        elif self.PLAY_STATE == play_state_Paused:
            status = "Paused"
        elif self.PLAY_STATE == play_state_Stopped:
            status = "Stopped"
        else:
            status = " !?! "
        retstring = f"{status} --"
        if self.PLAY_STATE != play_state_Stopped:
            retstring += f' Read {bytes}/{length} ({100*ratio:.0f}%) of track {tstat["track_being_read"]}/{tstat["ntracks"]-1}'
            retstring += f" InBuffer: {100*self.InBuffer.buffer_level():.0f}%"
            retstring += f" OutBuffer: {100*self.OutBuffer.buffer_level():.0f}%"
        return retstring

    def set_playlist(self, tracklist, urllist):
        assert len(tracklist) == len(urllist)
        self.ntracks = len(tracklist)
        self.tracklist = [re.sub(r"^\d*[\.\)\- ]*", "", x) for x in tracklist]
        ### TEMPORARY ###
        setbreak_url = "https://storage.googleapis.com/spertilo-data/sundry/silence600.ogg"
        urllist = [x if not (x.endswith("silence600.ogg")) else setbreak_url for x in urllist]
        encorebreak_url = "https://storage.googleapis.com/spertilo-data/sundry/silence0.ogg"
        urllist = [x if not (x.endswith("silence0.ogg")) else encorebreak_url for x in urllist]
        ### TEMPORARY ###
        urllist = [x.replace(" ", "%20") for x in urllist]
        self.playlist = urllist

        if self.ntracks > 0:
            self.current_track = 0
            self.next_track = self.set_next_track()
        self.callbacks["display"](*self.track_names())

    def track_status(self):
        if self.current_track is None:
            return {}
        return {
            "current_track": self.current_track,
            "next_track": self.next_track,
            "ntracks": self.ntracks,
            "track_being_read": self.track_being_read,
            "bytes_read": self.current_track_bytes_read,
            "length": self.TrackInfo[-1][0] if len(self.TrackInfo) > 0 else 0,
        }

    def track_names(self):
        if self.current_track is None:
            return "", ""
        current_name = self.tracklist[self.current_track]
        next_name = self.tracklist[self.next_track] if self.next_track is not None else ""
        return current_name, next_name

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
        #self.unmute_audio() # Do not unmute here or you will hear a tiny bit of the previous track when ffwd/rewinding

        if self.PLAY_STATE == play_state_Stopped:
            if self.MP3Decoder.MP3_Init():
                self.DEBUG and print("MP3 decoder Init success")
            else:
                raise RuntimeError("MP3 decoder Init failed")

            if self.VorbisDecoder.Vorbis_Init():
                self.DEBUG and print("Vorbis decoder Init success")
            else:
                raise RuntimeError("Vorbis decoder Init failed")

            print("Track read start")
            self.read_http_header(self.current_track)
            self.PLAY_STATE = play_state_Playing
        elif self.PLAY_STATE == play_state_Playing:
            print(f"Playing URL {self.playlist[self.current_track]}")
        elif self.PLAY_STATE == play_state_Paused:
            print(f"Un-pausing URL {self.playlist[self.current_track]}")
            self.PLAY_STATE = play_state_Playing
            # Kick off the playback loop
            self.play_chunk()
            
        self.unmute_audio()

    def pause(self):
        if self.PLAY_STATE == play_state_Playing:
            self.mute_audio()
            print(f"Pausing URL {self.playlist[self.current_track]}")
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

    def set_next_track(self):
        if self.current_track is None:
            return None

        self.next_track = self.current_track + 1 if (self.ntracks > (self.current_track + 1)) else None
        self.DEBUG and print(f"next track set to {self.next_track}")
        return self.next_track

    def advance_track(self, increment=1):
        if self.current_track is None:
            return

        if not 0 <= (self.current_track + increment) < self.ntracks:
            if self.PLAY_STATE == play_state_Playing:
                self.stop()
            return

        self.stop(reset_head=False)
        self.current_track += increment
        self.next_track = self.set_next_track()
        self.callbacks["display"](*self.track_names())
        print(self)

    def is_paused(self):
        return self.PLAY_STATE == play_state_Paused

    def is_stopped(self):
        return self.PLAY_STATE == play_state_Stopped

    def is_playing(self):
        return self.PLAY_STATE == play_state_Playing

    def is_started(self):
        return self.playlist_started

    def parse_url(self, location):
        parts = location.decode().split("://", 1)
        port = 80 if parts[0] == "http" else 443
        url = parts[1].split("/", 1)
        host = url[0]
        path = url[1] if url[1].startswith("/") else "/" + url[1]
        return host, port, path

    def read_http_header(self, trackno, offset=0, port=80):
        if trackno is None:
            return

        track_length = 0
        self.current_track_bytes_read = offset
        self.playlist_started = True
        self.track_being_read = trackno
        url = self.playlist[trackno]
        host, port, path = self.parse_url(url.encode())

        # We might have a socket already from the previous track
        if self.sock is not None:
            self.sock.close()
            del self.sock

        # Load up the outbuffer before we fetch a new file
        self.decode_chunk(timeout=50)
        self.play_chunk()

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

        if port == 443:
            ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
            self.sock = ctx.wrap_socket(conn, server_hostname=host, do_handshake_on_connect=False)
            self.sock.setblocking(False)
        else:
            self.sock = conn

        self.decode_chunk()
        self.play_chunk()

        poller = select.poll()
        poller.register(self.sock, select.POLLOUT)

        # Request the file with optional offset (Use an offset if we're re-requesting the same file after a long pause)
        data = bytes(f"GET {path} HTTP/1.1\r\nHost: {host}\r\nRange: bytes={offset}-\r\n\r\n", "utf8")

        # Write the data to the async socket. Use poller with a 50ms timeout
        while data:
            poller.poll(50)
            n = self.sock.write(data)
            self.decode_chunk()
            self.play_chunk()

            if n is not None:
                data = data[n:]

        # Read the response headers
        response_headers = b""
        while True:
            header = self.sock.readline()
            self.decode_chunk()
            self.play_chunk()

            if header is not None:
                response_headers += header.decode("utf-8")
                # Save the length of the track. We use this to keep track of when we have finished reading a track rather than relying on EOF
                # EOF is indistinguishable from the host closing a socket when we pause too long
                if header.startswith(b"Content-Range:"):
                    track_length = int(header.split(b"/", 1)[1])
            if header == b"\r\n":
                break

        # Check if the response is a redirect. If so, kill the socket and re-open it on the redirected host/path
        while b"HTTP/1.1 301" in response_headers or b"HTTP/1.1 302" in response_headers:

            redirect_location = None
            for line in response_headers.split(b"\r\n"):
                if line.startswith(b"Location:"):
                    redirect_location = line.split(b": ", 1)[1]
                    break

            if redirect_location:
                # Extract the new host, port, and path from the redirect location
                host, port, path = self.parse_url(redirect_location)
                self.sock.close()
                del self.sock

                # Load up the outbuffer before we fetch the new file
                self.decode_chunk(timeout=50)
                self.play_chunk()

                # Establish a new socket connection to the server
                conn = socket.socket()
                self.DEBUG and print(f"Redirecting to {path} from {host}, Port:{port}, Offset {offset}")
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

                if port == 443:
                    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
                    self.sock = ctx.wrap_socket(conn, server_hostname=host, do_handshake_on_connect=False)
                    self.sock.setblocking(False)
                else:
                    self.sock = conn

                self.decode_chunk()
                self.play_chunk()

                poller = select.poll()
                poller.register(self.sock, select.POLLOUT)

                # Request the file with optional offset (Use an offset if we're re-requesting the same file after a long pause)
                data = bytes(f"GET {path} HTTP/1.1\r\nHost: {host}\r\nRange: bytes={offset}-\r\n\r\n", "utf8")

                # Write the data to the async socket. Use poller with a 50ms timeout
                while data:
                    poller.poll(50)
                    n = self.sock.write(data)
                    self.decode_chunk()
                    self.play_chunk()

                    if n is not None:
                        data = data[n:]

                # Read the response headers
                response_headers = b""
                while True:
                    header = self.sock.readline()
                    self.decode_chunk()
                    self.play_chunk()

                    if header is not None:
                        response_headers += header.decode("utf-8")
                        # Save the length of the track. We use this to keep track of when we have finished reading a track rather than relying on EOF
                        # EOF is indistinguishable from the host closing a socket when we pause too long
                        if header.startswith(b"Content-Range:"):
                            track_length = int(header.split(b"/", 1)[1])

                    if header == b"\r\n":
                        break

        # Make sure we know the length of the track and got a valid response from the server. If not, skip this track.
        if track_length == 0 or (b"HTTP/1.1 200" not in response_headers and b"HTTP/1.1 206" not in response_headers):
            print("Bad URL:", url)
            print("Headers:", response_headers)
            print("TrackLength:", track_length)
            self.current_track_bytes_read = 0
            self.current_track += 1
            self.next_track = self.set_next_track()
            self.handle_end_of_track_read()
            return

        # Store the end-of-track and format marker for this track (except if we are restarting a track)
        if path.lower().endswith(".mp3"):
            if offset == 0:
                self.TrackInfo.append((track_length, format_MP3))
        elif path.lower().endswith(".ogg"):
            if offset == 0:
                self.TrackInfo.append((track_length, format_Vorbis))
        else:
            raise RuntimeError("Unsupported audio type")

        # Start the read loop
        self.ReadLoopRunning = True

    def handle_end_of_track_read(self):
        gc.collect()
        print("Track read end")
        self.DEBUG and print(f"Bytes read: {self.current_track_bytes_read}")

        if self.track_being_read + 1 < self.ntracks:
            # We can read the header of the next track now
            print("Track read start")
            self.read_http_header(self.track_being_read + 1)
        else:
            # We have no more data to read from the network, but we have to let the decoder run out, and then let the play loop run out
            print("Finished reading playlist")
            self.sock.close()
            del self.sock
            self.sock = None
            self.ReadLoopRunning = False
            self.playlist_started = False

    def read_chunk(self):
        # If there is any free space in the input buffer then add any data available from the network
        # If there is no socket then we have already read to the end of the playlist
        if self.sock is not None:
            if (BytesAvailable := self.InBuffer.get_write_available()) > 0:
                # We can get an exception here if we pause too long and the underlying socket gets closed
                try:
                    # Read data into the InBuffer if there new data available. The readinto() will return None if there is no data available, or 0 if the socket is closed
                    data = self.sock.readinto(self.InBuffer.Buffer[self.InBuffer.get_writePos() :], BytesAvailable)

                    if data is not None:
                        # Keep track of how many bytes of the current file we have read.
                        # We will need this if the user pauses for too long and we need to request the current track from the server again
                        self.current_track_bytes_read += data
                        self.InBuffer.bytes_wasWritten(data)

                        # Start the decode loop
                        self.DecodeLoopRunning = True

                    # We have read to the end of the track
                    if self.current_track_bytes_read == self.TrackInfo[-1][0]:
                        self.handle_end_of_track_read()

                    # Peer closed socket. This is usually because we are in a long pause, and our socket closes
                    if data == 0:
                        print("Peer close")
                        # Note: The exception below will be caught by the 'except' below
                        raise RuntimeError("Peer closed socket")

                except Exception as e:
                    # The user probably paused too long and the underlying socket got closed
                    # In this case we re-start playing the current track at the offset that we got up to before the pause. Uses the HTTP Range header to request data at an offset
                    print("Socket Exception:", e, " Restarting track at offset", self.current_track_bytes_read)

                    # Start reading the current track again, but at the offset where we were up to
                    self.read_http_header(self.track_being_read, self.current_track_bytes_read)

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
        }

        # No data to decode
        if self.InBuffer.BytesInBuffer == 0:
            return self.OutBuffer.buffer_level()

        if self.decode_phase == decode_phase_trackstart:
            # We're at the start of a new track.

            # Work out the size of the ID3 tag (if any) at the beginning
            if self.ID3Tag_size == 0:
                print(f"Track {self.current_track} decode start")
                self.current_track_bytes_decoded_in = 0
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
            self.current_track_bytes_decoded_in += bytesToSkip
            self.ID3Tag_size = self.ID3Tag_size - bytesToSkip

            # There are not enough bytes in the buffer to skip all of them. Catch them next time we enter audio_pump
            if self.ID3Tag_size > 0:
                return self.OutBuffer.buffer_level()
            else:
                self.decode_phase = decode_phase_inheader

        if self.decode_phase == decode_phase_inheader:
            if self.TrackInfo[0][1] == format_MP3:
                FoundSyncWordAt = self.MP3Decoder.MP3_Start(
                    self.InBuffer.Buffer[self.InBuffer.get_readPos() :], self.InBuffer.get_read_available()
                )
            elif self.TrackInfo[0][1] == format_Vorbis:
                FoundSyncWordAt = self.VorbisDecoder.Vorbis_Start(
                    self.InBuffer.Buffer[self.InBuffer.get_readPos() :], self.InBuffer.get_read_available()
                )

            if FoundSyncWordAt >= 0:
                print("Decoder Start success. Sync word at", FoundSyncWordAt)
                self.InBuffer.bytes_wasRead(FoundSyncWordAt)
                self.current_track_bytes_decoded_in += FoundSyncWordAt
                self.decode_phase = decode_phase_readinfo
            else:
                raise RuntimeError("Decoder Start failed")

        # Just for debugging. See how many times we run the loop before timeout
        counter = 0

        while True:
            # As we call this from read_http_header() we can get here before the TrackInfo is populated, so just exit in that case
            # We should see this at the beginning of the first track, but not between tracks
            if len(self.TrackInfo) == 0:
                break_reason = 5
                break

            # Do we have at least 5000 bytes available for the decoder to write to? If not we return and wait for the play loop to free up some space.
            if self.OutBuffer.get_write_available() < 5000:  # Note: this can change write_pos
                break_reason = 1
                break

            # Don't stay in the loop too long or we affect the responsiveness of the main app
            if time.ticks_diff(time.ticks_ms(), TimeStart) > timeout:
                break_reason = 2
                break

            # Note that this can move the read pointer
            InBytesAvailable = self.InBuffer.get_read_available()

            # The decoders need at least 4096 bytes. At the end of a track we have to let less through though.
            if InBytesAvailable < 4096:
                # How many bytes left to decode in this track? If less than 4096, let it through
                if (self.TrackInfo[0][0] - self.current_track_bytes_decoded_in) >= 4096:
                    break_reason = 3
                    break

            counter += 1

            pos = self.InBuffer.get_readPos()

            # print(f"Decoding: {pos}, {InBytesAvailable}: ", end=' ')
            # ts = time.ticks_ms()

            ### MP3 ###
            if self.TrackInfo[0][1] == format_MP3:
                Result, BytesLeft, AudioSamples = self.MP3Decoder.MP3_Decode(
                    self.InBuffer.Buffer[pos:],
                    InBytesAvailable,
                    self.OutBuffer.Buffer[self.OutBuffer.get_writePos() :],
                )

                if Result == 0:
                    self.current_track_bytes_decoded_in += InBytesAvailable - BytesLeft
                    self.InBuffer.bytes_wasRead(InBytesAvailable - BytesLeft)

                    self.OutBuffer.bytes_wasWritten(AudioSamples * 2)
                    self.current_track_bytes_decoded_out += (AudioSamples) * 2
                    pass

                # This means either that we tried to decode the TAG at the end of the file, or we have a corrupted packet
                elif Result == -6:
                    if (
                        self.InBuffer.Bytes[pos] == ord(b"T")
                        and self.InBuffer.Bytes[pos + 1] == ord(b"A")
                        and self.InBuffer.Bytes[pos + 2] == ord(b"G")
                    ):
                        # V1.x ID3 tag at the end. Fixed size of 128 bytes. Skip it.
                        print("Skipping TAG")
                        self.InBuffer.get_read_available()
                        self.InBuffer.bytes_wasRead(128)
                        self.current_track_bytes_decoded_in += 128
                    else:
                        print(pos, end=":")
                        print(self.InBuffer.Buffer[pos:].hex())
                        # Not sure what we should do here. Maybe we could handle it?
                        raise RuntimeError("Corrupted packet")
                    pass

                # If the packet is short/corrupted we can hopefully recover by the next packet
                elif Result == -2:
                    pass

                else:
                    print("Decode Packet failed. Error:", Result)
                    print(pos, end=":")
                    print(self.InBuffer.Buffer[pos:].hex())
                    raise RuntimeError("Decode Packet failed")

                if self.decode_phase == decode_phase_readinfo:
                    channels, sample_rate, bits_per_sample, bit_rate = self.MP3Decoder.MP3_GetInfo()

            ### Vorbis ###
            elif self.TrackInfo[0][1] == format_Vorbis:
                Result, BytesLeft, AudioSamples = self.VorbisDecoder.Vorbis_Decode(
                    self.InBuffer.Buffer[pos:],
                    InBytesAvailable,
                    self.OutBuffer.Buffer[self.OutBuffer.get_writePos() :],
                )

                # print(f"Decoded: {InBytesAvailable - BytesLeft}. Ret:{Result}. Samples:{AudioSamples}. Total:{self.current_track_bytes_decoded_in}. Time:{time.ticks_diff(time.ticks_ms(), ts)}")

                if Result == 0 or Result == 100 or Result == 110:
                    self.current_track_bytes_decoded_in += InBytesAvailable - BytesLeft
                    self.InBuffer.bytes_wasRead(InBytesAvailable - BytesLeft)

                    if Result == 0 or Result == 110:
                        self.OutBuffer.bytes_wasWritten(AudioSamples * 4)
                        self.current_track_bytes_decoded_out += (AudioSamples) * 4
                    pass

                # We have a corrupted packet
                elif Result == -6:
                    print(pos, end=":")
                    print(self.InBuffer.Buffer[pos:].hex())
                    # Not sure what we should do here. Maybe we could handle it?
                    raise RuntimeError("Corrupted packet")
                    pass

                # We got an OGG Header without Vorbis data (possibly a Ogg Theora video). Skip to next track as we can't decode this
                elif Result == -7:
                    print("Not an audio track")
                    self.ffwd()
                    self.play()
                    pass

                else:
                    print("Decode Packet failed. Error:", Result)
                    print(pos, end=":")
                    print(self.InBuffer.Buffer[pos:].hex())
                    raise RuntimeError("Decode Packet failed")

                # If we're at the beginning of the track, get info about this stream
                if self.decode_phase == decode_phase_readinfo:
                    channels, sample_rate, bits_per_sample, bit_rate = self.VorbisDecoder.Vorbis_GetInfo()

            # Make sure we got valid data back from GetInfo()
            if self.decode_phase == decode_phase_readinfo and channels != 0:
                self.DEBUG and print("Channels:", channels)
                self.DEBUG and print("Sample Rate:", sample_rate)
                self.DEBUG and print("Bits per Sample:", bits_per_sample)
                self.DEBUG and print("Bitrate:", bit_rate)

                # Store the track info so that the play loop can init the I2S device at the beginning of the track
                self.PlayInfo.append((channels, sample_rate, bits_per_sample))
                self.decode_phase = decode_phase_decoding

            # Check if we have decoded to the end of the current track
            if self.current_track_bytes_decoded_in == self.TrackInfo[0][0]:  # We have finished decoding the current track
                print(f"Track {self.current_track} decode end")

                # Save the length of decoded audio for this track. Play_chunk() will check this to re-init the I2S device at the right spot (required in case the bitrate changes between songs)
                self.PlayLength.append(self.current_track_bytes_decoded_out)

                self.TrackInfo.pop(0)  # Remove the current track info from the list

                if self.current_track + 1 < self.ntracks:  # Start decode of next track
                    self.current_track += 1
                    self.next_track = self.set_next_track()
                    self.callbacks["display"](*self.track_names())
                    self.decode_phase = decode_phase_trackstart

                # We have finished decoding the whole playlist. Now we just need to wait for the play loop to run out
                else:
                    print("Finished decoding playlist")
                    self.DecodeLoopRunning = False
                    self.playlist_started = False

                    # This frees up all the buffers that the decoders allocated, and resets their state
                    self.MP3Decoder.MP3_Close()
                    self.VorbisDecoder.Vorbis_Close()
                    # Don't call stop() here or the end of the song will be cut off
                break

            # If we have more than 1 second of output samples buffered (2 channels, 2 bytes per sample), start playing them.
            # Don't check self.OutBuffer.get_read_available here
            if self.PlayLoopRunning == False and self.OutBuffer.get_bytes_in_buffer() / 44100 / 2 / 2 > 1:
                self.DEBUG and print("************ Initiate Play Loop ************")

                # Start the playback loop by playing the first chunk
                self.I2SAvailable = True
                self.PlayLoopRunning = True  # So that we don't call this again
                self.play_chunk()

        if self.DEBUG and ((counter > 0) or (break_reason != 1)):
            print(f"Time {time.ticks_ms()}. Decoded {counter} chunks in ", end="")
            print(f"{time.ticks_diff(time.ticks_ms(), TimeStart)} ms. {break_reasons[break_reason]}", end="")
            if self.consecutive_zeros > 0:
                print(f" after {self.consecutive_zeros} Buffer Fulls")
                self.consecutive_zeros = 0
            else:
                print("")
        else:
            self.consecutive_zeros += 1

        return self.OutBuffer.buffer_level()

    @micropython.native
    def play_chunk(self):
        if (self.PLAY_STATE != play_state_Playing) or (not self.I2SAvailable):
            return

        self.I2SAvailable = False

        # Are we at the beginning of a track, and the decoder has given us some format info. If so, init the I2S device (Note that the sample_rate may vary between tracks)
        if self.current_track_bytes_played == 0 and len(self.PlayInfo) > 0:
            print("Track play start")

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
        BytesToPlay = min(self.OutBuffer.get_read_available(), self.ChunkSize)

        # Do we have a length for this track yet? (We only get this after the decoder has finished decoding it)
        if len(self.PlayLength) > 0:
            # If so, have we played all of the decoded bytes for this track?
            if self.current_track_bytes_played + BytesToPlay >= self.PlayLength[0]:
                print("Track play end")

                # Play the remaining bytes for this track, and remove the info for this track
                BytesToPlay = self.PlayLength[0] - self.current_track_bytes_played
                self.PlayLength.pop(0)

                if not self.DecodeLoopRunning:
                    self.PlayLoopRunning = False
                    print("Finished playing playlist")

                # Do this so that when the BytesToPlay gets added at the end of this function that current_track_bytes_played will then be zero
                self.current_track_bytes_played = -BytesToPlay

                # We have a zero length track, so we don't need to play anything
                if BytesToPlay == 0:
                    self.I2SAvailable = True
                    return

        # We can get zero bytes to play if the buffer is starved
        if BytesToPlay == 0:
            # The output buffer can get starved if the network is slow,
            # or if we slow the decoding loop too much (e.g. by writing too much debug output)
            self.DEBUG and print("Play buffer starved")

            # Clear this flag to let the decoder re-start the playback loop when the decoder has generated enough data
            self.PlayLoopRunning = False

            self.I2SAvailable = True
            return

        Offset = self.OutBuffer.get_readPos()

        # Make a memoryview of the output buffer slice.
        # Not sure why we have to do this instead of slicing the OutBuffer.Buffer memoryview.
        # Slicing a memoryview creates a new memoryview (which allocates a small amount of memory),
        # but we are not in an ISR here so it shouldn't matter.
        # However, we get corrupted audio if we slice the memoryview directly
        outbytes = memoryview(self.OutBuffer.Bytes[Offset : Offset + BytesToPlay])
        # outbytes = self.OutBuffer.Buffer[Offset : Offset + BytesToPlay]

        try:
            self.OutBuffer.bytes_wasRead(BytesToPlay)
        except Exception as e:
            print("Buffer error. Stopping playback loop", e)
            self.stop()
            return

        # Set the volume
        self.audio_out.shift(buf=outbytes, bits=16, shift=self.volume)

        # Write the PCM data to the I2S device. Returns straight away
        numout = self.audio_out.write(outbytes)
        assert numout == BytesToPlay, "I2S write error"

        self.current_track_bytes_played += BytesToPlay

    @micropython.native
    def i2s_callback(self, t):
        self.I2SAvailable = True

        if not self.ReadLoopRunning and not self.DecodeLoopRunning and not self.PlayLoopRunning and self.PLAY_STATE != play_state_Stopped:
           self.stop()

    ###############################################################################################################################################

    @micropython.native
    def audio_pump(self):
        buffer_level_in = self.InBuffer.buffer_level()
        buffer_level_out = self.OutBuffer.buffer_level()

        if self.is_stopped():
            return min(buffer_level_in, buffer_level_out)

        # Read the next chunk of audio data
        if self.ReadLoopRunning:
            self.read_chunk()

        # Decode the next chunk of audio data
        if self.DecodeLoopRunning:
            buffer_level_out = self.decode_chunk()

        # Play the next chunk of audio data
        if self.PlayLoopRunning:
            self.play_chunk()

        buffer_level_in = self.InBuffer.buffer_level()
        return min(buffer_level_in, buffer_level_out)
