import gc
import hashlib

# import requests
try:
    from async_urequests import urequests as requests
except ImportError:
    from mrequests import mrequests as requests


import time
import audioPlayer2 as audioPlayer
from machine import Timer


class PlayerManager:
    def __init__(self, callbacks, debug=0):
        self.callbacks = callbacks
        self.DEBUG = debug
        if "display" not in self.callbacks.keys():
            self.callbacks["display"] = lambda *x: print(f"PlayerManager display: {x}")

        self.player = audioPlayer.AudioPlayer(callbacks={"messages": self.messenger}, debug=debug)
        self.first_chunk_dict = {}
        self.chunklist = []
        self.flat_chunklist = []
        self.chunk_bounds = []
        self.urls = []  # high-level urls
        self.tracklist = []  # track titles
        self.track_playing = -1
        self.chunk_playing = 0
        self.chunk_reading = 0
        self.n_tracks_sent = 0
        self.n_tracks_pumped = 0
        self.chunked_urls = False
        self.playlist_completed = False
        self.all_tracks_sent = False
        self.release_throttle(None)
        self.pumptimer = Timer(1)
        self.DEBUG = debug

    def set_playlist(self, track_titles, urls):
        self.tracklist = track_titles
        self.playlist_completed = False
        self.all_tracks_sent = False
        self.release_throttle(None)
        self.n_tracks_pumped = 0

        setbreak_url = "https://storage.googleapis.com/spertilo-data/sundry/silence600.ogg"
        urls = [x if not (x.endswith("silence600.ogg")) else setbreak_url for x in urls]
        encorebreak_url = "https://storage.googleapis.com/spertilo-data/sundry/silence0.ogg"
        urls = [x if not (x.endswith("silence0.ogg")) else encorebreak_url for x in urls]
        urls = [x.replace(" ", "%20") for x in urls]
        self.urls = urls
        self.pump_chunks()
        self.chunk_timer()

    def __repr__(self):
        return f"PlayerManager: {self.player}. " + f"track bounds:{self.chunk_bounds}"

    @micropython.native
    def get_chunklist(self, url):
        if url.endswith("m3u8"):
            # determine the chunks
            print(f"first url is {url}")
            self.chunked_urls = True
            base_url = "/".join(url.split("/")[:-1])
            chunklist_url = requests.get(url)
            chunklist_url = f"{base_url}/{chunklist_url.text.splitlines()[-1]}"
            print(f"chunklist url is {chunklist_url}")
            lines = requests.get(chunklist_url).text.splitlines()
            chunks = [x for x in lines if x.startswith("media_")]
            chunklist = [f"{base_url}/{x}" for x in chunks]
            self.DEBUG and print(f"chunklist set to {chunks}")
        else:
            chunklist = [url]
        return chunklist

    def update_playlist(self, urllist, ntracks=1):
        print(f"update_playlist sending {len(urllist)} URLs to player")
        self.playdict = {hashlib.md5(x.encode()).digest().hex(): x for x in urllist}
        self.player.playlist.extend([(x, hashlib.md5(x.encode()).digest().hex()) for x in urllist])
        self.n_tracks_sent += ntracks

    def increment_track(self):
        self.track_playing += 1
        tracklist = self.tracklist[self.track_playing :] + [""] * 10
        try:
            print(f"playerManager display: {tracklist}")
            self.callbacks["display"](*tracklist)
        except Exception as e:
            print(f"Error in display callback: {e}")

    def messenger(self, message):
        last_word = message.split()[-1]
        try:
            if (title := self.first_chunk_dict.get(last_word, None)) and "Start" in message:
                message = message.replace(last_word, title)
        except Exception as e:
            print(f"Error in messenger: {e}")
        print(f"PlayerManager {message}")
        if title and "Start playing track" in message:
            self.increment_track()
            return

        """
        if "Finished playing track" in message:
            if self.chunked_urls:
                self.chunk_playing += 1
                if self.chunk_playing in self.chunk_bounds:
                    self.increment_track()
                return
            self.increment_track()
        """

        if "Finished reading track" in message:
            if not self.chunked_urls:
                return
            self.chunk_reading += 1

        if "Finished reading all tracks" in message:
            if not self.chunked_urls:
                return
            remaining_chunks = self.chunklist[self.n_tracks_sent :]
            if len(remaining_chunks) > 0:
                self.update_playlist(remaining_chunks[0])
                self.play()

        if "Finished playing playlist" in message:
            self.playlist_completed = True
            self.chunk_playing = 0
            self.track_playing = -1
            self.stop(reset_head=True)
            try:
                self.callbacks["display"](*self.tracklist)
            except Exception as e:
                print(f"Error in display callback: {e}")
            return

    def n_tracks(self):
        return len(self.tracklist)

    def track_names(self):
        track_names = self.tracklist[max(0, self.track_playing) :]
        if len(track_names) < 10:
            track_names = track_names + (10 - len(track_names)) * [""]
        return track_names

    def is_playing(self):
        return self.player.is_playing()

    def pause(self):
        return self.player.pause()

    def stop(self, reset_head=True):
        if self.is_playing():
            self.pumptimer.deinit()
            self.ready_to_pump = False
            print("No more chunks will be sent -- player reset")
            self.player.stop(reset_head)
        return

    def play(self):
        return self.player.play()

    def rewind(self):
        return self.player.rewind()

    def ffwd(self):
        if self.chunked_urls:
            # Handle case where we are on the last track.
            if self.chunked_urls:
                resume_playing = self.is_playing()
                destination = self.chunk_bounds[max(0, self.track_playing)]
                self.stop()
                print(f"ffwd: Moving to {destination}")
                self.player.advance_track(destination)
                self.chunk_reading = destination
                self.chunk_playing = destination
                if resume_playing:
                    self.play()
        else:
            self.player.ffwd()

    def release_throttle(self, _):
        self.ready_to_pump = True

    @micropython.native
    def pump_chunks(self):
        if not self.ready_to_pump:
            return
        if self.n_tracks_pumped >= len(self.urls):
            self.pumptimer.deinit()
            return
        url = self.urls[self.n_tracks_pumped]
        self.DEBUG and print(f"pump_chunks sending chunks for {url}")
        next_chunklist = self.get_chunklist(url)
        self.chunklist.append(next_chunklist)
        hashdict = {hashlib.md5(next_chunklist[0].encode()).digest().hex(): self.tracklist[self.n_tracks_pumped]}
        self.first_chunk_dict.update(hashdict)
        self.flat_chunklist.extend(next_chunklist)

        self.update_playlist(next_chunklist)
        self.n_tracks_pumped += 1
        self.DEBUG and print(f"hashdict now {self.first_chunk_dict}")
        self.ready_to_pump = False
        return

    def audio_pump(self):
        self.pump_chunks()

    def is_playing(self):
        return self.player.is_playing()

    def is_stopped(self):
        return self.player.is_stopped()

    def set_volume(self, volume):
        return self.player.set_volume(volume)

    def get_volume(self):
        return self.player.get_volume()

    def reset_player(self):
        return self.player.reset_player()

    def chunk_timer(self):
        self.pumptimer.init(period=2000, mode=Timer.PERIODIC, callback=self.release_throttle)
