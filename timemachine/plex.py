try:
    from timemachine.plex_mini import MyPlexAccount
except Exception:
    try:
        from .plex_mini import MyPlexAccount
    except Exception:
        from plex_mini import MyPlexAccount

import utils
import board as tm


class PlexMetadataClient:
    # Per-run caches shared by all instances.
    _ACCOUNT_CACHE = {}
    _SERVER_CACHE = {}
    _SECTION_CACHE = {}

    def __init__(self, plex_user, plex_password, plex_server=None, section_name=None, date_range=None):
        self.plex_user = plex_user
        self.plex_password = plex_password
        # Discovery mode should not force immediate login. Authentication is lazy
        # via _get_account_cached() so we only attempt account login when needed.
        self.account = None
        self.plex = None
        self.music = None
        self.date_range = date_range
        self.server_name = plex_server
        self.section_name = section_name

        # Playback mode: bind immediately when server/section are provided.
        if plex_server is not None:
            self.plex = self._get_connected_server(plex_server)
            if section_name is not None:
                self.music = self.plex.library.section(section_name)

    def _cache_key(self):
        return (self.plex_user, self.plex_password)

    def _get_account_cached(self):
        key = self._cache_key()
        account = PlexMetadataClient._ACCOUNT_CACHE.get(key)
        if account is None:
            account = MyPlexAccount(self.plex_user, self.plex_password)
            PlexMetadataClient._ACCOUNT_CACHE[key] = account
        self.account = account
        return account

    def _get_connected_server(self, server_name):
        key = (self._cache_key(), server_name)
        plex = PlexMetadataClient._SERVER_CACHE.get(key)
        if plex is not None:
            return plex

        account = self._get_account_cached()
        plex = account.resource(server_name).connect()
        PlexMetadataClient._SERVER_CACHE[key] = plex
        return plex

    def servers(self):
        key = self._cache_key()
        cached = PlexMetadataClient._SERVER_CACHE.get((key, "__server_list__"))
        if cached is not None:
            return cached

        resources = self._get_account_cached().resources()
        names = []
        for res in resources:
            server_name = getattr(res, "name", None)
            if server_name and server_name not in names:
                names.append(server_name)
        PlexMetadataClient._SERVER_CACHE[(key, "__server_list__")] = names
        return names

    def _date_span_in_title(self, title):
        text = str(title or "").strip()
        if len(text) < 10:
            return "", -1

        for start in range(0, len(text) - 9):
            candidate = text[start : start + 10]
            normalized = candidate.replace("_", "-")
            if utils.is_valid_iso_date(normalized):
                return normalized, start

        return "", -1

    def _strip_trailing_parenthetical(self, text):
        value = str(text or "").strip()
        if not value.endswith(")"):
            return value

        open_idx = value.rfind("(")
        if open_idx < 0:
            return value

        suffix = value[open_idx + 1 : -1].strip()
        if not suffix:
            return value

        compact = suffix.replace(" ", "").replace("-", "")
        if len(compact) > 8 or not compact.isalpha():
            return value

        return value[:open_idx].rstrip(" -_:|,")

    def _normalize_album_title(self, title):
        raw_title = str(title or "").strip()
        date_str, date_start = self._date_span_in_title(raw_title)
        if not date_str:
            return ""

        tail = raw_title[date_start + 10 :].strip(" -_:|,")
        tail = self._strip_trailing_parenthetical(tail)

        if tail:
            return f"{date_str} {tail}"
        return date_str

    def _is_supported_audio_media(self, media_item, part_key):
        container = str(getattr(media_item, "container", "") or "").strip().lower()
        if container in ("mp3", "ogg"):
            return True

        # Some Plex rows omit container metadata; use key extension as fallback.
        key_text = str(part_key or "").strip().lower()
        if key_text.endswith(".mp3") or key_text.endswith(".ogg"):
            return True

        return False

    def music_sections(self, server_name):
        key = (self._cache_key(), server_name)
        cached = PlexMetadataClient._SECTION_CACHE.get(key)
        if cached is not None:
            return cached

        plex = self._get_connected_server(server_name)
        sections = []
        for section in plex.library.sections():
            section_type = str(getattr(section, "type", "")).strip().lower()
            if section_type == "artist":
                sec_name = str(getattr(section, "title", "")).strip()
                if sec_name and sec_name not in sections:
                    sections.append(sec_name)
        PlexMetadataClient._SECTION_CACHE[key] = sections
        return sections

    @classmethod
    def clear_cache(cls, plex_user=None):
        if plex_user is None:
            cls._ACCOUNT_CACHE.clear()
            cls._SERVER_CACHE.clear()
            cls._SECTION_CACHE.clear()
            return

        account_keys = [k for k in cls._ACCOUNT_CACHE.keys() if k[0] == plex_user]
        for k in account_keys:
            if k in cls._ACCOUNT_CACHE:
                del cls._ACCOUNT_CACHE[k]

        server_keys = [k for k in cls._SERVER_CACHE.keys() if k[0][0] == plex_user]
        for k in server_keys:
            if k in cls._SERVER_CACHE:
                del cls._SERVER_CACHE[k]

        section_keys = [k for k in cls._SECTION_CACHE.keys() if k[0][0] == plex_user]
        for k in section_keys:
            if k in cls._SECTION_CACHE:
                del cls._SECTION_CACHE[k]

    def iter_albums(self):
        if self.music is None:
            return
        for album in self.music.searchAlbums():
            date_str, _date_start = self._date_span_in_title(getattr(album, "title", ""))
            if not date_str:
                continue

            if self.date_range:
                year = int(date_str[:4])
                if year < min(self.date_range) or year > max(self.date_range):
                    continue
            yield album

    def get_albums(self):
        albums = []
        for album in self.iter_albums():
            normalized_title = self._normalize_album_title(getattr(album, "title", ""))
            albums.append(
                {
                    "title": normalized_title or album.title,
                    "artist": album.parentTitle,
                    "rating_key": album.ratingKey,
                    "year": album.year,
                }
            )
        return albums

    def get_album_tracks(self, album):
        tracks = []
        if self.plex is None:
            return tracks
        album_rating_key = str(getattr(album, "ratingKey", "") or "")
        for position, track in enumerate(album.tracks(), start=1):
            stream_url = ""
            media_items = getattr(track, "media", [])
            for media_item in media_items:
                parts = getattr(media_item, "parts", [])
                if not parts:
                    continue

                part_key = getattr(parts[0], "key", "")
                if not part_key:
                    continue

                container = str(getattr(media_item, "container", "") or "").strip().lower()
                part_key_lower = str(part_key).strip().lower()
                is_flac = container == "flac" or part_key_lower.endswith(".flac")

                # For FLAC, use universal transcode URL keyed by track metadata id.
                if is_flac:
                    track_rating_key = str(getattr(track, "ratingKey", "") or "")
                    metadata_rating_key = track_rating_key or album_rating_key
                    if metadata_rating_key:
                        stream_url = self.plex.transcode_album_url(metadata_rating_key)
                    break

                if not self._is_supported_audio_media(media_item, part_key):
                    continue

                stream_url = self.plex.url(part_key, includeToken=True)
                break

            if not stream_url:
                continue

            tracks.append(
                {
                    "track_number": position,
                    "title": getattr(track, "title", "Unknown Track"),
                    "stream_url": stream_url,
                }
            )
        return tracks

    def _album_metadata(self, album):
        title = str(getattr(album, "title", "")).strip()
        date_str, date_start = self._date_span_in_title(title)

        artist = str(getattr(album, "parentTitle", "")).strip()
        if date_str:
            tail = title[date_start + 10 :].strip(" -_:|,")
        else:
            tail = ""
        tail = self._strip_trailing_parenthetical(tail)

        vcs_text = tail
        if not vcs_text:
            vcs_text = artist
        if not vcs_text:
            vcs_text = title

        return date_str, artist, vcs_text

    def get_vcs_by_date(self):
        """Return livemusic-style metadata map: {iso_date: vcs_string}."""
        vcs_by_date = {}
        for album in self.iter_albums():
            date_str, _artist, vcs_text = self._album_metadata(album)
            if not date_str:
                continue

            if date_str not in vcs_by_date and vcs_text:
                vcs_by_date[date_str] = vcs_text
        return vcs_by_date

    def _query_albums_for_date(self, key_date):
        """Try targeted Plex album queries for this date before full scan.

        This reduces first-time selection latency without adding discovery cost.
        """
        if self.music is None:
            return []

        candidates = []
        seen = set()
        query_values = [str(key_date)]
        underscored = str(key_date).replace("-", "_")
        if underscored not in query_values:
            query_values.append(underscored)

        for query_value in query_values:
            try:
                # Keep query bounded so unsupported filters do not fetch the
                # entire library through this fast path. Date queries rarely
                # have more than a few matching albums.
                matches = self.music.searchAlbums(title=query_value, maxresults=20)
            except Exception:
                matches = []

            matched_for_date = 0
            for album in matches:
                date_str, _artist, _vcs = self._album_metadata(album)
                if date_str != key_date:
                    continue
                matched_for_date += 1
                rating_key = str(getattr(album, "ratingKey", "") or "")
                dedupe_key = rating_key if rating_key else str(getattr(album, "title", ""))
                if dedupe_key in seen:
                    continue
                seen.add(dedupe_key)
                candidates.append(album)

            if matched_for_date > 0:
                print(f"Plex date lookup fast path hit for {key_date} ({self.server_name}/{self.section_name})")
                return candidates

        return []

    def get_trackdata_for_date(self, key_date, artist_name=None):
        artist_name_norm = str(artist_name).strip().lower() if artist_name is not None else None
        candidates = []

        fast_candidates = self._query_albums_for_date(key_date)
        if len(fast_candidates) > 0:
            albums_to_check = fast_candidates
        else:
            # If fast query returned nothing and we're filtering by artist, skip the
            # expensive fallback - this library doesn't have albums for this date.
            if artist_name_norm is not None:
                return []
            # Fallback for servers that ignore title filters.
            print(f"Plex date lookup fell back to full scan for {key_date} ({self.server_name}/{self.section_name})")
            albums_to_check = self.iter_albums()

        for album in albums_to_check:
            date_str, artist, vcs_text = self._album_metadata(album)
            if date_str != key_date:
                continue

            if artist_name_norm is not None and str(artist).strip().lower() != artist_name_norm:
                continue

            track_rows = self.get_album_tracks(album)
            tracklist = []
            urls = []
            for row in track_rows:
                stream_url = str(row.get("stream_url", "")).strip()
                if not stream_url:
                    continue
                tracklist.append(str(row.get("title", "Unknown Track")))
                urls.append(stream_url)

            if len(urls) == 0:
                continue

            candidates.append(
                {
                    "artist": artist,
                    "album_title": str(getattr(album, "title", "")),
                    "vcs": vcs_text,
                    "tape_id": str(getattr(album, "ratingKey", "unknown") or "unknown"),
                    "tracklist": tracklist,
                    "urls": urls,
                }
            )

        return candidates


