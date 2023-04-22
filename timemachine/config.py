import json
import os
import time

import st7789
import vga1_16x32 as font
import fonts.vga1_bold_16x16 as bfont
import fonts.vga1_16x16 as sfont
from machine import SPI, Pin
from rotary_irq_esp import RotaryIRQ


ROOT_DIR = None
OPTIONS_PATH = None
DB_PATH = None

optd = {}


# State variables
NOT_READY = -1
INIT = 0
READY = 1
PAUSED = 2
STOPPED = 3
PLAYING = 4
ENDED = 5
PLAY_STATE = INIT
# PLAY_STATES = ['Not Ready', 'Init','Ready','Paused','Stopped','Playing', 'Ended']
SELECT_STAGED_DATE = False
DATE = None
VENUE = None
ARTIST = None
STAGED_DATE = None
PAUSED_AT = None
WOKE_AT = None
OTHER_YEAR = None
DATE_RANGE = None

ON_TOUR = False
EXPERIENCE = False
TOUR_YEAR = None
TOUR_STATE = 0

# Hardware pins


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
    42,
    40,
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
    8, 7, min_val=1, max_val=31, reverse=False, range_mode=RotaryIRQ.RANGE_BOUNDED, pull_up=True, half_step=False
)


def default_options():
    d = {}
    d["MODULE"] = "livemusic"
    d["COLLECTIONS"] = ["GratefulDead"]
    d["FAVORED_TAPER"] = ["miller"]
    d["AUTO_UPDATE_ARCHIVE"] = True
    d["UPDATE_ARCHIVE_ON_STARTUP"] = False
    d["PLAY_LOSSLESS"] = False
    d["TIMEZONE"] = "America/New_York"
    return d


def save_options(optd_to_save):
    print(f"in save_options. optd {optd_to_save}")
    options = {}
    f = open(OPTIONS_PATH, "r")
    tmpd = json.loads(f.read())
    if optd_to_save["COLLECTIONS"] == None:
        optd_to_save["COLLECTIONS"] = tmpd["COLLECTIONS"]
    for arg in optd_to_save.keys():
        if arg == arg.upper():
            if isinstance(optd_to_save[arg], (list, tuple)):
                optd_to_save[arg] = ",".join(optd_to_save[arg])
            elif isinstance(optd_to_save[arg], (bool)):
                optd_to_save[arg] = str(optd_to_save[arg]).lower()
            options[arg] = optd_to_save[arg]
    with open(OPTIONS_PATH, "w") as outfile:
        json.dump(options, outfile, indent=1)


def load_options():
    global optd
    optd = default_options()
    tmpd = {}
    try:
        f = open(OPTIONS_PATH, "r")
        tmpd = json.loads(f.read())
        for k in optd.keys():
            print(f"Loading options key is {k}")
            try:
                if k in [
                    "AUTO_UPDATE_ARCHIVE",
                    "PLAY_LOSSLESS",
                    "UPDATE_ARCHIVE_ON_STARTUP",
                ]:  # make booleans.
                    tmpd[k] = tmpd[k].lower() == "true"
                    print(f"Booleans k is {k}")
                if k in ["COLLECTIONS", "FAVORED_TAPER"]:  # make lists from comma-separated strings.
                    print(f"lists k is {k}")
                    c = [x.strip() for x in tmpd[k].split(",") if x != ""]
                    if k == "COLLECTIONS":
                        c = ["Phish" if x.lower() == "phish" else x for x in c]
                    tmpd[k] = c
            except Exception:
                print(f"Failed to set option {k}. Using {optd[k]}")
    except Exception:
        print(f"Failed to read options from {OPTIONS_PATH}. Using defaults")
    optd.update(tmpd)  # update defaults with those read from the file.
    print(f"in load_options, optd {optd}")
