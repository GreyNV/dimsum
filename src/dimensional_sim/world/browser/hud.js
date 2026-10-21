/** Expedition HUD: vitals, attributes (regular + dimensional), inventory, log and
 * life reports. Reads snapshot fields only; never decides game rules. */
export const ATTRIBUTES = Object.freeze([
  ['strength', 'Strength', 'STR'], ['endurance', 'Endurance', 'END'], ['agility', 'Agility', 'AGI'],
  ['intelligence', 'Intelligence', 'INT'], ['perception', 'Perception', 'PER'], ['willpower', 'Willpower', 'WIL'],
  ['building', 'Building', 'BLD']]);
/** Disciplines show only once they have earned experience (this life or dimensional). */
export const usedAttributes = attributes => ATTRIBUTES.filter(([id]) => attributes?.[id]?.xp || attributes?.[id]?.dim_xp);
export const LABEL = Object.freeze(Object.fromEntries(ATTRIBUTES.map(([id, name]) => [id, name])));
/** Text color for items without a catalog color (catalog.ItemDef.color arrives in frames). */
export const ITEM_COLOR_DEFAULT = '#e7d7b0';

/** One-line description of what the auto-pilot is doing. */
export function activityText(state, paused = false) {
  if (paused) return 'Paused - the forest can wait';
  const ex = state.expedition;
  if (!ex) return null;
  if (ex.anchor_space?.kind === 'contact') return 'Speaking with the anchor - the world waits';
  if (ex.anchor_space?.kind === 'opening') return 'The anchor waits for you';
  if (ex.anchor_space) return ex.anchor_space.waiting ? 'The anchor waits for your choice'
    : `A new life begins in ${Math.ceil(ex.anchor_space.remaining_ms / 1000)}s`;
  if (ex.prologue) {
    const p = ex.prologue;
    if (p.stage === 'listen') return 'Listening to the old man';
    return `${p.stage === 'awaken' ? 'Wake up' : 'Stand up'} - ${Math.floor(p.progress / 10)}%`;
  }
  if (ex.activity) {
    const pct = Math.floor(ex.activity.progress / 10);
    if (ex.activity.kind === 'rest') return `${ex.activity.name || 'Resting at the anchor camp'} - ${pct}%`;
    if (ex.activity.kind === 'pray') return `Praying to the gods - ${pct}%`;
    if (ex.activity.kind === 'think') return `Thinking about the road - ${pct}%`;
    if (ex.activity.kind === 'contemplate') return `Contemplating the forest - ${pct}%`;
    if (ex.activity.kind === 'craft' || ex.activity.kind === 'build') return `${ex.activity.name} - ${pct}%`;
    if (ex.activity.interaction) return `${ex.activity.interaction} - ${pct}%`;
    return `${ex.activity.verb || 'Investigating'} ${ex.activity.name.toLowerCase()} - ${pct}%`;
  }
  if (ex.mode === 'home') return 'Badly hurt - heading back to the anchor camp';
  if (ex.mode === 'fight') return `${ex.weapon?.item ? 'Weapon up' : 'Fists up'} - fighting a ${(ex.opponent || 'foe').toLowerCase()}`;
  if (ex.control === 'manual') return `You possess the avatar - ${Math.ceil((ex.possession?.remaining_ms || 0) / 1000)}s`;
  if (ex.mode === 'travel' && ex.goal) {
    const spot = state.spots?.find(s => s.x === ex.goal.x && s.y === ex.goal.y);
    if (spot) return `Heading for ${spot.name.toLowerCase()}`;
  }
  return ex.depth > 0 ? `Exploring the dark forest - ring ${ex.depth}` : 'Exploring the dark forest';
}

/** Floating texts for new log entries: XP, items gained, food eaten. */
/** Floating texts for one log entry; items with a rarity glint (frame `item_glints`) carry
 * `glint` so the scene plays a reveal burst for them. */
export function rewardTexts(entry, colors = {}, glints = {}) {
  const texts = [];
  if (entry.type === 'encounter' && entry.xp) texts.push({text: `+${entry.xp} ${LABEL[entry.attribute]}`, color: '#bfe39a'});
  if (entry.type === 'possess') texts.push({text: 'Possessed', color: '#ffe3a0'});
  for (const [item, count] of entry.items || []) {
    if (count > 0) texts.push({text: `+${count} ${item.replaceAll('_', ' ')}`, color: colors[item] || ITEM_COLOR_DEFAULT,
      ...(glints[item] ? {glint: glints[item]} : {})});
  }
  if (entry.type === 'eat') texts.push({text: entry.text.replace(/^Ate /, '').replace(/\.$/, ''), color: '#f0c56a'});
  return texts;
}

