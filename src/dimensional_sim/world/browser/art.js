/** Fine terrain character assets, separate from logical collision cells.
 * Canvas text only: 6x4 drawing cells per movement tile. No bitmap world assets.
 * Player, enemy and combat art live in actors.js and never enter these caches.
 */
import {TILE_W, TILE_H, CELL_W, CELL_H, visualHash} from './view.js';
import {paintParts} from './sprites.js';
import {SHALLOW_BG, WATER_BG, blooms, drawBlooms, drawFlagstones, drawPath, drawPlanks, drawRubble, drawScorch, drawBlades, drawReflection, drawShores, isWater, drawLitRock, drawRipples, grassBlades, ripples, TREE_ART} from './nature_art.js';
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
/** Legacy text tree and rock (minimap-scale references); world stamps use nature_art.js. */
export const TREE = Object.freeze([
  '     .v.     ', '   .vYvYv.   ', '  vYvYvYvYv  ', ' .YvYvYvYvY. ',
  ' vYvYvYvYvYv ', '.YvYvYvYvYvY.', '  vYvYvYvYv  ', '    /|||\\    ',
  '     |||     ', '    /|||\\    '
]);
export const ROCK = Object.freeze(['  .___  ', ' /:o:.\\ ', '/o:::.| ', '\\_::__/ ']);
/** Every site object glyph (sites.STRUCTURE_GLYPHS), outlined like actors and spots:
 * `paint` picks a STRUCTURE_ROLES fill per cell, `glyph` the ink drawn over it. Rows are
 * bottom-aligned on the tile and centred on it; a sprite may be wider or taller than one
 * tile (it never blocks more). */
const STRUCTURE_ROLES = Object.freeze({
  d: {fill: '#4a3626', ink: '#a88a64'}, w: {fill: '#7a5532', ink: '#c9a46c'},
  t: {fill: '#b59050', ink: '#5a4128'}, h: {fill: '#a6845d', ink: '#4a3626'},
  c: {fill: '#c8b080', ink: '#6e5a3a'}, s: {fill: '#788278', ink: '#dfe3d6'},
  g: {fill: '#565d58', ink: '#b9bfae'}, m: {fill: '#4f6b34', ink: '#a9c97a'},
  y: {fill: '#e5c772', ink: '#fff3bc'}, r: {fill: '#8e3a30', ink: '#e0a080'},
  e: {fill: '#3b2a1c', ink: '#8b6b4a'}});
