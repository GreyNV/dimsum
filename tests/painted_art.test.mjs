import test from 'node:test';
import assert from 'node:assert/strict';
import {SPOTS, AMBUSH, BUILDING_PARTS} from '../src/dimensional_sim/world/browser/place_art.js';
import {STRUCTURE_ART} from '../src/dimensional_sim/world/browser/art.js';
import {ENEMY_SPRITES} from '../src/dimensional_sim/world/browser/combat_art.js';
import {ENEMY_FRAMES, E, P, C, R, enemyCanvas, heroCanvas, fill} from '../src/dimensional_sim/world/browser/painted.js';
import {SPOT_ART, STRUCTURE_PAINT, PART_PAINT, spotCanvas} from '../src/dimensional_sim/world/browser/painted_props.js';

test('every encounter, structure, camp part, wreck piece and enemy has painted art', () => {
  assert.deepEqual(Object.keys(SPOTS).filter(k => !SPOT_ART[k]), [], 'spots without painted art');
  assert.deepEqual(Object.keys(STRUCTURE_ART).filter(k => !STRUCTURE_PAINT[k]), [], 'structures');
  assert.deepEqual(Object.keys(BUILDING_PARTS).filter(k => !PART_PAINT[k]), [], 'camp building parts');
  assert.deepEqual(Object.keys(AMBUSH).filter(k => !PART_PAINT[k === 'sack' ? 'ambushSack' : k]), [], 'ambush pieces');
  assert.deepEqual(Object.keys(ENEMY_SPRITES).filter(k => !ENEMY_FRAMES[k]), [], 'enemies');
});

test('without a DOM the painted builders step aside for the cell-sprite fallback', () => {
  assert.equal(heroCanvas('south', 0, 0, false), null);
  assert.equal(enemyCanvas('boar'), null);
  assert.equal(spotCanvas('bramble_berries'), null);
});

test('painted props draw only inside their frame (a recording context; local transforms within a few px)', () => {
  const pts = [];
  let clipped = 0, depth = 0;   // strokes inside a clip (net mesh, grain) may overrun: the clip trims them
  const rec = new Proxy({}, {get: (t, k) => {
    if (k in t) return t[k];
    if (k === 'save') return () => depth++;
    if (k === 'restore') return () => { depth--; if (depth < clipped) clipped = 0; };
    if (k === 'clip') return () => { clipped = depth; };
    if (['moveTo', 'lineTo', 'fillRect', 'ellipse', 'arc'].includes(k)) return (x, y) => { if (!clipped) pts.push([x, y]); };
    if (k === 'createRadialGradient' || k === 'createLinearGradient') return () => ({addColorStop() {}});
    return () => {};
  }, set: (t, k, v) => { t[k] = v; return true; }});
  for (const [key, [w, h, draw]] of Object.entries(SPOT_ART)) {
    pts.length = 0; draw(rec, w, h);
    assert.ok(pts.length > 0, `${key} draws something`);
    for (const [x, y] of pts) assert.ok(x >= -6 && x <= w + 6 && y >= -6 && y <= h + 6, `${key} stays in its ${w}x${h} frame (${x}, ${y})`);
  }
});

test('shapes know their boxes', () => {
  assert.deepEqual(E(10, 10, 3, 2).box, [7, 8, 6, 4]);
  assert.deepEqual(R(1, 2, 3, 4).box, [1, 2, 3, 4]);
  assert.deepEqual(P([[0, 0], [4, 1], [2, 5]]).box, [0, 0, 4, 5]);
  assert.deepEqual(C(0, 0, 10, 0, 2).box, [-2, -2, 14, 4]);
  assert.equal(typeof fill, 'function');
});
