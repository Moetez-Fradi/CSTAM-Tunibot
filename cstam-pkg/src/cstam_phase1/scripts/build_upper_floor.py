#!/usr/bin/env python3
"""Open the elevator shaft and build the upper dining room (floor 2).

The Sweet Home 3D model already has an elevator shaft south of the dining
room (map x -0.10..1.92, y -12.64..-10.73) with a doorway on its north side
at floor 1 and on its south side at floor 2, and a furnished upper dining
room above the south wing (floor surface at z 2.56). The exported collision
model closes both doorways (one box per wall, ignoring the opening) and has
no floor slab upstairs. This tool

1. splits the collision boxes around the two shaft doorways,
2. writes andino_gz/models/upper_floor_collision: the floor-2 slab,
3. extends maps/restaurant/restaurant.pgm south over the shaft, and
4. writes maps/restaurant/floor2.{pgm,yaml} in the same map frame, drawn
   from the collision walls and the floor-2 furniture of the mesh.

Run from the workspace src directory, after build_terrace.py and
build_home.py; running it again changes nothing:
    python3 cstam_phase1/scripts/build_upper_floor.py
"""

import os
import re

import functools

import numpy as np

from build_terrace import MAP_DIR, SRC, WORLD_FROM_MAP, mesh_boxes, read_pgm

MESH_BOXES = functools.lru_cache(maxsize=1)(mesh_boxes)   # reading the mesh takes seconds

COLLISION = os.path.join(SRC, 'andino_gz/andino_gz/models/restaurant_collision/model.sdf')
SLAB_DIR = os.path.join(SRC, 'andino_gz/andino_gz/models/upper_floor_collision')
MESH_X0, MESH_Y0 = -14.115, 17.0   # restaurant_collision model pose (roll 90 deg)
RES = 0.05

FLOOR2_Z = 2.56                     # top of the upper floor slab
SLAB = ((-7.08, 8.72), (-31.88, -10.78), 0.12)   # x, y, thickness
SHAFT_X = (-0.08, 1.90)             # inside the shaft walls
SHAFT_Y = (-12.59, -10.78)
# Doorways (map x, map y band, z): floor 1 north side, floor 2 south side.
DOORWAYS = (((-0.05, 1.85), (-10.85, -10.65), (0.0, 2.03)),
            ((-0.12, 1.70), (-12.70, -12.55), (FLOOR2_Z, 4.60)))
UPPER_ROOM = ((-7.04, 8.69), (-31.85, -10.78))
DINING_ROOM = ((-7.00, 8.68), (-10.69, 10.35))   # floor 1, inside the walls
Z_BAND_2 = (FLOOR2_Z + 0.05, FLOOR2_Z + 1.30)
FLOOR2_ORIGIN = (-7.60, -32.30)
FLOOR2_SIZE = (17.0, 22.0)          # m
SOUTH_EXTENSION_Y = -12.90          # floor-1 map grows south to here


# 1. Collision doorways ---------------------------------------------------------
def _box_map(pose, size):
    """Collision box (model frame, roll 90 deg) -> map-frame min/max corners."""
    cx, cy, cz = pose[0] + MESH_X0 - WORLD_FROM_MAP[0], MESH_Y0 - pose[2] - WORLD_FROM_MAP[1], pose[1]
    sx, sy, sz = size[0], size[2], size[1]
    return (cx - sx / 2, cx + sx / 2), (cy - sy / 2, cy + sy / 2), (cz - sz / 2, cz + sz / 2)


def _box_xml(name, xs, ys, zs):
    """Map-frame box -> collision element in the model frame."""
    px = (xs[0] + xs[1]) / 2 - MESH_X0 + WORLD_FROM_MAP[0]
    pz = MESH_Y0 - WORLD_FROM_MAP[1] - (ys[0] + ys[1]) / 2
    py = (zs[0] + zs[1]) / 2
    return (f'      <collision name="{name}">\n'
            f'        <pose>{px:.4f} {py:.4f} {pz:.4f} 0 0 0</pose>\n'
            f'        <geometry>\n          <box>\n'
            f'            <size>{xs[1] - xs[0]:.4f} {zs[1] - zs[0]:.4f} {ys[1] - ys[0]:.4f}</size>\n'
            f'          </box>\n        </geometry>\n      </collision>\n')


