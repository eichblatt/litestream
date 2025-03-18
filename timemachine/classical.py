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

import os
import re
import time

# import micropython # Use micropython.mem_info() to see memory available.
#import fonts.date_font as date_font
#import fonts.DejaVu_33 as large_font
#import fonts.NotoSans_18 as pfont_smallx
import fonts.NotoSans_bold_18 as pfont_small
import fonts.NotoSans_24 as pfont_med
#import fonts.NotoSans_32 as pfont_large

# import archive_utils
import board as tm
import classical_utils as clu
import utils
from classical_utils import Composer, Genre, Work, Category
from classical_utils import get_performances, get_composer_by_id, get_composers

try:
    import playerManager
except ImportError as e:
    if "Firmware" in str(e):
        print("AAC_Decoder not available in this version of the firmware")
        raise utils.FirmwareUpdateRequiredException("AAC_Decoder not available in this firmware")
    else:
        raise e

DEBUG = True
CLASSICAL_API = "https://www.classicalarchives.com/ajax/cma-api-2.json"
METADATA_ROOT = clu.METADATA_ROOT

works_dict = {}
genres = []
genre_dict = {}
cat_dict = {}

AUTO_PLAY = True
COMPOSER_KEY_TIME = time.ticks_ms()
WORK_KEY_TIME = time.ticks_ms()
GENRE_KEY_TIME = time.ticks_ms()
KNOB_TIME = time.ticks_ms()
CONFIG_CHOICES = ["Composers", "Repertoire", "Account"]
HAS_TOKEN = False

class MusicBoxContext():
    COMPOSER = 1
    GENRE = 2
    WORK = 3
    PERFORMANCE = 4
    TRACKLIST = 5
    OTHER = 6

class MusicBoxState:
    def __init__(self, player, state):
        self.player = player
        self.state = state
        self.keyed_work = None
        self.selected_work = None
        self.selected_composer = None
        self.keyed_composer = None
        self.selected_genre = None
        self.keyed_genre = None
        self.selected_performance = None
        self.tracklist = []
        self.track_titles = []
        self.performance_index = 0
        self.worklist = []
        self.worklist_key = None
        self.worklist_index = 0
        self.last_update_time = 0
        self.play_pause_press_time = 0
        self.select_press_time = 0
        self.power_press_time = 0


tapeid_range_dict = {}

selection_bbox = tm.Bbox(0, 0, tm.SCREEN_WIDTH, tm.SCREEN_HEIGHT)
work_bbox = tm.Bbox(0, pfont_med.HEIGHT, tm.SCREEN_WIDTH, pfont_med.HEIGHT + 3 * pfont_small.HEIGHT)
tracklist_bbox = tm.Bbox(0, pfont_med.HEIGHT + 3 * pfont_small.HEIGHT, tm.SCREEN_WIDTH, tm.SCREEN_HEIGHT)
playpause_bbox = tm.Bbox(0.93 * tm.SCREEN_WIDTH, tm.SCREEN_HEIGHT - pfont_small.HEIGHT, tm.SCREEN_WIDTH, tm.SCREEN_HEIGHT)



def get_creators(composer_list):  # A non-library mode call to get a list of composers.
    if isinstance(composer_list, (str, int)):
        composer_list = [composer_list]
    url = f"{CLASSICAL_API}?action=creators"
    outpath = f"{METADATA_ROOT}/creators.json"
    if utils.path_exists(outpath):
        ALL_COMPOSERS = utils.read_json(outpath)
    else:
        ALL_COMPOSERS = request_json(url, outpath)
    return ALL_COMPOSERS


def get_genres(composer_id=0):
    global genres
    global genre_dict
    if composer_id == 0:
        if len(genres) > 0:
            return genres
        url = f"{CLASSICAL_API}?action=genres"
        outpath = f"{METADATA_ROOT}/genres.json"
    elif isinstance(composer_id, int):
        retval = genre_dict.get(composer_id, None)
        if retval:
            return retval
        url = f"{CLASSICAL_API}?action=genres&creator_ids={composer_id}"
        outpath = f"{METADATA_ROOT}/{composer_id}_genres.json"

    if utils.path_exists(outpath):
        g = utils.read_json(outpath)["genres"]
    else:
        g = request_json(url, outpath)["genres"]
    if composer_id != 0:
        genre_dict[composer_id] = [Genre(id=x[0], name=x[1], index=i) for i, x in enumerate(g)]
        return genre_dict[composer_id]
    else:
        genres = g
        return genres


def get_works(composer_id):
    global works_dict
    # Note: Keep a local cache (dictionary) of works by composer, but NOT a disk cache.
    if composer_id in works_dict.keys():
        return works_dict[composer_id]
    url = f"{CLASSICAL_API}?action=works&creator_ids={composer_id}"
    works = request_json(url)["works"]
    # works_dict[composer_ids] = works
    works_dict[composer_id] = [Work(id=w[0], name=w[1], genre=w[4], period=w[3], perf_id=w[5]) for w in works]
    return works_dict[composer_id]


def get_cats_helper(composer_id, category_id=None, already=[]):
    # Recursive function to get all categories beneath this composer.
    # For pure categories (categories containing only sub-categories), the second
    #     element of the list is False. These should not be "selected", but are purely for organization

    url = f"{CLASSICAL_API}?mode=library&action=work&composer_id={composer_id}" + (
        f"&category_id={category_id}" if category_id is not None else ""
    )
    j = request_json(url)
    cats = {x["name"]: x["id"] for x in j if x["type"] == "c"}
    works = [Work(**(x | {"index": i})) for i, x in enumerate([x for x in j if x["type"] != "c"])]
    if len(already) > 0:
        # We are "wasting" the effort of creating these works, but saving space. We will re-query if selected.
        already[-1].nworks = len(works)
    for category_name, category_id in cats.items():
        already = get_cats_helper(composer_id, category_id, already + [Category(name=category_name, id=category_id)])
    return already


