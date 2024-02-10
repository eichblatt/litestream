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

import audioPlayer

# API = "https://msdocs-python-webapp-quickstart-sle.azurewebsites.net"
CLOUD_PATH = "https://storage.googleapis.com/spertilo-data"
# API = "https://deadstream-api-3pqgajc26a-uc.a.run.app"  # google cloud version
API = "https://gratefuldeadtimemachine.com"  # google cloud version mapped to here
# API = 'http://westmain:5000' # westmain
AUTO_PLAY = True
ARTIST_KEY_TIME = time.ticks_ms()
TAPE_KEY_TIME = time.ticks_ms()

stage_date_color = st7789.color565(255, 255, 0)
yellow_color = st7789.color565(255, 255, 0)
purple_color = st7789.color565(255, 100, 255)
tracklist_color = st7789.color565(0, 255, 255)
play_color = st7789.color565(255, 0, 0)
nshows_color = st7789.color565(0, 100, 255)
new_tracklist_bbox = tm.tracklist_bbox.shift(tm.Bbox(0, 8, 0, 8))


def set_tapeid_name(id, artist_tapeids):
    for i, tid in enumerate(artist_tapeids):
        if tid["identifier"] == id:
            set_tapeid_index(i)
            return


def set_tapeid_index(index):
    tm.d._value = index
    return


def set_tapeid_range(keyed_artist):
    print(f"Setting tapeid range for {keyed_artist}")
    # load data file for artist
    artist_tapes = sorted(utils.read_json(f"/metadata/datpiff/{keyed_artist}.json"), key=lambda x: x["title"])
    # set the range of the "day" knob to be this number.
    tm.d._max_val = len(artist_tapes) - 1
    # tm.d._value = 0
    return artist_tapes


def select_tapeid(tapeid):
    print(f"Selecting tapeid {tapeid}")

    state = utils.load_state("datpiff")
    state["selected_tape"] = tapeid
    utils.save_state(state, "datpiff")
    return tapeid


def select_artist_by_index(artist_key_index):
    # run this function when we SELECT a new artist (not when we key them)
    print(f"setting artist index to {artist_key_index}")
    state = utils.load_state("datpiff")
    selected_artist = state["artist_list"][artist_key_index]
    utils.save_state(state, "datpiff")
    artist_tapes = set_tapeid_range(selected_artist)
    return selected_artist, artist_tapes


def set_artist(artist):
    print(f"setting artist to {artist}")
    state = utils.load_state("datpiff")
    for i, a in enumerate(state["artist_list"]):
        if a.lower() == artist.lower():
            tm.m._value = i
            return i
    print(f"ERROR Unknown Artist {artist}. Returning 0")
    return 0


def set_knob_times():
    global TAPE_KEY_TIME
    global ARTIST_KEY_TIME
    TAPE_KEY_TIME = time.ticks_ms()
    ARTIST_KEY_TIME = time.ticks_ms()
    return


# def set_date(date):
#    global DATE_SET_TIME
#    tm.y._value = int(date[:4])
#    tm.m._value = int(date[5:7])
#    tm.d._value = int(date[8:10])
#    key_date = f"{tm.y.value()}-{tm.m.value():02d}-{tm.d.value():02d}"
#    DATE_SET_TIME = time.ticks_ms()
#    return key_date


def get_tape_metadata(identifier):
    url_metadata = f"https://archive.org/metadata/{identifier}"
    # url_details = f"https://archive.org/details/{identifier}"
    url_download = f"https://archive.org/download/{identifier}"
    print(url_metadata)
    resp = requests.get(url_metadata)
    if resp.status_code != 200:
        print(f"Error in request from {resp.url}. Status code {resp.status_code}")
        raise Exception("Download Error")
    if not resp.chunked:
        j = resp.json()
    else:
        resp.save("/tmp.json")
        j = json.load(open("/tmp.json", "r"))
    resp.close()

    track_data = [x for x in j["files"] if "mp3" in x["format"].lower()]
    tracklist = []
    urls = []
    albums = []
    artists = []
    for track in track_data:
        albums.append(track.get("album", "Unknown"))
        artists.append(track.get("artist", "Unknown"))
        tracklist.append(track.get("title", "Unknown"))
        urls.append(f"{url_download}/{track['name']}")
    return tracklist, urls, albums, artists


def download_tape_ids(artist, id_path):
    pass


def load_tape_ids(artists):
    print(f"getting tape_ids from {artists}")
    tape_ids = {}
    for artist in artists:
        id_path = f"/metadata/datpiff/{artist}.json"
        if not utils.path_exists(id_path):
            download_tape_ids(artist, id_path)
        tape_ids[artist] = json.load(open(id_path, "r"))

    return tape_ids


