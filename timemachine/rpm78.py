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
import os
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

import archive_utils
import audioPlayer

# API = "https://msdocs-python-webapp-quickstart-sle.azurewebsites.net"
CLOUD_PATH = "https://storage.googleapis.com/spertilo-data"
# API = "https://deadstream-api-3pqgajc26a-uc.a.run.app"  # google cloud version
API = "https://gratefuldeadtimemachine.com"  # google cloud version mapped to here
# API = 'http://westmain:5000' # westmain
AUTO_PLAY = True
DATE_SET_TIME = time.ticks_ms()

stage_date_color = st7789.color565(255, 255, 0)
yellow_color = st7789.color565(255, 255, 0)
purple_color = st7789.color565(255, 100, 255)
tracklist_color = st7789.color565(0, 255, 255)
play_color = st7789.color565(255, 0, 0)
nshows_color = st7789.color565(0, 100, 255)
rpm78_tracklist_bbox = tm.Bbox(0, 30, tm.SCREEN_WIDTH, 112)
tapeid_range_dict = {}


def set_date_range(date_range):
    global DATE_SET_TIME
    start_year = date_range[0]
    end_year = date_range[1]
    tm.y._value = end_year
    tm.m._value = start_year
    tm.d._value = (start_year + end_year) // 2
    date_range = (start_year, end_year)
    DATE_SET_TIME = time.ticks_ms()
    return date_range


def get_ids_from_year(year):
    meta_path = f"/metadata/78rpm/georgeblood_{year}.json"
    tm.write(f"Loading {year}", tm.venue_bbox.x0, tm.venue_bbox.y0, pfont_small, purple_color, clear=0, show_end=1)
    ids = []
    if utils.path_exists(meta_path):
        ids = utils.read_json(meta_path)
    else:
        resdict = archive_utils.get_collection_year(["identifier"], "georgeblood", year)
        ids = resdict["identifier"]
        if utils.disk_free() > 1_000:
            utils.write_json(ids, meta_path)
        else:
            utils.remove_oldest_files(utils.dirname(meta_path), 1)
        print(f"{meta_path} written")
    return ids


