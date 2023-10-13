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
import json
import os
import re
import network
import sys
import time
from collections import OrderedDict
from mrequests import mrequests as requests

import machine
import st7789
import fonts.date_font as date_font
import fonts.DejaVu_33 as large_font
import fonts.NotoSans_18 as pfont_small
import fonts.NotoSans_24 as pfont_med
import fonts.NotoSans_32 as pfont_large
from machine import SPI, Pin
from rotary_irq_esp import RotaryIRQ
import network

import board as tm
import utils

ESP_DECODE = True
FORMAT = "ogg"
if ESP_DECODE:
    import audioPlayer
else:
    import audioPlayer_1053 as audioPlayer

# API = "https://msdocs-python-webapp-quickstart-sle.azurewebsites.net"
CLOUD_PATH = "https://storage.googleapis.com/spertilo-data"
API = "https://able-folio-397115.ue.r.appspot.com"  # google cloud version
# API = 'http://westmain:5000' # westmain
COLLECTION_LIST_PATH = "collection_list.json"
AUTO_PLAY = False


def set_date(date):
    tm.y._value = int(date[:4])
    tm.m._value = int(date[5:7])
    tm.d._value = int(date[8:10])
    key_date = f"{tm.y.value()}-{tm.m.value():02d}-{tm.d.value():02d}"
    return key_date


def best_tape(collection, key_date):
    pass


def select_date(coll_dict, key_date, ntape=0):
    print(f"selecting show from {key_date}. Collections {coll_dict.keys()}")
    # for collection, cdict in coll_dict.items():
    for collection in coll_dict.keys():
        if key_date in coll_dict[collection].keys():
            break

    tape_ids_url = f"{CLOUD_PATH}/tapes/{collection}/{key_date}/tape_ids.json"
    resp = requests.get(tape_ids_url)
    if resp.status_code == 200:
        tape_ids = resp.json()
        ntapes = len(tape_ids)
        selected_tape = tape_ids[ntape % ntapes][0]
        trackdata_url = f"{CLOUD_PATH}/tapes/{collection}/{key_date}/{selected_tape}/trackdata.json"
        resp = requests.get(trackdata_url).json()
        collection = resp["collection"]
        tracklist = resp["tracklist"]
        urls = resp["urls"]
    else:
        api_request = f"{API}/tracklist/{key_date}?collections={collection}&ntape={ntape}"
        print(f"API request is {api_request}")
        resp = requests.get(api_request).json()
        collection = resp["collection"]
        tracklist = resp["tracklist"]
        api_request = f"{API}/urls/{key_date}?collections={collection}&ntape={ntape}"
        print(f"API request is {api_request}")
        resp = requests.get(api_request).json()
        urls = resp["urls"]
    if FORMAT == "mp3":
        urls = [x.replace(".ogg", ".mp3") for x in urls]
    print(f"URLs: {urls}")
    return collection, tracklist, urls


def get_tape_ids(coll_dict, key_date):
    print(f"getting tape_ids from {key_date}")
    key_date_colls = []
    for collection, cdict in coll_dict.items():
        if cdict.get(key_date, None):
            key_date_colls.append(collection)
            url = f"{CLOUD_PATH}/tapes/{collection}/{key_date}/tape_ids.json"
            resp = requests.get(url)
            if resp.status_code == 200:
                tape_ids = [[collection, x[0]] for x in resp.json()]
            elif resp.status_code == 404:
                api_request = f"{API}/tape_ids/{key_date}?collections={collection}"
                tape_ids = requests.get(api_request).json()
            else:
                raise Exception(f"Failed to get_tape_ids for {coll_dict} on {key_date}")
    sorted_tape_ids = []
    while len(tape_ids) > 0:
        for coll in coll_dict.keys():
            for iid, id in enumerate(tape_ids):
                if id[0] == coll:
                    sorted_tape_ids.append(tape_ids.pop(iid))
                    break
    return sorted_tape_ids


def get_next_tih(date, valid_dates, valid_tihs=[]):
    print("Getting next Today In History date")
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


stage_date_bbox = utils.Bbox(0, 0, 160, 32)
nshows_bbox = utils.Bbox(150, 32, 160, 48)
venue_bbox = utils.Bbox(0, 32, 160, 32 + 20)
artist_bbox = utils.Bbox(0, 52, 160, 52 + 20)
tracklist_bbox = utils.Bbox(0, 72, 160, 112)
selected_date_bbox = utils.Bbox(15, 112, 145, 128)
playpause_bbox = utils.Bbox(145, 113, 160, 128)

