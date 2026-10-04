/** Actor and combat-feedback art: player, enemies, weapon, slash, hits, deaths.
 *
 * Presentation only. Every function reads snapshot fields (position, facing,
 * animation, animation_ms, active, hp) or client presentation clocks for purely
 * cosmetic fades. Nothing here decides hits, damage, timing or collision.
 *
 * Sprites are solid outlined silhouettes on the same 4x7 drawing cells as the
 * terrain, so they share its texture but read clearly against busy ground.
 * Each sprite is two equal-sized row arrays: `paint` (color role per cell, space =
 * transparent) and `glyph` (texture character per cell, space = none).
 */
import {TILE_W, TILE_H, CELL_W, CELL_H, visualHash} from './view.js';
import {setupText} from './art.js';

/** Feet rest this many pixels below the logical tile center. */
export const ACTOR_FOOT = 12;
export const OUTLINE = '#070a06';
export const ROLE = Object.freeze({
  // Player: rust cloak and brass trim contrast with the green forest.
  c: {fill: '#8e4731', ink: '#5a2a1b'}, t: {fill: '#d6a55e', ink: '#946733'},
  s: {fill: '#efc595', ink: '#3a2116'}, k: {fill: '#f5df8c', ink: '#8a6a2a'},
  a: {fill: '#8ec8f4', ink: '#ecfaff'},
  p: {fill: '#4d3c2b', ink: '#2c2219'}, b: {fill: '#2b211a', ink: '#76604a'},
  // Enemy (bramble boar): wine fur, bone horns, ember eyes.
  f: {fill: '#7e3447', ink: '#4c1b2a'}, d: {fill: '#56202f', ink: '#2f0f18'},
  h: {fill: '#d9c8a4', ink: '#8d7a5a'}, e: {fill: '#2a0b10', ink: '#ffd45e'},
  m: {fill: '#24090e', ink: '#f1e6cc'}, w: {fill: '#ece0c2', ink: '#a8977a'}
});
const FLASH = '#fff4dc';

const MIRROR = {'/': '\\', '\\': '/', '(': ')', ')': '(', '<': '>', '>': '<', '[': ']', ']': '['};
const mirrorRow = row => [...row].reverse().map(c => MIRROR[c] ?? c).join('');
export const mirrorSprite = s => ({paint: s.paint.map(mirrorRow), glyph: s.glyph.map(mirrorRow)});
const withLegs = (body, legs) => ({paint: [...body.paint.slice(0, -2), ...legs.paint],
  glyph: [...body.glyph.slice(0, -2), ...legs.glyph]});

// 9 columns x 9 rows = 36x63 px: 1.5 tiles wide, ~2.25 tiles tall.
const FRONT = {paint: [
  '   ccc   ', '  ccccc  ', '  csssc  ', ' cctktcc ', 'ccttattcc',
  'scctktccs', ' cctttcc ', '  pp pp  ', '  bb bb  '], glyph: [
  '   /^\\   ', '  /:::\\  ', '  (o.o)  ', " /:'*':\\ ", '/:|:::|:\\',
  'o:|=*=|:o', ' \\|:::|/ ', '  || ||  ', '  -- --  ']};
const BACK = {paint: [
  '   ccc   ', '  ccccc  ', '  ccccc  ', ' ccctccc ', 'ccccacccc',
  'scccccccs', ' ccccccc ', '  pp pp  ', '  bb bb  '], glyph: [
  '   /^\\   ', '  /:::\\  ', '  |:::|  ', ' /::v::\\ ', '/:::|:::\\',
  'o:::|:::o', ' \\:::::/ ', '  || ||  ', '  -- --  ']};
const SIDE = {paint: [
  '   ccc   ', '  ccccc  ', '  cccss  ', '  cctts  ', ' cctatc  ',
  ' cctkts  ', ' cctttc  ', '   pp    ', '   bb    '], glyph: [
  '   /^\\   ', '  /:::\\  ', '  |:: .  ', '  /:=:   ', ' /:|::\\  ',
  ' |:=*=o  ', ' \\:|::/  ', '   ||    ', '   -=    ']};
const LEGS = {
  front: [{paint: ['  pp pp  ', '  bb bb  '], glyph: ['  || ||  ', '  -- --  ']},
    {paint: ['  pp pp  ', '  bb     '], glyph: ['  || ||  ', '  --     ']},
    {paint: ['  pp pp  ', '     bb  '], glyph: ['  || ||  ', '     --  ']}],
  side: [{paint: ['   pp    ', '   bb    '], glyph: ['   ||    ', '   -=    ']},
    {paint: ['  p  p   ', ' bb   bb '], glyph: ['  /  \\   ', ' -=   -= ']},
    {paint: ['   pp    ', '   bb    '], glyph: ['   |\\    ', '   -=    ']}]
};
const VIEW = {south: FRONT, north: BACK, east: SIDE, west: mirrorSprite(SIDE)};

/** Sword hand, relative to the feet anchor, and whether the blade is behind the body. */
const FACING_ANGLE = {east: 0, south: Math.PI / 2, west: Math.PI, north: -Math.PI / 2};

/** Player sprite for a snapshot: view by facing, legs by walk phase. */
export function playerSprite(player) {
  const facing = VIEW[player.facing] ? player.facing : 'south';
  const side = facing === 'east' || facing === 'west';
  let sprite = VIEW[facing];
  if (player.animation === 'walk') {
    const step = 1 + Math.floor(player.animation_ms / 120) % 2;
    let legs = LEGS[side ? 'side' : 'front'][step];
    if (facing === 'west') legs = mirrorSprite(legs);
    sprite = withLegs(sprite, legs);
  } else if (player.animation === 'attack' && side) {
    let legs = LEGS.side[1];
    if (facing === 'west') legs = mirrorSprite(legs);
    sprite = withLegs(sprite, legs); // lunge stance
  }
  return sprite;
}

/** Stable sprite layers. Equipment art can later replace one slot with a same-size
 * paint/glyph sprite without changing terrain, facing or the combat state. */
