import audioPlayer_1053 as Player
import time

player = Player.AudioPlayer()
# player.set_playlist(["silence"], ["https://storage.googleapis.com/spertilo-data/sundry/silence600.ogg"])

playlist_titles = [f"track{x:02d}" for x in range(1, 26, 1)]
playlist_urls = (
    [
        f"https://archive.org/download/gd1972-05-18.sbd.miller.79057.sbeok.flac16/gd72-05-18d1t{x:02d}.mp3"
        for x in range(1, 13, 1)
    ]
    + [
        f"https://archive.org/download/gd1972-05-18.sbd.miller.79057.sbeok.flac16/gd72-05-18d2t{x:02d}.mp3"
        for x in range(1, 8, 1)
    ]
    + [
        f"https://archive.org/download/gd1972-05-18.sbd.miller.79057.sbeok.flac16/gd72-05-18d3t{x:02d}.mp3"
        for x in range(1, 7, 1)
    ]
)
print(list(zip(playlist_titles, playlist_urls)))
# player.set_playlist(['t1','t2'],["https://archive.org/download/gd75-08-13.fm.vernon.23661.sbeok.shnf/gd75-08-13d1t01.mp3","https://archive.org/download/gd75-08-13.fm.vernon.23661.sbeok.shnf/gd75-08-13d1t02.mp3"])
player.set_playlist(playlist_titles * 10, playlist_urls * 10)
player.decoder.reset()
print(hex(player.decoder.mode()))
player.play()
i = 0
while True:
    player.audio_pump()
    time.sleep_ms(40)
    if (i % 1000) == 0:
        print(f".{player}")
    i = i + 1
