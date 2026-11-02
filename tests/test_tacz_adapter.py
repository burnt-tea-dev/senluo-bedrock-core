import copy
import json
from pathlib import Path
import sys
import subprocess
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from install_tacz import adapt_files, apply_archive, FP, OFFHAND_FP
from assemble_family import read_definition


def encoded(value):
    return json.dumps(value).encode()


class TaczAdapterTests(unittest.TestCase):
    def fixture(self):
        descriptor = {'toolkit_version': 'test', 'behavior_min_engine_version': [1, 26, 60],
                      'output_version': [1, 1, 20002],
                      'grilling': {'bp_uuid': 'g-bp', 'rp_uuid': 'g-rp', 'version': [2, 8, 206]},
                      'immersive_eating': {'bp_uuid': 'ie-bp', 'rp_uuid': 'ie-rp'},
                      'tacz': {'id': 'tacz:test', 'bp_uuid': 't-bp', 'rp_uuid': 't-rp',
                               'version': [1, 0, 3], 'output_version': [1, 0, 20002],
                               'prefixes': {'BP': 'Author BP/', 'RP': 'Author RP/'}}}
        originals = {}
        for side, uid, peer in [('BP', 't-bp', 't-rp'), ('RP', 't-rp', 't-bp')]:
            originals['Author ' + side + '/manifest.json'] = encoded({
                'format_version': 2,
                'header': {'uuid': uid, 'name': 'Author name', 'version': [1, 0, 3], 'min_engine_version': [1, 20, 0]},
                'modules': [{'uuid': uid + '-module', 'type': 'data' if side == 'BP' else 'resources', 'version': [1, 0, 3]}],
                'dependencies': [{'uuid': peer, 'version': [1, 0, 3]}, {'module_name': '@minecraft/server', 'version': '1.18.0'}],
                'metadata': {'authors': ['Original author']}})
        originals.update({'Author BP/entities/plalyer.json': b'original player',
                          'Author BP/entities/bullet/awp.json': b'// Original author comment.\n' + encoded({'minecraft:entity': {'components': {
                              'minecraft:break_blocks': {'breakable_blocks': ['glass', 'glass_panel', 'stained_glass', 'stained_glass_panel', 'wheat']},
                              'minecraft:physics': {}}}}),
                          'Author BP/scripts/main.js': b'original author script',
                          'Author RP/entity/player.entity.json': b'original client player',
                          'Author RP/animations/gun.json': b'original animation',
                          'Author RP/models/body.json': b'original model',
                          'Author RP/textures/skin.png': b'original pixels',
                          'Author RP/render_controllers/player.json': encoded({'render_controllers': {
                              FP: {'geometry': 'original-fp'}, 'controller.render.gun': {'geometry': 'unchanged-gun'},
                              'controller.render.player.universal.first_person': {'geometry':'Geometry.custom','part_visibility':[{'*':False},{'rightArm':'v.gun'},{'leftArm':'v.gun'},{'leftSleeve':'v.gun'}]}}})})
        schema = {'minecraft:entity': {'description': {'identifier': 'minecraft:player',
                  'properties': {'field:' + str(i): {'type': 'int', 'default': 0, 'range': [0, 1]} for i in range(28)}}}}
        composed = {'BP/entities/player.json': encoded(schema), 'RP/entity/player.entity.json': encoded({'minecraft:client_entity': {'description': {'identifier':'minecraft:player','render_controllers':[{FP:'v.is_first_person && !v.holding_all_guns'}]}}}),
                    'RP/animations/gun.json': b'conditioned left arm', 'RP/models/body.json': b'complete repaired model'}
        controller = encoded({'render_controllers': {FP: {'geometry': 'composed-nongun-fp', 'part_visibility':[{'*':False},{'rightArm':'v.right'},{'rightSleeve':'v.right'},{'leftArm':'v.left'},{'leftSleeve':'v.left'}]}}})
        return originals, composed, controller, descriptor

    def test_complete_pair_keeps_author_identity_scripts_pixels_and_gun_controller(self):
        originals, composed, controller, descriptor = self.fixture()
        before = copy.deepcopy(originals)
        result, receipt = adapt_files(originals, composed, controller, descriptor)
        self.assertEqual(originals, before)
        self.assertNotIn('Author BP/entities/plalyer.json', result)
        self.assertEqual(result['Author BP/entities/player.json'], composed['BP/entities/player.json'])
        self.assertTrue(result['Author BP/entities/bullet/awp.json'].startswith(b'// Original author comment.\n'))
        awp = read_definition(result['Author BP/entities/bullet/awp.json'])['minecraft:entity']['components']
        self.assertEqual(awp['minecraft:break_blocks']['breakable_blocks'],
                         ['glass', 'glass_pane', 'stained_glass', 'stained_glass_pane', 'wheat'])
        self.assertEqual(awp['minecraft:physics'], {})
        for name in ['Author BP/scripts/main.js', 'Author RP/textures/skin.png']:
            self.assertEqual(result[name], originals[name])
        self.assertEqual(result['Author RP/animations/gun.json'], composed['RP/animations/gun.json'])
        self.assertEqual(result['Author RP/models/body.json'], composed['RP/models/body.json'])
        controllers = json.loads(result['Author RP/render_controllers/player.json'])['render_controllers']
        self.assertEqual(controllers['controller.render.gun'], {'geometry': 'unchanged-gun'})
        self.assertEqual(controllers[FP], json.loads(controller)['render_controllers'][FP])
        gun=controllers['controller.render.player.universal.first_person']['part_visibility']
        self.assertEqual(gun[1], {'rightArm':'v.gun'})
        expression=gun[2]['leftArm']
        script="const f=Function('v','q','return '+process.argv[1]);process.stdout.write(JSON.stringify([false,true].flatMap(gun=>[false,true].map(held=>Boolean(f({gun},{is_item_equipped:()=>held}))))));"
        values=json.loads(subprocess.check_output(['node','-e',script,expression],text=True))
        self.assertEqual(values,[False,False,True,False])
        arm=json.loads(result['Author RP/render_controllers/kg_tacz_offhand.render_controllers.json'])['render_controllers'][OFFHAND_FP]
        self.assertEqual(arm['part_visibility'][1], {'rightArm':False})
        self.assertEqual(arm['part_visibility'][3], {'leftArm':'v.left'})
        client=json.loads(result['Author RP/entity/player.entity.json'])['minecraft:client_entity']['description']
        self.assertIn(OFFHAND_FP, client['render_controllers'][-1])
        for side, uid in [('BP', 't-bp'), ('RP', 't-rp')]:
            manifest = json.loads(result['Author ' + side + '/manifest.json'])
            self.assertEqual(manifest['header']['uuid'], uid)
            self.assertEqual(manifest['header']['version'], [1, 0, 20002])
            self.assertEqual(manifest['modules'][0]['uuid'], uid + '-module')
            self.assertEqual(manifest['modules'][0]['version'], [1, 0, 20002])
            self.assertEqual(manifest['header']['min_engine_version'], [1, 26, 60])
            self.assertEqual(manifest.get('capabilities', []), ['pbr'] if side == 'RP' else [])
            self.assertIn({'module_name': '@minecraft/server', 'version': '1.18.0'}, manifest['dependencies'])
            self.assertIn({'uuid': 'g-' + side.lower(), 'version': [2, 8, 206]}, manifest['dependencies'])
            self.assertIn({'uuid': 'ie-' + side.lower(), 'version': [1, 1, 20002]}, manifest['dependencies'])
        self.assertEqual(receipt['player_properties'], 28)

    def test_rejects_unreviewed_player_owner_over_limit_and_unknown_output(self):
        for damage in ('second-player', 'over-limit', 'unknown-output', 'missing-controller'):
            originals, composed, controller, descriptor = self.fixture()
            if damage == 'second-player': originals['Author BP/entities/player.json'] = b'foreign player'
            elif damage == 'over-limit':
                value = json.loads(composed['BP/entities/player.json'])
                value['minecraft:entity']['description']['properties'].update({str(i): {} for i in range(5)})
                composed['BP/entities/player.json'] = encoded(value)
            elif damage == 'unknown-output': composed['RP/../scripts/foreign.js'] = b'foreign'
            else: originals['Author RP/render_controllers/player.json'] = b'{}'
            with self.subTest(damage=damage), self.assertRaises(ValueError):
                adapt_files(originals, composed, controller, descriptor)

    def test_archive_hash_is_checked_before_other_inputs_or_outputs(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / 'unreviewed.mcaddon'
            source.write_bytes(b'unreviewed')
            with self.assertRaisesRegex(ValueError, 'TACZ archive differs'):
                apply_archive(source, Path(directory) / 'missing-ie', Path(directory) / 'missing-g',
                              directory, {'tacz': {'archive_sha256': '0' * 64}})


if __name__ == '__main__':
    unittest.main()
