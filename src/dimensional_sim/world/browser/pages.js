/** Player pages (tabs) and collapsible HUD panels. Pure view models: pageModel() turns the
 * snapshot's `expedition.detail` block (session detail flag) into sections the DOM
 * renderer in app.js draws. Never decides game rules; every number comes from Python. */
import {LABEL} from './hud.js';

export const PAGES = Object.freeze([
  {id: 'world', label: 'World', icon: '◈'},
  {id: 'character', label: 'Hero', icon: '☺'},
  {id: 'stats', label: 'Stats', icon: '▤'},
  {id: 'speed', label: 'Speed', icon: '»'},
  {id: 'journal', label: 'Journal', icon: '✎'},
  {id: 'life', label: 'This life', icon: '⚄'},
  {id: 'settings', label: 'Settings', icon: '⚙'},
]);
export const PAGE_IDS = Object.freeze(PAGES.map(p => p.id));
export const needsDetail = page => page !== 'world' && page !== 'settings' && PAGE_IDS.includes(page);

/* ---------- formatting ---------- */
export const times = permille => `×${(permille / 1000).toFixed(2)}`;
export const seconds = ms => ms >= 60000 ? `${(ms / 60000).toFixed(1)} min` : `${(ms / 1000).toFixed(1)}s`;
const title = text => String(text).replaceAll('_', ' ').replace(/^\w/, c => c.toUpperCase());
const label = id => LABEL[id] || title(id);

