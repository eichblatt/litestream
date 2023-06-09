import network, time, Player, socket
from machine import Pin, I2S

sck_pin = Pin(13)   # Serial clock output
ws_pin = Pin(14)    # Word clock output
sd_pin = Pin(17)    # Serial data output

DEBUG_OGG = True
BlockFlag = False
PLAY_STATE = 0
TotalData = 0
sock = None
audio_out = None
channels = 0
max_frame_size = 0

HeaderBufferSize = 8192
InBufferSize = 4096
OutBufferSize = 132095 # Max size the I2S device will use for its buffer is 132095

HeaderBuffer = bytearray(HeaderBufferSize)  # An array to hold the Header data of the stream
HeaderBufferMV = memoryview(HeaderBuffer)

InBuffer = bytearray(InBufferSize)  # An array to hold samples which we read from the network
InBufferMV = memoryview(InBuffer)

OutBuffer = bytearray(OutBufferSize) # An array to hold decoded audio samples. This needs to be bigger than the incoming samples buffer as the decoder expands the data
OutBufferMV = memoryview(OutBuffer)

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
    global BlockFlag
    print('*')
    BlockFlag = False;
  
# There is a bit of a balancing act going on with buffers here:
# The Header buffer needs to be big enough to hold the header. By observation, headers are around 4k in size but I don't know how big they can get. So it is made a generous size (8k)
# What is left in the Headerbuffer after the header has been processed is then copied to the Inbuffer. So the Inbuffer needs to be big enough to hold that. 
# The Inbuffer is deliberately smaller than the Headerbuffer, because the decoder expands the data in the Inbuffer into data in the Outbuffer, and the Outbuffer can't be bigger than 129kb, as that is the max size of the I2S buffer.
# So if the Inbuffer is too big, we will overflow the Outbuffer.
# However, if the Inbuffer is too small then data that is left in the Headerbuffer after the header has been processed will overflow the Inbuffer

def play():
    global PLAY_STATE
    PLAY_STATE = 1

def pause():
    global PLAY_STATE
    if PLAY_STATE == 1:
        PLAY_STATE = 2

def stop():
    global PLAY_STATE
    PLAY_STATE = 0

def prep_URL(url, port=80):
    global TotalData
    global sock
    global audio_out
    global channels
    global max_frame_size
    global PLAY_STATE
        
    PLAY_STATE = 1
    with open('current_url.py','w') as f:
        f.write(url)
    _, _, host, path = url.split('/', 3)
    addr = socket.getaddrinfo(host, port)[0][-1]
    sock = socket.socket()

    # Experimental. May not work
    #sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 8192)
    #sock.settimeout(0.05)

    print("Getting", path, "from", host, "Port:", port)
    sock.connect(addr)
    sock.setblocking(False) # Tell the socket to return straight away (async)
    
    sock.send(bytes('GET /%s HTTP/1.1\r\nHost: %s\r\n\r\n' % (path, host), 'utf8'))
    
    # Read the response headers
    response_headers = b""
    while True:
        header = sock.readline()
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
            sock.close()
            # Establish a new socket connection to the server
            print("Redirecting to", new_host, new_port, new_path)
            sock = socket.socket()
            addr = socket.getaddrinfo(new_host, new_port)[0][-1]
            sock.connect(addr)
            sock.setblocking(False) # Return straight away
            
            sock.send(bytes('GET /%s HTTP/1.1\r\nHost: %s\r\n\r\n' % (new_path, new_host), 'utf8'))

            # Skip the response headers
            while True:
                header = sock.readline()
                if header == b"\r\n":
                    break

    SamplesOut = 0
    TotalData = 0
    data = -1
    TimeStart = time.ticks_ms()
    
    # Fill the header buffer. May take multiple reads
    while (TotalData < HeaderBufferSize) and (data != 0):
        data = sock.readinto(HeaderBufferMV[TotalData:], HeaderBufferSize - TotalData)
        time.sleep_ms(2) # Let the WiFi thread have some CPU time (not sure if needed as it *may* run on a different thread)
        #print('r:', data, time.ticks_ms(), end=' ')
        if data != None:
            TotalData += data

    print ("Filled header buffer. Time:", time.ticks_ms() - TimeStart, "ms. Total Data:", TotalData) if DEBUG_OGG else None
    
    # Process the header when we first start streaming the data, to initialise the decoder & set up buffers
    PlayerBuffer = bytearray(200000)     # Create a big buffer for the decoder to use (200kB seems enough)
    PlayerBufferMV = memoryview(PlayerBuffer)

    # Decode the header. This will return how many bytes it has consumed from the buffer
    Used = Player.Vorbis_Start(PlayerBufferMV, HeaderBufferMV)
    print("Header used", Used, "bytes") if DEBUG_OGG else None

    # Copy what's left in the header buffer to the Inbuffer for later decoding
    if Used < HeaderBufferSize:
        InBufferMV[:(HeaderBufferSize - Used)] = HeaderBufferMV[-(HeaderBufferSize - Used):]
        TotalData = HeaderBufferSize - Used
    
    # Get info about this stream
    channels, sample_rate, setup_memory_required, temp_memory_required, max_frame_size = Player.Vorbis_GetInfo()
    #print("MaxFrameSize", max_frame_size)

    # Set up the first I2S peripheral (0), make it async with a callback
    audio_out = I2S(0, sck=sck_pin, ws=ws_pin, sd=sd_pin, mode=I2S.TX, bits=16, format=I2S.STEREO if channels == 2 else I2S.MONO, rate=sample_rate, ibuf=OutBufferSize) # Max bufffer is 132095 (129kB). We have to assume 16-bit samples as there is no way to read it from the stream info.
    audio_out.irq(i2s_callback)
    