export const STRUCTURE_ART = Object.freeze({
  A: {paint: ['   cc   ', '  cccc  ', ' ccddcc ', 'cccddccc'],                       // travellers' tent
    glyph: ['   /\\   ', '  /..\\  ', ' /.||.\\ ', '/_/||\\_\\']},
  M: {paint: [' s  ss  ', 'sgsssgss', 'ssssssss', 'gssgssgs'],                       // fallen masonry
    glyph: [' .  .-. ', '|::|::|:', '+--+--+-', '|::|::|:']},
  L: {paint: [' wwwww', 'wwwwww', 'wwwwww', 'd    d'],   // seasoned logs (a run of tiles joins up)
    glyph: [' (@)(@', '(@)(@)', '@)(@)(', '|    |']},
  S: {paint: [' tttt ', 'wwwwww', 'dwwwwd'],   // stump
    glyph: [' (@@) ', '|::::|', '/\'\'\'\'\\']},
  U: {paint: ['     hhhh     ', '   hhhhhhhh   ', ' hhhhhhhhhhhh ', 'dddddddddddddd', ' wwwwwwwwwwww ', ' wwwwweewwwww ', ' wwwwweewwwww '],   // hunter's lodge (overhangs its tile)
    glyph: ['     _/\\_     ', '   _/####\\_   ', ' _/########\\_ ', '/============\\', ' |#|[]  |#|=| ', ' |#|  ||  |=| ', ' |_|__||__|_| ']},
  R: {paint: ['d      d', 'dhhhhhhd', 'dhhhhhhd', 'd hhhh d', 'd      d'],             // drying rack
    glyph: ['+------+', '|/~~~~\\|', '|(::::)|', '| \\__/ |', '|      |']},
  P: {paint: [' ssss ', '  gs  ', '  gs  ', '  gs  ', '  gs  ', ' ssss '],               // carved pillar
    glyph: [' /==\\ ', '  |:  ', '  |o  ', '  |:  ', '  |o  ', ' /__\\ ']},
  Q: {paint: ['   yy   ', '  ssss  ', ' gssssg ', ' g ss g ', 'gggggggg'],             // split altar
    glyph: ['   **   ', '  /__\\  ', ' |*||*| ', ' | || | ', '/______\\']},
  B: {paint: ['     mmmmmm     ', '  mmmmmmmmmmmm  ', ' mmmmmmmmmmmmmm ', 'mmmmmmggggmmmmmm', 'mmmmmmeeeemmmmmm'],   // barrow mound (overhangs its tile)
    glyph: ['     ;;;;;;     ', '  _/;:;:;:;;\\_  ', ' /;:;:;:;:;:;:\\ ', '/;:;:;|==|;:;:;\\', ';;;;;;|  |;;;;;;']},
  I: {paint: [' gg  ', 'gssg ', 'gssg ', 'gsgg ', 'mmmm '],                             // standing stone
    glyph: [' __  ', '/::\\ ', '|:o| ', '|::| ', ';;;; ']},
});
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
      glyph: ['*', "'", 'o', ','][(h >>> 2) % 4], color: PALETTE.bloom[(h >>> 3) % 4]});  // >>>: h is unsigned
    else if (glyph === 'F') marks.push({col, row,
      glyph: row % 2 ? (col % 3 === (row >> 1) % 3 ? '|' : '_') : h % 4 ? '.' : ',', color: PALETTE.stones[h % 3]});
    else if (glyph === '~' && h % 3 !== 0) marks.push({col, row,
      glyph: ['~', '.', '~', ','][h % 4], color: PALETTE.wet[h % 3]});
    else if (h % 5 !== 0) marks.push({col, row,
      glyph: glyph === ';' ? ",;v'"[h % 4] : glyph === 'o' ? "o.,'"[h % 4] : ".,':"[h % 4],
      color: PALETTE.grass[h % 4]});
  }
  return marks;
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
  const terrain = '=;o~x:w%H*F'.includes(glyph) ? glyph : '.';
  return stamp(`tile:${terrain}:${variant}`, TILE_W, TILE_H, ctx => {
    ctx.fillStyle = terrain === '=' ? PALETTE.path : terrain === '~' ? '#1b302b'
      : terrain === 'w' ? WATER_BG : terrain === '%' ? SHALLOW_BG : terrain === 'H' ? '#2b2116'
      : terrain === ':' ? '#292a25' : terrain === 'x' ? PALETTE.floor : terrain === 'F' ? '#262a24' : PALETTE.floor;
    ctx.fillRect(0, 0, TILE_W, TILE_H);
    const grassy = terrain === '.' || terrain === ';' || terrain === 'o' || terrain === '*';
    if (terrain === 'w' || terrain === '%') drawRipples(ctx, ripples(variant, terrain === '%'));
    if (terrain === '=') drawPath(ctx, variant, STAMP_SEED);
    if (terrain === 'H') drawPlanks(ctx, variant);
    if (terrain === 'F') drawFlagstones(ctx, variant);
    if (terrain === ':') drawScorch(ctx, variant);
    if (terrain === 'x') drawRubble(ctx, variant);
    const plain = terrain === 'w' || terrain === 'H' || terrain === 'F' || terrain === '*' || terrain === 'x';
    for (const mark of groundMarks(glyph, variant, 0, STAMP_SEED)) {
      if (plain || (terrain === '%' && mark.glyph !== 'o') || ((terrain === '=' || terrain === ':') && (variant + mark.col + mark.row) % 3)
        || (grassy && mark.glyph !== 'o' && variant + mark.col + mark.row & 1)) continue;
      ctx.fillStyle = mark.color; ctx.fillText(mark.glyph, mark.col * CELL_W, mark.row * CELL_H);
    }
    if (grassy) drawBlades(ctx, grassBlades(terrain === '*' ? '.' : terrain, variant, STAMP_SEED));
    if (terrain === '*') drawBlooms(ctx, blooms(variant, STAMP_SEED));
  }, createCanvas);
}
function treeStamp(variant, createCanvas, kind = 'o') {
  const draw = TREE_ART[kind] || TREE_ART.o;
  return stamp(`tree:${TREE_ART[kind] ? kind : 'o'}:${variant}`, 52, 70, ctx => draw(ctx, variant), createCanvas);
}
/** {canvas, dx, dy}: the stamp and its offset from the tile's top-left corner. */
function structureStamp(glyph, createCanvas) {
  const art = STRUCTURE_ART[glyph], cols = art.paint[0].length, rows = art.paint.length;
  const width = Math.max(32, cols * CELL_W + 2), height = Math.max(28, rows * CELL_H + 2);
  const canvas = stamp(`site:${glyph}`, width, height, ctx => {
    const left = 1 + Math.floor((width - 2 - cols * CELL_W) / 2), half = cols * CELL_W / 2 + 2;
    for (let r = 0; r < 3; r++) {   // a soft ground shadow under the lit structure
      ctx.fillStyle = '#04080455';
      const w = Math.round(half * (1 - Math.abs(r - 1) * .25));
      ctx.fillRect(left + cols * CELL_W / 2 - w + 3, height - 4 + r, w * 2, 1);
    }
    paintParts(ctx, art, STRUCTURE_ROLES, left, height - 1 - rows * CELL_H);
  }, createCanvas);
  return {canvas, dx: -4 - Math.round((width - 32) / 2), dy: -4 - (height - 28)};
}
function rockStamp(variant, createCanvas) {
  return stamp(`rock:${variant}`, 32, 28, ctx => drawLitRock(ctx, variant), createCanvas);
}
/** Tree whose logical tile top-left is (px, py). The trunk sits over the blocking
 * cell; canopy overhang is visual. Reused to repaint canopies in front of actors. */
