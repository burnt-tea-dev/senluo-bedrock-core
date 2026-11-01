import copy
import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from install_player_presentation import advance_manifest


class PlayerManifestTests(unittest.TestCase):
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
