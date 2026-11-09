"""Native menu/catalog behavior from reduced, local author input fragments."""
import copy
import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from creative_catalog import CATALOG, regroup_creative


def raw(value):
    return json.dumps(value, ensure_ascii=False).encode()


def definition(identifier, menu, components=None, kind='item'):
    return raw({'format_version': '1.21.10', 'minecraft:' + kind: {
        'description': {'identifier': identifier, 'menu_category': menu},
        'components': components or {}}})


def rules():
    # Shared icons are vanilla IDs, so this BP needs no Tavern/Cookery icon pack.
    groups = {
        'ingredients': ('items', 'kaleidoscope_cookery:itemGroup.name.ingredients', 'minecraft:wheat', '食材'),
        'bakery': ('items', 'senluo:creative.bakery', 'minecraft:bread', '烘焙'),
        'firearms': ('equipment', 'senluo:creative.firearms', 'minecraft:bow', '槍械'),
        'armor': ('equipment', 'senluo:creative.armor', 'minecraft:iron_chestplate', '護甲'),
    }
    return {'groups': {alias: {'category': c, 'name': n, 'icon': i, 'labels': {'zh_TW': label}}
                       for alias, (c, n, i, label) in groups.items()},
            'group_moves': {'kaleidoscope_cookery:itemGroup.name.ingredients': 'ingredients',
                            'krep:itemGroup.name.ar': 'firearms'},
            'components': {'food': 'bakery', 'wearable': 'armor'}}


def contents(files):
    return [(category['category_name'], group.get('group_identifier', {}), item)
            for category in json.loads(files[CATALOG])['minecraft:crafting_items_catalog']['categories']
            for group in category['groups'] for item in group['items']]


class CreativeCatalogTests(unittest.TestCase):
    def test_real_author_menu_and_component_facts_use_one_native_catalog(self):
        # Description/component facts from selected Cookery flour, TACZ AKM,
        # Baking pumpkin_mini_pie and AWW basic_spell_book. No author assets ship.
        files = {
            'items/flour.json': definition('kaleidoscope_cookery:flour', {
                'category': 'equipment', 'group': 'kaleidoscope_cookery:itemGroup.name.ingredients'}),
            'items/akm.json': definition('krep:akm', {'category': 'equipment'}, {
                'minecraft:food': {'can_always_eat': True}}),
            'items/pumpkin_mini_pie.json': definition('kaleidoscope_baking:pumpkin_mini_pie', {'category': 'items'}, {
                'minecraft:food': {'nutrition': 5, 'saturation_modifier': 0.6, 'can_always_eat': False},
                'minecraft:use_animation': 'eat'}),
            'items/book.json': definition('aww:basic_spell_book', {
                'category': 'equipment', 'group': 'aww:creative.spell_book'}, {
                    'minecraft:wearable': {'slot': 'slot.weapon.offhand'}}),
            CATALOG: raw({'format_version': '1.21.60', 'minecraft:crafting_items_catalog': {'categories': [{
                'category_name': 'equipment', 'groups': [
                    {'group_identifier': {'name': 'krep:itemGroup.name.ar', 'icon': 'krep:akm'}, 'items': ['krep:akm']},
                    {'group_identifier': {'name': 'aww:creative.spell_book', 'icon': 'aww:basic_spell_book'}, 'items': ['aww:basic_spell_book']}
                ]}]}}),
            'recipes/pie.json': b'{"recipe":"untouched"}',
            'manifest.json': b'{"identity":"untouched"}',
        }
        original = copy.deepcopy(files)
        result = regroup_creative(files, rules())
        output = {**files, **result['updates']}
        rows = {item: (category, group) for category, group, item in contents(output)}
        self.assertEqual(rows['kaleidoscope_cookery:flour'][0], 'items')
        self.assertEqual(rows['krep:akm'][1], {'name': 'senluo:creative.firearms', 'icon': 'minecraft:bow'})
        self.assertEqual(rows['kaleidoscope_baking:pumpkin_mini_pie'][1]['name'], 'senluo:creative.bakery')
        self.assertEqual(rows['aww:basic_spell_book'][1]['name'], 'aww:creative.spell_book')
        self.assertNotIn('items/book.json', result['updates'])
        self.assertEqual(result['labels']['zh_TW']['senluo:creative.bakery'], '烘焙')
        for path in files:
            if path.startswith('items/'):
                self.assertEqual(json.loads(output[path])['minecraft:item']['components'],
                                 json.loads(files[path])['minecraft:item']['components'])
        self.assertEqual(files, original)
        self.assertNotIn('recipes/pie.json', result['updates'])
        self.assertNotIn('manifest.json', result['updates'])
        self.assertEqual(regroup_creative(output, rules())['updates'], {})

    def test_hidden_half_stays_hidden_and_duplicate_ids_have_one_entry(self):
        visible = definition('local:cup', {'category': 'equipment'})
        hidden = definition('local:cup', {'category': 'none'}, kind='block')
        files = {'items/cup.json': visible, 'blocks/cup.json': hidden,
                 'items/internal.json': definition('local:internal', {'category': 'none'})}
        plan = rules()
        plan['items'] = {'local:cup': 'ingredients', 'local:internal': 'ingredients'}
        result = regroup_creative(files, plan)
        output = {**files, **result['updates']}
        self.assertEqual([row[2] for row in contents(output)], ['local:cup'])
        self.assertEqual(output['blocks/cup.json'], hidden)
        self.assertNotIn('items/internal.json', result['updates'])
        self.assertIn('local:internal', result['hidden'])

    def test_unknown_items_and_zero_nutrition_input_hooks_remain_unclassified(self):
        files = {'items/hook.json': definition('external:input_hook', {'category': 'equipment'}, {
            'minecraft:food': {'can_always_eat': True}}),
                 'items/unknown.json': definition('external:unknown', {'category': 'nature'}),
                 'items/commented.json': b'{// source JSONC kept local\n}'}
        result = regroup_creative(files, rules())
        self.assertEqual({row['identifier'] for row in result['unmapped']}, {'external:input_hook', 'external:unknown'})
        self.assertNotIn('items/hook.json', result['updates'])
        self.assertNotIn('items/unknown.json', result['updates'])
        self.assertEqual(result['unparsed_files'], ['items/commented.json'])

    def test_explicit_tags_and_ids_win_without_substring_matching(self):
        files = {'items/tool.json': definition('external:bread_named_tool', {'category': 'equipment'}, {
            'minecraft:tags': {'tags': ['external:reviewed_tool']}})}
        plan = rules()
        plan['tags'] = {'external:reviewed_tool': 'firearms'}
        plan['items'] = {'external:bread_named_tool': 'armor'}
        output = {**files, **regroup_creative(files, plan)['updates']}
        self.assertEqual(contents(output)[0][1]['name'], 'senluo:creative.armor')

    def test_unresolved_cross_pack_catalog_entries_are_preserved(self):
        files = {CATALOG: raw({'format_version': '1.21.60', 'minecraft:crafting_items_catalog': {'categories': [{
            'category_name': 'nature', 'groups': [{'items': ['minecraft:apple', 'minecraft:apple']}]}]}})}
        output = {**files, **regroup_creative(files, rules())['updates']}
        self.assertEqual(contents(output), [('nature', {}, 'minecraft:apple')])

    def test_custom_icon_dependencies_are_rejected_before_building_shared_groups(self):
        plan = rules()
        plan['groups']['ingredients']['icon'] = 'some_other_pack:unavailable_icon'
        with self.assertRaisesRegex(ValueError, 'vanilla icon'):
            regroup_creative({}, plan)


if __name__ == '__main__':
    unittest.main()
