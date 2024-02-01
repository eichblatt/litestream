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

import json
import machine
import network
import ntptime
import os
import st7789
import sys
import time

import fonts.NotoSans_18 as pfont_small

import board as tm

WIFI_CRED_HIST_PATH = "/wifi_cred_hist.json"
WIFI_CRED_PATH = "/wifi_cred.json"
STATE_PATH = "/latest_state{app_string}.json"

stage_date_color = st7789.color565(255, 255, 0)
yellow_color = st7789.color565(255, 255, 0)
tracklist_color = st7789.color565(0, 255, 255)
play_color = st7789.color565(255, 0, 0)
nshows_color = st7789.color565(0, 100, 255)
choices_color = st7789.color565(128, 255, 128)


def reset():
    machine.reset()


def reload(mod):
    # This doesn't seem to work. I wish it did.
    z = __import__(mod)
    del z
    del sys.modules[mod]
    return __import__(mod)


def read_file(path):
    fh = None
    contents = [""]
    try:
        fh = open(path, "r")
        contents = fh.readlines()
    except Exception as e:
        print(f"Exception suppressed in read_file {e}. Path {path}")
    finally:
        if fh is not None:
            fh.close()
    return contents


def select_option(message, choices):
    if len(choices) == 0:
        return ""
    pSelect_old = True
    tm.y._value = tm.y._min_val
    tm.d._value = tm.d._min_val
    step = step_old = 0
    text_height = 16
    choice = ""
    first_time = True
    tm.clear_screen()
    # init_screen()
    select_bbox = tm.Bbox(0, 20, 160, 128)
    tm.tft.write(pfont_small, f"{message}", 0, 0, tracklist_color)
    while pSelect_old == tm.pSelect.value():
        step = (tm.y.value() - tm.y._min_val) % len(choices)
        if (step != step_old) or first_time:
            i = j = 0
            first_time = False
            step_old = step
            tm.clear_bbox(select_bbox)
            # init_screen()

            for i, s in enumerate(range(max(0, step - 2), step)):
                tm.tft.write(pfont_small, choices[s], select_bbox.x0, select_bbox.y0 + text_height * i, choices_color)

            text = ">" + choices[step]
            tm.tft.write(pfont_small, text, select_bbox.x0, select_bbox.y0 + text_height * (i + 1), st7789.RED)

            for j, s in enumerate(range(step + 1, min(step + 5, len(choices)))):
                tm.tft.write(pfont_small, choices[s], select_bbox.x0, select_bbox.y0 + text_height * (i + j + 2), choices_color)
            # print(f"step is {step}. Text is {text}")
        time.sleep(0.2)
    choice = choices[step]
    # print(f"step is now {step}. Choice: {choice}")
    time.sleep(0.6)
    return choices[step]


