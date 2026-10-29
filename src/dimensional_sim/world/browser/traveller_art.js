/** The avatar: a bound traveller in plain undyed wraps, painted in layers (tools/art_lab/scene_lab.js,
 * docs/design/COMBAT_STATS_ART_PLAN.md step 7).
 *
 * A pose is a set of joints (head, shoulders, elbows, wrists, hips, knees, ankles, feet) in the
 * 32 x 40 hero frame; the body is painted against those joints, then one layer per worn gear slot
 * (body, head) against the same joints, so gear follows every pose. Seen three-quarters, facing
 * right (west is mirrored by the caller); `back` paints the same figure seen from behind.
 *
 * Gear looks are keyed by catalog item id (an art key, like WEAPON_LOOKS); unknown ids draw nothing.
 * Presentation only and deterministic; painted once per pose and cached by painted.js.
 */
import {E, HERO_H, HERO_W, P, R, T, paintedCanvas} from './painted.js';

const COLD = [214, 226, 236], DEEP = [9, 12, 17];
const CLOTH = {base: '#56544e', light: '#8d8f8c', dark: '#32312d', deep: '#1d1d1b', soot: '#29251f'};
const SKIN = {base: '#9f8a7c', dark: '#68564c', deep: '#352a25', light: '#c9b8aa'};
const HIDE = {base: '#4a3a2f', dark: '#2a211b', light: '#6c5848'};
const HAIR = '#17130f', ROPE = '#6a5e4d', INK = '#06070a', IRON = '#8d9496';
const hex = h => { const n = parseInt(h.slice(1), 16); return [n >> 16 & 255, n >> 8 & 255, n & 255]; };
const rgba = (c, a) => { const [r, g, b] = Array.isArray(c) ? c : hex(c); return `rgba(${r}, ${g}, ${b}, ${a})`; };

// ---- the kit: a cold key light from the upper left, deep shade, an ink edge ---------------------
function paint(c, shape, base, {key = .28, shade = .7, light = [.22, .18], edge = .5, rim = 0} = {}) {
  const [x, y, w, h] = shape.box;
  c.save(); c.beginPath(); shape.path(c); c.fillStyle = base; c.fill(); c.clip();
  const lx = x + w * light[0], ly = y + h * light[1], r = Math.max(w, h) * 1.15 + 1;
  const g = c.createRadialGradient(lx, ly, 0, lx, ly, r);
  g.addColorStop(0, rgba(COLD, key)); g.addColorStop(.35, rgba(COLD, 0));
  g.addColorStop(.55, rgba(DEEP, 0)); g.addColorStop(1, rgba(DEEP, shade));
  c.fillStyle = g; c.fillRect(x - 1, y - 1, w + 2, h + 2);
  if (rim) { c.strokeStyle = rgba(COLD, rim); c.lineWidth = .5; c.translate(.35, .2); c.beginPath(); shape.path(c); c.stroke(); }
  c.restore();
  if (edge) { c.save(); c.strokeStyle = rgba(INK, edge); c.lineWidth = .35; c.beginPath(); shape.path(c); c.stroke(); c.restore(); }
}
function occlude(c, x, y, rx, ry, a = .55) {
  c.save(); c.translate(x, y); c.scale(1, ry / rx);
  const g = c.createRadialGradient(0, 0, 0, 0, 0, rx);
  g.addColorStop(0, rgba(DEEP, a)); g.addColorStop(1, rgba(DEEP, 0));
  c.fillStyle = g; c.beginPath(); c.arc(0, 0, rx, 0, Math.PI * 2); c.fill(); c.restore();
}
function bands(c, shape, n, angle, color, alpha, width = .22, curve = 0) {
  const [x, y, w, h] = shape.box;
  c.save(); c.beginPath(); shape.path(c); c.clip();
  const step = h / (n + 1), t = Math.tan(angle) * w;
  c.strokeStyle = rgba(color, alpha); c.lineWidth = width;
  for (let i = 1; i <= n; i++) { const yy = y + i * step; c.beginPath(); c.moveTo(x - 1, yy - t / 2); c.quadraticCurveTo(x + w / 2, yy + curve, x + w + 1, yy + t / 2); c.stroke(); }
  c.restore();
}
function grain(c, shape, color, count, {len = 1.2, angle = Math.PI / 2, spread = .6, width = .16, seed = 1, alpha = .45} = {}) {
  const [x, y, w, h] = shape.box;
  c.save(); c.beginPath(); shape.path(c); c.clip(); c.strokeStyle = rgba(color, alpha); c.lineWidth = width;
  let s = seed * 9301 + 49297; const rnd = () => { s = (s * 9301 + 49297) % 233280; return s / 233280; };
  c.beginPath();
  for (let i = 0; i < count; i++) { const px = x + rnd() * w, py = y + rnd() * h, a = angle + (rnd() - .5) * spread, l = len * (.5 + rnd()); c.moveTo(px, py); c.lineTo(px + Math.cos(a) * l, py + Math.sin(a) * l); }
  c.stroke(); c.restore();
}
function stroke(c, pts, color, width, alpha = 1) {
  c.save(); c.strokeStyle = rgba(color, alpha); c.lineWidth = width; c.lineCap = 'round';
  c.beginPath(); c.moveTo(...pts[0]); for (const p of pts.slice(1)) c.lineTo(...p); c.stroke(); c.restore();
}
const dot = (c, x, y, r, color) => { c.fillStyle = color; c.beginPath(); c.arc(x, y, r, 0, Math.PI * 2); c.fill(); };

