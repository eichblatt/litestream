# OTA manages a MicroPython firmware update over-the-air.
# It assumes that there are two "app" partitions in the partition table and updates the one
# that is not currently running. When the update is complete, it sets the new partition as
# the next one to boot. If it does not reset/restart, use machine.reset() explicitly.

# https://github.com/tve/mqboard/blob/master/mqrepl/mqrepl.py#L23-L71

from .open_url import open_url
from esp32 import Partition

import usocket
import hashlib
import binascii
import sys
import gc


BLOCKLEN = const(4096)  # data bytes in a flash block

class OTA:
    
    # constructor, follow by calling ota(...)
    def __init__(self, verbose=False):
        self.verbose = verbose
        # the partition we are writing to
        self.part = Partition(Partition.RUNNING).get_next_update()
        
        # sha of the new app, computed in _app_data
        self.sha = hashlib.sha256()
        
        # keeping track (_app_data)
        self.block = 0
        self.buf = bytearray(BLOCKLEN)
        self.buflen = 0    # length of current content of self.buf
        
    # load app into the next partition and set it as the next one to boot upon restart
    #     :param:  url of app
    #     :sha256: sha256 of app
    def ota(self, url, sha256):
        if sys.platform != 'esp32':
            raise ValueError("N/A")
        if self.verbose: print('OTA ', end='')
        buffer = bytearray(BLOCKLEN)
        mv = memoryview(buffer)
        sock = open_url(url)
        while True:
            sz = sock.readinto(buffer)
            if not sz: break
            self._app_data(mv[0:sz])
        self._finish(sha256)
        buffer = None
        gc.collect()


    # accept chunks of the app and write to self.part
    def _app_data(self, data, last=False):
        global BLOCKLEN, buf, buflen, block
        data_len = len(data)
        self.sha.update(data)
        if self.buflen + data_len >= BLOCKLEN:
            # got a full block, assemble it and write to flash
            cpylen = BLOCKLEN - self.buflen
            self.buf[self.buflen : BLOCKLEN] = data[:cpylen]
            assert len(self.buf) == BLOCKLEN
            if self.verbose: print('.', end='')
            self.part.writeblocks(self.block, self.buf)
            self.block += 1
            data_len -= cpylen
            if data_len > 0:
                self.buf[:data_len] = data[cpylen:]
            self.buflen = data_len
        else:
            self.buf[self.buflen : self.buflen + data_len] = data
            self.buflen += data_len
            if last and self.buflen > 0:
                for i in range(BLOCKLEN - self.buflen):
                    self.buf[self.buflen + i] = 0xFF # ord('-') # erased flash is ff
                if self.verbose: print('.', end='')
                self.part.writeblocks(self.block, self.buf)
                assert len(self.buf) == BLOCKLEN
        

    # finish writing the app to the partition and check the sha
    def _finish(self, check_sha):
        # flush the app buffer and complete the write
        self._app_data(b'', last=False)
        self._app_data(b'', last=True)
        del self.buf
        # check the sha
        calc_sha = binascii.hexlify(self.sha.digest())
        check_sha = check_sha.encode()
        if calc_sha != check_sha:
            raise ValueError("SHA mismatch\n    calc:  {}\n    check: {}".format(calc_sha, check_sha))
        self.part.set_boot()
        if self.verbose: print(' Done.')
    

