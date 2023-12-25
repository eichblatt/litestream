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

# Display driver: https://github.com/russhughes/st7789_mpy
import gc
import json
import re
import time
from collections import OrderedDict
from mrequests import mrequests as requests

# import micropython # Use micropython.mem_info() to see memory available.
import st7789
import fonts.date_font as date_font
import fonts.DejaVu_33 as large_font
import fonts.NotoSans_18 as pfont_small
import fonts.NotoSans_24 as pfont_med
import fonts.NotoSans_32 as pfont_large

import board as tm
import utils

ESP_DECODE = True
if ESP_DECODE:
    import audioPlayer
else:
    import audioPlayer_1053 as audioPlayer

# API = "https://msdocs-python-webapp-quickstart-sle.azurewebsites.net"
CLOUD_PATH = "https://storage.googleapis.com/spertilo-data"
# API = "https://deadstream-api-3pqgajc26a-uc.a.run.app"  # google cloud version
API = "https://gratefuldeadtimemachine.com"  # google cloud version mapped to here
# API = 'http://westmain:5000' # westmain
AUTO_PLAY = True
DATE_SET_TIME = time.ticks_ms()
COLL_DICT_PATH = "/coll_dict.json"
TIME_VCS_LOADED = time.localtime()
# RESET_WHILE_SLEEPING = False

stage_date_color = st7789.color565(255, 255, 0)
yellow_color = st7789.color565(255, 255, 0)
tracklist_color = st7789.color565(0, 255, 255)
play_color = st7789.color565(255, 0, 0)
nshows_color = st7789.color565(0, 100, 255)


def set_date(date):
    global DATE_SET_TIME
    tm.y._value = int(date[:4])
    tm.m._value = int(date[5:7])
    tm.d._value = int(date[8:10])
    key_date = f"{tm.y.value()}-{tm.m.value():02d}-{tm.d.value():02d}"
    DATE_SET_TIME = time.ticks_ms()
    return key_date


def best_tape(collection, key_date):
    pass


def select_date(coll_dict, key_date, ntape=0, collection=None):
    print(f"selecting show from {key_date}. Collections {coll_dict.keys()}")
    # for collection, cdict in coll_dict.items():
    if collection is None:
        valid_collections = []
        for coll in coll_dict.keys():
            if key_date in coll_dict[coll].keys():
                valid_collections.append(coll)
        collection = valid_collections[ntape % len(valid_collections)]
        ntape = ntape // len(valid_collections)

    tape_ids_url = f"{CLOUD_PATH}/tapes/{collection}/{key_date}/tape_ids.json"
    try:
        resp = requests.get(tape_ids_url)
        if resp.status_code == 200:
            tape_ids = resp.json()
            ntapes = len(tape_ids)
            selected_tape_id = tape_ids[ntape % ntapes][0]
            trackdata_url = f"{CLOUD_PATH}/tapes/{collection}/{key_date}/{selected_tape_id}/trackdata.json"
            resp = requests.get(trackdata_url)
            response = resp.json()
            collection = response["collection"]
            tracklist = response["tracklist"]
            urls = response["urls"]
        else:
            api_request = f"{API}/track_urls/{key_date}?collections={collection}&ntape={ntape}"
            print(f"API request is {api_request}")
            resp = requests.get(api_request)
            response = resp.json()
            collection = response["collection"]
            tracklist = response["tracklist"]
            urls = response["urls"]
            selected_tape_id = response.get("tape_id", "unknown")
    finally:
        resp.close()
    print(f"URLs: {urls}")
    return collection, tracklist, urls, selected_tape_id


def get_tape_ids(coll_dict, key_date):
    print(f"getting tape_ids from {key_date}")
    key_date_colls = []
    tape_ids = []
    for collection, cdict in coll_dict.items():
        if cdict.get(key_date, None):
            key_date_colls.append(collection)
            url = f"{CLOUD_PATH}/tapes/{collection}/{key_date}/tape_ids.json"
            print(f"URL is {url}")
            try:
                resp = None
                resp = requests.get(url)
                if resp.status_code == 200:
                    tape_ids = tape_ids + [[collection, x[0]] for x in resp.json()]
                elif resp.status_code == 404:
                    api_request = f"{API}/tape_ids/{key_date}?collections={collection}"
                    print(f"api_request is {api_request}")
                    resp = requests.get(api_request)
                    tape_ids = tape_ids + resp.json()
                else:
                    raise Exception(f"Failed to get_tape_ids for {coll_dict} on {key_date}")
            finally:
                resp.close() if resp is not None else None
    sorted_tape_ids = []
    while len(tape_ids) > 0:
        for coll in coll_dict.keys():
            for iid, id in enumerate(tape_ids):
                if id[0] == coll:
                    sorted_tape_ids.append(tape_ids.pop(iid))
                    break
    return sorted_tape_ids