// ---- poses -------------------------------------------------------------------------------------
/** Joints for standing (`walk` null: `breath` 0..1), walking or running (`walk`/`run`: the step
 * phase 0..1). Pure. */
export function travellerPose({walk = null, run = null, breath = 0} = {}) {
  if (run !== null) return runPose(run);
  const br = Math.sin(breath * Math.PI * 2) * .35;
  if (walk === null) return {br, sway: Math.sin(breath * Math.PI * 2 + 1.1), lean: 0,
    head: [17.7, 5.9 + br * .4], shoulderF: [13.7, 11.5 + br], shoulderN: [20.5, 11 + br],
    elbowF: [13.1, 16.6 + br * .6], elbowN: [21.6, 16.2 + br * .6], wristF: [13.9, 21.1 + br * .3], wristN: [21.5, 21 + br * .3],
    hipF: [15.2, 21], hipN: [18.4, 21.6], kneeF: [15.6, 29.3], kneeN: [18.5, 30], ankleF: [14.6, 36.4], ankleN: [18.6, 37],
    footF: [15.3, 37.9], footN: [19.6, 38.7]};
  const a = walk * Math.PI * 2, s = Math.sin(a), bob = -Math.abs(Math.cos(a)) * .55 + .3;
  const leg = (hx, hy, phase) => {   // a stride: the foot reaches forward, plants, pushes back, lifts
    const q = Math.sin(phase), lift = Math.max(0, Math.cos(phase)) * 1.5;
    return {knee: [hx + q * 2 + .6 + lift * .4, hy + 8.2 - lift * .8], ankle: [hx + q * 3.4, hy + 15.6 - lift], foot: [hx + q * 3.4 + .8, hy + 17.1 - lift]};
  };
  const F = leg(15.2, 21 + bob, a + Math.PI), N = leg(18.2, 21.4 + bob, a);
  return {br: bob, sway: -Math.cos(a) * .8 - .6, lean: .8,
    head: [18.4, 6 + bob], shoulderF: [14.2, 11.3 + bob], shoulderN: [20.8, 11.2 + bob],
    elbowF: [13.6 + s * 1.8, 16.4 + bob], elbowN: [20.6 - s * 1.4, 16.3 + bob],
    wristF: [14 + s * 3.2, 20.6 + bob], wristN: [21 - s * 2.6, 20.8 + bob],
    hipF: [15.2, 21 + bob], hipN: [18.2, 21.4 + bob], kneeF: F.knee, kneeN: N.knee, ankleF: F.ankle, ankleN: N.ankle,
    footF: F.foot, footN: N.foot};
}
/** A run: the body leans into it, knees drive high, elbows pump, the cloak streams behind. */
function runPose(phase) {
  const a = phase * Math.PI * 2, s = Math.sin(a);
  const bob = -Math.abs(s) * 1.2 + .5;
  const lean = (x, y) => [x + (22 - y) * .14, y];
  const leg = (hx, hy, q) => {
    const reach = Math.sin(q), tuck = Math.max(0, Math.cos(q));
    const knee = [hx + reach * 3.4 + tuck * 2.4, hy + 8 - tuck * 3.4];
    const ankle = [hx + reach * 5.4 - tuck * 2, hy + 15.4 - tuck * 3.8];
    return {knee, ankle, foot: [ankle[0] + .9, ankle[1] + 1.4]};
  };
  const F = leg(15.2, 21 + bob, a + Math.PI), N = leg(18.2, 21.4 + bob, a);
  const arm = (sx, sy, w) => {
    const elbow = [sx + w * 2.2 - .4, sy + 4.4 - Math.max(0, w) * .8];
    return {elbow, wrist: [elbow[0] + 2.2 + w * .5, elbow[1] + (w > 0 ? -.7 : 1)]};
  };
  const shF = lean(14.4, 11.4 + bob), shN = lean(21, 11.2 + bob);
  const aF = arm(...shF, s), aN = arm(...shN, -s);
  return {br: bob, sway: -3.2 + Math.cos(a) * .6, lean: .14,
    head: lean(18.8, 6.2 + bob), shoulderF: shF, shoulderN: shN,
    elbowF: aF.elbow, elbowN: aN.elbow, wristF: aF.wrist, wristN: aN.wrist,
    hipF: [15.2, 21 + bob], hipN: [18.2, 21.4 + bob], kneeF: F.knee, kneeN: N.knee, ankleF: F.ankle, ankleN: N.ankle,
    footF: F.foot, footN: N.foot};
}
/** Down on one knee at work (crouch, kneel) or sitting (sit), drawn in the same 40 px frame; the
 * caller shifts it up into the 26 px compact frame. */
