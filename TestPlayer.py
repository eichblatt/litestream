# Display driver: https://github.com/russhughes/st7789_mpy
import time
import st7789
import vga1_16x32 as font
from machine import Pin, SPI
from rotary_irq_esp import RotaryIRQ
import machine, network, gc, time
from BasicOggPlayer import Play_URL, Audio_Pump


def connect_to_WiFi():
    sta_if = network.WLAN(network.STA_IF)
    sta_if.active(True)
    sta_if.config(pm=network.WLAN.PM_NONE)  # Switch off Power Management on the WiFi radio (better performance)

    if not sta_if.isconnected():
        print("Connecting to network...")
        sta_if.active(True)
        sta_if.connect("DODO-31BF", "PU7QUYXQE7")

        while not sta_if.isconnected():
            pass

    print("Connected. Network config:", sta_if.ifconfig())


def Callback():
    print(".", end="")
    time.sleep_ms(2)


########################################
# Main Code
########################################

machine.freq(240000000)
connect_to_WiFi()
starttime = time.ticks_ms()
gc.disable()  # Disable the garbage collector to avoid interrupting the stream

print("Starting...")


# Init screen
def config(rotation=0, buffer_size=0, options=0):
    return st7789.ST7789(
        SPI(1, baudrate=40000000, sck=Pin(12), mosi=Pin(11)),
        128,
        160,
        reset=Pin(4, Pin.OUT),
        cs=Pin(10, Pin.OUT),
        dc=Pin(6, Pin.OUT),
        backlight=Pin(5, Pin.OUT),
        color_order=st7789.RGB,
        inversion=False,
        rotation=rotation,
        options=options,
        buffer_size=buffer_size,
    )


PlayPausePoly = [(0, 0), (0, 15), (15, 8), (0, 0)]
RewPoly = [(7, 0), (0, 8), (7, 15), (7, 0), (15, 0), (8, 8), (15, 15), (15, 0)]
FFPoly = [(0, 0), (0, 15), (8, 8), (0, 0), (8, 0), (8, 15), (15, 8), (8, 0)]

# Configure display driver
tft = config(1, buffer_size=64 * 64 * 2)

# Init and clear screen
tft.init()
tft.fill(st7789.BLACK)

# Set up pins
pPower = Pin(21, Pin.IN, Pin.PULL_UP)
pSelect = Pin(47, Pin.IN, Pin.PULL_UP)
pPlayPause = Pin(2, Pin.IN, Pin.PULL_UP)
pStop = Pin(15, Pin.IN, Pin.PULL_UP)
pRewind = Pin(16, Pin.IN, Pin.PULL_UP)
pFFwd = Pin(1, Pin.IN, Pin.PULL_UP)
pYSw = Pin(41, Pin.IN, Pin.PULL_UP)
pMSw = Pin(38, Pin.IN, Pin.PULL_UP)
pDSw = Pin(9, Pin.IN, Pin.PULL_UP)

pLED = Pin(48, Pin.OUT)

PowerLED = False

# Initialise the three rotaries. First value is CL, second is DT
# Year
y = RotaryIRQ(42, 40, min_val=0, max_val=10, reverse=True, range_mode=RotaryIRQ.RANGE_UNBOUNDED, pull_up=True, half_step=False)
# Month
m = RotaryIRQ(39, 18, min_val=0, max_val=10, reverse=True, range_mode=RotaryIRQ.RANGE_UNBOUNDED, pull_up=True, half_step=False)
# Day
d = RotaryIRQ(8, 7, min_val=0, max_val=10, reverse=True, range_mode=RotaryIRQ.RANGE_UNBOUNDED, pull_up=True, half_step=False)

year_old = -1
month_old = -1
day_old = -1
pPower_old = False
pSelect_old = False
pPlayPause_old = False
pStop_old = False
pRewind_old = False
pFFwd_old = False
pYSw_old = False
pMSw_old = False
pDSw_old = False

# url = "http://192.168.1.117/examplein.ogg"
# url = "http://ia800305.us.archive.org/19/items/gd1980-10-29.beyer.stankiewicz.126919.flac1644/gd1980-10-29s1t02.ogg"
url = "https://archive.org/download/gd1980-10-29.beyer.stankiewicz.126919.flac1644/gd1980-10-29s1t02.ogg"
# url = "https://archive.org/download/gd1984-12-28.142611.sbd.miller.flac1648/13LooksLikeRain.ogg"
# url="https://archive.org/download/gd1984-12-28.142611.sbd.miller.flac1648/18TheOtherOne.ogg"
# url="https://archive.org/download/gd76-09-23.sbd.backus.14687.sbeok.shnf/gd1976-09-23d1t01.ogg"
url = "https://archive.org/download/datpiff-mixtape-m3d2a653/01%20-%20DJ%20EPPS%20INTRO.mp3"
print("Playing", url)
Play_URL(url)  # Play the file