def select_chars(message, message2="", already=None):
    charset = "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ!\"#$%&'()*+,-./:;<=>?@[\\]^_`{|}~ \t\n\r\x0b\x0c"
    message = message.split("\n")
    pSelect_old = pStop_old = True
    tm.y._max_val = tm.y._max_val + 100
    tm.y._value = int((tm.y._min_val + tm.y._max_val) / 2)
    tm.d._value = int((tm.d._min_val + tm.d._max_val) / 2)

    step = step_old = 0
    text_height = 17
    screen_width = 16
    tm.clear_screen()
    y_origin = len(message) * text_height

    select_bbox = tm.Bbox(0, y_origin, 160, y_origin + text_height)
    selected_bbox = tm.Bbox(0, y_origin + text_height, 160, y_origin + 2 * text_height)
    message2_bbox = tm.Bbox(0, y_origin + 2 * text_height, 160, 128)

    def decade_value(tens, ones, bounds, start_vals=(tm.d._value, tm.y._value)):
        value = (tens - start_vals[0]) * 10 + (ones - start_vals[1])
        value = max(value, bounds[0]) % bounds[1]

        if value == 0:
            tm.d._value = start_vals[0]
            tm.y._value = start_vals[1]
        return value

    for i, msg in enumerate(message):
        tm.init_screen()
        tm.tft.write(pfont_small, f"{msg}", 0, i * text_height, stage_date_color)

    print(f"Message2 is {message2}")
    if len(message2) > 0:
        tm.clear_bbox(message2_bbox)
        tm.init_screen()
        tm.tft.write(pfont_small, f"{message2}", 0, message2_bbox.y0, stage_date_color)

    singleLetter = already is not None
    already = already if singleLetter else ""
    selected = already
    print(f"already is {already}")
    print(f"Message2 is {message2}")
    text = "DEL"
    first_time = True
    finished = False
    prev_selected = ""

    while not finished:
        print(f"pStop_old {pStop_old}, pStop: {tm.pStop.value()}")
        while pSelect_old == tm.pSelect.value():
            if pStop_old != tm.pStop.value():
                finished = True
                break
            if (len(selected) > 0) and (selected != prev_selected):
                prev_selected = selected
                tm.clear_bbox(selected_bbox)
                tm.tft.write(pfont_small, selected, selected_bbox.x0, selected_bbox.y0, st7789.RED)
            if len(already) > 0:  # start with cursor on the most recent character.
                if first_time:
                    d0, y0 = divmod(1 + charset.index(already[-1]), 10)
                    d0 = tm.d._value - d0
                    y0 = tm.y._value - y0
                step = decade_value(tm.d.value(), tm.y.value(), (0, len(charset) + 1), (d0, y0))
            else:
                step = decade_value(tm.d.value(), tm.y.value(), (0, len(charset) + 1))
            if (step != step_old) or first_time:
                cursor = 0
                first_time = False
                step_old = step
                tm.clear_bbox(select_bbox)

                # Write the Delete character
                cursor += tm.tft.write(
                    pfont_small, "DEL", select_bbox.x0, select_bbox.y0, st7789.WHITE if step != 0 else st7789.RED
                )

                text = charset[max(0, step - 5) : -1 + step]
                for x in charset[94:]:
                    text = text.replace(x, ".")  # Should be "\u25A1", but I don't think we have the font for this yet.

                # Write the characters before the cursor
                cursor += tm.tft.write(pfont_small, text, select_bbox.x0 + cursor, select_bbox.y0, tracklist_color)

                # Write the character AT the cursor
                text = charset[-1 + min(step, len(charset))]
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
                text = charset[step : min(-1 + step + screen_width, len(charset))]
                for x in charset[94:]:
                    text = text.replace(x, ".")
                tm.tft.write(pfont_small, text, select_bbox.x0 + cursor, select_bbox.y0, tracklist_color)

                # print(f"step is {step}. Text is {text}")
            time.sleep(0.2)
        time.sleep(0.2)  # de-jitter
        if not finished:
            if step == 0:
                selected = selected[:-1]
            else:
                choice = charset[step - 1]  # -1 for the delete character.
                # print(f"step is now {step}. Choice: {choice}")
                selected = selected + choice
            tm.clear_bbox(selected_bbox)
            tm.tft.write(pfont_small, selected, selected_bbox.x0, selected_bbox.y0, st7789.RED)
        if singleLetter:
            print(f"singleLetter chosen {selected}")
            finished = True

    tm.y._max_val = tm.y._max_val - 100
    print(f"select_char Returning. selected is: {selected}")
    tm.clear_screen()
    tm.tft.write(pfont_small, "Selected:", 0, 0, stage_date_color)
    tm.tft.write(pfont_small, selected, selected_bbox.x0, text_height + 5, st7789.RED)
    time.sleep(0.3)
    return selected


def isdir(path):
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


def copy_file(src, dest):
    outfile = open(dest, "wb")
    infile = open(src, "rb")
    content = infile.readlines()
    infile.close()
    for line in content:
        outfile.write(line)
    outfile.close()


def touch(path):
    if not path_exists(path):
        with open(path, "w") as f:
            f.write("0")


def remove_file(path):
    if not path_exists(path):
        return
    os.remove(path)


def remove_dir(path):
    if not path_exists(path):
        return
    for file in os.listdir(path):
        full_path = f"{path}/{file}"
        if isdir(full_path):
            remove_dir(full_path)
        else:
            os.remove(full_path)
    os.rmdir(path)


def copy_dir(src_d, dest_d):
    print(f"Copy_dir {src_d}, {dest_d}")
    if path_exists(dest_d):
        os.rename(dest_d, f"{dest_d}_tmp")
    os.mkdir(dest_d)
    for file in os.listdir(src_d):
        print(f"file: {file}")
        if isdir(f"{src_d}/{file}"):
            print(".. is a directory")
            copy_dir(f"{src_d}/{file}", f"{dest_d}/{file}")
        else:
            copy_file(f"{src_d}/{file}", f"{dest_d}/{file}")
    remove_dir(f"{dest_d}_tmp")


def create_factory_image():
    # Use this function when you have the filesystem as desired for factory settings.
    # Copy the code into a "/factory_lib" folder
    remove_dir("/previous_lib")
    remove_dir("/factory_lib")
    remove_dir("/test_download")
    copy_dir("/lib", "/factory_lib")
    # put the wifi_cred of the factory in place
    remove_wifi_cred(hist=True)
    copy_file("/wifi_cred.json.factory.py", WIFI_CRED_PATH)
    # remove files that are peculiar to this instance
    remove_file(tm.KNOB_SENSE_PATH)
    remove_file(tm.SCREEN_TYPE_PATH)
    remove_file("/exception.log")
    for app_string in ["", "_datpiff"]:
        remove_file(STATE_PATH.format(app_string=app_string))
    if path_exists("/.is_dev_box"):
        os.rename("/.is_dev_box", "/.not_dev_box")


