# Display driver: https://github.com/russhughes/st7789_mpy
import time
import st7789
import vga1_16x32 as font
from machine import Pin, SPI

#TFA = 0
#BFA = 0

print('Starting...')

def config(rotation=0, buffer_size=0, options=0):
    return st7789.ST7789(
        SPI(1, baudrate=40000000, sck=Pin(12), mosi=Pin(11)),
        128,
        160,
        reset=Pin(4, Pin.OUT),
        cs=Pin(10, Pin.OUT),
        dc=Pin(6, Pin.OUT),
        backlight=Pin(5, Pin.OUT),
        color_order=st7789.RGB,
        inversion=False,
        rotation=rotation,
        options=options,
        buffer_size=buffer_size)

poly = [(-27, -27), (27, 0), (-27, 27), (-123, 0), (-27, -27)]
tft = config(1, buffer_size=64*64*2)   # configure display driver

# init and clear screen
tft.init()
tft.fill(st7789.BLACK)

val_old = 0

while True:
    val_new = val_old + 1
    #tft.fill_polygon(poly, 80, 60, st7789.BLUE, 0.01745329 * val_old * 18 , tft.polygon_center(poly)[0], tft.polygon_center(poly)[1])
    val_old = val_new

    #tft.fill_polygon(poly, 80, 60, st7789.GREEN, 0.01745329 * val_new * 18 , tft.polygon_center(poly)[0], tft.polygon_center(poly)[1])
    tft.text(font, 'Val:' + str(val_new) + ' ', 20, 40, st7789.WHITE, st7789.BLUE)
    #print('result =', val_new)
            
    #time.sleep_ms(100)
