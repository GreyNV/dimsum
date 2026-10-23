import test from 'node:test';
import assert from 'node:assert/strict';
import {storyLine} from '../src/dimensional_sim/world/browser/story_ui.js';
import {ANCHOR_TEXT, anchorDialogue, openingBeatText} from '../src/dimensional_sim/world/browser/anchor_ui.js';

test('story line: objective, then why it waits, that it is close, or where to look', () => {
  const current = {objective: 'Reach the grey wall', rings: [6, 6], waits: [], here: false};
  assert.deepEqual(storyLine({current}), {text: 'Story · Reach the grey wall', note: 'Somewhere in ring 6.'});
  assert.equal(storyLine({current: {...current, rings: [2, 5]}}).note, 'Somewhere in rings 2-5.');
  assert.equal(storyLine({current: {...current, here: true}}).note, 'It is close. The avatar will go to it.');
  assert.equal(storyLine({current: {...current, waits: ['needs Willpower 3 (now 2)']}}).note, 'Waiting: needs Willpower 3 (now 2).');
  assert.equal(storyLine({current: null, next: 'Chapter 2 is not written yet.'}).text, 'Story · Chapter 2 is not written yet.');
  assert.equal(storyLine(null), null);
});

test('the opening tells its story in short beats before the shop', () => {
  const opening = {anchor_space: {kind: 'opening'}};
  const beats = ANCHOR_TEXT.opening.beats;
  assert.ok(beats.length >= 3 && beats.length <= 5);
  for (const beat of beats) assert.ok(beat.length <= 260, 'a beat fits on a phone screen');
  assert.equal(openingBeatText(opening, 0), beats[0]);
  assert.equal(openingBeatText(opening, beats.length), null, 'then the shop');
  assert.equal(openingBeatText({anchor_space: {kind: 'death'}}, 0), null, 'only before the first life');
  assert.match(beats.join(' '), /ash/);
  assert.match(beats.join(' '), /anchor/);
  assert.match(beats.join(' '), /cannot die/);
});

test('the anchor names the cause of death on every return', () => {
  const ex = {anchor_space: {kind: 'death', first_return: false},
    report: {lines: ['Survived: 4m 12s', 'Cause: a wolf in the night', 'Returning to anchor...']}};
  assert.equal(anchorDialogue(ex), 'Cause: a wolf in the night');
  assert.match(anchorDialogue({...ex, anchor_space: {kind: 'death', first_return: true}}),
    /Cause: a wolf in the night.*dimensional ash/);
  assert.equal(anchorDialogue({...ex, anchor_space: {kind: 'contact'}}), '');
});

test('story cards: only new story lines, grouped by the place they came from', async () => {
  const {newStoryCards} = await import('../src/dimensional_sim/world/browser/story_ui.js');
  const log = [
    {seq: 4, type: 'story', encounter: 'a', text: 'old'},
    {seq: 5, type: 'encounter', encounter: 'a', text: 'Read the notes.'},
    {seq: 6, type: 'story', encounter: 'a', text: 'one'},
    {seq: 7, type: 'story', encounter: 'a', text: 'two'},
    {seq: 8, type: 'story', encounter: 'b', text: 'three'},
  ];
  assert.deepEqual(newStoryCards(log, 4), {cards: [{encounter: 'a', lines: ['one', 'two']}, {encounter: 'b', lines: ['three']}], seq: 8});
  assert.deepEqual(newStoryCards(log, 8), {cards: [], seq: 8});
});

test('the opening starts dark and the anchor stone fades in first, the body after', async () => {
  const {openingReveal} = await import('../src/dimensional_sim/world/browser/anchor_ui.js');
  const ex = {anchor_space: {kind: 'opening'}};
  assert.equal(openingReveal({anchor_space: {kind: 'death'}}, 0), null);
  const start = openingReveal(ex, 1000);
  assert.deepEqual(start, {anchor: 0, body: 0, world: 0});
  const later = openingReveal(ex, 1000 + 3000);
  assert.ok(later.anchor > .4 && later.anchor < 1 && later.body === 0 && later.world === 0);
  assert.equal(openingReveal(ex, 1000 + 10000).anchor, 1);
});
