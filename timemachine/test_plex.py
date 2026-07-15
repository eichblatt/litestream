try:
    from timemachine.plex_mini import MyPlexAccount
except Exception:
    try:
        from .plex_mini import MyPlexAccount
    except Exception:
        from plex_mini import MyPlexAccount


def is_valid_iso_date(text):
    if not isinstance(text, str):
        return False
    if len(text) != 10:
        return False
    if text[4] != "-" or text[7] != "-":
        return False
    if not (text[:4].isdigit() and text[5:7].isdigit() and text[8:10].isdigit()):
        return False
    return True


class PlexMetadataClient:
    def __init__(self, plex_user, plex_password, plex_server, section_name, date_range=None):
        self.account = MyPlexAccount(plex_user, plex_password)
        self.plex = self.account.resource(plex_server).connect()
        self.music = self.plex.library.section(section_name)
        self.date_range = date_range

    def iter_albums(self):
        for album in self.music.searchAlbums():
            date_str = album.title[:10] if isinstance(album.title, str) else ""
            if not is_valid_iso_date(date_str):
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


if __name__ == "__main__":
    # Replace with your own credentials and server details.
    plex_user = "my_plex_username"
    plex_password = "my_plex_password"
    plex_server = "my_plex_server"
    section_name = "Live Music"

    client = PlexMetadataClient(plex_user, plex_password, plex_server, section_name)
    albums = list(client.iter_albums())
    print("Albums found:", len(albums))

    if albums:
        sample_tracks = client.get_album_tracks(albums[0])
        print("Tracks in first album:", len(sample_tracks))
