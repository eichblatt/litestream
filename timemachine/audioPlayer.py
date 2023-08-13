import network, time, Player, socket
from machine import Pin, I2S

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

    def get_writePos(self):  # Returns the pointer to where we can read from
        return self._writePos

    def get_write_available(self):  # How many bytes can we add to the buffer before filling it
        if self._writePos > self._readPos:
            BytesInOverflow = max(self.OverflowSize - self._readPos, 0)
            return self.BufferSize + self.OverflowSize - self._writePos - BytesInOverflow
        elif self._writePos < self._readPos:
            return self._readPos - self._writePos
        else:  # readPos == writePos, so buffer is either empty or full
            if self.BytesInBuffer > 0:  # The buffer is full
                return 0
            else:  # The buffer is empty
                return self.BufferSize - self._writePos

    def bytes_wasWritten(
        self, count
    ):  # Tell the buffer how many bytes we just wrote. Must call this after every write to the buffer
        self.BytesInBuffer += count
        assert self.BytesInBuffer <= self.BufferSize, "InBuffer Overflow"
        self._writePos = self.OverflowSize + ((self._writePos - self.OverflowSize + count) % self.BufferSize)

    def get_readPos(self):  # Returns the pointer to where we can read from
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

    def bytes_wasRead(
        self, count
    ):  # Tell the buffer how many bytes we just read.  Must call this after every read from the buffer
        self.BytesInBuffer -= count
        assert self.BytesInBuffer >= 0, "InBuffer Underflow"
        self._readPos = self._readPos + count


####################### End of InRingBuffer #######################


# For the buffer between the decoder and the I2S output we use a Ring Buffer. Because the decoder must always be able to write one full frame (1024 samples = 4096 bytes at 16 bit stereo) we only return get_write_available if we have at least 4096 bytes available.
# If there are less than 4096 bytes available, then the writer has to wait until the reader has freed up enough space (done in the I2S callback)
# Because this means we won't always fill the buffer before wrapping, we keep track of a "high water mark" (_endPos) to let the reader know how far to read before it wraps
#
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

    # Note this function can change the writePos
    def get_write_available(self):  # How many bytes can we add to the buffer before filling it
        if self._writePos > self._readPos:  # We are writing ahead of the read pointer
            if self.BufferSize - self._writePos < 4096:  # Not enough space to write 4096 bytes, so wrap around
                self._writePos = 0
                return self._readPos  # We wrapped, so can write up to readpos
            else:  # There is enough room to write 4096 bytes
                return (
                    self.BufferSize - self._writePos
                )  # We can write up to the end of the buffer as we are ahead of the read pointer
        elif self._writePos < self._readPos:  # We are writing behind the read pointer
            return self._readPos - self._writePos  # We can write up to the read pointer as we are behind the read pointer
        else:  # readPos == writePos, so buffer is either empty or full
            if self.BytesInBuffer > 0:  # The buffer is full
                return 0  # No bytes available to write
            else:  # The buffer is empty, but we are not necessarily writing at the beginning
                return self.BufferSize - self._writePos  # We can write up to the end of the buffer

    def bytes_wasWritten(
        self, count
    ):  # Tell the buffer how many bytes we just wrote. Must call this after every write to the buffer
        if self._writePos < self._readPos:
            assert self._writePos + count <= self._readPos, "OutBuffer Overwrite"
        self.BytesInBuffer += count
        assert self.BytesInBuffer <= self.BufferSize, "OutBuffer Overflow"
        self._writePos += count  # The caller must call get_write_available before calling this, so we should never overwrite the end of the buffer
        assert self._writePos <= self.BufferSize, "Outbuffer Overflow2"  # We wrote past the end of the buffer

        if self._writePos > self._endPos:  # Update the high water mark of the buffer
            self._endPos = self._writePos

    def get_readPos(self):  # Returns the pointer to where we can read from
        return self._readPos

    def get_read_available(self):  # How many bytes can we read from the buffer before it is empty
        if self._readPos > self._writePos:  # We are reading ahead of the write pointer
            return self._endPos - self._readPos  # We can read all the way to the high water mark
        elif self._readPos < self._writePos:  # We are reading behind the write pointer
            return self._writePos - self._readPos  # We can read up to the write pointer
        else:  # readPos == writePos, so buffer is either empty or full
            if self.BytesInBuffer > 0:  # The buffer is full
                return self._endPos - self._readPos  # We can read up to the high water mark
            else:  # The buffer is empty, but we are not necessarily reading from at the beginning
                return 0  # No bytes available to read

    def bytes_wasRead(
        self, count
    ):  # Tell the buffer how many bytes we just read. Must call this after every read from the buffer
        if self._readPos < self._writePos:
            assert self._readPos + count <= self._writePos, "OutBuffer Overread"
        self.BytesInBuffer -= count
        assert self.BytesInBuffer >= 0, "OutBuffer Underflow"
        self._readPos += count  # The caller must call get_read_available before calling this, so we should never overwrite the end of the buffer
        assert self._readPos <= self._endPos, "Outbuffer Underflow2"  # We should never read past the high water mark

        if (
            self._readPos == self._endPos
        ):  # We have read to the high water mark so wrap back around to the beginning of the buffer and reset the high water mark
            self._readPos = 0
            self._endPos = self._writePos  # The new high water mark is where the current writepos is


