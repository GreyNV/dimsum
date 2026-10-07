/** The player avatar: pixel-art frames, activity poses, fists and work marks.
 *
 * Presentation only. Every function reads snapshot fields (position, facing,
 * animation, animation_ms, active) or client presentation clocks for purely
 * cosmetic motion. Nothing here decides hits, damage, timing or collision.
 */
import {TILE_W, TILE_H} from './view.js';
import {setupText} from './art.js';
import {ACTOR_FOOT, FACING_ANGLE, OUTLINE, ROLE, drawShadow} from './sprites.js';

/** Bare-handed punch from server metadata: active frame = strike; otherwise windup
 * until the active frame has been observed for this attack, then recover.
 * Returns how far (px) the fist travels from the shoulder toward the facing. */
export function punchReach(player, phase) {
  if (player.animation !== 'attack') return null;
  return {windup: -3, strike: 15, recover: 6}[phase] ?? -3;
}
/** Shoulder of the punching arm, relative to the feet anchor. */
const SHOULDER = {south: [9, -33], north: [-9, -33], east: [5, -33], west: [-5, -33]};

/** Snap to the pixel-player art grid so arms step in whole art pixels. */
const snap = v => Math.round(v / PIXEL) * PIXEL;
function drawFist(ctx, sx, sy, fx, fy) {
  sx = snap(sx); sy = snap(sy); fx = snap(fx); fy = snap(fy);
  // One sleeve cell per grid step: a staircase of whole cells, never a 1px diagonal.
  const steps = Math.max(1, Math.abs(fx - sx) / PIXEL, Math.abs(fy - sy) / PIXEL);
  const cells = [];
  for (let i = 0; i <= steps; i++) cells.push([snap(sx + (fx - sx) * i / steps), snap(sy + (fy - sy) * i / steps)]);
  ctx.fillStyle = OUTLINE;
  for (const [cx, cy] of cells) ctx.fillRect(cx - 1, cy - 1, PIXEL + 2, PIXEL + 2);
  ctx.fillRect(fx - PIXEL - 1, fy - PIXEL - 1, PIXEL * 2 + 2, PIXEL * 2 + 2);
  ctx.fillStyle = ROLE.c.fill; // sleeve
  for (const [cx, cy] of cells) ctx.fillRect(cx, cy, PIXEL, PIXEL);
  ctx.fillStyle = ROLE.s.fill; ctx.fillRect(fx - PIXEL, fy - PIXEL, PIXEL * 2, PIXEL * 2);
  ctx.fillStyle = ROLE.s.ink; ctx.fillRect(fx - PIXEL, fy + 1, PIXEL * 2, 1); // knuckles
}

/** Activity poses (presentation only) for encounter kinds performed in place. */
export const POSE = Object.freeze({forage: 'crouch', gather: 'crouch', observe: 'crouch',
  drink: 'crouch', study: 'crouch', meditate: 'sit', climb: 'climb', rest: 'sit',
  think: 'sit', contemplate: 'sit', pray: 'kneel', kneel: 'kneel', scavenge: 'crouch', craft: 'crouch'});

/** Pure: everything that selects a pixel-player frame. Equal poses paint identical pixels. */
export function pixelPlayerPose(player, reducedMotion = false) {
  const facing = ['north','south','east','west'].includes(player.facing) ? player.facing : 'south';
  const moving = player.animation === 'walk' || player.animation === 'run';
  const frame = reducedMotion ? 0 : Math.floor(player.animation_ms / (player.animation === 'run' ? 90 : 130)) % 4;
  const stride = moving ? [0, 1, 0, -1][frame] : 0;
  const breathe = !moving && !reducedMotion && Math.floor(player.animation_ms / 450) % 4 === 2 ? 1 : 0;
  return {facing, moving, stride, breathe};
}

/** Pixel-player art unit: one logical art pixel is 2x2 world px. */
export const PIXEL = 2;
const PIXEL_COLORS = Object.freeze({edge: OUTLINE, hair:'#3c2a27', hairLight:'#60423a', skin:'#f0bc89',
  skinLight:'#ffd0a0', scarf:'#944a3d', scarfLight:'#bd6c4e', tunic:'#484936',
  tunicLight:'#69654a', belt:'#ae8355', pants:'#25332e', pantsLight:'#3a4a3c',
  boot:'#5a4736', bootLight:'#9d8060', eye:'#30231e'});

