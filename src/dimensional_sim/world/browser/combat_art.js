/** Enemies and combat feedback: boar sprite, health pips, reach marker, punch
 * lines, impact bursts and floating numbers. Cosmetic only; the server owns combat. */
import {TILE_W, TILE_H, visualHash} from './view.js';
import {setupText} from './art.js';
import {ACTOR_FOOT, FACING_ANGLE, OUTLINE, drawShadow, paintSprite, spriteSize} from './sprites.js';

// 11 columns x 7 rows = 44x49 px.
export const ENEMY = Object.freeze({paint: [
  ' h       h ', ' hh fff hh ', '  fffffff  ', ' ffefffeff ', 'dfffmmmfffd',
  ' dfwfffwfd ', '  dd   dd  '], glyph: [
  ' /       \\ ', ' (\\ ^^^ /) ', '  ;;;;;;;  ', ' ;;o;;;o;; ', '/;;;vvv;;;\\',
  " \\;V;;;V;/ ", "  ''   ''  "]});

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

/** One-cell cardinal reach and the server-selected target, shown during Active play. */
export function drawUnarmedReach(ctx, x, y, target = null, attacking = false) {
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
export const drawDamage = (ctx, x, y, amount, age) => drawFloat(ctx, x, y, '-' + amount, age);
