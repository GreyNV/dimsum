import test from 'node:test';
import assert from 'node:assert/strict';
import {TILE_W, TILE_H} from '../src/dimensional_sim/world/browser/view.js';
import {LEAF, LEAF_GLYPHS, TREE_W, blobLight, canopyCells, grassBlades, ripples, drawReflection, drawShores}
  from '../src/dimensional_sim/world/browser/nature_art.js';

test('lit shapes: the upper left is brighter than the lower right, outside is null', () => {
  const ball = [[20, 20, 10]];
  assert.ok(blobLight(ball, 15, 15) > blobLight(ball, 25, 25));
  assert.equal(blobLight(ball, 40, 40), null);
});

test('canopies are deterministic, inside the stamp, and draw from the ramps', () => {
  for (let v = 0; v < 8; v++) {
    const cells = canopyCells(v);
    assert.deepEqual(cells, canopyCells(v));
    assert.ok(cells.length > 40, `variant ${v} has a full crown`);
    for (const c of cells) {
      assert.ok(c.x >= 0 && c.x < TREE_W && c.y >= 0 && c.y < 50);
      assert.ok(LEAF_GLYPHS.includes(c.glyph) && LEAF.includes(c.color));
    }
    const lights = cells.map(c => c.light);
    assert.ok(Math.max(...lights) - Math.min(...lights) > .5, 'real light and shade');
  }
  assert.notDeepEqual(canopyCells(0), canopyCells(1));
});

test('grass blades and ripples stay inside their tile and are stable', () => {
  for (const glyph of ['.', ';', 'o']) for (let v = 0; v < 16; v++) {
    const blades = grassBlades(glyph, v, 7);
    assert.deepEqual(blades, grassBlades(glyph, v, 7));
    for (const b of blades) assert.ok(b.x >= 0 && b.x < TILE_W && b.y < TILE_H && b.y - b.h >= -12 && /^#[0-9a-f]{6}$/.test(b.color));
  }
  assert.ok(grassBlades(';', 3).length > grassBlades('.', 3).length, 'tall grass is denser');
  for (let v = 0; v < 16; v++) for (const r of ripples(v)) assert.ok(r.x >= 0 && r.x < TILE_W && r.y >= 0 && r.y < TILE_H && r.w > 0);
});

test('a reflection is clipped to water and skipped without any', () => {
  const log = [];
  const ctx = new Proxy({}, {get: (_, k) => typeof k === 'string' && !['fillStyle', 'globalAlpha'].includes(k)
    ? (...a) => log.push(k) : undefined, set: () => true});
  drawReflection(ctx, [], 10, () => log.push('draw'));
  assert.deepEqual(log, []);
  drawReflection(ctx, [[0, 0, TILE_W, TILE_H]], 10, () => log.push('draw'));
  assert.ok(log.indexOf('clip') < log.indexOf('draw') && log.includes('scale') && log.at(-1) === 'fillRect');
});

test('shores draw only where water meets land', () => {
  const rects = [];
  const g = {set fillStyle(v) {}, fillRect: (...a) => rects.push(a)};
  drawShores(g, {width: 3, height: 1, seed: 1, tiles: ['www']});
  assert.equal(rects.length, 0, 'open water has no bank');
  drawShores(g, {width: 3, height: 1, seed: 1, tiles: ['.ww']});
  assert.ok(rects.length > 0);
});
