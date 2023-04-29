# Display driver: https://github.com/russhughes/st7789_mpy
import json
import os
import time
import network
import time
from mrequests_pkg import mrequests as requests

import config
import st7789
import vga1_16x32 as font
import fonts.vga1_bold_16x16 as bfont
import fonts.vga1_16x16 as sfont
import fonts.NotoSans_18 as pfont_small
import fonts.NotoSans_24 as pfont_med
import fonts.NotoSans_32 as pfont_large
import fonts.gothger as gothic_font
import fonts.romanc as roman_font
import fonts.romant as romant_font
from machine import SPI, Pin
from rotary_irq_esp import RotaryIRQ
import network


config.load_options()

#API = 'http://192.168.1.231:5000'
API = 'http://deadstreamv3:5000'

def connect_wifi():
    wifi = network.WLAN(network.STA_IF)
    wifi.active(True)
    # sta_if.scan()  # Scan for available access points
    if not wifi.isconnected():
        print("Attempting to connect to network")
        wifi.connect("fiosteve", "Fwest5%maini")
        time.sleep(2)

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

class Bbox:
    """Bounding Box -- Initialize with corners.
    """
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

def clear_bbox(tft, bbox):
    tft.fill_rect(bbox.x0, bbox.y0, bbox.width, bbox.height, st7789.BLACK)

def clear_area(tft, x, y, width, height):
    tft.fill_rect(x, y, width, height, st7789.BLACK)


def clear_screen(tft):
    clear_area(tft, 0, 0, 160, 128)

print("Starting...")


def set_ymd(year=None, month=None, day=None):
    global m
    global y
    global d
    if year is not None:
        y._value = year
    if month is not None:
        m._value = month
    if day is not None:
        d._value = day
    key_date = f"{y.value()}-{m.value():02d}-{d.value():02d}"
    return key_date


def set_date(date):
    global m
    global y
    global d
    y._value = int(date[:4])
    m._value = int(date[5:7])
    d._value = int(date[8:10])
    key_date = f"{y.value()}-{m.value():02d}-{d.value():02d}"
    return key_date


def best_tape(collection, key_date):
    pass


def select_date(collection, key_date):
    print(f"selecting show from {key_date}")
    # tape_id = best_tape(collection, key_date)
    api_request = f"{API}/tracklist/{key_date}" 
    resp = requests.get(api_request).json()
    tracklist = resp['tracklist']
    api_request = f"{API}/urls/{key_date}" 
    resp = requests.get(api_request).json()
    urls = resp['urls']
    print(f"URLs: {urls}")
    return tracklist

selected_date_bbox = Bbox(0,110,160,128)
venue_bbox = Bbox(0,32,160,32+18)
stage_date_bbox = Bbox(0,0,160,32)
tracklist_bbox = Bbox(0,52, 160, 95)
tracklist_color = st7789.color565(0, 255, 255)

def display_tracks(tft,current_track,next_track):
    clear_bbox(tft, tracklist_bbox)
    tft.write(pfont_small, f"{current_track}", tracklist_bbox.x0, tracklist_bbox.y0, tracklist_color)
    tft.write(pfont_small, f"{next_track}", tracklist_bbox.x0, tracklist_bbox.center()[1], tracklist_color)
    return 

