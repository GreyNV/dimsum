/** The full map (atlas): the minimap's picture of the world, for everything seen so far and not just
 * around the avatar. Opened by clicking the minimap (or N). Drag (or arrow keys) to scroll, wheel
 * (or + / -) to zoom, click to read a place. Every chunk is painted by minimap.paintChunk, the same
 * code as the minimap; tiles come once per chunk (world/atlas.py) and fog with every update. */
import {$, el} from './dom.js';
import {paintChunk, visibleAt} from './minimap.js';

/** Plain colours per kind of place (presentation only); unknown ids get a stable muted hue. */
const LOCATION_COLORS = {old_road: '#b09a62', deep_woods: '#4f8a55', bramble_thicket: '#a45b6c', still_glade: '#4f9aa0'};
const hue = id => [...(id || '?')].reduce((h, c) => (h * 31 + c.charCodeAt(0)) % 360, 7);
export const locationColor = id => LOCATION_COLORS[id] || `hsl(${hue(id)} 30% 50%)`;
const GROUND_NAMES = ['untouched', 'explored', 'picked over', 'hunted ground', 'dangerous'];

export function createAtlas({onToggle, getState}) {
  const root = $('atlas'), canvas = $('atlas-map'), info = $('atlas-info'), list = $('atlas-places');
  const g = canvas.getContext('2d');
  const tiles = new Map();     // `${world}:${chunk id}` -> glyph rows (they never change)
  const painted = new Map();   // same key -> {fog, canvas}: the chunk painted at one pixel per tile
  let data = null, world = null, open = false, fresh = true, places = false;
  let scale = 2, gx = 0, gy = 0, centered = false, picked = null, drag = null;

  function setOpen(value) {
    open = value; root.hidden = !open; centered = false; picked = null;
    onToggle(open);
    if (open) { canvas.focus(); resize(); }
  }
  function resize() {
    const r = canvas.getBoundingClientRect(), dpr = devicePixelRatio || 1;
    canvas.width = Math.max(1, Math.round(r.width * dpr)); canvas.height = Math.max(1, Math.round(r.height * dpr));
    draw();
  }
  const view = () => { const dpr = devicePixelRatio || 1; return {w: canvas.width / dpr, h: canvas.height / dpr, dpr}; };
  /** Global tile (x, y) to screen px. */
  const screen = (x, y) => { const v = view(); return [v.w / 2 + (x - gx) * scale, v.h / 2 + (y - gy) * scale]; };
  const W = () => data?.chunk_width || 32, H = () => data?.chunk_height || 16;
  const chunkAt = (px, py) => { const v = view();
    return [Math.floor(((px - v.w / 2) / scale + gx) / W()), Math.floor(((py - v.h / 2) / scale + gy) / H())]; };
  const centerOn = (cx, cy) => { gx = (cx + .5) * W(); gy = (cy + .5) * H(); };

  /** A chunk's picture at one pixel per tile, repainted only when its fog (or tiles) change. */
  function picture(c) {
    const key = `${world}:${c.id}`, rows = tiles.get(key), fog = (c.fog || []).join('') + (rows ? '' : '?')
      + (places ? `:${c.loc}` : '');
    let p = painted.get(key);
    if (!p || p.fog !== fog) {
      const off = p?.canvas || Object.assign(document.createElement('canvas'), {width: W(), height: H()});
      const o = off.getContext('2d'); o.clearRect(0, 0, W(), H());
      paintChunk(o, rows, c.fog, 0, 0, 1, W(), H());
      if (places && c.loc) {
        o.globalCompositeOperation = 'source-atop';
        o.globalAlpha = .35;
        o.fillStyle = locationColor(c.loc); o.fillRect(0, 0, W(), H());
        o.globalAlpha = 1;
        o.globalCompositeOperation = 'source-over';
      }
      p = {fog, canvas: off}; painted.set(key, p);
    }
    return p.canvas;
  }

  function draw() {
    if (!open) return;
    const v = view();
    g.setTransform(v.dpr, 0, 0, v.dpr, 0, 0);
    g.imageSmoothingEnabled = false;
    g.fillStyle = '#090d0d'; g.fillRect(0, 0, v.w, v.h);
    if (!data) { g.fillStyle = '#9a9478'; g.font = '12px ui-monospace,monospace'; g.fillText('Reading the map...', 16, 24); return; }
    const cw = W() * scale, ch = H() * scale;
    for (const c of data.chunks) {
      const [x, y] = screen(c.x * W(), c.y * H());
      if (x < -cw || y < -ch || x > v.w || y > v.h) continue;
      g.fillStyle = '#0e1414'; g.fillRect(x, y, cw, ch);
      g.drawImage(picture(c), x, y, cw, ch);
      if (c.ground) {   // worked ground: red hatching, denser each round
        g.save(); g.beginPath(); g.rect(x, y, cw, ch); g.clip();
        g.strokeStyle = 'rgba(255,110,80,.55)'; g.lineWidth = 1; g.beginPath();
        const step = Math.max(4, 16 / c.ground);
        for (let k = -ch; k < cw; k += step) { g.moveTo(x + k, y + ch); g.lineTo(x + k + ch, y); }
        g.stroke(); g.restore();
      }
      if (c.site && scale >= .75) {
        const loc = data.locations[c.site], r = Math.max(3, Math.min(7, scale * 2.5));
        g.fillStyle = '#0b0d0a'; g.fillRect(x + cw / 2 - r - 1, y + ch / 2 - r - 1, r * 2 + 2, r * 2 + 2);
        g.fillStyle = loc?.can_camp ? '#f0d58c' : '#c9b48a'; g.fillRect(x + cw / 2 - r, y + ch / 2 - r, r * 2, r * 2);
      }
      if (c.den) { g.fillStyle = '#ff6a50'; g.font = `bold ${Math.round(Math.max(10, ch * .45))}px Georgia`; g.fillText('!', x + 3, y + Math.max(10, ch * .45)); }
    }
    if (scale >= 1.5) {   // faint chunk grid: where one place stops and the next starts
      g.strokeStyle = 'rgba(0,0,0,.35)'; g.lineWidth = 1;
      for (const c of data.chunks) { const [x, y] = screen(c.x * W(), c.y * H()); g.strokeRect(x + .5, y + .5, cw, ch); }
    }
    // The frontier: rings the avatar is ready for (dashed rectangle around the anchor chunk).
    if (data.frontier != null) {
      const f = data.frontier, [ax, ay] = screen((data.anchor[0] - f) * W(), (data.anchor[1] - f) * H());
      g.setLineDash([5, 4]); g.strokeStyle = 'rgba(220,210,170,.55)'; g.lineWidth = 1;
      g.strokeRect(ax, ay, (2 * f + 1) * cw, (2 * f + 1) * ch); g.setLineDash([]);
    }
    if (data.camp) {
      g.strokeStyle = '#ff9a4a'; g.lineWidth = 2;
      for (const [x0, y0] of data.camp.cells) { const [x, y] = screen(x0 * W(), y0 * H()); g.strokeRect(x + 1, y + 1, cw - 2, ch - 2); }
    }
    // What the minimap shows around the avatar, drawn the same way: spots and enemies.
    const state = getState?.(), fog = state?.fog || {};
    const mark = (tx, ty, color, r) => { const [x, y] = screen(tx + .5, ty + .5);
      g.fillStyle = '#070a06'; g.fillRect(x - r - .6, y - r - .6, r * 2 + 1.2, r * 2 + 1.2); g.fillStyle = color; g.fillRect(x - r, y - r, r * 2, r * 2); };
    const r0 = Math.max(1.1, scale * .7);
    for (const spot of state?.spots || []) if (visibleAt(fog, spot.x, spot.y, W(), H()))
      mark(spot.x, spot.y, spot.story ? '#ffe27a' : '#e2c066', spot.story ? r0 * 1.6 : r0);
    for (const t of state?.targets || []) {
      if (t.hp <= 0) continue;
      if (t.hunting && t.hunting !== 'flee') mark(t.x, t.y, '#ff5a46', r0 * 1.3);
      else if (t.hunting === 'flee') mark(t.x, t.y, '#8a5a50', r0);
      else if (!t.hidden && visibleAt(fog, t.x, t.y, W(), H())) mark(t.x, t.y, '#e0604f', r0);
    }
    const diamond = (tx, ty, color, r = 5) => {
      const [x, y] = screen(tx + .5, ty + .5);
      g.fillStyle = '#070a06'; g.beginPath(); g.moveTo(x, y - r - 1); g.lineTo(x + r + 1, y); g.lineTo(x, y + r + 1); g.lineTo(x - r - 1, y); g.fill();
      g.fillStyle = color; g.beginPath(); g.moveTo(x, y - r); g.lineTo(x + r, y); g.lineTo(x, y + r); g.lineTo(x - r, y); g.fill();
    };
    diamond(...data.anchor_at, '#f1d38a');
    if (data.fire) diamond(data.fire.gx, data.fire.gy, data.fire.bed ? '#d9c6a0' : '#ff9a4a', 4);
    const [px, py] = screen(data.player_at[0] + .5, data.player_at[1] + .5);
    g.fillStyle = '#fff1bc'; g.fillRect(px - 2.5, py - 2.5, 5, 5);
    g.strokeStyle = '#ffe6a0'; g.lineWidth = 1; g.strokeRect(px - 6, py - 6, 12, 12);
    if (picked) {
      const [x, y] = screen(picked[0] * W(), picked[1] * H());
      g.strokeStyle = '#ffffff'; g.lineWidth = 1.5; g.strokeRect(x, y, cw, ch);
    }
  }

  function chunkText(x, y) {
    const c = data?.chunks.find(row => row.x === x && row.y === y);
    if (!c) return 'Unexplored.';
    const loc = data.locations[c.loc], site = c.site ? data.locations[c.site] : null;
    const place = p => !p ? '' : p.can_camp ? `${p.name}: ${p.grade_name.toLowerCase()}, camp can be made here`
      : `${p.name}: ${p.grade_name.toLowerCase()} ${p.done}/${p.next} to camp`;
    return [site && `${c.site_name}. ${place(site)}.`, loc && `${place(loc)}.`,
      `Ring ${c.ring}${c.ring > data.frontier ? ' (beyond what the avatar is ready for)' : ''}.`,
      c.ground ? `Ground: ${GROUND_NAMES[Math.min(c.ground, 4)]}${c.den ? ', a den' : ''}.` : '',
      data.camp?.cells.some(([a, b]) => a === x && b === y) ? `Your camp's area (${data.camp.name}).` : '']
      .filter(Boolean).join(' ');
  }

  function renderPlaces() {
    if (!data) return;
    const near = new Map();   // location -> nearest seen chunk to the avatar
    const [px, py] = data.player;
    for (const c of data.chunks) for (const id of [c.loc, c.site]) {
      if (!id) continue;
      const d = Math.max(Math.abs(c.x - px), Math.abs(c.y - py)), best = near.get(id);
      if (!best || d < best.d) near.set(id, {d, x: c.x, y: c.y});
    }
    const rows = [...near].sort((a, b) => a[1].d - b[1].d).map(([id, at]) => {
      const loc = data.locations[id];
      const button = el('button', 'atlas-place'); button.type = 'button';
      button.dataset.x = at.x; button.dataset.y = at.y;
      const sw = el('i'); sw.style.background = loc.kind === 'site' ? '#c9b48a' : locationColor(id);
      button.append(sw, el('b', '', loc.name),
        el('small', '', `${at.d ? `${at.d} away` : 'here'} · ${loc.can_camp ? (loc.camped ? 'camped' : 'camp ready') : `${loc.done}/${loc.next}`}`));
      return button;
    });
    const signature = rows.map(r => r.textContent).join('|');
    if (list.dataset.signature !== signature) { list.dataset.signature = signature; list.replaceChildren(...rows); }
  }

  function update(next, worldSeed) {
    world = worldSeed; data = next; fresh = false;
    for (const c of next.chunks) if (c.tiles) tiles.set(`${world}:${c.id}`, c.tiles);
    if (!centered) { [gx, gy] = next.player_at; centered = true; }
    if (!picked) info.textContent = chunkText(...data.player);
    renderPlaces(); draw();
  }

  canvas.addEventListener('pointerdown', e => { drag = {x: e.clientX, y: e.clientY, gx, gy, moved: false}; canvas.setPointerCapture(e.pointerId); });
  canvas.addEventListener('pointermove', e => {
    if (!drag) return;
    const dx = e.clientX - drag.x, dy = e.clientY - drag.y;
    if (Math.abs(dx) + Math.abs(dy) > 4) drag.moved = true;
    gx = drag.gx - dx / scale; gy = drag.gy - dy / scale; draw();
  });
  canvas.addEventListener('pointerup', e => {
    if (drag && !drag.moved) {
      const r = canvas.getBoundingClientRect();
      picked = chunkAt(e.clientX - r.left, e.clientY - r.top);
      info.textContent = chunkText(...picked); draw();
    }
    drag = null;
  });
  const zoom = f => { scale = Math.max(.5, Math.min(8, scale * f)); draw(); };
  canvas.addEventListener('wheel', e => { e.preventDefault(); zoom(e.deltaY < 0 ? 1.2 : 1 / 1.2); }, {passive: false});
  root.addEventListener('keydown', e => {
    const pan = {ArrowUp: [0, -1], KeyW: [0, -1], ArrowDown: [0, 1], KeyS: [0, 1], ArrowLeft: [-1, 0], KeyA: [-1, 0], ArrowRight: [1, 0], KeyD: [1, 0]}[e.code];
    if (pan) { gx += pan[0] * W() / 2; gy += pan[1] * H() / 2; draw(); }
    else if (e.code === 'Equal' || e.code === 'NumpadAdd') zoom(1.25);
    else if (e.code === 'Minus' || e.code === 'NumpadSubtract') zoom(1 / 1.25);
    else if (e.code === 'Escape' || e.code === 'KeyN') setOpen(false);
    else if (e.code === 'KeyC') { if (data) [gx, gy] = data.player_at; draw(); }
    else return;
    e.preventDefault(); e.stopPropagation();
  });
  list.addEventListener('click', e => {
    const b = e.target.closest('button[data-x]');
    if (!b) return;
    picked = [Number(b.dataset.x), Number(b.dataset.y)]; centerOn(...picked);
    info.textContent = chunkText(...picked); draw();
  });
  $('atlas-close').addEventListener('click', () => setOpen(false));
  $('atlas-center').addEventListener('click', () => { if (data) [gx, gy] = data.player_at; picked = null; draw(); });
  $('atlas-places-toggle').addEventListener('click', e => {
    places = !places; e.currentTarget.setAttribute('aria-pressed', String(places)); draw();
  });
  addEventListener('resize', () => open && resize());

  return {open: () => setOpen(true), close: () => setOpen(false), toggle: () => setOpen(!open),
          isOpen: () => open, update, redraw: draw,
          /** What to ask for: "reset" until this page has received tiles (the server then resends them). */
          request: () => (fresh ? 'reset' : true)};
}
