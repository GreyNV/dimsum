/** Player pages (tabs) and collapsible HUD panels. Pure view models: pageModel() turns the
 * snapshot's `expedition.detail` block (session detail flag) into sections the DOM
 * renderer in app.js draws. Never decides game rules; every number comes from Python. */
import {LABEL} from './hud.js';

export const PAGES = Object.freeze([
  {id: 'world', label: 'World', icon: '◈'},
  {id: 'stats', label: 'Stats', icon: '▤', subtabs: [{id: 'character', label: 'Character'}, {id: 'statistics', label: 'Statistics'}]},
  {id: 'journal', label: 'Journal', icon: '✎', subtabs: [{id: 'encounters', label: 'Encounters'}, {id: 'achievements', label: 'Achievements'}]},
  {id: 'settings', label: 'Settings', icon: '⚙'},
]);
/** Subtabs of a page ([] when it has none); the first one is the page's main view. */
export const subtabsOf = page => PAGES.find(p => p.id === page)?.subtabs || [];
export const PAGE_IDS = Object.freeze(PAGES.map(p => p.id));
export const needsDetail = page => page !== 'world' && page !== 'settings' && PAGE_IDS.includes(page);

/* ---------- formatting ---------- */
export const times = permille => `×${(permille / 1000).toFixed(2)}`;
export const seconds = ms => ms >= 60000 ? `${(ms / 60000).toFixed(1)} min` : `${(ms / 1000).toFixed(1)}s`;
const title = text => String(text).replaceAll('_', ' ').replace(/^\w/, c => c.toUpperCase());
const label = id => LABEL[id] || title(id);

/* ---------- collapsible panels ---------- */
// The inventory is never folded: on phones it opens as a centered bag (Bag button), on desktop it stays open.
export const PANELS = Object.freeze(['location', 'expedition', 'map']);
export const COLLAPSE_KEY = 'dimsum.ui.collapsed';
export function defaultCollapsed(mobile) {
  return {location: false, expedition: false, map: false};
}
/** Stored layout (JSON text or null) over the defaults; unknown keys and bad values are ignored. */
export function loadCollapsed(raw, mobile) {
  const result = defaultCollapsed(mobile);
  let stored = null;
  try { stored = raw ? JSON.parse(raw) : null; } catch { stored = null; }
  if (stored && typeof stored === 'object' && !Array.isArray(stored))
    for (const id of PANELS) if (typeof stored[id] === 'boolean') result[id] = stored[id];
  return result;
}
export const toggleCollapsed = (state, id) => PANELS.includes(id) ? {...state, [id]: !state[id]} : state;

/* ---------- page models ---------- */
const pct = permille => `${(permille / 10).toFixed(1)}%`;
const product = parts => parts.reduce((a, [, v]) => a * v, 1);
const JOURNAL_MODES = ['normal', 'favor', 'suppress'];
export const nextMode = mode => JOURNAL_MODES[(JOURNAL_MODES.indexOf(mode) + 1) % JOURNAL_MODES.length];

