# Dimensional Summoner: browser visual style spec

Based on the dominant existing style: the 4x7 cell sprites (SPOTS, CAMP.stone, ENEMY, ELDER) and the art.js terrain.
Units: **world px** (before camera zoom), **cell** = 4x7 world px (`CELL_W`/`CELL_H`), **tile** = 24x28 px = 6x4 cells.

## 1. Grid and density
- All solid matter is drawn on whole cells. `paint` and `glyph` rows have equal length and count, and a space means transparent.
- One sprite uses one density. Don't mix cell art with free `fillRect`/path art inside one object.
- The player is the only exception (pixel tier): 16x20 art px at 3x3 world px each, 48x60 frame. No other asset uses this tier.
  The pixel tier follows every other rule below (outline, palette, integer offsets, constant frame).
- Positions and offsets are integers in world px. Use `Math.round` before every draw call.
- Rasterise at integer world px once (offscreen stamp), then `drawImage` with `imageSmoothingEnabled = false`,
  the same way art.js stamps work. Don't draw sprite `fillRect`s straight under the zoom*dpr camera transform,
  because that antialiases every box edge.
- Don't squash non-uniformly (`scale(3,2)`). A pose change is new art on the same grid.

## 2. Outline
- Interactive or animate things (actors, spots, camp stone, props you can use) get a 1 px `OUTLINE` (#070a06) ring
  around every opaque cell: `fillRect(x-1, y-1, w+2, h+2)` under the fills.
- Pixel tier: every fill art-pixel must have 4 opaque neighbours (outline or fill). The only exception is the bottom
  (ground-contact) row. Uses the same `OUTLINE` colour (done 2026-10-05).
- Terrain scenery (ground marks, trees, rocks) is glyph-only, with no fill or outline. This keeps interactables readable.
  Don't draw a scenery-category object (tree, stone) in both techniques at very different scales.
- No stroke outlines (`strokeRect`, `stroke()`) on matter.

## 3. Palette families (fills; the glyph ink is a lighter or darker partner of the same hue)
| Category | Fills | Notes |
|---|---|---|
| Ground/void | #11180f #172011 #242418 | background only |
| Foliage | #314822 #44602b #5c7935 #839545 #abb65a, spot l/q #3f6a2e #55743c | |
| Wood/bark | #645033 #7a5532 #9b7944 #b59050, dark #3b2a1c | wagons, crates and branches use these |
| Stone | #536057 #6d7468 #788278 #a3a490 | |
| Water/spirit | #3c6f8f #a6bacc #294661 #9fd0ff | the only cool hues; used for anchor/magic |
| Hostile | #7e3447 #56202f #2a0b10, bone #d9c8a4 #ece0c2 | enemies only |
| Player | hair #3c2a27, scarf #944a3d, tunic #484936, skin #f0bc89 | rust and green; no hostile wine |
| Accent | gold #f1d27a #e5c772 #ffd45e, red #b8323f | a few cells per sprite at most |
- Each sprite uses at most 6 fill roles, plus OUTLINE and inks. No pure white or black fills. Highlights are flat cells.

## 4. Size budget (cells, W x H; the pixel player is 12x~9 cells in world px)
- Humanoid: <= 10x9 (40x63). Enemy (boar): 11x7. Elder 10x9.
- Encounter spot: <= 10x5 (40x35). It must fit inside its tile column ±1 tile.
- Large scenery (wagon, tent, ruin): <= 24x8 cells (96x56) per piece. Build composites from several pieces, each outlined.
- Terrain tree stamp 52x70, rock 32x28 (glyph-only).

## 5. Anchor and depth
- Feet/base sit at tile centre + `ACTOR_FOOT` (12): `left = x - w/2`, `top = y + ACTOR_FOOT - h` (spots use `-2`).
- Each sprite has a constant frame size and the same anchor for every facing, frame and pose. Animation happens inside the frame.
- Shadow: `drawShadow` ellipse at the feet (rx 14–17). It is the only allowed soft-alpha shape under matter.
- Depth sort is by feet row. Canopies south of an actor are repainted over it.

## 6. Lighting and shading
- Light comes from the top-left. A 1-cell lighter role on the top/left faces and darker inks low/right.
- Flat colours only. No gradients, blur, glow or alpha on matter.
- Light VFX (anchor tether, prayer ray, staff glint) and the region ground wash (flat tint, alpha 0.28) may use gradients or alpha <= 0.5. They live in a separate effect
  pass above or behind the sprite and never replace sprite pixels.

## 7. Glyph texture (cell tier)
- Every cell may carry one 7px monospace glyph (`setupText`), drawn at the cell's top-left in the role's `ink`.
- Use glyphs as texture or lines: `/ \ | - _ : ; ^ v o * =`. Don't put letters or words in a sprite.
- Mirroring uses `mirrorRow` (swaps `/ \ ( ) < > [ ]`). Put west/east-asymmetric detail only in glyph maps that mirror.

## 8. Animation
- Frame timing comes from the server's `animation`/`animation_ms`. Each frame is a whole-art-unit change
  (1 cell, or 1 art px = 3 world px). Don't add 1-world-px whole-body bobs to the pixel tier.
- Body parts move as units: outline, fill and highlight of a limb share one offset. Never move a fill
  without its outline (this caused the "detached hand" walk artifact).
- When parts overlap (legs passing), they coincide fully or are separated by >= 2 art px. No 1 px slivers.
- Each animation has a fixed list of frames: idle 1–2, walk 4 (contact/pass/contact/pass), attack 3 (windup/strike/recover).
- Every frame keeps the frame bounding box and feet row from §5.

## 9. Don't
- No `arc`, `ellipse`, `lineTo` polygons, `lineWidth` strokes or rotations for solid objects (see drawAmbushSite).
- No antialiasing on matter. No sub-pixel coordinates. No `imageSmoothing` on upscales.
- No second outline colour. No per-asset invented palettes outside §3.
- Equipment must not swap the character to a different art set. Overlays use the same tier, frame and pose anchors.

## 10. Acceptance checks (automate in tests/browser_view.test.mjs)
- Rasterise each frame with a recording ctx. Assert: the silhouette is one 4-connected component; no fill pixel touches transparency
  (except the ground row); no fill island is narrower or shorter than 2 units; the bbox bottom row and frame size are equal across frames and facings.
- Assert that the colours used ⊆ the palette table, and that `OUTLINE` is the only outline colour.

## 11. Status (2026-10-05)
- Player walk/idle/crouch frames pass the §10 checks (tests/browser_view.test.mjs); stamped per pose and
  drawn with `drawImage`; camera translation rounded to device pixels.
- Ambush wagons rebuilt from outlined cell sprites (`drawAmbushSite`).
- Known exceptions left: anchor glow/tether and prayer ray (effects pass), legacy glyph player sprite (used only
  when equipment overlays are passed; to be retired when pixel-tier equipment exists).
