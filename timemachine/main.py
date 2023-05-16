import sys
import time

import machine
import st7789
import fonts.DejaVu_20x as date_font
import fonts.DejaVu_33 as large_font
import fonts.NotoSans_18 as pfont_small
import fonts.NotoSans_24 as pfont_med
import fonts.NotoSans_32 as pfont_large
import fonts.romanc as roman_font
import fonts.romant as romant_font
from machine import SPI, Pin
from mrequests import mrequests as requests
from rotary_irq_esp import RotaryIRQ
import network

import board as tm

def copy_file(src, dest):
    print(f"Copying {src} to {dest}")
    f_in = open(src,'r')
    f_out = open(dest,'w')
    for line in f_in.readlines():
        f_out.write(line)
    f_in.close()
    f_out.close()
    
def basic_main():
    """
    This script will update livemusic.py if rewind button pressed within 2 seconds.
    """
    tm.tft.fill_rect(0, 0, 160, 128, st7789.BLACK)
    yellow_color = st7789.color565(255, 255, 0)
    red_color = st7789.color565(255, 0, 0)
    tm.tft.write(pfont_large, "Welcome..", 0, 0, red_color)
    tm.tft.write(pfont_med, "Time ", 0, 30, yellow_color)
    tm.tft.write(pfont_med, "Machine", 0, 60, yellow_color)
    tm.tft.write(pfont_med, "Loading", 0, 90, yellow_color)

    git_code_url = "https://raw.githubusercontent.com/eichblatt/litestream/main/timemachine/livemusic.py?token=GHSAT0AAAAAACBAKSJDFAR5ATJ7TPHAXRCOZDC2KGA"
    
    start_time = time.ticks_ms()
    pRewind_old = True
    pSelect_old = True
    pStop_old = True
    update_code = False

    while time.ticks_ms() < (start_time + 3000):

        if pSelect_old != tm.pSelect.value():
            pSelect_old = tm.pSelect.value()
            update_code = True
            print(f"{time.ticks_ms()} Select button Pressed!!")
            break

        if pStop_old != tm.pStop.value():
            pStop_old = tm.pStop.value()
            print(f"{time.ticks_ms()} Stop button Pressed -- bailing!!")
            return

        if pRewind_old != tm.pRewind.value():
            pRewind_old = tm.pRewind.value()
            update_code = True
            print(f"{time.ticks_ms()} Rewind button Pressed!!")
            break

    if update_code:
        try:
            copy_file('livemusic.py', 'livemusic_bak.py')
        except Exception:
            print("Failed to copy livemusic.py to livemusic_bak.py. Not updating!!")
            return  

        try:
            resp = requests.get(git_code_url)
            if resp.status_code != 200:
                raise Exception("Error downloading file")
            f_out = open('livemusic.py','w')
            for line in resp.text.split('\n'):
                f_out.write(line)
            f_out.close()
            print("livemusic.py written")
            
        except Exception:
            print("Failed to download livemusic.py Not updating!!")
            return
            

        print("This means we should update livemusic.py")
        tm.tft.fill_rect(0, 90, 160, 30, st7789.BLACK)
        tm.tft.write(pfont_med, "Updating", 0, 90, yellow_color)
        time.sleep(3)

    if 'livemusic' in sys.modules:
        del sys.modules['livemusic']


basic_main()

import livemusic as livemusic
try:
    livemusic.main()
except Exception:
    print("livemusic.py is not running!!")

