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
        family = json.loads(builder.DEFAULT_DESCRIPTOR.read_text())
        self.assertEqual(set(public['inputs']), {'grilling', 'cookery'})
        self.assertEqual({p['id'] for p in public['packs']},
                         {'grilling-bp', 'grilling-rp', 'cookery-bp', 'cookery-rp'})
        self.assertEqual(public['inputs']['cookery'], family['inputs']['cookery'])
        self.assertEqual(public['inputs']['grilling'], family['inputs']['grilling'])
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


class PublicInstallTests(unittest.TestCase):
    """Direct installation uses real adapters/ZIPs, with synthetic author data."""

    def fixture(self, root, stages=False):
        inputs, public, entries = PublicMinimalTests().fixture(root)
        cookery, grilling = inputs / 'cookery.mcaddon', inputs / 'grilling.mcaddon'
        # This input is the unadapted author package, not a prebuilt family input.
        for side in ('BP', 'RP'):
            path = side + '/manifest.json'
            doc = json.loads(entries['cookery'][path])
            doc['header']['version'] = [1, 6, 4]
            for module in doc['modules']:
                module['version'] = [1, 6, 4]
            for dependency in doc.get('dependencies', []):
                dependency['version'] = [1, 6, 4]
            entries['cookery'][path] = json.dumps(doc, indent=2).encode()
        cookery.write_bytes(make_archive(entries['cookery']))
        helper = b'export const publicHelper = true;\n'
        original = entries['cookery']['BP/scripts/main.js']
        hooked = b'// public host hook\n' + original
        api = {
            'schema': 1, 'archive_sha256': digest(cookery.read_bytes()),
            'host_uuid': 'c-bp-uuid',
            'original_files': {'scripts/main.js': digest(original)},
            'patched_files': {'scripts/main.js': digest(hooked)},
            'imports': {'scripts/main.js': '// public host hook\n'},
            'insertions': [], 'json_updates': [],
            'copies': {'scripts/host_api/shared.js': 'scripts/api/shared.js'},
        }
        spec_raw = json.dumps(api).encode()
        entries['grilling']['BP/host-extensions/board-api.json'] = spec_raw
        entries['grilling']['BP/scripts/host_api/shared.js'] = helper
        grilling.write_bytes(make_archive(entries['grilling']))
        adapter = {
            'schema': 1, 'id': 'test:reviewed-cookery-adapter',
            'archive_sha256': digest(cookery.read_bytes()),
            'host_uuid': 'c-bp-uuid', 'resource_uuid': 'c-rp-uuid',
            'author_version': [1, 6, 4], 'output_version': [1, 6, 20012],
            'prefixes': {'BP': 'BP/', 'RP': 'RP/'},
            'companion': {
                'archive_sha256': digest(grilling.read_bytes()),
                'bp_uuid': 'g-bp-uuid', 'version': [2, 8, 212],
                'rp_uuid': 'g-rp-uuid', 'rp_version': [2, 8, 212],
                'spec_path': 'host-extensions/board-api.json',
                'spec_sha256': digest(spec_raw),
                'source': {'commit': 'historical-template-not-actual-input'},
                'runtime_trees': {'BP': {'sha256': 'historical-template'}},
            },
            'owned_helpers': {'scripts/host_api/shared.js': digest(helper)},
        }
        public['inputs']['grilling']['sha256'] = digest(grilling.read_bytes())
        public['candidate_provenance'] = {'grilling_commit': 'historical-not-actual-input'}
        wrapper = __import__('install_cookery_from_descriptor')
        raw, _ = wrapper.apply_archive(cookery, grilling, adapter)
        if stages:
            for kind, name, before in (
                    ('post_adapter', 'post', hooked),
                    ('station_adapter', 'station', b'// post\n' + hooked)):
                owned = b'// ' + name.encode() + b' helper\n'
                (root / (name + '.js')).write_bytes(owned)
                adapter[kind] = {
                    'helper_path': name + '.js', 'helper_sha256': digest(owned),
                    'helper_destination': 'scripts/api/' + name + '.js',
                    'preimages': {'scripts/main.js': digest(before)},
                    'postimages': {'scripts/main.js': digest(b'// ' + name.encode() + b'\n' + before)},
                    'imports': {'scripts/main.js': '// ' + name + '\n'},
                }
            with patch.object(wrapper, 'ROOT', root):
                raw, _, _ = wrapper.apply_post_adapter(raw, adapter)
                raw, _, _ = wrapper.apply_station_adapter(raw, adapter)
        public['inputs']['cookery']['sha256'] = digest(raw)
        public_path, adapter_path = root / 'public.json', root / 'adapter.json'
        public_path.write_text(json.dumps(public))
        adapter_path.write_text(json.dumps(adapter))
        for owner, name, value in (
                (builder, 'PUBLIC_MINIMAL_DESCRIPTOR', public_path),
                (builder, 'PUBLIC_COOKERY_DESCRIPTOR', adapter_path),
                (wrapper, 'ROOT', root)):
            change = patch.object(owner, name, value)
            change.start()
            self.addCleanup(change.stop)
        return cookery, grilling, public, adapter, entries, raw

    def test_one_command_actual_cli_all_adapter_stages_and_no_optional_inputs(self):
        import shutil
        import subprocess
        with tempfile.TemporaryDirectory(prefix='public install ') as td:
            root = Path(td)
            cookery, grilling, public, adapter, entries, adapted = self.fixture(root, stages=True)
            before = {p: p.read_bytes() for p in (cookery, grilling)}
            # Exercise a fresh Python process; the CLI needs no patched module globals.
            executable_root = root / 'tool copy'
            (executable_root / 'tools').mkdir(parents=True)
            (executable_root / 'adapters').mkdir()
            for name in ('assemble_family.py', 'build_owned_family_recipe.py',
                         'install_cookery.py', 'install_cookery_from_descriptor.py'):
                shutil.copyfile(ROOT / 'tools' / name, executable_root / 'tools' / name)
            (executable_root / 'adapters/public-minimal-grilling-g212-cookery20012.json').write_text(json.dumps(public))
            (executable_root / 'adapters/cookery-1.6.4-grilling-2.8.212-station-performance.json').write_text(json.dumps(adapter))
            for name in ('post.js', 'station.js'):
                shutil.copyfile(root / name, executable_root / name)
            output = root / 'complete output'
            result = subprocess.run([
                sys.executable, str(executable_root / 'tools/build_owned_family_recipe.py'),
                '--cookery', str(cookery), '--grilling', str(grilling), '--output', str(output)
            ], text=True, capture_output=True, timeout=30)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(result.stdout)['packs'], 4)
            with zipfile.ZipFile(output / 'public-minimal.mcaddon') as package:
                self.assertEqual(set(package.namelist()),
                                 {'grilling-bp.mcpack', 'grilling-rp.mcpack', 'cookery-bp.mcpack', 'cookery-rp.mcpack'})
            with zipfile.ZipFile(output / 'cookery-bp.mcpack') as package:
                self.assertEqual(package.read('scripts/main.js'),
                                 b'// station\n// post\n// public host hook\nexport const cookery = true;\n')
                self.assertIn('scripts/api/shared.js', package.namelist())
            self.assertEqual(json.loads((output / 'cookery-adapter.receipt.json').read_text())['output_sha256'], digest(adapted))
            self.assertEqual(before, {p: p.read_bytes() for p in before})
            self.assertEqual(set(p.name for p in cookery.parent.iterdir()), {'cookery.mcaddon', 'grilling.mcaddon'})
            self.assertFalse((output / 'inputs').exists())
            self.assertEqual(json.loads((output / 'installation.json').read_text())['client'], 'NOT_RUN')

    def test_new_grilling_version_same_contract_preserves_changes_and_is_repeatable(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            cookery, grilling, public, adapter, entries, adapted = self.fixture(root)
            old_recipe_inputs = root / 'exact-inputs'
            old_recipe_inputs.mkdir()
            (old_recipe_inputs / 'cookery.mcaddon').write_bytes(adapted)
            for side in ('BP', 'RP'):
                path = side + '/manifest.json'
                doc = json.loads(entries['grilling'][path])
                doc['header']['version'] = [2, 8, 213]
                for module in doc['modules']:
                    module['version'] = [2, 8, 213]
                for dependency in doc.get('dependencies', []):
                    if dependency.get('uuid') == 'g-rp-uuid':
                        dependency['version'] = [2, 8, 213]
                entries['grilling'][path] = json.dumps(doc, indent=2).encode()
            entries['grilling']['RP/textures/item.txt'] = b'new unrelated texture'
            entries['grilling']['BP/scripts/main.js'] = b'// unrelated gameplay update\n'
            grilling.write_bytes(make_archive(entries['grilling']))
            (old_recipe_inputs / 'grilling.mcaddon').write_bytes(grilling.read_bytes())
            # Original exact-snapshot reproduction stays strict; only direct mode resolves the contract.
            with self.assertRaisesRegex(ValueError, 'input hash differs'):
                builder.build_recipe(public, old_recipe_inputs)
            from install_cookery import apply_archive
            with self.assertRaisesRegex(ValueError, 'Grilling archive hash'):
                apply_archive(cookery, grilling, adapter)
            before = (cookery.read_bytes(), grilling.read_bytes())
            one = builder.install_public_pair(cookery, grilling, root / 'one')
            builder.install_public_pair(cookery, grilling, root / 'two')
            self.assertEqual((root / 'one/public-minimal.mcaddon').read_bytes(),
                             (root / 'two/public-minimal.mcaddon').read_bytes())
            self.assertEqual(one['packs'][0]['version'], [2, 8, 213])
            with zipfile.ZipFile(root / 'one/grilling-rp.mcpack') as package:
                self.assertEqual(package.read('textures/item.txt'), b'new unrelated texture')
            provenance = json.loads((root / 'one/installation.json').read_text())
            self.assertEqual(provenance['grilling_version'], [2, 8, 213])
            self.assertEqual(provenance['grilling_sha256'], digest(grilling.read_bytes()))
            self.assertNotIn('historical-not-actual-input', (root / 'one/recipe.json').read_text())
            self.assertEqual(before, (cookery.read_bytes(), grilling.read_bytes()))

    def test_changed_api_helper_and_author_are_rejected_without_output(self):
        for field in ('api', 'helper', 'author'):
            with self.subTest(field=field), tempfile.TemporaryDirectory() as td:
                root = Path(td)
                cookery, grilling, _, _, entries, _ = self.fixture(root)
                if field == 'author':
                    cookery.write_bytes(cookery.read_bytes() + b'changed')
                    message = 'Cookery archive hash'
                else:
                    name = 'BP/host-extensions/board-api.json' if field == 'api' else 'BP/scripts/host_api/shared.js'
                    entries['grilling'][name] += b' '
                    grilling.write_bytes(make_archive(entries['grilling']))
                    message = 'API declaration hash' if field == 'api' else 'helper bytes'
                before = (cookery.read_bytes(), grilling.read_bytes())
                with self.assertRaisesRegex(ValueError, message):
                    builder.install_public_pair(cookery, grilling, root / 'failed')
                self.assertFalse((root / 'failed').exists())
                self.assertEqual(before, (cookery.read_bytes(), grilling.read_bytes()))
                self.assertFalse(list(root.glob('.public-install-*')))

    def test_missing_real_dependency_or_competing_player_is_not_hidden(self):
        for field in ('dependency', 'player'):
            with self.subTest(field=field), tempfile.TemporaryDirectory() as td:
                root = Path(td)
                cookery, grilling, _, _, entries, _ = self.fixture(root)
                if field == 'dependency':
                    doc = json.loads(entries['grilling']['BP/manifest.json'])
                    doc['dependencies'].append({'uuid': 'another-addon', 'version': [1, 0, 0]})
                    entries['grilling']['BP/manifest.json'] = json.dumps(doc).encode()
                    message = 'required pack dependency is absent'
                else:
                    entries['grilling']['BP/entities/other.json'] = entries['grilling']['BP/entities/player.json']
                    message = 'competing behavior'
                grilling.write_bytes(make_archive(entries['grilling']))
                with self.assertRaisesRegex(ValueError, message):
                    builder.install_public_pair(cookery, grilling, root / 'failed')
                self.assertFalse((root / 'failed').exists())

    def test_mismatched_bp_rp_or_modules_are_rejected(self):
        for field in ('pair', 'module'):
            with self.subTest(field=field), tempfile.TemporaryDirectory() as td:
                root = Path(td)
                cookery, grilling, _, _, entries, _ = self.fixture(root)
                doc = json.loads(entries['grilling']['RP/manifest.json'])
                if field == 'pair':
                    doc['header']['version'] = [2, 8, 213]
                    doc['modules'][0]['version'] = [2, 8, 213]
                else:
                    doc['modules'][0]['uuid'] = 'unrelated-module'
                entries['grilling']['RP/manifest.json'] = json.dumps(doc).encode()
                grilling.write_bytes(make_archive(entries['grilling']))
                with self.assertRaisesRegex(ValueError, 'same version|module identity'):
                    builder.install_public_pair(cookery, grilling, root / 'failed')
                self.assertFalse((root / 'failed').exists())

    def test_existing_output_is_not_replaced_and_bad_cli_has_no_side_effects(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            cookery, grilling, _, _, _, _ = self.fixture(root)
            output = root / 'existing'
            output.mkdir()
            (output / 'keep').write_bytes(b'do not replace')
            with self.assertRaisesRegex(ValueError, 'refusing to replace'):
                builder.install_public_pair(cookery, grilling, output)
            self.assertEqual((output / 'keep').read_bytes(), b'do not replace')
            for args in (['--cookery', str(cookery)],
                         ['--cookery', str(cookery), '--grilling', str(grilling), '--profile', 'full-family'],
                         ['--cookery', str(cookery), '--grilling', str(grilling), '--inputs', str(root)]):
                with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as failure:
                    builder.main(args + ['--output', str(root / 'invalid')])
                self.assertEqual(failure.exception.code, 2)
                self.assertFalse((root / 'invalid').exists())

    def test_legacy_wrapper_and_default_family_selection_are_unchanged(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            cookery, grilling, public, adapter, _, expected = self.fixture(root, stages=True)
            wrapper = __import__('install_cookery_from_descriptor')
            with redirect_stdout(io.StringIO()):
                wrapper.main(['--cookery', str(cookery), '--grilling', str(grilling),
                              '--descriptor', str(root / 'adapter.json'), '--output', str(root / 'legacy.mcaddon')])
            self.assertEqual((root / 'legacy.mcaddon').read_bytes(), expected)
            legacy_inputs = root / 'legacy-inputs'
            legacy_inputs.mkdir()
            (legacy_inputs / 'grilling.mcaddon').write_bytes(grilling.read_bytes())
            (legacy_inputs / 'cookery.mcaddon').write_bytes(expected)
            public['inputs']['ie'] = {'filename': 'optional-ie.mcaddon', 'sha256': '0' * 64}
            path = root / 'legacy-family.json'
            path.write_text(json.dumps(public))
            with patch.object(builder, 'DEFAULT_DESCRIPTOR', path):
                with self.assertRaisesRegex(ValueError, 'input file missing: optional-ie'):
                    builder.main(['--inputs', str(legacy_inputs), '--output', str(root / 'recipe.json')])
            self.assertFalse((root / 'recipe.json').exists())


if __name__ == '__main__':
    unittest.main()
