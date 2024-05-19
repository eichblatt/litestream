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
dc = tm.decade_counter((tm.d, tm.y), 100, 10)
tapeid_range_dict = {}


def set_tapeid_name(id, artist_tapes):
    for i, tid in enumerate(artist_tapes):
        if tid["identifier"] == id:
            set_tapeid_index(i)
            return


def set_tapeid_index(index):
    print(f"setting tapeid index to {index}")
    dc.set_value(index)
    return


def get_artist_tapes(artist, state={}):
    path = f"/metadata/datpiff/{artist}.json"
    range_index = 0
    if state != {}:
        range_index, range_size = state["artist_ind_range"].get(artist, (0, None))
    if utils.isdir(path):
        range_size = len([x for x in os.listdir(path) if x.endswith(".json")])
        state = utils.load_state("datpiff")
        state["artist_ind_range"][artist] = (range_index, range_size)
        utils.save_state(state, "datpiff")
        path = f"{path}/{artist}_{range_index:02d}.json"
    return utils.read_json(path)


@micropython.native
def set_tapeid_range(keyed_artist, state={}, index_change=False):
    global tapeid_range_dict
    if (keyed_artist in tapeid_range_dict.keys()) and not index_change:
        artist_tapes = tapeid_range_dict[keyed_artist]
        dc.set_max_value(len(artist_tapes) - 1)
        return artist_tapes
    print(f"Setting tapeid range for {keyed_artist}")
    # load data file for artist
    artist_tapes = get_artist_tapes(keyed_artist, state)
    # print(f"setting max value of dc to {len(artist_tapes) -1}")
    dc.set_max_value(len(artist_tapes) - 1)
    tapeid_range_dict[keyed_artist] = artist_tapes
    return artist_tapes


def set_range_display_title(keyed_artist, dc, state, index_change=False):
    artist_tapes = set_tapeid_range(keyed_artist, state, index_change)
    dc_new = dc.get_value()
    tape_id_dict = artist_tapes[dc_new]
    keyed_tape = tape_id_dict
    keyed_title = tape_id_dict["title"]
    display_keyed_title(keyed_title)
    return keyed_tape, artist_tapes


def select_tape_other(tapeid):
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
    artist_tapes = set_tapeid_range(selected_artist, state)
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


def get_tape_metadata(identifier):
    url_metadata = f"https://archive.org/metadata/{identifier}"
    # url_details = f"https://archive.org/details/{identifier}"
    url_download = f"https://archive.org/download/{identifier}"
    print(url_metadata)
    resp = None
    try:
        resp = requests.get(url_metadata)
        if resp.status_code != 200:
            print(f"Error in request from {url_metadata}. Status code {resp.status_code}")
            raise Exception("Download Error")
        if not resp.chunked:
            j = resp.json()
        else:
            resp.save("/tmp.json")
            j = json.load(open("/tmp.json", "r"))
    finally:
        utils.remove_file("/tmp.json")
        if resp is not None:
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
    state["selected_tape"] = tape
    utils.save_state(state, "datpiff")
    print(f"Displaying artist is {artists[0]}")
    display_selected_artist(artists[0])
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
    month_old = -1
    dc_old = -1
    pPower_old = 0
    pSelect_old = pPlayPause_old = pStop_old = pRewind_old = pFFwd_old = 1
    pYSw_old = pMSw_old = pDSw_old = 1
    keyed_tape = state["selected_tape"]
    keyed_artist = keyed_tape["artist"]
    selected_artist = keyed_artist
    selected_tape = keyed_tape
    select_press_time = 0
    power_press_time = 0
    resume_playing = -1
    resume_playing_delay = 500
    player.set_volume(8)
    month_change_time = 1e12
    nprints_old = 0

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
                    selected_tape = state["selected_tape"]
                    selected_artist = selected_tape["artist"]
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
        if time.ticks_diff(time.ticks_ms(), ARTIST_KEY_TIME) > 20_000:
            if ((keyed_artist != selected_artist) or (keyed_tape["identifier"] != selected_tape["identifier"])) or (
                time.ticks_diff(time.ticks_ms(), select_press_time) < 30_000
            ):
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
                if (keyed_tape["identifier"] == selected_tape["identifier"]) and (not player.is_stopped()):
                    display_keyed_title(keyed_tape["identifier"], color=st7789.WHITE)
                    dev_flag = "dev" if utils.is_dev_box() else ""
                    display_keyed_artist(f"{utils.get_software_version()} {dev_flag}", color=st7789.WHITE)
                    set_knob_times()
                else:
                    selected_artist, artist_tapes = select_artist_by_index(tm.m.value())
                    selected_title = artist_tapes[dc.get_value()]["title"]

                    player.stop()
                    selected_tape = artist_tapes[dc.get_value()]
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
                ind, range = state["artist_ind_range"].get(keyed_artist, (0, None))
                if range:
                    ind = (ind - 1) % range
                    keyed_tape, artists_tapes, state = update_artist_ind(keyed_artist, ind, range, dc)
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
                # If we are in a collection with indices, increase the index by 1 (modulo)
                ind, range = state["artist_ind_range"].get(keyed_artist, (0, None))
                if range:
                    ind = (ind + 1) % range
                    keyed_tape, artists_tapes, state = update_artist_ind(keyed_artist, ind, range, dc)
                print("Day DOWN")

        month_new = tm.m.value()
        dc_new = dc.get_value()

        if (month_old != month_new) | (dc_old != dc_new):
            # print(f"time diff is {time.ticks_diff(time.ticks_ms(), TAPE_KEY_TIME)}")
            set_knob_times()
            tm.power(1)
            keyed_artist = state["artist_list"][month_new]
            if month_old != month_new:  # artist change -- delay
                month_change_time = time.ticks_ms()
            else:  # tape change -- do now
                keyed_tape, artist_tapes = set_range_display_title(keyed_artist, dc, state)
            display_keyed_artist(keyed_artist)
            # print(f"selected artist {selected_artist}")
            month_old = month_new
            dc_old = dc_new

        if time.ticks_diff(time.ticks_ms(), month_change_time) > 60:
            month_change_time = 1e12
            dc_new = dc.get_value()
            keyed_tape, artist_tapes = set_range_display_title(keyed_artist, dc, state)

        nprints = (time.ticks_ms() - select_press_time) // 12_000
        if nprints > nprints_old:
            nprints_old = nprints
            print(player)
            update_display(player)

        player.audio_pump()


