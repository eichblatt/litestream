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

import deflate
import json
import machine
import network
import ntptime
import os
import random
import re
import sys
import time

import board as tm

WIFI_CRED_HIST_PATH = "/config/wifi_cred_hist.json"
WIFI_CRED_PATH = "/wifi_cred.json"
STATE_PATH = "/config/latest_state{app_string}.json"
DEV_BOX_PATH = "/config/.is_dev_box"
MAIN_APP_PATH = "/config/.main_app"
STOP_CHAR = "$StoP$"

choices_color = tm.WHITE
pfont_small = tm.pfont_small


# Utils using TM hardware
######################################################################################### Utils using TM hardware
#


def select_option(message, choices):
    if len(choices) == 0:
        return ""
    pSelect_old = True
    tm.y._value = tm.y._min_val = 0
    tm.d._value = tm.d._min_val = 0
    tm.y._max_val = len(choices) - 1
    tm.d._max_val = len(choices) - 1
    tm.y._range_mode = tm.y.RANGE_WRAP
    tm.d._range_mode = tm.d.RANGE_WRAP

    step = step_old = 0
    text_height = 17
    choice = ""
    first_time = True
    tm.clear_screen()
    # init_screen()
    message_height = len(message.split("\n"))
    select_bbox = tm.Bbox(0, (text_height + 1) * message_height, 160, 128)
    tm.write(f"{message}", 0, 0, pfont_small, tm.tracklist_color)
    while pSelect_old == tm.pSelect.value():
        step = (tm.y.value() - tm.y._min_val) % len(choices)
        if (step != step_old) or first_time:
            i = j = 0
            first_time = False
            step_old = step
            tm.clear_bbox(select_bbox)
            # init_screen()

            for i, s in enumerate(range(max(0, step - 2), step)):
                xval, yval = select_bbox.x0, select_bbox.y0 + text_height * i
                tm.write(choices[s], xval, yval, pfont_small, choices_color, clear=False, show_end=True)

            text = ">" + choices[step]
            xval, yval = select_bbox.x0, select_bbox.y0 + text_height * (i + 1)
            tm.write(text, xval, yval, pfont_small, tm.purple_color, clear=False, show_end=True)

            for j, s in enumerate(range(step + 1, min(step + 5, len(choices)))):
                xval, yval = select_bbox.x0, select_bbox.y0 + text_height * (i + j + 2)
                tm.write(choices[s], xval, yval, pfont_small, choices_color, clear=False, show_end=True)
            # print(f"step is {step}. Text is {text}")
        time.sleep(0.2)
    choice = choices[step]
    print(f"step is now {step}. Choice: {choice}")
    time.sleep(0.6)
    return choice


def select_chars(message, message2="", already=None):
    charset = "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ!\"#$%&'()*+,-./:;<=>?@[\\]^_`{|}~ \t\n\r\x0b\x0c"
    message = message.split("\n")
    pSelect_old = pStop_old = True
    tm.y._min_val = 0
    tm.y._max_val = len(charset)  # tm.y._max_val + 100
    tm.d._min_val = 0
    tm.d._max_val = len(charset) // 5
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
        tm.write(f"{msg}", 0, i * text_height, pfont_small, tm.stage_date_color, clear=False)

    print(f"Message2 is {message2}")
    if len(message2) > 0:
        tm.clear_bbox(message2_bbox)
        tm.write(f"{message2}", 0, message2_bbox.y0, pfont_small, tm.stage_date_color, clear=False)

    singleLetter = already is not None
    already = already if singleLetter else ""
    selected = already
    print(f"already is {already}")
    print(f"Message2 is {message2}")
    text = "DEL"
    first_time = True
    finished = False
    stopped = False
    prev_selected = ""

    while not finished:
        print(f"pStop_old {pStop_old}, pStop: {tm.pStop.value()}")
        while pSelect_old == tm.pSelect.value():
            if pStop_old != tm.pStop.value():
                finished = True
                stopped = True
                break
            if (len(selected) > 0) and (selected != prev_selected):
                prev_selected = selected
                tm.clear_bbox(selected_bbox)
                tm.tft.write(pfont_small, selected[-11:], selected_bbox.x0, selected_bbox.y0, tm.purple_color)
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
                    pfont_small, "DEL", select_bbox.x0, select_bbox.y0, tm.WHITE if step != 0 else tm.purple_color
                )

                text = charset[max(0, step - 5) : -1 + step]
                for x in charset[94:]:
                    text = text.replace(x, ".")  # Should be "\u25A1", but I don't think we have the font for this yet.

                # Write the characters before the cursor
                cursor += tm.tft.write(pfont_small, text, select_bbox.x0 + cursor, select_bbox.y0, tm.tracklist_color)

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

                cursor += tm.tft.write(pfont_small, text, select_bbox.x0 + cursor, select_bbox.y0, tm.purple_color)

                # Write the characters after the cursor
                text = charset[step : min(-1 + step + screen_width, len(charset))]
                for x in charset[94:]:
                    text = text.replace(x, ".")
                tm.tft.write(pfont_small, text, select_bbox.x0 + cursor, select_bbox.y0, tm.tracklist_color)

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
            tm.tft.write(pfont_small, selected, selected_bbox.x0, selected_bbox.y0, tm.purple_color)
        if singleLetter:
            if stopped:
                selected = selected + STOP_CHAR
            print(f"singleLetter chosen {selected.replace(STOP_CHAR,'')}")
            finished = True

    tm.y._max_val = tm.y._max_val - 100
    print(f"select_char Returning. selected is: {selected}")
    tm.clear_screen()
    tm.tft.write(pfont_small, "Selected:", 0, 0, tm.stage_date_color)
    tm.tft.write(pfont_small, selected.replace(STOP_CHAR, ""), selected_bbox.x0, text_height + 5, tm.purple_color)
    time.sleep(0.3)
    return selected


