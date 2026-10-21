/** The main story on screen: the objective line under the location, and the grey wall drawn
 * over every chunk past it while it stands closed (a faint haze at its line once it is open).
 * Story rules live in Python (autopilot/story.py); this only draws the snapshot's `story`. */
import {$} from './dom.js';

/** The HUD line: "Story · objective", with why it waits (or that it is close) underneath. */
export function storyLine(story) {
  const current = story?.current;
  if (!current) return story?.next ? {text: `Story · ${story.next}`, note: ''} : null;
  const note = current.here ? 'It is close. The avatar will go to it.'
    : current.waits.length ? `Waiting: ${current.waits.join('; ')}.`
    : current.rings[0] === current.rings[1] ? `Somewhere in ring ${current.rings[0]}.`
    : `Somewhere in rings ${current.rings[0]}-${current.rings[1]}.`;
  return {text: `Story · ${current.objective}`, note};
}

export function renderStory(ex) {
  const box = $('story-line');
  if (!box) return;
  const line = ex && !ex.anchor_space ? storyLine(ex.story) : null;
  box.hidden = !line;
  if (!line) return;
  const signature = line.text + '|' + line.note;
  if (box.dataset.signature === signature) return;
  box.dataset.signature = signature;
  box.replaceChildren();
  const b = document.createElement('b'); b.textContent = line.text;
  box.append(b);
  if (line.note) { const small = document.createElement('small'); small.textContent = line.note; box.append(small); }
}

/** Ring of chunk (cx, cy): Chebyshev distance from the anchor chunk, as in Python. */
export const ringOf = (cx, cy) => Math.max(Math.abs(cx), Math.abs(cy));

/** Sides of chunk (cx, cy) that touch the inside of a wall at `ring` ([] if not just outside it). */
export function wallEdges(cx, cy, ring) {
  if (ringOf(cx, cy) !== ring + 1) return [];
  return [['north', 0, -1], ['south', 0, 1], ['west', -1, 0], ['east', 1, 0]]
    .filter(([, dx, dy]) => ringOf(cx + dx, cy + dy) <= ring).map(([side]) => side);
}

const MIST_GLYPHS = ['~', ':', '.', '~', '`', ','];

/** Draw the wall over the visible chunks (world px; ctx already in camera space). */
export function drawWall(ctx, wall, chunks, tileW, tileH, clock, reducedMotion = false) {
  if (!wall) return;
  const drift = reducedMotion ? 0 : clock / 900;
  for (const chunk of chunks) {
    const past = ringOf(chunk.x, chunk.y) > wall.ring;
    if (!past) continue;
    const x0 = chunk.x * chunk.width * tileW, y0 = chunk.y * chunk.height * tileH;
    const w = chunk.width * tileW, h = chunk.height * tileH;
    if (!wall.open) {   // past a closed wall: the land lies under cold grey mist
      ctx.fillStyle = 'rgba(150, 156, 164, .58)';
      ctx.fillRect(x0, y0, w, h);
    }
    for (const side of wallEdges(chunk.x, chunk.y, wall.ring)) {
      const deep = (wall.open ? 2.5 : 5) * (side === 'north' || side === 'south' ? tileH : tileW);
      const [gx0, gy0, gx1, gy1] = side === 'north' ? [x0, y0, x0, y0 + deep] : side === 'south' ? [x0, y0 + h, x0, y0 + h - deep]
        : side === 'west' ? [x0, y0, x0 + deep, y0] : [x0 + w, y0, x0 + w - deep, y0];
      const grad = ctx.createLinearGradient(gx0, gy0, gx1, gy1);
      grad.addColorStop(0, wall.open ? 'rgba(205, 210, 218, .35)' : 'rgba(214, 218, 226, .85)');
      grad.addColorStop(1, 'rgba(190, 196, 204, 0)');
      ctx.fillStyle = grad;
      const [rx, ry, rw, rh] = side === 'north' ? [x0, y0, w, deep] : side === 'south' ? [x0, y0 + h - deep, w, deep]
        : side === 'west' ? [x0, y0, deep, h] : [x0 + w - deep, y0, deep, h];
      ctx.fillRect(rx, ry, rw, rh);
      if (wall.open) continue;
      // drifting mist written as text along the wall line, in keeping with the ASCII art
      ctx.save();
      ctx.font = `${Math.round(tileH * .7)}px ui-monospace, Consolas, monospace`;
      ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
      const along = side === 'north' || side === 'south' ? chunk.width : chunk.height;
      for (let i = 0; i < along; i++) for (let layer = 0; layer < 5; layer++) {
        const wave = Math.sin(drift + i * .7 + layer * 2.1);
        const off = (layer * 1.1 + .5 + wave * .45) * (side === 'north' || side === 'south' ? tileH : tileW) * .9;
        const px = side === 'north' || side === 'south' ? x0 + (i + .5) * tileW : side === 'west' ? x0 + off : x0 + w - off;
        const py = side === 'west' || side === 'east' ? y0 + (i + .5) * tileH : side === 'north' ? y0 + off : y0 + h - off;
        ctx.globalAlpha = .6 - layer * .11;
        ctx.fillStyle = '#eef1f6';
        ctx.fillText(MIST_GLYPHS[(i * 7 + layer * 3 + Math.floor(drift * 2)) % MIST_GLYPHS.length], px, py);
      }
      ctx.restore();
    }
  }
}

