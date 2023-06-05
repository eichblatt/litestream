import network, time, Player, socket
from machine import Pin, I2S

sck_pin = Pin(13)   # Serial clock output
ws_pin = Pin(14)    # Word clock output
sd_pin = Pin(17)    # Serial data output

block = False
InBufferSize = 8192
DecodedBufferSize = 132095 # Max size the I2S device will use for its buffer is 132095

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

def i2s_callback(t):
    global block
    print('*')
    block = False;
    
def Play_URL(url, port, callback):
    global block    # Flag which we use to block operation until the I2S decoder has finished playing

    StreamBuffer = bytearray(InBufferSize)  # An array to hold samples which we read from the network
    StreamBufferMV = memoryview(StreamBuffer)

    DecodedDataBuffer = bytearray(DecodedBufferSize) # An array to hold decoded audio samples. This needs to be bigger than the incoming samples array as the decoder expands the data
    DecodedDataBufferMV = memoryview(DecodedDataBuffer)
        
    _, _, host, path = url.split('/', 3)
    addr = socket.getaddrinfo(host, port)[0][-1]
    s = socket.socket()

    # Experimental. May not work
    #s.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 8192)
    #s.settimeout(0.05)

    print("Getting", path, "from", host, "Port:", port)
    s.connect(addr)
    s.setblocking(False) # Tell the socket to return straight away
    s.send(bytes('GET /%s HTTP/1.1\r\nHost: %s\r\n\r\n' % (path, host), 'utf8'))
    
    # Read the response headers
    response_headers = b""
    while True:
        header = s.readline()
        #print(header)
        if header != None:
            response_headers += header.decode('utf-8')
        if header == b"\r\n":
            break

    # Check if the response is a redirect. If so, kill the socket and re-open it on the redirected host/path
    if b"HTTP/1.1 301" in response_headers or b"HTTP/1.1 302" in response_headers:
        redirect_location = get_redirect_location(response_headers)
        if redirect_location:
            # Extract the new host, port, and path from the redirect location
            new_host, new_port, new_path = parse_redirect_location(redirect_location)
            s.close()
            # Establish a new socket connection to the server
            print("Redirecting to", new_host, new_port, new_path)
            s = socket.socket()
            addr = socket.getaddrinfo(new_host, new_port)[0][-1]
            s.connect(addr)
            s.setblocking(False) # Return straight away
            s.send(bytes('GET /%s HTTP/1.1\r\nHost: %s\r\n\r\n' % (new_path, new_host), 'utf8'))

            # Skip the response headers
            while True:
                header = s.readline()
                if header == b"\r\n":
                    break

    InHeader = True
    SamplesOut = 0
    TotalData = 0
    
    while True:
        data = -1
        TimeStart = time.ticks_ms()
        
        # Fill the buffer. May take multiple reads
        while (TotalData < InBufferSize) and (data != 0):
            data = s.readinto(StreamBufferMV[TotalData:], InBufferSize - TotalData)
            time.sleep_ms(2) # Let the WiFi thread have some CPU time (not sure if needed as it *may* run on a different thread)
            #print('r:', data, time.ticks_ms(), end=' ')
            if data != None:
                TotalData = data + TotalData
        
        print ("Filled buffer. Time:", time.ticks_ms() - TimeStart, "ms. Total Data:", TotalData)
        
        # We will block here (except for the first time through) until the I2S callback is fired. i.e. I2S has finished playing and needs more data
        while (block == True): 
            callback()
            continue
            
        print()
                
        if data == 0:
            print("Stream finished")
            audio_out.deinit()
            s.close()
            Player.Vorbis_Close()
            break
            
        else: # We have some data
            #print('w', time.ticks_ms(), end='') #str(data, 'utf8'), end='')
            # Process the header when we first start streaming the data, to initialise the decoder & set up buffers
            if InHeader:
                InHeader = False
                
                # Create the Vorbis Player, and pass it a big buffer for it to use (200kB seems enough)
                PlayerBuffer = bytearray(200000)
                PlayerBufferMV = memoryview(PlayerBuffer)
                                
                # Decode the header. This will return how many bytes it has consumed from the buffer
                Used = Player.Vorbis_Start(PlayerBufferMV, StreamBufferMV)
                print("Header used", Used, "bytes")
                
                # Get info about this stream
                channels, sample_rate, setup_memory_required, temp_memory_required, max_frame_size = Player.Vorbis_GetInfo()
                #print("MaxFrameSize", max_frame_size)
                
                # Set up the first I2S peripheral (0), make it async with a callback
                audio_out = I2S(0, sck=sck_pin, ws=ws_pin, sd=sd_pin, mode=I2S.TX, bits=16, format=I2S.STEREO if channels == 2 else I2S.MONO, rate=sample_rate, ibuf=DecodedBufferSize) # Max bufffer is 132095 (129kB)
                audio_out.irq(i2s_callback) 
           
            # Loop around, consuming all the data from the stream buffer one chunk at a time and building up a decoded samples buffer, and finally send the decoded data to the DAC
            else:
                while True:
                    #print("Calling decoder with offset", Used)
                    BytesUsed, AudioSamples = Player.Vorbis_Decode(StreamBufferMV[Used:], InBufferSize - Used, DecodedDataBufferMV[(SamplesOut * channels * 2):])  # Multiply by 2 because we are assuming 16-bit samples
                    #print("Result:", BytesUsed, AudioSamples)
                    # BytesUsed is the number of bytes used from the buffer 
                    # AudioSamples is the number of decoded audio samples available. Each sample is 2 bytes (16 bits) x number of channels, so usually will be 4 bytes

                    if BytesUsed == 0:   # No more usable data in the buffer. There may still be some data at the end which is not enough to decode
                        break

                    SamplesOut += AudioSamples;
                    Used += BytesUsed

            # If we got audio data, play it
            if SamplesOut > 0:
                numout = audio_out.write(DecodedDataBufferMV[:(SamplesOut * channels * 2)]) # Returns straight away. Multiply by 2 because we are assuming 16-bit samples
                SamplesOut = 0
                block = True;
                    
            # We may still have some data at the end of the buffer which was too short to decode. If so, move it to the beginning
            print(InBufferSize - Used, "bytes left")
            if Used < InBufferSize:
                StreamBufferMV[:(InBufferSize - Used)] = StreamBufferMV[-(InBufferSize - Used):]
                TotalData = InBufferSize - Used
            else:
                TotalData = 0
                
            Used = 0
