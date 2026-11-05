import copy
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from hud_composer import compose_hud


class NativeHudComposition(unittest.TestCase):
    def setUp(self):
        self.native = {'namespace': 'hud', 'root_panel': {
            'type': 'panel', 'bindings': [{'binding_name': '#hud_visible'}],
            'controls': [{'title@hud.native_title': {'layer': 2}}, {'boss@hud.native_boss': {}}]},
            'native_title': {'type': 'label', 'text': '#title'}}

    def test_mounts_preserve_native_order_bindings_and_leaf_controls(self):
        original = copy.deepcopy(self.native)
        before = [{'optional@$overlay': {}}]
        after = [{'other@other.root': {}}]
        result = compose_hud(self.native, before=before, after=after,
                             providers={'$overlay': 'example.root'})
        self.assertEqual(result['root_panel']['controls'][0], {'optional@example.root': {}})
        self.assertEqual(result['root_panel']['controls'][1:3], original['root_panel']['controls'])
        self.assertEqual(result['root_panel']['controls'][-1], after[0])
        self.assertEqual(result['root_panel']['bindings'], original['root_panel']['bindings'])
        self.assertEqual(result['native_title'], original['native_title'])
        self.assertEqual(self.native, original)
        self.assertEqual(before, [{'optional@$overlay': {}}])

    def test_absent_addons_need_no_mounts_or_alternate_native_root(self):
        self.assertEqual(compose_hud(self.native), self.native)

    def test_added_definitions_resolve_nested_providers_without_touching_values(self):
        definitions = {'fallback': {'type': 'panel', 'controls': [{'nested@$overlay': {'text': '$overlay'}}]}}
        result = compose_hud(self.native, definitions=definitions, providers={'$overlay': 'example.root'})
        self.assertEqual(result['fallback']['controls'], [{'nested@example.root': {'text': '$overlay'}}])
        self.assertEqual(definitions['fallback']['controls'][0], {'nested@$overlay': {'text': '$overlay'}})

    def test_additions_cannot_replace_native_root_or_title(self):
        for name in ('root_panel', 'native_title'):
            with self.subTest(name=name), self.assertRaisesRegex(ValueError, 'overwrites a native definition'):
                compose_hud(self.native, definitions={name: {'type': 'panel'}})


if __name__ == '__main__':
    unittest.main()