def get_cats(composer_id):
    global cat_dict
    # If this takes up too much memory, we can reduce the dict to just the index, id, and name. (ie. remove works)
    if composer_id == 0:
        raise ValueError("Cannot get categories for composer id 0")
    filepath = f"{METADATA_ROOT}/{composer_id}_cats.json"
    if len(cat_dict.get(composer_id, {})) == 0:
        if utils.path_exists(filepath):
            cat_dict[composer_id] = [Category(**x) for x in utils.read_json(filepath)]
            return cat_dict[composer_id]
        else:
            cat_dict[composer_id] = get_cats_helper(composer_id)
            for i, cat in enumerate(cat_dict[composer_id]):
                cat.index = i
        utils.write_json(cat_dict[composer_id], filepath)
    return cat_dict[composer_id]


def get_cat_works(composer_id, category, depth=0):
    global works_dict
    print(f"Getting works for {composer_id}, category {category.id}")
    # In this case, the works_dict requires 2 keys: Composer and Category.
    if not composer_id in works_dict.keys():
        works_dict[composer_id] = {}
    works = works_dict[composer_id]
    works = works.get(category.id, [])
    if len(works) > 0:
        return works

    cat_data = cat_dict.get(composer_id, [])
    cat = [x for x in cat_data if x.id == category.id]
    if len(cat) == 0:
        raise ValueError(f"No data for composer {composer_id} and category {category.id}")
    else:
        cat = cat[0]
    filepath = f"{METADATA_ROOT}/{composer_id}_{category.id}.works.json"
    print(f"filepath is {filepath}")
    if utils.path_exists(filepath):
        cache_expiry = 3600 * 24 * 7  # 7 days
        if (time.time() - os.stat(filepath)[7]) < cache_expiry:
            j = utils.read_json(filepath)
        else:
            utils.remove_file(filepath)

    if not utils.path_exists(filepath):
        url = f"{CLASSICAL_API}?mode=library&action=work&composer_id={composer_id}" + (
            f"&category_id={category.id}" if category.id is not None else ""
        )
        j = request_json(url, filepath)

    works = [Work(**(x | {"index": i})) for i, x in enumerate([x for x in j if x["type"] != "c"])]
    # if depth < 0:
    #    subcats = [Category(**(x | {"index": i})) for i, x in enumerate([x for x in j if x["type"] == "c"])]
    # else:
    #    subcats = []
    for w in works:
        w.genre = category.name
    if len(works) == 0:
        print("EMPTY CATEGORY!!!")
    else:
        works_dict[composer_id][category.id] = works
    return works


def get_tracklist(performance_id: int):
    protocol = 5  # 5: HLS without AES. 4: HLS with encryption. 7: M4A file (no access).
    url = f"{CLASSICAL_API}?action=get_stream&performance_id={performance_id}&sp={protocol}&verbose=1"
    tracklist = request_json(url)["tracks"]
    return tracklist


def set_knob_times(knob):
    global WORK_KEY_TIME
    global COMPOSER_KEY_TIME
    global GENRE_KEY_TIME
    global KNOB_TIME
    KNOB_TIME = time.ticks_ms()
    if knob == tm.m:
        COMPOSER_KEY_TIME = KNOB_TIME
    elif knob == tm.d:
        GENRE_KEY_TIME = KNOB_TIME
    elif knob == tm.y:
        WORK_KEY_TIME = KNOB_TIME
    return


load_state = clu.load_state
save_state = clu.save_state
request_json = clu.request_json


def configure(choice):
    assert choice in CONFIG_CHOICES, f"{choice} not in CONFIG_CHOICES: {CONFIG_CHOICES}"

    if choice == "Composers":
        return clu.configure_composers()
    elif choice == "Repertoire":
        return clu.configure_repertoire()
    elif choice == "Account":
        state = clu.configure_account()
    state = load_state()
    return


def play_pause(player):
    tm.clear_bbox(playpause_bbox)
    if player.is_playing():
        player.pause()
        tm.tft.fill_polygon(tm.PausePoly, playpause_bbox.x0, playpause_bbox.y0, tm.WHITE)
    elif len(player.tracklist) > 0:
        print(f"in play_pause: player.tracklist {player.tracklist}")
        player.play()
        tm.power(1)
        tm.tft.fill_polygon(tm.PlayPoly, playpause_bbox.x0, playpause_bbox.y0, tm.play_color)
    set_knob_times(None)  # So that twiddling any knob causes refresh screen.
    return


#def play_keyed_work(keyed_work, player, state):
def play_keyed_work(mind):
    print(f"Playing {mind.keyed_work}")
    mind.tracklist, mind.selected_performance, mind.state = select_performance(mind.keyed_work, mind.player, mind.state)
    save_state(mind.state)
    mind.selected_work = mind.keyed_work
    # Display the Title
    tracklist_bbox.y0 = display_title(mind.selected_work)
    # Display the performance information
    tracklist_bbox.y0 = display_performance_info(mind.keyed_work, mind.selected_performance)
    # Display the tracklist
    mind.track_titles = cleanup_track_names([x["subtitle"] for x in mind.tracklist])
    print(f"Track titles are {mind.track_titles}")
    display_tracks(*mind.track_titles)  # This doesn't show the credits.
    play_pause(mind.player)
#    return selected_work, track_titles, p_id
    return mind


