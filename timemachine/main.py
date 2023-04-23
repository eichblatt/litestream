# Display driver: https://github.com/russhughes/st7789_mpy
import json
import os
import time
import network
import time
import mrequests

import config

import st7789
import vga1_16x32 as font
import fonts.vga1_bold_16x16 as bfont
import fonts.vga1_16x16 as sfont
import fonts.NotoSans_32 as prop_font
import fonts.gothger as gothic_font
import fonts.romanc as roman_font
import fonts.romant as romant_font
from machine import SPI, Pin
from rotary_irq_esp import RotaryIRQ

config.load_options()

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

PlayPausePoly = [(0, 0), (0, 15), (15, 8), (0, 0)]
RewPoly = [(7, 0), (0, 8), (7, 15), (7, 0), (15, 0), (8, 8), (15, 15), (15, 0)]
FFPoly = [(0, 0), (0, 15), (8, 8), (0, 0), (8, 0), (8, 15), (15, 8), (8, 0)]

# Configure display driver
def conf_screen(rotation=0, buffer_size=0, options=0):
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


tft = conf_screen(1, buffer_size=64 * 64 * 2)
tft.init()
tft.fill(st7789.BLACK)


def clear_area(tft, x, y, width, height):
    tft.fill_rect(x, y, width, height, st7789.BLACK)


def clear_screen(tft):
    clear_area(tft, 0, 0, 160, 128)


def connect_network():
    wifi = network.WLAN(network.STA_IF)
    wifi.active(True)
    # wifi.scan()  # Scan for available access points
    if not wifi.isconnected():
        wifi.connect("fiosteve", "Fwest5%maini")  # Connect to an AP
    wifi.isconnected()  # Check for successful connection


print("Starting...")


def set_date(date):
    global m
    global y
    global d
    y._value = int(date[:4])
    m._value = int(date[5:7])
    d._value = int(date[8:10])
    key_date = f"{y.value()}-{m.value():02d}-{d.value():02d}"
    return key_date


def main_loop(col_dict):
    year_old = -1
    month_old = -1
    day_old = -1
    date_old = ""
    pPower_old = True
    pSelect_old = False
    pPlayPause_old = False
    pStop_old = False
    pRewind_old = False
    pFFwd_old = False
    pYSw_old = False
    pMSw_old = False
    pDSw_old = False
    stage_date_color = st7789.color565(255, 255, 0)
    clear_screen(tft)

    while True:

        if pPower_old != pPower.value():
            pPower_old = pPower.value()
            pLED.value(PowerLED)
            tft.off() if not PowerLED else tft.on()
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
                tft.text(sfont, "Y", 60, 70, st7789.WHITE, st7789.BLUE)
                print("Year UP")
            else:
                # cycle through Today In History (once we know what today is!)
                tft.text(sfont, "Y", 60, 70, st7789.BLUE, st7789.WHITE)
                print("Year DOWN")

        if pMSw_old != pMSw.value():
            pMSw_old = pMSw.value()
            if pMSw_old:
                tft.text(sfont, "M", 0, 70, st7789.WHITE, st7789.BLUE)
                print("Month UP")
            else:
                tft.text(sfont, "M", 0, 70, st7789.BLUE, st7789.WHITE)
                print("Month DOWN")

        if pDSw_old != pDSw.value():
            pDSw_old = pDSw.value()
            if pDSw_old:
                tft.text(sfont, "D", 30, 70, st7789.WHITE, st7789.BLUE)
                print("Day UP")
            else:
                for date in sorted(col_dict["GratefulDead"].keys()):
                    if date > key_date:
                        key_date = set_date(date)
                        break
                tft.text(sfont, "D", 30, 70, st7789.BLUE, st7789.WHITE)
                print("Day DOWN")

        year_new = y.value()
        month_new = m.value()
        day_new = d.value()
        date_new = f"{month_new}-{day_new}-{year_new%100}"
        key_date = f"{year_new}-{month_new:02d}-{day_new:02d}"

        if year_old != year_new:
            year_old = year_new
            tft.text(font, f"{year_new%100}", 90, 0, stage_date_color, st7789.BLACK)
            print("year =", year_new)

        if month_old != month_new:
            month_old = month_new
            tft.text(font, f"{month_new:2d}-", 0, 0, stage_date_color, st7789.BLACK)
            print("month =", month_new)

        if day_old != day_new:
            day_old = day_new
            tft.text(font, f"{day_new:2d}-", 43, 0, stage_date_color, st7789.BLACK)
            print("day =", day_new)

        if date_old != date_new:
            date_old = date_new
            print(f"date = {date_new} or {key_date}")
            try:
                vcs = col_dict["GratefulDead"][f"{key_date}"]
                print(vcs)
                clear_area(tft, 0, 25, 160, 32)
                tft.draw(roman_font, f"{vcs}", 0, 40, stage_date_color, 0.65)
            except KeyError:
                clear_area(tft, 0, 25, 160, 32)
                pass
        # time.sleep_ms(50)


def load_col(col):
    ids_path = f"metadata/{col}_ids/tiny.json"
    print(f"Loading collection {col} from {ids_path}")
    data = json.load(open(ids_path, "r"))
    return data


def lookup_date(d, col_d):
    response = []
    for col, data in col_d.items():
        if d in data.keys():
            response.append([col, data[d]])
    return response


def main():
    """
    This script will load a super-compressed version of the
    date, artist, venue, city, state.
    """
    tft.draw(gothic_font, f"Grateful Dead", 0, 30, st7789.color565(255, 255, 0), 0.8)
    tft.draw(gothic_font, f"Time Machine", 0, 60, st7789.color565(255, 255, 0), 0.8)
    tft.draw(gothic_font, f"Loading", 0, 90, st7789.color565(255, 255, 0), 1)
    col_dict = {}
    for col in config.optd["COLLECTIONS"]:
        col_dict[col] = load_col(col)

    print(f"Loaded collections {col_dict.keys()}")

    main_loop(col_dict)


# col_dict = main()
# lookup_date("1994-07-31", col_dict)
main()
