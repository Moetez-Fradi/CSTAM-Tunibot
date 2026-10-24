"""Serve the saved occupancy map to browsers: PGM (map_server) -> PNG.

Browsers cannot display PGM, and the map is static, so it is converted once
at startup with the standard library only (zlib + struct).
"""

import os
import struct
import zlib

import yaml


def read_pgm(path):
    """Return (width, height, bytes) of an 8-bit binary (P5) PGM."""
    with open(path, 'rb') as stream:
        data = stream.read()
    fields, index = [], 0
    while len(fields) < 4:
        while data[index:index + 1].isspace():
            index += 1
        if data[index:index + 1] == b'#':
            index = data.index(b'\n', index) + 1
            continue
        start = index
        while not data[index:index + 1].isspace():
            index += 1
        fields.append(data[start:index])
    if fields[0] != b'P5':
        raise ValueError(f'{path}: only binary P5 PGM maps are supported')
    width, height, maxval = (int(f) for f in fields[1:])
    if maxval > 255:
        raise ValueError(f'{path}: 16-bit PGM maps are not supported')
    pixels = data[index + 1:index + 1 + width * height]
    if len(pixels) != width * height:
        raise ValueError(f'{path}: truncated image data')
    return width, height, pixels


def grayscale_png(width, height, pixels):
    def chunk(kind, body):
        return (struct.pack('>I', len(body)) + kind + body
                + struct.pack('>I', zlib.crc32(kind + body) & 0xffffffff))
    rows = b''.join(b'\x00' + pixels[y * width:(y + 1) * width] for y in range(height))
    return (b'\x89PNG\r\n\x1a\n'
            + chunk(b'IHDR', struct.pack('>IIBBBBB', width, height, 8, 0, 0, 0, 0))
            + chunk(b'IDAT', zlib.compress(rows, 9))
            + chunk(b'IEND', b''))


def load_map(yaml_path):
    """Return (png_bytes, meta) for a map_server YAML file.

    meta gives what a browser needs to place map-frame points on the image:
    pixel column = (x - origin_x) / resolution,
    pixel row    = height - (y - origin_y) / resolution.
    """
    with open(yaml_path, encoding='utf-8') as stream:
        info = yaml.safe_load(stream)
    image = info['image']
    if not os.path.isabs(image):
        image = os.path.join(os.path.dirname(yaml_path), image)
    width, height, pixels = read_pgm(image)
    if int(info.get('negate', 0)):
        pixels = bytes(255 - p for p in pixels)
    meta = {
        'width': width, 'height': height,
        'resolution': float(info['resolution']),
        'origin': [float(v) for v in info['origin'][:2]],
    }
    return grayscale_png(width, height, pixels), meta