# OS Utils
################################################################################################################# OS-related utils
#


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


def ls_by_time(dir, ascending=True):
    files_in_dir = [f"{dir}/{x}" for x in os.listdir(dir)]
    files_in_dir = [x for x in files_in_dir if not isdir(x)]
    files_in_dir = sorted(files_in_dir, key=lambda x: os.stat(x)[7])
    if not ascending:
        files_in_dir = files_in_dir[::-1]
    return files_in_dir


def remove_oldest_files(dir, n=1):
    files_in_dir = ls_by_time(dir)
    for file in files_in_dir[:n]:
        remove_file(file)


def keep_only_n_files(dir, n):
    files_in_dir = ls_by_time(dir, ascending=False)
    if len(files_in_dir) <= n:
        return
    for file in files_in_dir[n:]:
        remove_file(file)


def disk_free():
    stat = os.statvfs("/")
    return stat[3] * stat[0] / 1024  # in kbytes


def disk_usage():
    stat = os.statvfs("/")
    return (stat[3] - stat[2]) * stat[0] / 1024  # in kbytes


def dirname(path):
    if isdir(path):
        return path
    return "/".join(path.split("/")[:-1])


def basename(path):
    return path.split("/")[-1]


def remove_file(path):
    if not path_exists(path):
        return
    try:
        os.remove(path)
        return path
    except Exception as e:
        print(f"Failed to remove {path}. {e}")


def remove_files(files):
    files = [files] if isinstance(files, str) else files
    print(f"files: {files}")
    for file in files:
        dir = dirname(file)
        fname = basename(file)
        if ("*" in fname) and isdir(dir):
            for x in os.listdir(dir):
                if re.match(fname, x):
                    remove_file("/".join([dir, x]))
        elif isdir(dir):
            remove_file(file)
        else:
            print(f"Failed to remove {file}")


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


def mkdirs(path):
    # Make all the dirs on the way to path
    if path_exists(path):
        return
    parent = "/".join(path.split("/")[:-1])
    if not path_exists(parent):
        mkdirs(parent)
    print(f"making dir {path}")
    os.mkdir(path)


def write_json(obj, path):
    print(f"writing json to {path}")
    parent_dir = "/".join(path.split("/")[:-1])
    mkdirs(parent_dir)
    if path.endswith(".gz"):
        with open(path, "wb") as f:
            with deflate.DeflateIO(f, deflate.GZIP) as f:
                json.dump(obj, f)
    else:
        with open(path, "w") as f:
            json.dump(obj, f)


def read_json(path):
    print(f"reading json from {path}")
    if path.endswith(".gz"):
        with open(path, "rb") as f:
            with deflate.DeflateIO(f, deflate.GZIP) as f:
                obj = json.load(f)
    else:
        with open(path, "r") as f:
            obj = json.load(f)
    return obj


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


def set_boot_partition(part_name):
    from esp32 import Partition

    Partition.set_boot(Partition(part_name))
    return


def get_current_partition_name():
    from esp32 import Partition

    current_partition = Partition(Partition.RUNNING).info()[4]
    return current_partition


def mark_partition():
    from esp32 import Partition

    current_partition = Partition(Partition.RUNNING)
    current_partition.mark_app_valid_cancel_rollback()


