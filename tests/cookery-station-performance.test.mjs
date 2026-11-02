import assert from 'node:assert/strict';
import test from 'node:test';
import {createCookeryStationPerformance} from '../src/host_api/cookery-station-performance.js';

function fixture() {
  const state = new Map(), listeners = {}, actors = [];
  const calls = {write: 0, query: 0, teleport: 0, rotation: 0, item: 0, property: 0};
  const system = {currentTick: 0};
  const world = {
    afterEvents: Object.fromEntries(['entityLoad', 'entitySpawn'].map(name => [name, {subscribe(fn) { listeners[name] = fn; }}])),
    getDynamicProperty: key => state.get(key),
    setDynamicProperty(key, value) { calls.write++; state.set(key, value); },
  };
  const dimension = {id: 'minecraft:overworld', getEntities(query) {
    calls.query++;
    return actors.filter(e => e.isValid && e.typeId === query.type && Math.hypot(e.location.x - query.location.x, e.location.y - query.location.y, e.location.z - query.location.z) <= query.maxDistance);
  }};
  const block = {x: 0, y: 64, z: 0, dimension};
  function actor(tag = 'kc_sd_0_64_0_0') {
    const properties = new Map();
    const e = {id: String(actors.length), typeId: 'test:display', isValid: true, dimension,
      location: {x: .5, y: 64.5, z: .5}, rotation: {x: 0, y: 0},
      getTags: () => [tag], getRotation() { return {...this.rotation}; },
      teleport(at, options) { calls.teleport++; this.location = {...at}; this.rotation = {...options.rotation}; },
      setRotation(value) { calls.rotation++; this.rotation = {...value}; },
      getProperty: key => properties.get(key), setProperty(key, value) { calls.property++; properties.set(key, value); },
      runCommand() { calls.item++; return {successCount: 1}; },
    };
    actors.push(e);
    return e;
  }
  const api = createCookeryStationPerformance(world, system, ['test:display']);
  return {state, listeners, calls, world, system, block, actor, api};
}

test('unchanged saves avoid writes and external changes are read again', () => {
  const f = fixture(), value = {progress: 7, foreign: {data: [1, false, 'keep']}};
  f.api.writeState('station', value);
  f.api.writeState('station', value);
  assert.equal(f.calls.write, 1);
  f.state.set('station', 'external');
  f.api.writeState('station', value);
  assert.equal(f.calls.write, 2);
  assert.deepEqual(JSON.parse(f.state.get('station')), value);
  f.world.setDynamicProperty = () => { throw Error('native write failure'); };
  assert.throws(() => f.api.writeState('station', {progress: 8}), /native write failure/);
  assert.deepEqual(JSON.parse(f.state.get('station')), value);
});

test('only owned displays are reused and loaded/removed replicas reconcile', () => {
  const f = fixture(), own = f.actor(), other = f.actor('kc_sd_1_64_0_0');
  assert.deepEqual(f.api.displays(f.block), [own]);
  f.system.currentTick = 1;
  assert.deepEqual(f.api.displays(f.block), [own]);
  assert.equal(f.calls.query, 1);
  own.isValid = false;
  assert.deepEqual(f.api.displays(f.block), []);
  const replacement = f.actor();
  f.listeners.entitySpawn({entity: replacement});
  assert.deepEqual(f.api.displays(f.block), [replacement]);
  assert.equal(other.isValid, true);
  f.system.currentTick = 21;
  f.api.displays(f.block);
  assert.equal(f.calls.query, 4);
});

test('unchanged native equipment and wrapped rotation need no new mutation', () => {
  const f = fixture(), e = f.actor(), at = {...e.location};
  f.api.syncItem(f.block, e, at, {x: 0, y: 0}, 'minecraft:carrot', 2);
  e.rotation.y = 360;
  f.api.syncItem(f.block, e, at, {x: 0, y: 0}, 'minecraft:carrot', 2);
  assert.deepEqual(f.calls, {write: 0, query: 0, teleport: 0, rotation: 0, item: 1, property: 1});
  f.api.syncItem(f.block, e, at, {x: 0, y: 90}, 'minecraft:wheat', 3);
  assert.equal(f.calls.item, 2);
  assert.equal(f.calls.rotation, 1);
  assert.equal(f.calls.property, 2);
  f.listeners.entityLoad({entity: e});
  f.api.syncItem(f.block, e, at, {x: 0, y: 90}, 'minecraft:wheat', 3);
  assert.equal(f.calls.item, 3);
});

test('a displaced owned replica is recovered and rejected item writes can retry', () => {
  const f = fixture(), e = f.actor(), at = {...e.location};
  f.api.syncItem(f.block, e, at, {x: 0, y: 0}, 'minecraft:carrot');
  e.location.x += 10;
  assert.deepEqual(f.api.displays(f.block), [e]);
  f.api.syncItem(f.block, e, at, {x: 0, y: 0}, 'minecraft:carrot');
  assert.equal(f.calls.teleport, 1);
  e.runCommand = () => ({successCount: 0});
  assert.throws(() => f.api.syncItem(f.block, e, at, {x: 0, y: 0}, 'minecraft:wheat'), /not acknowledged/);
  let retries = 0;
  e.runCommand = () => { retries++; return {successCount: 1}; };
  f.api.syncItem(f.block, e, at, {x: 0, y: 0}, 'minecraft:wheat');
  assert.equal(retries, 1);
});
