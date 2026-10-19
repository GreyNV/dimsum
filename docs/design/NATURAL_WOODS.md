# Natural woods (2026-10-19)

Andrew's reference ("Cobo Makes Games": trees spread evenly look fake; real woods grow in groves
with open clearings, rocks lie in piles). Our locations looked square: every unwalkable cell was a
tree centred on its tile, and terrain, tint and decoration all followed the tile grid.

## Layer 1 - drawing only (no gameplay change)
- Trees stand off-centre: each trunk is nudged up to 5 px across and 3 px down/up within its own
  tile (`art.treeAt`), on top of the size and kind variety.
- Undergrowth in clumps (`natural_ground.js`): smooth value noise on global tile coordinates plus the
  number of neighbouring trees decides where bushes, ferns, saplings, mushrooms, flowers and stone
  piles grow - thick along forest edges, in patches in the open, never on paths. Painted and read as
  ASCII like every prop; 6 kinds x 4 variants of stamps.
- Ragged terrain edges: a path or bare earth spills a few px over the grass beside it, along a
  jagged band (`raggedBand`).
- Soft region borders: the region tint is painted on a padded canvas (edge tiles clamped outward)
  and blurred before cropping (`scene_fx.tintPicture`).

## Layer 2 - generator v6 (world shape)
- `open_terrain._grove_block`: three octaves of smoothstep value noise (`_smooth_noise`, integer
  maths) make groves: nearly solid cores, an inner and an outer rim of thinning single trees, and a
  rare lone tree in the open. Region `canopy` sets how much land is grove (`t = 74 - canopy*0.55`),
  so deep woods keep glades and open country grows groves.
  Blocked share by region (11x11 chunks, seed 482910): old road 7% -> 16%, still glade 2% -> 8%,
  deep woods 70% -> 68%, bramble thicket 59% -> 55%.
- Boulders lie in piles (noise, scale 7) instead of one blocked cell in eleven at random.
- Walkable brush grows in clumps (noise, scale 5).
- `GENERATOR_VERSION = 6`, world save schema 7. Saved worlds keep their pinned generator mid-life
  and are regrown in the v6 shape at the next rebirth (`lives._current_generator_world`).

## Balance check (8 seeds x 90 min, shopper bot)
| | v5 worlds | v6 worlds |
|---|---|---|
| lives | 31 | 39 |
| life length, median | 17.5 min | 11.6 min |
| starvation share | 52% | 67% |
Shorter lives, mostly from starvation: groves near the anchor lengthen walks between food. The food
phase (audit round 2, phase A) is now the priority.

Tests: natural ground test in browser_view.test.mjs (clumping, edges, bands); generator version
and schema pins updated; region variety test uses seeds 2-4.