/** New log entries since `lastSeq`. */
export function newRewards(state, lastSeq) {
  return (state.expedition?.log || []).filter(entry => entry.seq > lastSeq);
}

/** Show a report on load only while it is fresh (the intro, or a death just now). */
export function reportIsFresh(ex, windowMs = 20000) {
  return !!ex?.report && ex.total_ms - ex.report.clock_ms < windowMs;
}

/** Opening scene presentation from the server's prologue stage and progress (0..1000).
 * awaken: dark screen, memory fragments appear one by one, then the eyes open.
 * listen: the old man's lines are typed out, one per equal share of the stage. */
export function prologueView(prologue) {
  if (!prologue) return {stage: null, dark: false, eyes: 1, memories: 0, line: -1, text: ''};
  const p = Math.max(0, Math.min(1000, prologue.progress)), lines = prologue.lines || [];
  if (prologue.stage === 'awaken') {
    const memories = Math.min(lines.length, 1 + Math.floor(p * lines.length / 780));
    return {stage: 'awaken', dark: true, eyes: Math.max(0, Math.min(1, (p - 820) / 180)), memories, line: -1, text: ''};
  }
  if (prologue.stage === 'listen' && lines.length) {
    const slot = 1000 / lines.length, line = Math.min(lines.length - 1, Math.floor(p / slot));
    const within = (p - line * slot) / slot, full = lines[line];
    return {stage: 'listen', dark: false, eyes: 1, memories: 0, line,
      text: full.slice(0, Math.ceil(full.length * Math.min(1, within / .6)))};
  }
  return {stage: prologue.stage, dark: false, eyes: 1, memories: 0, line: -1, text: ''};
}

/** A new seeded world gets its own opening even in a browser with an old save. */
export const reportStorageKey = (worldSeed, report) => `${worldSeed}:${report.life}:${report.seq}`;

