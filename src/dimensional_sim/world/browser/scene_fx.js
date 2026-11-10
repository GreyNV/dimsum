/** Screen-space and per-chunk effects for the world scene (cosmetic only). */
import {TILE_W, TILE_H} from './view.js';

/** A cached canvas washing each tile in its own region's colour (generator v3 sends
 * one tint code per tile). `picture` is the chunk's painted-picture cache entry. */
export function tintPicture(chunk, picture) {
  if (!picture) return null;
  if (picture.tint) return picture.tint;
  // Soft region borders: the per-tile wash is painted on a padded canvas (edge tiles clamped
  // outward, so neighbouring chunks blend alike), blurred, then cropped to the chunk.
  const W = chunk.width * TILE_W, H = chunk.height * TILE_H, P = TILE_W * 2;
  const wide = document.createElement('canvas');
  wide.width = W + P * 2; wide.height = H + P * 2;
  const c = wide.getContext('2d');
  const color = (x, y) => chunk.tint_legend?.[chunk.tint_rows[Math.max(0, Math.min(chunk.height - 1, y))][Math.max(0, Math.min(chunk.width - 1, x))]];
  for (let y = -2; y < chunk.height + 2; y++) for (let x = -3; x < chunk.width + 3; x++) {
    const col = color(x, y);
    if (col) { c.fillStyle = col; c.fillRect(P + x * TILE_W, P + y * TILE_H, TILE_W + .5, TILE_H + .5); }
  }
  const canvas = document.createElement('canvas');
  canvas.width = W; canvas.height = H;
  const out = canvas.getContext('2d');
  out.filter = `blur(${Math.round(TILE_W * .7)}px)`;
  out.drawImage(wide, -P, -P);
  picture.tint = canvas;
  return canvas;
}

/** Prologue: black while the eyes are closed, then two lids part from the middle. */
export function drawEyelids(ctx, opening, width, height, reducedMotion) {
  if (!opening.dark) return;
  const lid = (1 - (reducedMotion ? opening.eyes : 1 - (1 - opening.eyes) ** 2)) * height / 2;
  ctx.fillStyle = '#000';
  if (opening.eyes <= 0) { ctx.fillRect(0, 0, width, height); return; }
  ctx.fillRect(0, 0, width, lid); ctx.fillRect(0, height - lid, width, lid);
  for (const [y0, y1] of [[lid, lid + 40], [height - lid, height - lid - 40]]) {
    const edge = ctx.createLinearGradient(0, y0, 0, y1);
    edge.addColorStop(0, '#000'); edge.addColorStop(1, '#0000');
    ctx.fillStyle = edge; ctx.fillRect(0, Math.min(y0, y1), width, 40);
  }
}

/** A soft dark vignette around the screen edges. */
/* ---------- ambience: ash on the air and mist on the ground (cosmetic) ----------
 * Pure in the world position and the clock, so it never flickers between frames: motes are
 * fixed per 96 px world cell and drift on a slow fall; mist is a few broad soft bands that crawl
 * across the ground. Both are drawn in world px under the night layer. */