/** Pure pixel-player frame: logical art 16 wide x 20 tall (standing) or 13 tall
 * (crouch), as ordered rectangles [color, x, y, w, h] in art pixels, already
 * mirrored for west. Later rectangles paint over earlier ones. */
export function pixelPlayerArt(player, {compact = false, reducedMotion = false} = {}) {
  const {facing, moving, stride, breathe} = pixelPlayerPose(player, reducedMotion);
  const side = facing === 'east' || facing === 'west';
  const rects = [];
  const box = (color, x, y, w, h) => rects.push([PIXEL_COLORS[color], facing === 'west' ? 16 - x - w : x, y, w, h]);
  // Tousled dark hair is the strongest silhouette from the reference.
  const head = () => {
    box('edge',2,2,12,6); box('edge',4,0,9,9); box('edge',11,0,4,4);   // outline encloses every hair cell
    box('hair',5,1,7,7); box('hair',3,3,10,4);
    box('hairLight',5,2,4,1); box('hairLight',10,3,2,1); box('hair',12,1,2,2);
    if (facing === 'north') {
      box('hair',5,5,7,4); box('hairLight',6,6,4,1);
      box('scarf',4,8,8,2); box('scarfLight',5,8,5,1);
    } else if (side) {
      box('edge',8,4,4,5); box('skin',9,5,3,3); box('skinLight',11,5,1,2);
      box('eye',11,6,1,1); box('hair',8,3,4,2); box('scarf',5,8,7,2);
      box('scarfLight',9,8,3,1);
    } else {
      box('edge',5,4,7,5); box('skin',6,4,5,4); box('skinLight',7,5,3,2);
      box('eye',6,6,1,1); box('eye',10,6,1,1); box('hair',5,3,7,2);
      box('scarf',4,8,8,2); box('scarfLight',5,8,6,1);
    }
  };
  if (compact) {
    // Crouch: same head, torso shortened to belt height, knees bent. 16x13 art px.
    if (side) {
      // Hips back over the folded back leg, front knee forward and up, cloak hanging behind.
      box('edge',3,8,10,4); box('edge',0,8,5,5); box('edge',7,9,9,4);
      box('pants',4,11,4,1); box('boot',4,12,4,1);                 // back leg folded under
      box('tunic',4,10,4,1);
      box('pantsLight',8,10,7,1); box('pantsLight',12,11,3,1); box('boot',11,12,4,1); box('bootLight',12,12,2,1);
      box('scarf',1,9,3,3); box('scarfLight',2,10,1,1);             // cloak falls behind
    } else {
      // Knees splay up on both sides of the lowered hips; boots stay under them.
      box('edge',3,8,10,4); box('edge',0,9,16,4);
      box('pants',1,10,4,2); box('pantsLight',11,10,4,2);
      box('boot',1,12,5,1); box('bootLight',2,12,3,1); box('boot',10,12,5,1); box('bootLight',11,12,3,1);
      box('tunic',5,10,6,1); box('tunicLight',6,10,3,1); box('belt',5,11,6,1);
    }
    head();
    return {width: 16, height: 13, rects};
  }
  // Boots and trouser legs change independently, so movement reads at game scale.
  // Profile: legs scissor (wide / passing / wide) and fully coincide when passing, so the
  // far boot is never clipped to a 1px sliver. Front/back: legs keep their columns and lift.
  const leg = (x, dy, pants) => { box('edge',x-1,14,4,5+dy); box(pants,x,14,2,4+dy);
    box('edge',x-2,18+dy,6,2-dy); box('boot',x-1,18+dy,4,1); box('bootLight',x-1,19+dy,3,1); };
  if (side) { const a = stride > 0 ? 7 : 5 + stride, b = stride > 0 ? 7 : 9 - stride;
    leg(a, 0, 'pants'); leg(b, 0, 'pantsLight'); }
  else { leg(5, stride > 0 ? -1 : 0, 'pants'); leg(9, stride < 0 ? -1 : 0, 'pantsLight'); }
  // Rust scarf, muted green tunic, short travelling cloak and brass belt.
  // Each arm (outline, sleeve, hand) moves as ONE unit so no fill cell ever leaves its outline.
  const swing = moving ? stride : 0, armL = breathe + swing, armR = breathe - swing;
  box('edge',3,8,10,8+breathe); box('tunic',4,9+breathe,8,6);
  box('tunicLight',5,10+breathe,5,2); box('belt',4,14+breathe,8,1);
  if (side) { box('edge',0,8,4,8+breathe); box('scarf',1,9,3,6+breathe); box('scarfLight',2,10,2,1); }  // back cloak joins the torso outline
  if (!side) { box('edge',2,9+armL,3,8); box('scarf',3,9+armL,2,4); box('skin',3,14+armL,2,2); }  // far arm hidden by cape in profile
  box('edge',11,9+armR,3,8); box('scarf',11,9+armR,2,4); box('skinLight',11,14+armR,2,2);
  head();
  return {width: 16, height: 20, rects};
}

