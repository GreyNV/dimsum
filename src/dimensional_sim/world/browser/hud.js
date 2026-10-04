/** Expedition HUD: vitals, attributes (regular + dimensional), inventory, log and
 * life reports. Reads snapshot fields only; never decides game rules. */
export const ATTRIBUTES = Object.freeze([
  ['strength', 'Strength', 'STR'], ['endurance', 'Endurance', 'END'], ['agility', 'Agility', 'AGI'],
  ['intelligence', 'Intelligence', 'INT'], ['perception', 'Perception', 'PER'], ['willpower', 'Willpower', 'WIL']]);
export const LABEL = Object.freeze(Object.fromEntries(ATTRIBUTES.map(([id, name]) => [id, name])));
const VERB = Object.freeze({forage: 'Foraging', gather: 'Gathering', observe: 'Studying', climb: 'Climbing',
  drink: 'Drinking at', meditate: 'Meditating by', study: 'Deciphering'});
export const ITEM_COLOR = Object.freeze({wild_berries: '#e0505e', bird_egg: '#efe6cf', boar_meat: '#d9776a',
  stick: '#c39a62', bramble_thorn: '#a9c97a', boar_hide: '#a6845d'});

/** One-line description of what the auto-pilot is doing. */
export function activityText(state, paused = false) {
  if (paused) return 'Paused - the forest can wait';
  const ex = state.expedition;
  if (!ex) return null;
  if (ex.anchor_space) return ex.anchor_space.waiting ? 'The anchor waits for your choice'
    : `A new life begins in ${Math.ceil(ex.anchor_space.remaining_ms / 1000)}s`;
  if (ex.control === 'manual') return 'You have taken control';
  if (ex.prologue) {
    const p = ex.prologue;
    if (p.stage === 'listen') return 'Listening to the old man';
    return `${p.stage === 'awaken' ? 'Wake up' : 'Stand up'} - ${Math.floor(p.progress / 10)}%`;
  }
  if (ex.activity) {
    const pct = Math.floor(ex.activity.progress / 10);
    if (ex.activity.kind === 'rest') return `Resting at the anchor camp - ${pct}%`;
    if (ex.activity.kind === 'pray') return `Praying to the gods - ${pct}%`;
    if (ex.activity.kind === 'think') return `Thinking about the road - ${pct}%`;
    if (ex.activity.kind === 'contemplate') return `Contemplating the forest - ${pct}%`;
    return `${VERB[ex.activity.kind] || 'Investigating'} ${ex.activity.name.toLowerCase()} - ${pct}%`;
  }
  if (ex.mode === 'home') return 'Badly hurt - heading back to the anchor camp';
  if (ex.mode === 'fight') return 'Fists up - punching a bramble boar';
  if (ex.mode === 'travel' && ex.goal) {
    const spot = state.spots?.find(s => s.x === ex.goal.x && s.y === ex.goal.y);
    if (spot) return `Heading for ${spot.name.toLowerCase()}`;
  }
  return ex.depth > 0 ? `Exploring the dark forest - ring ${ex.depth}` : 'Exploring the dark forest';
}

