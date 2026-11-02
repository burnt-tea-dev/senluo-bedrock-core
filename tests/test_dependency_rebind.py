import copy
import hashlib
import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from install_player_presentation import advance_manifest, advance_reviewed_dependencies


class ReviewedDependencyTests(unittest.TestCase):
    def setUp(self):
        self.old = {'header': {'uuid': 'adapter-bp', 'version': [1, 0, 4],
                               'min_engine_version': [1, 26, 60], 'name': 'Author name'},
                    'modules': [{'uuid': 'module', 'version': [1, 0, 4], 'type': 'data'}],
                    'dependencies': [{'uuid': 'adapter-rp', 'version': [1, 0, 4]},
                                     {'uuid': 'grilling-bp', 'version': [2, 8, 206]},
                                     {'uuid': 'ie-bp', 'version': [1, 1, 2]},
                                     {'module_name': '@minecraft/server', 'version': '2.0.0'}],
                    'metadata': {'authors': ['Original author'], 'custom': {'retain': True}}}
        self.raw = json.dumps(self.old).encode()
        self.kw = dict(expected_sha256=hashlib.sha256(self.raw).hexdigest(),
                       expected_version=[1, 0, 4], version=[1, 0, 10], latest_version=[1, 0, 9],
                       paired_uuids={'adapter-bp', 'adapter-rp'},
                       rebindings=[{'before': {'uuid': 'grilling-bp', 'version': [2, 8, 206]},
                                    'after': {'uuid': 'grilling-bp', 'version': [2, 8, 211]}},
                                   {'before': {'uuid': 'ie-bp', 'version': [1, 1, 2]},
                                    'after': {'uuid': 'ie-bp', 'version': [1, 1, 3]}}],
                       companion={'uuid': 'grilling-bp', 'version': [2, 8, 211]})

    def test_only_explicit_edges_and_fresh_pair_versions_change(self):
        before_args = copy.deepcopy(self.kw)
        result = json.loads(advance_reviewed_dependencies(self.raw, **self.kw))
        expected = copy.deepcopy(self.old)
        expected['header']['version'] = [1, 0, 10]
        expected['modules'][0]['version'] = [1, 0, 10]
        expected['dependencies'][0]['version'] = [1, 0, 10]
        expected['dependencies'][1]['version'] = [2, 8, 211]
        expected['dependencies'][2]['version'] = [1, 1, 3]
        self.assertEqual(result, expected)
        self.assertEqual(self.kw, before_args)
        self.assertEqual(json.loads(self.raw), self.old)

    def test_ordinary_entry_still_rejects_conflicting_companion(self):
        with self.assertRaisesRegex(ValueError, 'Conflicting Grilling'):
            advance_manifest(self.raw, self.kw['version'], self.kw['paired_uuids'], self.kw['companion'])

    def test_source_digest_identity_and_module_drift_rejected(self):
        for field, value in [('expected_sha256', '0' * 64), ('expected_version', [1, 0, 3]),
                             ('paired_uuids', {'other-bp', 'other-rp'})]:
            with self.subTest(field=field):
                kw = copy.deepcopy(self.kw)
                kw[field] = value
                with self.assertRaises(ValueError):
                    advance_reviewed_dependencies(self.raw, **kw)
        changed = copy.deepcopy(self.old)
        changed['modules'][0]['version'] = [1, 0, 3]
        raw = json.dumps(changed).encode()
        kw = {**self.kw, 'expected_sha256': hashlib.sha256(raw).hexdigest()}
        with self.assertRaisesRegex(ValueError, 'source identity'):
            advance_reviewed_dependencies(raw, **kw)

    def test_unreviewed_missing_duplicate_or_wrong_edges_rejected(self):
        variants = []
        for change in ('wrong-old', 'changed-uuid', 'reuse-edge', 'downgrade-edge', 'paired-edge'):
            kw = copy.deepcopy(self.kw)
            edge = kw['rebindings'][0]
            if change == 'wrong-old': edge['before']['version'] = [2, 8, 205]
            if change == 'changed-uuid': edge['after']['uuid'] = 'unreviewed'
            if change == 'reuse-edge': edge['after']['version'] = edge['before']['version'].copy()
            if change == 'downgrade-edge': edge['after']['version'] = [2, 8, 1]
            if change == 'paired-edge': edge['before']['uuid'] = edge['after']['uuid'] = 'adapter-rp'
            variants.append(kw)
        kw = copy.deepcopy(self.kw)
        kw['rebindings'].append(copy.deepcopy(kw['rebindings'][0]))
        variants.append(kw)
        variants.extend([{**self.kw, 'rebindings': []},
                         {**self.kw, 'companion': {'uuid': 'new', 'version': [1, 0, 0]}},
                         {**self.kw, 'version': [1, 0, 4]},
                         {**self.kw, 'version': [1, 0, True]},
                         {**self.kw, 'version': [1, 0, 65536]}])
        for i, kw in enumerate(variants):
            with self.subTest(case=i), self.assertRaises(ValueError):
                advance_reviewed_dependencies(self.raw, **kw)
        for rows in (self.old['dependencies'] + [self.old['dependencies'][1]],
                     [r for r in self.old['dependencies'] if r.get('uuid') != 'grilling-bp']):
            changed = {**self.old, 'dependencies': rows}
            raw = json.dumps(changed).encode()
            kw = {**self.kw, 'expected_sha256': hashlib.sha256(raw).hexdigest()}
            with self.assertRaisesRegex(ValueError, 'edge preimage'):
                advance_reviewed_dependencies(raw, **kw)

    def test_pair_scope_and_registry_floor_fail_closed(self):
        for kwargs in ({'paired_uuids': {'adapter-bp', 'adapter-rp', 'ie-bp'}},
                       {'paired_uuids': ['adapter-bp', 'adapter-rp']},
                       {'latest_version': [1, 0, 10]}, {'latest_version': [1, 0, 3]}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                advance_reviewed_dependencies(self.raw, **{**self.kw, **kwargs})
        for paired in ([{'uuid': 'adapter-rp', 'version': [1, 0, 3]}],
                       [self.old['dependencies'][0], self.old['dependencies'][0]],
                       [{'uuid': 'adapter-bp', 'version': [1, 0, 4]}], []):
            changed = {**self.old, 'dependencies': paired + self.old['dependencies'][1:]}
            raw = json.dumps(changed).encode()
            with self.assertRaisesRegex(ValueError, 'paired edge preimage'):
                advance_reviewed_dependencies(raw, **{**self.kw,
                    'expected_sha256': hashlib.sha256(raw).hexdigest()})

    def test_ambiguous_or_malformed_json_and_records_rejected(self):
        bad_documents = [[], {**self.old, 'header': []}, {**self.old, 'modules': [None]},
                         {**self.old, 'dependencies': [None]},
                         {**self.old, 'metadata': float('nan')},
                         {**self.old, 'dependencies': [{'uuid': [], 'version': [1, 0, 4]}]}]
        bool_version = copy.deepcopy(self.old)
        bool_version['dependencies'][0]['version'][0] = True
        bad_documents.append(bool_version)
        bad_raw = [json.dumps(value).encode() for value in bad_documents]
        bad_raw.append(self.raw.replace(b'"name": "Author name"', b'"name": "First", "name": "Last"'))
        bad_raw.append(self.raw.replace(b'"retain": true', b'"retain": 1e999'))
        for raw in bad_raw:
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                advance_reviewed_dependencies(raw, **{**self.kw,
                    'expected_sha256': hashlib.sha256(raw).hexdigest()})
        for record in (None, 'bad', [None], [{'before': None, 'after': {}}]):
            with self.subTest(record=record), self.assertRaises(ValueError):
                advance_reviewed_dependencies(self.raw, **{**self.kw, 'rebindings': record})


if __name__ == '__main__':
    unittest.main()