def main_loop(player, state):
    global tracklist_bbox
    global HAS_TOKEN
    HAS_TOKEN = clu.validate_token(clu.access_token())
    pPower_old = 0
    pSelect_old = pPlayPause_old = pStop_old = pRewind_old = pFFwd_old = 1
    pYSw_old = pMSw_old = pDSw_old = 1
    tm.label_soft_knobs("Composer", "Genre", "Work")

    mind = MusicBoxState(player, state)

    clu.populate_favorites()  # Populate values for clu.FAVORITE_PERFORMANCES and clu.FAVORITE_WORKS
    composer_list = state.get("composer_list", ["GREATS"])
    composers = sorted(get_composers(composer_list), key=lambda x: x.name)
    if len(clu.FAVORITE_WORKS) > 0:
        composers.insert(0, Composer({"id": 0, "ln": "Favorites", "fn": ""}))
    tape = state["selected_tape"]
    # tm.m._max_val = len(composers) - 1
    mind.keyed_composer = get_composer_by_id(composers, tape.get("composer_id", composers[1].id))
    mind.selected_composer = mind.keyed_composer
    tm.m._value = clu.get_key_index(composers, mind.keyed_composer.id)
    month_old = -1  # to force the screen to start at composer.

    if state.get("repertoire", "Must Know") == "Full":
        composer_genres = get_cats(mind.selected_composer.id)
    else:
        composer_genres = get_genres(mind.selected_composer.id)
    try:
        tm.d._value = next(i for i, x in enumerate(composer_genres) if x.id == tape.get("genre_id", 1))
    except StopIteration:
        tm.d._value = 0
    day_old = tm.d.value()
    mind.keyed_genre = composer_genres[day_old]
    mind.selected_genre = mind.keyed_genre

    year_old = tm.y.value()
    works = None
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
        if player.playlist_completed and (len(mind.worklist) > 0):
            print(f"Player is finished, continuing the present worklist")
            mind.keyed_work = mind.worklist[0]
            mind.worklist = mind.worklist[1:]  # safer than popping, in case of empty list.
            clu.increment_worklist_dict(mind.worklist_key)
            #mind.selected_work, mind.track_titles, mind.selected_performance = play_keyed_work(mind.keyed_work, player, state)
            mind = play_keyed_work(mind)

        if pPlayPause_old != tm.pPlayPause.value():
            pPlayPause_old = tm.pPlayPause.value()
            if not pPlayPause_old:
                mind.play_pause_press_time = time.ticks_ms()
                print("PlayPause PRESSED")
                if (time.ticks_ms() - mind.play_pause_press_time) > 1_000:
                    continue  # go to top of loop -- This was a long press, so do nothing.
            else:
                print("short press of PlayPause -- RELEASED")
                if player.is_stopped():
                    state["selected_tape"]["composer_id"] = mind.selected_composer.id
                    state["selected_tape"]["genre_id"] = mind.selected_genre.id
                    mind.tracklist, mind.selected_performance, state = select_performance(mind.keyed_work, player, state)
                    save_state(state)
                    mind.selected_work = mind.keyed_work
                    tracklist_bbox.y0 = display_title(mind.selected_work)
                    mind.track_titles = cleanup_track_names([x["subtitle"] for x in mind.tracklist])
                    print(f"Track titles are {mind.track_titles}")
                    display_tracks(*mind.track_titles)
                play_pause(player)
                mind.last_update_time = time.ticks_ms()

        if not tm.pPlayPause.value():  # long press PlayPause
            if (time.ticks_ms() - mind.play_pause_press_time) > 1_000:
                print("                 Longpress of playpause")
                # clu.toggle_favorites(mind.selected_performance)
                mind.play_pause_press_time = time.ticks_ms() + 1_000
                pPlayPause_old = tm.pPlayPause.value()
                print("PlayPause RELEASED")

        if pStop_old != tm.pStop.value():
            pStop_old = tm.pStop.value()
            if pStop_old:
                print("Stop RELEASED")
            else:
                if tm.power():
                    tm.screen_on()
                    if player.stop():
                        tm.clear_bbox(playpause_bbox)
                    mind.worklist = mind.worklist[1:]
                print("Stop PRESSED")

        if pSelect_old != tm.pSelect.value():
            pSelect_old = tm.pSelect.value()
            if not pSelect_old:
                mind.select_press_time = time.ticks_ms()
                print("Select PRESSED")
            else:
                print("short press of select -- released")
                if (time.ticks_ms() - mind.select_press_time) > 1_000:
                    continue  # go to top of loop -- This was a long press, so do nothing.
                player.stop()
                mind.worklist = []
                if KNOB_TIME == COMPOSER_KEY_TIME:
                    print(f"Composer last keyed {mind.keyed_composer}")
                    mind.selected_composer = mind.keyed_composer
                    ## Play Composer Radio
                    # Not yet implemented
                elif KNOB_TIME == GENRE_KEY_TIME:
                    print(f"Genre last keyed {mind.keyed_genre}")
                    ## create playlist of all works in the genre
                    mind.selected_genre = mind.keyed_genre
                    mind.worklist_key = None
                    if state["repertoire"] == "Full":
                        mind.worklist = get_cat_works(mind.selected_composer.id, mind.selected_genre)
                        mind.worklist_key = f"{mind.selected_composer.id}_{mind.selected_genre.id}"
                    else:
                        mind.worklist = get_works(mind.selected_composer.id)
                    print(f"worklist is {mind.worklist}")
                    mind.worklist_index = clu.worklist_dict().get(mind.worklist_key, 0) % max(1, len(mind.worklist))
                    clu.set_worklist_dict(mind.worklist_key, mind.worklist_index)  # To keep the index within bounds of len(mind.worklist).
                    mind.keyed_work = mind.worklist[mind.worklist_index]
                    mind.worklist = mind.worklist[mind.worklist_index + 1 :] + mind.worklist[:mind.worklist_index]  # wrap around
                elif KNOB_TIME == WORK_KEY_TIME:
                    print(f"Work last keyed {mind.keyed_work}")
                else:
                    print("Unknown last keyed")

                if mind.keyed_work is None:
                    # Figure out which work and performance to play
                    # works = get_works(mind.selected_composer.id)
                    pass

                state["selected_tape"]["composer_id"] = mind.selected_composer.id
                state["selected_tape"]["genre_id"] = mind.selected_genre.id
                mind.selected_work, mind.track_titles, mind.selected_performance = play_keyed_work(mind.keyed_work, player, state)
                mind = play_keyed_work(mind)
                mind.last_update_time = time.ticks_ms()
                print("Select RELEASED")

        if not tm.pSelect.value():  # long press Select
            # pSelect_old = tm.pSelect.value()
            if (time.ticks_ms() - mind.select_press_time) > 1_000:
                player.pause()
                print("                 Longpress of select")
                mind.performance_index = choose_performance(mind.selected_composer, mind.keyed_work)  # take control of knobs
                if mind.performance_index is not None:
                    state["selected_tape"]["composer_id"] = mind.selected_composer.id
                    state["selected_tape"]["genre_id"] = mind.selected_genre.id
                    mind.tracklist, mind.selected_performance, state = select_performance(mind.keyed_work, player, state, mind.performance_index)
                    save_state(state)
                    mind.selected_work = mind.keyed_work
                    tracklist_bbox.y0 = display_title(mind.selected_work)
                    tracklist_bbox.y0 = display_performance_info(mind.selected_work, mind.selected_performance)
                    mind.track_titles = cleanup_track_names([x["subtitle"] for x in mind.tracklist])
                    print(f"Track titles are {mind.track_titles}")
                    display_tracks(*mind.track_titles)
                    play_pause(player)
                    mind.last_update_time = time.ticks_ms()
                else:
                    # behave as if we have twiddled a knob.
                    # tm.m._value = (tm.m.value() - 1) % len(composers)
                    set_knob_times(None)
                time.sleep(2)
                mind.select_press_time = time.ticks_ms() + 1_000
                pSelect_old = tm.pSelect.value()
                print("Select RELEASED")

        if pRewind_old != tm.pRewind.value():
            pRewind_old = tm.pRewind.value()
            if pRewind_old:
                print("Rewind RELEASED")
            else:
                print("Rewind PRESSED")
                if tm.power():
                    if tm.screen_state():
                        player.rewind()
                    else:
                        player.set_volume(max(player.get_volume() - 1, 5))
                        print(f"volume set to {player.get_volume()}")

        if pFFwd_old != tm.pFFwd.value():
            pFFwd_old = tm.pFFwd.value()
            if pFFwd_old:
                print("FFwd RELEASED")
            else:
                print("FFwd PRESSED")
                if tm.power():
                    if tm.screen_state():
                        player.ffwd()
                    else:
                        try:
                            player.set_volume(player.get_volume() + 1)
                        except AssertionError:
                            pass
                        print(f"volume set to {player.get_volume()}")

        if pPower_old != tm.pPower.value():
            # Press of Power button
            pPower_old = tm.pPower.value()
            if pPower_old:
                print("Power RELEASED")
            else:
                print(f"power state is {tm.power()}")
                if tm.power() == 1:
                    player.pause()
                    tm.power(0)
                else:
                    tm.power(1)
                mind.power_press_time = time.ticks_ms()
                print("Power PRESSED -- screen")

        if not tm.pPower.value():
            if (time.ticks_ms() - mind.power_press_time) > 1_000:
                print("Power UP -- back to reconfigure")
                mind.power_press_time = time.ticks_ms()
                tm.label_soft_knobs("-", "-", "-")
                tm.clear_screen()
                tm.write("Configure Music Box", 0, 0, pfont_med, tm.WHITE, show_end=-3)
                player.reset_player()
                tm.power(1)
                return

        if pYSw_old != tm.pYSw.value():
            pYSw_old = tm.pYSw.value()
            if pYSw_old:
                print("Right RELEASED")
                if not HAS_TOKEN:
                    was_playing = player.is_playing()
                    player.pause()
                    HAS_TOKEN = clu.authenticate_user()
                    state = load_state()  # State may have changed in authenticate_user
                    utils.reset()
                    # We need to update the screen here!!
                    if was_playing:
                        print("Restarting player after authenticating")
                        player.play()
                else:
                    print(f"mind.selected_performance is {mind.selected_performance}, keyed_work is {mind.keyed_work}")
                    favored = clu.toggle_favorites(mind.selected_performance if mind.selected_performance is not None else mind.keyed_work)
                    if favored:
                        print(f"Added {mind.selected_performance} to favorites")
                        # Draw the heart wherever on the screen it belongs
                    else:
                        print(f"Removed {mind.selected_performance} from favorites")
                        # Remove the heart from the screen.

            else:
                print("Right PRESSED")

        if pMSw_old != tm.pMSw.value():
            pMSw_old = tm.pMSw.value()
            if pMSw_old:
                print("Left RELEASED")
            else:
                tm.screen_off()  # screen off while playing
                print("Left PRESSED")

        if pDSw_old != tm.pDSw.value():
            pDSw_old = tm.pDSw.value()
            if pDSw_old:
                print("Center RELEASED")
            else:
                print("Center PRESSED")

        month_new = tm.m.value() % len(composers)
        day_new = tm.d.value()
        year_new = tm.y.value()

        if month_old != month_new:  # Composer changes # | year_old != year_new | day_old != day_new
            # print(f"time diff is {time.ticks_diff(time.ticks_ms(), WORK_KEY_TIME)}")
            # print(f"month_new: {month_new}")
            tm.power(1)
            mind.performance_index = 0
            force_update = (KNOB_TIME > COMPOSER_KEY_TIME) or (mind.last_update_time > KNOB_TIME)
            set_knob_times(tm.m)
            mind.keyed_composer = composers[month_new]
            display_keyed_composers(composers, month_new, month_old, force_update)
            print(f"keyed composer {mind.keyed_composer}")
            works = None
            month_old = month_new
        elif day_old != day_new:  # Genre changes
            tm.power(1)
            mind.performance_index = 0
            if mind.keyed_composer.id == 0: # "Favorites"
                mind.selected_composer, mind.selected_work, state = handle_favorites(composers, player, state)
                if mind.selected_work is None: # We bailed from handle favorites without selecting anything.
                    mind.selected_work = mind.keyed_work
                else:
                    mind.keyed_work = mind.selected_work 
                    mind.keyed_composer = mind.selected_composer 
                    mind.last_update_time = time.ticks_ms()
                    # tm.m._value = clu.get_key_index(composers, mind.selected_composer.id)
                    set_knob_times(None) # To ensure that genres will be drawn
            else:
                if mind.selected_composer != mind.keyed_composer:
                    mind.selected_composer = mind.keyed_composer  # we have selected the composer by changing the category
                    display_selected_composer(mind.selected_composer, show_loading=True)
                if state["repertoire"] == "Full":
                    composer_genres = get_cats(mind.selected_composer.id)
                    # print(f"cat_genres is {composer_genres}")
                else:
                    composer_genres = get_genres(mind.selected_composer.id)
                mind.keyed_genre = display_keyed_genres(mind.selected_composer, composer_genres, day_new, day_old)
                print(f"keyed genre is {mind.keyed_genre}")
                set_knob_times(tm.d) 
            day_old = day_new

        elif year_old != year_new:  # Works changes
            tm.power(1)
            mind.performance_index = 0
            if mind.selected_genre.index != mind.keyed_genre.index:
                mind.selected_genre = mind.keyed_genre
            if works is None:
                mind.selected_composer = mind.keyed_composer
                if mind.selected_composer.id == 0:
                    mind.selected_composer, mind.selected_work, state = handle_favorites(composers, player, state)
                    if mind.selected_work is None: # We bailed from handle favorites without selecting anything.
                        mind.selected_work = mind.keyed_work
                    else:
                        mind.keyed_work = mind.selected_work 
                        mind.keyed_composer = mind.selected_composer
                        mind.last_update_time = time.ticks_ms()
                        set_knob_times(None) # To ensure that genres will be drawn
                else:
                    display_selected_composer(mind.selected_composer, mind.selected_genre, show_loading=True)
                    if state["repertoire"] == "Full":
                        composer_genres = get_cats(mind.selected_composer.id)
                        print(f"cat_genres is {composer_genres}")
                    else:
                        composer_genres = get_genres(mind.selected_composer.id)
            t = [g for g in composer_genres if g.id == mind.keyed_genre.id]
            composer_genre = t[0] if len(t) > 0 else composer_genres[day_old % len(composer_genres)]
            print(f"composer_genre is {composer_genre}")
            if state["repertoire"] == "Full":
                works = get_cat_works(mind.selected_composer.id, composer_genre)
            else:
                works = get_works(mind.selected_composer.id)
                works = [w for w in works if w.genre == composer_genre.id]
            mind.keyed_work = display_keyed_works(mind.selected_composer, composer_genre, works, year_new, year_old)
            print(f"keyed work is {mind.keyed_work}")
            year_old = year_new
            set_knob_times(tm.y)

        if time.ticks_diff(time.ticks_ms(), max(KNOB_TIME, mind.last_update_time)) > 12_000:
            print(player)
            if KNOB_TIME > mind.last_update_time:
                update_display(player, mind.selected_composer, mind.selected_work, mind.selected_performance)
            mind.last_update_time = time.ticks_ms()