def select_date_range(date_range, N_to_select=60):
    print(f"selecting tapes from {date_range}.")

    # To minimize memory, select at most 15 different years.
    max_N_years = 15
    min_year = date_range[0]
    max_year = date_range[1] + 1
    year_list = list(range(min_year, max_year))
    if (max_year - min_year) > max_N_years:
        year_list = utils.deal_n(year_list, max_N_years)

    print(f"Selecting from years {year_list}")
    tape_ids = []
    for year in year_list:
        try:
            tm.clear_bbox(tm.venue_bbox)
            ids = utils.deal_n(get_ids_from_year(year), N_to_select // len(year_list))
            _ = [tape_ids.append(x) for x in ids]
        except:
            pass

    tm.clear_bbox(tm.venue_bbox)
    tape_ids = utils.shuffle(tape_ids)
    return tape_ids


def get_urls_for_ids(tape_ids):
    urls = []
    tracklist = []
    artists = []
    tm.clear_bbox(tm.venue_bbox)
    tm.clear_bbox(rpm78_tracklist_bbox)
    tm.write("Choosing Songs", tm.venue_bbox.x0, tm.venue_bbox.y0, pfont_small, purple_color, clear=0, show_end=1)
    for identifier in tape_ids:
        print(f"Getting metadata for {identifier}")
        u, t, a = get_tape_metadata(identifier)
        _ = [urls.append(x) for x in u]
        _ = [tracklist.append(x) for x in t]
        _ = [artists.append(x) for x in a]
    return urls, tracklist, artists


@micropython.native
def get_tape_metadata(identifier):
    tracklist = []
    urls = []
    artists = []
    url_m3u = f"https://archive.org/download/{identifier}/{identifier}_vbr.m3u"
    try:
        resp = requests.get(url_m3u)
        if resp.status_code != 200:
            print(f"Error in request from {url_m3u}. Status code {resp.status_code}")
            raise Exception("Download Error")
        text = resp.text.split("\n")
        urls = [x for x in text if len(x) > 0]
        fields = [x.split("/")[-2:] for x in urls]
        track_artist = [x[-1].split("-") for x in fields]
        tracklist = ["".join(x[:-1]).strip() for x in track_artist]
        tracklist = [x for x in tracklist if not x.startswith("_78")]
        tracklist = [re.sub(r"^\d*", "", re.sub(r"\(\d\)", "", x)).strip() for x in tracklist]
        artists = ["".join(x[-1:]).strip().replace(".mp3", "") for x in track_artist[: len(tracklist)]]
        urls = urls[: len(tracklist)]
    except Exception as e:
        print(f"Exception: {e}. Continuing")
        urls = tracklist = artists = []
    finally:
        if resp is not None:
            resp.close()
    return urls, tracklist, artists


def play_pause(player):
    tm.clear_bbox(tm.playpause_bbox)
    if player.is_playing():
        player.pause()
        tm.tft.fill_polygon(tm.PausePoly, tm.playpause_bbox.x0, tm.playpause_bbox.y0, st7789.WHITE)
    elif len(player.playlist) > 0:
        player.play()
        tm.power(1)
        tm.tft.fill_polygon(tm.PlayPoly, tm.playpause_bbox.x0, tm.playpause_bbox.y0, play_color)
    return


def main_loop(player, state):
    pPower_old = 0
    pSelect_old = pPlayPause_old = pStop_old = pRewind_old = pFFwd_old = 1
    pYSw_old = pMSw_old = pDSw_old = 1
    current_track_old = -1
    select_press_time = 0
    power_press_time = 0
    resume_playing = -1
    resume_playing_delay = 500
    month_change_time = 1e12
    nprints_old = 0
    date_range = set_date_range([1910, 1920])
    print(f"date range set to {date_range}")
    end_year_old = tm.y.value()
    start_year_old = tm.m.value()
    mid_year_old = tm.d.value()
    date_changed_time = 0
    tape_ids = []

    tm.screen_on_time = time.ticks_ms()
    tm.clear_screen()
    tm.tft.write(large_font, f"{date_range[0]}-{date_range[1]%100:02d}", 0, 0, stage_date_color)
    poll_count = 0
    while True:
        player.audio_pump()
        poll_count = poll_count + 1
        if player.is_playing():
            tm.screen_on_time = time.ticks_ms()
        elif time.ticks_diff(time.ticks_ms(), tm.screen_on_time) > (20 * 60_000):
            tm.power(0)

        if pPlayPause_old != tm.pPlayPause.value():
            pPlayPause_old = tm.pPlayPause.value()
            if pPlayPause_old:
                print("PlayPause DOWN")
            else:
                print("PlayPause UP")
                if (player.is_stopped()) and (player.current_track is None):
                    tm.clear_bbox(tm.venue_bbox)
                    tm.write("Loading Music", tm.venue_bbox.x0, tm.venue_bbox.y0, pfont_small, purple_color)
                    tape_ids = select_date_range(date_range)
                    urls, tracklist, artists = get_urls_for_ids(tape_ids[:5])
                    tm.clear_bbox(tm.venue_bbox)
                    player.set_playlist(tracklist, urls)
                    tape_ids = tape_ids[5:]
                    gc.collect()
                play_pause(player)

        if pStop_old != tm.pStop.value():
            pStop_old = tm.pStop.value()
            if pStop_old:
                print("Stop DOWN")
            else:
                if tm.power():
                    tm.screen_on()
                    if player.stop():
                        tm.clear_bbox(tm.playpause_bbox)
                print("Stop UP")

        player.audio_pump()

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
        # if (key_date != selected_date) and (time.ticks_diff(time.ticks_ms(), DATE_SET_TIME) > 20_000):
        #     print(f"setting key_date to {selected_date}")
        #     key_date = set_date(selected_date)

        if pSelect_old != tm.pSelect.value():
            pSelect_old = tm.pSelect.value()
            if pSelect_old:
                print("short press of select")
                player.stop()
                tm.clear_bbox(tm.venue_bbox)
                tm.write("Loading Music", tm.venue_bbox.x0, tm.venue_bbox.y0, pfont_small, purple_color, clear=0)
                tape_ids = select_date_range(date_range)
                urls, tracklist, artists = get_urls_for_ids(tape_ids[:5])
                tm.clear_bbox(tm.venue_bbox)
                player.set_playlist(tracklist, urls)
                tape_ids = tape_ids[5:]
                gc.collect()
                play_pause(player)
                print("Select UP")
            else:
                select_press_time = time.ticks_ms()
                print("Select DOWN")

        if (len(tape_ids) > 0) and player.is_stopped():
            pts = player.track_status()
            if pts["current_track"] == 0:
                tm.clear_bbox(tm.venue_bbox)
                tm.write("Flipping Record", tm.venue_bbox.x0, tm.venue_bbox.y0, pfont_small, purple_color, clear=0)
                urls, tracklist, artists = get_urls_for_ids(tape_ids[:5])
                player.set_playlist(tracklist, urls)
                tape_ids = tape_ids[5:]
                tm.clear_bbox(tm.venue_bbox)
                play_pause(player)

        if not tm.pSelect.value():  # long press Select
            if (time.ticks_ms() - select_press_time) > 1_000:
                player.stop()
                print("                 Longpress of select")
                select_press_time = time.ticks_ms() + 1_000

        if pPower_old != tm.pPower.value():
            # Press of Power button
            pPower_old = tm.pPower.value()
            if pPower_old:
                print("Power DOWN")
            else:
                print(f"power state is {tm.power()}")
                if tm.power() == 1:
                    player.pause()
                    tm.power(0)
                else:
                    tm.power(1)
                power_press_time = time.ticks_ms()
                print("Power UP -- screen")

        if not tm.pPower.value():
            if (time.ticks_ms() - power_press_time) > 1_250:
                power_press_time = time.ticks_ms()
                print("Power UP -- back to reconfigure")
                tm.power(1)
                tm.clear_screen()
                tm.screen_off()
                player.reset_player()
                return

        if pYSw_old != tm.pYSw.value():
            pYSw_old = tm.pYSw.value()
            if pYSw_old:
                print("Year DOWN")
            else:
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
                print("Day DOWN")

        end_year_new = tm.y.value()
        start_year_new = tm.m.value()
        mid_year_new = tm.d.value()

        if (end_year_old != end_year_new) | (start_year_old != start_year_new) | (mid_year_old != mid_year_new):
            tm.power(1)
            date_changed_time = time.ticks_ms()
            if mid_year_old != mid_year_new:
                offset = mid_year_new - mid_year_old
                proposed_max = min(end_year_old + offset, tm.y._max_val)
                proposed_min = max(start_year_old + offset, tm.m._min_val)
                if proposed_min <= tm.m._min_val:
                    mid_year_new = mid_year_old
                    tm.m._value = tm.m._min_val
                    start_year_new = tm.m._min_val
                elif proposed_max >= tm.y._max_val:
                    mid_year_new = mid_year_old
                    tm.y._value = tm.y._max_val
                    end_year_new = tm.y._max_val
                else:
                    start_year_new = proposed_min
                    end_year_new = proposed_max
                    mid_year_old = mid_year_new
                    tm.y._value = end_year_new
                    tm.m._value = start_year_new
                tm.d._value = mid_year_new
                # print(f"offset {offset}. day new {mid_year_new}")

            if end_year_old != end_year_new:
                # print(f"year new {end_year_new}")
                if end_year_new < start_year_old:
                    end_year_new = start_year_old
                    tm.y._value = end_year_new
                end_year_old = end_year_new
                tm.d._value = (start_year_new + end_year_new) // 2

            if start_year_old != start_year_new:
                # print(f"month new {start_year_new}")
                if start_year_new > end_year_old:
                    start_year_new = end_year_old
                    tm.m._value = start_year_new
                start_year_old = start_year_new
                tm.d._value = (start_year_new + end_year_new) // 2
            date_range = [start_year_new, end_year_new]
            mid_year_old = tm.d.value()
            print(f"date_range is now {date_range}")

            tm.clear_bbox(tm.stage_date_bbox)
            tm.tft.write(large_font, f"{date_range[0]}-{date_range[1]%100:02d}", 0, 0, stage_date_color)
            update_display(player)
        if player.is_playing() and player.current_track != current_track_old:
            current_track_old = player.current_track
            display_artist(utils.capitalize(artists[player.current_track]))
        player.audio_pump()


def update_display(player):
    tm.clear_bbox(tm.playpause_bbox)
    if player.is_stopped():
        pass
    elif player.is_playing():
        tm.tft.fill_polygon(tm.PlayPoly, tm.playpause_bbox.x0, tm.playpause_bbox.y0, play_color)
    elif player.is_paused():
        tm.tft.fill_polygon(tm.PausePoly, tm.playpause_bbox.x0, tm.playpause_bbox.y0, st7789.WHITE)


def display_artist(artist):
    print(f"in display_artist {artist}")
    try:
        state = utils.load_state("78rpm")
    except Exception as e:
        print(f"Failed to load state {e}")
    tm.clear_bbox(tm.selected_date_bbox)

    artist = tm.trim_string_middle(artist, 16, pfont_small)
    tm.write(f"{artist}", 0, tm.selected_date_bbox.y0 - 3, pfont_small, st7789.WHITE, clear=0)
    return


def display_tracks(*track_names):
    print(f"in display_tracks {track_names}")
    try:
        state = utils.load_state("78rpm")
    except Exception as e:
        print(f"Failed to load state {e}")
    tm.clear_bbox(rpm78_tracklist_bbox)
    last_valid_str = 0
    for i in range(len(track_names)):
        if len(track_names[i]) > 0:
            last_valid_str = i
    for i in range(5):
        name = track_names[i]
        if i < last_valid_str and len(name) == 0:
            name = "Unknown"
        name = utils.capitalize(name.lower())
        tm.write(f"{name}", rpm78_tracklist_bbox.x0, rpm78_tracklist_bbox.y0 + (16 * i), pfont_small, tracklist_color, clear=0)
    return


def run():
    """run the livemusic controls"""
    try:
        wifi = utils.connect_wifi()
        state = utils.load_state("78rpm")
        min_year, max_year = state["date_range"]

        tm.y._min_val = min_year
        tm.m._min_val = min_year
        tm.m._max_val = max_year
        tm.y._max_val = max_year
        tm.m._value = 1920
        tm.y._value = 1940
        tm.d._min_val = min_year
        tm.d._max_val = max_year
        tm.d._value = (tm.y.value() + tm.m.value()) // 2

        print(f"Range of month knob is {tm.m._max_val}")
        player = audioPlayer.AudioPlayer(callbacks={"display": display_tracks}, debug=False)
        main_loop(player, state)
    except Exception as e:
        msg = f"Error in playback loop {e}"
        print(msg)
        with open("/exception.log", "w") as f:
            f.write(msg)
        if utils.is_dev_box():
            tm.write("".join(msg[i : i + 16] + "\n" for i in range(0, len(msg), 16)), font=pfont_small)
            tm.write("Select to exit", 0, 100, color=yellow_color, font=pfont_small, clear=False)
            tm.poll_for_button(tm.pSelect, timeout=12 * 3600)
    return -1