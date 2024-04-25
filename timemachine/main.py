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
import os
import sys
import time

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
MAX_COLLECTIONS = 35


def factory_reset():
    print("Reseting to factory settings")
    if not utils.path_exists("/factory_lib"):
        print("Unable to perform factory reset")
        return
    utils.remove_dir("/test_download")
    utils.copy_dir("/factory_lib", "/test_download")  # as if we downloaded this
    utils.remove_wifi_cred()
    utils.remove_dir("/metadata")
    os.mkdir("/metadata")
    utils.remove_dir("/config")
    os.mkdir("/config")
    utils.reset()
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


def _datpiff_collection_names(first_char=""):
    if len(first_char) > 1:
        return []
    if first_char == "":
        filename = "top10.json"
    elif first_char in "#abcdefghijklmnopqrstuvwxyz":
        filename = f"bottom_{first_char}.json"
    else:
        filename = "bottom_#.json"

    url = f"https://storage.googleapis.com/spertilo-data/datpiff/{filename}"
    try:
        url = "https://storage.googleapis.com/spertilo-data/datpiff/top10.json"
        resp = requests.get(url)
        if resp.status_code != 200:
            raise Exception(f"error downloading from {url}")
        collection_names = resp.json()
    finally:
        resp.close()
    return collection_names


def configure_datpiff_collections():
    state = utils.load_state("datpiff")
    collection_list = state["artist_list"]

    if len(collection_list) >= MAX_COLLECTIONS:
        choices = ["Remove Artist", "Cancel"]
    elif len(collection_list) == 0:
        choices = ["Add Artist", "Cancel"]
    else:
        choices = ["Add Artist", "Remove Artist", "Cancel"]
    choice = utils.select_option("Year/Select", choices)
    utils.print_log(f"configure_collection: chose to {choice}")

    if choice == "Cancel":
        return

    utils.print_log(f"current collection_list is {collection_list}")
    if choice == "Add Artist":
        keepGoing = True
        reset_required = False
        all_collections = _datpiff_collection_names()

        choices = ["Artists >3 tapes", "All Artists"]
        choice = utils.select_option("Year/Select", choices)
        utils.print_log(f"configure_collection: chose to {choice}")
        if choice == "All Artists":
            colls_fn = _datpiff_collection_names
        else:
            colls_fn = None

        while keepGoing:
            coll_to_add = add_collection(all_collections, collection_list, colls_fn)
            if coll_to_add != "_CANCEL":
                collection_list.append(coll_to_add)
                reset_required = True
            if len(collection_list) >= MAX_COLLECTIONS:
                keepGoing = False
            else:
                choices = ["Add Another", "Finished"]
                choice2 = utils.select_option("Year/Select", choices)
                if choice2 == "Finished":
                    keepGoing = False

            state["artist_list"] = collection_list
            utils.save_state(state, "datpiff")
        if reset_required:
            utils.reset()

    elif choice == "Remove Artist":
        keepGoing = True
        while keepGoing & (len(collection_list) > 0):
            coll_to_remove = utils.select_option("Year/Select", collection_list + ["_CANCEL"])
            collection_list = [x for x in collection_list if not x == coll_to_remove]
            choices = ["Remove Another", "Finished"]
            choice2 = utils.select_option("Year/Select", choices)
            if choice2 == "Finished":
                keepGoing = False

            state["artist_list"] = collection_list
            # Remove the metadata for this collection
            path_to_meta = f"/metadata/datpiff/{coll_to_remove}.json"
            utils.remove_dir(path_to_meta) if utils.isdir(path_to_meta) else utils.remove_file(path_to_meta)
            utils.save_state(state, "datpiff")

    return


