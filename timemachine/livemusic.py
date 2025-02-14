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
import re
import time
from collections import OrderedDict
from mrequests import mrequests as requests

# import micropython # Use micropython.mem_info() to see memory available.

import archive_utils
import board as tm
import utils

import audioPlayer

# Local fonts - So that the font size can be independent of the screen size, or not.
# import fonts.DejaVu_33 as large_font
large_font = tm.large_font
import fonts.NotoSans_18 as pfont_smallx
import fonts.NotoSans_bold_18 as pfont_small
import fonts.NotoSans_24 as pfont_med
import fonts.date_font as date_font

venue_font = pfont_small


CLOUD_PATH = "https://storage.googleapis.com/spertilo-data"
API = "https://gratefuldeadtimemachine.com"  # google cloud version mapped to here
# API = "https://deadstream-api-3pqgajc26a-uc.a.run.app"  # google cloud version
# API = 'http://westmain:5000' # westmain
AUTO_PLAY = True
DATE_SET_TIME = time.ticks_ms()
COLLS_LOADED_TIME = None
CONFIG_CHOICES = ["Artists"]


# --------------------------------------------------------------- Bboxes
ycursor = 0
stage_date_bbox = tm.Bbox(0, ycursor, tm.SCREEN_WIDTH, large_font.HEIGHT)
ycursor += -2 + (7 * large_font.HEIGHT) // 8  # We never use the underhang on the staged date.
# nshows_bbox = tm.Bbox(0.9 * tm.SCREEN_WIDTH, ycursor, tm.SCREEN_WIDTH, ycursor + pfont_small.HEIGHT)
venue_bbox = tm.Bbox(0, ycursor, tm.SCREEN_WIDTH, ycursor + pfont_small.HEIGHT)
ycursor += pfont_small.HEIGHT
artist_bbox = tm.Bbox(0, ycursor, tm.SCREEN_WIDTH, ycursor + pfont_small.HEIGHT)
ycursor += pfont_small.HEIGHT
tracklist_bbox = tm.Bbox(0, ycursor, tm.SCREEN_WIDTH, tm.SCREEN_HEIGHT - (date_font.HEIGHT + 1))
ycursor = tm.SCREEN_HEIGHT - (date_font.HEIGHT + 1)
selected_date_bbox = tm.Bbox(0, ycursor, 0.91 * tm.SCREEN_WIDTH, tm.SCREEN_HEIGHT)
playpause_bbox = tm.Bbox(0.91 * tm.SCREEN_WIDTH, ycursor, tm.SCREEN_WIDTH, tm.SCREEN_HEIGHT)


def get_collection_list():
    state = utils.load_state()
    coll_list = state.get("collection_list", ["GratefulDead"])
    return coll_list


def append_to_collection_list(new_collection):
    state = utils.load_state()
    current_list = state.get("collection_list", ["GratefulDead"])
    full_list = current_list + [new_collection]
    state["collection_list"] = full_list
    utils.save_state(state)


def delete_from_collection_list(old_collection):
    state = utils.load_state()
    full_list = state.get("collection_list", ["GratefulDead"])
    full_list = [elem for elem in full_list if elem != old_collection]
    state["collection_list"] = full_list
    if len(full_list) > 0:
        utils.save_state(state)
    else:
        print("WARN tried to set collection list to empty. Bailing")


def set_collection_list(collection_list):
    state = utils.load_state()
    state["collection_list"] = collection_list
    utils.save_state(state)


def configure(choice):
    assert choice in CONFIG_CHOICES, f"{choice} not in CONFIG_CHOICES: {CONFIG_CHOICES}"

    if choice == "Artists":
        return configure_artists()
    return


