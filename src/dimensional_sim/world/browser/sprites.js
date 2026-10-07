/** Shared sprite machinery for actor art: palette roles, outlined cell sprites,
 * shadows and depth helpers.
 *
 * Sprites are solid outlined silhouettes on the same 4x7 drawing cells as the
 * terrain, so they share its texture but read clearly against busy ground.
 * Each sprite is two equal-sized row arrays: `paint` (color role per cell, space =
 * transparent) and `glyph` (texture character per cell, space = none).
 */
import {CELL_W, CELL_H, visualHash} from './view.js';

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

/** Unit direction angle per facing (east = 0, clockwise on screen). */
export const FACING_ANGLE = Object.freeze({east: 0, south: Math.PI / 2, west: Math.PI, north: -Math.PI / 2});

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

export function paintParts(ctx, sprite, roles, left, top, alpha = 1) {
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