def update_display(player):
    # display_tracks(*player.track_names())
    tm.clear_bbox(tm.playpause_bbox)
    if player.is_stopped():
        pass
    elif player.is_playing():
        tm.tft.fill_polygon(tm.PlayPoly, tm.playpause_bbox.x0, tm.playpause_bbox.y0, play_color)
    elif player.is_paused():
        tm.tft.fill_polygon(tm.PausePoly, tm.playpause_bbox.x0, tm.playpause_bbox.y0, st7789.WHITE)


def display_tracks(current_track_name, next_track_name):
    try:
        state = utils.load_state("datpiff")
        rm_txt = state["selected_tape"]["artist"].lower()  # Don't show artist name in track
        current_track_name, next_track_name = [x.lower().replace(rm_txt, "") for x in (current_track_name, next_track_name)]
        current_track_name, next_track_name = [utils.capitalize(x.strip("- .~")) for x in (current_track_name, next_track_name)]
    except:
        pass
    tm.clear_bbox(new_tracklist_bbox)
    tm.write(f"{current_track_name}", new_tracklist_bbox.x0, new_tracklist_bbox.y0, pfont_small, tracklist_color, clear=0)
    tm.write(f"{next_track_name}", new_tracklist_bbox.x0, new_tracklist_bbox.center()[1], pfont_small, tracklist_color, clear=0)
    return


def display_keyed_title(keyed_title, color=purple_color):
    # print(f"in display_keyed_title {keyed_title}")
    tm.clear_bbox(tm.title_bbox)
    tm.write(keyed_title, tm.title_bbox.x0, tm.title_bbox.y0, color=color, font=pfont_small, clear=False, show_end=2)


