import hashlib
from pathlib import Path
import subprocess
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from tacz_startup import prepare_script, prepare_scripts


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


class TaczStartupTests(unittest.TestCase):
    def fixture(self):
        bootstrap = b'(function(){const t=table();t.push(t.shift());})();'
        raw = bootstrap + b"function table(){const t=['C','A','B'];table=()=>t;return t;}const gameplay=()=>table().join('');process.stdout.write(gameplay());"
        expected = b"function table(){const t=['A','B','C'];table=()=>t;return t;}const gameplay=()=>table().join('');process.stdout.write(gameplay());"
        start = raw.index(b'[')
        end = raw.index(b']', start) + 1
        row = {'path': 'scripts/example.js', 'sha256': digest(raw),
               'table_span': [start, end], 'rotate_span': [0, len(bootstrap)],
               'strings': 3, 'offset': 1, 'output_sha256': digest(expected)}
        return raw, expected, row

    def test_prepared_table_keeps_observable_gameplay_and_other_files(self):
        raw, expected, row = self.fixture()
        originals = {row['path']: raw, 'scripts/other.js': b'untouched'}
        result = prepare_scripts(originals, {'scripts': [row]})
        self.assertEqual(result, {row['path']: expected})
        self.assertEqual(originals[row['path']], raw)
        for source in (raw, result[row['path']]):
            self.assertEqual(subprocess.check_output(['node', '-e', source.decode()]), b'ABC')

    def test_refuses_changed_author_bytes_or_unreviewed_output(self):
        raw, _, row = self.fixture()
        with self.assertRaisesRegex(ValueError, 'preimage'):
            prepare_script(raw + b' ', row)
        with self.assertRaisesRegex(ValueError, 'postimage'):
            prepare_script(raw, {**row, 'offset': 2})


if __name__ == '__main__':
    unittest.main()
