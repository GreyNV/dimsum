import test from 'node:test';
import assert from 'node:assert/strict';
import {PAGES, PAGE_IDS, needsDetail, pageModel, subtabsOf, nextMode, PANELS, COLLAPSE_KEY, defaultCollapsed, loadCollapsed, toggleCollapsed, times, seconds} from '../src/dimensional_sim/world/browser/pages.js';

// Same shape as details.detail() (tests/test_world_pages.py checks the Python side).
const stat = name => ({name, level: 2, xp: 250, into: 40, next: 130, dim_level: 1, dim_xp: 110, dim_into: 10, dim_next: 135,
  speed: 1210, speed_regular_only: 1200, speed_dimensional_only: 1010, life_gain: 50});
const detail = {
  character: {life: 3, depth: 2, best_depth: 5, frontier: 3, health: 80.5, hunger: 41, punch_damage: 2, gear: ['Walking staff'],
    threats: [{id: 'bramble_boar', name: 'Bramble boar', hp: 6, hit_at_frontier: 20.1, fight_cost_at_frontier: 40.2}], hunger_per_minute: 30,
    regen_per_minute: 12, rest_regen_per_minute: 60, inventory_slots: [3, 12], currencies: {ash: 2}, unlocked: ['Climbing'],
    openings: [{name: 'Snare lines', description: 'Hunter cabins.', attribute: 'perception', level: 3, have: 2, open: false}],
    camp: {buildings: [{id: 'crafting_station', name: 'Crafting station', bound: true}], chest: [{item: 'stick', name: 'Stick', count: 7}], at_camp: false},
    load: {percent: 118, carried: 28, free: 10, per_item: 1, max: 60, relief_permille: 1000},
    sight_radius: 6, possession_seconds: 38},
  stats: ['strength', 'endurance', 'agility', 'intelligence', 'perception', 'willpower'].map(stat),
  multipliers: {actions: [{id: 'bramble_berries', name: 'Bramble berries', attribute: 'perception', speed: 1410, base_ms: 2400, effective_ms: 1703}],
    hunger_drain: 0.909, enemy_hit: [['Endurance', 0.909], ['Hide wrap', 0.7]], punch_damage: 2, punch_parts: [['Base', 1], ['Strength levels', 1]]},
  rolls: {life: 3, windows: [
    {id: 'bramble_berries', name: 'Bramble berries', rolled: 2, min: 1, max: 2, active: 1, spawned: 4, mastery: 0, known: true},
    {id: 'gnarled_tree', name: 'Gnarled tree', rolled: 1, min: 1, max: 1, active: 0, spawned: 0, mastery: 0, known: false}],
    spots_per_chunk: [0, 3], tiers: [{tier: 'uncommon', name: 'Uncommon', permille: 83, actions: 2},
      {tier: 'common', name: 'Common', permille: 917, actions: 5}],
    pity: [{category: 'food', drought: 2, after: 5}], stats: {pity: 1},
    loot: [{id: 'bramble_boar', name: 'Bramble boar', drops: [{item: 'Boar meat', min: 1, max: 1, chance: 100, roll: 'fixed'},
      {item: 'Boar tusk', min: 1, max: 1, chance: 14.7, roll: 'Uncommon', color: '#efe2c4'}]}]},
  journal: {actions: [['Bramble berries', 'forage', 12], ['Fallen branches', 'gather', 3]], items: [['Wild berries', 30]],
    deaths: {starvation: 2}, best_life_min: 7.5, lives: 3, best_depth: 5,
    knowledge: ['deer_sign'], recipes: [], life_recipes: ['Snare'], disabled: [], leads: [],
    encounters: [
      {id: 'bramble_berries', name: 'Bramble berries', interaction: 'Picking berries', rarity: 'common', placement: 'spot', level: 3, done: 120, next: null,
        regions: [{id: 'old_road', name: 'The Old Road'}, {id: 'still_glade', name: 'Still Glade'}], current_share_permille: 127,
        locations: ['forest:0:0'], places: ['The Old Road', 'Still Glade']},
      {id: 'old_carvings', name: 'Old carvings', rarity: 'uncommon', placement: 'spot', level: 0, done: 2, next: 5,
        regions: [{id: 'old_road', name: 'The Old Road'}], current_share_permille: 41, locations: [], places: ['The Old Road']},
      {id: 'hunt_deer', name: 'Hunt deer', rarity: 'common', placement: 'lead', level: 1, done: 4, next: 25,
        regions: [], current_share_permille: 0, locations: [], places: []},
      {id: 'camp_bedroll', name: 'Torn bedroll', rarity: 'common', placement: 'site', site: 'Abandoned camp', level: 0,
        done: 1, next: null, regions: [], current_share_permille: 0, locations: [], places: ['Abandoned camp']}],
    places: {here: 'old_road', camp: {location: 'old_road', name: 'The Old Road', focus: 'Resources'},
      focus_modes: [{id: 'none', name: 'No camp'}, {id: 'all', name: 'Everything'}, {id: 'resources', name: 'Resources'}, {id: 'searching', name: 'Searching'}],
      places: [
        {id: 'old_road', name: 'The Old Road', kind: 'region', text: 'The road.', done: 52, grade: 2, grade_name: 'Mastered',
          next: 400, camp_at: 40, can_camp: true, focus: 'resources', here: true, camped: true},
        {id: 'old_ruins', name: 'Old ruins', kind: 'site', text: 'Ruins.', done: 1, grade: 0, grade_name: 'New',
          next: 3, camp_at: 12, can_camp: false, focus: 'none', here: false, camped: false},
        {id: 'still_glade', name: 'Still Glade', kind: 'region', text: 'Glade.', done: 0, grade: 0, grade_name: 'New',
          next: 10, camp_at: 40, can_camp: false, focus: 'none', here: false, camped: false}]},
    tree: [
      {id: 'food', title: 'Food and water', known: 1, total: 6, groups: [], nodes: [{id: 'bramble_berries', hidden: 1, children: []}]},
      {id: 'signs', title: 'Signs and lore', known: 1, total: 5, groups: [],
        nodes: [{id: 'old_carvings', hidden: 0, children: [{id: 'hunt_deer', hidden: 0, children: []}]}]},
      {id: 'landmarks', title: 'Landmarks', known: 1, total: 22, nodes: [], groups: [
        {id: 'site:abandoned_camp', title: 'Abandoned camp', known: 1, total: 3, groups: [], nodes: [{id: 'camp_bedroll', hidden: 0, children: []}]}]}],
    lead_history: [{action: 'follow_deer_tracks', source: 'enc:forest:1:0:2', status: 'expired'}],
    achievements: [{id: 'first_steps', name: 'First steps', description: 'Complete an action.', progress: 1, threshold: 1, done: true},
      {id: 'woodsman', name: 'Woodsman', description: 'Gather 25 times.', progress: 3, threshold: 25, done: false}]},
};
detail.story = {
  current: {id: 'story_wall', chapter: 1, chapter_name: 'The grey wall', objective: 'Reach the grey wall',
    name: 'The grey wall', rings: [6, 6], waits: ['you can safely go as far as ring 5'], here: false},
  done: [{id: 'story_camp', chapter: 1, name: "The old man's camp", lore: ['A cold fire.', 'A page.']}],
  next: null};