const MOTE_CELL = 96;
export function motes(x0, y0, x1, y1, clock) {
  const out = [];
  for (let cy = Math.floor(y0 / MOTE_CELL) - 1; cy <= Math.floor(y1 / MOTE_CELL); cy++)
    for (let cx = Math.floor(x0 / MOTE_CELL); cx <= Math.floor(x1 / MOTE_CELL); cx++) {
      let h = Math.imul(cx * 374761393 + cy * 668265263, 1274126177) >>> 0;
      for (let k = 0; k < 2; k++) {
        h = Math.imul(h ^ (h >>> 13), 1103515245) >>> 0;
        const fx = (h & 1023) / 1024, fy = ((h >>> 10) & 1023) / 1024, sp = .006 + ((h >>> 20) & 15) / 1600;
        const y = (cy + fy) * MOTE_CELL + (clock * sp) % (MOTE_CELL * 2);
        const x = (cx + fx) * MOTE_CELL + Math.sin(clock / 2400 + fx * 9) * 6;
        out.push({x, y, size: k ? .9 : 1.3, alpha: .18 + ((h >>> 24) & 7) / 40});
      }
    }
  return out;
}
export function drawAmbience(ctx, box, clock, {night = 0, reducedMotion = false} = {}) {
  const [x0, y0, x1, y1] = box, t = reducedMotion ? 0 : clock;
  ctx.save();
  for (let i = 0; i < 4; i++) {   // ground mist: wide pale bands, thicker at night
    const y = y0 + ((i * 211 + t * .004) % (y1 - y0 + 240)) - 120, h = 70 + i * 18;
    const g = ctx.createLinearGradient(0, y - h, 0, y + h);
    const a = .045 + night * .05;
    g.addColorStop(0, 'rgba(170,186,196,0)'); g.addColorStop(.5, `rgba(170,186,196,${a})`); g.addColorStop(1, 'rgba(170,186,196,0)');
    ctx.fillStyle = g; ctx.fillRect(x0, y - h, x1 - x0, h * 2);
  }
  for (const m of motes(x0, y0, x1, y1, t)) {   // ash drifting down through the cold light
    ctx.globalAlpha = m.alpha; ctx.fillStyle = '#c9d2d8';
    ctx.fillRect(m.x, m.y, m.size, m.size);
  }
  ctx.restore();
}

export function drawVignette(ctx, width, height) {
  const shade = ctx.createRadialGradient(width/2, height/2, Math.min(width, height)*.24, width/2, height/2, Math.max(width, height)*.68);
  shade.addColorStop(0, '#00000000'); shade.addColorStop(.55, '#05080c38'); shade.addColorStop(1, '#03060acc');   // cold and deep
  ctx.fillStyle = shade; ctx.fillRect(0, 0, width, height);
}

/** Where (screen px) an off-screen point's marker sits: on a rectangle inset from the screen
 * edges, along the line from the screen centre toward the point. Null when the point is on screen.
 * Pure (tested). `inset` = {top, right, bottom, left}. */
export function edgePoint(sx, sy, width, height, inset) {
  const left = inset.left, right = width - inset.right, top = inset.top, bottom = height - inset.bottom;
  if (sx >= left && sx <= right && sy >= top && sy <= bottom) return null;
  const cx = (left + right) / 2, cy = (top + bottom) / 2, dx = sx - cx, dy = sy - cy;
  const t = Math.min(dx ? (dx > 0 ? right - cx : left - cx) / dx : Infinity,
    dy ? (dy > 0 ? bottom - cy : top - cy) / dy : Infinity);
  return {x: cx + dx * t, y: cy + dy * t, angle: Math.atan2(dy, dx)};
}

/** An arrow at the screen edge pointing to something off screen, with a short label. */
export function drawEdgeMarker(ctx, at, label, color = '#f1d38a') {
  ctx.save();
  ctx.translate(Math.round(at.x), Math.round(at.y));
  ctx.save(); ctx.rotate(at.angle);
  ctx.fillStyle = '#070a06'; ctx.beginPath(); ctx.moveTo(15, 0); ctx.lineTo(-3, -10); ctx.lineTo(-3, 10); ctx.closePath(); ctx.fill();
  ctx.fillStyle = color; ctx.beginPath(); ctx.moveTo(12, 0); ctx.lineTo(-1, -7); ctx.lineTo(-1, 7); ctx.closePath(); ctx.fill();
  ctx.restore();
  ctx.font = '600 11px ui-monospace, Consolas, monospace';
  const w = ctx.measureText(label).width + 10;
  const lx = Math.cos(at.angle) > .3 ? -w - 14 : Math.cos(at.angle) < -.3 ? 14 : -w / 2;
  const ly = Math.sin(at.angle) > .3 ? -28 : Math.sin(at.angle) < -.3 ? 14 : -8;
  ctx.fillStyle = '#0d120bdd'; ctx.fillRect(lx, ly, w, 16);
  ctx.strokeStyle = color; ctx.lineWidth = 1; ctx.strokeRect(lx + .5, ly + .5, w - 1, 15);
  ctx.fillStyle = color; ctx.textBaseline = 'middle'; ctx.textAlign = 'left'; ctx.fillText(label, lx + 5, ly + 8.5);
  ctx.restore();
}

