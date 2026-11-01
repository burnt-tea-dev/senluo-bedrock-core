"""Exercise current/default and explicit historical entry points with synthetic inputs.

Only descriptor file reads are substituted. Builders, ZIP/hash checks, recipe
assembly and output writes execute normally; this is not author/client QA.
"""
import copy
from contextlib import redirect_stdout
import hashlib
import io
import json
from pathlib import Path
import runpy
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import assemble_family
import build_grilling_input as grilling
import build_owned_family_recipe as family
import install_cookery_from_descriptor as cookery
import test_build_owned_family_recipe as family_fixtures


def descriptor_reads(descriptors):
    """Replace only named descriptor reads, not hashes, payloads or builders."""
    original = Path.read_text

    def read(path, *args, **kwargs):
        if path in descriptors:
            return json.dumps(descriptors[path])
        return original(path, *args, **kwargs)

    return patch.object(Path, 'read_text', read)


def grilling_fixture(root):
    source = root / 'source'
    trees = {}
    for side, folder in [('BP', 'behavior_pack'), ('RP', 'resource_pack')]:
        pack = source / 'projects/grilling/gameplay_core' / folder
        pack.mkdir(parents=True)
        raw = (side + ' synthetic payload\n').encode()
        (pack / 'payload.txt').write_bytes(raw)
        files = {'payload.txt': hashlib.sha256(raw).hexdigest()}
        trees[side] = {'files': len(files), 'sha256': hashlib.sha256(
            json.dumps(files, sort_keys=True, separators=(',', ':')).encode()).hexdigest()}
    descriptor = {'companion': {'runtime_trees': trees}}
    output = grilling.build(source, descriptor)
    descriptor['companion']['archive_sha256'] = hashlib.sha256(output).hexdigest()
    return source, descriptor, output


def grilling_cli(source, output, descriptor=None):
    argv = [str(ROOT / 'tools/build_grilling_input.py'), '--source', str(source),
            '--output', str(output)]
    if descriptor is not None:
        argv += ['--descriptor', str(descriptor)]
    with patch.object(sys, 'argv', argv), redirect_stdout(io.StringIO()):
        runpy.run_path(argv[0], run_name='__main__')


class CurrentInstallationTests(unittest.TestCase):
    def test_grilling_default_function_and_cli_follow_cookery_selection(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            source, current, expected = grilling_fixture(root)
            historical = copy.deepcopy(current)
            historical['companion']['runtime_trees']['BP']['sha256'] = '0' * 64
            with descriptor_reads({cookery.DEFAULT_DESCRIPTOR: current,
                                   ROOT / 'adapters/cookery-1.6.4.json': historical}):
                self.assertEqual(grilling.build(source), expected)
                output = root / 'current.mcaddon'
                grilling_cli(source, output)
                self.assertEqual(output.read_bytes(), expected)

    def test_explicit_historical_grilling_selection_still_rebuilds(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            source, historical, expected = grilling_fixture(root)
            path = root / 'historical.json'
            path.write_text(json.dumps(historical))
            rejected_default = copy.deepcopy(historical)
            rejected_default['companion']['runtime_trees']['BP']['sha256'] = '0' * 64
            with descriptor_reads({cookery.DEFAULT_DESCRIPTOR: rejected_default}):
                self.assertEqual(grilling.build(source, path), expected)
                output = root / 'historical.mcaddon'
                grilling_cli(source, output, path)
                self.assertEqual(output.read_bytes(), expected)

    def test_grilling_rejects_tree_and_archive_drift_without_output(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            source, descriptor, _ = grilling_fixture(root)
            for failure in ('tree', 'archive'):
                rejected = copy.deepcopy(descriptor)
                if failure == 'tree':
                    rejected['companion']['runtime_trees']['BP']['sha256'] = '0' * 64
                    message = 'reviewed Grilling tree'
                else:
                    rejected['companion']['archive_sha256'] = '0' * 64
                    message = 'Local ZIP differs'
                path = root / (failure + '.json')
                path.write_text(json.dumps(rejected))
                output = root / (failure + '.mcaddon')
                with self.subTest(failure=failure), self.assertRaisesRegex(ValueError, message):
                    grilling_cli(source, output, path)
                self.assertFalse(output.exists())

    def test_grilling_does_not_fallback_or_overwrite(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            source, descriptor, _ = grilling_fixture(root)
            output = root / 'output.mcaddon'
            with self.assertRaises(FileNotFoundError):
                grilling_cli(source, output, root / 'missing.json')
            self.assertFalse(output.exists())
            path = root / 'explicit.json'
            path.write_text(json.dumps(descriptor))
            output.write_bytes(b'previous reviewed output')
            with self.assertRaises(FileExistsError):
                grilling_cli(source, output, path)
            self.assertEqual(output.read_bytes(), b'previous reviewed output')

    def family_fixture(self, root):
        current, entries, archive = family_fixtures.OwnedFamilyRecipeTests().fixture(root)
        current['id'] = 'synthetic:current-selection'
        historical = copy.deepcopy(current)
        historical['id'] = 'synthetic:historical-selection'
        reads = {
            ROOT / 'adapters/owned-t194-g206-w180-cookery-recipe-index.json': current,
            ROOT / 'adapters/owned-t194-g203-w180.json': historical,
        }
        return current, historical, entries, archive, reads

    def test_family_default_cli_selects_current_and_reassembles_original_bytes(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            current, _, entries, _, reads = self.family_fixture(root)
            output = root / 'recipe.json'
            with descriptor_reads(reads), redirect_stdout(io.StringIO()):
                family.main(['--inputs', str(root), '--output', str(output)])
            recipe = json.loads(output.read_text())
            self.assertEqual(recipe['id'], current['id'])
            self.assertEqual(recipe['order'], current['order'])
            assembled = root / 'assembled'
            assemble_family.assemble(recipe, output, root, assembled)
            for side in ('BP', 'RP'):
                with zipfile.ZipFile(assembled / ('owned-' + side.lower() + '.mcpack')) as archive:
                    expected = {name[3:]: raw for name, raw in entries.items() if name.startswith(side + '/')}
                    self.assertEqual({name: archive.read(name) for name in archive.namelist()}, expected)

    def test_explicit_historical_family_selection_is_not_redirected(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _, historical, _, _, reads = self.family_fixture(root)
            output = root / 'recipe.json'
            with descriptor_reads(reads), redirect_stdout(io.StringIO()):
                family.main(['--inputs', str(root), '--output', str(output), '--descriptor',
                             str(ROOT / 'adapters/owned-t194-g203-w180.json')])
            self.assertEqual(json.loads(output.read_text())['id'], historical['id'])

    def test_family_default_rejects_changed_input_without_output(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _, _, _, archive, reads = self.family_fixture(root)
            archive.write_bytes(b'unreviewed input')
            output = root / 'recipe.json'
            with descriptor_reads(reads), self.assertRaisesRegex(ValueError, 'input hash differs'):
                family.main(['--inputs', str(root), '--output', str(output)])
            self.assertFalse(output.exists())


if __name__ == '__main__':
    unittest.main()
