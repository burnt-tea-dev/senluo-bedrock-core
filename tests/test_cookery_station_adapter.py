"""Exercise the real local installer; author inputs remain outside public Git."""
import copy
import hashlib
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import install_cookery
import install_cookery_from_descriptor as installer


def members(raw):
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        return {info.filename: archive.read(info) for info in archive.infolist()}


@unittest.skipUnless(os.environ.get('COOKERY_ORIGINAL_ARCHIVE') and os.environ.get('GRILLING_ADAPTED_ARCHIVE'),
                     'Clean author and public Grilling inputs required; CI supplies both')
class RealCookeryStationTests(unittest.TestCase):
    def test_real_station_owner_and_fresh_pair_preserve_other_files(self):
        cookery = Path(os.environ['COOKERY_ORIGINAL_ARCHIVE'])
        grilling = Path(os.environ['GRILLING_ADAPTED_ARCHIVE'])
        descriptor = json.loads(installer.DEFAULT_DESCRIPTOR.read_text())
        stage1, _ = install_cookery.apply_archive(cookery, grilling, descriptor)
        ready, _, _ = installer.apply_post_adapter(stage1, descriptor)
        output, changed, helper = installer.apply_station_adapter(ready, descriptor)
        before, after = members(ready), members(output)
        prefix = descriptor['prefixes']['BP']
        target = prefix + 'scripts/custom_components/blocks/directStation.js'
        added = prefix + 'scripts/api/senluo_station_performance.js'
        self.assertEqual(set(after) - set(before), {added})
        self.assertEqual(set(before) - set(after), set())
        self.assertEqual({name for name in before if before[name] != after[name]}, {target})
        self.assertEqual(after[added], (ROOT / descriptor['station_adapter']['helper_path']).read_bytes())
        self.assertEqual(hashlib.sha256(after[added]).hexdigest(), helper)
        self.assertEqual(changed, descriptor['station_adapter']['postimages'])
        for side in ('BP', 'RP'):
            doc = json.loads(after[descriptor['prefixes'][side] + 'manifest.json'])
            self.assertEqual(doc['header']['version'], [1, 6, 20009])
            self.assertTrue(all(row['version'] == [1, 6, 20009] for row in doc['modules']))
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / 'cookery.mcaddon'
            installer.main(['--cookery', str(cookery), '--grilling', str(grilling), '--output', str(path)])
            self.assertEqual(path.read_bytes(), output)
            receipt = json.loads(Path(str(path) + '.receipt.json').read_text())
            self.assertEqual(receipt['output_file_count'], len(after))
            self.assertEqual(receipt['station_adapter']['helper_sha256'], helper)

    def test_real_drift_is_rejected_at_the_station_stage(self):
        descriptor = json.loads(installer.DEFAULT_DESCRIPTOR.read_text())
        stage1, _ = install_cookery.apply_archive(Path(os.environ['COOKERY_ORIGINAL_ARCHIVE']),
                                                 Path(os.environ['GRILLING_ADAPTED_ARCHIVE']), descriptor)
        ready, _, _ = installer.apply_post_adapter(stage1, descriptor)
        altered = copy.deepcopy(descriptor)
        target = next(iter(altered['station_adapter']['preimages']))
        altered['station_adapter']['preimages'][target] = '0' * 64
        with self.assertRaisesRegex(ValueError, 'preimage differs'):
            installer.apply_station_adapter(ready, altered)
        altered = copy.deepcopy(descriptor)
        altered['station_adapter']['helper_sha256'] = '0' * 64
        with self.assertRaisesRegex(ValueError, 'helper hash differs'):
            installer.apply_station_adapter(ready, altered)


if __name__ == '__main__':
    unittest.main()