PLEX_CONFIG_FILE = "/config/plex.json"


def _default_plex_config():
    return {"plex_sections": [], "plex_accounts": {}}


def _normalize_section_row(row):
    if not isinstance(row, dict):
        return None
    account = row.get("plex_account")
    server = row.get("plex_server")
    section = row.get("section_name")
    if not account or not server or not section:
        return None
    return {
        "plex_server": str(server),
        "section_name": str(section),
        "plex_account": str(account),
    }


def _dedupe_sections(section_rows):
    deduped = []
    seen = set()
    for row in section_rows:
        normalized = _normalize_section_row(row)
        if normalized is None:
            continue
        key = (normalized["plex_account"], normalized["plex_server"], normalized["section_name"])
        if key in seen:
            continue
        seen.add(key)
        deduped.append(normalized)
    return deduped


def _load_plex_config():
    cfg = _default_plex_config()
    if not utils.path_exists(PLEX_CONFIG_FILE):
        return cfg
    try:
        raw = utils.read_json(PLEX_CONFIG_FILE)
        sections = raw.get("plex_sections", [])
        accounts = raw.get("plex_accounts", {})
        cfg["plex_sections"] = _dedupe_sections(sections)
        cfg["plex_accounts"] = accounts
    except Exception as e:
        print(f"Failed reading {PLEX_CONFIG_FILE}: {e}")
    return cfg


