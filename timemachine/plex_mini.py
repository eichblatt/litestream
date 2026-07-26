"""Minimal PlexAPI-like shim for MicroPython.

Implements the subset used by archive metadata flows:
- MyPlexAccount(username, password)
- account.resource(server_name).connect()
- plex.library.section(section_name)
- music.searchAlbums()
- album.tracks()
- plex.url(path, includeToken=True)
"""

try:
    from mrequests import mrequests as requests
except Exception:
    import requests

try:
    import ubinascii  # type: ignore
except Exception:
    ubinascii = None

try:
    import base64
except Exception:
    base64 = None


class PlexError(Exception):
    pass


class PlexUnauthorized(PlexError):
    pass


class PlexNotFound(PlexError):
    pass


def _b64_encode(text):
    raw = text.encode("utf-8")
    if ubinascii is not None:
        return ubinascii.b2a_base64(raw).decode("utf-8").strip()
    if base64 is not None:
        return base64.b64encode(raw).decode("utf-8")
    raise PlexError("No base64 encoder available")


def _url_encode(value):
    s = str(value)
    s = s.replace("%", "%25")
    s = s.replace(" ", "%20")
    s = s.replace(":", "%3A")
    s = s.replace("/", "%2F")
    s = s.replace("?", "%3F")
    s = s.replace("&", "%26")
    s = s.replace("=", "%3D")
    s = s.replace("+", "%2B")
    s = s.replace(",", "%2C")
    return s


def _append_query(url, params):
    if not params:
        return url
    parts = []
    for key, value in params.items():
        if value is None:
            continue
        parts.append("%s=%s" % (_url_encode(key), _url_encode(value)))
    if not parts:
        return url
    joiner = "&" if "?" in url else "?"
    return "%s%s%s" % (url, joiner, "&".join(parts))


def _extract_container(payload):
    if isinstance(payload, dict):
        if "MediaContainer" in payload and isinstance(payload["MediaContainer"], dict):
            return payload["MediaContainer"]
        return payload
    return {}


class _PlexClientBase:
    def __init__(self, client_identifier="ESP32_Music_Player", product="ESP32 Plex Client", version="1.0"):
        self.client_identifier = client_identifier
        self.product = product
        self.version = version

    def _base_headers(self):
        return {
            "X-Plex-Client-Identifier": self.client_identifier,
            "X-Plex-Product": self.product,
            "X-Plex-Version": self.version,
            "Accept": "application/json",
        }

    def request_json(self, method, url, headers=None, data=None, params=None):
        full_url = _append_query(url, params)
        hdrs = self._base_headers()
        if headers:
            hdrs.update(headers)
        resp = None
        try:
            if method == "POST":
                resp = requests.post(full_url, headers=hdrs, data=data)
            else:
                resp = requests.get(full_url, headers=hdrs)
            status_code = int(getattr(resp, "status_code", 0))
            if status_code in (401, 403):
                raise PlexUnauthorized("Plex authentication failed")
            if status_code < 200 or status_code >= 300:
                raise PlexError("Plex request failed: %s %s" % (status_code, full_url))
            return resp.json()
        finally:
            if resp is not None:
                try:
                    resp.close()
                except Exception:
                    pass


