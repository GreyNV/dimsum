/** Fine terrain character assets, separate from logical collision cells.
 * Canvas-drawn only (no bitmap world assets), painted RES times denser than logical size.
 * Player, enemy and combat art live in actors.js and never enter these caches.
 */
import {TILE_W, TILE_H, CELL_W, CELL_H, visualHash} from './view.js';
import {paintParts} from './sprites.js';
import {paintedResolution} from './painted.js';
import {READ_K, asciify, asciiReady, onStyleChange} from './ascii_art.js';
import {structureCanvas} from './painted_props.js';
import {DECOR_H, DECOR_W, SPILLS, drawDecor, raggedBand, undergrowth} from './natural_ground.js';
import {SHALLOW_BG, WATER_BG, blooms, drawBlooms, drawFlagstones, drawPath, drawPlanks, drawRubble, drawScorch, drawBlades, drawReflection, drawShores, isWater, drawLitRock, drawRipples, grassBlades, ripples, TREE_ART, withDetail} from './nature_art.js';
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
export const OBJECT_PAD = 150;
/* Stamp cache: each ground tile, tree and rock is drawn once per visual variant and
 * then copied with drawImage. Painting a chunk drops from ~12k fillText calls to
 * ~600 image copies, which removes the hitch when new chunks stream in at a border.
 * Variant choice is still stable per global coordinate, so the world looks identical
 * after cache eviction; only the number of distinct patterns is bounded. */
export const TILE_VARIANTS = 16, TREE_VARIANTS = 8, ROCK_VARIANTS = 4;
const STAMP_SEED = 0x5eed;
const stamps = new Map();
const defaultCanvas = () => document.createElement('canvas');
/* Render resolution: every stamp and chunk surface is painted RES times denser than its
 * logical size, so glyph texture, blades and leaves keep their fine detail when the scene
 * is scaled up to the screen (zoom x device pixels) instead of being blown up into blocks.
 * The app picks it from the device (setResolution); logical sizes never change. */
export let RES = 2;
export function setResolution(res) {
  const next = Math.max(1, Math.min(4, Math.round(res)));
  if (next !== RES) { RES = next; stamps.clear(); }
  paintedResolution(RES);
  return RES;
}
/** A canvas `width` x `height` logical pixels, backed at RES, with the context scaled. */
function surface(width, height, createCanvas, k = RES) {
  const canvas = createCanvas();
  canvas.width = Math.ceil(width * k); canvas.height = Math.ceil(height * k);
  canvas.lw = width; canvas.lh = height;
  const ctx = canvas.getContext('2d');
  if (k !== 1) ctx.scale(k, k);
  return {canvas, ctx};
}
/** Copy a stamp or chunk surface at its logical size. */
export function put(ctx, canvas, x, y) {
  ctx.drawImage(canvas, x, y, canvas.lw ?? canvas.width, canvas.lh ?? canvas.height);
}
function stamp(key, width, height, draw, createCanvas = defaultCanvas, {ascii = false} = {}) {
  let canvas = stamps.get(key);
  if (!canvas) {
    // trees, rocks and ground are painted fine as pictures, then shown as text (ascii_art.js)
    const text = ascii && createCanvas === defaultCanvas && asciiReady();
    const made = surface(width, height, createCanvas, text ? READ_K : RES);
    canvas = made.canvas; setupText(made.ctx); draw(made.ctx);
    if (text) canvas = Object.assign(asciify(canvas, width, height, READ_K, RES, ascii === true ? {} : ascii), {lw: width, lh: height});
    stamps.set(key, canvas);
  }
  return canvas;
}
export function clearStamps() { stamps.clear(); }
onStyleChange(() => stamps.clear());
export function stampCount() { return stamps.size; }
/* Ground in text too: blades become strokes, earth and stone sparse dots, over a near-black base,
 * with light read on one fixed scale so neighbouring tiles match. Cells divide the 24 x 28 tile. */
const GROUND_ASCII = {cell: [1.5, 28 / 11], ground: false, absolute: [.04, .3], base: '#0b1009',
  style: {backing: 'none', lift: 1.45, whiten: 0}, glyphs: " .'`,:;-!|/\\"};
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
  }, createCanvas, {ascii: GROUND_ASCII});
}
/* Trees come in sizes: each kind has its own range (pines and old trees tower, dead trees and
 * birches stay slimmer), picked per variant, so a forest is never a row of identical lollipops
 * and a tree stands two to four times the height of a person. */
