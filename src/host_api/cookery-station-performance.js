/** Disposable Cookery display bookkeeping; saved machine data remains authoritative.
 * No recipe timer, input payload, output, particle or sound is cached here.
 */
const RECONCILE_TICKS = 20;
const RETIRE_AFTER_TICKS = 200;
const MAX_CACHED_STATIONS = 4096;

const positionMatches = (actual, expected) => ['x', 'y', 'z'].every(key => Math.fround(actual[key]) === Math.fround(expected[key]));
const angle = value => Math.fround(((Math.fround(value) % 360) + 360) % 360) % 360;
const rotationMatches = (actual, expected) => angle(actual.x) === angle(expected.x) && angle(actual.y) === angle(expected.y);

export function createCookeryStationPerformance(world, system, displayTypes) {
  const types = new Set(displayTypes);
  const stations = new Map();
  const equipment = new Map();
  let pruneTick = -1, cursor;
  const key = block => `${block.dimension.id}:${block.x},${block.y},${block.z}`;
  const prefix = block => `kc_sd_${block.x}_${block.y}_${block.z}_`;

  function discard(stationKey, entry) {
    stations.delete(stationKey);
    for (const entity of entry.entities) equipment.delete(entity.id);
  }

  function prune(now) {
    if (pruneTick === now) return;
    pruneTick = now;
    cursor ??= stations.entries();
    for (let count = 0; count < 8; count++) {
      const next = cursor.next();
      if (next.done) { cursor = stations.entries(); break; }
      const [stationKey, entry] = next.value;
      if (now - entry.lastUse > RETIRE_AFTER_TICKS) discard(stationKey, entry);
    }
  }

  function entryFor(block) {
    const now = system.currentTick;
    prune(now);
    const stationKey = key(block);
    let entry = stations.get(stationKey);
    if (!entry) {
      if (stations.size >= MAX_CACHED_STATIONS) {
        const [oldKey, oldEntry] = stations.entries().next().value;
        discard(oldKey, oldEntry); // Cache eviction changes cost only, never machine state.
      }
      entry = {entities: [], dirty: true, lastQuery: -Infinity, lastUse: now};
      stations.set(stationKey, entry);
    }
    entry.lastUse = now;
    return entry;
  }

  function invalidateLoadedEntity(event) {
    const entity = event.entity;
    if (!entity?.isValid || !types.has(entity.typeId)) return;
    equipment.delete(entity.id); // A reloaded replica needs a fresh native item assignment.
    for (const tag of entity.getTags()) {
      const match = /^kc_sd_(-?\d+)_(-?\d+)_(-?\d+)_\d+$/.exec(tag);
      if (!match) continue;
      const entry = stations.get(`${entity.dimension.id}:${match[1]},${match[2]},${match[3]}`);
      if (entry) entry.dirty = true;
    }
  }
  world.afterEvents.entityLoad.subscribe(invalidateLoadedEntity);
  world.afterEvents.entitySpawn.subscribe(invalidateLoadedEntity);

  function displays(block) {
    const entry = entryFor(block), now = system.currentTick;
    if (entry.entities.some(entity => !entity.isValid)) entry.dirty = true;
    if (entry.dirty || now - entry.lastQuery >= RECONCILE_TICKS) {
      const own = prefix(block), found = [];
      const query = {location: {x: block.x + .5, y: block.y + .5, z: block.z + .5}, maxDistance: 2.5};
      for (const type of types) for (const entity of block.dimension.getEntities({...query, type})) {
        if (entity.getTags().some(tag => tag.startsWith(own))) found.push(entity);
      }
      // A known replica may have been displaced beyond the query radius. Keep its
      // verified owner handle so the normal source synchronizer can move/remove it.
      for (const entity of entry.entities) {
        if (entity.isValid && !found.some(other => other.id === entity.id)
            && entity.getTags().some(tag => tag.startsWith(own))) found.push(entity);
        if (!entity.isValid) equipment.delete(entity.id);
      }
      entry.entities = found;
      entry.lastQuery = now;
      entry.dirty = false;
    }
    return entry.entities.slice();
  }

  function remember(block, entity) {
    const entry = entryFor(block);
    if (!entry.entities.some(other => other.id === entity.id)) entry.entities.push(entity);
  }

  function syncItem(block, entity, location, rotation, itemId, count) {
    remember(block, entity);
    const oldRotation = entity.getRotation();
    if (!positionMatches(entity.location, location)) entity.teleport(location, {rotation});
    else if (!rotationMatches(oldRotation, rotation)) entity.setRotation(rotation);
    if (count !== undefined && entity.getProperty('kaleidoscope_cookery:wok_item_count') !== count)
      entity.setProperty('kaleidoscope_cookery:wok_item_count', count);
    if (equipment.get(entity.id) !== itemId) {
      const result = entity.runCommand(`replaceitem entity @s slot.weapon.mainhand 0 ${itemId}`);
      if (result.successCount !== 1) throw Error('Cookery display item assignment was not acknowledged');
      equipment.set(entity.id, itemId);
    }
  }

  function writeState(stationKey, state) {
    const raw = Object.keys(state).length ? JSON.stringify(state) : undefined;
    // Read the actual property. A cached old string must never overwrite an
    // external owner or pretend a failed persistence write succeeded.
    if (world.getDynamicProperty(stationKey) !== raw) world.setDynamicProperty(stationKey, raw);
  }

  return Object.freeze({displays, remember, syncItem, writeState});
}