def _collection_names():
    # Note: This function appears to only work right after a reboot.
    tm.write("Getting all\ncollection\nnames", font=pfont_small)
    all_collection_names_dict = {}
    api_request = f"{API}/all_collection_names/"
    cloud_url = f"{CLOUD_PATH}/sundry/etree_collection_names.json"
    all_collection_names_dict = {"Phishin Archive": ["Phish"]}
    resp = None
    status = 0
    itries = 0
    try:
        while (status != 200) and (itries < 3):
            if itries > 0:
                time.sleep(2)
            itries = itries + 1
            gc.collect()
            resp = requests.get(cloud_url)
            utils.print_log(f"Trying to download collections names from {cloud_url}")
            status = resp.status_code
            if status == 200:
                utils.print_log("Collection Names successfully downloaded")
                colls = resp.json()["items"]
                all_collection_names_dict["Internet Archive"] = colls
    #        else:
    #            print(f"API request is {api_request}")
    #            resp = requests.get(api_request).json()
    #            all_collection_names_dict = resp["collection_names"]
    except Exception as e:
        utils.print_log(f"Exception when loading collnames {e}")
    finally:
        if resp is not None:
            resp.close()
    return all_collection_names_dict


def configure_collections():
    main_app = utils.get_main_app()
    if main_app == "datpiff":
        return configure_datpiff_collections()

    choices = ["Add Artist", "Remove Artist", "Cancel"]
    choice = utils.select_option("Year/Select", choices)
    print(f"configure_collection: chose to {choice}")

    if choice == "Cancel":
        return

    collection_list = utils.get_collection_list()

    print(f"current collection_list is {collection_list}")
    if choice == "Add Artist":
        keepGoing = True
        reset_required = False
        all_collections = []
        all_collections_dict = _collection_names()
        for archive in all_collections_dict.keys():
            all_collections = all_collections + all_collections_dict[archive]

        while keepGoing:
            coll_to_add = add_collection(all_collections, utils.get_collection_list())
            if coll_to_add != "_CANCEL":
                collection_list.append(coll_to_add)
                reset_required = True
            choices = ["Add Another", "Finished"]
            choice2 = utils.select_option("Year/Select", choices)
            if choice2 == "Finished":
                keepGoing = False

            utils.set_collection_list(collection_list)
        if reset_required:
            utils.reset()

    elif choice == "Remove Artist":
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


def add_collection(all_collections, collection_list, colls_fn=None):
    matching = [x for x in all_collections if not x in collection_list]
    n_matching = len(matching)

    selected_chars = ""
    subset_match = True
    while n_matching > 25:
        m2 = f"{n_matching} Matching\n(STOP to end)"
        print(m2)
        selected_chars = utils.select_chars("Spell desired\nArtist", message2=m2, already=selected_chars)
        if selected_chars.endswith(utils.STOP_CHAR):
            subset_match = False
            print(f"raw selected {selected_chars}")
            selected_chars = selected_chars.replace(utils.STOP_CHAR, "")
        selected_chars = selected_chars.lower().replace(" ", "")
        print(f"selected {selected_chars}")
        if colls_fn is not None:
            matching = utils.distinct(matching + colls_fn(selected_chars))
        if subset_match:
            matching = [x for x in matching if selected_chars in (x.lower().replace(" ", "") + "$")]
        else:
            matching = [x for x in matching if selected_chars == (x.lower().replace(" ", ""))]
        n_matching = len(matching)

    print(f"Matching is {matching}")
    choice = "_CANCEL"
    if n_matching > 0:
        choice = utils.select_option("Choose artist to add", matching + ["_CANCEL"])

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
        version = "releases" if not utils.is_dev_box() else "dev"
        target = "test_download"
        print(f"Installing from {base_url}, version {version}, target {target}")
        mip.install(base_url, version=version, target=target)
        return True
    except Exception as e:
        print(f"{e}\nFailed to download or save livemusic.py Not updating!!")
        return False


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
        utils.reset()


def choose_dev_mode():
    app_choices = ["no change", "prod", "dev"]
    dev_mode = "dev" if utils.is_dev_box() else "prod"
    new_dev_mode = utils.select_option("Mode", app_choices)
    if (new_dev_mode == "no change") or (new_dev_mode == dev_mode):
        return
    elif new_dev_mode == "dev":
        utils.make_dev_box()
    elif new_dev_mode == "prod":
        utils.make_not_dev_box()
    utils.reset()