def capitalize(string):
    if len(string) == 0:
        return string
    words = string.split()
    Words = [w[0].upper() + w[1:] for w in words]
    return " ".join(Words)


def clear_log(outpath="/log_out.py"):
    remove_file(outpath)


def print_log(msg, outpath="/log_out.py"):
    fout = open(outpath, "a")
    fout.write(msg + "\n")
    fout.close()
    print(msg)


# math
############################################################################################### math
#


def distinct(lis):
    return sorted(list(set(lis)))


def deal_n(all_items, n, unique=True):
    """deal n items (without replacement) from list or dictionary `all_items`"""
    result = [] if isinstance(all_items, (list, tuple)) else {}
    if unique and not isinstance(all_items, dict):
        all_items = distinct(all_items)
    n_items = len(all_items)
    if n > n_items:
        raise ValueError(f"Cannot deal {n} items from list of length {n_items}.\nall_items:{all_items}")
    for i in range(n):
        ind = random.randrange(n_items - i)
        if isinstance(result, list):
            result.append(all_items[ind])
            all_items = all_items[:ind] + all_items[(ind + 1) :]
        elif isinstance(result, dict):
            key = all_items.keys()[ind]
            result = result | all_items[key]
            del all_items[key]
    return result


def deal_frac(all_items, frac, unique=True):
    if unique:
        all_items = distinct(all_items)
    n_items = len(all_items)
    return deal_n(all_items, int(frac * n_items), unique)


def shuffle(all_items, unique=True):
    # Return the items from a list in a random order
    return deal_frac(all_items, 1, unique)


def random_character(first, last):
    if first > last:
        raise ValueError("Charcters {first} and {last} are not in order")
    return chr(random.randint(ord(first), ord(last)))


# Application-Specific
############################################################################################### Application-Specific
#

KNOWN_APPS = ["livemusic", "datpiff", "78rpm"]


def set_main_app(main_app):
    try:
        if not main_app in KNOWN_APPS:
            main_app = "livemusic"
        main_app = write_json(main_app, MAIN_APP_PATH)
    except Exception as e:
        pass
    return main_app


def get_main_app():
    main_app = "livemusic"
    try:
        if path_exists(MAIN_APP_PATH):
            main_app = read_json(MAIN_APP_PATH)
        if not main_app in KNOWN_APPS:
            main_app = "livemusic"
    except Exception as e:
        pass
    return main_app


def make_not_dev_box():
    remove_file(DEV_BOX_PATH)


def make_dev_box():
    touch(DEV_BOX_PATH)


def is_dev_box():
    return path_exists(DEV_BOX_PATH)


def create_factory_image():
    # Use this function when you have the filesystem as desired for factory settings.
    # Copy the code into a "/factory_lib" folder
    remove_dir("/previous_lib")
    remove_dir("/factory_lib")
    remove_dir("/test_download")
    remove_dir("/metadata")
    remove_wifi_cred(hist=True)
    remove_dir("/config")
    copy_dir("/lib", "/factory_lib")
    # put the wifi_cred of the factory in place
    copy_file("/wifi_cred.json.factory.py", WIFI_CRED_PATH)
    # remove files that are peculiar to this instance
    remove_file("/exception.log")
    remove_file("/tmp.json")
    os.mkdir("/config")
    if path_exists("/BOOT.py"):
        os.rename("/BOOT.py", "/boot.py")


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


# wifi
####################################################################################################################### wifi
#


def remove_wifi_cred(hist=False):
    remove_file(WIFI_CRED_PATH)
    if hist:
        remove_file(WIFI_CRED_HIST_PATH)


