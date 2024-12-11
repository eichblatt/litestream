#
import time
from ili9488 import Display, color565, color_rgb
from time import sleep
from machine import Pin, SPI

import fonts.date_font as datefont
import fonts.DejaVu_33 as deja33
import fonts.NotoSans_18 as pfont

spi = SPI(1, baudrate=60000000, sck=Pin(12), mosi=Pin(11))
led = Pin(5, Pin.OUT)
display = Display(spi, dc=Pin(6), cs=Pin(10), rst=Pin(4), backlight=led, rotation=0)
led.on()


def main():

    display.write_cmd(display.INVOFF)
    display.clear()
    display.fill_rect(0, 0, 100, 40, color_rgb(0, 255, 0))
    display.fill_rect(100, 40, 40, 100, color_rgb(255, 0, 0))

    for y in range(100, 140):
        display.draw_hline(255, y, 128, color_rgb(0, 0, 255))

    for x in range(200, 240):
        display.draw_vline(x, 128, 128, color_rgb(0, 255, 0))

    start_time = time.ticks_ms()
    display.write(pfont, "Noto 18. Hooray!!", 0, 220, color_rgb(255, 255, 255))
    display.write(pfont, pfont.MAP[:30], 0, 120, color_rgb(255, 255, 255))
    display.write(pfont, pfont.MAP[30:60], 0, 150, color_rgb(255, 255, 255))
    display.write(pfont, pfont.MAP[60:], 0, 180, color_rgb(255, 255, 255))
    print(f"Noto18 Hooray Duration: {time.ticks_diff(time.ticks_ms(), start_time)} ms")

    sleep(2)
    display.clear()

    start_time = time.ticks_ms()
    display.write(datefont, datefont.MAP, 0, 180, color_rgb(255, 255, 255))
    display.write(datefont, "05-08-77", 0, 0, color_rgb(255, 255, 55))
    print(f"datefont Duration: {time.ticks_diff(time.ticks_ms(), start_time)} ms")

    sleep(1)
    display.clear()
    start_time = time.ticks_ms()
    display.write(deja33, " 5- 8-77", 0, 0, color_rgb(255, 255, 55))
    date_time = time.ticks_ms()
    print(f" -- Date painting Duration: {time.ticks_diff(date_time, start_time)} ms")
    display.write(pfont, "Barton Hall, Cornell Univ.", 0, 60, color_rgb(255, 255, 55))
    display.write(pfont, "Grateful Dead", 0, 95, color_rgb(255, 255, 55))
    venue_time = time.ticks_ms()
    print(f" -- Venue painting Duration: {time.ticks_diff(venue_time, date_time)} ms")
    display.write(pfont, "Minglewood Blues", 0, 130, color_rgb(0, 158, 255))
    display.write(pfont, "Loser", 0, 130 + 35, color_rgb(0, 158, 255))
    display.write(pfont, "El Paso", 0, 130 + 2 * 35, color_rgb(0, 158, 255))
    display.write(pfont, "They Love Each Other", 0, 130 + 3 * 35, color_rgb(0, 158, 255))
    display.write(datefont, "05-08-1977", 100, 135 + 4 * 35, color_rgb(255, 255, 255))
    display.fill_polygon(3, 420, 290, 20, color_rgb(255, 0, 0))
    print(f" -- Tracklist paint Duration: {time.ticks_diff(time.ticks_ms(), venue_time)} ms")
    print(f"Total screen paint Duration: {time.ticks_diff(time.ticks_ms(), start_time)} ms")


main()
