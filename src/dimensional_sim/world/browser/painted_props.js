/** Painted props: every encounter spot, site structure, camp building part and the ambush
 * wreckage, composed from a small kit of lit shapes (stones, logs, planks, bushes, pools,
 * mushrooms, prints, bones, crates, cloth) in the same style as the painted actors.
 *
 * Each prop is a function painting into a w x h frame whose bottom edge is the ground line.
 * Presentation only; keys match place_art.js SPOTS, art.js STRUCTURE_ART, BUILDING_PARTS and
 * AMBUSH so the cell sprites stay as the no-DOM fallback.
 */
import {C, E, P, R, fill, onLayer, strokes, paintedCanvas} from './painted.js';

const WOOD = '#8a6440', WOOD_DARK = '#5a4128', WOOD_LIGHT = '#c39a62', BARK = '#5e4630', STONE = '#7d8576', STONE_DARK = '#565d58',
  LEAF = '#4f7a34', LEAF_DARK = '#2f4f22', WATER = '#2f6f96', MOSS = '#5f8a3a', BONE = '#e3dcc6', CLOTH = '#b8323f', BRASS = '#e5c772';
const OUT = 'rgba(7, 10, 6, .75)';
const dot = (c, x, y, r, color) => { c.fillStyle = color; c.beginPath(); c.arc(x, y, r, 0, Math.PI * 2); c.fill(); };
const line = (c, color, width, ...pts) => {
  c.strokeStyle = color; c.lineWidth = width; c.beginPath(); c.moveTo(pts[0], pts[1]);
  for (let i = 2; i < pts.length; i += 2) c.lineTo(pts[i], pts[i + 1]); c.stroke();
};
const ground = (c, w, h, rx = w * .42) => onLayer(c, 'under', g => { g.fillStyle = 'rgba(4, 8, 4, .32)'; g.beginPath(); g.ellipse(w / 2, h - 1.6, rx, 2.4, 0, 0, Math.PI * 2); g.fill(); });
/** A flat dark patch on the ground (a wrong-way shadow), under the outlined art. */
const patch = (c, x, y, rx, ry, color, rot = 0) => onLayer(c, 'under', g => { g.fillStyle = color; g.beginPath(); g.ellipse(x, y, rx, ry, rot, 0, Math.PI * 2); g.fill(); });

