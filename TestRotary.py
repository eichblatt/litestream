# Display driver: https://github.com/russhughes/st7789_mpy
import time
from rotary_irq_esp import RotaryIRQ

import st7789
import tft_config
import vga1_16x32 as font

poly = [(-27, -27), (27, 0), (-27, 27), (-123, 0), (-27, -27)]

tft = tft_config.config(1, buffer_size=64*62*2)   # configure display driver

# init and clear screen
tft.init()
tft.fill(st7789.BLACK)

r = RotaryIRQ(2, 4, min_val=0, max_val=10, reverse=False, range_mode=RotaryIRQ.RANGE_UNBOUNDED, pull_up=True, half_step=False)

print('Starting ')

val_old = r.value()
while True:
    val_new = r.value()
    
    if val_old != val_new:
        tft.fill_polygon(poly, 80, 60, st7789.BLUE, 0.01745329 * val_old * 18 , tft.polygon_center(poly)[0], tft.polygon_center(poly)[1])
        val_old = val_new
        tft.text(font, str(val_new) + ' ', 60, 40, st7789.WHITE, st7789.BLUE)
        tft.fill_polygon(poly, 80, 60, st7789.GREEN, 0.01745329 * val_new * 18 , tft.polygon_center(poly)[0], tft.polygon_center(poly)[1])
        print('result =', val_new)
                
    time.sleep_ms(50)