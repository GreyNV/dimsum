/** Enemies and combat feedback: boar sprite, health pips, reach marker, punch
 * lines, impact bursts and floating numbers. Cosmetic only; the server owns combat. */
import {TILE_W, TILE_H, visualHash} from './view.js';
import {setupText} from './art.js';
import {ACTOR_FOOT, FACING_ANGLE, OUTLINE, drawShadow, paintSprite, spriteSize} from './sprites.js';
import {ENEMY_FRAMES, drawPainted, enemyCanvas, flashCanvas} from './painted.js';

// 11 columns x 7 rows = 44x49 px.
export const ENEMY = Object.freeze({paint: [
  ' h       h ', ' hh fff hh ', '  fffffff  ', ' ffefffeff ', 'dfffmmmfffd',
  ' dfwfffwfd ', '  dd   dd  '], glyph: [
  ' /       \\ ', ' (\\ ^^^ /) ', '  ;;;;;;;  ', ' ;;o;;;o;; ', '/;;;vvv;;;\\',
  " \\;V;;;V;/ ", "  ''   ''  "]});
/** Enemy art by catalog sprite key (catalog.EnemyDef.sprite); unknown keys draw ENEMY. */
/** River lurker: low and wide, splayed legs, eyes on top - a different silhouette from the boar. */
export const LURKER = Object.freeze({paint: [
  '  y     y  ', ' lylllllyl ', 'llnnnnnnnll', 'r lllllll r', 'rr  l l  rr'], glyph: [
  '  o     o  ', ' (O=====O) ', '<:vvvvvvv:>', '/ ;;;;;;; \\', '<<  ^ ^  >>']});
/** Restless bones: an upright skeleton with cold eyes and a rusted blade - the only
 * two-legged enemy, so it reads as a person-shaped threat at a glance. */
export const SKELETON = Object.freeze({paint: ["   ggggg   ", "   gigig   ", "    ggg  j ", "  ggogogg j", "  g gog gj ", "   gg gg   ", "   gg gg   "],
  glyph: ["   .---.   ", "   |o:o|   ", "    \\=/  / ", "  /=)=(=\\ |", "  ' =|= '| ", "   /| |\\   ", "   =' '=   "]});
/** Pale wisp: a small cold light with trailing wisps; it floats, so it bobs and glows. */
export const WISP = Object.freeze({paint: ["   uuu   ", "  uqqqu  ", " uqqqqqu ", "  uqqqu  ", "   vuv   ", "  v v v  "],
  glyph: ["   .-.   ", "  (o o)  ", " ( ~~~ ) ", "  \\___/  ", "   )|(   ", "  ' ' '  "]});
/** Wolf (night only): seen side-on - long and low, ears up, a pointed muzzle and a brushy tail,
 * so it never reads as a grey boar. */
export const WOLF = Object.freeze({paint: [
  '         x x ',
  '        xxxxx',
  ' z  xxxxxxEww',
  'zzxxxxxxxxxx ',
  '  xzxxxxxzx  ',
  '  z z   z z  '], glyph: [
  '         ^ ^ ',
  '        /;;;\\',
  ' ~  ;;;;;;o=>',
  '/~;;;;;;;;;; ',
  "  ;';;;;;';  ",
  '  | |   | |  ']});
export const ENEMY_SPRITES = Object.freeze({boar: ENEMY, lurker: LURKER, skeleton: SKELETON, wisp: WISP, wolf: WOLF});

