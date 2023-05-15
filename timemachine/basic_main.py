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
    This script will update main.py if button pressed within 2 seconds.
    """
    tm.tft.fill_rect(0, 0, 160, 128, st7789.BLACK)
    yellow_color = st7789.color565(255, 255, 0)
    red_color = st7789.color565(255, 0, 0)
    tm.tft.write(pfont_large, "Welcome..", 0, 0, red_color)
    tm.tft.write(pfont_med, "Time ", 0, 30, yellow_color)
    tm.tft.write(pfont_med, "Machine", 0, 60, yellow_color)
    tm.tft.write(pfont_med, "Loading", 0, 90, yellow_color)
    
    
    start_time = time.ticks_ms()
    pRewind_old = True
    update_code = False

    while time.ticks_ms() < (start_time + 2000):
        if pRewind_old != tm.pRewind.value():
            pRewind_old = tm.pRewind.value()
            update_code = True
            print(f"{time.ticks_ms()} Rewind button Pressed!!")

    if update_code:
        try:
            copy_file('test_main.py', 'main_bak.py')
        except Exception:
            print("Failed to copy test_main.py to main_bak.py. Not updating!!")
            return  

        print("This means we should update main.py")
        tm.tft.fill_rect(0, 90, 160, 30, st7789.BLACK)
        tm.tft.write(pfont_med, "Updating", 0, 90, yellow_color)
        time.sleep(3)

    if 'test_main' in sys.modules:
        del sys.modules['test_main']


basic_main()

import test_main
try:
    test_main.main()
except Exception:
    print("test_main.py is not running!!")