// --- the kit -----------------------------------------------------------------------
export function stone(c, x, y, rx, ry, {color = STONE, moss = false} = {}) {
  const s = E(x, y, rx, ry);
  fill(c, s, color, {sheen: .42, shade: .55});
  strokes(c, s, 'rgba(20, 24, 20, .5)', Math.round(rx * ry / 4), {len: .9, angle: 0, spread: 3, seed: Math.round(x * 7 + y), alpha: .6});
  if (moss) { c.save(); c.beginPath(); s.path(c); c.clip(); fill(c, E(x - rx * .2, y - ry * .9, rx * .8, ry * .5), MOSS, {edge: 0, sheen: .35}); c.restore(); }
}
export function logEnd(c, x, y, r) {
  fill(c, E(x, y, r, r), BARK, {sheen: .25, shade: .5});
  fill(c, E(x, y, r * .78, r * .78), WOOD_LIGHT, {sheen: .3, shade: .3, edge: .35});
  c.strokeStyle = 'rgba(122, 85, 50, .8)'; c.lineWidth = .45;
  for (const k of [.52, .28]) { c.beginPath(); c.arc(x, y, r * k, 0, Math.PI * 2); c.stroke(); }
  dot(c, x, y, Math.max(.35, r * .1), WOOD_DARK);
}
export function log(c, x0, y0, x1, y1, r, {color = BARK, end = true} = {}) {
  const s = C(x0, y0, x1, y1, r);
  fill(c, s, color, {sheen: .3, shade: .55});
  strokes(c, s, 'rgba(30, 20, 12, .7)', Math.round(Math.hypot(x1 - x0, y1 - y0) * 1.2), {len: 2.6, angle: Math.atan2(y1 - y0, x1 - x0), spread: .2, seed: Math.round(x0 + y1 * 3), alpha: .7});
  if (end) logEnd(c, x1, y1, r * .95);
}
export function plank(c, x, y, w, h, {color = WOOD, nails = true} = {}) {
  const s = R(x, y, w, h, Math.min(1, h / 3));
  fill(c, s, color, {sheen: .3, shade: .5});
  strokes(c, s, 'rgba(40, 26, 14, .6)', Math.round(w * h / 6), {len: Math.min(4, w / 2), angle: w > h ? 0 : Math.PI / 2, spread: .1, seed: Math.round(x * 3 + y), alpha: .6});
  if (nails && w > 5) for (const nx of [x + 1.2, x + w - 1.2]) dot(c, nx, y + h / 2, .4, '#2a2018');
}
export function bush(c, x, y, r, {color = LEAF, berries = null, seed = 1} = {}) {
  const blobs = [[0, 0, 1], [-.62, .22, .7], [.62, .2, .72], [-.3, -.48, .62], [.34, -.44, .6], [0, .4, .66]];
  for (const [dx, dy, s] of blobs) {
    const b = E(x + dx * r, y + dy * r, r * .55 * s + .6, r * .5 * s + .5);
    fill(c, b, dy > .1 ? LEAF_DARK : color, {sheen: .38, shade: .5, edge: .45});
  }
  strokes(c, E(x, y, r, r * .9), '#9cc35a', Math.round(r * 2), {len: 1, angle: -Math.PI / 4, spread: 1.4, seed, alpha: .6});
  if (berries) for (let i = 0; i < Math.round(r * 1.4); i++) {
    const a = i * 2.39 + seed, d = r * (.25 + (i * 37 % 10) / 14);
    dot(c, x + Math.cos(a) * d, y + Math.sin(a) * d * .8, .95, berries); dot(c, x + Math.cos(a) * d - .3, y + Math.sin(a) * d * .8 - .3, .35, '#ffd0c8');
  }
}
export function tuft(c, x, y, h, color = '#6f9a3e') {
  c.lineCap = 'round';
  for (let i = -2; i <= 2; i++) line(c, i % 2 ? color : '#4b6f2c', .7, x + i * .7, y, x + i * 1.4 + (i > 0 ? .8 : -.2), y - h * (1 - Math.abs(i) * .18));
}
export function pool(c, cx, cy, rx, ry, {color = WATER, rim = true, glint = '#bfe8ff', moon = false} = {}) {
  if (rim) for (let i = 0; i < 10; i++) {
    const a = i / 10 * Math.PI * 2;
    stone(c, cx + Math.cos(a) * rx, cy + Math.sin(a) * ry, 1.9 + (i % 3) * .4, 1.4 + (i % 2) * .3, {color: i % 2 ? STONE : '#6d7468'});
  }
  const s = E(cx, cy, rx, ry);
  c.save(); c.beginPath(); s.path(c); c.clip();
  const g = c.createLinearGradient(0, cy - ry, 0, cy + ry);
  g.addColorStop(0, '#16384d'); g.addColorStop(.5, color); g.addColorStop(1, '#5a9cbf');
  c.fillStyle = g; c.fillRect(cx - rx, cy - ry, rx * 2, ry * 2);
  c.strokeStyle = 'rgba(191, 232, 255, .55)'; c.lineWidth = .5;
  for (const [dx, dy, w] of [[-.3, -.2, .3], [.25, .15, .25], [-.05, .35, .2]]) { c.beginPath(); c.ellipse(cx + dx * rx, cy + dy * ry, w * rx, w * ry * .35, 0, Math.PI, Math.PI * 2); c.stroke(); }
  if (moon) { dot(c, cx + rx * .2, cy - ry * .1, Math.min(rx, ry) * .35, 'rgba(240, 248, 255, .8)'); }
  dot(c, cx - rx * .4, cy - ry * .35, .6, glint);
  c.restore();
  c.strokeStyle = OUT; c.lineWidth = .7; c.beginPath(); s.path(c); c.stroke();
}
export function mushroom(c, x, y, s, cap = '#b8323f') {
  fill(c, R(x - s * .35, y - s * 1.2, s * .7, s * 1.2, s * .3), '#efe6cf', {sheen: .3, shade: .35});
  const top = {box: [x - s, y - s * 2.1, s * 2, s * 1.1], path: g => { g.ellipse(x, y - s * 1.1, s, s * .95, 0, Math.PI, Math.PI * 2); g.closePath(); }};
  fill(c, top, cap, {sheen: .5, shade: .4});
  for (const [dx, dy] of [[-.45, -.45], [.3, -.65], [.05, -.25]]) dot(c, x + dx * s, y - s * 1.1 + dy * s, s * .14, '#fff3e8');
}
export function hoofprint(c, x, y, s = 1, color = '#3b2a1c') {
  for (const d of [-1, 1]) { c.fillStyle = color; c.beginPath(); c.ellipse(x + d * .8 * s, y, .7 * s, 1.4 * s, d * .2, 0, Math.PI * 2); c.fill(); }
}
export function bootprint(c, x, y, s = 1, color = '#3b2a1c', rot = 0) {
  c.save(); c.translate(x, y); c.rotate(rot); c.fillStyle = color;
  c.beginPath(); c.ellipse(0, -1.2 * s, 1.2 * s, 1.6 * s, 0, 0, Math.PI * 2); c.fill();
  c.beginPath(); c.ellipse(0, 1.6 * s, .9 * s, 1 * s, 0, 0, Math.PI * 2); c.fill();
  c.restore();
}
export function pawprint(c, x, y, s = 1, color = '#3b2a1c') {
  c.fillStyle = color; c.beginPath(); c.ellipse(x, y + .6 * s, 1.1 * s, .9 * s, 0, 0, Math.PI * 2); c.fill();
  for (const d of [-1.1, -.4, .4, 1.1]) dot(c, x + d * s, y - .9 * s + Math.abs(d) * .3 * s, .42 * s, color);
}
export function bone(c, x0, y0, x1, y1, r = 1) {
  fill(c, C(x0, y0, x1, y1, r * .6), BONE, {sheen: .4, shade: .4});
  for (const [x, y] of [[x0, y0], [x1, y1]]) fill(c, E(x, y, r, r * .9), BONE, {sheen: .4, shade: .35, edge: .5});
}
export function skull(c, x, y, s = 1) {
  fill(c, E(x, y, 3 * s, 2.8 * s), BONE, {sheen: .45, shade: .45});
  fill(c, R(x - 1.8 * s, y + 1.4 * s, 3.6 * s, 2 * s, .8 * s), BONE, {sheen: .3, shade: .45});
  for (const d of [-1, 1]) dot(c, x + d * 1.15 * s, y + .2 * s, .8 * s, '#1a140e');
}
export function crate(c, x, y, w, h, {color = WOOD} = {}) {
  fill(c, R(x, y, w, h, .8), color, {sheen: .32, shade: .55});
  c.strokeStyle = 'rgba(40, 26, 14, .75)'; c.lineWidth = .5;
  for (let yy = y + h / 3; yy < y + h - .5; yy += h / 3) { c.beginPath(); c.moveTo(x + .5, yy); c.lineTo(x + w - .5, yy); c.stroke(); }
  plank(c, x + .3, y + .3, w - .6, 1.6, {color: WOOD_LIGHT, nails: false});
  line(c, WOOD_DARK, 1.1, x + 1, y + h - 1, x + w - 1, y + 2.2);
}
export function barrel(c, x, y, w, h) {
  const s = {box: [x, y, w, h], path: g => { g.moveTo(x + w * .12, y); g.quadraticCurveTo(x - w * .08, y + h / 2, x + w * .12, y + h); g.lineTo(x + w * .88, y + h);
    g.quadraticCurveTo(x + w * 1.08, y + h / 2, x + w * .88, y); g.closePath(); }};
  fill(c, s, WOOD, {sheen: .35, shade: .55});
  c.save(); c.beginPath(); s.path(c); c.clip();
  c.strokeStyle = 'rgba(40, 26, 14, .6)'; c.lineWidth = .45;
  for (let i = 1; i < 4; i++) { c.beginPath(); c.moveTo(x + w * i / 4, y); c.quadraticCurveTo(x + w * i / 4 + (i - 2) * .6, y + h / 2, x + w * i / 4, y + h); c.stroke(); }
  for (const k of [.18, .82]) { c.fillStyle = '#4a4f4a'; c.fillRect(x - 1, y + h * k - .6, w + 2, 1.2); c.fillStyle = 'rgba(220,225,215,.5)'; c.fillRect(x, y + h * k - .6, w, .35); }
  c.restore();
  fill(c, E(x + w / 2, y + .4, w * .38, 1), WOOD_DARK, {edge: .5});
}
export function sack(c, x, y, w, h, color = '#b59a6a') {
  const s = P([[x + w * .5, y], [x + w * .82, y + h * .3], [x + w, y + h * .8], [x + w * .8, y + h], [x + w * .2, y + h], [x, y + h * .8], [x + w * .18, y + h * .3]], true);
  fill(c, s, color, {sheen: .38, shade: .5});
  strokes(c, s, 'rgba(90, 66, 40, .55)', Math.round(w * h / 5), {len: 1.2, angle: Math.PI / 2, spread: .4, seed: Math.round(x + y), alpha: .5});
  line(c, '#6e5a3a', .7, x + w * .32, y + h * .28, x + w * .68, y + h * .28);
}
export function block(c, x, y, w, h, {color = STONE, moss = false} = {}) {
  fill(c, R(x, y, w, h, .9), color, {sheen: .38, shade: .55});
  strokes(c, R(x, y, w, h), 'rgba(20, 24, 20, .5)', Math.round(w * h / 5), {len: .8, angle: 0, spread: 3, seed: Math.round(x * 5 + y), alpha: .55});
  if (moss) fill(c, R(x + .4, y - .3, w * .6, 1.4, .7), MOSS, {edge: .4, sheen: .3});
}
export function cloth(c, points, color = CLOTH) {
  const s = P(points, true);
  fill(c, s, color, {sheen: .4, shade: .5});
  strokes(c, s, 'rgba(255, 220, 200, .3)', 6, {len: 2.5, angle: Math.PI / 2, spread: .5, seed: 3, alpha: .5});
}
export function reed(c, x, y, h, lean = 0) {
  line(c, '#6f8f3e', .7, x, y, x + lean, y - h);
  fill(c, C(x + lean * .9, y - h + 1.8, x + lean, y - h - .6, .7), '#7a5532', {edge: .4, sheen: .3});
}
export function fish(c, x, y, s = 1, dir = 1, color = '#8fb0c8') {
  c.save(); c.translate(x, y); c.scale(dir, 1);
  fill(c, E(0, 0, 2.6 * s, 1.1 * s), color, {sheen: .55, shade: .4});
  fill(c, P([[-2.2 * s, 0], [-3.8 * s, -1.1 * s], [-3.8 * s, 1.1 * s]]), color, {edge: .5});
  dot(c, 1.6 * s, -.25 * s, .3 * s, '#101820');
  c.restore();
}
export function glow(c, x, y, r, color) {
  onLayer(c, 'after', o => {
    const g = o.createRadialGradient(x, y, 0, x, y, r);
    g.addColorStop(0, color); g.addColorStop(1, 'rgba(0,0,0,0)');
    o.fillStyle = g; o.fillRect(x - r, y - r, r * 2, r * 2);
  });
}
export function sparkle(c, x, y, r, color = '#fff3bc') {
  line(c, color, .5, x - r, y, x + r, y); line(c, color, .5, x, y - r, x, y + r); dot(c, x, y, r * .3, '#ffffff');
}
export function smallTree(c, x, ground, h, {color = LEAF, gnarled = false} = {}) {
  log(c, x, ground, x + (gnarled ? 1.2 : 0), ground - h * .5, 1.6, {end: false});
  if (gnarled) { line(c, BARK, 1.1, x, ground - h * .35, x - 4, ground - h * .55); line(c, BARK, 1, x + 1, ground - h * .45, x + 4.6, ground - h * .6); }
  for (const [dx, dy, r] of [[0, -.72, .34], [-.32, -.56, .26], [.32, -.58, .26], [0, -.9, .24]])
    fill(c, E(x + dx * h, ground + dy * h, r * h, r * h * .85), dy < -.8 ? color : color, {sheen: .4, shade: .55});
  strokes(c, E(x, ground - h * .7, h * .5, h * .35), '#9cc35a', 14, {len: 1, angle: -Math.PI / 4, spread: 1.2, seed: 9, alpha: .55});
}
function rune(c, x, y, s, color) {
  line(c, color, .6, x - s, y - s, x, y + s, x + s, y - s); line(c, color, .6, x - s * .8, y, x + s * .8, y);
}

