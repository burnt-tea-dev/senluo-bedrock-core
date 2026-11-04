#!/usr/bin/env python3
"""Build a local owned-port recipe from independently obtained, pinned archives."""
import argparse
import copy
from contextlib import redirect_stdout
import hashlib
import io
import json
import os
from pathlib import Path
import tempfile

from assemble_family import (_load_and_verify_inputs, _tree_fingerprint,
                             _read_archive_source, _transform, read_definition, assemble)
from install_cookery import _atomic_new, _read_zip, sha256
import install_cookery_from_descriptor as cookery_installer

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DESCRIPTOR = ROOT / 'adapters/owned-t194-g212-w180-cookery-station-performance.json'
PUBLIC_MINIMAL_DESCRIPTOR = ROOT / 'adapters/public-minimal-g219-player.json'
PUBLIC_COOKERY_DESCRIPTOR = ROOT / 'adapters/cookery-1.6.4-grilling-2.8.219-station-performance.json'


def _rewrite_manifest_dependency(raw, rule, pack_id):
    """Pin the exact dependency change; keep the source ZIP immutable."""
    if (not isinstance(rule, dict) or set(rule) != {'uuid', 'before', 'after'}
            or not isinstance(rule['uuid'], str)
            or any(not isinstance(rule[key], list) or len(rule[key]) != 3
                   or any(type(n) is not int or n < 0 for n in rule[key])
                   for key in ('before', 'after'))):
        raise ValueError('invalid dependency rewrite: ' + pack_id)
    manifest = json.loads(raw)
    before = manifest.get('dependencies')
    if not isinstance(before, list):
        raise ValueError('manifest has no dependencies: ' + pack_id)
    matches = [i for i, row in enumerate(before)
               if isinstance(row, dict) and row.get('uuid') == rule['uuid']]
    if len(matches) != 1 or before[matches[0]].get('version') != rule['before']:
        raise ValueError('manifest dependency preimage differs: ' + pack_id)
    after = copy.deepcopy(before)
    after[matches[0]]['version'] = rule['after'].copy()
    manifest['dependencies'] = after
    changed = (json.dumps(manifest, ensure_ascii=False, indent=2) + '\n').encode()
    return sha256(changed), {'kind': 'json_replace', 'pointer': ['dependencies'],
                             'before': before, 'after': after}