export function travellerLowPose(kind = 'crouch') {
  if (kind === 'sit') return {br: 0, sway: .4, lean: 0,
    head: [17.4, 18.6], shoulderF: [13.8, 24], shoulderN: [20.4, 23.6],
    elbowF: [15.2, 28.6], elbowN: [21.8, 28.2], wristF: [19.2, 30.4], wristN: [23.4, 30.2],
    hipF: [15, 33.4], hipN: [18.2, 33.8], kneeF: [21.6, 31.4], kneeN: [23.4, 32], ankleF: [21, 37.2], ankleN: [24.6, 37.6],
    footF: [22, 38.2], footN: [25.6, 38.6]};
  return {br: 0, sway: .2, lean: .5,   // the far knee on the ground, the near one up
    head: [19, 15.4], shoulderF: [15, 21], shoulderN: [21.4, 20.6],
    elbowF: [17.6, 25.4], elbowN: [23, 25], wristF: [21.4, 27.4], wristN: [24.6, 28.6],
    hipF: [15.2, 30], hipN: [18.2, 30.4], kneeF: [21.4, 28.6], kneeN: [15.6, 37.4], ankleF: [21, 36.6], ankleN: [10.6, 37.6],
    footF: [22, 37.8], footN: [9.4, 38.4]};
}

// ---- gear layers (catalog item ids are art keys) ------------------------------------------------
/** Body slot: painted over the torso, under the near arm. */
const BODY_LOOKS = Object.freeze({
  hide_wrap: (c, torso) => {             // a pale tanned hide lashed round the chest with cord
    paint(c, torso, HIDE.light, {shade: .6, key: .35, light: [.18, .15], rim: .4});
    grain(c, torso, HIDE.dark, 46, {len: 1, angle: .3, spread: .8, width: .2, seed: 9, alpha: .7});
    bands(c, torso, 3, -.5, '#b8a888', .95, .4, .4);
  },
  padded_jerkin: (c, torso) => {         // quilted cloth: rows of stitched pads, lighter than the wraps
    paint(c, torso, '#77715f', {shade: .6, key: .35, light: [.18, .15], rim: .4});
    bands(c, torso, 5, -.1, '#2b2924', .95, .4, .4);
    grain(c, torso, '#b9b4a2', 22, {len: .6, angle: Math.PI / 2, spread: .2, width: .18, seed: 13, alpha: .6});
  },
  studded_wrap: (c, torso, j) => {       // the hide wrap set with iron studs
    BODY_LOOKS.hide_wrap(c, torso, j);
    const [x, y, w, h] = torso.box;
    for (let row = 0; row < 3; row++) for (let col = 0; col < 3; col++) {
      const sx = x + w * (.22 + col * .26), sy = y + h * (.22 + row * .26);
      dot(c, sx, sy, .6, '#1a1c1d'); dot(c, sx, sy, .48, IRON); dot(c, sx - .15, sy - .15, .2, 'rgba(235, 240, 242, .95)');
    }
  },
});
/** Head slot: painted last, over the head anchor. */
const HEAD_LOOKS = Object.freeze({
  hood: (c, j, back) => hood(c, j, back),
});
export const GEAR_LOOK_IDS = Object.freeze([...Object.keys(BODY_LOOKS), ...Object.keys(HEAD_LOOKS)]);