/** Stats · Character (main): levels, vitals, gear and every multiplier on the character. */
function character(d) {
  const c = d.character, m = d.multipliers, rows = d.stats.filter(r => r.used ?? true);
  const camp = c.camp || {buildings: [], chest: []}, load = c.load;
  return [
    {title: 'Levels', kind: 'progress', items: rows.map(r => ({label: label(r.name), bars: [
      {label: `level ${r.level}`, value: r.into, max: r.next, text: `${r.into} / ${r.next} xp`},
      {label: `dimensional ${r.dim_level}`, value: r.dim_into, max: r.dim_next,
        text: `${r.dim_into} / ${r.dim_next} xp`, dim: true},
    ]}))},
    {title: 'Vitals', kind: 'rows', rows: [
      ['Health', `${c.health} / 100`], ['Hunger', `${c.hunger} / 100`],
      ['Hunger drain', `${c.hunger_per_minute} per min`, `×${m.hunger_drain} from endurance`],
      ['Regeneration', `${c.regen_per_minute} per min`, `${c.rest_regen_per_minute} per min resting at camp`],
    ]},
    {title: 'Combat', kind: 'rows', rows: [
      ...m.punch_parts.filter(([, v]) => v).map(([name, v]) => [`Punch · ${name}`, `+${v}`]),
      ['Punch damage', String(m.punch_damage)],
      ...m.enemy_hit.map(([name, v]) => [`Damage taken · ${name}`, `×${v}`]),
      ['Damage taken', `×${product(m.enemy_hit).toFixed(3)}`],
      ...c.threats.flatMap(t => [
        [`${t.name} at the frontier`, `${t.hit_at_frontier} health per bite`, `${t.hp} HP in ring ${c.frontier}`],
        [`Full fight with a ${t.name.toLowerCase()}`, `${t.fight_cost_at_frontier} health`, 'expected cost of one fight'],
      ]),
    ]},
    {title: 'Attribute speed', kind: 'table', head: ['Attribute', 'Lv', 'Dim', 'Life levels', 'Dimensional', 'Speed'],
      rows: rows.map(r => [label(r.name), r.level, r.dim_level, times(r.speed_regular_only),
        times(r.speed_dimensional_only), times(r.speed)]),
      note: 'Speed multiplies every action using that attribute. Regular levels reset each life; dimensional levels stay.'},
    {title: 'Anchor camp', kind: 'rows', rows: [
      ...(camp.buildings.length ? camp.buildings.map(b => [b.name, b.bound ? 'bound - stands in every life' : 'this life only',
        b.bound ? '' : 'bind it with ash at the anchor to keep it']) : [['Buildings', 'none yet', 'build a crafting station at the camp (primitive crafting)']]),
      ...(camp.chest.length ? [['Chest contents', camp.chest.map(i => `${i.name} x${i.count}`).join(', ')]] : []),
      ...(load ? [['Carry load', load.percent > 100 ? `walking +${load.percent - 100}% slower` : 'no penalty',
        `${load.carried} items carried; the first ${load.free} are free, then +${load.per_item}% each (max +${load.max}%), eased by Endurance and Strength (x${(load.relief_permille / 1000).toFixed(2)})`]] : []),
    ], note: 'Every craft needs a crafting station at the camp. Buildings fall when the life ends unless bound.'},
    {title: 'Gear', kind: 'rows', rows: [
      ['Gear', c.gear.length ? c.gear.join(', ') : 'none'],
    ]},
    {title: 'Journey', kind: 'rows', rows: [
      ['Life', String(c.life)], ['Ring now', String(c.depth)], ['Frontier (safe push)', `ring ${c.frontier}`],
      ['Inventory', `${c.inventory_slots[0]} / ${c.inventory_slots[1]} slots`],
      ['Dimensional ash', String(c.currencies.ash), 'carried resources convert when a life ends; keeps recipes, binds buildings, buys skills (buy skill 1 to contact the anchor)'],
      ['Unlocked', c.unlocked.length ? c.unlocked.join(', ') : 'none yet'],
    ]},
    ...(c.openings ? [{title: 'What opens as you grow', kind: 'table', head: ['Opens', 'Needs (dimensional level)', 'You', ''],
      rows: c.openings.map(o => [o.name, `${label(o.attribute)} ${o.level}`, String(o.have), o.open ? 'open' : `${o.level - o.have} to go`]),
      note: 'New kinds of encounters open by themselves when a dimensional level is reached. Dimensional levels carry over between lives.'}] : []),
  ];
}

/** Stats · Statistics: lifetime record and every count. */
function statistics(d) {
  const j = d.journal, rows = d.stats.filter(r => r.used ?? true);
  const deaths = Object.entries(j.deaths);
  const categories = {};
  for (const [, category, n] of j.actions) categories[category] = (categories[category] || 0) + n;
  return [
    {title: 'Lifetime', kind: 'rows', rows: [
      ['Lives', String(j.lives)], ['Deepest ring', String(j.best_depth)], ['Longest life', `${j.best_life_min} min`],
      ...(deaths.length ? deaths.map(([cause, n]) => [`Deaths by ${cause}`, String(n)]) : [['Deaths', 'none yet']]),
    ]},
    {title: 'This life so far', kind: 'rows', rows: Object.entries(d.rolls?.stats || {}).map(([k, v]) => [title(k), String(v)])},
    {title: 'Experience', kind: 'table', head: ['Attribute', 'Total XP', 'This life'],
      rows: rows.map(r => [label(r.name), r.xp, `+${r.life_gain}`])},
    {title: 'Actions by type', kind: 'table', head: ['Type', 'Done'],
      rows: Object.entries(categories).sort((a, b) => b[1] - a[1]).map(([c, n]) => [title(c), n]),
      empty: 'Nothing completed yet.'},
    {title: 'Actions', kind: 'table', head: ['Action', 'Type', 'Done'],
      rows: j.actions.map(([name, category, n]) => [name, title(category), n]), empty: 'Nothing completed yet.'},
    {title: 'Items gathered', kind: 'table', head: ['Item', 'Total'], rows: j.items, empty: 'Nothing gathered yet.'},
  ];
}

