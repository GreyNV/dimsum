# Movement feel and render detail (2026-10-18)

Playtest (Andrew, 2026-10-17): getting stuck in the forest - movement feels square and the
avatar snags on trees; the resolution is very low for what the technique can do.

## Movement
- **Corner assist** (`runtime.Exploration._corner_assist`): a cardinal step into a blocked cell
  eases diagonally around a lone obstacle when the cell beside the avatar and the cell beyond the
  obstacle on that side are open (the side with the longer clear run ahead wins, then north/west).
  Diagonals pass the corner of a lone obstacle too; along a wall they still slide, and they never
  squeeze between two blocked cells. Manual input only - autopilot paths never hit walls.
- **Even glide** (`view.glide`): the drawn avatar walks toward its cell at one tile per step interval
  (`movement_interval_ms`, so possession's +20% shows) instead of easing in and out of every tile;
  it hurries when a burst of steps lands.
- **See-through canopies**: leaves repainted over the avatar are drawn at 45% so it never vanishes
  behind a tree.

## Render detail
- `art.RES` (2, or 3 on high-DPI screens; `setResolution`): every stamp and chunk ground surface is
  painted RES times denser than its logical size and copied at logical size (`art.put`). Logical
  sizes, tiles and collision are unchanged.
- Chunk objects (trees, rocks, structures) are no longer a second full-chunk surface: `paintChunk`
  returns a list of stamp copies drawn each frame (`drawObjects`) - lighter at RES.
- Trees are fine lit art (`nature_art.js`): 2x2 px leaf cells shaded by the whole crown and by
  their own leaf clump, 1 px specks of light and shade, half-pixel bark with grain, knots, birch
  lenticels and moss; tiered drooping pines; tapering dead limbs; hanging moss strands. Rocks are
  half-pixel faceted boulders with cracks and lichen.
- Next: actor sprites (boar, wolf, player) and site structures at the same density.

Tests: test_world_runtime (corner assist), test_world_browser, nature_art.test.mjs,
browser_view.test.mjs (RES surfaces, glide).

## Painted actors and props (phase 2, 2026-10-18)
Andrew: "do the same for the actor sprites and structures - good quality art that will hook players".
- `painted.js`: a small painting kit - shapes with boxes (E, R, P smoothed polygons, C capsules),
  `fill` (base colour lit inside its own outline: warm sheen upper left, cool shade lower right,
  thin dark edge), `strokes` (fur, grain, weave) - and `paintedCanvas`, which paints a pose once at
  RES, adds one soft silhouette outline, and caches it. Soft layers (`onLayer`: ground shadows
  under, glows after) stay out of the outline. Hit flash = the canvas washed pale (`flashCanvas`).
- Painted: the avatar (south / north / east / west, walk strides, breathing, crouch), arms, fists
  and weapon shafts; the five enemies (bramble boar with thorny back and ember eyes, river lurker,
  restless bones with a rusted blade, pale wisp, side-on wolf); the old man; the anchor stone; the
  campfire (live flames and sparks).
- `painted_props.js`: every encounter spot (all 58 SPOTS keys), site structure (STRUCTURE_ART),
  camp building part and ambush piece, composed from a prop kit (stones, logs, log ends, planks,
  bushes, pools, mushrooms, prints, bones, skulls, crates, barrels, sacks, cloth, reeds, fish).
- `fine_art.js`: any remaining cell sprite (fallbacks) is rendered from its grid as lit fine art -
  rounded corners, height-field shading, vector glyph marks.
- Without a DOM every builder returns null and the cell sprites remain (node tests).
- Smoothing quality 'low' (bilinear) for these copies: at RES≈screen density it looks the same
  as 'high' and is ~2x cheaper in software rendering (30 fps headless vs 24 before this round).

Tests: tests/painted_art.test.mjs (coverage of every key, frames, no-DOM fallback, vector marks).
