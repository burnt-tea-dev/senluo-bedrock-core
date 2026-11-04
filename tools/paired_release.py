"""Plan fresh pack identities and exact dependency changes from pinned inputs."""
import copy
import hashlib
import json


def encoded(value):
    return (json.dumps(value, ensure_ascii=False, indent=2) + '\n').encode()


def version(value):
    return isinstance(value, list) and len(value) == 3 and all(type(n) is int and n >= 0 for n in value)


def _validate_rule(rule, pack_id):
    if (not isinstance(rule, dict) or set(rule) != {'uuid', 'before', 'after'}
            or not isinstance(rule['uuid'], str)
            or not all(version(rule[key]) for key in ('before', 'after'))):
        raise ValueError('invalid dependency rewrite: ' + pack_id)


def rewrite_dependency(raw, rule, pack_id):
    _validate_rule(rule, pack_id)
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
    changed = encoded(manifest)
    return hashlib.sha256(changed).hexdigest(), {
        'kind': 'json_replace', 'pointer': ['dependencies'], 'before': before, 'after': after}


def advance_manifest(raw, output_version, paired_uuids):
    manifest = json.loads(raw)
    before = manifest['header']['version']
    if not version(output_version) or not version(before) or output_version <= before:
        raise ValueError('Local adapter needs a fresh increasing paired version')
    manifest['header']['version'] = output_version.copy()
    for module in manifest['modules']:
        module['version'] = output_version.copy()
    for dependency in manifest.get('dependencies', []):
        if dependency.get('uuid') in paired_uuids:
            dependency['version'] = output_version.copy()
    return encoded(manifest)


def plan_pair(manifests, output_version, dependency_rewrites=()):
    if set(manifests) != {'BP', 'RP'}:
        raise ValueError('A paired release requires both BP and RP manifests')
    ids = {json.loads(raw)['header']['uuid'] for raw in manifests.values()}
    if len(ids) != 2:
        raise ValueError('A paired release requires distinct pack UUIDs')
    if not isinstance(dependency_rewrites, (list, tuple)):
        raise ValueError('Paired dependency rewrites must be a list')
    for rule in dependency_rewrites:
        _validate_rule(rule, 'pair')
    planned, seen = {}, set()
    for side, raw in manifests.items():
        current = json.loads(advance_manifest(raw, output_version, ids))
        for index, rule in enumerate(dependency_rewrites):
            if rule.get('uuid') not in {row.get('uuid') for row in current.get('dependencies', [])}:
                continue
            _, operation = rewrite_dependency(encoded(current), rule, side)
            current['dependencies'] = operation['after']
            seen.add(index)
        before = json.loads(raw)
        transforms = [{'kind': 'json_replace', 'pointer': ['header', 'version'],
                       'before': before['header']['version'], 'after': output_version.copy()},
                      {'kind': 'json_replace', 'pointer': ['modules'],
                       'before': before['modules'], 'after': current['modules']}]
        if current.get('dependencies') != before.get('dependencies'):
            transforms.append({'kind': 'json_replace', 'pointer': ['dependencies'],
                               'before': before.get('dependencies', []),
                               'after': current.get('dependencies', [])})
        planned[side] = {'raw': encoded(current), 'transforms': transforms}
    if seen != set(range(len(dependency_rewrites))):
        raise ValueError('Paired release has an unused dependency rewrite')
    return planned
