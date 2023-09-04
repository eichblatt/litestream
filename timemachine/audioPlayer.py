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

import network, time, Player, socket
from machine import Pin, I2S
import machine

sck_pin = Pin(13)  # Serial clock output
ws_pin = Pin(14)  # Word clock output
sd_pin = Pin(17)  # Serial data output

# For the buffer between the network and the decoder we use a Ring Buffer with an exta "overflow" area at the beginning.
# If the space between readPos and the end of the buffer is less than OverflowSize then we copy data from the end of the buffer to the overflow area so that the mp3/Vorbis frame is always completed.
#
# Notes:
# 1) We only ever write to the main buffer area. The buffer itself handles copying data to the overflow area when required, transparently to the consumer of the buffer
# 2) If there are x bytes of data in the overflow area, we limit the write to x bytes less than the main buffer so that the total data available is always <= BufferSize
# 3) Calling get_read_available() can change the readPos if it copies data to the overflow area
# 4) After every read and write you must call bytes_wasRead or bytes_wasWritten respectively to update the read and write pointers
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

    # Returns the pointer to where we can read from
    def get_writePos(self):
        return self._writePos

    # Returns the number of bytes in the buffer
    def get_bytes_in_buffer(self):
        return self.BytesInBuffer

    # How many bytes can we add to the buffer before filling it
    def get_write_available(self):
        if self._writePos > self._readPos:
            BytesInOverflow = max(
                self.OverflowSize - self._readPos, 0
            )  # If the read_pos is within the overflow area return the num bytes in there, else zero
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

    # How many bytes can we read from the buffer before it is empty. If there are less than "OverflowSize" bytes available at the end of the buffer, move the bytes at the end of the buffer into the overflow area.
    # Note this function can change the readPos
    def get_read_available(self):
        if self._writePos > self._readPos:
            return self._writePos - self._readPos
        else:  # self._writePos <= self._readPos:
            if self.BytesInBuffer == 0:  # Buffer is empty
                return 0
            else:  # Buffer has data
                if (
                    self.BufferSize + self.OverflowSize - self._readPos > self.OverflowSize
                ):  # The data left to read is larger than the overflow buffer, so just return the bytes left to read
                    return self.BufferSize + self.OverflowSize - self._readPos
                else:  # The data left to read is smaller than the overflow buffer, so move it to the overflow buffer and update the readPos
                    bytesToMove = self.BufferSize + self.OverflowSize - self._readPos
                    self.Buffer[(self.OverflowSize - bytesToMove) : self.OverflowSize] = self.Buffer[
                        -bytesToMove:
                    ]  # Move the last bytes into the overflow area
                    self._readPos = self.OverflowSize - bytesToMove
                    return bytesToMove + self._writePos - self.OverflowSize

    # Tell the buffer how many bytes we just read.  Must call this after every read from the buffer
    def bytes_wasRead(self, count):
        self.BytesInBuffer -= count
        assert self.BytesInBuffer >= 0, "InBuffer Underflow"
        self._readPos = self._readPos + count


####################### End of InRingBuffer #######################


# For the buffer between the decoder and the I2S output we use a Ring Buffer. Because the decoder must always be able to write one full frame (1024 samples = 4096 bytes at 16 bit stereo) we only return get_write_available if we have at least 4096 bytes available.
# If there are less than 4096 bytes available, then the writer has to wait until the reader has freed up enough space (done in the I2S callback)
# Because this means we won't always fill the buffer before wrapping, we keep track of a "high water mark" (_endPos) to let the reader know how far to read before it wraps
#
# Notes:
# If read_pos is near the end of outBuffer then get_read_available only shows a little bit of data even though the write pointer has wrapped and written lots more.
# Therefore, be careful about checking get_read_available as an indicator of buffer fullness - use get_bytes_in_buffer() instead
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

    def get_writePos(self):  # Returns the pointer to where we can read from
        return self._writePos

    # How many bytes can we add to the buffer before filling it. Note this function can change the writePos
    def get_write_available(self):
        if self._writePos > self._readPos:  # We are writing ahead of the read pointer
            if self.BufferSize - self._writePos < 4096:  # Not enough space to write 4096 contiguous bytes, so wrap around
                self._writePos = 0
                return self._readPos  # We wrapped, so can write up to readpos
            else:  # There is enough room to write 4096 bytes, so we can write up to the end of the buffer as we are ahead of the read pointer
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
            assert self._writePos + count <= self._readPos, "OutBuffer Overwrite"
        self.BytesInBuffer += count
        assert self.BytesInBuffer <= self.BufferSize, "OutBuffer Overflow"
        self._writePos += count  # The caller must call get_write_available before calling this, so we should never overwrite the end of the buffer
        assert self._writePos <= self.BufferSize, "Outbuffer Overflow2"  # We wrote past the end of the buffer

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
        assert self.BytesInBuffer >= 0, "OutBuffer Underflow"
        self._readPos += count  # The caller must call get_read_available before calling this, so we should never overwrite the end of the buffer
        assert self._readPos <= self._endPos, "Outbuffer Underflow2"  # We should never read past the high water mark

        # We have read to the high water mark so wrap back around to the beginning of the buffer and reset the high water mark
        if self._readPos == self._endPos:
            if self._readPos != self._writePos:  # If the reader caught up to the writer, then don't wrap in this case
                self._readPos = 0  # Otherwise wrap
                self._endPos = self._writePos  # The new high water mark is where the current writepos is