export const PLAYER_SLOTS = Object.freeze(['body', 'pants', 'boots', 'chest', 'helmet']);
export function playerSpriteLayers(player, compact = false) {
  const standing = playerSprite(player);
  const sprite = compact ? crouchSprite(standing) : standing;
  const layers = Object.fromEntries(PLAYER_SLOTS.map(slot => [slot, {paint: [], glyph: []}]));
  sprite.paint.forEach((row, r) => {
    [...row].forEach((role, c) => {
      const logicalRow = compact && r === sprite.paint.length - 1 ? 8 : r;
      const slot = role === 's' ? 'body' : logicalRow === 8 ? 'boots'
        : logicalRow === 7 ? 'pants' : logicalRow <= 2 ? 'helmet' : 'chest';
      for (const name of PLAYER_SLOTS) {
        layers[name].paint[r] ??= ' '.repeat(row.length);
        layers[name].glyph[r] ??= ' '.repeat(row.length);
        if (name === slot && role !== ' ') {
          layers[name].paint[r] = layers[name].paint[r].slice(0, c) + role + layers[name].paint[r].slice(c + 1);
          layers[name].glyph[r] = layers[name].glyph[r].slice(0, c) + sprite.glyph[r][c] + layers[name].glyph[r].slice(c + 1);
        }
      }
    });
  });
  return layers;
}

export function paintPlayerLayers(ctx, player, left, top, equipment = {}, compact = false) {
  const layers = playerSpriteLayers(player, compact);
  for (const slot of PLAYER_SLOTS) paintSprite(ctx, layers[slot], left, top);
  // Equipment is a transparent overlay; face and hands remain part of the body.
  for (const slot of PLAYER_SLOTS.slice(1)) if (equipment[slot])
    paintSprite(ctx, compact ? crouchSprite(equipment[slot]) : equipment[slot], left, top);
}

// 11 columns x 7 rows = 44x49 px.
export const ENEMY = Object.freeze({paint: [
  ' h       h ', ' hh fff hh ', '  fffffff  ', ' ffefffeff ', 'dfffmmmfffd',
  ' dfwfffwfd ', '  dd   dd  '], glyph: [
  ' /       \\ ', ' (\\ ^^^ /) ', '  ;;;;;;;  ', ' ;;o;;;o;; ', '/;;;vvv;;;\\',
  " \\;V;;;V;/ ", "  ''   ''  "]});

export function spriteSize(sprite) {
  return {width: sprite.paint[0].length * CELL_W, height: sprite.paint.length * CELL_H};
}

/**
 * Paint a sprite with its top-left at (x, y): outline, solid fills, then glyph
 * texture. `dissolve` (0..1) removes cells in a stable per-cell order.
 */
export function paintSprite(ctx, sprite, x, y, {flash = false, alpha = 1, dissolve = 0, seed = 0} = {}) {
  const {paint, glyph} = sprite;
  const keep = (r, c) => dissolve <= 0 || visualHash(c, r, seed) % 1000 >= dissolve * 1000;
  ctx.globalAlpha = alpha;
  ctx.fillStyle = OUTLINE;
  paint.forEach((row, r) => [...row].forEach((role, c) => {
    if (role !== ' ' && keep(r, c)) ctx.fillRect(x + c * CELL_W - 1, y + r * CELL_H - 1, CELL_W + 2, CELL_H + 2);
  }));
  paint.forEach((row, r) => [...row].forEach((role, c) => {
    if (role === ' ' || !keep(r, c)) return;
    ctx.fillStyle = flash ? FLASH : ROLE[role].fill;
    ctx.fillRect(x + c * CELL_W, y + r * CELL_H, CELL_W, CELL_H);
  }));
  if (!flash) paint.forEach((row, r) => [...row].forEach((role, c) => {
    const ch = glyph[r][c];
    if (role === ' ' || ch === ' ' || !keep(r, c)) return;
    ctx.fillStyle = ROLE[role].ink;
    ctx.fillText(ch, x + c * CELL_W, y + r * CELL_H);
  }));
  ctx.globalAlpha = 1;
}

export function drawShadow(ctx, x, y, rx) {
  ctx.fillStyle = 'rgba(3, 6, 3, .5)';
  ctx.beginPath(); ctx.ellipse(x, y + ACTOR_FOOT - 1, rx, 4, 0, 0, Math.PI * 2); ctx.fill();
}

/** Bare-handed punch from server metadata: active frame = strike; otherwise windup
 * until the active frame has been observed for this attack, then recover.
 * Returns how far (px) the fist travels from the shoulder toward the facing. */
export function punchReach(player, phase) {
  if (player.animation !== 'attack') return null;
  return {windup: -3, strike: 15, recover: 6}[phase] ?? -3;
}
/** Shoulder of the punching arm, relative to the feet anchor. */
const SHOULDER = {south: [9, -33], north: [-9, -33], east: [5, -33], west: [-5, -33]};

function drawFist(ctx, sx, sy, fx, fy) {
  const len = Math.hypot(fx - sx, fy - sy), steps = Math.max(1, Math.ceil(len / 2));
  ctx.fillStyle = OUTLINE;
  for (let i = 0; i <= steps; i++) ctx.fillRect(Math.round(sx + (fx - sx) * i / steps) - 2, Math.round(sy + (fy - sy) * i / steps) - 2, 5, 5);
  ctx.fillRect(Math.round(fx) - 4, Math.round(fy) - 4, 8, 8);
  ctx.fillStyle = ROLE.c.fill; // sleeve
  for (let i = 0; i <= steps; i++) ctx.fillRect(Math.round(sx + (fx - sx) * i / steps) - 1, Math.round(sy + (fy - sy) * i / steps) - 1, 3, 3);
  ctx.fillStyle = ROLE.s.fill; ctx.fillRect(Math.round(fx) - 3, Math.round(fy) - 3, 6, 6);
  ctx.fillStyle = ROLE.s.ink; ctx.fillRect(Math.round(fx) - 3, Math.round(fy) + 1, 6, 1); // knuckles
}

/** Activity poses (presentation only) for encounter kinds performed in place. */
export const POSE = Object.freeze({forage: 'crouch', gather: 'crouch', observe: 'crouch',
  drink: 'crouch', study: 'crouch', meditate: 'sit', climb: 'climb', rest: 'sit',
  think: 'sit', contemplate: 'sit', pray: 'kneel', kneel: 'kneel'});