def open_doorways():
    text = open(COLLISION, encoding='utf-8').read()
    if '_doorway_' in text:
        return 0
    pattern = re.compile(r'      <collision name="([^"]+)">.*?</collision>\n', re.S)
    split = 0

    def replace(match):
        nonlocal split
        block = match.group(0)
        pose = [float(v) for v in re.search(r'<pose>([^<]+)</pose>', block).group(1).split()]
        size = [float(v) for v in re.search(r'<size>([^<]+)</size>', block).group(1).split()]
        xs, ys, zs = _box_map(pose, size)
        for (hx, hy, hz) in DOORWAYS:
            if not (xs[0] < hx[1] and xs[1] > hx[0] and ys[0] < hy[1] and ys[1] > hy[0]
                    and zs[0] < hz[1] and zs[1] > hz[0]):
                continue
            name, parts = match.group(1), []
            if xs[0] < hx[0]:
                parts.append((xs[0], hx[0], zs[0], zs[1]))
            if xs[1] > hx[1]:
                parts.append((hx[1], xs[1], zs[0], zs[1]))
            gx = (max(xs[0], hx[0]), min(xs[1], hx[1]))
            if zs[0] < hz[0]:
                parts.append((gx[0], gx[1], zs[0], hz[0]))   # below the sill
            if zs[1] > hz[1]:
                parts.append((gx[0], gx[1], hz[1], zs[1]))   # lintel
            split += 1
            return ''.join(_box_xml(f'{name}_doorway_{i}', (x0, x1), ys, (z0, z1))
                           for i, (x0, x1, z0, z1) in enumerate(parts))
        return block

    text = pattern.sub(replace, text)
    with open(COLLISION, 'w', encoding='utf-8') as stream:
        stream.write(text)
    return split


# 2. Floor-2 slab ------------------------------------------------------------------
def write_slab():
    os.makedirs(SLAB_DIR, exist_ok=True)
    (x0, x1), (y0, y1), thick = SLAB
    wx, wy = WORLD_FROM_MAP
    with open(os.path.join(SLAB_DIR, 'model.sdf'), 'w', encoding='utf-8') as stream:
        stream.write(
            '<?xml version="1.0"?>\n'
            '<!-- Generated by cstam_phase1/scripts/build_upper_floor.py: the upper\n'
            '     dining room floor, which the exported collision model lacks. -->\n'
            '<sdf version="1.7">\n  <model name="upper_floor_collision">\n'
            '    <static>true</static>\n    <link name="slab">\n'
            '      <collision name="floor2">\n'
            f'        <pose>{(x0 + x1) / 2 + wx:.3f} {(y0 + y1) / 2 + wy:.3f} '
            f'{FLOOR2_Z - thick / 2:.3f} 0 0 0</pose>\n'
            f'        <geometry><box><size>{x1 - x0:.3f} {y1 - y0:.3f} {thick:.3f}</size></box></geometry>\n'
            '      </collision>\n    </link>\n  </model>\n</sdf>\n')
    with open(os.path.join(SLAB_DIR, 'model.config'), 'w', encoding='utf-8') as stream:
        stream.write(
            '<?xml version="1.0"?>\n<model>\n  <name>upper_floor_collision</name>\n'
            '  <version>1.0</version>\n  <sdf version="1.7">model.sdf</sdf>\n'
            '  <description>Floor slab of the upper dining room.</description>\n</model>\n')


# 3./4. Maps -------------------------------------------------------------------------
def collision_boxes():
    text = open(COLLISION, encoding='utf-8').read()
    for block in re.findall(r'<collision name="[^"]+">.*?</collision>', text, re.S):
        pose = [float(v) for v in re.search(r'<pose>([^<]+)</pose>', block).group(1).split()]
        size = [float(v) for v in re.search(r'<size>([^<]+)</size>', block).group(1).split()]
        yield _box_map(pose, size)


def _painter(img, ox, oy):
    h, w = img.shape

    def paint(xs, ys, value):
        c0, c1 = int(np.floor((xs[0] - ox) / RES)), int(np.ceil((xs[1] - ox) / RES))
        r0, r1 = int(np.floor((ys[0] - oy) / RES)), int(np.ceil((ys[1] - oy) / RES))
        c0, c1, r0, r1 = max(c0, 0), min(c1, w), max(r0, 0), min(r1, h)
        if c0 < c1 and r0 < r1:
            img[h - r1:h - r0, c0:c1] = value   # image rows grow downwards
    return paint


def _shaft_walls(boxes, zband):
    """Collision walls around the shaft at one floor's height."""
    for xs, ys, zs in boxes:
        if zs[1] < zband[0] or zs[0] > zband[1]:
            continue
        if xs[1] < SHAFT_X[0] - 0.2 or xs[0] > SHAFT_X[1] + 0.2:
            continue
        if ys[1] < SHAFT_Y[0] - 0.2 or ys[0] > SHAFT_Y[1] + 0.2:
            continue
        yield xs, ys