/** Story log entries newer than `lastSeq`, grouped into cards by the story place they came from:
 * [{encounter, lines}], plus the newest seq seen. Pure (tested). */
export function newStoryCards(log, lastSeq) {
  const cards = [];
  let seq = lastSeq;
  for (const entry of log || []) {
    if (entry.seq <= lastSeq) continue;
    seq = Math.max(seq, entry.seq);
    if (entry.type !== 'story') continue;
    const last = cards[cards.length - 1];
    if (last && last.encounter === entry.encounter) last.lines.push(entry.text);
    else cards.push({encounter: entry.encounter, lines: [entry.text]});
  }
  return {cards, seq};
}

const CARD_LINE_MS = 7000;

/** A finished story place tells its lore on a card, one line at a time (Next, or every 7 s),
 * instead of letting the lines scroll past in the four-line log. Lore seen before a reload is
 * not replayed; it stays on Journal > Story. */
export class StoryCard {
  constructor() {
    this.seq = null; this.queue = []; this.card = null; this.line = 0; this.shownAt = 0;
    $('story-card-next')?.addEventListener('click', () => this.next());
    $('story-card-close')?.addEventListener('click', () => { this.card = null; this.queue = []; this.render(); });
  }
  feed(ex, now) {
    if (!ex?.log) return;
    if (this.seq === null) { this.seq = Math.max(0, ...ex.log.map(e => e.seq)); return; }   // first snapshot: nothing new
    const {cards, seq} = newStoryCards(ex.log, this.seq);
    this.seq = seq;
    const names = new Map((ex.story?.done || []).map(step => [step.action, step.name]));
    for (const card of cards) this.queue.push({...card, title: names.get(card.encounter) || 'The story'});
    if (!this.card && this.queue.length) this.open(now);
    else if (this.card && now - this.shownAt >= CARD_LINE_MS) this.next(now);
  }
  open(now) { this.card = this.queue.shift(); this.line = 0; this.shownAt = now; this.render(); }
  next(now = performance.now()) {
    if (!this.card) return;
    if (this.line + 1 < this.card.lines.length) { this.line += 1; this.shownAt = now; this.render(); return; }
    this.card = null;
    if (this.queue.length) this.open(now); else this.render();
  }
  render() {
    const box = $('story-card');
    if (!box) return;
    box.hidden = !this.card;
    if (!this.card) return;
    $('story-card-title').textContent = this.card.title;
    $('story-card-text').textContent = this.card.lines[this.line];
    $('story-card-next').textContent = this.line + 1 < this.card.lines.length ? 'Next' : 'Close';
    $('story-card-pips').replaceChildren(...this.card.lines.map((_, i) =>
      Object.assign(document.createElement('i'), {className: i < this.line ? 'done' : i === this.line ? 'now' : ''})));
  }
}
