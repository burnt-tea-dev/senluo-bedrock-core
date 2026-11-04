"""Compose optional controls around an unchanged native HUD root."""
import copy


def compose_hud(native, *, before=(), after=(), definitions=None, providers=None):
    """Providers and mount order are caller data; no addon or version is selected here."""
    hud = copy.deepcopy(native)
    controls = hud['root_panel']['controls']
    hud['root_panel']['controls'] = copy.deepcopy(list(before)) + controls + copy.deepcopy(list(after))
    for name, definition in (definitions or {}).items():
        if name in hud:
            raise ValueError('HUD addition overwrites a native definition: ' + name)
        hud[name] = copy.deepcopy(definition)
    providers = providers or {}

    def resolve(value):
        if isinstance(value, dict):
            result = {}
            for key, child in value.items():
                name, separator, base = key.partition('@')
                key = name + separator + providers.get(base, base) if separator else key
                result[key] = resolve(child)
            return result
        if isinstance(value, list):
            return [resolve(child) for child in value]
        return value

    return resolve(hud)