/** Floating texts for new log entries: XP, items gained, food eaten. */
export function rewardTexts(entry) {
  const texts = [];
  if (entry.type === 'encounter' && entry.xp) texts.push({text: `+${entry.xp} ${LABEL[entry.attribute]}`, color: '#bfe39a'});
  if (entry.blessing) texts.push({text: `+${entry.blessing} blessing`, color: '#ffe9a8'});
  if (entry.type === 'blessing') texts.push({text: 'Prayer completed', color: '#fff3c4'});
  for (const [item, count] of entry.items || []) {
    if (count > 0) texts.push({text: `+${count} ${item.replaceAll('_', ' ')}`, color: ITEM_COLOR[item] || '#e7d7b0'});
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
    const signature = JSON.stringify([ex.attributes, ex.log.map(e => e.seq), ex.inventory, ex.skills, ex.control]);
    if (signature === this.signature) return;
    this.signature = signature;
    this.renderAttributes(ex);
    this.renderInventory(ex);
    this.renderLog(ex);
    this.doc.body.classList.toggle('manual-unlocked', ex.skills.includes('take_control'));
  }
  updateVitals(ex) {
    const v = ex.vitals, cd = v.food_cooldown_ms;
    const signature = [v.health, v.hunger, Math.ceil(cd / 250), ex.life, ex.depth, ex.best_depth, v.blessing].join();
    if (signature === this.vitalsSignature) return;
    this.vitalsSignature = signature;
    for (const [name, value] of [['health', v.health], ['hunger', v.hunger]]) {
      const pct = Math.max(0, Math.min(100, value / v.max * 100));
      this.$(`${name}-bar`).style.width = pct.toFixed(1) + '%';
      this.$(`${name}-value`).textContent = String(Math.ceil(pct));
      this.$(`${name}-bar`).closest('.vital').classList.toggle('low', pct < 30);
    }
    const ring = this.$('food-ring');
    ring.style.strokeDashoffset = String(50.27 * (cd / v.food_cooldown_total_ms));
    this.$('food-label').textContent = cd ? `Food in ${Math.ceil(cd / 1000)}s` : 'Food ready';
    this.updateFoodCooldown(ex);
    this.$('life').textContent = `Life ${ex.life}`;
    this.$('depth').textContent = `Ring ${ex.depth} - best ${ex.best_depth}`;
    const blessing = this.$('blessing');
    if (blessing) blessing.textContent = `✦ ${v.blessing ?? 0} blessing`;
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
  updateFoodCooldown(ex) {
    const remaining = ex.vitals.food_cooldown_ms;
    const total = ex.vitals.food_cooldown_total_ms || 1;
    const ready = Math.max(0, Math.min(1, 1 - remaining / total));
    for (const slot of this.$('inventory').querySelectorAll('li.food')) {
      slot.style.setProperty('--food-brightness', (.35 + ready * .65).toFixed(3));
      slot.style.setProperty('--food-fill', (ready * 100).toFixed(1) + '%');
      slot.classList.toggle('on-cooldown', remaining > 0);
      slot.setAttribute('aria-label', `${slot.dataset.name}, ${slot.dataset.count}. ${remaining ? `Food ready in ${Math.ceil(remaining / 1000)} seconds` : 'Food ready'}`);
    }
  }
  renderAttributes(ex) {
    this.$('attributes').replaceChildren(...ATTRIBUTES.map(([id, name, short]) => {
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
    this.$('inventory-count').textContent = `${rows.length}/${ex.inventory_slots}`;
    const slots = [];
    for (let i = 0; i < ex.inventory_slots; i++) {
      const row = rows[i], li = this.doc.createElement('li');
      if (!row) { li.className = 'empty'; slots.push(li); continue; }
      li.className = row.kind;
      li.title = `${row.name} x${row.count}` + (row.food ? ` - restores ${row.food} hunger (eaten automatically)` : ' - material');
      li.dataset.name = row.name;
      li.dataset.count = String(row.count);
      li.textContent = row.glyph;
      li.style.color = ITEM_COLOR[row.id] || '#e7d7b0';
      const count = this.doc.createElement('small'); count.textContent = String(row.count);
      li.append(count);
      slots.push(li);
    }
    this.$('inventory').replaceChildren(...slots);
    this.updateFoodCooldown(ex);
  }
  renderLog(ex) {
    const entries = [...ex.log].reverse().slice(0, 4);
    this.$('log').replaceChildren(...(entries.length ? entries.map(entry => {
      const li = this.doc.createElement('li');
      const head = this.doc.createElement('b');
      head.textContent = entry.type === 'encounter'
        ? `+${entry.xp} ${LABEL[entry.attribute]}` + (entry.dim_xp ? ` (◆+${entry.dim_xp})` : '')
          + (entry.blessing ? ` ✦+${entry.blessing}` : '')
        : {eat: 'Ate', rest: 'Rested', life: 'Anchor', blessing: 'Prayer', lore: 'The road', trade: 'Offered', ambush: 'Ambush'}[entry.type];
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