def get_wifi_cred(wifi):
    choices = wifi.scan()  # Scan for available access points
    choices = [x[0].decode().replace('"', "") for x in choices]
    choices = [x for x in choices if x != ""]
    choices = sorted(set(choices), key=choices.index)
    choices = choices + ["Hidden WiFi", "Rescan WiFi"]
    print(f"get_wifi_cred. Choices are {choices}")
    choice = select_option("Select Wifi", choices)
    if choice == "Hidden WiFi":
        choice = select_chars(f"Input WiFi Name\n(Day,Year), Select\n ", "Stop to End")
    elif choice == "Rescan WiFi":
        print("Chose to rescan wifi")
        return get_wifi_cred(wifi)

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
            try:
                tm.self_test()
                tm.calibrate_knobs()
            except:
                pass
        try:
            disconnect_wifi()
        except Exception as e:
            print(e)
        wifi_cred = get_wifi_cred(wifi)
        write_json(wifi_cred, WIFI_CRED_PATH)
        reset()

    if not hidden:
        tm.write("Connecting..", color=tm.yellow_color)
        tm.write("Powered by archive.org and phish.in", 0, 23, tm.pfont_med, tm.purple_color, 23, clear=False, show_end=-3)
        version_strings = sys.version.split(" ")
        uversion = f"{version_strings[2][:7]} {version_strings[4].replace('-','')}"
        tm.write(f"{uversion}", y=110, color=tm.WHITE, font=pfont_small, clear=False)
        software_version = get_software_version()
        dev_flag = "dev" if is_dev_box() else ""
        print(f"Software_version {software_version} {dev_flag}")
        tm.write(f"{software_version} {dev_flag}", y=93, color=tm.WHITE, font=pfont_small, clear=False)

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
            tm.write("Connected", y=50, color=tm.WHITE, clear=False)

        wifi_cred_hist = read_json(WIFI_CRED_HIST_PATH) if path_exists(WIFI_CRED_HIST_PATH) else {}
        wifi_cred_hist[wifi_cred["name"]] = wifi_cred["passkey"]
        write_json(wifi_cred_hist, WIFI_CRED_HIST_PATH)
        print(f"Wifi cred hist {wifi_cred_hist} written to {WIFI_CRED_HIST_PATH}")
        return wifi
    else:
        tm.write("Not Connected", y=93, color=tm.RED, clear=False, font=pfont_small)
        if itry > 3:
            remove_wifi_cred()
        time.sleep(2)
        connect_wifi(itry=itry + 1)


# app states
############################################################################################# app states
#


def save_state(state, app="livemusic"):
    state_path = STATE_PATH.format(app_string=f"_{app}" if app != "livemusic" else "")
    print(f"writing {state} to {state_path}")
    write_json(state, state_path)
    return


def load_livemusic_state(state_path):
    state = {}
    if path_exists(state_path):
        state = read_json(state_path)
        collection_list = state.get("collection_list", "GratefulDead")
        selected_date = state.get("selected_date", "1975-08-13")
        selected_collection = state.get("selected_collection", collection_list[0])
        selected_tape_id = state.get("selected_tape_id", "unknown")
        state = {
            "collection_list": collection_list,
            "selected_date": selected_date,
            "selected_collection": selected_collection,
            "selected_tape_id": selected_tape_id,
        }
    else:
        collection_list = ["GratefulDead"]
        selected_date = "1975-08-13"
        selected_collection = collection_list[0]
        selected_tape_id = "unknown"
        state = {
            "collection_list": collection_list,
            "selected_date": selected_date,
            "selected_collection": selected_collection,
            "selected_tape_id": selected_tape_id,
        }
        write_json(state, state_path)
    return state


def load_datpiff_state(state_path):
    state = {}
    if path_exists(state_path):
        state = read_json(state_path)
        artist_list = state.get("artist_list", ["2pac", "50 cent", "chief keef", "drake", "eminem", "jay-z", "lil wayne"])
        selected_tape = state.get("selected_tape", {"artist": "eminem", "title": "2", "identifier": "datpiff-mixtape-m1b32d4c"})
        artist_ind_range = state.get("artist_ind_range", {})
        state = {
            "artist_list": artist_list,
            "selected_tape": selected_tape,
            "artist_ind_range": artist_ind_range,
        }
    else:
        artist_list = ["2pac", "50 cent", "chief keef", "drake", "eminem", "jay-z", "lil wayne"]
        selected_tape = {"artist": "eminem", "title": "2", "identifier": "datpiff-mixtape-m1b32d4c"}
        artist_ind_range = {}
        state = {
            "artist_list": artist_list,
            "selected_tape": selected_tape,
            "artist_ind_range": artist_ind_range,
        }
        write_json(state, state_path)
    return state


def load_78rpm_state(state_path):
    state = {}
    if path_exists(state_path):
        state = read_json(state_path)
        date_range = state.get("date_range", [1898, 1910])
        state = {
            "date_range": date_range,
        }
    else:
        date_range = [1898, 1910]
        state = {
            "date_range": date_range,
        }
        write_json(state, state_path)
    return state


def load_state(app="livemusic"):
    state_path = STATE_PATH.format(app_string=f"_{app}" if app != "livemusic" else "")
    if app == "livemusic":
        return load_livemusic_state(state_path)
    elif app == "datpiff":
        return load_datpiff_state(state_path)
    elif app == "78rpm":
        return load_78rpm_state(state_path)
    else:
        raise NotImplementedError("Unknown app {app}")


if not isdir("/config"):
    os.mkdir("/config")