def main_loop(col_dict):
    year_old = -1
    month_old = -1
    day_old = -1
    date_old = ""
    PowerLED = True
    pPower_old = False
    pSelect_old = False
    pPlayPause_old = False
    pStop_old = False
    pRewind_old = False
    pFFwd_old = False
    pYSw_old = False
    pMSw_old = False
    pDSw_old = False
    stage_date_color = st7789.color565(255, 255, 0)
    key_date = set_date('1975-08-13')
    selected_date = key_date
    current_track_index = -1
    tracklist = []
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
                if key_date in col_dict["GratefulDead"].keys():
                    current_track_index = 0
                    tracklist = select_date('GratefulDead',key_date)
                    current_track = tracklist[current_track_index]
                    next_track = tracklist[current_track_index+1] if len(tracklist)> current_track_index else ''
                    display_tracks(tft,current_track,next_track)

                    selected_date = key_date
                    clear_bbox(tft, selected_date_bbox)
                    tft.write(pfont_small, f"{selected_date[5:7]}-{selected_date[8:10]}-{selected_date[:4]}",
                              selected_date_bbox.x0,selected_date_bbox.y0)

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
                if current_track_index <= 0:
                    pass
                elif current_track_index>=0:
                    current_track_index += -1
                    current_track = tracklist[current_track_index]
                    next_track = tracklist[current_track_index+1] if len(tracklist) > current_track_index + 1 else ''
                    display_tracks(tft,current_track,next_track)




        if pFFwd_old != pFFwd.value():
            pFFwd_old = pFFwd.value()
            if pFFwd_old:
                tft.fill_polygon(FFPoly, 80, 108, st7789.BLUE)
                print("FFwd UP")
            else:
                tft.fill_polygon(FFPoly, 80, 108, st7789.WHITE)
                print("FFwd DOWN")
                if current_track_index >= len(tracklist):
                    pass
                elif current_track_index>=0:
                    current_track_index += 1 if len(tracklist)> current_track_index + 1 else 0
                    current_track = tracklist[current_track_index]
                    next_track = tracklist[current_track_index+1] if len(tracklist) > current_track_index + 1 else ''
                    display_tracks(tft,current_track,next_track)

        if pYSw_old != pYSw.value():
            pYSw_old = pYSw.value()
            if pYSw_old:
                print("Year UP")
            else:
                # cycle through Today In History (once we know what today is!)
                print("Year DOWN")

        if pMSw_old != pMSw.value():
            pMSw_old = pMSw.value()
            if pMSw_old:
                print("Month UP")
            else:
                print("Month DOWN")

        if pDSw_old != pDSw.value():
            pDSw_old = pDSw.value()
            if pDSw_old:
                print("Day UP")
            else:
                for date in sorted(col_dict["GratefulDead"].keys()):
                    if date > key_date:
                        key_date = set_date(date)
                        break
                print("Day DOWN")

        year_new = y.value()
        month_new = m.value()
        day_new = d.value()
        if (month_new in [4, 6, 9, 11]) and (day_new > 30):
            day_new = 30
        if (month_new == 2) and (day_new > 28):
            if year_new % 4 == 0:
                day_new = min(29, day_new)
                if (year_new % 100 == 0) and (year_new % 400 != 0):
                    day_new = min(28, day_new)
            else:
                day_new = min(28, day_new)

        date_new = f"{month_new:2d}-{day_new:2d}-{year_new%100:2d}"
        key_date = f"{year_new}-{month_new:02d}-{day_new:02d}"
        key_date = set_date(key_date)
        if year_old != year_new:
            year_old = year_new
            print("year =", year_new)

        if month_old != month_new:
            month_old = month_new
            print("month =", month_new)

        if day_old != day_new:
            day_old = day_new
            print("day =", day_new)

        if date_old != date_new:
            clear_bbox(tft,stage_date_bbox)
            tft.write(pfont_large, f"{date_new}", 0, 0, stage_date_color) # no need to clear this.
            # tft.text(font, f"{date_new}", 0, 0, stage_date_color, st7789.BLACK) # no need to clear this.
            date_old = date_new
            print(f"date = {date_new} or {key_date}")
            try:
                vcs = col_dict["GratefulDead"][f"{key_date}"]
                print(f'vcs is {vcs}')
                clear_bbox(tft, venue_bbox)
                #tft.draw(romant_font, f"{vcs}", 0, 40, stage_date_color, 0.65)
                tft.write(pfont_small, f"{vcs}", venue_bbox.x0, venue_bbox.y0, stage_date_color) # no need to clear this.
            except KeyError:
                clear_bbox(tft, venue_bbox)
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
    
    connect_wifi()
    print(f"Loaded collections {col_dict.keys()}")

    main_loop(col_dict)

main()
