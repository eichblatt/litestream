# Issues 

## 2023-09-06
### Problem when playing 8/13/75 
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

## 2023-09-07

### Long-press of select no longer working.

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

### End of Tape Make the Play Triangle disappear.

At the end of the tape the triangle needs to disappear.