def _complete_public_player(recipe, descriptor, verified, grilling_source, vanilla_source):
    """Compose the public RP in place using the existing canonical composer.

    Vanilla files are local build references, not another selected addon. No
    author input is modified, and the previous package identity stays frozen.
    """
    contract = descriptor.get('player_presentation')
    if contract is None:
        return
    if grilling_source is None or vanilla_source is None:
        raise ValueError('public-minimal presentation needs --grilling-source and --vanilla-source; '
                         'see docs/FAMILY-ASSEMBLY.md#public-player-presentation')
    packs = {p['id']: p for p in recipe['packs']}
    if (set(packs) != {'grilling-bp', 'grilling-rp', 'cookery-bp', 'cookery-rp'}
            or set(recipe['inputs']) != {'grilling', 'cookery'}):
        raise ValueError('public player composition requires only Grilling and Cookery')
    version = contract['output_version']
    if (not isinstance(version, list) or len(version) != 3
            or any(type(n) is not int or n < 0 for n in version)
            or any(tuple(version) <= tuple(packs[key]['version'])
                   for key in ('grilling-bp', 'grilling-rp'))):
        raise ValueError('public presentation needs a fresh increasing paired version')
    vanilla = Path(vanilla_source)
    refs = contract['vanilla']
    # Validate exact source bytes, not a mutable main/tag or an invented player
    # stub. A downloaded/extracted official reference need not be a Git checkout.
    reference = {}
    for key, path in (('player', 'resource_pack/entity/player.entity.json'),
                      ('license', 'LICENSE.md')):
        raw = (vanilla / path).read_bytes()
        blob = hashlib.sha1(b'blob ' + str(len(raw)).encode() + b'\0' + raw).hexdigest()
        if blob != refs[key + '_blob_sha1']:
            raise ValueError('vanilla ' + key + ' differs from the reviewed engine reference')
        reference[key] = raw
    host = read_definition(reference['player'])
    if host.get('minecraft:client_entity', {}).get('description', {}).get('identifier') != 'minecraft:player':
        raise ValueError('vanilla reference must be the complete minecraft:player')
    from install_player_presentation import compose_players
    generated, receipt = compose_players(grilling_source, reference['player'],
        {'grilling': {'source': contract['source']}})
    player = generated['RP/entity/player.entity.json']
    # compose_players has verified the exact, clean canonical source checkout.
    extension = json.loads((Path(grilling_source) /
        'projects/grilling/gameplay_core/behavior_pack/host-extensions/player-presentation.json').read_bytes())
    requirement = {'owner': 'grilling-rp',
                   'variables': extension['scripts']['variables'],
                   'animations': extension['animations']}
    added = {'entity/player.entity.json': player,
             'MOJANG-VANILLA-LICENSE.md': reference['license']}
    rp = packs['grilling-rp']
    for name, raw in added.items():
        if name in rp['files']:
            raise ValueError('public player output already exists; do not replace another owner: ' + name)
        rp['files'][name] = {'kind': 'generated', 'content': raw.decode('utf-8'), 'sha256': sha256(raw)}
    own_uuids = {packs[key]['uuid'] for key in ('grilling-bp', 'grilling-rp')}
    for key in ('grilling-bp', 'grilling-rp'):
        pack = packs[key]
        spec = pack['files']['manifest.json']
        original = _read_archive_source(verified[spec['input']]['path'], spec['members'])
        operations = spec.setdefault('transforms', [])
        manifest = json.loads(_transform(original, operations, key))
        changes = [(['header', 'version'], manifest['header']['version'], version),
                   (['modules'], manifest['modules'],
                    [{**m, 'version': version.copy()} for m in manifest['modules']])]
        deps = manifest.get('dependencies', [])
        paired = [{**d, 'version': version.copy()} if d.get('uuid') in own_uuids else d
                  for d in deps]
        if paired != deps:
            changes.append((['dependencies'], deps, paired))
        operations.extend({'kind': 'json_replace', 'pointer': path, 'before': before, 'after': after}
                          for path, before, after in changes)
        spec['output_sha256'] = sha256(_transform(original, operations, key))
        pack['version'] = version.copy()
        pack['modules'] = [{**m, 'version': version.copy()} for m in pack['modules']]
        hashes = {name: value.get('output_sha256', value['sha256']) for name, value in pack['files'].items()}
        pack['expected_tree'] = {'files': hashes, 'sha256': _tree_fingerprint(hashes)}
    recipe['required_resource_player'] = requirement
    recipe['player_presentation_provenance'] = {
        'composer_source': contract['source'], 'vanilla': refs,
        'player_sha256': sha256(player), 'output_version': version,
        'canonical_composer_outputs': receipt['outputs'],
        'distribution': 'user-local composed player; retain Mojang license; no author archive publication',
        'client': 'NOT-RUN'}


