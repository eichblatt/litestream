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

import st7789
import time
from machine import SPI, Pin
from rotary_irq_esp import RotaryIRQ
import fonts.NotoSans_24 as pfont_med
import fonts.NotoSans_18 as pfont_small


KNOB_SENSE_PATH = "/.knob_sense"
SCREEN_TYPE_PATH = "/.screen_type"
SCREEN_STATE = 1
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

m = d = y = None  # knobs
year_pins = (40, 42)
month_pins = (39, 18)
day_pins = (7, 8)


def get_int_from_file(path, default_val, max_val):
    val = default_val
    fh = None
    try:
        fh = open(path, "r")
        val = int(fh.readline().strip())
        if val > max_val:
            raise ValueError(f"value {val} read from path is out of bounds (0,{max_val})")
    except Exception:
        val = default_val
        if val is not None:
            fh = open(path, "w")
            fh.write(f"{val}")
    finally:
        if fh is not None:
            fh.close()
    return val


def get_knob_sense():
    return get_int_from_file(KNOB_SENSE_PATH, 0, 7)


def setup_knobs(knob_sense):
    global m
    global d
    global y
    # Month
    m = RotaryIRQ(
        month_pins[knob_sense & 0x1],
        month_pins[~knob_sense & 0x1],
        min_val=1,
        max_val=12,
        reverse=False,
        range_mode=RotaryIRQ.RANGE_BOUNDED,
        pull_up=True,
        half_step=False,
    )
    # Day
    d = RotaryIRQ(
        day_pins[(knob_sense >> 1) & 0x1],
        day_pins[~(knob_sense >> 1) & 0x1],
        min_val=1,
        max_val=31,
        reverse=False,
        range_mode=RotaryIRQ.RANGE_BOUNDED,
        pull_up=True,
        half_step=False,
    )
    # Year
    y = RotaryIRQ(
        year_pins[(knob_sense >> 2) & 0x1],
        year_pins[~(knob_sense >> 2) & 0x1],
        min_val=1966,
        max_val=1995,
        reverse=False,
        range_mode=RotaryIRQ.RANGE_BOUNDED,
        pull_up=True,
        half_step=False,
    )


knob_sense = get_knob_sense()
setup_knobs(knob_sense)

PlayPoly = [(0, 0), (0, 15), (15, 8), (0, 0)]
PausePoly = [(0, 0), (0, 15), (3, 15), (3, 0), (7, 0), (7, 15), (10, 15), (10, 0)]
StopPoly = [(0, 0), (0, 15), (15, 15), (15, 0)]
RewPoly = [(7, 0), (0, 8), (7, 15), (7, 0), (15, 0), (8, 8), (15, 15), (15, 0)]
FFPoly = [(0, 0), (0, 15), (8, 8), (0, 0), (8, 0), (8, 15), (15, 8), (8, 0)]

_SCREEN_BAUDRATE = 10_000_000

screen_spi = SPI(1, baudrate=_SCREEN_BAUDRATE, sck=Pin(12), mosi=Pin(11))


class Bbox:
    """Bounding Box -- Initialize with corners."""

    def __init__(self, x0, y0, x1, y1):
        self.corners = (x0, y0, x1, y1)
        self.x0, self.y0, self.x1, self.y1 = self.corners
        self.width = self.x1 - self.x0
        self.height = self.y1 - self.y0
        self.origin = self.corners[:2]
        self.topright = self.corners[-2:]

    def __str__(self):
        return self.__repr__()

    def __repr__(self):
        return f"Bbox: x0 {self.x0},y0 {self.y0},x1 {self.x1},y1 {self.y1}"

    def __getitem__(self, key):
        return self.corners[key]

    def size(self):
        return (int(self.height), int(self.width))

    def center(self):
        return (int((self.x0 + self.x1) / 2), int((self.y0 + self.y1) / 2))

    def shift(self, d):
        return Bbox(self.x0 - d.x0, self.y0 - d.y0, self.x1 - d.x1, self.y1 - d.y1)


stage_date_bbox = Bbox(0, 0, 160, 32)
nshows_bbox = Bbox(150, 32, 160, 48)
venue_bbox = Bbox(0, 32, 160, 32 + 19)
artist_bbox = Bbox(0, 51, 160, 51 + 19)
tracklist_bbox = Bbox(0, 70, 160, 112)
selected_date_bbox = Bbox(15, 112, 145, 128)
playpause_bbox = Bbox(145, 113, 160, 128)

stage_date_color = st7789.color565(255, 255, 0)
yellow_color = st7789.color565(255, 255, 0)
tracklist_color = st7789.color565(0, 255, 255)
play_color = st7789.color565(255, 0, 0)
nshows_color = st7789.color565(0, 100, 255)


def init_screen():
    screen_spi.init(baudrate=_SCREEN_BAUDRATE)


def clear_bbox(bbox):
    init_screen()
    tft.fill_rect(bbox.x0, bbox.y0, bbox.width, bbox.height, st7789.BLACK)


def clear_area(x, y, width, height):
    init_screen()
    tft.fill_rect(x, y, width, height, st7789.BLACK)


def clear_screen():
    clear_area(0, 0, 160, 128)


def clear_area(x, y, width, height):
    init_screen()
    tft.fill_rect(x, y, width, height, st7789.BLACK)


