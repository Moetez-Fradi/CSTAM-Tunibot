"""Keep the perception and navigation envelopes outside real robot geometry."""
import ast
from pathlib import Path
import xml.etree.ElementTree as ET
import math

from ament_index_python.packages import get_package_share_directory
import numpy as np
import xacro
import yaml


def rotation(values):
    roll, pitch, yaw = values
    cr, sr, cp, sp, cy, sy = (math.cos(roll), math.sin(roll),
                             math.cos(pitch), math.sin(pitch),
                             math.cos(yaw), math.sin(yaw))
    return np.array([[cy*cp, cy*sp*sr-sy*cr, cy*sp*cr+sy*sr],
                     [sy*cp, sy*sp*sr+cy*cr, sy*sp*cr-cy*sr],
                     [-sp, cp*sr, cp*cr]])


def test_collision_envelope():
    source = Path(get_package_share_directory('cstam_robot')) / 'urdf/cstam_robot.urdf.xacro'
    root = ET.fromstring(xacro.process_file(str(source)).toxml())
    joints = {j.find('child').attrib['link']: j for j in root.findall('joint')}
    transforms = {'base_footprint': (np.zeros(3), np.eye(3))}

    def transform(link):
        if link not in transforms:
            joint = joints[link]
            position, orientation = transform(joint.find('parent').attrib['link'])
            origin = joint.find('origin')
            offset = np.fromstring(origin.get('xyz', '0 0 0'), sep=' ')
            angles = np.fromstring(origin.get('rpy', '0 0 0'), sep=' ')
            transforms[link] = position + orientation @ offset, orientation @ rotation(angles)
        return transforms[link]

    bounds = []
    for link in root.findall('link'):
        position, orientation = transform(link.get('name'))
        for collision in link.findall('collision'):
            origin = collision.find('origin')
            offset = np.zeros(3) if origin is None else np.fromstring(origin.get('xyz', '0 0 0'), sep=' ')
            angles = np.zeros(3) if origin is None else np.fromstring(origin.get('rpy', '0 0 0'), sep=' ')
            geometry = collision.find('geometry')
            box, cylinder = geometry.find('box'), geometry.find('cylinder')
            if box is not None:
                half = np.fromstring(box.get('size'), sep=' ') / 2
            else:
                assert cylinder is not None, 'Audit the new collision primitive'
                half = np.array([float(cylinder.get('radius'))]*2 + [float(cylinder.get('length'))/2])
            center = position + orientation @ offset
            extent = abs(orientation @ rotation(angles)) @ half
            bounds.extend([center - extent, center + extent])
    bounds = np.array(bounds)
    config = yaml.safe_load((Path(__file__).parents[1] / 'config/nav2_params.yaml').read_text())
    for name in ['local_costmap', 'global_costmap']:
        params = config[name][name]['ros__parameters']
        footprint = np.array(ast.literal_eval(params['footprint']))
        assert np.all(bounds[:, :2].min(axis=0) >= footprint.min(axis=0))
        assert np.all(bounds[:, :2].max(axis=0) <= footprint.max(axis=0))
        radius = np.linalg.norm(np.abs(footprint).max(axis=0) + params['footprint_padding'])
        assert params['inflation_layer']['inflation_radius'] >= radius + 0.05
    local = config['local_costmap']['local_costmap']['ros__parameters']['voxel_layer']
    assert bounds[:, 2].max() <= local['max_obstacle_height']
    assert bounds[:, 2].max() <= local['z_resolution'] * local['z_voxels']


def test_map_spawn_registration():
    directory = Path(__file__).parents[1] / 'maps/restaurant'
    alignment = yaml.safe_load((directory / 'world_alignment.yaml').read_text())['world_from_map']
    dock = yaml.safe_load((directory / 'locations.yaml').read_text())['dock']
    assert alignment == {'x': 11.22, 'y': 6.95, 'yaw': 0.0}
    assert math.isclose(alignment['x'] + dock['x'], 7.59)
    assert math.isclose(alignment['y'] + dock['y'], 7.80)


def test_drive_reference_at_skid_steer_centre():
    """Encoder selection does not move the virtual four-wheel drive centre."""
    source = Path(get_package_share_directory('cstam_robot')) / 'urdf/cstam_robot.urdf.xacro'
    root = ET.fromstring(xacro.process_file(str(source)).toxml())
    axle = np.mean([np.fromstring(root.find(
        f"joint[@name='{side}_{position}_wheel_joint']/origin").get('xyz'), sep=' ')
        for side in ['left', 'right'] for position in ['front', 'rear']], axis=0)
    launch = ast.parse((Path(__file__).parents[1] / 'launch/phase1.launch.py').read_text())
    for call in ast.walk(launch):
        if not isinstance(call, ast.Call):
            continue
        keywords = {item.arg: item.value for item in call.keywords}
        name = keywords.get('name')
        if isinstance(name, ast.Constant) and name.value == 'cstam_drive_reference_tf':
            arguments = ast.literal_eval(keywords['arguments'])
            assert arguments[-2:] == ['base_drive', 'base_footprint']
            assert np.allclose(np.array(arguments[:2], dtype=float), -axle[:2])
            assert float(arguments[2]) == 0.0  # Both references are ground projections.
            return
    raise AssertionError('Drive-reference transform missing')
