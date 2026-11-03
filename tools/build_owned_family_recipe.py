#!/usr/bin/env python3
"""Build a local owned-port recipe from independently obtained, pinned archives."""
import argparse
from copy import deepcopy
import json
from pathlib import Path

from assemble_family import _load_and_verify_inputs, _tree_fingerprint, _transform
from install_cookery import _atomic_new, _read_zip, sha256

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DESCRIPTOR = ROOT / 'adapters/owned-t194-g212-w180-cookery-station-performance.json'


def select_profile(descriptor, profile):
    """Select a public-capability subset without changing a frozen family lock."""
    if profile == 'family':
        return descriptor
    if profile != 'public-minimal':
        raise ValueError('unknown installation profile: ' + str(profile))
    needed = {'grilling', 'cookery'}
    if not isinstance(descriptor.get('inputs'), dict) or not needed.issubset(descriptor['inputs']):
        raise ValueError('public-minimal needs pinned Grilling and Cookery inputs')
    packs = [pack for pack in descriptor.get('packs', []) if pack.get('input') in needed]
    expected = {(name, side) for name in needed for side in ('BP', 'RP')}
    if len(packs) != 4 or {(pack['input'], pack.get('side')) for pack in packs} != expected:
        raise ValueError('public-minimal needs exactly one BP/RP pair per dependency')
    if descriptor.get('behavior_player_override') is not None:
        raise ValueError('public-minimal cannot silently discard a family player override')
    ids = {pack['id'] for pack in packs}
    if len(ids) != 4 or len({pack['uuid'] for pack in packs}) != 4:
        raise ValueError('public-minimal pack identities are duplicated')
    order = {}
    for side in ('BP', 'RP'):
        declared = descriptor.get('order', {}).get(side)
        if not isinstance(declared, list):
            raise ValueError('public-minimal requires explicit pack priority')
        order[side] = [pack_id for pack_id in declared if pack_id in ids]
        expected_ids = {pack['id'] for pack in packs if pack['side'] == side}
        if len(order[side]) != len(expected_ids) or set(order[side]) != expected_ids:
            raise ValueError('public-minimal order does not cover exactly its selected packs')
    result = deepcopy(descriptor)
    result['id'] = descriptor['id'] + ':public-minimal'
    result['recipe_version'] = descriptor['recipe_version'] + ':public-minimal'
    result['inputs'] = {key: descriptor['inputs'][key] for key in ('grilling', 'cookery')}
    result['packs'] = packs
    result['order'] = order
    return result


def bind_public_dependencies(recipe, manifests, inputs_for_uuid):
    """Pin dependencies to the locally adapted Cookery version, never to missing packs.

    The original Grilling archive still declares official Cookery 1.6.4. The
    author Cookery host installer produces local 1.6.20012. A public recipe
    records exact source and transformed manifest hashes rather than quietly
    passing incompatible versions to Minecraft.
    """
    by_uuid = {pack['uuid']: pack for pack in recipe['packs']}
    if len(by_uuid) != len(recipe['packs']):
        raise ValueError('public-minimal UUID identities are duplicated')
    changes = []
    for pack in recipe['packs']:
        raw = manifests[pack['id']]
        manifest = json.loads(raw)
        dependencies = manifest.get('dependencies', [])
        if not isinstance(dependencies, list):
            raise ValueError('invalid manifest dependencies in ' + pack['id'])
        operations = []
        for index, dependency in enumerate(dependencies):
            if not isinstance(dependency, dict):
                raise ValueError('invalid manifest dependency in ' + pack['id'])
            target_uuid = dependency.get('uuid')
            if target_uuid is None:
                # Script module dependencies such as @minecraft/server are unchanged.
                continue
            target = by_uuid.get(target_uuid)
            if target is None:
                raise ValueError('public-minimal requires an unselected pack: ' + str(target_uuid))
            actual = dependency.get('version')
            expected = target['version']
            if actual == expected:
                continue
            if not (inputs_for_uuid[pack['uuid']] == 'grilling'
                    and inputs_for_uuid[target_uuid] == 'cookery'
                    and isinstance(actual, list) and len(actual) == 3
                    and all(type(value) is int and value >= 0 for value in actual)
                    and actual[:2] == expected[:2] and actual[2] < expected[2]):
                raise ValueError('public-minimal dependency version differs: ' + pack['id'])
            operations.append({'kind': 'json_replace',
                               'pointer': ['dependencies', str(index), 'version'],
                               'before': actual, 'after': expected})
            changes.append({'pack': pack['id'], 'dependency_uuid': target_uuid,
                            'source_version': actual, 'output_version': expected})
        if operations:
            transformed = _transform(raw, operations, pack['id'] + '/manifest.json')
            record = pack['files']['manifest.json']
            record['transforms'] = operations
            record['output_sha256'] = sha256(transformed)
            pack['expected_tree']['files']['manifest.json'] = sha256(transformed)
            pack['expected_tree']['sha256'] = _tree_fingerprint(pack['expected_tree']['files'])
    recipe['manifest_dependency_rebindings'] = changes


def build_recipe(descriptor, inputs_dir, profile='family'):
    descriptor = select_profile(descriptor, profile)
    if descriptor.get('schema') != 1:
        raise ValueError('unsupported owned-port descriptor schema')
    selected = descriptor.get('packs')
    if not isinstance(selected, list) or not selected:
        raise ValueError('descriptor needs explicit pack identities')
    verified = _load_and_verify_inputs(descriptor, inputs_dir)
    found = {}
    manifests = {}
    inputs_for_uuid = {pack['uuid']: pack['input'] for pack in selected}
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
                manifests[pin['id']] = raw
                found[pin['id']] = {key: pin[key] for key in ('id', 'uuid', 'version', 'side', 'modules')}
                found[pin['id']].update(files=members,
                                        expected_tree={'files': hashes, 'sha256': _tree_fingerprint(hashes)})
        finally:
            archive.close()
    if set(found) != {row['id'] for row in selected} or len(found) != len(selected):
        raise ValueError('descriptor pack set is missing or duplicated')
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
        bind_public_dependencies(recipe, manifests, inputs_for_uuid)
    return recipe


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--descriptor', type=Path, default=DEFAULT_DESCRIPTOR)
    parser.add_argument('--profile', choices=('family', 'public-minimal'), default='family')
    parser.add_argument('--inputs', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args(argv)
    if args.output.exists():
        raise ValueError('refusing to overwrite an existing recipe')
    recipe = build_recipe(json.loads(args.descriptor.read_text()), args.inputs, args.profile)
    raw = (json.dumps(recipe, ensure_ascii=False, indent=2) + '\n').encode()
    _atomic_new(args.output, raw)
    print(json.dumps({'recipe': str(args.output), 'sha256': sha256(raw), 'packs': len(recipe['packs']),
                      'archives_embedded': False, 'gameplay_transforms': False}))


if __name__ == '__main__':
    main()
