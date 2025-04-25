import json
import network
import re
import time
import utils

import archive_utils
import board as tm
import fonts.NotoSans_18 as pfont_small
import fonts.NotoSans_24 as pfont_med

try:
    from async_urequests import urequests as requests
except ImportError:
    from mrequests import mrequests as requests

METADATA_ROOT = "/metadata/classical"
CLASSICAL_API = "https://www.classicalarchives.com/ajax/cma-api-2.json"
TOKEN_FILE = "/metadata/classical/token.txt"
PLAYLIST_IDS = {}
FAVORITE_PERFORMANCES = []
FAVORITE_WORKS = []
perf_dict = {}


# ------------------------------------------------------------------------------------ API requests
def request_json(url, outpath="/tmp.json", debug=False):
    url0 = url
    state = load_state()
    if len(state["access_token"]) > 0 and not "access_token" in url0:
        url = f"{url0}&access_token={state['access_token']}"
    if debug:
        print(f"request_json: url: {url}")
    json_resp = archive_utils.get_request(url, outpath=outpath)
    return json_resp


# ------------------------------------------------------------------------------------ classes
class Composer:
    def __init__(self, data):
        self.id = data["id"]
        self.name = f"{data['ln']}, {data['fn']}"
        self._data = data

    def __repr__(self):  # dump the dict so that we can write to/read from json.
        return json.dumps(self.__dict__)

    def __str__(self):
        return f"{self.id} - {self.name}"


class Genre:
    # init with **kwargs so that we can instantiate from json. E.g. Genre(**utils.read_json(path))
    def __init__(self, **kwargs):  # name, id, works=[], index=0):
        self.name = kwargs["title"]
        self.id = kwargs["id"]
        self.index = kwargs.get("seq", 0)
        self.nworks = kwargs.get("nw", 0)
        self.parent = kwargs.get("pid", None)
        self.has_radio = kwargs.get("r", False)

    def __repr__(self):  # dump the dict so that we can write to/read from json.
        return json.dumps(self.__dict__)

    def __str__(self):
        return f"({self.index}) {self.id} - {self.name} - {self.nworks} works"


class Category:
    # init with **kwargs so that we can instantiate from json. E.g. Category(**utils.read_json(path))
    def __init__(self, **kwargs):  # name, id, works=[], index=0):
        self.name = kwargs["name"]
        self.id = kwargs["id"]
        self.nworks = kwargs.get("nworks", -1)
        self.index = kwargs.get("index", 0)
        # self.works = [Work(**x) for x in kwargs.get("works", [])]

    def __repr__(self):  # dump the dict so that we can write to/read from json.
        return json.dumps(self.__dict__)

    def __str__(self):
        return f"({self.index}) {self.id} - {self.name} "  # + (f"[{len(self.works)}]" if len(self.works) > 0 else "[]")


class Work:
    def __init__(self, **kwargs):  # name, id, index=0):
        self.name = kwargs["name"]
        self.id = kwargs["id"]
        self.index = kwargs.get("index", 0)
        self.genre = kwargs.get("genre", 0)
        self.period = kwargs.get("period", 0)
        self.perf_id = kwargs.get("perf_id", 0)

    def __repr__(self):
        return json.dumps(self.__dict__)

    def __str__(self):
        return f"({self.index}) {self.id} - {self.name}."


