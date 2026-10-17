import test from 'node:test';
import assert from 'node:assert/strict';
import {SoundEngine, VOLUMES, WORK, loadSettings, soundEvents, surfaceOf}
  from '../src/dimensional_sim/world/browser/sound.js';

const snap = (over = {}) => ({
  player: {x: 0, y: 0, animation: 'idle', animation_ms: 0, ...over.player},
  targets: over.targets || [],
  expedition: {life: 1, log: [], attributes: {strength: {level: 1}}, item_glints: {amber_charm: '#fff'},
    weapon: {shape: 'thrust'}, campfire: null, ...over.expedition},
});
const names = list => list.map(e => e.name);

test('steps, swings, hits, kills and bites are heard', () => {
  const a = snap({targets: [{id: 'b', hp: 3, strikes: 0}]});
  const b = snap({player: {x: 1, animation: 'attack', animation_ms: 40}, targets: [{id: 'b', hp: 2, strikes: 1}]});
  const heard = soundEvents(a, b, () => 'water');
  assert.deepEqual(heard[0], {name: 'step', surface: 'water'});
  assert.deepEqual(heard[1], {name: 'swing', shape: 'thrust'});
  assert.deepEqual(names(heard).slice(2), ['hit', 'hurt']);
  const c = snap({player: {x: 1, animation: 'attack', animation_ms: 90}, targets: [{id: 'b', hp: 0, strikes: 1}]});
  assert.deepEqual(names(soundEvents(b, c)), ['kill'], 'the same swing is not heard twice');
});

test('log entries, levels, a new fire and a new life are heard', () => {
  const a = snap();
  const b = snap({expedition: {log: [
    {seq: 1, type: 'encounter', items: [['stick', 2]]}, {seq: 2, type: 'encounter', items: [['amber_charm', 1]]},
    {seq: 3, type: 'ambush', items: []}, {seq: 4, type: 'eat', items: [['wild_berries', -1]]},
    {seq: 5, type: 'craft', items: [['walking_staff', 1]]}],
    attributes: {strength: {level: 2}}, campfire: {x: 1, y: 1}}});
  assert.deepEqual(names(soundEvents(a, b)), ['loot', 'rare', 'ambush', 'eat', 'crafted', 'loot', 'level', 'kindle']);
  assert.deepEqual(names(soundEvents(b, snap({expedition: {life: 2}}))), ['death'], 'a new life is only the death');
  assert.deepEqual(soundEvents(null, a), []);
});

test('surfaces, settings and work rhythms', () => {
  assert.equal(surfaceOf('.'), 'grass'); assert.equal(surfaceOf('%'), 'water'); assert.equal(surfaceOf('H'), 'wood');
  assert.equal(surfaceOf('='), 'dirt'); assert.equal(surfaceOf('F'), 'stone');
  assert.deepEqual(loadSettings('{"volume":1,"ambience":false}'), {volume: 1, ambience: false});
  for (const bad of [null, 'nope', '{"volume":9,"ambience":true}', '{"volume":1}']) assert.deepEqual(loadSettings(bad), {volume: 2, ambience: true});
  for (const [patch, ms] of Object.values(WORK)) { assert.equal(typeof patch, 'string'); assert.ok(ms >= 300); }
});

/** A minimal Web Audio stand-in that records node creation. */
function fakeAudio() {
  const made = [];
  const param = () => ({value: 0, setValueAtTime() {}, linearRampToValueAtTime() {}, exponentialRampToValueAtTime() {}, setTargetAtTime() {}});
  const node = kind => { made.push(kind); return {connect() {}, start() {}, stop() {}, gain: param(), frequency: param(), Q: param(), type: '', buffer: null, loop: false}; };
  class Ctx {
    constructor() { this.state = 'running'; this.currentTime = 0; this.sampleRate = 8000; this.destination = {}; }
    createGain() { return node('gain'); } createOscillator() { return node('osc'); }
    createBiquadFilter() { return node('filter'); } createBufferSource() { return node('source'); }
    createBuffer(_, n) { return {getChannelData: () => new Float32Array(n)}; }
    resume() { this.state = 'running'; } suspend() { this.state = 'suspended'; }
  }
  return {Ctx, made};
}

test('every patch plays without errors, and silence makes no nodes', () => {
  const {Ctx, made} = fakeAudio();
  const quiet = new SoundEngine({AudioContextClass: Ctx, settings: {volume: 0, ambience: true}});
  quiet.unlock(); quiet.play({name: 'hit'});
  assert.equal(made.length, 0, 'volume Off never creates a context');
  const engine = new SoundEngine({AudioContextClass: Ctx, settings: {volume: 2, ambience: true}});
  engine.unlock();
  const before = made.length;
  for (const name of ['hit', 'kill', 'hurt', 'ambush', 'loot', 'rare', 'level', 'eat', 'crafted', 'built', 'blessing',
    'kindle', 'shimmer', 'death', 'anchor', 'chop', 'rustle', 'tap', 'thunk', 'scrape', 'sip', 'page', 'click', 'tab'])
    engine.play({name});
  for (const shape of ['punch', 'thrust', 'swing']) engine.play({name: 'swing', shape});
  for (const surface of ['grass', 'dirt', 'water', 'wood', 'stone']) engine.play({name: 'step', surface});
  assert.ok(made.length > before + 40);
  for (let now = 0; now < 20000; now += 250) engine.update({now, paused: false, work: 'gather', water: 1, fire: 1, outdoors: true});
  engine.suspend(true);
  const n = made.length; engine.play({name: 'hit'});
  assert.equal(made.length, n, 'a hidden tab is silent');
  assert.equal(VOLUMES[engine.settings.volume][0], engine.label);
});
