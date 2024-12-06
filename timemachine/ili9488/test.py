#
import time
from testlib.ili9488 import Display, color565, color_rgb
from testlib.xglcd_font import XglcdFont
from time import sleep
from machine import Pin, SPI

from testlib import bitmap_font as bmf
import fonts.date_font as datefont
import fonts.DejaVu_33 as deja33
import fonts.NotoSans_18 as pfont

bmf.DEBUG_FONT = False
d33 = bmf.BitmapFont(deja33)
noto18 = bmf.BitmapFont(pfont)
datef = bmf.BitmapFont(datefont)

spi = SPI(1, baudrate=60000000, sck=Pin(12), mosi=Pin(11))
display = Display(spi, dc=Pin(6), cs=Pin(10), rst=Pin(4), rotation=0)
led = Pin(5, Pin.OUT)
led.on()


def main():

    display.write_cmd(display.INVOFF)
    display.clear()
    display.fill_rectangle(0, 0, 100, 40, color_rgb(0, 255, 0))
    display.fill_rectangle(100, 40, 40, 100, color_rgb(255, 0, 0))

    for y in range(100, 140):
        display.draw_hline(255, y, 128, color_rgb(0, 0, 255))

    for x in range(200, 240):
        display.draw_vline(x, 128, 128, color_rgb(0, 255, 0))

    start_time = time.ticks_ms()
    bally5x8 = XglcdFont("/testlib/fonts/Bally5x8.c", 5, 8)
    display.draw_letter(25, 250, "B", bally5x8, color_rgb(255, 0, 0))
    display.draw_letter(40, 250, "B", bally5x8, color_rgb(255, 255, 255), landscape=False)
    display.draw_text(0, 100, "Bally 5x8 font", bally5x8, color_rgb(255, 255, 255), landscape=False)
    display.draw_text(
        0, 140, "Bally 5x8 font, scaled by 2", bally5x8, color_rgb(255, 255, 255), landscape=False, scale_factor=2
    )

    arcade = XglcdFont("/testlib/fonts/ArcadePix9x11.c", 9, 11)
    display.draw_letter(200, 200, "B", arcade, color_rgb(200, 100, 100))
    display.draw_text(150, 100, "ArcadePix9x11 font", arcade, color_rgb(255, 255, 255), landscape=False)

    times = XglcdFont("testlib/fonts/Times_New_Roman28x25.h", 28, 25)
    display.draw_letter(200, 200, "B", times, color_rgb(200, 100, 100))
    display.draw_text(0, 220, "Times New Roman 28x25. Hooray!!", times, color_rgb(255, 255, 255), landscape=False)

    print(f"Bally Arcade Times Duration: {time.ticks_diff(time.ticks_ms(), start_time)} ms")
    sleep(2)
    led.off()
    display.clear()
    led.on()
    noto18.get_letter("r", color_rgb(250, 250, 0))
    start_time = time.ticks_ms()
    display.draw_letter(200, 200, "r", noto18, color_rgb(200, 100, 100))
    display.draw_text(0, 220, "Noto 18. Hooray!!", noto18, color_rgb(255, 255, 255))
    display.draw_text(0, 120, noto18.font.MAP[:30], noto18, color_rgb(255, 255, 255))
    display.draw_text(0, 150, noto18.font.MAP[30:60], noto18, color_rgb(255, 255, 255))
    display.draw_text(0, 180, noto18.font.MAP[60:], noto18, color_rgb(255, 255, 255))
    print(f"Noto18 Hooray Duration: {time.ticks_diff(time.ticks_ms(), start_time)} ms")

    sleep(2)
    display.clear()

    start_time = time.ticks_ms()
    display.draw_text(0, 120, datef.font.MAP, datef, color_rgb(255, 255, 255))
    display.draw_text(0, 0, "05-08-77", datef, color_rgb(255, 255, 55))
    print(f"datefont Duration: {time.ticks_diff(time.ticks_ms(), start_time)} ms")

    sleep(1)
    display.clear()

    start_time = time.ticks_ms()
    display.draw_text(0, 120, datef.font.MAP, datef, color_rgb(255, 255, 255))
    display.draw_text(0, 0, "05-08-77", datef, color_rgb(255, 255, 55), scale_factor=4)
    print(f"datefont scale4 Duration: {time.ticks_diff(time.ticks_ms(), start_time)} ms")

    sleep(1)

    display.clear()
    start_time = time.ticks_ms()
    display.draw_text(0, 0, d33.font.MAP[:20], d33, color_rgb(255, 255, 255))
    display.draw_text(0, 40, d33.font.MAP[20:40], d33, color_rgb(255, 255, 255))
    display.draw_text(0, 80, d33.font.MAP[40:60], d33, color_rgb(255, 255, 255))
    display.draw_text(0, 120, d33.font.MAP[60:80], d33, color_rgb(255, 255, 255))
    display.draw_text(0, 160, d33.font.MAP[80:], d33, color_rgb(255, 255, 255))
    print(f"d33 Duration: {time.ticks_diff(time.ticks_ms(), start_time)} ms")

    sleep(2)
    display.clear()
    start_time = time.ticks_ms()
    display.draw_text(0, 0, " 5- 8-77", d33, color_rgb(255, 255, 55))
    date_time = time.ticks_ms()
    print(f" -- Date painting Duration: {time.ticks_diff(date_time, start_time)} ms")
    display.draw_text(0, 60, "Barton Hall, Cornell Univ.", noto18, color_rgb(255, 255, 55))
    display.draw_text(0, 95, "Grateful Dead", noto18, color_rgb(255, 255, 55))
    venue_time = time.ticks_ms()
    print(f" -- Venue painting Duration: {time.ticks_diff(venue_time, date_time)} ms")
    display.draw_text(0, 130, "Minglewood Blues", noto18, color_rgb(0, 158, 255))
    display.draw_text(0, 130 + 35, "Loser", noto18, color_rgb(0, 158, 255))
    display.draw_text(0, 130 + 2 * 35, "El Paso", noto18, color_rgb(0, 158, 255))
    display.draw_text(0, 130 + 3 * 35, "They Love Each Other", noto18, color_rgb(0, 158, 255))
    display.draw_text(100, 135 + 4 * 35, "05-08-1977", datef, color_rgb(255, 255, 255))
    display.fill_polygon(3, 420, 290, 20, color_rgb(255, 0, 0))
    print(f" -- Tracklist paint Duration: {time.ticks_diff(time.ticks_ms(), venue_time)} ms")
    print(f"Total screen paint Duration: {time.ticks_diff(time.ticks_ms(), start_time)} ms")

    sleep(2)
    display.clear()
    start_time = time.ticks_ms()
    display.draw_text(0, 0, " 5- 8-77", d33, color_rgb(255, 255, 55), scale_factor=2)
    date_time = time.ticks_ms()
    print(f" -- Date painting Duration: {time.ticks_diff(date_time, start_time)} ms")
    display.draw_text(0, 60, "Barton Hall, Cornell Univ.", noto18, color_rgb(255, 255, 55), scale_factor=2)
    display.draw_text(0, 95, "Grateful Dead", noto18, color_rgb(255, 255, 55), scale_factor=2)
    venue_time = time.ticks_ms()
    print(f" -- Venue painting Duration: {time.ticks_diff(venue_time, date_time)} ms")
    display.draw_text(0, 130, "Minglewood Blues", noto18, color_rgb(0, 158, 255), scale_factor=2)
    display.draw_text(0, 130 + 35, "Loser", noto18, color_rgb(0, 158, 255), scale_factor=2)
    display.draw_text(0, 130 + 2 * 35, "El Paso", noto18, color_rgb(0, 158, 255), scale_factor=2)
    display.draw_text(0, 130 + 3 * 35, "They Love Each Other", noto18, color_rgb(0, 158, 255), scale_factor=2)
    display.draw_text(100, 135 + 4 * 35, "05-08-1977", datef, color_rgb(255, 255, 255), scale_factor=2)
    display.fill_polygon(3, 420, 290, 20, color_rgb(255, 0, 0))
    print(f" -- Tracklist paint Duration: {time.ticks_diff(time.ticks_ms(), venue_time)} ms")
    print(f"Scaled screen paint Duration: {time.ticks_diff(time.ticks_ms(), start_time)} ms")


main()
