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