def _save_plex_config(cfg):
    cfg["plex_sections"] = _dedupe_sections(cfg.get("plex_sections", []))
    cfg["plex_accounts"] = cfg.get("plex_accounts", {})
    utils.write_json(cfg, PLEX_CONFIG_FILE)


def _safe_menu_choice(title, choices):
    choice = utils.select_option(title, choices)
    if choice == "_CANCEL":
        return "Cancel"
    return choice


def _with_unique_labels(items):
    """Return shallow copies with unique _display labels for menu selection.

    This avoids ambiguous selection when two options render the same human label.
    """
    counts = {}
    out = []
    for item in items:
        row = dict(item)
        label = row.get("label", "")
        n = counts.get(label, 0) + 1
        counts[label] = n
        if n == 1:
            row["_display"] = label
        else:
            row["_display"] = f"{label} [{n}]"
        out.append(row)
    return out


def _with_section_labels(items):
    """Build menu labels centered on section name.

    If a section name appears multiple times, include server/account context
    so options remain understandable.
    """
    section_counts = {}
    for item in items:
        section = str(item.get("section_name", "?"))
        section_counts[section] = section_counts.get(section, 0) + 1

    labeled = []
    for item in items:
        row = dict(item)
        section = str(row.get("section_name", "?"))
        if section_counts.get(section, 0) > 1:
            server = str(row.get("plex_server", "?"))
            account = str(row.get("plex_account", "?"))
            row["label"] = f"{section} ({server}, {account})"
        else:
            row["label"] = section
        labeled.append(row)

    return _with_unique_labels(labeled)


