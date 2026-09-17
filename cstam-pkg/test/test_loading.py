#!/usr/bin/env python3
import os
import yaml
import difflib
from math import sin, cos
def yaw_to_quat(yaw: float):
    return {'x':0, 'y':0, 'z':sin(yaw/2), 'w':cos(yaw/2)}
def load_named_poses(path: str):
    print(f"Loading from: {path}")
    if not os.path.exists(path):
        print("File not found!")
        return {}
    with open(path, 'r') as f:
        data = yaml.safe_load(f) or {}
    base = data.get('waypoints', data) if isinstance(data, dict) else {}
    poses = {}
    for name, pose in (base.items() if isinstance(base, dict) else []):
        if not isinstance(pose, dict):
            continue
        poses[str(name)] = pose
    return poses
def resolve_name(named_poses, name: str, fuzzy_cutoff=0.7):
    if name in named_poses:
        return name
    names = list(named_poses.keys())
    lower_map = {n.lower(): n for n in names}
    if name.lower() in lower_map:
        return lower_map[name.lower()]
    cand = difflib.get_close_matches(name.lower(), [n.lower() for n in names], n=1, cutoff=fuzzy_cutoff)
    return lower_map[cand[0]] if cand else None
yaml_path = os.path.expanduser('~/ws/src/App/map_info/maps/office_simulation.yaml')
poses = load_named_poses(yaml_path)
print(f"Loaded {len(poses)} waypoints: {list(poses.keys())}")
for query in ["Library", "library", "LIB", "Kitchen"]:
    res = resolve_name(poses, query)
    print(f"Query: '{query}' -> Resolved: '{res}'")
