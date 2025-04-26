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


async def dummy():
    await asyncio.sleep(0)
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
        self.tracklist = []  # track titles
        self.credits = []
        self.pumped_indices = []
        self.playlist_completed = False
        self.first_chunk_dict = {}
        self.track_index = 0
        self.pump_dry = True
        self.block_pump = True
        self.pumpahead = 1
        self.chunk_generator = None
        self.urls = []  # high-level urls
        self.volume = 11

        self.chunked_urls = False
        self.button_window = None
        self.last_button_time = time.ticks_ms()
        self.resume_playing = False

    def set_playlist(self, track_titles, urls, credits=[]):
        self.chunklist = [[] for _ in range(len(urls))]
        self.tracklist = track_titles
        self.pumped_indices = []
        self.credits = credits
        self.playlist_completed = False
        self.first_chunk_dict = {}
        self.track_index = 0
        self.pump_dry = True
        self.block_pump = False
        self.chunk_generator = None

        setbreak_url = "https://storage.googleapis.com/spertilo-data/sundry/silence600.ogg"
        urls = [x if not (x.endswith("silence600.ogg")) else setbreak_url for x in urls]
        encorebreak_url = "https://storage.googleapis.com/spertilo-data/sundry/silence0.ogg"
        urls = [x if not (x.endswith("silence0.ogg")) else encorebreak_url for x in urls]
        urls = [x.replace(" ", "%20") for x in urls]
        self.urls = urls
        self.audio_pump()

    def __repr__(self):
        clstr = f"Player Manager: {self.track_index+1}/{len(self.tracklist)} tracks. Chunk lengths:{[len(x) for x in self.chunklist]}"
        return clstr + f" {self.player}. "

    def extend_playlist(self, next_index):
        if next_index in self.pumped_indices:
            print(f"extend_playlist: Track {next_index} already pumped")
            return 0
        urllist = self.chunklist[next_index]
        print(f"extend_playlist: Track {next_index}/{len(self.tracklist)}. + {len(urllist)} URLs to player.")
        new_elements = [(x, hashlib.md5(x.encode()).digest().hex()) for x in urllist]
        # This is not working, the URL's can change between calls.
        # len0 = len(new_elements)
        # new_elements = [x for x in new_elements if x[0] not in [y[0] for y in self.player.playlist]]
        # if len(new_elements) < len0:
        #    print(f"extend_playlist: {len0 - len(new_elements)} duplicates removed")
        # if len(new_elements) == 0:
        #    return 0
        hashkey = new_elements[0][1]
        hashdict = {hashkey: next_index}
        self.first_chunk_dict.update(hashdict)
        self.player.playlist.extend(new_elements)
        self.pumped_indices.append(next_index)
        # self.chunklist[next_index] = []  # No caching of URLs
        return len(new_elements)

    def increment_track_screen(self, track_num=None, increment=1):
        if track_num and track_num == self.track_index:
            return self.track_index
        if (self.track_index + increment) >= self.n_tracks:
            print(f"increment_track_screen. already on last track {self.track_index}")
            return self.track_index
        if (self.track_index + increment) <= 0:
            print(f"increment_track_screen. already on first track {self.track_index}")

        self.track_index = self.track_index + increment if track_num is None else track_num
        tracklist = self.remaining_track_names()
        try:
            self.DEBUG and print(f"playerManager display: {tracklist}")
            self.callbacks["display"](*tracklist)
        except Exception as e:
            print(f"Error in display callback: {e}")
        finally:
            self.DEBUG and print(f"increment_track_screen: returning track {self.track_index} of {self.n_tracks}")
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
            self.increment_track_screen(track_num)
            return

        if "Finished playing track" in message:
            return

        if "Finished reading track" in message:
            if not self.chunked_urls:
                return

        if "Finished reading all tracks" in message:
            if not self.chunked_urls:
                return

        if "Finished playing playlist" in message:
            self.stop(reset_head=True)
            self.playlist_completed = True
            try:
                self.callbacks["display"](*self.tracklist)
            except Exception as e:
                print(f"Error in display callback: {e}")
            return

        if "long pause" in message:
            self.stop(reset_head=False)
            chunks_to_send = []
            for track_chunks in self.chunklist[self.track_index :]:
                for chunk in track_chunks:
                    if hashlib.md5(chunk.encode()).digest().hex() == last_word:
                        print("Found the chunk to resume from.")
                        chunks_to_send = []
                    chunks_to_send.append(chunk)
            self.player.playlist = [(chunk, hashlib.md5(chunk.encode()).digest().hex()) for chunk in chunks_to_send]
            self.play()
            return

    @property
    def n_tracks(self):
        return len(self.tracklist)

    @property
    def max_chunks_ahead(self):
        return 5 if self.is_playing() else len(self.urls) * 2

    def remaining_track_names(self):
        track_names = self.tracklist[max(0, self.track_index) :] + self.credits + [""] * 10
        return track_names

    def is_playing(self):
        return self.player.is_playing()

    def pause(self):
        return self.player.pause()

    def stop(self, reset_head=True):
        # self.ready_to_pump = False
        # print("No more chunks will be sent -- player reset")
        self.button_window = None
        self.player.stop()  # set the player.playlist to [] if reset_head
        self.set_volume(self.volume)
        self.pumped_indices = []
        if reset_head:
            self.increment_track_screen(0)  # reset the track index, and update the screen
        return

    def play(self):
        if len(self.player.playlist) == 0:
            print("No tracks in playlist")
            return
        return self.player.play()

    def handle_button_presses(self):
        if self.button_window is None:
            self.resume_playing = self.is_playing()
            self.stop(reset_head=False)  # set player.playlist to []
            self.block_pump = True
            self.button_window = Timer(-1)
            self.button_window.init(period=1_000, mode=Timer.ONE_SHOT, callback=self._play_selected_track)
        return

    def _play_selected_track(self, timer):
        if time.ticks_diff(time.ticks_ms(), self.last_button_time) < 1_000:
            # re-initialize the button window
            print(f"Button window extended, {timer}")
            if not self.button_window:
                return
            self.button_window.deinit()
            self.button_window.init(period=1_000, mode=Timer.ONE_SHOT, callback=self._play_selected_track)
            return
        # set the track to the cumulative position of the button presses (self.track_index)
        print(f"Button window expired, track index is {self.track_index}")
        self.button_window = None
        if not 0 < (self.track_index) < self.n_tracks:
            print("setting track_index to be within bounds")
            self.track_index = max(0, min(self.track_index, len(self.urls) - 1))
            # self.playlist_completed = True
            # self.block_pump = False
            # return
        self.pump_dry = True
        chunks_to_send = self.chunklist[self.track_index]
        if len(chunks_to_send) > 0:
            self.player.playlist = [(chunk, hashlib.md5(chunk.encode()).digest().hex()) for chunk in chunks_to_send]
        self.audio_pump(unblock=True)
        if self.resume_playing:
            self.play()

    def rewind(self):
        self.last_button_time = time.ticks_ms()
        self.increment_track_screen(increment=-1)  # sets the track index
        self.handle_button_presses()

    def ffwd(self):
        self.last_button_time = time.ticks_ms()
        self.increment_track_screen()  # sets the track index
        self.handle_button_presses()

    def pump_chunks(self):
        if self.block_pump or (len(self.player.playlist) > self.max_chunks_ahead):
            return
        next_chunklist = None
        next_index = None
        if self.pump_dry:  # Block until first chunks are pumped
            next_index = self.track_index
            next_chunklist = asyncio.run(self.get_chunklist(self.urls[next_index]))
            self.pump_dry = False
        else:
            # Find the next index without a chunklist
            for i in range(self.track_index + self.pumpahead, len(self.chunklist)):
                if len(self.chunklist[i]) > 0:
                    print(f"pump_chunks: chunklist {i} is not empty")
                    elements_added = self.extend_playlist(i)
                    self.pumpahead = 1 if elements_added > 0 else self.pumpahead + 1
                    return
                elif self.chunklist[i] == []:
                    next_index = i
                    break

            if next_index:
                # self.DEBUG and print(f"{next_index}(+{self.pumpahead})", end=". ")
                if self.chunk_generator is None:
                    self.chunk_generator = self.poll_chunklist(next_index)
                try:
                    next(self.chunk_generator)
                except StopIteration as e:
                    next_index, next_chunklist = e.value
                    self.chunk_generator = None  # prepare for next task
        if next_chunklist:
            # self.DEBUG and print(f"pump_chunks {next_chunklist}")
            if not isinstance(next_chunklist, list):  # A hack, this should not be needed.
                next_chunklist = next_chunklist.value
            self.chunklist[next_index] = next_chunklist
            self.extend_playlist(next_index)
            self.pumpahead = 1
        return

    def poll_chunklist(self, next_index):
        url = self.urls[next_index]
        loop = asyncio.get_event_loop()
        task = loop.create_task(self.get_chunklist(url))
        while not task.done():
            loop.run_until_complete(dummy())  # start the task, not sure why dummy is required
            yield
        next_chunklist = task.data
        loop.close()
        return next_index, next_chunklist

    async def get_chunklist(self, url):
        if url.endswith("m3u8"):
            # determine the chunks
            print(f"get_chunklist. first url is {url}")
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

    def audio_pump(self, unblock=False):
        if self.block_pump and not unblock:
            return
        self.block_pump = False
        self.pump_chunks()
        return

    def is_playing(self):
        return self.player.is_playing()

    def is_stopped(self):
        return self.player.is_stopped()

    def is_paused(self):
        return self.player.is_paused()

    def set_volume(self, volume):
        self.volume = min(max(volume, 5), 11)
        return self.player.set_volume(self.volume)

    def get_volume(self):
        self.volume = self.player.get_volume()
        return self.volume

    def reset_player(self):
        return self.player.reset_player()
