# Display driver: https://github.com/russhughes/st7789_mpy
import json
import os
import re
import time
import network
import time
from mrequests import mrequests as requests

import machine
import st7789
import fonts.DejaVu_20x as date_font
import fonts.DejaVu_33 as large_font
import fonts.NotoSans_18 as pfont_small
import fonts.NotoSans_24 as pfont_med
import fonts.NotoSans_32 as pfont_large
import fonts.romanc as roman_font
import fonts.romant as romant_font
from machine import SPI, Pin
from rotary_irq_esp import RotaryIRQ
import network

import board as tm


machine.freq(240_000_000)
API = 'http://westmain:5000' # westmain
#API = 'http://192.168.1.235:5000' # westmain
#API = 'http://deadstreamv3:5000'


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

def clear_bbox(bbox):
    tm.tft.fill_rect(bbox.x0, bbox.y0, bbox.width, bbox.height, st7789.BLACK)

def clear_area(x, y, width, height):
    tm.tft.fill_rect(x, y, width, height, st7789.BLACK)


def clear_screen():
    clear_area(0, 0, 160, 128)

def select_option(message, choices):
    pSelect_old = True
    tm.y._value = tm.y._min_val
    tm.d._value = tm.d._min_val
    step = step_old = 0
    text_height = 16
    choice = ""
    first_time = True
    clear_screen()
    select_bbox = Bbox(0,20,160,128)
    tm.tft.write(pfont_small, f"{message}", 0, 0, tracklist_color)
    while pSelect_old == tm.pSelect.value():
        step = (tm.y.value() - tm.y._min_val)% len(choices) 
        if (step != step_old) or first_time: 
            i = j = 0
            first_time = False
            step_old = step
            clear_bbox(select_bbox)

            for i,s in enumerate(range(max(0,step-2), step)):
                tm.tft.write(pfont_small, choices[s], select_bbox.x0, select_bbox.y0 + text_height*i, tracklist_color)

            text = ">" + choices[step]
            tm.tft.write(pfont_small, text, select_bbox.x0, select_bbox.y0 + text_height*(i+1), st7789.RED)

            for j,s in enumerate(range(step+1,min(step+5,len(choices)))):
                tm.tft.write(pfont_small, choices[s], select_bbox.x0, select_bbox.y0 + text_height*(i+j+2), tracklist_color)
            # print(f"step is {step}. Text is {text}")
        time.sleep(0.2)
    choice = choices[step]
    # print(f"step is now {step}. Choice: {choice}")
    time.sleep(0.6)
    return choices[step]        
        
