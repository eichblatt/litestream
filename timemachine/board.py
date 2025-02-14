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

import math
import os
import st7789
import time
from machine import SPI, Pin
from rotary_irq_esp import RotaryIRQ


# --------------------------------------- configuration
try:
    os.mkdir("/config")
except:
    pass
KNOB_SENSE_PATH = "/config/knob_sense"
SCREEN_TYPE_PATH = "/config/screen_type"
_SCREEN_BAUDRATE = 40_000_000
SCREEN_STATE = 1
BOARD_ON = 1

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
    except Exception as e:
        print(f"Exception in get_int_from_file {e}. path {path}")
        val = default_val
    finally:
        if fh is not None:
            fh.close()
    return val


# -------------------------------------------- set up screen

screen_type = get_int_from_file(SCREEN_TYPE_PATH, default_val=0, max_val=3)
# screen_types:
# 0 - SMALL st7789 128x160 offset 0
# 1 - SMALL st7789 128x160 offset 1
# 2 - MED   st7789 240x320 offset 0
# 3 - MED   st7789 240x320 offset 1
if screen_type < 2:
    SCREEN_DRIVER = "st7789"
    SCREEN_HEIGHT = 128
    SCREEN_WIDTH = 160
    SCREEN_VPARTS = (SCREEN_HEIGHT,)
    import fonts.NotoSans_18 as pfont_smallx
    import fonts.NotoSans_bold_18 as pfont_small
    import fonts.NotoSans_24 as pfont_med
    import fonts.NotoSans_32 as pfont_large
    import fonts.DejaVu_33 as large_font
    import fonts.date_font as date_font
elif screen_type in (2, 3):
    SCREEN_DRIVER = "st7789"
    import fonts.NotoSans_bold_18 as pfont_tiny
    import fonts.NotoSans_24 as pfont_small
    import fonts.NotoSans_24 as pfont_med
    import fonts.NotoSans_48 as pfont_large
    import fonts.DejaVu_60 as large_font
    import fonts.DejaVu_33 as date_font

    SCREEN_HEIGHT = 240 - pfont_tiny.HEIGHT
    SCREEN_WIDTH = 320
    SCREEN_VPARTS = (SCREEN_HEIGHT, pfont_tiny.HEIGHT)

    # import fonts.NotoSans_24 as pfont_med
    # import fonts.NotoSans_18 as pfont_small
    # import fonts.DejaVu_33 as large_font
    # import fonts.date_font as date_font
else:
    pass


screen_spi = SPI(1, baudrate=_SCREEN_BAUDRATE, sck=Pin(12), mosi=Pin(11))


# Configure display driver
def conf_screen(rotation=1, buffer_size=0, options=0, driver="st7789"):
    reset = Pin(4, Pin.OUT)
    cs = Pin(10, Pin.OUT)
    dc = Pin(6, Pin.OUT)
    backlight = Pin(5, Pin.OUT)

    return st7789.ST7789(
        screen_spi,
        sum(SCREEN_VPARTS),
        SCREEN_WIDTH,
        reset=reset,
        cs=cs,
        dc=dc,
        backlight=backlight,
        color_order=st7789.RGB,
        inversion=False,
        rotation=rotation,
        options=options,
        buffer_size=buffer_size,
    )


# tft = conf_screen(buffer_size=64 * 64 * 2, driver=SCREEN_DRIVER)
tft = conf_screen(buffer_size=0, driver=SCREEN_DRIVER)
psychedelic_screen = False
tft.init()

tft.madctl(0x60 if screen_type < 2 else 0xE8)

screen_on_time = time.ticks_ms()


def init_screen():
    screen_spi.init(baudrate=_SCREEN_BAUDRATE)


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


# ------------------------------------------------- knobs
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


