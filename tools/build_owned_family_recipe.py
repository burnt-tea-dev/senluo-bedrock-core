#!/usr/bin/env python3
"""Build a local owned-port recipe from independently obtained, pinned archives."""
import argparse
import json
from pathlib import Path

from assemble_family import _load_and_verify_inputs, _tree_fingerprint
from install_cookery import _atomic_new, _read_zip, sha256

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DESCRIPTOR = ROOT / 'adapters/owned-t194-g212-w180-cookery-station-performance.json'


PUBLIC_MINIMAL = {
    'BP': ('grilling-bp', 'cookery-bp'),
    'RP': ('grilling-rp', 'cookery-rp'),
}


def select_profile(descriptor, profile):
    if profile == 'family':
        return descriptor
    if profile != 'public-minimal':
        raise ValueError('unknown installation profile: ' + profile)

    # This is a filtered view of the existing, reviewed current recipe, not a
    # second installer or an IE/TACZ fallback. Only the two real input archives
    # are read and verified by the unchanged assembly code.
    required = {name for names in PUBLIC_MINIMAL.values() for name in names}
    packs = [pack for pack in descriptor['packs'] if pack['id'] in required]
    if len(packs) != len(required) or {p['id'] for p in packs} != required:
        raise ValueError('current descriptor lacks the four public-minimal packs')
    if {p['input'] for p in packs} != {'grilling', 'cookery'}:
        raise ValueError('public-minimal requires only Grilling and adapted Cookery')
    if descriptor.get('behavior_player_override') is not None:
        raise ValueError('public-minimal cannot inherit a family player override')
    order = {}
    for side, names in PUBLIC_MINIMAL.items():
        chosen = [name for name in descriptor['order'][side] if name in names]
        if len(chosen) != len(names) or set(chosen) != set(names):
            raise ValueError('public-minimal order lacks its paired ' + side + ' packs')
        order[side] = chosen
    return {
        'schema': descriptor['schema'],
        'id': descriptor['id'] + ':public-minimal',
        'recipe_version': descriptor['recipe_version'] + '-public-minimal',
        'toolkit_version': descriptor.get('toolkit_version'),
        'inputs': {key: descriptor['inputs'][key] for key in ('grilling', 'cookery')},
        'packs': packs, 'order': order,
    }


def build_recipe(descriptor, inputs_dir, profile='family'):
    if descriptor.get('schema') != 1:
        raise ValueError('unsupported owned-port descriptor schema')
    descriptor = select_profile(descriptor, profile)
    selected = descriptor.get('packs')
    if not isinstance(selected, list) or not selected:
        raise ValueError('descriptor needs explicit pack identities')
    verified = _load_and_verify_inputs(descriptor, inputs_dir)
    found = {}
    manifest_dependencies = {}
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
                manifest_dependencies[pin['id']] = manifest.get('dependencies', [])
                found[pin['id']] = {key: pin[key] for key in ('id', 'uuid', 'version', 'side', 'modules')}
                found[pin['id']].update(files=members,
                                        expected_tree={'files': hashes, 'sha256': _tree_fingerprint(hashes)})
        finally:
            archive.close()
    if set(found) != {row['id'] for row in selected} or len(found) != len(selected):
        raise ValueError('descriptor pack set is missing or duplicated')
    if profile == 'public-minimal':
        by_uuid = {row['uuid']: row for row in selected}
        for pack_id, dependencies in manifest_dependencies.items():
            for dependency in dependencies:
                if not isinstance(dependency, dict):
                    raise ValueError('invalid manifest dependency in ' + pack_id)
                if 'uuid' not in dependency:
                    continue  # Script API modules are supplied by the game.
                other = by_uuid.get(dependency['uuid'])
                if other is None:
                    raise ValueError('public-minimal pack depends on an absent pack: ' + pack_id)
                minimum = dependency.get('version')
                if not isinstance(minimum, list) or len(minimum) != 3 or tuple(minimum) > tuple(other['version']):
                    raise ValueError('public-minimal pack requires a newer paired pack: ' + pack_id)
    recipe = {'schema': 1, 'id': descriptor['id'], 'version': descriptor['recipe_version'],
              'inputs': {key: {'filename': value['filename'], 'sha256': value['sha256']}
                         for key, value in descriptor['inputs'].items()},
              'packs': [found[row['id']] for row in selected], 'order': descriptor['order']}
    if 'toolkit_version' in descriptor:
        recipe['toolkit_version'] = descriptor['toolkit_version']
    if 'behavior_player_override' in descriptor:
        recipe['behavior_player_override'] = descriptor['behavior_player_override']
    if profile == 'public-minimal':
        recipe['profile'] = profile
    return recipe


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--descriptor', type=Path, default=DEFAULT_DESCRIPTOR)
    parser.add_argument('--profile', choices=('family', 'public-minimal'), default='family',
                        help='public-minimal uses only Grilling and local adapted Cookery')
    parser.add_argument('--inputs', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args(argv)
    if args.output.exists():
        raise ValueError('refusing to overwrite an existing recipe')
    recipe = build_recipe(json.loads(args.descriptor.read_text()), args.inputs, profile=args.profile)
    raw = (json.dumps(recipe, ensure_ascii=False, indent=2) + '\n').encode()
    _atomic_new(args.output, raw)
    print(json.dumps({'recipe': str(args.output), 'sha256': sha256(raw), 'packs': len(recipe['packs']),
                      'archives_embedded': False, 'gameplay_transforms': False}))


if __name__ == '__main__':
    main()