/* ---------- possession: the god inside the avatar (cosmetic) ---------- */
const POSSESS_GOLD = '#ffd77a', POSSESS_CORE = '#fff4cf';

/** Pure (tested): how strongly the possession glow shows, 0..1. It flares for the first
 * `flareMs`, holds, then fades out over the last 5 seconds so the end never surprises. */
export function possessionGlow(possession, sinceMs = Infinity, flareMs = 600) {
  if (!possession?.active) return 0;
  const left = Math.max(0, possession.remaining_ms || 0);
  const tail = Math.min(1, left / 5000);
  const flare = sinceMs < flareMs ? 1 + (1 - sinceMs / flareMs) * .6 : 1;
  return Math.min(1.6, (.55 + .45 * tail) * flare);
}

/** Ground layer under a possessed avatar: a slowly turning ring of marks and a warm pool of
 * light. `x`, `y` are the avatar's drawing anchor (tile centre); feet sit at y + foot. */
export function drawPossessionGround(ctx, x, y, {clock = 0, glow = 1, foot = 12, reducedMotion = false} = {}) {
  if (glow <= 0) return;
  const fy = y + foot, turn = reducedMotion ? 0 : clock / 1400;
  ctx.save();
  const pool = ctx.createRadialGradient(x, fy, 2, x, fy, 34);
  pool.addColorStop(0, `rgba(255,224,140,${.38 * Math.min(1, glow)})`); pool.addColorStop(1, 'rgba(255,224,140,0)');
  ctx.fillStyle = pool; ctx.beginPath(); ctx.ellipse(x, fy, 34, 14, 0, 0, Math.PI * 2); ctx.fill();
  ctx.strokeStyle = POSSESS_GOLD; ctx.globalAlpha = .55 * Math.min(1, glow); ctx.lineWidth = 1;
  ctx.beginPath(); ctx.ellipse(x, fy, 20, 8, 0, 0, Math.PI * 2); ctx.stroke();
  for (let i = 0; i < 8; i++) {   // eight marks on the ring, like the old carvings
    const a = turn + i * Math.PI / 4, mx = x + Math.cos(a) * 20, my = fy + Math.sin(a) * 8;
    ctx.fillStyle = i % 2 ? POSSESS_GOLD : POSSESS_CORE;
    ctx.fillRect(Math.round(mx) - 1, Math.round(my) - 1, 2, 2);
  }
  ctx.restore();
}

/** Over the avatar: a soft halo at the chest, motes rising off the shoulders, and an
 * expanding ring in the first moments (`sinceMs`). */
export function drawPossessionAura(ctx, x, y, {clock = 0, glow = 1, sinceMs = Infinity, lift = 14, reducedMotion = false} = {}) {
  if (glow <= 0) return;
  const cy = y - lift / 2;
  ctx.save();
  ctx.globalCompositeOperation = 'lighter';
  const halo = ctx.createRadialGradient(x, cy, 1, x, cy, 22);
  halo.addColorStop(0, `rgba(255,236,170,${.30 * Math.min(1.4, glow)})`); halo.addColorStop(1, 'rgba(255,236,170,0)');
  ctx.fillStyle = halo; ctx.fillRect(x - 24, cy - 24, 48, 48);
  if (!reducedMotion) for (let i = 0; i < 7; i++) {
    const t = ((clock / 1300) + i / 7) % 1, wobble = Math.sin(clock / 260 + i * 2.1) * 3;
    const mx = x + (i - 3) * 2.6 + wobble, my = y + 6 - t * 30;
    ctx.globalAlpha = (1 - t) * .9 * Math.min(1, glow);
    ctx.fillStyle = i % 3 ? POSSESS_GOLD : POSSESS_CORE;
    ctx.fillRect(Math.round(mx), Math.round(my), 1 + (i % 2), 1 + (i % 2));
  }
  if (sinceMs < 700) {   // the moment of taking hold
    const k = sinceMs / 700;
    ctx.globalAlpha = (1 - k) * .9; ctx.strokeStyle = POSSESS_CORE; ctx.lineWidth = 2 - k;
    ctx.beginPath(); ctx.arc(x, cy, 6 + k * 40, 0, Math.PI * 2); ctx.stroke();
  }
  ctx.restore();
}

