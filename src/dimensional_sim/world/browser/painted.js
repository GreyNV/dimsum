/** Painted actors: the avatar, the enemies, the old man, the anchor stone and the campfire as
 * shaded vector illustrations instead of coarse cell sprites.
 *
 * Each part is a closed shape filled with its base colour, then lit inside its own outline -
 * a warm sheen toward the upper left, cool shade toward the lower right - and edged with a
 * thin dark line; when all parts are down, the whole figure gets one soft outline, so it
 * reads cleanly against busy ground. Poses are painted once at the render resolution and
 * cached (`paintedCanvas`); a hit flash is the same canvas washed pale.
 *
 * Presentation only and deterministic. Without a DOM (node tests) every builder returns null
 * and callers keep their cell-sprite fallback.
 */
import {asciify} from './ascii_art.js';
const OUTLINE = '#070a06';
let RES = 2;
const cache = new Map();
export function paintedResolution(res) { if (res !== RES) { RES = res; cache.clear(); } }
export const paintedCount = () => cache.size;
const PAD = 2;

/** A cached canvas of logical size (w + 2*PAD) x (h + 2*PAD); `draw(ctx)` paints in the w x h
 * frame. `outline` adds the soft silhouette edge. */
export function paintedCanvas(key, w, h, draw, {outline = true} = {}) {
  if (cache.has(key)) return cache.get(key);
  if (typeof document === 'undefined' || !document.createElement) return null;
  const W = w + PAD * 2, H = h + PAD * 2, k = RES;
  const art = document.createElement('canvas');
  art.width = Math.ceil(W * k); art.height = Math.ceil(H * k);
  const a = art.getContext('2d');
  a.scale(k, k); a.translate(PAD, PAD); a.lineJoin = 'round'; a.lineCap = 'round';
  // Soft layers stay out of the silhouette: `under` (ground shadows) is painted beneath the
  // outlined art, `after` (glows) above it. Kit functions push to them (see onLayer).
  a.under = []; a.after = [];
  draw(a);
  // Shown as text, never as the picture: the ASCII shader reads it (ascii_art.js).
  const text = asciify(art, w, h, k, {pad: PAD, lift: 1.45, whiten: .45});
  let out = text;
  if (a.under.length || a.after.length) {
    out = document.createElement('canvas');
    out.width = art.width; out.height = art.height;
    const o = out.getContext('2d');
    const layer = list => { if (!list.length) return; o.save(); o.scale(k, k); o.translate(PAD, PAD); o.lineJoin = 'round'; o.lineCap = 'round'; for (const f of list) f(o); o.restore(); };
    layer(a.under);
    o.drawImage(text, 0, 0);
    layer(a.after);
  }
  out.lw = W; out.lh = H; out.pad = PAD;
  cache.set(key, out);
  return out;
}
/** The same canvas washed pale (a hit flash), cached. */
export function flashCanvas(source, key) {
  const id = `${key}|flash`;
  if (cache.has(id)) return cache.get(id);
  const c = document.createElement('canvas'); c.width = source.width; c.height = source.height;
  const g = c.getContext('2d');
  g.drawImage(source, 0, 0);
  g.globalCompositeOperation = 'source-atop'; g.fillStyle = 'rgba(255, 244, 220, .82)'; g.fillRect(0, 0, c.width, c.height);
  c.lw = source.lw; c.lh = source.lh; c.pad = source.pad;
  cache.set(id, c);
  return c;
}
/** Draw a painted canvas with its frame's top-left at (x, y), smoothly resampled. */
export function drawPainted(ctx, canvas, x, y, alpha = 1) {
  const smoothing = ctx.imageSmoothingEnabled;
  ctx.imageSmoothingEnabled = true; ctx.imageSmoothingQuality = 'low';
  ctx.globalAlpha = alpha;
  ctx.drawImage(canvas, x - canvas.pad, y - canvas.pad, canvas.lw, canvas.lh);
  ctx.globalAlpha = 1;
  ctx.imageSmoothingEnabled = smoothing;
}

// --- the painting kit ----------------------------------------------------------
/** Run `draw(ctx)` on a soft layer of the canvas being painted ('under' or 'after' the
 * outlined art), or right away when drawing live. */
export function onLayer(c, which, draw) { if (Array.isArray(c[which])) c[which].push(draw); else draw(c); }
/** Shapes carry their path and bounding box: E(llipse), R(ounded rect), P(olygon, optionally
 * smoothed through its points), C(apsule between two points). */
export const E = (cx, cy, rx, ry, rot = 0) => ({box: [cx - rx, cy - ry, rx * 2, ry * 2],
  path: c => c.ellipse(cx, cy, Math.max(.01, rx), Math.max(.01, ry), rot, 0, Math.PI * 2)});
export const R = (x, y, w, h, r = 1) => ({box: [x, y, w, h], path: c => {
  const q = Math.min(r, w / 2, h / 2);
  c.moveTo(x + q, y); c.arcTo(x + w, y, x + w, y + h, q); c.arcTo(x + w, y + h, x, y + h, q);
  c.arcTo(x, y + h, x, y, q); c.arcTo(x, y, x + w, y, q); c.closePath(); }});
export function P(points, smooth = false) {
  const xs = points.map(p => p[0]), ys = points.map(p => p[1]);
  const box = [Math.min(...xs), Math.min(...ys), Math.max(...xs) - Math.min(...xs), Math.max(...ys) - Math.min(...ys)];
  return {box, path: c => {
    if (!smooth) { c.moveTo(...points[0]); for (const p of points.slice(1)) c.lineTo(...p); c.closePath(); return; }
    const n = points.length, mid = i => [(points[i][0] + points[(i + 1) % n][0]) / 2, (points[i][1] + points[(i + 1) % n][1]) / 2];
    c.moveTo(...mid(n - 1));
    for (let i = 0; i < n; i++) c.quadraticCurveTo(points[i][0], points[i][1], ...mid(i));
    c.closePath();
  }};
}
export function C(x0, y0, x1, y1, r) {
  const a = Math.atan2(y1 - y0, x1 - x0);
  return {box: [Math.min(x0, x1) - r, Math.min(y0, y1) - r, Math.abs(x1 - x0) + r * 2, Math.abs(y1 - y0) + r * 2],
    path: c => { c.arc(x0, y0, r, a + Math.PI / 2, a - Math.PI / 2); c.arc(x1, y1, r, a - Math.PI / 2, a + Math.PI / 2); c.closePath(); }};
}
const rgba = (hex, a) => {
  const h = hex.replace('#', ''); const n = parseInt(h.length === 3 ? [...h].map(c => c + c).join('') : h.slice(0, 6), 16);
  return `rgba(${n >> 16 & 255}, ${n >> 8 & 255}, ${n & 255}, ${a})`;
};
/** Fill a shape and light it inside its own outline. opts: sheen (0..1), shade (0..1),
 * light [fx, fy] (where the sheen sits in the box), edge (inner line alpha), glow (no shade). */
