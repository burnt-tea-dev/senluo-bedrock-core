import copy
import json
from pathlib import Path
import subprocess
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from install_player_presentation import (LEFT_ARM_REQUEST, advance_manifest,
                                        compose_first_person_arm_request, modern_tacz_player)


class FirstPersonArmRequestTests(unittest.TestCase):
    def fixture(self):
        player = {'format_version': '1.10.0', 'minecraft:client_entity': {'description': {
            'identifier': 'minecraft:player',
            'scripts': {'pre_animation': ['v.holding_all_guns=q.is_item_name_any("slot.weapon.mainhand",0,"gun:item");'],
                        'animate': ['native', {'gun': 'v.holding_all_guns'}]},
            'render_controllers': [{'controller.render.player.first_person': '!v.holding_all_guns'},
                                   {'controller.render.gun': 'v.holding_all_guns'}],
            'geometry': {'default': 'geometry.humanoid.custom'},
            'animations': {'native': 'animation.player.first_person'}}}}
        controller = {'format_version': '1.8.0', 'render_controllers': {
            'controller.render.player.first_person': {
                'geometry': 'Geometry.default', 'materials': [{'default': 'Material.default'}],
                'part_visibility': [{'*': False}, {'rightArm': '!v.hide_right'},
                                    {'rightSleeve': '!v.hide_right'},
                                    {'leftArm': 'q.is_using_item && v.map'},
                                    {'leftSleeve': 'v.map || v.eating_left'}]},
            'controller.render.gun': {'geometry': 'Geometry.gun'}}}
        return player, controller

    def test_request_extends_only_the_selected_left_arm_and_preserves_other_routes(self):
        player, controller = self.fixture()
        player_raw, controller_raw = (json.dumps(value).encode() for value in (player, controller))
        result_player, result_controller = map(json.loads,
            compose_first_person_arm_request(player_raw, controller_raw))
        reset = result_player['minecraft:client_entity']['description']['scripts']['pre_animation'].pop()
        self.assertEqual(reset, LEFT_ARM_REQUEST + '=0.0;')
        parts = result_controller['render_controllers']['controller.render.player.first_person']['part_visibility']
        self.assertEqual(parts[3]['leftArm'], '(q.is_using_item && v.map) || ' + LEFT_ARM_REQUEST)
        self.assertEqual(parts[4]['leftSleeve'], '(v.map || v.eating_left) || ' + LEFT_ARM_REQUEST)
        parts[3:5] = controller['render_controllers']['controller.render.player.first_person']['part_visibility'][3:5]
        self.assertEqual(result_player, player)
        self.assertEqual(result_controller, controller)
        self.assertEqual(json.loads(player_raw), player)
        self.assertEqual(json.loads(controller_raw), controller)

    def test_retained_selected_pair_does_not_accumulate_fragments(self):
        inputs = tuple(json.dumps(value).encode() for value in self.fixture())
        first = compose_first_person_arm_request(*inputs)
        self.assertEqual(compose_first_person_arm_request(*first), first)

    def test_partial_pair_cannot_silently_leave_the_effective_renderer_unconnected(self):
        inputs = tuple(json.dumps(value).encode() for value in self.fixture())
        player, _ = compose_first_person_arm_request(*inputs)
        with self.assertRaisesRegex(ValueError, 'partial arm-request'):
            compose_first_person_arm_request(player, inputs[1])

    def test_two_providers_reset_and_request_independently_in_generated_expressions(self):
        inputs = tuple(json.dumps(value).encode() for value in self.fixture())
        channels = (LEFT_ARM_REQUEST, 'variable.other_fp_left_arm_request')
        player, controller = map(json.loads,
            compose_first_person_arm_request(*inputs, request_variables=channels))
        scripts = player['minecraft:client_entity']['description']['scripts']['pre_animation']
        parts = controller['render_controllers']['controller.render.player.first_person']['part_visibility']
        expressions = [parts[3]['leftArm'], parts[4]['leftSleeve']]
        # Execute the generated assignment/boolean subset. This checks source
        # composition, not Molang's client scheduling or actual rendering.
        program = r'''
const {scripts, expressions} = JSON.parse(require('node:fs').readFileSync(0, 'utf8'));
const variable = {senluo_fp_left_arm_request: 1, other_fp_left_arm_request: 1};
const v = variable;
const q = {is_using_item: false, is_item_name_any: () => false};
scripts.forEach(script => eval(script));
const reset = [variable.senluo_fp_left_arm_request, variable.other_fp_left_arm_request];
const results = [];
for (const [first, second, native] of [[1,0,0], [0,1,0], [0,0,0], [0,0,1]]) {
  variable.senluo_fp_left_arm_request = first;
  variable.other_fp_left_arm_request = second;
  q.is_using_item = Boolean(native);
  v.map = Boolean(native);
  results.push(expressions.map(expression => Boolean(eval(expression))));
}
process.stdout.write(JSON.stringify({reset, results}));
'''
        result = json.loads(subprocess.check_output(['node', '-e', program],
            input=json.dumps({'scripts': scripts, 'expressions': expressions}).encode()))
        self.assertEqual(result, {'reset': [0, 0],
            'results': [[True, True], [True, True], [False, False], [True, True]]})

    def test_existing_single_channel_can_gain_a_provider_without_duplicate_fragments(self):
        inputs = tuple(json.dumps(value).encode() for value in self.fixture())
        first = compose_first_person_arm_request(*inputs)
        channels = (LEFT_ARM_REQUEST, 'variable.other_fp_left_arm_request')
        upgraded = compose_first_person_arm_request(*first, request_variables=channels)
        self.assertEqual(upgraded, compose_first_person_arm_request(*inputs,
            request_variables=channels))
        self.assertEqual(compose_first_person_arm_request(*upgraded,
            request_variables=channels), upgraded)
        self.assertEqual(compose_first_person_arm_request(*upgraded), upgraded)

    def test_new_channel_partial_pair_is_rejected(self):
        inputs = tuple(json.dumps(value).encode() for value in self.fixture())
        channels = (LEFT_ARM_REQUEST, 'variable.other_fp_left_arm_request')
        player, controller = compose_first_person_arm_request(*inputs, request_variables=channels)
        single = compose_first_person_arm_request(*inputs)
        for pair in ((player, single[1]), (single[0], controller)):
            with self.subTest(pair=pair), self.assertRaisesRegex(ValueError, 'partial arm-request'):
                compose_first_person_arm_request(*pair, request_variables=channels)

    def test_variable_names_cannot_inject_expressions_or_alias_another_provider(self):
        inputs = tuple(json.dumps(value).encode() for value in self.fixture())
        for names in ((), LEFT_ARM_REQUEST, (LEFT_ARM_REQUEST, LEFT_ARM_REQUEST),
                      ('variable.a;variable.b=1',), ('variable.MixedCase',), (None,)):
            with self.subTest(names=names), self.assertRaises(ValueError):
                compose_first_person_arm_request(*inputs, request_variables=names)

    def test_provider_names_with_a_common_prefix_remain_separate(self):
        inputs = tuple(json.dumps(value).encode() for value in self.fixture())
        channels = ('variable.provider', 'variable.provider_long')
        first = compose_first_person_arm_request(*inputs, request_variables=channels)
        self.assertEqual(compose_first_person_arm_request(*first,
            request_variables=channels), first)
        player = json.loads(first[0])
        scripts = player['minecraft:client_entity']['description']['scripts']['pre_animation']
        self.assertEqual(scripts[-2:], [name + '=0.0;' for name in channels])


