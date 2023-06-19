import network, time, Player, socket
from machine import Pin, I2S


sck_pin = Pin(13)  # Serial clock output
ws_pin = Pin(14)  # Word clock output
sd_pin = Pin(17)  # Serial data output


def get_redirect_location(headers):
    for line in headers.split(b"\r\n"):
        if line.startswith(b"Location:"):
            return line.split(b": ", 1)[1]
    return None


def parse_redirect_location(location):
    parts = location.decode().split("://", 1)[1].split("/", 1)
    host_port = parts[0].split(":", 1)
    host = host_port[0]
    port = int(host_port[1]) if len(host_port) > 1 else 80
    path = "/" + parts[1] if len(parts) > 1 else "/"
    return host, port, path


class AudioPlayer:
    def __init__(self, callbacks={}):
        self.callbacks = callbacks
        self.DEBUG = False
        self.PLAY_STATE = 0  # 0 = init, 1 = playing , 2 = paused
        self.BlockFlag = False
        self.TotalData = 0
        self.sock = None
        self.audio_out = None
        self.channels = 0
        self.max_frame_size = 0

        self.HeaderBufferSize = 8192
        self.InBufferSize = 4096
        self.OutBufferSize = 132095  # Max size the I2S device will use for its buffer is 132095

        HeaderBuffer = bytearray(self.HeaderBufferSize)  # An array to hold the Header data of the stream
        self.HeaderBufferMV = memoryview(HeaderBuffer)

        InBuffer = bytearray(self.InBufferSize)  # An array to hold samples which we read from the network
        self.InBufferMV = memoryview(InBuffer)

        # An array to hold decoded audio samples. This needs to be bigger than the incoming samples buffer as the decoder expands the data
        OutBuffer = bytearray(self.OutBufferSize)
        self.OutBufferMV = memoryview(OutBuffer)

        self.playlist = self.tracklist = []
        self.ntracks = 0
        self.current_track = self.next_track = None  # the index of current track in playlist
        self.buffer_status = "inactive"

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

    def i2s_callback(self, t):
        print("*", end="")
        self.BlockFlag = False

    # There is a bit of a balancing act going on with buffers here:
    # The Header buffer needs to be big enough to hold the header. By observation, headers are around 4k in size but I don't know how big they can get. So it is made a generous size (8k)
    # What is left in the Headerbuffer after the header has been processed is then copied to the Inbuffer. So the Inbuffer needs to be big enough to hold that.
    # The Inbuffer is deliberately smaller than the Headerbuffer, because the decoder expands the data in the Inbuffer into data in the Outbuffer, and the Outbuffer can't be bigger than 129kb, as that is the max size of the I2S buffer.
    # So if the Inbuffer is too big, we will overflow the Outbuffer.
    # However, if the Inbuffer is too small then data that is left in the Headerbuffer after the header has been processed will overflow the Inbuffer

    def play(self):
        if self.PLAY_STATE == 0:
            self.prep_URL(self.playlist[self.current_track])
        elif self.PLAY_STATE == 1:
            print(f"Playing URL {self.playlist[self.current_track]}")
        self.PLAY_STATE = 1

    def pause(self):
        print(f"Pausing URL {self.playlist[self.current_track]}")
        if self.PLAY_STATE == 1:
            self.PLAY_STATE = 2

    def stop(self):
        self.PLAY_STATE = 0

    def rewind(self):
        self.advance_track(-1)

    def ffwd(self):
        self.advance_track()

    def advance_track(self, increment=1):
        if not 0 <= (self.current_track + increment) <= self.ntracks:
            if self.PLAY_STATE == 1:
                self.stop()
            return
        self.current_track += increment
        self.next_track = self.current_track + 1 if self.ntracks > (self.current_track + 1) else None
        self.callbacks["display"](*self.track_names())
        if self.PLAY_STATE == 1:  # Play the track that we are advancing to if playing
            self.PLAY_STATE = 0
            self.play()

    def prep_URL(self, url, port=80):
        self.PLAY_STATE = 1
        with open("current_url.py", "w") as f:
            f.write(url)
        _, _, host, path = url.split("/", 3)
        addr = socket.getaddrinfo(host, port)[0][-1]
        self.sock = socket.socket()

        # Experimental. May not work
        # sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 8192)
        # sock.settimeout(0.05)

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
            redirect_location = get_redirect_location(response_headers)
            if redirect_location:
                # Extract the new host, port, and path from the redirect location
                new_host, new_port, new_path = parse_redirect_location(redirect_location)
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

        SamplesOut = 0
        self.TotalData = 0
        data = -1
        TimeStart = time.ticks_ms()

        # Fill the header buffer. May take multiple reads
        while (self.TotalData < self.HeaderBufferSize) and (data != 0):
            data = self.sock.readinto(self.HeaderBufferMV[self.TotalData :], self.HeaderBufferSize - self.TotalData)
            # Let the WiFi thread have some CPU time (not sure if needed as it *may* run on a different thread)
            time.sleep_ms(2)
            # print('r:', data, time.ticks_ms(), end=' ')
            if data != None:
                self.TotalData += data

        dtime = time.ticks_ms() - TimeStart
        print(
            f"Filled header buffer. Time: {dtime} ms. Total Data: {self.TotalData}\n" if (self.DEBUG and dtime > 10) else " ",
            end="",
        )

        # Process the header when we first start streaming the data, to initialise the decoder & set up buffers
        PlayerBuffer = bytearray(200000)  # Create a big buffer for the decoder to use (200kB seems enough)
        PlayerBufferMV = memoryview(PlayerBuffer)

        # Decode the header. This will return how many bytes it has consumed from the buffer
        Used = Player.Vorbis_Start(PlayerBufferMV, self.HeaderBufferMV)
        print("Header used", Used, "bytes") if self.DEBUG else None

        # Copy what's left in the header buffer to the Inbuffer for later decoding
        if Used < self.HeaderBufferSize:
            self.InBufferMV[: (self.HeaderBufferSize - Used)] = self.HeaderBufferMV[-(self.HeaderBufferSize - Used) :]
            self.TotalData = self.HeaderBufferSize - Used

        # Get info about this stream
        self.channels, sample_rate, setup_memory_required, temp_memory_required, self.max_frame_size = Player.Vorbis_GetInfo()
        # print("MaxFrameSize", self.max_frame_size)

        # Set up the first I2S peripheral (0), make it async with a callback
        self.audio_out = I2S(
            0,
            sck=sck_pin,
            ws=ws_pin,
            sd=sd_pin,
            mode=I2S.TX,
            bits=16,
            format=I2S.STEREO if self.channels == 2 else I2S.MONO,
            rate=sample_rate,
            ibuf=self.OutBufferSize,
        )
        # Max bufffer is 132095 (129kB). We have to assume 16-bit samples as there is no way to read it from the stream info.
        self.audio_out.irq(self.i2s_callback)

    def Audio_Pump(self):
        SamplesOut = 0

        if self.PLAY_STATE != 1:  # Only while playing
            self.buffer_status = "inactive"
            return self.buffer_status

        if self.sock == None:
            raise ValueError("Need to call prep_URL first")

        # Decode the rest of the stream
        while True:
            Data = -1
            TimeStart = time.ticks_ms()

            if self.TotalData == self.InBufferSize:
                print(".", end="") if self.DEBUG else None
            else:
                # Fill the Inbuffer. May take multiple reads. We may exit with data == 0 which means we are at the end of the stream, but we still need to play the last buffer
                while (self.TotalData < self.InBufferSize) and (Data != 0):
                    Data = self.sock.readinto(self.InBufferMV[self.TotalData :], self.InBufferSize - self.TotalData)
                    # Let the WiFi thread have some CPU time (not sure if needed as it *may* run on a different thread)
                    time.sleep_ms(2)
                    # print('r:', data, time.ticks_ms(), end=' ')
                    if Data != None:
                        self.TotalData += Data

                dtime = time.ticks_ms() - TimeStart
                print(
                    f"Filled header buffer. Time: {dtime} ms. Total Data: {self.TotalData}\n"
                    if (self.DEBUG and dtime > 10)
                    else " ",
                    end="",
                )

            # We will block here (except for the first time through) until the I2S callback is fired. i.e. I2S has finished playing and needs more data
            if self.BlockFlag == True:
                self.buffer_status = "pumping"
                return self.buffer_status

            if self.PLAY_STATE > 1:
                self.buffer_status = "paused"
                return self.buffer_status

            self.TotalData = 0

            # We have some data. Repeatedly call the decoder to decode one chunk at a time from Inbuffer, and build up audio samples in Outbuffer
            Used = 0
            # print('w', time.ticks_ms(), end='') #str(data, 'utf8'), end='')

            while True:
                # Make sure that we have enough OutBuffer space left for one more frame
                if (SamplesOut * self.channels * 2) + (self.max_frame_size * self.channels * 2) > self.OutBufferSize:
                    break

                # print("Calling decoder with offset", Used)
                BytesUsed, AudioSamples = Player.Vorbis_Decode(
                    self.InBufferMV[Used:], self.InBufferSize - Used, self.OutBufferMV[(SamplesOut * self.channels * 2) :]
                )  # Multiply by 2 because we are assuming 16-bit samples

                print("Decoded", BytesUsed, "to", AudioSamples) if self.DEBUG else None
                # BytesUsed is the number of bytes used from the buffer
                # AudioSamples is the number of decoded audio samples available. Each sample is 2 bytes (16 bits) x number of channels, so usually will be 4 bytes

                if BytesUsed == 0:
                    # No more usable data in the Inbuffer. There may still be some data at the end which is not enough to decode
                    if Data == 0:
                        # If the decoder has finished decoding the Inbuffer AND the last read was zero, then we must be at the end of the stream. Otherwise just break out of the loop, play any samples and fill the Inbuffer again
                        print("Stream finished")
                        self.audio_out.deinit()
                        self.sock.close()
                        Player.Vorbis_Close()
                        self.advance_track()
                        self.buffer_status = "track_finished"
                        return self.buffer_status
                    break

                SamplesOut += AudioSamples
                Used += BytesUsed

            # If we got audio data, play it
            if SamplesOut > 0:
                print(f"{SamplesOut} samples to audio buffer") if self.DEBUG else None
                # Returns straight away. Multiply by 2 because we are assuming 16-bit samples
                numout = self.audio_out.write(self.OutBufferMV[: SamplesOut * self.channels * 2])
                # SamplesOut = max(SamplesOut - 1024,0)
                self.BlockFlag = True

            # We may still have some data at the end of the buffer which was too short to decode. If so, move it to the beginning
            print(self.InBufferSize - Used, "bytes left") if self.DEBUG else None
            if Used < self.InBufferSize:
                self.InBufferMV[: (self.InBufferSize - Used)] = self.InBufferMV[-(self.InBufferSize - Used) :]
                self.TotalData = self.InBufferSize - Used