export function crouchSprite(sprite) {
  // Drop the lower cloak and legs; boots stay under the body.
  return {paint: [...sprite.paint.slice(0, 6), sprite.paint[8]], glyph: [...sprite.glyph.slice(0, 6), sprite.glyph[8]]};
}

/** A clean pixel character drawn from the uploaded four-direction reference.
 * Logical art is 16x20 pixels, enlarged with hard-edged rectangles at runtime.
 * Four timed frames are derived for idle, walk and a future run animation. */
function paintPixelPlayer(ctx, player, left, top, {compact = false, reducedMotion = false} = {}) {
  const P = {edge:'#241c1b', hair:'#3c2a27', hairLight:'#60423a', skin:'#f0bc89',
    skinLight:'#ffd0a0', scarf:'#944a3d', scarfLight:'#bd6c4e', tunic:'#484936',
    tunicLight:'#69654a', belt:'#ae8355', pants:'#25332e', pantsLight:'#3a4a3c',
    boot:'#5a4736', bootLight:'#9d8060', eye:'#30231e'};
  const facing = ['north','south','east','west'].includes(player.facing) ? player.facing : 'south';
  const moving = player.animation === 'walk' || player.animation === 'run';
  const frame = reducedMotion ? 0 : Math.floor(player.animation_ms / (player.animation === 'run' ? 90 : 130)) % 4;
  const stride = moving ? [0, 1, 0, -1][frame] : 0;
  const breathe = !moving && !reducedMotion && Math.floor(player.animation_ms / 450) % 4 === 2 ? 1 : 0;
  const side = facing === 'east' || facing === 'west';
  ctx.save(); ctx.translate(left, top); ctx.scale(3, compact ? 2 : 3);
  if (facing === 'west') { ctx.translate(16, 0); ctx.scale(-1, 1); }
  const box = (color, x, y, w, h) => { ctx.fillStyle = P[color]; ctx.fillRect(x, y, w, h); };
  // Boots and trouser legs change independently, so movement reads at game scale.
  const legA = side ? 5 + stride : 5 - stride, legB = side ? 9 - stride : 9 + stride;
  box('edge',legA-1,14,4,5); box('pants',legA,14,2,4);
  box('edge',legB-1,14,4,5); box('pantsLight',legB,14,2,4);
  box('edge',legA-2,18,5,2); box('boot',legA-1,18,4,1); box('bootLight',legA-1,19,3,1);
  box('edge',legB-2,18,5,2); box('boot',legB-1,18,4,1); box('bootLight',legB-1,19,3,1);
  // Rust scarf, muted green tunic, short travelling cloak and brass belt.
  if (side) { box('edge',1,8,8,7); box('scarf',1,9,5,6); box('scarfLight',2,10,3,1); }
  box('edge',3,8+breathe,10,8); box('tunic',4,9+breathe,8,6);
  box('tunicLight',5,10+breathe,5,2); box('belt',4,14+breathe,8,1);
  box('edge',2,9+breathe,3,6); box('scarf',3,9+breathe,2,4);
  box('edge',11,9+breathe,3,6); box('scarf',11,9+breathe,2,4);
  const swing = moving ? stride : 0;
  box('skin',3,14+breathe+swing,2,2); box('skinLight',11,14+breathe-swing,2,2);
  // Tousled dark hair is the strongest silhouette from the reference.
  box('edge',4,1,9,8); box('hair',5,1,7,7); box('hair',3,3,10,4);
  box('hairLight',5,2,4,1); box('hairLight',10,3,2,1);
  box('edge',11,0,2,2); box('hair',12,1,2,2);
  if (facing === 'north') {
    box('hair',5,5,7,4); box('hairLight',6,6,4,1);
    box('scarf',4,8,9,2); box('scarfLight',5,8,5,1);
  } else if (side) {
    box('edge',8,4,4,5); box('skin',9,5,3,3); box('skinLight',11,5,1,2);
    box('eye',11,6,1,1); box('hair',8,3,4,2); box('scarf',5,8,8,2);
    box('scarfLight',9,8,3,1);
  } else {
    box('edge',5,4,7,5); box('skin',6,4,5,4); box('skinLight',7,5,3,2);
    box('eye',6,6,1,1); box('eye',10,6,1,1); box('hair',5,3,7,2);
    box('scarf',4,8,9,2); box('scarfLight',5,8,6,1);
  }
  ctx.restore();
}

/** (x, y) is the tile-center position of the player in world pixels. `activity` is
 * the server's current encounter activity (or null); `clock` animates its pose. */