def select_tape(tape, player, state):
    tm.clear_bbox(tm.playpause_bbox)
    tm.tft.fill_polygon(tm.PausePoly, tm.playpause_bbox.x0, tm.playpause_bbox.y0, st7789.RED)
    player.stop()
    tracklist, urls, albums, artists = get_tape_metadata(tape["identifier"])

    player.set_playlist(tracklist, urls)
    state["selected_artist"] = artists[0]
    state["selected_tape"] = tape
    utils.save_state(state, "datpiff")
    print(f"Displaying artist is {artists[0][:17]}")
    display_selected_artist(artists[0][:17])
    return state


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
    year_old = -1
    month_old = -1
    day_old = -1
    pPower_old = 0
    pSelect_old = pPlayPause_old = pStop_old = pRewind_old = pFFwd_old = 1
    pYSw_old = pMSw_old = pDSw_old = 1
    keyed_artist = state["selected_artist"]
    selected_artist = keyed_artist
    keyed_tape = state["selected_tape"]
    selected_tape = keyed_tape
    select_press_time = 0
    power_press_time = 0
    resume_playing = -1
    resume_playing_delay = 500

    tm.screen_on_time = time.ticks_ms()
    tm.clear_screen()
    poll_count = 0
    print("main loop before while")
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
                    state = select_tape(keyed_tape, player, state)
                    selected_artist = state["selected_artist"]
                    selected_tape = state["selected_tape"]
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
                        tm.tft.fill_polygon(tm.StopPoly, tm.playpause_bbox.x0, tm.playpause_bbox.y0, play_color)
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
        if time.ticks_diff(time.ticks_ms(), ARTIST_KEY_TIME) > 20_000:
            if (keyed_artist != selected_artist) or (keyed_tape["identifier"] != selected_tape["identifier"]):
                set_knob_times()
                print(f"resetting keyed_artist to {selected_artist}")
                selected_title = selected_tape["title"]
                keyed_artist = selected_artist
                keyed_tape = selected_tape
                display_keyed_title(selected_title, color=yellow_color)
                display_keyed_artist(selected_artist, color=yellow_color)

        if pSelect_old != tm.pSelect.value():
            pSelect_old = tm.pSelect.value()
            if pSelect_old:
                print("short press of select")
                print("Select UP")
            else:
                select_press_time = time.ticks_ms()
                selected_artist, artist_tapes = select_artist_by_index(tm.m.value())
                selected_title = artist_tapes[tm.d.value()]["title"]

                player.stop()
                selected_tape = select_tapeid(artist_tapes[tm.d.value()])
                state = select_tape(selected_tape, player, state)

                display_keyed_title(selected_title, color=yellow_color)
                display_keyed_artist(selected_artist, color=yellow_color)
                play_pause(player)
                print("Select DOWN")

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
            if (time.ticks_ms() - power_press_time) > 2_500:
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
                tm.screen_off()  # screen off while playing
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
                print("Day UP")
            else:
                print("Day DOWN")

        year_new = tm.y.value()
        month_new = tm.m.value()
        day_new = tm.d.value()

        if (year_old != year_new) | (month_old != month_new) | (day_old != day_new):
            year_old = year_new
            print(f"time diff is {time.ticks_diff(time.ticks_ms(), TAPE_KEY_TIME)}")
            set_knob_times()
            tm.power(1)
        if (month_old != month_new) or (day_old != day_new):
            print(f"Month {month_new}, Day {day_new}/{tm.d._max_val}")
            keyed_artist = state["artist_list"][month_new]
            if month_old != month_new:
                artist_tapes = set_tapeid_range(keyed_artist)
            tape_id_dict = artist_tapes[day_new]
            keyed_tape = tape_id_dict
            keyed_title = tape_id_dict["title"]
            display_keyed_title(keyed_title)
            display_keyed_artist(keyed_artist)
            print(f"selected artist {selected_artist}")
            month_old = month_new
            day_old = day_new

        player.audio_pump()


def update_display(player):
    # display_tracks(*player.track_names())
    tm.clear_bbox(tm.playpause_bbox)
    if not player.is_started():
        pass
    elif player.is_stopped():
        tm.tft.fill_polygon(tm.StopPoly, tm.playpause_bbox.x0, tm.playpause_bbox.y0, play_color)
    elif player.is_playing():
        tm.tft.fill_polygon(tm.PlayPoly, tm.playpause_bbox.x0, tm.playpause_bbox.y0, play_color)
    elif player.is_paused():
        tm.tft.fill_polygon(tm.PausePoly, tm.playpause_bbox.x0, tm.playpause_bbox.y0, st7789.WHITE)