export function fill(ctx, shape, base, {sheen = .32, shade = .5, light = [.3, .24], edge = .55, rim = null} = {}) {
  const [x, y, w, h] = shape.box;
  ctx.save();
  ctx.beginPath(); shape.path(ctx);
  ctx.fillStyle = base; ctx.fill();
  ctx.clip();
  const cx = x + w * light[0], cy = y + h * light[1], r = Math.max(w, h) * 1.05 + 1;
  const g = ctx.createRadialGradient(cx, cy, 0, cx, cy, r);
  g.addColorStop(0, `rgba(255, 246, 222, ${sheen})`);
  g.addColorStop(.42, 'rgba(255, 246, 222, 0)');
  g.addColorStop(.62, 'rgba(12, 10, 24, 0)');
  g.addColorStop(1, `rgba(12, 10, 24, ${shade})`);
  ctx.fillStyle = g; ctx.fillRect(x - 1, y - 1, w + 2, h + 2);
  if (rim) {   // a thin back-light along the lower right edge
    ctx.strokeStyle = rim; ctx.lineWidth = .8; ctx.globalAlpha = .55;
    ctx.beginPath(); shape.path(ctx); ctx.translate(-.5, -.5); ctx.stroke();
  }
  ctx.restore();
  if (edge) { ctx.save(); ctx.strokeStyle = rgba(OUTLINE, edge); ctx.lineWidth = .7; ctx.beginPath(); shape.path(ctx); ctx.stroke(); ctx.restore(); }
}
/** Short strokes clipped inside a shape: fur, grain, cloth weave. Deterministic per seed. */
export function strokes(ctx, shape, color, count, {len = 2.2, angle = Math.PI / 2, spread = .5, width = .55, seed = 1, alpha = .7} = {}) {
  const [x, y, w, h] = shape.box;
  ctx.save(); ctx.beginPath(); shape.path(ctx); ctx.clip();
  ctx.strokeStyle = color; ctx.lineWidth = width; ctx.globalAlpha = alpha;
  let s = seed * 9301 + 49297;
  const rnd = () => { s = (s * 9301 + 49297) % 233280; return s / 233280; };
  ctx.beginPath();
  for (let i = 0; i < count; i++) {
    const px = x + rnd() * w, py = y + rnd() * h, a = angle + (rnd() - .5) * spread, l = len * (.6 + rnd() * .8);
    ctx.moveTo(px, py); ctx.lineTo(px + Math.cos(a) * l, py + Math.sin(a) * l);
  }
  ctx.stroke(); ctx.restore();
}
const dot = (ctx, x, y, r, color) => { ctx.fillStyle = color; ctx.beginPath(); ctx.arc(x, y, r, 0, Math.PI * 2); ctx.fill(); };
const mirrorX = (ctx, w, draw) => { ctx.save(); ctx.translate(w, 0); ctx.scale(-1, 1); draw(); ctx.restore(); };

// --- the avatar ------------------------------------------------------------------
/* Proportions of a person, not a doll: about six heads tall in the 40 px frame (head ~6.6 px,
 * shoulders at 10, waist at 20, knees at 30, soles on the frame's bottom edge). Limbs are
 * tapered segments hinged at the joints, so walking swings thighs and shins, not blocks. */
export const HERO = Object.freeze({skin: '#e9b487', skinDark: '#b98058', hair: '#3a2925', hairLight: '#6b4a3f',
  scarf: '#9a4b3c', scarfDark: '#6e3128', cloak: '#5e2f27', tunic: '#55603d', tunicLight: '#76804f', sleeve: '#48522f',
  belt: '#8f6a43', buckle: '#e3c27a', pants: '#2c3a33', pantsLight: '#3a4b41', boot: '#4e3c2c', bootLight: '#8d7055', eye: '#1e1512'});
