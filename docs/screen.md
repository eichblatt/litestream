# Larger Screen

## Intro

A customer is seeking a special time machine with a larger screen for a custom installation. How doable is this?

## Description

The current screen is a 1.8" TFT (thin film transistor) LED screen driven with SPI (serial port interface). The library that drives the current screen is st7789, compiled from C, which makes it somewhat faster than it might be. The Raspberry Pi screen driver is noticably slower, and I had to do various tricks to make it go faster.

## Candidate Screens

### 3.5 inch screen

I ordered one of these from Amazon: <https://www.amazon.com/gp/product/B08C7NPQZR>

Mike pointed me to this Micropython driver for this screen <https://github.com/QiaoTuCodes/MicroPython-_ILI9488/tree/main> which might be easy enough to get going.

Datasheet here <https://www.hpinfotech.ro/ILI9488.pdf>

I am able to illuminate the screen, and draw filled rectangles which are not the correct size. 

This package also might be useful, but it's in C++ <https://github.com/Bodmer/TFT_eSPI>

Maybe I should migrate to the Raspberry Pi, which may have more advanced drivers for this screen.

I have it working now, except for the fonts. I have downloaded a larger font here <https://os.mbed.com/users/star297/code/Fonts//file/b7905075b31a/TimesNR28x25.h/> but it is not putting the pixels in the correct order, so it's coming out all jumbled.
See page 192 of the datasheet <https://www.hpinfotech.ro/ILI9488.pdf> for information about the pixel ordering.

### A 5 inch screen

There is a much larger SPI-driven screen:
<https://www.crystalfontz.com/product/cfa800480e3050sn-800x480-5-inch-eve-tft> but it costs $87, and I think that it would be a huge project just to figure out how to talk to it.

### Current Screen Pins

The code to set up the screen is in board.py

```{}
from machine import SPI,Pin

# Set up pins

def conf_screen(rotation=0, buffer_size=0, options=0):
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
        buffer_size=buffer_size,
    )
```

So it looks like the screen is using pins:

| Pin  | label |
| -----| ------|
| 4 | reset |
| 5 | light |
| 6 | dc |
| 10 | cs |
| 11  | mosi |
| 12  | sck |

### Decoder Pins

On the decoder chip, the pins are labelled:

| label | correpsondence |
| -- | - |
| MISO | ? |
| MOSI | screen: mosi |
| SCK | DAC: sck |
| DREQ | ? |
| XRST | screen: reset |
| XCS |  screen: cs |
| XDCS | screen: dc ? |
