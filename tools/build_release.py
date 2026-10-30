"""Build a source/SDK release from the explicit public file allowlist."""
import argparse
import hashlib
import io
import json
from pathlib import Path
import subprocess
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def validate():
    publication = json.loads((ROOT / 'PUBLICATION.json').read_text())
    names = publication['files']
    tracked = subprocess.check_output(['git', 'ls-files', '-z'], cwd=ROOT).decode().split('\0')
    if set(names) != set(filter(None, tracked)) or len(names) != len(set(names)):
        raise ValueError('Tracked files differ from the explicit publication allowlist')
    sdk = json.loads((ROOT / 'sdk.json').read_text())
    history = json.loads((ROOT / 'release-history.json').read_text())
    release = history[sdk['version']]
    payloads = release['payloads']
    for name, expected in payloads.items():
        if digest((ROOT / name).read_bytes()) != expected:
            raise ValueError('Release payload changed without a fresh identity: ' + name)
    for row in sdk['files'].values():
        if digest((ROOT / row['source']).read_bytes()) != row['sha256'] or row['source'] not in payloads:
            raise ValueError('SDK source differs from its release manifest')
    for name in names:
        path = ROOT / name
        if path.is_symlink() or not path.is_file() or not path.resolve().is_relative_to(ROOT):
            raise ValueError('Publication input is not a regular source file: ' + name)
    return sdk, names, release


def archive(files):
    output = io.BytesIO()
    with zipfile.ZipFile(output, 'w', zipfile.ZIP_DEFLATED) as writer:
        for name in sorted(files):
            info = zipfile.ZipInfo(name, (2026, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            writer.writestr(info, (ROOT / name).read_bytes())
    return output.getvalue()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    sdk, names, release = validate()
    output = args.output.resolve()
    if output.exists():
        raise ValueError('Choose a new output directory')
    output.mkdir(parents=True)
    version = sdk['version']
    assets = {'senluo-core-' + version + '-source.zip': archive(names),
              'senluo-core-' + version + '-sdk.zip': archive(['LICENSE', 'sdk.json', *[v['source'] for v in sdk['files'].values()]])}
    for name, raw in assets.items():
        (output / name).write_bytes(raw)
    (output / 'SHA256SUMS').write_text(''.join(digest(raw) + '  ' + name + '\n' for name, raw in assets.items()))
    print(json.dumps({'version': version, 'files': len(names), 'assets': {name: digest(raw) for name, raw in assets.items()}, 'cookery_version': release['cookery_version']}))


if __name__ == '__main__':
    main()
