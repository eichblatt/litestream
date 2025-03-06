import asyncio
import gc
import hashlib

# import requests
import async_urequests as requests

"""
try:
    from async_urequests import urequests as requests
except ImportError:
    from mrequests import mrequests as requests
"""

import time
import audioPlayer2 as audioPlayer
from machine import Timer


async def dummy(seconds):
    await asyncio.sleep(seconds)
    return


class PlayerManager:
    def __init__(self, callbacks, debug=0):
        self.callbacks = callbacks
        self.DEBUG = debug
        self.init_vars()
        if "display" not in self.callbacks.keys():
            self.callbacks["display"] = lambda *x: print(f"PlayerManager display: {x}")

        self.player = audioPlayer.AudioPlayer(callbacks={"messages": self.messenger}, debug=debug)
        self.DEBUG = debug

    def init_vars(self):
        self.chunklist = []
        self.urls = []  # high-level urls
        self.tracklist = []  # track titles
        self.n_tracks_sent = 0
        self.first_chunk_dict = {}
        self.track_index = 0
        self.chunked_urls = False
        self.playlist_completed = False
        self.ready_to_pump = False
        self.chunk_generator = None
        self.credits = []

    def set_playlist(self, track_titles, urls, credits=[]):
        self.tracklist = track_titles
        self.credits = credits
        self.playlist_completed = False
        self.n_tracks_sent = 0
        self.chunklist = []
        self.first_chunk_dict = {}
        self.track_index = 0
        self.track_offset = 0
        self.ready_to_pump = True
        self.chunk_generator = None

        setbreak_url = "https://storage.googleapis.com/spertilo-data/sundry/silence600.ogg"
        urls = [x if not (x.endswith("silence600.ogg")) else setbreak_url for x in urls]
        encorebreak_url = "https://storage.googleapis.com/spertilo-data/sundry/silence0.ogg"
        urls = [x if not (x.endswith("silence0.ogg")) else encorebreak_url for x in urls]
        urls = [x.replace(" ", "%20") for x in urls]
        self.urls = urls
        self.pump_chunks()

    def __repr__(self):
        clstr = f"Player Manager: chunk lengths {[len(x) for x in self.chunklist]}"
        return clstr + f" {self.player}. "

    @property
    def all_tracks_sent(self):
        return self.n_tracks_sent >= len(self.urls)

    def extend_playlist(self, urllist, ntracks=1):
        print(f"extend_playlist: Track {self.n_tracks_sent + 1}. sending {len(urllist)} more URLs to player.")
        self.player.playlist.extend([(x, hashlib.md5(x.encode()).digest().hex()) for x in urllist])
        self.n_tracks_sent += ntracks

    def increment_track(self, track_num=None):
        if track_num and track_num == self.track_index:
            return self.track_index
        if (self.track_index + 1) >= self.n_tracks:
            return None
        self.track_index = self.track_index + 1 if track_num is None else track_num
        tracklist = self.remaining_track_names()
        try:
            self.DEBUG and print(f"playerManager display: {tracklist}")
            self.callbacks["display"](*tracklist)
        except Exception as e:
            print(f"Error in display callback: {e}")
        finally:
            self.DEBUG and print(f"increment_track: returning track {self.track_index} of {self.n_tracks}")
            return self.track_index

    def messenger(self, message):
        last_word = message.split()[-1]
        track_num = self.first_chunk_dict.get(last_word, -1)
        title = None
        try:
            if (track_num >= 0) and "Start" in message:
                title = self.tracklist[track_num]
                message = message.replace(last_word, title)
        except Exception as e:
            print(f"Error in messenger: {e}")

        # print(f"PlayerManager {message}")
        if title and "Start playing track" in message:
            self.increment_track(track_num)
            return

        if "Finished playing track" in message:
            return

        if "Finished reading track" in message:
            if not self.chunked_urls:
                return

        if "Finished reading all tracks" in message:
            if not self.chunked_urls:
                return
            remaining_chunks = self.chunklist[self.n_tracks_sent :]
            if len(remaining_chunks) > 0:
                self.extend_playlist(remaining_chunks[0])
                self.play()

        if "Finished playing playlist" in message:
            self.stop(reset_head=True)
            self.playlist_completed = True
            try:
                self.callbacks["display"](*self.tracklist)
            except Exception as e:
                print(f"Error in display callback: {e}")
            return

    @property
    def n_tracks(self):
        return len(self.tracklist)

    def remaining_track_names(self):
        track_names = self.tracklist[max(0, self.track_index) :] + self.credits + [""] * 10
        return track_names

    def is_playing(self):
        return self.player.is_playing()

    def pause(self):
        return self.player.pause()

    def stop(self, reset_head=True):
        self.ready_to_pump = False
        print("No more chunks will be sent -- player reset")
        self.player.stop(reset_head)
        return

    def play(self):
        if len(self.player.playlist) == 0:
            print("No tracks in playlist")
            return
        return self.player.play()

    def rewind(self):
        raise NotImplementedError("Cannot rewind yet.")
        return

    def ffwd(self):
        resume_playing = self.is_playing()
        if not self.all_tracks_sent:  # We are still pumping chunks.
            raise NotImplementedError("Cannot fast forward while pumping chunks.")
        if self.increment_track() is None:
            print("Cannot fast forward, already on last track.")
            return  # return if we are on the last track.
        self.stop()
        chunks_to_send = []
        for chunk in self.chunklist[self.track_index :]:
            chunks_to_send.extend(chunk)
        self.player.playlist = [(chunk, hashlib.md5(chunk.encode()).digest().hex()) for chunk in chunks_to_send]
        if resume_playing:
            self.play()
        return

    def pump_chunks(self):
        if not self.ready_to_pump:
            return
        if self.all_tracks_sent:
            return
        url = self.urls[self.n_tracks_sent]
        next_chunklist = None
        if self.n_tracks_sent == 0:  # Block until first chunks are pumped
            next_chunklist = asyncio.run(self.get_chunklist(url))
            self.DEBUG and print(
                f"pump_chunks: first chunklist is {next_chunklist[:2]}..{next_chunklist[-2:]} type {type(next_chunklist)}"
            )
        else:
            if self.chunk_generator is None:
                self.chunk_generator = self.poll_chunklist(url)
            try:
                next(self.chunk_generator)
            except StopIteration as e:
                next_chunklist = e.value
                self.chunk_generator = None  # prepare for next task
                self.DEBUG and print(f"pump_chunks: StopIteration next chunklist is a {type(next_chunklist)}")
            self.ready_to_pump = True
        if next_chunklist:
            if not isinstance(next_chunklist, list):  # A hack, this should not be needed.
                next_chunklist = next_chunklist.value
                self.DEBUG and print("Converting chunklist to a list")
            self.chunklist.append(next_chunklist)
            hashdict = {hashlib.md5(next_chunklist[0].encode()).digest().hex(): self.n_tracks_sent}
            self.first_chunk_dict.update(hashdict)

            self.extend_playlist(next_chunklist)
            self.DEBUG and print(f"hashdict now {self.first_chunk_dict}")
        return

    def poll_chunklist(self, url):
        loop = asyncio.get_event_loop()
        task = loop.create_task(self.get_chunklist(url))
        while not task.done():
            loop.run_until_complete(dummy(0))  # give some time back to the main_loop
            yield
        next_chunklist = task.data
        loop.close()
        return next_chunklist

    async def get_chunklist(self, url):
        if url.endswith("m3u8"):
            # determine the chunks
            self.DEBUG and print(f"first url is {url}")
            self.chunked_urls = True
            base_url = "/".join(url.split("/")[:-1])
            chunklist_url = await requests.get(url)
            chunklist_url = f"{base_url}/{chunklist_url.text.splitlines()[-1]}"
            lines = await requests.get(chunklist_url)
            lines = lines.text.splitlines()
            chunks = [x for x in lines if x.startswith("media_")]
            chunklist = [f"{base_url}/{x}" for x in chunks]
        else:
            chunklist = [url]
        return chunklist

    def audio_pump(self):
        self.pump_chunks()
        return

    def is_playing(self):
        return self.player.is_playing()

    def is_stopped(self):
        return self.player.is_stopped()

    def is_paused(self):
        return self.player.is_paused()

    def set_volume(self, volume):
        return self.player.set_volume(volume)

    def get_volume(self):
        return self.player.get_volume()

    def reset_player(self):
        return self.player.reset_player()
