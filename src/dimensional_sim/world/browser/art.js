/** Fine terrain character assets, separate from logical collision cells.
 * Canvas text only: 6x4 drawing cells per movement tile. No bitmap world assets.
 * Player, enemy and combat art live in actors.js and never enter these caches.
 */
import {TILE_W, TILE_H, CELL_W, CELL_H, visualHash} from './view.js';
export const PALETTE = Object.freeze({
  void: '#11180f', floor: '#172011', path: '#242418',
  grass: ['#334824', '#405930', '#59713b', '#748648'],
  leaves: ['#314822', '#44602b', '#5c7935', '#839545', '#abb65a'],
  bark: ['#645033', '#9b7944', '#b59050'], stone: ['#536057', '#788278', '#a3a490'],
  pathInk: ['#695b36', '#8e7445', '#b19459'],
  ash: ['#4d4940', '#696055', '#867264'], debris: ['#775538', '#a07548', '#c09660'],
  wet: ['#416b68', '#5a8d85', '#8db1a0'],
  water: ['#3a7397', '#5a9cbf', '#93c6d8'], stones: ['#6d7569', '#8d9585', '#5a6157'],
  plank: ['#6e5233', '#8f6c41', '#a9834f'], bloom: ['#c9b458', '#b77fa8', '#d9d2b0', '#59713b']
});
export const TREE = Object.freeze([
  '     .v.     ', '   .vYvYv.   ', '  vYvYvYvYv  ', ' .YvYvYvYvY. ',
  ' vYvYvYvYvYv ', '.YvYvYvYvYvY.', '  vYvYvYvYv  ', '    /|||\\    ',
  '     |||     ', '    /|||\\    '
]);
export const ROCK = Object.freeze(['  .___  ', ' /:o:.\\ ', '/o:::.| ', '\\_::__/ ']);
export function setupText(ctx) {
  ctx.font = '7px Consolas, "Liberation Mono", monospace';
  ctx.textBaseline = 'top'; ctx.textAlign = 'left';
}
/** Consistent coordinate-based detail remains unchanged after cache eviction. */
export function groundMarks(glyph, x, y, seed) {
  const marks = [];
  for (let row = 0; row < 4; row++) for (let col = 0; col < 6; col++) {
    const h = visualHash(x * 6 + col, y * 4 + row, seed);
    if (glyph === '=') marks.push({col, row, glyph: '.,:.'[h % 4], color: PALETTE.pathInk[h % 3]});
    else if (glyph === 'x' && h % 3 !== 0) marks.push({col, row,
      glyph: ['/', '=', '\\', 'x', '_'][h % 5], color: PALETTE.debris[h % 3]});
    else if (glyph === ':' && h % 3 !== 0) marks.push({col, row,
      glyph: ['.', ':', ',', '~'][h % 4], color: PALETTE.ash[h % 3]});
    else if (glyph === 'w') { if (h % 3 !== 0) marks.push({col, row,
      glyph: ['~', '-', '~', '.', '='][h % 5], color: PALETTE.water[h % 3]}); }
    else if (glyph === '%') marks.push({col, row,
      glyph: h % 3 === 0 ? 'o' : ['~', '.', '-'][h % 3], color: h % 3 === 0 ? PALETTE.stones[h % 3] : PALETTE.water[h % 3]});
    else if (glyph === 'H') marks.push({col, row,
      glyph: col === 0 || col === 5 ? '|' : row % 2 ? '=' : '-', color: PALETTE.plank[h % 3]});
    else if (glyph === '*' && h % 4 === 0) marks.push({col, row,
      glyph: ['*', "'", 'o', ','][(h >> 2) % 4], color: PALETTE.bloom[(h >> 3) % 4]});
    else if (glyph === '~' && h % 3 !== 0) marks.push({col, row,
      glyph: ['~', '.', '~', ','][h % 4], color: PALETTE.wet[h % 3]});
    else if (h % 5 !== 0) marks.push({col, row,
      glyph: glyph === ';' ? ",;v'"[h % 4] : glyph === 'o' ? "o.,'"[h % 4] : ".,':"[h % 4],
      color: PALETTE.grass[h % 4]});
  }
  return marks;
}
function sprite(ctx, rows, x, y, colors, seed = 0) {
  rows.forEach((row, ry) => [...row].forEach((char, rx) => {
    if (char === ' ') return;
    ctx.fillStyle = colors[visualHash(rx, ry, seed) % colors.length];
    ctx.fillText(char, x + rx * CELL_W, y + ry * CELL_H);
  }));
}
export const OBJECT_PAD = 56;
/* Stamp cache: each ground tile, tree and rock is drawn once per visual variant and
 * then copied with drawImage. Painting a chunk drops from ~12k fillText calls to
 * ~600 image copies, which removes the hitch when new chunks stream in at a border.
 * Variant choice is still stable per global coordinate, so the world looks identical
 * after cache eviction; only the number of distinct patterns is bounded. */