// ---- the figure --------------------------------------------------------------------------------
/** Paint the traveller at joints `j`. `back`: seen from behind (facing north). `worn`: {body, head}
 * catalog item ids (or missing). */
export function paintTraveller(c, j, {back = false, worn = {}} = {}) {
  const sw = j.sway * .5;
  const [sx, sy] = j.shoulderF, st = Math.max(0, -j.sway - 1.5);   // st: how far the cloak streams out
  const cloak = P([[sx - .7, sy - .4], [sx + 2.3, sy - 1], [sx + 2.4, sy + 7], [16 + sw * .4, 25 - st], [15.2 + sw * .9, 30.6 - st * 1.6], [14.3 + sw, 29.2 - st * 1.8],
    [13.4 + sw * 1.2, 31.2 - st * 2.2], [12.5 + sw * 1.1, 29.4 - st * 2], [11.4 + sw, 30.4 - st * 2.3], [11.2 + sw * .6, 24 - st * 1.2], [sx - 1.9, sy + 3.6]], true);
  if (!back) {
    paint(c, cloak, CLOTH.dark, {shade: .8, light: [.1, .1], rim: .35});
    bands(c, cloak, 5, 1.45, CLOTH.deep, .5, .22);
  }
  // the far arm (body's right), behind the torso, in shadow
  paint(c, T(...j.shoulderN, 1.3, ...j.elbowN, 1.02), CLOTH.dark, {shade: .9, key: .05});
  paint(c, T(...j.elbowN, 1.02, ...j.wristN, .84), HIDE.dark, {shade: .9, key: .05});
  paint(c, E(j.wristN[0] + .05, j.wristN[1] + 1.2, .82, 1.02), SKIN.dark, {shade: .85, key: .05});
  // legs: the far leg in shadow, then the near leg, lit
  for (const [s, dim, key] of [['N', .88, .06], ['F', .45, .24]]) {
    const thigh = T(...j['hip' + s], 2.2, ...j['knee' + s], 1.65), shin = T(...j['knee' + s], 1.65, ...j['ankle' + s], 1.1);
    paint(c, thigh, CLOTH.dark, {shade: dim, key});
    paint(c, shin, HIDE.base, {shade: dim, key});
    bands(c, shin, 7, s === 'F' ? .5 : -.5, HIDE.dark, .85, .24);
    const [fx, fy] = j['foot' + s];
    paint(c, P([[fx - 1.6, fy - 1], [fx + .6, fy - 1.2], [fx + 2.4, fy - .2], [fx + 2.5, fy + .6], [fx - 1.7, fy + .7]], true), HIDE.dark, {shade: dim, key});
  }
  occlude(c, 16.7, 23.5 + j.br, 2.6, 4, .7);
  const hipY = (j.hipF[1] + j.hipN[1]) / 2;
  const torso = P([[j.shoulderF[0] + .4, j.shoulderF[1] - .8], [j.shoulderN[0] - .2, j.shoulderN[1] - .9], [j.shoulderN[0] + .3, j.shoulderN[1] + 2.6],
    [19.6, hipY - .6], [19.2, hipY + 1.4], [14.6, hipY + 1.2], [14.3, hipY - .8], [j.shoulderF[0] - .1, j.shoulderF[1] + 2.4]], true);
  paint(c, torso, CLOTH.base, {shade: .75, light: [.18, .15], rim: .35});
  bands(c, torso, 9, -.6, CLOTH.deep, .55, .24, .6);
  grain(c, torso, CLOTH.soot, 40, {len: .8, angle: 0, spread: .4, width: .13, seed: 4, alpha: .5});
  BODY_LOOKS[worn.body]?.(c, torso, j);
  occlude(c, 19.6, j.shoulderN[1] + 3.8, 1.6, 4, .55);   // the far flank turns away from the light
  const nx = (j.shoulderF[0] + j.shoulderN[0]) / 2 + .2, ny = (j.shoulderF[1] + j.shoulderN[1]) / 2 - 1.6;
  const cowl = P([[nx - 3, ny + .8], [nx, ny - .2], [nx + 3.4, ny + 1], [nx + 3.2, ny + 3.2], [nx + .2, ny + 4], [nx - 2.8, ny + 3.2]], true);
  paint(c, cowl, CLOTH.base, {shade: .7, light: [.15, .1], rim: .4});
  bands(c, cowl, 3, .1, CLOTH.deep, .55, .22, 1);
  paint(c, R(14.2, hipY - 1.4, 5.6, 1.1, .5), ROPE, {shade: .7, key: .15, edge: .45});
  stroke(c, [[19, hipY - .4], [18.7 + sw * .3, hipY + 2.3]], ROPE, .35, .95); stroke(c, [[19.4, hipY - .4], [19.8 + sw * .3, hipY + 1.8]], ROPE, .35, .95);
  if (back) {   // seen from behind the cloak covers the back
    paint(c, cloak, CLOTH.dark, {shade: .75, light: [.3, .1], rim: .35});
    bands(c, cloak, 5, 1.45, CLOTH.deep, .5, .22);
  }
  // the near arm (body's left): a wrapped forearm and a bare, bony hand
  paint(c, T(...j.shoulderF, 1.45, ...j.elbowF, 1.12), CLOTH.base, {shade: .7, light: [.2, .2], rim: .3});
  const fore = T(...j.elbowF, 1.12, ...j.wristF, .9);
  paint(c, fore, HIDE.base, {shade: .65}); bands(c, fore, 6, .7, HIDE.dark, .85, .22);
  const [hx, hy] = [j.wristF[0] + .05, j.wristF[1] + 1.3];
  paint(c, E(hx, hy, .9, 1.15), SKIN.base, {shade: .65, light: [.2, .2]});
  for (let f = 0; f < 4; f++) stroke(c, [[hx - .55 + f * .37, hy + .5], [hx - .5 + f * .37, hy + 1.45]], SKIN.deep, .17, .85);
  head(c, j.head, back);
  HEAD_LOOKS[worn.head]?.(c, j, back);
}
function head(c, [cx, cy], back) {
  paint(c, R(cx - .9, cy + 2.2, 2, 2.4, .8), SKIN.dark, {shade: .8, key: .05, edge: .35});   // neck
  const skull = P([[cx - 2.6, cy + 1.4], [cx - 2.9, cy - 1.4], [cx - 1.6, cy - 3.4], [cx + .6, cy - 3.8], [cx + 2.4, cy - 2.8], [cx + 2.9, cy - .4],
    [cx + 2.6, cy + 1.6], [cx + 1.9, cy + 3.2], [cx + .6, cy + 3.7], [cx - .6, cy + 3.1], [cx - 1.8, cy + 2.6]], true);
  paint(c, skull, SKIN.base, {shade: .75, key: .3, light: [.25, .2], rim: .3});
  if (back) {   // the back of the head: matted hair over all of it, an ear at the side
    paint(c, skull, HAIR, {shade: .6, key: .18, rim: .3});
    grain(c, skull, '#3a3029', 24, {len: 1.2, angle: Math.PI / 2 + .4, spread: .9, width: .15, seed: 23, alpha: .7});
    paint(c, E(cx + 2.4, cy + .4, .55, .9), SKIN.dark, {shade: .8, edge: .35});
    return;
  }
  paint(c, E(cx - 1.9, cy + .4, .6, .95), SKIN.dark, {shade: .7, edge: .35});        // the near ear
  occlude(c, cx + 1.6, cy + .2, 1.5, 1, .6);                                          // the far side of the face
  stroke(c, [[cx + 1.9, cy - .3], [cx + 2.7, cy + 1], [cx + 2.3, cy + 1.3]], SKIN.light, .2, .55);   // nose ridge
  stroke(c, [[cx + .4, cy + 1.4], [cx + .9, cy + 2.2]], SKIN.deep, .2, .65);                         // hollow cheek
  stroke(c, [[cx + 1, cy + 2.7], [cx + 2, cy + 2.6]], SKIN.deep, .22, .85);                          // mouth
  stroke(c, [[cx + .1, cy - .75], [cx + 1.1, cy - .9]], HAIR, .3, .9); stroke(c, [[cx + 1.6, cy - .9], [cx + 2.4, cy - .8]], HAIR, .28, .9);
  for (const [ex, ey] of [[cx + .6, cy + .05], [cx + 1.95, cy]]) {
    c.fillStyle = rgba(DEEP, .9); c.beginPath(); c.ellipse(ex, ey, .42, .26, 0, 0, Math.PI * 2); c.fill();
    c.fillStyle = 'rgba(190, 214, 230, .85)'; c.beginPath(); c.arc(ex + .08, ey - .02, .1, 0, Math.PI * 2); c.fill();
  }
  const hair = P([[cx - 2.9, cy + .4], [cx - 3, cy - 1.8], [cx - 1.7, cy - 3.6], [cx + .6, cy - 4.1], [cx + 2.5, cy - 3.1], [cx + 2.8, cy - 1.4],
    [cx + 1.6, cy - 1.7], [cx + .4, cy - 1.2], [cx - .8, cy - 1.6], [cx - 1.9, cy - .6]], true);
  paint(c, hair, HAIR, {shade: .6, key: .18, rim: .3});
  grain(c, hair, '#3a3029', 16, {len: 1.2, angle: Math.PI / 2 + .4, spread: .9, width: .15, seed: 21, alpha: .7});
}
function hood(c, j, back) {
  const [cx, cy] = j.head;
  const shell = back
    ? P([[cx - 3.6, cy + 3.6], [cx - 3.9, cy - .8], [cx - 2.4, cy - 3.9], [cx + .4, cy - 4.6], [cx + 2.8, cy - 3.6], [cx + 3.6, cy - .8], [cx + 3.4, cy + 3.6]], true)
    : P([[cx - 3.7, cy + 3.4], [cx - 4, cy - .6], [cx - 2.5, cy - 3.8], [cx + .4, cy - 4.6], [cx + 2.9, cy - 3.5], [cx + 3.4, cy - 1.2],
      [cx + 2.2, cy - 2.4], [cx + .6, cy - 2.6], [cx - .7, cy - 1.4], [cx - 1, cy + 1.6], [cx - .4, cy + 3.8], [cx - 2, cy + 4.6]], true);
  paint(c, shell, CLOTH.base, {shade: .8, light: [.15, .1], rim: .45});
  bands(c, shell, 4, .3, CLOTH.deep, .45, .2, -1);
  if (!back) occlude(c, cx + .9, cy - 1, 2.6, 1.6, .85);   // its brim throws the brow into shadow
  const drape = P([[cx - 3.4, cy + 3], [cx + 3.6, cy + 3.4], [cx + 4, cy + 6.4], [cx, cy + 7.4], [cx - 4, cy + 6.2]], true);
  paint(c, drape, CLOTH.base, {shade: .75, light: [.15, .1], rim: .4});
  bands(c, drape, 3, .1, CLOTH.deep, .5, .22, 1);
}

