import network
import time
import Player
from machine import Pin, I2S
import machine
import gc

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

def Play_URL(url, port):
    import socket
    
    global block    # Flag which we use to block operation until the I2S decoder has finished playing

    StreamBuffer = bytearray(InBufferSize)  # array to hold samples
    StreamBufferMV = memoryview(StreamBuffer)

    DecodedDataBuffer = bytearray(DecodedBufferSize) #bytearray(MaxFrameSize * 4)   # 2 channels, 16-bit (or 2-byte) samples
    DecodedDataBufferMV = memoryview(DecodedDataBuffer)
        
    _, _, host, path = url.split('/', 3)
    addr = socket.getaddrinfo(host, port)[0][-1]
    s = socket.socket()
    
    #s.setblocking(False)
    #s.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 8192)
    #s.settimeout(0.05)

    print("Getting", path, "from", host, "Port:", port)
    s.connect(addr)
    s.setblocking(False) # Return straight away
    s.send(bytes('GET /%s HTTP/1.1\r\nHost: %s\r\n\r\n' % (path, host), 'utf8'))
    
    # Read the response headers
    response_headers = b""
    while True:
        header = s.readline()
        print(header)
        if header != None:
            response_headers += header.decode('utf-8')
        if header == b"\r\n":
            break

    # Check if the response is a redirect
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
        
        # Fill the buffer
        while (TotalData < InBufferSize) and (data != 0):
            data = s.readinto(StreamBufferMV[TotalData:], InBufferSize - TotalData)
            time.sleep_ms(2)
            #print('r:', data, time.ticks_ms(), end=' ')
            #print('r', end='')
            if data != None:
                TotalData = data + TotalData
        
        #print()        
        print ("Time:", time.ticks_ms() - TimeStart, "Total Data:", TotalData, end='')
        
        # We will block here (except for the first time through) until the I2S callback is fired. i.e. I2S has finished playing and needs more data
        while (block == True): 
            print('.', end='')
            time.sleep_ms(2)
            continue
            
        print()
                
        if data == 0:
            print("No more data")
            break
        else:
            #print('w', time.ticks_ms(), end='') #str(data, 'utf8'), end='')
            # Do this once, when we first start streaming the data, to initialise the decoder & set up buffers
            if InHeader:
                InHeader = False
                
                # Create the Vorbis Player, and pass it a big buffer for it to use (200kB seems enough)
                PlayerBuffer = bytearray(200000)
                PlayerBufferMV = memoryview(PlayerBuffer)
                                
                # Decode the header, will return how many bytes it has consumed from the buffer
                Used = Player.Vorbis_Start(PlayerBufferMV, StreamBufferMV)
                print("Used", Used)
                
                # Get info about this stream, specifically the max frame size, and then create a buffer to hold the decoded data
                channels, sample_rate, setup_memory_required, temp_memory_required, max_frame_size = Player.Vorbis_GetInfo()
                print("MaxFrameSize", max_frame_size)
           
            # Loop around, consuming all the data from the stream buffer one chunk at a time, and finally send the decoded data to the DAC
            else:
                while True:
                    #print("Calling decoder with offset", Used)
                    BytesUsed, AudioSamples = Player.Vorbis_Decode(StreamBufferMV[Used:], InBufferSize - Used, DecodedDataBufferMV[(SamplesOut * 4):])
                    print("Result:", BytesUsed, AudioSamples)
                    # BytesUsed is the number of bytes used from the buffer 
                    # AudioSamples is the number of decoded audio samples available. Each sample is 4 bytes

                    if BytesUsed == 0:   # No more usable data in the buffer. There may still be some data at the end which is not enough to decode
                        break

                    SamplesOut += AudioSamples;
                    Used += BytesUsed

            # If we got audio data, play it
            if SamplesOut > 0:
                print("DAC", SamplesOut * 4)
                numout = audio_out.write(DecodedDataBufferMV[:(SamplesOut * 4)]) #returns straight away
                print("DACOUT", numout)
                SamplesOut = 0
                block = True;
                    
            # We may still have some data at the end of the buffer. If so, move it to the beginning
            print(InBufferSize - Used, "bytes left")
            if Used < InBufferSize:
                StreamBufferMV[:(InBufferSize - Used)] = StreamBufferMV[-(InBufferSize - Used):]
                TotalData = InBufferSize - Used
            else:
                TotalData = 0
                
            Used = 0
            
    s.close()
    Player.Vorbis_Close()

# Maybe use this later
class RINGBUFFER:
    def __init__(self, size):
        self.data = bytearray(size)
        self.size = size
        self.index_put = 0
        self.index_get = 0
        
    def put(self, value):
        next_index = (self.index_put + 1) % self.size
        # check for overflow
        if self.index_get != next_index: 
            self.data[self.index_put] = value
            self.index_put = next_index
            return value
        else:
            return None
        
    def get(self):
        if self.index_get == self.index_put:
            return None  ## buffer empty
        else:
            value = self.data[self.index_get]
            self.index_get = (self.index_get + 1) % self.size
            return value



def i2s_callback(t):
    global block
    print('*', time.ticks_ms())
    block = False;
    
def connect_to_WiFi():
    print("STARTING!")
    sta_if = network.WLAN(network.STA_IF)
    sta_if.active(True)
    sta_if.config(pm=network.WLAN.PM_NONE)  # Switch off Power Management on the WiFi radio (better performance)
    if not sta_if.isconnected():
        print('connecting to network...')
        sta_if.active(True)
        sta_if.connect("DODO-31BF", "PU7QUYXQE7")
        #sta_if.connect("AndroidAP4425", "fuzn2660")
        #sta_if.connect("TOWER2021WAP", "PU7QUYXQE7")
        while not sta_if.isconnected():
            pass
        #sta_if.config(pm=sta_if.PM_NONE)
    print('network config:', sta_if.ifconfig())

########################################
# Main Code
########################################

#url = "http://192.168.1.117/examplein.ogg" 
#url = "http://ia800305.us.archive.org/19/items/gd1980-10-29.beyer.stankiewicz.126919.flac1644/gd1980-10-29s1t02.ogg"
url="https://archive.org/download/gd1980-10-29.beyer.stankiewicz.126919.flac1644/gd1980-10-29s1t02.ogg"

machine.freq(240000000)

# Set up the I2S output, async with a callback
audio_out = I2S(0, sck=sck_pin, ws=ws_pin, sd=sd_pin, mode=I2S.TX, bits=16, format=I2S.STEREO, rate=44100, ibuf=DecodedBufferSize) # Max bufffer is 132095 (129kB)
audio_out.irq(i2s_callback) 

connect_to_WiFi()
starttime = time.ticks_ms()
gc.disable()        # Disable the garbage collector to avoid interrupting the stream

Play_URL(url, 80) # Play the file

gc.enable()

print("\nTime:", (time.ticks_ms() - starttime)/1000, "seconds")
audio_out.deinit()
