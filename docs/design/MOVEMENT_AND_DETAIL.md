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

## ASCII shader (2026-10-18, after Andrew's reference video "ASCII MMORPG")
Reference: a lit 3D scene read back as text - dense small glyphs on near-black, letters for the
mid tones and highlights, stroke glyphs along edges, colour from the scene, grass as green strokes.
- `ascii_art.asciify`: every painted actor/prop (painted.js), tree and rock stamp, and every ground
  tile is shaded as a hidden picture, then read in 1.4 x 2.5 px character cells. Silhouette edges
  (Sobel on coverage) and strong light steps become '|' '-' '_' '/' '\'; other cells take a glyph
  of matching measured ink (GLYPHS ramp, stable variety among equal weights); colour = the cell's
  colour lifted toward the light (actors whiten more). No solid backing - a soft blurred dark ground
  under figures keeps them readable. Ground tiles use stroke/dot glyphs only on a near-black base,
  light read on one fixed scale so tiles match.
- The painted actors and props (realistic proportions, varied tree sizes) are the source pictures.
- Default zoom 2.4 so figures are big enough to read as text.
- Still vector, to convert next: fists, weapon shafts, punch lines, flames.

## Back to ASCII (2026-10-18)
Andrew: the painted art lost the vibe and left ASCII behind. Decision: restore the glyph look and
keep the movement fixes and sharper rendering; rebuild detail as finer glyph art; keep the scale
changes (trees 2-4x a person, realistic proportions) in ASCII.
- The painted vector actors/props (painted.js, painted_props.js) and the fine-pixel renderer are
  removed. Spots, structures, camp, campfire, buildings and the ambush are the hand-made cell
  sprites again, rendered crisp at RES.
- Trees and rocks are glyph art again (`nature_art.js`): one character per cell on a dark
  backing, character and colour from the light (LEAF_GLYPHS '.,:;+*%&@', pine '^A#', stone
  'o0O@', bark '|:!' with '/' '\' roots, birch '=' bands, dead limbs written in '/|\-' strokes),
  on finer GLYPH_W x GLYPH_H (2.4 x 3.6) cells, crowns lit as a whole and clump by clump. Tree
  sizes vary (`art.treeScale`); big trees shrink their cells (`withDetail`) so text stays fine.
- Actors in fine ASCII (`ascii_actors.js`): hand-made paint + glyph rows on 2.2 x 3.6 cells (the
  classic sprites use 4 x 7). The avatar is ten or eleven rows with a three-row head, in four
  facings, front knee-lift and side scissor strides, and a crouch; a side-on wild boar (half a
  person high, bramble mane, tusks), a side-on wolf, a person-height skeleton with a blade, the
  lurker, the wisp, and the old man at the avatar's height. Side-on enemies face the avatar.
  `sprites.paintSprite` draws any sprite with its own `cell` and `roles`.
- Kept from the scale round: canopyFade around the avatar, see-through canopies over enemies and
  spots, trees drawn whole past the fog line, default zoom 1.6.
