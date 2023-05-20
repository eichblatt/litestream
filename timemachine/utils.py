import json
import network
import os
import st7789
import time

import fonts.NotoSans_18 as pfont_small

from mrequests import mrequests as requests

import board as tm

def reload(mod):
    import sys
    z = __import__(mod)
    del z
    del sys.modules[mod]
    return __import__(mod)

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


def clear_bbox(bbox):
    tm.tft.fill_rect(bbox.x0, bbox.y0, bbox.width, bbox.height, st7789.BLACK)

def clear_area(x, y, width, height):
    tm.tft.fill_rect(x, y, width, height, st7789.BLACK)

def clear_screen():
    clear_area(0, 0, 160, 128)

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
    tm.y._max_val = tm.y._max_val + 100
    tm.y._value = int((tm.y._min_val + tm.y._max_val)/2)
    tm.d._value = int((tm.d._min_val + tm.d._max_val)/2)

    step = step_old = 0
    text_height = 18
    screen_width = 16
    clear_screen()
    y_origin = len(message) * text_height

    select_bbox = Bbox(0,y_origin,160,y_origin + text_height)
    selected_bbox = Bbox(0,y_origin + text_height,160,128)

    def decade_value(tens, ones, bounds, start_vals=(tm.d._value,tm.y._value)):
        value = ((tens - start_vals[0]) * 10 + (ones - start_vals[1])) 
        value = max(value,bounds[0]) % bounds[1] 
        print(f'decade value {value}')

        if value == 0:
            tm.d._value = start_vals[0]
            tm.y._value = start_vals[1]
        return value

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
            # step = (tm.y.value() - tm.y._min_val) % (len(charset) + 1) 
            step = decade_value(tm.d.value(), tm.y.value(), (0,len(charset) + 1))
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
    clear_screen()
    tm.tft.write(pfont_small, "Selected:", 0, 0, stage_date_color)
    tm.tft.write(pfont_small, selected, selected_bbox.x0, text_height+5 , st7789.RED)
    tm.tft.write(pfont_small, "Connecting...", selected_bbox.x0, selected_bbox.y0, stage_date_color)
    time.sleep(0.3)
    return selected
 
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
    wifi.config(pm=network.WLAN.PM_NONE)
    wifi_cred_path = 'wifi_cred.json'
    # sta_if.scan()  # Scan for available access points

    if path_exists(wifi_cred_path):
        wifi_cred = json.load(open(wifi_cred_path, "r"))
    else:
        wifi_cred = get_wifi_cred(wifi)
        with open(wifi_cred_path,'w') as f:
            json.dump(wifi_cred,f)

    attempts = 0
    max_attempts = 5
    while (not wifi.isconnected()) & (attempts <= max_attempts):
        print("Attempting to connect to network")
        try:
            wifi.connect(wifi_cred["name"], wifi_cred["passkey"])
        except OSError:
            pass
        attempts += 1
        time.sleep(2)
    if not wifi.isconnected():
        tm.tft.write(pfont_small, f"failed. Retrying", 0, 90, st7789.WHITE)
        with open(f'{wifi_cred_path}.bak','w') as f:
            json.dump(wifi_cred,f)
        os.remove(wifi_cred_path)
        return connect_wifi()
    else:
        return wifi
 