def label_soft_knobs(left, center, right):
    if len(SCREEN_VPARTS) < 2:
        return
    print("labelling soft knobs")
    left = f"  {left}  "
    center = f"  {center}  "
    right = f"  {right}  "
    font = pfont_tiny
    bg = YELLOW
    fg = BLACK
    widths = [tft.write_len(font, x) for x in [left, center, right]]
    if sum(widths) > SCREEN_WIDTH:
        raise NotImplementedError("Strings are too wide, Bailing")
    clear_area(0, SCREEN_VPARTS[0], SCREEN_WIDTH, pfont_tiny.HEIGHT)
    write(left, 0, SCREEN_VPARTS[0], font, color=fg, background=bg, bounds_check=False)
    write(center, int(0.5 * SCREEN_WIDTH - 0.5 * widths[1]), SCREEN_VPARTS[0], font, fg, background=bg, bounds_check=False)
    write(right, SCREEN_WIDTH - widths[2], SCREEN_VPARTS[0], font, fg, background=bg, bounds_check=False)
    return


# ------------------------------------------------ areas
class Bbox:
    """Bounding Box -- Initialize with corners, x0, y0, x1, y1."""

    def __init__(self, x0, y0, x1, y1):
        self.corners = (int(x0), int(y0), int(x1), int(y1))
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