def configure_artists():
    choices = ["Add Artist", "Remove Artist", "Phish Only", "Dead Only", "Other", "Cancel"]
    choice = utils.select_option("Select Option", choices)
    print(f"configure_collection: chose to {choice}")
    if choice == "Cancel":
        return

    all_collections = []
    collection_list = get_collection_list()

    print(f"current collection_list is {collection_list}")
    if choice == "Add Artist":
        tm.clear_screen()
        tm.write("Loading All Artist Names...", 0, 0, pfont_small, tm.YELLOW, show_end=-4)
        all_collections_dict = get_collection_names_dict()
        for archive in all_collections_dict.keys():
            all_collections = all_collections + all_collections_dict[archive]
        utils.add_list_element("Artist", all_collections, get_collection_list, append_to_collection_list)

    elif choice == "Remove Artist":
        utils.remove_list_element(get_collection_list, delete_from_collection_list)

    elif choice == "Phish Only":
        set_collection_list(["Phish"])
        utils.reset()
    elif choice == "Dead Only":
        set_collection_list(["GratefulDead"])
        utils.reset()
    elif choice == "Other":
        other_choices = ["Gizzard Only", "Goose Only", "Dead + Phish", "Cancel"]
        other_choice = utils.select_option("Select", other_choices)
        if other_choice == "Gizzard Only":
            set_collection_list(["KingGizzardAndTheLizardWizard"])
            utils.reset()
        if other_choice == "Goose Only":
            set_collection_list(["GooseBand"])
            utils.reset()
        elif other_choice == "Dead + Phish":
            set_collection_list(["GratefulDead", "Phish"])
            utils.reset()
        else:
            pass
    return


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
    print(f"selecting show from {key_date}. Collections {coll_dict.keys()}. Collection {collection}")
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
                    these_tape_ids = resp.json()[collection]
                    if not isinstance(these_tape_ids, (list, tuple)):
                        these_tape_ids = list(these_tape_ids)
                    tape_ids = tape_ids + these_tape_ids
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
    dt = time.localtime(time.mktime(time.gmtime()) - 6 * 3600)  # Central time
    tih_pattern = f"{dt[1]:02d}-{dt[2]:02d}"
    if len(valid_tihs) == 0:
        for d in valid_dates:
            if d[5:] == tih_pattern:
                valid_tihs.append(d)
    if len(valid_tihs) == 0:  # There are no today in history shows.
        return date
    if date >= valid_tihs[-1]:
        return valid_tihs[0]
    for d in valid_tihs:
        if d > date:
            return d
    return date