def display_keyed_artist(artist, color=purple_color):
    # print(f"in display_keyed_artist {artist}")
    tm.clear_bbox(tm.keyed_artist_bbox)
    artist = artist[:1].upper() + artist[1:]
    if len(artist) < 19:
        artist = (9 - len(artist) // 2) * " " + artist
    tm.write(artist, tm.keyed_artist_bbox.x0, tm.keyed_artist_bbox.y0, color=color, font=pfont_small, clear=False, show_end=1)


def display_selected_artist(artist):
    # print(f"in display_selected_artist {artist}")
    tm.clear_bbox(tm.selected_artist_bbox)
    tm.write(artist, tm.selected_artist_bbox.x0, tm.selected_artist_bbox.y0, font=pfont_small, clear=False, show_end=1)


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


def update_artist_ind(artist, ind, range, dc):
    print(f"ind is now {ind}/{range}")
    state = utils.load_state("datpiff")  # Needed?
    state["artist_ind_range"][artist] = (ind, range)
    utils.save_state(state, "datpiff")  # Needed?
    keyed_tape, artist_tapes = set_range_display_title(artist, dc, state, index_change=True)
    display_keyed_artist(artist)
    print(f"Keyed artist {artist}, keyed_tape {keyed_tape}, len(artist_tapes) {len(artist_tapes)}")
    return keyed_tape, artist_tapes, state


def get_artist_metadata(artist_list):
    for artist in artist_list:
        path_to_meta = f"/metadata/datpiff/{artist}.json"
        need_to_download = False
        if not utils.path_exists(path_to_meta):
            need_to_download = True
        elif utils.isdir(path_to_meta) and not utils.path_exists(f"{path_to_meta}/completed"):
            need_to_download = True
            utils.remove_dir(path_to_meta)
        if need_to_download:
            if utils.disk_free() < 3_000:
                state = utils.load_state("datpiff")
                state["artist_list"] = [x for x in artist_list if not x == artist]
                utils.save_state(state, "datpiff")
                utils.remove_dir(path_to_meta)
                raise Exception("Failed to load artists -- disk full")
            try:
                url = f"https://gratefuldeadtimemachine.com/datpiff_tapes_by_artist/{artist.lower().replace(' ','%20')}"
                print(f"Querying from {url}")
                print(f"saving to {path_to_meta}")
                resp = requests.get(url)
                if resp.status_code != 200:
                    print(f"Failed to load from {url}")
                    artist_list = [x for x in artist_list if not x == artist]  # Remove artist from artist_list
                    state = utils.load_state("datpiff")
                    state["artist_list"] = sorted(artist_list)
                    utils.save_state(state, "datpiff")
                    continue
                if resp.chunked:
                    print("saving json to /tmp.json")
                    resp.save("/tmp.json")
                    resp.close()
                    metadata = json.load(open("/tmp.json", "r"))
                elif len(resp.text) > 1_000_000:
                    print("saving json to /tmp.json")
                    with open("/tmp.json", "w") as f:
                        f.write(resp.text)
                    resp.close()
                    gc.collect()
                    metadata = utils.read_json("/tmp.json")
                    utils.remove_file("/tmp.json")
                else:
                    metadata = resp.json()

                keys = ["artist", "title", "identifier"]
                chunk_size = 1_600
                if len(metadata) > chunk_size:
                    if not utils.isdir(path_to_meta):
                        utils.remove_file(path_to_meta)
                        os.mkdir(path_to_meta)

                    for chunk_i in range(1 + len(metadata) // chunk_size):
                        sub_path = f"{path_to_meta}/{artist}_{chunk_i:02d}.json"
                        end = min(chunk_size, len(metadata))
                        chunk = metadata[:end]
                        gc.collect()
                        chunk = [dict(zip(keys, x)) for x in chunk]
                        utils.write_json(chunk, sub_path)
                        metadata = metadata[end:]
                        print(f"len metadata is {len(metadata)}")
                    utils.touch(f"{path_to_meta}/completed")
                    state = utils.load_state("datpiff")
                    state["artist_ind_range"][artist] = (0, chunk_i)
                    utils.save_state(state, "datpiff")
                else:
                    metadata = [dict(zip(keys, x)) for x in metadata]
                    utils.write_json(metadata, path_to_meta)
            except Exception as e:
                print(f"Exception in getting artist metadata: {e}")
                raise e
            finally:
                resp.close()
    if len(artist_list) == 0:
        raise Exception(f"Failed to load all artists")


def run():
    """run the livemusic controls"""
    try:
        wifi = utils.connect_wifi()
        state = utils.load_state("datpiff")
        state["artist_list"] = sorted(state["artist_list"])
        utils.save_state(state, "datpiff")
        artist_list = state["artist_list"]
        show_artists(artist_list)

        get_artist_metadata(artist_list)
        tm.y._min_val = 0
        tm.m._min_val = 0
        tm.d._min_val = 0

        tm.m._max_val = len(state["artist_list"]) - 1
        tm.m._value = 0

        print(f"Range of month knob is {tm.m._max_val}")
        artist_index = set_artist(state["selected_tape"]["artist"])  # set the artist knob
        print(f"tm.m.value() is {tm.m.value()}. index {artist_index}")
        tape = state["selected_tape"]
        _, artist_tapes = select_artist_by_index(artist_index)
        set_tapeid_name(tape["identifier"], artist_tapes)  # set the tapeid knobs
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