export function drawPlayer(ctx, player, x, y, phase = 'windup', {activity = null, clock = 0, equipment = {}, reducedMotion = false} = {}) {
  setupText(ctx);
  x = Math.round(x); y = Math.round(y);
  const pose = activity && player.animation !== 'attack' ? POSE[activity.kind] : null;
  let sprite = playerSprite(player);
  const compact = pose === 'crouch' || pose === 'sit' || pose === 'kneel';
  if (compact) sprite = crouchSprite(sprite);
  const usingLegacyEquipment = Object.keys(equipment).length > 0;
  const {width, height} = usingLegacyEquipment ? spriteSize(sprite) : {width: 48, height: compact ? 40 : 60};
  let bob = player.animation === 'idle' ? Math.floor(player.animation_ms / 600) % 2
    : player.animation === 'walk' ? Math.floor(player.animation_ms / 120) % 2 : 0;
  if (pose === 'crouch') bob = Math.floor(clock / 300) % 2;          // working hands
  if (pose === 'sit' || pose === 'kneel') bob = 0;
  if (pose === 'climb') bob = -Math.round(Math.abs(Math.sin(clock / 260)) * 6);
  const reach = punchReach(player, phase);
  const angle = FACING_ANGLE[player.facing] ?? Math.PI / 2;
  const lunge = reach !== null && phase === 'strike' ? 2 : 0;
  const lx = Math.round(Math.cos(angle) * lunge), ly = Math.round(Math.sin(angle) * lunge);
  const left = x - width / 2 + lx, top = y + ACTOR_FOOT - height + bob + ly;
  drawShadow(ctx, x, y, 14);
  if (pose === 'sit') {
    const pulse = .25 + .2 * Math.sin(clock / 400);
    ctx.save(); ctx.globalAlpha = pulse; ctx.strokeStyle = '#cfe6ff'; ctx.lineWidth = 2;
    ctx.beginPath(); ctx.ellipse(x, y + ACTOR_FOOT - 2, 18, 6, 0, 0, Math.PI * 2); ctx.stroke(); ctx.restore();
  }
  let fist = null;
  if (reach !== null) {
    const [sx, sy] = SHOULDER[player.facing] || SHOULDER.south;
    const ox = x + sx + lx, oy = y + ACTOR_FOOT + sy + ly;
    fist = [ox, oy, ox + Math.cos(angle) * reach, oy + Math.sin(angle) * reach * .8];
  }
  // Seen from behind, a pulled-back fist hides behind the body; a strike is in front.
  if (fist && player.facing === 'north' && phase !== 'strike') drawFist(ctx, ...fist);
  if (activity?.kind === 'pray') {  // a thin column of light over the kneeling avatar
    ctx.save(); ctx.globalAlpha = .32 + .16 * Math.sin(clock / 350);
    const ray = ctx.createLinearGradient(x, top - 60, x, top + height);
    ray.addColorStop(0, '#fff3c400'); ray.addColorStop(.5, '#fff3c4'); ray.addColorStop(1, '#fff3c400');
    ctx.fillStyle = ray; ctx.fillRect(x - 9, top - 60, 18, height + 60); ctx.restore();
  }
  const hands = pose === 'crouch' ? workingHands(activity, player.facing, x, y, clock, reducedMotion) : null;
  if (hands?.behind) for (const arm of hands.arms) drawFist(ctx, ...arm);   // seen from behind
  if (usingLegacyEquipment) paintPlayerLayers(ctx, player, left, top, equipment, compact);
  else paintPixelPlayer(ctx, player, left, top, {compact, reducedMotion});
  // Small brass clasp and collar glint keep the body readable over dark terrain.
  if (usingLegacyEquipment && !compact && !equipment.chest) {
    ctx.fillStyle = '#ffe6a4'; ctx.fillRect(Math.round(x) - 2 + lx, top + 25, 4, 2);
    ctx.fillStyle = '#845528'; ctx.fillRect(Math.round(x) - 1 + lx, top + 27, 2, 2);
  }
  if (fist && !(player.facing === 'north' && phase !== 'strike')) drawFist(ctx, ...fist);
  if (hands && !hands.behind) for (const arm of hands.arms) drawFist(ctx, ...arm);
  if (pose && activity.kind !== 'rest' && activity.kind !== 'kneel')
    drawActionInteraction(ctx, activity, x, y, clock, reducedMotion, {armDrawn: !!hands});
  if (activity) drawProgress(ctx, x, top - 6, activity.progress / 1000, clock);
  return {left, top, width, height};
}

/** Visible, cosmetic contact with the actual encounter cell. The simulation owns
 * timing and rewards; these marks only explain what the avatar is doing. */
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
  const shoulderY = y - 8;   // compact sprite: head y-28..y-14, torso below
  if (dir === 'south') return {behind: false, arms: [
    [x - 9, shoulderY, x - 6, y + 6 + beat], [x + 9, shoulderY, x + 6, y + 6 - beat]]};
  if (dir === 'north') return {behind: true, arms: [
    [x - 9, shoulderY, x - 11, y - 20 + beat], [x + 9, shoulderY, x + 11, y - 20 - beat]]};
  const side = dir === 'east' ? 1 : -1;
  return {behind: false, arms: [[x + side * 7, shoulderY, x + side * (19 + beat), y + 4]]};
}

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
    const sx = x + ux * 8, sy = y - 24 + uy * 3;
    const reach = 11 + beat * 4;
    drawFist(ctx, sx, sy, sx + ux * reach, sy + uy * reach - (activity.kind === 'climb' ? 8 + beat * 6 : 0));
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

/** Enemy at tile center (x, y). `hit` = ms since last HP loss; `dying` = 0..1 progress. */
export function drawEnemy(ctx, target, x, y, {clock = 0, hit = Infinity, dying = null, maxHp = 3, reducedMotion = false, ghost = false} = {}) {
  setupText(ctx);
  x = Math.round(x); y = Math.round(y);
  const {width, height} = spriteSize(ENEMY);
  const seed = visualHash(target.x, target.y, 77);
  const breathe = reducedMotion ? 0 : Math.floor((clock + seed % 1000) / 500) % 2;
  const shake = !reducedMotion && hit < 160 ? (Math.floor(hit / 40) % 2 ? 2 : -2) : 0;
  const left = x - width / 2 + shake, top = y + ACTOR_FOOT - height + breathe;
  if (dying !== null) {
    paintSprite(ctx, ENEMY, left, top - Math.round(dying * 6), {dissolve: dying, alpha: 1 - dying * .6, seed});
    return {left, top, width, height};
  }
  if (ghost) {
    // X-ray pass for an enemy hidden behind the player: translucent, no shadow.
    paintSprite(ctx, ENEMY, left, top, {flash: hit < 110, alpha: .42, seed});
    drawHealth(ctx, x, top - 7, target.hp, Math.max(maxHp, target.hp));
    return {left, top, width, height};
  }
  drawShadow(ctx, x, y, 17);
  paintSprite(ctx, ENEMY, left, top, {flash: hit < 110, seed});
  // Breath and horn glints distinguish a living boar from a static encounter prop.
  if (hit >= 110) {
    ctx.fillStyle = '#fff0c2';
    ctx.fillRect(left + 5, top + 8, 2, 3);
    ctx.fillRect(left + width - 7, top + 8, 2, 3);
    if (!reducedMotion) {
      ctx.save(); ctx.globalAlpha = .25 + .25 * Math.sin((clock + seed % 500) / 190);
      ctx.fillStyle = '#f1d2be';
      ctx.fillRect(x - 7, top + 31, 3, 2);
      ctx.fillRect(x + 5, top + 31, 3, 2);
      ctx.restore();
    }
  }
  drawHealth(ctx, x, top - 7, target.hp, Math.max(maxHp, target.hp));
  return {left, top, width, height};
}

