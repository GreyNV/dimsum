/** Lit nature art: grass blades, shaded tree canopies and rocks, dark water with
 * ripples and reflections, and drifting motes. Cosmetic only and deterministic per
 * variant (visualHash), so cached stamps look identical after eviction.
 *
 * Canopies and rocks are shaded like a lit ball: each glyph cell takes a light value
 * from a surface normal (light from the upper left), and the value picks both the
 * character (denser = brighter) and the color. Blades are thin pixel strokes leaning
 * with one wind, so a field reads as grass rather than scattered punctuation. */
import {TILE_W, TILE_H, visualHash} from './view.js';

const LIGHT = (() => { const v = [-.5, -.62, .6], n = Math.hypot(...v); return v.map(c => c / n); })();
const unit = h => (h % 10007) / 10007;

/** Light 0..1 at (px, py) inside a union of circles [cx, cy, r] (null when outside). */
export function blobLight(circles, px, py, sy = 1) {
  let best = null, depth = -1;
  for (const [cx, cy, r] of circles) {
    const dx = (px - cx) / r, dy = (py - cy) / r / sy, d2 = dx * dx + dy * dy;
    if (d2 <= 1 && 1 - d2 > depth) { depth = 1 - d2; best = [dx, dy, Math.sqrt(1 - d2)]; }
  }
  if (!best) return null;
  const lit = best[0] * LIGHT[0] + best[1] * LIGHT[1] + best[2] * LIGHT[2];
  return Math.max(0, Math.min(1, lit * .85 + .12));
}

const ramp = (list, v) => list[Math.max(0, Math.min(list.length - 1, Math.floor(v * list.length)))];

// --- grass -------------------------------------------------------------------
export const GRASS = Object.freeze(['#203316', '#2c441d', '#3a5726', '#4c6c2f', '#618438', '#7f9d46']);
/** Thin leaning strokes for one ground tile: [{x, y, h, lean, color, tip}] (pure). */
export function grassBlades(glyph, variant, seed = 0) {
  const tall = glyph === ';', moss = glyph === 'o';
  const count = tall ? 26 : moss ? 10 : 16;
  const blades = [];
  for (let i = 0; i < count; i++) {
    const h = visualHash(variant * 131 + i, i * 17 + 3, seed);
    if (!tall && h % 7 === 0) continue;               // patchy: a few gaps per tile
    const height = (tall ? 6 : 3) + (h >>> 3) % (tall ? 6 : 4);
    blades.push({x: (h >>> 7) % TILE_W, y: 3 + (h >>> 12) % (TILE_H - 3), h: height,
      lean: ((h >>> 17) % 5) - 1,                     // the wind leans most blades east
      color: GRASS[(h >>> 20) % (tall ? 6 : 4) + (tall ? 0 : 1)], tip: h % 11 === 0});
  }
  return blades;
}
export function drawBlades(ctx, blades) {
  for (const b of blades) for (let k = 0; k < b.h; k++) {
    const t = k / b.h;
    ctx.fillStyle = b.tip && k > b.h - 3 ? '#a9c46a' : b.color;
    ctx.fillRect(Math.round(b.x + b.lean * t * t * 2), b.y - k, 1, 1);
  }
}

