#!/usr/bin/env python3
"""Build a user-local IE player adapter with the reviewed Grilling composer.

Author archives remain local. The public tool delegates player semantics to
the exact canonical Grilling source used by the server integration.
"""
import argparse
import io
import json
import math
from pathlib import Path
import subprocess
import sys
import tempfile
import zipfile

from export_ie_grilling_compat import export_controller
from install_cookery import _atomic_new, _read_zip, _safe_name, sha256

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DESCRIPTOR = ROOT / 'adapters/ie-grilling-2.8.206.json'


def modern_tacz_player(raw):
    """Translate the pinned TACZ legacy push flags to G's modern schema."""
    value = json.loads(raw)
    components = value['minecraft:entity']['components']
    legacy = components.get('minecraft:pushable')
    if (legacy != {'is_pushable': False, 'is_pushable_by_piston': True}
            or components.get('minecraft:pushable_by_block') != {}
            or 'minecraft:pushable_by_entity' in components):
        raise ValueError('TACZ push rules differ from the reviewed native conversion')
    # Since1.26.10, block/entity pushing use separate components. The selected
    # G player already has exactly TACZ's block-only rule. The legacy component
    # is rejected in format1.26.30 and invalidates the whole composed player.
    del components['minecraft:pushable']
    return (json.dumps(value, ensure_ascii=False, indent=2) + '\n').encode()


def compose_players(source, player, descriptor, tacz=None):
    source = Path(source).resolve()
    pin = descriptor.get('composer_source', descriptor['grilling']['source'])
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
        files = {}
        for name, expected in receipt['outputs'].items():
            if not _safe_name(name) or not name.startswith(('BP/', 'RP/')):
                raise ValueError('Unsafe player-composer output path')
            raw = (output / name).read_bytes()
            if sha256(raw) != expected:
                raise ValueError('Player-composer output hash differs: ' + name)
            files[name] = raw
        if tacz is not None:
            receipt['canonical_composer_outputs'] = receipt['outputs'].copy()
            name = 'BP/entities/player.json'
            files[name] = modern_tacz_player(files[name])
            receipt['outputs'][name] = sha256(files[name])
            receipt['native_compatibility'] = 'Legacy TACZ pushable converted to the existing modern block-only push rule; all28 properties and other components retained.'
        receipt['composer_source'] = pin
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