// ---- the cached frame ---------------------------------------------------------------------------
const WALK_FRAMES = 4;   // pixelPlayerPose's frame counter: four phases per step cycle
/** The avatar's body for a pose, painted once and cached: `look` from pixelPlayerPose
 * ({facing, moving, frame, breathe, run}); `low` 'crouch' | 'sit' | 'kneel' | null; `worn` {body,
 * head} item ids. Always the full 32 x 40 frame, feet on its bottom edge. Null without a DOM. */
export function travellerCanvas(look, {low = null, worn = {}} = {}) {
  const facing = look.facing, back = facing === 'north', west = facing === 'west';
  const phase = look.moving ? (look.frame % WALK_FRAMES) / WALK_FRAMES : null;
  const lowKind = low === 'sit' ? 'sit' : low ? 'crouch' : null;
  const key = `traveller|${back ? 'n' : west ? 'w' : 'e'}|${lowKind || (phase === null ? `b${look.breathe}` : `${look.run ? 'r' : 'w'}${phase}`)}|${worn.body || ''}|${worn.head || ''}`;
  return paintedCanvas(key, HERO_W, HERO_H, c => {
    const joints = lowKind ? travellerLowPose(lowKind)
      : phase === null ? travellerPose({breath: look.breathe ? .25 : 0})
      : look.run ? travellerPose({run: phase}) : travellerPose({walk: phase});
    c.save();
    if (west) { c.translate(HERO_W, 0); c.scale(-1, 1); }
    c.translate(-1.5, 0);   // the figure's centre of mass over the tile's centre
    paintTraveller(c, joints, {back, worn});
    c.restore();
  });
}
