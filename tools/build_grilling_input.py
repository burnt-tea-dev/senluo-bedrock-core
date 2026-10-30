"""Reproduce the pinned Grilling input from its public source checkout.

This local export is not a new gameplay release or a family admission receipt.
"""
import argparse
import io
import json
from pathlib import Path
import zipfile

from install_cookery import _atomic_new, sha256

ROOT = Path(__file__).resolve().parents[1]
TREES = {
    'BP': {'sha256': '439564eb07f36b110e6d526d3e0318f1f517309b6c2b395e04bf2250fd9e33c1', 'files': 787},
    'RP': {'sha256': '8cdf8c0091bcfcbddd17653219d90cff333c251608e385ccdc37d5a1005fd353', 'files': 2859},
}


def build(source):
    payloads = {}
    for side, folder in [('BP', 'behavior_pack'), ('RP', 'resource_pack')]:
        root = source / 'projects/grilling/gameplay_core' / folder
        if root.is_symlink() or any(parent.is_symlink() for parent in root.parents):
            raise ValueError('Source pack is linked')
        records = {}
        for path in sorted(root.rglob('*')):
            if path.is_symlink():
                raise ValueError('Linked file in source runtime')
            if path.is_file():
                name = path.relative_to(root).as_posix()
                raw = path.read_bytes()
                records[name] = sha256(raw)
                payloads[side + '/' + name] = raw
        actual = {'sha256': sha256(json.dumps(records, sort_keys=True, separators=(',', ':')).encode()), 'files': len(records)}
        if actual != TREES[side]:
            raise ValueError('Source runtime differs from the reviewed Grilling 2.8.201 tree: ' + side)
    output = io.BytesIO()
    with zipfile.ZipFile(output, 'w', zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name, raw in payloads.items():
            info = zipfile.ZipInfo(name, (2026, 9, 29, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, raw)
    result = output.getvalue()
    descriptor = json.loads((ROOT / 'adapters/cookery-1.6.4.json').read_text())
    if sha256(result) != descriptor['companion']['archive_sha256']:
        raise ValueError('Local ZIP differs from the pinned Grilling input; retain the original lock')
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    raw = build(args.source)
    _atomic_new(args.output, raw)
    print(json.dumps({'output': str(args.output), 'sha256': sha256(raw)}))
