import network
import time
import Player
from machine import Pin, I2S
import machine

buffsize = 8192

sck_pin = Pin(13)   # Serial clock output
ws_pin = Pin(14)    # Word clock output
sd_pin = Pin(17)    # Serial data output

block = False
    
def http_get(url, port):
    import socket
    global block
    
    StreamBuffer = bytearray(buffsize)  # array to hold samples
    StreamBufferMV = memoryview(StreamBuffer)

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
    
    while True:
        data = -1
        TotalData = 0
        TimeStart = time.ticks_ms()
        InHeader = True;
        
        # Fill the buffer
        while (TotalData < buffsize) and (data != 0):
            data = s.readinto(StreamBufferMV[TotalData:], buffsize - TotalData)
            time.sleep_ms(2)
            #print('r:', data, time.ticks_ms(), end=' ')
            print('r', end='')
            if data != None:
                TotalData = data + TotalData
        
        print()        
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
            #print(hex(mva[0]))
            #print(hex(mva[1]))
            # Do this once, when we first start streaming the data, to initialise the decoder & set up buffers
            if InHeader:
                InHeader = False
                
                # Create the Vorbis Player, and pass it a big buffer for it to use
                PlayerBuffer = bytearray(200000)
                PlayerBufferMV = memoryview(PlayerBuffer)
                
                # Decode the header, will return how many bytes it has consumed from the buffer
                Used = Player.Vorbis_Start(PlayerBufferMV, 200000, StreamBufferMV[178:]) # Hack for now. Offset 178 bytes into the returned data to skip the HTTP response and go straight to the data body
                print("Used", Used)

                # Get info about this stream, specifically the max frame size, and then create a buffer to hold the decoded data
                MaxFrameSize = Player.Vorbis_GetInfo()
                print("MaxFrameSize", MaxFrameSize)
                DecodedDataBuffer = bytearray(MaxFrameSize * 4)   # 2 channels, 16-bit (or 2-byte) samples
                DecodedDataBufferMV = memoryview(DecodedDataBuffer)
            
            # Loop around, consuming all the data from the stream buffer one chunk at a time, and send the decoded data to the DAC
            while True:
                print("Calling decoder with offset", Used)
                BytesUsed, AudioBytes = Player.Vorbis_Decode(StreamBufferMV[178 + Used:], buffsize - Used - 178, DecodedDataBufferMV)
                print("Result:", BytesUsed, AudioBytes)
                # BytesUsed is the number of bytes used from the buffer 
                # AudioBytes is the number of bytes of decoded audio data available

                # If we got audio data, play it
                if AudioBytes > 0:
                    audio_out.write(DecodedDataBufferMV[:AudioBytes]) #returns straight away
                
                if BytesUsed == 0:   # No more usable data in the buffer. There may still be some at the end, but the function will move it to the beginning
                    break
                
                Used += BytesUsed
                block = True;
            
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

url = "http://192.168.1.117/examplein.ogg"  

machine.freq(240000000)

# Set up the I2S output, async with a callback
audio_out = I2S(0, sck=sck_pin, ws=ws_pin, sd=sd_pin, mode=I2S.TX, bits=16, format=I2S.STEREO, rate=44100, ibuf=2048)
audio_out.irq(i2s_callback) 

connect_to_WiFi()
starttime = time.ticks_ms()
gc.disable()        # Disable the garbage collector to avoid interrupting the stream

http_get(url, 1180) # Play the file

gc.enable()

print("\nTime:", (time.ticks_ms() - starttime)/1000, "seconds")
audio_out.deinit()