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
  let out = art;
  if (outline || a.under.length || a.after.length) {
    out = document.createElement('canvas');
    out.width = art.width; out.height = art.height;
    const o = out.getContext('2d');
    // silhouette: the art stamped around a small circle, tinted dark, then the art on top
    const sil = document.createElement('canvas'); sil.width = art.width; sil.height = art.height;
    const s = sil.getContext('2d');
    const r = .95 * k;
    if (outline) for (let i = 0; i < 12; i++) { const t = i / 12 * Math.PI * 2; s.drawImage(art, Math.cos(t) * r, Math.sin(t) * r); }
    s.globalCompositeOperation = 'source-in'; s.fillStyle = OUTLINE; s.fillRect(0, 0, sil.width, sil.height);
    const layer = list => { if (!list.length) return; o.save(); o.scale(k, k); o.translate(PAD, PAD); o.lineJoin = 'round'; o.lineCap = 'round'; for (const f of list) f(o); o.restore(); };
    layer(a.under);
    o.drawImage(sil, 0, 0); o.drawImage(art, 0, 0);
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
export const HERO = Object.freeze({skin: '#f0bc89', skinDark: '#c98f62', hair: '#3c2a27', hairLight: '#6b4a3f',
  scarf: '#9a4b3c', scarfDark: '#6e3128', tunic: '#55603d', tunicLight: '#76804f', belt: '#ae8355', buckle: '#ecd08a',
  pants: '#2a3933', pantsLight: '#3d5045', boot: '#5a4736', bootLight: '#9d8060', eye: '#271a16'});
export const HERO_W = 32, HERO_H = 40, HERO_COMPACT_H = 26;

function heroHead(c, facing, cx, cy) {
  const H = HERO;
  if (facing === 'north') {
    fill(c, E(cx - 6.8, cy + 1.2, 1.3, 1.8), H.skinDark, {edge: .4});
    fill(c, E(cx + 6.8, cy + 1.2, 1.3, 1.8), H.skinDark, {edge: .4});
    const hair = P([[cx - 7.6, cy + 3], [cx - 8, cy - 4], [cx - 4.5, cy - 8.6], [cx, cy - 9.6], [cx + 4.8, cy - 8.4], [cx + 8, cy - 4], [cx + 7.6, cy + 3],
      [cx + 4.5, cy + 5.8], [cx + 2, cy + 4.6], [cx, cy + 6.2], [cx - 2.3, cy + 4.6], [cx - 4.8, cy + 5.8]], true);
    fill(c, hair, H.hair, {sheen: .28, shade: .45});
    strokes(c, hair, H.hairLight, 14, {len: 3.2, angle: Math.PI / 2 + .2, spread: .8, seed: 3, alpha: .6});
    fill(c, P([[cx - 1, cy - 8.8], [cx + 1.4, cy - 11.2], [cx + 2.6, cy - 8.2]]), H.hair, {edge: .5});
    return;
  }
  if (facing === 'east') {
    fill(c, E(cx + 1.4, cy, 5.9, 6.3), H.skin, {sheen: .35, shade: .32, light: [.62, .3]});
    fill(c, E(cx + 7, cy + 1.4, 1.3, 1.1), H.skin, {edge: .45, shade: .2});          // nose
    dot(c, cx + 4.6, cy + 1, .95, H.eye); dot(c, cx + 4.85, cy + .55, .35, '#ffffff');
    c.strokeStyle = rgba(H.skinDark, .9); c.lineWidth = .6;
    c.beginPath(); c.moveTo(cx + 4.4, cy + 4); c.lineTo(cx + 5.8, cy + 3.8); c.stroke();     // mouth
    dot(c, cx + 2.6, cy + 2.6, 1, rgba('#d9705a', .3));                               // cheek
    const hair = P([[cx - 6.6, cy + 2.2], [cx - 6.8, cy - 4.4], [cx - 3.8, cy - 8.4], [cx + .6, cy - 9.6], [cx + 5.4, cy - 8.2], [cx + 7.6, cy - 4.4],
      [cx + 6.6, cy - 2.6], [cx + 4.4, cy - 3.6], [cx + 3.4, cy - 1.6], [cx + 1.6, cy - 3], [cx + .2, cy + .4], [cx - 1, cy + 3.4], [cx - 2.4, cy + 6], [cx - 5.6, cy + 5.4]], true);
    fill(c, hair, H.hair, {sheen: .3, shade: .45});
    strokes(c, hair, H.hairLight, 12, {len: 3, angle: Math.PI * .7, spread: .7, seed: 5, alpha: .6});
    fill(c, E(cx - 1.4, cy + 1.2, 1.4, 1.9), H.skin, {edge: .45, shade: .3});          // ear
    fill(c, P([[cx - 1, cy - 8.8], [cx + .8, cy - 11.2], [cx + 2.4, cy - 8.6]]), H.hair, {edge: .5});
    return;
  }
  // south: the face
  fill(c, E(cx - 6.6, cy + 1, 1.3, 1.8), H.skin, {edge: .45, shade: .3});
  fill(c, E(cx + 6.6, cy + 1, 1.3, 1.8), H.skin, {edge: .45, shade: .3});
  fill(c, E(cx, cy + .2, 6.5, 6.2), H.skin, {sheen: .35, shade: .32});
  for (const s of [-1, 1]) {
    c.fillStyle = H.eye; c.beginPath(); c.ellipse(cx + s * 2.7, cy + 1.2, .95, 1.25, 0, 0, Math.PI * 2); c.fill();
    dot(c, cx + s * 2.7 + .3, cy + .7, .38, '#ffffff');
    dot(c, cx + s * 3.9, cy + 3.1, 1.1, rgba('#d9705a', .28));
  }
  c.strokeStyle = rgba(H.skinDark, .9); c.lineWidth = .6;
  c.beginPath(); c.moveTo(cx - .9, cy + 4.1); c.quadraticCurveTo(cx, cy + 4.6, cx + .9, cy + 4.1); c.stroke();
  const hair = P([[cx - 7.4, cy + 2.4], [cx - 7.6, cy - 4.4], [cx - 4.4, cy - 8.6], [cx, cy - 9.7], [cx + 4.6, cy - 8.5], [cx + 7.7, cy - 4.4], [cx + 7.4, cy + 2.4],
    [cx + 6, cy - 2], [cx + 4, cy - 3.6], [cx + 2.4, cy - 1.8], [cx + .4, cy - 3.8], [cx - 1.6, cy - 1.8], [cx - 3.8, cy - 3.6], [cx - 6, cy - 1.6]], true);
  fill(c, hair, H.hair, {sheen: .3, shade: .45});
  strokes(c, hair, H.hairLight, 12, {len: 3, angle: Math.PI / 2 + .3, spread: .9, seed: 7, alpha: .55});
  fill(c, P([[cx - 1, cy - 8.8], [cx + 1, cy - 11.2], [cx + 2.6, cy - 8.4]]), H.hair, {edge: .5});
}
function boot(c, x, y, facing) {
  const H = HERO;
  const s = facing === 'east' ? R(x - 2.4, y - 3.2, 6.2, 3.8, 1.6) : R(x - 2.6, y - 3.4, 5.2, 4, 1.6);
  fill(c, s, H.boot, {sheen: .3, shade: .5});
  c.fillStyle = rgba(H.bootLight, .8); c.fillRect(s.box[0] + .8, y - .6, s.box[2] - 1.6, .5);
}
/** The standing avatar (south / north / east; west is east mirrored) in a 32 x 40 frame. */
function heroStanding(c, facing, stride, breathe) {
  const H = HERO, b = breathe * .6;
  if (facing === 'east') {
    // cloak streams behind, back leg, body, front leg, near arm, scarf, head
    const cloak = P([[13, 18.5 + b], [17, 18.5 + b], [15.5, 31.5], [11, 33 - stride], [7.5, 31]], true);
    fill(c, cloak, H.scarfDark, {sheen: .2, shade: .45});
    const back = -stride * 2.6, front = stride * 2.6;
    fill(c, C(15.5, 29, 15.5 + back, 36.4, 2), H.pants, {shade: .55});
    boot(c, 15.5 + back + .6, 39.6, 'east');
    const torso = R(11.6, 17.8 + b, 9.4, 12.8, 3.2);
    fill(c, torso, H.tunic, {sheen: .3});
    strokes(c, torso, H.tunicLight, 10, {len: 2.4, seed: 2, alpha: .35});
    fill(c, R(11.6, 27.4 + b, 9.4, 2.2, 1), H.belt, {edge: .45, shade: .3});
    fill(c, C(17, 29, 17 + front, 36.4, 2), H.pantsLight, {shade: .5});
    boot(c, 17 + front + .6, 39.6, 'east');
    const swing = -stride * 2.4;
    fill(c, C(16.4, 20.4 + b, 16.6 + swing, 26.6 + b, 1.8), H.scarf, {sheen: .3});
    fill(c, E(16.6 + swing, 28 + b, 1.75, 1.75), H.skin, {shade: .35});
    fill(c, R(11.4, 16.4 + b, 10.4, 3.8, 1.9), H.scarf, {sheen: .35});
    fill(c, P([[12.4, 18], [9.4, 19.4], [7.8, 23.6], [10.6, 22.2]], true), H.scarf, {edge: .5});
    heroHead(c, 'east', 15.5, 10.9 + b * .5);
    return;
  }
  const back = facing === 'north';
  if (!back) fill(c, P([[8.4, 18.8 + b], [23.6, 18.8 + b], [26, 32.2], [6, 32.2]], true), H.scarfDark, {sheen: .15, shade: .5});
  for (const s of [-1, 1]) {   // legs lift alternately, so a front view still walks
    const lift = stride === s ? -1.4 : 0, x = 16 + s * 3.1;
    fill(c, C(x, 29, x, 36.2 + lift, 2.1), s < 0 ? H.pants : H.pantsLight, {shade: .55});
    boot(c, x, 39.6 + lift, facing);
  }
  const torso = R(10, 17.8 + b, 12, 12.8, 3.6);
  fill(c, torso, H.tunic, {sheen: .3});
  strokes(c, torso, H.tunicLight, 12, {len: 2.4, seed: 4, alpha: .35});
  fill(c, R(10, 27.4 + b, 12, 2.2, 1), H.belt, {edge: .45, shade: .3});
  if (!back) fill(c, R(15, 27.1 + b, 2.2, 2.8, .6), H.buckle, {edge: .5, shade: .2});
  for (const s of [-1, 1]) {
    const swing = stride * s * 1.6, sx = 16 + s * 6.3;
    fill(c, C(sx, 20.2 + b, sx + s * 1.1, 26.6 + b + swing, 1.85), H.scarf, {sheen: .3});
    fill(c, E(sx + s * 1.1, 28 + b + swing, 1.8, 1.8), H.skin, {shade: .35});
  }
  if (back) {
    const cloak = P([[8.6, 17.8 + b], [23.4, 17.8 + b], [25.6, 33], [16, 34], [6.4, 33]], true);
    fill(c, cloak, H.scarf, {sheen: .26, shade: .5});
    c.save(); c.strokeStyle = rgba(H.scarfDark, .9); c.lineWidth = .7;
    for (const x of [12.5, 16, 19.5]) { c.beginPath(); c.moveTo(x, 21 + b); c.quadraticCurveTo(x + .6, 27, x - .2 * (x - 16), 33); c.stroke(); }
    c.restore();
  }
  fill(c, R(9.4, 16.3 + b, 13.2, 4, 2), H.scarf, {sheen: .35});
  if (!back) fill(c, P([[18.8, 18.8 + b], [21.6, 18.8 + b], [22.6, 25 + b], [20.2, 24.2 + b]], true), H.scarf, {edge: .5});
  heroHead(c, facing, 16, 10.9 + b * .5);
}
/** Crouching / sitting / kneeling at work, in a 32 x 26 frame. */
function heroCompact(c, facing) {
  const H = HERO;
  if (facing === 'east') {
    fill(c, P([[12.6, 14], [16, 14], [14.6, 23.4], [7.4, 24], [7.8, 20]], true), H.scarfDark, {sheen: .2});
    fill(c, C(13, 21.8, 16, 23, 2), H.pants, {shade: .55});                          // folded back leg
    boot(c, 12.6, 25.6, 'east');
    fill(c, R(11.4, 13.4, 9.6, 9.4, 3.2), H.tunic, {sheen: .3});
    fill(c, R(11.4, 20.6, 9.6, 2, 1), H.belt, {edge: .45});
    fill(c, C(15.6, 21, 22, 19.2, 2.1), H.pantsLight, {shade: .5});                 // thigh up to the knee
    fill(c, C(22, 19.4, 22.4, 23.4, 2), H.pantsLight, {shade: .55});
    boot(c, 23, 25.6, 'east');
    fill(c, R(11.2, 12.2, 10.4, 3.6, 1.8), H.scarf, {sheen: .35});
    heroHead(c, 'east', 15.5, 6.6);
    return;
  }
  const back = facing === 'north';
  for (const s of [-1, 1]) {   // knees splay up either side of the lowered hips
    fill(c, E(16 + s * 6.4, 20.2, 3.6, 3.2), s < 0 ? H.pants : H.pantsLight, {shade: .5});
    boot(c, 16 + s * 6.8, 25.8, facing);
  }
  fill(c, R(10.2, 13.4, 11.6, 9, 3.4), back ? H.scarf : H.tunic, {sheen: .3});
  if (!back) fill(c, R(10.2, 20.4, 11.6, 2, 1), H.belt, {edge: .45});
  fill(c, R(9.6, 12.2, 12.8, 3.6, 1.8), H.scarf, {sheen: .35});
  heroHead(c, facing, 16, 6.6);
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
export const ENEMY_FRAMES = Object.freeze({boar: [46, 46], lurker: [48, 32], skeleton: [40, 50], wisp: [34, 40], wolf: [54, 38]});

function boar(c) {
  const fur = '#7e3447', furLight = '#9a4559', dark = '#4c1b2a', bone = '#e3d4b0', thorn = '#33502a';
  for (const x of [12, 34]) fill(c, R(x - 3.2, 34, 6.4, 10, 2.6), dark, {shade: .55});        // hind legs
  const body = E(23, 27.5, 18, 13.5);
  fill(c, body, fur, {sheen: .3, shade: .55});
  strokes(c, body, dark, 46, {len: 2.6, angle: Math.PI * .58, spread: .7, seed: 11, alpha: .55});
  strokes(c, body, furLight, 22, {len: 2.2, angle: Math.PI * .58, spread: .7, seed: 12, alpha: .45});
  // brambles across the back: a dark vine with thorns and a few berries
  c.save(); c.strokeStyle = thorn; c.lineWidth = 1.6;
  c.beginPath(); c.moveTo(6.5, 24); c.bezierCurveTo(12, 12, 32, 10, 39.5, 23); c.stroke();
  c.lineWidth = .9; c.beginPath(); c.moveTo(10, 18.5); c.bezierCurveTo(17, 13.5, 26, 12.5, 33, 15.5); c.stroke();
  c.fillStyle = '#5c7f3c';
  for (const [x, y, a] of [[9, 20, -2.4], [13, 15.6, -2], [18, 13.4, -1.7], [23, 12.8, -1.5], [28, 13.4, -1.3], [33, 15.4, -1], [37, 19, -.7]]) {
    c.beginPath(); c.moveTo(x - 1, y + .4); c.lineTo(x + Math.cos(a) * 2.6, y + Math.sin(a) * 2.6); c.lineTo(x + 1, y - .2); c.closePath(); c.fill();
  }
  c.restore();
  for (const [x, y] of [[15.5, 16.2], [30.5, 15.6], [21, 13.4]]) { dot(c, x, y, 1.15, '#b8323f'); dot(c, x - .35, y - .35, .4, '#ffb0a0'); }
  for (const x of [16.4, 29.6]) {                                                                // front legs
    fill(c, R(x - 3, 33, 6, 11.2, 2.6), fur, {shade: .5});
    fill(c, R(x - 3.1, 42.4, 6.2, 3.4, 1.2), '#2a1a14', {sheen: .25});
  }
  mirrorPair(c, 46, () => {                                                                       // ears and horns
    fill(c, P([[13.6, 22.6], [10.2, 16.6], [17.4, 20.4]]), fur, {edge: .55});
    fill(c, P([[13.8, 21.4], [11.6, 18], [16, 20.4]]), '#c56a7c', {edge: 0, sheen: .2});
    fill(c, P([[15.8, 24.6], [11.6, 21], [9.4, 14.8], [10.4, 9.4], [12.4, 13.8], [14.4, 19], [18, 22.4]], true), bone, {sheen: .45, shade: .45});
    c.save(); c.strokeStyle = rgba('#8d7a5a', .8); c.lineWidth = .5;
    for (const y of [13, 15.5, 18]) { c.beginPath(); c.moveTo(10.2, y); c.lineTo(12.6, y + .8); c.stroke(); } c.restore();
  });
  const head = E(23, 30.4, 10.8, 9.2);
  fill(c, head, furLight, {sheen: .32, shade: .5});
  strokes(c, head, dark, 18, {len: 1.8, angle: Math.PI * .5, spread: .9, seed: 13, alpha: .45});
  c.save(); c.fillStyle = rgba(dark, .9);                                                      // a heavy brow
  c.beginPath(); c.moveTo(14.6, 27.4); c.quadraticCurveTo(23, 23.6, 31.4, 27.4); c.quadraticCurveTo(23, 26, 14.6, 27.4); c.fill(); c.restore();
  for (const s of [-1, 1]) {                                                                     // ember eyes
    dot(c, 23 + s * 4.6, 29.2, 1.9, '#2a0b10');
    const g = c.createRadialGradient(23 + s * 4.6, 29.2, 0, 23 + s * 4.6, 29.2, 1.6);
    g.addColorStop(0, '#fff3a8'); g.addColorStop(.5, '#ffb43c'); g.addColorStop(1, 'rgba(255,120,40,0)');
    c.fillStyle = g; c.beginPath(); c.arc(23 + s * 4.6, 29.2, 1.6, 0, Math.PI * 2); c.fill();
  }
  fill(c, E(23, 35.4, 5.8, 4.2), '#b8606e', {sheen: .4, shade: .4});                         // snout
  for (const s of [-1, 1]) { c.fillStyle = '#3a1218'; c.beginPath(); c.ellipse(23 + s * 2, 35.6, .9, 1.4, 0, 0, Math.PI * 2); c.fill(); }
  mirrorPair(c, 46, () => fill(c, P([[18.6, 38.2], [16.2, 37], [15.2, 33.6], [17.2, 35.8], [19.6, 36.6]], true), '#f1e6cc', {sheen: .5, shade: .3}));
}
function mirrorPair(c, w, draw) { draw(); mirrorX(c, w, draw); }

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
  const bone = '#d8d2bc', boneDark = '#9d977f', socket = '#14100c', rust = '#8a5130';
  for (const s of [-1, 1]) {
    const hip = 20 + s * 3;
    fill(c, C(hip, 32, hip + s * .6, 40, 1.4), bone, {shade: .45});
    fill(c, C(hip + s * .6, 40.6, hip + s * .4, 47, 1.2), bone, {shade: .45});
    fill(c, E(hip + s * .4, 41, 1.7, 1.4), bone, {edge: .5});                                   // knee
    fill(c, R(hip + s * .4 - 2.2 + (s > 0 ? 1 : 0), 46.6, 3.6, 2, .9), boneDark, {edge: .5});
  }
  fill(c, P([[15.4, 30], [24.6, 30], [23.4, 34], [20, 35.2], [16.6, 34]], true), bone, {sheen: .4});   // pelvis
  c.save(); c.strokeStyle = bone; c.lineWidth = 1.5;                                        // spine
  c.beginPath(); c.moveTo(20, 19); c.lineTo(20, 31); c.stroke(); c.restore();
  for (let i = 0; i < 4; i++) {                                                                  // ribs
    const y = 20.4 + i * 2.4, w = 6.4 - i * .7;
    for (const s of [-1, 1]) {
      c.save(); c.strokeStyle = OUTLINE; c.lineWidth = 2.1;
      c.beginPath(); c.moveTo(20, y); c.quadraticCurveTo(20 + s * w * 1.1, y - .4, 20 + s * w * .8, y + 2); c.stroke();
      c.strokeStyle = i ? bone : '#ece7d4'; c.lineWidth = 1.1; c.stroke(); c.restore();
    }
  }
  fill(c, C(13.6, 19.4, 26.4, 19.4, 1.1), bone, {edge: .6});                                  // collar
  fill(c, C(13.4, 20, 11.6, 27.4, 1.25), bone, {shade: .45});                                 // far arm
  fill(c, C(11.6, 27.8, 12.4, 33.4, 1.1), bone, {shade: .45});
  fill(c, E(12.4, 34, 1.4, 1.2), boneDark, {edge: .5});
  // a rusted blade, raised in the near hand
  fill(c, P([[30.4, 31], [33.6, 6.4], [34.8, 4.6], [35.6, 6.8], [32.6, 31.6]]), '#9a9c92', {sheen: .55, shade: .45, light: [.2, .1]});
  c.save(); c.strokeStyle = '#e4e6dc'; c.lineWidth = .5; c.beginPath(); c.moveTo(33.9, 8); c.lineTo(31.2, 30.6); c.stroke();
  c.fillStyle = rgba(rust, .85); for (const [x, y, r] of [[33, 14, .9], [32.4, 20, .7], [32.8, 25, 1.1], [33.6, 10, .5]]) { c.beginPath(); c.arc(x, y, r, 0, Math.PI * 2); c.fill(); } c.restore();
  fill(c, C(28.2, 31.6, 35.2, 32.6, .9), '#5a3a22', {edge: .6});                              // crossguard
  fill(c, C(26.6, 20, 28.6, 27, 1.25), bone, {shade: .45});                                   // near arm
  fill(c, C(28.6, 27.4, 31.6, 32.4, 1.1), bone, {shade: .45});
  fill(c, E(31.6, 32.6, 1.5, 1.3), bone, {edge: .5});
  const skull = E(20, 10.6, 6.6, 6.8);
  fill(c, skull, bone, {sheen: .45, shade: .45});
  fill(c, R(16.4, 13.6, 7.2, 4.8, 1.8), bone, {sheen: .3, shade: .45});                       // jaw
  c.strokeStyle = rgba(OUTLINE, .75); c.lineWidth = .5;
  for (let i = 0; i < 5; i++) { c.beginPath(); c.moveTo(17.4 + i * 1.3, 15.2); c.lineTo(17.4 + i * 1.3, 17.4); c.stroke(); }
  c.beginPath(); c.moveTo(16.8, 16.2); c.lineTo(23.2, 16.2); c.stroke();
  for (const s of [-1, 1]) { c.fillStyle = socket; c.beginPath(); c.ellipse(20 + s * 2.6, 10.8, 1.8, 2.1, s * .2, 0, Math.PI * 2); c.fill(); }
  c.fillStyle = socket; c.beginPath(); c.moveTo(19.3, 14.2); c.lineTo(20, 12.6); c.lineTo(20.7, 14.2); c.fill();
  c.strokeStyle = rgba(boneDark, .9); c.lineWidth = .5; c.beginPath(); c.moveTo(21.8, 4.6); c.lineTo(22.6, 6.6); c.lineTo(21.9, 7.8); c.stroke();  // a crack
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
export function enemyCanvas(sprite, breathe = 0) {
  const draw = ENEMY_ART[sprite];
  if (!draw) return null;
  const [w, h] = ENEMY_FRAMES[sprite];
  return paintedCanvas(`enemy|${sprite}|${breathe}`, w, h, c => {
    if (breathe) { c.translate(0, h); c.scale(1, 1 - .025); c.translate(0, -h); }   // a slow heave
    draw(c);
  }, {outline: sprite !== 'wisp'});
}

// --- the old man, the anchor stone ---------------------------------------------------
export const ELDER_W = 36, ELDER_H = 60;
function elder(c) {
  const robe = '#5b5d53', robeLight = '#7d7f72', hood = '#6b6457', skin = '#d8b48c', beard = '#ece6d6', staff = '#7b5a36';
  fill(c, C(5.6, 6, 6.6, 59, 1.4), staff, {sheen: .35});                                       // staff (held west)
  fill(c, E(5.6, 5, 2.4, 2.4), '#8a6a44', {edge: .6});
  const body = P([[13, 20], [24, 18.6], [29, 30], [31.6, 57], [10.4, 57.6], [11.6, 34]], true);
  fill(c, body, robe, {sheen: .28, shade: .5});
  c.save(); c.beginPath(); body.path(c); c.clip(); c.strokeStyle = rgba('#3a3c34', .8); c.lineWidth = .8;
  for (const x of [16, 21, 26]) { c.beginPath(); c.moveTo(x, 26); c.quadraticCurveTo(x + 1.4, 42, x + (x - 21) * .3, 57); c.stroke(); }
  c.restore();
  fill(c, R(13, 33, 15.6, 2.2, 1), '#3a2c20', {edge: .5});                                   // rope belt
  fill(c, C(14.4, 23, 7.4, 30.6, 2.4), robeLight, {sheen: .3});                                // arm to the staff
  fill(c, E(6.8, 31, 2, 1.9), skin, {shade: .4});
  for (const x of [14.4, 23.4]) fill(c, R(x, 56, 5.6, 3.4, 1.4), '#3a2c20', {sheen: .25});      // feet
  fill(c, P([[12.2, 13], [15.4, 3.6], [22.4, 2.6], [27.6, 9.4], [28.4, 20.4], [24, 24.6], [14.6, 23.4]], true), hood, {sheen: .3, shade: .55});   // hood
  fill(c, E(19.2, 14.6, 4.6, 5.2), skin, {sheen: .3, shade: .35});
  fill(c, P([[14.6, 15], [19.6, 18.6], [23.8, 15.6], [23, 23.4], [19.6, 30.4], [15.4, 23.8]], true), beard, {sheen: .45, shade: .35});   // beard
  strokes(c, P([[15, 17], [24, 17], [20, 30]]), '#b9b19c', 10, {len: 3.2, angle: Math.PI / 2, spread: .3, seed: 31, alpha: .7});
  c.save(); c.strokeStyle = '#3a2618'; c.lineWidth = .7;
  for (const x of [17, 21.4]) { c.beginPath(); c.moveTo(x - 1, 13.6); c.lineTo(x + 1, 13.8); c.stroke(); }   // kind narrowed eyes
  c.strokeStyle = '#ffffff'; c.globalAlpha = .7; c.beginPath(); c.moveTo(16, 12.2); c.lineTo(18.4, 11.8); c.moveTo(20.4, 11.8); c.lineTo(22.8, 12.2); c.stroke(); c.restore();
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