def _discover_servers_for_account(username, password):
    try:
        client = PlexMetadataClient(username, password)
        return client.servers()
    except Exception as e:
        print(f"Unable to discover servers for account {username}: {e}")
        return []


def _discover_music_sections(username, password, server_name):
    try:
        client = PlexMetadataClient(username, password)
        return client.music_sections(server_name)
    except Exception as e:
        print(f"Unable to discover sections for {username}@{server_name}: {e}")
        return []


def _selected_keys(cfg):
    keys = set()
    for row in cfg.get("plex_sections", []):
        if not isinstance(row, dict):
            continue
        account = row.get("plex_account")
        server = row.get("plex_server")
        section = row.get("section_name")
        if account and server and section:
            keys.add((account, server, section))
    return keys


def _discover_addable_sections(cfg, server_scope=None):
    selected = _selected_keys(cfg)
    options = []
    accounts = cfg.get("plex_accounts", {})
    for username, password in accounts.items():
        if not username:
            continue
        servers = _discover_servers_for_account(username, password)
        for server_name in servers:
            if server_scope is not None:
                scope_user = server_scope.get("plex_account")
                scope_server = server_scope.get("plex_server")
                if username != scope_user or server_name != scope_server:
                    continue
            sections = _discover_music_sections(username, password, server_name)
            for section_name in sections:
                key = (username, server_name, section_name)
                if key in selected:
                    continue
                options.append(
                    {
                        "label": section_name,
                        "plex_account": username,
                        "plex_server": server_name,
                        "section_name": section_name,
                    }
                )
    return options


def _discover_addable_servers(cfg):
    chosen_pairs = set()
    for row in cfg.get("plex_sections", []):
        if isinstance(row, dict):
            acc = row.get("plex_account")
            srv = row.get("plex_server")
            if acc and srv:
                chosen_pairs.add((acc, srv))

    options = []
    accounts = cfg.get("plex_accounts", {})
    for username, password in accounts.items():
        servers = _discover_servers_for_account(username, password)
        for server_name in servers:
            key = (username, server_name)
            if key in chosen_pairs:
                continue
            options.append(
                {
                    "label": f"{server_name} ({username})",
                    "plex_account": username,
                    "plex_server": server_name,
                }
            )
    return options


