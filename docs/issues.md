# Issues 

## 2023-09-06
###  OutBuffer Overwrite when playing 8/13/75 
This does not happen every time. It _may_ be caused by a lot of print statements that I've added to the code.

Finished decoding track 1  - Playing track: 2/19. Read 183663/2976071 (6.17%) of track 2
File "/lib/audioPlayer.py", line 191, in bytes_wasWritten
AssertionError: OutBuffer Overwrite

Line 191 is the first `assert` statement in the clause below:
```
    # Tell the buffer how many bytes we just wrote. Must call this after every write to the buffer
    def bytes_wasWritten(self, count):
        if self._writePos < self._readPos:
            assert self._writePos + count <= self._readPos, "OutBuffer Overwrite"
        self.BytesInBuffer += count
        assert self.BytesInBuffer <= self.BufferSize, "OutBuffer Overflow"
```
I see the same error when playing 1989-07-17, track 4
```
Playing track: 4/25. Read 5078458/5210196 (97.47%) of track 4
Playing track: 4/25. Read 30020/7748142 (0.39%) of track 5
File "/lib/audioPlayer.py", line 199, in bytes_wasWritten
AssertionError: OutBuffer Overwrite
```
**NOTE** This happened at the track boundary. That is probably not a coincidence.
**Update 2023-09-09:** I have added some text to the Assertion Error message, for next time we see this error.

==Update from Mike==

I'm pretty sure the OutBuffer overwrite is from the interrupt firing just as we are reading the value of the Outbuffer in the decode loop...
It needs to be protected with a mutex, but I ran out of time to figure out it
Probably best to do it in the outbuffer class. Whenever readpointer and writepointer get updated it needs a mutex
Inbuffer doesn't need it because it is never accessed from an interrupt


Playing track: 16/24. Read 2673237/6148949 (43.47%) of track 16
File "/lib/audioPlayer.py", line 201, in bytes_wasWritten
AssertionError: OutBuffer Overwrite Readpos. Count: 4096. WritePos: 859648. ReadPos:0

And again on 1988-06-23

Playing track: 10/21. Read 1374319/8451583 (16.26%) of track 12
Playing track: 10/21. Read 1496850/8451583 (17.71%) of track 12
Traceback (most recent call last):
  File "boot.py", line 122, in <module>
  File "/lib/main.py", line 321, in run_livemusic
  File "/lib/livemusic.py", line 526, in run
  File "/lib/livemusic.py", line 216, in main_loop
  File "/lib/audioPlayer.py", line 201, in bytes_wasWritten
AssertionError: OutBuffer Overwrite Readpos. Count: 4096. WritePos: 853504. ReadPos:0
MicroPython v1.20.0-438-g65f0cb11a-dirty on 2023-09-04; Generic ESP32S3 module with Octal-SPIRAM with ESP32S3

Again, this is impossible. The _readPos must have been set to 0 between the if statement and the assertion.

Also of note: Both Time Machines failed at the same point, one of them, though, reset the device while the other is still ok.

## 2023-09-07
### Long-press of select no longer working.
It looks like it works, but it doesn't update the list of URL's.

### Failing to get data from the cloud after playing music
Normally, this works, but if I play something and then change dates, I often get this problem or run out of memory.
```
  File "/lib/livemusic.py", line 85, in select_date
  File "/lib/mrequests/mrequests.py", line 27, in get
  File "/lib/mrequests/mrequests.py", line 299, in request
OSError: [Errno 1] EPERM
MicroPython v1.20.0-438-g65f0cb11a-dirty on 2023-09-04; Generic ESP32S3 module with Octal-SPIRAM with ESP32S3
Type "help()" for more information.
```

## 2023-09-08

### Jama kills it sometimes. 
I was all the way through a second show, and the second I woke up my computer it died. 
The computer must have woken up Jama which was connected to the device. It can't have been a coincidence.

### ~~End of Tape Make the Play Triangle disappear.~~
At the end of the tape the triangle needs to disappear.
FIXED

