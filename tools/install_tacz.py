#!/usr/bin/env python3
"""Build the reviewed user-local TACZ pair with the canonical player composer.

Gameplay/animation rules belong to the pinned Grilling source. This installer
preserves author identities and unrelated payloads, and never deploys a pack.
"""
import argparse
import copy
import io
import json
from pathlib import Path
import zipfile

from export_ie_grilling_compat import export_controller
from install_cookery import _atomic_new, _read_zip, _safe_name, sha256
from install_player_presentation import advance_manifest, compose_players
from assemble_family import read_definition
from tacz_startup import prepare_scripts

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DESCRIPTOR = ROOT / 'adapters/tacz-1.0.3-grilling-2.8.206.json'
FP = 'controller.render.player.first_person'
OFFHAND_FP = 'controller.render.kg_tacz.offhand_first_person'
OFFHAND = "q.is_item_equipped('off_hand')"


def offhand_controller(controller):
    result = copy.deepcopy(controller)
    rows = result.get('part_visibility', [])
    if {key for row in rows for key in row} != {'*', 'rightArm', 'rightSleeve', 'leftArm', 'leftSleeve'} or rows[0] != {'*': False}:
        raise ValueError('Unreviewed native first-person arm visibility')
    for row in rows:
        for bone in ('rightArm', 'rightSleeve'):
            if bone in row:
                row[bone] = False
    return result


def adapt_files(originals, composed, controller, descriptor):
    pin = descriptor['tacz']
    roots = pin['prefixes']
    old_player = roots['BP'] + 'entities/plalyer.json'
    player = roots['BP'] + 'entities/player.json'
    if old_player not in originals or player in originals:
        raise ValueError('TACZ behavior player preimage differs')
    schema = json.loads(composed['BP/entities/player.json'])['minecraft:entity']['description']
    if schema.get('identifier') != 'minecraft:player' or len(schema.get('properties', {})) > 32:
        raise ValueError('Invalid composed behavior player')
    changed = {player: composed['BP/entities/player.json']}
    awp_path = roots['BP'] + 'entities/bullet/awp.json'
    awp_raw = originals[awp_path]
    awp = read_definition(awp_raw)
    breaking = awp['minecraft:entity']['components']['minecraft:break_blocks']
    if breaking['breakable_blocks'] != ['glass', 'glass_panel', 'stained_glass', 'stained_glass_panel', 'wheat']:
        raise ValueError('TACZ AWP block names differ from the reviewed native repair')
    # The author meant glass panes. The two "panel" spellings fail native
    # registry lookup and prevent this projectile's break-block component.
    for before, after in [(b'"glass_panel"', b'"glass_pane"'),
                          (b'"stained_glass_panel"', b'"stained_glass_pane"')]:
        if awp_raw.count(before) != 1:
            raise ValueError('TACZ AWP block spelling must occur exactly once')
        awp_raw = awp_raw.replace(before, after, 1)
    changed[awp_path] = awp_raw
    client_path = roots['RP'] + 'entity/player.entity.json'
    for name, raw in composed.items():
        if name == 'BP/entities/player.json':
            continue
        if not _safe_name(name) or not name.startswith('RP/'):
            raise ValueError('Unexpected player-composer output path')
        target = roots['RP'] + name.removeprefix('RP/')
        if target not in originals:
            raise ValueError('Missing reviewed TACZ resource preimage: ' + target)
        changed[target] = raw
    client = json.loads(changed[client_path])
    client['minecraft:client_entity']['description']['render_controllers'].append({
        OFFHAND_FP: "v.is_first_person && !q.is_spectator && v.holding_all_guns && " + OFFHAND})
    changed[client_path] = (json.dumps(client, ensure_ascii=False, indent=2) + '\n').encode()
    # Use the same virtual path as Grilling. The reviewed TACZ profile selects
    # this merged 28-field owner above the unchanged four-field source pack.
    # The filename is not an entity identity or a persisted save key.
    result = {name: raw for name, raw in originals.items() if name != old_player}
    merged_controller = json.loads(controller)['render_controllers'][FP]
    controller_paths = []
    for name, raw in originals.items():
        if not name.startswith(roots['RP'] + 'render_controllers/') or not name.endswith('.json'):
            continue
        document = json.loads(raw)
        modified = False
        if FP in document.get('render_controllers', {}):
            controller_paths.append(name)
            document['render_controllers'][FP] = merged_controller
            modified = True
        for alias, value in document.get('render_controllers', {}).items():
            if alias == FP or not alias.startswith('controller.render.player.') or not alias.endswith('.first_person'):
                continue
            # Gun viewmodels have extra animated parent rigs. Hide their left
            # arm meshes while the normal skeleton renders the occupied hand;
            # otherwise IE/Grilling motion would still inherit a magazine rig.
            for row in value.get('part_visibility', []):
                for bone in ('leftArm', 'leftSleeve'):
                    if bone in row:
                        expression = str(int(row[bone])) if isinstance(row[bone], bool) else row[bone]
                        row[bone] = '(' + expression + ') && !(' + OFFHAND + ')'
                        modified = True
        if modified:
            changed[name] = (json.dumps(document, ensure_ascii=False, indent=2) + '\n').encode()
    if len(controller_paths) != 1:
        raise ValueError('Expected one TACZ generic first-person controller')
    changed[roots['RP'] + 'render_controllers/kg_tacz_offhand.render_controllers.json'] = (
        json.dumps({'format_version': '1.8.0', 'render_controllers': {
            OFFHAND_FP: offhand_controller(merged_controller)}}, ensure_ascii=False, indent=2) + '\n').encode()
    pair = {pin['bp_uuid'], pin['rp_uuid']}
    for side in ('BP', 'RP'):
        name = roots[side] + 'manifest.json'
        original = json.loads(originals[name])
        if original['header']['uuid'] != pin[side.lower() + '_uuid'] or original['header']['version'] != pin['version']:
            raise ValueError('TACZ pack identity differs from reviewed input')
        companion = {'uuid': descriptor['grilling'][side.lower() + '_uuid'],
                     'version': descriptor['grilling']['version'].copy()}
        # The selected IE adapter supplies the identical nongun FP controller.
        raw = advance_manifest(originals[name], pin['output_version'], pair, companion,
                               descriptor['behavior_min_engine_version'])
        value = json.loads(raw)
        ie = {'uuid': descriptor['immersive_eating'][side.lower() + '_uuid'],
              'version': descriptor['output_version'].copy()}
        previous = [row for row in value['dependencies'] if row.get('uuid') == ie['uuid']]
        if previous and previous != [ie]:
            raise ValueError('Conflicting IE compatibility dependency')
        if not previous:
            value['dependencies'].append(ie)
        changed[name] = (json.dumps(value, ensure_ascii=False, indent=2) + '\n').encode()
    result.update(changed)
    return result, {'changed_files': {name: sha256(raw) for name, raw in changed.items()},
                    'removed_paths': [old_player], 'behavior_player_path': player,
                    'preserved_author_files': sum(name not in changed and name != old_player for name in originals),
                    'player_properties': len(schema['properties']),
                    'required_priority': 'Adapted TACZ BP/RP above Grilling and the selected IE adapter; raw TACZ pair disabled'}