def get_composers(composer_list, match_field="lnu", beyond_notable=False):
    # NOTE This uses the library, which makes it very slow. It would be nice if we could limit this
    # to the 110 creators, instead of dealing with 17,000 extra composers
    if isinstance(composer_list, (str, int)):
        composer_list = [composer_list]
    url = f"{CLASSICAL_API}?mode=library&action=comp"
    full_outpath = f"{METADATA_ROOT}/composers_all.json"
    outpath = full_outpath if beyond_notable else f"{METADATA_ROOT}/composers.json"
    composers = []
    if utils.path_exists(outpath):
        ALL_COMPOSERS = utils.read_json(outpath)
    else:
        if utils.path_exists(full_outpath):
            try:
                ALL_COMPOSERS = utils.read_json(full_outpath)
            except Exception as e:
                utils.remove_file(full_outpath)
                ALL_COMPOSERS = request_json(url, outpath=full_outpath)
        else:
            ALL_COMPOSERS = request_json(url, outpath=full_outpath)
        if not beyond_notable:
            ALL_COMPOSERS = [x for x in ALL_COMPOSERS if x["nc"]]  # Notable only
            utils.write_json(ALL_COMPOSERS, outpath)

    for composer in composer_list:
        if composer == "GREATS":
            composers += [x for x in ALL_COMPOSERS if x["gc"]]
        elif composer == "NOTABLES":
            composers += [x for x in ALL_COMPOSERS if x["nc"]]
        elif composer == "ALL":
            composers = ALL_COMPOSERS
        else:
            if utils.isinteger(composer):
                if composer > 0:
                    composers += [x for x in ALL_COMPOSERS if x["id"] == int(composer)]
                else:
                    composers = [x for x in composers if x["id"] != abs(int(composer))]
            else:
                if match_field == "name":
                    composers += [x for x in ALL_COMPOSERS if Composer(x).name == composer]
                else:
                    composers += [x for x in ALL_COMPOSERS if x[match_field] == composer]
    # Add this name to the cache of composers, so we can avoid reading full file when queried again
    if match_field == "name" and beyond_notable:
        print(f"Adding {composers} to {outpath}")
        outpath = f"{METADATA_ROOT}/composers.json"
        ALL_COMPOSERS = utils.read_json(outpath)
        ALL_COMPOSERS += composers
        utils.write_json(ALL_COMPOSERS, outpath)

    composers = [Composer(x) for x in [x for x in composers if len(x["lnu"]) > 0]]
    return composers


def get_composer_by_id(composers, composer_id):
    print(f"getting composer {composer_id}")
    composer_key_index = get_key_index(composers, composer_id)
    return composers[max(0, composer_key_index)]


def get_key_index(composers, composer_id):
    # Return the index in the list of composers matching the composer_id
    for i, c in enumerate(composers):
        if c.id == composer_id:
            return i
    return -1


# ------------------------------------------------------------------------------------ configure composers
# NOTE This should move to classical_utils, but it depends on get_composers, which is harder to move.
def configure_composers():
    choices = ["Add Composer", "Remove Composer", "Greats Only", "Remove All Greats", "Beyond Notables", "Cancel"]
    choice = utils.select_option("Select Option", choices)
    print(f"configure_collection: chose to {choice}")
    if choice == "Cancel":
        return
    print(f"current collection_list is {get_composer_list_names()}")
    if choice == "Add Composer":
        tm.clear_screen()
        tm.write("Loading Notable Composers ... ", 0, 0, pfont_med, show_end=-4)
        all_composer_names = [c.name for c in get_composers("ALL", beyond_notable=False)]
        utils.add_list_element("Composer (notable)", all_composer_names, get_composer_list_names, modify_composer_list)

    elif choice == "Remove Composer":
        utils.remove_list_element(get_composer_list_names, lambda x: modify_composer_list(x, remove=True))

    elif choice == "Greats Only":
        state = load_state()
        state["composer_list"] = ["GREATS"]
        save_state(state)
        utils.reset()

    elif choice == "Remove All Greats":
        state = load_state()
        composer_list = state.get("composer_list", ["GREATS"])
        composer_list = [x for x in composer_list if x != "GREATS"]
        if len(composer_list) > 0:
            state["composer_list"] = composer_list
            save_state(state)
            utils.reset()
        else:
            tm.clear_screen()
            tm.write("At least one composer required", 0, 0, pfont_small, tm.WHITE, show_end=-4)
            time.sleep(3)

    elif choice == "Beyond Notables":  # Add composers who are not Notable -- NOT REALLY WORKING because no genres.
        tm.clear_screen()
        tm.write("Loading ALL Composers ... ", 0, 0, pfont_med, show_end=-4)
        all_composer_names = [c.name for c in get_composers("ALL", beyond_notable=True)]
        utils.add_list_element(
            "Composer (any)",
            all_composer_names,
            get_composer_list_names,
            lambda x: modify_composer_list(x, beyond_notable=True),
        )


def get_composer_list_names():
    composer_list = get_composers(expand_composer_list(get_composer_list()))
    return [c.name for c in composer_list]


