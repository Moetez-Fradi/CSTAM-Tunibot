import pathlib

import yaml


def test_locations_are_first_floor_and_complete():
    locations_file = pathlib.Path(__file__).parents[1] / 'maps' / 'restaurant' / 'locations.yaml'
    data = yaml.safe_load(locations_file.read_text(encoding='utf-8'))
    assert data['supported_floors'] == [1]
    for name in ('dock', 'kitchen', 'table_1'):
        assert name in data
        assert data[name]['floor'] == 1
        assert all(key in data[name] for key in ('x', 'y', 'yaw'))


def test_locations_have_distinct_semantic_names():
    locations_file = pathlib.Path(__file__).parents[1] / 'maps' / 'restaurant' / 'locations.yaml'
    data = yaml.safe_load(locations_file.read_text(encoding='utf-8'))
    names = [name for name, value in data.items() if isinstance(value, dict)]
    assert len(names) == len(set(names))
