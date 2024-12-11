# Making new TrueType fonts

## use the font2bitmap.py utility to convert it to a bitmap

: ~/st7789_mpy ; python3 utils/font2bitmap.py -c 32-127 fonts/truetype/NotoSans-Regular.ttf 36 > NotoSans_36.py

: ~/st7789_mpy ; python3 utils/font2bitmap.py -c 32-127 /home/steve/projects/deadstream/timemachine/fonts/DejaVuSansMono-Bold.ttf  60 > DejaVu_60.py

### Making the datefont

: ~/st7789_mpy ; #python3 utils/font2bitmap.py -s '0123456789/.- ' /home/steve/projects/deadstream/timemachine/fonts/DejaVuSansMono-Bold.ttf 20  > DejaVu_20.ttf

## Reference

See <https://github.com/russhughes/st7789_mpy>
