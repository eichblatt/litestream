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

- <https://github.com/baldram/ESP_VS1053_Library>

## Pins

### DAC Pins

The python code to set up and send data to the DAC via I2S is from audioPlayer.py

```{}
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

### Examples

#### Arduino

##### Baldram

In the project <https://github.com/baldram/ESP_VS1053_Library/tree/master> he has defined the pins to be

```{}
#ifdef ARDUINO_ARCH_ESP32
#define VS1053_CS     5
#define VS1053_DCS    16
#define VS1053_DREQ   4

VS1053 player(VS1053_CS, VS1053_DCS, VS1053_DREQ);
```

##### mengguang

This repo appears to work with the 1003, rather than the 1053.
<https://github.com/mengguang/ESPVS1003>

This picture of his setup <https://user-images.githubusercontent.com/16861531/27875071-3ead1674-61b2-11e7-9a69-02edafa7b286.jpg> uses the ESP8266, But this table shows the mapping to the ESP32

  The circuit (example wiring for ESP8266 based board like eg. LoLin NodeMCU V3):
  | VS1053  | ESP8266 |  ESP32   |
  | ------  | ------- |  -----   |
  |   SCK   |   D5    |   IO18   |
  |   MISO  |   D6    |   IO19   |
  |   MOSI  |   D7    |   IO23   |
  |   XRST  |   RST   |   EN     |
  |   CS    |   D1    |   IO5    |
  |   DCS   |   D0    |   IO16   |
  |   DREQ  |   D3    |   IO4    |
  |   5V    |   5V    |   5V     |
  |   GND   |   GND   |   GND    |

#### Micropython

This project looks interesting, and it's in Micropython
<https://github.com/peterhinch/micropython-vs1053/tree/master>
or
<https://github.com/peterhinch/micropython-vs1053/blob/master/synchronous/esp32audio.py>

I have cloned this repo into my ~/projects/micropython-vs1053 folder

Note: This was apparently based on the VS1053, and I have a VS1003B/VS1053 (The chip is actually marked as VS1003B, but the board says VS1003/VS1053 -- I suspect it is *not* going to work as a vs1053).
For a breakout board of a VS1053, see <https://www.adafruit.com/product/1381>

##### Asyncronous

There is an asyncronous version which apparently doesn't work on the ESP32:
See <https://github.com/peterhinch/micropython-vs1053/blob/master/ASYNC.md>

From section 6.1, `Test Results`, we see:

The ESP32, even at 240MHz, failed properly to decode any file. I suspect this is a consequence of the underlying OS stealing processor timeslices.

##### Syncronous

<https://github.com/peterhinch/micropython-vs1053/blob/master/SYNCHRONOUS.md>

Section 7, `Plugins` describes how to install the plugin for flac, and probably ogg.
Based on what I read <http://www.vlsi.fi/en/support/software/vs10xxpatches.html>, the VS1053 should already decode ogg.

Key passages from the syncronous version:

```{}
from machine import SPI, Pin, freq