// --- trees -------------------------------------------------------------------
export const LEAF = Object.freeze(['#16250f', '#1f3415', '#2b461b', '#395c22', '#4b732a', '#628c33', '#80a53f', '#a6c05a', '#cbd884']);
export const LEAF_GLYPHS = Object.freeze(['.', ',', ':', ';', '+', '*', '%', '&', '@']);
const BARK = ['#2e2317', '#4a3826', '#6c5435', '#937246', '#b59050'];
export const TREE_W = 52, TREE_H = 70;
/** Canopy circles for a tree variant (pixel space of the 52x70 stamp). */
export function canopyShape(variant) {
  const h = i => visualHash(variant, i, 0x7ee);
  const j = (i, span) => (h(i) % (span * 2 + 1)) - span;
  return [[26 + j(1, 2), 25 + j(2, 2), 17 + h(3) % 3], [14 + j(4, 2), 32 + j(5, 2), 11 + h(6) % 3],
    [38 + j(7, 2), 31 + j(8, 2), 11 + h(9) % 3], [24 + j(10, 4), 12 + j(11, 2), 11 + h(12) % 3],
    ...(h(13) % 2 ? [[34 + j(14, 2), 17 + j(15, 2), 9]] : [])];
}
/** Glyph cells of a canopy: [{x, y, glyph, color, light}] on the 4x6 px grid (pure). */
export function canopyCells(variant) {
  const circles = canopyShape(variant), cells = [];
  for (let y = 0; y < 50; y += 6) for (let x = 0; x < TREE_W; x += 4) {
    const n = visualHash(x, y, variant * 7 + 1);
    // ragged rim: each cell tests a slightly larger or smaller crown
    const grow = (unit(visualHash(x, y, variant + 3)) - .45) * 7;
    let light = blobLight(circles.map(([cx, cy, r]) => [cx, cy, r + grow]), x + 2, y + 3);
    if (light === null) continue;
    // leaf clumps: low-frequency patches lighter or darker, plus a darker underside
    const clump = unit(visualHash(Math.floor(x / 10), Math.floor(y / 11), variant + 99)) - .5;
    light = Math.max(0, Math.min(.999, light * 1.3 - .12 + clump * .3 + (unit(n) - .5) * .16 - Math.max(0, y - 30) * .012));
    cells.push({x, y, glyph: ramp(LEAF_GLYPHS, light), color: ramp(LEAF, light), light});
  }
  return cells;
}
const DARK_LEAF = '#0b1408', DARK_BARK = '#140e08';
export function drawLitTree(ctx, variant) {
  // ground shadow (stepped ellipse of translucent rows)
  for (let r = 0; r < 6; r++) {
    const half = Math.round(16 * Math.sqrt(1 - ((r - 2.5) / 3) ** 2));
    ctx.fillStyle = '#04080466'; ctx.fillRect(29 - half, 59 + r, half * 2, 1);
  }
  // trunk: a dark backing, a lit west edge, a dark east edge and flared roots
  ctx.fillStyle = DARK_BARK; ctx.fillRect(20, 40, 12, 22); ctx.fillRect(17, 58, 18, 5);
  for (let y = 40; y < 62; y += 6) for (let x = 20; x < 32; x += 4) {
    const side = (x - 20) / 8, n = visualHash(x, y, variant + 5);
    ctx.fillStyle = ramp(BARK, Math.max(0, .95 - side * .75 + (unit(n) - .5) * .2));
    ctx.fillText(y >= 56 ? (x < 24 ? '/' : x > 24 ? '\\' : '|') : n % 3 ? '|' : ':', x, y);
  }
  // canopy: a dark silhouette (one cell of outline) under lit glyphs
  const cells = canopyCells(variant);
  ctx.fillStyle = '#050a04';
  for (const c of cells) ctx.fillRect(c.x - 1, c.y - 1, 6, 8);
  ctx.fillStyle = DARK_LEAF;
  for (const c of cells) ctx.fillRect(c.x, c.y, 4, 6);
  for (const c of cells) {
    if (c.light < .12) continue;
    ctx.fillStyle = c.color; ctx.fillText(c.glyph, c.x, c.y - 1);
  }
}

// --- rocks -------------------------------------------------------------------
const STONE = ['#252a25', '#363d36', '#4b544b', '#646f63', '#828c7f', '#a3ab9b', '#c8ccbb'];
const STONE_GLYPHS = ['.', ':', ';', 'o', 'O', '0', '@'];
export function drawLitRock(ctx, variant) {
  const h = i => visualHash(variant, i, 0x70c);
  const circles = [[15 + h(1) % 3, 17, 10 + h(2) % 3], [9 + h(3) % 3, 20, 6], [22, 20, 6 + h(4) % 3]];
  for (let r = 0; r < 3; r++) { ctx.fillStyle = '#04080466'; ctx.fillRect(3 - r, 24 + r, 27 + r * 2, 1); }
  const cells = [];
  for (let y = 4; y < 26; y += 6) for (let x = 0; x < 32; x += 4) {
    const light = blobLight(circles, x + 2, y + 3, .8);
    if (light !== null) cells.push({x, y, v: Math.max(0, Math.min(.999, light + (unit(visualHash(x, y, variant)) - .5) * .15))});
  }
  ctx.fillStyle = '#050a04';
  for (const c of cells) ctx.fillRect(c.x - 1, c.y - 1, 6, 8);
  for (const c of cells) {
    ctx.fillStyle = ramp(STONE, c.v * .45); ctx.fillRect(c.x, c.y, 4, 6);
    ctx.fillStyle = ramp(STONE, c.v); ctx.fillText(ramp(STONE_GLYPHS, c.v), c.x, c.y - 1);
  }
}

