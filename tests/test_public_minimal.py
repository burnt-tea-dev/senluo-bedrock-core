"""Public-minimal: real ZIP/manifest assembly using synthetic, author-free packs."""
import copy
from contextlib import redirect_stderr, redirect_stdout
import hashlib
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import assemble_family
import build_owned_family_recipe as builder


def digest(data):
    return hashlib.sha256(data).hexdigest()


def make_archive(entries):
    out = io.BytesIO()
    with zipfile.ZipFile(out, 'w', zipfile.ZIP_DEFLATED) as archive:
        for path, data in entries.items():
            archive.writestr(path, data)
    return out.getvalue()


def manifest(uuid, version, module, dependencies=()):
    return json.dumps({
        'format_version': 2,
        'header': {'uuid': uuid, 'version': version, 'min_engine_version': [1, 26, 60]},
        'modules': [{'type': 'data', 'uuid': module, 'version': version}],
        'dependencies': list(dependencies),
    }, indent=2).encode()


class PublicMinimalTests(unittest.TestCase):
    def fixture(self, root):
        inputs = root / 'inputs'
        inputs.mkdir()
        gver, cver, original = [2, 8, 212], [1, 6, 20012], [1, 6, 4]
        g_bp, g_rp, c_bp, c_rp = 'g-bp-uuid', 'g-rp-uuid', 'c-bp-uuid', 'c-rp-uuid'
        player = json.dumps({'minecraft:entity': {'description': {
            'identifier': 'minecraft:player', 'properties': {
                'g:one': {}, 'g:two': {}, 'g:three': {}, 'g:four': {}
            }}}}).encode()
        source_entries = {
            'grilling': {
                'BP/manifest.json': manifest(g_bp, gver, 'g-bp-module', [
                    {'uuid': g_rp, 'version': gver},
                    {'uuid': c_bp, 'version': original},
                    {'module_name': '@minecraft/server', 'version': '2.12.0-beta'}]),
                'RP/manifest.json': manifest(g_rp, gver, 'g-rp-module', [
                    {'uuid': c_rp, 'version': original}]),
                'BP/entities/player.json': player,
                'BP/scripts/main.js': b'export const grilling = true;\n',
                'RP/textures/item.txt': b'grilling texture',
            },
            'cookery': {
                'BP/manifest.json': manifest(c_bp, cver, 'c-bp-module', [
                    {'uuid': c_rp, 'version': cver}]),
                'RP/manifest.json': manifest(c_rp, cver, 'c-rp-module'),
                'BP/scripts/main.js': b'export const cookery = true;\n',
                'RP/textures/item.txt': b'cookery texture',
            },
        }
        for source, entries in source_entries.items():
            (inputs / (source + '.mcaddon')).write_bytes(make_archive(entries))
        pins = [
            ('grilling-bp', 'grilling', g_bp, gver, 'g-bp-module', 'BP'),
            ('grilling-rp', 'grilling', g_rp, gver, 'g-rp-module', 'RP'),
            ('cookery-bp', 'cookery', c_bp, cver, 'c-bp-module', 'BP'),
            ('cookery-rp', 'cookery', c_rp, cver, 'c-rp-module', 'RP'),
        ]
        descriptor = {
            'schema': 1, 'id': 'test:public-minimal', 'recipe_version': 'g212-c20012-r1',
            'inputs': {key: {'filename': key + '.mcaddon',
                             'sha256': digest((inputs / (key + '.mcaddon')).read_bytes())}
                       for key in ('grilling', 'cookery')},
            'packs': [{'id': pid, 'input': source, 'uuid': uuid, 'version': version,
                       'side': side, 'modules': [{'uuid': module, 'version': version}]}
                      for pid, source, uuid, version, module, side in pins],
            'order': {'BP': ['grilling-bp', 'cookery-bp'], 'RP': ['grilling-rp', 'cookery-rp']},
            'dependency_rewrites': {
                'grilling-bp': {'uuid': c_bp, 'before': original, 'after': cver},
                'grilling-rp': {'uuid': c_rp, 'before': original, 'after': cver},
            },
            'require_closed_pack_dependencies': True,
            'required_behavior_player_owner': 'grilling-bp',
        }
        return inputs, descriptor, source_entries

    def test_real_public_profile_is_two_inputs_and_four_pinned_packs(self):
        public = json.loads(builder.PUBLIC_MINIMAL_DESCRIPTOR.read_text())
        source = json.loads((ROOT / 'adapters/public-minimal-grilling-g213-cookery20012.json').read_text())
        self.assertEqual(set(public['inputs']), {'grilling', 'cookery'})
        self.assertEqual({p['id'] for p in public['packs']},
                         {'grilling-bp', 'grilling-rp', 'cookery-bp', 'cookery-rp'})
        self.assertEqual(public['inputs']['cookery'], source['inputs']['cookery'])
        self.assertEqual(public['inputs']['grilling'], source['inputs']['grilling'])
        self.assertEqual(public['required_behavior_player_owner'], 'grilling-bp')

    def test_reproduces_missing_dependency_rewrite_then_builds_four_pack_pair(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            inputs, descriptor, entries = self.fixture(root)
            broken = copy.deepcopy(descriptor)
            del broken['dependency_rewrites']
            recipe = builder.build_recipe(broken, inputs)
            old_recipe = root / 'old-recipe.json'
            old_recipe.write_text(json.dumps(recipe))
            with self.assertRaisesRegex(ValueError, 'required pack dependency version differs'):
                assemble_family.assemble(recipe, old_recipe, inputs, root / 'before')
            self.assertFalse((root / 'before').exists())

            hashes = {p.name: digest(p.read_bytes()) for p in inputs.iterdir()}
            recipe = builder.build_recipe(descriptor, inputs)
            recipe_path = root / 'recipe.json'
            recipe_path.write_text(json.dumps(recipe))
            receipt = assemble_family.assemble(recipe, recipe_path, inputs, root / 'out')
            self.assertEqual(len(receipt['packs']), 4)
            self.assertEqual(receipt['behavior_player_definition']['pack_id'], 'grilling-bp')
            self.assertEqual(hashes, {p.name: digest(p.read_bytes()) for p in inputs.iterdir()})
            self.assertEqual(len(json.loads((root / 'out/world_behavior_packs.json').read_text())), 2)
            self.assertEqual(len(json.loads((root / 'out/world_resource_packs.json').read_text())), 2)
            with zipfile.ZipFile(root / 'out/public-minimal.mcaddon') as combined:
                self.assertEqual(set(combined.namelist()), {p['archive'] for p in receipt['packs']})
                for pack in recipe['packs']:
                    with zipfile.ZipFile(io.BytesIO(combined.read(pack['id'] + '.mcpack'))) as archive:
                        files = {p: archive.read(p) for p in archive.namelist()}
                        expected = {p[3:]: body
                                    for p, body in entries[pack['id'].split('-')[0]].items()
                                    if p.startswith(pack['side'] + '/')}
                        self.assertEqual(set(files), set(expected))
                        for path, raw in files.items():
                            if pack['id'].startswith('grilling-') and path == 'manifest.json':
                                dependencies = json.loads(raw)['dependencies']
                                cookery = [d for d in dependencies if d.get('uuid', '').startswith('c-')]
                                self.assertEqual(cookery[0]['version'], [1, 6, 20012])
                            else:
                                self.assertEqual(raw, expected[path])
                        self.assertEqual(json.loads(files['manifest.json'])['header']['uuid'], pack['uuid'])

    def test_cli_and_explicit_descriptor_preserve_history(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            inputs, descriptor, _ = self.fixture(root)
            path = root / 'public-descriptor.json'
            path.write_text(json.dumps(descriptor))
            recipe_path = root / 'recipe.json'
            with patch.object(builder, 'PUBLIC_MINIMAL_DESCRIPTOR', path), redirect_stdout(io.StringIO()):
                builder.main(['--profile', 'public-minimal', '--inputs', str(inputs),
                              '--output', str(recipe_path)])
            with patch.object(sys, 'argv', ['assemble_family.py', '--recipe', str(recipe_path),
                                            '--inputs', str(inputs), '--output', str(root / 'built')]):
                with redirect_stdout(io.StringIO()):
                    assemble_family.main()
            self.assertTrue((root / 'built/public-minimal.mcaddon').exists())
            with redirect_stdout(io.StringIO()):
                builder.main(['--descriptor', str(path), '--inputs', str(inputs),
                              '--output', str(root / 'explicit.json')])
            self.assertEqual(json.loads((root / 'explicit.json').read_text())['id'], descriptor['id'])
            with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                builder.main(['--profile', 'public-minimal', '--descriptor', str(path),
                              '--inputs', str(inputs), '--output', str(root / 'ambiguous.json')])

    def test_aggregate_filename_safety_and_historical_default(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            inputs, descriptor, _ = self.fixture(root)
            recipe = builder.build_recipe(descriptor, inputs)
            path = root / 'recipe.json'
            path.write_text(json.dumps(recipe))
            for index, name in enumerate(('../outside.mcaddon', '/tmp/out.mcaddon',
                                           'grilling-bp.mcpack', 'bad.zip', 'a\\b.mcaddon',
                                           'D:outside.mcaddon', 'output.mcaddon:stream.mcaddon',
                                           'CON.mcaddon', 'nul.mcaddon', 'COM1.mcaddon',
                                           'LPT9.mcaddon', 'COM¹.mcaddon', 'bad?.mcaddon',
                                           'bad\x1f.mcaddon')):
                invalid = copy.deepcopy(recipe)
                invalid['aggregate_filename'] = name
                output = root / ('invalid-' + str(index))
                with self.assertRaisesRegex(ValueError, 'invalid aggregate'):
                    assemble_family.assemble(invalid, path, inputs, output)
                self.assertFalse(output.exists())
            del recipe['aggregate_filename']
            assemble_family.assemble(recipe, path, inputs, root / 'historical')
            self.assertTrue((root / 'historical/family.mcaddon').is_file())

    def test_g213_descriptor_provenance_and_adapter_pin(self):
        public = json.loads((ROOT / 'adapters/public-minimal-grilling-g213-cookery20012.json').read_text())
        self.assertEqual(public['candidate_provenance']['grilling_commit'],
                         '6ea3fa5222c56d8ee2451c7c2d51e7d1dc5894e3')
        self.assertEqual(public['candidate_provenance']['grilling_input_archive_sha256'],
                         public['inputs']['grilling']['sha256'])
        self.assertEqual(set(public['inputs']), {'grilling', 'cookery'})
        self.assertEqual([p['version'] for p in public['packs'] if p['input'] == 'grilling'],
                         [[2, 8, 213], [2, 8, 213]])

    @unittest.skipUnless(os.environ.get('PUBLIC_MINIMAL_INPUTS'), 'Real public-minimal archives required')
    def test_real_g213_pair_repeatability_and_manifest_closure(self):
        inputs = Path(os.environ['PUBLIC_MINIMAL_INPUTS'])
        descriptor = json.loads((ROOT / 'adapters/public-minimal-grilling-g213-cookery20012.json').read_text())
        self.assertEqual({p.name for p in inputs.iterdir()},
                         {p['filename'] for p in descriptor['inputs'].values()})
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            path = root / 'recipe.json'
            recipe = builder.build_recipe(descriptor, inputs)
            path.write_text(json.dumps(recipe))
            one = assemble_family.assemble(recipe, path, inputs, root / 'one')
            assemble_family.assemble(recipe, path, inputs, root / 'two')
            self.assertEqual(len(one['packs']), 4)
            self.assertEqual(one['behavior_player_definition']['pack_id'], 'grilling-bp')
            versions = {p['uuid']: p['version'] for p in one['packs']}
            for pack in one['packs']:
                raw = (root / 'one' / pack['archive']).read_bytes()
                self.assertEqual(raw, (root / 'two' / pack['archive']).read_bytes())
                self.assertEqual(digest(raw), pack['archive_sha256'])
                with zipfile.ZipFile(io.BytesIO(raw)) as archive:
                    manifest = json.loads(archive.read('manifest.json'))
                    for dep in manifest.get('dependencies', []):
                        if 'uuid' in dep:
                            self.assertEqual(dep['version'], versions[dep['uuid']])
            raw = (root / 'one/public-minimal.mcaddon').read_bytes()
            self.assertEqual(raw, (root / 'two/public-minimal.mcaddon').read_bytes())
            self.assertEqual(digest(raw), '96856304f186320014636d3cca81f2e8429edee433780c761de82bb1b029423e')
            with zipfile.ZipFile(io.BytesIO(raw)) as archive:
                self.assertEqual(set(archive.namelist()), {p['archive'] for p in one['packs']})
                for name in archive.namelist():
                    self.assertEqual(archive.read(name), (root / 'one' / name).read_bytes())

    def player_fixture(self, root, descriptor):
        source = root / 'grilling-source'
        path = source / 'projects/grilling/gameplay_core/behavior_pack/host-extensions/player-presentation.json'
        path.parent.mkdir(parents=True)
        extension = {'scripts': {'variables': {'variable.grilling_word': 'public'}},
                     'animations': {'kg_reader': 'controller.animation.kg_reader'}}
        path.write_text(json.dumps(extension))
        vanilla = root / 'vanilla'
        player_path = vanilla / 'resource_pack/entity/player.entity.json'
        player_path.parent.mkdir(parents=True)
        host = {'format_version': '1.26.0', 'minecraft:client_entity': {'description': {
            'identifier': 'minecraft:player', 'scripts': {'animate': ['root']},
            'animations': {'root': 'controller.animation.player.root'},
            'render_controllers': ['controller.render.player.first_person'],
            'enable_attachables': True}}}
        player_path.write_text(json.dumps(host))
        (vanilla / 'LICENSE.md').write_text('Synthetic test reference license, not Mojang source.\n')
        blob = lambda raw: hashlib.sha1(b'blob ' + str(len(raw)).encode() + b'\0' + raw).hexdigest()
        descriptor['player_presentation'] = {'output_version': [2, 8, 218],
            'source': {'commit': 'fixture', 'git_tree': 'fixture'},
            'vanilla': {'player_blob_sha1': blob(player_path.read_bytes()),
                        'license_blob_sha1': blob((vanilla / 'LICENSE.md').read_bytes())}}
        composed = copy.deepcopy(host)
        desc = composed['minecraft:client_entity']['description']
        desc['scripts']['variables'] = extension['scripts']['variables'].copy()
        desc['animations'].update(extension['animations'])
        raw = json.dumps(composed).encode()
        result = ({'RP/entity/player.entity.json': raw},
                  {'outputs': {'RP/entity/player.entity.json': digest(raw)}})
        return source, vanilla, host, result

    def test_public_resource_player_is_composed_in_grilling_not_an_extra_pack(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            inputs, descriptor, original = self.fixture(root)
            source, vanilla, host, result = self.player_fixture(root, descriptor)
            before = {p.name: digest(p.read_bytes()) for p in inputs.iterdir()}
            with patch('install_player_presentation.compose_players', return_value=result) as compose:
                recipe = builder.build_recipe(descriptor, inputs, grilling_source=source, vanilla_source=vanilla)
            self.assertEqual(len(compose.call_args.args), 3)  # No TACZ/IE argument or private host.
            self.assertEqual(compose.call_args.args[0], source)
            self.assertEqual(json.loads(compose.call_args.args[1]), host)
            self.assertEqual(set(recipe['inputs']), {'grilling', 'cookery'})
            self.assertEqual(len(recipe['packs']), 4)
            for pack in recipe['packs']:
                if pack['id'].startswith('grilling-'):
                    self.assertEqual(pack['version'], [2, 8, 218])
            path = root / 'recipe.json'
            path.write_text(json.dumps(recipe))
            one = assemble_family.assemble(recipe, path, inputs, root / 'one')
            assemble_family.assemble(recipe, path, inputs, root / 'two')
            self.assertEqual(one['resource_player_definition']['pack_id'], 'grilling-rp')
            self.assertEqual(one['behavior_player_definition']['pack_id'], 'grilling-bp')
            self.assertEqual((root/'one/public-minimal.mcaddon').read_bytes(), (root/'two/public-minimal.mcaddon').read_bytes())
            for pack in recipe['packs']:
                with zipfile.ZipFile(root / 'one' / (pack['id'] + '.mcpack')) as archive:
                    for name in archive.namelist():
                        if pack['id'] == 'grilling-rp' and name in ('entity/player.entity.json', 'MOJANG-VANILLA-LICENSE.md'):
                            continue
                        if name == 'manifest.json' and pack['id'].startswith('grilling-'):
                            continue
                        self.assertEqual(archive.read(name), original[pack['id'].split('-')[0]][pack['side'] + '/' + name])
            self.assertEqual(before, {p.name: digest(p.read_bytes()) for p in inputs.iterdir()})

    def test_missing_reference_and_reused_identity_fail_before_composition(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            inputs, descriptor, _ = self.fixture(root)
            source, vanilla, _, _ = self.player_fixture(root, descriptor)
            with patch('install_player_presentation.compose_players') as compose:
                with self.assertRaisesRegex(ValueError, '--grilling-source and --vanilla-source'):
                    builder.build_recipe(descriptor, inputs)
                bad = copy.deepcopy(descriptor)
                bad['player_presentation']['output_version'] = [2, 8, 212]
                with self.assertRaisesRegex(ValueError, 'fresh increasing'):
                    builder.build_recipe(bad, inputs, grilling_source=source, vanilla_source=vanilla)
                (vanilla / 'resource_pack/entity/player.entity.json').write_text('{}')
                with self.assertRaisesRegex(ValueError, 'vanilla player differs'):
                    builder.build_recipe(descriptor, inputs, grilling_source=source, vanilla_source=vanilla)
                compose.assert_not_called()

    def test_missing_incomplete_or_competing_resource_player_is_not_admitted(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            inputs, descriptor, _ = self.fixture(root)
            source, vanilla, _, result = self.player_fixture(root, descriptor)
            with patch('install_player_presentation.compose_players', return_value=result):
                recipe = builder.build_recipe(descriptor, inputs, grilling_source=source, vanilla_source=vanilla)
            for index, mode in enumerate(('missing', 'incomplete', 'competing')):
                broken = copy.deepcopy(recipe)
                packs = {p['id']: p for p in broken['packs']}
                rp = packs['grilling-rp']
                player = rp['files']['entity/player.entity.json']
                if mode == 'missing':
                    del rp['files']['entity/player.entity.json']
                elif mode == 'incomplete':
                    value = json.loads(player['content'])
                    value['minecraft:client_entity']['description']['scripts']['variables'] = {}
                    player['content'] = json.dumps(value)
                    player['sha256'] = digest(player['content'].encode())
                else:
                    packs['cookery-rp']['files']['entity/foreign_player.json'] = copy.deepcopy(player)
                for pack in packs.values():
                    hashes = {p: spec.get('output_sha256', spec['sha256']) for p, spec in pack['files'].items()}
                    pack['expected_tree'] = {'files': hashes, 'sha256': assemble_family._tree_fingerprint(hashes)}
                path = root / ('bad' + str(index) + '.json')
                path.write_text(json.dumps(broken))
                output = root / ('bad' + str(index))
                with self.assertRaisesRegex(ValueError, 'resource.*player'):
                    assemble_family.assemble(broken, path, inputs, output)
                self.assertFalse(output.exists())

    @unittest.skipUnless(os.environ.get('PUBLIC_PLAYER_GRILLING_SOURCE') and os.environ.get('PUBLIC_PLAYER_VANILLA_SOURCE')
                         and os.environ.get('PUBLIC_MINIMAL_INPUTS'), 'Real public player build references required')
    def test_real_public_player_with_only_grilling_and_cookery(self):
        descriptor = json.loads(builder.PUBLIC_MINIMAL_DESCRIPTOR.read_text())
        inputs = Path(os.environ['PUBLIC_MINIMAL_INPUTS'])
        recipe = builder.build_recipe(descriptor, inputs,
            grilling_source=Path(os.environ['PUBLIC_PLAYER_GRILLING_SOURCE']),
            vanilla_source=Path(os.environ['PUBLIC_PLAYER_VANILLA_SOURCE']))
        self.assertEqual(set(recipe['inputs']), {'grilling', 'cookery'})
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            path = root / 'recipe.json'
            path.write_text(json.dumps(recipe))
            first = assemble_family.assemble(recipe, path, inputs, root/'first')
            assemble_family.assemble(recipe, path, inputs, root/'second')
            self.assertEqual(first['resource_player_definition']['pack_id'], 'grilling-rp')
            self.assertEqual(first['behavior_player_definition']['pack_id'], 'grilling-bp')
            self.assertEqual(len(first['packs']), 4)
            self.assertEqual((root/'first/public-minimal.mcaddon').read_bytes(), (root/'second/public-minimal.mcaddon').read_bytes())
            with zipfile.ZipFile(root/'first/grilling-rp.mcpack') as archive:
                desc = json.loads(archive.read('entity/player.entity.json'))['minecraft:client_entity']['description']
                vanilla = json.loads((Path(os.environ['PUBLIC_PLAYER_VANILLA_SOURCE'])/'resource_pack/entity/player.entity.json').read_bytes())['minecraft:client_entity']['description']
                for key in ('materials', 'textures', 'geometry', 'render_controllers', 'enable_attachables'):
                    self.assertEqual(desc[key], vanilla[key])
                self.assertEqual(archive.read('MOJANG-VANILLA-LICENSE.md'),
                    (Path(os.environ['PUBLIC_PLAYER_VANILLA_SOURCE'])/'LICENSE.md').read_bytes())
            print(json.dumps({'public_player_source_contract': 'PASS', 'aggregate_sha256':
                             digest((root/'first/public-minimal.mcaddon').read_bytes()),
                             'packs': 4, 'client': 'NOT-RUN'}))

    def test_bad_inputs_preimages_and_output_rollback(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            inputs, descriptor, _ = self.fixture(root)
            wrong = copy.deepcopy(descriptor)
            wrong['dependency_rewrites']['grilling-bp']['before'] = [1, 6, 999]
            with self.assertRaisesRegex(ValueError, 'manifest dependency preimage differs'):
                builder.build_recipe(wrong, inputs)
            mismatch = copy.deepcopy(descriptor)
            mismatch['inputs']['cookery']['sha256'] = '0' * 64
            with self.assertRaisesRegex(ValueError, 'input hash differs'):
                builder.build_recipe(mismatch, inputs)
            recipe = builder.build_recipe(descriptor, inputs)
            path = root / 'recipe.json'
            path.write_text(json.dumps(recipe))
            altered = copy.deepcopy(recipe)
            altered['packs'][0]['files']['manifest.json']['transforms'][0]['before'] = []
            with self.assertRaisesRegex(ValueError, 'JSON transform preimage differs'):
                assemble_family.assemble(altered, path, inputs, root / 'failed')
            self.assertFalse((root / 'failed').exists())
            assemble_family.assemble(recipe, path, inputs, root / 'built')
            with self.assertRaisesRegex(ValueError, 'refusing to replace'):
                assemble_family.assemble(recipe, path, inputs, root / 'built')


if __name__ == '__main__':
    unittest.main()
