/** Shared sprite machinery for actor art: palette roles, outlined cell sprites,
 * shadows and depth helpers.
 *
 * Sprites are solid outlined silhouettes on the same 4x7 drawing cells as the
 * terrain, so they share its texture but read clearly against busy ground.
 * Each sprite is two equal-sized row arrays: `paint` (color role per cell, space =
 * transparent) and `glyph` (texture character per cell, space = none).
 */
import {CELL_W, CELL_H, visualHash} from './view.js';
import {cellSpriteCanvas} from './fine_art.js';

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
  m: {fill: '#24090e', ink: '#f1e6cc'}, w: {fill: '#ece0c2', ink: '#a8977a'},
  // Enemy (river lurker): wet green-blue hide, pale belly, yellow eyes on top of the head.
  l: {fill: '#2f5f57', ink: '#16352f'}, n: {fill: '#9fbf8a', ink: '#5c7a4a'},
  y: {fill: '#e8d84a', ink: '#2a2a10'}, r: {fill: '#1b3d37', ink: '#7fc9b8'},
  // Enemy (restless bones): old bone, dark gaps between the ribs, cold eye-light, a rusted blade.
  g: {fill: '#d8d2bc', ink: '#5e584a'}, o: {fill: '#3a362e', ink: '#b9b29a'},
  i: {fill: '#14100c', ink: '#8fe3ff'}, j: {fill: '#7a4a2a', ink: '#d09060'},
  // Enemy (pale wisp): a bright core, a blue halo, fading tendrils.
  q: {fill: '#eaf6ff', ink: '#7fa8d8'}, u: {fill: '#7e9ad0', ink: '#e2eeff'}, v: {fill: '#3e4f86', ink: '#a9bcf2'},
  // Enemy (wolf, night only): smoke-grey coat, a darker saddle, moon-yellow eyes, white teeth.
  x: {fill: '#5f646b', ink: '#33373c'}, z: {fill: '#3a3d43', ink: '#1c1e22'}, E: {fill: '#20160a', ink: '#ffe066'}
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
  const fine = cellSpriteCanvas(sprite, ROLE, CELL_W, CELL_H, {flash: flash ? FLASH : null});
  if (fine) { drawFine(ctx, fine, x, y, alpha, dissolve > 0 ? keep : null); return; }
  ctx.globalAlpha = alpha;
  ctx.fillStyle = OUTLINE;
  paint.forEach((row, r) => [...row].forEach((role, c) => {
    if (role !== ' ' && keep(r, c)) ctx.fillRect(x + c * CELL_W - 1, y + r * CELL_H - 1, CELL_W + 2, CELL_H + 2);
  }));
  paint.forEach((row, r) => [...row].forEach((role, c) => {
    if (role === ' ' || !keep(r, c)) return;
    ctx.fillStyle = flash ? FLASH : ROLE[role].fill;
    ctx.fillRect(x + c * CELL_W, y + r * CELL_H, CELL_W, CELL_H);
    if (!flash) litCell(ctx, paint, r, c, x + c * CELL_W, y + r * CELL_H);
  }));
  if (!flash) paint.forEach((row, r) => [...row].forEach((role, c) => {
    const ch = glyph[r][c];
    if (role === ' ' || ch === ' ' || !keep(r, c)) return;
    ctx.fillStyle = ROLE[role].ink;
    ctx.fillText(ch, x + c * CELL_W, y + r * CELL_H);
  }));
  ctx.globalAlpha = 1;
}

/** Light from the upper left on a cell sprite (the same light as the lit trees and rocks):
 * cells darken toward the lower right, and cells on the lit rim (nothing above or to the
 * left) catch a thin highlight. Drawn over a cell's fill, under its glyph. */
export function litCell(ctx, paint, r, c, x, y) {
  const rows = paint.length, cols = paint[0].length;
  const dark = .3 * (.65 * r / Math.max(1, rows - 1) + .35 * c / Math.max(1, cols - 1));
  ctx.fillStyle = `rgba(4, 6, 4, ${dark.toFixed(3)})`;
  ctx.fillRect(x, y, CELL_W, CELL_H);
  ctx.fillStyle = 'rgba(255, 248, 214, .2)';
  if (r === 0 || paint[r - 1][c] === ' ') ctx.fillRect(x, y, CELL_W, 1);
  if (c === 0 || paint[r][c - 1] === ' ') ctx.fillRect(x, y, 1, CELL_H);
}

export function drawShadow(ctx, x, y, rx) {
  ctx.fillStyle = 'rgba(3, 6, 3, .5)';
  ctx.beginPath(); ctx.ellipse(x, y + ACTOR_FOOT - 1, rx, 4, 0, 0, Math.PI * 2); ctx.fill();
}

export function paintParts(ctx, sprite, roles, left, top, alpha = 1) {
  const fine = cellSpriteCanvas(sprite, roles, CELL_W, CELL_H);
  if (fine) { drawFine(ctx, fine, left, top, alpha); return; }
  ctx.globalAlpha = alpha;
  ctx.fillStyle = OUTLINE;
  sprite.paint.forEach((row, r) => [...row].forEach((role, c) => {
    if (role !== ' ') ctx.fillRect(left + c * CELL_W - 1, top + r * CELL_H - 1, CELL_W + 2, CELL_H + 2);
  }));
  sprite.paint.forEach((row, r) => [...row].forEach((role, c) => {
    if (role === ' ') return;
    ctx.fillStyle = roles[role].fill; ctx.fillRect(left + c * CELL_W, top + r * CELL_H, CELL_W, CELL_H);
    litCell(ctx, sprite.paint, r, c, left + c * CELL_W, top + r * CELL_H);
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
 * trees up to five rows south and two columns either side overlap the sprite. */
export function occludingTreeTiles(tx, ty) {
  // Trees stand 2-4x a person (art.treeScale): canopies rooted up to five rows south and two
  // columns aside can cover an actor.
  const result = [];
  for (let dy = 1; dy <= 5; dy++) for (let dx = -2; dx <= 2; dx++) result.push({x: tx + dx, y: ty + dy});
  return result;
}

/** Copy a fine sprite canvas (fine_art.js) with its cell grid's top-left at (x, y), smoothly
 * resampled. `keep(r, c)` (dying enemies) erases the cells that have dissolved. */
let scratch = null;
export function drawFine(ctx, fine, x, y, alpha = 1, keep = null) {
  let source = fine;
  if (keep) {
    scratch ||= document.createElement('canvas');
    scratch.width = fine.width; scratch.height = fine.height;
    const s = scratch.getContext('2d'), k = fine.width / fine.lw;
    s.drawImage(fine, 0, 0);
    s.globalCompositeOperation = 'destination-out';
    const rows = Math.round((fine.lh - 2) / CELL_H), cols = Math.round((fine.lw - 2) / CELL_W);
    for (let r = 0; r < rows; r++) for (let c = 0; c < cols; c++)
      if (!keep(r, c)) s.fillRect((1 + c * CELL_W - .5) * k, (1 + r * CELL_H - .5) * k, (CELL_W + 1) * k, (CELL_H + 1) * k);
    s.globalCompositeOperation = 'source-over';
    source = scratch;
  }
  const smoothing = ctx.imageSmoothingEnabled;
  ctx.imageSmoothingEnabled = true; ctx.imageSmoothingQuality = 'low';
  ctx.globalAlpha = alpha;
  ctx.drawImage(source, x - 1, y - 1, fine.lw, fine.lh);
  ctx.globalAlpha = 1;
  ctx.imageSmoothingEnabled = smoothing;
}
