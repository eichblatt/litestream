# esp32audio.py VS1053b driver demo/test for ESP32
# Uses synchronous driver.

# (C) Peter Hinch 2020
# Released under the MIT licence

from vs1053_syn import *
from machine import SPI, Pin, freq
import uasyncio as asyncio

# Works at stock speed
# freq(240_000_000)

# 128K conversion
# ffmpeg -i yellow.flac -acodec libmp3lame -ab 128k yellow.mp3
# VBR conversion
# ffmpeg -i yellow.flac -acodec libmp3lame -qscale:a 0 yellow_v.mp3
# Yeah, I know. I like Coldplay...


spi = SPI(1, sck=Pin(12), mosi=Pin(13), miso=Pin(11))
reset = Pin(4, Pin.OUT, value=1)  # Active low hardware reset
xcs = Pin(10, Pin.OUT, value=1)  # Labelled CS on PCB, xcs on chip datasheet
# sdcs = Pin(10, Pin.OUT, value=1)  # SD card CS
xdcs = Pin(9, Pin.OUT, value=1)  # Data chip select xdcs in datasheet
dreq = Pin(14, Pin.IN)  # Active high data request
player = VS1053(spi, reset, dreq, xdcs, xcs)

try:
    player.patch()  # Optional. From /fc/plugins/
except ValueError as e:
    print(e)
except Exception as e:
    raise e


def main(songs):
    # player.volume(-10, -10)  # -10dB (0dB is loudest)
    # player.sine_test()  # Cattles volume
    # player.volume(-10, -10)  # -10dB (0dB is loudest)
    # player.mode_set(SM_EARSPEAKER_LO | SM_EARSPEAKER_HI)  # You decide.
    # player.response(bass_freq=150, bass_amp=15)  # This is extreme.
    for song in songs:
        print(song)
        with open(song, "rb") as f:
            player.play(f)


# main(["/lib/01Tuning.mp3"])
# main(['/data/gd75-08-13d1t01.ogg'])
# main(['/data/gd75-08-13d1t02.ogg'])
# main(['/data/gd75-08-13d1t02.mp3'])
# main(['/data/gd75-08-13d1t01.ogg','/data/gd75-08-13d1t02.ogg'])
# main(['/data/gd75-08-13d1t01.mp3','/data/gd75-08-13d1t02.mp3'])