/** Frame size in world px; the art sits on the bottom edge so feet share one row. */
export const pixelPlayerFrame = compact => ({width: 16 * PIXEL, height: (compact ? 13 : 20) * PIXEL});

/** A clean pixel character drawn from the uploaded four-direction reference, at
 * whole world pixels with (left, top) the frame's top-left. */
export function paintPixelPlayer(ctx, player, left, top, {compact = false, reducedMotion = false} = {}) {
  const art = pixelPlayerArt(player, {compact, reducedMotion});
  const oy = top + pixelPlayerFrame(compact).height - art.height * PIXEL;
  for (const [color, x, y, w, h] of art.rects) {
    ctx.fillStyle = color; ctx.fillRect(left + x * PIXEL, oy + y * PIXEL, w * PIXEL, h * PIXEL);
  }
}

/** Each pose is painted once at integer pixels and blitted nearest-neighbour, like the
 * terrain stamps; fillRect under the fractional zoom*dpr camera transform antialiases.
 * Without a DOM canvas (node tests) the frame is painted directly instead. */
const PIXEL_STAMPS = new Map();
function newCanvas(width, height) {
  if (typeof document !== 'undefined' && document.createElement) {
    const canvas = document.createElement('canvas'); canvas.width = width; canvas.height = height; return canvas;
  }
  if (typeof OffscreenCanvas !== 'undefined') return new OffscreenCanvas(width, height);
  return null;
}
export function pixelPlayerStamp(player, compact = false, reducedMotion = false) {
  const pose = pixelPlayerPose(player, reducedMotion);
  const key = compact ? `${pose.facing}|crouch` : `${pose.facing}|${pose.stride}|${pose.breathe}`;
  if (PIXEL_STAMPS.has(key)) return PIXEL_STAMPS.get(key);
  const {width, height} = pixelPlayerFrame(compact);
  const canvas = newCanvas(width, height);
  if (!canvas) return null;
  paintPixelPlayer(canvas.getContext('2d'), player, 0, 0, {compact, reducedMotion});
  PIXEL_STAMPS.set(key, canvas);
  return canvas;
}

/** (x, y) is the tile-center position of the player in world pixels. `activity` is

/** (x, y) is the tile-center position of the player in world pixels. `activity` is
 * the server's current encounter activity (or null); `clock` animates its pose. */
