#
from testlib.ili9488 import Display, color565, color666
from testlib.xglcd_font import XglcdFont
from time import sleep
from machine import Pin, SPI

spi = SPI(1, baudrate=60000000, sck=Pin(12), mosi=Pin(11))
display = Display(spi, dc=Pin(6), cs=Pin(10), rst=Pin(4), rotation=0)
d = display
led = Pin(5, Pin.OUT)

display.write_cmd(display.INVOFF)
display.fill_rectangle(0, 0, 100, 40, color666(0, 255, 0))
display.fill_rectangle(100, 40, 40, 100, color666(255, 0, 0))

for y in range(100, 140):
    display.draw_hline(255, y, 128, color666(0, 0, 255))

for x in range(200, 240):
    display.draw_vline(x, 128, 128, color666(0, 255, 0))

bally5x8 = XglcdFont("/testlib/fonts/Bally5x8.c", 5, 8)
display.draw_letter(25, 250, "B", bally5x8, color666(255, 0, 0))
display.draw_letter(40, 250, "B", bally5x8, color666(255, 255, 255), landscape=False)
display.draw_text(0, 100, "Built in 8x8", bally5x8, color666(255, 255, 255), landscape=False)


display.draw_letter(100, 100, "B", bally5x8, color666(200, 100, 100))
display.draw_text(0, 100, "Built in 8x8", bally5x8, color666(200, 100, 80))

arcade = XglcdFont("/testlib/fonts/ArcadePix9x11.c", 9, 11)
display.draw_letter(200, 200, "B", arcade, color666(200, 100, 100))

times = XglcdFont("testlib/fonts/Times_New_Roman28x25.h", 28, 25)
display.draw_letter(200, 200, "B", times, color666(200, 100, 100))


led.off()
sleep(2)
display.clear()
led.on()


def clear565(display, color=color565(0, 0, 0)):
    w = display.width
    h = display.height
    # Clear display in 1024 byte blocks
    if color:
        line = color.to_bytes(2, "big") * (w * 8)
    else:
        line = bytearray(w * 18)
    for y in range(0, h, 8):
        display.block(0, y, w - 1, y + 7, line)
