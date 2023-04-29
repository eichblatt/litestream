# Making new TrueType fonts

## Create a string of characters

: ~/projects/litestream ; string=" \!\"#\$%&\'()*+,-./0123456789:;<=>?@ABCDEFGHIJKLMNOPQRSTUVWXYZ[\\]^_\`abcdefghijklmnopqrstuvwxyz{|}~ "

## use the font2bitmap.py utility to convert it to a bitmap

: ~/projects/litestream ; python3 font2bitmap.py -s $string NotoSans-Regular.ttf 6 > NotoSans_6.py
