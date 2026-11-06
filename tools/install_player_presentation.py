#!/usr/bin/env python3
"""Build a user-local IE player adapter with the reviewed Grilling composer.

Author archives remain local. The public tool delegates player semantics to
the exact canonical Grilling source used by the server integration.
"""
import argparse
import io
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import zipfile

from export_ie_grilling_compat import export_controller
from install_cookery import _atomic_new, _read_zip, _safe_name, sha256
from paired_release import advance_manifest as advance_paired_manifest

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DESCRIPTOR = ROOT / 'adapters/ie-grilling-2.8.212.json'
LEFT_ARM_REQUEST = 'variable.senluo_fp_left_arm_request'


def _inherit_part_visibility(controller, children):
    """Keep each new mesh on its original limb/skin-layer visibility gate."""
    if (not isinstance(children, dict)
            or any(not isinstance(name, str) or not re.fullmatch(r'[A-Za-z_]\w*', name)
                   for pair in children.items() for name in pair)
            or any(parent in children for parent in children.values())):
        raise ValueError('Child parts need distinct literal bones and original parent bones')
    for selected in controller['render_controllers'].values():
        # Gun/armor geometry has its own skeleton and must retain its routes.
        if selected.get('geometry', '').lower() != 'geometry.default':
            continue
        original = selected.get('part_visibility', [])
        parts = [{name: gate for name, gate in row.items() if name not in children}
                 for row in original]
        parts = [row for row in parts if row]
        additions = []
        for child, parent in children.items():
            gate = True
            for row in parts:
                for pattern, condition in row.items():
                    # Bedrock applies wildcard rules in order, with later
                    # matches replacing earlier ones (including the FP '*').
                    if re.fullmatch(re.escape(pattern).replace(r'\*', '.*'), parent):
                        gate = condition
            additions.append({child: gate})
        if additions:
            selected['part_visibility'] = parts + additions


def compose_first_person_arm_request(player_raw, controller_raw, *,
                                     request_variables=(LEFT_ARM_REQUEST,), child_parts=None):
    """Extend one selected player/controller pair; do not add another owner.

    Each active animation owns a request variable. Clearing before animations
    prevents a completed or interrupted clip from leaving the arm requested.
    Client evaluation order and the rendered pose still need observation.
    """
    if isinstance(request_variables, (str, bytes)):
        raise ValueError('Arm requests need a sequence of variable names')
    request_variables = tuple(request_variables)
    if (not request_variables
            or any(not isinstance(name, str)
                   or not re.fullmatch(r'variable\.[a-z][a-z0-9_]*', name)
                   for name in request_variables)):
        raise ValueError('Arm requests need simple lowercase variable names')
    if len(set(request_variables)) != len(request_variables):
        raise ValueError('Arm request variables must be distinct')
    player = json.loads(player_raw)
    controller = json.loads(controller_raw)
    description = player['minecraft:client_entity']['description']
    if description.get('identifier') != 'minecraft:player':
        raise ValueError('Arm requests need the selected minecraft:player')
    parts = controller['render_controllers']['controller.render.player.first_person']['part_visibility']
    left = [(row, name) for row in parts for name in ('leftArm', 'leftSleeve') if name in row]
    if sorted(name for _, name in left) != ['leftArm', 'leftSleeve']:
        raise ValueError('Selected first-person controller needs one left arm and sleeve')
    if any(not isinstance(row[name], str) for row, name in left):
        raise ValueError('Selected left-arm visibility must contain Molang conditions')
    before = description.setdefault('scripts', {}).setdefault('pre_animation', [])
    missing = []
    # A retained single-channel pair may gain another provider. Keep complete
    # fragments, including the legacy channel, and reject disconnected halves.
    for variable in dict.fromkeys((LEFT_ARM_REQUEST, *request_variables)):
        reset = variable + '=0.0;'
        token = r'(?<![\w.])' + re.escape(variable) + r'(?![\w.])'
        term = r' \|\| ' + re.escape(variable) + r'(?![\w.])'
        complete = (before.count(reset) == 1
                    and all(re.search(term, row[name]) for row, name in left))
        if complete:
            continue
        if any(re.search(token, value) for value in [*before, *(row[name] for row, name in left)]):
            raise ValueError('Selected player/controller has a partial arm-request fragment')
        if variable in request_variables:
            missing.append(variable)
    for variable in missing:
        before.append(variable + '=0.0;')
        for row, name in left:
            row[name] = '(' + row[name] + ') || ' + variable
    if child_parts is not None:
        _inherit_part_visibility(controller, child_parts)
    # Existing callers and a repeated complete composition retain exact bytes.
    return tuple(raw if value == json.loads(raw) else
                 (json.dumps(value, ensure_ascii=False, indent=2) + '\n').encode()
                 for raw, value in ((player_raw, player), (controller_raw, controller)))


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
    manifest = json.loads(advance_paired_manifest(raw, version, paired_uuids))
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
