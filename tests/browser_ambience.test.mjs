import test from 'node:test';
import assert from 'node:assert/strict';
import {dayGrade} from '../src/dimensional_sim/world/browser/scene_fx.js';
import {BEND, swayKind, windAt, windShear} from '../src/dimensional_sim/world/browser/wind.js';

const DAY = 720_000, at = f => dayGrade({time_ms: Math.round(f * DAY), day_ms: DAY});

test('dawn starts rosy and warms, then pales into plain daylight over minutes', () => {
  const dawn = at(0), morning = at(.1), late = at(.2), noon = at(.4);
  assert.ok(dawn.r > dawn.b && dawn.tint > .3, 'a rosy dawn');
  assert.ok(dawn.tint > morning.tint && morning.tint > late.tint && late.tint > noon.tint, 'the colour fades gradually');
  assert.ok(dawn.dim > morning.dim && morning.dim >= late.dim, 'and the morning brightens');
  assert.equal(noon.tint, 0);
  assert.equal(noon.dim, 0);
  assert.ok(at(.64).sun > 0 && !at(.64).east, 'the evening sun is low in the west');
  assert.ok(at(.02).east, 'the morning sun is in the east');
});

test('the grade has no seams: small steps in time make small changes', () => {
  for (let f = 0; f < 1; f += .001) {
    const a = at(f), b = at(f + .001);
    assert.ok(Math.abs(a.tint - b.tint) < .03 && Math.abs(a.r - b.r) < 12, `jump at ${f.toFixed(3)}`);
  }
  assert.deepEqual(at(0), at(1));
  assert.equal(dayGrade(null).tint, 0);
});

test('wind bends plants by kind, neighbours alike, and leaves stones still', () => {
  assert.equal(windShear(3, 4, 1000, 'stones'), 0);
  assert.equal(swayKind({decor: 'ferns'}, '.'), 'ferns');
  assert.equal(swayKind({}, 'T'), 'tree');
  assert.equal(swayKind({}, '^'), null);
  let most = 0;
  for (let t = 0; t < 20_000; t += 97) {
    const w = windAt(10, 10, t);
    assert.ok(w > -.5 && w < 1.3);
    most = Math.max(most, Math.abs(windShear(10, 10, t, 'ferns')));
    assert.ok(Math.abs(windAt(10, 10, t) - windAt(11, 10, t)) < .35, 'gusts sweep, they do not flicker tile to tile');
  }
  assert.ok(most > BEND.ferns * .6, 'gusts do arrive');
});
