# Browser character renderer

The browser is a presentation/input adapter. Python owns positions, collision,
discovery, animation clocks and damage. Transport is frozen in world-browser.md.
No frontend dependency, external font, AI provider or build step is required.

## Module contracts
- browser/art.js: terrain palette and text sprites; 4x7 drawing cells, 24x28
  logical tiles (six columns and four rows). paintChunk returns separate cached
  environment/object surfaces; drawTree repaints one tree for canopy occlusion.
- browser/actors.js: player, enemy and combat-feedback art. Never cached in chunks.
  Punch (no weapon yet): the fist travels from the shoulder (windup -3px, strike
  15px, recover 6px) with speed lines; encounter spot sprites (SPOTS) with a goal
  sparkle; activity poses (POSE: crouch/sit/climb) and a progress bar.
- browser/hud.js: expedition HUD (activity line, six-attribute XP grid, last four
  log entries) and reward popups; reads snapshot fields only. See world-autopilot.md.
- browser/view.js: pure coordinate math, stable uint32 visual noise, resident cache
  pruning and input latch. Visual noise controls punctuation/color only.
- browser/app.js: serial 50ms input requests, resident surfaces, continuous global
  camera, animation drawing, actual-state minimap and accessible DOM controls.
- browser/index.html and style.css: compact copper/olive HUD, keyboard and touch
  controls, pause overlay, responsive layout. No fictitious player health is shown.

World coordinates can be negative. Convert chunk origins with chunk.x * width;
never reset camera/player drawing coordinates when crossing a storage boundary.
Environment surfaces draw first, then padded object surfaces, actors and effects.
Canopies extend above/around blocking trunks. They do not introduce collisions.
Transparent padding keeps canopies visible across chunk boundaries. Logical room
walls in an older pinned world remain visible obstacles; graphics cannot remove them.

## Actors and battle graphics
Actors are solid outlined silhouettes on the shared 4x7 cell grid: each sprite is
equal-sized paint (color role per cell) and glyph (texture) rows. Player 9x9 cells
(36x63px, 1.5x2.25 tiles) with south/north/east views (west mirrors east), two
walk leg frames, a lunge stance and a procedural sword. Bramble boar 11x7 cells
(44x49px) with idle breathing from clock_ms and a segmented HP bar. Feet rest
ACTOR_FOOT px below the tile center; actors depth-sort by row, and tree canopies
one or two rows south are repainted over them. An enemy one or two rows behind
the player gets a translucent x-ray pass so a fight from the south stays visible.
Attack phase: active snapshot = strike; before the active frame was observed =
windup; after = recover. The slash arc and impact burst start when the active
frame is first observed and fade over 220ms; hit flash/shake, floating damage and
a 600ms death dissolve start when a target's HP drops between snapshots. These
client clocks only fade cosmetics; they never decide hits, damage or timing.
Default zoom is 130% (range 70..240%, ZOOM in view.js) so combat reads at a glance.
Reduced motion disables the arc, shake, bob drift and rising numbers.
JS test guard: player >= 1.5x2 tiles, enemy >= 1.5x1.5 tiles with a solid body.

Animation samples player.animation_ms from snapshots. RAF only interpolates
positions and camera; it cannot advance attacks, discover chunks or apply damage.
Only server active/effect metadata triggers the attack effect. Enemy figures are
stationary targets until a later gameplay slice introduces their AI.

## Adding art safely
New encounter: add an EncounterDef to the biome pool (new ENCOUNTER_VERSION for
existing worlds), a SPOTS sprite keyed by its ID and, for a new kind, a POSE and
HUD verb.
Edit TREE/ROCK and PALETTE in art.js; actor sprites, ROLE colors and combat marks
in actors.js. Keep paint/glyph rows rectangular and roles defined (tested). Keep tree trunks centered
over their logical obstacle and within OBJECT_PAD. Reuse text sprites; never bake
the player into a terrain surface. Additional terrain glyphs require coordinated
server transport mapping. For example, a different leaf glyph or color needs no
change to collision metadata, seeds, saves or simulation tests.

## Cache, scaling and failure behavior
Only IDs in frame.resident remain cached; /api/input sends known IDs so unchanged
terrain is not resent/repainted. Minimap draws tiles already cached and discovery
metadata; it never requests/generates chunks. Visited terrain is bright, generated
terrain dim, unknown dark/dotted. Known nonresident regions retain metadata color.

Canvas output tracks device pixel ratio (capped at 3); source character surfaces
have fixed fine cells for crisp text at integer scales. Zoom ranges 70..240% (default 130%) with
an automatic lower bound derived from resident coverage, including 4K viewports.
Reported zoom reflects that bound. Camera clamps to available data, avoiding void
at the outer streamed edge. No storage rectangles appear in the world view.

Requests are serial and abort after 2.5 seconds. Errors release input and pause;
successful reconnection keeps the local pause choice until Resume. Browser blur,
tab hiding and pointer cancellation release held controls. A server lease protects
against abrupt closure; pagehide also sends a best-effort release. Short attack taps
are latched across polling gaps; so are movement taps (queued, max 4, each sent
once with a move:null release between same-direction taps). The browser session
enables Exploration.step_on_press: a new direction press turns AND steps at once,
then holding repeats every movement_interval_ms (terminal/demo keep the original
step-after-interval timing; the flag is not saved). With very slow local requests
(>120ms) a tap can occasionally yield two steps because the input lease holds it; a revision token preserves another tap received
during an in-flight request, with a release edge before its next press. P/visible buttons pause; +/- zoom; WASD/arrows move.

## Verification ledger
Run: .codex/tools/node-v22.22.3-win-x64/node.exe --test tests/browser_view.test.mjs
Focused tests: deterministic decoration, negative coordinates, resident bounds at
390/1440/3840 widths, timestep-independent camera interpolation, cache eviction,
collision readout independent of glyph, short attack latch/in-flight second-tap regression, held-key ordering and
pause/reset, separate cached layer sizes and multi-character art; actor sprite
shape/roles in every pose, actor size guard, west mirror, walk/attack pose changes,
flash/dissolve painting, x-ray and occlusion helpers. Python: every module imported
by app.js is served (actors.js allowlisted in browser_server.STATIC).
Browser screenshots/input/console/responsive QA are owned by lead integration.
Known limits: font rasterization varies by system; an actor standing directly
behind a tree trunk row can briefly overdraw adjacent canopy text during movement
interpolation; the boar has a single front view because enemies do not yet move; canopies are visual overhangs;
camera interpolation adds a small presentation delay; browser transport is local,
single-session and polls authoritative state rather than predicting gameplay.
