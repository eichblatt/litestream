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

import gc
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

API = "https://gratefuldeadtimemachine.com"  # google cloud version mapped to here
CLOUD_PATH = "https://storage.googleapis.com/spertilo-data"


def factory_reset():
    print("Reseting to factory settings")
    if not utils.path_exists("/.factory_lib"):
        print("Unable to perform factory reset")
        return
    utils.remove_dir("./lib")
    utils.copy_dir("./factory_lib", "./lib")
    return


def configure_wifi():
    print("Configuring Wifi")
    choices = ["Remove Wifi", "Cancel"]
    choice = utils.select_option("Year/Select", choices)
    print(f"configure_wifi: chose {choice}")
    if choice == "Remove Wifi":
        utils.remove_wifi_cred()
    utils.disconnect_wifi()
    time.sleep(2)
    wifi = utils.connect_wifi()
    return wifi


def test_update():
    tm.tft.fill_rect(0, 0, 160, 128, st7789.BLACK)
    yellow_color = st7789.color565(255, 255, 0)
    red_color = st7789.color565(255, 0, 0)
    pSelect_old = True
    pStop_old = True
    update_code = False

    try:
        import livemusic

        wifi = utils.connect_wifi()
        livemusic.test_update()
    except Exception as e:
        print(f"UpdateException {e}")
        return False

    tm.clear_screen()
    tm.tft.write(pfont_large, "Welcome..", 0, 0, red_color)
    tm.tft.write(pfont_med, "Press ", 0, 30, yellow_color)
    tm.tft.write(pfont_med, "Select", 0, 60, yellow_color)
    tm.tft.write(pfont_med, "Button", 0, 90, yellow_color)

    start_time = time.ticks_ms()
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


def _collection_names():
    tm.write("Getting all\ncollection\nnames", font=pfont_small)
    all_collection_names_dict = {}
    api_request = f"{API}/all_collection_names/"
    cloud_url = f"{CLOUD_PATH}/sundry/etree_collection_names.json"
    all_collection_names_dict = {"Phishin Archive": ["Phish"]}
    resp = None
    try:
        gc.collect()
        resp = requests.get(cloud_url)
        if resp.status_code == 200:
            print(f"Downloaded collections names from {cloud_url}")
            colls = resp.json()["items"]
            all_collection_names_dict["Internet Archive"] = colls
        else:
            print(f"API request is {api_request}")
            resp = requests.get(api_request).json()
            all_collection_names_dict = resp["collection_names"]
    except Exception as e:
        print("Exception when loading collnames {e}")
    finally:
        if resp is not None:
            resp.close()
    return all_collection_names_dict


def configure_collections():
    choices = ["Add Collection", "Remove Collection", "Cancel"]
    choice = utils.select_option("Year/Select", choices)
    print(f"configure_collection: chose to {choice}")

    if choice == "Cancel":
        return

    collection_list = utils.get_collection_list()

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
            choice2 = utils.select_option("Year/Select", choices)
            if choice2 == "Finished":
                keepGoing = False

            utils.set_collection_list(collection_list)

    elif choice == "Remove Collection":
        keepGoing = True
        while keepGoing & (len(collection_list) > 0):
            coll_to_remove = utils.select_option("Year/Select", collection_list + ["_CANCEL"])
            collection_list = [x for x in collection_list if not x == coll_to_remove]
            choices = ["Remove Another", "Finished"]
            choice2 = utils.select_option("Year/Select", choices)
            if choice2 == "Finished":
                keepGoing = False
            utils.set_collection_list(collection_list)

    return


def add_collection(all_collections):
    collection_list = utils.get_collection_list()

    matching = [x for x in all_collections if not x in collection_list]
    n_matching = len(matching)

    selected_chars = ""
    while n_matching > 20:
        m2 = f"{n_matching} Matching"
        print(m2)
        selected_chars = utils.select_chars("Spell desired\nCollection", message2=m2, already=selected_chars)
        matching = [x for x in matching if selected_chars.lower() in x.lower()]
        n_matching = len(matching)

    print(f"Matching is {matching}")
    choice = "_CANCEL"
    if n_matching > 0:
        choice = utils.select_option("Choose coll to add", matching + ["_CANCEL"])

    return choice