def build_recipe(descriptor, inputs_dir, *, grilling_source=None, vanilla_source=None):
    if descriptor.get('schema') != 1:
        raise ValueError('unsupported owned-port descriptor schema')
    selected = descriptor.get('packs')
    if not isinstance(selected, list) or not selected:
        raise ValueError('descriptor needs explicit pack identities')
    rewrites = descriptor.get('dependency_rewrites', {})
    if (not isinstance(rewrites, dict)
            or set(rewrites) - {pack['id'] for pack in selected}):
        raise ValueError('dependency rewrites refer to unknown packs')
    verified = _load_and_verify_inputs(descriptor, inputs_dir)
    found = {}
    applied_rewrites = set()
    for input_id, source in verified.items():
        expected = {p['uuid']: p for p in selected if p['input'] == input_id}
        archive, files = _read_zip(source['path'])
        try:
            for name, (_, raw) in files.items():
                if not (name == 'manifest.json' or name.endswith('/manifest.json')):
                    continue
                manifest = json.loads(raw)
                uid = manifest.get('header', {}).get('uuid')
                if uid not in expected:
                    continue
                pin = expected[uid]
                modules = [{'uuid': row.get('uuid'), 'version': row.get('version')}
                           for row in manifest.get('modules', [])]
                if (manifest['header'].get('version') != pin['version'] or modules != pin['modules']):
                    raise ValueError('pack identity differs from descriptor: ' + pin['id'])
                if pin['id'] in found:
                    raise ValueError('pack identity occurs more than once: ' + pin['id'])
                prefix = name[:-len('manifest.json')]
                hashes, members = {}, {}
                for member, (_, body) in files.items():
                    if not member.startswith(prefix) or member.endswith('/'):
                        continue
                    relative = member[len(prefix):]
                    digest = sha256(body)
                    hashes[relative] = digest
                    members[relative] = {'kind': 'archive', 'input': input_id,
                                         'members': [member], 'sha256': digest}
                    if relative == 'manifest.json' and pin['id'] in rewrites:
                        output_hash, operation = _rewrite_manifest_dependency(
                            body, rewrites[pin['id']], pin['id'])
                        members[relative]['transforms'] = [operation]
                        members[relative]['output_sha256'] = output_hash
                        hashes[relative] = output_hash
                        applied_rewrites.add(pin['id'])
                found[pin['id']] = {key: pin[key] for key in ('id', 'uuid', 'version', 'side', 'modules')}
                found[pin['id']].update(files=members,
                                        expected_tree={'files': hashes, 'sha256': _tree_fingerprint(hashes)})
        finally:
            archive.close()
    if set(found) != {row['id'] for row in selected} or len(found) != len(selected):
        raise ValueError('descriptor pack set is missing or duplicated')
    if applied_rewrites != set(rewrites):
        raise ValueError('dependency rewrite was not applied to a manifest')
    recipe = {'schema': 1, 'id': descriptor['id'], 'version': descriptor['recipe_version'],
              'inputs': {key: {'filename': value['filename'], 'sha256': value['sha256']}
                         for key, value in descriptor['inputs'].items()},
              'packs': [found[row['id']] for row in selected], 'order': descriptor['order']}
    if 'toolkit_version' in descriptor:
        recipe['toolkit_version'] = descriptor['toolkit_version']
    if 'aggregate_filename' in descriptor:
        recipe['aggregate_filename'] = descriptor['aggregate_filename']
    elif (descriptor.get('require_closed_pack_dependencies') is True
          and descriptor.get('required_behavior_player_owner') == 'grilling-bp'):
        recipe['aggregate_filename'] = 'public-minimal.mcaddon'
    if 'behavior_player_override' in descriptor:
        recipe['behavior_player_override'] = descriptor['behavior_player_override']
    if descriptor.get('require_closed_pack_dependencies') is True:
        recipe['require_closed_pack_dependencies'] = True
    if 'required_behavior_player_owner' in descriptor:
        owner = descriptor['required_behavior_player_owner']
        if owner not in {row['id'] for row in selected if row['side'] == 'BP'}:
            raise ValueError('required player owner is not a selected behavior pack')
        recipe['required_behavior_player_owner'] = owner
    _complete_public_player(recipe, descriptor, verified, grilling_source, vanilla_source)
    return recipe