export const HERO_W = 32, HERO_H = 40, HERO_COMPACT_H = 26;
/** A tapered limb segment from (x0, y0) radius r0 to (x1, y1) radius r1. */
export function T(x0, y0, r0, x1, y1, r1) {
  const a = Math.atan2(y1 - y0, x1 - x0), h = Math.PI / 2;
  return {box: [Math.min(x0 - r0, x1 - r1), Math.min(y0 - r0, y1 - r1), Math.abs(x1 - x0) + r0 + r1, Math.abs(y1 - y0) + r0 + r1],
    path: c => { c.arc(x0, y0, r0, a + h, a - h); c.arc(x1, y1, r1, a - h, a + h); c.closePath(); }};
}
/** Hip/shoulder -> knee/elbow -> ankle/wrist as two tapered segments. */
function limb(c, [x0, y0, r0], [x1, y1, r1], [x2, y2, r2], color, opts = {}) {
  fill(c, T(x0, y0, r0, x1, y1, r1), color, {sheen: .28, shade: .5, ...opts});
  fill(c, T(x1, y1, r1, x2, y2, r2), color, {sheen: .28, shade: .5, ...opts});
}
function heroBoot(c, x, y, facing, dir = 1) {
  const H = HERO;
  if (facing === 'east') {
    fill(c, T(x, y - 3.4, 1.35, x, y - .6, 1.45), H.boot, {sheen: .3, edge: .5});
    const f = dir;
    fill(c, P([[x - 1.5 * f, y - 1.4], [x + 2.2 * f, y - 1.1], [x + 3.2 * f, y + .4], [x + 3.2 * f, y + 1.6], [x - 1.6 * f, y + 1.6]], true), H.boot, {sheen: .3});
    c.fillStyle = rgba(H.bootLight, .7); c.fillRect(Math.min(x - 1.2 * f, x + 3.2 * f), y + 1.1, 4.2, .35);
    return;
  }
  fill(c, T(x, y - 3.6, 1.35, x, y - .4, 1.5), H.boot, {sheen: .3, edge: .5});
  fill(c, E(x, y + .5, 1.75, 1.15), H.boot, {sheen: .35});
  c.fillStyle = rgba(H.bootLight, .6); c.fillRect(x - 1.1, y - 3.4, 2.2, .35);
}
function heroHead(c, facing, cx, cy) {
  const H = HERO;
  fill(c, R(cx - 1.1, cy + 2, 2.2, 3.2, 1), H.skinDark, {edge: .4, sheen: .1});                 // neck
  if (facing === 'north') {
    for (const d of [-1, 1]) fill(c, E(cx + d * 2.85, cy + .3, .55, .9), H.skinDark, {edge: .35});
    const hair = P([[cx - 2.9, cy + 1.8], [cx - 3.1, cy - 1.8], [cx - 1.6, cy - 3.9], [cx + .4, cy - 4.3], [cx + 2.3, cy - 3.6], [cx + 3.2, cy - 1.4],
      [cx + 2.9, cy + 1.9], [cx + 1.2, cy + 2.6], [cx - 1.2, cy + 2.6]], true);
    fill(c, hair, H.hair, {sheen: .3, shade: .45});
    strokes(c, hair, H.hairLight, 10, {len: 1.6, angle: Math.PI / 2 + .25, spread: .7, width: .35, seed: 3, alpha: .7});
    return;
  }
  if (facing === 'east') {
    fill(c, E(cx + .3, cy, 2.7, 3.2), H.skin, {sheen: .32, shade: .35, light: [.7, .3]});
    fill(c, E(cx + 1.4, cy + 1.9, 1.4, 1.05), H.skin, {edge: .35, shade: .3});                  // jaw and chin
    fill(c, P([[cx + 2.5, cy - .7], [cx + 3.6, cy + .9], [cx + 2.6, cy + 1.1]]), H.skin, {edge: .45, shade: .25});   // nose
    c.fillStyle = H.eye; c.beginPath(); c.ellipse(cx + 1.75, cy - .1, .33, .42, 0, 0, Math.PI * 2); c.fill();
    c.strokeStyle = rgba(H.hair, .9); c.lineWidth = .35; c.beginPath(); c.moveTo(cx + 1.1, cy - .95); c.lineTo(cx + 2.3, cy - 1.05); c.stroke();
    c.strokeStyle = rgba(H.skinDark, .9); c.lineWidth = .3; c.beginPath(); c.moveTo(cx + 1.8, cy + 2.05); c.lineTo(cx + 2.5, cy + 1.95); c.stroke();
    fill(c, E(cx - .8, cy + .3, .7, 1), H.skinDark, {edge: .35});                                  // ear
    const hair = P([[cx - 2.6, cy + 1.6], [cx - 2.9, cy - 1.8], [cx - 1.4, cy - 3.9], [cx + .9, cy - 4.3], [cx + 2.7, cy - 3.3], [cx + 3.1, cy - 1.6],
      [cx + 2.1, cy - 1.8], [cx + 1.2, cy - 1], [cx + .2, cy - 1.5], [cx - .3, cy + .2], [cx - 1, cy + 2], [cx - 1.8, cy + 2.8]], true);
    fill(c, hair, H.hair, {sheen: .3, shade: .45});
    strokes(c, hair, H.hairLight, 9, {len: 1.5, angle: Math.PI * .75, spread: .6, width: .35, seed: 5, alpha: .7});
    return;
  }
  for (const d of [-1, 1]) fill(c, E(cx + d * 2.75, cy + .3, .55, .9), H.skin, {edge: .35, shade: .3});
  const face = P([[cx - 2.6, cy - 1.6], [cx + 2.6, cy - 1.6], [cx + 2.5, cy + 1.2], [cx + 1.3, cy + 3], [cx, cy + 3.4], [cx - 1.3, cy + 3], [cx - 2.5, cy + 1.2]], true);
  fill(c, face, H.skin, {sheen: .32, shade: .32});
  for (const d of [-1, 1]) {
    c.fillStyle = H.eye; c.beginPath(); c.ellipse(cx + d * 1.15, cy + .1, .34, .4, 0, 0, Math.PI * 2); c.fill();
    c.strokeStyle = rgba(H.hair, .9); c.lineWidth = .35; c.beginPath(); c.moveTo(cx + d * .6, cy - .85); c.lineTo(cx + d * 1.75, cy - .95); c.stroke();
  }
  c.strokeStyle = rgba(H.skinDark, .85); c.lineWidth = .3;
  c.beginPath(); c.moveTo(cx + .1, cy + .3); c.lineTo(cx + .3, cy + 1.2); c.lineTo(cx - .1, cy + 1.3); c.stroke();   // nose
  c.beginPath(); c.moveTo(cx - .6, cy + 2.1); c.quadraticCurveTo(cx, cy + 2.35, cx + .6, cy + 2.1); c.stroke();
  const hair = P([[cx - 2.9, cy + 1.2], [cx - 3.1, cy - 2], [cx - 1.6, cy - 3.9], [cx + .4, cy - 4.3], [cx + 2.4, cy - 3.6], [cx + 3.2, cy - 1.6], [cx + 2.9, cy + 1.2],
    [cx + 2.4, cy - .9], [cx + 1.1, cy - 1.5], [cx - .1, cy - 1], [cx - 1.3, cy - 1.7], [cx - 2.4, cy - .9]], true);
  fill(c, hair, H.hair, {sheen: .3, shade: .45});
  strokes(c, hair, H.hairLight, 9, {len: 1.5, angle: Math.PI / 2 + .35, spread: .9, width: .35, seed: 7, alpha: .7});
}
function heroTunic(c, x0, x1, top, waist, hem, b, light = true) {
  const H = HERO, mid = (x0 + x1) / 2, w = x1 - x0;
  const tunic = P([[x0 + .2, top + b], [x1 - .2, top + b], [x1 + .2, top + 4 + b], [x1 - w * .08, waist + b], [x1 + w * .06, hem], [mid, hem + .7], [x0 - w * .06, hem], [x0 + w * .08, waist + b], [x0 - .2, top + 4 + b]], true);
  fill(c, tunic, H.tunic, {sheen: .3});
  strokes(c, tunic, H.tunicLight, 9, {len: 2.4, angle: Math.PI / 2, spread: .3, width: .35, seed: Math.round(x0 * 3), alpha: light ? .45 : .25});
  strokes(c, tunic, rgba('#20281a', .8), 6, {len: 3, angle: Math.PI / 2, spread: .2, width: .3, seed: Math.round(x1 * 5), alpha: .5});
  fill(c, R(x0 + w * .06, waist - .9 + b, w * .88, 1.7, .6), H.belt, {edge: .45, shade: .3});
}
/** The standing avatar (south / north / east; west is east mirrored) in a 32 x 40 frame. */
function heroStanding(c, facing, stride, breathe) {
  const H = HERO, b = breathe * .4;
  if (facing === 'east') {
    const sw = -stride;   // the near arm swings against the near leg
    fill(c, P([[14.2, 9.8 + b], [17.2, 9.8 + b], [16.2, 21], [13.8, 31.2 - stride * .5], [10, 30.2], [11.6, 18]], true), H.cloak, {sheen: .18, shade: .45});
    limb(c, [16.6, 11 + b, 1.4], [16.6 + stride * 1.6, 16.2 + b, 1.15], [16.6 + stride * 2.8, 21 + b, .95], rgba(H.sleeve, 1), {shade: .65});   // far arm
    const legs = stride === 0 ? [[16.4, 30.3, 16.1, 37.2], [16.8, 30.4, 16.6, 37.4]]
      : [[16 - 1.5, 30.5, 16 - 4.1, 36.6], [16 + 2.6, 30, 16 + 4.3, 37.4]];
    const [far, near] = stride >= 0 ? [legs[0], legs[1]] : [legs[1], legs[0]];
    limb(c, [16, 22, 2.1], [far[0], far[1], 1.6], [far[2], far[3], 1.2], H.pants, {shade: .62});
    heroBoot(c, far[2], far[3] + 1.6 + (far[2] < 14 ? -.6 : 0), 'east');
    limb(c, [16.4, 22, 2.2], [near[0], near[1], 1.7], [near[2], near[3], 1.25], H.pantsLight);
    heroBoot(c, near[2], near[3] + 1.6 + (near[2] < 14 ? -.6 : 0), 'east');
    heroTunic(c, 13, 19.4, 9.8, 19.8, 25.6, b);
    limb(c, [16.1, 11 + b, 1.5], [16.1 + sw * 1.9, 16.3 + b, 1.2], [16.1 + sw * 3.4, 21.1 + b, 1], H.sleeve);   // near arm
    fill(c, E(16.1 + sw * 3.6, 22.2 + b, 1.05, 1.2), H.skin, {shade: .35});
    fill(c, E(16.3, 9.4 + b, 2.6, 1.4), H.scarf, {sheen: .35});
    fill(c, P([[14.8, 9.6 + b], [12.2, 10.4], [10.6, 13.4], [12.8, 12.4]], true), H.scarf, {edge: .5});
    heroHead(c, 'east', 16.2, 4.4 + b * .5);
    return;
  }
  const back = facing === 'north';
  if (!back) fill(c, P([[10.4, 9.6 + b], [21.6, 9.6 + b], [23.6, 30.4], [16, 31.6], [8.4, 30.4]], true), H.cloak, {sheen: .12, shade: .5});
  for (const d of [-1, 1]) {   // a front view walks by lifting one knee, then the other
    const lift = stride === d ? 1 : 0;
    limb(c, [16 + d * 2.2, 22, 2.2], [16 + d * 2.5, 30.4 - lift * 1.3, 1.7], [16 + d * 2.4, 37.2 - lift * 1.6, 1.25], d < 0 ? H.pants : H.pantsLight);
    heroBoot(c, 16 + d * 2.4, 38.8 - lift * 1.6, facing);
  }
  heroTunic(c, 10.6, 21.4, 9.8, 19.8, 25.8, b, !back);
  if (!back) fill(c, R(15.1, 18.8 + b, 1.8, 2, .4), H.buckle, {edge: .45, shade: .2});
  for (const d of [-1, 1]) {
    const swing = stride * d * .9;
    limb(c, [16 + d * 5.3, 10.8 + b, 1.55], [16 + d * 6.2, 16.2 + b - swing * .3, 1.25], [16 + d * 6.3, 21.2 + b - swing, 1], H.sleeve);
    fill(c, E(16 + d * 6.3, 22.3 + b - swing, 1.05, 1.25), H.skin, {shade: .35});
  }
  if (back) {
    const cloak = P([[10.2, 9.6 + b], [21.8, 9.6 + b], [23.4, 30.2], [16, 31.4], [8.6, 30.2]], true);
    fill(c, cloak, H.scarf, {sheen: .24, shade: .5});
    c.save(); c.strokeStyle = rgba(H.cloak, .9); c.lineWidth = .5;
    for (const x of [13, 16, 19]) { c.beginPath(); c.moveTo(x, 12 + b); c.quadraticCurveTo(x + .4, 22, x + (x - 16) * .35, 30.6); c.stroke(); }
    c.restore();
  }
  fill(c, E(16, 9.3 + b, 3.6, 1.5), H.scarf, {sheen: .35});
  if (!back) fill(c, P([[17, 9.8 + b], [18.6, 9.8 + b], [19.2, 15.4 + b], [17.8, 15 + b]], true), H.scarf, {edge: .5});
  heroHead(c, facing, 16, 4.4 + b * .5);
}
/** Crouching / sitting / kneeling at work, in a 32 x 26 frame. */
function heroCompact(c, facing) {
  const H = HERO;
  if (facing === 'east') {
    fill(c, P([[14.2, 9.6], [17.6, 9.6], [15.4, 19], [11.6, 24.4], [9.6, 21]], true), H.cloak, {sheen: .18});
    limb(c, [14, 20.4, 2.1], [15.8, 24.2, 1.6], [11, 24.4, 1.2], H.pants, {shade: .62});           // kneeling far leg
    heroBoot(c, 10.2, 25.4, 'east', -1);
    limb(c, [14.4, 20.2, 2.2], [20, 16.8, 1.7], [19.8, 23.4, 1.25], H.pantsLight);                 // near leg, knee up
    heroBoot(c, 19.8, 25.2, 'east');
    const torso = P([[13.4, 20.6], [12.8, 15], [15, 10], [18.2, 9.8], [19, 13], [17.4, 19], [16.4, 21.6]], true);
    fill(c, torso, H.tunic, {sheen: .3});
    fill(c, R(13.4, 18.4, 4.4, 1.6, .6), H.belt, {edge: .45});
    limb(c, [17.2, 11.2, 1.45], [19.4, 15.6, 1.2], [21.6, 18.4, 1], H.sleeve);
    fill(c, E(22.2, 19, 1.05, 1.15), H.skin, {shade: .35});
    fill(c, E(17.4, 9.6, 2.4, 1.3), H.scarf, {sheen: .35});
    heroHead(c, 'east', 18.6, 5.2);
    return;
  }
  const back = facing === 'north';
  for (const d of [-1, 1]) {   // knees up either side, forearms resting on them
    limb(c, [16 + d * 2.2, 20.6, 2.1], [16 + d * 4.6, 17, 1.7], [16 + d * 3.8, 23.4, 1.25], d < 0 ? H.pants : H.pantsLight);
    heroBoot(c, 16 + d * 3.8, 25, facing);
  }
  if (back) fill(c, P([[10.6, 10], [21.4, 10], [22.6, 21.4], [16, 22.4], [9.4, 21.4]], true), H.scarf, {sheen: .24});
  else heroTunic(c, 11.2, 20.8, 10, 18.4, 21.4, 0);
  for (const d of [-1, 1]) {
    limb(c, [16 + d * 4.8, 11.2, 1.5], [16 + d * 5.6, 15.6, 1.2], [16 + d * 3.8, 18, 1], H.sleeve);
    if (!back) fill(c, E(16 + d * 3.6, 18.8, 1.05, 1.15), H.skin, {shade: .35});
  }
  fill(c, E(16, 9.8, 3.4, 1.4), H.scarf, {sheen: .35});
  heroHead(c, facing, 16, 5.2);
}
/** The avatar's body for a pose (fists, weapons and work hands are drawn live around it). */
export function heroCanvas(facing, stride, breathe, compact) {
  const side = facing === 'west' ? 'east' : facing;
  const key = `hero|${facing}|${compact ? 'c' : `${stride}|${breathe}`}`;
  const h = compact ? HERO_COMPACT_H : HERO_H;
  return paintedCanvas(key, HERO_W, h, c => {
    const draw = () => compact ? heroCompact(c, side) : heroStanding(c, side, stride, breathe);
    if (facing === 'west') mirrorX(c, HERO_W, draw); else draw();
  });
}

