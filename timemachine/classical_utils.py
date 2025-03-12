import archive_utils
import utils
import board as tm
import time
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


def authenticate_user():
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
        validated = False
    finally:
        tm.label_soft_knobs("Composer", "Genre", "Work")
    return validated


def authenticate_user_qr():
    tm.clear_screen()
    tm.label_soft_knobs("", "", "")
    # Send API call to server to obtain code.
    # auth_code = requests.get("https://prs.net/tm/get_code").text
    auth_code = "123456"
    url = f"https://prs.net/tm/{auth_code}"
    x0, y0 = utils.qr_code(url)
    msg = tm.write(f"Visit https://prs.net/tm/{auth_code} to authenticate.", 0, y0, pfont_small, tm.YELLOW, show_end=-2)
    y0 = y0 + pfont_small.HEIGHT * len(msg.split("\n"))
    token = poll_for_token(auth_code, y0=y0)
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


def poll_for_token(auth_code, timeout=60 * 6, y0=0):
    # Poll server for validation
    token = ""
    start_time = time.time()
    while time.time() - start_time < timeout:
        elapsed_time = time.time() - start_time
        print(f"Polling for token: {auth_code}. Time elapsed: {elapsed_time}/{timeout}s")
        tm.write(f"Polling: {timeout - elapsed_time}s", 0, y0, pfont_med, tm.WHITE)
        tm.write(f"Stop to cancel", 0, y0 + pfont_med.HEIGHT, pfont_med, tm.YELLOW)
        # token = requests.get(f"https://prs.net/tm/validate/{auth_code}").text
        if elapsed_time > 10:
            token = utils.read_file(TOKEN_FILE)[0].strip()
        if tm.poll_for_button(tm.pStop, 1):
            print(f"Cancelled polling for token. Time elapsed: {time.time() - start_time}s")
            break
        if token != "":
            break
    return token


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


# ------------------------------------------------------------------------------------ repertoire
def configure_repertoire():
    state = load_state()
    repertoire = state.get("repertoire", "Must Know")
    choices = ["Must Know", "Full", "No Change"]
    choice = utils.select_option(f"Select Option (now: {repertoire})", choices)
    print(f"configure_collection: chose {choice}")
    if choice in ["No Change", "Cancel", repertoire]:
        return

    state["repertoire"] = choice
    save_state(state)
    utils.reset()


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
    p_ids, w_ids = get_playlist_ids("tm_favorites")
    if performance_id in p_ids:
        remove_from_playlist("tm_favorites", performance_id)
    else:
        add_to_playlist("tm_favorites", performance_id)

    # NOTE We could speed this up by just updating the lists.
    populate_favorites()


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
    print(f"getting playlist items from {playlist_name}")
    playlist_id = get_public_playlist_id(playlist_name)
    url = f"{CLASSICAL_API}?mode=edit_playlist&action=list_playlist_items&public_playlist_id={playlist_id}"
    items = request_json(url)
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
    wifi = utils.connect_wifi()
    mac_address = wifi.config("mac").hex()
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


# ------------------------------------------------------------------------------------ state management
def load_state():
    state = utils.load_state("classical")
    return state


def save_state(state):
    utils.save_state(state, "classical")
