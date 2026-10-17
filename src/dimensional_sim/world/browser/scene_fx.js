/** Screen-space and per-chunk effects for the world scene (cosmetic only). */
import {TILE_W, TILE_H} from './view.js';

/** A cached canvas washing each tile in its own region's colour (generator v3 sends
 * one tint code per tile). `picture` is the chunk's painted-picture cache entry. */
export function tintPicture(chunk, picture) {
  if (!picture) return null;
  if (picture.tint) return picture.tint;
  const canvas = document.createElement('canvas');
  canvas.width = chunk.width * TILE_W; canvas.height = chunk.height * TILE_H;
  const c = canvas.getContext('2d');
  chunk.tint_rows.forEach((row, y) => {
    let start = 0;
    for (let x = 1; x <= row.length; x++) if (x === row.length || row[x] !== row[start]) {
      const color = chunk.tint_legend?.[row[start]];
      if (color) { c.fillStyle = color; c.fillRect(start * TILE_W, y * TILE_H, (x - start) * TILE_W, TILE_H); }
      start = x;
    }
  });
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
export function drawVignette(ctx, width, height) {
  const shade = ctx.createRadialGradient(width/2, height/2, Math.min(width, height)*.24, width/2, height/2, Math.max(width, height)*.68);
  shade.addColorStop(0, '#00000000'); shade.addColorStop(1, '#040804a0');
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