export class ExpeditionHud {
  constructor(doc = document) {
    this.doc = doc; this.signature = ''; this.vitalsSignature = '';
    this.$ = id => doc.getElementById(id);
  }
  update(state) {
    const ex = state.expedition;
    if (!ex) return;
    this.updateVitals(ex);
    this.updatePrologue(ex);
    const signature = JSON.stringify([ex.attributes, ex.log.map(e => e.seq), ex.inventory, ex.control]);
    if (signature === this.signature) return;
    this.signature = signature;
    this.renderAttributes(ex);
    this.renderInventory(ex);
    this.renderLog(ex);
  }
  updateVitals(ex) {
    const v = ex.vitals;
    const signature = [v.health, v.hunger, ex.life, ex.depth, ex.best_depth, v.ash,
      Math.ceil((ex.clock?.until_ms || 0) / 1000), ex.clock?.night].join();
    if (signature === this.vitalsSignature) return;
    this.vitalsSignature = signature;
    for (const [name, value] of [['health', v.health], ['hunger', v.hunger]]) {
      const pct = Math.max(0, Math.min(100, value / v.max * 100));
      this.$(`${name}-bar`).style.width = pct.toFixed(1) + '%';
      this.$(`${name}-value`).textContent = String(Math.ceil(pct));
      this.$(`${name}-bar`).closest('.vital').classList.toggle('low', pct < 30);
    }
    this.$('life').textContent = `Life ${ex.life}`;
    this.$('depth').textContent = `Ring ${ex.depth} - best ${ex.best_depth}`;
    const clock = this.$('clock');
    if (clock && ex.clock) {
      const s = Math.ceil(ex.clock.until_ms / 1000), mmss = `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`;
      clock.textContent = ex.clock.night ? `☾ Night · dawn in ${mmss}` : `☀ Day ${ex.clock.day} · night in ${mmss}`;
      clock.classList.toggle('night', !!ex.clock.night);
    }
    const wealth = this.$('wealth');
    if (wealth) wealth.textContent = `◇ ${v.ash ?? 0} dimensional ash`;
  }
  /** Opening scene: dark screen with memories, then the old man's words. The rest
   * of the HUD stays hidden until the prologue ends, then fades in. */
  updatePrologue(ex) {
    const view = prologueView(ex.prologue), body = this.doc.body;
    const key = [view.stage, view.memories, view.line, view.text.length, view.eyes > 0].join();
    if (key === this.prologueSignature) return;
    this.prologueSignature = key;
    body.classList.toggle('prologue', !!view.stage);
    body.classList.toggle('prologue-dark', view.dark);
    body.classList.toggle('eyes-open', view.dark && view.eyes > 0);
    const memory = this.$('memory'), dialogue = this.$('dialogue');
    if (memory) {
      memory.hidden = !view.dark;
      const lines = ex.prologue?.stage === 'awaken' ? ex.prologue.lines.slice(0, view.memories) : [];
      const list = this.$('memory-lines');
      while (list.children.length > lines.length) list.lastChild.remove();
      for (let i = list.children.length; i < lines.length; i++)
        list.append(Object.assign(this.doc.createElement('li'), {textContent: lines[i]}));
    }
    if (dialogue) {
      dialogue.hidden = view.stage !== 'listen';
      if (view.stage === 'listen') {
        this.$('dialogue-text').textContent = view.text;
        this.$('dialogue-pips').replaceChildren(...ex.prologue.lines.map((_, i) =>
          Object.assign(this.doc.createElement('i'), {className: i < view.line ? 'done' : i === view.line ? 'now' : ''})));
      }
    }
  }
  renderAttributes(ex) {
    this.$('attributes').replaceChildren(...usedAttributes(ex.attributes).map(([id, name, short]) => {
      const a = ex.attributes[id], li = this.doc.createElement('li');
      li.title = `${name}: level ${a.level} (${a.into}/${a.next} XP this life)\n`
        + `Dimensional level ${a.dim_level} (${a.dim_into}/${a.dim_next}, persists)\nSpeed x${(a.speed / 1000).toFixed(2)}`;
      const label = this.doc.createElement('span'); label.textContent = short;
      const value = this.doc.createElement('b'); value.textContent = String(a.level);
      const dim = this.doc.createElement('em'); dim.textContent = `◆${a.dim_level}`;
      const bar = this.doc.createElement('i'), fill = this.doc.createElement('s');
      fill.style.width = Math.min(100, a.into / a.next * 100).toFixed(1) + '%';
      bar.append(fill);
      li.append(label, value, dim, bar);
      if (a.xp || a.dim_xp) li.className = 'earned';
      return li;
    }));
  }
  renderInventory(ex) {
    const rows = ex.inventory;
    const load = ex.load?.percent > 100 ? ` · load +${ex.load.percent - 100}%` : '';
    this.$('inventory-count').textContent = `${rows.length}/${ex.inventory_slots}${load}`;
    this.$('inventory-count').title = ex.load ? `Carrying ${ex.load.carried} items: walking takes ${ex.load.percent}% of normal time` : '';
    const slots = [];
    for (let i = 0; i < ex.inventory_slots; i++) {
      const row = rows[i], li = this.doc.createElement('li');
      if (!row) { li.className = 'empty'; slots.push(li); continue; }
      li.className = row.kind;
      li.title = `${row.name} x${row.count}` + (row.food ? ` - restores ${row.food} hunger (eaten when it fully fits)` : ' - material');
      li.setAttribute('aria-label', `${row.name}, ${row.count}.` + (row.food ? ` Restores ${row.food} hunger when it fully fits.` : ''));
      li.dataset.name = row.name;
      li.dataset.count = String(row.count);
      li.textContent = row.glyph;
      li.style.color = row.color || ITEM_COLOR_DEFAULT;
      const count = this.doc.createElement('small'); count.textContent = String(row.count);
      li.append(count);
      slots.push(li);
    }
    this.$('inventory').replaceChildren(...slots);
  }
  renderLog(ex) {
    const entries = [...ex.log].reverse().slice(0, 4);
    this.$('log').replaceChildren(...(entries.length ? entries.map(entry => {
      const li = this.doc.createElement('li');
      const head = this.doc.createElement('b');
      head.textContent = entry.type === 'encounter'
        ? `+${entry.xp} ${LABEL[entry.attribute]}` + (entry.dim_xp ? ` (◆+${entry.dim_xp})` : '')
        : {eat: 'Ate', rest: 'Rested', life: 'Anchor', possess: 'Possessed', night: 'Night', lore: 'The road', story: 'Story', trade: 'Offered',
          ambush: 'Ambush', craft: entry.xp ? `Crafted +${entry.xp} ${LABEL[entry.attribute] || ''}` : 'Crafted',
          reflect: 'Thought', purchase: 'Anchor', rebirth: 'Rebirth',
          build: entry.xp ? `Built +${entry.xp} ${LABEL[entry.attribute] || ''}` : 'Built', stow: 'Chest'}[entry.type] || entry.type;
      const text = this.doc.createElement('span'); text.textContent = entry.text;
      li.append(head, text);
      return li;
    }) : [Object.assign(this.doc.createElement('li'), {className: 'empty', textContent: 'Nothing found yet - the forest is wide.'})]));
  }
  showReport(report) {
    this.$('report-title').textContent = report.title;
    this.$('report-lines').replaceChildren(...report.lines.map((line, i) => {
      const li = this.doc.createElement('li'); li.textContent = line;
      li.style.animationDelay = (i * 0.18) + 's';
      return li;
    }));
    this.$('report').hidden = false;
    this.$('report').classList.toggle('opening', report.life === 0);
    this.$('report-close').textContent = report.life === 0 ? 'Begin the next life' : 'Continue';
    this.$('report').focus({preventScroll: true});
    this.$('report').scrollTop = 0;
  }
  hideReport() { this.$('report').hidden = true; }
}

