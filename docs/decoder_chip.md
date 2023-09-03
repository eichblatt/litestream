# Decoder Chip VS1053

## Intro
While Mike is in Europe, I would like to test the viability of using the VS1053 decoder chip, which claims that it can decode ogg, flac, and mp3 files. 

The VS1053 can output the digital WAV signal, as well as the analog sound. 

The advantages of using the chip would be:
 - More responsive to the knobs and buttons while playing.
 - Reduced memory usage in the ESP32.

The disadvantages to using a decoder chip are:
 - May not have gapless playback capability
 - If it cannot decode a track, we have no recourse.
 - Work required to decode other than mp3 format.
 - Slightly more expensive

## Notes from Mike

- You need to install a patch to the chip in order to make it decode ogg, which is hard to do.
- I think you will still need at least an input ring buffer to guard against WiFi glitches/slowness.
- The decoder chip runs from SPI, same as the screen.
- So basically the same code but instead of calling the single line in the current player that calls the C decode function, you would send it to SPI. And no need for the playback loop.
- Try and use the same pins as we are using for the DAC. I think you can assign SPI to any pins
- I hope that gapless works as we have no opportunity to buffer the output

## Internet Radio Projects
Although most, if not all, internet radio projects here use Arduino, they may be useful. 
See these links:
 - https://github.com/baldram/ESP_VS1053_Library

## Pins
### DAC Pins
The python code to set up and send data to the DAC via I2S is from audioPlayer.py

```
from machine import Pin, I2S

sck_pin = Pin(13)  # Serial clock output
ws_pin = Pin(14)  # Word clock output
sd_pin = Pin(17)  # Serial data output


    self.audio_out = I2S(
        0,
        sck=sck_pin,
        ws=ws_pin,
        sd=sd_pin,
        mode=I2S.TX,
        bits=bits_per_sample,
        format=I2S.STEREO if channels == 2 else I2S.MONO,
        rate=sample_rate,
        ibuf=self.ChunkSize,
    )
```

So it appears that the Dac is using pins

| Pin | label | 
| --  | ---- |
| 13 | sck |
| 14 | ws | 
| 17 | sd | 


### Screen Pins
The code to set up the screen in isn board.py

```
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