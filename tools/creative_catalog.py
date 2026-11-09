"""Regroup visible native creative entries using reviewed semantic data.

Input paths are relative to one BP. The returned updates never install packs or
change item IDs, gameplay components, recipes, hidden definitions or manifests.
Rules use explicit item/group mappings; optional component/tag mappings apply
only to previously ungrouped items. Complete author packs remain local inputs.
"""
import copy
import json


CATEGORIES = ('construction', 'equipment', 'items', 'nature')
CATALOG = 'item_catalog/crafting_item_catalog.json'


def _encoded(value):
    return (json.dumps(value, ensure_ascii=False, indent=2) + '\n').encode()


def _role(components):
    if 'minecraft:wearable' in components:
        return 'wearable'
    if 'minecraft:shooter' in components:
        return 'ranged'
    if 'minecraft:projectile' in components:
        return 'projectile'
    if 'minecraft:digger' in components:
        return 'tool'
    if 'minecraft:weapon' in components:
        return 'weapon'
    animation = components.get('minecraft:use_animation')
    food = components.get('minecraft:food')
    if food and animation == 'drink':
        return 'drink'
    # A zero-nutrition food component can be an input hook (for example a gun).
    if food and food.get('nutrition', 0) > 0:
        return 'food'
    return None


def regroup_creative(bp_files, rules):
    """Return ``updates``, RP ``labels`` and untouched ``unmapped`` entries.

    ``groups`` maps aliases to category/name/vanilla-icon/locale-label objects.
    ``group_moves`` and ``items`` map exact old names/IDs to those aliases.
    Optional ``components`` maps the roles food/drink/tool/weapon/ranged/
    projectile/wearable; ``tags`` maps exact native item tags. No rule matches
    by an identifier substring, and no rule promotes a hidden implementation.
    """
    groups = rules['groups']
    by_name, aliases = {}, {}
    for alias, spec in groups.items():
        if spec['category'] not in CATEGORIES or not spec['icon'].startswith('minecraft:'):
            raise ValueError('Creative groups require a native category and vanilla icon')
        previous = by_name.setdefault(spec['name'], spec)
        if previous != spec:
            raise ValueError('Conflicting shared creative group: ' + spec['name'])
        aliases.setdefault(spec['name'], alias)
    for key in ('group_moves', 'items', 'components', 'tags'):
        if any(alias not in groups for alias in rules.get(key, {}).values()):
            raise ValueError('Unknown creative group alias in ' + key)

    catalog = (json.loads(bp_files[CATALOG]) if CATALOG in bp_files else
               {'format_version': '1.21.60', 'minecraft:crafting_items_catalog': {'categories': []}})
    catalog = copy.deepcopy(catalog)
    membership, identifiers = {}, {}
    order = []
    for category in catalog['minecraft:crafting_items_catalog']['categories']:
        if category['category_name'] not in CATEGORIES:
            raise ValueError('Unknown native creative category: ' + category['category_name'])
        for group in category['groups']:
            ident = group.get('group_identifier', {})
            key = (category['category_name'], ident.get('name'))
            identifiers.setdefault(key, copy.deepcopy(ident))
            for item in group['items']:
                if item not in membership:
                    membership[item] = key
                    order.append(item)

    definitions, unparsed = {}, []
    for path, raw in sorted(bp_files.items()):
        if not path.endswith('.json') or not path.startswith(('items/', 'blocks/')):
            continue
        try:
            document = json.loads(raw)
        except (ValueError, UnicodeError):
            # Unknown author JSONC remains byte-identical and is not silently
            # advertised as classified. Native catalog-only entries are retained.
            unparsed.append(path)
            continue
        kind = 'minecraft:item' if path.startswith('items/') else 'minecraft:block'
        value = document.get(kind)
        if not isinstance(value, dict) or 'identifier' not in value.get('description', {}):
            continue
        item = value['description']['identifier']
        definitions.setdefault(item, []).append((path, document, kind))
        if item not in order:
            order.append(item)

    updates, buckets, labels, unmapped, hidden = {}, {}, {}, [], []
    item_rules = rules.get('items', {})
    group_rules = rules.get('group_moves', {})
    component_rules = rules.get('components', {})
    tag_rules = rules.get('tags', {})
    for item in order:
        rows = definitions.get(item, [])
        visible = [row for row in rows if row[1][row[2]]['description'].get('menu_category', {}).get('category') in CATEGORIES]
        if rows and not visible:
            hidden.append(item)
            continue
        if not visible and item not in membership:
            continue
        menu = visible[0][1][visible[0][2]]['description']['menu_category'] if visible else {}
        category, group_name = membership.get(item, (menu.get('category'), menu.get('group')))
        alias = item_rules.get(item)
        if alias is None:
            alias = group_rules.get(group_name) or group_rules.get(menu.get('group'))
        if alias is None:
            alias = aliases.get(group_name) or aliases.get(menu.get('group'))
        if alias is None and not group_name and not menu.get('group'):
            for _, document, kind in visible:
                if kind != 'minecraft:item':
                    continue
                components = document[kind].get('components', {})
                tags = components.get('minecraft:tags', {}).get('tags', [])
                alias = next((tag_rules[tag] for tag in tags if tag in tag_rules), None)
                alias = alias or component_rules.get(_role(components))
                if alias is not None:
                    break
        if alias is not None:
            spec = groups[alias]
            category, group_name = spec['category'], spec['name']
            identifiers[(category, group_name)] = {'name': group_name, 'icon': spec['icon']}
            for locale, label in spec.get('labels', {}).items():
                labels.setdefault(locale, {})[group_name] = label
            for path, document, kind in visible:
                description = document[kind]['description']
                original = description['menu_category']
                changed = {**original, 'category': category, 'group': group_name}
                if changed != original:
                    description['menu_category'] = changed
                    updates[path] = _encoded(document)
        else:
            unmapped.append({'identifier': item, 'category': category, 'group': group_name})
        if category not in CATEGORIES:
            raise ValueError('Visible entry has no native creative category: ' + item)
        buckets.setdefault((category, group_name), []).append(item)

    ranks = {name: index for index, name in enumerate(by_name)}
    categories = []
    for category in CATEGORIES:
        keys = [key for key in buckets if key[0] == category]
        keys.sort(key=lambda key: ranks.get(key[1], len(ranks)))
        output = []
        for key in keys:
            group = {'items': buckets[key]}
            ident = identifiers.get(key) or ({'name': key[1]} if key[1] else None)
            if ident:
                group['group_identifier'] = ident
            output.append(group)
        if output:
            categories.append({'category_name': category, 'groups': output})
    catalog['minecraft:crafting_items_catalog']['categories'] = categories
    raw = _encoded(catalog)
    if (categories or CATALOG in bp_files) and raw != bp_files.get(CATALOG):
        updates[CATALOG] = raw
    return {'updates': updates, 'labels': labels, 'unmapped': unmapped,
            'unparsed_files': unparsed, 'hidden': hidden}