const state = {world_seed: '482910', expedition: {detail}};

const allSections = () => PAGES.flatMap(p => (subtabsOf(p.id).length ? subtabsOf(p.id).map(t => t.id) : [null])
  .map(sub => pageModel(p.id, state, null, sub))).filter(Boolean).flatMap(m => m.sections);

test('pages: every tab and subtab has a model, world has none, detail pages wait for data', () => {
  assert.deepEqual(PAGE_IDS, ['world', 'stats', 'journal', 'settings']);
  assert.deepEqual(subtabsOf('stats').map(t => t.id), ['character', 'statistics']);
  assert.deepEqual(subtabsOf('journal').map(t => t.id), ['places', 'encounters', 'story', 'achievements']);
  assert.equal(pageModel('world', state), null);
  assert.equal(pageModel('nope', state), null);
  for (const p of PAGES.filter(p => needsDetail(p.id))) {
    assert.equal(pageModel(p.id, {expedition: {detail: null}}).loading, true);
    assert.equal(pageModel(p.id, state).sub, subtabsOf(p.id)[0].id, 'the first subtab is the main view');
    assert.equal(pageModel(p.id, state, null, 'nope').sub, subtabsOf(p.id)[0].id, 'unknown subtab falls back');
    for (const t of subtabsOf(p.id)) {
      const model = pageModel(p.id, state, null, t.id);
      assert.equal(model.sub, t.id);
      assert.ok(model.sections.length >= 1, `${p.id}/${t.id}`);
      for (const s of model.sections) {
        assert.ok(['rows', 'table', 'progress', 'actions', 'controls', 'tree', 'lore'].includes(s.kind));
        assert.ok(JSON.stringify(s).length > 10);
        if (s.kind === 'table') for (const row of s.rows) assert.equal(row.length, s.head.length, `${p.id}:${s.title}`);
      }
    }
  }
  assert.equal(needsDetail('settings'), false);
  assert.equal(needsDetail('world'), false);
});

