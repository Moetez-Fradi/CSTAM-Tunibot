#!/usr/bin/env python3
"""Align a SLAM map of floor 2 into the shared map frame.

SLAM Toolbox's map frame starts at the robot's spawn pose; map_floor2.sh
spawns it facing east (yaw 0 in the map frame), so the alignment is the
spawn position added to the map origin. The elevator shaft, which the
patrol does not enter, is drawn free between its walls so the cabin pose
stays reachable. Writes floor2.pgm and floor2.yaml into MAPS_DIR.

    align_floor2_map.py SLAM_YAML SPAWN_X SPAWN_Y MAPS_DIR
"""

import os
import sys

import numpy as np
import yaml

SHAFT_X, SHAFT_Y = (-0.08, 1.90), (-12.59, -10.78)
WALL = 0.05


def read_pgm(path):
    raw = open(path, 'rb').read()
    parts, i = [], 0
    while len(parts) < 4:
        while raw[i:i + 1].isspace():
            i += 1
        if raw[i:i + 1] == b'#':
            i = raw.index(b'\n', i) + 1
            continue
        j = i
        while not raw[j:j + 1].isspace():
            j += 1
        parts.append(raw[i:j])
        i = j
    w, h = int(parts[1]), int(parts[2])
    return np.frombuffer(raw[i + 1:i + 1 + w * h], dtype=np.uint8).reshape(h, w).copy()


def main():
    slam_yaml, sx, sy, maps = sys.argv[1], float(sys.argv[2]), float(sys.argv[3]), sys.argv[4]
    meta = yaml.safe_load(open(slam_yaml))
    img = read_pgm(os.path.join(os.path.dirname(slam_yaml), meta['image']))
    res = float(meta['resolution'])
    ox, oy = float(meta['origin'][0]) + sx, float(meta['origin'][1]) + sy
    h, w = img.shape

    def paint(xs, ys, value):
        c0, c1 = max(0, int(np.floor((xs[0] - ox) / res))), min(w, int(np.ceil((xs[1] - ox) / res)))
        r0, r1 = max(0, int(np.floor((ys[0] - oy) / res))), min(h, int(np.ceil((ys[1] - oy) / res)))
        if c0 < c1 and r0 < r1:
            img[h - r1:h - r0, c0:c1] = value
    paint(SHAFT_X, SHAFT_Y, 254)
    paint((SHAFT_X[0] - WALL, SHAFT_X[0]), SHAFT_Y, 0)
    paint((SHAFT_X[1], SHAFT_X[1] + WALL), SHAFT_Y, 0)
    paint(SHAFT_X, (SHAFT_Y[1], SHAFT_Y[1] + WALL), 0)   # closed to the north at floor 2
    with open(os.path.join(maps, 'floor2.pgm'), 'wb') as stream:
        stream.write(b'P5\n%d %d\n255\n' % (w, h))
        stream.write(img.tobytes())
    with open(os.path.join(maps, 'floor2.yaml'), 'w') as stream:
        stream.write(
            '# Upper dining room (floor 2), mapped with SLAM Toolbox by\n'
            '# scripts/map_floor2.sh and aligned into the shared map frame by\n'
            '# scripts/align_floor2_map.py (the elevator shaft drawn in).\n'
            f'image: floor2.pgm\nmode: trinary\nresolution: {res:.3f}\n'
            f'origin: [{ox:.3f}, {oy:.3f}, 0]\n'
            'negate: 0\noccupied_thresh: 0.65\nfree_thresh: 0.196\n')
    print(f'floor2.pgm {w}x{h}, origin ({ox:.2f}, {oy:.2f})')


if __name__ == '__main__':
    main()