def remove_wifi_cred(hist=False):
    os.remove(WIFI_CRED_PATH)
    if hist:
        os.remove(WIFI_CRED_HIST_PATH)


def get_wifi_cred(wifi):
    choices = wifi.scan()  # Scan for available access points
    choices = [x[0].decode().replace('"', "") for x in choices]
    choices = [x for x in choices if x != ""]
    choices = sorted(set(choices), key=choices.index)
    choices = choices + ["Hidden WiFi"]
    print(f"get_wifi_cred. Choices are {choices}")
    choice = select_option("Select Wifi", choices)
    if choice == "Hidden WiFi":
        choice = select_chars(f"Input WiFi Name\n(Day,Year), Select\n ", "Stop to End")
    if path_exists(WIFI_CRED_HIST_PATH):
        wch = read_json(WIFI_CRED_HIST_PATH)
        if choice in wch.keys():
            ask_passkey = wch[choice]
            use_passkey = select_option(f"Use {ask_passkey} ?", ["Yes", "No"])
            if use_passkey == "Yes":
                return {"name": choice, "passkey": ask_passkey}
            else:
                del wch[choice]
                write_json(wch, WIFI_CRED_HIST_PATH)

    passkey = select_chars(f"Input Passkey for\n{choice}\n(Day,Year), Select\n ", "Stop to End")
    return {"name": choice, "passkey": passkey}


def disconnect_wifi():
    wifi = network.WLAN(network.STA_IF)
    wifi.active(True)
    wifi.disconnect()


def set_datetime(hidden=False):
    print("Setting datetime")
    if not hidden:
        tm.write("Setting Date", y=45, clear=False)
    time_set = time.localtime()[0] >= 2024
    # for some reason, we have to try several times before it works.
    for i in range(10):
        if time_set:
            return time.localtime()
        try:
            ntptime.time()
            ntptime.settime()
            time_set = True
        except OSError:
            time.sleep(0.3)
            pass
        except OverflowError:
            time.sleep(0.3)
            pass
        except Exception:
            pass
    else:
        return None


def write_json(obj, path):
    print(f"writing json to {path}")
    with open(path, "w") as f:
        json.dump(obj, f)


def read_json(path):
    print(f"reading json from {path}")
    with open(path, "r") as f:
        obj = json.load(f)
    return obj


def connect_wifi(retry_time=100, timeout=10000, itry=0, hidden=False):
    wifi = network.WLAN(network.STA_IF)
    wifi.active(True)
    wifi.config(pm=network.WLAN.PM_NONE)
    if wifi.isconnected():
        return wifi

    if path_exists(WIFI_CRED_PATH):
        wifi_cred = read_json(WIFI_CRED_PATH)
    else:
        # We want to re-calibrate whenever the wifi changes, so that users will
        # calibrate the machine when they receive it.
        # (It will be shipped with WIFI CRED from the manufacturing tests, that will fail).
        hidden = False
        if itry <= 1:
            tm.self_test()
            tm.calibrate_knobs()

        try:
            disconnect_wifi()
        except Exception as e:
            print(e)
        wifi_cred = get_wifi_cred(wifi)
        write_json(wifi_cred, WIFI_CRED_PATH)
        reset()

    if not hidden:
        tm.write("Connecting\nWiFi....", color=yellow_color)
        version_strings = sys.version.split(" ")
        uversion = f"{version_strings[2][:7]} {version_strings[4].replace('-','')}"
        tm.write(f"{uversion}", y=110, color=st7789.WHITE, font=pfont_small, clear=False)
        software_version = get_software_version()
        print(f"Software_version {software_version}")
        tm.write(f"{software_version}", y=85, color=st7789.WHITE, font=pfont_small, clear=False)

    try:
        wifi.connect(wifi_cred["name"], wifi_cred["passkey"])
    except Exception as e:
        print("Exception connecting to wifi {e}")
    s = wifi.status()
    wait_time = 0

    while s == network.STAT_CONNECTING:
        time.sleep_ms(retry_time)
        wait_time += retry_time
        if wifi.isconnected():
            print(f"Returning connected after {wait_time} ms")
            break
        elif wait_time > timeout:
            print(f"Timed out after {wait_time} ms")
            wifi.disconnect()
            break
        s = wifi.status()

    if wifi.isconnected():
        tm.clear_area(0, 50, 160, 30)
        if not hidden:
            tm.write("Connected", y=50, color=st7789.WHITE, clear=False)

        wifi_cred_hist = read_json(WIFI_CRED_HIST_PATH) if path_exists(WIFI_CRED_HIST_PATH) else {}
        wifi_cred_hist[wifi_cred["name"]] = wifi_cred["passkey"]
        write_json(wifi_cred_hist, WIFI_CRED_HIST_PATH)
        print(f"Wifi cred hist {wifi_cred_hist} written to {WIFI_CRED_HIST_PATH}")
        return wifi
    else:
        tm.write("Not Connected", y=80, color=st7789.RED, clear=False, font=pfont_small)
        remove_wifi_cred()
        time.sleep(2)
        connect_wifi(itry=itry + 1)


