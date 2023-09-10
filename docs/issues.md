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


## 2023-09-07
### ~~Long-press of select no longer working.~~
This is working.

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

This may have been a long silence at the end of the previous track, because the display shows the track that it's reading instead of the one that it's playing.

## Track on Screen Not Updating
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

A workaround would be to check the track status and set the tracknames to the track that we are reading?

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
