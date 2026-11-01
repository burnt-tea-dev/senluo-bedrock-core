#!/usr/bin/env python3
"""Build a user-local IE player adapter with the reviewed Grilling composer.

Author archives remain local. The public tool delegates player semantics to
the exact canonical Grilling source used by the server integration.
"""
import argparse
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import zipfile

from export_ie_grilling_compat import export_controller
from install_cookery import _atomic_new, _read_zip, sha256

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DESCRIPTOR = ROOT / 'adapters/ie-grilling-2.8.206.json'


def compose_players(source, player, descriptor, tacz=None):
    source = Path(source).resolve()
    pin = descriptor['grilling']['source']
    def git(*args):
        return subprocess.check_output(['git', *args], cwd=source, text=True).strip()
    if (git('rev-parse', 'HEAD') != pin['commit']
            or git('rev-parse', 'HEAD^{tree}') != pin['git_tree']
            or git('status', '--porcelain')):
        raise ValueError('Grilling composer checkout differs from reviewed source')
    if tacz is not None and sha256(Path(tacz).read_bytes()) != descriptor['tacz']['archive_sha256']:
        raise ValueError('TACZ archive differs from reviewed source')
    with tempfile.TemporaryDirectory(prefix='senluo-player-') as directory:
        directory = Path(directory)
        host = directory / 'player.json'
        host.write_bytes(player)
        output = directory / 'output'
        command = [sys.executable, str(source / 'tools/compose_held_player.py'),
                   '--host-player', str(host), '--host-sha256', sha256(player),
                   '--output', str(output)]
        if tacz is not None:
            command.extend(['--tacz', str(Path(tacz).resolve())])
        subprocess.run(command, check=True, capture_output=True, text=True)
        receipt = json.loads((output / 'receipt.json').read_bytes())
        files = {name: (output / name).read_bytes() for name in receipt['outputs']}
        return files, receipt


def advance_manifest(raw, version, paired_uuids, companion, minimum=None):
    manifest = json.loads(raw)
    before = manifest['header']['version']
    if tuple(version) <= tuple(before):
        raise ValueError('Local adapter needs a fresh increasing paired version')
    manifest['header']['version'] = version.copy()
    for module in manifest['modules']:
        module['version'] = version.copy()
    for dependency in manifest.get('dependencies', []):
        if dependency.get('uuid') in paired_uuids:
            dependency['version'] = version.copy()
    if minimum is not None:
        if tuple(minimum) < tuple(manifest['header']['min_engine_version']):
            raise ValueError('Cannot lower the author engine requirement')
        manifest['header']['min_engine_version'] = minimum.copy()
    dependencies = manifest.setdefault('dependencies', [])
    existing = [row for row in dependencies if row.get('uuid') == companion['uuid']]
    if existing:
        if existing != [companion]:
            raise ValueError('Conflicting Grilling dependency')
    else:
        dependencies.append(companion)
    return (json.dumps(manifest, ensure_ascii=False, indent=2) + '\n').encode()


def apply_archive(ie, grilling, source, descriptor, tacz=None):
    if tacz is not None:
        raise ValueError('TACZ needs the reviewed single behavior-player owner adapter')
    ie, grilling = Path(ie), Path(grilling)
    pin = descriptor['immersive_eating']
    if sha256(ie.read_bytes()) != pin['archive_sha256']:
        raise ValueError('IE archive differs from reviewed source')
    # This also verifies the Grilling archive, exact player and both controller
    # preimages. Replacing IE's controller in place avoids duplicate owners.
    controller, controller_receipt = export_controller(ie, grilling, descriptor)
    archive, entries = _read_zip(ie)
    try:
        originals = {name: raw for name, (_, raw) in entries.items()}
        roots = {}
        for name, raw in originals.items():
            if not name.endswith('/manifest.json'):
                continue
            uid = json.loads(raw)['header']['uuid']
            for side in ('BP', 'RP'):
                if uid == pin[side.lower() + '_uuid']:
                    if side in roots:
                        raise ValueError('Duplicate IE pack identity')
                    roots[side] = name[:-len('manifest.json')]
        if set(roots) != {'BP', 'RP'}:
            raise ValueError('Missing paired IE identities')
        players, receipt = compose_players(source, originals[pin['player_entity_path']], descriptor, tacz)
        # G206 supplies BP/entities/player.json. Keep exactly one behavior owner.
        changed = {roots['RP'] + 'entity/player.entity.json': players['RP/entity/player.entity.json']}
        changed[pin['controller_path']] = controller
        for side in ('BP', 'RP'):
            name = roots[side] + 'manifest.json'
            changed[name] = advance_manifest(originals[name], descriptor['output_version'],
                {pin['bp_uuid'], pin['rp_uuid']},
                {'uuid': descriptor['grilling'][side.lower() + '_uuid'],
                 'version': descriptor['grilling']['version'].copy()},
                descriptor['behavior_min_engine_version'] if side == 'BP' else None)
        files = {**originals, **changed}
        output = io.BytesIO()
        with zipfile.ZipFile(output, 'w', zipfile.ZIP_DEFLATED, compresslevel=9) as target:
            for name, raw in files.items():
                info = zipfile.ZipInfo(name, (2026, 9, 29, 0, 0, 0))
                info.compress_type = zipfile.ZIP_DEFLATED
                info.external_attr = 0o100644 << 16
                target.writestr(info, raw)
        result = output.getvalue()
        receipt.update(toolkit_version=descriptor['toolkit_version'], adapter=descriptor['id'],
                       version=descriptor['output_version'], output_sha256=sha256(result),
                       ie_archive_sha256=pin['archive_sha256'],
                       grilling_source=descriptor['grilling']['source'],
                       controller=controller_receipt,
                       changed_files={name: sha256(raw) for name, raw in changed.items()},
                       preserved_author_files=sum(name not in changed for name in originals),
                       behavior_player_owner='Grilling; no duplicate added to IE',
                       distribution='user-local only; never a public release asset')
        return result, receipt
    finally:
        archive.close()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--ie', type=Path, required=True)
    parser.add_argument('--grilling', type=Path, required=True)
    parser.add_argument('--grilling-source', type=Path, required=True)
    parser.add_argument('--descriptor', type=Path, default=DEFAULT_DESCRIPTOR)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args(argv)
    receipt_path = Path(str(args.output) + '.receipt.json')
    if args.output.exists() or receipt_path.exists():
        parser.error('Choose a new output and receipt path')
    descriptor = json.loads(args.descriptor.read_bytes())
    raw, receipt = apply_archive(args.ie, args.grilling, args.grilling_source, descriptor)
    _atomic_new(args.output, raw)
    _atomic_new(receipt_path, (json.dumps(receipt, ensure_ascii=False, indent=2) + '\n').encode())
    print(json.dumps({'output': str(args.output), 'sha256': sha256(raw),
                      'player_properties': receipt['player_properties'], 'client': False}))


if __name__ == '__main__':
    main()