const TREE_SIZES = Object.freeze({o: [1.35, 1.85], p: [1.55, 2.2], b: [1.4, 1.9], d: [1.2, 1.7], m: [1.8, 2.2]});
export function treeScale(kind, variant) {
  const [lo, hi] = TREE_SIZES[kind] || TREE_SIZES.o;
  return Math.round((lo + (hi - lo) * ((variant * 5 + 3) % TREE_VARIANTS) / (TREE_VARIANTS - 1)) * 20) / 20;
}
function treeStamp(variant, createCanvas, kind = 'o') {
  const known = TREE_ART[kind] ? kind : 'o', draw = TREE_ART[known], scale = treeScale(known, variant);
  return stamp(`tree:${known}:${variant}`, 52 * scale, 70 * scale, ctx => {
    ctx.scale(scale, scale);
    withDetail(scale, () => draw(ctx, variant));
  }, createCanvas, {ascii: true});
}
/** Where a tree stamp goes for the tile whose top-left is (px, py): the roots (stamp 26, 62)
 * on the tile's lower middle. */
export function treeAt(px, py, seed, createCanvas = defaultCanvas, kind = 'o') {
  const variant = seed % TREE_VARIANTS, known = TREE_ART[kind] ? kind : 'o', scale = treeScale(known, variant);
  // off the grid: each trunk stands a few px from its tile centre (still on its own tile)
  const jx = ((seed >>> 5) % 11) - 5, jy = ((seed >>> 9) % 7) - 3;
  return {canvas: treeStamp(variant, createCanvas, known), x: px + 12 + jx - 26 * scale, y: py + 20 + jy - 62 * scale};
}
/** {canvas, dx, dy}: the stamp and its offset from the tile's top-left corner. */
function structureStamp(glyph, createCanvas) {
  const painted = createCanvas === defaultCanvas ? structureCanvas(glyph) : null;
  if (painted?.canvas) return {canvas: painted.canvas, dx: 12 - painted.w / 2 - painted.canvas.pad, dy: 24 - painted.h - painted.canvas.pad};
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
const GRASSY_TRAIL = new Set(['.', ';', 'o', '*']);
function decorStamp(kind, variant, createCanvas) {
  return stamp(`decor:${kind}:${variant}`, DECOR_W, DECOR_H, ctx => drawDecor(ctx, kind, variant), createCanvas, {ascii: true});
}
function rockStamp(variant, createCanvas) {
  return stamp(`rock:${variant}`, 32, 28, ctx => drawLitRock(ctx, variant), createCanvas, {ascii: true});
}
/** Tree whose logical tile top-left is (px, py). The trunk sits over the blocking
 * cell; canopy overhang is visual. Reused to repaint canopies in front of actors. */
export function drawTree(ctx, px, py, seed, createCanvas, kind = 'o') {
  const tree = treeAt(px, py, seed, createCanvas, kind);
  put(ctx, tree.canvas, tree.x, tree.y);
}
/** The tree kind letter at a chunk cell (frames send chunk.trees; older frames: oak). */
export const treeKind = (chunk, x, y) => chunk.trees?.[y]?.[x] || 'o';
/** The chunk's ground is one cached surface; its objects (trees, rocks, structures) are a
 * list of stamp copies [{canvas, x, y}] in chunk pixels, drawn each frame (drawObjects) -
 * cheap, and far lighter than a second full-chunk surface at RES. */
export function paintChunk(chunk, createCanvas = defaultCanvas) {
  const width = chunk.width * TILE_W, height = chunk.height * TILE_H;
  const {canvas: ground, ctx: g} = surface(width, height, createCanvas);
  const objects = [];
  let tile = [0, 0];   // the root tile of the object being placed (drawObjects can skip hidden ones)
  const o = {drawImage: (canvas, x, y) => objects.push({canvas, x: x - OBJECT_PAD, y: y - OBJECT_PAD, tx: tile[0], ty: tile[1]})};
  let wet = false;
  for (let y = 0; y < chunk.height; y++) for (let x = 0; x < chunk.width; x++) {
    const glyph = chunk.tiles[y][x], px = x * TILE_W, py = y * TILE_H;
    const gx = chunk.x * chunk.width + x, gy = chunk.y * chunk.height + y;
    const seed = visualHash(gx, gy, chunk.seed);
    put(g, tileStamp(glyph, seed % TILE_VARIANTS, createCanvas), px, py);
    wet ||= isWater(glyph);
    tile = [x, y];
    if (glyph === 'T') { const tree = treeAt(px, py, seed, createCanvas, treeKind(chunk, x, y)); objects.push({canvas: tree.canvas, x: tree.x, y: tree.y, tx: x, ty: y, cover: pathCover(chunk, x, y)}); }
    else if (glyph === '^') o.drawImage(rockStamp(seed % ROCK_VARIANTS, createCanvas), px + OBJECT_PAD - 4, py + OBJECT_PAD - 4);
    else if (STRUCTURE_ART[glyph]) {
      const {canvas, dx, dy} = structureStamp(glyph, createCanvas);
      o.drawImage(canvas, px + OBJECT_PAD + dx, py + OBJECT_PAD + dy);
    }
  }
  // ragged terrain edges: a path or bare earth spills a few px over the grass beside it
  const at = (x, y) => chunk.tiles[y]?.[x];
  for (let y = 0; y < chunk.height; y++) for (let x = 0; x < chunk.width; x++) {
    const glyph = at(x, y);
    if (SPILLS[glyph] || isWater(glyph) || glyph === 'H') continue;
    for (const [side, nx, ny] of [['n', x, y - 1], ['s', x, y + 1], ['w', x - 1, y], ['e', x + 1, y]]) {
      const other = at(nx, ny);
      if (!SPILLS[other]) continue;
      const gx = chunk.x * chunk.width + x, gy = chunk.y * chunk.height + y;
      const pts = raggedBand(x * TILE_W, y * TILE_H, TILE_W, TILE_H, side, side === 'n' || side === 's' ? 7 : 6, visualHash(gx, gy, chunk.seed ^ 0xf1));
      g.save(); g.beginPath(); g.moveTo(...pts[0]); for (const p of pts.slice(1)) g.lineTo(...p); g.closePath(); g.clip();
      put(g, tileStamp(other, visualHash(gx, gy, chunk.seed) % TILE_VARIANTS, createCanvas), x * TILE_W, y * TILE_H);
      g.restore();
    }
  }
  // worn forest trails: a walkable cell hemmed in by trees is trodden earth, so a path through the
  // woods reads on the ground (a soft-edged patch per cell; neighbouring patches join into a strip)
  for (let y = 0; y < chunk.height; y++) for (let x = 0; x < chunk.width; x++) {
    if (chunk.collision?.[y]?.[x] === '1' || !GRASSY_TRAIL.has(at(x, y))) continue;
    let hem = 0;
    for (let dy = -1; dy <= 1; dy++) for (let dx = -1; dx <= 1; dx++) hem += (dx || dy) && (at(x + dx, y + dy) === 'T' || at(x + dx, y + dy) === '^') ? 1 : 0;
    if (hem < 4) continue;
    const gx = chunk.x * chunk.width + x, gy = chunk.y * chunk.height + y, h = visualHash(gx, gy, chunk.seed ^ 0x7a11);
    const cx = x * TILE_W + 12 + (h % 5) - 2, cy = y * TILE_H + 14 + ((h >>> 3) % 5) - 2;
    g.save(); g.beginPath();
    for (let i = 0; i < 12; i++) {   // a ragged blob a little larger than the cell
      const a = i / 12 * Math.PI * 2, r = 1 + ((visualHash(i, gx, gy) % 100) / 100 - .5) * .35;
      g.lineTo(cx + Math.cos(a) * 15 * r, cy + Math.sin(a) * 17 * r);
    }
    g.closePath(); g.clip(); g.globalAlpha = .62;
    put(g, tileStamp('=', h % TILE_VARIANTS, createCanvas), x * TILE_W - 6, y * TILE_H - 4);
    put(g, tileStamp('=', (h >>> 4) % TILE_VARIANTS, createCanvas), x * TILE_W + 6, y * TILE_H + 4);
    g.restore();
  }
  // undergrowth in clumps: thick along the forest edge, rare in the open (natural_ground.js)
  const blocked = (x, y) => at(x, y) === 'T';
  for (let y = 0; y < chunk.height; y++) for (let x = 0; x < chunk.width; x++) {
    if (chunk.collision?.[y]?.[x] === '1') continue;
    let trees = 0, hem = 0;
    for (let dy = -1; dy <= 1; dy++) for (let dx = -1; dx <= 1; dx++) trees += (dx || dy) && blocked(x + dx, y + dy) ? 1 : 0;
    for (let dy = -1; dy <= 1; dy++) for (let dx = -1; dx <= 1; dx++) hem += (dx || dy) && (at(x + dx, y + dy) === 'T' || at(x + dx, y + dy) === '^') ? 1 : 0;
    if (hem >= 4) continue;   // a trodden trail stays clear
    const piece = undergrowth(chunk.x * chunk.width + x, chunk.y * chunk.height + y, at(x, y), trees, chunk.seed | 0);
    if (!piece) continue;
    objects.push({decor: piece.kind, canvas: decorStamp(piece.kind, piece.variant, createCanvas), x: x * TILE_W + 12 - DECOR_W / 2 + piece.dx, y: y * TILE_H + 26 - DECOR_H + piece.dy, tx: x, ty: y});
  }
  objects.sort((a, b) => a.ty - b.ty || a.tx - b.tx);   // trees and undergrowth layer by row
  if (wet) reflect(g, chunk, createCanvas);
  return {ground, objects};
}
/** Draw a painted chunk's objects with the chunk's top-left at (ox, oy). */
export function drawObjects(ctx, picture, ox, oy, shown = null, alpha = null, sway = null) {
  for (const item of picture.objects) {
    if (shown && !shown(item.tx, item.ty)) continue;
    const a = alpha ? alpha(item.tx, item.ty, item) : 1;
    if (a <= 0) continue;
    const shear = sway ? sway(item.tx, item.ty, item) : 0;
    if (a < 1) { ctx.globalAlpha = a; putSwayed(ctx, item.canvas, ox + item.x, oy + item.y, shear); ctx.globalAlpha = 1; }
    else putSwayed(ctx, item.canvas, ox + item.x, oy + item.y, shear);
  }
}
/** Draw `canvas` at (x, y) leaning by `shear` about its bottom edge (a plant's root): the
 * wind (wind.js) bends grass and treetops while the base stays where it grows. */
export function putSwayed(ctx, canvas, x, y, shear = 0) {
  if (!shear || Math.abs(shear) < .002) { put(ctx, canvas, x, y); return; }
  const base = y + (canvas.lh ?? canvas.height);
  ctx.save();
  ctx.transform(1, 0, shear, 1, -shear * base, 0);
  put(ctx, canvas, x, y);
  ctx.restore();
}
/** Leaves thin out around the avatar: trees rooted just south of it and a few columns aside
 * (the ones whose canopies cover the ground it stands on) fade, so the way ahead stays readable
 * in deep woods. `dx`, `dy` in tiles from the avatar to the tree's root (south positive). */
/** The walkable tiles (global [gx, gy]) a tree's crown hangs over, within its own chunk: a
 * forest trail under a big tree is hidden by leaves, so those trees are drawn see-through. */
export function pathCover(chunk, x, y) {
  const gx0 = chunk.x * chunk.width, gy0 = chunk.y * chunk.height;
  const seed = visualHash(gx0 + x, gy0 + y, chunk.seed), kind = treeKind(chunk, x, y);
  const scale = treeScale(TREE_ART[kind] ? kind : 'o', seed % TREE_VARIANTS);
  const up = Math.ceil((62 * scale - 18) / TILE_H), side = Math.round(22 * scale / TILE_W);
  const out = [];
  for (let dy = -up; dy <= 0; dy++) for (let dx = -side; dx <= side; dx++) {
    const tx = x + dx, ty = y + dy;
    if (tx < 0 || ty < 0 || tx >= chunk.width || ty >= chunk.height) continue;
    if (chunk.collision?.[ty]?.[tx] === '1' || isWater(chunk.tiles[ty][tx])) continue;
    out.push([gx0 + tx, gy0 + ty]);
  }
  return out;
}
/** How see-through a tree is because of the trail under it: only a crown the avatar is actually
 * standing under (on one of the walkable cells it hangs over) is thinned; every other crown stays
 * solid, so trails never leave see-through trees around the scene. `cover` is pathCover's list,
 * (ax, ay) the avatar in tiles. */
export function trailFade(cover, ax, ay) {
  if (!cover || !cover.length) return 1;
  for (const [x, y] of cover) if (Math.abs(x - ax) < .75 && Math.abs(y - ay) < .75) return .45;
  return 1;
}
export function canopyFade(dx, dy) {
  if (dy < -1 || dy > 6) return 1;
  const ax = Math.abs(dx);
  if (ax <= 1.5 && dy <= 5) return .28;
  if (ax <= 3 && dy <= 6) return .55;
  return 1;
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
      else if (glyph === '^') put(ctx, rockStamp(seed % ROCK_VARIANTS, createCanvas), px - 4, py - 4);
      else { const {canvas, dx, dy} = structureStamp(glyph, createCanvas); put(ctx, canvas, px + dx, py + dy); }
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
