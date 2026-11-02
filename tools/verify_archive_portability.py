"""Compare real pinned installers under Linux and Windows ZIP defaults.

Only zipfile's platform selection is simulated. Real source/author validation,
composition, serialization and ZIP writers execute; this is not client QA.
"""
import argparse
import hashlib
import json
from pathlib import Path
import tempfile
from unittest.mock import patch
import zipfile

import build_grilling_input
import build_release
import install_cookery
import install_cookery_from_descriptor as cookery
import install_player_presentation as eating
import install_tacz as tacz

ROOT = Path(__file__).resolve().parents[1]


def verify(source, original_cookery, original_ie, original_tacz, composer_source=None, source_sounds=None):
    descriptor = json.loads(cookery.DEFAULT_DESCRIPTOR.read_bytes())
    family = json.loads((ROOT / 'adapters/owned-t194-g208-w180-station-performance-tacz.json').read_bytes())
    expected = {key: family['inputs'][key]['sha256'] for key in ('grilling', 'cookery', 'immersive-eating', 'tacz')}
    reference = None
    rows = {}
    with tempfile.TemporaryDirectory(prefix='senluo-zip-platform-') as temporary:
        for platform in ('linux', 'win32'):
            with patch.object(zipfile.sys, 'platform', platform):
                g = build_grilling_input.build(source)
                gpath = Path(temporary) / (platform + '-grilling.mcaddon')
                gpath.write_bytes(g)
                first, _ = install_cookery.apply_archive(original_cookery, gpath, descriptor)
                adapted, _, _ = cookery.apply_post_adapter(first, descriptor)
                adapted, _, _ = cookery.apply_station_adapter(adapted, descriptor)
                ie, _ = eating.apply_archive(original_ie, gpath, source, json.loads(eating.DEFAULT_DESCRIPTOR.read_bytes()))
                guns, _ = tacz.apply_archive(original_tacz, original_ie, gpath, composer_source or source, json.loads(tacz.DEFAULT_DESCRIPTOR.read_bytes()), source_sounds)
                sdk = build_release.archive(build_release.sdk_files(json.loads((ROOT / 'sdk.json').read_bytes())))
                outputs = {'grilling': g, 'cookery': adapted, 'immersive-eating': ie, 'tacz': guns, 'sdk': sdk}
                hashes = {name: hashlib.sha256(raw).hexdigest() for name, raw in outputs.items()}
                for name, digest in expected.items():
                    if hashes[name] != digest:
                        raise ValueError(platform + ' output differs from pinned archive: ' + name)
                if reference is None:
                    reference = outputs
                elif outputs != reference:
                    raise ValueError('Platform-dependent archive bytes')
                rows[platform] = hashes
    return {'platform_zip_defaults': rows, 'all_archives_byte_identical': True,
            'archives_match_current_descriptor': True, 'native_loading': False, 'client': False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--grilling-source', type=Path, required=True)
    parser.add_argument('--cookery', type=Path, required=True)
    parser.add_argument('--ie', type=Path, required=True)
    parser.add_argument('--tacz', type=Path, required=True)
    parser.add_argument('--composer-source', type=Path)
    parser.add_argument('--source-assets', '--source-sounds', dest='source_sounds', type=Path)
    args = parser.parse_args()
    print(json.dumps(verify(args.grilling_source, args.cookery, args.ie, args.tacz, args.composer_source, args.source_sounds)))


if __name__ == '__main__':
    main()
