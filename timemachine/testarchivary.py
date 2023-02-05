import os
import psutil
import sys
import time
import pympler
from pympler import summary
from pympler import muppy

# from threading import Event

process = psutil.Process(os.getpid())
print(f"Init: {process.memory_info()}")

from timemachine import Archivary
from timemachine import config

# from timemachine import GD

# track_event = Event()

config.optd = {
    "COLLECTIONS": ["GratefulDead", "Phish", "PhilLeshandFriends", "TedeschiTrucksBand", "DeadAndCompany"],
    "FAVORED_TAPER": "miller",
    "PLAY_LOSSLESS": "false",
}
print(f"Before: {process.memory_info()}")

aa = Archivary.Archivary(collection_list=config.optd["COLLECTIONS"])

print(f"After: {process.memory_info()}")

allObjects = muppy.get_objects()
sum = summary.summarize(allObjects)
summary.print_(sum)


config.optd = {"COLLECTIONS": ["georgeblood"], "FAVORED_TAPER": "miller", "PLAY_LOSSLESS": "false"}
aa = Archivary.Archivary(collection_list=config.optd["COLLECTIONS"], date_range=[1930, 1935])

config.optd = {"COLLECTIONS": ["Phish"], "FAVORED_TAPER": "miller", "PLAY_LOSSLESS": "false"}
aa = Archivary.Archivary(collection_list=config.optd["COLLECTIONS"])

print(f"tape dates on 1995-07-02 are {aa.tape_dates['1995-07-02']}")

tape = aa.best_tape("1992-05-05")
tape = aa.best_tape("1996-11-18")

allObjects = muppy.get_objects()
sum = summary.summarize(allObjects)
summary.print_(sum)