def modify_composer_list(new_composer_name, remove=False, beyond_notable=False):
    state = load_state()
    composer_list = state.get("composer_list", ["GREATS"])
    new_composer = get_composers(new_composer_name, match_field="name", beyond_notable=beyond_notable)[0]
    if remove:
        try:
            composer_list.remove(new_composer.id)
        except ValueError:
            composer_list.append(-new_composer.id)
    else:
        composer_list = [x for x in composer_list if isinstance(x, str) or abs(x) != new_composer.id] + [new_composer.id]
    state["composer_list"] = composer_list
    save_state(state)


def get_composer_list():
    # The composer_list is stored in state as a list of items, which may be "GREATS", <int> or -<int>.
    # If the item is a negative integer, then that composer id should be removed from the list, if it is present after expanding "GREATS"
    #
    # Return: list of composers as read in the state file

    state = load_state()
    composer_list = state.get("composer_list", ["GREATS"])
    if "GREATS" in composer_list:  # remove any "extra" greats
        greats_ids = [x.id for x in get_composers("GREATS")]
        composer_list = [x for x in composer_list if isinstance(x, str) or not x in greats_ids]
    for composer in composer_list:
        if isinstance(composer, str):
            continue
        if (composer < 0) and (-composer in composer_list):
            # remove both negative and positive values in the list, if both present
            composer_list = [x for x in composer_list if isinstance(x, str) or abs(x) != abs(composer)]
    state["composer_list"] = composer_list
    save_state(state)
    return composer_list


def expand_composer_list(composer_list):
    # return the list on composer_ids that are in the current composer_list. ie. GREATS -> list of ids
    if "GREATS" in composer_list:
        composer_list.remove("GREATS")
        greats = get_composers("GREATS")
        greats_list = [g.id for g in greats]
        composer_id_list = composer_list + greats_list
        composer_id_list = utils.distinct(composer_id_list)
    else:
        composer_id_list = composer_list
    # coll_list should be all integers or strings of integers at this point
    for composer_id in composer_id_list.copy():  # NOTE: because I am removing elements, I must loop over a copy
        if composer_id < 0:
            composer_id_list.remove(composer_id)
            if abs(composer_id) in composer_id_list:
                composer_id_list.remove(abs(composer_id))
    composer_id_list = utils.distinct(composer_id_list)
    return composer_id_list


# ------------------------------------------------------------------------------------ performances

#'{|}~áäçèéëíòóöüÿčřš′'
favored_names = {
    "Perahia": 100,
    "Vladimir Horowitz": 100,
    "Glenn Gould": 100,
    "Arthur Rubinstein": 100,
    "Szell": 100,
    "Karajan": 100,
    "Solti": 60,
    "Barenboim": 60,
    "Abbado": 60,
    "Bernstein": 60,
    "Klemperer": 60,
    "Furtwängler": 60,
    "Böhm": 60,
    "Kubelik": 60,
    "Cleveland": 60,
    "London": 60,
    "Berlin": 60,
    "Prague": 60,
    "New York": 50,
    # "Muti": 60,
    # "Maazel": 60,
    # "Haitink": 60,
}