// --- enemies -----------------------------------------------------------------------
/** Frame sizes (w, h) per enemy sprite key: feet on the bottom edge, centred on the tile. */
/* Sized against the avatar (about 1.75 m in a 40 px frame): a boar stands about half a person
 * at the shoulder, a wolf a little less, a lurker lies low, the bones are a person's height and
 * a wisp is no bigger than a lantern-glow. ENEMY_ART draws at `scale` 1 in ENEMY_ART_FRAMES. */
const ENEMY_ART_FRAMES = {boar: [41, 26, 1], lurker: [48, 32, .74], skeleton: [24, 41, 1], wisp: [34, 40, .62], wolf: [54, 38, .74]};
export const ENEMY_FRAMES = Object.freeze(Object.fromEntries(Object.entries(ENEMY_ART_FRAMES).map(([k, [w, h, s]]) => [k, [Math.round(w * s), Math.round(h * s)]])));
/** Enemies seen side-on (boar, wolf) turn to face the avatar; the art faces east. */
export const SIDE_ON = Object.freeze(new Set(['boar', 'wolf']));

function boar(c) {
  // A wild boar seen side-on, facing east: high bristled withers, a long wedge head, tusks,
  // thin legs under a heavy barrel body - with brambles tangled in the mane.
  const coat = '#4e2b2c', coatLight = '#74404a', dark = '#2a1517', snout = '#8e6464', thorn = '#33502a';
  c.save(); c.strokeStyle = coat; c.lineWidth = .7; c.beginPath(); c.moveTo(4.2, 10.4); c.quadraticCurveTo(2, 12.4, 2.2, 15.6); c.stroke(); c.restore();
  fill(c, E(2.2, 16, .8, 1.3), dark, {edge: .4});                                                     // tail tuft
  for (const [x0, y0, x1] of [[9.6, 17, 8.6], [29.6, 17, 30.4]]) {                                     // far legs
    fill(c, T(x0, y0, 1.4, x1, 24.6, .75), dark, {shade: .55});
    fill(c, R(x1 - .9, 24.2, 1.9, 1.6, .5), '#120a08', {edge: .4});
  }
  const body = P([[4.2, 12.6], [5.6, 7.6], [11, 5], [17, 3.4], [22.6, 2.8], [27.6, 4.4], [31.2, 7.4], [32, 12.6], [30.6, 17], [24, 18.4], [15, 18.6], [8.4, 17.6], [4.8, 15.6]], true);
  fill(c, body, coat, {sheen: .3, shade: .55});
  strokes(c, body, dark, 60, {len: 2, angle: Math.PI * .62, spread: .5, width: .4, seed: 11, alpha: .75});
  strokes(c, body, coatLight, 30, {len: 1.8, angle: Math.PI * .62, spread: .5, width: .35, seed: 12, alpha: .55});
  c.save(); c.strokeStyle = dark; c.lineWidth = .55;                                                 // the bristled mane
  for (let i = 0; i < 26; i++) {
    const t = i / 25, x = 7 + t * 23, y = 6.2 - Math.sin(t * Math.PI) * 3.6 + (t > .7 ? (t - .7) * 4 : 0);
    c.beginPath(); c.moveTo(x, y + 1.2); c.lineTo(x - .5 + (i % 3) * .3, y - 1.4 - (i % 2) * .6); c.stroke();
  }
  c.restore();
  c.save(); c.strokeStyle = thorn; c.lineWidth = .8;                                                // brambles in the mane
  c.beginPath(); c.moveTo(8, 7.4); c.bezierCurveTo(13, 2.6, 22, 1.4, 29, 5.4); c.stroke();
  c.fillStyle = '#5c7f3c';
  for (const [x, y] of [[11, 5], [15, 3.4], [19, 2.6], [23, 2.8], [27, 4.2]]) { c.beginPath(); c.moveTo(x - .5, y); c.lineTo(x + .2, y - 1.4); c.lineTo(x + .5, y); c.fill(); }
  c.restore();
  for (const [x, y] of [[13.4, 4.4], [21, 2.4], [25.6, 3.8]]) { dot(c, x, y, .65, '#b8323f'); dot(c, x - .2, y - .2, .25, '#ffb0a0'); }
  fill(c, E(9.4, 13.6, 4, 4.6), coat, {sheen: .28, shade: .5, edge: .35});                            // haunch
  fill(c, T(9.8, 16.4, 1.7, 9.4, 24.6, .85), coat, {shade: .5});                                     // near legs
  fill(c, R(8.4, 24.2, 2.1, 1.7, .5), '#120a08', {edge: .4});
  fill(c, T(27.4, 15.6, 1.9, 27.8, 24.6, .9), coat, {shade: .5});
  fill(c, R(26.8, 24.2, 2.1, 1.7, .5), '#120a08', {edge: .4});
  const head = P([[28.6, 5.8], [33, 6.2], [36.6, 9.2], [39.2, 11.6], [39.6, 13.6], [37.6, 15], [33.4, 15.4], [29.6, 14.2]], true);
  fill(c, head, coat, {sheen: .32, shade: .5, light: [.4, .2]});
  strokes(c, head, dark, 14, {len: 1.4, angle: Math.PI * .1, spread: .5, width: .35, seed: 13, alpha: .7});
  fill(c, E(39.3, 12.7, .95, 1.35), snout, {sheen: .35, edge: .55});
  dot(c, 39.5, 12.4, .3, '#2a1214'); dot(c, 39.4, 13.2, .3, '#2a1214');
  fill(c, P([[32.2, 6.6], [31.2, 2.8], [34, 5.8]], true), coat, {edge: .55});                         // ear
  fill(c, P([[32.3, 5.6], [31.9, 3.9], [33.2, 5.6]], true), '#8e5a5a', {edge: 0});
  fill(c, P([[36.2, 14.6], [37.6, 12.2], [38.2, 10.6], [38.1, 12.8], [37.2, 14.8]], true), '#efe6cf', {sheen: .5, shade: .3, edge: .6});   // tusk
  dot(c, 34.6, 9.4, .7, '#1a0606');
  const g = c.createRadialGradient(34.6, 9.3, 0, 34.6, 9.3, .75);
  g.addColorStop(0, '#fff3a8'); g.addColorStop(.55, '#ff9d3c'); g.addColorStop(1, 'rgba(255,120,40,0)');
  c.fillStyle = g; c.beginPath(); c.arc(34.6, 9.3, .75, 0, Math.PI * 2); c.fill();
}

