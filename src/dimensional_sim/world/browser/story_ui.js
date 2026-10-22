/** The main story on screen: the objective line, the story card and the opening's darkness.
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

let darkLayer = null;
/** The opening's darkness (screen space): black everywhere but a soft light around the anchor
 * stone (`reveal.anchor`) and the body bound to it (`reveal.body`); `reveal.world` lifts it all. */
export function drawOpeningDark(ctx, reveal, width, height, anchorAt, bodyAt, scale = 1) {
  if (!reveal) return;
  const alpha = 1 - reveal.world;
  if (alpha <= 0) return;
  darkLayer ??= document.createElement('canvas');
  const layer = darkLayer;
  if (layer.width !== Math.ceil(width) || layer.height !== Math.ceil(height)) { layer.width = Math.ceil(width); layer.height = Math.ceil(height); }
  const g = layer.getContext('2d');
  g.globalCompositeOperation = 'source-over'; g.clearRect(0, 0, layer.width, layer.height);
  g.fillStyle = `rgba(2, 3, 4, ${alpha})`; g.fillRect(0, 0, width, height);
  g.globalCompositeOperation = 'destination-out';
  const hole = (at, r, strength) => {
    if (!at || strength <= 0) return;
    const grad = g.createRadialGradient(at.x, at.y, r * .1, at.x, at.y, r);
    grad.addColorStop(0, `rgba(0,0,0,${strength})`); grad.addColorStop(.55, `rgba(0,0,0,${strength * .75})`);
    grad.addColorStop(1, 'rgba(0,0,0,0)');
    g.fillStyle = grad; g.fillRect(at.x - r, at.y - r, r * 2, r * 2);
  };
  hole(anchorAt, 120 * scale, reveal.anchor);
  hole(bodyAt, 70 * scale, reveal.body * .9);
  ctx.save(); ctx.setTransform(1, 0, 0, 1, 0, 0);
  ctx.drawImage(layer, 0, 0, width * (ctx.canvas.width / width), height * (ctx.canvas.height / height));
  ctx.restore();
}