## 2023-09-09

### Make Autoplay work
Right now, you have to select the date and then play the show. I'd like selecting a date to automatically play it.

### Player Hangs at 100% of a Track Read.

The output in Jama says that it has completely played the track, but the screen shows it on track 24, and it's not playing.

PlayPause DOWN
Playing track: 23/25. Read 4144428/4144428 (100.00%) of track 24
Pausing URL https://archive.org/download/gd89-07-17.sbd.unknown.17702.sbeok.shnf/gd1989-07-17d3t06.ogg
PlayPause UP
PlayPause DOWN
Paused track: 23/25. Read 4144428/4144428 (100.00%) of track 24

However, the device is still working, and I can stop, and ffwd to the same track and play it (although pause/unpause didn't work).

### Althea 7/17/88 -- hung on 100% read
This is basically the same as the previous issue, but it happened on BOTH players at the same track.

Both players halted overnight and were on Althea, 7/17/88 in the morning. I resumed them and they both started playing. Perhaps the problem was in the transition from the previous track or on the transtion from Althea to the next track. 

Listening again, no problem from previous track or the next track. Maybe archive.org went down briefly overnight?

## 2023-09-10
### Encore Break lasts several minutes!
The encore break is pointing to https://storage.googleapis.com/spertilo-data/sundry/silence0.ogg, which is in fact 0 seconds of silence. But for some reason, it plays it for a minute or 2. 

I recently had a crash at the end of the encore break:

Playing track: 18/21. Read 7544550/7767696 (97.13%) of track 18
Playing track: 18/21. Read 7667768/7767696 (98.71%) of track 18
Playing track: 18/21. Read 4029/4029 (100.00%) of track 19
Finished decoding track 18  - Playing track: 19/21. Read 4029/4029 (100.00%) of track 19
Playing track: 19/21. Read 4029/4029 (100.00%) of track 19
Playing track: 19/21. Read 4029/4029 (100.00%) of track 19
Playing track: 19/21. Read 4029/4029 (100.00%) of track 19
Playing track: 19/21. Read 4029/4029 (100.00%) of track 19
Playing track: 19/21. Read 4029/4029 (100.00%) of track 19
Playing track: 19/21. Read 4029/4029 (100.00%) of track 19  -- 1 Minute
Playing track: 19/21. Read 4029/4029 (100.00%) of track 19
Playing track: 19/21. Read 4029/4029 (100.00%) of track 19
Playing track: 19/21. Read 4029/4029 (100.00%) of track 19
Playing track: 19/21. Read 4029/4029 (100.00%) of track 19
Playing track: 19/21. Read 4029/4029 (100.00%) of track 19
Playing track: 19/21. Read 4029/4029 (100.00%) of track 19  -- 2 Minutes
Playing track: 19/21. Read 4029/4029 (100.00%) of track 19
Playing track: 19/21. Read 4029/4029 (100.00%) of track 19
Playing track: 19/21. Read 4029/4029 (100.00%) of track 19
Playing track: 19/21. Read 4029/4029 (100.00%) of track 19
Playing track: 19/21. Read 4029/4029 (100.00%) of track 19
Playing track: 19/21. Read 4029/4029 (100.00%) of track 19  -- 3 Minutes
Playing track: 19/21. Read 4029/4029 (100.00%) of track 19
Playing track: 19/21. Read 4029/4029 (100.00%) of track 19
Playing track: 19/21. Read 4029/4029 (100.00%) of track 19
Playing track: 19/21. Read 4029/4029 (100.00%) of track 19
Decoder Start success. Sync word at 0
Finished decoding track 20  - Guru Meditation Error: Core  1 panic'ed (StoreProhibited). Exception was unhandled.

Core  1 register dump:
PC      : 0x42003524  PS      : 0x00060930  A0      : 0x82002426  A1      : 0x3fced080  
A2      : 0x00000000  A3      : 0x0000001e  A4      : 0x00000000  A5      : 0x00000000  
A6      : 0x00000000  A7      : 0x3fced080  A8      : 0x00000000  A9      : 0x3fced040  
A10     : 0x00000000  A11     : 0x00000004  A12     : 0x3c13a928  A13     : 0x3c13e53c  
A14     : 0x00000001  A15     : 0x3fced040  SAR     : 0x0000001a  EXCCAUSE: 0x0000001d  
EXCVADDR: 0x00000000  LBEG    : 0x400556d5  LEND    : 0x400556e5  LCOUNT  : 0xfffffffe  


Backtrace: 0x42003521:0x3fced080 0x42002423:0x3fced140 0x4200a022:0x3fced190 0x4201dca9:0x3fced1f0 0x42024ae5:0x3fced210 0x42024ba9:0x3fced230 0x403b8e41:0x3fced250 0x403b8444:0x3fced360 0x42024ae5:0x3fced380 0x42024ba9:0x3fced3a0 0x4037973d:0x3fced3c0 0x4201dd78:0x3fced460 0x42024ae5:0x3fced490 0x4037968d:0x3fced4b0 0x4201dd78:0x3fced550 0x42024ae5:0x3fced580 0x42024ba9:0x3fced5a0 0x4037973d:0x3fced5c0 0x4201dd78:0x3fced660 0x42024ae5:0x3fced6c0 0x42024ba9:0x3fced6e0 0x4037973d:0x3fced700 0x4201dd78:0x3fced7a0 0x42024ae5:0x3fced800 0x42024b50:0x3fced820 0x42043d4d:0x3fced860 0x4204407a:0x3fced890 0x42024c28:0x3fced980* Device disconnected.

## Track on Screen Not Updating
==FIXED==
This is happening on both Machines, so it's something about the track or show.

The track is from 6-17-88, between Gimme Some Loving and All Along the Watchtower.
Un-pausing URL https://archive.org/download/gd1988-06-17.aud.holtz.nak100s.112317.flac16/gd1988-06-17d03t03.ogg
```
Playing track: 18/24. Read 3707639/3931694 (94.30%) of track 18
Playing track: 18/24. Read 3828246/3931694 (97.37%) of track 18
Playing track: 18/24. Read 18468/4064896 (0.45%) of track 19
Playing track: 18/24. Read 150215/4064896 (3.70%) of track 19
Playing track: 18/24. Read 285271/4064896 (7.02%) of track 19
```
Note: The after All Along the Watchtower finished, we STILL don't get a track update into Black Peter
```
Playing track: 18/24. Read 3975956/4064896 (97.81%) of track 19
Playing track: 18/24. Read 0/6889914 (0.00%) of track 20
Playing track: 18/24. Read 166514/6889914 (2.42%) of track 20
Playing track: 18/24. Read 292283/6889914 (4.24%) of track 20
```
Or into Turn On Your Lovelight
The screen never advances after this track.
However, if we ffwd and then rewind, and thus advance the screen, it cacthes up.
```
Playing track: 18/24. Read 4195043/5227318 (80.25%) of track 21
Playing track: 18/24. Read 4315468/5227318 (82.56%) of track 21
Playing track: 18/24. Read 4437806/5227318 (84.90%) of track 21
Rewind UP
Stopped track
Rewind DOWN
Resuming playing
FFwd UP
Stopped track
FFwd DOWN
FFwd UP
Stopped track
FFwd DOWN
FFwd UP
Stopped track
FFwd DOWN
Stopped track
Resuming playing
FFwd UP
Stopped track
FFwd DOWN
Resuming playing
FFwd UP
Stopped track
FFwd DOWN
Resuming playing
Playing track: 22/24. Read 206512/1220236 (16.92%) of track 22
Playing track: 22/24. Read 378515/1220236 (31.02%) of track 22
Playing track: 22/24. Read 512535/1220236 (42.00%) of track 22
Playing track: 22/24. Read 642489/1220236 (52.65%) of track 22
Playing track: 22/24. Read 771831/1220236 (63.25%) of track 22
```
And it continues to advance after that.

Same thing happens for 1988-05-01, after track 9 (Cassidy, which was 1 before Set Break).
I wonder if this is related to the Set/Encore breaks somehow?

I believe I fixed thi
### Failure!

After more than 5.5 full shows, it has finally crashed and requires a reboot.

Playing track: 11/24. Read 71558/71558 (100.00%) of track 10
Traceback (most recent call last):
  File "boot.py", line 122, in <module>
  File "/lib/main.py", line 321, in run_livemusic
  File "/lib/livemusic.py", line 526, in run
  File "/lib/livemusic.py", line 216, in main_loop
  File "/lib/audioPlayer.py", line 129, in bytes_wasRead
KeyboardInterrupt: 
MicroPython v1.20.0-438-g65f0cb11a-dirty on 2023-09-04; Generic ESP32S3 module with Octal-SPIRAM with ESP32S3
Type "help()" for more information.

### Set Break as current track
The set break is the "track being read" for about 4 minutes, and then it starts reading the next track.
```
Playing track: 10/24. Read 71558/71558 (100.00%) of track 10
Playing track: 10/24. Read 71558/71558 (100.00%) of track 10
Playing track: 10/24. Read 71558/71558 (100.00%) of track 10
Playing track: 10/24. Read 71558/71558 (100.00%) of track 10
Playing track: 10/24. Read 71558/71558 (100.00%) of track 10
Playing track: 10/24. Read 71558/71558 (100.00%) of track 10 # 1 Minute
Playing track: 10/24. Read 71558/71558 (100.00%) of track 10
Playing track: 10/24. Read 71558/71558 (100.00%) of track 10
Playing track: 10/24. Read 71558/71558 (100.00%) of track 10
Playing track: 10/24. Read 71558/71558 (100.00%) of track 10
Playing track: 10/24. Read 71558/71558 (100.00%) of track 10
Playing track: 10/24. Read 71558/71558 (100.00%) of track 10 # 2 Minutes
Playing track: 10/24. Read 71558/71558 (100.00%) of track 10
Playing track: 10/24. Read 71558/71558 (100.00%) of track 10
Playing track: 10/24. Read 71558/71558 (100.00%) of track 10
Playing track: 10/24. Read 71558/71558 (100.00%) of track 10
Playing track: 10/24. Read 71558/71558 (100.00%) of track 10
Playing track: 10/24. Read 71558/71558 (100.00%) of track 10 # 3 Minutes
Playing track: 10/24. Read 71558/71558 (100.00%) of track 10
Playing track: 10/24. Read 71558/71558 (100.00%) of track 10
Playing track: 10/24. Read 71558/71558 (100.00%) of track 10
Playing track: 10/24. Read 71558/71558 (100.00%) of track 10
Playing track: 10/24. Read 82781/3522582 (2.35%) of track 11
Playing track: 10/24. Read 83926/3522582 (2.38%) of track 11 # 4 Minutes
Playing track: 10/24. Read 85084/3522582 (2.42%) of track 11
Playing track: 10/24. Read 86241/3522582 (2.45%) of track 11
Playing track: 10/24. Read 87389/3522582 (2.48%) of track 11
```
Because of this, I don't want to have the display show the "track_being_read". However, this would be a good solution otherwise.

## 2023-09-11
### Need to Stop Player Before Selecting a New Date
As soon as select is pressed on a new date, **stop the player** similar to what happens with Ffwd and Rewind.

## 2023-09-20
### VS1053 decoder chip working!

However, it's ogg coverage is spotty. For example, it will play 8/13/75 track01 fine, but won't play track02.  Maybe there is a patch.

Also, there is a **noticeable gap between tracks**, even if both are mp3. However, according to http://www.vsdsp-forum.com/phpbb/viewtopic.php?t=1671
PS. In MP3 there is no problem to play files back to back without pause between files ... IF you are very careful to send only complete MP3 blocks: no extra bytes, no missing bytes, no garbage at the beginning or end of the file (like ID3 tags, make your microcontroller code to strip these) and all MP3 files have the same sample rate.

### Can we run VS1053 in a non-blocking way?
Current code is simply playing in a tight loop, with no way to do anything else. Can we play chunks of larger than 32 bytes, and pump it from a method like audio_pump?

## 2023-09-22
### Duty Cycle of VS1053 Audio Pump
We have to pump the vs1053 every 70 ms or so. The whole pumping takes about 30 ms, so it is busy 30% of the time.

### Playing Full Shows
So far, the VS1053 has been able to play every mp3 file that it has seen. It doesn't play ogg very well at all. Patch? I'm not sure. For now, I'm going with mp3.

### Can't Play and See Screen at the Same Time
The screen and the VS1053 share a PCI bus, and for some reason, once I start pumping audio to the chip, I can't update the screen. For now, that means I can't run headless. 
See https://docs.micropython.org/en/latest/esp32/quickref.html#hardware-spi-bus

Note:
```
MicroPython >>> player.decoder._spi

SPI(id=2, baudrate=11428571, polarity=0, phase=0, bits=8, firstbit=0, sck=12, mosi=11, miso=13)

MicroPython >>> tm.screen_spi

SPI(id=1, baudrate=40000000, polarity=0, phase=0, bits=8, firstbit=0, sck=12, mosi=11, miso=13)
```
## 2023-09-26
### Ground Loop Problem?
I am not sure if this is the same problem that I have. I am hearing buzzing when I power up the chip until it is reset, which is annoying.
https://github.com/karawin/Ka-Radio32/issues/167

## 2023-09-27
### URL that Cannot Be Played
https://archive.org/download/gd1972-07-21.148725.sbd.bear.dalton.miller.clugston.flac1648/gd72-07-21 s1t02 BTW.mp3
All of the files from this show are unplayable.
```
PlayPause DOWN
Peer close
read_header starting at 643887
   feed_decoder 643890
Peer close
read_header starting at 644128
   feed_decoder 644130
Peer close
read_header starting at 644375
   feed_decoder 644378
Peer close
read_header starting at 644619
   feed_decoder 644621
File "/lib/audioPlayer_1053.py", line 499, in feed_decoder
RuntimeError: Decode Packet failed
```
This is due to **spaces in the URL**. Fixed with `urllist = [x.replace(" ","%20") for x in urllist]`

## 2023-09-29
### Getting rid of ID3 tags from MP3 files
These are probably causing gaps between tracks. Let's get rid of them.
Here is how to do it with a file. 
```
In [36]: f = open('hurtsmetoo.mp3','rb')
    ...: out = open('test.mp3','wb')
    ...: marker = b"\xff\xfb"
    ...: i = 0
    ...: print(marker)
    ...: while f.peek(2)[:2] != marker:
    ...:     b = f.read(1)
    ...:     i = i + 1
    ...: print(f"i is {i}")
    ...: 
    ...: b = bytearray(f.read())
    ...: out.write(b)
    ...: 
    ...: f.close()
    ...: out.close()
b'\xff\xfb'
i is 78696
```
Now I just need to do it with a socket stream
**Solved**
## 2023-09-30
### Still Some Tiny Gaps
MP3 Format information here:
http://www.mp3-tech.org/programmer/frame_header.html
It's harder that I would think to find good information about this.
Test out a pair of files concatenated together using the file player.

I created a file with the tail end of China Cat Sunflower, and the other the head of I Know You Rider. I stripped out tags and concatenated the files. But there is still a gap when I play it, either in the VS1053 or using ffplay or mplayer. So gluing mp3 files together, even on frame boundaries, does not work.

Mplayer on my computer also cannot play the 2 tracks separately without a gap between them (ogg or mp3). But it DOES play them on gaplessly (ogg format) on the Time Machine.

This has information about the LAME headers and gapless playback:
https://wiki.hydrogenaud.io/index.php?title=MP3#VBRI.2C_XING.2C_and_LAME_headers

This page describes the LAME tags, which should have a delay & padding values for gapless playback
http://gabriel.mp3-tech.org/mp3infotag.html   **This is the most useful link on this subject**

Also https://lame.sourceforge.io/using.php , less useful.
### Seeking
Good info here https://stackoverflow.com/questions/60247805/seeking-within-mp3-file
## 2023-11-04
### From Grateful Dead 1993-04-04 (mp3 tape)

Playing -- Read 11380700/13398492 (85%) of track 9/21 InBuffer: 4029(3%) OutBuffer: 239616(33%)
Playing -- Read 11385080/13398492 (85%) of track 9/21 InBuffer: 3921(3%) OutBuffer: 0(0%)
Playing -- Read 11385080/13398492 (85%) of track 9/21 InBuffer: 3921(3%) OutBuffer: 0(0%)
Playing -- Read 11385080/13398492 (85%) of track 9/21 InBuffer: 3921(3%) OutBuffer: 0(0%)
Playing -- Read 11385080/13398492 (85%) of track 9/21 InBuffer: 3921(3%) OutBuffer: 0(0%)
Playing -- Read 11385080/13398492 (85%) of track 9/21 InBuffer: 3921(3%) OutBuffer: 0(0%)
Playing -- Read 11385080/13398492 (85%) of track 9/21 InBuffer: 3921(3%) OutBuffer: 0(0%)
Peer close
Socket Exception: Peer closed socket  Restarting track at offset 11475600
Playing -- Read 11504800/13398492 (86%) of track 9/21 InBuffer: 30755(25%) OutBuffer: 19968(3%)
Playing -- Read 11868340/13398492 (89%) of track 9/21 InBuffer: 24102(20%) OutBuffer: 711680(99%)
Playing -- Read 11934040/13398492 (89%) of track 9/21 InBuffer: 3700(3%) OutBuffer: 0(0%)
Playing -- Read 11934040/13398492 (89%) of track 9/21 InBuffer: 3700(3%) OutBuffer: 0(0%)
Playing -- Read 11934040/13398492 (89%) of track 9/21 InBuffer: 3700(3%) OutBuffer: 0(0%)
Playing -- Read 11934040/13398492 (89%) of track 9/21 InBuffer: 3700(3%) OutBuffer: 0(0%)
Socket Exception: [Errno 113] ECONNABORTED  Restarting track at offset 11934040
Error in playback loop -202

This must be an http error code 202, meaning "Accepted". 


### From Grateful Dead 1993-04-05 (mp3 tape)
I see this output and hear some glitches.

Playing -- Read 3836880/8471774 (45%) of track 1/20 InBuffer: 117810(96%) OutBuffer: 710656(99%)
Playing -- Read 4063180/8471774 (48%) of track 1/20 InBuffer: 43737(36%) OutBuffer: 710656(99%)
Playing -- Read 4248600/8471774 (50%) of track 1/20 InBuffer: 3522(3%) OutBuffer: 307712(43%)
Playing -- Read 4456568/8471774 (53%) of track 1/20 InBuffer: 3906(3%) OutBuffer: 0(0%)
Playing -- Read 4818000/8471774 (57%) of track 1/20 InBuffer: 9964(8%) OutBuffer: 410112(57%)
Playing -- Read 5047220/8471774 (60%) of track 1/20 InBuffer: 3839(3%) OutBuffer: 0(0%)
Playing -- Read 5365949/8471774 (63%) of track 1/20 InBuffer: 3618(3%) OutBuffer: 212480(30%)
Playing -- Read 5704220/8471774 (67%) of track 1/20 InBuffer: 47056(38%) OutBuffer: 303104(42%)

Lowering the timeout in decode_chunk to 10 ms fixed this problem, as far as I can tell.