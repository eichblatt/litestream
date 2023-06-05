import network
import time
from machine import Pin, I2S

buffsize = 81920 #4096 worked well

sck_pin = Pin(13)   # Serial clock output
ws_pin = Pin(14)    # Word clock output
sd_pin = Pin(17)    # Serial data output

block = False
    
def http_get(url):
    import socket
    global block
    
    ba = bytearray(buffsize)  # big array
    mva = memoryview(ba)

    _, _, host, path = url.split('/', 3)
    addr = socket.getaddrinfo(host, 1180)[0][-1]
    s = socket.socket()
    
    #s.setblocking(False)
    #s.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 8192)
    #s.settimeout(0.05)
    print("Getting", path, "from", host)
    s.connect(addr)
    s.setblocking(False)
    s.send(bytes('GET /%s HTTP/1.1\r\nHost: %s\r\n\r\n' % (path, host), 'utf8'))
    
    while True:
        data = -1
        TotalData = 0
        TimeStart = time.ticks_ms()
        
        while (TotalData < buffsize) and (data != 0):
            data = s.readinto(mva[TotalData:], buffsize - TotalData)
            time.sleep_ms(2)
            #print('r:', data, time.ticks_ms(), end=' ')
            print('r', end='')
            if data != None:
                TotalData = data + TotalData
           
            print (time.ticks_ms() - TimeStart, end='')
        
        while (block == True):
            print('.', end='')
            time.sleep_ms(2)
            continue
            
        print()
            
        if data != 0:
            #print('w', time.ticks_ms(), end='') #str(data, 'utf8'), end='')
            block = True;
            audio_out.write(mva) #returns straight away
        else:
            print("No more data")
            break
            
    s.close()

def i2s_callback(t):
    global block
    #print('*', time.ticks_ms())
    block = False;
    
def do_connect():
    print("STARTING!")
    sta_if = network.WLAN(network.STA_IF)
    sta_if.active(True)
    sta_if.config(pm=network.WLAN.PM_NONE)
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

#url = "http://207.241.232.195/20/items/mjq-1983-montreal-jazz-festival-cbc/01-Introduction.mp3"
#url = "http://ia803405.us.archive.org/20/items/mjq-1983-montreal-jazz-festival-cbc/01-Introduction.mp3"
url = "http://192.168.1.117/GDCDQuality.wav"
#url = "http://192.168.1.117/examplein.ogg"
#url = "http://raw.githubusercontent.com/eichblatt/litestream/main/GDCDQualityTrim.wav?token=GHSAT0AAAAAAB455C3KMDVX7LHTSBVEEYW2ZDGHAYQ"
#url = "http://testhostsa.z13.web.core.windows.net/music.mp3"
#url = "http://20.115.121.255/music.mp3"


audio_out = I2S(0, sck=sck_pin, ws=ws_pin, sd=sd_pin, mode=I2S.TX, bits=16, format=I2S.STEREO, rate=44100, ibuf=2048)
audio_out.irq(i2s_callback) 

do_connect()
starttime = time.ticks_ms()
gc.disable()
http_get(url)
gc.enable()
print("\nTime:", (time.ticks_ms() - starttime)/1000, "seconds")
audio_out.deinit()
