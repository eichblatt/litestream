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

import fonts.NotoSans_18 as pfont_small
import fonts.NotoSans_24 as pfont_med
import fonts.NotoSans_32 as pfont_large
from machine import SPI, Pin
from mrequests import mrequests as requests
from rotary_irq_esp import RotaryIRQ
import mip
import network

import archive_utils
import board as tm
import utils


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
    choice = utils.select_option("Select", choices)
    print(f"configure_wifi: chose {choice}")
    if choice == "Remove Wifi":
        utils.remove_wifi_cred()
    utils.disconnect_wifi()
    time.sleep(2)
    wifi = utils.connect_wifi()
    return wifi


def test_update():
    tm.tft.fill_rect(0, 0, 160, 128, tm.BLACK)
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
    tm.write("Welcome..", 0, 0, tm.pfont_large, tm.RED)
    tm.write("Press Select Button", 0, tm.pfont_large.HEIGHT, tm.pfont_med, tm.YELLOW, show_end=-3, clear=False)

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

    tm.tft.fill_rect(0, 0, 160, 128, tm.BLACK)
    tm.clear_screen()
    tm.write("Welcome..", 0, 0, tm.pfont_large, tm.RED)
    if update_code:
        tm.write("Updating ... ", 0, tm.pfont_large.HEIGHT, tm.pfont_med, tm.YELLOW, clear=False)
    else:
        tm.write("Not Updating", 0, tm.pfont_large.HEIGHT, tm.pfont_med, tm.RED, clear=False)

    return update_code


def update_code():
    print("Updating code")
    wifi = utils.connect_wifi()
    if not wifi.isconnected():
        print("Error -- not connected to wifi")
        return
    tm.clear_screen()
    tm.label_soft_knobs("-", "-", "-")
    tm.write("Updating", 0, 40, tm.pfont_med, tm.YELLOW)
    tm.write("code", 0, 40 + tm.pfont_med.HEIGHT, tm.pfont_med, tm.RED, clear=False)

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

    tm.clear_screen()
    tm.write("Updating", 0, 50, tm.pfont_med, tm.YELLOW)
    tm.write(" Firmware", 0, 50 + tm.pfont_med.HEIGHT, tm.pfont_med, tm.RED, clear=False)

    current_partition = utils.get_current_partition_name()
    print(f"The current partition is {current_partition}")
    status = utils.update_firmware()

    if status == 0:
        utils.reset()


def choose_dev_mode():
    app_choices = ["no change", "prod", "dev"]
    dev_mode = "dev" if utils.is_dev_box() else "prod"
    new_dev_mode = utils.select_option(f"Mode.\nNow:{dev_mode}", app_choices)
    if (new_dev_mode == "no change") or (new_dev_mode == dev_mode):
        return
    elif new_dev_mode == "dev":
        utils.make_dev_box()
    elif new_dev_mode == "prod":
        utils.make_not_dev_box()
    utils.reset()


def choose_main_app():
    app_choices = ["no change", "livemusic", "78rpm", "classical_std"]  # "datpiff" removed
    main_app = utils.get_main_app()
    new_main_app_name = utils.select_option(f"Choose App\nNow:{main_app.__name__}", app_choices)
    if new_main_app_name != "no change":
        main_app = utils.set_main_app(new_main_app_name)
    return main_app


def reconfigure():
    tm.tft.on()
    tm.clear_screen()
    print("Reconfiguring")
    tm.tft.fill_rect(0, 90, 160, 30, tm.BLACK)
    # time.sleep(0.1)
    app = utils.get_main_app()
    exit_string = (f"Return to {app.__name__}",)
    app_config_choices = app.CONFIG_CHOICES if "CONFIG_CHOICES" in dir(app) else []
    config_choices = app_config_choices + [
        "Update Code",
        exit_string,
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

    if choice in app_config_choices:
        app.configure(choice)
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
        utils.reset()
    elif choice == exit_string:
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
    ypos = 0
    tm.clear_screen()
    tm.write("Welcome", 0, ypos, tm.pfont_large, tm.RED)
    ypos += tm.pfont_large.HEIGHT
    tm.write("Time ", 0, ypos, tm.pfont_med, tm.YELLOW, clear=False)
    ypos += tm.pfont_med.HEIGHT
    tm.write("Machine", 0, ypos, tm.pfont_med, tm.YELLOW, clear=False)
    ypos += tm.pfont_med.HEIGHT
    software_version = utils.get_software_version()
    dev_flag = "dev" if utils.is_dev_box() else ""
    tm.write(f"{software_version} {dev_flag}", 0, ypos, tm.pfont_med, tm.YELLOW, clear=False)
    ypos += tm.pfont_med.HEIGHT
    version_strings = sys.version.split(" ")
    uversion = f"{version_strings[2][:7]} {version_strings[4].replace('-','')}"
    tm.write(f"{uversion}", 0, ypos, tm.pfont_small, tm.WHITE, clear=False, show_end=1)
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
    tm.clear_screen()
    return wifi


def run_livemusic():
    while True:
        try:
            if utils.is_dev_box():
                main_app = utils.get_main_app()
            else:
                import livemusic as main_app

            utils.mark_partition()  # If we make it this far, the firmware is good.
            main_app.run()
        except Exception as e:
            print(f"Exception in main. {e} -- reconfiguring")
        finally:
            time.sleep(2)
            reconfigure()


# basic_main()
