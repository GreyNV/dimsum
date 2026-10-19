/** Natural ground (presentation only): breaks the tile grid without touching collision.
 *  - `undergrowth`: smooth value noise on global tile coordinates, so bushes, ferns, saplings,
 *    flowers and stone piles grow in clumps - thick along the forest edge, rare out in the open -
 *    instead of one roll per tile;
 *  - `drawDecor`: the clump pieces, painted and read as ASCII like every other prop;
 *  - `fringe`: ragged edges where a path or bare earth meets grass, so terrain never ends on a
 *    straight tile line.
 * Deterministic per world seed and coordinate (visualHash); never used for gameplay. */
import {visualHash} from './view.js';
import {bush, stone, tuft, mushroom} from './painted_props.js';

const smooth = t => t * t * (3 - 2 * t);
/** Value noise 0..1 at global tile (x, y), lattice `scale` tiles, smoothstep-blended. */
export function valueNoise(x, y, scale, seed) {
  const qx = Math.floor(x / scale), qy = Math.floor(y / scale);
  const fx = smooth(x / scale - qx), fy = smooth(y / scale - qy);
  const v = (i, j) => (visualHash(qx + i, qy + j, seed) % 1000) / 999;
  const top = v(0, 0) * (1 - fx) + v(1, 0) * fx, bottom = v(0, 1) * (1 - fx) + v(1, 1) * fx;
  return top * (1 - fy) + bottom * fy;
}
const GRASSY = new Set(['.', ';', 'o', '*']);
/** What grows on walkable tile (gx, gy), or null: {kind, variant, dx, dy}. `trees` is the
 * number of blocking trees among the 8 neighbours; `glyph` the ground glyph. */
export function undergrowth(gx, gy, glyph, trees, seed) {
  if (!GRASSY.has(glyph)) return null;
  const h = visualHash(gx, gy, seed ^ 0x6e0d);
  const patch = valueNoise(gx + 3, gy - 7, 5, seed ^ 0x5eed) * .55 + valueNoise(gx, gy, 2, seed ^ 0xbeef) * .45;
  const chance = Math.max(0, (patch - .46) * 1.9) + trees * .15;   // clumps, and thick along edges
  if ((h % 1000) / 1000 >= chance) return null;
  const rocky = valueNoise(gx, gy, 7, seed ^ 0x70c4) > .72;
  const roll = (h >>> 10) % 100;
  const kind = rocky ? (roll < 70 ? 'stones' : 'ferns')
    : trees >= 2 ? (roll < 45 ? 'bush' : roll < 75 ? 'ferns' : 'sapling')
    : trees === 1 ? (roll < 40 ? 'ferns' : roll < 70 ? 'bush' : roll < 85 ? 'mushrooms' : 'sapling')
    : (roll < 45 ? 'flowers' : roll < 75 ? 'ferns' : 'bush');
  return {kind, variant: (h >>> 17) % 4, dx: ((h >>> 20) % 9) - 4, dy: ((h >>> 24) % 7) - 3};
}
const LEAVES = ['#4f7a34', '#5c7f3c', '#44602b', '#628c33'];
/** Paint one clump piece in a 42 x 36 frame (ground line at the bottom); drawn at 1.5x the
 * 28 x 24 sketch so undergrowth holds its own beside big trees. */
export const DECOR_W = 42, DECOR_H = 36;
export function drawDecor(c, kind, variant) {
  c.scale(1.5, 1.5);
  const v = variant, r = (i, n) => (visualHash(v, i, 0xdec0) % n);
  if (kind === 'bush') {
    bush(c, 11 + r(1, 5), 16, 5 + r(2, 3), {color: LEAVES[v % 4], seed: v + 1, berries: v === 3 ? '#b8323f' : null});
    if (v % 2) bush(c, 19, 18, 3.5, {color: LEAVES[(v + 1) % 4], seed: v + 5});
  } else if (kind === 'ferns') {
    for (let i = 0; i < 4 + r(3, 3); i++) tuft(c, 5 + r(10 + i, 18), 22 - r(20 + i, 5), 4 + r(30 + i, 4), i % 2 ? '#6f9a3e' : '#86a84a');
  } else if (kind === 'sapling') {
    c.fillStyle = '#5e4630'; c.fillRect(13, 12, 1.4, 10);
    bush(c, 13.6, 10, 4 + r(4, 2), {color: LEAVES[(v + 2) % 4], seed: v + 9});
    tuft(c, 9, 22, 3); tuft(c, 18, 22, 3);
  } else if (kind === 'stones') {
    stone(c, 10 + r(5, 4), 18, 4 + r(6, 2), 3, {moss: v % 2 === 0});
    stone(c, 18, 19, 3, 2.2, {color: '#6d7468'});
    if (v > 1) stone(c, 14, 21, 2.2, 1.6, {color: '#8d9585'});
  } else if (kind === 'mushrooms') {
    for (let i = 0; i < 3; i++) mushroom(c, 8 + i * 5 + r(40 + i, 3), 21 - (i % 2) * 2, 1.5 + (i === 1 ? .6 : 0), v % 2 ? '#c9864a' : '#b8323f');
    tuft(c, 6, 22, 3);
  } else {   // flowers
    for (let i = 0; i < 6; i++) {
      const x = 4 + r(50 + i, 20), y = 12 + r(60 + i, 9);
      c.strokeStyle = '#4b6f2c'; c.lineWidth = .5; c.beginPath(); c.moveTo(x, y); c.lineTo(x, y + 3); c.stroke();
      c.fillStyle = ['#e6c95a', '#d08cc0', '#ece7cf', '#8fb0e0'][(v + i) % 4];
      c.beginPath(); c.arc(x, y, 1, 0, Math.PI * 2); c.fill();
    }
    tuft(c, 8, 22, 3); tuft(c, 18, 22, 3.5);
  }
}
/** Terrain families for ragged edges: a path or bare earth spills over the grass beside it. */
export const SPILLS = Object.freeze({'=': 3, 'x': 2, ':': 2, 'F': 2});
/** A ragged band polygon inside a tile (w x h at px, py) along one side: depth 1..`depth` px. */
export function raggedBand(px, py, w, h, side, depth, seed) {
  const pts = [], steps = 6;
  const bite = i => 1 + (visualHash(i, side.length, seed) % 100) / 100 * (depth - 1);
  if (side === 'n' || side === 's') {
    const edge = side === 'n' ? py : py + h, dir = side === 'n' ? 1 : -1;
    pts.push([px, edge]);
    for (let i = 0; i <= steps; i++) pts.push([px + w * i / steps, edge + dir * bite(i)]);
    pts.push([px + w, edge]);
  } else {
    const edge = side === 'w' ? px : px + w, dir = side === 'w' ? 1 : -1;
    pts.push([edge, py]);
    for (let i = 0; i <= steps; i++) pts.push([edge + dir * bite(i), py + h * i / steps]);
    pts.push([edge, py + h]);
  }
  return pts;
}