/** Journal controls for one encounter: favor/suppress (grade 2) and a regional guarantee (grade 3). */
function encounterButtons(e, guarantee) {
  return [
    ...(e.can_favor ? [{label: `Odds: ${e.mode}`, note: 'select to cycle normal → favor → suppress',
      action: {type: 'journal_favor', id: e.id, mode: nextMode(e.mode)}, on: e.mode !== 'normal'}] : []),
    ...(e.can_guarantee ? e.regions.map(region => {
      const chosen = guarantee.id === e.id && guarantee.region === region.id;
      return {label: chosen ? `Guaranteed in ${region.name}` : `Guarantee in ${region.name}`,
        note: chosen ? (guarantee.used ? 'placed this life; select to clear' : 'select to clear') : 'once per life',
        action: {type: 'journal_guarantee', id: chosen ? null : e.id, region: chosen ? null : region.id}, on: chosen};
    }) : []),
  ];
}

const pips = level => '●'.repeat(level) + '○'.repeat(Math.max(0, 3 - level));
/** One encounter as a tree node: a one-line summary, details on opening, and the trails it opens. */
function encounterNode(n, byId, guarantee) {
  const e = byId[n.id];
  if (!e) return null;
  const spot = e.placement === 'spot';
  const where = e.placement === 'site' ? `at ${e.site.toLowerCase()}` : e.placement === 'lead' ? 'follows another encounter'
    : e.regions.map(x => x.name).join(', ') || '-';
  const count = e.next ? `${e.done} / ${e.next}` : String(e.done);
  return {key: `enc:${e.id}`, label: e.name, tier: e.rarity,
    badge: spot ? `${pips(e.level)} ${count}` : count === '0' ? 'not done yet' : `done ${count}`,
    rows: [
      ['What you do', e.interaction || '-'],
      ['Where', where],
      ...(spot ? [['Grade', `${e.level} / 3`, e.next ? `next at ${e.next} completions` : 'mastered'],
        ['Chance here', e.level >= 1 ? `${pct(e.current_share_permille)} per spot` : '?', 'grade 1 reveals it']] : []),
      ...(spot && e.level >= 1 ? [['Seen this life', e.locations.length ? `${e.locations.length} place${e.locations.length > 1 ? 's' : ''}` : 'none yet']] : []),
    ],
    buttons: encounterButtons(e, guarantee),
    hidden: n.hidden,
    children: n.children.map(c => encounterNode(c, byId, guarantee)).filter(Boolean)};
}

/** The encounter tree: branches by what you do, landmarks by site, trails under their source. */
export function encounterTree(j) {
  const byId = Object.fromEntries((j.encounters || []).map(e => [e.id, e]));
  const guarantee = j.guarantee || {};
  const branch = g => ({key: `group:${g.id}`, label: g.title, group: true, badge: `${g.known} / ${g.total} found`,
    rows: [], buttons: [], hidden: 0,
    children: [...(g.groups || []).map(branch), ...g.nodes.map(n => encounterNode(n, byId, guarantee)).filter(Boolean)]});
  return (j.tree || []).map(branch);
}