// --- encounter spots ------------------------------------------------------------------
/** [w, h, draw] per SPOTS key. */
export const SPOT_ART = {
  bramble_berries: [36, 28, (c, w, h) => { ground(c, w, h); bush(c, 12, 19, 7, {berries: '#b8323f', seed: 1}); bush(c, 24, 17, 8, {berries: '#b8323f', seed: 2}); }],
  fallen_branches: [40, 21, (c, w, h) => { ground(c, w, h); log(c, 4, 16, 33, 12, 2); line(c, BARK, 1.1, 14, 14, 11, 7); line(c, BARK, 1, 24, 13, 28, 6); log(c, 9, 18.5, 37, 17.5, 1.6); dot(c, 11, 7, 1.2, LEAF); dot(c, 28, 6, 1.2, LEAF); }],
  animal_tracks: [36, 21, (c, w, h) => { for (const [x, y] of [[5, 6], [12, 12], [19, 7], [26, 13], [31, 7], [8, 17], [22, 18]]) hoofprint(c, x, y, 1.1); }],
  gnarled_tree: [36, 35, (c, w, h) => { ground(c, w, h); smallTree(c, 18, h - 2, 30, {gnarled: true, color: '#5c7935'}); }],
  forest_spring: [40, 28, (c, w, h) => { pool(c, 20, 17, 15, 7); tuft(c, 4, 12, 5); tuft(c, 36, 13, 5); sparkle(c, 15, 4, 1.6, '#e8f5ff'); sparkle(c, 27, 6, 1.2, '#e8f5ff'); }],
  hanging_leaf: [36, 42, (c, w, h) => { line(c, '#6f8f3e', .6, 18, 0, 18, 9); glow(c, 18, 16, 10, 'rgba(226, 210, 255, .5)');
    fill(c, P([[18, 8], [24, 15], [18, 25], [12, 15]], true), '#55743c', {sheen: .5, shade: .45}); line(c, '#a9c97a', .5, 18, 9, 18, 24);
    for (const x of [10, 18, 26]) patch(c, x, 38, 3, 1, 'rgba(22, 19, 31, .6)'); sparkle(c, 18, 5, 1.6, '#e2d2ff'); }],
  backward_ripple: [36, 21, (c, w, h) => { pool(c, 18, 11, 16, 7.5, {rim: false, color: '#3c6f8f'});
    c.strokeStyle = '#d6c4ff'; c.lineWidth = .7; for (const r of [3, 6, 9]) { c.beginPath(); c.ellipse(18, 11, r * 1.4, r * .6, 0, 0, Math.PI * 2); c.stroke(); } sparkle(c, 18, 11, 1.4, '#e2d2ff'); }],
  double_shadow: [44, 28, (c, w, h) => { for (const d of [-1, 1]) patch(c, 22 + d * 13, 25, 8, 2.6, 'rgba(22, 19, 31, .7)', d * .15);
    stone(c, 22, 18, 9, 7, {moss: true}); }],
  split_shadow_tree: [44, 35, (c, w, h) => { for (const d of [-1, 1]) patch(c, 22 + d * 14, 32, 8, 2.4, 'rgba(22, 19, 31, .7)');
    smallTree(c, 22, h - 2, 30); sparkle(c, 9, 6, 1.4, '#e2d2ff'); sparkle(c, 35, 6, 1.4, '#e2d2ff'); }],
  mossy_stone: [36, 28, (c, w, h) => { ground(c, w, h); stone(c, 18, 17, 11, 9, {moss: true}); stone(c, 28, 23, 4, 3); tuft(c, 7, 26, 4); }],
  // Main story places.
  watch_post: [36, 32, (c, w, h) => { ground(c, w, h); plank(c, 4, 9, 2.6, 21, {nails: false}); plank(c, 29, 9, 2.6, 21, {nails: false});
    fill(c, P([[1, 11], [18, 3], [35, 11], [33, 13], [3, 13]]), '#6b6a62', {sheen: .35}); plank(c, 9, 17, 18, 9, {color: '#7a6a52'});
    fill(c, R(14, 19, 8, 5, .8), '#3b2a1c', {edge: .5}); line(c, '#e6d6aa', .6, 15, 21, 21, 21); line(c, '#e6d6aa', .6, 15, 22.6, 20, 22.6); }],
  grey_wall: [44, 42, (c, w, h) => { for (let i = 0; i < 4; i++) glow(c, 11 + i * 7.3, 24 - (i % 2) * 6, 10, 'rgba(214, 220, 230, .4)');
    for (let i = 0; i < 9; i++) line(c, 'rgba(238, 241, 246, .65)', .7, 3 + i * 4.6, h - 3, 5 + i * 4.6 + (i % 2 ? 2 : -2), 6 + (i % 3) * 3);
    sparkle(c, 14, 10, 1.3, '#eef1f6'); sparkle(c, 30, 15, 1.1, '#eef1f6'); }],
  dead_gate: [44, 42, (c, w, h) => { ground(c, w, h, 20); for (const x of [8, 36]) fill(c, P([[x - 4, h - 2], [x - 3, 9], [x, 6], [x + 3, 9], [x + 4, h - 2]], true), STONE, {sheen: .4, shade: .55});
    block(c, 5, 4, 34, 6, {moss: true}); fill(c, E(22, 7, 4, 2.6), '#2a2620', {edge: .5});
    for (const [x, y] of [[8, 18], [36, 18], [8, 28], [36, 28]]) rune(c, x, y, 1.3, '#9aa3ad'); }],
  elder: [24, 42, (c, w, h) => { ground(c, w, h, 7); line(c, WOOD_DARK, 1.2, 19, h - 2, 18, 9);
    fill(c, P([[7, h - 2], [9, 16], [12, 12], [15, 16], [17, h - 2]], true), '#6b5a44', {sheen: .35, shade: .55});
    fill(c, E(12, 11, 3.6, 3.8), '#d9b896', {sheen: .4}); fill(c, P([[7.6, 11], [12, 4.6], [16.4, 11], [12, 9]], true), '#8a7a62', {sheen: .35});
    line(c, '#e8dcc4', 1, 10.6, 14, 12, 18, 13.4, 14); }],
  old_carvings: [36, 28, (c, w, h) => { ground(c, w, h); block(c, 9, 5, 18, 21, {moss: true}); for (const [x, y] of [[14, 12], [22, 12], [18, 19]]) rune(c, x, y, 1.6, '#f2d27a'); glow(c, 18, 15, 9, 'rgba(242, 210, 122, .25)'); }],
  moonlit_pool: [36, 28, (c, w, h) => { pool(c, 18, 16, 14, 7.5, {moon: true, color: '#3c6f8f'}); sparkle(c, 12, 4, 1.4, '#e8f5ff'); sparkle(c, 25, 3, 1.8, '#e8f5ff'); }],
  mushroom_ring: [36, 28, (c, w, h) => { patch(c, 18, 19, 15, 6, 'rgba(160, 200, 120, .18)');
    for (let i = 0; i < 7; i++) { const a = Math.PI + i / 6 * Math.PI; mushroom(c, 18 + Math.cos(a) * 13, 20 + Math.sin(a) * -5.5, 2 + (i % 2) * .6, i % 3 ? '#b8323f' : '#c9864a'); }
    for (const x of [8, 18, 28]) mushroom(c, x, 26, 2.4, '#b8323f'); }],
  camp_packs: [36, 28, (c, w, h) => { ground(c, w, h); sack(c, 5, 8, 12, 18, '#9a6a3c'); sack(c, 20, 12, 11, 14, '#7a6a48'); line(c, '#3b2a1c', .8, 8, 12, 14, 12); }],
  camp_firepit: [36, 28, (c, w, h) => { ground(c, w, h); for (let i = 0; i < 8; i++) { const a = i / 8 * Math.PI * 2; stone(c, 18 + Math.cos(a) * 11, 20 + Math.sin(a) * 4.5, 2.4, 1.8); }
    fill(c, E(18, 20, 8, 3), '#2a2620', {edge: 0}); log(c, 12, 20, 23, 17, 1.4, {color: '#2e2620'}); dot(c, 17, 19, 1, '#e8742c'); dot(c, 20, 20, .7, '#ffd36a'); }],
  camp_bedroll: [36, 28, (c, w, h) => { ground(c, w, h); fill(c, R(4, 12, 28, 11, 4), '#4f6b34', {sheen: .4}); fill(c, C(6, 13.5, 6, 21.5, 3.6), '#6e8a4a', {sheen: .45}); line(c, '#3b2a1c', .8, 14, 12, 14, 23, 22, 12, 22, 23); }],
  tower_rubble: [36, 28, (c, w, h) => { ground(c, w, h); block(c, 4, 18, 9, 7); block(c, 13, 13, 10, 12, {moss: true}); block(c, 22, 19, 9, 6); stone(c, 30, 23, 3, 2.4); block(c, 9, 9, 7, 5); }],
  tower_stair: [36, 28, (c, w, h) => { ground(c, w, h); for (let i = 0; i < 4; i++) { const y = 21 - i * 5.5; block(c, 2 + i * 7, y, 32 - i * 7, 26 - y, {moss: i === 3}); } }],
  tower_armory: [36, 28, (c, w, h) => { ground(c, w, h); plank(c, 4, 3, 3, 22, {nails: false}); plank(c, 29, 3, 3, 22, {nails: false}); plank(c, 4, 5, 28, 2.4);
    for (const x of [10, 16, 22]) { line(c, '#3a2c20', 1, x, 7, x, 22); fill(c, P([[x - 1.3, 7.6], [x, 2.6], [x + 1.3, 7.6]]), '#b9bfae', {sheen: .55}); } plank(c, 4, 20, 28, 2.4); }],
  lumber_logs: [36, 28, (c, w, h) => { ground(c, w, h); for (const [x, y] of [[8, 20], [17, 20], [26, 20], [12.5, 12.5], [21.5, 12.5]]) logEnd(c, x, y, 4.6); }],
  lumber_shed: [36, 28, (c, w, h) => { ground(c, w, h); plank(c, 5, 8, 2.6, 18, {nails: false}); plank(c, 29, 8, 2.6, 18, {nails: false}); fill(c, P([[2, 9], [18, 2], [34, 9], [32, 11], [4, 11]]), '#6e5233', {sheen: .35});
    for (const [x, y] of [[11, 22], [17, 22], [23, 22], [14, 17], [20, 17]]) logEnd(c, x, y, 3); }],
  lumber_oak: [36, 28, (c, w, h) => { ground(c, w, h); log(c, 6, 18, 31, 16, 4.6); for (const [x, y] of [[4, 10], [8, 7]]) bush(c, x, y, 3, {seed: x}); fill(c, R(9, 21, 1.6, 4, .6), BARK); fill(c, R(25, 20, 1.6, 4.4, .6), BARK); }],
  lodge_racks: [32, 28, (c, w, h) => { ground(c, w, h); plank(c, 3, 5, 2.4, 21, {nails: false}); plank(c, 26, 5, 2.4, 21, {nails: false}); plank(c, 2, 5, 28, 2);
    for (const x of [8, 14, 20]) fill(c, P([[x, 7], [x + 4, 7], [x + 4.6, 18], [x + 2, 20], [x - .6, 18]], true), '#a6845d', {sheen: .35}); }],
  lodge_snares: [32, 28, (c, w, h) => { ground(c, w, h); for (const x of [8, 22]) { line(c, WOOD_DARK, 1.2, x, 26, x, 6); c.strokeStyle = '#c8b080'; c.lineWidth = .6; c.beginPath(); c.ellipse(x + 2, 14, 2.6, 3.4, 0, 0, Math.PI * 2); c.stroke(); }
    line(c, '#c8b080', .5, 2, 22, 30, 21); tuft(c, 15, 26, 4); }],
  lodge_trophies: [32, 28, (c, w, h) => { plank(c, 5, 8, 22, 12); for (const x of [10, 22]) { line(c, BONE, 1, x, 8, x - 2, 2, x - 4, 1); line(c, BONE, 1, x, 8, x + 2, 2, x + 4, 1); }
    skull(c, 16, 13, 1.2); line(c, WOOD_DARK, 1.2, 9, 20, 9, 27); line(c, WOOD_DARK, 1.2, 23, 20, 23, 27); }],
  shrine_altar: [36, 35, (c, w, h) => { ground(c, w, h); block(c, 3, 26, 30, 7); block(c, 7, 14, 6, 12); block(c, 23, 14, 6, 12); block(c, 6, 10, 24, 5, {moss: true});
    glow(c, 18, 7, 8, 'rgba(255, 220, 140, .6)'); sparkle(c, 15, 6, 1.4); sparkle(c, 21, 5, 1.8); }],
  shrine_offerings: [36, 28, (c, w, h) => { ground(c, w, h); for (const x of [10, 25]) { fill(c, R(x - 4, 16, 8, 8, 2), '#a6845d', {sheen: .35}); fill(c, E(x, 16, 4, 1.4), '#4a3626'); }
    dot(c, 10, 13.4, 1.8, BRASS); dot(c, 9.4, 12.8, .6, '#fff3bc'); fill(c, E(25, 13.6, 2.4, 2.2), '#b8323f', {sheen: .5}); glow(c, 18, 12, 10, 'rgba(255, 230, 160, .25)'); }],
  shrine_pillars: [28, 35, (c, w, h) => { ground(c, w, h); block(c, 6, 29, 16, 4); fill(c, R(9, 7, 10, 22, 1.6), STONE, {sheen: .4, shade: .55}); block(c, 7, 4, 14, 4, {moss: true});
    for (const y of [12, 19, 25]) rune(c, 14, y, 1.4, '#cfe6ff'); }],
  barrow_goods: [36, 28, (c, w, h) => { ground(c, w, h); fill(c, P([[3, 26], [8, 8], [28, 8], [33, 26]], true), '#4f6b34', {sheen: .35}); fill(c, R(11, 13, 14, 13, 1.2), '#2a1f16', {edge: .6});
    dot(c, 15, 22, 1.6, BRASS); dot(c, 20, 23, 1.3, BRASS); sparkle(c, 15, 21, 1.2); }],
  barrow_stones: [36, 28, (c, w, h) => { ground(c, w, h); for (const x of [6, 18, 30]) { fill(c, P([[x - 3.4, 26], [x - 2.6, 6], [x, 3.4], [x + 2.6, 6], [x + 3.4, 26]], true), STONE, {sheen: .4, shade: .55}); fill(c, E(x - .6, 6, 2, 1.2), MOSS, {edge: .3}); } }],
  barrow_bones: [36, 28, (c, w, h) => { ground(c, w, h); bone(c, 6, 22, 18, 19); bone(c, 16, 24, 30, 23); bone(c, 22, 18, 26, 26, .9); skull(c, 11, 14, 1.2); }],
  broken_branches: [36, 28, (c, w, h) => { ground(c, w, h); log(c, 3, 24, 15, 10, 1.6); log(c, 33, 24, 21, 11, 1.6); line(c, BARK, .9, 9, 17, 4, 12); bush(c, 18, 24, 4, {color: '#44602b', seed: 4}); }],
  cut_wood: [36, 28, (c, w, h) => { ground(c, w, h); for (const [x, y] of [[8, 21], [16, 21], [12, 14]]) logEnd(c, x, y, 4); fill(c, R(24, 17, 9, 9, 1.4), BARK, {sheen: .3}); fill(c, E(28.5, 17, 4.5, 1.6), WOOD_LIGHT, {edge: .5});
    line(c, '#4a3626', 1.2, 26, 16, 32, 6); fill(c, P([[30.4, 4.6], [34.6, 6], [33, 9.4]], true), '#b9bfae', {sheen: .55}); }],
  trampled_bushes: [36, 28, (c, w, h) => { ground(c, w, h); for (const x of [6, 30]) bush(c, x, 18, 4.6, {color: '#44602b', seed: x}); fill(c, E(18, 21, 11, 4), '#4a5a2c', {sheen: .2, edge: .3});
    for (const x of [10, 15, 20, 25]) line(c, '#6f8a3e', .8, x, 22, x + 2.6, 19.6); hoofprint(c, 14, 22, .9); hoofprint(c, 22, 20, .9); }],
  feeding_ground: [36, 28, (c, w, h) => { ground(c, w, h); bush(c, 18, 13, 8, {berries: '#b8323f', seed: 5}); for (const [x, y] of [[6, 24], [12, 26], [25, 25], [31, 23]]) hoofprint(c, x, y, .9); }],
  mushroom_dust: [36, 28, (c, w, h) => { glow(c, 18, 16, 14, 'rgba(220, 230, 170, .35)'); for (const [x, y, s] of [[7, 24, 2.2], [26, 25, 2.6], [17, 26, 1.8]]) mushroom(c, x, y, s, '#c9a85a');
    for (let i = 0; i < 12; i++) dot(c, 4 + (i * 53 % 28), 3 + (i * 31 % 17), .55, '#f4f0c8'); }],
  rotten_log: [36, 28, (c, w, h) => { ground(c, w, h); log(c, 5, 18, 30, 18, 5, {color: '#4a3a28'}); fill(c, E(16, 13.6, 7, 1.6), MOSS, {edge: .4, sheen: .35}); mushroom(c, 10, 14, 1.6, '#c9864a'); mushroom(c, 25, 14, 2, '#c9864a'); }],
  trail_marker: [36, 35, (c, w, h) => { ground(c, w, h, 8); log(c, 14, h - 2, 14, 6, 1.4, {end: false}); fill(c, P([[6, 5], [22, 5], [26, 8], [22, 11], [6, 11]]), WOOD_LIGHT, {sheen: .35}); fill(c, P([[24, 13], [8, 13], [4, 16], [8, 19], [24, 19]]), WOOD, {sheen: .35}); tuft(c, 12, h - 2, 4); }],
  looping_path: [36, 28, (c, w, h) => { c.strokeStyle = '#8e7445'; c.lineWidth = 3; c.lineCap = 'round'; c.beginPath(); c.moveTo(3, 24); c.bezierCurveTo(10, 4, 32, 4, 28, 16); c.bezierCurveTo(24, 26, 12, 20, 18, 12); c.stroke();
    c.strokeStyle = '#b19459'; c.lineWidth = 1; c.stroke(); for (const [x, y] of [[8, 14], [22, 8]]) bootprint(c, x, y, .6, '#5a4128', .6); }],
  map_scrap: [36, 28, (c, w, h) => { fill(c, P([[4, 6], [30, 4], [32, 22], [6, 24]], true), '#e6d6aa', {sheen: .4, shade: .4}); c.strokeStyle = '#8a6a44'; c.lineWidth = .6;
    c.beginPath(); c.moveTo(8, 18); c.bezierCurveTo(12, 8, 20, 18, 26, 9); c.stroke(); line(c, '#b8323f', .8, 24, 7, 28, 11); line(c, '#b8323f', .8, 28, 7, 24, 11); }],
  hidden_stash: [36, 28, (c, w, h) => { ground(c, w, h); crate(c, 10, 12, 16, 12, {color: '#6e5233'}); for (const x of [6, 30]) bush(c, x, 20, 4.4, {seed: x}); dot(c, 18, 18, 1.2, BRASS); }],
  reed_bed: [36, 28, (c, w, h) => { fill(c, E(18, 24, 17, 3.6), '#2f6f96', {sheen: .35, edge: .5}); for (let i = 0; i < 9; i++) reed(c, 4 + i * 3.4, 24, 13 + (i * 7 % 6), (i % 3 - 1) * 1.6); }],
  fishing_pool: [36, 28, (c, w, h) => { pool(c, 18, 16, 14, 7.5); fish(c, 16, 16, 1.1, 1); fish(c, 23, 19, .8, -1, '#c8a06a'); }],
  river_shallows: [36, 28, (c, w, h) => { pool(c, 18, 15, 17, 9, {rim: false}); for (const [x, y, r] of [[9, 12, 2.4], [24, 9, 2], [15, 20, 3], [28, 18, 2.2]]) stone(c, x, y, r, r * .75); }],
  fishing_net: [36, 28, (c, w, h) => { ground(c, w, h); const net = P([[3, 8], [33, 8], [31, 24], [5, 24]], true); fill(c, net, 'rgba(160, 140, 100, .25)', {sheen: .1, edge: .4});
    c.save(); c.beginPath(); net.path(c); c.clip(); c.strokeStyle = '#c8b080'; c.lineWidth = .5; for (let i = -30; i < 40; i += 3.4) { line(c, '#c8b080', .5, i, 0, i + 18, 28); line(c, '#c8b080', .5, i + 18, 0, i, 28); } c.restore();
    for (const x of [6, 18, 30]) dot(c, x, 8, 1.4, '#c39a62'); }],
  fish_scales: [36, 28, (c, w, h) => { for (let i = 0; i < 9; i++) { const x = 5 + (i * 29 % 26), y = 8 + (i * 17 % 16); fill(c, E(x, y, 1.6, 1.1, i), '#bcd6e6', {sheen: .7, shade: .3, edge: .4}); } sparkle(c, 12, 6, 1.2, '#ffffff'); sparkle(c, 26, 12, 1.2, '#ffffff'); }],
  busy_pool: [36, 28, (c, w, h) => { pool(c, 18, 16, 14, 7.5); fish(c, 13, 15, 1, 1); fish(c, 22, 18, 1, -1); fish(c, 20, 13, .8, 1, '#c8a06a'); }],
  ripples: [36, 21, (c, w, h) => { pool(c, 18, 11, 16, 8, {rim: false}); c.strokeStyle = 'rgba(220, 240, 255, .8)'; c.lineWidth = .6; for (const r of [2.5, 5.5, 9]) { c.beginPath(); c.ellipse(18, 11, r * 1.4, r * .55, 0, 0, Math.PI * 2); c.stroke(); } }],
  float_line: [36, 21, (c, w, h) => { pool(c, 18, 13, 17, 7, {rim: false}); line(c, '#e8dcc4', .4, 2, 4, 30, 12); fill(c, E(30, 12.6, 1.6, 1.6), '#b8323f', {sheen: .5}); fill(c, R(29.4, 10.6, 1.2, 1.4, .4), '#f1ecd2', {edge: .4}); }],
  fishing_platform: [36, 28, (c, w, h) => { fill(c, E(20, 24, 17, 3.6), '#2f6f96', {sheen: .35, edge: .5}); for (const x of [5, 15, 25]) plank(c, x, 12, 2.4, 13, {nails: false}); plank(c, 2, 9, 28, 3.4); line(c, '#8f6c41', 1, 26, 9, 33, 1); line(c, '#e8dcc4', .4, 33, 1, 34, 20); }],
  bootprints: [36, 28, (c, w, h) => { for (const [x, y, r] of [[6, 5, -.2], [13, 11, .2], [7, 17, -.2], [14, 23, .2], [24, 6, -.2], [31, 12, .2]]) bootprint(c, x, y, 1.2, '#3b2a1c', r); }],
  fishing_camp: [40, 28, (c, w, h) => { ground(c, w, h); fill(c, P([[2, 26], [12, 4], [22, 26]]), '#c8b080', {sheen: .4}); fill(c, P([[10, 26], [12, 14], [14, 26]]), '#3b2a1c', {edge: .4});
    line(c, WOOD_DARK, 1.2, 28, 26, 28, 4); line(c, WOOD_DARK, 1.2, 36, 26, 36, 4); line(c, WOOD_DARK, 1, 27, 6, 37, 6); fish(c, 30, 11, .9, 1); fish(c, 34, 16, .9, -1); }],
  fresh_footprints: [36, 28, (c, w, h) => { for (const [x, y, r] of [[5, 4, -.25], [11, 8, .25], [17, 12, -.25], [23, 16, .25], [29, 20, -.25]]) bootprint(c, x, y, 1.1, '#2a1f16', r); tuft(c, 5, 26, 4); tuft(c, 29, 27, 3.6); }],
  hidden_ford: [36, 28, (c, w, h) => { pool(c, 18, 14, 17, 11, {rim: false}); for (const [x, y] of [[5, 16], [11, 12], [17, 16], [23, 12], [29, 16]]) stone(c, x, y, 2.4, 1.6, {color: '#8d9585'}); }],
  dead_tree: [36, 35, (c, w, h) => { ground(c, w, h); log(c, 18, h - 2, 18, 14, 2.2, {color: '#625a4c', end: false});
    for (const [x0, y0, x1, y1] of [[18, 16, 8, 4], [18, 18, 28, 5], [12, 10, 10, 2], [24, 11, 30, 8], [18, 14, 19, 2]]) line(c, '#837a68', 1.2, x0, y0, x1, y1); }],
  deer_trail: [40, 28, (c, w, h) => { for (const [x, y] of [[4, 5], [10, 9], [16, 6], [22, 11], [28, 8], [34, 13], [30, 20]]) hoofprint(c, x, y, 1); log(c, 3, 23, 13, 21, 1.4); }],
  deer: [40, 42, (c, w, h) => { ground(c, w, h, 14);
    for (const x of [9, 25]) { fill(c, C(x, 26, x - .4, 39, 1.3), '#7a5532', {shade: .5}); }
    fill(c, P([[6, 20], [24, 18], [30, 21], [29, 28], [8, 28]], true), '#9a6a3c', {sheen: .35, shade: .5});
    fill(c, E(7.4, 24, 3, 3.4), '#e8dcc4', {edge: .4});                                                  // white tail
    for (const x of [12, 28]) { fill(c, C(x, 26, x + .4, 39.5, 1.3), '#9a6a3c', {shade: .5}); fill(c, E(x + .5, 40, 1.4, .8), '#2a1f16'); }
    fill(c, C(27, 21, 31, 12, 2.6), '#9a6a3c', {sheen: .35});
    fill(c, P([[29, 9], [36, 10.6], [37, 13], [31, 14.4]], true), '#a8784a', {sheen: .4});
    dot(c, 36.8, 11.4, .8, '#101010'); dot(c, 32.4, 10.6, .7, '#101010');
    for (const s of [-1, 1]) line(c, '#d9c8a4', .9, 30 + s, 8.6, 29 + s * 3, 3, 30 + s * 4, 1); line(c, '#d9c8a4', .7, 30, 5.6, 27, 4); }],
  wayside_shrine: [36, 42, (c, w, h) => { ground(c, w, h); block(c, 9, 34, 18, 6); fill(c, R(11, 18, 14, 16, 1.4), STONE, {sheen: .4, shade: .55}); fill(c, R(14, 21, 8, 9, 3.4), '#2a2f2a', {edge: .6});
    glow(c, 18, 26, 6, 'rgba(255, 220, 140, .8)'); dot(c, 18, 27, 1.4, '#ffe7a0'); fill(c, P([[7, 19], [18, 9], [29, 19]]), '#6e5233', {sheen: .35}); line(c, '#d9c8a4', 1, 18, 2, 18, 9); line(c, '#d9c8a4', 1, 15.4, 4.6, 20.6, 4.6); }],
};
export function spotCanvas(key) {
  const art = SPOT_ART[key];
  if (!art) return null;
  const [w, h, draw] = art;
  return paintedCanvas(`spot|${key}`, w, h, c => draw(c, w, h));
}

