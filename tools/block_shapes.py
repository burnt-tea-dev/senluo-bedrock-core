"""Compact native block bounds while preserving state, visuals and saved data.

This shared build operation applies to addon-owned block definitions; it does
not require a server, addon combination or release-specific profile.
"""
import copy
import json

FIELDS = ('minecraft:collision_box', 'minecraft:selection_box')


def compact_block(value, *, allow_empty=False):
    result = copy.deepcopy(value)
    block = result['minecraft:block']
    rows = [block['components'], *[p['components'] for p in block.get('permutations', [])]]
    for field in FIELDS:
        values = [row[field] for row in rows if field in row]
        if not values:
            continue
        # A permanently non-solid decoration remains non-solid. Interactive
        # blocks that switch solidity require a separate semantic decision.
        if allow_empty and any(not isinstance(v, bool) for v in values):
            values = [v for v in values if v is not False]
        if any(isinstance(v, bool) for v in values):
            if not all(v is values[0] for v in values):
                raise ValueError('Selected block changes enabled shape: ' + block['description']['identifier'])
            bound = values[0]
        else:
            boxes = [box for v in values for box in (v if isinstance(v, list) else [v])]
            lo = [min(box['origin'][i] for box in boxes) for i in range(3)]
            hi = [max(box['origin'][i] + box['size'][i] for box in boxes) for i in range(3)]
            bound = {'origin': lo, 'size': [hi[i] - lo[i] for i in range(3)]}
        if (field == 'minecraft:collision_box' and isinstance(bound, dict)
                and tuple(map(int, value['format_version'].split('.'))) >= (1, 26, 60)):
            bound = [bound]
        block['components'][field] = bound
        for permutation in block.get('permutations', []):
            permutation['components'].pop(field, None)
    if 'permutations' in block:
        block['permutations'] = [p for p in block['permutations'] if p['components']]
    return result