/* ---------- collapsible panels ---------- */
export const PANELS = Object.freeze(['location', 'expedition', 'map', 'inventory']);
export const COLLAPSE_KEY = 'dimsum.ui.collapsed';
export function defaultCollapsed(mobile) {
  return {location: false, expedition: !!mobile, map: false, inventory: !!mobile};
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
function character(d) {
  const c = d.character;
  return [
    {title: 'Vitals', kind: 'rows', rows: [
      ['Health', `${c.health} / 100`], ['Hunger', `${c.hunger} / 100`],
      ['Hunger drain', `${c.hunger_per_minute} per min`, 'Endurance slows it'],
      ['Regeneration', `${c.regen_per_minute} per min`, `${c.rest_regen_per_minute} per min resting at camp`],
    ]},
    {title: 'Combat', kind: 'rows', rows: [
      ['Punch damage', String(c.punch_damage), 'Boars have 3 HP'],
      ['Boar hit at the frontier', `${c.boar_hit_at_frontier} health`, `ring ${c.frontier}`],
      ['Full fight at the frontier', `${c.fight_cost_at_frontier} health`, 'expected cost of one boar'],
    ]},
    {title: 'Journey', kind: 'rows', rows: [
      ['Life', String(c.life)], ['Ring now', String(c.depth)], ['Frontier (safe push)', `ring ${c.frontier}`],
      ['Deepest ring ever', String(c.best_depth)],
      ['Inventory', `${c.inventory_slots[0]} / ${c.inventory_slots[1]} slots`],
    ]},
    {title: 'Gear and boons', kind: 'rows', rows: [
      ['Gear', c.gear.length ? c.gear.join(', ') : 'none'],
      ['Boon this life', c.boon || 'none'], ['Boon next life', c.boon_next || 'none'],
    ]},
    {title: 'Across lives', kind: 'rows', rows: [
      ['Dust', String(c.currencies.dust), 'offer items at the anchor; buys actions'],
      ['Ash', String(c.currencies.ash), 'unoffered items burn at rebirth; buys mastery'],
      ['Blessing', String(c.currencies.blessing), 'from prayer; buys boons and the shrine path'],
      ['Unlocked actions', c.unlocked.length ? c.unlocked.join(', ') : 'none yet'],
    ]},
  ];
}

function stats(d) {
  const rows = d.stats;
  return [
    {title: 'Levels', kind: 'progress', items: rows.map(r => ({label: label(r.name), bars: [
      {label: `level ${r.level}`, value: r.into, max: r.next, text: `${r.into} / ${r.next} xp`},
      {label: `dimensional ${r.dim_level}`, value: r.dim_into, max: r.dim_next,
        text: `${r.dim_into} / ${r.dim_next} xp`, dim: true},
    ]}))},
    {title: 'Breakdown', kind: 'table', head: ['Attribute', 'Lv', 'Dim', 'Total XP', 'This life', 'Speed'],
      rows: rows.map(r => [label(r.name), r.level, r.dim_level, r.xp, `+${r.life_gain}`, times(r.speed)]),
      note: 'Speed multiplies every action using that attribute. Regular levels reset each life; dimensional levels stay.'},
    {title: 'Where speed comes from', kind: 'table', head: ['Attribute', 'Life levels', 'Dimensional', 'Combined'],
      rows: rows.map(r => [label(r.name), times(r.speed_regular_only), times(r.speed_dimensional_only), times(r.speed)])},
  ];
}

function speed(d) {
  const m = d.multipliers;
  const product = parts => parts.reduce((a, [, v]) => a * v, 1);
  return [
    {title: 'Action speed', kind: 'table', head: ['Action', 'Attribute', 'Speed', 'Base', 'Now'],
      rows: m.actions.map(a => [a.name, label(a.attribute), times(a.speed), seconds(a.base_ms), seconds(a.effective_ms)]),
      note: 'Only actions you know are listed. Prayer and reflection take fixed time.'},
    {title: 'Damage taken from boars', kind: 'rows',
      rows: [...m.boar_hit.map(([name, v]) => [name, `×${v}`]), ['Total', `×${product(m.boar_hit).toFixed(3)}`]]},
    {title: 'Punch damage', kind: 'rows',
      rows: [...m.punch_parts.filter(([, v]) => v).map(([name, v]) => [name, `+${v}`]), ['Total', String(m.punch_damage)]]},
    {title: 'Hunger', kind: 'rows', rows: [['Drain multiplier', `×${m.hunger_drain}`, 'from endurance']]},
  ];
}

function journal(d) {
  const j = d.journal;
  const done = j.achievements.filter(a => a.done).length;
  const deaths = Object.entries(j.deaths);
  const categories = {};
  for (const [, category, n] of j.actions) categories[category] = (categories[category] || 0) + n;
  return [
    {title: `Achievements · ${done} / ${j.achievements.length}`, kind: 'progress', items: j.achievements.map(a => ({
      label: a.name, value: a.progress, max: a.threshold, text: a.done ? 'done' : `${a.progress} / ${a.threshold}`,
      note: a.description, done: a.done}))},
    {title: 'Lifetime', kind: 'rows', rows: [
      ['Lives', String(j.lives)], ['Deepest ring', String(j.best_depth)], ['Longest life', `${j.best_life_min} min`],
      ...(deaths.length ? deaths.map(([cause, n]) => [`Deaths by ${cause}`, String(n)]) : [['Deaths', 'none yet']]),
    ]},
    {title: 'Actions by type', kind: 'table', head: ['Type', 'Done'],
      rows: Object.entries(categories).sort((a, b) => b[1] - a[1]).map(([c, n]) => [title(c), n]),
      empty: 'Nothing completed yet.'},
    {title: 'Actions', kind: 'table', head: ['Action', 'Type', 'Done'],
      rows: j.actions.map(([name, category, n]) => [name, title(category), n]), empty: 'Nothing completed yet.'},
    {title: 'Items gathered', kind: 'table', head: ['Item', 'Total'], rows: j.items, empty: 'Nothing gathered yet.'},
    {title: 'Discoveries', kind: 'rows', rows: [
      ['Knowledge', j.knowledge.map(title).join(', ') || 'none yet'],
      ['Recipes', j.recipes.map(title).join(', ') || 'none yet'],
      ['Active leads', String(j.leads.length)],
    ]},
    {title: 'Recent leads', kind: 'table', head: ['Lead', 'Source', 'State'],
      rows: j.lead_history.slice(-10).reverse().map(row => [title(row.action), row.source, row.status]),
      empty: 'No leads yet.'},
  ];
}

function life(d) {
  const r = d.rolls;
  const known = r.windows.filter(w => w.known), locked = r.windows.filter(w => !w.known);
  const rollRow = w => [w.name, w.rolled ?? '∞', w.max === null ? '-' : `${w.min}–${w.max}`,
    w.rolled === w.max ? 'max' : w.rolled === w.min ? 'min' : '', `${w.active} / ${w.spawned}`, w.mastery];
  const lucky = known.filter(w => w.rolled === w.max).length;
  return [
    {title: `Spawn windows · life ${r.life}`, kind: 'table', head: ['Action', 'Rolled', 'Possible', '', 'Now / spawned', 'Mastery'],
      rows: known.map(rollRow),
      note: `${lucky} of ${known.length} rolled their maximum. Each life rolls how many of each can exist at once; mastery (ash) widens the range.`},
    ...(locked.length ? [{title: 'Rolled but not yet known', kind: 'table', head: ['Action', 'Rolled', 'Possible', '', 'Now / spawned', 'Mastery'],
      rows: locked.map(rollRow), note: 'Unlock these with dust at the anchor.'}] : []),
    {title: 'Spots and pity', kind: 'rows', rows: [
      ['Spots per chunk', `${r.spots_per_chunk[0]}–${r.spots_per_chunk[1]}`],
      ...r.pity.map(p => [`${title(p.category)} drought`, `${p.drought} / ${p.after} chunks`, 'a spot is forced when it reaches the limit']),
    ]},
    {title: 'This life so far', kind: 'rows', rows: Object.entries(r.stats).map(([k, v]) => [title(k), String(v)])},
    {title: 'Loot ranges', kind: 'table', head: ['Action', 'Item', 'Amount', 'Chance'],
      rows: r.loot.flatMap(a => a.drops.map((drop, i) => [i ? '' : a.name, drop.item,
        drop.min === drop.max ? drop.min : `${drop.min}–${drop.max}`, `${drop.chance}%`]))},
  ];
}

function settings(state, host) {
  const rows = [['World seed', String(state?.world_seed ?? '-')]];
  if (host?.build) rows.push(['Build', String(host.build).replace('T', ' ').slice(0, 19)]);
  if (host?.cloudStatus) rows.push(['Cloud save', host.cloudStatus()]);
  const sections = [{title: 'This world', kind: 'rows', rows}];
  if (host) sections.push({title: 'Reset', kind: 'actions', buttons: [
    {id: 'rebuild', label: 'New world, keep progress',
      note: 'A fresh forest from a new seed. Keeps dimensional levels, dust, ash, blessing, unlocks, mastery and the journal; starts the next life.'},
    {id: 'wipe', label: 'Start over', danger: true,
      note: 'Deletes this browser\'s save and its cloud link, then starts a brand-new game. Copy your save code first if you may want it back.'},
  ]});
  else sections.push({title: 'Reset', kind: 'rows', rows: [
    ['Local server', 'restart it with --seed N for a new world'],
  ]});
  sections.push({title: 'Layout', kind: 'actions', buttons: [
    {id: 'layout', label: 'Reset panel layout', note: 'Expands or collapses the HUD panels back to the defaults for this screen size.', plain: true},
    {id: 'debug', label: 'Toggle debug overlay', note: 'Seeds, buckets, windows and pity (also the ` key).', plain: true},
  ]});
  return sections;
}

const BUILDERS = {character, stats, speed, journal, life};

/** {title, sections} for one page, or {title, loading: true} while the detail block is on its way. */
export function pageModel(page, state, host = null) {
  const meta = PAGES.find(p => p.id === page);
  if (!meta || page === 'world') return null;
  if (page === 'settings') return {title: 'Settings', sections: settings(state, host)};
  const detail = state?.expedition?.detail;
  if (!detail) return {title: meta.label, loading: true, sections: []};
  return {title: meta.label === 'Hero' ? 'Character' : meta.label, sections: BUILDERS[page](detail)};
}