function lurker(c) {
  const hide = '#2f5f57', hideDark = '#1b3d37', belly = '#9fbf8a', eye = '#e8d84a';
  for (const [x0, y0, x1, y1] of [[12, 22, 3.5, 29.5], [36, 22, 44.5, 29.5], [15, 25, 9, 30.5], [33, 25, 39, 30.5]]) {
    fill(c, C(x0, y0, x1, y1, 2.2), hideDark, {shade: .5});
    for (const d of [-1.6, 0, 1.6]) fill(c, E(x1 + d, y1 + .8, 1.1, .8), '#16352f', {edge: .4});   // webbed toes
  }
  const body = E(24, 20, 18.4, 9.2);
  fill(c, body, hide, {sheen: .32, shade: .55});
  c.save(); c.beginPath(); body.path(c); c.clip();
  for (let i = 0; i < 26; i++) {                                                                // scales
    const x = 8 + (i * 37 % 32), y = 13 + (i * 13 % 11);
    c.strokeStyle = rgba(hideDark, .7); c.lineWidth = .5; c.beginPath(); c.arc(x, y, 1.4, Math.PI * .1, Math.PI * .9); c.stroke();
  }
  c.restore();
  for (let i = 0; i < 7; i++) fill(c, E(12 + i * 4, 12.6 - Math.sin(i / 6 * Math.PI) * 1.4, 1.4, 1.1), hideDark, {edge: .4, sheen: .2});  // ridge
  fill(c, E(24, 25, 13.6, 4.2), belly, {sheen: .3, shade: .35});
  const jaw = E(24, 21.6, 11.4, 6.2);
  fill(c, jaw, '#3a7067', {sheen: .35, shade: .45});
  c.strokeStyle = OUTLINE; c.lineWidth = .8;
  c.beginPath(); c.moveTo(13.6, 23); c.quadraticCurveTo(24, 27.2, 34.4, 23); c.stroke();
  c.fillStyle = '#f1ecd2';
  for (let i = 0; i < 8; i++) { const x = 15.6 + i * 2.4, y = 24 + Math.sin(i / 7 * Math.PI) * 1.7; c.beginPath(); c.moveTo(x - .6, y - .2); c.lineTo(x, y + 1.1); c.lineTo(x + .6, y - .2); c.fill(); }
  for (const s of [-1, 1]) {                                                                     // eyes up on top
    fill(c, E(24 + s * 7, 12.6, 3.4, 3), hide, {sheen: .3, shade: .5});
    fill(c, E(24 + s * 7, 12.2, 2.1, 1.9), eye, {sheen: .55, shade: .25, edge: .6});
    c.fillStyle = '#1a1a08'; c.beginPath(); c.ellipse(24 + s * 7, 12.3, .45, 1.5, 0, 0, Math.PI * 2); c.fill();
  }
  c.save(); c.globalAlpha = .45; c.strokeStyle = '#d8fff2'; c.lineWidth = .7;                 // wet sheen
  c.beginPath(); c.moveTo(12, 15.4); c.quadraticCurveTo(18, 12.6, 22, 13.6); c.stroke(); c.restore();
}

