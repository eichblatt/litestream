import network, time, Player, socket
from machine import Pin, I2S

sck_pin = Pin(13)   # Serial clock output
ws_pin = Pin(14)    # Word clock output
sd_pin = Pin(17)    # Serial data output

# We use a Ring Buffer with an exta "overflow" area at the beginning. 
# If the space between readPos and the end of the buffer is less than OverflowSize then copy data from the end of the buffer to the overflow area so that the mp3/Vorbis frame is always completed.
#
# Notes:
# 1) We only ever write to the main buffer area. The buffer itself handles copying data to the overflow area when required, transparently to the consumer of the buffer 
# 2) If there is x bytes of data in the overflow area, we limit the write to x bytes less than the main buffer so that the total data available is always <= BufferSize
# 3) Calling get_read_available can change the readPos if it copies data to the overflow area
# 4) After every read and write you must call bytes_wasRead or bytes_wasWritten respectively to update the read and write pointers
#
#
#   0                          OverflowSize              readPos                   writePos          BufferSize + OverflowSize
#   |                               |                       |<------dataLength------->|<-------freeSpace------->|
#   ▼                               ▼                       ▼                         ▼                         ▼
#   -------------------------------------------------------------------------------------------------------------
#   |      <--OverflowSize-->       |                        <--BufferSize-->                                   |
#   -------------------------------------------------------------------------------------------------------------
#                                   |<-----freeSpace------->|
#   
#
#   0                          OverflowSize                       writePos                readPos    BufferSize + OverflowSize
#   |                               |                                |<------freeSpace------>|<---dataLength--->|
#   ▼                               ▼                                ▼                       ▼                  ▼
#   -------------------------------------------------------------------------------------------------------------
#   |      <--OverflowSize-->       |                        <--BufferSize-->                                   |
#   -------------------------------------------------------------------------------------------------------------
#                                   |<------dataLength-------------->|

class RingBuffer:
    def __init__(self, RingBufferSize, OverflowSize):
        self.AudioBytes = bytearray(RingBufferSize + OverflowSize)          # An array to hold the Audio data of the stream
        self.BufferSize = RingBufferSize
        self.OverflowSize = OverflowSize
        self.Buffer = memoryview(self.AudioBytes)
        self.InitBuffer()
            
    def InitBuffer(self):
        self.BytesInBuffer = 0
        self._readPos = self.OverflowSize                                   # The next byte we will read
        self._writePos = self.OverflowSize                                  # The next byte we will write
        
    def get_writePos(self):                                                 # Returns the pointer to where we can read from
        return self._writePos 
    
    def get_write_available(self):                                          # How many bytes can we add to the buffer before filling it
        if self._writePos > self._readPos:
            BytesInOverflow = max(self.OverflowSize - self._readPos, 0)
            return self.BufferSize + self.OverflowSize - self._writePos - BytesInOverflow
        elif self._writePos < self._readPos:
            return self._readPos - self._writePos
        else:                                                               # readPos == writePos, so buffer is either empty or full
            if self.BytesInBuffer > 0:                                      # The buffer is full
                return 0
            else:                                                           # The buffer is empty
                return self.BufferSize - self._writePos
    
    def bytes_wasWritten(self, count):                                      # Tell the buffer how many bytes we just wrote. Must call this after every write to the buffer
        self.BytesInBuffer += count
        assert self.BytesInBuffer <= self.BufferSize, "Buffer Overflow"
        self._writePos = self.OverflowSize + ((self._writePos - self.OverflowSize + count) % self.BufferSize)
                                              
    def get_readPos(self):                                                  # Returns the pointer to where we can read from
        return self._readPos
    
    # How many bytes can we read from the buffer before it is empty. If there are less than "OverflowSize" bytes available at the end of the buffer, move the bytes at the end of the buffer into the overflow area. 
    # Note this function can change the readPos
    def get_read_available(self):
        if self._writePos > self._readPos:
            return self._writePos - self._readPos
        else:                                                                                                                   # self._writePos <= self._readPos:
            if self.BytesInBuffer == 0:                                                                                         # Buffer is empty
                return 0
            else:                                                                                                               # Buffer has data
                if self.BufferSize + self.OverflowSize - self._readPos > self.OverflowSize:                                     # The data left to read is larger than the overflow buffer, so just return the bytes left to read
                    return self.BufferSize + self.OverflowSize - self._readPos
                else:                                                                                                           # The data left to read is smaller than the overflow buffer, so move it to the overflow buffer and update the readPos
                    #print("Moving bytes")
                    bytesToMove = self.BufferSize + self.OverflowSize - self._readPos
                    self.Buffer[(self.OverflowSize - bytesToMove):self.OverflowSize] = self.Buffer[-bytesToMove:]               # Move the last bytes into the overflow area
                    self._readPos = self.OverflowSize - bytesToMove
                    return bytesToMove + self._writePos - self.OverflowSize

    def bytes_wasRead(self, count):                                         # Tell the buffer how many bytes we just read.  Must call this after every read from the buffer
        self.BytesInBuffer -= count
        assert self.BytesInBuffer >= 0, "Buffer underflow"
        self._readPos = self._readPos + count
 
