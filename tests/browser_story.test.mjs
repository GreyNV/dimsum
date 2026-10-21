import test from 'node:test';
import assert from 'node:assert/strict';
import {storyLine, wallEdges, ringOf} from '../src/dimensional_sim/world/browser/story_ui.js';
import {beyondWall} from '../src/dimensional_sim/world/browser/minimap.js';
import {ANCHOR_TEXT, openingBeatText} from '../src/dimensional_sim/world/browser/anchor_ui.js';

test('story line: objective, then why it waits, that it is close, or where to look', () => {
  const current = {objective: 'Reach the grey wall', rings: [6, 6], waits: [], here: false};
  assert.deepEqual(storyLine({current}), {text: 'Story · Reach the grey wall', note: 'Somewhere in ring 6.'});
  assert.equal(storyLine({current: {...current, rings: [2, 5]}}).note, 'Somewhere in rings 2-5.');
  assert.equal(storyLine({current: {...current, here: true}}).note, 'It is close. The avatar will go to it.');
  assert.equal(storyLine({current: {...current, waits: ['needs Willpower 3 (now 2)']}}).note, 'Waiting: needs Willpower 3 (now 2).');
  assert.equal(storyLine({current: null, next: 'Chapter 2 is not written yet.'}).text, 'Story · Chapter 2 is not written yet.');
  assert.equal(storyLine(null), null);
});

test('the wall: chunks past its ring are grey while it is closed; its edge faces inward', () => {
  const state = wall => ({expedition: {story: {wall}}});
  assert.equal(beyondWall(state({ring: 6, open: false}), 7, 0), true);
  assert.equal(beyondWall(state({ring: 6, open: false}), 6, -6), false);
  assert.equal(beyondWall(state({ring: 6, open: true}), 9, 0), false);
  assert.equal(beyondWall({}, 9, 0), false);
  assert.equal(ringOf(-7, 3), 7);
  assert.deepEqual(wallEdges(7, 0, 6), ['west']);
  assert.deepEqual(wallEdges(0, -7, 6), ['south']);
  assert.deepEqual(wallEdges(7, 7, 6), []);          // a corner touches no inside chunk
  assert.deepEqual(wallEdges(8, 0, 6), []);          // two rings out: no wall line here
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
  assert.match(beats.join(' '), /wall/);
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
