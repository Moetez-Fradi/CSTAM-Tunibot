"""Keep deliberate heading alignment subject to physical and progress limits."""
import math
from pathlib import Path
import xml.etree.ElementTree as ET

import yaml


def test_heading_alignment_contract():
    package = Path(__file__).parents[1]
    params = yaml.safe_load((package / 'config/nav2_params.yaml').read_text())
    controller = params['controller_server']['ros__parameters']
    follow = controller['FollowPath']
    progress = controller['progress_checker']
    assert follow['plugin'] == 'nav2_rotation_shim_controller::RotationShimController'
    assert follow['primary_controller'] == 'dwb_core::DWBLocalPlanner'
    assert follow['rotate_to_goal_heading']
    assert progress['plugin'] == 'nav2_controller::PoseProgressChecker'
    assert 0 < progress['required_movement_angle'] < math.pi
    speed = follow['rotate_to_heading_angular_vel']
    assert 0 < speed <= follow['max_vel_theta']
    assert follow['max_angular_accel'] <= follow['acc_lim_theta']
    # Include acceleration/deceleration in the worst half-turn duration.
    assert math.pi / speed + speed / follow['max_angular_accel'] < progress['movement_time_allowance']
    manifest = ET.parse(package / 'package.xml').getroot()
    assert 'nav2_rotation_shim_controller' in [item.text for item in manifest.findall('exec_depend')]