export function drawPlayer(ctx, player, x, y, phase = 'windup', {activity = null, clock = 0, reducedMotion = false} = {}) {
  setupText(ctx);
  x = Math.round(x); y = Math.round(y);
  const pose = activity && player.animation !== 'attack' ? POSE[activity.kind] : null;
  const compact = pose === 'crouch' || pose === 'sit' || pose === 'kneel';
  const {width, height} = pixelPlayerFrame(compact);
  // Only climbing moves the whole body; walk frames carry their own motion in whole art pixels.
  const bob = pose === 'climb' ? -Math.round(Math.abs(Math.sin(clock / 260)) * 6) : 0;
  const reach = punchReach(player, phase);
  const angle = FACING_ANGLE[player.facing] ?? Math.PI / 2;
  const lunge = reach !== null && phase === 'strike' ? 2 : 0;
  const lx = Math.round(Math.cos(angle) * lunge), ly = Math.round(Math.sin(angle) * lunge);
  const left = x - width / 2 + lx, top = y + ACTOR_FOOT - height + bob + ly;
  drawShadow(ctx, x, y, 10);
  if (pose === 'sit') {
    const pulse = .25 + .2 * Math.sin(clock / 400);
    ctx.save(); ctx.globalAlpha = pulse; ctx.strokeStyle = '#cfe6ff'; ctx.lineWidth = 2;
    ctx.beginPath(); ctx.ellipse(x, y + ACTOR_FOOT - 2, 18, 6, 0, 0, Math.PI * 2); ctx.stroke(); ctx.restore();
  }
  let fist = null;
  if (reach !== null) {
    const [shoulderX, shoulderY] = SHOULDER[player.facing] || SHOULDER.south;
    const scale = PIXEL / 3;   // shoulder offsets were authored for the 3x larger cell sprite
    const sx = Math.round(shoulderX * scale), sy = Math.round(shoulderY * scale);
    const ox = x + sx + lx, oy = y + ACTOR_FOOT + sy + ly;
    fist = [ox, oy, ox + Math.cos(angle) * reach * scale, oy + Math.sin(angle) * reach * .8 * scale];
  }
  // Seen from behind, a pulled-back fist hides behind the body; a strike is in front.
  const fistBehind = player.facing === 'north' && phase !== 'strike';
  if (fist && fistBehind) drawFist(ctx, ...fist);
  if (activity?.kind === 'pray') {  // a thin column of light over the kneeling avatar
    ctx.save(); ctx.globalAlpha = .32 + .16 * Math.sin(clock / 350);
    const ray = ctx.createLinearGradient(x, top - 40, x, top + height);
    ray.addColorStop(0, '#fff3c400'); ray.addColorStop(.5, '#fff3c4'); ray.addColorStop(1, '#fff3c400');
    ctx.fillStyle = ray; ctx.fillRect(x - 6, top - 40, 12, height + 40); ctx.restore();
  }
  const hands = pose === 'crouch' ? workingHands(activity, player.facing, x, y, clock, reducedMotion) : null;
  if (hands?.behind) for (const arm of hands.arms) drawFist(ctx, ...arm);   // seen from behind
  const stamp = pixelPlayerStamp(player, compact, reducedMotion);
  if (stamp) { ctx.imageSmoothingEnabled = false; ctx.drawImage(stamp, left, top); }
  else paintPixelPlayer(ctx, player, left, top, {compact, reducedMotion});
  if (fist && !fistBehind) drawFist(ctx, ...fist);
  if (hands && !hands.behind) for (const arm of hands.arms) drawFist(ctx, ...arm);
  if (pose && activity.kind !== 'rest' && activity.kind !== 'kneel')
    drawActionInteraction(ctx, activity, x, y, clock, reducedMotion, {armDrawn: !!hands});
  if (activity) drawProgress(ctx, x, top - 6, activity.progress / 1000, clock);
  return {left, top, width, height};
}

/** Arms of a crouching avatar working at the encounter cell. Shoulders sit at the
 * torso of the compact sprite (never the head): toward the viewer both hands work
 * in front of the knees; sideways one arm reaches forward and down; seen from
 * behind the forearms show above the shoulders and are drawn under the body.
 * Returns {behind, arms: [[shoulderX, shoulderY, handX, handY], ...]}. */
export function workingHands(activity, facing, x, y, clock = 0, reducedMotion = false) {
  let dir = facing;
  if (activity && Number.isFinite(activity.x) && Number.isFinite(activity.y)) {
    const dx = (activity.x + .5) * TILE_W - x, dy = (activity.y + .5) * TILE_H - y;
    if (dx || dy) dir = Math.abs(dy) >= Math.abs(dx) ? (dy > 0 ? 'south' : 'north') : (dx > 0 ? 'east' : 'west');
  }
  const beat = reducedMotion ? 0 : Math.round(Math.sin(clock / 145) * 2);
  const shoulderY = y + 1;   // compact frame: shoulders near the torso, below the head
  if (dir === 'south') return {behind: false, arms: [
    [x - 6, shoulderY, x - 4, y + 7 + beat], [x + 6, shoulderY, x + 4, y + 7 - beat]]};
  if (dir === 'north') return {behind: true, arms: [
    [x - 6, shoulderY, x - 7, y - 10 + beat], [x + 6, shoulderY, x + 7, y - 10 - beat]]};
  const side = dir === 'east' ? 1 : -1;
  return {behind: false, arms: [[x + side * 5, shoulderY, x + side * (13 + beat), y + 5]]};
}