def handle_favorites(composers, player, state):
    global tracklist_bbox
    print("handling favorites")
    tm.clear_screen()
    tm.write("Favorites", 0, 0, pfont_med, tm.YELLOW)
    tm.write("loading ... ", 0, pfont_med.HEIGHT, pfont_small, tm.WHITE)
    favorites = clu.get_playlist_items("tm_favorites")
    selection = select_from_favorites(favorites)
    if selection is not None:
        selected_composer = get_composer_by_id(composers, int(selection["c_id"]))
        state["selected_tape"]["composer_id"] = selected_composer.id
        state["selected_tape"]["genre_id"] = 1  # Not sure what to do here
        selected_work = Work(name=selection["w_title"], id=int(selection["w_id"]))
        tracklist, selected_performance, state = select_performance(selected_work, player, state, p_id=selection["kv"])
        display_selected_composer(selected_composer, show_loading=True)
        tracklist_bbox.y0 = display_title(selected_work)
        tracklist_bbox.y0 = display_performance_info(selected_work, selected_performance)
        track_titles = cleanup_track_names([x["subtitle"] for x in tracklist])
        print(f"Track titles are {track_titles}")
        display_tracks(*track_titles)
        play_pause(player)
        set_knob_times(None)
    else:
        selected_composer = composers[1]  # Avoid favorites as a composer
        selected_work = None
    return selected_composer, selected_work, state