def get_next_tih(date, valid_dates, valid_tihs=[]):
    dt = time.localtime()
    tih_pattern = f"{dt[1]:02d}-{dt[2]:02d}"
    if len(valid_tihs) == 0:
        for d in valid_dates:
            if d[5:] == tih_pattern:
                valid_tihs.append(d)
    if date == valid_tihs[-1]:
        return valid_tihs[0]
    for d in valid_tihs:
        if d > date:
            return d
    return date


def select_key_date(key_date, player, coll_dict, state, ntape, key_collection=None):
    tm.clear_bbox(tm.playpause_bbox)
    tm.tft.fill_polygon(tm.PausePoly, tm.playpause_bbox.x0, tm.playpause_bbox.y0, st7789.RED)
    player.stop()
    collection, tracklist, urls, selected_tape_id = select_date(coll_dict, key_date, ntape, key_collection)
    vcs = coll_dict[collection][key_date]
    player.set_playlist(tracklist, urls)
    ntape = 0

    selected_date = key_date
    state["selected_date"] = selected_date
    state["selected_collection"] = collection
    state["selected_tape_id"] = selected_tape_id
    utils.save_state(state)
    selected_vcs = vcs
    update_venue(selected_vcs)
    selected_date_str = f"{int(selected_date[5:7]):2d}-{int(selected_date[8:10]):2d}-{selected_date[:4]}"
    print(f"Selected date string {selected_date_str}")
    tm.tft.write(date_font, selected_date_str, tm.selected_date_bbox.x0, tm.selected_date_bbox.y0)
    return selected_vcs, state


def play_pause(player):
    tm.clear_bbox(tm.playpause_bbox)
    if player.is_playing():
        player.pause()
        tm.tft.fill_polygon(tm.PausePoly, tm.playpause_bbox.x0, tm.playpause_bbox.y0, st7789.WHITE)
    else:  # initial state or stopped
        player.play()
        tm.power(1)
        tm.tft.fill_polygon(tm.PlayPoly, tm.playpause_bbox.x0, tm.playpause_bbox.y0, play_color)
    return player.PLAY_STATE


@micropython.native
def get_next_show(key_date, valid_dates, coll_name, coll_dict):
    coll_names = list(coll_dict.keys())
    if not (coll_name in coll_names):
        coll_name = coll_names[0]
    print(f"getting next show {key_date}, {coll_name}")
    c_index = coll_names.index(coll_name)

    start_index = 0
    for i, date in enumerate(valid_dates):
        if date >= key_date:
            start_index = i
            break
    print(f"start_index {start_index}/{len(valid_dates)-1}")
    for i, date in enumerate(valid_dates[start_index:] + valid_dates[:start_index]):
        if (i == 0) and ((c_index + 1) < len(coll_names)):
            for c in coll_names[c_index + 1 :]:
                if date in coll_dict[c].keys():
                    return date, c
        elif i > 0:
            for c in coll_names:
                if date in coll_dict[c].keys():
                    return date, c
    return key_date, coll_name


def audio_pump(player, Nmax=1, fill_level=0.95):
    player.audio_pump()
    # ipump = 1
    # buffer_level = player.audio_pump()
    # while (buffer_level < fill_level) and ipump < Nmax:
    #    ipump += 1
    #    buffer_level = player.audio_pump()
    # return buffer_level