stage_date_color = st7789.color565(255, 255, 0)
yellow_color = st7789.color565(255, 255, 0)
tracklist_color = st7789.color565(0, 255, 255)
play_color = st7789.color565(255, 0, 0)
nshows_color = st7789.color565(0, 100, 255)


def update_display(player):
    utils.init_screen()
    display_tracks(*player.track_names())
    if not player.playlist_started:
        utils.clear_bbox(playpause_bbox)
    elif player.PLAY_STATE == player.STOPPED:
        tm.tft.fill_polygon(tm.StopPoly, playpause_bbox.x0, playpause_bbox.y0, play_color)
    elif player.PLAY_STATE == player.PLAYING:
        tm.tft.fill_polygon(tm.PlayPoly, playpause_bbox.x0, playpause_bbox.y0, play_color)
    elif player.PLAY_STATE == player.PAUSED:
        tm.tft.fill_polygon(tm.PausePoly, playpause_bbox.x0, playpause_bbox.y0, st7789.WHITE)


def display_tracks(current_track_name, next_track_name):
    utils.init_screen()
    utils.clear_bbox(tracklist_bbox)
    tm.tft.write(pfont_small, f"{current_track_name}", tracklist_bbox.x0, tracklist_bbox.y0, tracklist_color)
    tm.tft.write(pfont_small, f"{next_track_name}", tracklist_bbox.x0, tracklist_bbox.center()[1], tracklist_color)
    return


def play_pause(player):
    utils.init_screen()
    utils.clear_bbox(playpause_bbox)
    if player.is_playing():
        player.pause()
        tm.tft.fill_polygon(tm.PausePoly, playpause_bbox.x0, playpause_bbox.y0, st7789.WHITE)
    else:  # initial state or stopped
        player.play()
        tm.tft.fill_polygon(tm.PlayPoly, playpause_bbox.x0, playpause_bbox.y0, play_color)
    return player.PLAY_STATE


def audio_pump(player, Nmax=1, fill_level=0.95):
    ipump = 1
    buffer_level = player.audio_pump()
    while (buffer_level < fill_level) and ipump < Nmax:
        ipump += 1
        buffer_level = player.audio_pump()
    return buffer_level