/** Visible, cosmetic contact with the actual encounter cell. The simulation owns
 * timing and rewards; these marks only explain what the avatar is doing. */
function drawActionInteraction(ctx, activity, x, y, clock, reducedMotion, {armDrawn = false} = {}) {
  const colors = {forage:'#e96c75', gather:'#d6ac6a', observe:'#e6d6a2', climb:'#b5d58b',
    drink:'#a9eaff', meditate:'#c8c5ff', study:'#d3b6ff', pray:'#fff0b4',
    think:'#b6bed1', contemplate:'#c8c5ff'};
  const color = colors[activity.kind];
  if (!color || !Number.isFinite(activity.x) || !Number.isFinite(activity.y)) return;
  const tx = (activity.x + .5) * TILE_W, ty = (activity.y + .5) * TILE_H;
  const distance = Math.hypot(tx - x, ty - y);
  if (distance > TILE_W * 1.6) return;
  const ux = distance ? (tx - x) / distance : 0, uy = distance ? (ty - y) / distance : 1;
  const beat = reducedMotion ? 0 : Math.sin(clock / (activity.kind === 'climb' ? 170 : 145));
  const touch = ['forage','gather','climb','drink','study'].includes(activity.kind);
  if (touch && !armDrawn) {   // climbing: the standing sprite reaches up from the chest
    const sx = x + ux * 5, sy = y - 11 + uy * 2;
    const reach = 8 + beat * 3;
    drawFist(ctx, sx, sy, sx + ux * reach, sy + uy * reach - (activity.kind === 'climb' ? 5 + beat * 4 : 0));
  }
  ctx.save();
  ctx.strokeStyle = color; ctx.fillStyle = color;
  ctx.globalAlpha = reducedMotion ? .65 : .55 + .25 * beat;
  const lift = reducedMotion ? 0 : beat * 4;
  if (['meditate','pray','think','contemplate'].includes(activity.kind)) {
    ctx.lineWidth = 2; ctx.beginPath(); ctx.ellipse(x, y + ACTOR_FOOT, 18 + Math.abs(lift), 6, 0, 0, Math.PI * 2); ctx.stroke();
  } else {
    const px = touch ? tx - ux * 7 : tx, py = ty - 10 + lift;
    ctx.fillRect(Math.round(px) - 2, Math.round(py) - 2, 4, 4);
    if (activity.kind === 'observe' || activity.kind === 'study') {
      ctx.lineWidth = 1; ctx.strokeRect(Math.round(px) - 8, Math.round(py) - 8, 16, 16);
    }
    if (activity.kind === 'drink') {
      ctx.beginPath(); ctx.moveTo(x + ux * 5, y - 28); ctx.lineTo(x + ux * 5 - 3, y - 22);
      ctx.lineTo(x + ux * 5 + 3, y - 22); ctx.closePath(); ctx.fill();
    }
  }
  ctx.restore();
}

export function drawProgress(ctx, cx, y, fraction, clock = 0) {
  const w = 32, x = Math.round(cx - w / 2), f = Math.max(0, Math.min(1, fraction));
  const filled = Math.round(w * f);
  ctx.fillStyle = OUTLINE; ctx.fillRect(x - 2, y - 2, w + 4, 8);
  ctx.fillStyle = '#3b3418'; ctx.fillRect(x, y, w, 4);
  ctx.fillStyle = '#cb873a'; ctx.fillRect(x, y, filled, 4);
  ctx.fillStyle = '#ffe3a0'; ctx.fillRect(x, y, filled, 1);
  if (filled > 1) {
    ctx.fillStyle = '#fff6d7';
    ctx.fillRect(x + Math.min(filled - 2, Math.floor(clock / 90) % Math.max(1, filled)), y + 1, 2, 2);
  }
  ctx.fillStyle = '#fff0b0'; ctx.fillRect(x + filled - 1, y - 3, 2, 10);
}