// --- water -------------------------------------------------------------------
export const WATER_BG = '#0d2232', SHALLOW_BG = '#163640';
const RIPPLE = ['#1d4258', '#2a5873', '#3d7391', '#6ea2bd'];
/** Horizontal ripple dashes for one water tile: [{x, y, w, color}] (pure). */
export function ripples(variant, shallow = false) {
  const out = [];
  for (let row = 0; row < 7; row++) {
    const h = visualHash(variant, row, 0x3a7e);
    if (h % 3 === 0) continue;
    const runs = 1 + h % 2;
    for (let k = 0; k < runs; k++) {
      const g = visualHash(variant, row * 4 + k, 0x3a7f);
      out.push({x: g % TILE_W, y: row * 4 + 1 + (g >>> 5) % 2, w: 2 + (g >>> 8) % (shallow ? 4 : 7),
        color: RIPPLE[(g >>> 12) % (g % 9 === 0 ? 4 : 3)]});
    }
  }
  return out;
}
export function drawRipples(ctx, list) {
  for (const r of list) { ctx.fillStyle = r.color; ctx.fillRect(r.x, r.y, Math.min(r.w, TILE_W - r.x), 1); }
}
/** Moving glints on visible water tiles: [[gx, gy], ...] tile coords; clock in ms. */
export function drawWaterGlints(ctx, tiles, clock) {
  for (const [gx, gy] of tiles) {
    const h = visualHash(gx, gy, 0x9117);
    const period = 2600 + h % 1800, t = ((clock + h % period) % period) / period;
    if (t > .5) continue;
    const a = Math.sin(t * 2 * Math.PI);
    ctx.globalAlpha = .55 * a;
    ctx.fillStyle = '#a9d2e4';
    const x = gx * TILE_W + (h >>> 4) % (TILE_W - 6) + Math.round(t * 6), y = gy * TILE_H + 3 + (h >>> 9) % (TILE_H - 6);
    ctx.fillRect(x, y, 3 + (h >>> 14) % 4, 1);
  }
  ctx.globalAlpha = 1;
}
/** Break a mirrored image on water into ripples: every third row darkened. */
export function rippleMask(ctx, x, y, w, h, color = WATER_BG) {
  ctx.globalAlpha = .6; ctx.fillStyle = color;
  for (let r = y - (y % 3); r < y + h; r += 3) ctx.fillRect(x, r, w, 1);
  ctx.globalAlpha = 1;
}

// --- motes -------------------------------------------------------------------
/** Drifting pollen/firefly specks over the visible world rectangle (world px). */
export function drawMotes(ctx, left, top, right, bottom, clock, density = 1, colors = ['#e6f2a2', '#f4fbcf']) {
  const CELL = 72;
  for (let cy = Math.floor(top / CELL); cy * CELL < bottom; cy++) for (let cx = Math.floor(left / CELL); cx * CELL < right; cx++) {
    const h = visualHash(cx, cy, 0xf1e5);
    if (h % 100 >= 34 * density) continue;
    const s = (h >>> 8) % 6283 / 1000, period = 4000 + h % 3000;
    const x = cx * CELL + (h >>> 4) % CELL + Math.sin(clock / period * 2 + s) * 9;
    const y = cy * CELL + (h >>> 12) % CELL + Math.cos(clock / (period * 1.3) + s) * 6;
    const glow = .5 + .5 * Math.sin(clock / (700 + h % 900) + s);
    if (glow < .15) continue;
    ctx.globalAlpha = .18 * glow; ctx.fillStyle = colors[0]; ctx.fillRect(Math.round(x) - 1, Math.round(y) - 1, 3, 3);
    ctx.globalAlpha = .85 * glow; ctx.fillStyle = colors[1]; ctx.fillRect(Math.round(x), Math.round(y), 1, 1);
  }
  ctx.globalAlpha = 1;
}