def install_public_pair(cookery, grilling, grilling_source, vanilla_source, output):
    """Build the existing reviewed public four-pack route in one local command.

    Unlike the older package-only prototype, this *requires* the canonical
    player composer and official vanilla reference; it cannot silently produce
    a resource pack missing the first-person player presentation.
    """
    output = Path(output).absolute()
    if output.exists() or output.is_symlink():
        raise ValueError('refusing to overwrite an existing public installation')
    descriptor = json.loads(PUBLIC_MINIMAL_DESCRIPTOR.read_text(encoding='utf-8'))
    if (set(descriptor['inputs']) != {'grilling', 'cookery'}
            or {p['id'] for p in descriptor['packs']}
            != {'grilling-bp', 'grilling-rp', 'cookery-bp', 'cookery-rp'}
            or 'player_presentation' not in descriptor):
        raise ValueError('reviewed public-minimal profile must include its player presentation')
    # Inputs are snapshotted in a temporary directory. No archive, author
    # resource or player world is modified; staging is removed on failure.
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.public-install-', dir=output.parent) as temp:
        stage = Path(temp)
        inputs = stage / 'inputs'
        inputs.mkdir()
        grilling_file = inputs / descriptor['inputs']['grilling']['filename']
        cookery_file = inputs / descriptor['inputs']['cookery']['filename']
        _atomic_new(grilling_file, Path(grilling).read_bytes())
        if sha256(grilling_file.read_bytes()) != descriptor['inputs']['grilling']['sha256']:
            raise ValueError('Grilling source archive differs from reviewed public-minimal input')
        # Same canonical adapter as the two-step install; its own clean-author,
        # source API, helper and postimage checks remain in force.
        with redirect_stdout(io.StringIO()):
            cookery_installer.main([
                '--cookery', str(Path(cookery).resolve()),
                '--grilling', str(grilling_file),
                '--descriptor', str(PUBLIC_COOKERY_DESCRIPTOR),
                '--output', str(cookery_file),
            ])
        if sha256(cookery_file.read_bytes()) != descriptor['inputs']['cookery']['sha256']:
            raise ValueError('adapted Cookery output differs from reviewed public-minimal input')
        recipe = build_recipe(descriptor, inputs,
                              grilling_source=Path(grilling_source),
                              vanilla_source=Path(vanilla_source))
        recipe_raw = (json.dumps(recipe, ensure_ascii=False, indent=2) + '\n').encode()
        recipe_path = stage / 'recipe.json'
        _atomic_new(recipe_path, recipe_raw)
        candidate = stage / 'candidate'
        receipt = assemble(recipe, recipe_path, inputs, candidate)
        if (len(receipt['packs']) != 4
                or receipt['behavior_player_definition']['pack_id'] != 'grilling-bp'
                or receipt['resource_player_definition']['pack_id'] != 'grilling-rp'):
            raise ValueError('public installation lacks a unique Grilling player owner')
        _atomic_new(candidate / 'recipe.json', recipe_raw)
        _atomic_new(candidate / 'cookery-adapter.receipt.json',
                    Path(str(cookery_file) + '.receipt.json').read_bytes())
        _atomic_new(candidate / 'installation.json', (
            json.dumps({
                'profile': 'public-minimal',
                'grilling_source_sha256': sha256(grilling_file.read_bytes()),
                'original_cookery_sha256': sha256(Path(cookery).read_bytes()),
                'adapted_cookery_sha256': sha256(cookery_file.read_bytes()),
                'client': 'NOT_RUN', 'saved_world': 'NOT_RUN',
                'live': False,
            }, indent=2) + '\n').encode())
        if output.exists() or output.is_symlink():
            raise ValueError('public output appeared during staging')
        os.rename(candidate, output)
        return receipt


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    selection = parser.add_mutually_exclusive_group()
    selection.add_argument('--descriptor', type=Path, help='Explicit current or historical descriptor')
    selection.add_argument('--profile', choices=('public-minimal', 'full-family'),
                           help='Reviewed installation selection (default: full-family)')
    parser.add_argument('--grilling-source', type=Path, help='Exact canonical composer checkout (public profile)')
    parser.add_argument('--vanilla-source', type=Path, help='Official engine player reference directory, not an addon')
    parser.add_argument('--inputs', type=Path, help='Existing recipe input directory')
    parser.add_argument('--cookery', type=Path, help='Original author Cookery .mcaddon (direct public mode)')
    parser.add_argument('--grilling', type=Path, help='Reviewed Grilling .mcaddon (direct public mode)')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args(argv)
    if args.cookery is not None or args.grilling is not None:
        if (args.cookery is None or args.grilling is None or args.inputs is not None
                or args.descriptor is not None or args.profile not in (None, 'public-minimal')
                or args.grilling_source is None or args.vanilla_source is None):
            parser.error('direct public install needs --cookery, --grilling, --grilling-source and --vanilla-source only')
        receipt = install_public_pair(args.cookery, args.grilling,
                                      args.grilling_source, args.vanilla_source, args.output)
        print(json.dumps({'output': str(args.output / 'public-minimal.mcaddon'),
                          'packs': len(receipt['packs']), 'client': 'NOT_RUN',
                          'saved_world': 'NOT_RUN'}, ensure_ascii=False))
        return
    if args.inputs is None:
        parser.error('supply --inputs for a recipe or --cookery and --grilling for direct install')
    if args.output.exists():
        raise ValueError('refusing to overwrite an existing recipe')
    descriptor_path = args.descriptor or (
        PUBLIC_MINIMAL_DESCRIPTOR if args.profile == 'public-minimal' else DEFAULT_DESCRIPTOR)
    recipe = build_recipe(json.loads(descriptor_path.read_text()), args.inputs,
                          grilling_source=args.grilling_source, vanilla_source=args.vanilla_source)
    raw = (json.dumps(recipe, ensure_ascii=False, indent=2) + '\n').encode()
    _atomic_new(args.output, raw)
    print(json.dumps({'recipe': str(args.output), 'sha256': sha256(raw), 'packs': len(recipe['packs']),
                      'archives_embedded': False, 'gameplay_transforms': False}))


if __name__ == '__main__':
    main()