def extend_floor1_map(boxes):
    yaml_path = os.path.join(MAP_DIR, 'restaurant.yaml')
    meta = open(yaml_path).read()
    origin_line = [line for line in meta.splitlines() if line.startswith('origin:')][0]
    ox, oy, oth = [float(v) for v in origin_line.split('[')[1].split(']')[0].split(',')]
    img = read_pgm(os.path.join(MAP_DIR, 'restaurant.pgm'))
    if oy > SOUTH_EXTENSION_Y + 0.01:
        extra = int(round((oy - SOUTH_EXTENSION_Y) / RES))
        img = np.vstack([img, np.full((extra, img.shape[1]), 205, dtype=np.uint8)])
        oy -= extra * RES
    paint = _painter(img, ox, oy)
    # SLAM left the south of the dining room (the way to the shaft) and the
    # shadows behind tables unknown. Fill only those unknown cells: free
    # inside the dining-room walls, the mesh furniture occupied.
    unknown = img == 205
    filled = img.copy()
    fill = _painter(filled, ox, oy)
    fill(*DINING_ROOM, 254)
    for _name, xs, ys in furniture_in(DINING_ROOM, (0.05, 1.30)):
        fill(xs, ys, 0)
    img[unknown] = filled[unknown]
    paint(SHAFT_X, SHAFT_Y, 254)
    for xs, ys in _shaft_walls(boxes, (0.05, 1.30)):
        paint(xs, ys, 0)
    (dx, dy, _dz) = DOORWAYS[0]
    paint(dx, dy, 254)   # SLAM drew the closed doorway as wall
    # The shaft's south side is closed at floor 1; the robot never leaves that way.
    paint(SHAFT_X, (-12.70, -12.59), 0)
    with open(os.path.join(MAP_DIR, 'restaurant.pgm'), 'wb') as stream:
        stream.write(b'P5\n%d %d\n255\n' % (img.shape[1], img.shape[0]))
        stream.write(img.tobytes())
    with open(yaml_path, 'w') as stream:
        stream.write(meta.replace(origin_line, f'origin: [{ox:.3f}, {oy:.3f}, {oth:g}]'))
    return img.shape


def furniture_in(room, zband):
    found = []
    for name, (x0, x1, y0, y1, z0, z1) in MESH_BOXES().items():
        if x1 < room[0][0] or x0 > room[0][1] or y1 < room[1][0] or y0 > room[1][1]:
            continue
        if z1 < zband[0] or z0 > zband[1]:
            continue
        if x1 - x0 > 2.5 or y1 - y0 > 2.5 or name.startswith('wall_'):
            continue   # floors and walls come from the (doorway-split) collision walls
        if min(x1 - x0, y1 - y0) < 0.15 and max(x1 - x0, y1 - y0) > 1.0:
            continue   # a door frame: its box would span the opening it frames
        found.append((name, (x0, x1), (y0, y1)))
    return found


def write_floor2_map(boxes, furniture):
    w, h = int(FLOOR2_SIZE[0] / RES), int(FLOOR2_SIZE[1] / RES)
    img = np.full((h, w), 205, dtype=np.uint8)
    paint = _painter(img, *FLOOR2_ORIGIN)
    paint(*UPPER_ROOM, 254)
    paint(SHAFT_X, SHAFT_Y, 254)
    for xs, ys, zs in boxes:
        if zs[1] < Z_BAND_2[0] or zs[0] > Z_BAND_2[1]:
            continue
        if xs[1] < UPPER_ROOM[0][0] - 0.3 or xs[0] > UPPER_ROOM[0][1] + 0.3:
            continue
        if ys[1] < UPPER_ROOM[1][0] - 0.3 or ys[0] > UPPER_ROOM[1][1] + 0.3:
            continue
        paint(xs, ys, 0)
    for _name, xs, ys in furniture:
        paint(xs, ys, 0)
    with open(os.path.join(MAP_DIR, 'floor2.pgm'), 'wb') as stream:
        stream.write(b'P5\n%d %d\n255\n' % (w, h))
        stream.write(img.tobytes())
    with open(os.path.join(MAP_DIR, 'floor2.yaml'), 'w') as stream:
        stream.write(
            '# Upper dining room (floor 2), drawn by scripts/build_upper_floor.py from\n'
            '# the collision walls and the floor-2 furniture of the restaurant mesh.\n'
            '# Same map frame as restaurant.yaml; the elevator switches between them.\n'
            'image: floor2.pgm\nmode: trinary\nresolution: 0.050\n'
            f'origin: [{FLOOR2_ORIGIN[0]:.3f}, {FLOOR2_ORIGIN[1]:.3f}, 0]\n'
            'negate: 0\noccupied_thresh: 0.65\nfree_thresh: 0.196\n')
    return img.shape


def main():
    split = open_doorways()
    write_slab()
    boxes = list(collision_boxes())
    shape1 = extend_floor1_map(boxes)
    furniture = furniture_in(UPPER_ROOM, Z_BAND_2)
    shape2 = write_floor2_map(boxes, furniture)
    print(f'split {split} collision boxes at the shaft doorways; floor-1 map {shape1[1]}x{shape1[0]}; '
          f'floor-2 map {shape2[1]}x{shape2[0]} with {len(furniture)} furniture parts')


if __name__ == '__main__':
    main()