/** Anchor shop rows grouped for display: [{title, rows}] (rows come from the server). */
export function shopSections(shop) {
  const groups = [['keep', 'Keep what you learned this life'], ['unlock', 'Skills'],
    ['bind', 'Bind camp buildings']];
  return groups.map(([kind, title]) => ({kind, title, rows: (shop || []).filter(r => r.kind === kind && !r.owned)}))
    .filter(section => section.rows.length);
}

/** Compact multi-line text for the debug overlay (backquote key or ?debug). */
export function debugText(info) {
  if (!info) return 'debug: waiting for data...';
  const pct = r => `${r.id} ${(r.modifiers || []).length
    ? `${r.base_weight} ${(r.modifiers || []).map(m => `x${m.percent / 100} ${m.source}`).join(' ')} = ` : ''}${r.weight} (${(r.share_permille / 10).toFixed(1)}%)`;
  return [
    `seed ${info.world_seed}  life ${info.life}  chunk ${info.chunk}  region ${info.region}`,
    `ash ${info.currencies.ash}`,
    `unlocked: ${info.unlocked.join(', ') || 'none'}  knowledge: ${(info.knowledge || []).join(', ') || 'none'}  recipes: ${(info.recipes || []).join(', ') || 'none'}`,
    `region params: ${info.region_parameters ? `canopy ${info.region_parameters.canopy} brush ${info.region_parameters.brush} ${info.region_parameters.landmark}` : '-'}  generator v${info.generator_version ?? '?'}`,
    `states: ${(info.states || []).map(r => `${r.id}=${r.state}${r.admitted ? '*' : ''}`).join(' ')}`,
    `leads: ${(info.leads || []).map(l => `${l.action}@${l.chunk} until ${Math.round(l.expires_ms / 1000)}s`).join(' | ') || 'none'}`,
    `spot bucket: ${info.spot_bucket.map(pct).join(' | ')}`,
    `self bucket: ${info.self_bucket.map(pct).join(' | ')}  need: ${info.need || '-'}`,
    `windows: ${info.windows.map(w => `${w.id} ${w.active}/${w.limit} (${w.spawned})`).join(' | ')}`,
    `drought: ${Object.entries(info.drought).map(([k, v]) => `${k} ${v}/${info.pity_after[k]}`).join(' ')}`,
    `stats: ${Object.entries(info.stats).map(([k, v]) => `${k} ${v}`).join(' ')}`,
    'not eligible:', ...info.why_not.slice(0, 10).map(r => `  ${r.id}: ${r.reasons.join('; ')}`),
    'recent screening:', ...info.screening.slice(-8).map(n => `  ${n.chunk} ${n.action || '-'}: ${n.result}`),
    'recent runtime rolls:', ...(info.recent_rolls || []).slice(-5).map(r =>
      `  ${r.chunk} ${r.region}: [${r.result.join(', ') || 'nothing'}] from ${r.bucket.map(b => `${b.id} ${b.base} x${b.region_percent / 100} =${b.final}`).join(' | ')}`),
  ].join('\n');
}