function skeleton(c) {
  // A person's frame, about the avatar's height: a small skull, a narrow ribcage, long bones.
  const bone = '#d8d2bc', boneDark = '#9d977f', socket = '#14100c', rust = '#8a5130';
  for (const s of [-1, 1]) {
    const hip = 12 + s * 1.9;
    fill(c, T(hip, 22.4, .95, hip + s * .3, 31, .75), bone, {shade: .45});
    fill(c, E(hip + s * .3, 31.2, 1, .9), bone, {edge: .5});                                           // knee
    fill(c, T(hip + s * .3, 31.6, .75, hip + s * .2, 39.4, .6), bone, {shade: .45});
    fill(c, R(hip + s * .2 - 1.3 + (s > 0 ? .7 : 0), 39.4, 2.1, 1.2, .5), boneDark, {edge: .5});
  }
  fill(c, P([[8.6, 20.2], [15.4, 20.2], [14.4, 23.2], [12, 24], [9.6, 23.2]], true), bone, {sheen: .4});   // pelvis
  c.save(); c.strokeStyle = OUTLINE; c.lineWidth = 1.5; c.beginPath(); c.moveTo(12, 7.6); c.lineTo(12, 20.6); c.stroke();
  c.strokeStyle = bone; c.lineWidth = .8; c.setLineDash([.8, .35]); c.stroke(); c.restore();           // spine
  for (let i = 0; i < 5; i++) {                                                                        // ribs
    const y = 10 + i * 1.5, w = 4 - i * .35;
    for (const s of [-1, 1]) {
      c.save(); c.strokeStyle = OUTLINE; c.lineWidth = 1.2;
      c.beginPath(); c.moveTo(12, y); c.quadraticCurveTo(12 + s * w * 1.1, y - .3, 12 + s * w * .75, y + 1.4); c.stroke();
      c.strokeStyle = i ? bone : '#ece7d4'; c.lineWidth = .6; c.stroke(); c.restore();
    }
  }
  fill(c, T(7.6, 9.6, .7, 16.4, 9.6, .7), bone, {edge: .6});                                         // collarbones
  fill(c, T(7.6, 10, .8, 6.9, 16.4, .7), bone, {shade: .45});                                       // far arm
  fill(c, T(6.9, 16.8, .7, 7.3, 22, .6), bone, {shade: .45});
  fill(c, E(7.4, 22.6, .9, .8), boneDark, {edge: .5});
  fill(c, P([[18.6, 19.8], [20.6, 2.2], [21.4, 1], [21.8, 2.4], [19.8, 20.2]]), '#9a9c92', {sheen: .55, shade: .45, light: [.2, .1]});   // a pitted old blade
  c.save(); c.strokeStyle = '#e4e6dc'; c.lineWidth = .3; c.beginPath(); c.moveTo(20.9, 3); c.lineTo(19.1, 19.4); c.stroke();
  c.fillStyle = rgba(rust, .85); for (const [x, y, r] of [[20.4, 7, .5], [19.9, 12, .45], [19.6, 16, .6]]) { c.beginPath(); c.arc(x, y, r, 0, Math.PI * 2); c.fill(); } c.restore();
  fill(c, T(17.2, 20.4, .55, 22, 20, .55), '#5a3a22', {edge: .6});                                  // crossguard
  fill(c, T(16.4, 10, .8, 18, 15.2, .7), bone, {shade: .45});                                       // near arm
  fill(c, T(18, 15.6, .7, 19.2, 20.4, .6), bone, {shade: .45});
  fill(c, E(19.2, 20.8, .95, .85), bone, {edge: .5});
  fill(c, T(12, 6.6, .6, 12, 8.4, .6), bone, {edge: .5});                                            // neck
  fill(c, E(12, 3.6, 2.7, 2.9), bone, {sheen: .45, shade: .45});                                   // skull
  fill(c, R(10.4, 5, 3.2, 2.2, .9), bone, {sheen: .3, shade: .45});                                // jaw
  c.strokeStyle = rgba(OUTLINE, .75); c.lineWidth = .25;
  for (let i = 0; i < 4; i++) { c.beginPath(); c.moveTo(10.9 + i * .75, 5.6); c.lineTo(10.9 + i * .75, 6.8); c.stroke(); }
  for (const s of [-1, 1]) { c.fillStyle = socket; c.beginPath(); c.ellipse(12 + s * 1.1, 3.6, .75, .85, s * .2, 0, Math.PI * 2); c.fill(); }
  c.fillStyle = socket; c.beginPath(); c.moveTo(11.7, 5.1); c.lineTo(12, 4.4); c.lineTo(12.3, 5.1); c.fill();
}

function wisp(c) {
  const halo = c.createRadialGradient(17, 15, 1, 17, 15, 17);
  halo.addColorStop(0, 'rgba(226, 238, 255, .7)'); halo.addColorStop(.45, 'rgba(127, 168, 216, .25)'); halo.addColorStop(1, 'rgba(127, 168, 216, 0)');
  c.fillStyle = halo; c.fillRect(0, 0, 34, 34);
  for (let i = 0; i < 4; i++) {                                                                  // trailing wisps
    const x = 11 + i * 4, sway = (i % 2 ? 1 : -1) * 2.4;
    const g = c.createLinearGradient(0, 18, 0, 39);
    g.addColorStop(0, 'rgba(126, 154, 208, .95)'); g.addColorStop(1, 'rgba(62, 79, 134, 0)');
    c.fillStyle = g;
    c.beginPath(); c.moveTo(x - 2, 20);
    c.bezierCurveTo(x - 2 + sway, 27, x + sway * -1, 32, x + sway * .6, 39);
    c.bezierCurveTo(x + 1 - sway, 32, x + 2 + sway * .4, 27, x + 2, 20); c.closePath(); c.fill();
  }
  const core = c.createRadialGradient(15.4, 12.6, .5, 17, 15, 8.4);
  core.addColorStop(0, '#ffffff'); core.addColorStop(.55, '#eaf6ff'); core.addColorStop(1, '#8fb2e6');
  c.fillStyle = core; c.beginPath(); c.ellipse(17, 15, 8, 8.4, 0, 0, Math.PI * 2); c.fill();
  c.strokeStyle = 'rgba(62, 79, 134, .55)'; c.lineWidth = .7; c.stroke();
  for (const s of [-1, 1]) { c.fillStyle = '#3e4f86'; c.beginPath(); c.ellipse(17 + s * 2.9, 14.4, 1.2, 1.9, 0, 0, Math.PI * 2); c.fill(); }
  c.fillStyle = '#3e4f86'; c.beginPath(); c.ellipse(17, 18.6, 1.1, 1.3, 0, 0, Math.PI * 2); c.fill();
}

