# Making new TrueType fonts

## use the font2bitmap.py utility to convert it to a bitmap

: (myenv) ~/st7789_mpy ; python3 utils/font2bitmap.py -c 32-127 fonts/truetype/NotoSans-Regular.ttf 36 > NotoSans_36.py

: (myenv) ~/st7789_mpy ; python3 utils/font2bitmap.py -c 32-127 /home/steve/projects/deadstream/timemachine/fonts/DejaVuSansMono-Bold.ttf  60 > DejaVu_60.py

### Making fonts with accents

*: (myenv)  ~/st7789_mpy ; python3 utils/font2bitmap.py -c 32-127,201,225,228,231,232,233,235,237,242,243,246,252,255,269,345,353,366,367,8242 fonts/truetype/NotoSans-Regular.ttf 18 > NotoSans_18.py*
*Note: This is the complete list of characters in the names of Classical composers. We may need more characters at some point.*
This makes the accents, excepting capital letters with accents, which make the font significantly taller.
: (myenv)  ~/st7789_mpy ; python3 utils/font2bitmap.py -c 32-127,225,228,231,232,233,235,237,242,243,246,252,255,269,345,353,8242 fonts/truetype/NotoSans-Regular.ttf 18 > NotoSans_18.py

### Making the datefont

: (myenv) ~/st7789_mpy ; #python3 utils/font2bitmap.py -s '0123456789/.- ' /home/steve/projects/deadstream/timemachine/fonts/DejaVuSansMono-Bold.ttf 20  > DejaVu_20.ttf

## Reference

See <https://github.com/russhughes/st7789_mpy>
