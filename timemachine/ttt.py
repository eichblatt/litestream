from machine import SPI, Pin
import st7789

import fonts.NotoSans_24 as pfont_med

_SCREEN_BAUDRATE = 40_000_000
SCREEN_HEIGHT = 240
SCREEN_WIDTH = 320

screen_spi = SPI(1, baudrate=_SCREEN_BAUDRATE, sck=Pin(12), mosi=Pin(11))
reset = Pin(4, Pin.OUT)
cs = Pin(10, Pin.OUT)
dc = Pin(6, Pin.OUT)
backlight = Pin(5, Pin.OUT)


tft = st7789.ST7789(
    screen_spi,
    SCREEN_HEIGHT,
    SCREEN_WIDTH,
    reset=reset,
    cs=cs,
    dc=dc,
    backlight=backlight,
    color_order=st7789.RGB,
    inversion=False,
    rotation=1,
    options=0,
    buffer_size=64 * 64 * 3,
)
tft.init()
tft.madctl(0xE0)
screen_spi.init(baudrate=_SCREEN_BAUDRATE)
tft.rect(0, 0, SCREEN_WIDTH, SCREEN_HEIGHT, st7789.WHITE)
tft.write(pfont_med, "testing", 0, 0, st7789.WHITE)

tm.tft.write(tm.pfont_small, f"{selected_vcs[startchar:]}", tm.venue_bbox.x0, tm.venue_bbox.y0, tm.stage_date_color)

import async_urequests as requests

# from async_urequests import urequests as requests
import time, network, asyncio

wifi = network.WLAN(network.STA_IF)
wifi.active(True)
wifi.config(pm=network.WLAN.PM_NONE)
if not wifi.isconnected():
    wifi.connect("fiosteve-guest", "saragansteve3")

url = "https://stream.classicalarchives.com/tm/_definst_/mp4:NweQoOqxFMILL9LkLgHmif3ejDGhhhIQidLki_3uDoryHSRqDsW2FXzVzA948EcRD9hKZHaj-mDf3eFiXweY1JZa8uxp-QuzyvjPgMWIlBVOWPZAiHXgl8HQ7haRfQQNtWVljGniCb9_IinU8mQCTeEOTipfhCxA1VgckKXsE9c/_moUpsoizIm0SPxBLvdNAw/playlist.m3u8"

response = requests.get(url)
# task = asyncio.create_task(response)
# print(f"task {task}")
loop = asyncio.get_event_loop()
result = loop.run_until_complete(response)
print(result.text)