function wolf(c) {
  const coat = '#62676f', coatLight = '#8d939b', saddle = '#383b41', dark = '#26282c';
  fill(c, P([[10, 18], [5, 21], [1.6, 27.4], [3, 31.4], [6.4, 27.6], [9.6, 25], [12.4, 22]], true), coat, {sheen: .3, shade: .5});   // tail
  fill(c, P([[3.6, 29.6], [1.6, 27.4], [2.6, 31.6]], true), coatLight, {edge: .3});
  for (const [x0, x1] of [[16.6, 15.6], [37, 38]]) {                                            // far legs
    fill(c, C(x0, 27, x1, 35.6, 1.9), dark, {shade: .5});
    fill(c, E(x1 + .6, 36.6, 2.1, 1.1), dark, {edge: .5});
  }
  const body = P([[42, 18], [36, 13.6], [26, 13.4], [16, 14.6], [9.6, 18.6], [10.4, 25.4], [16, 28.4], [28, 28.6], [38, 27.6], [43, 24]], true);
  fill(c, body, coat, {sheen: .32, shade: .55});
  strokes(c, body, saddle, 34, {len: 3, angle: Math.PI * .1, spread: .4, seed: 21, alpha: .6});
  fill(c, P([[38, 15.4], [30, 13], [20, 13.6], [12, 17], [17, 17.4], [28, 16.4], [36, 17.6]], true), saddle, {edge: 0, sheen: .15});
  strokes(c, body, coatLight, 16, {len: 2.4, angle: Math.PI * .1, spread: .5, seed: 22, alpha: .45});
  fill(c, P([[38.4, 16], [44, 13.4], [46, 20], [43.4, 26.4], [38.6, 25]], true), '#7a8088', {sheen: .35, edge: .3});   // ruff
  for (const [x0, x1] of [[19.4, 19], [40, 40.8]]) {                                            // near legs
    fill(c, C(x0, 26, x1, 35.8, 2), coat, {shade: .5});
    fill(c, E(x1 + .8, 36.8, 2.3, 1.2), dark, {edge: .5});
  }
  fill(c, P([[42.8, 12.6], [43.6, 4.4], [46.8, 11]], true), coat, {edge: .55});               // ears
  fill(c, P([[46, 11.4], [48, 4.8], [50, 12]], true), coat, {edge: .55});
  fill(c, P([[44.2, 11], [44.4, 6.8], [45.8, 10.6]], true), '#a77d7d', {edge: 0});
  fill(c, E(46.4, 15, 6, 5.2), coat, {sheen: .35, shade: .45});
  fill(c, P([[48, 13.6], [53.6, 16.2], [53.2, 19.4], [47.4, 19.8]], true), coatLight, {sheen: .4, shade: .35});   // muzzle
  dot(c, 53.4, 16.6, 1.15, '#101114');
  c.fillStyle = '#f6f2e6';
  for (let i = 0; i < 3; i++) { c.beginPath(); c.moveTo(48.6 + i * 1.5, 19.4); c.lineTo(49.2 + i * 1.5, 20.8); c.lineTo(49.8 + i * 1.5, 19.4); c.fill(); }
  dot(c, 48.8, 14, 1.2, '#20160a');
  const g = c.createRadialGradient(48.8, 14, 0, 48.8, 14, 1.1);
  g.addColorStop(0, '#fff8c0'); g.addColorStop(.6, '#ffe066'); g.addColorStop(1, 'rgba(255,224,102,0)');
  c.fillStyle = g; c.beginPath(); c.arc(48.8, 14, 1.1, 0, Math.PI * 2); c.fill();
}
const ENEMY_ART = {boar, lurker, skeleton, wisp, wolf};
export function enemyCanvas(sprite, breathe = 0, west = false) {
  const draw = ENEMY_ART[sprite];
  if (!draw) return null;
  const [w, h] = ENEMY_FRAMES[sprite], scale = ENEMY_ART_FRAMES[sprite][2], flip = west && SIDE_ON.has(sprite);
  return paintedCanvas(`enemy|${sprite}|${breathe}|${flip ? 'w' : 'e'}`, w, h, c => {
    if (flip) { c.translate(w, 0); c.scale(-1, 1); }
    if (breathe) { c.translate(0, h); c.scale(1, 1 - .025); c.translate(0, -h); }   // a slow heave
    c.scale(scale, scale);
    draw(c);
  }, {outline: sprite !== 'wisp'});
}

// --- the old man, the anchor stone ---------------------------------------------------
export const ELDER_W = 30, ELDER_H = 46;
function elder(c) {
  // An old man of ordinary height, a little stooped over his staff (held west), hood up,
  // a long white beard - drawn to the same proportions as the avatar.
  const robe = '#5b5d53', robeLight = '#7d7f72', hood = '#6b6457', skin = '#d8b48c', beard = '#ece6d6', staff = '#7b5a36';
  fill(c, T(4.2, 4.6, .75, 5.2, 45.4, .6), staff, {sheen: .35});
  fill(c, E(4.1, 3.8, 1.35, 1.3), '#8a6a44', {edge: .6});
  const body = P([[11.4, 10.4], [18.8, 9.8], [21.6, 17], [23.8, 44.2], [16.4, 45], [9.2, 44.4], [10, 25]], true);
  fill(c, body, robe, {sheen: .28, shade: .5});
  c.save(); c.beginPath(); body.path(c); c.clip(); c.strokeStyle = rgba('#3a3c34', .8); c.lineWidth = .5;
  for (const x of [13, 16.4, 19.8]) { c.beginPath(); c.moveTo(x, 18); c.quadraticCurveTo(x + .8, 32, x + (x - 16.4) * .35, 45); c.stroke(); }
  c.restore();
  fill(c, R(10.6, 22, 11, 1.3, .6), '#3a2c20', {edge: .5});                                          // rope belt
  fill(c, T(15.2, 22.6, .45, 14.8, 27, .4), '#3a2c20', {edge: .4});
  for (const x of [11.4, 17.6]) fill(c, R(x, 44.2, 3.6, 1.7, .8), '#3a2c20', {sheen: .25});           // feet
  fill(c, T(12.8, 12.4, 1.6, 8, 17.4, 1.3), robeLight, {sheen: .3});                                 // arm to the staff
  fill(c, T(8, 17.4, 1.3, 5.2, 20.2, 1.1), robeLight, {sheen: .3});
  fill(c, E(4.9, 20.6, 1.15, 1.1), skin, {shade: .4});
  fill(c, P([[11.2, 10.6], [11, 5.2], [13.6, 1.4], [17.6, 1.2], [20.2, 4.6], [20, 10.8], [16.4, 12]], true), hood, {sheen: .3, shade: .55});   // hood
  fill(c, E(14.6, 6.4, 2.4, 2.9), skin, {sheen: .3, shade: .35, light: [.35, .3]});
  fill(c, P([[12.4, 5.8], [11.3, 7.4], [12.4, 7.7]], true), skin, {edge: .45});                     // nose
  fill(c, P([[12.4, 7.8], [16.8, 7.6], [17, 10.6], [15.2, 15.8], [12.6, 11.8]], true), beard, {sheen: .45, shade: .35});   // beard
  strokes(c, P([[12.8, 8.4], [16.6, 8.4], [15, 15]]), '#b9b19c', 8, {len: 2.2, angle: Math.PI / 2, spread: .3, width: .3, seed: 31, alpha: .8});
  c.save(); c.strokeStyle = '#f4efe2'; c.lineWidth = .55;                                         // bushy brows
  c.beginPath(); c.moveTo(12.4, 5); c.lineTo(14.6, 4.8); c.stroke(); c.restore();
  c.save(); c.strokeStyle = '#3a2618'; c.lineWidth = .3; c.beginPath(); c.moveTo(12.8, 5.9); c.lineTo(13.9, 6); c.stroke(); c.restore();
}
export function elderCanvas(facing = 'west') {
  return paintedCanvas(`elder|${facing}`, ELDER_W, ELDER_H, c => facing === 'east' ? mirrorX(c, ELDER_W, () => elder(c)) : elder(c));
}