def update_display(player, composer, work, p_id):
    global tracklist_bbox

    print(f"Updating display for {composer}, {work}, {p_id}")
    tm.clear_bbox(playpause_bbox)
    if player.is_stopped():
        pass
    elif player.is_playing():
        display_selected_composer(composer)
        tracklist_bbox.y0 = display_title(work)
        tracklist_bbox.y0 = display_performance_info(work.id, p_id)
        display_tracks(*player.remaining_track_names())
        tm.tft.fill_polygon(tm.PlayPoly, playpause_bbox.x0, playpause_bbox.y0, tm.play_color)
    elif player.is_paused():
        tm.tft.fill_polygon(tm.PausePoly, playpause_bbox.x0, playpause_bbox.y0, tm.pause_color)


def display_title(work):
    tm.clear_bbox(work_bbox)
    title = work.name
    msg = tm.write(f"{title}", 0, work_bbox.y0, pfont_small, tm.YELLOW, show_end=-3, indent=2)
    if work.id in clu.FAVORITE_WORKS:
        tm.tft.fill_polygon(tm.HeartPoly, tm.SCREEN_WIDTH - 20, work_bbox.y0, tm.RED)
    return work_bbox.y0 + len(msg.split("\n")) * pfont_small.HEIGHT


def cleanup_track_names(track_names):
    # Define a regular expression pattern to match unwanted prefixes
    pattern = re.compile(r"^(No\.?\s*|Track\s*|#)\d+\s*[-:.,]*\s*")

    track_names = utils.remove_common_start(track_names)
    track_names = [s.lstrip(" .,0123456789") for s in track_names]
    track_names = utils.remove_common_start(track_names)
    track_names = [pattern.sub("", s) for s in track_names]
    for i, name in enumerate(track_names):
        if len(name) == 0:
            track_names[i] = f"Track {i+1}"
    return track_names


def get_this_performance(work_id, p_id):
    performances = get_performances(work_id)
    this_perf = None
    for perf in performances:
        if perf["p_id"] == p_id:
            this_perf = perf
            break
    return this_perf


def display_performance_info(work_id, p_id):
    # Display performance information for the selected work above the tracklist
    global tracklist_bbox
    if p_id is None:
        return tracklist_bbox.y0
    y0 = tracklist_bbox.y0
    this_perf = get_this_performance(work_id, p_id)
    if this_perf is None:
        return tracklist_bbox.y0
    print(f"Performance is {this_perf}")
    for prj in this_perf.get("performers", {"type": "Unknown", "name": "Unknown"}):
        msg = tm.write(f"{prj["name"]}", 0, y0, color=tm.PURPLE, font=pfont_small, show_end=1)
        y0 = y0 + pfont_small.HEIGHT * len(msg.split("\n"))
    tracklist_bbox.y0 = y0
    return tracklist_bbox.y0


