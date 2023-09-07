# Issues 

## 2023-09-06
Problem when playing 8/13/75 -- This does not happen every time. It _may_ be caused by a lot of print statements that I've added to the code.

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