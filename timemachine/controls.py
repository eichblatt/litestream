"""controls -- the definition of the hardward on the Time Machine board """
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
"""
import st7789
import vga1_16x32 as font
import fonts.vga1_bold_16x16 as bfont
import fonts.vga1_16x16 as sfont
import fonts.NotoSans_32 as pfont_large
import fonts.gothger as gothic_font
import fonts.romanc as roman_font
from machine import SPI, Pin
from rotary_irq_esp import RotaryIRQ


class Bbox:
    def __init__(self, x0, y0, x1, y1):
        self.corners = (x0, y0, x1, y1)
        self.x0, self.y0, self.x1, self.y1 = self.corners

    def __str__(self):
        return self.__repr__()

    def __repr__(self):
        return f"Bbox: x0 {self.x0},y0 {self.y0},x1 {self.x1},y1 {self.y1}"

    def __getitem__(self, key):
        return self.corners[key]

    def width(self):
        return self.x1 - self.x0

    def height(self):
        return self.y1 - self.y0

    def origin(self):
        return (self.x0, self.y0)

    def topright(self):
        return (self.x1, self.y1)

    def size(self):
        return (int(self.height()), int(self.width()))

    def center(self):
        return (int((self.x0 + self.x1) / 2), int((self.y0 + self.y1) / 2))

    def shift(self, d):
        return Bbox(self.x0 - d.x0, self.y0 - d.y0, self.x1 - d.x1, self.y1 - d.y1)


class screen:
    def __init__(self, rotation=0, buffer_size=0, options=0):
        self.disp = st7789.ST7789(
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
        self.disp.init()
        self.disp.fill(st7789.BLACK)
        self.venue_color = st7789.color565(255, 255, 0)
        self.font = roman_font
        self.width = 160
        self.height = 128

        self.staged_years = (-1, -1)
        self.staged_date = None
        self.selected_date = None

        self.bbox = Bbox(0, 0, 160, 128)
        self.staged_date_bbox = Bbox(0, 0, 160, 31)
        self.selected_date_bbox = Bbox(0, 100, 160, 128)
        self.venue_bbox = Bbox(0, 31, 160, 56)
        self.nevents_bbox = Bbox(148, 31, 160, 56)
        self.track1_bbox = Bbox(0, 55, 160, 77)
        self.track2_bbox = Bbox(0, 78, 160, 100)
        self.playstate_bbox = Bbox(130, 100, 160, 128)
        self.sbd_bbox = Bbox(155, 100, 160, 108)
        self.exp_bbox = Bbox(0, 55, 160, 100)

        self.update_now = True
        self.sleeping = False

    def clear_area(self, bbox):
        self.disp.fill_rect(*bbox.corners, st7789.BLACK)

    def clear(self):
        self.clear_area(self.bbox)

    def show_text(self, text, bbox=(0, 0, 160, 128), font=None, color=(255, 255, 255), scale=1):
        # controls.tft.show_text(controls.roman_font, f"{vcs}", 0, 40, stage_date_color, 0.65)
        if text is None:
            text = " "
        if font is None:
            font = self.font
        if font.__name__.endswith("romanc"):
            bboxt = bbox.shift(Bbox(0, int(-10 * scale), 0, int(-10 * scale)))
        self.clear_area(bbox)
        self.disp.draw(font, text, *bboxt.origin(), color, scale)

    def off(self):
        self.disp.off()

    def on(self):
        self.disp.on()

    def show_venue(self, text, color=None):
        color = self.venue_color if color is None else st7789.color565(color)
        self.show_text(text, self.venue_bbox, roman_font, color, 0.65)

    def show_staged_date(self, text, color=None):
        color = self.venue_color if color is None else st7789.color565(color)
        self.show_text(text, self.staged_date_bbox, roman_font, color, 1)


PlayPausePoly = [(0, 0), (0, 15), (15, 8), (0, 0)]
RewPoly = [(7, 0), (0, 8), (7, 15), (7, 0), (15, 0), (8, 8), (15, 15), (15, 0)]
FFPoly = [(0, 0), (0, 15), (8, 8), (0, 0), (8, 0), (8, 15), (15, 8), (8, 0)]

# Configure display driver
# tft = configure(1, buffer_size=64 * 64 * 2)

tft = screen(rotation=1, buffer_size=64 * 64 * 2)


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

# pLED = Pin(48, Pin.OUT) # Using for 1053's XDCS

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
m = RotaryIRQ(39, 18, min_val=1, max_val=12, reverse=False, range_mode=RotaryIRQ.RANGE_BOUNDED, pull_up=True, half_step=False)
# Day
d = RotaryIRQ(7, 8, min_val=1, max_val=31, reverse=False, range_mode=RotaryIRQ.RANGE_BOUNDED, pull_up=True, half_step=False)
"""
