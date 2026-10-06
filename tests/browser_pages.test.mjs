import test from 'node:test';
import assert from 'node:assert/strict';
import {PAGES, PAGE_IDS, needsDetail, pageModel, PANELS, COLLAPSE_KEY, defaultCollapsed, loadCollapsed, toggleCollapsed, times, seconds} from '../src/dimensional_sim/world/browser/pages.js';

// Same shape as details.detail() (tests/test_world_pages.py checks the Python side).
const stat = name => ({name, level: 2, xp: 250, into: 40, next: 130, dim_level: 1, dim_xp: 110, dim_into: 10, dim_next: 135,
  speed: 1210, speed_regular_only: 1200, speed_dimensional_only: 1010, life_gain: 50});
const detail = {
  character: {life: 3, depth: 2, best_depth: 5, frontier: 3, health: 80.5, hunger: 41, punch_damage: 2, gear: ['Walking staff'],
    boon: null, boon_next: 'Iron skin', boar_hit_at_frontier: 20.1, fight_cost_at_frontier: 40.2, hunger_per_minute: 30,
    regen_per_minute: 12, rest_regen_per_minute: 60, inventory_slots: [3, 12], currencies: {dust: 4, ash: 2, blessing: 1}, unlocked: ['Climbing']},
  stats: ['strength', 'endurance', 'agility', 'intelligence', 'perception', 'willpower'].map(stat),
  multipliers: {actions: [{id: 'bramble_berries', name: 'Bramble berries', attribute: 'perception', speed: 1410, base_ms: 2400, effective_ms: 1703}],
    hunger_drain: 0.909, boar_hit: [['Endurance', 0.909], ['Hide wrap', 0.7]], punch_damage: 2, punch_parts: [['Base', 1], ['Strength levels', 1]]},
  rolls: {life: 3, windows: [
    {id: 'bramble_berries', name: 'Bramble berries', rolled: 2, min: 1, max: 2, active: 1, spawned: 4, mastery: 0, known: true},
    {id: 'gnarled_tree', name: 'Gnarled tree', rolled: 1, min: 1, max: 1, active: 0, spawned: 0, mastery: 0, known: false}],
    spots_per_chunk: [0, 3], pity: [{category: 'food', drought: 2, after: 5}], stats: {pity: 1},
    loot: [{id: 'bramble_berries', name: 'Bramble berries', drops: [{item: 'Wild berries', min: 2, max: 4, chance: 100}]}]},
  journal: {actions: [['Bramble berries', 'forage', 12], ['Fallen branches', 'gather', 3]], items: [['Wild berries', 30]],
    deaths: {starvation: 2}, best_life_min: 7.5, lives: 3, best_depth: 5,
    knowledge: ['deer_sign'], recipes: [], disabled: [], favor: {}, leads: [],
    lead_history: [{action: 'follow_deer_tracks', source: 'enc:forest:1:0:2', status: 'expired'}],
    achievements: [{id: 'first_steps', name: 'First steps', description: 'Complete an action.', progress: 1, threshold: 1, done: true},
      {id: 'woodsman', name: 'Woodsman', description: 'Gather 25 times.', progress: 3, threshold: 25, done: false}]},
};
const state = {world_seed: '482910', expedition: {detail}};

test('pages: every tab has a model, world has none, detail pages wait for data', () => {
  assert.deepEqual(PAGE_IDS, ['world', 'character', 'stats', 'speed', 'journal', 'life', 'settings']);
  assert.equal(pageModel('world', state), null);
  assert.equal(pageModel('nope', state), null);
  for (const p of PAGES.filter(p => needsDetail(p.id))) {
    assert.equal(pageModel(p.id, {expedition: {detail: null}}).loading, true);
    const model = pageModel(p.id, state);
    assert.ok(model.sections.length >= 2, p.id);
    for (const s of model.sections) {
      assert.ok(['rows', 'table', 'progress', 'actions'].includes(s.kind));
      assert.ok(JSON.stringify(s).length > 10);
      if (s.kind === 'table') for (const row of s.rows) assert.equal(row.length, s.head.length, `${p.id}:${s.title}`);
    }
  }
  assert.equal(needsDetail('settings'), false);
  assert.equal(needsDetail('world'), false);
});

test('pages: journal counts by type, rolls flag max, multipliers multiply', () => {
  const journal = pageModel('journal', state).sections;
  assert.match(journal[0].title, /1 \/ 2/);
  assert.deepEqual(journal.find(s => s.title === 'Actions by type').rows, [['Forage', 12], ['Gather', 3]]);
  assert.deepEqual(journal.find(s => s.title === 'Discoveries').rows[0], ['Knowledge', 'Deer sign']);
  assert.deepEqual(journal.find(s => s.title === 'Recent leads').rows, [['Follow deer tracks', 'enc:forest:1:0:2', 'expired']]);
  const life = pageModel('life', state).sections;
  assert.equal(life[0].rows[0][3], 'max');
  assert.equal(life[1].title, 'Rolled but not yet known');
  const speed = pageModel('speed', state).sections;
  assert.deepEqual(speed[0].rows[0], ['Bramble berries', 'Perception', '×1.41', '2.4s', '1.7s']);
  assert.deepEqual(speed[1].rows.at(-1), ['Total', '×0.636']);
  assert.equal(times(1000), '×1.00'); assert.equal(seconds(90000), '1.5 min');
});

test('stats: each attribute groups its regular bar with its dimensional bar right below', () => {
  const levels = pageModel('stats', state).sections[0];
  assert.equal(levels.items.length, 6);
  assert.equal(levels.items[0].label, 'Strength');
  assert.deepEqual(levels.items[0].bars.map(b => [b.label, !!b.dim]), [['level 2', false], ['dimensional 1', true]]);
});

test('settings: reset buttons only when hosted, seed always shown', () => {
  const local = pageModel('settings', state);
  assert.deepEqual(local.sections[0].rows[0], ['World seed', '482910']);
  assert.ok(!JSON.stringify(local).includes('"rebuild"'));
  const hosted = pageModel('settings', state, {build: '2026-10-05T10:00:00.000Z', cloudStatus: () => 'connected'});
  const ids = hosted.sections.flatMap(s => s.buttons || []).map(b => b.id);
  assert.deepEqual(ids, ['rebuild', 'wipe', 'layout', 'debug']);
  assert.ok(hosted.sections[0].rows.some(([k, v]) => k === 'Cloud save' && v === 'connected'));
});

test('collapse state: defaults per screen, stored values win, junk ignored', () => {
  assert.equal(COLLAPSE_KEY, 'dimsum.ui.collapsed');
  assert.deepEqual(PANELS, ['location', 'expedition', 'map', 'inventory']);
  assert.deepEqual(defaultCollapsed(false), {location: false, expedition: false, map: false, inventory: false});
  assert.equal(defaultCollapsed(true).expedition, true);
  assert.deepEqual(loadCollapsed('{"map":true,"bogus":true,"location":"yes"}', false),
    {location: false, expedition: false, map: true, inventory: false});
  assert.deepEqual(loadCollapsed('not json', true), defaultCollapsed(true));
  assert.deepEqual(loadCollapsed(null, false), defaultCollapsed(false));
  const s = toggleCollapsed(defaultCollapsed(false), 'map');
  assert.equal(s.map, true); assert.equal(toggleCollapsed(s, 'nope'), s);
});
