"""Voice / typed order understanding."""
import os

import pytest

from cstam_ui.catalog import Catalog
from cstam_ui.voice import normalize, OrderParser


PACKAGE = os.path.dirname(os.path.dirname(__file__))
CATALOG = Catalog(os.path.join(PACKAGE, '..', 'cstam_phase1', 'maps', 'restaurant', 'locations.yaml'),
                  os.path.join(PACKAGE, 'config', 'menu.yaml'))
PARSER = OrderParser(CATALOG.menu, [p['name'] for p in CATALOG.delivery_locations()])


def heard(text):
    result = PARSER.parse(text)
    return {i['id']: i['qty'] for i in result['items']}, result['location']


@pytest.mark.parametrize('text, items, location', [
    ('Two cappuccinos and a brik for table 3', {'cappuccino': 2, 'brik': 1}, 'table_3'),
    ('I would like 3 espressos please', {'espresso': 3}, None),
    ('one coffee, one orange juice and two glasses of water', {'espresso': 1, 'fresh_juice': 1, 'water': 2}, None),
    ('Deux cafés et une citronnade pour la terrasse 2', {'espresso': 2, 'citronnade': 1}, 'terrace_2'),
    ('trois verres de jus d\'orange', {'fresh_juice': 3}, None),
    ('Couscous with lamb and makrout', {'couscous': 1, 'makroudh': 1}, None),
    ('a brik à l\'oeuf, then another brik', {'brik': 2}, None),
    ('Salade méchouia et deux bambalouni', {'salade_mechouia': 1, 'bambalouni': 2}, None),
    ('table two: a lemonade', {'citronnade': 1}, 'table_2'),
    ('café crème', {'cappuccino': 1}, None),
    ('un couscous à l\'agneau et une eau minérale', {'couscous': 1, 'water': 1}, None),
])
def test_orders_are_understood(text, items, location):
    assert heard(text) == (items, location)


def test_unknown_things_are_ignored():
    assert heard('can I have a pizza at table 9') == ({}, None)
    assert heard('') == ({}, None)


def test_quantities_are_capped_and_order_is_kept():
    result = PARSER.parse('99 waters and one espresso')
    assert [(i['id'], i['qty']) for i in result['items']] == [('water', 20), ('espresso', 1)]
    assert result['items'][0]['name'] == 'Mineral water'


def test_normalize_strips_accents_and_punctuation():
    assert normalize("Brik à l'œuf, S'IL vous plaît!") == ['brik', 'a', 'l', 'oeuf', 's', 'il', 'vous', 'plait']