def Audio_Pump():
    global BlockFlag        # Flag which we use to block operation until the I2S decoder has finished playing
    global TotalData
    SamplesOut = 0
    
    if PLAY_STATE != 1:   # Only while playing
        return 'inactive'

    if sock == None:
       raise ValueError("Need to call Play_URL first")     
        
    # Decode the rest of the stream
    while True:
        Data = -1
        TimeStart = time.ticks_ms()
        
        if TotalData == InBufferSize:
            print(".", end='') if DEBUG_OGG else None
        else:    
            # Fill the Inbuffer. May take multiple reads. We may exit with data == 0 which means we are at the end of the stream, but we still need to play the last buffer
            while (TotalData < InBufferSize) and (Data != 0):
                Data = sock.readinto(InBufferMV[TotalData:], InBufferSize - TotalData)
                time.sleep_ms(2) # Let the WiFi thread have some CPU time (not sure if needed as it *may* run on a different thread)
                #print('r:', data, time.ticks_ms(), end=' ')
                if Data != None:
                    TotalData += Data

            print ("Filled buffer. Time:", time.ticks_ms() - TimeStart, "ms. Total Data:", TotalData)

        # We will block here (except for the first time through) until the I2S callback is fired. i.e. I2S has finished playing and needs more data
        if BlockFlag == True: 
            return 'pumping'
        
        if PLAY_STATE > 1:
            return 'paused'
        
        TotalData = 0
            
        # We have some data. Repeatedly call the decoder to decode one chunk at a time from Inbuffer, and build up audio samples in Outbuffer
        Used = 0
        #print('w', time.ticks_ms(), end='') #str(data, 'utf8'), end='')

        while True:
            if (SamplesOut * channels * 2) + (max_frame_size * channels * 2)  > OutBufferSize: # Make sure that we have enough OutBuffer space left for one more frame
                    break
                    
            #print("Calling decoder with offset", Used)
            BytesUsed, AudioSamples = Player.Vorbis_Decode(InBufferMV[Used:], InBufferSize - Used, OutBufferMV[(SamplesOut * channels * 2):])  # Multiply by 2 because we are assuming 16-bit samples
            print("Decoded", BytesUsed, "to", AudioSamples) if DEBUG_OGG else None
            # BytesUsed is the number of bytes used from the buffer 
            # AudioSamples is the number of decoded audio samples available. Each sample is 2 bytes (16 bits) x number of channels, so usually will be 4 bytes

            if BytesUsed == 0:      # No more usable data in the Inbuffer. There may still be some data at the end which is not enough to decode
                if Data == 0:       # If the decoder has finished decoding the Inbuffer AND the last read was zero, then we must be at the end of the stream. Otherwise just break out of the loop, play any samples and fill the Inbuffer again
                    print("Stream finished")
                    audio_out.deinit()
                    sock.close()
                    Player.Vorbis_Close()
                    stop()
                    return 'track_finished'
                break

            SamplesOut += AudioSamples;
            Used += BytesUsed

        # If we got audio data, play it
        if SamplesOut > 0:
            print(f"{SamplesOut} samples to audio buffer") if DEBUG_OGG else None
            numout = audio_out.write(OutBufferMV[:SamplesOut * channels * 2]) # Returns straight away. Multiply by 2 because we are assuming 16-bit samples
            # SamplesOut = max(SamplesOut - 1024,0)
            BlockFlag = True;

        # We may still have some data at the end of the buffer which was too short to decode. If so, move it to the beginning
        print(InBufferSize - Used, "bytes left") if DEBUG_OGG else None
        if Used < InBufferSize:
            InBufferMV[:(InBufferSize - Used)] = InBufferMV[-(InBufferSize - Used):]
            TotalData = InBufferSize - Used