def _add_account_screen(cfg):
    while True:
        username = utils.select_chars("Plex user", "Enter Plex username. Press Stop to finish")
        if not username:
            return False

        password = utils.select_chars("Plex password", "Enter Plex password. Press Stop to finish")
        if password is None:
            return False

        try:
            # Force a real login/network call so bad credentials are rejected here.
            client = PlexMetadataClient(username, password)
            _ = client.servers()

            cfg["plex_accounts"][username] = password
            _save_plex_config(cfg)
            return True
        except Exception as e:
            print(f"Plex authentication failed for {username}: {e}")
            PlexMetadataClient.clear_cache(username)
            tm.clear_screen()
            tm.write("Plex login failed", 0, 0, tm.pfont_small, tm.YELLOW, show_end=-2)
            tm.write("Check user/password/network", 0, tm.pfont_small.HEIGHT + 2, tm.pfont_smallx, tm.WHITE, show_end=-2)

            action = _safe_menu_choice("Auth failed", ["Retry", "Save Anyway", "Cancel"])
            if action == "Retry":
                continue
            if action == "Save Anyway":
                cfg["plex_accounts"][username] = password
                _save_plex_config(cfg)
                return True
            return False


def _add_server_screen(cfg):
    while True:
        server_options = _with_unique_labels(_discover_addable_servers(cfg))
        choices = [x["_display"] for x in server_options] + ["Add Account", "Cancel"]
        choice = _safe_menu_choice("Add Server", choices)
        if choice == "Cancel":
            return None
        if choice == "Add Account":
            _add_account_screen(cfg)
            continue

        for option in server_options:
            if option["_display"] == choice:
                return option
        return None


def _add_section_screen(cfg, server_scope=None):
    while True:
        section_options = _with_section_labels(_discover_addable_sections(cfg, server_scope=server_scope))
        choices = ["Add Server"] + [x["_display"] for x in section_options] + ["Cancel"]
        choice = _safe_menu_choice("Add Library", choices)

        if choice == "Cancel":
            return
        if choice == "Add Server":
            chosen_server = _add_server_screen(cfg)
            if chosen_server is not None:
                server_scope = chosen_server
            continue

        for option in section_options:
            if option["_display"] == choice:
                row = {
                    "plex_server": option["plex_server"],
                    "section_name": option["section_name"],
                    "plex_account": option["plex_account"],
                }
                key = (row["plex_account"], row["plex_server"], row["section_name"])
                existing = _selected_keys(cfg)
                if key not in existing:
                    cfg["plex_sections"].append(row)
                _save_plex_config(cfg)
                _show_selected_sections_screen(cfg)
                return


def _delete_section_screen(cfg):
    sections = cfg.get("plex_sections", [])

    if len(sections) == 0:
        tm.clear_screen()
        tm.write("No libraries configured", 0, 0, tm.pfont_small, tm.YELLOW, show_end=-2)
        return

    section_rows = [row for row in sections if isinstance(row, dict)]
    section_options = _with_section_labels(section_rows)
    labels = [x["_display"] for x in section_options]

    choice = _safe_menu_choice("Delete Library", labels + ["Cancel"])
    if choice == "Cancel":
        return

    for option in section_options:
        if option["_display"] == choice:
            target = {
                "plex_account": option.get("plex_account"),
                "plex_server": option.get("plex_server"),
                "section_name": option.get("section_name"),
            }
            for idx, row in enumerate(cfg.get("plex_sections", [])):
                if not isinstance(row, dict):
                    continue
                if (
                    row.get("plex_account") == target["plex_account"]
                    and row.get("plex_server") == target["plex_server"]
                    and row.get("section_name") == target["section_name"]
                ):
                    del cfg["plex_sections"][idx]
                    _save_plex_config(cfg)
                    return
            _save_plex_config(cfg)
            return


def _delete_account_screen(cfg):
    accounts = cfg.get("plex_accounts", {})
    usernames = sorted(list(accounts.keys()))
    if len(usernames) == 0:
        tm.clear_screen()
        tm.write("No accounts configured", 0, 0, tm.pfont_small, tm.YELLOW, show_end=-2)
        return

    choice = _safe_menu_choice("Delete Account", usernames + ["Cancel"])
    if choice == "Cancel":
        return
    if choice not in accounts:
        return

    del accounts[choice]
    cfg["plex_sections"] = [x for x in cfg.get("plex_sections", []) if x.get("plex_account") != choice]
    PlexMetadataClient.clear_cache(choice)
    _save_plex_config(cfg)