export function drawHealth(ctx, cx, y, hp, maxHp) {
  const seg = 7, gap = 1, w = maxHp * seg + (maxHp - 1) * gap, x = Math.round(cx - w / 2);
  ctx.fillStyle = OUTLINE; ctx.fillRect(x - 1, y - 1, w + 2, 5);
  for (let i = 0; i < maxHp; i++) {
    ctx.fillStyle = i < hp ? '#e3604c' : '#3b1c19';
    ctx.fillRect(x + i * (seg + gap), y, seg, 3);
    if (i < hp) { ctx.fillStyle = '#ffa48a'; ctx.fillRect(x + i * (seg + gap), y, seg, 1); }
  }
}

/** Punch speed lines from the shoulder toward the facing; age in ms (0..200). */
export function drawPunchLines(ctx, x, y, facing, age, duration = 200) {
  if (age < 0 || age >= duration) return;
  const a = FACING_ANGLE[facing] ?? Math.PI / 2, t = age / duration;
  const cx = Math.cos(a), cy = Math.sin(a), px = -cy, py = cx;
  const ox = x + cx * 10, oy = y + ACTOR_FOOT - 30 + cy * 8;
  ctx.save(); ctx.globalAlpha = 1 - t; ctx.lineCap = 'round';
  for (const k of [-5, 0, 5]) {
    const sx = ox + px * k, sy = oy + py * k * .8, len = 9 - Math.abs(k) * .6;
    ctx.strokeStyle = OUTLINE; ctx.lineWidth = 4;
    ctx.beginPath(); ctx.moveTo(sx, sy); ctx.lineTo(sx + cx * len, sy + cy * len); ctx.stroke();
    ctx.strokeStyle = '#fff3d0'; ctx.lineWidth = 2;
    ctx.beginPath(); ctx.moveTo(sx, sy); ctx.lineTo(sx + cx * len, sy + cy * len); ctx.stroke();
  }
  ctx.restore();
}

/** Impact burst at a server effect cell (tile center coordinates). */
export function drawEffect(ctx, x, y, age = 0) {
  setupText(ctx);
  const r = 5 + Math.min(age, 160) / 20;
  ctx.globalAlpha = Math.max(0, 1 - age / 220);
  for (const [dx, dy, ch] of [[0, -r, '|'], [0, r, '|'], [-r, 0, '-'], [r, 0, '-'],
    [-r * .7, -r * .7, '\\'], [r * .7, r * .7, '\\'], [r * .7, -r * .7, '/'], [-r * .7, r * .7, '/']]) {
    ctx.fillStyle = OUTLINE; ctx.fillRect(x + dx - 2, y + dy - 4, 5, 8);
    ctx.fillStyle = '#ffe9a8'; ctx.fillText(ch, x + dx - 1, y + dy - 3);
  }
  ctx.fillStyle = '#fffbe8'; ctx.fillRect(Math.round(x) - 2, Math.round(y) - 2, 4, 4);
  ctx.globalAlpha = 1;
}

/** Floating combat/reward text above a point; age 0..duration ms. */
export function drawFloat(ctx, x, y, text, age, {color = '#ffd36a', duration = 600, size = 10} = {}) {
  if (age >= duration) return;
  ctx.save();
  ctx.font = `bold ${size}px Consolas, "Liberation Mono", monospace`;
  ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
  ctx.globalAlpha = Math.max(0, 1 - Math.max(0, age - duration / 2) / (duration / 2));
  const ty = Math.round(y - age / 30);
  ctx.lineWidth = 3; ctx.strokeStyle = OUTLINE; ctx.strokeText(text, x, ty);
  ctx.fillStyle = color; ctx.fillText(text, x, ty);
  ctx.restore();
}
export const drawDamage = (ctx, x, y, amount, age) => drawFloat(ctx, x, y, '-' + amount, age);

/** Encounter spot sprites: small ground features, outlined like actors. */
const SPOT_ROLES = Object.freeze({
  r: {fill: '#b8323f', ink: '#ffb0a0'}, l: {fill: '#3f6a2e', ink: '#8fbf5a'},
  o: {fill: '#7a5532', ink: '#c39a62'}, a: {fill: '#3c6f8f', ink: '#bfe8ff'},
  g: {fill: '#6d7468', ink: '#b9bfae'}, q: {fill: '#55743c', ink: '#a9c97a'},
  u: {fill: '#3b2a1c', ink: '#8b6b4a'}, x: {fill: '#6d7468', ink: '#f2d27a'},
  y: {fill: '#e5c772', ink: '#fff3bc'}, c: {fill: '#a6bacc', ink: '#e8f5ff'}
});
export const SPOTS = Object.freeze({
  bramble_berries: {paint: ['  l r l  ', ' lrlrlrl ', 'lrrllrrll', ' lllrlll '], glyph: ['  / o \\  ', ' /o/o/o\\ ', ';o;v;o;v;', ' \\;o;;;/ ']},
  fallen_branches: {paint: ['   l  l   ', ' oooooooo ', 'oooooooooo'], glyph: ['   /  \\   ', ' /==\\==\\  ', '=\\===/===/']},
  animal_tracks: {paint: ['u  u   u ', '  u  u   ', 'u   u  u '], glyph: ['v  v   v ', '  v  v   ', 'v   v  v ']},
  gnarled_tree: {paint: ['   lll   ', '  lllll  ', '  lolol  ', '   ooo   ', '  oo oo  '], glyph: ['   ^^^   ', '  /:::\\  ', '  (|:|)  ', '   |||   ', '  /| |\\  ']},
  forest_spring: {paint: ['  cccccc  ', ' gaaaaaag ', 'gaaaaaaaag', ' gggggggg '], glyph: ['  .    .  ', ' /~~~~~~\\ ', '|~*~~~~*~|', ' \\______/ ']},
  mossy_stone: {paint: ['   qqq   ', '  qgqgq  ', ' ggggggg ', '  ggggg  '], glyph: ['   .^.   ', '  /:,:\\  ', ' /:___:\\ ', '  \\___/  ']},
  old_carvings: {paint: ['   xxx   ', '  ggggg  ', '  gxgxg  ', '  ggggg  '], glyph: ['   *:*   ', '  /___\\  ', '  |*o*|  ', '  /___\\  ']},
  abandoned_camp: {paint: ['  rrrrr  ', 'orrrrrro ', ' ooooooo ', ' qooqooq '],
    glyph: ['  /^^^\\  ', ' /_____\\ ', ' |# # #| ', ' /_o_o_\\ ']},
  moonlit_pool: {paint: ['  ccccc  ', ' caaaaac ', 'caaaaaaac', ' gcccccg '],
    glyph: ['  .***.  ', ' /~~~~~\\ ', '|~*~~~*~|', ' \\_____/ ']},
  fallen_watchtower: {paint: ['  qxxq   ', '  qxxq   ', ' qxxxxq  ', ' qgxxgq  ', ' qgggggq '],
    glyph: ['  /++\\   ', '  |::|   ', ' /|::|\\  ', ' |/__\\|  ', ' /_//_\\  ']},
  mushroom_ring: {paint: [' r r r r ', 'rggrggrgr', ' gg gg gg', 'rgggggggr'],
    glyph: [' ^ ^ ^ ^ ', '/o\\/o\\/o\\', ' .. .. ..', '^.......^']}
});

