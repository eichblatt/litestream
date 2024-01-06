# Pin Assignments For VS1053

## List

|ESP 32 (GPIO) | VS1053 | comments |
| -  | -        | -    |
| 3V3 | 5V | |
| GND | DGND | |
| 0 | XDCS | |
| 11 | MOSI | |
| 12 | SCK | |
| 13 | MISO | |
| 14 | DREQ | |
| 17 | XCS | |
| 45 | RESET | |

## Big List

|Pin (GPIO) | component | Function | comments |
| -  | -        | - |  -       |
| 0 | VS1053 | XDCS | |
| 1 | button | ffwd |
| 2 | button | playPause |
| 4 | screen | reset | |
| 5 | screen | backlight |
| 6 | screen | dc | power? |
| 7 | knob | day |
| 8 | knob | day |
| 9 | button | day | | 41 | button | year |
| 10 | screen | cs | |
| 11 | PCI | MOSI | |
| 12  | PCI | SCK | screen/vs1053 |
| 13 | I2S/PCI | SCK/MISO | DAC/vs1053 |
| 14 | I2S/PCI | ws/DREQ | | DAC/vs1053 |
| 15 | button | stop |
| 16 | button | rewind |
| 17 | I2S/VS1053 | sd/CS | DAC/VS1053 |
| 18 | knob | month|
| 19? | | | Can I use this?|
| 20? | | | Can I use this?|
| 21 | button | power |
| 35 | unused | **INVALID**| internal SPI |
| 36 | unused | **INVALID**| internal SPI |
| 37 | unused | **INVALID**| internal SPI |
| 38 | button | month |
| 39 | knob | month|
| 40 | knob | year |
| 41 | unused | |
| 42 | knob | year |
| 43 | unused | UART TX|
| 44 | unused | UART RX|
| 45 | VS1053 | reset |
| 46 | unused | |
| 47 | button | select |
| 48 | button | led |  |

See <https://docs.espressif.com/projects/esp-idf/en/latest/esp32s3/hw-reference/esp32s3/user-guide-devkitc-1.html>

## From <https://docs.micropython.org/en/latest/esp32/quickref.html#pins-and-gpio>

Available Pins are from the following ranges (inclusive): 0-19, 21-23, 25-27, 32-39. These correspond to the actual GPIO pin numbers of ESP32 chip.

Notes:

Pins 1 and 3 are REPL UART TX and RX respectively

Pins 6, 7, 8, 11, 16, and 17 are used for connecting the embedded flash, and are not recommended for other uses

Pins 34-39 are input only, and also do not have internal pull-up resistors

See Deep-sleep mode for a discussion of pin behaviour during sleep

## And <https://docs.micropython.org/en/latest/esp32/quickref.html#hardware-spi-bus>

| | HSPI (id=1)| SPI (id=2)|
| - | - | - |
|sck | 14 | 18 |
| mosi | 13 | 23|
| miso | 12 | 19|

Hardware SPI is accessed via the machine.SPI class and has the same methods as software SPI above
