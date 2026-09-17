#!/usr/bin/env python3
"""Create lightweight Gazebo collision boxes from the Sweet Home 3D OBJ.

The visual OBJ is a single self-intersecting triangle mesh, which cannot be
used directly for stable ODE collision.  This script collects the bounds of
the named wall, table-top, chair-seat and chair-back groups and emits static
box collisions in the same Sweet Home coordinate frame.
"""

from pathlib import Path
import re
import xml.etree.ElementTree as ET


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "models" / "restaurant" / "meshes" / "restaurant.obj"
OUTPUT = ROOT / "models" / "restaurant_collision" / "model.sdf"
GROUPS = re.compile(r"^(wall_|Plateau_|Assise_|Dossier_)")
MIN_SIZE_M = 0.02


def update(bounds, point):
    if bounds is None:
        return [list(point), list(point)]
    for axis, value in enumerate(point):
        bounds[0][axis] = min(bounds[0][axis], value)
        bounds[1][axis] = max(bounds[1][axis], value)
    return bounds


def load_bounds(path):
    vertices = [None]
    bounds = {}
    group = None
    with path.open(encoding="utf-8") as obj:
        for raw in obj:
            fields = raw.split()
            if not fields:
                continue
            if fields[0] == "v":
                vertices.append(tuple(map(float, fields[1:4])))
            elif fields[0] == "g":
                group = fields[1] if len(fields) > 1 else None
            elif fields[0] == "f" and group and GROUPS.match(group):
                for reference in fields[1:]:
                    index = int(reference.split("/", 1)[0])
                    if index < 0:
                        index += len(vertices)
                    bounds[group] = update(bounds.get(group), vertices[index])
    return bounds


def element(parent, tag, text=None, **attrs):
    node = ET.SubElement(parent, tag, attrs)
    node.text = text
    return node


def main():
    boxes = load_bounds(SOURCE)
    sdf = ET.Element("sdf", {"version": "1.7"})
    model = element(sdf, "model", name="restaurant_collision")
    # Same centimetre / Y-up to metre / Z-up transform as the visual model.
    element(model, "pose", "-14.115 17.000 0 1.57079632679 0 0")
    element(model, "static", "true")
    link = element(model, "link", name="collision_link")

    for number, (name, (lower, upper)) in enumerate(sorted(boxes.items())):
        # (low + high) / 2 converts bounds to a centre; convert cm to m.
        center = [(low + high) * 0.005 for low, high in zip(lower, upper)]
        size = [max((high - low) * 0.01, MIN_SIZE_M)
                for low, high in zip(lower, upper)]
        collision = element(link, "collision", name=f"box_{number}_{name}")
        element(collision, "pose", " ".join(f"{v:.4f}" for v in center) + " 0 0 0")
        geometry = element(collision, "geometry")
        box = element(geometry, "box")
        element(box, "size", " ".join(f"{v:.4f}" for v in size))
        surface = element(collision, "surface")
        friction = element(surface, "friction")
        ode = element(friction, "ode")
        element(ode, "mu", "1.0")
        element(ode, "mu2", "1.0")

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    ET.indent(sdf, space="  ")
    ET.ElementTree(sdf).write(OUTPUT, encoding="utf-8", xml_declaration=True)
    print(f"Wrote {len(boxes)} collision boxes to {OUTPUT}")


if __name__ == "__main__":
    main()
