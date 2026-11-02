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
DEFAULT_DESCRIPTOR = ROOT / 'adapters/tacz-1.0.3-grilling-2.8.212.json'
FP = 'controller.render.player.first_person'
OFFHAND_FP = 'controller.render.kg_tacz.offhand_first_person'
OFFHAND = "q.is_item_equipped('off_hand')"


def repair_ui(originals, prefix):
    """Correct the existing author controls using current native UI types."""
    changed = {}
    hud_path = prefix + 'ui/hud_screen.json'
    if hud_path in originals:
        hud = read_definition(originals[hud_path])
        hud['namespace'] = 'hud'
        # Native hud_actionbar_text is an image and contributes its texture
        # during pack merging. A panel override leaves an invalid property.
        # The author's existing transparent pixel keeps this background clear.
        hud['hud_actionbar_text']['type'] = 'image'
        hud['hud_actionbar_text']['texture'] = 'textures/ikon/empty'
        changed[hud_path] = (json.dumps(hud, ensure_ascii=False, indent=2) + '\n').encode()
    form_path = prefix + 'ui/server_form.json'
    if form_path in originals:
        form = read_definition(originals[form_path])
        default = form['long_form']['controls'][0]['long_form@common_dialogs.main_panel_no_buttons']
        # Each title comparison must be boolean before applying `and`.
        default['bindings'][1]['source_property_name'] = '(' + ' and '.join(
            "(not (#title_text = '" + title + "'))"
            for title in ('Custom dial', 'Custom triple', 'grip13', 'Main')) + ')'

        def buttons(value):
            if isinstance(value, list):
                for child in value:
                    buttons(child)
            elif isinstance(value, dict):
                for name, child in value.items():
                    if name == 'form_button@common_buttons.light_text_button' and 'color' in child:
                        child['$default_text_color'] = child.pop('color')
                    buttons(child)

        buttons(form)
        changed[form_path] = (json.dumps(form, ensure_ascii=False, indent=2) + '\n').encode()
    return changed


def repair_sound_definitions(raw, descriptor):
    definitions = read_definition(raw)
    retired = set(descriptor.get('retired_unused_sound_events', []))
    corrections = descriptor.get('sound_path_corrections', {})
    result = {name: copy.deepcopy(row) for name, row in definitions.items() if name not in retired}
    for row in result.values():
        for index, sound in enumerate(row.get('sounds', [])):
            if isinstance(sound, str):
                row['sounds'][index] = corrections.get(sound, sound)
            elif sound['name'] in corrections:
                sound['name'] = corrections[sound['name']]
    return (json.dumps(result, ensure_ascii=False, indent=2) + '\n').encode()


def repair_attachable_textures(originals, prefix, descriptor):
    """Use the author's shipped transparent pixel for hidden held-item meshes."""
    corrections = descriptor.get('texture_path_corrections', {})
    changed = {}
    for path, raw in originals.items():
        if not path.startswith(prefix + 'attachables/') or not path.endswith('.json'):
            continue
        value = read_definition(raw)
        textures = value['minecraft:attachable']['description']['textures']
        fixed = {key: corrections.get(texture, texture) for key, texture in textures.items()}
        if fixed != textures:
            value['minecraft:attachable']['description']['textures'] = fixed
            changed[path] = (json.dumps(value, ensure_ascii=False, indent=2) + '\n').encode()
    return changed


def _source_files(directory, descriptor, kind):
    result = {}
    for name, pin in descriptor.get('restored_' + kind + '_files', {}).items():
        if directory is None:
            raise ValueError('This TACZ descriptor requires --source-assets (or --source-sounds) from the pinned original author blobs')
        if not _safe_name(name) or not name.startswith(kind + 's/'):
            raise ValueError('Unsafe source asset path')
        path = Path(directory) / name
        if path.is_symlink() or any(parent.is_symlink() for parent in path.parents):
            raise ValueError('Source asset path is linked')
        raw = path.read_bytes()
        if sha256(raw) != pin['sha256']:
            raise ValueError('Original author ' + kind + ' differs: ' + name)
        result[descriptor['tacz']['prefixes']['RP'] + name] = raw
    return result


