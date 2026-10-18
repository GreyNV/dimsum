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