def select_key_date(key_date, player, coll_dict, state, ntape, key_collection=None):
    tm.clear_bbox(playpause_bbox)
    tm.tft.fill_polygon(tm.PausePoly, playpause_bbox.x0, playpause_bbox.y0, tm.RED)
    player.stop()
    # player.reset_player()
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
    audio_pump(player, Nmax=3)  # Try to keep buffer filled.
    update_venue(selected_vcs)
    selected_date_str = f"{int(selected_date[5:7]):2d}-{int(selected_date[8:10]):2d}-{selected_date[:4]}"
    x0 = max(0, -10 + (tm.SCREEN_WIDTH - tm.tft.write_len(date_font, "01-01-2000")) // 2)
    print(f"Writing selected date string {selected_date_str} to {x0},{selected_date_bbox.y0}.")
    tm.write(selected_date_str, x0, selected_date_bbox.y0, date_font)
    return selected_vcs, state


def play_pause(player):
    tm.clear_bbox(playpause_bbox)
    if player.is_playing():
        player.pause()
        tm.tft.fill_polygon(tm.PausePoly, playpause_bbox.x0, playpause_bbox.y0, tm.pause_color)
    elif len(player.playlist) > 0:
        player.play()
        tm.power(1)
        tm.tft.fill_polygon(tm.PlayPoly, playpause_bbox.x0, playpause_bbox.y0, tm.play_color)
    return


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
    play_pause_press_time = 0
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
    tm.label_soft_knobs("Month", "Day", "Year")
    poll_count = 0
    while True:
        nshows = 0
        buffer_fill = audio_pump(player)
        poll_count = poll_count + 1
        if player.is_playing():
            tm.screen_on_time = time.ticks_ms()
        elif time.ticks_diff(time.ticks_ms(), tm.screen_on_time) > (20 * 60_000):
            tm.power(0)

        if pPlayPause_old != tm.pPlayPause.value():
            pPlayPause_old = tm.pPlayPause.value()
            if pPlayPause_old:
                print("PlayPause RELEASED")
                if (player.is_stopped()) and (player.current_track is None):
                    if (key_date in valid_dates) and tm.power():
                        selected_vcs, state = select_key_date(key_date, player, coll_dict, state, ntape)
                        selected_date = state["selected_date"]
                        collection = state["selected_collection"]
                        vcs = selected_vcs
                        gc.collect()
                play_pause(player)
            else:
                play_pause_press_time = time.ticks_ms()
                print("PlayPause PRESSED")

        if not tm.pPlayPause.value():  # long press PlayPause
            if (time.ticks_ms() - play_pause_press_time) > 5_000:
                print("                 Longpress of play_pause")  # Choose a random date
                player.stop()
                player.current_track = None
                play_pause_press_time = time.ticks_ms() + 5_000
                key_date = set_date(utils.deal_n(valid_dates, 1)[0])
        if pStop_old != tm.pStop.value():
            pStop_old = tm.pStop.value()
            if pStop_old:
                print("Stop DOWN")
            else:
                if tm.power():
                    tm.screen_on()
                    if player.stop():
                        tm.clear_bbox(playpause_bbox)
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
                    if tm.screen_state():
                        player.rewind()
                    else:
                        player.set_volume(max(player.get_volume() - 1, 5))
                        print(f"volume set to {player.get_volume()}")

        if pFFwd_old != tm.pFFwd.value():
            pFFwd_old = tm.pFFwd.value()
            if pFFwd_old:
                print("FFwd DOWN")
            else:
                print("FFwd UP")
                if player.is_playing() or (resume_playing > 0):
                    resume_playing = time.ticks_ms() + resume_playing_delay
                if tm.power():
                    if tm.screen_state():
                        player.ffwd()
                    else:
                        try:
                            player.set_volume(player.get_volume() + 1)
                        except AssertionError:
                            pass
                        print(f"volume set to {player.get_volume()}")

        # set the knobs to the most recently selected date after 20 seconds of inaction
        if (key_date != selected_date) and (time.ticks_diff(time.ticks_ms(), DATE_SET_TIME) > 20_000):
            print(f"setting key_date to {selected_date}")
            key_date = set_date(selected_date)

        if pSelect_old != tm.pSelect.value():
            pSelect_old = tm.pSelect.value()
            if pSelect_old:
                print("short press of select")
                print(f"key {key_date}, selected {selected_date}, Collection {collection}. stopped {player.is_stopped()}")
                if (key_date == selected_date) and (not player.is_stopped()):  # We're already on this date
                    if state.get("selected_collection", collection) == collection:
                        # Display the tape_id in the vcs bbox.
                        tape_id = short_tape_id(utils.get_tape_id())
                        print(f"tape_id is {utils.get_tape_id()}, or {tape_id}")
                        tm.clear_bbox(venue_bbox)
                        tm.write(f"{tape_id}", venue_bbox.x0, venue_bbox.y0, venue_font, tm.stage_date_color)
                        software_version = utils.get_software_version()
                        dev_flag = "dev" if utils.is_dev_box() else ""
                        tm.clear_bbox(artist_bbox)
                        tm.write(
                            f"{software_version} {dev_flag}",
                            artist_bbox.x0,
                            artist_bbox.y0,
                            pfont_smallx,
                            tm.stage_date_color,
                            show_end=1,
                        )
                elif (key_date in valid_dates) and tm.power():
                    player.stop()
                    # player.reset_player()
                    selected_vcs, state = select_key_date(key_date, player, coll_dict, state, ntape, collection)
                    selected_date = state["selected_date"]
                    collection = state["selected_collection"]
                    selected_tape_id = state["selected_tape_id"]
                    vcs = selected_vcs
                    if AUTO_PLAY:
                        gc.collect()
                        play_pause(player)
                print("Select RELEASED")
            else:
                select_press_time = time.ticks_ms()
                print("Select PRESSED")

        if not tm.pSelect.value():  # long press Select
            if (time.ticks_ms() - select_press_time) > 1_000:
                player.stop()
                print("                 Longpress of select")
                select_press_time = time.ticks_ms() + 1_000
                if ntape == 0:
                    tape_ids = get_tape_ids(coll_dict, key_date)
                if len(tape_ids) == 0:
                    continue
                tm.clear_bbox(venue_bbox)
                display_str = short_tape_id(tape_ids[ntape][1])
                print(f"display string is {display_str}")
                tm.write(f"{display_str}", venue_bbox.x0, venue_bbox.y0, venue_font, tm.stage_date_color)

                print(f"tape_ids are {tape_ids}, length {len(tape_ids)}. ntape now is {ntape}")
                ntape = (ntape + 1) % len(tape_ids)
                tm.clear_bbox(artist_bbox)
                collection = tape_ids[ntape][0]
                x0 = max((tm.SCREEN_WIDTH - tm.tft.write_len(pfont_small, f"{collection}")) // 2, 0)
                tm.write(f"{collection}", x0, artist_bbox.y0, pfont_small, tm.stage_date_color)
                # vcs = coll_dict[collection][key_date]
                print(f"Select LONG_PRESS values is {tm.pSelect.value()}. ntape = {ntape}")

        if pPower_old != tm.pPower.value():
            # Press of Power button
            pPower_old = tm.pPower.value()
            if pPower_old:
                print("Power DOWN")
            else:
                print(f"power state is {tm.power()}")
                if tm.power() == 1:  # power off
                    key_date = set_date(selected_date)
                    year_new = year_old = tm.y._value
                    month_new = month_old = tm.m._value
                    day_new = day_old = tm.d._value
                    player.pause()
                    tm.power(0)
                else:  # power back on.
                    if refresh_meta_needed():
                        coll_dict = get_coll_dict(state["collection_list"])
                    tm.power(1)
                power_press_time = time.ticks_ms()
                print("Power UP -- screen")

        if not tm.pPower.value():
            if (time.ticks_ms() - power_press_time) > 1_250:
                power_press_time = time.ticks_ms()
                print("Power UP -- back to reconfigure")
                tm.label_soft_knobs("-", "-", "-")
                tm.clear_screen()
                tm.write("Configure Time Machine", 0, 0, pfont_med, tm.WHITE, show_end=-3)
                player.reset_player(reset_head=False)
                tm.power(1)
                return

        vcs_line = ((time.ticks_ms() - select_press_time) // 12_000) % (1 + len(selected_vcs) // 16)
        if (vcs == selected_vcs) & (vcs_line != pvcs_line):
            pvcs_line = vcs_line
            tm.clear_bbox(venue_bbox)
            startchar = min(15 * vcs_line, len(selected_vcs) - 16)
            audio_pump(player, Nmax=3)  # Try to keep buffer filled.
            tm.write(f"{selected_vcs[startchar:]}", venue_bbox.x0, venue_bbox.y0, venue_font, tm.stage_date_color)
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
                tm.screen_off()  # screen off while playing
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
                audio_pump(player, Nmax=3)  # Try to keep buffer filled.
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
                tm.clear_bbox(stage_date_bbox)
                tm.tft.write(large_font, f"{date_new}", 0, 0, tm.stage_date_color)
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
                    audio_pump(player, Nmax=3)  # Try to keep buffer filled.
                    update_venue(vcs, nshows=nshows, collection=collection)
                except KeyError:
                    tm.clear_bbox(venue_bbox)
                    tm.clear_bbox(artist_bbox)
                    x0 = max((tm.SCREEN_WIDTH - tm.tft.write_len(pfont_small, f"{current_collection}")) // 2, 0)
                    tm.write(f"{current_collection}", x0, artist_bbox.y0, pfont_small, tm.stage_date_color)
                    update_display(player)
        audio_pump(player, Nmax=3)  # Try to keep buffer filled.


def short_tape_id(tape_id, max_chars=16):
    display_str = re.sub(r"\d\d\d\d-\d\d-\d\d\.*", "~", tape_id)
    display_str = re.sub(r"\d\d-\d\d-\d\d\.*", "~", display_str)
    if (max_chars is None) or (max_chars <= 7) or (len(display_str) <= max_chars):
        return display_str
    return f"{display_str[: max_chars - 6]}~{display_str[len(display_str) - 6 :]}"


def update_venue(vcs, nshows=1, collection=None):
    tm.clear_bbox(venue_bbox)
    tm.write(f"{vcs}", venue_bbox.x0, venue_bbox.y0, venue_font, tm.stage_date_color)
    if nshows > 1:
        x0 = tm.SCREEN_WIDTH - tm.tft.write_len(pfont_small, f" {nshows}")
        tm.write(f" {nshows}", x0, venue_bbox.y0, pfont_small, tm.nshows_color)
    if collection is not None:
        tm.clear_bbox(artist_bbox)
        x0 = max((tm.SCREEN_WIDTH - tm.tft.write_len(pfont_small, f"{collection}")) // 2, 0)
        tm.write(f"{collection}", x0, artist_bbox.y0, pfont_small, tm.stage_date_color)


def update_display(player):
    audio_pump(player, Nmax=3)  # Try to keep buffer filled.
    tm.clear_bbox(playpause_bbox)
    if player.is_stopped():
        pass
    elif player.is_playing():
        tm.tft.fill_polygon(tm.PlayPoly, playpause_bbox.x0, playpause_bbox.y0, tm.play_color)
    elif player.is_paused():
        tm.tft.fill_polygon(tm.PausePoly, playpause_bbox.x0, playpause_bbox.y0, tm.pause_color)


def display_tracks(*track_names):
    print(f"in display_tracks {track_names}")
    tm.clear_bbox(tracklist_bbox)
    max_lines, rem = divmod(tracklist_bbox.height, pfont_small.HEIGHT)
    # tracklist_bbox.y0 += rem // 2
    y0 = tracklist_bbox.y0 + (rem // 2)
    print(f"max_lines is {max_lines}. rem:{rem}. tracklist_bbox:{tracklist_bbox}")
    last_valid_str = 0
    for i in range(len(track_names)):
        if len(track_names[i]) > 0:
            last_valid_str = i
    i = 0
    text_height = pfont_small.HEIGHT
    while y0 < tracklist_bbox.y1 - text_height:
        name = track_names[i]
        name = name.strip("-> ")  # remove trailing spaces and >'s
        if i < last_valid_str and len(name) == 0:
            name = "Unknown"
        name = utils.capitalize(name.lower())
        show_end = -2 if i == 0 else 0
        color = tm.WHITE if i == 0 else tm.tracklist_color
        font = pfont_small if i == 0 else pfont_smallx
        msg = tm.write(f"{name}", 0, y0, font, color, show_end, indent=2)
        y0 += text_height * len(msg.split("\n"))
        i = i + 1
    return msg


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


def load_vcs(coll):
    data = add_vcs(coll)
    return data


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
    text_height = pfont_small.HEIGHT + 2
    text_start = pfont_med.HEIGHT + 1
    tm.tft.write(pfont_med, message, 0, 0, tm.YELLOW)
    max_lines = (tm.SCREEN_HEIGHT - text_start) // text_height
    for i, coll in enumerate(collection_list[:max_lines]):
        tm.tft.write(pfont_smallx, f"{coll}", 0, text_start + text_height * i, tm.WHITE)
    if ncoll > max_lines:
        tm.tft.write(pfont_smallx, f"...", 0, text_start + text_height * max_lines, tm.WHITE)
    time.sleep(0.1)


def test_update():
    vcs = load_vcs("GratefulDead")
    coll_dates = vcs.keys()
    min_year = tm.y._min_val
    max_year = tm.y._max_val
    min_year = min(int(min(coll_dates)[:4]), min_year)
    max_year = max(int(max(coll_dates)[:4]), max_year)
    print(f"Max year {max_year}, Min year {min_year}")
    assert (max_year - min_year) >= 29


def refresh_meta_needed():
    if COLLS_LOADED_TIME is None:
        return True
    elif time.ticks_diff(time.ticks_ms(), COLLS_LOADED_TIME) > (24 * 3600 * 1000):
        current_year = time.localtime()[0]
        max_year = tm.y._max_val
        if (current_year - max_year) < 2:
            print("We need to refresh metadata")
            return True
    else:
        return False


def get_collection_names_dict():
    all_collections_dict = archive_utils.collection_names()
    return all_collections_dict


def get_coll_dict(collection_list):
    global COLLS_LOADED_TIME
    coll_dict = OrderedDict({})
    min_year = tm.y._min_val
    max_year = tm.y._max_val
    for coll in collection_list:
        coll_dict[coll] = load_vcs(coll)
        if len(coll_dict[coll]) == 0:
            print(f"Collection {coll} is empty. No shows added")
            continue
        coll_dates = coll_dict[coll].keys()
        min_year = min(int(min(coll_dates)[:4]), min_year)
        max_year = max(int(max(coll_dates)[:4]), max_year)
        tm.y._min_val = min_year
        tm.y._max_val = max_year
    COLLS_LOADED_TIME = time.ticks_ms()
    return coll_dict


def ping_archive():
    # Verify that archive.org is up
    n = 0
    i_try = 0
    while (n == 0) and (i_try < 50):
        i_try = i_try + 1
        try:
            n = archive_utils.count_collection("GratefulDead", (1965, 1968))
        except archive_utils.ArchiveDownError:
            tm.clear_screen()
            tm.write(f"Archive.org not responding. Check status on web. Retry {i_try}", 0, 0, pfont_small, show_end=-4)
            tm.write(
                f"Press Power for config menu",
                0,
                4 * pfont_small.HEIGHT,
                pfont_small,
                tm.PURPLE,
                show_end=-2,
            )
            button = tm.poll_for_which_button({"power": tm.pPower}, timeout=30, default="None")
            if button == "power":
                tm.clear_screen()
                i_try = 100
        except Exception as e:
            raise e
    if i_try >= 50:
        return -1
    return 0


def ping_phishin():
    # Verify that phish.in is up
    raise NotImplementedError("Not Implemented")


def save_error(e):
    msg = f"{e}"
    print(msg)
    with open("/exception.log", "w") as f:
        f.write(msg)


def run():
    """run the livemusic controls"""
    try:
        tm.label_soft_knobs("-", "-", "-")
        state = utils.load_state()
        show_collections(state["collection_list"])

        tm.m._min_val = 1
        tm.m._max_val = 12
        tm.d._min_val = 1
        tm.d._max_val = 31
        coll_dict = get_coll_dict(state["collection_list"])
        print(f"Loaded collections {coll_dict.keys()}")

        # if state["collection_list"] != ["Phish"]:
        #    if ping_archive() == -1:
        #        return -1
        # else:
        # if archive_utils.ping_phishin() == -1:
        #    return -1
        player = audioPlayer.AudioPlayer(callbacks={"display": display_tracks}, debug=False)
        main_loop(player, coll_dict, state)
    except OSError as e:
        msg = f"livemusic: {e}"
        if isinstance(e, OSError) and "ECONNABORTED" in msg:
            tm.clear_screen()
            tm.write("Error at the archive", 0, 0, color=tm.YELLOW, font=pfont_med, show_end=-2)
            tm.write("Press Select to return", 0, 2 * pfont_med.HEIGHT, font=pfont_med, show_end=-2)
            if tm.poll_for_button(tm.pSelect, timeout=12 * 3600):
                run()
    except Exception as e:
        msg = f"livemusic: {e}"
        save_error(msg)
        if utils.is_dev_box():
            tm.clear_screen()
            msg = tm.write(msg, font=pfont_small, show_end=5)
            y0 = pfont_small.HEIGHT * len(msg.split("\n"))
            tm.write("Select to exit", 0, y0, color=tm.YELLOW, font=pfont_small)
            tm.poll_for_button(tm.pSelect, timeout=12 * 3600)
        else:
            utils.reset()
    return -1