def _show_selected_sections_screen(cfg):
    sections = cfg.get("plex_sections", [])
    if len(sections) == 0:
        _safe_menu_choice("Plex Libraries", ["No libraries added", "Continue"])
        return

    section_rows = [row for row in sections if isinstance(row, dict)]
    section_options = _with_section_labels(section_rows)
    labels = [x["_display"] for x in section_options]

    _safe_menu_choice("Plex Libraries", labels + ["Continue"])


def get_plex_clients():
    cfg = _load_plex_config()
    accounts = cfg.get("plex_accounts", {})
    sections = cfg.get("plex_sections", [])

    for section in sections:
        if not isinstance(section, dict):
            continue
        plex_user = section.get("plex_account")
        plex_server = section.get("plex_server")
        section_name = section.get("section_name")
        plex_password = accounts.get(plex_user)

        if section_name is None or plex_server is None or plex_user is None or plex_password is None:
            print(f"Skipping invalid plex section row: {section}")
            continue
        try:
            client = PlexMetadataClient(plex_user, plex_password, plex_server, section_name)
            yield client
        except Exception as e:
            print(f"Skipping plex section due to connection error: {e}")


def get_plex_vcs_collections():
    """Return livemusic-style dict keyed by album artist.

    Output shape: {artist_name: {iso_date: vcs_string}}.
    """
    collections = {}
    for client in get_plex_clients():
        try:
            for album in client.iter_albums():
                date_str, artist, vcs_text = client._album_metadata(album)
                if not date_str:
                    continue

                artist = artist or str(client.section_name or "Plex")

                if artist not in collections:
                    collections[artist] = {}
                if date_str not in collections[artist] and vcs_text:
                    collections[artist][date_str] = vcs_text
        except Exception as e:
            print(f"Skipping plex vcs collection {client.plex_user}:{client.server_name}:{client.section_name}: {e}")
    return collections


def get_plex_trackdata_for_date(collection_name, key_date, ntape=0):
    candidates = []
    for client in get_plex_clients():
        try:
            candidates.extend(client.get_trackdata_for_date(key_date, artist_name=collection_name))
        except Exception as e:
            print(f"Error loading plex trackdata {collection_name} {key_date}: {e}")

    if len(candidates) == 0:
        return None

    chosen = candidates[ntape % len(candidates)]
    return {
        "collection": collection_name,
        "tracklist": chosen["tracklist"],
        "urls": chosen["urls"],
        "tape_id": chosen.get("tape_id", "unknown"),
        "vcs": chosen.get("vcs", ""),
    }


def get_configured_section_count():
    cfg = _load_plex_config()
    sections = cfg.get("plex_sections", [])
    return len(sections) if isinstance(sections, list) else 0


def get_configured_section_labels():
    cfg = _load_plex_config()
    rows = cfg.get("plex_sections", [])
    if not isinstance(rows, list):
        return []

    labels = []
    section_counts = {}
    normalized = []
    for row in rows:
        norm = _normalize_section_row(row)
        if norm is None:
            continue
        normalized.append(norm)
        sec = norm.get("section_name", "?")
        section_counts[sec] = section_counts.get(sec, 0) + 1

    for row in normalized:
        sec = row.get("section_name", "?")
        if section_counts.get(sec, 0) > 1:
            server = row.get("plex_server", "?")
            account = row.get("plex_account", "?")
            labels.append(f"Plex Library: {sec} ({server}, {account})")
        else:
            labels.append(f"Plex Library: {sec}")
    return labels


def configure():
    while True:
        cfg = _load_plex_config()
        choices = ["Show Libraries", "Add Library", "Delete Library"]
        if len(cfg.get("plex_accounts", {})) > 0:
            choices.append("Delete Account")
        choices.append("Cancel")

        choice = _safe_menu_choice("Plex Setup", choices)

        if choice == "Cancel":
            return
        if choice == "Show Libraries":
            _show_selected_sections_screen(cfg)
            continue
        if choice == "Add Library":
            _add_section_screen(cfg)
            continue
        if choice == "Delete Library":
            _delete_section_screen(cfg)
            continue
        if choice == "Delete Account":
            _delete_account_screen(cfg)
            continue
