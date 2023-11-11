"""
litestream
Copyright (C) 2023  spertilo.net

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

import re, socket, time

try:
    import MP3Decoder, VorbisDecoder
except ImportError:
    import VorbisPlayer as VorbisDecoder
    import MP3Player as MP3Decoder
from machine import Pin, I2S
import gc

sck_pin = Pin(13)  # Serial clock output
ws_pin = Pin(14)  # Word clock output
sd_pin = Pin(17)  # Serial data output

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

    # Returns the pointer to where we can read from
    def get_writePos(self):
        return self._writePos

    # Returns the number of bytes in the buffer
    def get_bytes_in_buffer(self):
        return self.BytesInBuffer

    # How many bytes can we add to the buffer before filling it
    @micropython.native
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
                return self.BufferSize - self._writePos

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
    @micropython.native
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
    @micropython.native
    def bytes_wasRead(self, count):
        self.BytesInBuffer -= count
        assert self.BytesInBuffer >= 0, "InBuffer Underflow"
        self._readPos = self._readPos + count

    @micropython.native
    def buffer_level(self):
        return self.BytesInBuffer / self.BufferSize


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

    def get_writePos(self):  # Returns the pointer to where we can read from
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
    @micropython.native
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
    @micropython.native
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

    @micropython.native
    def buffer_level(self):
        return self.BytesInBuffer / self.BufferSize


####################### End of OutRingBuffer #######################


class AudioPlayer:
    def __init__(self, callbacks={}, debug=False):
        self.STOPPED, self.PLAYING, self.PAUSED = 0, 1, 2
        self.MP3, self.OGGVORBIS = 0, 1
        self.callbacks = callbacks
        if not "display" in self.callbacks.keys():
            self.callbacks["display"] = lambda x, y: None
        self.DEBUG = debug
        self.PLAY_STATE = self.STOPPED
        self.sock = None
        self.audio_out = None
        self.playlist_started = False

        self.playlist = self.tracklist = []
        self.ntracks = 0

        # The index of the current track in the playlist that we are playing (actually this is which track we are currently decoding - playback lags by the size of the OutBuffer)
        self.current_track = self.next_track = self.track_being_read = None

        # Size of the chunks of decoded audio that we will send to I2S
        self.ChunkSize = 70 * 1024

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
        self.PlayLoopRunning = False
        self.FinishedStreaming = False
        self.FinishedDecoding = False
        self.InHeader = False
        self.AtTrackStart = True
        self.I2SAvailable = True
        self.ID3Tag_size = 0
        self.Decoder = None
        self.audio_out = None

        if reset_head:
            if self.ntracks > 0:
                self.current_track = 0
                self.next_track = 1 if self.ntracks > 1 else None

        # A list of offsets into the InBuffer where the tracks end. This tells the decoder when to move onto the next track by decoding the next header
        self.TrackEnds = []

        # Keep track of how many bytes of the current track that we are streaming from the network
        # (this is potentially different to which track we are currently playing. We could be reading ahead of playing by one or more tracks)
        self.current_track_bytes_read = 0
        # Keep track of the current number of bytes decoded. Usd to detect the end of track by the decoder
        self.current_track_bytes_decoded = 0
        self.current_track_length = 0

        self.InBuffer.InitBuffer()
        self.OutBuffer.InitBuffer()

        # This frees up all the buffers that the decoder allocated, and resets its state
        MP3Decoder.MP3_Close()
        VorbisDecoder.Vorbis_Close()

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
        if self.PLAY_STATE == self.PLAYING:
            status = "Playing"
        elif self.PLAY_STATE == self.PAUSED:
            status = "Paused"
        elif self.PLAY_STATE == self.STOPPED:
            status = "Stopped"
        else:
            status = " !?! "
        retstring = f"{status} --"
        if self.PLAY_STATE != self.STOPPED:
            retstring += f' Read {bytes}/{length} ({100*ratio:.0f}%) of track {tstat["track_being_read"]}/{tstat["ntracks"]}'
            retstring += f" InBuffer: {100*self.InBuffer.buffer_level():.0f}%"
            retstring += f" OutBuffer: {100*self.OutBuffer.buffer_level():.0f}%"
        return retstring

    @micropython.native
    def play_chunk(self):
        if (
            (self.PLAY_STATE != self.PLAYING)
            or (not self.I2SAvailable)
            or (not self.PlayLoopRunning)
            or (self.OutBuffer.get_bytes_in_buffer() == 0)
        ):
            return
        self.I2SAvailable = False

        BytesToPlay = min(self.OutBuffer.get_read_available(), self.ChunkSize)  # Play what we have, up to the chunk size

        # We can get zero bytes to play if the buffer is starved, or when we reach the end of the playlist
        if BytesToPlay == 0:
            if self.FinishedDecoding:  # End of playlist
                print("Finished Playing")
                self.stop()
                return
            else:  # Buffer starved
                # The output buffer can get starved if the network is slow, or if we write too much debug output
                self.DEBUG and print("Play buffer starved")
                # Set this flag to re-start the player loop when the decoder has generated enough data
                self.PlayLoopRunning = False
                return

        Offset = self.OutBuffer.get_readPos()

        # Make a memoryview of the output buffer slice. We have to do this instead of slicing OutBuffer.Buffer
        # because slicing a memoryview creates a new memoryview, and we cannot allocate memory in an ISR
        outbytes = memoryview(self.OutBuffer.Bytes[Offset : Offset + BytesToPlay])

        try:
            self.OutBuffer.bytes_wasRead(BytesToPlay)
        except Exception as e:
            print("Buffer error. Stopping playback loop", e)
            self.stop()
            return

        numout = self.audio_out.write(outbytes)  # Write the PCM data to the I2S device. Returns straight away
        assert numout == BytesToPlay, "I2S write error"

    @micropython.native
    def i2s_callback(self, t):
        self.I2SAvailable = True

    def set_playlist(self, tracklist, urllist):
        assert len(tracklist) == len(urllist)
        self.ntracks = len(tracklist)
        self.tracklist = [re.sub(r"^\d*[\.\)\- ]*", "", x) for x in tracklist]
        ### TEMPORARY ###
        setbreak_url = "https://storage.googleapis.com/spertilo-data/sundry/silence600.{current_format}"
        urllist = [x if not (x.endswith("silence600.ogg")) else setbreak_url for x in urllist]
        encorebreak_url = "https://storage.googleapis.com/spertilo-data/sundry/silence0.{current_format}"
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
            "length": self.current_track_length,
        }

    def track_names(self):
        if self.current_track is None:
            return "", ""
        current_name = self.tracklist[self.current_track]
        next_name = self.tracklist[self.next_track] if self.next_track is not None else ""
        return current_name, next_name

    def get_redirect_location(self, headers):
        for line in headers.split(b"\r\n"):
            if line.startswith(b"Location:"):
                return line.split(b": ", 1)[1]
        return None

    def parse_redirect_location(self, location):
        parts = location.decode().split("://", 1)[1].split("/", 1)
        host_port = parts[0].split(":", 1)
        host = host_port[0]
        port = int(host_port[1]) if len(host_port) > 1 else 80
        path = "/" + parts[1] if len(parts) > 1 else "/"
        return host, port, path

    def play(self):
        if self.PLAY_STATE == self.STOPPED:
            self.InBuffer.InitBuffer()
            self.read_header(self.current_track)
            self.PLAY_STATE = self.PLAYING
        elif self.PLAY_STATE == self.PLAYING:
            print(f"Playing URL {self.playlist[self.current_track]}")
        elif self.PLAY_STATE == self.PAUSED:
            print(f"Un-pausing URL {self.playlist[self.current_track]}")
            self.PLAY_STATE = self.PLAYING
            self.play_chunk()  # Kick off the playback loop

    def pause(self):
        if self.PLAY_STATE == self.PLAYING:
            print(f"Pausing URL {self.playlist[self.current_track]}")
            self.PLAY_STATE = self.PAUSED

    def rewind(self):
        self.DEBUG and print("in rewind")
        self.advance_track(-1)

    def ffwd(self):
        self.DEBUG and print("in ffwd")
        self.advance_track()

    def stop(self, reset_head=True):
        if self.PLAY_STATE == self.STOPPED:
            return
        self.PLAY_STATE = self.STOPPED
        self.reset_player(reset_head)

    def set_next_track(self):
        if self.current_track is None:
            return None
        self.next_track = self.current_track + 1 if self.ntracks > (self.current_track + 1) else None
        self.DEBUG and print(f"next track set to {self.next_track}")
        return self.next_track

    def advance_track(self, increment=1):
        if self.current_track is None:
            return
        if not 0 <= (self.current_track + increment) <= self.ntracks:
            if self.PLAY_STATE == self.PLAYING:
                self.stop()
            return

        self.stop(reset_head=False)
        self.current_track += increment
        self.next_track = self.set_next_track()
        print(self)
        self.callbacks["display"](*self.track_names())

    def is_paused(self):
        return self.PLAY_STATE == self.PAUSED

    def is_stopped(self):
        return self.PLAY_STATE == self.STOPPED

    def is_playing(self):
        return self.PLAY_STATE == self.PLAYING

    @micropython.native
    def read_header(self, trackno, offset=0, port=80):
        if trackno is None:
            return
        self.playlist_started = True
        # TimeStart = time.ticks_ms()
        self.track_being_read = trackno

        url = self.playlist[trackno]

        url = url.format(current_format=("mp3" if self.Decoder == self.MP3 else "ogg"))
        if url.lower().endswith(".mp3"):
            self.Decoder = self.MP3
        elif url.lower().endswith(".ogg"):
            self.Decoder = self.OGGVORBIS
        else:
            raise RuntimeError("Unsupported audio type")

        _, _, host, path = url.split("/", 3)
        addr = socket.getaddrinfo(host, port)[0][-1]

        if self.sock is not None:  # We might have a socket already from the previous track
            self.sock.close()

        self.play_chunk()
        self.sock = socket.socket()

        self.DEBUG and print("Getting", path, "from", host, "Port:", port)
        self.sock.connect(addr)
        self.sock.setblocking(False)  # Tell the socket to return straight away (async)

        self.play_chunk()
        # Request the file with optional offset (Use an offset if we're re-requesting the same file after a long pause)
        self.sock.send(bytes(f"GET /{path} HTTP/1.1\r\nHost: {host}\r\nRange: bytes={offset}-\r\n\r\n", "utf8"))

        # Read the response headers
        response_headers = b""
        while True:
            header = self.sock.readline()
            self.play_chunk()

            if header is not None:
                response_headers += header.decode("utf-8")
                if header.startswith(b"Content-Range:"):
                    self.current_track_length = int(header.split(b"/", 1)[1])
            if header == b"\r\n":
                break

        # Check if the response is a redirect. If so, kill the socket and re-open it on the redirected host/path
        if b"HTTP/1.1 301" in response_headers or b"HTTP/1.1 302" in response_headers:
            redirect_location = self.get_redirect_location(response_headers)
            if redirect_location:
                # Extract the new host, port, and path from the redirect location
                new_host, new_port, new_path = self.parse_redirect_location(redirect_location)
                self.sock.close()
                # Establish a new socket connection to the server
                self.DEBUG and print("Redirecting to", new_host, new_port, new_path, "Offset", offset)
                self.play_chunk()
                self.sock = socket.socket()
                addr = socket.getaddrinfo(new_host, new_port)[0][-1]
                self.sock.connect(addr)
                self.sock.setblocking(False)  # Return straight away
                self.play_chunk()

                # Request the file with optional offset (Use an offset if we're re-requesting the same file after a long pause)
                self.sock.send(bytes(f"GET /{new_path} HTTP/1.1\r\nHost: {new_host}\r\nRange: bytes={offset}-\r\n\r\n", "utf8"))

                # Skip the response headers
                while True:
                    header = self.sock.readline()
                    self.play_chunk()

                    if header is not None:
                        # Save the length of the track. We use this to keep track of when we have finished reading a track rather than relying on EOF
                        # EOF is indistinguishable from the host closing a socket when we pause too long
                        if header.startswith(b"Content-Range:"):
                            self.current_track_length = int(header.split(b"/", 1)[1])

                    if header == b"\r\n":
                        break

        self.current_track_bytes_read = offset

    #######################################################################################################################################
    @micropython.native
    def handle_end_of_track(self):
        # Store the end-of-track marker for this track
        gc.collect()
        self.TrackEnds.append(self.current_track_length)
        self.DEBUG and print(f"EOF. Track end at {self.InBuffer.get_writePos()}. ", end="")
        self.DEBUG and print(f"Bytes read: {self.current_track_bytes_read} - ", end="")
        if self.track_being_read + 1 < self.ntracks:
            print("reading next track")
            self.read_header(self.track_being_read + 1)  # We can read the header of the next track now
            self.current_track_bytes_read = 0
        else:
            print("end of playlist")
            self.FinishedStreaming = True  # We have no more data to read from the network, but we have to let the decoder run out, and then let the play loop run out
            self.sock.close()
            self.sock = None
            self.playlist_started = False
            self.stop()
        return

    @micropython.native
    def audio_pump(self):
        if self.is_stopped():
            buffer_level_in = self.InBuffer.buffer_level()
            buffer_level_out = self.OutBuffer.buffer_level()
            return min(buffer_level_in, buffer_level_out)

        TimeStart = time.ticks_ms()

        # If there is any free space in the input buffer then add any data available from the network.
        if self.sock is not None:  # If there is no socket than we have already read to the end of the playlist
            if (BytesAvailable := self.InBuffer.get_write_available()) > 0:
                try:  # We can get an exception here if we pause too long and the underlying socket gets closed
                    # Read real data into the InBuffer
                    data = self.sock.readinto(self.InBuffer.Buffer[self.InBuffer.get_writePos() :], BytesAvailable)

                    # Is there new data available? The readinto will return None if there is no data available, or 0 if the socket is closed
                    if self.current_track_length == self.current_track_bytes_read:
                        data = 0
                    if data is not None:
                        # Keep track of how many bytes of the current file we have read.
                        # We will need this if the user pauses for too long and we need to request the current track from the server again
                        self.current_track_bytes_read += data
                        self.InBuffer.bytes_wasWritten(data)

                        # Peer closed socket. This can be because of End-of-stream or it can happen in a long pause before our socket closes
                        if data == 0:
                            # End of track
                            if self.current_track_length == self.current_track_bytes_read:
                                self.handle_end_of_track()
                            else:  # Peer closed its socket, but not at the end of the track
                                print("Peer close")
                                raise RuntimeError("Peer closed socket")  # Will be caught by the 'except' below

                except Exception as e:
                    # The user probably paused too long and the underlying socket got closed
                    # In this case we re-start playing the current track at the offset that we got up to before the pause. Uses the HTTP Range header to request data at an offset
                    print("Socket Exception:", e, " Restarting track at offset", self.current_track_bytes_read)

                    # Start reading the current track again, but at the offset where we were up to
                    self.read_header(self.track_being_read, self.current_track_bytes_read)

        #        if self.OutBuffer.get_bytes_in_buffer() > 0 and self.I2SAvailable and self.PlayLoopRunning:
        #            self.I2SAvailable = False
        self.play_chunk()

        if self.AtTrackStart:
            if self.InBuffer.BytesInBuffer == 0:
                return

            # We're at the start of a new track. Work out the size of the ID3 tag (if any) at the beginning
            if self.ID3Tag_size == 0:
                self.current_track_bytes_decoded = 0
                readpos = self.InBuffer.get_readPos()
                # ID3 tag at beginning. Work out the size
                if (
                    self.InBuffer.Bytes[readpos] == ord(b"I")
                    and self.InBuffer.Bytes[readpos + 1] == ord(b"D")
                    and self.InBuffer.Bytes[readpos + 2] == ord(b"3")
                ):
                    self.ID3Tag_size = 0

                    for i in range(4):
                        self.ID3Tag_size += self.InBuffer.Bytes[readpos + i + 6] << (3 - i) * 7

                    self.ID3Tag_size = self.ID3Tag_size + 10
                    print(f"ID3 tag size:{self.ID3Tag_size}")

            # Skip past the tag. There may not be enough bytes in the InBuffer to skip all of the tag
            bytesToSkip = min(self.ID3Tag_size, self.InBuffer.get_read_available())
            print(f"Skipping {bytesToSkip} bytes")
            self.InBuffer.bytes_wasRead(bytesToSkip)
            self.current_track_bytes_decoded = self.current_track_bytes_decoded + bytesToSkip
            self.ID3Tag_size = self.ID3Tag_size - bytesToSkip

            # There are not enough bytes in the buffer to skip all of them. Catch them next time we enter audio_pump
            if self.ID3Tag_size > 0:
                return
            else:
                self.AtTrackStart = False
                self.InHeader = True

        if self.InHeader:
            if self.Decoder == self.MP3:
                ret = MP3Decoder.MP3_Init()
            elif self.Decoder == self.OGGVORBIS:
                ret = VorbisDecoder.Vorbis_Init()

            if ret:
                self.DEBUG and print("Decoder Init success")
            else:
                raise RuntimeError("Decoder Init failed")

            if self.Decoder == self.MP3:
                FoundSyncWordAt = MP3Decoder.MP3_Start(
                    self.InBuffer.Buffer[self.InBuffer.get_readPos() :], self.InBuffer.get_read_available()
                )
            elif self.Decoder == self.OGGVORBIS:
                FoundSyncWordAt = VorbisDecoder.Vorbis_Start(
                    self.InBuffer.Buffer[self.InBuffer.get_readPos() :], self.InBuffer.get_read_available()
                )

            if FoundSyncWordAt >= 0:
                self.DEBUG and print("Decoder Start success. Sync word at", FoundSyncWordAt)
                self.InBuffer.bytes_wasRead(FoundSyncWordAt)
                self.current_track_bytes_decoded = self.current_track_bytes_decoded + FoundSyncWordAt
                self.InHeader = False
                # self.current_track = self.track_being_read
                # self.next_track = self.set_next_track()
            else:
                raise RuntimeError("Decoder Start failed")
        buffer_level_out = self.decode_chunk()
        buffer_level_in = self.InBuffer.buffer_level()
        return min(buffer_level_in, buffer_level_out)

    @micropython.native
    def decode_chunk(self, timeout=10):
        TimeStart = time.ticks_ms()
        break_reason = 0
        break_reasons = {0: "Unknown", 1: "Out Buffer Full", 2: "Timeout", 3: "InBuffer Dry", 4: "Finished Decoding"}
        counter = 0  # Just for debugging. See how many times we run the loop before timeout
        while True:
            # Do we have at least 5000 bytes available for the decoder to write to? If not we return and wait for the play loop to free up some space.
            if self.OutBuffer.get_write_available() < 5000:  # Note: this can change write_pos
                break_reason = 1
                break
            # Don't stay in the loop too long or we affect the responsiveness of the main app
            if time.ticks_diff(time.ticks_ms(), TimeStart) > timeout:
                break_reason = 2
                break
            InBytesAvailable = self.InBuffer.get_read_available()
            # return if the InBuffer is at running dry.
            # if not self.FinishedStreaming and self.InBuffer.buffer_level() < 0.20:
            #    break_reason = 3
            #    break
            # Normally, the decoder needs around 4096 bytes to decode the next packet.
            # However at the end of the playlist we have to let smaller packets through or the end of the last song will be cut off
            if not self.FinishedStreaming and self.InBuffer.get_bytes_in_buffer() < 4096:
                break_reason = 3
                break
            # We have finished streaming and decoding, but the play loop hasn't finished yet
            if InBytesAvailable == 0:
                break_reason = 4
                break

            counter += 1

            # For OggVorbis it takes about 14ms to decode 1024 samples, which is about 23ms worth of audio. Ratio 1:1.64 i.e. 1ms of decoding gives us 1.64ms of audio
            # For MP3 it takes about 18ms to decode 1152 samples, which is about 26ms worth of audio. Ratio: 1:1.44 i.e. 1ms of decoding gives us 1.44ms of audio
            # print(f"Decoding: {self.InBuffer.get_readPos()}", end=' ')

            if self.Decoder == self.MP3:
                Result, BytesLeft, AudioSamples = MP3Decoder.MP3_Decode(
                    self.InBuffer.Buffer[self.InBuffer.get_readPos() :],
                    InBytesAvailable,
                    self.OutBuffer.Buffer[self.OutBuffer.get_writePos() :],
                )
            elif self.Decoder == self.OGGVORBIS:
                Result, BytesLeft, AudioSamples = VorbisDecoder.Vorbis_Decode(
                    self.InBuffer.Buffer[self.InBuffer.get_readPos() :],
                    InBytesAvailable,
                    self.OutBuffer.Buffer[self.OutBuffer.get_writePos() :],
                )

            # print(f"Decoded: {InBytesAvailable - BytesLeft}. Ret:{Result}. Samples:{AudioSamples}. Total:{self.current_track_bytes_decoded}. Time:{time.ticks_diff(time.ticks_ms(), t)}")

            if Result == 0 or Result == 100 or Result == 110:
                self.current_track_bytes_decoded = self.current_track_bytes_decoded + InBytesAvailable - BytesLeft
                self.InBuffer.bytes_wasRead(InBytesAvailable - BytesLeft)

                if self.Decoder == self.MP3 and Result == 0:
                    self.OutBuffer.bytes_wasWritten(AudioSamples * 2)
                elif self.Decoder == self.OGGVORBIS and Result == 0:
                    self.OutBuffer.bytes_wasWritten(AudioSamples * 4)
                # self.DEBUG and print("Read Packet success. Result:", Result, ", Bytes Left:", BytesLeft, ", Audio Samples:", AudioSamples)
                pass
            elif Result == -6:  # Either the TAG at the end of the filea, or a corrupted packet
                pos = self.InBuffer.get_readPos()

                if (
                    self.InBuffer.Bytes[pos] == ord(b"T")
                    and self.InBuffer.Bytes[pos + 1] == ord(b"A")
                    and self.InBuffer.Bytes[pos + 2] == ord(b"G")
                ):  # ID3 tag at the end. Fixed size of 128 bytes. Skip it.
                    print("Skipping TAG")
                    self.InBuffer.get_read_available()
                    self.InBuffer.bytes_wasRead(
                        128
                    )  # // This is an V1.x id3tag after an audio block, ID3 v1 tags are ASCII. Version 1.x is a fixed size at the end of the file (128 bytes) after a TAG keyword.
                    self.current_track_bytes_decoded = self.current_track_bytes_decoded + 128
                else:
                    raise RuntimeError("Corrupted packet")  # Not sure what we should do here. Maybe we could handle it?
                pass
            else:
                self.DEBUG and print("Decode Packet failed. Error:", Result)
                raise RuntimeError("Decode Packet failed")

            # Check if we have decoded to the end of the current track
            if len(self.TrackEnds) > 0:  # Do we have any end-of-track markers stored?
                if self.current_track_bytes_decoded == self.TrackEnds[0]:  # We have finished decoding the current track
                    print("Finished decoding track", self.current_track, " - ", end="")
                    self.TrackEnds.pop(0)  # Remove the current end-of-track marker from the list
                    MP3Decoder.MP3_Close()  # This frees up all the buffers that the decoder allocated, and resets its state
                    VorbisDecoder.Vorbis_Close()
                    # self.audio_out.deinit() # Don't close I2S here, as it still has to play the last part of the track

                    if self.current_track + 1 < self.ntracks:  # Start decode of next track
                        self.DEBUG and print("starting decode of track", self.current_track + 1)
                        self.current_track += 1
                        self.next_track = self.set_next_track()
                        self.callbacks["display"](*self.track_names())
                        self.AtTrackStart = True
                    else:  # We have finished decoding the whole playlist. Now we just need to wait for the play loop to run out
                        print("end of playlist")
                        self.FinishedDecoding = True
                        self.playlist_started = False
                    break

            # If we have more than 1 second of output samples buffered (2 channels, 2 bytes per sample), set up the I2S device and start playing them.
            # Don't check self.OutBuffer.get_read_available here
            if self.PlayLoopRunning == False and self.OutBuffer.get_bytes_in_buffer() / 44100 / 2 / 2 > 1:
                self.DEBUG and print("************ Initiate Playing ************")

                # Get info about this stream
                if self.Decoder == self.MP3:
                    channels, sample_rate, bits_per_sample, bit_rate = MP3Decoder.MP3_GetInfo()
                elif self.Decoder == self.OGGVORBIS:
                    channels, sample_rate, bits_per_sample, bit_rate = VorbisDecoder.Vorbis_GetInfo()

                self.DEBUG and print("Channels:", channels)
                self.DEBUG and print("Sample Rate:", sample_rate)
                self.DEBUG and print("Bits per Sample:", bits_per_sample)
                self.DEBUG and print("Bitrate:", bit_rate)

                # If it doesn't already exist, set up the first I2S peripheral (0) based on the stream info, and make it async with a callback
                if self.audio_out == None:
                    self.audio_out = I2S(
                        0,
                        sck=sck_pin,
                        ws=ws_pin,
                        sd=sd_pin,
                        mode=I2S.TX,
                        bits=bits_per_sample,
                        format=I2S.STEREO if channels == 2 else I2S.MONO,
                        rate=sample_rate,
                        ibuf=self.ChunkSize,
                    )

                    # Make the I2S device asyncronous by defining a callback
                    self.audio_out.irq(self.i2s_callback)

                # Start the playback loop by playing the first chunk. The callback will play the next chunk when it returns
                self.play_chunk()
                self.PlayLoopRunning = True  # So that we don't call this again
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
