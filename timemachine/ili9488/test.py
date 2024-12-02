#
from testlib.ili9488 import Display, color565, color_rgb
from testlib.xglcd_font import XglcdFont
from time import sleep
from machine import Pin, SPI

spi = SPI(1, baudrate=60000000, sck=Pin(12), mosi=Pin(11))
display = Display(spi, dc=Pin(6), cs=Pin(10), rst=Pin(4), rotation=0)
led = Pin(5, Pin.OUT)
led.on()

display.write_cmd(display.INVOFF)
display.fill_rectangle(0, 0, 100, 40, color_rgb(0, 255, 0))
display.fill_rectangle(100, 40, 40, 100, color_rgb(255, 0, 0))

for y in range(100, 140):
    display.draw_hline(255, y, 128, color_rgb(0, 0, 255))

for x in range(200, 240):
    display.draw_vline(x, 128, 128, color_rgb(0, 255, 0))

bally5x8 = XglcdFont("/testlib/fonts/Bally5x8.c", 5, 8)
display.draw_letter(25, 250, "B", bally5x8, color_rgb(255, 0, 0))
display.draw_letter(40, 250, "B", bally5x8, color_rgb(255, 255, 255), landscape=False)
display.draw_text(0, 100, "Bally 5x8 font", bally5x8, color_rgb(255, 255, 255), landscape=False)


display.draw_letter(100, 100, "B", bally5x8, color_rgb(200, 100, 100))
display.draw_text(0, 100, "Built in 8x8", bally5x8, color_rgb(200, 100, 80))


arcade = XglcdFont("/testlib/fonts/ArcadePix9x11.c", 9, 11)
display.draw_letter(200, 200, "B", arcade, color_rgb(200, 100, 100))
display.draw_text(150, 100, "ArcadePix9x11 font", arcade, color_rgb(255, 255, 255), landscape=False)

times = XglcdFont("testlib/fonts/Times_New_Roman28x25.h", 28, 25)
display.draw_letter(200, 200, "B", times, color_rgb(200, 100, 100))
display.draw_text(0, 220, "Times New Roman 28x25. Hooray!!", times, color_rgb(255, 255, 255), landscape=False)


led.off()
sleep(2)
display.clear()
led.on()