export const TILE_VARIANTS = 16, TREE_VARIANTS = 8, ROCK_VARIANTS = 4;
const STAMP_SEED = 0x5eed;
const stamps = new Map();
const defaultCanvas = () => document.createElement('canvas');
function stamp(key, width, height, draw, createCanvas = defaultCanvas) {
  let canvas = stamps.get(key);
  if (!canvas) {
    canvas = createCanvas(); canvas.width = width; canvas.height = height;
    const ctx = canvas.getContext('2d'); setupText(ctx); draw(ctx);
    stamps.set(key, canvas);
  }
  return canvas;
}
export function clearStamps() { stamps.clear(); }
export function stampCount() { return stamps.size; }
function tileStamp(glyph, variant, createCanvas) {
  const terrain = '=;o~x:w%H*'.includes(glyph) ? glyph : '.';
  return stamp(`tile:${terrain}:${variant}`, TILE_W, TILE_H, ctx => {
    ctx.fillStyle = terrain === '=' ? PALETTE.path : terrain === '~' ? '#1b302b'
      : terrain === 'w' ? '#173b52' : terrain === '%' ? '#21434d' : terrain === 'H' ? '#2b2116'
      : terrain === ':' ? '#292a25' : terrain === 'x' ? '#30271f' : PALETTE.floor;
    ctx.fillRect(0, 0, TILE_W, TILE_H);
    for (const mark of groundMarks(glyph, variant, 0, STAMP_SEED)) {
      ctx.fillStyle = mark.color; ctx.fillText(mark.glyph, mark.col * CELL_W, mark.row * CELL_H);
    }
  }, createCanvas);
}
function treeStamp(variant, createCanvas) {
  return stamp(`tree:${variant}`, 52, 70, ctx => {
    sprite(ctx, TREE, 0, 0, PALETTE.leaves, variant);
    sprite(ctx, ['|||','|||','/|\\'], 20, 44, PALETTE.bark, variant);
  }, createCanvas);
}
function rockStamp(variant, createCanvas) {
  return stamp(`rock:${variant}`, 32, 28, ctx => sprite(ctx, ROCK, 0, 0, PALETTE.stone, variant), createCanvas);
}
/** Tree whose logical tile top-left is (px, py). The trunk sits over the blocking
 * cell; canopy overhang is visual. Reused to repaint canopies in front of actors. */
export function drawTree(ctx, px, py, seed, createCanvas) {
  ctx.drawImage(treeStamp(seed % TREE_VARIANTS, createCanvas), px - 14, py - 42);
}
/** Two surfaces preserve global environment < objects < actors order at seams. */
export function paintChunk(chunk, createCanvas = defaultCanvas) {
  const width = chunk.width * TILE_W, height = chunk.height * TILE_H;
  const ground = createCanvas(), objects = createCanvas();
  ground.width = width; ground.height = height;
  objects.width = width + OBJECT_PAD * 2; objects.height = height + OBJECT_PAD * 2;
  const g = ground.getContext('2d'), o = objects.getContext('2d');
  for (let y = 0; y < chunk.height; y++) for (let x = 0; x < chunk.width; x++) {
    const glyph = chunk.tiles[y][x], px = x * TILE_W, py = y * TILE_H;
    const gx = chunk.x * chunk.width + x, gy = chunk.y * chunk.height + y;
    const seed = visualHash(gx, gy, chunk.seed);
    g.drawImage(tileStamp(glyph, seed % TILE_VARIANTS, createCanvas), px, py);
    if (glyph === 'T') drawTree(o, px + OBJECT_PAD, py + OBJECT_PAD, seed, createCanvas);
    else if (glyph === '^') o.drawImage(rockStamp(seed % ROCK_VARIANTS, createCanvas), px + OBJECT_PAD - 4, py + OBJECT_PAD - 4);
  }
  return {ground, objects};
}
export function terrainColor(glyph) {
  return glyph === '=' ? '#b29a5b' : glyph === 'T' ? '#718347' : glyph === '^' ? '#959582'
    : glyph === 'x' ? '#a07548' : glyph === ':' ? '#696055' : glyph === '~' ? '#5a8d85'
    : glyph === 'o' ? '#789658' : glyph === 'w' ? '#3f7fa6' : glyph === '%' ? '#6f9fb3'
    : glyph === 'H' ? '#9b7944' : glyph === '*' ? '#55703a' : '#3d512b';
}