####################### End of OutRingBuffer #######################


class AudioPlayer:
    def __init__(self, callbacks={}):
        self.STOPPED, self.PLAYING, self.PAUSED = 0, 1, 2
        self.callbacks = callbacks
        if not "display" in self.callbacks.keys():
            self.callbacks["display"] = lambda x, y: None
        self.DEBUG = False
        self.PLAY_STATE = self.STOPPED
        self.sock = None
        self.audio_out = None

        self.playlist = self.tracklist = []
        self.ntracks = 0
        self.current_track = self.next_track = None  # the index of current track in playlist
        self.TrackNumber = 0
        self.ChunkSize = 50 * 1024  # Size of the chunks of decoded audio that we will send to I2S
        self.Started = False

        InBufferSize = (
            120 * 1024
        )  # An array to hold packets from the network. As an example, a 96000 bps bitrate is 12kB per second, so a ten second buffer should be about 120kB
        InOverflowBufferSize = (
            600  # The decoder seems to always take less than 600 bytes at a time from the buffer when decoding
        )
        self.InBuffer = InRingBuffer(InBufferSize, InOverflowBufferSize)

        OutBufferSize = (
            700 * 1024
        )  # An array to hold decoded audio samples. 44,100kHz takes 176,400 bytes per second (16 bit samples, stereo). eg 1MB will hold 5.9 seconds
        self.OutBuffer = OutRingBuffer(OutBufferSize)

    @micropython.native
    def i2s_callback(self, t):
        if self.PLAY_STATE == self.PAUSED:
            return

        BytesToPlay = min(self.OutBuffer.get_read_available(), self.ChunkSize)  # Play what we have, up to the chunk size
        Offset = self.OutBuffer.get_readPos()
        ob = memoryview(self.OutBuffer.Bytes[Offset : Offset + BytesToPlay])
        numout = self.audio_out.write(ob)  # Returns straight away
        assert numout == BytesToPlay, "I2S write error"
        self.OutBuffer.bytes_wasRead(BytesToPlay)

    def set_playlist(self, tracklist, urllist):
        assert len(tracklist) == len(urllist)
        self.ntracks = len(tracklist)
        self.tracklist = tracklist
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
            self.ReadHeader(self.playlist[self.current_track])
            self.PLAY_STATE = self.PLAYING
        elif self.PLAY_STATE == self.PLAYING:
            print(f"Playing URL {self.playlist[self.current_track]}")
        elif self.PLAY_STATE == self.PAUSED:
            self.PLAY_STATE = self.PLAYING
            self.i2s_callback(0)

    def pause(self):
        print(f"Pausing URL {self.playlist[self.current_track]}")
        if self.PLAY_STATE == self.PLAYING:
            self.PLAY_STATE = self.PAUSED

    def rewind(self):
        self.advance_track(-1, mute=True)

    def ffwd(self):
        self.advance_track(mute=True)

    def stop(self):
        self.PLAY_STATE = self.STOPPED
        self.current_track = 0
        try:
            Player.Vorbis_Close()
        except ValueError:
            print("Failed to close player. Perhaps it's not yet open?")

        self.Started = False

        if self.audio_out is not None:
            self.audio_out.deinit()
            self.audio_out = None

        if self.sock is not None:
            self.sock.close()
            self.sock = None

        self.InBuffer.InitBuffer()
        self.OutBuffer.InitBuffer()

    # Use mute if the user pushes the FF/Rew button as we want the music to stop as soon as they push it
    # However if we are advancing because we got to the end of the previous track, then we don't want to mute - just keep playing
    def advance_track(self, increment=1, mute=False):
        if not 0 <= (self.current_track + increment) <= self.ntracks:
            if self.PLAY_STATE == self.PLAYING:
                self.stop()
            return

        self.current_track += increment
        self.next_track = self.current_track + 1 if self.ntracks > (self.current_track + 1) else None
        self.callbacks["display"](*self.track_names())
        if self.PLAY_STATE == self.PLAYING:  # Play the track that we are advancing to if playing
            self.PLAY_STATE = self.STOPPED
            if mute:
                self.Started = False
                self.OutBuffer.InitBuffer()
            Player.Vorbis_Close()
            self.sock.close()
            self.play()

    def IsPaused(self):
        return self.PLAY_STATE == self.PAUSED

    def IsStopped(self):
        return self.PLAY_STATE == self.STOPPED

    def ReadHeader(self, url, port=80):
        _, _, host, path = url.split("/", 3)
        addr = socket.getaddrinfo(host, port)[0][-1]
        self.sock = socket.socket()

        print("Getting", path, "from", host, "Port:", port)
        self.sock.connect(addr)
        self.sock.setblocking(False)  # Tell the socket to return straight away (async)

        self.sock.send(bytes("GET /%s HTTP/1.1\r\nHost: %s\r\n\r\n" % (path, host), "utf8"))

        # Read the response headers
        response_headers = b""
        while True:
            header = self.sock.readline()
            # print(header)
            if header != None:
                response_headers += header.decode("utf-8")
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
                print("Redirecting to", new_host, new_port, new_path)
                self.sock = socket.socket()
                addr = socket.getaddrinfo(new_host, new_port)[0][-1]
                self.sock.connect(addr)
                self.sock.setblocking(False)  # Return straight away

                self.sock.send(bytes("GET /%s HTTP/1.1\r\nHost: %s\r\n\r\n" % (new_path, new_host), "utf8"))

                # Skip the response headers
                while True:
                    header = self.sock.readline()
                    if header == b"\r\n":
                        break

        TimeStart = time.ticks_ms()
        print("Filling Buffer...")

        self.InBuffer.InitBuffer()
        while (BytesAvailable := self.InBuffer.get_write_available()) > 0:
            data = self.sock.readinto(self.InBuffer.Buffer[self.InBuffer.get_writePos() :], BytesAvailable)
            if data:
                self.InBuffer.bytes_wasWritten(data)

        print(
            "Filled buffer. Time:", time.ticks_ms() - TimeStart, "ms. Total Data:", self.InBuffer.get_read_available()
        )  # Note: This can change _readPos

        # Init the decoder
        Result = Player.Vorbis_Init()

        if Result:
            print("Decoder Init success")
        else:
            print("Decoder Init failed")
            return -1

        FoundSyncWordAt = Player.Vorbis_Start(
            self.InBuffer.Buffer[self.InBuffer.get_readPos() :], self.InBuffer.get_read_available()
        )  # Note: This can change _readPos

        if FoundSyncWordAt >= 0:
            print("Decoder Start success. Sync word at", FoundSyncWordAt)
        else:
            print("Decoder Start failed")
            return -1

        # Decode the first part of the file after the sync word to get info that we need about the bitrate etc. Keep going until we don't get "Need more data" any more
        while True:
            BytesAvailable = self.InBuffer.get_read_available()  # Note: This can change _readPos
            # print("Decoding at offset", self.InBuffer.get_readPos())
            Result, BytesLeft, AudioSamples = Player.Vorbis_Decode(
                self.InBuffer.Buffer[self.InBuffer.get_readPos() :], BytesAvailable, self.OutBuffer.Buffer
            )
            # print("Bytes Used:", BytesAvailable - BytesLeft)
            self.InBuffer.bytes_wasRead(BytesAvailable - BytesLeft)

            if Result == 100 or Result == 110:  # Expect 100 (Need more data) or 110 (Continued Packet) here
                TimeStart = time.ticks_ms()
                # print("Read Header Packet success. Result:", Result)
            else:
                print("No more header data. Result:", Result)
                break

        # Get info about this stream
        channels, sample_rate, bits_per_sample, bit_rate = Player.Vorbis_GetInfo()
        print("Channels:", channels)
        print("Sample Rate:", sample_rate)
        print("Bits per Sample:", bits_per_sample)
        print("Bitrate:", bit_rate)

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
            self.audio_out.irq(self.i2s_callback)

    #############################################

    @micropython.native
    def Audio_Pump(self):
        # print("Pump")

        if self.IsStopped():
            return

        if self.sock == None:
            raise ValueError("Need to call ReadHeader first")

        TimeStart = time.ticks_ms()

        # If there is any free space in the input buffer then add any data available from the network.
        if (BytesAvailable := self.InBuffer.get_write_available()) > 0:
            # print("Adding data to buffer", BytesAvailable)
            try:  # Can get an exception here if we pause too long and the underlying socket gets closed
                data = self.sock.readinto(self.InBuffer.Buffer[self.InBuffer.get_writePos() :], BytesAvailable)
            except:
                print("Socket Exception")
                self.stop()
                return -1

            if data:
                # print("Added", data)
                self.InBuffer.bytes_wasWritten(data)

        # We have some data. Repeatedly call the decoder to decode one chunk at a time from the InBuffer, and build up audio samples in Outbuffer.
        while True:
            if self.IsStopped() or self.IsPaused():
                return

            # Do we have at least 4096 bytes available for the decoder to write to?
            if self.OutBuffer.get_write_available() < 4096:
                # print("X", end='')
                return

            # print("Decoding")
            if (InBytesAvailable := self.InBuffer.get_read_available()) < 600:  # Note: This can change _readPos
                # Either the buffer has emptied (slow network) but we are not at the end of the stream yet, or we are actually at the end of the stream. Check to see if the last read returned anything or is an empty object (EOS)
                if data:
                    print("Inbuffer empty")
                    return  # Not enough data to decode
                else:  # End of stream.
                    Player.Vorbis_Close()
                    self.sock.close()
                    self.advance_track()
                    # self.audio_out.deinit()   # Don't close the I2S here, as it still has to play the last packet
                    return 0

            Result, BytesLeft, AudioSamples = Player.Vorbis_Decode(
                self.InBuffer.Buffer[self.InBuffer.get_readPos() :],
                InBytesAvailable,
                self.OutBuffer.Buffer[self.OutBuffer.get_writePos() :],
            )
            self.InBuffer.bytes_wasRead(InBytesAvailable - BytesLeft)
            self.OutBuffer.bytes_wasWritten(AudioSamples * 4)

            if (
                not self.Started and self.OutBuffer.get_read_available() > 44100 * 2 * 2 * 2
            ):  # If we have more than 2 seconds of output samples buffered, start playing them. The callback will play the next chunk when it returns
                print("************ Initiate Playing ************")
                self.i2s_callback(0)
                self.Started = True
                break

            if Result == 0:
                # print("Read Packet success. Result:", Result, ", Bytes Left:", BytesLeft, ", Audio Samples:", AudioSamples)
                pass
            elif Result == 100:
                # print("Need more data. Bytes Left:", BytesLeft)
                pass
            elif Result == 110:
                # print("Continued Page. Bytes Left:", BytesLeft)
                pass
            else:
                print("Read Packet failed. Error:", Result)
                return -1
