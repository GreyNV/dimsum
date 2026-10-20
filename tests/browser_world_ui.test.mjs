import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {regionCue, skillSlots, worldMode} from '../src/dimensional_sim/world/browser/world_ui.js';

test('location cues teach geography without exposing weights', () => {
  assert.match(regionCue({id: 'deep_woods'}), /Branches and tracks/);
  assert.match(regionCue({id: 'still_glade'}), /water/);
  assert.match(regionCue({id: 'deep_woods', worked: ['wood', 'berries']}), /Picked over this life: fewer fallen wood and berries/);
  assert.doesNotMatch(regionCue({id: 'deep_woods', worked: []}), /Picked over/);
  assert.match(regionCue({id: 'old_road'}), /travel/);
  assert.doesNotMatch(regionCue({id: 'deep_woods'}), /\d+%|x\d/);
});

test('three skill slots retain state in either World mode', () => {
  const slots = [{name: 'Trail Sense', state: 'ready'}, {name: 'Ward', state: 'cooldown'}];
  for (const control of ['auto', 'manual']) {
    const view = skillSlots({control, skill_slots: slots});
    assert.equal(view.length, 3);
    assert.deepEqual(view.map(row => row.state), ['ready', 'cooldown', 'locked']);
    assert.deepEqual(view.map(row => row.usable), [true, false, false]);
  }
  assert.equal(worldMode({control: 'manual'}), 'active');
  assert.equal(worldMode({control: 'auto'}), 'auto');
});

test('mobile World has one canvas and both control presentations', () => {
  const html = readFileSync(new URL('../src/dimensional_sim/world/browser/index.html', import.meta.url), 'utf8');
  const css = readFileSync(new URL('../src/dimensional_sim/world/browser/style.css', import.meta.url), 'utf8');
  assert.equal((html.match(/<canvas id="scene"/g) || []).length, 1);
  for (const id of ['context-toggle', 'context-panel', 'skill-bar', 'touch-interact', 'move-stick', 'attack-state'])
    assert.match(html, new RegExp(`id="${id}"`));
  assert.match(css, /body\.active-control \.expedition\{display:none/);
  assert.match(css, /body\.active-control:not\(\.page-open\):not\(\.anchor-active\) \.touch-controls\.manual-only\{display:grid!important\}/);
});

import {edgePoint} from '../src/dimensional_sim/world/browser/scene_fx.js';
import {clockText} from '../src/dimensional_sim/world/browser/world_ui.js';

test('an off-screen camp gets a marker on the inset edge, an on-screen one none', () => {
  const inset = {top: 100, right: 100, bottom: 100, left: 100};
  assert.equal(edgePoint(500, 400, 1000, 800, inset), null);
  const east = edgePoint(3000, 400, 1000, 800, inset);
  assert.deepEqual([Math.round(east.x), Math.round(east.y), east.angle], [900, 400, 0]);
  const corner = edgePoint(-5000, -5000, 1000, 800, inset);
  assert.ok(corner.x >= 100 && corner.y >= 100 && (Math.round(corner.x) === 100 || Math.round(corner.y) === 100));
});

test('skill slots carry a note, a hint and a cooldown charge', () => {
  const [ret, fire] = skillSlots({skill_slots: [
    {name: 'Return to anchor', state: 'cooldown', remaining_ms: 90_000, cooldown_ms: 300_000, hint: 'End this life.'},
    {name: 'Make campfire', state: 'disabled', note: 'Needs 3 sticks (have 1)', hint: 'Set down a fire.'}]});
  assert.equal(ret.note, 'Ready in 1:30');
  assert.equal(ret.charge, .7);
  assert.equal(fire.note, 'Needs 3 sticks (have 1)');
  assert.equal(fire.usable, false);
  assert.equal(clockText(61_000), '1:01');
});

test('possession shows partial charge while ready or active', () => {
  const [ready, active] = skillSlots({skill_slots: [
    {name: 'Possess', state: 'ready', note: '15s available', charge_ms: 30_000, charge_max_ms: 60_000},
    {name: 'Possess', state: 'active', note: '10s left', charge_ms: 20_000, charge_max_ms: 60_000}]});
  assert.equal(ready.charge, .5);
  assert.equal(ready.usable, true);
  assert.equal(active.charge, 1 / 3);
  assert.equal(active.note, '10s left');
});