/** Enemy at tile center (x, y). `hit` = ms since last HP loss; `dying` = 0..1 progress. */
export function drawEnemy(ctx, target, x, y, {clock = 0, hit = Infinity, dying = null, maxHp = 3, reducedMotion = false, ghost = false, reflection = false} = {}) {
  setupText(ctx);
  x = Math.round(x); y = Math.round(y);
  const sprite = ENEMY_SPRITES[target.sprite] || ENEMY;
  const {width, height} = spriteSize(sprite);
  const seed = visualHash(target.x, target.y, 77);
  const breathe = reducedMotion ? 0 : Math.floor((clock + seed % 1000) / 500) % 2;
  const shake = !reducedMotion && hit < 160 ? (Math.floor(hit / 40) % 2 ? 2 : -2) : 0;
  const float = sprite === WISP ? (reducedMotion ? -8 : -8 + Math.round(3 * Math.sin((clock + seed % 900) / 260))) : 0;
  const kind = ENEMY_FRAMES[target.sprite] ? target.sprite : 'boar';
  const painted = enemyCanvas(kind, breathe);
  if (painted) return drawPaintedEnemy(ctx, target, painted, kind, x, y, {clock, hit, dying, maxHp, reducedMotion, ghost, reflection, shake, float, seed, breathe});
  const left = x - width / 2 + shake, top = y + ACTOR_FOOT - height + breathe + float;
  if (dying !== null) {
    paintSprite(ctx, sprite, left, top - Math.round(dying * 6), {dissolve: dying, alpha: 1 - dying * .6, seed});
    return {left, top, width, height};
  }
  if (ghost) {
    // X-ray pass for an enemy hidden behind the player: translucent, no shadow.
    paintSprite(ctx, sprite, left, top, {flash: hit < 110, alpha: .42, seed});
    drawHealth(ctx, x, top - 7, target.hp, Math.max(maxHp, target.hp));
    return {left, top, width, height};
  }
  if (reflection) { paintSprite(ctx, sprite, left, top, {seed}); return {left, top, width, height}; }
  if (sprite === WISP) {   // a soft cold halo instead of a shadow on the ground
    const glow = ctx.createRadialGradient(x, top + height / 2, 2, x, top + height / 2, 26);
    glow.addColorStop(0, '#cfe6ff55'); glow.addColorStop(1, '#cfe6ff00');
    ctx.fillStyle = glow; ctx.fillRect(x - 26, top + height / 2 - 26, 52, 52);
    drawShadow(ctx, x, y, 7);
  } else drawShadow(ctx, x, y, 17);
  paintSprite(ctx, sprite, left, top, {flash: hit < 110, seed});
  // Breath and horn glints distinguish a living boar from a static encounter prop.
  if (hit >= 110 && sprite === ENEMY) {
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
  if (hit >= 110 && sprite === SKELETON) {   // cold eye-light, flickering
    ctx.save(); ctx.globalAlpha = reducedMotion ? .8 : .55 + .45 * Math.abs(Math.sin((clock + seed % 700) / 230));
    ctx.fillStyle = '#bff3ff';
    ctx.fillRect(left + 4 * 4 + 1, top + 7 + 3, 2, 2); ctx.fillRect(left + 6 * 4 + 1, top + 7 + 3, 2, 2);
    ctx.restore();
  }
  drawHealth(ctx, x, top - 7, target.hp, Math.max(maxHp, target.hp));
  return {left, top, width, height};
}

/** The painted enemy (painted.js): same placement, flash, ghost, reflection and dying rules. */
function drawPaintedEnemy(ctx, target, painted, kind, x, y, {clock, hit, dying, maxHp, reducedMotion, ghost, reflection, shake, float, seed, breathe}) {
  const [width, height] = ENEMY_FRAMES[kind];
  const left = x - width / 2 + shake, top = y + ACTOR_FOOT - height + float;
  const key = `enemy|${kind}|${breathe}`;
  if (dying !== null) {   // sinks a little and fades as it dissolves
    drawPainted(ctx, painted, left, top - Math.round(dying * 6), 1 - dying);
    return {left, top, width, height};
  }
  const flash = hit < 110 ? flashCanvas(painted, key) : painted;
  if (ghost) {
    drawPainted(ctx, flash, left, top, .42);
    drawHealth(ctx, x, top - 7, target.hp, Math.max(maxHp, target.hp));
    return {left, top, width, height};
  }
  if (reflection) { drawPainted(ctx, painted, left, top); return {left, top, width, height}; }
  if (kind === 'wisp') {   // a soft cold halo instead of a shadow on the ground
    const glow = ctx.createRadialGradient(x, top + 15, 2, x, top + 15, 26);
    glow.addColorStop(0, '#cfe6ff55'); glow.addColorStop(1, '#cfe6ff00');
    ctx.fillStyle = glow; ctx.fillRect(x - 26, top - 11, 52, 52);
    drawShadow(ctx, x, y, 7);
  } else drawShadow(ctx, x, y, kind === 'wolf' ? 20 : kind === 'lurker' ? 19 : kind === 'skeleton' ? 11 : 17);
  drawPainted(ctx, flash, left, top);
  if (hit >= 110 && !reducedMotion && kind === 'boar') {   // breath puffs from the snout
    ctx.save(); ctx.globalAlpha = .18 + .18 * Math.sin((clock + seed % 500) / 190);
    ctx.fillStyle = '#f1e2d6';
    ctx.beginPath(); ctx.ellipse(left + 18, top + 40, 2, 1.2, 0, 0, Math.PI * 2); ctx.ellipse(left + 28, top + 40, 2, 1.2, 0, 0, Math.PI * 2); ctx.fill();
    ctx.restore();
  }
  if (hit >= 110 && kind === 'skeleton') {   // cold eye-light, flickering
    ctx.save(); ctx.globalAlpha = reducedMotion ? .8 : .55 + .45 * Math.abs(Math.sin((clock + seed % 700) / 230));
    for (const s of [-1, 1]) {
      const g = ctx.createRadialGradient(left + 20 + s * 2.6, top + 10.8, 0, left + 20 + s * 2.6, top + 10.8, 2.4);
      g.addColorStop(0, '#e8fbff'); g.addColorStop(.4, '#8fe3ff'); g.addColorStop(1, 'rgba(143,227,255,0)');
      ctx.fillStyle = g; ctx.fillRect(left + 20 + s * 2.6 - 2.4, top + 8.4, 4.8, 4.8);
    }
    ctx.restore();
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

/** The blow's reach (one cell for fists; a weapon adds marks along the four lines it can
 * strike) and the server-selected target, shown during Active play. */
export function drawUnarmedReach(ctx, x, y, target = null, attacking = false, reach = 1) {
  const foot = y + ACTOR_FOOT - 2;
  ctx.save();
  ctx.lineWidth = 1.5;
  ctx.strokeStyle = target ? '#f2cb79' : '#a8b88b';
  ctx.fillStyle = target ? '#d9a65325' : '#8caf6b12';
  ctx.globalAlpha = attacking ? .85 : target ? .68 : .42;
  ctx.beginPath();
  ctx.moveTo(x, foot - TILE_H);
  ctx.lineTo(x + TILE_W, foot);
  ctx.lineTo(x, foot + TILE_H);
  ctx.lineTo(x - TILE_W, foot);
  ctx.closePath();
  ctx.fill(); ctx.stroke();
  for (let step = 2; step <= reach; step++) for (const [dx, dy] of [[1, 0], [-1, 0], [0, 1], [0, -1]]) {
    ctx.fillStyle = target ? '#f2cb79' : '#a8b88b';
    ctx.fillRect(Math.round(x + dx * step * TILE_W) - 2, Math.round(foot + dy * step * TILE_H) - 2, 4, 4);
  }
  if (target) {
    const [tx, ty] = target;
    ctx.globalAlpha = 1;
    ctx.strokeStyle = '#ffdb8f';
    ctx.lineWidth = 2;
    ctx.strokeRect(tx - TILE_W * .42, ty - TILE_H * .45, TILE_W * .84, TILE_H * .9);
    ctx.beginPath(); ctx.moveTo(x, foot); ctx.lineTo(tx, ty); ctx.stroke();
  }
  ctx.restore();
}

/** Punch speed lines from the shoulder toward the facing; age in ms (0..200). */
export function drawPunchLines(ctx, x, y, facing, age, duration = 200) {
  if (age < 0 || age >= duration) return;
  const a = FACING_ANGLE[facing] ?? Math.PI / 2, t = age / duration;
  const cx = Math.cos(a), cy = Math.sin(a), px = -cy, py = cx;
  const ox = x + cx * 7, oy = y + ACTOR_FOOT - 20 + cy * 5;
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
/** A rare drop's reveal: a ring and eight rays in the rarity color, around (x, y). */
export function drawReveal(ctx, x, y, color, age, reducedMotion = false, duration = 700) {
  if (age < 0 || age >= duration) return;
  const t = age / duration;
  ctx.save(); ctx.globalAlpha = Math.max(0, 1 - t);
  ctx.strokeStyle = color; ctx.lineWidth = 2;
  const r = reducedMotion ? 16 : 6 + t * 22;
  ctx.beginPath(); ctx.arc(x, y, r, 0, Math.PI * 2); ctx.stroke();
  ctx.fillStyle = color;
  for (let i = 0; i < 8; i++) {
    const a = i * Math.PI / 4;
    ctx.fillRect(Math.round(x + Math.cos(a) * (r + 5)) - 1, Math.round(y + Math.sin(a) * (r + 5)) - 1, 3, 3);
  }
  ctx.restore();
}
export const drawDamage = (ctx, x, y, amount, age) => drawFloat(ctx, x, y, '-' + amount, age);
