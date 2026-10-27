"""Understand a spoken (or typed) order: menu items, quantities and a table.

"two cappuccinos and a brik for table 3" ->
    items [Cappuccino x2, Brik x1], location table_3.
English and French number words; menu names plus the aliases in menu.yaml;
accents, case and plurals ignored. Nothing is ordered here: the page puts
the result in the cart and the guest confirms.
"""

import re
import unicodedata


NUMBERS = {
    # English
    'a': 1, 'an': 1, 'one': 1, 'two': 2, 'three': 3, 'four': 4, 'five': 5, 'six': 6,
    'seven': 7, 'eight': 8, 'nine': 9, 'ten': 10, 'couple': 2, 'pair': 2,
    # French
    'un': 1, 'une': 1, 'deux': 2, 'trois': 3, 'quatre': 4, 'cinq': 5, 'sept': 7,
    'huit': 8, 'neuf': 9, 'dix': 10,
}
# Words between a number and the item ("two cups of tea", "deux verres de").
FILLERS = {'of', 'cup', 'cups', 'glass', 'glasses', 'bottle', 'bottles', 'plate', 'plates',
           'portion', 'portions', 'de', 'd', 'du', 'des', 'tasse', 'tasses', 'verre', 'verres',
           'bouteille', 'bouteilles', 'assiette', 'assiettes', 'more', 'other', 'big', 'small'}
PLACES = {'table': 'table', 'tables': 'table', 'terrace': 'terrace', 'terrasse': 'terrace'}
MAX_QTY = 20


LIGATURES = str.maketrans({'œ': 'oe', 'æ': 'ae', 'ß': 'ss'})   # not split by NFKD


def normalize(text):
    text = unicodedata.normalize('NFKD', text.lower().translate(LIGATURES))
    text = ''.join(c for c in text if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", ' ', text).split()


def _singular(word):
    return word[:-1] if len(word) > 3 and word.endswith('s') else word


class OrderParser:
    def __init__(self, menu, location_names):
        """menu: [{'id', 'name', 'aliases', 'names'}]; location_names: e.g. table_1."""
        self.locations = set(location_names)
        self.phrases = []   # (tokens, item) longest first
        for item in menu:
            # Translated names too; Arabic ones normalise to nothing and drop out.
            for phrase in [item['name'], *item.get('aliases', []), *item.get('names', {}).values()]:
                tokens = [_singular(t) for t in normalize(phrase)]
                if tokens:
                    self.phrases.append((tokens, item))
        self.phrases.sort(key=lambda p: -len(p[0]))

    def _number(self, token):
        if token.isdigit():
            return int(token)
        return NUMBERS.get(token)

    def parse(self, text):
        tokens = normalize(text)
        stems = [_singular(t) for t in tokens]
        quantities, order, used = {}, [], set()
        location = None
        i = 0
        while i < len(tokens):
            # "table 3" / "terrace two" / "terrasse 1"
            if tokens[i] in PLACES and i + 1 < len(tokens):
                number = self._number(tokens[i + 1])
                name = f'{PLACES[tokens[i]]}_{number}' if number else None
                if name in self.locations:
                    location = name
                    used.update((i, i + 1))
                    i += 2
                    continue
            match = next((p for p in self.phrases if stems[i:i + len(p[0])] == p[0]), None)
            if match is None:
                i += 1
                continue
            tokens_len, item = len(match[0]), match[1]
            qty, j = 1, i - 1
            while j >= 0 and tokens[j] in FILLERS and j not in used:
                j -= 1
            if j >= 0 and j not in used and self._number(tokens[j]) is not None:
                qty = self._number(tokens[j])
                used.add(j)
            used.update(range(i, i + tokens_len))
            if item['id'] not in quantities:
                order.append(item)
            quantities[item['id']] = min(MAX_QTY, quantities.get(item['id'], 0) + max(1, qty))
            i += tokens_len
        return {
            'transcript': text.strip(),
            'items': [{'id': item['id'], 'name': item['name'], 'qty': quantities[item['id']]}
                      for item in order],
            'location': location,
        }
