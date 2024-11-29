from testlib.ili9488 import Display, color565, color666
from testlib.xglcd_font import XglcdFont
from time import sleep
from machine import Pin, SPI

spi = SPI(1, baudrate=60000000, sck=Pin(12), mosi=Pin(11))
display = Display(spi, dc=Pin(6), cs=Pin(10), rst=Pin(4), rotation=0)
d = display
led = Pin(5, Pin.OUT)

display.fill_rectangle(0, 0, 100, 40, color666(255, 0, 255))
display.fill_rectangle(100, 40, 40, 100, color666(0, 255, 255))

for y in range(100, 140):
    display.draw_hline(255, y, 128, color666(255, 255, 0))

for x in range(200, 240):
    display.draw_vline(x, 128, 128, color666(255, 0, 255))

display.fill_circle(100, 200, 30, color666(128, 0, 128))
sleep(10)

display.clear()


bally = XglcdFont("/testlib/fonts/Bally5x8.c", 5, 8)
import random

for i in range(0, 60):
    display.draw_text8x8(
        random.randint(0, 440),
        random.randint(0, 309),
        "Built in 8x8",
        color565(200, 100, 80),
        background=color565(255, 255, 255),
    )
    print("writing 8x8 text")
sleep(5)
led.off()
sleep(2)
display.clear()
led.on()