def update_code():
    print("Updating code")
    wifi = utils.connect_wifi()
    if not wifi.isconnected():
        print("Error -- not connected to wifi")
        return
    yellow_color = st7789.color565(255, 255, 0)
    red_color = st7789.color565(255, 0, 0)
    tm.clear_screen()
    tm.tft.write(pfont_med, "Updating", 0, 40, yellow_color)
    tm.tft.write(pfont_med, " code", 0, 70, red_color)

    try:
        base_url = "github:eichblatt/litestream/timemachine/package.json"
        version = "releases" if not utils.path_exists("/.is_dev_box") else "dev"
        target = "test_download"
        print(f"Installing from {base_url}, version {version}, target {target}")
        mip.install(base_url, version=version, target=target)
        print("rebooting")
        machine.reset()
    except Exception as e:
        print(f"{e}\nFailed to download or save livemusic.py Not updating!!")
        return

    print("We should update livemusic.py")


def update_firmware():
    print("Updating firmware -- This will reboot")

    yellow_color = st7789.color565(255, 255, 0)
    red_color = st7789.color565(255, 0, 0)
    tm.clear_screen()
    tm.tft.write(pfont_med, "Updating", 0, 50, yellow_color)
    tm.tft.write(pfont_med, " Firmware", 0, 80, red_color)

    current_partition = utils.get_current_partition_name()
    print(f"The current partition is {current_partition}")
    status = utils.update_firmware()

    if status == 0:
        machine.reset()


def reconfigure():
    tm.tft.on()
    print("Reconfiguring")
    tm.tft.fill_rect(0, 90, 160, 30, st7789.BLACK)
    time.sleep(1)
    choice = utils.select_option(
        "Reconfigure",
        [
            "Collections",
            "Update Code",
            "Update Firmware",
            "Wifi",
            "Reboot",
            "Test Buttons",
            "Calibrate Knobs",
            "Calibrate Screen",
            "FactoryReset",
            "Debug",
        ],
    )
    if choice == "Collections":
        configure_collections()
    elif choice == "Wifi":
        wifi = configure_wifi()
    elif choice == "Calibrate Knobs":
        tm.calibrate_knobs()
    elif choice == "Test Buttons":
        tm.self_test()
    elif choice == "Update Code":
        update_code()
    elif choice == "Update Firmware":
        update_firmware()
    elif choice == "FactoryReset":
        factory_reset()
    elif choice == "Reboot":
        machine.reset()
    elif choice == "Calibrate Screen":
        tm.calibrate_screen(force=True)
    return choice


def basic_main():
    """
    This script will update livemusic.py if rewind button pressed within 2 seconds.
    """
    print("in basic_main")

    start_time = time.ticks_ms()
    pSelect_old = True
    pStop_old = True
    configure = False
    tm.calibrate_screen()
    tm.clear_screen()
    yellow_color = st7789.color565(255, 255, 0)
    red_color = st7789.color565(255, 0, 0)
    tm.tft.write(pfont_large, "Welcome..", 0, 0, red_color)
    tm.tft.write(pfont_med, "Time ", 0, 30, yellow_color)
    tm.tft.write(pfont_med, "Machine", 0, 55, yellow_color)
    software_version = utils.get_software_version()
    tm.tft.write(pfont_med, f"{software_version}", 0, 80, yellow_color)
    version_strings = sys.version.split(" ")
    uversion = f"{version_strings[2][:7]} {version_strings[4].replace('-','')}"
    tm.tft.write(pfont_small, f"{uversion}", 0, 105, st7789.WHITE)
    print(f"firmware version: {uversion}. Software version {software_version}")

    wifi = utils.connect_wifi()
    if not utils.path_exists("/.knob_sense"):
        print("knob sense not present")
        tm.self_test()
        tm.calibrate_knobs()
    if configure:
        reconfigure()
    dt = utils.set_datetime()
    if dt is not None:
        print(f"Date set to {dt}")
        # tm.tft.write(pfont_med, f"{dt[0]}-{dt[1]:02d}-{dt[2]:02d}", 0, 100, yellow_color)
    tm.clear_screen()
    return wifi


def run_livemusic():
    import livemusic

    utils.mark_partition()  # If we make it this far, the firmware is good.
    while True:
        livemusic.run()
        choice = reconfigure()
        if choice == "Debug":
            break


# basic_main()