/** Journal · Encounters (main): tiers here, the encounter tree, durations, drops, chains. */
function encounters(d) {
  const j = d.journal, r = d.rolls || {};
  const bonus = (r.loot || []).flatMap(a => a.drops.filter(drop => drop.roll !== 'fixed')
    .map((drop, i) => [i ? '' : a.name, drop.item, drop.roll, `${drop.chance}%`]));
  const m = d.multipliers;
  return [
    {title: 'Encounter rarity here', kind: 'rows', rows: (r.tiers || []).map(t =>
      [t.name, `${pct(t.permille)} per spot`, `${t.actions} eligible`]),
      note: 'Each spot rolls rare first, then uncommon; a miss falls through to common. Unlocking more of a tier raises its odds.'},
    {title: 'Encounters', kind: 'tree', items: encounterTree(j), empty: 'No encounters known yet.',
      note: 'Open a branch, then an encounter. ●●○ is its grade: grade 1 reveals where and how often it appears, grade 2 lets you favor or suppress it, grade 3 guarantees it in a chosen region. Trails hang under what opens them; "not found yet" keeps their names secret.'},
    {title: 'Action durations', kind: 'table', head: ['Action', 'Attribute', 'Speed', 'Base', 'Now'],
      rows: m.actions.map(a => [a.name, label(a.attribute), times(a.speed), seconds(a.base_ms), seconds(a.effective_ms)]),
      note: 'Only actions you know are listed. Prayer and reflection take fixed time.'},
    {title: 'Bonus drops', kind: 'table', head: ['Action', 'Item', 'Rarity', 'Chance'], rows: bonus,
      empty: 'No known action has a bonus roll yet.'},
    {title: 'Chains and discoveries', kind: 'rows', rows: [
      ['Knowledge', j.knowledge.map(title).join(', ') || 'none yet'],
      ['Recipes kept', j.recipes.map(title).join(', ') || 'none yet', 'known in every life'],
      ...(j.life_recipes?.length ? [['Found this life', j.life_recipes.map(title).join(', '), 'keep them at the anchor with ash, or they are forgotten']] : []),
      ['Active leads', String(j.leads.length)],
    ]},
    {title: 'Recent leads', kind: 'table', head: ['Lead', 'Source', 'State'],
      rows: j.lead_history.slice(-10).reverse().map(row => [title(row.action), row.source, row.status]),
      empty: 'No leads yet.'},
  ];
}

/** Journal · Achievements. */
function achievementsPage(d) {
  const list = d.journal.achievements;
  const done = list.filter(a => a.done).length;
  return [
    {title: `Achievements · ${done} / ${list.length}`, kind: 'progress', items: list.map(a => ({
      label: a.name, value: a.progress, max: a.threshold, text: a.done ? 'done' : `${a.progress} / ${a.threshold}`,
      note: a.description, done: a.done}))},
  ];
}

function settings(state, host, prefs = {}) {
  const rows = [['World seed', String(state?.world_seed ?? '-')]];
  if (host?.build) rows.push(['Build', String(host.build).replace('T', ' ').slice(0, 19)]);
  if (host?.cloudStatus) rows.push(['Cloud save', host.cloudStatus()]);
  const sections = [{title: 'This world', kind: 'rows', rows}];
  if (host) sections.push({title: 'Reset', kind: 'actions', buttons: [
    {id: 'rebuild', label: 'New world, keep progress',
      note: 'A fresh forest from a new seed. Keeps dimensional levels, ash, unlocks, mastery and the journal; starts the next life.'},
    {id: 'wipe', label: 'Start over', danger: true,
      note: 'Deletes this browser\'s save and its cloud link, then starts a brand-new game. Copy your save code first if you may want it back.'},
  ]});
  else sections.push({title: 'Reset', kind: 'rows', rows: [
    ['Local server', 'restart it with --seed N for a new world'],
  ]});
  if (prefs.sound) sections.push({title: 'Sound', kind: 'actions', buttons: [
    {id: 'sound-volume', label: `Volume: ${prefs.sound.label}`, note: 'Off, low, medium or high. M mutes and unmutes.', plain: true},
    {id: 'sound-ambience', label: `Ambience: ${prefs.sound.ambience ? 'On' : 'Off'}`, note: 'Wind, birds, the river near water and fire crackle beside a fire.', plain: true},
  ]});
  sections.push({title: 'Layout', kind: 'actions', buttons: [
    {id: 'layout', label: 'Reset panel layout', note: 'Expands or collapses the HUD panels back to the defaults for this screen size.', plain: true},
    {id: 'debug', label: 'Toggle debug overlay', note: 'Seeds, buckets, windows and pity (also the ` key).', plain: true},
  ]});
  return sections;
}

const BUILDERS = {stats: {character, statistics}, journal: {encounters, achievements: achievementsPage}};

/** {title, subtabs, sub, sections} for one page (sub defaults to the main subtab), or
 * {title, loading: true} while the detail block is on its way. */
export function pageModel(page, state, host = null, sub = null, prefs = {}) {
  const meta = PAGES.find(p => p.id === page);
  if (!meta || page === 'world') return null;
  if (page === 'settings') return {title: 'Settings', subtabs: [], sub: null, sections: settings(state, host, prefs)};
  const subtabs = subtabsOf(page);
  const chosen = subtabs.some(t => t.id === sub) ? sub : subtabs[0].id;
  const detail = state?.expedition?.detail;
  if (!detail) return {title: meta.label, subtabs, sub: chosen, loading: true, sections: []};
  return {title: meta.label, subtabs, sub: chosen, sections: BUILDERS[page][chosen](detail)};
}
