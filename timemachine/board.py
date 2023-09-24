"""
litestream
Copyright (C) 2023  spertilo.net

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""

import os

import machine
import st7789
from machine import SPI, Pin
from rotary_irq_esp import RotaryIRQ


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

# Initialise the three rotaries. First value is CL, second is DT

knob_sense = 0
try:
    kf = open("/.knob_sense", "r")
    knob_sense = int(kf.readline().strip())
    if (knob_sense < 0) or (knob_sense > 7):
        print(f"knob_sense {knob_sense} read from /knob_sense out of bounds")
        knob_sense = 0
except Exception:
    knob_sense = 0

year_pins = (40, 42)
month_pins = (39, 18)
day_pins = (7, 8)

# Month
m = RotaryIRQ(
    month_pins[knob_sense & 1],
    month_pins[~knob_sense & 1],
    min_val=1,
    max_val=12,
    reverse=False,
    range_mode=RotaryIRQ.RANGE_BOUNDED,
    pull_up=True,
    half_step=False,
)
# Day
d = RotaryIRQ(
    day_pins[(knob_sense >> 1) & 1],
    day_pins[~(knob_sense >> 1) & 1],
    min_val=1,
    max_val=31,
    reverse=False,
    range_mode=RotaryIRQ.RANGE_BOUNDED,
    pull_up=True,
    half_step=False,
)
# Year
y = RotaryIRQ(
    year_pins[(knob_sense >> 2) & 1],
    year_pins[~(knob_sense >> 2) & 1],
    min_val=1966,
    max_val=1995,
    reverse=False,
    range_mode=RotaryIRQ.RANGE_BOUNDED,
    pull_up=True,
    half_step=False,
)

PlayPoly = [(0, 0), (0, 15), (15, 8), (0, 0)]
PausePoly = [(0, 0), (0, 15), (3, 15), (3, 0), (7, 0), (7, 15), (10, 15), (10, 0)]
StopPoly = [(0, 0), (0, 15), (15, 15), (15, 0)]
RewPoly = [(7, 0), (0, 8), (7, 15), (7, 0), (15, 0), (8, 8), (15, 15), (15, 0)]
FFPoly = [(0, 0), (0, 15), (8, 8), (0, 0), (8, 0), (8, 15), (15, 8), (8, 0)]

_SCREEN_BAUDRATE = 10_000_000

screen_spi = SPI(1, baudrate=_SCREEN_BAUDRATE, sck=Pin(12), mosi=Pin(11))


# Configure display driver
def conf_screen(rotation=0, buffer_size=0, options=0):
    return st7789.ST7789(
        screen_spi,
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


tft = conf_screen(1, buffer_size=64 * 64 * 2)
tft.init()
screen_spi.init(baudrate=_SCREEN_BAUDRATE)
tft.fill(st7789.BLACK)


stage_date_color = st7789.color565(255, 255, 0)
yellow_color = st7789.color565(255, 255, 0)
tracklist_color = st7789.color565(0, 255, 255)
play_color = st7789.color565(255, 0, 0)
nshows_color = st7789.color565(0, 100, 255)
