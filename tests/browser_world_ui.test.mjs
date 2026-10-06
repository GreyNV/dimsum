import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {regionCue, skillSlots, worldMode} from '../src/dimensional_sim/world/browser/world_ui.js';

test('location cues teach geography without exposing weights', () => {
  assert.match(regionCue({id: 'deep_woods'}), /Branches and tracks/);
  assert.match(regionCue({id: 'still_glade'}), /water/);
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
  for (const id of ['mode-switch', 'skill-bar', 'touch-interact', 'move-stick', 'attack-state'])
    assert.match(html, new RegExp(`id="${id}"`));
  assert.match(css, /body\.active-control \.expedition\{display:none/);
  assert.match(css, /body\.active-control:not\(\.page-open\):not\(\.anchor-active\) \.touch-controls\.manual-only\{display:grid!important\}/);
});
