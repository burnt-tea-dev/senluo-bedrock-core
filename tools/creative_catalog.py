"""Project one owner's explicit tab sequence into a native Bedrock catalog.

The caller supplies reviewed tab/member/icon data. With no plan, author data is
unchanged. This module has no family taxonomy, component inference, load-order
policy or cross-pack ownership resolver. It never installs or versions packs.
"""
import copy
import json

CATEGORIES = ('construction', 'equipment', 'items', 'nature')
CATALOG = 'item_catalog/crafting_item_catalog.json'


def _encoded(value):
    return (json.dumps(value, ensure_ascii=False, indent=2) + '\n').encode()


def project_creative_tabs(bp_files, plan=None):
    """Return changed BP bytes, labels and source rows that cannot be emitted.

    ``tabs`` contains ordered category/group/icon/entries/labels objects. Each
    entry names an existing ``bedrock`` ID, or explicitly records an unavailable
    Java stack. ``bedrock_additions`` explicitly names retained loose entries.
    Hidden item/block halves remain hidden; no stack metadata is synthesized.
    """
    if plan is None:
        return {'updates': {}, 'labels': {}, 'unavailable': []}
    if plan.get('schema') != 1:
        raise ValueError('Unknown creative tab plan schema')
    definitions = {}
    for path, raw in bp_files.items():
        if not path.endswith('.json') or not path.startswith(('items/', 'blocks/')):
            continue
        kind = 'minecraft:item' if path.startswith('items/') else 'minecraft:block'
        document = json.loads(raw)
        description = document[kind]['description']
        definitions.setdefault(description['identifier'], []).append((path, document, kind))
    updates, labels, categories, emitted, unavailable = {}, {}, {}, set(), []
    rows = [(tab, entry) for tab in plan['tabs'] for entry in tab['entries']]
    rows.extend((None, entry) for entry in plan.get('bedrock_additions', []))
    for tab, entry in rows:
        item = entry.get('bedrock')
        if not item or entry.get('unavailable'):
            unavailable.append(copy.deepcopy(entry))
            continue
        visible = []
        for row in definitions.get(item, []):
            _, document, kind = row
            menu = document[kind]['description'].get('menu_category', {})
            legacy = tuple(map(int, document['format_version'].split('.'))) < (1, 21, 60)
            # Preserve the supported legacy default without exposing a modern
            # hidden half. Membership/order still comes only from the plan.
            if menu.get('category', 'items' if legacy else 'none') in CATEGORIES:
                visible.append(row)
        if not visible:
            unavailable.append({**entry, 'unavailable': 'No existing visible definition'})
            continue
        if item in emitted:
            raise ValueError('One native ID cannot represent two creative stacks: ' + item)
        category = tab['category'] if tab else entry['category']
        if category not in CATEGORIES:
            raise ValueError('Unknown native creative category: ' + category)
        if tab:
            if not isinstance(tab['icon'], str) or ':' not in tab['icon']:
                raise ValueError('Creative icon must name an item, including custom items')
            group = next((g for g in categories.setdefault(category, [])
                          if g.get('group_identifier', {}).get('name') == tab['group']), None)
            if group is None:
                group = {'group_identifier': {'name': tab['group'], 'icon': tab['icon']}, 'items': []}
                categories[category].append(group)
            for locale, label in tab.get('labels', {}).items():
                labels.setdefault(locale, {})[tab['group']] = label
        else:
            group = {'items': []}
            categories.setdefault(category, []).append(group)
        group['items'].append(item)
        emitted.add(item)
        for path, document, kind in visible:
            description = document[kind]['description']
            menu = {**description.get('menu_category', {}), 'category': category}
            # Older definitions cannot declare a namespaced group reliably;
            # their catalog still owns the explicit group and member sequence.
            legacy = tuple(map(int, document['format_version'].split('.'))) < (1, 21, 60)
            if tab and not legacy:
                menu['group'] = tab['group']
            else:
                menu.pop('group', None)
            description['menu_category'] = menu
            raw = _encoded(document)
            if raw != bp_files[path]:
                updates[path] = raw
    for entry in plan.get('hidden', []):
        for path, document, kind in definitions.get(entry['bedrock'], []):
            description = document[kind]['description']
            description['menu_category'] = {**description.get('menu_category', {}), 'category': 'none'}
            description['menu_category'].pop('group', None)
            raw = _encoded(document)
            if raw != bp_files[path]:
                updates[path] = raw
    catalog = {'format_version': '1.21.60', 'minecraft:crafting_items_catalog': {'categories': [
        {'category_name': category, 'groups': groups} for category, groups in categories.items()]}}
    raw = _encoded(catalog)
    if raw != bp_files.get(CATALOG):
        updates[CATALOG] = raw
    return {'updates': updates, 'labels': labels, 'unavailable': unavailable}