def select_chars(message, message2="So Far"):
    charset = '0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ!"#$%&\'()*+,-./:;<=>?@[\\]^_`{|}~ \t\n\r\x0b\x0c'
    message = message.split("\n")
    pSelect_old = pStop_old = True
    tm.y._value = tm.y._min_val
    tm.d._value = tm.d._min_val
    tm.y._max_val = tm.y._max_val + 100
    step = step_old = 0
    text_height = 18
    screen_width = 16
    clear_screen()
    y_origin = len(message) * text_height

    select_bbox = Bbox(0,y_origin,160,y_origin + text_height)
    selected_bbox = Bbox(0,y_origin + text_height,160,128)

    for i,msg in enumerate(message):
        tm.tft.write(pfont_small, f"{msg}", 0, i*text_height, stage_date_color)

    selected = ""
    text = "DEL"
    first_time = True
    finished = False

    while not finished:
        print(f"pStop_old {pStop_old}, pStop: {tm.pStop.value()}")
        while pSelect_old == tm.pSelect.value():
            if pStop_old != tm.pStop.value():
                finished = True
                break
            step = (tm.y.value() - tm.y._min_val) % (len(charset) + 1) 
            if (step != step_old) or first_time: 
                cursor = 0
                first_time = False
                step_old = step
                clear_bbox(select_bbox)

                # Write the Delete character
                cursor += tm.tft.write(pfont_small, "DEL", select_bbox.x0, select_bbox.y0, st7789.WHITE if step!=0 else st7789.RED)

                text = charset[max(0,step - 5) : -1 + step]
                for x in charset[94:]:
                    text = text.replace(x,".")   # Should be "\u25A1", but I don't think we have the font for this yet.

                # Write the characters before the cursor
                cursor += tm.tft.write(pfont_small, text, select_bbox.x0 + cursor, select_bbox.y0, tracklist_color)
                
                # Write the character AT the cursor
                text = charset[-1 + min(step,len(charset))]
                if text == " ":
                    text = "SPC"
                elif text == "\t":
                    text = "\\t"
                elif text == "\n":
                    text = "\\n"
                elif text == "\r":
                    text = "\\r"
                elif text == "\x0b":
                    text = "\\v"
                elif text == "\x0c":
                    text = "\\f"

                cursor += tm.tft.write(pfont_small, text, select_bbox.x0 + cursor, select_bbox.y0, st7789.RED)

                # Write the characters after the cursor
                text = charset[step:min(-1+step+screen_width,len(charset))]
                for x in charset[94:]:
                    text = text.replace(x, ".")
                tm.tft.write(pfont_small, text, select_bbox.x0+cursor, select_bbox.y0, tracklist_color)

                # print(f"step is {step}. Text is {text}")
            time.sleep(0.2)
        time.sleep(0.2) # de-jitter
        if not finished:
            if step == 0:
                selected = selected[:-1]
            else:
                choice = charset[step-1] # -1 for the delete character.
                # print(f"step is now {step}. Choice: {choice}")
                selected = selected + choice
            clear_bbox(selected_bbox)
            tm.tft.write(pfont_small, selected, selected_bbox.x0, selected_bbox.y0, st7789.RED)
    tm.y._max_val = tm.y._max_val - 100
    print(f"stop pressed. selected is: {selected}")
    time.sleep(0.3)
    return selected
 
    

def get_wifi_cred(wifi):
    choices = wifi.scan()  # Scan for available access points
    choices = [x[0].decode().replace('"', "") for x in choices]
    choices = [x for x in choices if x != '']
    choices = sorted(set(choices),key=choices.index)
    print(f"get_wifi_cred. Choices are {choices}") 
    choice = select_option("Select Wifi", choices)
    passkey = select_chars("Input Passkey for {choice}\nSelect. Stop to End\n ")
    return {'name':choice,"passkey":passkey}

def connect_wifi():
    wifi = network.WLAN(network.STA_IF)
    wifi.active(True)
    wifi_cred_path = 'wifi_cred.json'
    # sta_if.scan()  # Scan for available access points

    if path_exists(wifi_cred_path):
        wifi_cred = json.load(open(wifi_cred_path, "r"))
    else:
        wifi_cred = get_wifi_cred(wifi)
    attempts = 0
    max_attempts = 5
    while (not wifi.isconnected()) & (attempts < max_attempts):
        print("Attempting to connect to network")
        wifi.connect(wifi_cred["name"], wifi_cred["passkey"])
        attempts += 1
        time.sleep(2)
    if wifi.isconnected():
        with open(wifi_cred_path,'w') as f:
            json.dump(wifi_cred,f)
    return wifi

print("Starting...")


def set_date(date):
    tm.y._value = int(date[:4])
    tm.m._value = int(date[5:7])
    tm.d._value = int(date[8:10])
    key_date = f"{tm.y.value()}-{tm.m.value():02d}-{tm.d.value():02d}"
    return key_date


def best_tape(collection, key_date):
    pass


def select_date(collections, key_date, ntape=0):
    print(f"selecting show from {key_date}")
    collstring = ",".join(collections)
    api_request = f"{API}/tracklist/{key_date}?collections={collstring}&ntape={ntape}" 
    print(f"API request is {api_request}")
    resp = requests.get(api_request).json()
    collection = resp['collection']
    tracklist = resp['tracklist']
    api_request = f"{API}/urls/{key_date}?collections={collstring}&ntape={ntape}" 
    resp = requests.get(api_request).json()
    urls = resp['urls']
    print(f"URLs: {urls}")
    return collection, tracklist, urls

def get_tape_ids(collections,key_date):
    print(f"getting tape_ids from {key_date}")
    collstring = ",".join(collections)
    api_request = f"{API}/tape_ids/{key_date}?collections={collstring}"
    print(f"API request is {api_request}")
    tape_ids = requests.get(api_request).json()
    return tape_ids
     