####################### End of RingBuffer #######################

class AudioPlayer:
    def __init__(self, callbacks={}):
        print("Constructor")
        self.STOPPED, self.PLAYING, self.PAUSED = range(3)
        self.callbacks = callbacks
        self.DEBUG = False
        self.PLAY_STATE = self.STOPPED  # 0 = Stopped, 1 = Playing , 2 = Paused
        self.BlockFlag = False
        self.sock = None
        self.audio_out = None
        self.playlist = []
        self.TrackNumber = 1
               
        AudioBufferSize = 60 * 1024                        # An array to hold packets from the network. As an example, a 96000 bps bitrate is 12kB per second, so a ten second buffer should be about 120kB
        OverflowBufferSize = 600
        self.AudioBuffer = RingBuffer(AudioBufferSize, OverflowBufferSize)

        self.OutBufferSize = 20 * 1024
        self.OutBytes = bytearray(self.OutBufferSize)       # An array to hold decoded audio samples. 44,100kHz takes 176,400 bytes per second (16 bit samples, stereo)
        self.OutBuffer = memoryview(self.OutBytes)
        
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
    
    def i2s_callback(self, t):
        print('*', end='')
        self.BlockFlag = False

    def AddToPlaylist(self, url):
        self.playlist.append(url)
    
    def Play(self):
        if self.PLAY_STATE == self.STOPPED:
            if self.TrackNumber <= len(self.playlist):
                print("Playing track:", self.TrackNumber)
                self._readHeader(self.playlist[self.TrackNumber - 1])  # Start playing a track
    
        self.PLAY_STATE = self.PLAYING
        
    def Pause(self):
        self.PLAY_STATE = self.PAUSED
        
    def PrevTrack(self):
        if self.TrackNumber > 1 and self.PLAY_STATE == self.PLAYING:
                self.PLAY_STATE = self.STOPPED
                Player.Vorbis_Close()
                self.sock.close()
                self.TrackNumber -= 1
                self.Play()

    def NextTrack(self):
        if self.TrackNumber < len(self.playlist) and self.PLAY_STATE == self.PLAYING:
            self.PLAY_STATE = self.STOPPED
            Player.Vorbis_Close()
            self.sock.close()
            self.TrackNumber += 1
            self.Play()
        
    def Stop(self):
        self.PLAY_STATE = self.STOPPED
        Player.Vorbis_Close()
        #self.audio_out.deinit()
        self.sock.close()
        self.AudioBuffer.InitBuffer()
        self.TrackNumber = 1
 
    def IsPaused(self):
        return self.PLAY_STATE == self.PAUSED
     
    def IsStopped(self):
        return self.PLAY_STATE == self.STOPPED
        
        
    def _readHeader(self, url, port=80):
        global audio_out
        global channels
        global bits_per_sample
        global BlockFlag        # Flag which we use to block operation until the I2S decoder has finished playing

        _, _, host, path = url.split('/', 3)
        addr = socket.getaddrinfo(host, port)[0][-1]
        self.sock = socket.socket()

        print("Getting", path, "from", host, "Port:", port)
        self.sock.connect(addr)
        self.sock.setblocking(False) # Tell the socket to return straight away (async)

        self.sock.send(bytes('GET /%s HTTP/1.1\r\nHost: %s\r\n\r\n' % (path, host), 'utf8'))

        # Read the response headers
        response_headers = b""
        while True:
            header = self.sock.readline()
            #print(header)
            if header != None:
                response_headers += header.decode('utf-8')
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
                self.sock.setblocking(False) # Return straight away

                self.sock.send(bytes('GET /%s HTTP/1.1\r\nHost: %s\r\n\r\n' % (new_path, new_host), 'utf8'))

                # Skip the response headers
                while True:
                    header = self.sock.readline()
                    if header == b"\r\n":
                        break

        TimeStart = time.ticks_ms()
        print("Filling Buffer...")
        self.AudioBuffer.InitBuffer()
        while ((BytesAvailable := self.AudioBuffer.get_write_available()) > 0):
            data = self.sock.readinto(self.AudioBuffer.Buffer[self.AudioBuffer.get_writePos():], BytesAvailable)
            if data:
                self.AudioBuffer.bytes_wasWritten(data)

        print ("Filled buffer. Time:", time.ticks_ms() - TimeStart, "ms. Total Data:", self.AudioBuffer.get_read_available())  # Note: This can change _readPos

        # Init the decoder
        Result = Player.Vorbis_Init()

        if (Result):
            print("Decoder Init success")
        else:
            print("Decoder Init failed")
            return -1

        FoundSyncWordAt = Player.Vorbis_Start(self.AudioBuffer.Buffer[self.AudioBuffer.get_readPos():], self.AudioBuffer.get_read_available())  # Note: This can change _readPos

        if (FoundSyncWordAt >= 0):
            print("Decoder Start success. Sync word at", FoundSyncWordAt)
        else:
            print("Decoder Start failed")
            return -1

        # Decode the first part of the file after the sync word to get info that we need about the bitrate etc. Keep going until we don't get "Need more data" any more
        while True:
            BytesAvailable = self.AudioBuffer.get_read_available()      # Note: This can change _readPos
            #print("Decoding at offset", self.AudioBuffer.get_readPos())
            Result, BytesLeft, AudioSamples = Player.Vorbis_Decode(self.AudioBuffer.Buffer[self.AudioBuffer.get_readPos():], BytesAvailable, self.OutBuffer)
            #print("Bytes Used:", BytesAvailable - BytesLeft)
            self.AudioBuffer.bytes_wasRead(BytesAvailable - BytesLeft)

            if (Result == 100 or Result == 110): # Expect 100 (Need more data) or 110 (Continued Packet) here
                TimeStart = time.ticks_ms()
                #print("Read Header Packet success. Result:", Result)
            else:
                print("No more header data. Result:", Result)
                break

        # Get info about this stream
        channels, sample_rate, bits_per_sample, bit_rate = Player.Vorbis_GetInfo()
        print("Channels:", channels)
        print("Sample Rate:", sample_rate)
        print("Bits per Sample:", bits_per_sample)
        print("Bitrate:", bit_rate)

        # Set up the first I2S peripheral (0) based on the stream info, and make it async with a callback
        self.audio_out = I2S(0, sck=sck_pin, ws=ws_pin, sd=sd_pin, mode=I2S.TX, bits=bits_per_sample, format=I2S.STEREO if channels == 2 else I2S.MONO, rate=sample_rate, ibuf=self.OutBufferSize)
        self.audio_out.irq(self.i2s_callback)
        self.BlockFlag = False

    def Audio_Pump(self):
        #global BlockFlag        # Flag which we use to block operation until the I2S decoder has finished playing

        #print("Pump")

        if self.IsStopped():
            return
        
        if self.sock == None:
           raise ValueError("Need to call Play_URL first")     

        TimeStart = time.ticks_ms()
        TotalAudioSamples = 0

        # We have some data. Repeatedly call the decoder to decode one chunk at a time from the AudioBuffer, and build up audio samples in Outbuffer. 
        while True:
            # If there is any free space in the buffer then add any data available from the network
            BytesAvailable = self.AudioBuffer.get_write_available()
            if (BytesAvailable > 0):
                #print("Adding data to buffer", AudioBuffer.get_writePos(), BytesAvailable)
                try:    # Can get an exception here if we pause too long and the underlying socket gets closed
                    data = self.sock.readinto(self.AudioBuffer.Buffer[self.AudioBuffer.get_writePos():], BytesAvailable)
                except:
                    print("Socket Exception")
                    self.Stop()
                    return -1
                    
                if data:
                    #print("Added", data)
                    self.AudioBuffer.bytes_wasWritten(data)

            # We will block here (except for the first time through) until the I2S callback is fired. i.e. I2S has finished playing and needs more data
            if self.BlockFlag == True or self.PLAY_STATE != self.PLAYING: 
               return

            if ((TotalAudioSamples + 1024) * channels * (2 if bits_per_sample == 16 else 1)) > self.OutBufferSize: # Make sure that we have enough OutBuffer space left for one more frame of 1024 samples
                break

            BytesAvailable = self.AudioBuffer.get_read_available()  # Note: This can change _readPos

            if BytesAvailable == 0: # Either the buffer has emptied (slow network) but we are not at the end of the stream yet, or we are actually at the end of the stream. Check to see if the last read returned anything or an empty object (EOS)
                if data:
                    return          # No data to decode
                else:
                    Player.Vorbis_Close()
                    self.sock.close()
                    return 0        # End of stream. Don't close the I2S here, as it still has to play the last packet

            #print("BIB:", AudioBuffer.BytesInBuffer,  "Available:", BytesAvailable, "Decoding at offset", AudioBuffer.get_readPos())
            Result, BytesLeft, AudioSamples = Player.Vorbis_Decode(self.AudioBuffer.Buffer[self.AudioBuffer.get_readPos():], BytesAvailable, self.OutBuffer[(TotalAudioSamples * channels * (2 if bits_per_sample == 16 else 1)):])
            #print("BytesLeft:", BytesLeft, "Bytes Used:", BytesAvailable - BytesLeft)
            self.AudioBuffer.bytes_wasRead(BytesAvailable - BytesLeft)

            TotalAudioSamples += AudioSamples

            if (Result == 0):
                TimeStart = time.ticks_ms()
                #print("Read Packet success. Result:", Result, ", Bytes Left:", BytesLeft, ", Audio Samples:", AudioSamples)
            elif (Result == 100):
                TimeStart = time.ticks_ms()
                #print("Need more data. Bytes Left:", BytesLeft)
            elif (Result == 110):
                TimeStart = time.ticks_ms()
                #print("Continued Page. Bytes Left:", BytesLeft)
            else:
                print("Read Packet failed. Error:", Result)
                return -1

        # We have left the decode loop either because the output buffer is full, or all of the samples in the input buffer have been decoded
        if (TotalAudioSamples > 0):
            #print("Playing Audio. TotalAudioSamples =", TotalAudioSamples)
            numout = self.audio_out.write(self.OutBuffer[:(TotalAudioSamples * channels * (2 if bits_per_sample == 16 else 1))]) # Returns straight away
            #print("Played", numout)
            self.BlockFlag = True