####################### End of OutRingBuffer #######################


class AudioPlayer:
    def __init__(self, callbacks={}, debug=False):
        self.STOPPED, self.PLAYING, self.PAUSED = 0, 1, 2
        self.callbacks = callbacks
        if not "display" in self.callbacks.keys():
            self.callbacks["display"] = lambda x, y: None
        self.DEBUG = debug
        self.PLAY_STATE = self.STOPPED
        self.sock = None
        self.audio_out = None
        self.Player = Player

        self.playlist = self.tracklist = []
        self.ntracks = 0

        # The index of the current track in the playlist that we are playing (actually this is which track we are currently decoding - playback lags by the size of the OutBuffer)
        self.current_track = self.next_track = self.track_being_read = None

        # Size of the chunks of decoded audio that we will send to I2S
        self.ChunkSize = 100 * 1024

        # An array to hold packets from the network. As an example, a 96000 bps bitrate is 12kB per second, so a ten second buffer should be about 120kB
        InBufferSize = 120 * 1024

        # Maximum segment size is 512 bytes, so use 600 to be sure
        InOverflowBufferSize = 4096
        self.InBuffer = InRingBuffer(InBufferSize, InOverflowBufferSize)

        # An array to hold decoded audio samples. 44,100kHz takes 176,400 bytes per second (16 bit samples, stereo). e.g. 1MB will hold 5.9 seconds, 700kB will hold 4 seconds
        OutBufferSize = 900 * 1024
        self.OutBuffer = OutRingBuffer(OutBufferSize)

        self.reset_player()

    def reset_player(self):
        self.PlayLoopRunning = False
        self.FinishedStreaming = False
        self.FinishedDecoding = False
        self.InHeader = True

        if self.ntracks > 0:
            self.current_track = 0
            self.next_track = 1 if self.ntracks > 1 else None

        # A list of offsets into the InBuffer where the tracks end. This tells the decoder when to move onto the next track by decoding the next header
        self.TrackEnds = []

        # Keep track of how many bytes of the current track that we are streaming from the network
        # (this is potentially different to which track we are currently playing. We could be reading ahead of playing by one or more tracks)
        self.current_track_bytes_read = 0
        self.current_track_length = 0

        self.InBuffer.InitBuffer()
        self.OutBuffer.InitBuffer()

        # This frees up all the buffers that the decoder allocated, and resets its state
        Player.Vorbis_Close()

        if self.sock is not None:
            self.sock.close()
            self.sock = None

    @micropython.native
    def play_chunk(self):  # Don't be tempted to just put this function directly in to i2s_callback(). Weird errors occur...
        BytesToPlay = min(self.OutBuffer.get_read_available(), self.ChunkSize)  # Play what we have, up to the chunk size

        # We can get zero bytes to play if the buffer is starved, or when we reach the end of the playlist
        if BytesToPlay == 0:
            if self.FinishedDecoding:  # End of playlist
                self.DEBUG and print("Finished Playing")
                self.PLAY_STATE = self.STOPPED  # Stop the playback loop
                self.reset_player()
                return
            else:  # Buffer starved
                # The output buffer can get starved if the network is slow, or if we write too much debug output
                self.DEBUG and print("Play buffer starved")
                self.PlayLoopRunning = (
                    False  # Set this flag to re-start the player loop when the decoder has generated enough data
                )
                return

        Offset = self.OutBuffer.get_readPos()

        # Make a memoryview of the output buffer slice. We have to do this instead of slicing OutBuffer.Buffer
        # because slicing a memoryview creates a new memoryview, and we cannot allocate memory in an ISR
        outbytes = memoryview(self.OutBuffer.Bytes[Offset : Offset + BytesToPlay])

        try:
            self.OutBuffer.bytes_wasRead(BytesToPlay)
        except Exception as e:
            self.DEBUG and print("Buffer error. Stopping playback loop", e)
            self.PLAY_STATE = self.STOPPED  # Stop the playback loop
            self.current_track = 0
            self.reset_player()
            return

        numout = self.audio_out.write(outbytes)  # Write the PCM data to the I2S device. Returns straight away
        assert numout == BytesToPlay, "I2S write error"

    @micropython.native
    def i2s_callback(self, t):
        if self.PLAY_STATE == self.PLAYING:
            self.play_chunk()

    def set_playlist(self, tracklist, urllist):
        assert len(tracklist) == len(urllist)
        self.ntracks = len(tracklist)
        self.tracklist = tracklist
        setbreak_url = "https://storage.googleapis.com/spertilo-data/sundry/silence600.ogg"
        urllist = [x if not (x.endswith("silence600.ogg")) else setbreak_url for x in urllist]
        encorebreak_url = "https://storage.googleapis.com/spertilo-data/sundry/silence0.ogg"
        urllist = [x if not (x.endswith("silence0.ogg")) else encorebreak_url for x in urllist]
        self.playlist = urllist
        if self.ntracks > 0:
            self.current_track = 0
            self.next_track = 1 if self.ntracks > 1 else None
        self.callbacks["display"](*self.track_names())

    def track_status(self):
        if self.current_track is None:
            return None
        return {"current_track": self.current_track, "next_track": self.next_track, "ntracks": self.ntracks}

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
            self.DEBUG and print(f"Playing URL {self.playlist[self.current_track]}")
        elif self.PLAY_STATE == self.PAUSED:
            self.DEBUG and print(f"Un-pausing URL {self.playlist[self.current_track]}")
            self.PLAY_STATE = self.PLAYING
            self.play_chunk()  # Kick off the playback loop

    def pause(self):
        self.DEBUG and print(f"Pausing URL {self.playlist[self.current_track]}")
        if self.PLAY_STATE == self.PLAYING:
            self.PLAY_STATE = self.PAUSED

    def rewind(self):
        self.DEBUG and print("in rewind")
        self.stop(reset_head=False)
        self.advance_track(-1)

    def ffwd(self):
        self.DEBUG and print("in ffwd")
        self.stop(reset_head=False)
        self.advance_track()

    def stop(self, reset_head=True):
        if self.PLAY_STATE == self.STOPPED:
            return
        self.PLAY_STATE = self.STOPPED
        if reset_head:
            self.current_track = 0
            self.next_track = self.current_track + 1 if self.ntracks > (self.current_track + 1) else None
            self.callbacks["display"](*self.track_names())
        self.reset_player()

    def advance_track(self, increment=1):
        print("Advance")
        if not 0 <= (self.current_track + increment) <= self.ntracks:
            if self.PLAY_STATE == self.PLAYING:
                self.stop()
            return

        self.current_track += increment
        self.next_track = self.current_track + 1 if self.ntracks > (self.current_track + 1) else None
        self.callbacks["display"](*self.track_names())
        if self.PLAY_STATE == self.PLAYING:  # Play the track that we are advancing to if playing
            self.PLAY_STATE = self.STOPPED
            self.reset_player()
            self.play()

    def is_paused(self):
        return self.PLAY_STATE == self.PAUSED

    def is_stopped(self):
        return self.PLAY_STATE == self.STOPPED

    def is_playing(self):
        return self.PLAY_STATE == self.PLAYING

    def read_header(self, trackno, offset=0, port=80):
        TimeStart = time.ticks_ms()
        self.track_being_read = trackno
        url = self.playlist[trackno]
        _, _, host, path = url.split("/", 3)
        addr = socket.getaddrinfo(host, port)[0][-1]

        if self.sock is not None:  # We might have a socket already from the previous track
            self.sock.close()

        self.sock = socket.socket()

        self.DEBUG and print("Getting", path, "from", host, "Port:", port)
        self.sock.connect(addr)
        self.sock.setblocking(False)  # Tell the socket to return straight away (async)

        # Request the file with optional offset (Use an offset if we're re-requesting the same file after a long pause)
        self.sock.send(bytes(f"GET /{path} HTTP/1.1\r\nHost: {host}\r\nRange: bytes={offset}-\r\n\r\n", "utf8"))

        # Read the response headers
        response_headers = b""
        while True:
            header = self.sock.readline()
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
                self.sock = socket.socket()
                addr = socket.getaddrinfo(new_host, new_port)[0][-1]
                self.sock.connect(addr)
                self.sock.setblocking(False)  # Return straight away

                # Request the file with optional offset (Use an offset if we're re-requesting the same file after a long pause)
                self.sock.send(bytes(f"GET /{new_path} HTTP/1.1\r\nHost: {new_host}\r\nRange: bytes={offset}-\r\n\r\n", "utf8"))

                # Skip the response headers
                while True:
                    header = self.sock.readline()

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
    def audio_pump(self):
        if self.is_stopped():
            return

        TimeStart = time.ticks_ms()

        # If there is any free space in the input buffer then add any data available from the network.
        if self.sock is not None:  # If there is no socket than we have already read to the end of the playlist
            if (BytesAvailable := self.InBuffer.get_write_available()) > 0:
                try:  # We can get an exception here if we pause too long and the underlying socket gets closed
                    # Read real data into the InBuffer
                    data = self.sock.readinto(self.InBuffer.Buffer[self.InBuffer.get_writePos() :], BytesAvailable)

                    # Is there new data available? The readinto will return None if there is no data available, or 0 if the socket is closed
                    if data is not None:
                        # Keep track of how many bytes of the current file we have read.
                        # We will need this if the user pauses for too long and we need to request the current track from the server again
                        self.current_track_bytes_read += data
                        self.InBuffer.bytes_wasWritten(data)

                        if (
                            data == 0
                        ):  # Peer closed socket. This can be because of End-of-stream or it can happen in a long pause before our socket closes
                            if self.current_track_length == self.current_track_bytes_read:  # End of track
                                self.TrackEnds.append(
                                    self.InBuffer.get_writePos()
                                )  # Store the end-of-track marker for this track
                                self.DEBUG and print(f"EOF. Track end at {self.InBuffer.get_writePos()}. ", end="")
                                self.DEBUG and print(f"Bytes read: {self.current_track_bytes_read} - ", end="")
                                if self.track_being_read + 1 < self.ntracks:
                                    self.DEBUG and print("reading next track")
                                    self.read_header(self.track_being_read + 1)  # We can read the header of the next track now
                                    self.current_track_bytes_read = 0
                                else:
                                    self.DEBUG and print("end of playlist")
                                    self.FinishedStreaming = True  # We have no more data to read from the network, but we have to let the decoder run out, and then let the play loop run out
                                    self.sock.close()
                                    self.sock = None
                            else:  # Peer closed its socket, but not at the end of the track
                                print("Peer close")
                                raise RuntimeError("Peer closed socket")  # Will be caught by the 'except' below

                except Exception as e:
                    # The user probably paused too long and the underlying socket got closed
                    # In this case we re-start playing the current track at the offset that we got up to before the pause. Uses the HTTP Range header to request data at an offset
                    self.DEBUG and print("Socket Exception:", e, " Restarting track at offset", self.current_track_bytes_read)

                    # Start reading the current track again, but at the offset where we were up to
                    self.read_header(self.track_being_read, self.current_track_bytes_read)

        # If we are decoding the header, some of the initial packets are up to 2kB
        if self.InHeader and self.InBuffer.get_bytes_in_buffer() < 4096:
            return

        if self.InHeader:
            if self.Player.Vorbis_Init():
                self.DEBUG and print("Decoder Init success")
            else:
                raise RuntimeError("Decoder Init failed")

            FoundSyncWordAt = Player.Vorbis_Start(
                self.InBuffer.Buffer[self.InBuffer.get_readPos() :], self.InBuffer.get_read_available()
            )

            if FoundSyncWordAt >= 0:
                self.DEBUG and print("Decoder Start success. Sync word at", FoundSyncWordAt)
                self.InHeader = False
            else:
                raise RuntimeError("Decoder Start failed")

        # We have some data to decode. Repeatedly call the decoder to decode one chunk at a time from the InBuffer, and build up audio samples in Outbuffer.
        Counter = 0  # Just for debugging. See how many times we run the loop in the 25ms
        while True:
            # Do we have at least 4096 bytes available for the decoder to write to? If not we return and wait for the play loop to free up some space.
            if self.OutBuffer.get_write_available() < 4096:  # Note: this can change write_pos
                break

            InBytesAvailable = self.InBuffer.get_read_available()

            # We have finished streaming and decoding, but the play loop hasn't finished yet
            if InBytesAvailable == 0:
                break

            # Normally, the decoder needs at least 600 bytes to decode the next packet.
            # However at the end of the playlist we have to let smaller packets through or the end of the last song will be cut off
            if not self.FinishedStreaming and self.InBuffer.get_bytes_in_buffer() < 600:
                break

            # Don't stay in the loop too long or we affect the responsiveness of the main app
            if time.ticks_diff(time.ticks_ms(), TimeStart) > 30:
                break

            Counter += 1
            # It takes about 14ms to decode 1024 samples, which is about 23ms worth of audio. So, not a lot of headroom.
            Result, BytesLeft, AudioSamples = self.Player.Vorbis_Decode(
                self.InBuffer.Buffer[self.InBuffer.get_readPos() :],
                InBytesAvailable,
                self.OutBuffer.Buffer[self.OutBuffer.get_writePos() :],
            )

            self.InBuffer.bytes_wasRead(InBytesAvailable - BytesLeft)

            # If we get a I2S completed interrupt here it could mess up the buffer. So disable interrupts.
            state = machine.disable_irq()
            self.OutBuffer.bytes_wasWritten(AudioSamples * 4)
            machine.enable_irq(state)

            if Result == 0:
                # self.DEBUG and print("Read Packet success. Result:", Result, ", Bytes Left:", BytesLeft, ", Audio Samples:", AudioSamples)
                pass
            elif Result == 100:
                # self.DEBUG and print("Need more data. Bytes Left:", BytesLeft)
                pass
            elif Result == 110:
                # self.DEBUG and print("Continued Page. Bytes Left:", BytesLeft)
                pass
            else:
                # self.DEBUG and print("Decode Packet failed. Error:", Result)
                raise RuntimeError("Decode Packet failed")

            # Check if we have decoded to the end of the current track
            if len(self.TrackEnds) > 0:  # Do we have any end-of-track markers stored?
                if self.InBuffer.get_readPos() == self.TrackEnds[0]:  # We have finished decoding the current track
                    self.DEBUG and print("Finished decoding track", self.current_track, " - ", end="")
                    self.TrackEnds.pop(0)  # Remove the current end-of-track marker from the list
                    Player.Vorbis_Close()  # This frees up all the buffers that the decoder allocated, and resets its state
                    # self.audio_out.deinit() # Don't close I2S here, as it still has to play the last part of the track

                    if self.current_track + 1 < self.ntracks:  # Start decode of next track
                        self.DEBUG and print("starting decode of track", self.current_track + 1)
                        self.current_track += 1
                        self.next_track = self.current_track + 1 if self.ntracks > (self.current_track + 1) else None
                        self.callbacks["display"](*self.track_names())
                        self.InHeader = True
                    else:  # We have finished decoding the whole playlist. Now we just need to wait for the play loop to run out
                        self.DEBUG and print("end of playlist")
                        self.FinishedDecoding = True

                    return

            # If we have more than 1 second of output samples buffered (2 channels, 2 bytes per sample), set up the I2S device and start playing them.
            # Don't check self.OutBuffer.get_read_available here
            if self.PlayLoopRunning == False and self.OutBuffer.get_bytes_in_buffer() / 44100 / 2 / 2 > 1:
                self.DEBUG and print("************ Initiate Playing ************")

                # Get info about this stream
                channels, sample_rate, bits_per_sample, bit_rate = self.Player.Vorbis_GetInfo()
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