def display_tracks(*track_names):
    print(f"in display_tracks. Track names are {track_names[:3]}...")
    if len(track_names) == 0:
        return
    tm.clear_to_bottom(0, tracklist_bbox.y0)
    lines_written = 0
    last_valid_str = 0
    in_credits = False

    for i in range(len(track_names)):
        if len(track_names[i]) > 0:
            last_valid_str = i
    i = 0
    y0 = tracklist_bbox.y0
    text_height = pfont_small.HEIGHT
    max_lines = (tm.SCREEN_HEIGHT - y0) // text_height
    while (lines_written < max_lines) and i < len(track_names):
        name = track_names[i]
        name = name.strip("-> ")  # remove trailing spaces and >'s
        if i <= last_valid_str and len(name) == 0:
            name = "Unknown"
        if name == "..credits..":
            name = " - -" * 20
            in_credits = True
        name = utils.capitalize(name.lower())
        y0 = tracklist_bbox.y0 + (text_height * lines_written)
        show_end = -2 if i == 0 else 0
        color = tm.WHITE if i == 0 else tm.tracklist_color if not in_credits else tm.PURPLE
        msg = tm.write(f"{name}", 0, y0, pfont_small, color, show_end, indent=2)
        lines_written += len(msg.split("\n"))
        i = i + 1
    if not HAS_TOKEN:
        print("Writing Subscription Note")
        # This message informs the user to press the right knob to access full tracks, likely requiring authentication or subscription.
        message = "Press Right knob for full tracks"
        n_lines = tm.add_line_breaks(message, 0, pfont_small, 2).count("\n") + 1
        y1 = tm.SCREEN_HEIGHT - n_lines * (text_height + 1)
        tm.clear_to_bottom(0, y1)
        tm.write(message, 0, y1, pfont_small, tm.YELLOW, show_end=-2)
    return


def display_keyed_title(keyed_title, color=tm.PURPLE):
    # print(f"in display_keyed_title {keyed_title}")
    tm.clear_bbox(tm.title_bbox)
    tm.write(keyed_title, tm.title_bbox.x0, tm.title_bbox.y0, color=color, font=pfont_small, show_end=-2)