def apply_archive(tacz, ie, grilling, source, descriptor):
    tacz, ie, grilling = Path(tacz), Path(ie), Path(grilling)
    if sha256(tacz.read_bytes()) != descriptor['tacz']['archive_sha256']:
        raise ValueError('TACZ archive differs from reviewed source')
    if sha256(ie.read_bytes()) != descriptor['immersive_eating']['archive_sha256']:
        raise ValueError('IE archive differs from reviewed source')
    controller, controller_receipt = export_controller(ie, grilling, descriptor)
    author, entries = _read_zip(tacz)
    host, host_entries = _read_zip(ie)
    try:
        player = host_entries[descriptor['immersive_eating']['player_entity_path']][1]
        composed, composition = compose_players(source, player, descriptor, tacz)
        originals = {name: raw for name, (_, raw) in entries.items()}
        files, receipt = adapt_files(originals, composed, controller, descriptor)
        startup = prepare_scripts(originals)
        files.update(startup)
        receipt['changed_files'].update({name: sha256(raw) for name, raw in startup.items()})
        receipt['preserved_author_files'] -= len(startup)
        receipt['startup_script_count'] = len(startup)
        output = io.BytesIO()
        with zipfile.ZipFile(output, 'w', zipfile.ZIP_DEFLATED, compresslevel=9) as target:
            for name, raw in files.items():
                info = zipfile.ZipInfo(name, (2026, 9, 29, 0, 0, 0))
                info.compress_type = zipfile.ZIP_DEFLATED
                info.external_attr = 0o100644 << 16
                target.writestr(info, raw)
        payload = output.getvalue()
        receipt.update(schema=1, adapter=descriptor['tacz']['id'],
                       toolkit_version=descriptor['toolkit_version'],
                       version=descriptor['tacz']['output_version'], output_sha256=sha256(payload),
                       source_archive_sha256=descriptor['tacz']['archive_sha256'],
                       grilling_source=descriptor['grilling']['source'],
                       composition=composition, controller=controller_receipt,
                       distribution='user-local only; no author archive in public releases',
                       client=False, production_ready=False)
        return payload, receipt
    finally:
        author.close(); host.close()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('tacz', 'ie', 'grilling', 'grilling-source', 'output'):
        parser.add_argument('--' + name, type=Path, required=True)
    parser.add_argument('--descriptor', type=Path, default=DEFAULT_DESCRIPTOR)
    args = parser.parse_args(argv)
    receipt_path = Path(str(args.output) + '.receipt.json')
    if args.output.exists() or receipt_path.exists():
        parser.error('Choose a new output and receipt path')
    descriptor = json.loads(args.descriptor.read_bytes())
    payload, receipt = apply_archive(args.tacz, args.ie, args.grilling, args.grilling_source, descriptor)
    _atomic_new(args.output, payload)
    _atomic_new(receipt_path, (json.dumps(receipt, ensure_ascii=False, indent=2) + '\n').encode())
    print(json.dumps({'output': str(args.output), 'sha256': sha256(payload),
                      'player_properties': receipt['player_properties'], 'client': False}))


if __name__ == '__main__':
    main()
