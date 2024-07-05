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
import re
import sys
import time
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
stage_date_bbox = tm.Bbox(0, 0, tm.SCREEN_WIDTH, 27)
playpause_bbox = tm.Bbox(145, 0, tm.SCREEN_WIDTH, 27)
bottom_bbox = tm.Bbox(0, 29, tm.SCREEN_WIDTH, tm.SCREEN_HEIGHT)
tapeid_range_dict = {}


def set_date_range(date_range, state=None):
    global DATE_SET_TIME
    start_year = date_range[0]
    end_year = date_range[1]
    tm.y._value = end_year
    tm.m._value = start_year
    tm.d._value = (start_year + end_year) // 2
    date_range = (start_year, end_year)
    DATE_SET_TIME = time.ticks_ms()
    if state is not None:
        state["date_range"] = date_range
        utils.save_state(state, "78rpm")
    return date_range


def select_date_range(date_range, N_to_select=60):
    print(f"Selecting tapes from {date_range}.")

    track_index = 0
    tm.clear_bbox(tm.venue_bbox)
    tm.clear_bbox(bottom_bbox)
    msg = f"Loading {date_range[0]}"
    if date_range[1] > date_range[0]:
        msg = msg + f" to {date_range[1]}"
    tm.write(
        msg,
        bottom_bbox.x0,
        bottom_bbox.y0,
        pfont_small,
        purple_color,
        clear=0,
        show_end=-2,
    )
    metadata_cache = f"/metadata/78rpm/{date_range[0]}_{date_range[1]}_tracklist.json"
    metadata_track_index = f"/metadata/78rpm/{date_range[0]}_{date_range[1]}_tracknum.json"
    if utils.path_exists(metadata_cache):
        try:
            track_index = utils.read_json(metadata_track_index)
            coll_dict = utils.read_json(metadata_cache)
            tracks_remaining = len(coll_dict["identifier"]) - track_index
            if tracks_remaining < 7:
                print(f"Only {tracks_remaining} remaining. Deleting")
                utils.remove_file(metadata_cache)
                utils.remove_file(metadata_track_index)
                track_index = 0
        except Exception as e:
            utils.remove_file(metadata_cache)
    if not utils.path_exists(metadata_cache):
        track_index = 0
        coll_dict = archive_utils.subset_collection(
            ["identifier", "date"], "georgeblood", date_range, N_to_select, prefix="78_"
        )
        while utils.disk_free() < 100:
            utils.remove_oldest_files("/metadata/rpm78", 1)
        utils.write_json(coll_dict, metadata_cache)
        utils.write_json(0, metadata_track_index)
    coll_dict = {k: v[track_index:] for k, v in coll_dict.items()}
    tape_ids = coll_dict["identifier"]
    tape_dates = [x[:10] for x in coll_dict["date"]]
    tm.clear_bbox(bottom_bbox)
    indices = utils.shuffle(list(range(len(tape_ids))))
    tape_ids = [tape_ids[i] for i in indices]
    tape_dates = [tape_dates[i] for i in indices]
    return tape_ids, tape_dates, track_index


def get_urls_for_ids(tape_ids):
    urls = []
    tracklist = []
    artists = []
    tm.clear_bbox(bottom_bbox)
    tm.clear_bbox(playpause_bbox)
    tm.write("Choosing Songs", bottom_bbox.x0, bottom_bbox.y0, pfont_small, purple_color, clear=0, show_end=1)
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
    if player.is_playing():
        player.pause()
    elif len(player.playlist) > 0:
        player.play()
        tm.power(1)
    update_playpause(player)
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
    min_year, max_year = state["date_range"]
    date_range = set_date_range([min_year, max_year], state)
    staged_date_range = date_range
    print(f"date range set to {date_range}")
    end_year_old = tm.y.value()
    start_year_old = tm.m.value()
    mid_year_old = tm.d.value()
    date_changed_time = 0
    tape_ids = []
    tracks_played = 0
    track_index = 0
    tracks_length = 60

    tm.screen_on_time = time.ticks_ms()
    date_range_msg = f"{date_range[0]}"
    if date_range[1] > date_range[0]:
        date_range_msg += f"-{date_range[1]%100:02d}"
    tm.write(date_range_msg, 0, 0, color=stage_date_color, font=large_font, clear=True)
    tm.write("Turn knobs to\nChange timespan\nthen Select", 0, 42, color=yellow_color, font=pfont_small, clear=False)
    tm.write("min  mid  max", 0, 100, color=st7789.WHITE, font=pfont_med, clear=False)
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
                    tm.clear_bbox(playpause_bbox)
                    tape_ids, tape_dates, track_index = select_date_range(staged_date_range, tracks_length)
                    date_range = set_date_range(staged_date_range, state)
                    urls, tracklist, artists = get_urls_for_ids(tape_ids[:5])
                    dates = tape_dates[:5]
                    player.set_playlist(tracklist, urls)
                    display_tracks(*player.track_names())
                    tape_ids = tape_ids[5:]
                    tape_dates = tape_dates[5:]
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
                        tm.clear_bbox(playpause_bbox)
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

        if pSelect_old != tm.pSelect.value():
            pSelect_old = tm.pSelect.value()
            if pSelect_old:
                print("short press of select")
                player.stop()
                tm.clear_bbox(tm.venue_bbox)
                tm.clear_bbox(playpause_bbox)
                tape_ids, tape_dates, track_index = select_date_range(staged_date_range, tracks_length)
                date_range = set_date_range(staged_date_range, state)
                urls, tracklist, artists = get_urls_for_ids(tape_ids[:5])
                dates = tape_dates[:5]
                player.set_playlist(tracklist, urls)
                display_tracks(*player.track_names())
                tape_ids = tape_ids[5:]
                tape_dates = tape_dates[5:]
                gc.collect()
                play_pause(player)
            else:
                select_press_time = time.ticks_ms()
                print("Select DOWN")

        if (len(tape_ids) > 0) and player.is_stopped():
            pts = player.track_status()
            if pts["current_track"] == 0:
                tm.clear_bbox(bottom_bbox)
                tm.write("Flipping Record", bottom_bbox.x0, bottom_bbox.y0, pfont_small, purple_color, clear=0)
                urls, tracklist, artists = get_urls_for_ids(tape_ids[:5])
                dates = tape_dates[:5]
                player.set_playlist(tracklist, urls)
                display_tracks(*player.track_names())
                tape_ids = tape_ids[5:]
                tape_dates = tape_dates[5:]
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

        if (staged_date_range != date_range) and (time.ticks_diff(time.ticks_ms(), DATE_SET_TIME) > 20_000):
            print(f"setting date_range to {date_range}")
            staged_date_range = set_date_range(date_range, state)
            msg = update_staged_date_range(staged_date_range, player)
            display_tracks(*player.track_names())
            end_year_old = tm.y.value()
            start_year_old = tm.m.value()
            mid_year_old = tm.d.value()

        end_year_new = tm.y.value()
        start_year_new = tm.m.value()
        mid_year_new = tm.d.value()

        if (end_year_old != end_year_new) | (start_year_old != start_year_new) | (mid_year_old != mid_year_new):
            tm.power(1)
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
            staged_date_range = set_date_range((start_year_new, end_year_new))
            mid_year_old = tm.d.value()
            print(f"staged date_range is now {staged_date_range}")
            msg = update_staged_date_range(staged_date_range, player)
        if player.is_playing() and player.current_track != current_track_old:
            tracks_played += 1
            track_index += 1
            utils.write_json(track_index, f"/metadata/78rpm/{date_range[0]}_{date_range[1]}_tracknum.json")
            current_track_old = player.current_track
            display_artist(utils.capitalize(artists[player.current_track]), dates[player.current_track])
        player.audio_pump()