stage_date_bbox = Bbox(0, 0, SCREEN_WIDTH, SCREEN_HEIGHT // 4)
nshows_bbox = Bbox(0.95 * SCREEN_WIDTH, SCREEN_HEIGHT // 4, SCREEN_WIDTH, 3 * (SCREEN_HEIGHT // 8))


PlayPoly = [(0, 0), (0, 15), (15, 8), (0, 0)]
PausePoly = [(0, 0), (0, 15), (3, 15), (3, 0), (7, 0), (7, 15), (10, 15), (10, 0)]
# StopPoly = [(0, 0), (0, 15), (15, 15), (15, 0)]
RewPoly = [(7, 0), (0, 8), (7, 15), (7, 0), (15, 0), (8, 8), (15, 15), (15, 0)]
FFPoly = [(0, 0), (0, 15), (8, 8), (0, 0), (8, 0), (8, 15), (15, 8), (8, 0)]


# ------------------------------------------------ colors
def color_rgb(r, g, b):
    if SCREEN_DRIVER == "st7789":
        return st7789.color565(r, g, b)
    else:
        raise ValueError(f"Unknown Screen Driver {SCREEN_DRIVER}")


tracklist_color = color_rgb(0, 158, 255)
# play_color = color_rgb(20, 255, 60)
play_color = color_rgb(255, 0, 15)
pause_color = color_rgb(255, 0, 15)
nshows_color = tracklist_color
selected_date_color = color_rgb(255, 255, 150)
RED = color_rgb(255, 0, 0)
WHITE = color_rgb(255, 255, 255)
BLACK = color_rgb(0, 0, 0)
YELLOW = color_rgb(255, 255, 20)
PURPLE = color_rgb(255, 72, 255)
stage_date_color = YELLOW


# ------------------------------------------------ clear areas
def clear_bbox(bbox):
    init_screen()
    tft.fill_rect(bbox.x0, bbox.y0, bbox.width, bbox.height, BLACK)


def clear_area(x, y, width, height):
    init_screen()
    tft.fill_rect(x, y, width, height, BLACK)


def clear_to_bottom(x0, y0):
    tft.fill_rect(x0, y0, SCREEN_WIDTH - x0, SCREEN_HEIGHT - y0, BLACK)


def clear_screen():
    clear_area(0, 0, SCREEN_WIDTH, SCREEN_HEIGHT)


def power(state=None):
    global screen_on_time
    global BOARD_ON

    if state is None:
        return BOARD_ON
    elif state in (0, 1):
        pLED.value(state)
        BOARD_ON = state
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


# ---------------------------------------- calibration
def calibrate_knobs():
    print("Running knob calibration")
    knob_sense = get_knob_sense()
    print(f"knob_sense before is {knob_sense}")
    change = 0
    text_height = pfont_med.HEIGHT
    for knob, name, bit in zip([m, d, y], ["Left knob", "Center knob", "Right knob"], (0, 1, 2)):
        knob._value = (knob._min_val + knob._max_val) // 2  # can move in either direction.
        prev_value = knob.value()
        clear_screen()
        write("Rotate")
        write(f"{name}", 0, text_height, color=YELLOW)
        write("Forward", 0, 2 * text_height)
        while prev_value == knob.value():
            time.sleep(0.05)
        change = (change | int(knob.value() < prev_value) << bit) & 0x7
    knob_sense = knob_sense ^ change
    print(f"knob sense change: {change}. Value after {knob_sense}")
    setup_knobs(knob_sense)
    clear_screen()
    write("Knobs Calibrated", show_end=-2)
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
    label_soft_knobs("-", "-", "-")
    screen_type = get_int_from_file(SCREEN_TYPE_PATH, default_val=None, max_val=3)
    if (screen_type is not None) and not force:
        tft.madctl(0x60 if screen_type < 2 else 0xE8)
        tft.offset(0, 0) if (screen_type % 2 == 0) else tft.offset(1, 2)
        return screen_type
    screen_type = 0 if (SCREEN_WIDTH == 160) else 2  # in case of factory reset, we MUST have a screen type.
    print(f"screen_type before is {screen_type}")
    # Draw a rectangle on screen.
    tft.on()
    clear_screen()
    tft.offset(0, 0)
    tft.rect(0, 0, SCREEN_WIDTH, SCREEN_HEIGHT, WHITE)
    # Can you see all 4 sides?
    msg = write("Press SELECT if all 4 sides visible", 1, 5, font=pfont_small, show_end=-3)
    nlines = len(msg.split("\n"))
    write("else press STOP", 1, nlines * pfont_small.HEIGHT + 5, font=pfont_small)

    button = poll_for_which_button({"select": pSelect, "stop": pStop, "ffwd": pFFwd}, timeout=45, default="select")
    if button == "stop":
        screen_type = screen_type | 0x01
        tft.offset(1, 2)
    elif button == "select":
        screen_type = screen_type & 0xE
        tft.offset(0, 0)
    elif button == "ffwd":  # change from big to small or vice versa
        screen_type = screen_type ^ 0x02
    else:
        print(f"Unknown action when {button} pressed. Continuing")
        pass
    print(f"Screen Type is after {screen_type}")

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


# ---------------------------------------- utilities
def self_test():
    print("Running self_test")
    label_soft_knobs("Left", "Center", "Right")
    buttons = [pSelect, pStop, pRewind, pFFwd, pPlayPause, pPower, pMSw, pDSw, pYSw]
    button_names = ["Select", "Stop", "Rewind", "FFwd", "PlayPause", "Power", "Left knob", "Center knob", "Right knob"]
    for button, name in zip(buttons, button_names):
        clear_screen()
        write("Press")
        write(f"{name}", 0, pfont_med.HEIGHT, color=YELLOW)
        # write("Button", 0, 2 * pfont_med.HEIGHT)
        poll_for_button(button)
    clear_screen()
    write("Button Test\nPassed")
    time.sleep(0.2)
    return


def poll_for_button(button, timeout=None):
    start_time = time.ticks_ms()
    pButton_old = True
    while pButton_old == button.value():
        if (timeout is not None) and (time.ticks_diff(time.ticks_ms(), start_time) > (timeout * 1000)):
            return False
    return True


def poll_for_which_button(button_dict, timeout=None, default=None):
    start_time = time.ticks_ms()

    pButton_old_dict = {x: False for x in button_dict.keys()}
    while (timeout is None) or (time.ticks_diff(time.ticks_ms(), start_time) < (timeout * 1000)):
        for button_name, button in button_dict.items():
            if pButton_old_dict[button_name] == button.value():
                return button_name
    return default


# ---------------------------------------- text functions
def trim_string_middle(text, x_pos, font):
    pixel_width = tft.write_len(font, text)
    while (pixel_width + x_pos) > SCREEN_WIDTH:
        middle_char = len(text) // 2
        text = text[: middle_char - 1] + "~" + text[middle_char + 1 :]
        pixel_width = tft.write_len(font, text)
    return text


def add_line_breaks(text, x_pos, font, max_new_lines, indent=0):
    out_lines = []
    new_lines = 0
    split_on_words = max_new_lines < 0
    lines = text.split("\n")
    for line in lines:
        while new_lines < abs(max_new_lines):
            indention = (indent * " ") if new_lines > 0 else ""
            test = indention + line
            pixel_width = tft.write_len(font, test)
            while (pixel_width + x_pos) > SCREEN_WIDTH:
                if split_on_words:
                    test = test.split(" ")
                    test = " ".join(test[:-1])
                else:
                    test = test[:-1]
                pixel_width = tft.write_len(font, test)
            out_lines.append(test)
            if len(test) < len(line):
                new_lines = new_lines + 1
                line = line[len(test) :]
            else:
                break
        out_lines = "\n".join(out_lines)
        return out_lines


def write(msg, x=0, y=0, font=pfont_med, color=WHITE, show_end=0, indent=0, background=0, bounds_check=True):
    # write the msg starting at x,y in font with color.
    # show_end: 0 - display as much as possible in 1 line.
    # show_end: +n - break the text up into as many as n lines.
    # show_end: -n - break the text up on *word boundaries* in as many as n lines.

    if abs(show_end) > 1:
        msg = add_line_breaks(msg, x, font, show_end, indent=indent)
    text = msg.split("\n")
    y0 = y
    for line in text:
        if show_end == 1:
            line = trim_string_middle(line, x, font)
        if bounds_check and ((x >= SCREEN_WIDTH) or (y0 >= SCREEN_HEIGHT - font.HEIGHT)):
            continue
        tft.write(font, line, x, y0, color, background)
        y0 += font.HEIGHT
    return msg


# ---------------------------------------- decade counter
class decade_counter:
    def __init__(self, knobs, max_val, decade_size=None):
        self.knobs = knobs
        self.knobs[1]._range_mode = self.knobs[1].RANGE_WRAP
        self.max_val = max_val
        self.compute_decade_size(decade_size)
        self.set_max_value(max_val)
        value = self.get_value()

    def __repr__(self):
        return str(
            f"({self.knobs[0]._value} * {self.decade_size}) + {self.knobs[1]._value} = {self.get_value()}. Max {self.max_val}"
        )

    def _reduce_vals(self, val):
        # Set the knob vals to their lowest values.
        self.knobs[0]._value = val // self.decade_size
        self.knobs[1]._value = val % self.decade_size

    def compute_decade_size(self, decade_size=None):
        # print(f"decade_counter decade size is {decade_size}")
        if decade_size is not None:
            self.decade_size = decade_size
        elif self.max_val < 13:
            self.decade_size = 1
        elif self.max_val < 100:
            self.decade_size = 10
        else:
            self.decade_size = int(math.sqrt(self.max_val))
        return self.decade_size

    def get_value(self):
        val = (self.decade_size * self.knobs[0].value()) + self.knobs[1].value()
        val = min(val, self.max_val)
        val = max(val, 0)
        self._reduce_vals(val)
        return val

    def set_value(self, value):
        value = min(value, self.max_val)
        value = max(value, 0)
        self._reduce_vals(value)

    def set_max_value(self, max_val):
        # print(f"setting max value in decade_counter to {max_val}")
        if max_val is None:
            self.max_val = self.decade_size * (self.knobs[0]._max_val + 1)
        else:
            self.max_val = max_val
        self.compute_decade_size()
        self.n_decades = 1 + self.max_val // self.decade_size
        # print(f"decade_size to {self.decade_size}")
        self.knobs[0]._max_val = 1 + self.max_val // self.decade_size
        self.knobs[1]._max_val = self.max_val
        self.knobs[1]._min_val = -self.max_val
        self.knobs[0]._min_val = 0
        self.set_value(self.get_value())