// --- shores and reflections ---------------------------------------------------
export const isWater = glyph => glyph === 'w' || glyph === '%';
/** Wet bank and a pale waterline wherever water meets land inside one chunk. */
export function drawShores(g, chunk) {
  const at = (x, y) => chunk.tiles[y]?.[x];
  for (let y = 0; y < chunk.height; y++) for (let x = 0; x < chunk.width; x++) {
    if (!isWater(at(x, y))) continue;
    const px = x * TILE_W, py = y * TILE_H;
    for (const [dx, dy] of [[0, -1], [0, 1], [-1, 0], [1, 0]]) {
      const n = at(x + dx, y + dy);
      if (n === undefined || isWater(n)) continue;
      // shallows: a lighter band fading from the bank into deeper water
      for (let k = 0; k < 6; k++) {
        g.fillStyle = `rgba(70, 130, 145, ${(.16 * (1 - k / 6)).toFixed(3)})`;
        if (dy) g.fillRect(px, dy < 0 ? py + k : py + TILE_H - 1 - k, TILE_W, 1);
        else g.fillRect(dx < 0 ? px + k : px + TILE_W - 1 - k, py, 1, TILE_H);
      }
      // dark wet soil on the land side, a broken pale line on the water side
      g.fillStyle = '#0a140d';
      if (dy) g.fillRect(px, dy < 0 ? py - 2 : py + TILE_H, TILE_W, 2);
      else g.fillRect(dx < 0 ? px - 2 : px + TILE_W, py, 2, TILE_H);
      for (let k = 0; k < (dy ? TILE_W : TILE_H); k += 3) {
        const h = visualHash(x * 64 + k, y * 64 + dx * 7 + dy * 13, chunk.seed);
        if (h % 4 === 0) continue;
        g.fillStyle = h % 5 === 0 ? '#9cc4d4' : '#4f7f97';
        const len = 1 + h % 3;
        if (dy) g.fillRect(px + k, dy < 0 ? py + 1 : py + TILE_H - 2, len, 1);
        else g.fillRect(dx < 0 ? px + 1 : px + TILE_W - 2, py + k, 1, len);
      }
    }
  }
}
/** Mirror `draw` (which paints an object whose base line is `baseY`) onto the water
 * tiles of `waterRects` [[x, y, w, h], ...], faded and broken into ripple rows. */
export function drawReflection(ctx, waterRects, baseY, draw, alpha = .32) {
  if (!waterRects.length) return;
  ctx.save();
  ctx.beginPath();
  for (const [x, y, w, h] of waterRects) ctx.rect(x, y, w, h);
  ctx.clip();
  ctx.globalAlpha = alpha;
  ctx.translate(0, baseY * 2); ctx.scale(1, -1);
  draw(ctx);
  ctx.restore();
  for (const [x, y, w, h] of waterRects) rippleMask(ctx, x, y, w, h);
}

