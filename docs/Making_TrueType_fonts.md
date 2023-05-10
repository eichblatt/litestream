# Making new TrueType fonts

## use the font2bitmap.py utility to convert it to a bitmap

: ~/projects/litestream/utils ; python3 font2bitmap.py -c 32-127 NotoSans-Regular.ttf 6 > NotoSans_6.py

# Reference
See https://github.com/russhughes/st7789_mpy