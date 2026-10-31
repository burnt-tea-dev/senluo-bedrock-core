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