class PlayerManifestTests(unittest.TestCase):
    def test_modern_tacz_player_keeps_block_only_push_rule_and_other_data(self):
        actor = {'format_version': '1.26.30', 'minecraft:entity': {
            'description': {'identifier': 'minecraft:player', 'properties': {'gun:state': {'type': 'int'}}},
            'components': {'minecraft:pushable': {'is_pushable': False, 'is_pushable_by_piston': True},
                           'minecraft:pushable_by_block': {}, 'minecraft:health': {'value': 20}},
            'events': {'gun:keep': {'set_property': {'gun:state': 1}}}}}
        raw = json.dumps(actor).encode()
        result = json.loads(modern_tacz_player(raw))
        self.assertNotIn('minecraft:pushable', result['minecraft:entity']['components'])
        self.assertEqual(result['minecraft:entity']['components']['minecraft:pushable_by_block'], {})
        self.assertNotIn('minecraft:pushable_by_entity', result['minecraft:entity']['components'])
        result['minecraft:entity']['components']['minecraft:pushable'] = actor['minecraft:entity']['components']['minecraft:pushable']
        self.assertEqual(result, actor)
        self.assertEqual(json.loads(raw), actor)

    def test_pair_upgrade_preserves_ids_metadata_and_other_dependencies(self):
        original = {'header': {'uuid': 'original-bp', 'version': [1, 1, 0],
                               'min_engine_version': [1, 26, 1], 'name': 'Author name'},
                    'modules': [{'uuid': 'original-module', 'version': [1, 1, 0],
                                 'type': 'script', 'entry': 'scripts/main.js'}],
                    'dependencies': [{'uuid': 'original-rp', 'version': [1, 1, 0]},
                                     {'module_name': '@minecraft/server', 'version': '2.0.0'}],
                    'metadata': {'authors': ['Original author']}}
        raw = json.dumps(original).encode()
        companion = {'uuid': 'grilling-bp', 'version': [2, 8, 206]}
        result = json.loads(advance_manifest(raw, [1, 1, 20001],
            {'original-bp', 'original-rp'}, companion, [1, 26, 60]))
        self.assertEqual(result['header']['version'], [1, 1, 20001])
        self.assertEqual(result['header']['min_engine_version'], [1, 26, 60])
        self.assertEqual(result['modules'][0]['version'], [1, 1, 20001])
        self.assertEqual(result['dependencies'][0]['version'], [1, 1, 20001])
        restored = copy.deepcopy(result)
        restored['header'].update(version=[1, 1, 0], min_engine_version=[1, 26, 1])
        restored['modules'][0]['version'] = [1, 1, 0]
        restored['dependencies'][0]['version'] = [1, 1, 0]
        self.assertEqual(restored['dependencies'].pop(), companion)
        self.assertEqual(restored, original)
        self.assertEqual(json.loads(raw), original)

    def test_rejects_reused_identity_and_engine_downgrade(self):
        raw = json.dumps({'header': {'version': [1, 1, 0], 'min_engine_version': [1, 26, 60]},
                          'modules': [], 'dependencies': []}).encode()
        with self.assertRaisesRegex(ValueError, 'fresh increasing'):
            advance_manifest(raw, [1, 1, 0], set(), {'uuid': 'G', 'version': [2, 8, 206]})
        with self.assertRaisesRegex(ValueError, 'Cannot lower'):
            advance_manifest(raw, [1, 1, 20001], set(), {'uuid': 'G', 'version': [2, 8, 206]}, [1, 26, 1])


if __name__ == '__main__':
    unittest.main()
