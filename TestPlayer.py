import BasicOggPlayer
import gc

def connect_to_WiFi():
    sta_if = network.WLAN(network.STA_IF)
    sta_if.active(True)
    sta_if.config(pm=network.WLAN.PM_NONE)  # Switch off Power Management on the WiFi radio (better performance)
    
    if not sta_if.isconnected():
        print('Connecting to network...')
        sta_if.active(True)
        sta_if.connect("DODO-31BF", "PU7QUYXQE7")

        while not sta_if.isconnected():
            pass
        
    print('Connected. Network config:', sta_if.ifconfig())

def Callback():
    print('.', end="")
    time.sleep_ms(2)
    
########################################
# Main Code
########################################

machine.freq(240000000)
connect_to_WiFi()
starttime = time.ticks_ms()
gc.disable()        # Disable the garbage collector to avoid interrupting the stream

#url = "http://192.168.1.117/examplein.ogg" 
#url = "http://ia800305.us.archive.org/19/items/gd1980-10-29.beyer.stankiewicz.126919.flac1644/gd1980-10-29s1t02.ogg"
url="https://archive.org/download/gd1980-10-29.beyer.stankiewicz.126919.flac1644/gd1980-10-29s1t02.ogg"
Play_URL(url, 80, Callback) # Play the file

gc.enable()

print("\nTime:", (time.ticks_ms() - starttime)/1000, "seconds")