export const STONE_W = 40, STONE_H = 54;
/** The anchor stone: a leaning blue-grey monolith split by a glowing seam, runes cut in its face. */
export function anchorStoneCanvas() {
  return paintedCanvas('anchor-stone', STONE_W, STONE_H, c => {
    fill(c, E(20, 50.6, 17, 3.6), '#3a4048', {sheen: .2, edge: .5});                           // footing
    for (const [x, y, r] of [[7, 49, 3.6], [33.4, 49.4, 3.2], [27, 51, 2.6]]) fill(c, E(x, y, r, r * .7), '#6b7280', {sheen: .4});
    const stone = P([[11, 50], [9.6, 30], [12.6, 11], [19.4, 2.4], [26.6, 9], [30.4, 28], [29.4, 50]]);
    fill(c, stone, '#5d6470', {sheen: .42, shade: .6, light: [.25, .15]});
    c.save(); c.beginPath(); stone.path(c); c.clip();
    c.fillStyle = 'rgba(169, 190, 212, .35)';                                                  // lit west facet
    c.beginPath(); c.moveTo(12.6, 11); c.lineTo(19.4, 2.4); c.lineTo(18.6, 50); c.lineTo(11, 50); c.lineTo(9.6, 30); c.closePath(); c.fill();
    c.fillStyle = 'rgba(20, 24, 40, .35)';
    c.beginPath(); c.moveTo(26.6, 9); c.lineTo(30.4, 28); c.lineTo(29.4, 50); c.lineTo(24, 50); c.closePath(); c.fill();
    c.restore();
    const seam = c.createLinearGradient(0, 6, 0, 48);
    seam.addColorStop(0, '#f1faff'); seam.addColorStop(.5, '#7fd0ff'); seam.addColorStop(1, '#2b6ea0');
    c.strokeStyle = seam; c.lineWidth = 1.2;
    c.beginPath(); c.moveTo(19.4, 6); c.lineTo(17.6, 16); c.lineTo(21, 24); c.lineTo(18.4, 34); c.lineTo(20.6, 47); c.stroke();
    c.strokeStyle = '#cfe6ff'; c.lineWidth = .7;
    for (const [x, y] of [[14, 19], [24.4, 22], [14.6, 33], [24.6, 37]]) {                       // runes
      c.beginPath(); c.moveTo(x - 1.4, y - 1.6); c.lineTo(x, y + 1.6); c.lineTo(x + 1.4, y - 1.6); c.moveTo(x - 1.2, y); c.lineTo(x + 1.2, y); c.stroke();
    }
  });
}

/** Live flames (not cached: they move every frame) over a ring of stones and crossed logs. */
export function drawFireArt(ctx, x, ground, clock, reducedMotion) {
  const base = paintedCanvas('fire-base', 30, 12, c => {
    for (const [ax, ay, bx, by] of [[4, 9, 25, 5], [5, 4.6, 26, 9.4]]) {
      fill(c, C(ax, ay, bx, by, 2.1), '#6e4a2c', {sheen: .35, shade: .5});
      for (const [ex, ey] of [[ax, ay], [bx, by]]) { fill(c, E(ex, ey, 1.9, 2), '#c39a62', {edge: .6, sheen: .2}); dot(c, ex, ey, .7, '#7a5532'); }
    }
    for (const [sx, sy, r] of [[2.4, 9.4, 2.4], [8, 10.6, 2.2], [15, 11, 2.4], [22, 10.6, 2.2], [27.6, 9.4, 2.4]]) fill(c, E(sx, sy, r, r * .75), '#7d8576', {sheen: .45});
  });
  if (base) drawPainted(ctx, base, x - 15, ground - 12);
  else return false;
  ctx.save();
  const t = reducedMotion ? 0 : clock / 1000;
  ctx.globalCompositeOperation = 'lighter';
  for (let i = 0; i < 5; i++) {
    const phase = t * (3.1 + i * .7) + i * 1.9, fx = x + (i - 2) * 2.6 + Math.sin(phase) * 1.1;
    const tall = 9 + (i % 2 ? 3 : 6) + Math.sin(phase * 1.7) * 2.2, wide = 2.6 + (2 - Math.abs(i - 2)) * .9;
    const g = ctx.createLinearGradient(0, ground - 5 - tall, 0, ground - 4);
    g.addColorStop(0, 'rgba(255, 246, 200, 0)'); g.addColorStop(.25, 'rgba(255, 214, 106, .85)');
    g.addColorStop(.7, 'rgba(232, 116, 44, .85)'); g.addColorStop(1, 'rgba(184, 50, 63, .5)');
    ctx.fillStyle = g;
    ctx.beginPath(); ctx.moveTo(fx - wide, ground - 4);
    ctx.quadraticCurveTo(fx - wide * 1.1, ground - 4 - tall * .55, fx + Math.sin(phase * 2) * 1.4, ground - 4 - tall);
    ctx.quadraticCurveTo(fx + wide * 1.1, ground - 4 - tall * .55, fx + wide, ground - 4); ctx.closePath(); ctx.fill();
  }
  if (!reducedMotion) for (let i = 0; i < 4; i++) {                                              // sparks rising
    const life = (t * .7 + i * .27) % 1, sx = x + Math.sin(i * 2.3 + t * 2) * 5 * life;
    ctx.fillStyle = `rgba(255, 210, 120, ${1 - life})`; ctx.fillRect(sx, ground - 10 - life * 22, .9, .9);
  }
  ctx.restore();
  return true;
}