test('stats: the camp section lists buildings, the chest and carry load; unused disciplines are hidden', () => {
  const camp = pageModel('stats', state).sections.find(x => x.title === 'Anchor camp').rows;
  assert.deepEqual(camp[0].slice(0, 2), ['Crafting station', 'bound - stands in every life']);
  assert.deepEqual(camp[1], ['Chest contents', 'Stick x7']);
  assert.deepEqual(camp[2].slice(0, 2), ['Carry load', 'walking +18% slower']);
  const hidden = {...detail, stats: detail.stats.map((r, i) => ({...r, used: i === 0}))};
  assert.equal(pageModel('stats', {expedition: {detail: hidden}}).sections[0].items.length, 1);
});

test('stats: character is the main view with multipliers; statistics holds every count', () => {
  const character = pageModel('stats', state).sections.map(x => x.title);
  assert.deepEqual(character.slice(0, 4), ['Levels', 'Vitals', 'Combat', 'Attribute speed']);
  const exploration = pageModel('stats', state).sections.find(x => x.title === 'Exploration and control').rows;
  assert.equal(exploration[0][1], '6 cells');
  assert.equal(exploration[1][1], '38 seconds');
  const combat = pageModel('stats', state).sections.find(x => x.title === 'Combat').rows;
  assert.ok(combat.some(([k, v]) => k === 'Damage taken' && v === '×0.636'));
  const stats = pageModel('stats', state, null, 'statistics').sections;
  assert.deepEqual(stats.find(x => x.title === 'Actions by type').rows, [['Forage', 12], ['Gather', 3]]);
  assert.ok(stats.some(x => x.title === 'Items gathered'));
  for (const removed of ['character', 'speed', 'life']) {
    assert.equal(pageModel(removed, state), null);
    assert.equal(needsDetail(removed), false);
  }
  assert.equal(times(1000), '×1.00'); assert.equal(seconds(90000), '1.5 min');
});

