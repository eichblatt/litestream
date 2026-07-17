from plex_mini import MyPlexAccount
import utils
import board as tm


class PlexMetadataClient:
    def __init__(self, plex_user, plex_password, plex_server, section_name, date_range=None):
        print(f"Initializing PlexMetadataClient with user: {plex_user}, server: {plex_server}, section: {section_name}")
        self.account = MyPlexAccount(plex_user, plex_password)
        self.plex = self.account.resource(plex_server).connect()
        self.music = self.plex.library.section(section_name)
        self.date_range = date_range
        self.server_name = plex_server
        self.section_name = section_name

    def iter_albums(self):
        for album in self.music.searchAlbums():
            date_str = album.title[:10] if isinstance(album.title, str) else ""
            if not utils.is_valid_iso_date(date_str):
                continue

            if self.date_range:
                year = int(date_str[:4])
                if year < min(self.date_range) or year > max(self.date_range):
                    continue
            yield album

    def get_albums(self):
        albums = []
        for album in self.iter_albums():
            albums.append(
                {
                    "title": album.title,
                    "artist": album.parentTitle,
                    "rating_key": album.ratingKey,
                    "year": album.year,
                }
            )
        return albums

    def get_album_tracks(self, album):
        tracks = []
        for position, track in enumerate(album.tracks(), start=1):
            stream_url = ""
            media_items = getattr(track, "media", [])
            if media_items:
                parts = getattr(media_items[0], "parts", [])
                if parts:
                    part_key = getattr(parts[0], "key", "")
                    if part_key:
                        stream_url = self.plex.url(part_key, includeToken=True)
            tracks.append(
                {
                    "track_number": position,
                    "title": getattr(track, "title", "Unknown Track"),
                    "stream_url": stream_url,
                }
            )
        return tracks


PLEX_SECTIONS_FILE = "/config/plex.json"


def get_plex_clients():
    plex_sections = utils.read_json(PLEX_SECTIONS_FILE)
    for section in plex_sections:
        plex_user, plex_password = section.get("plex_account")
        plex_server = section.get("plex_server")
        section_name = section.get("section_name")
        if section_name is None:
            print(f"Skipping section with missing section_name: {section} for account {plex_user}")
            continue
        client = PlexMetadataClient(plex_user, plex_password, plex_server, section_name)
        yield client


def configure_plex():
    choices = ["Add Collection", "Remove Collection", "Cancel"]
    choice = utils.select_option("Select Option", choices)
    print(f"configure_collection: chose to {choice}")
    if choice == "Cancel":
        return

    plex_sections = utils.read_json(PLEX_SECTIONS_FILE)
    collection_list = [section["section_name"] for section in plex_sections if section.get("section_name") is not None]

    print(f"current collection_list is {collection_list}")
    if choice == "Add Collection":
        all_clients = list(get_plex_clients())
        all_collections = [c.section_name for c in all_clients]
        known_choices = [c for c in all_collections if c not in collection_list]
        tm.clear_screen()
        utils.add_list_element("Collection", known_choices, get_collection_list, append_to_collection_list)

    elif choice == "Remove Collection":
        utils.remove_list_element(get_collection_list, delete_from_collection_list)

    return