def main_loop(player, coll_dict):
    year_old = -1
    month_old = -1
    day_old = -1
    date_old = ""
    PowerLED = 1
    pPower_old = 0
    pSelect_old = pPlayPause_old = pStop_old = pRewind_old = pFFwd_old = 1
    pYSw_old = pMSw_old = pDSw_old = 1
    key_date = set_date("1975-08-13")
    selected_date = key_date
    collection = "GratefulDead"
    tracklist = []
    urls = []
    collections = list(coll_dict.keys())
    current_collection = ""
    vcs = selected_vcs = ""
    pvcs_line = 0
    select_press_time = 0
    power_press_time = 0
    stop_press_time = 0
    resume_playing = -1
    resume_playing_delay = 500
    ntape = 0
    valid_dates = set()
    for c in collections:
        valid_dates = valid_dates | set(list(coll_dict[c].keys()))
    del c
    valid_dates = list(sorted(valid_dates))
    utils.clear_screen()

    poll_count = 0
    while True:
        nshows = 0
        buffer_fill = audio_pump(player)
        poll_count = poll_count + 1
        # if player.is_playing() and (poll_count % 5 != 0):  # throttle the polling, to pump more often.
        #     continue

        if pPlayPause_old != tm.pPlayPause.value():
            pPlayPause_old = tm.pPlayPause.value()
            if pPlayPause_old:
                print("PlayPause DOWN")
            else:
                play_pause(player)
                print("PlayPause UP")

        if pStop_old != tm.pStop.value():
            pStop_old = tm.pStop.value()
            if pStop_old:
                print("Stop DOWN")
            else:
                player.stop()
                utils.init_screen()
                tm.tft.fill_polygon(tm.StopPoly, playpause_bbox.x0, playpause_bbox.y0, play_color)
                stop_press_time = time.ticks_ms()
                print("Stop UP")

        if not tm.pStop.value():
            if (time.ticks_ms() - stop_press_time) > 1_500:
                stop_press_time = time.ticks_ms()
                print("Power UP -- back to reconfigure")
                utils.clear_screen()
                tm.tft.off()
                time.sleep(2)
                # sys.exit()
                return

        # Throttle Downstream polling
        # if (player.is_playing()) and (poll_count % 10 != 0):
        #    continue
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
                player.rewind()

        if pFFwd_old != tm.pFFwd.value():
            pFFwd_old = tm.pFFwd.value()
            if pFFwd_old:
                print("FFwd DOWN")
            else:
                print("FFwd UP")
                if player.is_playing() or (resume_playing > 0):
                    resume_playing = time.ticks_ms() + resume_playing_delay
                player.ffwd()

        if pSelect_old != tm.pSelect.value():
            pSelect_old = tm.pSelect.value()
            if pSelect_old:
                print("short press of select")
                if (key_date == selected_date) and (player.PLAY_STATE != player.STOPPED):  # We're already on this date
                    pass
                elif key_date in valid_dates:
                    utils.init_screen()
                    tm.tft.fill_polygon(tm.PausePoly, playpause_bbox.x0, playpause_bbox.y0, st7789.RED)
                    collection, tracklist, urls = select_date(coll_dict, key_date, ntape)
                    vcs = coll_dict[collection][key_date]
                    player.stop(reset_head=False)
                    player.set_playlist(tracklist, urls)
                    ntape = 0

                    selected_date = key_date
                    selected_vcs = vcs
                    utils.clear_bbox(venue_bbox)
                    utils.clear_bbox(playpause_bbox)
                    tm.tft.write(pfont_small, f"{selected_vcs}", venue_bbox.x0, venue_bbox.y0, stage_date_color)
                    utils.clear_bbox(selected_date_bbox)
                    selected_date_str = f"{int(selected_date[5:7]):2d}-{int(selected_date[8:10]):2d}-{selected_date[:4]}"
                    print(f"Selected date string {selected_date_str}")
                    tm.tft.write(date_font, selected_date_str, selected_date_bbox.x0, selected_date_bbox.y0)
                    if AUTO_PLAY:
                        play_pause(player)
                print("Select DOWN")
            else:
                select_press_time = time.ticks_ms()
                print("Select UP")

        if not tm.pSelect.value():  # long press Select
            if (time.ticks_ms() - select_press_time) > 1_000:
                print("                 Longpress of select")
                select_press_time = time.ticks_ms()
                if ntape == 0:
                    tape_ids = get_tape_ids(coll_dict, key_date)
                ntape = (ntape + 1) % len(tape_ids)
                utils.init_screen()
                utils.clear_bbox(artist_bbox)
                tm.tft.write(pfont_small, f"{tape_ids[ntape][0]}", artist_bbox.x0, artist_bbox.y0, stage_date_color)
                # vcs = coll_dict[tape_ids[ntape][0]][key_date]
                utils.clear_bbox(venue_bbox)
                display_str = re.sub(r"\d\d\d\d-\d\d-\d\d\.*", "~", tape_ids[ntape][1])
                display_str = re.sub(r"\d\d-\d\d-\d\d\.*", "~", display_str)
                print(f"display string is {display_str}")
                if len(display_str) > 18:
                    display_str = display_str[:11] + display_str[-6:]
                tm.tft.write(pfont_small, f"{display_str}", venue_bbox.x0, venue_bbox.y0, stage_date_color)
                print(f"Select LONG_PRESS values is {tm.pSelect.value()}. ntape = {ntape}")
                collection, tracklist, urls = select_date(coll_dict, key_date, ntape)

        if pPower_old != tm.pPower.value():
            pPower_old = tm.pPower.value()
            tm.pLED.value(PowerLED)
            tm.tft.off() if not PowerLED else tm.tft.on()
            if pPower_old:
                print("Power DOWN")
            else:
                PowerLED = not PowerLED
                power_press_time = time.ticks_ms()
                print("Power UP -- screen")

        if not tm.pPower.value():
            if (time.ticks_ms() - power_press_time) > 1_000:
                power_press_time = time.ticks_ms()
                print("Power DOWN -- exiting")
                tm.tft.off()
                time.sleep(0.1)
                machine.reset()

        vcs_line = ((time.ticks_ms() - select_press_time) // 12_000) % (1 + len(selected_vcs) // 16)
        if (vcs == selected_vcs) & (vcs_line != pvcs_line):
            pvcs_line = vcs_line
            utils.init_screen()
            utils.clear_bbox(venue_bbox)
            startchar = min(15 * vcs_line, len(selected_vcs) - 16)
            tm.tft.write(pfont_small, f"{selected_vcs[startchar:]}", venue_bbox.x0, venue_bbox.y0, stage_date_color)
            print(player)
            update_display(player)
            # display_tracks(*player.track_names())

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
                print("Month UP")

        if pDSw_old != tm.pDSw.value():
            pDSw_old = tm.pDSw.value()
            if pDSw_old:
                print("Day DOWN")
            else:
                for date in valid_dates:
                    if date > key_date:
                        key_date = set_date(date)
                        break
                print("Day UP")

        year_new = tm.y.value()
        month_new = tm.m.value()
        day_new = tm.d.value()
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
            print("year =", year_new)

        if month_old != month_new:
            month_old = month_new
            print("month =", month_new)

        if day_old != day_new:
            day_old = day_new
            print("day =", day_new)

        if date_old != date_new:
            utils.clear_bbox(stage_date_bbox)
            tm.tft.write(large_font, f"{date_new}", 0, 0, stage_date_color)  # no need to clear this.
            # tm.tft.text(font, f"{date_new}", 0, 0, stage_date_color, st7789.BLACK) # no need to clear this.
            date_old = date_new
            print(f"date = {date_new} or {key_date}")
            try:
                if key_date in valid_dates:
                    for c in list(coll_dict.keys()):
                        if key_date in coll_dict[c].keys():
                            nshows += 1
                            collection = c
                            vcs = coll_dict[collection][f"{key_date}"]
                            utils.clear_bbox(artist_bbox)
                            tm.tft.write(pfont_small, f"{collection}", artist_bbox.x0, artist_bbox.y0, stage_date_color)
                else:
                    vcs = ""
                    collection = ""
                    utils.clear_bbox(artist_bbox)
                    tm.tft.write(pfont_small, f"{current_collection}", artist_bbox.x0, artist_bbox.y0, tracklist_color)
                print(f"vcs is {vcs}")
                utils.clear_bbox(venue_bbox)
                tm.tft.write(pfont_small, f"{vcs}", venue_bbox.x0, venue_bbox.y0, stage_date_color)
                utils.clear_bbox(nshows_bbox)
                if nshows > 1:
                    tm.tft.write(
                        pfont_small, f"{nshows}", nshows_bbox.x0, nshows_bbox.y0, nshows_color
                    )  # no need to clear this.
                update_display(player)
                # display_tracks(*player.track_names())
            except KeyError:
                utils.clear_bbox(venue_bbox)
                utils.clear_bbox(artist_bbox)
                tm.tft.write(pfont_small, f"{current_collection}", artist_bbox.x0, artist_bbox.y0, stage_date_color)
                update_display(player)
                # display_tracks(*player.track_names())
                pass

        audio_pump(player, Nmax=3)  # Try to keep buffer filled.


def add_vcs(coll):
    print(f"Adding vcs for coll {coll}")
    vcs_url = f"{CLOUD_PATH}/vcs/{coll}_vcs.json"
    print(vcs_url)
    resp = requests.get(vcs_url)
    if resp.status_code == 200:
        vcs = resp.json()
    else:
        print(f"status was {resp.status_code}")
        api_request = f"{API}/vcs/{coll}"
        print(f"API request is {api_request}")
        vcs = requests.get(api_request).json()[coll]
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
    utils.clear_screen()
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
    return coll_dict


def run():
    """run the livemusic controls"""
    if utils.path_exists(COLLECTION_LIST_PATH):
        collection_list = json.load(open(COLLECTION_LIST_PATH, "r"))
    else:
        collection_list = ["GratefulDead"]
        with open(COLLECTION_LIST_PATH, "w") as f:
            json.dump(collection_list, f)
    show_collections(collection_list)

    coll_dict = get_coll_dict(collection_list)
    print(f"Loaded collections {coll_dict.keys()}")
    player = audioPlayer.AudioPlayer(callbacks={"display": display_tracks, "screen_off": utils.screen_off}, format=FORMAT)
    main_loop(player, coll_dict)