// --- site structures (art.js STRUCTURE_ART glyphs) ----------------------------------------
/** [w, h, draw]: bottom-aligned on the tile and centred on it, like the cell structures. */
export const STRUCTURE_PAINT = {
  A: [34, 30, (c, w, h) => { ground(c, w, h); cloth(c, [[2, 28], [17, 2], [32, 28]], '#c8b080'); fill(c, P([[13, 28], [17, 12], [21, 28]]), '#4a3626', {edge: .5}); line(c, '#6e5a3a', .8, 17, 2, 17, 0); line(c, '#6e5a3a', .5, 2, 28, 0, 29); }],
  M: [34, 30, (c, w, h) => { ground(c, w, h); block(c, 2, 18, 12, 10); block(c, 13, 12, 12, 16, {moss: true}); block(c, 24, 20, 8, 8); block(c, 6, 9, 9, 8); stone(c, 30, 26, 2.4, 1.8); }],
  L: [30, 30, (c, w, h) => { ground(c, w, h); log(c, 2, 25, 26, 25, 3.6); log(c, 4, 18, 26, 18, 3.4); log(c, 6, 11.4, 24, 11.4, 3); }],
  S: [26, 26, (c, w, h) => { ground(c, w, h); fill(c, R(5, 9, 16, 15, 2.4), BARK, {sheen: .35, shade: .55}); strokes(c, R(5, 9, 16, 15), '#2e2317', 20, {len: 3, seed: 2});
    for (const d of [-1, 1]) fill(c, P([[13 + d * 6, 22], [13 + d * 11, 25], [13 + d * 7, 25]]), BARK, {edge: .5}); fill(c, E(13, 9.4, 8, 2.8), WOOD_LIGHT, {edge: .5}); c.strokeStyle = 'rgba(122,85,50,.8)'; c.lineWidth = .45;
    for (const r of [5.4, 3]) { c.beginPath(); c.ellipse(13, 9.4, r, r * .35, 0, 0, Math.PI * 2); c.stroke(); } }],
  U: [58, 50, (c, w, h) => { ground(c, w, h, 27); for (let x = 6; x < 52; x += 4.6) plank(c, x, 22, 4.6, 26, {nails: false, color: x % 9 < 4.6 ? WOOD : '#7a5532'});
    fill(c, R(22, 31, 9, 17, 1), '#2a1f16', {edge: .6}); fill(c, R(37, 28, 8, 7, 1), '#3a2c20', {edge: .6}); glow(c, 41, 31.4, 6, 'rgba(255, 210, 120, .5)');
    const roof = P([[1, 25], [29, 4], [57, 25], [53, 27], [5, 27]]); fill(c, roof, '#6e5233', {sheen: .4, shade: .5});
    c.save(); c.beginPath(); roof.path(c); c.clip(); for (let y = 8; y < 28; y += 3) line(c, 'rgba(40, 26, 14, .6)', .6, 0, y, 58, y); c.restore(); log(c, 28, 5, 30, 1, 1.2, {end: false}); }],
  R: [32, 34, (c, w, h) => { ground(c, w, h); for (const x of [3, 27]) plank(c, x, 4, 2.6, 28, {nails: false}); plank(c, 2, 4, 28, 2.2);
    fill(c, P([[8, 7], [24, 7], [22, 22], [10, 22]], true), '#a6845d', {sheen: .4}); strokes(c, R(8, 7, 16, 15), '#6e4a2c', 14, {len: 3, angle: Math.PI / 2, seed: 4}); }],
  P: [24, 42, (c, w, h) => { ground(c, w, h, 9); block(c, 3, 36, 18, 5); fill(c, R(6, 8, 12, 28, 1.6), STONE, {sheen: .45, shade: .55}); block(c, 4, 4, 16, 5, {moss: true});
    for (const y of [14, 22, 30]) rune(c, 12, y, 1.6, '#cfe6ff'); }],
  Q: [34, 36, (c, w, h) => { ground(c, w, h); block(c, 2, 28, 30, 7); fill(c, P([[5, 28], [7, 14], [15, 14], [16.4, 28]]), STONE, {sheen: .4}); fill(c, P([[18, 28], [19, 14], [27, 14], [29, 28]]), STONE, {sheen: .4});
    glow(c, 17, 9, 9, 'rgba(255, 230, 140, .7)'); fill(c, P([[17, 3], [20, 8], [17, 13], [14, 8]]), BRASS, {sheen: .6, shade: .3}); }],
  B: [64, 38, (c, w, h) => { ground(c, w, h, 30); const mound = P([[1, 37], [8, 16], [22, 4], [42, 4], [56, 16], [63, 37]], true); fill(c, mound, '#4f6b34', {sheen: .35, shade: .55});
    strokes(c, mound, '#86a85a', 50, {len: 1.6, angle: -Math.PI / 2, spread: .5, seed: 6, alpha: .6}); fill(c, R(24, 19, 16, 18, 4), '#1a140e', {edge: .7});
    block(c, 22, 17, 20, 3.4); block(c, 21, 19, 3.6, 18); block(c, 40, 19, 3.6, 18); }],
  I: [22, 36, (c, w, h) => { ground(c, w, h, 8); fill(c, P([[4, 35], [3, 10], [7, 2], [14, 1.4], [18, 8], [18, 35]], true), STONE, {sheen: .45, shade: .6, light: [.25, .15]});
    fill(c, E(9, 5, 5, 2.4), MOSS, {edge: .3, sheen: .4}); rune(c, 10.6, 18, 2, '#cfe6ff'); tuft(c, 3, 35, 4); tuft(c, 19, 35, 4); }],
};
export function structureCanvas(glyph) {
  const art = STRUCTURE_PAINT[glyph];
  if (!art) return null;
  const [w, h, draw] = art;
  return {canvas: paintedCanvas(`site|${glyph}`, w, h, c => draw(c, w, h)), w, h};
}