while True:
    Audio_Pump()

    if pPower_old != pPower.value():
        pPower_old = pPower.value()
        pLED.value(PowerLED)
        if pPower_old:
            tft.fill_circle(5 + 8, 108 + 8, 8, st7789.BLUE)
            print("Power UP")
        else:
            PowerLED = not PowerLED
            tft.fill_circle(5 + 8, 108 + 8, 8, st7789.WHITE)
            print("Power DOWN")

    if pSelect_old != pSelect.value():
        pSelect_old = pSelect.value()
        if pSelect_old:
            tft.rect(105, 108, 16, 16, st7789.BLUE)
            print("Select UP")
        else:
            tft.rect(105, 108, 16, 16, st7789.WHITE)
            print("Select DOWN")

    if pPlayPause_old != pPlayPause.value():
        pPlayPause_old = pPlayPause.value()
        if pPlayPause_old:
            tft.fill_polygon(PlayPausePoly, 130, 108, st7789.BLUE)
            print("PlayPause UP")
        else:
            tft.fill_polygon(PlayPausePoly, 130, 108, st7789.WHITE)
            print("PlayPause DOWN")

    if pStop_old != pStop.value():
        pStop_old = pStop.value()
        if pStop_old:
            tft.fill_rect(55, 108, 16, 16, st7789.BLUE)
            print("Stop UP")
        else:
            tft.fill_rect(55, 108, 16, 16, st7789.WHITE)
            print("Stop DOWN")

    if pRewind_old != pRewind.value():
        pRewind_old = pRewind.value()
        if pRewind_old:
            tft.fill_polygon(RewPoly, 30, 108, st7789.BLUE)
            print("Rewind UP")
        else:
            tft.fill_polygon(RewPoly, 30, 108, st7789.WHITE)
            print("Rewind DOWN")

    if pFFwd_old != pFFwd.value():
        pFFwd_old = pFFwd.value()
        if pFFwd_old:
            tft.fill_polygon(FFPoly, 80, 108, st7789.BLUE)
            print("FFwd UP")
        else:
            tft.fill_polygon(FFPoly, 80, 108, st7789.WHITE)
            print("FFwd DOWN")

    if pYSw_old != pYSw.value():
        pYSw_old = pYSw.value()
        if pYSw_old:
            tft.text(font, "Y", 0, 60, st7789.WHITE, st7789.BLUE)
            print("Year UP")
        else:
            tft.text(font, "Y", 0, 60, st7789.BLUE, st7789.WHITE)
            print("Year DOWN")

    if pMSw_old != pMSw.value():
        pMSw_old = pMSw.value()
        if pMSw_old:
            tft.text(font, "M", 0, 0, st7789.WHITE, st7789.BLUE)
            print("Month UP")
        else:
            tft.text(font, "M", 0, 0, st7789.BLUE, st7789.WHITE)
            print("Month DOWN")

    if pDSw_old != pDSw.value():
        pDSw_old = pDSw.value()
        if pDSw_old:
            tft.text(font, "D", 0, 30, st7789.WHITE, st7789.BLUE)
            print("Day UP")
        else:
            tft.text(font, "D", 0, 30, st7789.BLUE, st7789.WHITE)
            print("Day DOWN")

    year_new = y.value()
    month_new = m.value()
    day_new = d.value()

    if year_old != year_new:
        year_old = year_new
        tft.text(font, "Y = " + str(year_new) + "     ", 0, 60, st7789.WHITE, st7789.BLUE)
        print("year =", year_new)

    if month_old != month_new:
        month_old = month_new
        tft.text(font, "M = " + str(month_new) + "     ", 0, 0, st7789.WHITE, st7789.BLUE)
        print("month =", month_new)

    if day_old != day_new:
        day_old = day_new
        tft.text(font, "D = " + str(day_new) + "     ", 0, 30, st7789.WHITE, st7789.BLUE)
        print("day =", day_new)

gc.enable()

print("\nTime:", (time.ticks_ms() - starttime) / 1000, "seconds")
