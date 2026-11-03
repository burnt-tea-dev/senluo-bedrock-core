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


class PublicMinimalRecipeTests(unittest.TestCase):
    """Assemble current Grilling/Cookery without IE, TACZ, Tavern or World Liquor."""

    def fixture(self, root, missing_dependency=False):
        versions = {'grilling': [2, 8, 212], 'cookery': [1, 6, 20012]}
        descriptor = {'schema': 1, 'id': 'synthetic:family', 'recipe_version': 'fixture',
                      'inputs': {}, 'packs': [], 'order': {'BP': [], 'RP': []}}
        player_bytes = None
        for name, version in versions.items():
            files = {}
            for side in ('BP', 'RP'):
                ident = f'{name}-{side.lower()}'
                deps = [{'uuid': f'{name}-rp', 'version': version}] if side == 'BP' else []
                if name == 'grilling' and side == 'BP':
                    deps += [{'uuid': 'cookery-bp', 'version': [1, 6, 4]}]
                    if missing_dependency:
                        deps += [{'uuid': 'immersive-eating-bp', 'version': [1, 1, 0]}]
                if name == 'grilling' and side == 'RP':
                    deps += [{'uuid': 'cookery-rp', 'version': [1, 6, 4]}]
                manifest = {'header': {'uuid': ident, 'version': version},
                            'modules': [{'uuid': ident + '-module', 'version': version}],
                            'dependencies': deps}
                files[f'{side}/manifest.json'] = json.dumps(manifest).encode()
                files[f'{side}/assets/source.txt'] = (ident + ' original bytes').encode()
                if ident == 'grilling-bp':
                    player = {'minecraft:entity': {'description': {
                        'identifier': 'minecraft:player',
                        'properties': {'kaleidoscope_grilling:held_frame': {'type': 'int', 'default': 0}},
                    }}}
                    player_bytes = json.dumps(player).encode()
                    files[f'{side}/entities/player.json'] = player_bytes
                descriptor['packs'].append({'id': ident, 'input': name, 'uuid': ident,
                                            'version': version, 'side': side,
                                            'modules': manifest['modules']})
                descriptor['order'][side].append(ident)
            archive = root / (name + '.mcaddon')
            with zipfile.ZipFile(archive, 'w') as output:
                for member, raw in files.items():
                    output.writestr(member, raw)
            descriptor['inputs'][name] = {'filename': archive.name,
                                           'sha256': hashlib.sha256(archive.read_bytes()).hexdigest()}
        # Do not even create optional input ZIPs; a family-wide read would fail.
        for name in ('tavern', 'world-liquor', 'immersive-eating'):
            descriptor['inputs'][name] = {'filename': name + '-absent.mcaddon', 'sha256': '0' * 64}
            for side in ('BP', 'RP'):
                ident = f'{name}-{side.lower()}'
                descriptor['packs'].append({'id': ident, 'input': name, 'uuid': ident,
                                            'version': [1, 0, 0], 'side': side,
                                            'modules': [{'uuid': ident + '-module', 'version': [1, 0, 0]}]})
                descriptor['order'][side].insert(0, ident)
        return descriptor, player_bytes

    def test_four_packs_build_with_single_behavior_player(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            descriptor, player_bytes = self.fixture(root)
            recipe = builder.build_recipe(descriptor, root, profile='public-minimal')
            self.assertEqual(recipe['profile'], 'public-minimal')
            self.assertEqual(set(recipe['inputs']), {'grilling', 'cookery'})
            self.assertEqual({row['id'] for row in recipe['packs']},
                             {'grilling-bp', 'grilling-rp', 'cookery-bp', 'cookery-rp'})
            self.assertEqual(recipe['order'], {'BP': ['grilling-bp', 'cookery-bp'],
                                               'RP': ['grilling-rp', 'cookery-rp']})
            recipe_path = root / 'recipe.json'
            recipe_path.write_text(json.dumps(recipe))
            output = root / 'assembled'
            receipt = assemble_family.assemble(recipe, recipe_path, root, output)
            self.assertEqual(len(receipt['packs']), 4)
            self.assertEqual(set(receipt['inputs']), {'grilling', 'cookery'})
            self.assertEqual(receipt['behavior_player_definition']['pack_id'], 'grilling-bp')
            with zipfile.ZipFile(output / 'grilling-bp.mcpack') as bp:
                self.assertEqual(bp.read('entities/player.json'), player_bytes)
            with zipfile.ZipFile(output / 'family.mcaddon') as addon:
                self.assertEqual(set(addon.namelist()),
                                 {'grilling-bp.mcpack', 'grilling-rp.mcpack',
                                  'cookery-bp.mcpack', 'cookery-rp.mcpack'})

    def test_mandatory_optional_pack_reference_is_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            descriptor, _ = self.fixture(root, missing_dependency=True)
            with self.assertRaisesRegex(ValueError, 'depends on an absent pack'):
                builder.build_recipe(descriptor, root, profile='public-minimal')
