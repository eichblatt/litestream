import audioPlayer_1053 as Player

player = Player.AudioPlayer()

player.set_playlist(
    ["t1", "t2"],
    [
        "https://archive.org/download/gd75-08-13.fm.vernon.23661.sbeok.shnf/gd75-08-13d1t01.mp3",
        "https://archive.org/download/gd75-08-13.fm.vernon.23661.sbeok.shnf/gd75-08-13d1t02.mp3",
    ],
)
player.play()
while True:
    player.audio_pump()