def update_playpause(player):
    tm.clear_bbox(playpause_bbox)
    if player.is_stopped():
        pass
    elif player.is_playing():
        tm.tft.fill_polygon(tm.PlayPoly, playpause_bbox.x0, 10, play_color)
    elif player.is_paused():
        tm.tft.fill_polygon(tm.PausePoly, playpause_bbox.x0, 10, st7789.WHITE)


def update_staged_date_range(staged_date_range, player):
    date_range_msg = f"{staged_date_range[0]}"
    #    if staged_date_range[1] > staged_date_range[0]:
    date_range_msg += f"-{staged_date_range[1]%100:02d}"
    msg = tm.write(date_range_msg, 0, 0, large_font, stage_date_color, clear=0)
    # display_tracks(*player.track_names())  # causes screen flicker. Could avoid by lowering tracks bbox.
    return msg


def display_artist(artist, date=""):
    artist = utils.capitalize(artist.lower()).strip()
    artist = "Unknown" if len(artist) == 0 else artist
    text_height = 15
    max_lines = 3
    artist_msg = tm.add_line_breaks(artist, 0, pfont_small, -max_lines, indent=1)
    n_lines = len(artist_msg.split("\n"))

    y0 = 65
    y1 = y0 + (max_lines - n_lines) * text_height
    if n_lines < max_lines:
        y1 = y1 - 5
    tm.clear_bbox(tm.Bbox(0, y0, tm.SCREEN_WIDTH, tm.SCREEN_HEIGHT))

    bottom_y0 = y0 + (text_height * max_lines) + 2
    date_msg = tm.write(f"{date}", 20, bottom_y0, date_font, st7789.GREEN, text_height, 0)
    msg = tm.write(f"{artist}", 0, y1, pfont_small, st7789.WHITE, text_height, 0, -max_lines, indent=1)
    print(f"in display_artist {artist},\n{msg} at 0,{y1}")
    return msg


def display_tracks(*track_names):
    print(f"in display_tracks {track_names}")
    max_tracknames = 1
    max_lines = 2
    lines_written = 0
    # tm.clear_bbox(bottom_bbox)
    tm.clear_bbox(tm.Bbox(0, 27, tm.SCREEN_WIDTH, 65))
    last_valid_str = 0
    for i in range(len(track_names)):
        if len(track_names[i]) > 0:
            last_valid_str = i
    i = 0
    text_height = 17
    while (lines_written < max_lines) and i < max_tracknames:
        name = track_names[i]
        name = name.strip("-> ")  # remove trailing spaces and >'s
        if i < last_valid_str and len(name) == 0:
            name = "Unknown"
        name = utils.capitalize(name.lower())
        y0 = bottom_bbox.y0 + 2 + (text_height * lines_written)
        show_end = -2 if i == 0 else 0
        msg = tm.write(f"{name}", 0, y0, pfont_small, tracklist_color, text_height, 0, show_end, indent=2)
        lines_written += len(msg.split("\n"))
        i = i + 1
    return msg


def run():
    """run the livemusic controls"""
    try:
        wifi = utils.connect_wifi()
        state = utils.load_state("78rpm")
        min_year, max_year = [1898, 1965]
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
