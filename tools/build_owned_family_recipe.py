#!/usr/bin/env python3
"""Build a public Grilling/Cookery installation or an exact legacy recipe."""
import argparse
import copy
import json
import os
import tempfile
from pathlib import Path

from assemble_family import _load_and_verify_inputs, _tree_fingerprint, assemble
from install_cookery import _atomic_new, _read_zip, sha256
import install_cookery_from_descriptor as cookery_adapter

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DESCRIPTOR = ROOT / 'adapters/owned-t194-g212-w180-cookery-station-performance.json'
PUBLIC_MINIMAL_DESCRIPTOR = ROOT / 'adapters/public-minimal-grilling-g212-cookery20012.json'
PUBLIC_COOKERY_DESCRIPTOR = cookery_adapter.DEFAULT_DESCRIPTOR


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


def install_public_pair(cookery: Path, grilling: Path, output: Path) -> dict:
    """Build the two-addon public package; compatibility follows the host contract.

    Only the Grilling archive/version pin is resolved from user input. The
    reviewed Cookery original, API declaration and copied helper hashes are
    still checked by the existing adapter. This is assembly, not game QA.
    """
    output = output.absolute()
    if output.exists() or output.is_symlink():
        raise ValueError('refusing to replace existing public output')
    public_raw = PUBLIC_MINIMAL_DESCRIPTOR.read_bytes()
    adapter_raw = PUBLIC_COOKERY_DESCRIPTOR.read_bytes()
    descriptor, adapter = json.loads(public_raw), json.loads(adapter_raw)
    if (set(descriptor['inputs']) != {'grilling', 'cookery'}
            or len(descriptor['packs']) != 4
            or {p['id'] for p in descriptor['packs']} != {
                'grilling-bp', 'grilling-rp', 'cookery-bp', 'cookery-rp'}):
        raise ValueError('public installation requires exactly the two-addon profile')
    # Never inherit a full-family player override or an old candidate's identity.
    descriptor.pop('behavior_player_override', None)
    descriptor.pop('candidate_provenance', None)
    descriptor.pop('toolkit_version', None)
    descriptor.update(require_closed_pack_dependencies=True,
                      required_behavior_player_owner='grilling-bp',
                      aggregate_filename='public-minimal.mcaddon')
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.public-install-', dir=output.parent) as td:
        stage = Path(td)
        inputs = stage / 'inputs'
        inputs.mkdir()
        # Work on snapshots, so neither source is ever rewritten or reread mid-build.
        original = stage / 'original-cookery.mcaddon'
        source = inputs / 'grilling.mcaddon'
        _atomic_new(original, cookery.read_bytes())
        _atomic_new(source, grilling.read_bytes())
        source_sha = sha256(source.read_bytes())
        archive, files = _read_zip(source)
        try:
            manifests = [json.loads(raw) for name, (_, raw) in files.items()
                         if name == 'manifest.json' or name.endswith('/manifest.json')]
            pins = [p for p in descriptor['packs'] if p['input'] == 'grilling']
            if (len(manifests) != 2 or
                    {m.get('header', {}).get('uuid') for m in manifests} != {p['uuid'] for p in pins}):
                raise ValueError('Grilling input must contain its original BP and RP identities')
            versions = []
            for pin in pins:
                manifest = next(m for m in manifests if m['header']['uuid'] == pin['uuid'])
                version, modules = manifest['header'].get('version'), manifest.get('modules', [])
                if (not isinstance(version, list) or len(version) != 3
                        or any(type(v) is not int or v < 0 for v in version)
                        or [m.get('uuid') for m in modules] != [m['uuid'] for m in pin['modules']]
                        or any(m.get('version') != version for m in modules)):
                    raise ValueError('Grilling pack/module identity or version is inconsistent')
                pin['version'] = version
                pin['modules'] = [{'uuid': m['uuid'], 'version': m['version']} for m in modules]
                versions.append(version)
            if versions[0] != versions[1]:
                raise ValueError('Grilling BP and RP must be the same version')
        finally:
            archive.close()
        # The adapter independently verifies spec_sha256, every owned helper,
        # the original author's SHA and every changed author's file pre/postimage.
        adapter['id'] = 'senluo-core:cookery-contract-local'
        adapter.pop('toolkit_version', None)
        adapter['companion'].pop('source', None)
        adapter['companion'].pop('runtime_trees', None)
        adapter['companion'].update(archive_sha256=source_sha,
                                    version=versions[0], rp_version=versions[0])
        adapted, adapter_receipt = cookery_adapter.adapt_archive(original, source, adapter)
        if sha256(adapted) != descriptor['inputs']['cookery']['sha256']:
            raise ValueError('adapted Cookery differs from the reviewed public host output')
        _atomic_new(inputs / 'cookery.mcaddon', adapted)
        for key in ('grilling', 'cookery'):
            path = inputs / (key + '.mcaddon')
            descriptor['inputs'][key] = {'filename': path.name, 'sha256': sha256(path.read_bytes())}
        descriptor['id'] = 'senluo-core:public-minimal-contract-local'
        descriptor['recipe_version'] = 'grilling-' + '.'.join(map(str, versions[0])) + '-local'
        recipe = build_recipe(descriptor, inputs)
        recipe_raw = (json.dumps(recipe, ensure_ascii=False, indent=2) + '\n').encode()
        recipe_path = stage / 'recipe.json'
        _atomic_new(recipe_path, recipe_raw)
        result = stage / 'result'
        receipt = assemble(recipe, recipe_path, inputs, result)
        _atomic_new(result / 'recipe.json', recipe_raw)
        _atomic_new(result / 'cookery-adapter.receipt.json',
                    (json.dumps(adapter_receipt, ensure_ascii=False, indent=2) + '\n').encode())
        provenance = {
            'profile': 'public-minimal',
            'matching': 'reviewed host API and helper bytes; actual Grilling version recorded',
            'grilling_sha256': source_sha, 'grilling_version': versions[0],
            'original_cookery_sha256': sha256(original.read_bytes()),
            'public_template_sha256': sha256(public_raw),
            'reviewed_adapter_sha256': sha256(adapter_raw),
            'resolved_adapter_sha256': adapter_receipt['descriptor_sha256'],
            'scope': 'user-local build; not source authenticity or Minecraft acceptance',
            'client': 'NOT_RUN', 'saved_world': 'NOT_RUN',
        }
        _atomic_new(result / 'installation.json',
                    (json.dumps(provenance, ensure_ascii=False, indent=2) + '\n').encode())
        if output.exists() or output.is_symlink():
            raise ValueError('refusing to replace existing public output')
        os.rename(result, output)
        return receipt


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    selection = parser.add_mutually_exclusive_group()
    selection.add_argument('--descriptor', type=Path, help='Explicit current or historical descriptor')
    selection.add_argument('--profile', choices=('public-minimal', 'full-family'),
                           help='Legacy recipe selection (default: full-family); direct archives are public-minimal')
    parser.add_argument('--inputs', type=Path, help='Legacy recipe input directory')
    parser.add_argument('--cookery', type=Path, help='Original Cookery archive (direct public installation)')
    parser.add_argument('--grilling', type=Path, help='Grilling BP/RP archive (direct public installation)')
    parser.add_argument('--output', type=Path, required=True,
                        help='New directory for direct install, or new JSON file for a legacy recipe')
    args = parser.parse_args(argv)
    if args.cookery is not None or args.grilling is not None:
        if (args.cookery is None or args.grilling is None or args.inputs is not None
                or args.descriptor is not None or args.profile not in (None, 'public-minimal')):
            parser.error('direct public install needs --cookery and --grilling, without --inputs, --descriptor or full-family')
        receipt = install_public_pair(args.cookery, args.grilling, args.output)
        print(json.dumps({'output': str(args.output / 'public-minimal.mcaddon'),
                          'profile': 'public-minimal', 'packs': len(receipt['packs']),
                          'client': 'NOT_RUN', 'saved_world': 'NOT_RUN'}))
        return
    if args.inputs is None:
        parser.error('supply --cookery and --grilling, or --inputs for a legacy recipe')
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
