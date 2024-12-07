"""XGLCD Font Utility."""

from math import ceil, floor

DEBUG_FONT = False


class BitmapFont(object):
    """Font data in bitmap format.
    Attributes:
        letters: A bytearray of letters (columns consist of bytes)
        width: Maximum pixel width of font
        height: Pixel height of font
        start_letter: ASCII number of first letter
        height_bytes: How many bytes comprises letter height
    Note:
        Font files can be generated with the free version of MikroElektronika
        GLCD Font Creator:  www.mikroe.com/glcd-font-creator
        The font file must be in X-GLCD 'C' format.
        To save text files from this font creator program in Win7 or higher
        you must use XP compatibility mode or you can just use the clipboard.
    """

    # Dict to tranlate bitwise values to byte position
    # BIT_POS = {1: 0, 2: 2, 4: 4, 8: 6, 16: 8, 32: 10, 64: 12, 128: 14, 256: 16}
    BIT_POS = {1: 0, 2: 1, 4: 2, 8: 3, 16: 4, 32: 5, 64: 6, 128: 7, 256: 8}

    def __init__(self, font):
        """Constructor for bitmap Font object.
        Args:
            font (module): a python module loaded (eg. NotoSans_18.py)
        """
        self.font = font
        self.charind = {k: i for i, k in enumerate(font.MAP)}
        self.offset_dict = self.get_offset_dict()  # integer number of bytes offset, indexed by letter
        self.width_dict = self.get_width_dict()  # integer width (bits), indexed by letter
        self.litbit_dict = {}

    def get_offset_dict(self):
        offwid = self.font.OFFSET_WIDTH
        offset_dict = {}
        for letter in self.font.MAP:
            ind = self.charind[letter]
            offset = int.from_bytes(self.font._OFFSETS[ind * offwid : (ind + 1) * offwid])  # starting bit in the _BITMAPS data
            offset_dict[letter] = offset
        return offset_dict

    def get_width_dict(self):
        # build a dictionary with keys = letters, values = width in bits.
        width_dict = {letter: self.font._WIDTHS[self.charind[letter]] for letter in self.font.MAP}
        return width_dict

    def lit_bits(self, n, bit_spacing=2):
        """Return positions of 1 bits only."""
        while n:
            b = n & (~n + 1)
            yield self.BIT_POS[b] * bit_spacing
            n ^= b

    def print_bitmap(self, letter_bits, width):
        print(f"Printing bitmap {letter_bits}")
        print(f"Printing bits   {letter_bits[:width*self.font.HEIGHT]}")
        string = "\n".join(
            [
                (letter_bits[i : i + width]).replace("0", " ").replace("1", "*")
                for i in list(range(0, len(letter_bits), width))[:-1]
            ]
        )
        print(string)

    def get_lit_bits(self, letter):
        if letter in self.litbit_dict.keys():
            return self.litbit_dict[letter]
        width = self.width_dict[letter]
        height = self.font.HEIGHT
        letter_size = width * height
        offset = self.offset_dict[letter]
        start_byte, start_bit = divmod(offset, 8)
        end_byte, end_bit = divmod((offset + width * height), 8)
        letter_bytes = self.font._BITMAPS[start_byte : end_byte + (1 if end_bit > 0 else 0)]
        print(f"letter_bytes orig {letter_bytes}. Width {width}, Height {height}") if DEBUG_FONT else None
        print(f"start_byte:{start_byte},{start_bit}. end_byte:{end_byte},{end_bit}") if DEBUG_FONT else None
        # shift the entire array so that it ends on a byte boundary
        lba = (int.from_bytes(letter_bytes, "big") >> (8 - end_bit) % 8) & (1 << letter_size) - 1
        lba = int.to_bytes(lba, len(letter_bytes), "big")

        letter_bits = str(bin(int.from_bytes(lba)).lstrip("0b"))
        print(f"Printing bits {letter_bits}") if DEBUG_FONT else None
        if len(letter_bits) < width * self.font.HEIGHT:
            letter_bits = "0" * ((width * self.font.HEIGHT) - len(letter_bits)) + letter_bits
        self.print_bitmap(letter_bits, width) if DEBUG_FONT else None
        self.litbit_dict[letter] = []
        for ibit in range(letter_size):
            if letter_bits[ibit] == "1":
                self.litbit_dict[letter].append(ibit)
        return self.litbit_dict[letter]

    def get_letter(self, letter, color, landscape=False):
        """Convert letter byte data to pixels for color666 display
        Args:
            letter (string): Letter to return (must exist within font).
            color (int): color value.
            landscape (bool): Orientation (default: False = portrait)
        Returns:
            (bytearray): Pixel data.
            (int, int): Letter width and height.
        """
        # Confirm font contains letter
        if not letter in self.font.MAP:
            print("Font does not contain character: " + letter)
            return b"", 0, 0
        width = self.width_dict[letter]
        height = self.font.HEIGHT
        # letter_bits = self.get_letter_bits(letter)
        lit_bits = self.get_lit_bits(letter)
        letter_size = width * height

        # Create buffer (triple size to accommodate 18 bit colors)
        if isinstance(color, bytes):
            bytes_per_pixel = 3
        elif isinstance(color, int):
            bytes_per_pixel = 2
        else:
            raise ValueError("color must be of type color666 or color565")

        buf = bytearray(letter_size * bytes_per_pixel)

        if bytes_per_pixel == 2:
            color = color.to_bytes(2, "big")

        print(f"color_bytes = {color}") if DEBUG_FONT else None
        if landscape:
            # Populate buffer in order for landscape
            pos = (letter_size - height) * bytes_per_pixel
            print(f"pos: {pos}. letter_height {height}, letter_width {width}.") if DEBUG_FONT else None
            lh = height
            # Loop through letter byte data and convert to pixel data
            for ibit in range(letter_size):
                pass
                """
                if letter_bits[ibit] == "1":
                    pos = pos + bytes_per_pixel
                    for ib, cb in enumerate(color):
                        buf[pos + ib] = cb
                if lh > 8:
                    pos += 8 * bytes_per_pixel
                    lh -= 8
                    print(f"lh:{lh}, pos:{pos}") if DEBUG_FONT else None
                """
        else:
            # Populate buffer in order for portrait
            column = 0  # Set column to first column
            # Loop through letter byte data and convert to pixel data
            pos = 0
            for ibit in lit_bits:
                column, row = divmod(ibit, width)
                # print(f"ibit:{ibit}, width:{width}, column:{column}, row:{row}, len(buf):{len(buf)}") if DEBUG_FONT else None
                pos = ibit * bytes_per_pixel
                # print(f"pos:{pos}") if DEBUG_FONT else None
                for ib, cb in enumerate(color):
                    buf[pos + ib] = cb
            """
            for ibit in range(letter_size):
                column, row = divmod(ibit, width)
                # print(f"ibit:{ibit}, width:{width}, column:{column}, row:{row}, len(buf):{len(buf)}") if DEBUG_FONT else None
                if letter_bits[ibit] == "1":
                    pos = ibit * bytes_per_pixel
                    # print(f"pos:{pos}") if DEBUG_FONT else None
                    for ib, cb in enumerate(color):
                        buf[pos + ib] = cb
            """
        return buf, width, height

    def measure_text(self, text, spacing=1):
        """Measure length of text string in pixels.
        Args:
            text (string): Text string to measure
            spacing (optional int): Pixel spacing between letters.  Default: 1.
        Returns:
            int: length of text
        """
        length = 0
        for letter in text:
            # Get index of letter
            letter_ord = ord(letter) - self.start_letter
            offset = letter_ord * self.bytes_per_letter
            # Add length of letter and spacing
            length += self.letters[offset] + spacing
        return length