/** The anchor stone at the anchor cell. Ground decoration only (non-blocking). */
const CAMP_ROLES = Object.freeze({g: {fill: '#5d6470', ink: '#9fd0ff'}, v: {fill: '#2b3140', ink: '#cfe6ff'},
  a: {fill: '#a9bed4', ink: '#f1faff'}, c: {fill: '#294661', ink: '#99daff'}});
export const CAMP = Object.freeze({
  stone: {paint: ['   aaa   ', '  agvga  ', '  gcvgg  ', '  gvcvg  ', '  gcvgg  ', '  ggvgg  ', ' ggggggg '],
    glyph: ['   /\\    ', '  /<>\\   ', '  |*|:|  ', '  |:O:|  ', '  |:|*|  ', '  \\:::/  ', ' /_____\\ ']}
});
function paintParts(ctx, sprite, roles, left, top, alpha = 1) {
  ctx.globalAlpha = alpha;
  ctx.fillStyle = OUTLINE;
  sprite.paint.forEach((row, r) => [...row].forEach((role, c) => {
    if (role !== ' ') ctx.fillRect(left + c * CELL_W - 1, top + r * CELL_H - 1, CELL_W + 2, CELL_H + 2);
  }));
  sprite.paint.forEach((row, r) => [...row].forEach((role, c) => {
    if (role === ' ') return;
    ctx.fillStyle = roles[role].fill; ctx.fillRect(left + c * CELL_W, top + r * CELL_H, CELL_W, CELL_H);
    const ch = sprite.glyph[r][c];
    if (ch !== ' ') { ctx.fillStyle = roles[role].ink; ctx.fillText(ch, left + c * CELL_W, top + r * CELL_H); }
  }));
  ctx.globalAlpha = 1;
}
export function drawCamp(ctx, x, y, {clock = 0, reducedMotion = false} = {}) {
  setupText(ctx);
  x = Math.round(x); y = Math.round(y);
  const pulse = reducedMotion ? .35 : .3 + .18 * Math.sin(clock / 520);
  // The soul tether rises behind the stone, never entering the location asset.
  ctx.save();
  ctx.globalAlpha = reducedMotion ? .18 : .14 + pulse * .18;
  const beam = ctx.createLinearGradient(x - 18, y - 88, x - 18, y + 12);
  beam.addColorStop(0, '#9bd9ff00');
  beam.addColorStop(.35, '#9bd9ff');
  beam.addColorStop(1, '#cceeff00');
  ctx.fillStyle = beam;
  ctx.beginPath(); ctx.moveTo(x - 26, y - 86); ctx.lineTo(x - 10, y - 86);
  ctx.lineTo(x - 2, y + 14); ctx.lineTo(x - 34, y + 14); ctx.closePath(); ctx.fill();
  ctx.restore();
  ctx.save(); ctx.globalAlpha = pulse;
  const glow = ctx.createRadialGradient(x, y + 2, 2, x, y + 2, 46);
  glow.addColorStop(0, '#9fd0ff'); glow.addColorStop(1, '#9fd0ff00');
  ctx.fillStyle = glow; ctx.beginPath(); ctx.ellipse(x, y + 4, 46, 20, 0, 0, Math.PI * 2); ctx.fill(); ctx.restore();
  ctx.save(); ctx.strokeStyle = '#80b9e3'; ctx.lineWidth = 2; ctx.globalAlpha = pulse + .18;
  ctx.beginPath(); ctx.ellipse(x - 18, y + 14, 42, 13, 0, 0, Math.PI * 2); ctx.stroke();
  for (let i = 0; i < 8; i++) {
    const angle = i * Math.PI / 4, rx = x - 18 + Math.cos(angle) * 42, ry = y + 14 + Math.sin(angle) * 13;
    ctx.fillStyle = '#d4eeff'; ctx.fillRect(Math.round(rx) - 1, Math.round(ry) - 1, 3, 3);
  }
  ctx.restore();
  paintParts(ctx, CAMP.stone, CAMP_ROLES, x - 36, y - 56);
  for (let i = 0; i < 4; i++) {
    const phase = reducedMotion ? i * 1.57 : clock / 700 + i * 1.57;
    const sx = x - 18 + Math.cos(phase) * (24 + i % 2 * 6);
    const sy = y - 44 + Math.sin(phase) * 9 - i * 6;
    ctx.save(); ctx.globalAlpha = .45 + pulse * .5;
    ctx.fillStyle = '#c8edff'; ctx.fillRect(Math.round(sx) - 1, Math.round(sy) - 3, 3, 6);
    ctx.fillStyle = '#f3fcff'; ctx.fillRect(Math.round(sx), Math.round(sy) - 2, 1, 3);
    ctx.restore();
  }
  ctx.globalAlpha = 1;
}