def source_sound_files(directory, descriptor):
    return _source_files(directory, descriptor, 'sound')


def repair_projectile_hit(raw, pin):
    """A queued hit can reference an already removed target in server 1.18."""
    before = b'if(!_0x357e52||'
    after = b'if(!_0x357e52||!_0x357e52.isValid()||'
    if sha256(raw) != pin['prepared_sha256'] or raw.count(before) != 1:
        raise ValueError('TACZ projectile hit source differs')
    result = raw.replace(before, after, 1)
    if sha256(result) != pin['output_sha256']:
        raise ValueError('TACZ projectile hit repair differs')
    return result


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
    description = client['minecraft:client_entity']['description']
    # The author ships no animation.humanoid.slide. Retire that dead TP
    # reference; the existing G36 hold pose and movement transitions remain.
    description.get('animations', {}).pop('slide', None)
    # Use actual author particle definitions: G3 ejects the existing 7.62
    # casing and the muzzle-smoke resource is named muzzlesmoke, not nothin.
    description.setdefault('particle_effects', {}).update({
        'krep.shell': 'krep:762shell', 'krep.g3shell': 'krep:762shell',
        'krep.muzzlesmoke': 'krep:muzzlesmoke'})
    retired = set(descriptor.get('retired_unused_sound_events', []))
    if retired:
        description['sound_effects'] = {name: target for name, target in description['sound_effects'].items()
                                        if target not in retired}
    client['minecraft:client_entity']['description']['render_controllers'].append({
        OFFHAND_FP: "v.is_first_person && !q.is_spectator && v.holding_all_guns && " + OFFHAND})
    changed[client_path] = (json.dumps(client, ensure_ascii=False, indent=2) + '\n').encode()
    # Use the same virtual path as Grilling. The reviewed TACZ profile selects
    # this merged 28-field owner above the unchanged four-field source pack.
    # The filename is not an entity identity or a persisted save key.
    result = {name: raw for name, raw in originals.items() if name != old_player}
    for name, raw in originals.items():
        if not name.startswith(roots['RP'] + 'animation_controllers/') or not name.endswith('.json'):
            continue
        document = read_definition(changed.get(name, raw))
        slide = document.get('animation_controllers', {}).get('controller.animation.g36.tp')
        if slide is not None:
            rows = slide['states']['slide']['animations']
            rows.remove({'slide': 'v.g36'})
            changed[name] = (json.dumps(document, ensure_ascii=False, indent=2) + '\n').encode()
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
        if descriptor.get('restored_texture_files'):
            # Keep the translator credit while dropping the removed cosmetic
            # pack label. No player skin or geometry is replaced.
            value['header']['name'] = value['header']['name'].replace('+SkinPack', '').replace('  ', ' ') + ' [original gun textures]'
            value['header']['description'] = value['header'].get('description', '').replace(' +added SkinPack.', '.')
        if side == 'RP':
            # The complete family uses the engine's PBR resource stack. The
            # locally adapted pair must declare it before family admission.
            capabilities = value.setdefault('capabilities', [])
            if 'pbr' not in capabilities:
                capabilities.append('pbr')
        ie = {'uuid': descriptor['immersive_eating'][side.lower() + '_uuid'],
              'version': descriptor['output_version'].copy()}
        previous = [row for row in value['dependencies'] if row.get('uuid') == ie['uuid']]
        if previous and previous != [ie]:
            raise ValueError('Conflicting IE compatibility dependency')
        if not previous:
            value['dependencies'].append(ie)
        changed[name] = (json.dumps(value, ensure_ascii=False, indent=2) + '\n').encode()
    changed.update(repair_ui(originals, roots['RP']))
    sound_path = roots['RP'] + 'sounds/sound_definitions.json'
    changed.update(repair_attachable_textures(originals, roots['RP'], descriptor))
    if sound_path in originals:
        changed[sound_path] = repair_sound_definitions(originals[sound_path], descriptor)
    blocks_path = roots['RP'] + 'blocks.json'
    if blocks_path in originals:
        catalog = read_definition(originals[blocks_path])
        catalog['format_version'] = '1.1.0'
        changed[blocks_path] = (json.dumps(catalog, ensure_ascii=False, indent=2) + '\n').encode()
    result.update(changed)
    return result, {'changed_files': {name: sha256(raw) for name, raw in changed.items()},
                    'removed_paths': [old_player], 'behavior_player_path': player,
                    'preserved_author_files': sum(name not in changed and name != old_player for name in originals),
                    'player_properties': len(schema['properties']),
                    'required_priority': 'Adapted TACZ BP/RP above Grilling and the selected IE adapter; raw TACZ pair disabled'}