// --- meadow flowers, trodden paths, planks, flagstones ----------------------------
export const BLOOMS = Object.freeze([['#e6c95a', '#8a6a1c'], ['#d08cc0', '#6e3a62'], ['#ece7cf', '#8f8a70'], ['#8fb0e0', '#3c5682']]);
/** Flower heads on a meadow tile: [{x, y, stem, color, eye}] (pure; heads stay inside). */
export function blooms(variant, seed = 0) {
  const out = [], n = 4 + visualHash(variant, 1, seed) % 4;
  for (let i = 0; i < n; i++) {
    const h = visualHash(variant, i + 7, seed);
    const [color, eye] = BLOOMS[(h >>> 3) % (h % 5 === 0 ? 4 : 3)];
    out.push({x: 1 + (h >>> 6) % (TILE_W - 3), y: 4 + (h >>> 11) % (TILE_H - 7), stem: 2 + (h >>> 16) % 3, color, eye});
  }
  return out;
}
export function drawBlooms(ctx, list) {
  for (const b of list) {
    ctx.fillStyle = '#3f6a2a'; ctx.fillRect(b.x, b.y + 1, 1, b.stem);
    ctx.fillStyle = b.color; ctx.fillRect(b.x - 1, b.y, 3, 1); ctx.fillRect(b.x, b.y - 1, 1, 3);
    ctx.fillStyle = b.eye; ctx.fillRect(b.x, b.y, 1, 1);
  }
}
/** Trodden earth: worn hollows, pebbles lit on top with a shadow under, a stray tuft. */
export function drawPath(ctx, variant, seed = 0) {
  for (let i = 0; i < 3; i++) {
    const h = visualHash(variant, i, seed + 11);
    ctx.fillStyle = i % 2 ? '#201d13' : '#2f2a1c';
    ctx.fillRect(h % 18, (h >>> 5) % 22, 4 + (h >>> 10) % 6, 3 + (h >>> 14) % 4);
  }
  for (let i = 0; i < 9; i++) {
    const h = visualHash(variant, i + 20, seed + 11), x = h % (TILE_W - 2), y = 1 + (h >>> 5) % (TILE_H - 3);
    const w = 1 + (h >>> 10) % 2;
    ctx.fillStyle = '#15120b'; ctx.fillRect(x, y + 1, w, 1);
    ctx.fillStyle = h % 3 ? '#6e6450' : '#857a5e'; ctx.fillRect(x, y, w, 1);
    if (w > 1) { ctx.fillStyle = '#a89a76'; ctx.fillRect(x, y, 1, 1); }
  }
  const h = visualHash(variant, 99, seed);
  if (h % 3 === 0) drawBlades(ctx, [{x: h % TILE_W, y: TILE_H - 2, h: 3, lean: 1, color: GRASS[2]},
    {x: (h % TILE_W) + 1, y: TILE_H - 2, h: 4, lean: 2, color: GRASS[3]}]);
}
const WOOD = ['#1d160e', '#35281a', '#4f3d27', '#644d31', '#8a6c44'];
/** Boards across the tile: lit top edge, grain, dark gaps and a pair of nails. */
export function drawPlanks(ctx, variant) {
  for (let b = 0; b < 4; b++) {
    const y = b * 7, h = visualHash(variant, b, 0x91a);
    ctx.fillStyle = WOOD[2 + h % 2]; ctx.fillRect(0, y, TILE_W, 6);
    ctx.fillStyle = WOOD[4]; ctx.fillRect(0, y, TILE_W, 1);
    ctx.fillStyle = WOOD[1]; ctx.fillRect((h >>> 4) % 12, y + 3, 6 + (h >>> 8) % 8, 1);
    ctx.fillStyle = WOOD[0]; ctx.fillRect(0, y + 6, TILE_W, 1);
    ctx.fillStyle = '#c9c2ad'; ctx.fillRect(2, y + 2, 1, 1); ctx.fillRect(TILE_W - 3, y + 2, 1, 1);
  }
}
/** Laid stones: three rows of slabs, lit on the top-left edge, dark mortar between. */
export function drawFlagstones(ctx, variant) {
  ctx.fillStyle = '#121510'; ctx.fillRect(0, 0, TILE_W, TILE_H);
  for (let r = 0; r < 3; r++) {
    let x = -((visualHash(variant, r, 0xf1) % 6));
    while (x < TILE_W) {
      const h = visualHash(variant, r * 10 + x, 0xf2), w = 7 + h % 6, y = r * 9 + 1;
      ctx.fillStyle = ['#363d36', '#3f473f', '#4b544b'][h % 3]; ctx.fillRect(x + 1, y, w - 1, 8);
      ctx.fillStyle = '#687264'; ctx.fillRect(x + 1, y, w - 1, 1); ctx.fillRect(x + 1, y, 1, 8);
      ctx.fillStyle = '#23281f'; ctx.fillRect(x + 1, y + 7, w - 1, 1);
      x += w;
    }
  }
}

/** Burnt ground (old fire pits): soot, grey ash flecks and a few dull embers. */
export function drawScorch(ctx, variant) {
  for (let i = 0; i < 4; i++) {
    const h = visualHash(variant, i, 0x5c0);
    ctx.fillStyle = i % 2 ? '#161512' : '#1d1b17';
    ctx.fillRect(h % 16, (h >>> 5) % 20, 6 + (h >>> 9) % 6, 4 + (h >>> 13) % 5);
  }
  for (let i = 0; i < 14; i++) {
    const h = visualHash(variant, i + 9, 0x5c1);
    ctx.fillStyle = h % 7 === 0 ? '#7a3a1c' : ['#4d4940', '#696055', '#867264'][h % 3];
    ctx.fillRect(h % TILE_W, (h >>> 6) % TILE_H, 1 + (h >>> 11) % 2, 1);
  }
}
/** Rubble, wood chips or old bones: small lit pieces, each with a shadow, among sparse grass. */
export function drawRubble(ctx, variant) {
  drawBlades(ctx, grassBlades('.', variant, 0x7b).filter((_, i) => i % 3 !== 0));
  for (let i = 0; i < 6; i++) {
    const h = visualHash(variant, i, 0x7c), x = 1 + h % (TILE_W - 5), y = 2 + (h >>> 6) % (TILE_H - 5);
    const w = 2 + (h >>> 11) % 3, tone = ['#5a5248', '#6d6458', '#7d705c'][h % 3];
    ctx.fillStyle = '#100e0a'; ctx.fillRect(x + 1, y + 2, w, 1);
    ctx.fillStyle = tone; ctx.fillRect(x, y, w, 2);
    ctx.fillStyle = '#a89a7c'; ctx.fillRect(x, y, w - 1, 1);
  }
}
