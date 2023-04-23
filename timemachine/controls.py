"""controls -- the definition of the hardward on the Time Machine board
"""
import st7789
import vga1_16x32 as font
import fonts.vga1_bold_16x16 as bfont
import fonts.vga1_16x16 as sfont
import fonts.NotoSans_32 as prop_font
import fonts.gothger as gothic_font
import fonts.romanc as roman_font
from machine import SPI, Pin
from rotary_irq_esp import RotaryIRQ

# Init screen
def configure(rotation=0, buffer_size=0, options=0):
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
tft = configure(1, buffer_size=64 * 64 * 2)

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
y = RotaryIRQ(
    40,
    42,
    min_val=1966,
    max_val=1995,
    reverse=False,
    range_mode=RotaryIRQ.RANGE_BOUNDED,
    pull_up=True,
    half_step=False,
)
# Month
m = RotaryIRQ(
    39, 18, min_val=1, max_val=12, reverse=False, range_mode=RotaryIRQ.RANGE_BOUNDED, pull_up=True, half_step=False
)
# Day
d = RotaryIRQ(
    7, 8, min_val=1, max_val=31, reverse=False, range_mode=RotaryIRQ.RANGE_BOUNDED, pull_up=True, half_step=False
)