stage_date_bbox = Bbox(0,0,160,32)
nshows_bbox = Bbox(150,32,160,48)
venue_bbox = Bbox(0,32,160,32+20)
artist_bbox = Bbox(0,52,160,52+20)
tracklist_bbox = Bbox(0,70, 160, 110)
selected_date_bbox = Bbox(15,113,145,128)
playpause_bbox = Bbox(145 ,113, 160, 128)

stage_date_color = st7789.color565(255, 255, 0)
yellow_color = st7789.color565(255, 255, 0)
tracklist_color = st7789.color565(0, 255, 255)
play_color = st7789.color565(255, 0, 0)
nshows_color = st7789.color565(0, 100, 255)

def display_tracks(current_track_name,next_track_name):
    clear_bbox(tracklist_bbox)
    tm.tft.write(pfont_small, f"{current_track_name}", tracklist_bbox.x0, tracklist_bbox.y0, tracklist_color)
    tm.tft.write(pfont_small, f"{next_track_name}", tracklist_bbox.x0, tracklist_bbox.center()[1], tracklist_color)
    return 

def main_loop(coll_dict):
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
    key_date = set_date('1989-08-13')
    selected_date = key_date
    playstate = 0
    collection = "GratefulDead"; tracklist = []; urls = []
    collections = list(coll_dict.keys())
    current_collection = ''
    current_track_index = -1
    current_track_name = next_track_name = '' 
    select_press_time = 0
    ntape = 0
    valid_dates = set()
    for c in collections:
        valid_dates = valid_dates | set(list(coll_dict[c].keys()))
    del c
    valid_dates = list(sorted(valid_dates))
    clear_screen()

    while True:
        nshows = 0
        
        if pPower_old != tm.pPower.value():
            pPower_old = tm.pPower.value()
            tm.pLED.value(PowerLED)
            tm.tft.off() if not PowerLED else tm.tft.on()
            if pPower_old:
                # tm.tft.fill_circle(5 + 8, 108 + 8, 8, st7789.BLUE)
                print("Power UP")
            else:
                PowerLED = not PowerLED
                # tm.tft.fill_circle(5 + 8, 108 + 8, 8, st7789.WHITE)
                print("Power DOWN")

        if pSelect_old != tm.pSelect.value():
            pSelect_old = tm.pSelect.value()
            if pSelect_old:
                if key_date in valid_dates:
                    current_track_index = 0
                    collection, tracklist, urls = select_date(coll_dict.keys(),key_date, ntape)
                    vcs = coll_dict[collection][key_date]
                    ntape = 0
                    current_collection = collection
                    current_track_name = tracklist[current_track_index]
                    next_track_name = tracklist[current_track_index+1] if len(tracklist)> current_track_index else ''
                    display_tracks(current_track_name,next_track_name)

                    selected_date = key_date
                    clear_bbox(venue_bbox)
                    tm.tft.write(pfont_small, f"{vcs}", venue_bbox.x0, venue_bbox.y0, stage_date_color) # no need to clear this.
                    clear_bbox(selected_date_bbox)
                    tm.tft.write(date_font, f"{int(selected_date[5:7]):2d}-{selected_date[8:10]}-{selected_date[:4]}",
                              selected_date_bbox.x0,selected_date_bbox.y0)
                print("Select UP")
            else:
                select_press_time = time.ticks_ms()
                print("Select DOWN")

        if not tm.pSelect.value():
            if (time.ticks_ms()-select_press_time) > 1_000:
                select_press_time = time.ticks_ms()
                if ntape == 0:
                    tape_ids = get_tape_ids(coll_dict.keys(),key_date)
                ntape = (ntape + 1)%len(tape_ids)
                clear_bbox(artist_bbox)
                tm.tft.write(pfont_small, f"{tape_ids[ntape][0]}", artist_bbox.x0, artist_bbox.y0, stage_date_color) 
                #vcs = coll_dict[tape_ids[ntape][0]][key_date]
                clear_bbox(venue_bbox)
                display_str = re.sub(r"\d\d\d\d-\d\d-\d\d\.*","~", tape_ids[ntape][1])
                display_str = re.sub(r"\d\d-\d\d-\d\d\.*","~", display_str)
                print(f"display string is {display_str}")
                if len(display_str) > 18:
                    display_str = display_str[:11] + display_str[-6:]
                tm.tft.write(pfont_small, f"{display_str}", venue_bbox.x0, venue_bbox.y0, stage_date_color) # no need to clear this.
                print(f"Select LONG_PRESS values is {tm.pSelect.value()}. ntape = {ntape}")

        
        if pPlayPause_old != tm.pPlayPause.value():
            pPlayPause_old = tm.pPlayPause.value()
            if pPlayPause_old:
                print("PlayPause UP")
            else:
                playstate = 1 if playstate == 0 else 0
                clear_bbox(playpause_bbox)
                if playstate > 0:
                    print(f"Playing URL {urls[current_track_index]}")
                    tm.tft.fill_polygon(tm.PlayPoly, playpause_bbox.x0, playpause_bbox.y0 , play_color)
                else:
                    print(f"Pausing URL {urls[current_track_index]}")
                    tm.tft.fill_polygon(tm.PausePoly, playpause_bbox.x0, playpause_bbox.y0 , st7789.WHITE)
                print("PlayPause DOWN")

        if pStop_old != tm.pStop.value():
            pStop_old = tm.pStop.value()
            if pStop_old:
                print("Stop UP")
            else:
                print("Stop DOWN")

        if pRewind_old != tm.pRewind.value():
            pRewind_old = tm.pRewind.value()
            if pRewind_old:
                # tm.tft.fill_polygon(tm.RewPoly, 30, 108, st7789.BLUE)
                print("Rewind UP")
            else:
                # tm.tft.fill_polygon(tm.RewPoly, 30, 108, st7789.WHITE)
                print("Rewind DOWN")
                if current_track_index <= 0:
                    pass
                elif current_track_index>=0:
                    current_track_index += -1
                    current_track_name = tracklist[current_track_index]
                    next_track_name = tracklist[current_track_index+1] if len(tracklist) > current_track_index + 1 else ''
                    display_tracks(current_track_name,next_track_name)




        if pFFwd_old != tm.pFFwd.value():
            pFFwd_old = tm.pFFwd.value()
            if pFFwd_old:
                # tm.tft.fill_polygon(tm.FFPoly, 80, 108, st7789.BLUE)
                print("FFwd UP")
            else:
                # tm.tft.fill_polygon(tm.FFPoly, 80, 108, st7789.WHITE)
                print("FFwd DOWN")
                if current_track_index >= len(tracklist):
                    pass
                elif current_track_index>=0:
                    current_track_index += 1 if len(tracklist)> current_track_index + 1 else 0
                    current_track_name = tracklist[current_track_index]
                    next_track_name = tracklist[current_track_index+1] if len(tracklist) > current_track_index + 1 else ''
                    display_tracks(current_track_name,next_track_name)

        if pYSw_old != tm.pYSw.value():
            pYSw_old = tm.pYSw.value()
            if pYSw_old:
                print("Year UP")
            else:
                # cycle through Today In History (once we know what today is!)
                print("Year DOWN")

        if pMSw_old != tm.pMSw.value():
            pMSw_old = tm.pMSw.value()
            if pMSw_old:
                print("Month UP")
            else:
                print("Month DOWN")

        if pDSw_old != tm.pDSw.value():
            pDSw_old = tm.pDSw.value()
            if pDSw_old:
                print("Day UP")
            else:
                for date in valid_dates:
                    if date > key_date:
                        key_date = set_date(date)
                        break
                print("Day DOWN")

        year_new = tm.y.value()
        month_new = tm.m.value()
        day_new = tm.d.value()
        if (month_new in [4, 6, 9, 11]) and (day_new > 30):
            day_new = 30
        if (month_new == 2) and (day_new > 28):
            if year_new % 4 == 0:
                day_new = min(29, day_new)
                if (year_new % 100 == 0) and (year_new % 400 != 0):
                    day_new = min(28, day_new)
            else:
                day_new = min(28, day_new)

        date_new = f"{month_new:2d}-{day_new:02d}-{year_new%100:02d}"
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
            clear_bbox(stage_date_bbox)
            tm.tft.write(large_font, f"{date_new}", 0, 0, stage_date_color) # no need to clear this.
            # tm.tft.text(font, f"{date_new}", 0, 0, stage_date_color, st7789.BLACK) # no need to clear this.
            date_old = date_new
            print(f"date = {date_new} or {key_date}")
            try:
                if key_date in valid_dates:
                    for c in list(coll_dict.keys()):
                        if key_date in coll_dict[c].keys():
                            nshows += 1
                            collection = c
                            vcs = coll_dict[collection][f"{key_date}"]
                            clear_bbox(artist_bbox)
                            tm.tft.write(pfont_small, f"{collection}", artist_bbox.x0, artist_bbox.y0, stage_date_color) 
                else:
                    vcs = ''
                    collection = ''
                    clear_bbox(artist_bbox)
                    tm.tft.write(pfont_small, f"{current_collection}", artist_bbox.x0, artist_bbox.y0, tracklist_color) 
                    display_tracks(current_track_name,next_track_name)
                print(f'vcs is {vcs}')
                clear_bbox(venue_bbox)
                tm.tft.write(pfont_small, f"{vcs}", venue_bbox.x0, venue_bbox.y0, stage_date_color) # no need to clear this.
                clear_bbox(nshows_bbox)
                if nshows > 1:
                    tm.tft.write(pfont_small, f"{nshows}", nshows_bbox.x0, nshows_bbox.y0, nshows_color) # no need to clear this.
            except KeyError:
                clear_bbox(venue_bbox)
                clear_bbox(artist_bbox)
                tm.tft.write(pfont_small, f"{current_collection}", artist_bbox.x0, artist_bbox.y0, stage_date_color) 
                display_tracks(current_track_name,next_track_name)
                pass
        # time.sleep_ms(50)