def apply_archive(tacz, ie, grilling, source, descriptor, source_sounds=None):
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
        restored = source_sound_files(source_sounds, descriptor)
        if any(name in originals for name in restored):
            raise ValueError('Restored source sound must fill an absent author file')
        files.update(restored)
        receipt['changed_files'].update({name: sha256(raw) for name, raw in restored.items()})
        receipt['restored_original_sounds'] = list(restored)
        startup = prepare_scripts(originals)
        files.update(startup)
        receipt['changed_files'].update({name: sha256(raw) for name, raw in startup.items()})
        receipt['preserved_author_files'] -= len(startup)
        receipt['startup_script_count'] = len(startup)
        for kind in ('texture', 'model'):
            assets = _source_files(source_sounds, descriptor, kind)
            for name, raw in assets.items():
                pin = descriptor['restored_' + kind + '_files'][name.removeprefix(descriptor['tacz']['prefixes']['RP'])]
                if sha256(originals[name]) != pin['preimage_sha256'] or files[name] != originals[name]:
                    raise ValueError('TACZ cosmetic preimage differs or overlaps player composition: ' + name)
                files[name] = raw
            receipt['changed_files'].update({name: sha256(raw) for name, raw in assets.items()})
            receipt['preserved_author_files'] -= len(assets)
            receipt['restored_original_' + kind + 's'] = list(assets)
        if descriptor.get('projectile_hit_repair'):
            pin = descriptor['projectile_hit_repair']
            name = pin['path']
            files[name] = repair_projectile_hit(files[name], pin)
            if name not in receipt['changed_files']:
                receipt['preserved_author_files'] -= 1
            receipt['changed_files'][name] = sha256(files[name])
            receipt['runtime_repairs'] = ['projectile_hit_invalid_target']
        output = io.BytesIO()
        with zipfile.ZipFile(output, 'w', zipfile.ZIP_DEFLATED, compresslevel=9) as target:
            for name, raw in files.items():
                info = zipfile.ZipInfo(name, (2026, 9, 29, 0, 0, 0))
                info.create_system = 3  # Canonical ZIP metadata is independent of the builder OS.
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
    parser.add_argument('--source-assets', '--source-sounds', dest='source_sounds', type=Path,
                        help='Pinned original sounds and unskinned gun textures')
    args = parser.parse_args(argv)
    receipt_path = Path(str(args.output) + '.receipt.json')
    if args.output.exists() or receipt_path.exists():
        parser.error('Choose a new output and receipt path')
    descriptor = json.loads(args.descriptor.read_bytes())
    payload, receipt = apply_archive(args.tacz, args.ie, args.grilling, args.grilling_source, descriptor, args.source_sounds)
    _atomic_new(args.output, payload)
    _atomic_new(receipt_path, (json.dumps(receipt, ensure_ascii=False, indent=2) + '\n').encode())
    print(json.dumps({'output': str(args.output), 'sha256': sha256(payload),
                      'player_properties': receipt['player_properties'], 'client': False}))


if __name__ == '__main__':
    main()