export function drawTree(ctx, px, py, seed, createCanvas, kind = 'o') {
  ctx.drawImage(treeStamp(seed % TREE_VARIANTS, createCanvas, kind), px - 14, py - 42);
}
/** The tree kind letter at a chunk cell (frames send chunk.trees; older frames: oak). */
export const treeKind = (chunk, x, y) => chunk.trees?.[y]?.[x] || 'o';
/** Two surfaces preserve global environment < objects < actors order at seams. */
export function paintChunk(chunk, createCanvas = defaultCanvas) {
  const width = chunk.width * TILE_W, height = chunk.height * TILE_H;
  const ground = createCanvas(), objects = createCanvas();
  ground.width = width; ground.height = height;
  objects.width = width + OBJECT_PAD * 2; objects.height = height + OBJECT_PAD * 2;
  const g = ground.getContext('2d'), o = objects.getContext('2d');
  let wet = false;
  for (let y = 0; y < chunk.height; y++) for (let x = 0; x < chunk.width; x++) {
    const glyph = chunk.tiles[y][x], px = x * TILE_W, py = y * TILE_H;
    const gx = chunk.x * chunk.width + x, gy = chunk.y * chunk.height + y;
    const seed = visualHash(gx, gy, chunk.seed);
    g.drawImage(tileStamp(glyph, seed % TILE_VARIANTS, createCanvas), px, py);
    wet ||= isWater(glyph);
    if (glyph === 'T') drawTree(o, px + OBJECT_PAD, py + OBJECT_PAD, seed, createCanvas, treeKind(chunk, x, y));
    else if (glyph === '^') o.drawImage(rockStamp(seed % ROCK_VARIANTS, createCanvas), px + OBJECT_PAD - 4, py + OBJECT_PAD - 4);
    else if (STRUCTURE_ART[glyph]) {
      const {canvas, dx, dy} = structureStamp(glyph, createCanvas);
      o.drawImage(canvas, px + OBJECT_PAD + dx, py + OBJECT_PAD + dy);
    }
  }
  if (wet) reflect(g, chunk, createCanvas);
  return {ground, objects};
}
/** Banks, then trees, rocks and structures mirrored in the water south of them. */
function reflect(g, chunk, createCanvas) {
  drawShores(g, chunk);
  for (let y = 0; y < chunk.height; y++) for (let x = 0; x < chunk.width; x++) {
    const glyph = chunk.tiles[y][x];
    if (glyph !== 'T' && glyph !== '^' && !STRUCTURE_ART[glyph]) continue;
    const rects = [];
    for (let dy = 1; dy <= 3; dy++) for (let dx = -1; dx <= 1; dx++) {
      if (isWater(chunk.tiles[y + dy]?.[x + dx])) rects.push([(x + dx) * TILE_W, (y + dy) * TILE_H, TILE_W, TILE_H]);
    }
    if (!rects.length) continue;
    const px = x * TILE_W, py = y * TILE_H;
    const seed = visualHash(chunk.x * chunk.width + x, chunk.y * chunk.height + y, chunk.seed);
    drawReflection(g, rects, py + TILE_H - 2, ctx => {
      if (glyph === 'T') drawTree(ctx, px, py, seed, createCanvas, treeKind(chunk, x, y));
      else if (glyph === '^') ctx.drawImage(rockStamp(seed % ROCK_VARIANTS, createCanvas), px - 4, py - 4);
      else { const {canvas, dx, dy} = structureStamp(glyph, createCanvas); ctx.drawImage(canvas, px + dx, py + dy); }
    });
  }
}
export function terrainColor(glyph) {
  return glyph === '=' ? '#b29a5b' : glyph === 'T' ? '#718347' : glyph === '^' ? '#959582'
    : glyph === 'x' ? '#a07548' : glyph === ':' ? '#696055' : glyph === '~' ? '#5a8d85'
    : glyph === 'o' ? '#789658' : glyph === 'w' ? '#3f7fa6' : glyph === '%' ? '#6f9fb3'
    : glyph === 'H' ? '#9b7944' : glyph === '*' ? '#55703a'
    : glyph === 'A' ? '#c8b080' : glyph === 'M' ? '#a3a490' : glyph === 'F' ? '#7d8576'
    : glyph === 'L' || glyph === 'S' || glyph === 'U' ? '#9b7944' : glyph === 'R' ? '#a6845d'
    : glyph === 'P' || glyph === 'Q' || glyph === 'I' ? '#a3a490' : glyph === 'B' ? '#59713b' : '#3d512b';
}