# --------------------------------------------------
# These functions belong in a utils library
# --------------------------------------------------
def is_dir(path):
    try:
        return (os.stat(path)[0] & 0x4000) != 0
    except OSError:
        return False


def path_exists(path):
    try:
        os.stat(path)
        return True
    except OSError:
        return False


#  ---------------------------------   End utils library
def add_vcs(coll):
    ids_path = f"metadata/{coll}_vcs.json"
    print(f"Loading collection {coll} from {ids_path}")
    api_request = f"{API}/vcs/{coll}" 
    resp = requests.get(api_request).json()
    vcs = resp[coll]
    print(f"vcs: {vcs}")
    with open(ids_path,'w') as f:
        json.dump(vcs,f)
    

def load_vcs(coll):
    ids_path = f"metadata/{coll}_vcs.json"
    if not path_exists(ids_path):
        add_vcs(coll)
    print(f"Loading collection {coll} from {ids_path}")
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
    tm.tft.write(large_font, "Time ", 0, 0, yellow_color)
    tm.tft.write(large_font, "Machine", 0, 30, yellow_color)
    tm.tft.write(large_font, "Loading", 0, 90, yellow_color)

    collection_list_path = 'collection_list.json'
    if path_exists(collection_list_path):
        collection_list = json.load(open(collection_list_path, "r"))
    else:
        collection_list = ['GratefulDead']
        with open(collection_list_path,'w') as f:
            json.dump(collection_list,f)

    coll_dict = {}
    min_year = tm.y._min_val
    max_year = tm.y._max_val
    for coll in collection_list:
        coll_dict[coll] = load_vcs(coll)
        coll_dates = coll_dict[coll].keys()
        min_year = min(int(min(coll_dates)[:4]),min_year)
        max_year = max(int(max(coll_dates)[:4]),max_year)
        tm.y._min_val = min_year
        tm.y._max_val = max_year

    wifi = connect_wifi()
    ip_address = wifi.ifconfig()[0]
    tm.tft.write(pfont_med, ip_address, 0, 60, st7789.WHITE)

    print(f"Loaded collections {coll_dict.keys()}")

    main_loop(coll_dict)

main()
