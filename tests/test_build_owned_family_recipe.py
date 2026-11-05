import copy
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import assemble_family
import build_owned_family_recipe as builder


class OwnedFamilyRecipeTests(unittest.TestCase):
    def fixture(self, root):
        entries = {
            'BP/manifest.json': json.dumps({
                'header': {'uuid': 'owned-bp', 'version': [1, 2, 3]},
                'modules': [{'uuid': 'script-module', 'version': [1, 2, 3]}],
            }).encode(),
            'BP/scripts/main.js': b'export const preserved = "exact bytes";\n',
            'RP/manifest.json': json.dumps({
                'header': {'uuid': 'owned-rp', 'version': [1, 2, 3]},
                'modules': [{'uuid': 'resource-module', 'version': [1, 2, 3]}],
            }).encode(),
            'RP/textures/payload.bin': bytes(range(256)),
        }
        source = root / 'owned.mcaddon'
        with zipfile.ZipFile(source, 'w') as archive:
            for name, body in entries.items():
                archive.writestr(name, body)
        descriptor = {
            'schema': 1, 'id': 'test:owned', 'recipe_version': '1.0.0',
            'toolkit_version': '0.7.0',
            'inputs': {'owned': {'filename': source.name,
                                 'sha256': hashlib.sha256(source.read_bytes()).hexdigest()}},
            'packs': [
                {'id': 'owned-bp', 'input': 'owned', 'uuid': 'owned-bp',
                 'version': [1, 2, 3], 'side': 'BP',
                 'modules': [{'uuid': 'script-module', 'version': [1, 2, 3]}]},
                {'id': 'owned-rp', 'input': 'owned', 'uuid': 'owned-rp',
                 'version': [1, 2, 3], 'side': 'RP',
                 'modules': [{'uuid': 'resource-module', 'version': [1, 2, 3]}]},
            ],
            'order': {'BP': ['owned-bp'], 'RP': ['owned-rp']},
        }
        return descriptor, entries, source

    def test_generated_recipe_reassembles_original_bytes_and_order(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            descriptor, entries, _ = self.fixture(root)
            recipe = builder.build_recipe(descriptor, root)
            self.assertEqual(recipe['toolkit_version'], '0.7.0')
            recipe_path = root / 'recipe.json'
            recipe_path.write_text(json.dumps(recipe))
            output = root / 'assembled'
            receipt = assemble_family.assemble(recipe, recipe_path, root, output)
            self.assertEqual(receipt['order'], descriptor['order'])
            for side in ('BP', 'RP'):
                with zipfile.ZipFile(output / ('owned-' + side.lower() + '.mcpack')) as archive:
                    expected = {name[3:]: body for name, body in entries.items()
                                if name.startswith(side + '/')}
                    self.assertEqual({name: archive.read(name) for name in archive.namelist()}, expected)

    def test_paired_release_without_player_updates_only_declared_manifest_fields(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            descriptor, entries, source = self.fixture(root)
            for side, peer in [('BP', 'rp'), ('RP', 'bp')]:
                name = side + '/manifest.json'
                manifest = json.loads(entries[name])
                manifest['header']['name'] = 'Keep original name'
                manifest['metadata'] = {'authors': ['Original author']}
                manifest['dependencies'] = [
                    {'uuid': 'owned-' + peer, 'version': [1, 2, 3]},
                    {'uuid': 'host-' + side.lower(), 'version': [2, 0, 0]},
                    {'module_name': '@minecraft/server', 'version': '2.7.0'}]
                entries[name] = json.dumps(manifest).encode()
            with zipfile.ZipFile(source, 'w') as archive:
                for name, raw in entries.items(): archive.writestr(name, raw)
            original_archive = source.read_bytes()
            descriptor['inputs']['owned']['sha256'] = hashlib.sha256(original_archive).hexdigest()
            descriptor['paired_releases'] = [{
                'packs': {'BP': 'owned-bp', 'RP': 'owned-rp'}, 'version': [1, 2, 4],
                'dependency_rewrites': [
                    {'uuid': 'host-bp', 'before': [2, 0, 0], 'after': [2, 0, 1]},
                    {'uuid': 'host-rp', 'before': [2, 0, 0], 'after': [2, 0, 1]}]}]
            recipe = builder.build_recipe(descriptor, root)
            path = root / 'recipe.json'; path.write_text(json.dumps(recipe))
            output = root / 'assembled'
            assemble_family.assemble(recipe, path, root, output)
            for side in ('BP', 'RP'):
                with zipfile.ZipFile(output / ('owned-' + side.lower() + '.mcpack')) as archive:
                    for name, raw in entries.items():
                        if name.startswith(side + '/') and name != side + '/manifest.json':
                            self.assertEqual(archive.read(name[3:]), raw)
                    actual = json.loads(archive.read('manifest.json'))
                    expected = json.loads(entries[side + '/manifest.json'])
                    expected['header']['version'] = [1, 2, 4]
                    expected['modules'][0]['version'] = [1, 2, 4]
                    expected['dependencies'][0]['version'] = [1, 2, 4]
                    expected['dependencies'][1]['version'] = [2, 0, 1]
                    self.assertEqual(actual, expected)
            self.assertEqual(source.read_bytes(), original_archive)

    def test_pair_release_rejects_reused_identity_or_unused_dependency(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            descriptor, _, _ = self.fixture(root)
            release = {'packs': {'BP': 'owned-bp', 'RP': 'owned-rp'},
                       'version': [1, 2, 3], 'dependency_rewrites': []}
            descriptor['paired_releases'] = [release]
            with self.assertRaisesRegex(ValueError, 'fresh increasing'):
                builder.build_recipe(descriptor, root)
            release.update(version=[1, 2, 4], dependency_rewrites=[
                {'uuid': 'not-selected', 'before': [1, 0, 0], 'after': [2, 0, 0]}])
            with self.assertRaisesRegex(ValueError, 'unused dependency'):
                builder.build_recipe(descriptor, root)

    def test_rejects_wrong_archive_and_missing_pack(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            descriptor, _, source = self.fixture(root)
            missing = copy.deepcopy(descriptor)
            missing['packs'][0]['uuid'] = 'absent-pack'
            with self.assertRaisesRegex(ValueError, 'missing or duplicated'):
                builder.build_recipe(missing, root)
            source.write_bytes(b'wrong release')
            with self.assertRaisesRegex(ValueError, 'input hash differs'):
                builder.build_recipe(descriptor, root)

    def test_rejects_header_and_module_identity_changes(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            descriptor, _, _ = self.fixture(root)
            for field in ('version', 'modules'):
                changed = copy.deepcopy(descriptor)
                changed['packs'][0][field] = [9, 9, 9] if field == 'version' else []
                with self.subTest(field=field), self.assertRaisesRegex(ValueError, 'identity differs'):
                    builder.build_recipe(changed, root)

    def test_cli_preserves_existing_recipe(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            output = root / 'recipe.json'
            output.write_bytes(b'existing reviewed recipe')
            with self.assertRaisesRegex(ValueError, 'refusing to overwrite'):
                builder.main(['--inputs', str(root), '--output', str(output)])
            self.assertEqual(output.read_bytes(), b'existing reviewed recipe')