/** Screen edges warm to gold while possessed: the player is inside the world now. */
export function drawPossessionTint(ctx, width, height, glow) {
  if (glow <= 0) return;
  const edge = ctx.createRadialGradient(width / 2, height / 2, Math.min(width, height) * .28,
    width / 2, height / 2, Math.max(width, height) * .72);
  edge.addColorStop(0, 'rgba(255,210,120,0)'); edge.addColorStop(1, `rgba(255,200,110,${.16 * Math.min(1.4, glow)})`);
  ctx.save(); ctx.globalCompositeOperation = 'lighter'; ctx.fillStyle = edge; ctx.fillRect(0, 0, width, height); ctx.restore();
}

/* ---------- day and night (cosmetic; the server owns the clock) ---------- */
let nightCanvas = null;
/** Pure (tested): how dark the scene is drawn, 0..1, from the frame clock's darkness (0..1000). */
export const nightAlpha = clock => clock ? Math.max(0, Math.min(1, (clock.darkness || 0) / 1000)) * .78 : 0;

/** Night over the scene: a deep blue dark with holes of warm light - `lights` are
 * [{x, y, r, warm}] in screen px (avatar, anchor camp, campfire). Drawn after the world,
 * before the HUD. Firelight flickers a little unless motion is reduced. */
export function drawNight(ctx, width, height, alpha, lights = [], {clock = 0, reducedMotion = false} = {}) {
  if (alpha <= 0) return;
  if (!nightCanvas) nightCanvas = document.createElement('canvas');
  if (nightCanvas.width !== Math.ceil(width) || nightCanvas.height !== Math.ceil(height)) {
    nightCanvas.width = Math.ceil(width); nightCanvas.height = Math.ceil(height);
  }
  const n = nightCanvas.getContext('2d');
  n.globalCompositeOperation = 'source-over';
  n.clearRect(0, 0, width, height);
  n.fillStyle = `rgba(6,10,28,${alpha})`; n.fillRect(0, 0, width, height);
  n.globalCompositeOperation = 'destination-out';
  for (const l of lights) {
    const flicker = l.warm && !reducedMotion ? 1 + Math.sin(clock / 90 + l.x) * .03 + Math.sin(clock / 37) * .02 : 1;
    const r = l.r * flicker, g = n.createRadialGradient(l.x, l.y, r * .15, l.x, l.y, r);
    g.addColorStop(0, 'rgba(0,0,0,1)'); g.addColorStop(.55, 'rgba(0,0,0,.75)'); g.addColorStop(1, 'rgba(0,0,0,0)');
    n.fillStyle = g; n.beginPath(); n.arc(l.x, l.y, r, 0, Math.PI * 2); n.fill();
  }
  ctx.save(); ctx.setTransform(1, 0, 0, 1, 0, 0);
  const scale = ctx.canvas.width / width;
  ctx.drawImage(nightCanvas, 0, 0, width * scale, height * scale);
  ctx.restore();
  ctx.save(); ctx.globalCompositeOperation = 'lighter';   // a warm glow where the fires burn
  for (const l of lights) if (l.warm) {
    const g = ctx.createRadialGradient(l.x, l.y, 2, l.x, l.y, l.r * .7);
    g.addColorStop(0, `rgba(255,150,60,${.16 * alpha})`); g.addColorStop(1, 'rgba(255,150,60,0)');
    ctx.fillStyle = g; ctx.fillRect(l.x - l.r, l.y - l.r, l.r * 2, l.r * 2);
  }
  ctx.restore();
}


