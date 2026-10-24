"""Minimal QR Code encoder (ISO/IEC 18004), standard library only.

Byte mode, versions 1-40, error correction L/M/Q/H, automatic mask choice.
Only what the table cards need: encode a URL, render it as SVG. Follows the
structure of Project Nayuki's reference implementation (MIT licence).
"""

ECC_FORMAT_BITS = {'L': 1, 'M': 0, 'Q': 3, 'H': 2}
_ECC_INDEX = {'L': 0, 'M': 1, 'Q': 2, 'H': 3}
# Per version 1..40 (index 0 unused).
ECC_CODEWORDS_PER_BLOCK = (
    (-1, 7, 10, 15, 20, 26, 18, 20, 24, 30, 18, 20, 24, 26, 30, 22, 24, 28, 30, 28, 28,
     28, 28, 30, 30, 26, 28, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30),
    (-1, 10, 16, 26, 18, 24, 16, 18, 22, 22, 26, 30, 22, 22, 24, 24, 28, 28, 26, 26, 26,
     26, 28, 28, 28, 28, 28, 28, 28, 28, 28, 28, 28, 28, 28, 28, 28, 28, 28, 28, 28),
    (-1, 13, 22, 18, 26, 18, 24, 18, 22, 20, 24, 28, 26, 24, 20, 30, 24, 28, 28, 26, 30,
     28, 30, 30, 30, 30, 28, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30),
    (-1, 17, 28, 22, 16, 22, 28, 26, 26, 24, 28, 24, 28, 22, 24, 24, 30, 28, 28, 26, 28,
     30, 24, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30),
)
NUM_ERROR_CORRECTION_BLOCKS = (
    (-1, 1, 1, 1, 1, 1, 2, 2, 2, 2, 4, 4, 4, 4, 4, 6, 6, 6, 6, 7, 8,
     8, 9, 9, 10, 12, 12, 12, 13, 14, 15, 16, 17, 18, 19, 19, 20, 21, 22, 24, 25),
    (-1, 1, 1, 1, 2, 2, 4, 4, 4, 5, 5, 5, 8, 9, 9, 10, 10, 11, 13, 14, 16,
     17, 17, 18, 20, 21, 23, 25, 26, 28, 29, 31, 33, 35, 37, 38, 40, 43, 45, 47, 49),
    (-1, 1, 1, 2, 2, 4, 4, 6, 6, 8, 8, 8, 10, 12, 16, 12, 17, 16, 18, 21, 20,
     23, 23, 25, 27, 29, 34, 34, 35, 38, 40, 43, 45, 48, 51, 53, 56, 59, 62, 65, 68),
    (-1, 1, 1, 2, 4, 4, 4, 5, 6, 8, 8, 11, 11, 16, 16, 18, 16, 19, 21, 25, 25,
     25, 34, 30, 32, 35, 37, 40, 42, 45, 48, 51, 54, 57, 60, 63, 66, 70, 74, 77, 81),
)


def _bit(value, index):
    return (value >> index) & 1 != 0


def _raw_data_modules(version):
    result = (16 * version + 128) * version + 64
    if version >= 2:
        num_align = version // 7 + 2
        result -= (25 * num_align - 10) * num_align - 55
        if version >= 7:
            result -= 36
    return result


def _data_codewords(version, ecl):
    e = _ECC_INDEX[ecl]
    return (_raw_data_modules(version) // 8
            - ECC_CODEWORDS_PER_BLOCK[e][version] * NUM_ERROR_CORRECTION_BLOCKS[e][version])


def _gf_multiply(x, y):
    z = 0
    for i in reversed(range(8)):
        z = (z << 1) ^ ((z >> 7) * 0x11D)
        z ^= ((y >> i) & 1) * x
    return z


def _rs_divisor(degree):
    result = [0] * (degree - 1) + [1]
    root = 1
    for _ in range(degree):
        for j in range(degree):
            result[j] = _gf_multiply(result[j], root)
            if j + 1 < degree:
                result[j] ^= result[j + 1]
        root = _gf_multiply(root, 0x02)
    return result


def _rs_remainder(data, divisor):
    result = [0] * len(divisor)
    for byte in data:
        factor = byte ^ result.pop(0)
        result.append(0)
        for i, coef in enumerate(divisor):
            result[i] ^= _gf_multiply(coef, factor)
    return result


