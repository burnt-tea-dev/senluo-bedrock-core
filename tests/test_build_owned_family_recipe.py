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

    def public_fixture(self, root, *, external=False, wrong_version=False):
        """A clean two-archive input: optional family archives do not exist."""
        grill_version = [2, 8, 212]
        cook_version = [1, 6, 20012]
        source_version = [1, 5, 4] if wrong_version else [1, 6, 4]

        def manifest(uuid, version, dependencies=()):
            return (json.dumps({
                'format_version': 2,
                'header': {'uuid': uuid, 'version': version, 'min_engine_version': [1, 26, 60]},
                'modules': [{'uuid': uuid + '-module', 'version': version}],
                'dependencies': list(dependencies),
            }, ensure_ascii=False, indent=2) + '\n').encode()

        dep = lambda uuid, version: {'uuid': uuid, 'version': version}
        grilling = {
            'BP/manifest.json': manifest('grilling-bp', grill_version, [
                dep('grilling-rp', grill_version),
                dep('cookery-bp', source_version),
                *([dep('missing-optional-uuid', [1, 0, 0])] if external else []),
                {'module_name': '@minecraft/server', 'version': '2.12.0-beta'},
            ]),
            'BP/entities/player.json': json.dumps({'minecraft:entity': {'description': {
                'identifier': 'minecraft:player', 'properties': {
                    'kaleidoscope_grilling:held_frame': {'type': 'int', 'range': [0, 1], 'default': 0},
                }}}}).encode(),
            'BP/scripts/main.js': b'export const originalGrilling = true;\n',
            'RP/manifest.json': manifest('grilling-rp', grill_version, [
                dep('cookery-rp', [1, 6, 4]),
            ]),
            'RP/textures/grilling.txt': b'grilling textures preserved',
        }
        cookery = {
            'BP/manifest.json': manifest('cookery-bp', cook_version, [
                dep('cookery-rp', cook_version), dep('grilling-bp', grill_version),
            ]),
            'BP/scripts/host_api.js': b'// local host capability, not the original author archive\n',
            'RP/manifest.json': manifest('cookery-rp', cook_version, [
                dep('grilling-rp', grill_version),
            ]),
            'RP/textures/cookery.txt': b'original Cookery RP bytes preserved',
        }
        paths = {}
        for key, files in (('grilling', grilling), ('cookery', cookery)):
            path = root / (key + '.mcaddon')
            with zipfile.ZipFile(path, 'w', zipfile.ZIP_DEFLATED) as archive:
                for name, raw in files.items():
                    archive.writestr(name, raw)
            paths[key] = path

        def pin(key, side, version):
            return {'id': key + '-' + side.lower(), 'input': key,
                    'uuid': key + '-' + side.lower(), 'side': side, 'version': version,
                    'modules': [{'uuid': key + '-' + side.lower() + '-module',
                                 'version': version}]}

        selected = [
            pin('grilling', 'BP', grill_version), pin('grilling', 'RP', grill_version),
            pin('cookery', 'BP', cook_version), pin('cookery', 'RP', cook_version),
        ]
        optional = [pin(key, side, [1, 0, 0])
                    for key in ('tavern', 'world-liquor', 'immersive-eating')
                    for side in ('BP', 'RP')]
        descriptor = {
            'schema': 1, 'id': 'test:owned-family', 'recipe_version': 'full-family-legacy',
            'inputs': {
                **{key: {'filename': path.name,
                         'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}
                   for key, path in paths.items()},
                **{key: {'filename': key + '.mcaddon', 'sha256': '0' * 64}
                   for key in ('tavern', 'world-liquor', 'immersive-eating')},
            },
            'packs': optional + selected,
            'order': {
                'BP': ['immersive-eating-bp', 'world-liquor-bp', 'tavern-bp',
                       'grilling-bp', 'cookery-bp'],
                'RP': ['immersive-eating-rp', 'world-liquor-rp', 'tavern-rp',
                       'grilling-rp', 'cookery-rp'],
            },
        }
        return descriptor, paths, {**grilling, **{'cookery/' + k: v for k, v in cookery.items()}}

    def test_public_minimal_reproduces_four_packs_without_optional_archives(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            descriptor, sources, entries = self.public_fixture(root)
            original_descriptor = copy.deepcopy(descriptor)
            original_hashes = {key: hashlib.sha256(path.read_bytes()).hexdigest()
                               for key, path in sources.items()}
            # This is the actual historical failure: full-family tries to open IE.
            with self.assertRaisesRegex(ValueError, 'input file missing'):
                builder.build_recipe(descriptor, root)
            recipe = builder.build_recipe(descriptor, root, 'public-minimal')
            self.assertEqual(descriptor, original_descriptor)
            self.assertEqual(set(recipe['inputs']), {'grilling', 'cookery'})
            self.assertEqual(len(recipe['packs']), 4)
            self.assertEqual(len(recipe['manifest_dependency_rebindings']), 2)
            self.assertEqual(recipe['order']['BP'], ['grilling-bp', 'cookery-bp'])
            recipe_path = root / 'public-recipe.json'
            recipe_path.write_text(json.dumps(recipe))
            output = root / 'assembled'
            receipt = assemble_family.assemble(recipe, recipe_path, root, output)
            self.assertEqual(receipt['profile'], 'public-minimal')
            self.assertEqual(len(receipt['packs']), 4)
            self.assertEqual(set(receipt['inputs']), {'grilling', 'cookery'})
            self.assertEqual(receipt['behavior_player_definition']['pack_id'], 'grilling-bp')
            self.assertTrue((output / 'public-minimal.mcaddon').is_file())
            self.assertFalse((output / 'family.mcaddon').exists())
            chosen_versions = {pack['uuid']: pack['version'] for pack in recipe['packs']}
            for pack in recipe['packs']:
                side = pack['side']
                source = 'cookery' if pack['id'].startswith('cookery') else 'grilling'
                with zipfile.ZipFile(output / (pack['id'] + '.mcpack')) as archive:
                    for name in archive.namelist():
                        if name == 'manifest.json':
                            manifest = json.loads(archive.read(name))
                            for dependency in manifest.get('dependencies', []):
                                if 'uuid' in dependency:
                                    self.assertEqual(dependency['version'],
                                                     chosen_versions[dependency['uuid']])
                        else:
                            source_name = side + '/' + name
                            expected = entries['cookery/' + source_name] if source == 'cookery' else entries[source_name]
                            self.assertEqual(archive.read(name), expected)
            with zipfile.ZipFile(output / 'public-minimal.mcaddon') as aggregate:
                self.assertEqual(set(aggregate.namelist()),
                                 {pack['id'] + '.mcpack' for pack in recipe['packs']})
                for name in aggregate.namelist():
                    self.assertEqual(aggregate.read(name), (output / name).read_bytes())
            for key, path in sources.items():
                self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), original_hashes[key])
            second = root / 'assembled-again'
            assemble_family.assemble(recipe, recipe_path, root, second)
            for name in [pack['id'] + '.mcpack' for pack in recipe['packs']] + ['public-minimal.mcaddon']:
                self.assertEqual((output / name).read_bytes(), (second / name).read_bytes())

    def test_public_minimal_cli_and_bad_inputs_fail_closed(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            descriptor, paths, _ = self.public_fixture(root)
            path = root / 'descriptor.json'
            path.write_text(json.dumps(descriptor))
            output = root / 'public-recipe.json'
            builder.main(['--profile', 'public-minimal', '--descriptor', str(path),
                          '--inputs', str(root), '--output', str(output)])
            self.assertEqual(json.loads(output.read_text())['profile'], 'public-minimal')
            # No accidental overwrite or silent fallback to an older release.
            with self.assertRaisesRegex(ValueError, 'refusing to overwrite'):
                builder.main(['--profile', 'public-minimal', '--descriptor', str(path),
                              '--inputs', str(root), '--output', str(output)])
            self.assertEqual(json.loads(output.read_text())['profile'], 'public-minimal')
            with self.assertRaisesRegex(ValueError, 'unknown installation profile'):
                builder.build_recipe(descriptor, root, 'unknown')
            changed = copy.deepcopy(descriptor)
            changed['packs'] = [p for p in changed['packs'] if p['id'] != 'cookery-rp']
            with self.assertRaisesRegex(ValueError, 'exactly one BP/RP'):
                builder.build_recipe(changed, root, 'public-minimal')
            paths['cookery'].write_bytes(b'changed Cookery source')
            with self.assertRaisesRegex(ValueError, 'input hash differs'):
                builder.build_recipe(descriptor, root, 'public-minimal')

    def test_public_minimal_rejects_unselected_manifest_dependencies_and_unrelated_rebinds(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            for scenario in ('external', 'wrong'):
                with self.subTest(scenario=scenario):
                    descriptor, _, _ = self.public_fixture(root,
                        external=scenario == 'external', wrong_version=scenario == 'wrong')
                    expected = 'unselected pack' if scenario == 'external' else 'dependency version differs'
                    with self.assertRaisesRegex(ValueError, expected):
                        builder.build_recipe(descriptor, root, 'public-minimal')
