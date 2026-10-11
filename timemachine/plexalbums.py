"""Artist / Album / Track browsing with shared Plex accounts."""

import gc
import time

import audioPlayer
import board as tm
import plex
import utils

CONFIG_CHOICES = ["Plex"]


def configure(choice):
    assert choice in CONFIG_CHOICES
    return plex.configure("plexalbums")


def load_catalog():
    catalog = {}
    for client in plex.get_plex_clients("plexalbums"):
        try:
            albums = client.get_catalog_albums()
        except Exception as error:
            print("Unable to load Plex library %s: %s" % (client.section_name, error))
            continue
        for album in albums:
            album["client"] = client
            catalog.setdefault(album["artist"], []).append(album)
    for albums in catalog.values():
        albums.sort(key=lambda row: (row["release_date"] or "9999", row["title"].lower()))
    return catalog


class Browser:
    def __init__(self, catalog):
        self.catalog = catalog
        self.artists = sorted(catalog, key=lambda name: str(name).lower())
        self.artist_index = 0
        self.album_index = 0
        self.track_index = 0
        self.tracks = None
        self.page = "Artist"

    @property
    def artist(self):
        return self.artists[self.artist_index] if self.artists else ""

    @property
    def albums(self):
        return self.catalog.get(self.artist, [])

    @property
    def album(self):
        return self.albums[self.album_index] if self.albums else None

    def get_tracks(self):
        if self.tracks is None:
            album = self.album
            self.tracks = [] if album is None else album["client"].get_album_tracks(album["album"])
            self.tracks.sort(key=lambda row: (row.get("disc_number", 1), row["track_number"]))
        return self.tracks

    def turn(self, page, delta):
        previous_page = self.page
        self.page = page
        if page == "Artist" and self.artists and delta:
            self.artist_index = (self.artist_index + delta) % len(self.artists)
            self.album_index = self.track_index = 0
            self.tracks = None
        elif page == "Album" and self.albums and delta:
            self.album_index = (self.album_index + delta) % len(self.albums)
            self.track_index = 0
            self.tracks = None
        elif page == "Track":
            tracks = self.get_tracks()
            if previous_page in ("Artist", "Album"):
                self.track_index = 0
            else:
                self.track_index = (self.track_index + delta) % len(tracks) if tracks else 0

    def restore_playback(self, playback):
        selection = playback.get("selection")
        if selection is not None:
            self.artist_index, self.album_index, self.tracks = selection
            remaining = playback.get("tracks", [])
            self.track_index = self.tracks.index(remaining[0]) if remaining else 0
        self.page = "Playing"

    def play_selection(self, player):
        tracks = self.get_tracks()
        if not tracks:
            return False
        start = self.track_index if self.page == "Track" else 0
        player.stop()
        player.set_playlist(
            [row["title"] for row in tracks[start:]],
            [row["stream_url"] for row in tracks[start:]],
        )
        player.play()
        return True


