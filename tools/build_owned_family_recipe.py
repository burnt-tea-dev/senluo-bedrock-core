#!/usr/bin/env python3
"""Build a local owned-port recipe from independently obtained, pinned archives."""
import argparse
import copy
import json
from pathlib import Path

from assemble_family import _load_and_verify_inputs, _tree_fingerprint
from install_cookery import _atomic_new, _read_zip, sha256

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DESCRIPTOR = ROOT / 'adapters/owned-t194-g212-w180-cookery-station-performance.json'
PUBLIC_MINIMAL_DESCRIPTOR = ROOT / 'adapters/public-minimal-grilling-g212-cookery20012.json'


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


def build_recipe(descriptor, inputs_dir):
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
    return recipe


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    selection = parser.add_mutually_exclusive_group()
    selection.add_argument('--descriptor', type=Path, help='Explicit current or historical descriptor')
    selection.add_argument('--profile', choices=('public-minimal', 'full-family'),
                           help='Reviewed installation selection (default: full-family)')
    parser.add_argument('--inputs', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args(argv)
    if args.output.exists():
        raise ValueError('refusing to overwrite an existing recipe')
    descriptor_path = args.descriptor or (
        PUBLIC_MINIMAL_DESCRIPTOR if args.profile == 'public-minimal' else DEFAULT_DESCRIPTOR)
    recipe = build_recipe(json.loads(descriptor_path.read_text()), args.inputs)
    raw = (json.dumps(recipe, ensure_ascii=False, indent=2) + '\n').encode()
    _atomic_new(args.output, raw)
    print(json.dumps({'recipe': str(args.output), 'sha256': sha256(raw), 'packs': len(recipe['packs']),
                      'archives_embedded': False, 'gameplay_transforms': False}))


if __name__ == '__main__':
    main()