def main_loop(player, coll_dict, state):
    year_old = -1
    month_old = -1
    day_old = -1
    date_old = ""
    pPower_old = 0
    pSelect_old = pPlayPause_old = pStop_old = pRewind_old = pFFwd_old = 1
    pYSw_old = pMSw_old = pDSw_old = 1
    key_date = set_date(state["selected_date"])
    collection = state["selected_collection"]
    selected_date = key_date
    collections = list(coll_dict.keys())
    current_collection = ""
    vcs = selected_vcs = ""
    pvcs_line = 0
    select_press_time = 0
    date_changed_time = 0
    power_press_time = 0
    resume_playing = -1
    resume_playing_delay = 500
    ntape = 0
    valid_dates = set()
    for c in collections:
        valid_dates = valid_dates | set(list(coll_dict[c].keys()))
    del c
    valid_dates = sorted(list(valid_dates))
    tm.screen_on_time = time.ticks_ms()
    tm.clear_screen()
    poll_count = 0
    while True:
        nshows = 0
        buffer_fill = audio_pump(player)
        poll_count = poll_count + 1
        # if player.is_playing() and (poll_count % 5 != 0):  # throttle the polling, to pump more often.
        #     continue
        if player.is_playing():
            tm.screen_on_time = time.ticks_ms()
        elif time.ticks_diff(time.ticks_ms(), tm.screen_on_time) > (20 * 60_000):
            tm.power(0)
            # if (
            #     player.PLAY_STATE == player.STOPPED
            #     and RESET_WHILE_SLEEPING
            #     and (DATE_SET_TIME < tm.screen_on_time)  # This machine has been played since bootup.
            #     and time.ticks_diff(time.ticks_ms(), tm.screen_on_time) > (4 * 3600_000)
            # ):
            #     print("Rebooting Machine proactively, since it hasn't played in 4 hours")
            #    import machine
            #    machine.reset()

        if pPlayPause_old != tm.pPlayPause.value():
            pPlayPause_old = tm.pPlayPause.value()
            if pPlayPause_old:
                print("PlayPause DOWN")
            else:
                if (player.PLAY_STATE == player.STOPPED) and (player.current_track == 0):
                    if (key_date in valid_dates) and tm.power():
                        selected_vcs, state = select_key_date(key_date, player, coll_dict, state, ntape)
                        selected_date = state["selected_date"]
                        collection = state["selected_collection"]
                        selected_tape_id = state["selected_tape_id"]
                        vcs = selected_vcs
                play_pause(player)
                print("PlayPause UP")

        if pStop_old != tm.pStop.value():
            pStop_old = tm.pStop.value()
            if pStop_old:
                print("Stop DOWN")
            else:
                if tm.power():
                    player.stop()
                    tm.tft.on()
                    tm.tft.fill_polygon(tm.StopPoly, tm.playpause_bbox.x0, tm.playpause_bbox.y0, play_color)
                print("Stop UP")

        buffer_fill = audio_pump(player, fill_level=0.3)
        # buffer_fill = player.audio_pump()

        if player.is_stopped() and (resume_playing > 0) and (time.ticks_ms() >= resume_playing):
            print("Resuming playing")
            resume_playing = -1
            player.play()

        if pRewind_old != tm.pRewind.value():
            pRewind_old = tm.pRewind.value()
            if pRewind_old:
                print("Rewind DOWN")
            else:
                print("Rewind UP")
                if player.is_playing() or (resume_playing > 0):
                    resume_playing = time.ticks_ms() + resume_playing_delay
                if tm.power():
                    player.rewind()
                    tm.tft.on()

        if pFFwd_old != tm.pFFwd.value():
            pFFwd_old = tm.pFFwd.value()
            if pFFwd_old:
                print("FFwd DOWN")
            else:
                print("FFwd UP")
                if player.is_playing() or (resume_playing > 0):
                    resume_playing = time.ticks_ms() + resume_playing_delay
                if tm.power():
                    player.ffwd()
                    tm.tft.on()

        # set the knobs to the most recently selected date after 20 seconds of inaction
        if (key_date != selected_date) and (time.ticks_diff(time.ticks_ms(), DATE_SET_TIME) > 20_000):
            print(f"setting key_date to {selected_date}")
            key_date = set_date(selected_date)

        if pSelect_old != tm.pSelect.value():
            pSelect_old = tm.pSelect.value()
            if pSelect_old:
                print("short press of select")
                if (key_date == selected_date) and (player.PLAY_STATE != player.STOPPED):  # We're already on this date
                    if state.get("selected_collection", collection) == collection:
                        # Display the tape_id in the vcs bbox.
                        tape_id = short_tape_id(utils.get_tape_id())
                        print(f"tape_id is {utils.get_tape_id()}, or {tape_id}")
                        tm.clear_bbox(tm.venue_bbox)
                        tm.tft.write(pfont_small, f"{tape_id}", tm.venue_bbox.x0, tm.venue_bbox.y0, stage_date_color)
                        pass
                elif (key_date in valid_dates) and tm.power():
                    player.stop()
                    selected_vcs, state = select_key_date(key_date, player, coll_dict, state, ntape, collection)
                    selected_date = state["selected_date"]
                    collection = state["selected_collection"]
                    selected_tape_id = state["selected_tape_id"]
                    vcs = selected_vcs
                    if AUTO_PLAY:
                        gc.collect()
                        play_pause(player)
                print("Select UP")
            else:
                select_press_time = time.ticks_ms()
                print("Select DOWN")

        if not tm.pSelect.value():  # long press Select
            if (time.ticks_ms() - select_press_time) > 1_000:
                print("                 Longpress of select")
                select_press_time = time.ticks_ms() + 1_000
                if ntape == 0:
                    tape_ids = get_tape_ids(coll_dict, key_date)
                print(f"tape_ids are {tape_ids}, length {len(tape_ids)}. ntape now is {ntape}")
                ntape = (ntape + 1) % len(tape_ids)
                tm.clear_bbox(tm.artist_bbox)
                tm.tft.write(pfont_small, f"{tape_ids[ntape][0]}", tm.artist_bbox.x0, tm.artist_bbox.y0, stage_date_color)
                # vcs = coll_dict[tape_ids[ntape][0]][key_date]
                tm.clear_bbox(tm.venue_bbox)
                display_str = short_tape_id(tape_ids[ntape][1])
                print(f"display string is {display_str}")
                tm.tft.write(pfont_small, f"{display_str}", tm.venue_bbox.x0, tm.venue_bbox.y0, stage_date_color)
                print(f"Select LONG_PRESS values is {tm.pSelect.value()}. ntape = {ntape}")

        if pPower_old != tm.pPower.value():
            # Press of Power button
            pPower_old = tm.pPower.value()
            if pPower_old:
                print("Power DOWN")
            else:
                print(f"power state is {tm.power()}")
                if tm.power() == 1:
                    key_date = set_date(selected_date)
                    year_new = year_old = tm.y._value
                    month_new = month_old = tm.m._value
                    day_new = day_old = tm.d._value
                    player.pause()
                    tm.power(0)
                else:
                    tm.power(1)
                power_press_time = time.ticks_ms()
                print("Power UP -- screen")

        if not tm.pPower.value():
            if (time.ticks_ms() - power_press_time) > 2_500:
                power_press_time = time.ticks_ms()
                print("Power UP -- back to reconfigure")
                tm.clear_screen()
                tm.tft.off()
                # time.sleep(2)
                return

        vcs_line = ((time.ticks_ms() - select_press_time) // 12_000) % (1 + len(selected_vcs) // 16)
        if (vcs == selected_vcs) & (vcs_line != pvcs_line):
            pvcs_line = vcs_line
            tm.clear_bbox(tm.venue_bbox)
            startchar = min(15 * vcs_line, len(selected_vcs) - 16)
            tm.tft.write(pfont_small, f"{selected_vcs[startchar:]}", tm.venue_bbox.x0, tm.venue_bbox.y0, stage_date_color)
            print(player)
            update_display(player)

        if pYSw_old != tm.pYSw.value():
            pYSw_old = tm.pYSw.value()
            if pYSw_old:
                print("Year DOWN")
            else:  # cycle through Today In History (once we know what today is!)
                key_date = set_date(get_next_tih(key_date, valid_dates))
                print("Year UP")

        if pMSw_old != tm.pMSw.value():
            pMSw_old = tm.pMSw.value()
            if pMSw_old:
                print("Month DOWN")
            else:
                tm.tft.off()  # screen off while playing
                print("Month UP")

        if pDSw_old != tm.pDSw.value():
            pDSw_old = tm.pDSw.value()
            if pDSw_old:
                print("Day UP")
            else:
                date, collection = get_next_show(key_date, valid_dates, collection, coll_dict)
                vcs = coll_dict[collection][date]
                key_date = set_date(date)
                print(f"vcs {vcs}. collection {collection}. date {date}")
                update_venue(vcs, collection=collection)
                # for date in valid_dates:
                #     if date > key_date:
                #        key_date = set_date(date)
                #        break
                print("Day DOWN")

        year_new = tm.y.value()
        month_new = tm.m.value()
        day_new = tm.d.value()

        if (year_old != year_new) | (month_old != month_new) | (day_old != day_new):
            tm.power(1)
            date_changed_time = time.ticks_ms()
            if (month_new in [4, 6, 9, 11]) and (day_new > 30):
                day_new = 30
            if (month_new == 2) and (day_new > 28):
                if year_new % 4 == 0:
                    day_new = min(29, day_new)
                    if (year_new % 100 == 0) and (year_new % 400 != 0):
                        day_new = min(28, day_new)
                else:
                    day_new = min(28, day_new)

            date_new = f"{month_new:2d}-{day_new:2d}-{year_new%100:02d}"
            key_date = f"{year_new}-{month_new:02d}-{day_new:02d}"
            key_date = set_date(key_date)
            if year_old != year_new:
                year_old = year_new

            if month_old != month_new:
                month_old = month_new

            if day_old != day_new:
                day_old = day_new

            if date_old != date_new:  # in case the knobs went to an invalid date and the date is still the same.
                tm.clear_bbox(tm.stage_date_bbox)
                tm.tft.write(large_font, f"{date_new}", 0, 0, stage_date_color)
                date_old = date_new
                try:
                    if key_date in valid_dates:
                        nshows = 0
                        for c in list(coll_dict.keys()):
                            if key_date in coll_dict[c].keys():
                                collection = c if nshows == 0 else collection
                                nshows += 1
                        vcs = coll_dict[collection][f"{key_date}"]
                    else:
                        vcs = ""
                        collection = ""
                    update_venue(vcs, nshows=nshows, collection=collection)
                except KeyError:
                    tm.clear_bbox(tm.venue_bbox)
                    tm.clear_bbox(tm.artist_bbox)
                    tm.tft.write(pfont_small, f"{current_collection}", tm.artist_bbox.x0, tm.artist_bbox.y0, stage_date_color)
                    update_display(player)
        audio_pump(player, Nmax=3)  # Try to keep buffer filled.


def short_tape_id(tape_id, max_chars=16):
    display_str = re.sub(r"\d\d\d\d-\d\d-\d\d\.*", "~", tape_id)
    display_str = re.sub(r"\d\d-\d\d-\d\d\.*", "~", display_str)
    if (max_chars is None) or (max_chars <= 7) or (len(display_str) <= max_chars):
        return display_str
    return f"{display_str[: max_chars - 6]}~{display_str[len(display_str) - 6 :]}"


def update_venue(vcs, nshows=1, collection=None):
    tm.clear_bbox(tm.venue_bbox)
    tm.tft.write(pfont_small, f"{vcs}", tm.venue_bbox.x0, tm.venue_bbox.y0, stage_date_color)
    tm.clear_bbox(tm.nshows_bbox)
    if nshows > 1:
        tm.tft.write(pfont_small, f"{nshows}", tm.nshows_bbox.x0, tm.nshows_bbox.y0, nshows_color)
    if collection is not None:
        tm.clear_bbox(tm.artist_bbox)
        tm.tft.write(pfont_small, f"{collection}", tm.artist_bbox.x0, tm.artist_bbox.y0, stage_date_color)


def update_display(player):
    # display_tracks(*player.track_names())
    tm.clear_bbox(tm.playpause_bbox)
    if not player.playlist_started:
        pass
    elif player.PLAY_STATE == player.STOPPED:
        tm.tft.fill_polygon(tm.StopPoly, tm.playpause_bbox.x0, tm.playpause_bbox.y0, play_color)
    elif player.PLAY_STATE == player.PLAYING:
        tm.tft.fill_polygon(tm.PlayPoly, tm.playpause_bbox.x0, tm.playpause_bbox.y0, play_color)
    elif player.PLAY_STATE == player.PAUSED:
        tm.tft.fill_polygon(tm.PausePoly, tm.playpause_bbox.x0, tm.playpause_bbox.y0, st7789.WHITE)


def display_tracks(current_track_name, next_track_name):
    tm.init_screen()  # Do we need this if not sharing SPI bus?
    tm.clear_bbox(tm.tracklist_bbox)
    tm.tft.write(pfont_small, f"{current_track_name}", tm.tracklist_bbox.x0, tm.tracklist_bbox.y0, tracklist_color)
    tm.tft.write(pfont_small, f"{next_track_name}", tm.tracklist_bbox.x0, tm.tracklist_bbox.center()[1], tracklist_color)
    return


def add_vcs(coll):
    print(f"Adding vcs for coll {coll}")
    vcs_url = f"{CLOUD_PATH}/vcs/{coll}_vcs.json"
    print(vcs_url)
    resp = None
    try:
        resp = requests.get(vcs_url)
        if resp.status_code == 200:
            vcs = resp.json()
        else:
            print(f"status was {resp.status_code}")
            api_request = f"{API}/vcs/{coll}"
            print(f"API request is {api_request}")
            resp = requests.get(api_request)
            vcs = resp.json()[coll]
    finally:
        if resp is not None:
            resp.close()
    return vcs


def load_vcs(coll, max_cache_days=10000):
    global TIME_VCS_LOADED
    try:
        with open(COLL_DICT_PATH, "r") as f:
            coll_dict_loaded = json.load(f)
        TIME_VCS_LOADED = coll_dict_loaded["time_saved"]
        if (time.time() - time.mktime(TIME_VCS_LOADED)) < 3600 * 24 * max_cache_days:
            data = coll_dict_loaded[coll]
            print(f"loaded vcs data for {coll} from {COLL_DICT_PATH}")
            return data
        else:
            raise Exception(f"VCS File Out of Date")
    except Exception as e:
        print(f"Exception in load_vcs({coll}): {e}")
        data = add_vcs(coll)
        TIME_VCS_LOADED = time.localtime()
    return data


def save_coll_dict(coll_dict):
    coll_dict["time_saved"] = TIME_VCS_LOADED
    try:
        with open(COLL_DICT_PATH, "w") as f:
            json.dump(coll_dict, f)
            print(f"coll_dict saved to {COLL_DICT_PATH}")
        del coll_dict["time_saved"]
    except Exception as e:
        print(e)
        utils.remove_file(COLL_DICT_PATH)


def lookup_date(d, col_d):
    response = []
    for col, data in col_d.items():
        if d in data.keys():
            response.append([col, data[d]])
    return response


def show_collections(collection_list):
    ncoll = len(collection_list)
    message = f"Loading {ncoll} Collections"
    print(message)
    tm.clear_screen()
    tm.tft.write(pfont_med, message, 0, 0, st7789.RED)
    for i, coll in enumerate(collection_list[:5]):
        tm.tft.write(pfont_small, f"{coll}", 0, 25 + 20 * i, st7789.WHITE)
    if ncoll > 5:
        tm.tft.write(pfont_small, f"...", 0, 25 + 20 * 5, st7789.WHITE)
    time.sleep(1)


def test_update():
    vcs = load_vcs("GratefulDead")
    coll_dates = vcs.keys()
    min_year = tm.y._min_val
    max_year = tm.y._max_val
    min_year = min(int(min(coll_dates)[:4]), min_year)
    max_year = max(int(max(coll_dates)[:4]), max_year)
    print(f"Max year {max_year}, Min year {min_year}")
    assert (max_year - min_year) >= 29


def get_coll_dict(collection_list):
    coll_dict = OrderedDict({})
    min_year = tm.y._min_val
    max_year = tm.y._max_val
    for coll in collection_list:
        coll_dict[coll] = load_vcs(coll)
        coll_dates = coll_dict[coll].keys()
        min_year = min(int(min(coll_dates)[:4]), min_year)
        max_year = max(int(max(coll_dates)[:4]), max_year)
        tm.y._min_val = min_year
        tm.y._max_val = max_year
    save_coll_dict(coll_dict)
    return coll_dict


def run():
    """run the livemusic controls"""
    state = utils.load_state()
    show_collections(state["collection_list"])

    coll_dict = get_coll_dict(state["collection_list"])
    print(f"Loaded collections {coll_dict.keys()}")
    player = audioPlayer.AudioPlayer(callbacks={"display": display_tracks}, debug=False)
    try:
        main_loop(player, coll_dict, state)
    except Exception as e:
        msg = f"Error in playback loop {e}"
        print(msg)
        tm.write("".join(msg[i : i + 16] + "\n" for i in range(0, len(msg), 16)), font=pfont_small)
        tm.write("Select to exit", 0, 100, color=yellow_color, font=pfont_small, clear=False)
        tm.poll_for_button(tm.pSelect, timeout=12 * 3600)
    return -1