def display_page(browser, playing=None, track_names=()):
    font = getattr(tm, "pfont_tiny", tm.pfont_small)
    height = font.HEIGHT
    bottom = min(tm.SCREEN_HEIGHT, tm.SCREEN_VPARTS[0]) if len(tm.SCREEN_VPARTS) > 1 else tm.SCREEN_HEIGHT
    page = browser.page
    entries = []

    def write(text, x, y, font, color, show_end):
        entries.append((text, x, y, font, color, show_end))

    write(page, 0, 0, font, tm.YELLOW, show_end=1)
    ycursor = height
    if page != "Artist":
        artist = playing[0] if page == "Playing" and playing else browser.artist
        write(artist, 0, ycursor, font, tm.GREEN, show_end=1)
        ycursor += height
    if page in ("Track", "Playing") and browser.album:
        title = playing[1] if page == "Playing" and playing else browser.album["title"]
        title = tm.add_line_breaks(title, 0, font, -3)
        write(title, 0, ycursor, font, tm.YELLOW, show_end=0)
        ycursor += height * len(title.split("\n"))
    if page == "Artist":
        labels, index = browser.artists, browser.artist_index
    elif page == "Album":
        labels = [row["title"] for row in browser.albums]
        index = browser.album_index
    elif page == "Track":
        track_rows = browser.get_tracks()
        labels = ["%s %s" % (row["track_number"], row["title"]) for row in track_rows]
        index = browser.track_index
    else:
        track_rows = [
            row if isinstance(row, dict) else {"track_number": position + 1, "title": row}
            for position, row in enumerate(track_names)
            if row
        ]
        labels, index = ["%s %s" % (row["track_number"], row["title"]) for row in track_rows], 0
    nlines = max(1, (bottom - ycursor) // height)
    start = nlines * (index // nlines)
    end = min(start + nlines, len(labels))
    if page == "Album":
        labels = [
            tm.add_line_breaks((">" if position == index else "") + label, 0, font, -3) for position, label in enumerate(labels)
        ]
        start = 0
        used_lines = 0
        for position, label in enumerate(labels):
            lines = len(label.split("\n"))
            if used_lines + lines > nlines and position > start:
                if position > index:
                    break
                start = position
                used_lines = 0
            used_lines += lines
        else:
            position = len(labels)
        end = position
    selected_text = None
    selected_lines = 1
    if page in ("Track", "Playing") and labels:
        selected_text = ">" + track_rows[index]["title"]
        if nlines > 1:
            selected_text = tm.add_line_breaks(selected_text, 0, font, -2)
            selected_lines = len(selected_text.split("\n"))
            if selected_lines > 1 and index == start + nlines - 1:
                start += 1
                end = min(start + nlines, len(labels))
    if not labels:
        write("No playable tracks" if page == "Track" else "No items", 0, ycursor, font, tm.WHITE, show_end=1)
    for position in range(start, end):
        selected = position == index
        if page in ("Track", "Playing") and selected_lines > 1 and position == index + 1:
            ycursor += height
            continue
        prefix = ">" if selected and page != "Album" else ""
        write(
            selected_text if page in ("Track", "Playing") and selected else prefix + labels[position],
            0,
            ycursor,
            font,
            tm.WHITE if selected else tm.PURPLE,
            show_end=0 if page == "Album" or (page in ("Track", "Playing") and selected_lines > 1 and selected) else 1,
        )
        ycursor += height * (len(labels[position].split("\n")) if page == "Album" else 1)
    rows = {}
    for text, x, y, entry_font, color, show_end in entries:
        for offset, line in enumerate(text.split("\n")):
            row_y = y + offset * height
            if row_y + height <= bottom:
                rows[row_y] = (line, x, entry_font, color, show_end)
    display_key = (tm, font, height, bottom, page)
    previous_key, previous_rows = getattr(browser, "_display_frame", (None, {}))
    full_redraw = previous_key != display_key
    if full_redraw:
        tm.clear_screen()
        changed = set(rows)
    else:
        changed = {row_y for row_y in set(rows) | set(previous_rows) if rows.get(row_y) != previous_rows.get(row_y)}
        for row_y in sorted(changed):
            tm.clear_area(0, row_y, tm.SCREEN_WIDTH, height)
    for text, x, y, entry_font, color, show_end in entries:
        if any(y + offset * height in changed for offset in range(len(text.split("\n")))):
            tm.write(text, x, y, entry_font, color, show_end=show_end)
    if full_redraw:
        tm.label_soft_knobs("Artist", "Album", "Track", (tm.BLACK, tm.GREEN, tm.RED))
    browser._display_frame = (display_key, rows)


def main_loop(browser, player, state, playback):
    knobs = (tm.m, tm.d, tm.y)
    pages = ("Artist", "Album", "Track")
    for knob in knobs:
        knob._range_mode = knob.RANGE_UNBOUNDED
        knob._value = 0
    previous = [knob.value() for knob in knobs]
    buttons = (tm.pSelect, tm.pPlayPause, tm.pStop, tm.pRewind, tm.pFFwd, tm.pPower, tm.pMSw, tm.pDSw, tm.pYSw)
    button_values = [button.value() for button in buttons]
    power_pressed = None
    resume_at = None
    last_browse_time = None
    display_page(browser)
    while True:
        player.audio_pump()
        for position, knob in enumerate(knobs):
            value = knob.value()
            if value != previous[position]:
                last_browse_time = time.ticks_ms()
                tm.power(1)
                browser.turn(pages[position], value - previous[position])
                previous[position] = value
                display_page(browser)
        for position, button in enumerate(buttons):
            value = button.value()
            if value == button_values[position]:
                continue
            button_values[position] = value
            if value:
                if button == tm.pPower:
                    power_pressed = None
                continue
            if button == tm.pPower:
                power_pressed = time.ticks_ms()
                resume_at = None
                if tm.power():
                    player.pause()
                    tm.power(0)
                else:
                    tm.power(1)
                    display_page(browser, playback["album"], playback["tracks"])
                continue
            if button == tm.pMSw:
                tm.screen_off()
                continue
            if not tm.power():
                continue
            if button not in (tm.pRewind, tm.pFFwd):
                tm.screen_on()
            if button == tm.pSelect or (button == tm.pPlayPause and not player.playlist):
                last_browse_time = time.ticks_ms()
                if browser.page == "Artist":
                    browser.page = "Album"
                    display_page(browser)
                elif browser.get_tracks():
                    playback["album"] = (browser.artist, browser.album["title"])
                    start = browser.track_index if browser.page == "Track" else 0
                    playback["playlist"] = browser.get_tracks()[start:]
                    if browser.play_selection(player):
                        playback["selection"] = (browser.artist_index, browser.album_index, browser.get_tracks())
                        resume_at = None
                        state["artist"] = browser.artist
                        state["album_key"] = str(browser.album["rating_key"])
                        client = browser.album["client"]
                        state["album_source"] = [client.plex_user, client.server_name, client.section_name]
                        state["volume"] = player.get_volume()
                        utils.save_state(state, "plexalbums")
                        browser.page = "Playing"
                    display_page(browser, playback["album"], playback["tracks"])
                else:
                    browser.page = "Track"
                    display_page(browser)
            elif button == tm.pPlayPause:
                if player.is_playing():
                    player.pause()
                    resume_at = None
                else:
                    player.play()
                    browser.page = "Playing"
                display_page(browser, playback["album"], playback["tracks"])
            elif button == tm.pStop:
                resume_at = None
                player.stop()
            elif button in (tm.pRewind, tm.pFFwd):
                if not tm.screen_state():
                    volume = player.get_volume() + (-1 if button == tm.pRewind else 1)
                    player.set_volume(max(1, min(11, volume)))
                    state["volume"] = player.get_volume()
                    utils.save_state(state, "plexalbums")
                else:
                    resume = player.is_playing() or resume_at is not None
                    player.rewind() if button == tm.pRewind else player.ffwd()
                    if resume:
                        resume_at = time.ticks_add(time.ticks_ms(), 1000)
            elif button == tm.pDSw or button == tm.pYSw:
                last_browse_time = time.ticks_ms()
                browser.turn("Album" if button == tm.pDSw else "Track", 0)
                display_page(browser)
        if (
            last_browse_time is not None
            and browser.page != "Playing"
            and player.is_playing()
            and playback["album"] is not None
            and tm.power()
            and time.ticks_diff(time.ticks_ms(), last_browse_time) >= 30_000
        ):
            browser.restore_playback(playback)
            last_browse_time = None
            display_page(browser, playback["album"], playback["tracks"])
        if resume_at is not None and time.ticks_diff(time.ticks_ms(), resume_at) >= 0:
            resume_at = None
            if player.playlist and tm.power():
                player.play()
        if power_pressed is not None and time.ticks_diff(time.ticks_ms(), power_pressed) > 1250:
            tm.power(1)
            return


def run():
    tm.power(1)
    tm.clear_screen()
    tm.write("Loading Plex albums", 0, 0, tm.pfont_small, tm.YELLOW, show_end=1)
    catalog = load_catalog()
    if not catalog:
        tm.clear_screen()
        message = (
            "No Plex libraries selected" if plex.get_configured_section_count("plexalbums") == 0 else "No Plex albums found"
        )
        tm.write(message, 0, 0, tm.pfont_small, tm.YELLOW, show_end=1)
        return -1
    browser = Browser(catalog)
    state = utils.load_state("plexalbums")
    if state.get("artist") in browser.artists:
        browser.artist_index = browser.artists.index(state["artist"])
        for position, album in enumerate(browser.albums):
            client = album["client"]
            source = [client.plex_user, client.server_name, client.section_name]
            if str(album["rating_key"]) == state.get("album_key") and source == state.get("album_source", source):
                browser.album_index = position
                break
    playback = {"album": None, "tracks": (), "playlist": []}

    def display_tracks(*track_names):
        remaining = len([name for name in track_names if name])
        playlist = playback["playlist"]
        playback["tracks"] = playlist[len(playlist) - remaining :] if remaining else []
        if browser.page == "Playing":
            display_page(browser, playback["album"], playback["tracks"])

    player = audioPlayer.AudioPlayer(callbacks={"display": display_tracks}, debug=False)
    player.set_volume(state.get("volume", 11))
    try:
        main_loop(browser, player, state, playback)
    finally:
        player.reset_player()
        gc.collect()
    return -1