def advance_reviewed_dependencies(raw, *, expected_sha256, expected_version,
                                  version, latest_version, paired_uuids, rebindings, companion):
    """Advance an immutable adapter's explicitly reviewed dependency edges.

    This opt-in path is for a new diagnostic identity, not an in-place repair.
    Ordinary advance_manifest callers retain their conflicting-edge rejection.
    Callers must additionally pin and verify the complete input archive/body and
    obtain latest_version from the current reviewed identity registry.
    """
    if sha256(raw) != expected_sha256:
        raise ValueError('Dependency rebind manifest preimage differs')
    if (not isinstance(paired_uuids, (set, frozenset)) or len(paired_uuids) != 2
            or any(not isinstance(uid, str) or not uid for uid in paired_uuids)):
        raise ValueError('Dependency rebind requires exactly two paired UUIDs')
    for value in (expected_version, version, latest_version):
        if (not isinstance(value, list) or len(value) != 3
                or any(type(n) is not int or n < 0 or n > 65535 for n in value)):
            raise ValueError('Dependency rebind requires three integer version components')
    if tuple(latest_version) < tuple(expected_version) or tuple(version) <= tuple(latest_version):
        raise ValueError('Dependency rebind version must exceed the reviewed registry floor')
    def unique_object(pairs):
        value = {}
        for key, item in pairs:
            if key in value:
                raise ValueError('Duplicate manifest JSON key: ' + key)
            value[key] = item
        return value

    def reject_constant(value):
        raise ValueError('Non-finite manifest JSON constant: ' + value)

    def finite_float(value):
        number = float(value)
        if not math.isfinite(number):
            raise ValueError('Non-finite manifest JSON number')
        return number

    manifest = json.loads(raw, object_pairs_hook=unique_object,
                          parse_constant=reject_constant, parse_float=finite_float)
    if (not isinstance(manifest, dict) or not isinstance(manifest.get('header'), dict)
            or not isinstance(manifest['header'].get('uuid'), str)
            or not isinstance(manifest.get('modules'), list)
            or any(not isinstance(m, dict) for m in manifest['modules'])
            or not isinstance(manifest.get('dependencies'), list)
            or any(not isinstance(row, dict) for row in manifest['dependencies'])):
        raise ValueError('Invalid dependency rebind manifest structure')
    if (manifest['header'].get('version') != expected_version
            or manifest['header']['uuid'] not in paired_uuids
            or not manifest.get('modules')
            or any(m.get('version') != expected_version for m in manifest['modules'])):
        raise ValueError('Dependency rebind source identity differs')
    if not isinstance(rebindings, list) or not rebindings:
        raise ValueError('Dependency rebind requires explicit reviewed edges')
    if (not isinstance(companion, dict) or set(companion) != {'uuid', 'version'}
            or not isinstance(companion['uuid'], str)):
        raise ValueError('Invalid dependency rebind companion')
    dependencies = manifest.get('dependencies', [])
    if any('uuid' in row and not isinstance(row['uuid'], str) for row in dependencies):
        raise ValueError('Invalid dependency UUID type')
    source_versions = [manifest['header']['version']] + [m['version'] for m in manifest['modules']]
    source_versions += [row.get('version') for row in dependencies if 'uuid' in row]
    if any(not isinstance(value, list) or len(value) != 3
           or any(type(n) is not int or n < 0 or n > 65535 for n in value)
           for value in source_versions):
        raise ValueError('Invalid source manifest version components')
    other_uuid = next(uid for uid in paired_uuids if uid != manifest['header']['uuid'])
    paired_rows = [row for row in dependencies if row.get('uuid') in paired_uuids]
    if paired_rows != [{'uuid': other_uuid, 'version': expected_version}]:
        raise ValueError('Dependency rebind paired edge preimage differs')
    seen = set()
    for binding in rebindings:
        if not isinstance(binding, dict) or set(binding) != {'before', 'after'}:
            raise ValueError('Invalid dependency rebind record')
        before, after = binding['before'], binding['after']
        if (not isinstance(before, dict) or not isinstance(after, dict)
                or set(before) != {'uuid', 'version'} or set(after) != {'uuid', 'version'}
                or not isinstance(before['uuid'], str) or not isinstance(after['uuid'], str)
                or before['uuid'] != after['uuid'] or before['uuid'] in paired_uuids
                or before['uuid'] in seen):
            raise ValueError('Dependency rebind must preserve a unique external UUID')
        for value in (before['version'], after['version']):
            if (not isinstance(value, list) or len(value) != 3
                    or any(type(n) is not int or n < 0 or n > 65535 for n in value)):
                raise ValueError('Dependency rebind requires three integer version components')
        if tuple(after['version']) <= tuple(before['version']):
            raise ValueError('Dependency rebind requires an increasing external version')
        indices = [i for i, row in enumerate(dependencies) if row.get('uuid') == before['uuid']]
        if len(indices) != 1 or dependencies[indices[0]] != before:
            raise ValueError('Dependency rebind edge preimage differs')
        dependencies[indices[0]] = {'uuid': after['uuid'], 'version': after['version'].copy()}
        seen.add(before['uuid'])
    # Do not silently add an unreviewed companion through the ordinary helper.
    if [row for row in dependencies if row.get('uuid') == companion['uuid']] != [companion]:
        raise ValueError('Dependency rebind companion is not already reviewed')
    encoded = (json.dumps(manifest, ensure_ascii=False, indent=2, allow_nan=False) + '\n').encode()
    return advance_manifest(encoded, version, paired_uuids, companion)


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
                info.create_system = 3  # Canonical ZIP metadata is independent of the builder OS.
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
