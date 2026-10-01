"""Keep the evaluator GUI compatible with Harmonic and free of drive commands."""

from pathlib import Path
import re
import xml.etree.ElementTree as ET

from ament_index_python.packages import get_package_share_directory


def test_restaurant_gui_contract():
    source = (Path(get_package_share_directory('andino_gz')) /
              'config_gui/restaurant.config').read_text()
    # Gazebo GUI configs are XML fragments with several top-level elements.
    root = ET.fromstring('<config>' + re.sub(r'<\?xml.*?\?>', '', source) + '</config>')
    plugins = root.findall('plugin')
    assert plugins
    assert all(p.find('gz-gui') is not None for p in plugins)
    assert all(p.find('ignition-gui') is None for p in plugins)
    assert not any(p.get('filename') == 'Teleop' for p in plugins)
    scene = root.find("plugin[@filename='MinimalScene']")
    assert scene.find('engine').text == 'ogre2'
    # MinimalScene's FOV configuration is in degrees, unlike SDF cameras.
    assert float(scene.find('horizontal_fov').text) == 80.0
    assert len(scene.find('camera_pose').text.split()) == 6
