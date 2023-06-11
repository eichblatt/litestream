import json
import sys
import os
import time

import machine
import st7789
import fonts.date_font as date_font
import fonts.NotoSans_18 as pfont_small
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
   
def factory_reset():
    print("Reseting to factory settings")
    utils.remove_dir('./lib')
    utils.copy_dir('./factory_lib','./lib')
    return 

def connect_wifi():
    yellow_color = st7789.color565(255, 255, 0)
    utils.write("Connecting\nWiFi..", color=yellow_color)
 
    wifi = utils.connect_wifi()
    if not wifi.isconnected():
        print("Wifi did not connect!!!")
        raise Exception("Wifi Failed to Connect")
    ip_address = wifi.ifconfig()[0]
    utils.write(ip_address, font=date_font, y=60, clear=False) 
    return wifi

def configure_wifi(): 
    print("Configuring Wifi")
    choices = ["Remove Wifi", "Cancel"]
    choice = utils.select_option("Year/Select",choices)
    print(f"configure_wifi: chose {choice}")
    if choice == "Remove Wifi":
        utils.remove_wifi_cred() 
    utils.disconnect_wifi()
    time.sleep(2)
    wifi = connect_wifi()
    return wifi

def _collection_names():
    utils.write("Getting all\ncollection\nnames", font=pfont_small)
    all_collection_names_dict = {}
    api_request = f"{API}/all_collection_names/"
    print(f"API request is {api_request}")
    resp = requests.get(api_request).json()
    all_collection_names_dict = resp['collection_names']
    return all_collection_names_dict

def configure_collections(): 
    choices = ["Add Collection","Remove Collection", "Cancel"]
    choice = utils.select_option("Year/Select",choices)
    print(f"configure_collection: chose to {choice}")

    if choice == "Cancel":
        return
    
    if utils.path_exists(COLLECTION_LIST_PATH):
        collection_list = json.load(open(COLLECTION_LIST_PATH, "r"))
    else:
        collection_list = []

    print(f"current collection_list is {collection_list}")
    if choice == "Add Collection":
        keepGoing = True
        all_collections = []
        all_collections_dict = _collection_names()
        for archive in all_collections_dict.keys():
            all_collections = all_collections + all_collections_dict[archive]
    
        while keepGoing:
            coll_to_add = add_collection(all_collections)
            if coll_to_add != "_CANCEL":
                collection_list.append(coll_to_add)
            choices = ["Add Another", "Finished"]
            choice2 = utils.select_option("Year/Select",choices)
            if choice2 == "Finished":
                keepGoing = False

            json.dump(collection_list,open(COLLECTION_LIST_PATH, "w"))

    elif (choice == "Remove Collection"):
        keepGoing = True
        while keepGoing & (len(collection_list)> 0):
            coll_to_remove = utils.select_option("Year/Select",collection_list + ["_CANCEL"])
            collection_list = [x for x in collection_list if not x==coll_to_remove]
            choices = ["Remove Another", "Finished"]
            choice2 = utils.select_option("Year/Select",choices)
            if choice2 == "Finished":
                keepGoing = False
            json.dump(collection_list,open(COLLECTION_LIST_PATH, "w"))

    print(f"Collection List set to {collection_list} written to {COLLECTION_LIST_PATH}")
    return 


def add_collection(all_collections): 
    collection_list = []
    if utils.path_exists(COLLECTION_LIST_PATH):
        collection_list = json.load(open(COLLECTION_LIST_PATH, "r"))
       
    matching = [x for x in all_collections if not x in collection_list]
    n_matching = len(matching)

    selected_chars = ""
    while n_matching > 20:
        m2 = f"{n_matching} Matching"
        print(m2)
        selected_chars = utils.select_chars("Spell desired\nCollection", message2=m2,already=selected_chars)
        matching = [x for x in matching if selected_chars.lower() in x.lower()]
        n_matching = len(matching)

    print(f"Matching is {matching}")
    if n_matching > 0:
        choice = utils.select_option("Choose coll to add",matching + ["_CANCEL"])

    return choice
        
def update_code():
    print('Updating code')
    yellow_color = st7789.color565(255, 255, 0)
    tm.tft.fill_rect(0, 90, 160, 30, st7789.BLACK)
    tm.tft.write(pfont_med, "Updating", 0, 90, yellow_color)

    try:
        tm.tft.write(pfont_med, "Updating", 0, 90, yellow_color)
        mip.install("github:eichblatt/litestream/timemachine/package.json", target="test_download")
        print("rebooting")
        machine.reset()
    except Exception as e:
        print(f"{e}\nFailed to download or save livemusic.py Not updating!!")
        return

    print("We should update livemusic.py")


 
def basic_main():
    """
    This script will update livemusic.py if rewind button pressed within 2 seconds.
    """
    print("in basic_main")

    utils.clear_screen()
    yellow_color = st7789.color565(255, 255, 0)
    red_color = st7789.color565(255, 0, 0)
    tm.tft.write(pfont_large, "Welcome..", 0, 0, red_color)
    tm.tft.write(pfont_med, "Time ", 0, 30, yellow_color)
    tm.tft.write(pfont_med, "Machine", 0, 60, yellow_color)
    tm.tft.write(pfont_med, "Loading", 0, 90, yellow_color)

    start_time = time.ticks_ms()
    pFFwd_old = True
    pSelect_old = True
    pStop_old = True
    update = False
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

        if pFFwd_old != tm.pFFwd.value():
            pFFwd_old = tm.pFFwd.value()
            update = True
            print(f"{time.ticks_ms()} FFwd button Pressed!!")
            break

    wifi = connect_wifi()
    if update:
        update_code()
    elif reconfigure:
        print('Reconfiguring')
        tm.tft.fill_rect(0, 90, 160, 30, st7789.BLACK)
        choice = utils.select_option("Reconfigure",["Collections","Wifi","Update Code","FactoryReset","Cancel"])
        if choice == "Collections":
            configure_collections()
        elif choice == "Wifi":
            wifi = configure_wifi()
        elif choice == "Update Code":
            update_code()
        elif choice == "FactoryReset":
            factory_reset()
    utils.clear_screen()
    tm.tft.write(pfont_med, "Updating", 0, 90, yellow_color)
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