// --- camp building parts and the ambush wreckage ------------------------------------------
/** [w, h, draw] per BUILDING_PARTS / AMBUSH key; drawn bottom-left where the cell part was. */
export const PART_PAINT = {
  rack: [28, 35, (c, w, h) => { for (const x of [2, 24]) plank(c, x, 2, 2.4, 33, {nails: false}); plank(c, 1, 2, 26, 2.2);
    for (const x of [6, 13, 19]) fill(c, P([[x, 4], [x + 5, 4], [x + 5.4, 16], [x + 2.5, 18], [x - .4, 16]], true), '#a6845d', {sheen: .35}); }],
  bench: [40, 28, (c, w, h) => { plank(c, 1, 9, 38, 3.6); for (const x of [3, 34]) plank(c, x, 12, 3, 16, {nails: false}); plank(c, 3, 21, 34, 2, {nails: false});
    fill(c, R(9, 3, 2, 6, .6), '#5f6660', {edge: .5}); fill(c, R(7, 2, 6, 2.2, .6), '#b9bfae', {sheen: .5}); crate(c, 26, 14, 8, 7); dot(c, 22, 7, 1.6, BRASS); }],
  grind: [20, 21, (c, w, h) => { fill(c, E(10, 10, 9, 5), STONE, {sheen: .45}); fill(c, E(10, 8, 6.4, 2.6), '#a3ab9b', {sheen: .5}); dot(c, 10, 8, 1.2, '#3a3c34'); line(c, WOOD, 1.2, 10, 8, 15, 2); for (const x of [4, 16]) plank(c, x - 1, 13, 2.4, 8, {nails: false}); }],
  stump: [16, 21, (c, w, h) => { fill(c, R(2, 7, 12, 13, 2), BARK, {sheen: .35}); fill(c, E(8, 7.4, 6, 2.2), WOOD_LIGHT, {edge: .5}); line(c, '#4a3626', 1.1, 9, 7, 12, .5); fill(c, P([[10.6, 0], [14.6, 1.4], [12.4, 4]], true), '#b9bfae', {sheen: .55}); }],
  chest: [36, 28, (c, w, h) => { fill(c, R(2, 10, 32, 17, 1.4), '#7a5532', {sheen: .35, shade: .55}); fill(c, P([[2, 11], [5, 3], [31, 3], [34, 11]], true), '#8f6c41', {sheen: .45});
    for (const x of [7, 27]) fill(c, R(x, 3, 2.4, 24, .4), '#5f6660', {sheen: .5, edge: .5}); fill(c, R(15.4, 11, 5.2, 6, 1), BRASS, {sheen: .6, shade: .3}); dot(c, 18, 14.6, .8, '#3a2c20'); }],
  barrel: [16, 28, (c, w, h) => barrel(c, 1, 2, 14, 25)],
  rope: [12, 14, (c, w, h) => { for (const r of [5, 3.6, 2.2]) { c.strokeStyle = '#8e3a30'; c.lineWidth = 1.4; c.beginPath(); c.ellipse(6, 8, r, r * .75, 0, 0, Math.PI * 2); c.stroke(); c.strokeStyle = '#e0a080'; c.lineWidth = .4; c.stroke(); } }],
  sack: [12, 21, (c, w, h) => sack(c, 0, 2, 12, 18)],
  wagon: [88, 49, (c, w, h) => { fill(c, P([[4, 34], [58, 34], [86, 44], [80, 47], [56, 40], [4, 40]]), '#4a3626', {sheen: .25});
    for (let x = 4; x < 58; x += 6.6) plank(c, x, 12, 6.6, 22, {nails: true, color: x % 13 < 6.6 ? '#7a5532' : '#8f6c41'});
    fill(c, P([[58, 12], [86, 36], [86, 44], [58, 34]]), '#6e5233', {sheen: .3}); plank(c, 4, 9, 54, 3.4, {color: '#b59050'});
    for (const x of [10, 30, 50]) line(c, '#3b2a1c', 1.4, x, 9, x, 2); wheel(c, 20, 40, 8.4); log(c, 76, 44, 88, 47, 1.2, {end: false}); }],
  tipped: [80, 49, (c, w, h) => { fill(c, R(4, 10, 68, 22, 2), '#7a5532', {sheen: .35, shade: .55}); for (let x = 8; x < 70; x += 8) line(c, '#3b2a1c', .7, x, 10, x, 32);
    plank(c, 4, 30, 68, 4, {color: '#b59050'}); wheel(c, 18, 9, 7); wheel(c, 54, 9, 7);
    cloth(c, [[6, 34], [30, 33], [56, 34], [74, 30], [78, 40], [60, 46], [36, 44], [14, 47], [8, 40]], CLOTH); }],
  wheel: [20, 9, (c, w, h) => wheel(c, 10, 4.5, 4.2)],
  crate: [16, 14, (c, w, h) => crate(c, 1, 1, 14, 12)],
  crateDark: [16, 14, (c, w, h) => crate(c, 1, 1, 14, 12, {color: '#5a4128'})],
  plank: [20, 7, (c, w, h) => plank(c, 1, 2, 18, 3.4, {color: '#b59050'})],
  plankShort: [12, 7, (c, w, h) => plank(c, 1, 2, 10, 3.4, {color: '#b59050'})],
  plankTilted: [20, 21, (c, w, h) => { c.save(); c.translate(10, 10.5); c.rotate(-.6); plank(c, -9, -1.7, 18, 3.4, {color: '#b59050'}); c.restore(); }],
  spoke: [8, 7, (c, w, h) => { line(c, '#3b2a1c', 1.4, 1, 4, 6, 4); dot(c, 6.4, 4, 1.4, '#9b7944'); }],
  arrow: [24, 7, (c, w, h) => { line(c, '#3b2a1c', 1, 2, 3.5, 20, 3.5); fill(c, P([[19, 1.6], [23.6, 3.5], [19, 5.4]]), '#b9bfae', {sheen: .5}); for (const d of [-1, 1]) line(c, '#e8dcc4', .8, 1, 3.5 + d * 1.6, 4, 3.5); }],
  ambushSack: [20, 14, (c, w, h) => sack(c, 1, 1, 18, 12, '#9b7944')],
  tornCloth: [24, 14, (c, w, h) => cloth(c, [[1, 2], [22, 1], [20, 8], [15, 12], [11, 8], [7, 13], [2, 8]], CLOTH)],
};
function wheel(c, x, y, r) {
  c.strokeStyle = '#2a1f16'; c.lineWidth = 2.6; c.beginPath(); c.ellipse(x, y, r, r, 0, 0, Math.PI * 2); c.stroke();
  c.strokeStyle = '#9b7944'; c.lineWidth = 1.6; c.stroke();
  for (let i = 0; i < 6; i++) { const a = i / 6 * Math.PI * 2; line(c, '#7a5532', .9, x, y, x + Math.cos(a) * r, y + Math.sin(a) * r); }
  fill(c, E(x, y, r * .26, r * .26), '#5f6660', {sheen: .5, edge: .5});
}
export function partCanvas(key) {
  const art = PART_PAINT[key];
  if (!art) return null;
  const [w, h, draw] = art;
  return {canvas: paintedCanvas(`part|${key}`, w, h, c => draw(c, w, h)), w, h};
}