class MyPlexAccount(_PlexClientBase):
    def __init__(self, username=None, password=None, token=None, client_identifier="ESP32_Music_Player"):
        super().__init__(client_identifier=client_identifier)
        self.username = username
        self.authToken = token
        if self.authToken is None:
            if not (username and password):
                raise PlexUnauthorized("Username/password required when token is not supplied")
            self.authToken = self._login(username, password)

    def _token_headers(self):
        return {"X-Plex-Token": self.authToken}

    def _login(self, username, password):
        print("Logging in to Plex with username:", username)
        encoded = _b64_encode("%s:%s" % (username, password))
        headers = {"Authorization": "Basic %s" % encoded}
        payload = self.request_json("POST", "https://plex.tv/users/sign_in.json", headers=headers, data="")
        user = payload.get("user", {}) if isinstance(payload, dict) else {}
        token = user.get("authToken")
        if not token:
            raise PlexUnauthorized("Plex sign-in succeeded but no auth token was returned")
        return token

    def resources(self):
        payload = self.request_json(
            "GET",
            "https://plex.tv/api/v2/resources",
            headers=self._token_headers(),
            params={"includeHttps": 1, "includeRelay": 1},
        )
        container = _extract_container(payload)

        devices = None
        if isinstance(container, dict):
            for key in ("Device", "devices", "Resources", "resources"):
                value = container.get(key)
                if isinstance(value, list):
                    devices = value
                    break
        if devices is None and isinstance(payload, list):
            devices = payload
        if devices is None:
            devices = []

        result = []
        for raw in devices:
            provides = str(raw.get("provides", ""))
            if "server" in provides:
                result.append(MyPlexResource(self, raw))
        return result

    def resource(self, name):
        wanted = str(name or "").strip().lower()
        for res in self.resources():
            names = [
                str(res.name or "").lower(),
                str(res.clientIdentifier or "").lower(),
                str(res.machineIdentifier or "").lower(),
            ]
            if wanted in names:
                return res
        raise PlexNotFound("Plex resource not found: %s" % name)


class MyPlexResource:
    def __init__(self, account, raw):
        self._account = account
        self._raw = raw if isinstance(raw, dict) else {}
        self.name = self._raw.get("name")
        self.clientIdentifier = self._raw.get("clientIdentifier")
        self.machineIdentifier = self._raw.get("machineIdentifier")
        self.accessToken = self._raw.get("accessToken") or account.authToken

    def _connections(self):
        conn = self._raw.get("Connection")
        if isinstance(conn, list):
            return conn
        conn = self._raw.get("connections")
        if isinstance(conn, list):
            return conn
        return []

    def _preferred_uris(self):
        conns = self._connections()

        def _sort_key(c):
            local = bool(c.get("local", False))
            relay = bool(c.get("relay", False))
            protocol = str(c.get("protocol", "")).lower()
            https = protocol == "https"
            return (relay, not local, not https)

        ordered = sorted(conns, key=_sort_key)
        uris = []
        for c in ordered:
            uri = c.get("uri") or c.get("httpuri")
            uri_text = str(uri).strip()
            if uri_text:
                uris.append(uri_text.rstrip("/"))
        return uris

    def connect(self):
        headers = self._account._token_headers()
        token = self.accessToken or self._account.authToken
        uris = self._preferred_uris()
        if not uris:
            raise PlexNotFound("No usable connections found for Plex resource %s" % self.name)

        for uri in uris:
            identity_url = "%s/identity" % uri
            client = _PlexClientBase(
                client_identifier=self._account.client_identifier,
                product=self._account.product,
                version=self._account.version,
            )
            try:
                client.request_json("GET", identity_url, headers=headers)
                return PlexServer(uri, token, self._account.client_identifier, self._account.product, self._account.version)
            except Exception:
                pass

        raise PlexNotFound("Unable to connect to any Plex endpoint for resource %s" % self.name)


class PlexServer(_PlexClientBase):
    def __init__(self, base_url, token, client_identifier, product, version):
        super().__init__(client_identifier=client_identifier, product=product, version=version)
        self.base_url = base_url.rstrip("/")
        self._token = token
        self.library = Library(self)

    def _token_headers(self):
        return {"X-Plex-Token": self._token}

    def _get_json(self, path, params=None):
        path = str(path)
        path = path if path.startswith("/") else "/%s" % path
        return self.request_json("GET", "%s%s" % (self.base_url, path), headers=self._token_headers(), params=params)

    def url(self, path, includeToken=False):
        path = str(path)
        path = path if path.startswith("/") else "/%s" % path
        url = "%s%s" % (self.base_url, path)
        if includeToken:
            url = _append_query(url, {"X-Plex-Token": self._token})
        return url


class Library:
    def __init__(self, server):
        self._server = server

    def sections(self):
        payload = self._server._get_json("/library/sections")
        container = _extract_container(payload)
        dirs = container.get("Directory", [])
        if not isinstance(dirs, list):
            dirs = []
        return [LibrarySection(self._server, d) for d in dirs if isinstance(d, dict)]

    def section(self, title):
        wanted = str(title or "")
        sections = self.sections()
        for section in sections:
            if str(section.title) == wanted:
                return section
        for section in sections:
            if str(section.title).lower() == wanted.lower():
                return section
        raise PlexNotFound("Library section not found: %s" % title)