/* ---------- the colour of the day (cosmetic) ----------
 * Keyframes over the day (fraction of DAY_MS, dawn = 0), muted for the cold atmosphere
 * (docs/design/ATMOSPHERE.md): an ashen rose dawn that pales into grey daylight, a thin amber
 * afternoon, a dull ember sunset, a slate-violet dusk, a deep blue night and a grey hour before
 * dawn. `tint` is laid over the scene in soft-light (it colours without blacking out), `dim`
 * darkens a little more (morning haze, late dusk), `sun` is a low glow from the horizon. */
const DAY_KEYS = [
  [0.000, [206, 150, 156], .32, .16, .30],
  [0.045, [210, 164, 140], .26, .12, .34],
  [0.100, [204, 184, 160], .17, .07, .22],
  [0.190, [196, 204, 208], .07, .02, .06],
  [0.260, [255, 255, 255], 0, 0, 0],
  [0.500, [255, 255, 255], 0, 0, 0],
  [0.560, [214, 196, 160], .07, .01, .05],
  [0.600, [212, 158, 110], .18, .04, .26],
  [0.635, [190, 112, 96], .24, .08, .32],
  [0.690, [96, 92, 150], .24, .12, .08],
  [0.780, [62, 84, 150], .14, .02, 0],
  [0.940, [82, 88, 140], .14, .02, 0],
  [0.975, [150, 118, 140], .22, .12, .14],
  [1.000, [206, 150, 156], .32, .16, .30],
];

/** Pure (tested): {r, g, b, tint, dim, sun, east} for a frame clock ({time_ms, day_ms}). */
export function dayGrade(clock) {
  if (!clock || !clock.day_ms) return {r: 255, g: 255, b: 255, tint: 0, dim: 0, sun: 0, east: true};
  const f = ((clock.time_ms % clock.day_ms) + clock.day_ms) % clock.day_ms / clock.day_ms;
  let i = 0;
  while (i < DAY_KEYS.length - 2 && DAY_KEYS[i + 1][0] <= f) i++;
  const [f0, c0, t0, d0, s0] = DAY_KEYS[i], [f1, c1, t1, d1, s1] = DAY_KEYS[i + 1];
  const k = f1 > f0 ? (f - f0) / (f1 - f0) : 0, e = k * k * (3 - 2 * k);   // smoothstep: no visible seams
  const mix = (a, b) => a + (b - a) * e;
  return {r: Math.round(mix(c0[0], c1[0])), g: Math.round(mix(c0[1], c1[1])), b: Math.round(mix(c0[2], c1[2])),
    tint: mix(t0, t1), dim: mix(d0, d1), sun: mix(s0, s1), east: f < .4};
}

/** Lay the day's colour over the scene (screen px, after the world, before night and the HUD). */
export function drawDayGrade(ctx, width, height, grade) {
  if (!grade || (grade.tint <= .004 && grade.dim <= .004 && grade.sun <= .004)) return;
  ctx.save(); ctx.setTransform(1, 0, 0, 1, 0, 0);
  const scale = ctx.canvas.width / width, w = width * scale, h = height * scale;
  const rgb = `${grade.r},${grade.g},${grade.b}`;
  if (grade.tint > .004) {
    ctx.globalCompositeOperation = 'soft-light';
    ctx.fillStyle = `rgba(${rgb},${Math.min(1, grade.tint * 1.7)})`; ctx.fillRect(0, 0, w, h);
  }
  if (grade.dim > .004) {
    ctx.globalCompositeOperation = 'source-over';
    ctx.fillStyle = `rgba(14,12,26,${grade.dim})`; ctx.fillRect(0, 0, w, h);
  }
  if (grade.sun > .004) {   // the low sun: a broad warm wash from the horizon side
    ctx.globalCompositeOperation = 'lighter';
    const sx = grade.east ? w * 1.05 : -w * .05, sy = h * .15;
    const g = ctx.createRadialGradient(sx, sy, 0, sx, sy, Math.max(w, h) * .95);
    g.addColorStop(0, `rgba(${rgb},${.20 * grade.sun})`); g.addColorStop(.5, `rgba(${rgb},${.07 * grade.sun})`);
    g.addColorStop(1, `rgba(${rgb},0)`);
    ctx.fillStyle = g; ctx.fillRect(0, 0, w, h);
  }
  ctx.restore();
}
