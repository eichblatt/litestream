from machine import SPI, Pin
import st7789
import sys

import playerManager
import fonts.NotoSans_24 as pfont_med

_SCREEN_BAUDRATE = 40_000_000
SCREEN_HEIGHT = 240
SCREEN_WIDTH = 320

screen_spi = SPI(1, baudrate=_SCREEN_BAUDRATE, sck=Pin(12), mosi=Pin(11))
reset = Pin(4, Pin.OUT)
cs = Pin(10, Pin.OUT)
dc = Pin(6, Pin.OUT)
backlight = Pin(5, Pin.OUT)


tft = st7789.ST7789(
    screen_spi,
    SCREEN_HEIGHT,
    SCREEN_WIDTH,
    reset=reset,
    cs=cs,
    dc=dc,
    backlight=backlight,
    color_order=st7789.RGB,
    inversion=False,
    rotation=1,
    options=0,
    buffer_size=64 * 64 * 3,
)
tft.init()
tft.madctl(0xE0)
screen_spi.init(baudrate=_SCREEN_BAUDRATE)
tft.rect(0, 0, SCREEN_WIDTH, SCREEN_HEIGHT, st7789.WHITE)
tft.write(pfont_med, "testing", 0, 0, st7789.WHITE)

import async_urequests as requests

# from async_urequests import urequests as requests
import time, network, asyncio

wifi = network.WLAN(network.STA_IF)
wifi.active(True)
wifi.config(pm=network.WLAN.PM_NONE)
if not wifi.isconnected():
    wifi.connect("fiosteve-guest", "saragansteve3")

import classical

player = playerManager.PlayerManager(callbacks={"display": classical.display_tracks}, debug=True)
urllist = [
    "https://stream.classicalarchives.com/tm/_definst_/mp4:syIKvGZtKLGB5xKL-iuiu-mdXRtgnp810mnsIrPcpPisPnH2h7n_757X_xv5YHEVRUvDkIh5NknQ6-yQQrwrIT98SCPxLuqLTwV_lw5iUw0g8RvjveJD_lyOJHmX5lE1_een9Ff6Itk6BJp5gCOEu7CA-tZWHSiCZpO8hu3rYDs/RAu6e0ALZbO0T5JMQTFgqQ/media_w1803006417_0.ts",
    "https://stream.classicalarchives.com/tm/_definst_/mp4:syIKvGZtKLGB5xKL-iuiu-mdXRtgnp810mnsIrPcpPisPnH2h7n_757X_xv5YHEVRUvDkIh5NknQ6-yQQrwrIT98SCPxLuqLTwV_lw5iUw0g8RvjveJD_lyOJHmX5lE1_een9Ff6Itk6BJp5gCOEu7CA-tZWHSiCZpO8hu3rYDs/RAu6e0ALZbO0T5JMQTFgqQ/media_w1803006417_1.ts",
    "https://stream.classicalarchives.com/tm/_definst_/mp4:syIKvGZtKLGB5xKL-iuiu-mdXRtgnp810mnsIrPcpPisPnH2h7n_757X_xv5YHEVRUvDkIh5NknQ6-yQQrwrIT98SCPxLuqLTwV_lw5iUw0g8RvjveJD_lyOJHmX5lE1_een9Ff6Itk6BJp5gCOEu7CA-tZWHSiCZpO8hu3rYDs/RAu6e0ALZbO0T5JMQTFgqQ/media_w1803006417_2.ts",
    "https://stream.classicalarchives.com/tm/_definst_/mp4:syIKvGZtKLGB5xKL-iuiu-mdXRtgnp810mnsIrPcpPisPnH2h7n_757X_xv5YHEVRUvDkIh5NknQ6-yQQrwrIT98SCPxLuqLTwV_lw5iUw0g8RvjveJD_lyOJHmX5lE1_een9Ff6Itk6BJp5gCOEu7CA-tZWHSiCZpO8hu3rYDs/RAu6e0ALZbO0T5JMQTFgqQ/media_w1803006417_3.ts",
    "https://stream.classicalarchives.com/tm/_definst_/mp4:syIKvGZtKLGB5xKL-iuiu-mdXRtgnp810mnsIrPcpPisPnH2h7n_757X_xv5YHEVRUvDkIh5NknQ6-yQQrwrIT98SCPxLuqLTwV_lw5iUw0g8RvjveJD_lyOJHmX5lE1_een9Ff6Itk6BJp5gCOEu7CA-tZWHSiCZpO8hu3rYDs/RAu6e0ALZbO0T5JMQTFgqQ/media_w1803006417_4.ts",
    "https://stream.classicalarchives.com/tm/_definst_/mp4:syIKvGZtKLGB5xKL-iuiu-mdXRtgnp810mnsIrPcpPisPnH2h7n_757X_xv5YHEVRUvDkIh5NknQ6-yQQrwrIT98SCPxLuqLTwV_lw5iUw0g8RvjveJD_lyOJHmX5lE1_een9Ff6Itk6BJp5gCOEu7CA-tZWHSiCZpO8hu3rYDs/RAu6e0ALZbO0T5JMQTFgqQ/media_w1803006417_5.ts",
    "https://stream.classicalarchives.com/tm/_definst_/mp4:syIKvGZtKLGB5xKL-iuiu-mdXRtgnp810mnsIrPcpPisPnH2h7n_757X_xv5YHEVRUvDkIh5NknQ6-yQQrwrIT98SCPxLuqLTwV_lw5iUw0g8RvjveJD_lyOJHmX5lE1_een9Ff6Itk6BJp5gCOEu7CA-tZWHSiCZpO8hu3rYDs/RAu6e0ALZbO0T5JMQTFgqQ/media_w1803006417_6.ts",
]


tracklist = [f"Track {i+1}" for i in range(len(urllist))]

print("Playing...", tracklist, urllist)
player.set_playlist(tracklist, urllist)

player.play()

while True:
    try:
        player.audio_pump()
    except Exception as e:
        print("Decoder error", e)
        sys.exit()