test('journal: encounters (main) are a tree - branches, landmarks by site, trails under their source', () => {
  const journal = pageModel('journal', state, null, 'encounters').sections;
  assert.equal(journal[0].title, 'Encounter rarity here');
  assert.deepEqual(journal.find(s => s.title === 'Encounter rarity here').rows[0], ['Uncommon', '8.3% per spot', '2 eligible']);
  const tree = journal.find(s => s.title === 'Encounters');
  assert.equal(tree.kind, 'tree');
  const [food, signs, landmarks] = tree.items;
  assert.deepEqual([food.label, food.badge, food.group], ['Food and water', '1 / 6 found', true]);
  const berries = food.children[0];
  assert.equal(berries.label, 'Bramble berries');
  assert.equal(berries.badge, 'done 120');
  assert.equal(berries.hidden, 1, 'trails not found yet are counted, not named');
  assert.deepEqual(berries.rows.find(r => r[0] === 'Chance here').slice(0, 2), ['Chance here', '12.7% per spot']);
  const carvings = signs.children[0];
  assert.equal(carvings.rows.find(r => r[0] === 'Chance here')[1], '?', 'an unknown place hides odds');
  assert.equal(carvings.badge, 'done 2');
  assert.equal(carvings.children[0].label, 'Hunt deer', 'a trail hangs under what opens it');
  assert.equal(carvings.children[0].rows.find(r => r[0] === 'Where')[1], 'follows another encounter');
  assert.equal(landmarks.children[0].label, 'Abandoned camp');
  assert.equal(landmarks.children[0].children[0].rows.find(r => r[0] === 'Where')[1], 'Abandoned camp');
  assert.deepEqual(berries.buttons, [], 'encounters have no controls: places do');
  assert.ok(journal.some(s => s.title === 'Action durations'));
  assert.deepEqual(journal.find(s => s.title === 'Chains and discoveries').rows[0], ['Knowledge', 'Deer sign']);
  assert.deepEqual(journal.find(s => s.title === 'Recent leads').rows, [['Follow deer tracks', 'enc:forest:1:0:2', 'expired']]);
  assert.deepEqual(journal.find(s => s.title === 'Bonus drops').rows, [['Bramble boar', 'Boar tusk', 'Uncommon', '14.7%']]);
  const achievements = pageModel('journal', state, null, 'achievements').sections;
  assert.equal(achievements.length, 1);
  assert.match(achievements[0].title, /1 \/ 2/);
  assert.ok(allSections().length > 15);
});

test('journal places (main): grades with progress, focus buttons only where mastered, this life\'s camp', () => {
  const [list, focus, life] = pageModel('journal', state).sections;
  assert.equal(list.title, 'Places');
  assert.deepEqual(list.items.map(i => i.label), ['The Old Road · Mastered · you are here', 'Old ruins · New'],
    'places with nothing done are left out');
  assert.deepEqual([list.items[0].text, list.items[1].text], ['52 / 400', '1 / 3']);
  assert.match(list.items[1].note, /Camp from 12 encounters/);
  assert.deepEqual(focus.items.map(i => i.label), ['The Old Road']);
  const resources = focus.items[0].buttons.find(b => b.label === 'Resources');
  assert.deepEqual([resources.on, resources.action], [true, {type: 'location_focus', id: 'old_road', mode: 'resources'}]);
  assert.deepEqual(life.rows[0].slice(0, 2), ['Camp', 'The Old Road · Resources']);
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
  assert.deepEqual(PANELS, ['location', 'expedition', 'map'], 'the bag is never folded');
  assert.deepEqual(defaultCollapsed(false), {location: false, expedition: false, map: false});
  assert.equal(defaultCollapsed(true).expedition, false, 'auto action and recent events stay visible on phones');
  assert.deepEqual(loadCollapsed('{"map":true,"bogus":true,"location":"yes"}', false),
    {location: false, expedition: false, map: true});
  assert.deepEqual(loadCollapsed('not json', true), defaultCollapsed(true));
  assert.deepEqual(loadCollapsed(null, false), defaultCollapsed(false));
  const s = toggleCollapsed(defaultCollapsed(false), 'map');
  assert.equal(s.map, true); assert.equal(toggleCollapsed(s, 'nope'), s);
});

test('stats: what opens as you grow; journal: found recipes', () => {
  const open = pageModel('stats', state).sections.find(x => x.title === 'What opens as you grow');
  assert.ok(open && JSON.stringify(open).includes('Snare lines'));
  const j = JSON.stringify(pageModel('journal', state, null, 'encounters'));
  assert.ok(j.includes('Found this life') && j.includes('Snare'), 'found recipes are listed');
});

test('journal story: the objective and why it waits, then the lore found, newest first', () => {
  const sections = pageModel('journal', state, null, 'story').sections;
  assert.deepEqual(sections[0].rows[0], ['Now', 'Reach the grey wall', 'Waiting: you can safely go as far as ring 5']);
  assert.deepEqual(sections[1], {title: "The old man's camp", kind: 'lore', lines: ['A cold fire.', 'A page.']});
});