spi = SPI(2, sck=Pin(18), mosi=Pin(23), miso=Pin(19))
reset = Pin(32, Pin.OUT, value=1)  # Active low hardware reset
xcs = Pin(33, Pin.OUT, value=1)  # Labelled CS on PCB, xcs on chip datasheet
sdcs = Pin(25, Pin.OUT, value=1)  # SD card CS
xdcs = Pin(26, Pin.OUT, value=1)  # Data chip select xdcs in datasheet
dreq = Pin(27, Pin.IN)  # Active high data request
player = VS1053(spi, reset, dreq, xdcs, xcs, sdcs, '/fc')
```

Where the player is in the `vs1053_syn.py` file

```{}
class VS1053:


    def __init__(self, spi, reset, dreq, xdcs, xcs, sdcs=None, mp=None, cancb=lambda : False):
        self._reset = reset
        self._dreq = dreq  # Data request
        self._xdcs = xdcs  # Data CS
        self._xcs = xcs  # Register CS
        self._mp = mp
        self._spi = spi
        self._cbuf = bytearray(4)  # Command buffer
        self._cancb = cancb  # Cancellation callback
        self._slow_spi = True  # Start on low baudrate
        self._overrun = 0  # Recording
        self.reset()
        if ((sdcs is not None) and (mp is not None)):
            import sdcard
            import os
            sd = sdcard.SDCard(spi, sdcs)
            vfs = os.VfsFat(sd)
            os.mount(vfs, mp)
        self._spi.init(baudrate=_DATA_BAUDRATE)

 ...

    def write(self, buf):
        while not self._dreq():  # minimise for speed
            pass
        self._xdcs(0)
        self._spi.write(buf)
        self._xdcs(1)
        return len(buf)

 ... 

    @micropython.native
    def play(self, s, buf = bytearray(32)):
        cancb = self._cancb
        cancnt = 0
        cnt = 0
        dreq = self._dreq
        while s.readinto(buf):  # Read <=32 bytes
            cnt += 1
            # When running, dreq goes True when on-chip buffer can hold about 640 bytes.
            # At 128Kbps this will take 40ms - at higher rates, less. Call the cancel
            # callback during waiting periods or after 960 bytes if dreq never goes False.
            # This is a fault condition where the VS1053 wants data faster than we can
            # provide it. 
            while (not dreq()) or cnt > 30:  # 960 byte backstop
                cnt = 0
                if cancnt == 0 and cancb():  # Not cancelling. Check callback when waiting on dreq.
                    cancnt = 1  # Send at least one more buffer
            self._xdcs(0)  # Fast write
            self._spi.write(buf)
            self._xdcs(1)
            # cancnt > 0: Cancelling
            if cancnt:
                if cancnt == 1:  # Just cancelled
                    self.mode_set(_SM_CANCEL)
                if not self.mode() & _SM_CANCEL:  # Cancel done
                    efb = self._read_ram(_END_FILL_BYTE) & 0xff
                    for n in range(len(buf)):
                        buf[n] = efb
                    for n in range(64):  # send 2048 bytes of end fill byte
                        self.write(buf)
                    self.write(buf[:4])  # Take to 2052 bytes
                    if self._read_reg(_SCI_HDAT0) or self._read_reg(_SCI_HDAT1):
                        raise RuntimeError('Invalid HDAT value.')
                    break
                if cancnt > 64:  # Cancel has failed
                    self.soft_reset()
                    break
                cancnt += 1  # keep feeding data from stream
        else:
            self._end_play(buf)

    def _write_reg(self, addr, value):  # Datasheet 7.4
        self._wait_ready()
        self._spi.init(baudrate = _INITIAL_BAUDRATE if self._slow_spi else _SCI_BAUDRATE)
        b = self._cbuf
        b[0] = 2  # WRITE
        b[1] = addr & 0xff
        b[2] = (value >> 8) & 0xff
        b[3] = value & 0xff
        self._xcs(0)
        self._spi.write(b)
        self._xcs(1)
        self._spi.init(baudrate=_DATA_BAUDRATE)
 ...
 
    def reset(self):  # Issue hardware reset to VS1053
        self._xcs(1)
        self._xdcs(1)
        self._reset(0)
        time.sleep_ms(20)
        self._reset(1)
        time.sleep_ms(20)
        self.soft_reset()

    def soft_reset(self):
        self._slow_spi = True  # Use _INITIAL_BAUDRATE
        self.mode_set(_SM_RESET)
        # This has many interesting settings data P39
        time.sleep_ms(20)  # Adafruit have a total of 200ms
        while not self._dreq():
            pass
        # Data P42. P7 footnote 4 recommends xtal * 3.5 + 1: using that.
        self._write_reg(_SCI_CLOCKF, 0x8800)
        if self._read_reg(_SCI_CLOCKF) != 0x8800:
            raise OSError('No VS1053 device found.')
        time.sleep_ms(1)  # Clock setting can take 100us
        # Datasheet suggests writing to SPI_BASS. 
        self._write_reg(_SCI_BASS, 0)  # 0 is flat response
        self.volume(0, 0)
        while not self._dreq():
            pass
        self._slow_spi = False

    # Range is 0 to -63.5 dB
    def volume(self, left, right, powerdown=False):
        bits = [0, 0]
        obits = 0xffff  # powerdown
        if not powerdown:
            for n, l in enumerate((left, right)):
                bits[n] = round(min(max(2 * -l, 0), 127))
            obits = bits[0] << 8 | bits[1]
        self._write_reg(_SCI_VOL, obits)

```

This source <https://github.com/adafruit/Adafruit_CircuitPython_VS1053> despairs that the micropython can't keep up. I don't think this is true for us, though, because we are currently doing even more than this.

#### CircuitPython

A similar variant of python, this project looks simple enough <https://github.com/urish/vs1053-circuitpython>

## 2023-09-12

## Installed Micropython on the device

## 2023-09-19

I got it working!! I had to solder together pins 33 and 34 on the VS1053 chip to get it out of MIDI mode. Argh!!

It plays ogg, but it only played track 1 (not track 2) from 8/13/75. That could mean that this was a waste of time, but I want to spend a little time to see if I can get that working.
