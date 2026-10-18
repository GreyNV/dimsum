import test from 'node:test';
import assert from 'node:assert/strict';
import {TILE_W, TILE_H} from '../src/dimensional_sim/world/browser/view.js';
import {LEAF, LEAF_STEP, TREE_W, blobLight, leafCells, leafClumps, canopyShape, grassBlades, ripples, drawReflection, drawShores}
  from '../src/dimensional_sim/world/browser/nature_art.js';

test('lit shapes: the upper left is brighter than the lower right, outside is null', () => {
  const ball = [[20, 20, 10]];
  assert.ok(blobLight(ball, 15, 15) > blobLight(ball, 25, 25));
  assert.equal(blobLight(ball, 40, 40), null);
});

test('canopies are fine leaf cells: deterministic, inside the stamp, lit clump by clump', () => {
  for (let v = 0; v < 8; v++) {
    const cells = leafCells(v);
    assert.deepEqual(cells, leafCells(v));
    assert.ok(cells.length > 300, `variant ${v} has a dense crown (${cells.length} cells)`);
    for (const c of cells) {
      assert.ok(c.x >= 0 && c.x < TREE_W && c.y >= 0 && c.y < 52 && c.x % LEAF_STEP === 0);
      assert.ok(LEAF.includes(c.color));
    }
    const lights = cells.map(c => c.v);
    assert.ok(Math.max(...lights) - Math.min(...lights) > .5, 'real light and shade');
    assert.ok(leafClumps(v, canopyShape(v)).length > 20, 'many leaf clumps');
  }
  assert.notDeepEqual(leafCells(0), leafCells(1));
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

test('every tree kind draws its own stamp and pines stay inside the stamp', async () => {
  const {TREE_ART, TREE_KIND_LETTERS, pineCells} = await import('../src/dimensional_sim/world/browser/nature_art.js');
  assert.deepEqual(Object.keys(TREE_ART).sort(), Object.values(TREE_KIND_LETTERS).sort());
  for (const v of [0, 3, 7]) {
    const cells = pineCells(v);
    assert.deepEqual(cells, pineCells(v), 'deterministic');
    assert.ok(cells.length > 40);
    for (const c of cells) assert.ok(c.x >= 0 && c.x < TREE_W && c.y >= 0 && c.y < 54);
    const top = Math.min(...cells.map(c => c.y)), widthAt = y => cells.filter(c => c.y === y).length;
    assert.ok(widthAt(top) < widthAt(top + 36), 'a pine narrows to its tip');
  }
  const calls = [];
  const ctx = new Proxy({}, {get: (_, k) => k === 'fillText' || k === 'fillRect' ? (...a) => calls.push(k) : undefined, set: () => true});
  for (const draw of Object.values(TREE_ART)) { calls.length = 0; draw(ctx, 2); assert.ok(calls.length > 20); }
});
