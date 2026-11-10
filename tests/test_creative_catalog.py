"""Native menu/catalog behavior from reduced, local author input fragments."""
import copy
import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from creative_catalog import CATALOG, catalog_delegations, regroup_creative


def raw(value):
    return json.dumps(value, ensure_ascii=False).encode()


def definition(identifier, menu, components=None, kind='item', format_version='1.21.10'):
    return raw({'format_version': format_version, 'minecraft:' + kind: {
        'description': {'identifier': identifier, 'menu_category': menu},
        'components': components or {}}})


def rules():
    # Shared icons are vanilla IDs, so this BP needs no Tavern/Cookery icon pack.
    groups = {
        'ingredients': ('items', 'kaleidoscope_cookery:itemGroup.name.ingredients', 'minecraft:wheat', '食材'),
        'bakery': ('items', 'senluo:creative.bakery', 'minecraft:bread', '烘焙'),
        'firearms': ('equipment', 'senluo:creative.firearms', 'minecraft:bow', '槍械'),
        'armor': ('equipment', 'senluo:creative.armor', 'minecraft:iron_chestplate', '護甲'),
        'workbenches': ('items', 'krep:itemGroup.name.workbenches', 'minecraft:smithing_table', '槍械工作台'),
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


def catalog(items):
    return raw({'format_version': '1.21.60', 'minecraft:crafting_items_catalog': {
        'categories': [{'category_name': 'items', 'groups': [{'items': items}]}]}})


class CreativeCatalogTests(unittest.TestCase):
    def test_legacy_biomes_block_without_menu_keeps_its_actual_catalog_group(self):
        # Reduced shape of the selected BB 1.21.0 tall_dead_bush definition.
        # Its omitted menu is a default-visible entry, not an internal variant.
        block = {'format_version': '1.21.0', 'minecraft:block': {
            'description': {'identifier': 'bb:tall_dead_bush'},
            'components': {'minecraft:collision_box': False}}}
        group = {'name': 'bb:itemGroup.name.desert_plants', 'icon': 'bb:apache_plume'}
        files = {'blocks/bush.json': raw(block), CATALOG: raw({
            'format_version': '1.21.60', 'minecraft:crafting_items_catalog': {'categories': [{
                'category_name': 'nature', 'groups': [{'group_identifier': group, 'items': ['bb:tall_dead_bush']}]}]}})}
        result = regroup_creative(files, rules())
        output = {**files, **result['updates']}
        self.assertEqual(contents(output), [('nature', group, 'bb:tall_dead_bush')])
        self.assertEqual(result['hidden'], [])
        self.assertNotIn('blocks/bush.json', result['updates'])
        self.assertEqual(regroup_creative(output, rules())['updates'], {})

    def test_legacy_omitted_category_defaults_to_items_and_accepts_explicit_rules(self):
        for menu in (None, {}, {'category': ''}):
            with self.subTest(menu=menu):
                block = {'format_version': '1.21.0', 'minecraft:block': {
                    'description': {'identifier': 'bb:red_mushrooms_group'},
                    'components': {'minecraft:collision_box': False}}}
                if menu is not None:
                    block['minecraft:block']['description']['menu_category'] = menu
                files = {'blocks/mushrooms.json': raw(block)}
                result = regroup_creative(files, rules())
                self.assertEqual(contents({**files, **result['updates']}), [('items', {}, 'bb:red_mushrooms_group')])
                self.assertEqual(result['hidden'], [])
                self.assertNotIn('blocks/mushrooms.json', result['updates'])
                plan = rules()
                plan['items'] = {'bb:red_mushrooms_group': 'ingredients'}
                result = regroup_creative(files, plan)
                output = {**files, **result['updates']}
                expected = copy.deepcopy(block)
                expected['minecraft:block']['description']['menu_category'] = {'category': 'items'}
                self.assertEqual(json.loads(output['blocks/mushrooms.json']), expected)
                self.assertEqual(contents(output)[0][1]['name'], 'kaleidoscope_cookery:itemGroup.name.ingredients')

    def test_explicit_none_and_modern_omitted_categories_remain_hidden(self):
        for version, menu in [('1.21.0', {'category': 'none'}),
                              ('1.21.60', None), ('1.21.100', {}),
                              ('1.21.60', {'category': 'none'})]:
            with self.subTest(version=version, menu=menu):
                document = {'format_version': version, 'minecraft:block': {
                    'description': {'identifier': 'local:hidden'}, 'components': {}}}
                if menu is not None:
                    document['minecraft:block']['description']['menu_category'] = menu
                files = {'blocks/hidden.json': raw(document), CATALOG: catalog(['local:hidden'])}
                plan = rules()
                plan['items'] = {'local:hidden': 'ingredients'}
                result = regroup_creative(files, plan)
                self.assertEqual(contents({**files, **result['updates']}), [])
                self.assertNotIn('blocks/hidden.json', result['updates'])
                self.assertEqual(result['hidden'], ['local:hidden'])

    def test_legacy_block_uses_catalog_group_without_changing_its_gameplay_format(self):
        # Reduced TACZ 1.20.70 workbench definition: its legacy properties and
        # crafting components must not be migrated just to move its menu entry.
        document = {'format_version': '1.20.70', 'minecraft:block': {
            'description': {'identifier': 'krep:ammoworkbench',
                            'properties': {'wiki:rotation': [0, 1, 2, 3]},
                            'menu_category': {'category': 'equipment', 'group': 'itemGroup.name.craftingTables'}},
            'components': {'minecraft:crafting_table': {'table_name': 'ammo', 'crafting_tags': ['ammo']}}}}
        files = {'blocks/ammo.json': raw(document)}
        plan = rules()
        plan['items'] = {'krep:ammoworkbench': 'workbenches'}
        result = regroup_creative(files, plan)
        output = {**files, **result['updates']}
        expected = copy.deepcopy(document)
        expected['minecraft:block']['description']['menu_category'] = {'category': 'items'}
        self.assertEqual(json.loads(output['blocks/ammo.json']), expected)
        self.assertEqual(contents(output), [('items', {
            'name': 'krep:itemGroup.name.workbenches', 'icon': 'minecraft:smithing_table'}, 'krep:ammoworkbench')])
        self.assertEqual(regroup_creative(output, plan)['updates'], {})

    def test_modern_definition_keeps_the_namespaced_group(self):
        for version in ('1.21.60', '1.21.100'):
            with self.subTest(version=version):
                files = {'blocks/ammo.json': definition('krep:ammoworkbench',
                    {'category': 'equipment'}, kind='block', format_version=version)}
                plan = rules()
                plan['items'] = {'krep:ammoworkbench': 'workbenches'}
                output = {**files, **regroup_creative(files, plan)['updates']}
                self.assertEqual(json.loads(output['blocks/ammo.json'])['minecraft:block']['description']['menu_category'],
                                 {'category': 'items', 'group': 'krep:itemGroup.name.workbenches'})

    def test_effective_definition_catalog_owns_the_item_across_real_pack_maps(self):
        item = 'kaleidoscope_cookery:flour'
        # The higher-priority catalog-only pack must defer to the actual
        # definition owner's catalog, rather than claiming the first mention.
        packs = [{CATALOG: catalog([item])},
                 {CATALOG: catalog([item]), 'items/flour.json': definition(item, {'category': 'equipment'})}]
        delegations = catalog_delegations(packs)
        self.assertEqual(delegations, [{item}, set()])
        outputs, results = [], []
        plan = rules()
        plan['items'] = {item: 'ingredients'}
        for files, delegated in zip(packs, delegations):
            result = regroup_creative(files, plan, cataloged_elsewhere=delegated)
            results.append(result)
            outputs.append({**files, **result['updates']})
        self.assertEqual([row[2] for output in outputs for row in contents(output)], [item])
        self.assertEqual(results[0]['delegated'], [{'identifier': item, 'category': 'items',
                                                  'group': 'kaleidoscope_cookery:itemGroup.name.ingredients'}])
        self.assertEqual(results[0]['hidden'], [])
        self.assertEqual(results[0]['unmapped'], [])

    def test_catalog_only_fallback_and_delegated_definition_updates(self):
        item = 'kaleidoscope_cookery:flour'
        # An effective definition without its own catalog falls back to the
        # first genuine catalog declarer. It still receives its menu update.
        packs = [{'items/flour.json': definition(item, {'category': 'equipment'}, format_version='1.21.60'),
                  'items/internal.json': definition('local:internal', {'category': 'none'})},
                 {CATALOG: catalog([item, 'minecraft:apple'])},
                 {CATALOG: catalog([item, 'minecraft:apple'])}]
        delegations = catalog_delegations(packs)
        self.assertEqual(delegations, [{item, 'minecraft:apple'}, set(), {item, 'minecraft:apple'}])
        plan = rules()
        plan['items'] = {item: 'ingredients', 'local:internal': 'ingredients'}
        delegations[0].add('local:internal')
        results = [regroup_creative(files, plan, cataloged_elsewhere=delegated)
                   for files, delegated in zip(packs, delegations)]
        output = {**packs[0], **results[0]['updates']}
        self.assertEqual(json.loads(output['items/flour.json'])['minecraft:item']['description']['menu_category'],
                         {'category': 'items', 'group': 'kaleidoscope_cookery:itemGroup.name.ingredients'})
        self.assertEqual(results[0]['labels']['zh_TW']['kaleidoscope_cookery:itemGroup.name.ingredients'], '食材')
        self.assertNotIn(CATALOG, output)
        self.assertEqual(results[0]['hidden'], ['local:internal'])
        self.assertEqual([row['identifier'] for row in results[0]['delegated']], [item])
        combined = []
        for files, result in zip(packs, results):
            output = {**files, **result['updates']}
            if CATALOG in output:
                combined.extend(row[2] for row in contents(output))
        self.assertCountEqual(combined, [item, 'minecraft:apple'])

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