def choose_main_app():
    app_choices = ["no change", "livemusic", "datpiff"]
    new_main_app = utils.select_option("Choose App", app_choices)
    if new_main_app != "no change":
        main_app = utils.set_main_app(new_main_app)
    else:
        main_app = utils.get_main_app()
    return main_app


def reconfigure():
    tm.tft.on()
    print("Reconfiguring")
    tm.tft.fill_rect(0, 90, 160, 30, st7789.BLACK)
    time.sleep(0.1)
    config_choices = [
        "Artists",
        "Update Code",
        "Exit",
        "Update Firmware",
        "Wifi",
        "Reboot",
        "Test Buttons",
        "Calibrate Knobs",
        "Calibrate Screen",
        "Factory Reset",
        "Dev Mode",
    ]
    if utils.is_dev_box():
        config_choices.append("Choose App")
    choice = utils.select_option("Config Menu", config_choices)

    if choice == "Artists":
        configure_collections()
    elif choice == "Wifi":
        wifi = configure_wifi()
    elif choice == "Calibrate Knobs":
        tm.calibrate_knobs()
    elif choice == "Test Buttons":
        tm.self_test()
    elif choice == "Update Code":
        if update_code():
            print("rebooting")
            utils.reset()
    elif choice == "Update Firmware":
        update_firmware()
    elif choice == "Factory Reset":
        factory_reset()
    elif choice == "Reboot":
        utils.reset()
    elif choice == "Calibrate Screen":
        tm.calibrate_screen(force=True)
    elif choice == "Exit":
        return choice
    elif choice == "Dev Mode":
        dev_mode = choose_dev_mode()
    elif choice == "Choose App":
        main_app = choose_main_app()
    return choice


def basic_main():
    """
    This script will update livemusic.py if rewind button pressed within 2 seconds.
    """
    print("in basic_main")

    start_time = time.ticks_ms()
    hidden_setdate = False
    tm.calibrate_screen()
    tm.clear_screen()
    yellow_color = st7789.color565(255, 255, 0)
    red_color = st7789.color565(255, 0, 0)
    tm.tft.write(pfont_large, "Welcome..", 0, 0, red_color)
    tm.tft.write(pfont_med, "Time ", 0, 30, yellow_color)
    tm.tft.write(pfont_med, "Machine", 0, 55, yellow_color)
    software_version = utils.get_software_version()
    dev_flag = "dev" if utils.is_dev_box() else ""
    tm.tft.write(pfont_med, f"{software_version} {dev_flag}", 0, 80, yellow_color)
    version_strings = sys.version.split(" ")
    uversion = f"{version_strings[2][:7]} {version_strings[4].replace('-','')}"
    tm.tft.write(pfont_small, f"{uversion}", 0, 105, st7789.WHITE)
    print(f"firmware version: {uversion}. Software version {software_version} {dev_flag}")

    if tm.poll_for_button(tm.pPlayPause, timeout=2):
        reconfigure()

    wifi = utils.connect_wifi()
    if not utils.path_exists(tm.KNOB_SENSE_PATH):
        hidden_setdate = True
        print("knob sense not present")
        tm.self_test()
        tm.calibrate_knobs()
    dt = utils.set_datetime(hidden=hidden_setdate)
    if dt is not None:
        print(f"Date set to {dt}")
        # tm.tft.write(pfont_med, f"{dt[0]}-{dt[1]:02d}-{dt[2]:02d}", 0, 100, yellow_color)
    tm.clear_screen()
    return wifi


def run_livemusic():
    main_app = "livemusic"
    while True:
        try:
            if utils.is_dev_box():
                main_app = utils.get_main_app()
            if main_app == "livemusic":
                import livemusic

                utils.mark_partition()  # If we make it this far, the firmware is good.
                livemusic.run()
            elif main_app == "datpiff":
                import datpiff

                utils.mark_partition()
                datpiff.run()
            else:
                raise NotImplementedError(f"Unknown app {main_app}")
        except Exception as e:
            print(f"Exception in main. {e} -- reconfiguring")
        finally:
            reconfigure()


# basic_main()