def get_current_partition_name():
    from esp32 import Partition

    current_partition = Partition(Partition.RUNNING).info()[4]
    return current_partition


def mark_partition():
    from esp32 import Partition

    current_partition = Partition(Partition.RUNNING)
    current_partition.mark_app_valid_cancel_rollback()


def get_software_version():
    code_version = read_file("/lib/.VERSION")[0]
    if len(code_version) == 0:
        code_version = "unknown"
    return code_version


def update_firmware():
    from ota32.ota import OTA
    from ota32 import open_url
    import gc

    latest_release = "latest"
    branch = "releases"
    server_path = "https://raw.githubusercontent.com/eichblatt/litestream"
    sha_url = f"{server_path}/{branch}/MicropythonFirmware/{latest_release}/micropython.sha"
    micropython_url = f"{server_path}/{branch}/MicropythonFirmware/{latest_release}/micropython.bin"

    try:
        s = open_url(sha_url)
        sha = s.read(1024).split()[0].decode()
        s.close()
        gc.collect()

        ota = OTA(verbose=True)
        ota.ota(micropython_url, sha)

    except Exception as e:
        print(f"{e}\nFailed to update to a new partition")
        return -1

    return 0


def get_tape_id(app="livemusic"):
    return load_state(app)["selected_tape_id"]


def get_collection_list():
    return load_state()["collection_list"]


def set_collection_list(collection_list):
    state = load_state()
    state["collection_list"] = collection_list
    save_state(state)


def save_state(state, app="livemusic"):
    # print(f"writing {state} to {STATE_PATH}")
    state_path = STATE_PATH.format(app_string=f"_{app}" if app != "livemusic" else "")
    with open(state_path, "w") as f:
        json.dump(state, f)
    return


def load_livemusic_state(state_path):
    state = {}
    if path_exists(state_path):
        state = read_json(state_path)
        collection_list = state.get("collection_list", "GratefulDead")
        selected_date = state.get("selected_date", "1975-08-13")
        selected_collection = state.get("selected_collection", collection_list[0])
        selected_tape_id = state.get("selected_tape_id", "unknown")
        boot_mode = state.get("boot_mode", "normal")
        state = {
            "collection_list": collection_list,
            "selected_date": selected_date,
            "selected_collection": selected_collection,
            "selected_tape_id": selected_tape_id,
            "boot_mode": boot_mode,
        }
    else:
        collection_list = ["GratefulDead"]
        selected_date = "1975-08-13"
        selected_collection = collection_list[0]
        selected_tape_id = "unknown"
        boot_mode = "normal"
        state = {
            "collection_list": collection_list,
            "selected_date": selected_date,
            "selected_collection": selected_collection,
            "selected_tape_id": selected_tape_id,
            "boot_mode": boot_mode,
        }
    write_json(state, state_path)
    return state


def load_datpiff_state(state_path):
    state = {}
    if path_exists(state_path):
        state = read_json(state_path)
        artist_list = state.get("artist_list", ["2pac", "50 cent", "chief keef", "drake", "eminem", "jay-z", "lil wayne"])
        selected_artist = state.get("selected_artist", artist_list[0])
        selected_tape_id = state.get("selected_tape_id", "datpiff-mixtape-m014640a")
        boot_mode = state.get("boot_mode", "normal")
        state = {
            "artist_list": artist_list,
            "selected_artist": selected_artist,
            "selected_tape_id": selected_tape_id,
            "boot_mode": boot_mode,
        }
    else:
        artist_list = ["2pac", "50 cent", "chief keef", "drake", "eminem", "jay-z", "lil wayne"]
        selected_artist = artist_list[0]
        selected_tape_id = "datpiff-mixtape-m014640a"
        boot_mode = "normal"
        state = {
            "artist_list": artist_list,
            "selected_artist": selected_artist,
            "selected_tape_id": selected_tape_id,
            "boot_mode": boot_mode,
        }
    write_json(state, state_path)
    return state


def load_state(app="livemusic"):
    state_path = STATE_PATH.format(app_string=f"_{app}" if app != "livemusic" else "")
    if app == "livemusic":
        return load_livemusic_state(state_path)
    elif app == "datpiff":
        return load_datpiff_state(state_path)
    else:
        raise NotImplementedError("Unknown app {app}")