@micropython.native
def score(perf, track_counts_mode=(0, 0)):
    if track_counts_mode == (0, 0):
        return 1
    promotion = 0
    # date = 19000101
    n_tracks = perf.get("trk", 0)
    track_count_penalty = 100 if n_tracks < track_counts_mode[1] else 65  # too few tracks is worse than too many
    trk = max(0, 1000 - track_count_penalty * min(abs(n_tracks - track_counts_mode[0]), abs(n_tracks - track_counts_mode[1])))
    dur = perf.get("dur", 0) // 60
    dur = dur if dur <= 15 else min(15 + (dur - 15) // 10, 30)
    try:
        perf_info = perf.get("performers", [{"type": "Unknown", "name": "Unknown"}])
        for performer_item in perf_info:
            for favored_name, favored_value in favored_names.items():
                if re.search(favored_name.lower(), performer_item.get("name", "").lower()):
                    promotion += favored_value
        # date = int(perf.get("release_date", "1900-01-01").replace("-", ""))
    except ValueError:
        pass
    return dur + trk + promotion


def get_performances(work):
    global perf_dict
    if isinstance(work, Work):
        work_id = work.id
    elif isinstance(work, int):
        work_id = work

    if work_id in perf_dict.keys():
        return perf_dict[work_id]

    url = f"{CLASSICAL_API}?mode=library&action=perf&work_id={work_id}"
    performances = request_json(url)
    track_counts = [perf.get("trk", 0) for perf in performances[:35]]  # for symphonies prefer 4 tracks generally
    # compute bimodal track counts if one of the modes is 1 track (e.g. Eugene Onegin)
    track_counts_set = set(track_counts)
    if not track_counts:
        track_counts_mode = (0, 0)
    elif (track_counts_set == {1}) or (track_counts.count(1) / len(track_counts) >= 0.9):
        track_counts_mode = (1, 1)
    elif track_counts_set == {1, 2}:
        track_counts_mode = (1, 2)
    elif track_counts_set == {2}:
        track_counts_mode = (2, 2)
    else:
        track_counts_mode = max(track_counts_set, key=track_counts.count)
        track_counts_mode = (track_counts_mode, max(track_counts_set - {1, 2}, key=track_counts.count))
    print(f"getting performances, before sorting {time.ticks_ms()}. Track counts mode is {track_counts_mode}")
    performances = sorted(performances[:30], key=lambda perf: score(perf, track_counts_mode), reverse=True) + performances[30:]
    if work_id in FAVORITE_WORKS:  # Promote a favorite performance to the top of the list, regardless of score.
        for i, p in enumerate(performances):
            if p["p_id"] in FAVORITE_PERFORMANCES:
                performances.insert(0, performances.pop(i))
                break

    print(f"{time.ticks_ms()}. Top score {score(performances[0],track_counts_mode)}, {performances[0].get('trk',0)} tracks")
    perf_dict[work_id] = performances
    return performances


# ------------------------------------------------------------------------------------ authentication
def configure_account():
    print("Configuring Account")
    token = access_token()
    if validate_token(token):
        choices = ["Logout", "Change Account", "Cancel"]
    else:
        choices = ["Login", "Cancel"]
    choice = utils.select_option("Select Option", choices)
    print(f"configure_account: chose {choice}")
    if choice == "Cancel":
        return
    state = load_state()
    if choice == "Login":
        if authenticate_user():
            state = load_state()
    elif choice == "Logout":
        logout_user()
        state = load_state()
        # Print a message to the screen indicating that the user has been logged out.
        time.sleep(2)
        # Print a message to the screen indicating that the user has been logged out.
        # Adding a delay to ensure the user sees the logout confirmation message.
    elif choice == "Change Account":
        logout_user()
        if authenticate_user():
            state = load_state()
    save_state(state)
    utils.reset()


def authenticate_user_password():
    validated = False
    tm.clear_screen()
    tm.label_soft_knobs("", "jump 10", "next")
    eml = utils.select_chars("User email", "Credentials for classicalarchives.com. Press Stop to end")
    eml = utils.url_escape(eml)
    tm.clear_screen()
    pwd = utils.select_chars("password", "Credentials for classicalarchives.com. Press Stop to end")
    pwd = utils.url_escape(pwd)
    url = f"{CLASSICAL_API}?action=register_device&eml={eml}&pwd={pwd}&dev=timemachine"
    try:
        resp = requests.get(url)
        if resp.status_code == 200:
            token = resp.json().get("access_token", "")
            if len(token) > 0:
                state = load_state()
                state["access_token"] = token
                save_state(state)
                utils.write_file(TOKEN_FILE, token)
                tm.clear_screen()
                tm.write("Authentication Successful", 0, 0, pfont_small, show_end=-2)
                time.sleep(2)
                validated = True
        else:
            tm.clear_screen()
            tm.write(f"Failed response {resp.status_code}", 0, 0, pfont_small, tm.YELLOW, show_end=-2)
            time.sleep(2)
            validated = False
    except Exception as e:
        print(f"Error in authenticate_user: {e}")
        tm.clear_screen()
        tm.write("Authentication Failed", 0, 0, pfont_small, tm.YELLOW, show_end=-2)
        time.sleep(2)
        validated = False
    finally:
        tm.label_soft_knobs("Composer", "Genre", "Work")
    return validated


def getlinkcode():
    mac_address = network.WLAN().config("mac").hex()
    url = f"{CLASSICAL_API}?action=oauth_getlinkcode&deviceid=TimeMachine%20{mac_address}"
    oauth_resp = request_json(url)
    return oauth_resp


def authenticate_user_qr():
    tm.clear_screen()
    tm.label_soft_knobs("", "", "")
    # Send API call to server to obtain code.
    # auth_code = requests.get("https://prs.net/tm/get_code").text
    linkcode = getlinkcode()
    x0, y0 = utils.qr_code(linkcode["oauthUrl"])
    msg = tm.write(
        f"Visit {linkcode['oauthShortUrl']} to authenticate. Code {linkcode['linkCode']}",
        0,
        y0,
        pfont_small,
        tm.YELLOW,
        show_end=-3,
    )
    y0 = y0 + pfont_small.HEIGHT * len(msg.split("\n"))
    token = poll_for_token(linkcode, y0=y0)
    validated = validate_token(token)
    if validated:
        tm.clear_to_bottom(0, y0)
        tm.write("Authentication Successful", 0, y0, pfont_small, show_end=-2)
    else:
        tm.clear_to_bottom(0, y0)
        tm.write("Authentication Failed", 0, y0, pfont_small, show_end=-2)
        time.sleep(4)
    time.sleep(1)
    tm.clear_screen()
    tm.label_soft_knobs("Composer", "Genre", "Work")
    return validated


def poll_for_token(auth_code, timeout=60 * 15, y0=0):
    # Poll server for validation
    token = ""
    start_time = time.time()
    while time.time() - start_time < timeout:
        elapsed_time = time.time() - start_time
        print(f"Polling for token: {auth_code}. Time elapsed: {elapsed_time}/{timeout}s")
        tm.write(f"Polling: {timeout - elapsed_time}s", 0, y0, pfont_med, tm.WHITE)
        tm.write(f"Stop to cancel", 0, y0 + pfont_med.HEIGHT, pfont_med, tm.YELLOW)
        resp = requests.get(
            f"{CLASSICAL_API}?action=oauth_getauthtoken&linkCode={auth_code['linkCode']}&linkDeviceId={auth_code['linkDeviceId']}"
        ).json()
        if "error" in resp.keys():
            if resp["error"].endswith("FAILURE"):
                return ""
            elif resp["error"].endswith("RETRY"):
                time.sleep(5)
                continue
        else:
            token = resp.get("authToken", "")
        if tm.poll_for_button(tm.pStop, 1):
            print(f"Cancelled polling for token. Time elapsed: {time.time() - start_time}s")
            break
        if token != "":
            break
    return token


authenticate_user = authenticate_user_qr


def validate_token(token):
    # Check that the token provided is valid.
    result_of_validation = len(token) > 0  # for now
    if result_of_validation:
        state = load_state()
        state["access_token"] = token
        save_state(state)
    return result_of_validation


def access_token():
    state = load_state()
    token = state.get("access_token", "")
    return token


def logout_user():
    state = load_state()
    state["access_token"] = ""
    save_state(state)


# ------------------------------------------------------------------------------------ worklists
def worklist_dict():
    path = f"{METADATA_ROOT}/worklists.json"
    if not utils.path_exists(path):
        return {}
    worklist_dict = utils.read_json(path)
    return worklist_dict


def increment_worklist_dict(key):
    if key is None:
        return
    val = worklist_dict().get(key, 0) + 1
    set_worklist_dict(key, val)


def set_worklist_dict(key, val):
    # Not strictly required, but useful to keep the val within bounds of the length of the worklist.
    if key is None:
        return
    wl_dict = worklist_dict()
    wl_dict_change = {key: val}
    wl_dict.update(wl_dict_change)
    utils.write_json(wl_dict, f"{METADATA_ROOT}/worklists.json")


# ------------------------------------------------------------------------------------ cache management
def clear_cache(pattern="*"):
    utils.remove_files(f"{METADATA_ROOT}/{pattern}")


# ------------------------------------------------------------------------------------ knobs
def initialize_knobs():
    tm.y._min_val = 0
    tm.m._min_val = 0
    tm.d._min_val = 0
    tm.y._range_mode = tm.y.RANGE_UNBOUNDED  # 1
    # tm.y._range_mode = tm.y.RANGE_BOUNDED
    tm.m._range_mode = tm.m.RANGE_UNBOUNDED  # 1  # was tm.m.RANGE_WRAP
    tm.d._range_mode = tm.d.RANGE_UNBOUNDED  # 1  # RotaryIRQ.RANGE_UNBOUNDED
    tm.m._value = 0
    tm.d._value = 0
    tm.y._value = 0
    # tm.y._range_mode = tm.y.RANGE_WRAP
    # tm.d._range_mode = tm.d.RANGE_WRAP


# ------------------------------------------------------------------------------------ playlist management
def create_playlist(playlist_name):
    member_alias = get_member_alias()
    if len(member_alias) == 0:
        member_alias = create_member_alias()  # raise exception if unable to create member alias
    url = f"{CLASSICAL_API}?mode=edit_playlist&action=create_playlist&title={playlist_name}"
    resp = request_json(url)
    playlist_id = None
    if resp.get("result", "error") == "OK":
        playlist_id = resp.get("public_playlist_id", -1)
    return playlist_id


def toggle_favorites(performance_id):
    print(f"toggle_favorites: p_ids: {performance_id}, type: {type(performance_id)}")
    result = 0  # 0 means removed, 1 means added
    if performance_id is None:
        return result
    p_ids, w_ids = get_playlist_ids("tm_favorites")
    if isinstance(performance_id, Work):
        work_id = performance_id.id
        print(f"toggle_favorites: performance_id is a Work: {work_id}")
        if work_id in w_ids:
            for i, w_id in enumerate(w_ids):
                if w_id == work_id:
                    remove_from_playlist("tm_favorites", p_ids[i])
                    result = 0
                    break
        else:
            performance_id = get_performances(work_id)[0].get("p_id", 0)
            add_to_playlist("tm_favorites", performance_id)
            result = 1
    else:
        if performance_id in p_ids:
            remove_from_playlist("tm_favorites", performance_id)
            result = 0
        else:
            add_to_playlist("tm_favorites", performance_id)
            result = 1

    # NOTE We could speed this up by just updating the lists.
    populate_favorites()
    print(f"toggle_favorites returning {result}")
    return result


def populate_favorites():
    global FAVORITE_PERFORMANCES
    global FAVORITE_WORKS
    FAVORITE_PERFORMANCES, FAVORITE_WORKS = get_playlist_ids("tm_favorites")
    print(f"populate_favorites: FAVORITE_PERFORMANCES: {FAVORITE_PERFORMANCES}, FAVORITE_WORKS: {FAVORITE_WORKS}")


def add_to_playlist(playlist_name, performance_id):
    print(f"add_to_playlist: adding performance_id {performance_id} to {playlist_name}")
    if (performance_id is None) or (playlist_name == ""):
        print("Returning without adding")
        return
    playlist_id = get_public_playlist_id(playlist_name)
    if playlist_id == -1:
        playlist_id = create_playlist(playlist_name)

    # add this performance to the playlist.
    url = f"{CLASSICAL_API}?mode=edit_playlist&action=add_performance&public_playlist_id={playlist_id}&performance_id={performance_id}"
    resp = request_json(url, debug=True)
    return


def remove_from_playlist(playlist_name, performance_id):
    print(f"remove_from_playlist: removing performance_id {performance_id} from {playlist_name}")
    playlist_items = get_playlist_items(playlist_name)
    playlist_id = get_public_playlist_id(playlist_name)
    items_to_keep = []
    for item in playlist_items:
        if item["kv"] != performance_id:
            items_to_keep.append(str(item["item_id"]))
    print(f"remove_from_playlist: items_to_keep: {items_to_keep}")
    # remove this performance from the playlist.
    url = f"{CLASSICAL_API}?mode=edit_playlist&action=update_playlist_items&public_playlist_id={playlist_id}&item_list={','.join(items_to_keep)}"
    resp = request_json(url, debug=True)
    return


def get_playlist_ids(playlist_name):
    items = get_playlist_items(playlist_name)
    performance_ids = [item["kv"] for item in items if item["kt"] == "p"]
    work_ids = [int(item["w_id"]) for item in items if item["kt"] == "p"]
    return performance_ids, work_ids


def get_playlist_items(playlist_name):
    if not glc.HAS_TOKEN:
        return []
    print(f"getting playlist items from {playlist_name}")
    playlist_id = get_public_playlist_id(playlist_name)
    url = f"{CLASSICAL_API}?mode=edit_playlist&action=list_playlist_items&public_playlist_id={playlist_id}"
    items = request_json(url)
    items = [x for x in items if x.get("kt", "") in ["p"]]  # , "w"]]
    return items


def get_public_playlist_id(playlist_name):
    global PLAYLIST_IDS
    if PLAYLIST_IDS.get(playlist_name, -1) != -1:
        return PLAYLIST_IDS[playlist_name]
    playlist_id = -1
    my_playlists = request_json(f"{CLASSICAL_API}?mode=playlists&action=my")
    for playlist in my_playlists:
        if playlist.get("title", "") == playlist_name:
            playlist_id = playlist.get("public_playlist_id", -1)
            PLAYLIST_IDS[playlist_name] = playlist_id
            break
    return playlist_id


def get_member_info():
    url = f"{CLASSICAL_API}?action=member"
    resp = request_json(url)
    return resp


def get_member_alias():
    mi = get_member_info().get("member", {})
    return mi.get("member_alias", "")


def propose_member_alias():
    # Create a member alias based on the MAC address of the device.
    mac_address = network.WLAN().config("mac").hex()
    member_alias = f"tm{mac_address}"[:16]
    return member_alias


def create_member_alias(proposed_alias=None):
    if proposed_alias is None:
        proposed_alias = propose_member_alias()
    successful = False
    i_tries = 0
    while not successful:
        url = f"{CLASSICAL_API}?action=set_member_alias&member_alias={proposed_alias}"
        resp = request_json(url)
        if resp.get("result", "error") == "OK":
            print(f"Created member alias: {proposed_alias}")
            return proposed_alias
        elif "already" in resp.get("error", ""):
            proposed_alias = f"{proposed_alias[:15]}{chr(ord("Z") - i_tries)}"
        i_tries += 1
        if i_tries > 5:
            raise RuntimeError("Unable to create member alias")


"""
def manage_playlist():
    tm.clear_screen()
    tm.label_soft_knobs("", "", "next")
    knob_vals = utils.capture_knob_values()
    my_playlists = request_json(f"{CLASSICAL_API}?mode=playlists&action=my")
    print(f"manage_playlist: my_playlists: {my_playlists}")
    choices = my_playlists + ["Create Playlist", "Cancel"]
    choice = utils.select_option("Playlist Manager", choices)
    print(f"manage_playlist: chose {choice}")
    if choice == "Create Playlist":
        create_playlist()
    initialize_knobs()
    tm.label_soft_knobs("Composer", "Genre", "Work")
    utils.restore_knob_values(*knob_vals)
    tm.d._value = tm.d.value() + 1  # to trigger the screen to show the categories
"""


# ------------------------------------------------------------------------------------ radio stuff
radio_groups = [
    "Early/Renaissance",
    "Baroque",
    "Classical",
    "Romantic",
    "Late Romantic",
    "Impressionist",
    "Modern",
    "Orchestral",
    "Chamber",
    "Solo Instrument",
    "Vocal",
    "Stage (incl. Opera)",
]


def get_custom_radio_id(radio_options):
    # Get the radio id for the selected periods and genres.
    # This is a string of the form "fw:pgrggr:1,2;3,4"
    # where 1,2 are the period ids and 3,4 are the genre ids.
    # The first part is the period ids, and the second part is the genre ids.
    # The ids are separated by commas and semicolons.
    # The periods are 1-7 and the genres are 8-12.
    # The periods are 1-7 and the genres are 8-12.
    if not radio_options:
        return None
    periods = []
    genres = []
    for option in radio_options:
        ind = 1 + radio_groups.index(option)
        if ind <= 7:
            periods.append(ind)
        else:
            genres.append(ind - 7)
    radio_id = f"fw:pgrggr:{','.join([str(x) for x in periods])};{','.join([str(x) for x in genres])}"
    print(f"radio_id is {radio_id}")
    return radio_id


def get_radio_name(radio_id):
    # Get the radio name for the selected periods and genres.
    # This is a string of the form "fw:pgrggr:1,2;3,4"
    # where 1,2 are the period ids and 3,4 are the genre ids.
    # The parts before the ; are period ids, after ; are the genre ids.
    # The ids are separated by commas
    # The periods are 1-7 and the genres are 8-12.
    print(f"get_radio_name: radio_id is {radio_id}")
    works = ""
    radio_name = radio_id
    radio_id = radio_id.split(":")
    if radio_id[0] == "fw":
        works = " works"
    if "pgrggr" in radio_id:
        pgr = radio_id[-1].split(";")
        periods = [int(x) for x in pgr[0].split(",")]
        genres = [int(x) + 7 for x in pgr[1].split(",")]
        radio_name = f"Radio: {', '.join([radio_groups[x - 1] for x in periods + genres])}{works}"
    elif "composer" in radio_id:
        composer_name = get_composer_by_id(glc.composers, int(radio_id[-1])).name
        radio_name = f"Radio:{works} {composer_name}"
    print(f"radio_name is {radio_name}")
    return radio_name


# ------------------------------------------------------------------------------------ state management
def load_state():
    state = utils.load_state("classical")
    return state


def save_state(state):
    utils.save_state(state, "classical")


# ------------------------------------------------------------------------------------ context
class ScreenContext:
    NONE = 0
    COMPOSER = 1
    GENRE = 2
    WORK = 3
    PERFORMANCE = 4
    TRACKLIST = 5
    FAVORITES = 6
    RADIO = 7
    OTHER = 8


class GeneralContext:
    def __init__(self):
        self.player = None
        self.state = None
        self.works = None
        self.composers = None
        self.composer_genres = None
        self.keyed_composer = None
        self.keyed_genre = None
        self.keyed_work = None
        self.selected_composer = None
        self.selected_genre = None
        self.selected_work = None
        self.selected_performance = None
        self.this_work_y = None
        self.performance_index = 0
        self.tracklist = []
        self.track_titles = []
        self.worklist = []
        self.worklist_key = None
        self.worklist_index = 0
        self.last_update_time = 0
        self.play_pause_press_time = 0
        self.select_press_time = 0
        self.power_press_time = 0
        self.ycursor = 0
        self.radio_id = None
        self.radio_mode = None
        self.radio_counter = 0
        self.radio_data = []
        self.SCREEN = ScreenContext.NONE
        self.prev_SCREEN = ScreenContext.NONE
        self.HAS_TOKEN = False

    def __repr__(self):
        items = [
            f"player: {self.player}",
            f"state: {self.state}",
            f"works: {self.works}",
            f"composers: {self.composers}",
            f"composer_genres: {self.composer_genres}",
            f"keyed_composer: {self.keyed_composer}",
            f"keyed_genre: {self.keyed_genre}",
            f"keyed_work: {self.keyed_work}",
            f"selected_composer: {self.selected_composer}",
            f"selected_genre: {self.selected_genre}",
            f"selected_work: {self.selected_work}",
            f"selected_performance: {self.selected_performance}",
            f"this_work_y: {self.this_work_y}",
            f"performance_index: {self.performance_index}",
            f"tracklist: {self.tracklist}",
            f"track_titles: {self.track_titles}",
            f"worklist: {self.worklist}",
            f"worklist_key: {self.worklist_key}",
            f"worklist_index: {self.worklist_index}",
            f"last_update_time: {self.last_update_time}",
            f"play_pause_press_time: {self.play_pause_press_time}",
            f"select_press_time: {self.select_press_time}",
            f"power_press_time: {self.power_press_time}",
            f"ycursor: {self.ycursor}",
            f"radio_id: {self.radio_id}",
            f"radio_mode: {self.radio_mode}",
            f"radio_counter: {self.radio_counter}",
            f"radio_data: {self.radio_data}",
            f"SCREEN: {self.SCREEN}",
            f"prev_SCREEN: {self.prev_SCREEN}",
            f"HAS_TOKEN: {self.HAS_TOKEN}",
        ]
        return "GeneralContext:\n" + "\n".join(items)


glc = GeneralContext()
glc.SCREEN = ScreenContext.NONE