def display_keyed_works(composer, composer_genre, works, index, prev_index):
    # Set up the display
    # print(f"in display_keyed_works -- {works}, of type {type(works)}, index {index}")
    names = [w.name for w in works]
    index = index % len(names)
    prev_index = prev_index % len(names)
    nlines, npixels = divmod(tm.SCREEN_HEIGHT - (2 * pfont_med.HEIGHT), pfont_small.HEIGHT)
    nlines = min(len(names), nlines)
    page_start = nlines * (index // nlines)
    prev_page_start = nlines * (prev_index // nlines)
    draw_all = (KNOB_TIME > WORK_KEY_TIME) or page_start != prev_page_start

    # Write the Composer and Genre
    if draw_all:
        display_selected_composer(composer, composer_genre)
    y0 = 2 * pfont_med.HEIGHT

    # Write the works
    for i in range(nlines):
        array_index = (page_start + i) % len(names)
        keyed_work = array_index == index
        prev_work = array_index == prev_index
        text = (">" if keyed_work else "") + names[(page_start + i) % len(names)]
        text_color = tm.WHITE if keyed_work else tm.PURPLE
        if (keyed_work or prev_work) or draw_all:
            if prev_work:
                tm.clear_area(selection_bbox.x0, y0 + i * pfont_small.HEIGHT, tm.SCREEN_WIDTH, pfont_small.HEIGHT)
            text = tm.write(text, 0, y0 + i * pfont_small.HEIGHT, color=text_color, font=pfont_small, show_end=1)
        if works[array_index].id in clu.FAVORITE_WORKS:
            tm.tft.fill_polygon(tm.HeartPoly, tm.SCREEN_WIDTH - 20, y0 + i * pfont_small.HEIGHT, tm.RED)
    return works[index]


def display_selected_composer(composer, composer_genre=None, show_loading=False):
    tm.clear_bbox(selection_bbox)
    y0 = 0
    tm.write(composer.name, 0, y0, color=tm.YELLOW, font=pfont_med, show_end=1)
    y0 = y0 + pfont_med.HEIGHT
    if composer_genre is not None:
        tm.write(composer_genre.name, 0, y0, color=tm.YELLOW, font=pfont_med, show_end=1)
        y0 = y0 + pfont_med.HEIGHT
    if show_loading:
        tm.write("loading from classicalarchives.com...", 0, y0, color=tm.WHITE, font=pfont_small, show_end=-3)


def display_keyed_genres(composer, composer_genres, index, prev_index):
    genres = [x.name for x in composer_genres]
    nlines = min(len(genres), (tm.SCREEN_HEIGHT - pfont_med.HEIGHT) // pfont_small.HEIGHT)
    y0 = pfont_med.HEIGHT
    index = index % len(genres)
    prev_index = prev_index % len(genres)
    start_index = nlines * (index // nlines)
    prev_start_index = nlines * (prev_index // nlines)
    draw_all = (KNOB_TIME > GENRE_KEY_TIME) or start_index != prev_start_index
    print( f"display keyed genre: all:{draw_all}, start {start_index} ({index}), prev {prev_start_index}({prev_index})")
    if draw_all:
        display_selected_composer(composer)
    for i in range(nlines):
        array_index = (start_index + i) % len(genres)
        keyed_genre = array_index == index
        prev_genre = array_index == prev_index
        if (keyed_genre or prev_genre) or draw_all:
            text = (">" if keyed_genre else "") + genres[(start_index + i) % len(genres)]
            text_color = tm.WHITE if keyed_genre else tm.PURPLE
            if composer_genres[array_index].nworks < 1:  # Empty categories
                text_color = tm.YELLOW
            if prev_genre:
                tm.clear_area(0, y0 + i * pfont_small.HEIGHT, tm.SCREEN_WIDTH, pfont_small.HEIGHT)
            tm.write(
                text,
                selection_bbox.x0,
                y0 + i * pfont_small.HEIGHT,
                color=text_color,
                font=pfont_small,
                show_end=-2 if keyed_genre else 1,
            )
    return composer_genres[index]


def display_keyed_composers(composers, index, prev_index, force_update=False):
    n_comp = len(composers)
    nlines = min(n_comp, tm.SCREEN_HEIGHT // pfont_small.HEIGHT)
    index = index % n_comp
    prev_index = prev_index % n_comp
    start_index = nlines * (index // nlines)
    prev_start_index = nlines * (prev_index // nlines)
    draw_all = force_update or start_index != prev_start_index
    if draw_all:
        tm.clear_bbox(selection_bbox)
    for i in range(nlines):
        array_index = (start_index + i) % n_comp
        keyed_composer = array_index == index
        prev_composer = array_index == prev_index
        text = (">" if keyed_composer else "") + composers[(start_index + i) % n_comp].name
        text_color = tm.WHITE if keyed_composer else tm.PURPLE
        if (keyed_composer or prev_composer) or draw_all:
            if prev_composer:
                tm.clear_area(selection_bbox.x0, i * pfont_small.HEIGHT, tm.SCREEN_WIDTH, pfont_small.HEIGHT)
            tm.write(text, selection_bbox.x0, i * pfont_small.HEIGHT, color=text_color, font=pfont_small, show_end=1)
    return


def get_performance_info(perf):
    pr = perf.get("performers", {"type": "Unknown", "name": "Unknown"})
    label = perf.get("label", "Unknown")
    n_tracks = perf.get("trk", 0)
    dur = int(perf.get("dur", 0))
    duration = f"{dur//3600}h{(dur%3600)//60:02}m" if dur > 3600 else f"{(dur%3600)//60:02}m{dur%60:02}s"
    date = perf.get("release_date", "1900-01-01")
    return pr, label, n_tracks, duration, date


def display_performance_choices(composer, work, performances, index):
    # Screen Layout:
    # Composer (medium font)
    # Work Title (medium font)
    # Release Date, Ntracks, Duration
    # performance titles (small font; up to 3 lines for current, 1 line for rest)
    #  ...
    # instructions to exit (small font)

    tm.clear_screen()
    display_selected_composer(composer)
    y0 = display_title(work)
    i = 0
    while y0 < tm.SCREEN_HEIGHT - 3 * pfont_small.HEIGHT:
        indx = (index + i) % len(performances)
        pr, label, n_tracks, duration, date = get_performance_info(performances[indx])
        ind = f"{indx+1}/{len(performances)}"
        color = tm.WHITE if i == 0 else tm.tracklist_color
        tm.write(ind, 0, y0, color=color, font=pfont_small, show_end=1)
        x0 = tm.SCREEN_WIDTH - tm.tft.write_len(pfont_small, f"{duration} {n_tracks}trk")
        tm.write(f"{duration} {n_tracks}trk", x0, y0, color=color, font=pfont_small, show_end=1)
        y0 = y0 + pfont_small.HEIGHT
        for prj in pr[:2]:
            ptype = prj["type"].replace("Chorus/", "")
            msg = tm.write(f"{ptype}: {prj["name"]}", 0, y0, color=color, font=pfont_small, show_end=-2)
            y0 = y0 + pfont_small.HEIGHT * len(msg.split("\n"))
        tm.write(label, 0, y0, color=color, font=pfont_small, show_end=1)
        x0 = tm.SCREEN_WIDTH - tm.tft.write_len(pfont_small, f"r:{date}")
        tm.write(f"r:{date}", x0, y0, color=color, font=pfont_small)
        y0 = y0 + pfont_small.HEIGHT
        i = i + 1
    return i


def show_composers(composer_list):
    message = "Loading Composers"
    print(f"{composer_list}")
    print(message)
    tm.clear_screen()
    tm.write(message, 0, 0, pfont_med, tm.YELLOW)
    y0 = pfont_med.HEIGHT

    for composer in composer_list:
        if isinstance(composer, int):
            composer_name = get_composers(abs(composer))[0].name
            if composer < 0:
                composer_name = f"-{composer_name}"
        else:
            composer_name = composer
        if y0 > tm.SCREEN_HEIGHT - pfont_small.HEIGHT:
            break
        tm.write(f"{composer_name}", 0, y0, pfont_small, color=tm.WHITE)
        y0 += pfont_small.HEIGHT
    time.sleep(0.5)


def select_from_favorites(favorites):
    # Hijack the knobs for navigation purposes
    # Show a set of favorites on the screen.
    # Scroll through options based on the knobs.
    # Poll for select, play, or stop buttons, to select a particular performance.
    print("In select_from_favorites")
    tm.clear_screen()
    tm.label_soft_knobs("Jump 100", "Jump 10", "Next/Prev")
    tm.write("Favorites", 0, 0, pfont_med, tm.YELLOW)
    y0 = pfont_med.HEIGHT
    incoming_knobs = (tm.m.value(), tm.d.value(), tm.y.value())
    tm.m._value = 0
    tm.d._value = 0
    tm.y._value = 0
    prev_index = -1
    button_press_time = time.ticks_ms()
    retval = None

    while True:
        index = tm.m.value() * 100 + tm.d.value() * 10 + tm.y.value()
        index = index % len(favorites)
        if index != prev_index:
            set_knob_times(None)  # force screen refresh
            display_favorite_choices(index, favorites)
            prev_index = index

        if time.ticks_diff(time.ticks_ms(), button_press_time) < 2_000:  # crude de-bouncing.
            continue
        if not tm.pYSw.value():  # drop a favorite
            button_press_time = time.ticks_ms()
            print("Year switch pressed -- toggling a favorite")
            favored = clu.toggle_favorites(favorites[index]["kv"])
            print(f"favorite {index} toggled. Favored = {favored}")
            if not favored:
                favorites.pop(index)
                prev_index = (prev_index - 2) % len(favorites)

        if not tm.pStop.value():
            retval = None
            break

        if (not tm.pSelect.value()) or (not tm.pPlayPause.value()):
            retval = favorites[index]
            break

        if time.ticks_diff(time.ticks_ms(), KNOB_TIME) > 120_000:
            print("Returning to composers/genres/works after 120 sec of inactivity")
            retval = None
            break
    tm.m._value, tm.d._value, tm.y._value = incoming_knobs
    tm.label_soft_knobs("Composer", "Genre", "Work")
    return retval


def display_favorite_choices(index, favorites):
    # Screen Layout:
    # "Favorites" (med font)
    # Composer (small font, 1 line)
    # Work Title (small font, up to 2 lines)
    # performer info (small font; up to 2 lines)
    #  ...
    # instructions to exit (small font)
    y0 = pfont_med.HEIGHT
    tm.clear_to_bottom(0, y0)
    i = 0
    # print(f"Displaying favorites from index {index}. Favorites = {favorites}")
    while y0 < tm.SCREEN_HEIGHT - 3 * pfont_small.HEIGHT:
        indx = (index + i) % len(favorites)
        ind = f"{indx+1}/{len(favorites)}"
        item = favorites[indx]
        color = tm.WHITE if i == 0 else tm.tracklist_color
        tm.write(ind, 0, y0, color=color, font=pfont_small)
        x0 = tm.tft.write_len(pfont_small, ind)
        tm.write(f"{item['c_ln']},{item['c_fn']}", x0 + 3, y0, color=color, font=pfont_small)
        y0 = y0 + pfont_small.HEIGHT
        msg = tm.write(item["w_title"], 0, y0, color=color, font=pfont_small, show_end=-3)
        y0 = y0 + pfont_small.HEIGHT * len(msg.split("\n"))
        for prj in item["performers"][:2]:
            msg = tm.write(f"{prj["name"]}", 0, y0, color=color, font=pfont_small, show_end=-2)
            y0 = y0 + pfont_small.HEIGHT * len(msg.split("\n"))
        i = i + 1
    return i


def choose_performance(composer, keyed_work):
    # Hijack the knobs for navigation purposes
    # Show a set of performance options on the screen.
    # Scroll through performance options based on the knobs.
    # Poll for select, play, or stop buttons, to select a particular performance.
    # Reset the knobs if necessary.
    tm.clear_screen()
    tm.label_soft_knobs("Jump 100", "Jump 10", "Next/Prev")
    display_selected_composer(composer)
    y0 = display_title(keyed_work)
    tm.write(" loading performances from classicalarchives.com ...", 0, y0, pfont_small, show_end=-3)

    performances = get_performances(keyed_work)
    print(f"There are {len(performances)} performances of work {keyed_work}")
    incoming_knobs = (tm.m.value(), tm.d.value(), tm.y.value())
    tm.m._value = 0
    tm.d._value = 0
    tm.y._value = 0
    pStop_old = tm.pStop.value()
    pPlayPause_old = tm.pPlayPause.value()
    prev_index = -1
    start_time = time.ticks_ms()

    while True:
        index = tm.m.value() * 100 + tm.d.value() * 10 + tm.y.value()
        if index != prev_index:
            set_knob_times(None)  # force screen refresh
            display_performance_choices(composer, keyed_work, performances, index)
            prev_index = index
        if pStop_old != tm.pStop.value():
            pStop_old = tm.pStop.value()
            if pStop_old:
                print("Stop DOWN")
            else:
                print("Stop UP")
                retval = None
                break

        if time.ticks_diff(time.ticks_ms(), start_time) < 2_000:  # crude de-bouncing.
            continue
        if (not tm.pSelect.value()) or (pPlayPause_old != tm.pPlayPause.value()):
            pPlayPause_old = tm.pPlayPause.value()
            retval = index % len(performances)
            break

        if time.ticks_diff(time.ticks_ms(), KNOB_TIME) > 120_000:
            print("Returning to composers/genres/works after 120 sec of inactivity")
            retval = None
            break
    tm.m._value, tm.d._value, tm.y._value = incoming_knobs
    tm.label_soft_knobs("Composer", "Genre", "Work")
    return retval


def select_performance(keyed_work, player, state, ntape=None, p_id=None):
    print(f"selecting performance of keyed_work {keyed_work}")
    tracklist_bbox.y0 = display_title(keyed_work)
    tm.clear_to_bottom(0, tracklist_bbox.y0)
    tm.write("loading...", 0, tracklist_bbox.y0, pfont_small, tm.WHITE)
    tm.clear_bbox(playpause_bbox)
    tm.tft.fill_polygon(tm.PausePoly, playpause_bbox.x0, playpause_bbox.y0, tm.RED)
    player.pause()  # was stop()
    if ntape is None:
        p_id = keyed_work.perf_id
        if p_id == 0:  # i.e, repertoire in Full, we don't get a p_id with the work.
            perf = get_performances(keyed_work)[0]
            p_id = perf["p_id"]
    elif p_id is None:  # p_id and ntape are both None
        perf = get_performances(keyed_work)[ntape]
        p_id = perf["p_id"]
    perf = get_this_performance(keyed_work.id, p_id)
    print(f"select_performance: Performance is {perf}")
    if perf:
        pr, label, n_tracks, duration, rel_date = get_performance_info(perf)
        additional_performers = [f'{prj["type"]}: {prj["name"]}' for prj in pr[2:]]
        credits = (
            ["..credits.."]
            + additional_performers
            + [f"Label: {label}", f"Released: {rel_date}", f"Duration: {duration}. {n_tracks} trks"]
        )
    else:
        credits = []
    print(f"performance id is {p_id}")
    tracklist_bbox.y0 = display_performance_info(keyed_work, p_id)
    tm.write("loading tracks...", 0, tracklist_bbox.y0, pfont_small, tm.WHITE, show_end=-3)
    state["selected_tape"]["work_id"] = keyed_work.id
    state["selected_tape"]["p_id"] = p_id
    # Display the performance information

    tracklist = get_tracklist(p_id)
    # print(f"tracklist is {[(x['subtitle'],x['url']) for x in tracklist]}")
    urllist = [x["url"] for x in tracklist]
    urllist = [re.sub(r"/a/", "/tm/", x) for x in urllist]  # Let's get it working w/ 5s chunks first
    titles = cleanup_track_names([x["subtitle"] for x in tracklist])
    player.set_playlist(titles, urllist, credits)
    return tracklist, p_id, state



def run():
    """run the livemusic controls"""
    try:
        wifi = utils.connect_wifi()
        state = load_state()
        print(f"state is {state}")  # Temporary
        composer_list = state["composer_list"]
        show_composers(composer_list)
        clu.initialize_knobs()

        player = playerManager.PlayerManager(callbacks={"display": display_tracks}, debug=False)
        main_loop(player, state)

    except Exception as e:
        if "Firmware" in str(e):
            raise utils.FirmwareUpdateRequiredException("AAC_Decoder not available in this firmware")
        msg = f"Classical: {e}"
        print(msg)
        with open("/exception.log", "w") as f:
            f.write(msg)
        if utils.is_dev_box():
            tm.clear_screen()
            msg = tm.write(msg, font=pfont_small, show_end=5)
            y0 = pfont_small.HEIGHT * len(msg.split("\n"))
            tm.write("Select to exit", 0, y0, color=tm.YELLOW, font=pfont_small)
            tm.poll_for_button(tm.pSelect, timeout=12 * 3600)
    return -1
