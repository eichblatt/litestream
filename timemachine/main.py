import json
import sys
import os
import time

import machine
import st7789
import fonts.date_font as date_font
import fonts.NotoSans_24 as pfont_med
import fonts.NotoSans_32 as pfont_large
from machine import SPI, Pin
from mrequests import mrequests as requests
from rotary_irq_esp import RotaryIRQ
import mip
import network

import board as tm
import utils

COLLECTION_LIST_PATH = 'collection_list.json'
API = 'https://msdocs-python-webapp-quickstart-sle.azurewebsites.net'


def copy_file(src, dest):
    print(f"Copying {src} to {dest}")
    f_in = open(src,'r')
    f_out = open(dest,'w')
    for line in f_in.readlines():
        f_out.write(line)
    f_in.close()
    f_out.close()
   
def connect_wifi():
    utils.clear_screen()
    yellow_color = st7789.color565(255, 255, 0)
    tm.tft.write(pfont_med, "Connecting", 0, 0, yellow_color)
    tm.tft.write(pfont_med, "WiFi...", 0, 30, yellow_color)
 
    wifi = utils.connect_wifi()
    if not wifi.isconnected():
        print("Wifi did not connect!!!")
        raise Exception("Wifi Failed to Connect")
    ip_address = wifi.ifconfig()[0]
    tm.tft.write(date_font, ip_address, 0, 60, st7789.WHITE) 
    return wifi

def _collection_names():
    all_collection_names_dict = {}
    api_request = f"{API}/all_collection_names/" 
    print(f"API request is {api_request}")
    resp = requests.get(api_request).json()
    all_collection_names_dict = resp['collection_names']
    return all_collection_names_dict

def choose_collections(): 
    collection_list = []
    all_collections = []
    if utils.path_exists(COLLECTION_LIST_PATH):
        collection_list = json.load(open(COLLECTION_LIST_PATH, "r"))
    all_collections_dict = _collection_names()
    for archive in all_collections_dict.keys():
        all_collections = all_collections + all_collections_dict[archive]
        
    matching = [x for x in all_collections if not x in collection_list]
    n_matching = len(matching)

    selected_chars = ""
    while n_matching > 20:
        selected_chars = utils.select_chars("Spell desired Collection", message2=f"{n_matching} Matching",already=selected_chars,singleLetter=True)
        matching = [x for x in matching if selected_chars in x]
        n_matching = len(matching)

    if n_matching > 0:
        choice = utils.select_option("Choose coll to add",matching)

    return choice
 
def basic_main():
    """
    This script will update livemusic.py if rewind button pressed within 2 seconds.
    """
    print("in basic_main")
    tm.tft.fill_rect(0, 0, 160, 128, st7789.BLACK)
    yellow_color = st7789.color565(255, 255, 0)
    red_color = st7789.color565(255, 0, 0)
    tm.tft.write(pfont_large, "Welcome..", 0, 0, red_color)
    tm.tft.write(pfont_med, "Time ", 0, 30, yellow_color)
    tm.tft.write(pfont_med, "Machine", 0, 60, yellow_color)
    tm.tft.write(pfont_med, "Loading", 0, 90, yellow_color)

    start_time = time.ticks_ms()
    pRewind_old = True
    pSelect_old = True
    pStop_old = True
    update_code = False
    reconfigure = False

    while time.ticks_ms() < (start_time + 5000):

        if pSelect_old != tm.pSelect.value():
            pSelect_old = tm.pSelect.value()
            reconfigure = True
            print(f"{time.ticks_ms()} Select button Pressed!!")
            break

        if pStop_old != tm.pStop.value():
            pStop_old = tm.pStop.value()
            print(f"{time.ticks_ms()} Stop button Pressed -- bailing!!")
            return

        if pRewind_old != tm.pRewind.value():
            pRewind_old = tm.pRewind.value()
            update_code = True
            print(f"{time.ticks_ms()} Rewind button Pressed!!")
            break

    if update_code:
        print('Updating code')
        tm.tft.fill_rect(0, 90, 160, 30, st7789.BLACK)
        tm.tft.write(pfont_med, "Updating", 0, 90, yellow_color)

        try:
            wifi = connect_wifi()

            if not wifi.isconnected():
                raise RuntimeError("Wifi Not Connected -- not able to update code")
            tm.tft.write(pfont_med, "Updating", 0, 90, yellow_color)
            mip.install("github:eichblatt/litestream/timemachine/package.json", target="test_download")
            print("rebooting")
            machine.reset()
        except Exception as e:
            print(f"{e}\nFailed to download or save livemusic.py Not updating!!")
            return

        print("We should update livemusic.py")

    elif reconfigure:
        print('Reconfiguring')
        tm.tft.fill_rect(0, 90, 160, 30, st7789.BLACK)
        choice = utils.select_option("Reconfigure",["Collections","Wifi","Factory Reset"])
        if choice == "Collections":
            choose_collections() 
    time.sleep(3)



def test_update():
    tm.tft.fill_rect(0, 0, 160, 128, st7789.BLACK)
    yellow_color = st7789.color565(255, 255, 0)
    red_color = st7789.color565(255, 0, 0)
    tm.tft.write(pfont_large, "Welcome..", 0, 0, red_color)
    tm.tft.write(pfont_med, "Press ", 0, 30, yellow_color)
    tm.tft.write(pfont_med, "Select", 0, 60, yellow_color)
    tm.tft.write(pfont_med, "Button", 0, 90, yellow_color)

    start_time = time.ticks_ms()
    pRewind_old = True
    pSelect_old = True
    pStop_old = True
    update_code = False

    while time.ticks_ms() < (start_time + 60_000):

        if pSelect_old != tm.pSelect.value():
            pSelect_old = tm.pSelect.value()
            update_code = True
            print(f"{time.ticks_ms()} Select button Pressed!!")
            break

        if pStop_old != tm.pStop.value():
            pStop_old = tm.pStop.value()
            print(f"{time.ticks_ms()} Stop button Pressed -- bailing!!")
            return

        if pRewind_old != tm.pRewind.value():
            pRewind_old = tm.pRewind.value()
            update_code = True
            print(f"{time.ticks_ms()} Rewind button Pressed!!")
            break

    tm.tft.fill_rect(0, 0, 160, 128, st7789.BLACK)
    tm.tft.write(pfont_large, "Welcome..", 0, 0, red_color)
    if update_code:
        tm.tft.write(pfont_med, "Updating ... ", 0, 30, yellow_color)
    else:
        tm.tft.write(pfont_med, "Not Updating", 0, 60, red_color)

    return update_code

def run_livemusic():
    try:
        print("Connecting Wifi")
        wifi = connect_wifi()
        print("Trying to run livemusic main")
        if 'livemusic' in sys.modules:
            utils.reload('livemusic')
            livemusic.run()
        else:
            import livemusic 
            livemusic.run()
    except Exception:
        print("livemusic.py is not running!!")


#basic_main()