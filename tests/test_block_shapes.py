import copy
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import unittest
from block_shapes import compact_block, FIELDS


class NativeQuantityShapes(unittest.TestCase):
    def test_native_visuals_states_and_storage_survive_with_containing_bounds(self):
        small = {'origin': [-4, 0, -4], 'size': [8, 2, 8]}
        large = {'origin': [-6, 0, -5], 'size': [12, 7, 10]}
        source = {'format_version': '1.26.50', 'minecraft:block': {'description': {'identifier': 'test:food', 'states': {'test:quantity': [0, 1]}},
                  'components': {FIELDS[0]: small, FIELDS[1]: small, 'minecraft:block_entity': {'container': {'slot_count': 36}}},
                  'permutations': [{'condition': "q.block_state('test:quantity') == 1", 'components':
                                   {FIELDS[0]: [large], FIELDS[1]: large, 'minecraft:geometry': {'identifier': 'geometry.food', 'bone_visibility': {'food': True}}}}]}}
        before = copy.deepcopy(source)
        result = compact_block(source)
        self.assertEqual(source, before)
        block = result['minecraft:block']
        self.assertEqual(block['components'][FIELDS[0]], large)
        self.assertEqual(block['components'][FIELDS[1]], large)
        for value in (before, result):
            b = value['minecraft:block']
            for row in [b['components'], *[p['components'] for p in b['permutations']]]:
                for field in FIELDS: row.pop(field, None)
        self.assertEqual(result, before)

    def test_non_solid_decoration_stays_non_solid(self):
        source = {'format_version': '1.26.50', 'minecraft:block': {'description': {'identifier': 'test:ribbon'}, 'components':
                  {FIELDS[0]: False, FIELDS[1]: {'origin': [-1, 0, -1], 'size': [2, 4, 2]}}}}
        self.assertIs(compact_block(source)['minecraft:block']['components'][FIELDS[0]], False)

    def test_switching_solidity_is_not_silently_changed(self):
        source = {'format_version': '1.26.50', 'minecraft:block': {'description': {'identifier': 'test:door'}, 'components': {FIELDS[0]: False},
                  'permutations': [{'condition': 'true', 'components': {FIELDS[0]: {'origin': [-1, 0, -1], 'size': [2, 4, 2]}}}]}}
        with self.assertRaisesRegex(ValueError, 'changes enabled shape'): compact_block(source)

    def test_current_native_schema_keeps_a_single_collision_in_an_array(self):
        box = {'origin': [-8, 0, -8], 'size': [16, 24, 16]}
        source = {'format_version': '1.26.60', 'minecraft:block': {'description': {'identifier': 'test:freezer'},
                  'components': {FIELDS[0]: [box], FIELDS[1]: {'origin': [-8, 0, -8], 'size': [16, 16, 16]}}}}
        block = compact_block(source)['minecraft:block']
        self.assertEqual(block['components'][FIELDS[0]], [box])
        self.assertIsInstance(block['components'][FIELDS[1]], dict)


if __name__ == '__main__': unittest.main()