def display_tracks(current_track_name, next_track_name):
    tm.clear_bbox(new_tracklist_bbox)
    tm.tft.write(pfont_small, f"{current_track_name}", new_tracklist_bbox.x0, new_tracklist_bbox.y0, tracklist_color)
    tm.tft.write(pfont_small, f"{next_track_name}", new_tracklist_bbox.x0, new_tracklist_bbox.center()[1], tracklist_color)
    return


def display_keyed_title(keyed_title, color=purple_color):
    print(f"in display_keyed_title {keyed_title}")
    tm.clear_bbox(tm.title_bbox)
    tm.write(keyed_title[:17], tm.title_bbox.x0, tm.title_bbox.y0, color=color, font=pfont_small, clear=False)
    if len(keyed_title) > 17:
        tm.write(keyed_title[17:], tm.title_bbox.x0, tm.title_bbox.y0 + 20, color=color, font=pfont_small, clear=False)


def display_keyed_artist(artist, color=purple_color):
    print(f"in display_keyed_artist {artist}")
    tm.clear_bbox(tm.keyed_artist_bbox)
    artist = artist[:1].upper() + artist[1:]
    if len(artist) < 19:
        artist = (9 - len(artist) // 2) * " " + artist
    elif len(artist) > 20:
        artist = artist[:16] + "~" + artist[-4:]
    tm.write(artist, tm.keyed_artist_bbox.x0, tm.keyed_artist_bbox.y0, color=color, font=pfont_small, clear=False)


def display_selected_artist(artist):
    print(f"in display_selected_artist {artist}")
    tm.clear_bbox(tm.selected_artist_bbox)
    if len(artist) < 15:
        artist = (7 - len(artist) // 2) * " " + artist
    elif len(artist) > 16:
        artist = artist[:12] + "~" + artist[-4:]
    tm.write(artist, tm.selected_artist_bbox.x0, tm.selected_artist_bbox.y0, font=pfont_small, clear=False)


def show_artists(artist_list):
    ncoll = len(artist_list)
    message = f"Loading {ncoll} Collections"
    print(message)
    tm.clear_screen()
    tm.tft.write(pfont_med, message, 0, 0, yellow_color)
    colls_to_write = 5

    for min_col in range(0, 1 + ncoll - colls_to_write, 1):
        tm.clear_area(0, 25, 160, 103)
        for i, coll in enumerate(artist_list[min_col : min_col + colls_to_write]):
            tm.write(f"{coll}", 0, 25 + 20 * i, font=pfont_small, color=st7789.WHITE, clear=False)
        time.sleep(0.5)


def get_artist_metadata(artist_list):
    for artist in artist_list:
        path_to_meta = f"/metadata/datpiff/{artist}.json"
        print(f"loading {path_to_meta}")
        if not utils.path_exists(path_to_meta):
            try:
                url = f"https://default-withdatpiff-3pqgajc26a-uc.a.run.app/tapes_by_artist/{artist.lower().replace(' ','%20')}"
                print(f"Querying from {url}")
                resp = requests.get(url)
                if resp.status_code != 200:
                    raise Exception(f"Failed to load from {url}")
                metadata = resp.json()
                keys = ["artist", "title", "identifier"]
                metadata = [dict(zip(keys, x)) for x in metadata]
                utils.write_json(metadata, path_to_meta)
            finally:
                resp.close()


def run():
    """run the livemusic controls"""
    try:
        wifi = utils.connect_wifi()
        state = utils.load_state("datpiff")
        artist_list = state["artist_list"]
        show_artists(artist_list)

        get_artist_metadata(artist_list)
        tm.y._min_val = 0
        tm.m._min_val = 0
        tm.d._min_val = 0

        tm.m._max_val = len(state["artist_list"]) - 1
        tm.m._value = 0

        print(f"Range of month knob is {tm.m._max_val}")
        artist_index = set_artist(state["selected_artist"])  # set the knobs
        print(f"tm.m.value() is {tm.m.value()}. index {artist_index}")
        select_tapeid(state["selected_tape"])
        _, _ = select_artist_by_index(artist_index)
        player = audioPlayer.AudioPlayer(callbacks={"display": display_tracks}, debug=False)
        main_loop(player, state)
    except Exception as e:
        msg = f"Error in playback loop {e}"
        print(msg)
        with open("/exception.log", "w") as f:
            f.write(msg)
        if utils.path_exists("/.is_dev_box"):
            tm.write("".join(msg[i : i + 16] + "\n" for i in range(0, len(msg), 16)), font=pfont_small)
            tm.write("Select to exit", 0, 100, color=yellow_color, font=pfont_small, clear=False)
            tm.poll_for_button(tm.pSelect, timeout=12 * 3600)
    return -1