class LibrarySection:
    def __init__(self, server, raw):
        self._server = server
        self._raw = raw
        self.key = raw.get("key")
        self.title = str(raw.get("title"))
        self.type = str(raw.get("type"))

    def searchAlbums(self, **kwargs):
        start = int(kwargs.get("container_start", 0))
        maxresults = kwargs.get("maxresults")
        maxresults = int(maxresults) if maxresults is not None else None

        # Optimize page size based on maxresults to avoid over-fetching
        base_page_size = int(kwargs.get("container_size", 200))
        page_size = min(base_page_size, maxresults) if maxresults else base_page_size

        # Pass through additional query filters (for example, title=YYYY-MM-DD)
        # while keeping pagination controls local to this helper.
        extra_params = {}
        for key, value in kwargs.items():
            if key in ("container_start", "container_size", "maxresults"):
                continue
            if value is None:
                continue
            extra_params[str(key)] = value

        all_albums = []
        while True:
            # Adjust page size if we're close to maxresults limit
            if maxresults is not None:
                remaining = maxresults - len(all_albums)
                if remaining <= 0:
                    break
                page_size = min(page_size, remaining)

            params = {
                "X-Plex-Container-Start": start,
                "X-Plex-Container-Size": page_size,
            }
            for key, value in extra_params.items():
                params[key] = value

            payload = self._server._get_json(
                "/library/sections/%s/albums" % self.key,
                params=params,
            )
            container = _extract_container(payload)
            items = container.get("Metadata", [])
            if not isinstance(items, list):
                items = []

            for item in items:
                if isinstance(item, dict):
                    all_albums.append(Album(self._server, item))

            if maxresults is not None and len(all_albums) >= maxresults:
                return all_albums[:maxresults]

            total_size = container.get("totalSize")
            if len(items) == 0:
                break
            if total_size is not None:
                try:
                    if (start + len(items)) >= int(total_size):
                        break
                except Exception:
                    pass
            if len(items) < page_size:
                break
            start += len(items)

        return all_albums


class Album:
    def __init__(self, server, raw):
        self._server = server
        self._raw = raw

    @property
    def title(self):
        return self._raw.get("title", "")

    @property
    def ratingKey(self):
        return self._raw.get("ratingKey")

    @property
    def parentTitle(self):
        return self._raw.get("parentTitle", "")

    @property
    def key(self):
        return self._raw.get("key")

    @property
    def year(self):
        return self._raw.get("year")

    def tracks(self):
        if not self.ratingKey:
            return []
        payload = self._server._get_json("/library/metadata/%s/children" % self.ratingKey)
        container = _extract_container(payload)
        items = container.get("Metadata", [])
        if not isinstance(items, list):
            items = []
        return [Track(self._server, item) for item in items if isinstance(item, dict)]


class Track:
    def __init__(self, server, raw):
        self._server = server
        self._raw = raw
        self._media_cache = None

    @property
    def title(self):
        return self._raw.get("title", "")

    @property
    def index(self):
        return self._raw.get("index", 0)

    @property
    def media(self):
        if self._media_cache is None:
            media_rows = self._raw.get("Media", [])
            if not isinstance(media_rows, list):
                media_rows = []
            self._media_cache = [Media(media_row) for media_row in media_rows if isinstance(media_row, dict)]
        return self._media_cache


class Media:
    def __init__(self, raw):
        self._raw = raw
        self._parts_cache = None

    @property
    def container(self):
        return self._raw.get("container")

    @property
    def parts(self):
        if self._parts_cache is None:
            part_rows = self._raw.get("Part", [])
            if not isinstance(part_rows, list):
                part_rows = []
            self._parts_cache = [Part(part_row) for part_row in part_rows if isinstance(part_row, dict)]
        return self._parts_cache


class Part:
    def __init__(self, raw):
        self._raw = raw

    @property
    def key(self):
        return self._raw.get("key", "")