class QrCode:
    """Encode bytes or text; `modules[y][x]` is True for a dark module."""

    def __init__(self, data, ecl='M', mask=None):
        if isinstance(data, str):
            data = data.encode('utf-8')
        if ecl not in ECC_FORMAT_BITS:
            raise ValueError('error correction level must be L, M, Q or H')
        for version in range(1, 41):
            count_bits = 8 if version <= 9 else 16
            needed = 4 + count_bits + 8 * len(data)
            if len(data) < (1 << count_bits) and needed <= _data_codewords(version, ecl) * 8:
                break
        else:
            raise ValueError('data too long for a QR code')
        self.version, self.ecl = version, ecl
        self.size = version * 4 + 17

        # Data bits: byte mode, length, payload, terminator, padding.
        bits = []
        append = lambda value, n: bits.extend((value >> i) & 1 for i in reversed(range(n)))  # noqa: E731
        append(0b0100, 4)
        append(len(data), count_bits)
        for byte in data:
            append(byte, 8)
        capacity = _data_codewords(version, ecl) * 8
        append(0, min(4, capacity - len(bits)))
        append(0, -len(bits) % 8)
        pad = 0xEC
        while len(bits) < capacity:
            append(pad, 8)
            pad ^= 0xEC ^ 0x11
        codewords = [int(''.join(map(str, bits[i:i + 8])), 2) for i in range(0, len(bits), 8)]

        self.modules = [[False] * self.size for _ in range(self.size)]
        self.function = [[False] * self.size for _ in range(self.size)]
        self._draw_function_patterns()
        self._draw_codewords(self._add_ecc_and_interleave(codewords))
        best, best_penalty = mask, None
        for candidate in range(8) if mask is None else ():
            self._apply_mask(candidate)
            self._draw_format_bits(candidate)
            penalty = self._penalty()
            if best_penalty is None or penalty < best_penalty:
                best, best_penalty = candidate, penalty
            self._apply_mask(candidate)  # XOR again undoes it
        self.mask = best
        self._apply_mask(best)
        self._draw_format_bits(best)

    # ----- layout ----------------------------------------------------------

    def _set(self, x, y, dark):
        self.modules[y][x] = dark
        self.function[y][x] = True

    def _draw_function_patterns(self):
        size = self.size
        for i in range(size):
            self._set(6, i, i % 2 == 0)
            self._set(i, 6, i % 2 == 0)
        for cx, cy in ((3, 3), (size - 4, 3), (3, size - 4)):
            for dy in range(-4, 5):
                for dx in range(-4, 5):
                    x, y = cx + dx, cy + dy
                    if 0 <= x < size and 0 <= y < size:
                        self._set(x, y, max(abs(dx), abs(dy)) not in (2, 4))
        positions = self._alignment_positions()
        last = len(positions) - 1
        for i, ax in enumerate(positions):
            for j, ay in enumerate(positions):
                if (i, j) in ((0, 0), (0, last), (last, 0)):
                    continue  # overlaps a finder pattern
                for dy in range(-2, 3):
                    for dx in range(-2, 3):
                        self._set(ax + dx, ay + dy, max(abs(dx), abs(dy)) != 1)
        self._draw_format_bits(0)  # reserve the areas; redrawn with the real mask
        if self.version >= 7:
            rem = self.version
            for _ in range(12):
                rem = (rem << 1) ^ ((rem >> 11) * 0x1F25)
            bits = self.version << 12 | rem
            for i in range(18):
                dark = _bit(bits, i)
                a, b = size - 11 + i % 3, i // 3
                self._set(a, b, dark)
                self._set(b, a, dark)

    def _alignment_positions(self):
        if self.version == 1:
            return []
        num_align = self.version // 7 + 2
        step = (self.version * 8 + num_align * 3 + 5) // (num_align * 4 - 4) * 2
        result = [self.size - 7 - i * step for i in range(num_align - 1)] + [6]
        return list(reversed(result))

    def _draw_format_bits(self, mask):
        data = ECC_FORMAT_BITS[self.ecl] << 3 | mask
        rem = data
        for _ in range(10):
            rem = (rem << 1) ^ ((rem >> 9) * 0x537)
        bits = (data << 10 | rem) ^ 0x5412
        size = self.size
        for i in range(6):
            self._set(8, i, _bit(bits, i))
        self._set(8, 7, _bit(bits, 6))
        self._set(8, 8, _bit(bits, 7))
        self._set(7, 8, _bit(bits, 8))
        for i in range(9, 15):
            self._set(14 - i, 8, _bit(bits, i))
        for i in range(8):
            self._set(size - 1 - i, 8, _bit(bits, i))
        for i in range(8, 15):
            self._set(8, size - 15 + i, _bit(bits, i))
        self._set(8, size - 8, True)  # always-dark module

    def _add_ecc_and_interleave(self, data):
        e = _ECC_INDEX[self.ecl]
        num_blocks = NUM_ERROR_CORRECTION_BLOCKS[e][self.version]
        ecc_len = ECC_CODEWORDS_PER_BLOCK[e][self.version]
        raw = _raw_data_modules(self.version) // 8
        num_short = num_blocks - raw % num_blocks
        short_len = raw // num_blocks
        divisor = _rs_divisor(ecc_len)
        blocks, k = [], 0
        for i in range(num_blocks):
            block = data[k:k + short_len - ecc_len + (0 if i < num_short else 1)]
            k += len(block)
            ecc = _rs_remainder(block, divisor)
            if i < num_short:
                block = block + [0]
            blocks.append(block + ecc)
        result = []
        for i in range(len(blocks[0])):
            for j, block in enumerate(blocks):
                if i != short_len - ecc_len or j >= num_short:
                    result.append(block[i])
        return result

    def _draw_codewords(self, data):
        size, i = self.size, 0
        right = size - 1
        while right >= 1:
            if right == 6:
                right = 5
            for vert in range(size):
                for j in range(2):
                    x = right - j
                    upward = ((right + 1) & 2) == 0
                    y = size - 1 - vert if upward else vert
                    if not self.function[y][x] and i < len(data) * 8:
                        self.modules[y][x] = _bit(data[i >> 3], 7 - (i & 7))
                        i += 1
            right -= 2

    def _apply_mask(self, mask):
        conditions = (
            lambda x, y: (x + y) % 2 == 0,
            lambda x, y: y % 2 == 0,
            lambda x, y: x % 3 == 0,
            lambda x, y: (x + y) % 3 == 0,
            lambda x, y: (x // 3 + y // 2) % 2 == 0,
            lambda x, y: x * y % 2 + x * y % 3 == 0,
            lambda x, y: (x * y % 2 + x * y % 3) % 2 == 0,
            lambda x, y: ((x + y) % 2 + x * y % 3) % 2 == 0,
        )
        condition = conditions[mask]
        for y in range(self.size):
            for x in range(self.size):
                if not self.function[y][x] and condition(x, y):
                    self.modules[y][x] = not self.modules[y][x]

    def _penalty(self):
        """Readability score (lower is better): runs, 2x2 blocks, balance."""
        size, m = self.size, self.modules
        penalty = 0
        for lines in (m, list(zip(*m))):
            for line in lines:
                run, colour = 0, None
                for dark in line:
                    if dark == colour:
                        run += 1
                    else:
                        if run >= 5:
                            penalty += run - 2
                        run, colour = 1, dark
                if run >= 5:
                    penalty += run - 2
                text = ''.join('1' if d else '0' for d in line)
                for pattern in ('10111010000', '00001011101'):
                    penalty += 40 * text.count(pattern)
        for y in range(size - 1):
            for x in range(size - 1):
                if m[y][x] == m[y][x + 1] == m[y + 1][x] == m[y + 1][x + 1]:
                    penalty += 3
        dark = sum(sum(row) for row in m)
        total = size * size
        penalty += 10 * ((abs(dark * 20 - total * 10) + total - 1) // total - 1)
        return penalty

    # ----- output ----------------------------------------------------------

    def svg(self, border=4, title=None):
        """Black on white SVG (scanners need dark-on-light; never themed)."""
        dim = self.size + 2 * border
        path = ''.join(f'M{x + border},{y + border}h1v1h-1z'
                       for y, row in enumerate(self.modules) for x, dark in enumerate(row) if dark)
        label = f'<title>{_escape(title)}</title>' if title else ''
        return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {dim} {dim}" '
                f'shape-rendering="crispEdges" role="img">{label}'
                f'<rect width="100%" height="100%" fill="#fff"/>'
                f'<path d="{path}" fill="#000"/></svg>')


def _escape(text):
    return (str(text).replace('&', '&amp;').replace('<', '&lt;')
            .replace('>', '&gt;').replace('"', '&quot;'))