/** The origin is the road ambush: two broken wagons and scattered supplies.
 * This is scenery only, behind actors and independent of collision. */
export function drawAmbushSite(ctx, x, y) {
  ctx.save();
  ctx.translate(Math.round(x), Math.round(y));
  ctx.lineJoin='round';
  // Snapped cart, tilted canopy and axle to the west of the anchor.
  ctx.fillStyle='#38291d';ctx.fillRect(-146,-23,88,23);
  ctx.fillStyle='#80603c';ctx.fillRect(-140,-29,70,13);
  ctx.fillStyle='#b89465';ctx.fillRect(-138,-28,51,4);
  ctx.fillStyle='#563a2a';ctx.beginPath();ctx.moveTo(-139,-30);ctx.lineTo(-126,-59);ctx.lineTo(-78,-51);ctx.lineTo(-67,-29);ctx.closePath();ctx.fill();
  ctx.fillStyle='#b6a17a';ctx.beginPath();ctx.moveTo(-131,-51);ctx.lineTo(-112,-59);ctx.lineTo(-94,-51);ctx.lineTo(-81,-54);ctx.lineTo(-75,-38);ctx.lineTo(-99,-43);ctx.closePath();ctx.fill();
  ctx.strokeStyle='#55402f';ctx.lineWidth=4;ctx.beginPath();ctx.moveTo(-137,-28);ctx.lineTo(-69,-28);ctx.moveTo(-111,-54);ctx.lineTo(-96,-34);ctx.stroke();
  const wheel=(wx,wy)=>{ctx.fillStyle='#201c1a';ctx.beginPath();ctx.arc(wx,wy,18,0,Math.PI*2);ctx.fill();
    ctx.strokeStyle='#ad8554';ctx.lineWidth=5;ctx.beginPath();ctx.arc(wx,wy,14,0,Math.PI*2);ctx.stroke();
    ctx.lineWidth=2;for(let i=0;i<6;i++){let a=i*Math.PI/3;ctx.beginPath();ctx.moveTo(wx,wy);ctx.lineTo(wx+Math.cos(a)*12,wy+Math.sin(a)*12);ctx.stroke();}
    ctx.fillStyle='#d1ab6e';ctx.fillRect(wx-3,wy-3,6,6);};
  wheel(-121,0);wheel(-69,0);
  // Second wagon lies on its side; torn crimson cover recalls the raid.
  ctx.fillStyle='#35291e';ctx.beginPath();ctx.moveTo(74,-8);ctx.lineTo(129,-35);ctx.lineTo(150,-19);ctx.lineTo(96,12);ctx.closePath();ctx.fill();
  ctx.strokeStyle='#a98150';ctx.lineWidth=6;ctx.beginPath();ctx.moveTo(72,-7);ctx.lineTo(130,-36);ctx.moveTo(93,13);ctx.lineTo(150,-19);ctx.stroke();
  ctx.fillStyle='#7c3d39';ctx.beginPath();ctx.moveTo(84,-40);ctx.lineTo(111,-52);ctx.lineTo(135,-34);ctx.lineTo(101,-19);ctx.closePath();ctx.fill();
  ctx.fillStyle='#ad6355';ctx.beginPath();ctx.moveTo(87,-39);ctx.lineTo(108,-49);ctx.lineTo(119,-40);ctx.lineTo(95,-29);ctx.closePath();ctx.fill();
  wheel(143,7);
  // Crates, loose planks and arrows on both sides of the road.
  for(const [px,py] of [[-42,17],[-25,28],[43,22],[60,37]]){ctx.fillStyle='#654529';ctx.fillRect(px,py,18,13);ctx.strokeStyle='#ad8653';ctx.lineWidth=2;ctx.strokeRect(px+1,py+1,16,11);ctx.beginPath();ctx.moveTo(px+2,py+2);ctx.lineTo(px+16,py+11);ctx.stroke();}
  ctx.strokeStyle='#96744c';ctx.lineWidth=3;for(const [ax,ay] of [[-152,28],[-12,38],[32,-31],[153,34]]){ctx.beginPath();ctx.moveTo(ax,ay);ctx.lineTo(ax+25,ay-9);ctx.stroke();}
  ctx.strokeStyle='#b7a67c';ctx.lineWidth=2;for(const [ax,ay] of [[-32,-18],[47,-11],[79,30]]){ctx.beginPath();ctx.moveTo(ax,ay);ctx.lineTo(ax+17,ay+8);ctx.stroke();ctx.beginPath();ctx.moveTo(ax+1,ay-3);ctx.lineTo(ax+1,ay+3);ctx.stroke();}
  ctx.restore();
}

/** Spot at tile center (x, y); a sparkle marks it, brighter when it is the goal. */
export function drawSpot(ctx, spot, x, y, {clock = 0, goal = false, fade = 0} = {}) {
  const sprite = SPOTS[spot.encounter];
  if (!sprite) return;
  setupText(ctx);
  x = Math.round(x); y = Math.round(y);
  const w = sprite.paint[0].length * CELL_W, h = sprite.paint.length * CELL_H;
  const left = x - w / 2, top = y + ACTOR_FOOT - 2 - h;
  ctx.save(); ctx.globalAlpha = 1 - fade;
  ctx.fillStyle = OUTLINE;
  sprite.paint.forEach((row, r) => [...row].forEach((role, c) => {
    if (role !== ' ') ctx.fillRect(left + c * CELL_W - 1, top + r * CELL_H - 1, CELL_W + 2, CELL_H + 2);
  }));
  sprite.paint.forEach((row, r) => [...row].forEach((role, c) => {
    if (role === ' ') return;
    ctx.fillStyle = SPOT_ROLES[role].fill; ctx.fillRect(left + c * CELL_W, top + r * CELL_H, CELL_W, CELL_H);
    const ch = sprite.glyph[r][c];
    if (ch !== ' ') { ctx.fillStyle = SPOT_ROLES[role].ink; ctx.fillText(ch, left + c * CELL_W, top + r * CELL_H); }
  }));
  if (!fade) {
    const lift = Math.round(Math.sin((clock + visualHash(spot.x, spot.y, 3) % 900) / 300) * 2);
    const sy = top - 7 + lift, size = goal ? 3 : 2;
    ctx.fillStyle = OUTLINE; ctx.fillRect(x - size - 1, sy - size - 1, size * 2 + 2, size * 2 + 2);
    ctx.fillStyle = goal ? '#fff0b0' : '#d8b860'; ctx.fillRect(x - size, sy - size, size * 2, size * 2);
  }
  ctx.restore();
}