def screen_state(state=None):
    global SCREEN_STATE
    if state is None:
        pass
    elif state == 0:
        tft.off()
        SCREEN_STATE = 0
    elif state > 0:
        tft.on()
        SCREEN_STATE = 1
    return SCREEN_STATE


def screen_off():
    return screen_state(0)


def screen_on():
    return screen_state(1)


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
psychedelic_screen = False
tft.init()

screen_spi.init(baudrate=_SCREEN_BAUDRATE)
tft.fill(st7789.BLACK)
screen_on_time = time.ticks_ms()
board_on = 1


stage_date_color = st7789.color565(255, 255, 0)
yellow_color = st7789.color565(255, 255, 0)
tracklist_color = st7789.color565(0, 255, 255)
play_color = st7789.color565(255, 0, 0)
nshows_color = st7789.color565(0, 100, 255)


def power(state=None):
    global screen_on_time
    global board_on

    if state is None:
        return board_on
    elif state in (0, 1):
        pLED.value(state)
        board_on = state
        if state:
            # tft.on()
            screen_on()
            screen_on_time = time.ticks_ms()
        else:
            # tft.off()
            screen_off()
    else:
        raise ValueError(f"invalid power state {state}")
    return state


def calibrate_knobs():
    print("Running knob calibration")
    knob_sense = get_knob_sense()
    print(f"knob_sense before is {knob_sense}")
    change = 0
    for knob, name, bit in zip([m, d, y], ["Month", "Day", "Year"], (0, 1, 2)):
        knob._value = (knob._min_val + knob._max_val) // 2  # can move in either direction.
        prev_value = knob.value()
        write("Rotate")
        write(f"{name}", 0, 25, color=yellow_color, clear=False)
        write("Knob Forward", 0, 50, clear=False)
        while prev_value == knob.value():
            time.sleep(0.05)
        change = (change | int(knob.value() < prev_value) << bit) & 0x7
    knob_sense = knob_sense ^ change
    print(f"knob sense change: {change}. Value after {knob_sense}")
    setup_knobs(knob_sense)
    write("Knobs\nCalibrated")
    try:
        kf = open(KNOB_SENSE_PATH, "w")
        kf.write(f"{knob_sense}")
    except Exception:
        print(f"Exception writing {KNOB_SENSE_PATH}")
        knob_sense = 0
    finally:
        kf.close()
    return knob_sense


def calibrate_screen(force=False):
    print("Running screen calibration")
    screen_type = get_int_from_file(SCREEN_TYPE_PATH, default_val=None, max_val=1)
    if (screen_type is not None) and not force:
        if screen_type == 0:
            tft.offset(0, 0)
        elif screen_type == 1:
            tft.offset(1, 2)
        return screen_type
    print(f"screen_type before is {screen_type}")
    # Draw a rectangle on screen.
    tft.on()
    clear_screen()
    tft.offset(0, 0)
    tft.rect(0, 0, 160, 128, st7789.WHITE)
    # Can you see all 4 sides?
    write("Press SELECT if", 1, 5, font=pfont_small, clear=False)
    write("all 4 sides visible", 1, 25, font=pfont_small, clear=False)
    write("else press STOP", 1, 60, font=pfont_small, clear=False)

    button = poll_for_which_button({"select": pSelect, "stop": pStop}, timeout=45, default="select")
    if button == "stop":
        screen_type = 1
        tft.offset(1, 2)
    else:
        screen_type = 0
        tft.offset(0, 0)

    try:
        fh = open(SCREEN_TYPE_PATH, "w")
        fh.write(f"{screen_type}")
    except Exception:
        print(f"Exception writing {SCREEN_TYPE_PATH}")
        screen_type = 0
    finally:
        fh.close()
        tft.on()
        clear_screen()
    return screen_type


def self_test():
    print("Running self_test")
    buttons = [pSelect, pStop, pRewind, pFFwd, pPlayPause, pPower, pMSw, pDSw, pYSw]
    button_names = ["Select", "Stop", "Rewind", "FFwd", "PlayPause", "Power", "Month", "Day", "Year"]
    for button, name in zip(buttons, button_names):
        write("Press")
        write(f"{name}", 0, 25, color=yellow_color, clear=False)
        write("Button", 0, 50, clear=False)
        poll_for_button(button)
    write("Button Test\nPassed")
    time.sleep(2)
    return


def poll_for_button(button, timeout=None):
    start_time = time.ticks_ms()
    pButton_old = True
    while pButton_old == button.value():
        if (timeout is not None) and (time.ticks_diff(time.ticks_ms(), start_time) > (timeout * 1000)):
            break
    return


def poll_for_which_button(button_dict, timeout=None, default=None):
    start_time = time.ticks_ms()

    pButton_old_dict = {x: False for x in button_dict.keys()}
    while (timeout is None) or (time.ticks_diff(time.ticks_ms(), start_time) < (timeout * 1000)):
        for button_name, button in button_dict.items():
            if pButton_old_dict[button_name] == button.value():
                return button_name
    return default


def write(msg, x=0, y=0, font=pfont_med, color=st7789.WHITE, text_height=20, clear=True):
    if clear:
        clear_screen()
    text = msg.split("\n")
    for i, line in enumerate(text):
        tft.write(font, line, x, y + (i * text_height), color)
