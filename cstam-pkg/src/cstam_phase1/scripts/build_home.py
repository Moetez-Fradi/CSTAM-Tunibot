#!/usr/bin/env python3
"""Draw the robot's home corridor into the saved map.

The Sweet Home 3D model has a 1.86 m wide service corridor north of the
dining room (map x 4.85..6.71, y 10.44..17.98). It is the robot's home: it
charges there and is loaded through the kitchen service hatch in the end
wall. SLAM only saw its mouth, so this tool extends
maps/restaurant/restaurant.pgm northwards and draws the corridor from the
mesh geometry: walls occupied, interior free, doorway (x 5.02..6.58, the
door frame jambs either side) open. Everything else beyond the building
stays unknown.

Run from the workspace src directory, after build_terrace.py:
    python3 cstam_phase1/scripts/build_home.py
The map frame and world alignment are unchanged; only the image grows.
"""

import os

import numpy as np

from build_terrace import MAP_DIR, read_pgm

RES = 0.05
TOP_Y = 18.30               # map extends north to here
INTERIOR_X = (4.85, 6.71)
INTERIOR_Y = (10.44, 17.98)
WEST_WALL_X = (4.77, 4.85)
EAST_WALL_X = (6.71, 6.78)
END_WALL_Y = (17.98, 18.05)
# North dining-room wall with the doorway cut out (jambs included in walls).
NORTH_WALL_Y = (10.35, 10.46)
DOORWAY_X = (5.02, 6.58)


def main():
    yaml_path = os.path.join(MAP_DIR, 'restaurant.yaml')
    meta = open(yaml_path).read()
    origin_line = [line for line in meta.splitlines() if line.startswith('origin:')][0]
    ox, oy, _ = [float(v) for v in origin_line.split('[')[1].split(']')[0].split(',')]
    img = read_pgm(os.path.join(MAP_DIR, 'restaurant.pgm'))
    h, w = img.shape
    extra = int(round((TOP_Y - (oy + h * RES)) / RES))
    if extra > 0:  # rows grow downwards: new northern rows go on top
        img = np.vstack([np.full((extra, w), 205, dtype=np.uint8), img])
        h, w = img.shape

    def cells(x0, x1, y0, y1):
        c0, c1 = int(np.floor((x0 - ox) / RES)), int(np.ceil((x1 - ox) / RES))
        r0, r1 = int(np.floor((y0 - oy) / RES)), int(np.ceil((y1 - oy) / RES))
        c0, c1 = max(c0, 0), min(c1, w)
        r0, r1 = max(r0, 0), min(r1, h)
        return slice(h - r1, h - r0), slice(c0, c1)

    img[cells(INTERIOR_X[0], INTERIOR_X[1], INTERIOR_Y[0], INTERIOR_Y[1])] = 254
    img[cells(DOORWAY_X[0], DOORWAY_X[1], NORTH_WALL_Y[0], NORTH_WALL_Y[1])] = 254
    img[cells(WEST_WALL_X[0], DOORWAY_X[0], NORTH_WALL_Y[0], NORTH_WALL_Y[1])] = 0
    img[cells(DOORWAY_X[1], EAST_WALL_X[1], NORTH_WALL_Y[0], NORTH_WALL_Y[1])] = 0
    img[cells(WEST_WALL_X[0], WEST_WALL_X[1], NORTH_WALL_Y[0], END_WALL_Y[1])] = 0
    img[cells(EAST_WALL_X[0], EAST_WALL_X[1], NORTH_WALL_Y[0], END_WALL_Y[1])] = 0
    img[cells(WEST_WALL_X[0], EAST_WALL_X[1], END_WALL_Y[0], END_WALL_Y[1])] = 0

    with open(os.path.join(MAP_DIR, 'restaurant.pgm'), 'wb') as stream:
        stream.write(b'P5\n%d %d\n255\n' % (w, h))
        stream.write(img.tobytes())
    print(f'map {w}x{h}, top y {oy + h * RES:.2f}')


if __name__ == '__main__':
    main()