/** A finished task leaves a brief, readable seal over its former spot. This is
 * presentation only; the encounter log and simulation decide completion. */
export function drawSpotCompletion(ctx, spot, x, y, age, reducedMotion = false) {
  if (age < 0 || age >= 650) return;
  const t = age / 650;
  ctx.save(); ctx.globalAlpha = Math.max(0, 1 - t);
  const color = spot.encounter === 'forest_spring' ? '#a9eaff'
    : spot.encounter === 'old_carvings' ? '#d3b6ff' : '#ffe5a0';
  ctx.strokeStyle = color; ctx.lineWidth = 2;
  ctx.beginPath(); ctx.ellipse(x, y + 4, reducedMotion ? 19 : 6 + t * 23,
    reducedMotion ? 8 : 3 + t * 9, 0, 0, Math.PI * 2); ctx.stroke();
  for (let i = 0; i < 6; i++) {
    const angle = i * Math.PI / 3 + (reducedMotion ? 0 : t * .5);
    const radius = reducedMotion ? 21 : 8 + t * 26;
    ctx.fillStyle = i % 2 ? '#fff9df' : color;
    ctx.fillRect(Math.round(x + Math.cos(angle) * radius) - 2,
      Math.round(y - 4 + Math.sin(angle) * radius * .55) - 2, 4, 4);
  }
  ctx.restore();
}

/** Enemies standing just behind (north of) the player are largely covered by the
 * taller player sprite; they get a translucent x-ray pass drawn over the player. */
export function hiddenBehind(target, player) {
  const dy = player.y - target.y;
  return target.hp > 0 && dy >= 1 && dy <= 2 && Math.abs(player.x - target.x) <= 1;
}

/** Torso-height point for combat marks on a tile (feet sit below tile center). */
export const TORSO_LIFT = 14;

/** Tiles whose tree canopy must be repainted over an actor standing at (tx, ty):
 * trees one or two rows south and one column either side overlap the sprite. */
export function occludingTreeTiles(tx, ty) {
  const result = [];
  for (let dy = 1; dy <= 2; dy++) for (let dx = -1; dx <= 1; dx++) result.push({x: tx + dx, y: ty + dy});
  return result;
}

export const actorFootY = ty => (ty + .5) * TILE_H + ACTOR_FOOT;
export const tileCenter = (tx, ty) => ({x: (tx + .5) * TILE_W, y: (ty + .5) * TILE_H});

/** The old man who finds the newborn avatar: hooded grey robe, white beard, staff.
 * Presentation only; the server says where he stands during the prologue. */
const ELDER_ROLES = Object.freeze({h: {fill: '#6b6457', ink: '#a39a86'}, r: {fill: '#57594f', ink: '#8d8f80'},
  s: {fill: '#d8b48c', ink: '#3a2618'}, w: {fill: '#ece6d6', ink: '#b9b19c'}, o: {fill: '#7b5a36', ink: '#b88c58'},
  g: {fill: '#f1d27a', ink: '#fff6cf'}, b: {fill: '#3a2c20', ink: '#76604a'}});
export const ELDER = Object.freeze({paint: [
  ' g  hhh   ', ' o hhhhh  ', ' o hsshh  ', ' oswwwhr  ', ' o wwwrrr ',
  ' o rwrrrr ', ' o rrrrrr ', ' o rrrrrr ', ' o  bb bb '], glyph: [
  ' *  /^\\   ', ' | /:::\\  ', ' | (o.:\\  ', ' |-;;;:|\\ ', ' | ;;;:::\\',
  ' | |;::::|', ' | |::::| ', ' | /::::\\ ', ' |  -- -- ']});
export function drawElder(ctx, x, y, {clock = 0, facing = 'west', alpha = 1, talking = false, reducedMotion = false} = {}) {
  setupText(ctx);
  x = Math.round(x); y = Math.round(y);
  const sprite = facing === 'east' ? mirrorSprite(ELDER) : ELDER;
  const width = sprite.paint[0].length * CELL_W, height = sprite.paint.length * CELL_H;
  const sway = reducedMotion ? 0 : Math.floor(clock / 900) % 2;
  const left = x - width / 2, top = y + ACTOR_FOOT - height + sway;
  ctx.save(); ctx.globalAlpha = alpha;
  ctx.fillStyle = 'rgba(3, 6, 3, .5)';
  ctx.beginPath(); ctx.ellipse(x, y + ACTOR_FOOT - 1, 15, 4, 0, 0, Math.PI * 2); ctx.fill();
  paintParts(ctx, sprite, ELDER_ROLES, left, top, alpha);
  // Lantern-warm glint on the staff head.
  const gx = facing === 'east' ? left + width - CELL_W * 2 : left + CELL_W;
  ctx.globalAlpha = alpha * (.35 + (reducedMotion ? .1 : .15 * Math.sin(clock / 300)));
  const glow = ctx.createRadialGradient(gx + 2, top + 3, 1, gx + 2, top + 3, 14);
  glow.addColorStop(0, '#ffe7a0'); glow.addColorStop(1, '#ffe7a000');
  ctx.fillStyle = glow; ctx.fillRect(gx - 12, top - 11, 28, 28);
  if (talking) {  // three speech dots above the hood
    for (let i = 0; i < 3; i++) {
      const lift = reducedMotion ? 0 : Math.round(Math.max(0, Math.sin(clock / 160 - i * .9)) * 3);
      ctx.globalAlpha = alpha;
      ctx.fillStyle = OUTLINE; ctx.fillRect(x - 9 + i * 7, top - 12 - lift, 6, 6);
      ctx.fillStyle = '#f3e7c6'; ctx.fillRect(x - 8 + i * 7, top - 11 - lift, 4, 4);
    }
  }
  ctx.restore();
  return {left, top, width, height};
}
