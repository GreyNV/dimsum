# Browser character world - scope and contract

## Scope and direction
User direction: detailed character art in a browser, smaller cells, seamless
scrolling. Use the first generated forest concept as the engineering default;
no further visual selection is required by the user's autonomous-work instruction.
This supersedes the foundation's browser-out-of-scope decision for this slice.
The concept is an art-direction reference, not a static background image.

In scope: local browser client, fine multi-character terrain/player art, continuous
world-space camera, terrain minimap, keyboard movement/attack, zoom, pause, a local
standard-library adapter to the existing authoritative simulation, and an opt-in
open terrain catalog. Preserve terminal play and existing pinned worlds.
Out of scope: hosting, accounts, multiplayer, enemy AI, merging idle balance,
external AI services, changing existing saved room worlds into open worlds.

## Architectural decisions
B1: Python remains authoritative. The browser paints Canvas text, independently
of simulation ticks. No raster world screenshot, AI call, or provider dependency.
B2: Add ChunkAsset.topology (room default, open opt-in). Room assets continue to
serialize byte-identically as schema1. Open assets use schema2 with topology=open.
Open assets describe every walkable boundary cell as an exit; all exits/spawns
must be reachable. Open terrain layout is pinned by tag open-terrain-v1 and catalog
identity; existing generator1 room behavior remains unchanged.
B3: Open terrain uses global integer coordinate noise and connected winding paths.
Chunk edges are storage boundaries, not enclosing walls. Movement accepts any
listed exit. Collision remains authoritative. Cross-edge hitboxes use world
coordinates, so an invisible storage boundary cannot stop an attack.
B4: Browser server binds loopback only. One local game/session, fixed 20ms ticks,
input lease expires after 300ms. Pause/blur release input. No runtime dependency
beyond Python; HTML/CSS/ES modules ship as package data. HTTP is an adapter only.
B5: Frame snapshots read resident chunks through peek only; rendering/minimap never
generate. Client keeps only the returned 3x3 resident set. Drawing cells are finer
than movement cells. Cached text terrain redraws independently of actor animation.

## Frozen browser transport
GET /api/state returns the same frame as POST /api/input. POST JSON:
{move:null|north|east|south|west, attack:boolean, paused:boolean, known:string[]}.
known contains chunk IDs already cached by client (max25). Unknown fields rejected.
Frame: {world_seed:string, clock_ms:int, movement_interval_ms:int,
player:{x:int,y:int,facing:string,animation:string,animation_ms:int,active:boolean},
targets:[{id:string,x:int,y:int,hp:int}], effects:[{x:int,y:int}],
chunks:[{id:string,x:int,y:int,width:int,height:int,biome:string,seed:int,
tiles:string[],collision:string[]}], resident:string[],
minimap:[{x:int,y:int,status:unknown|generated|visited,biome:string|null}],
chunk_width:int,chunk_height:int,paused:boolean}.
Player/target/effect x,y are GLOBAL movement-cell coordinates. Chunk x,y are chunk
coordinates; IDs dimension:x:y. Chunk seed is a deterministic uint32 VISUAL seed;
world seed stays a string to avoid JS precision loss. tiles use '=' path, '.' floor,
'T' tree, '^' rock, ';' grass. collision uses '1'/'0'. Frontend MUST use collision
for readout/tests and never compute gameplay from glyphs. Missing chunks returned
only; GET state returns all resident chunks. Input is held, attack rising-edge.
Sprites and colors live in browser/art.js; view math in browser/view.js; app.js
owns transport/input/camera/rendering; no generation inside animation/minimap.

## Definition of Done
B-D1: Existing 143 tests pass and old room asset canonical data stays unchanged.
B-D2: Open chunks reproduce canonical data after order changes/save reload;
>=50 coordinates validate reachable exits/spawns, including negative coordinates.
B-D3: Walk across a non-midpoint edge in all four directions; walls block;
a cross-edge active hit damages once, before active time it does not.
B-D4: Browser renders an actual seeded forest using small text cells, multi-cell
trees and player, two colors, adjacent chunks, and a smoothly following camera.
B-D5: Browser movement/attack/pause/zoom/blur tested; no JS errors; rendered
minimap distinguishes generated/visited/unknown and moves with actual position.
B-D6: Frame reads generate zero chunks; input expiry stops movement; malformed
requests cannot alter game; renderer FPS never controls simulation damage time.
B-D7: Full suite and wheel build pass; browser files included in wheel; run and
extension instructions, verification ledger, and known limitations updated.

## Work packages and dependencies
Discovery/baseline (143 tests pass) -> contracts (this file) ->
{B-W world topology/generation/runtime, B-U browser art/input/rendering} ->
B-A local adapter/integration -> B-V tests/browser QA/docs.
B-W: models.py, open_terrain.py, generation.py, runtime.py; tests open world and
cross-edge combat; document topology/version/save behavior here.
B-U: browser/{index.html,style.css,art.js,view.js,app.js}; implement frozen protocol;
node tests for view/art invariants; document renderer contract near code.
B-A: browser_server.py, cli.py, pyproject.toml; test transport purity/validation,
input lease and packaged resources. No shared interface redesign by delegates.
B-V: inspect diffs, unit/integration/regressions, browser keyboard/screenshots,
responsive QA, wheel, update ledger and AGENTS/quickstart.

## Risks and failure behavior
Local server is a single-player development adapter, not an internet service.
A disconnected browser stops input after its lease. Bad assets/saves still fail
validation. Missing optional assets use bundled catalog for new worlds only.
Character detail depends on font rasterization; use monospace/system fonts and
DPR-aware canvas. Camera coverage must stay inside resident data at all zooms.
No external network/font dependency. Input/transport errors show reconnect status.

## Verification ledger
Baseline: 143 unittest tests pass (4.239s), before browser/topology modifications.
B-W/B-U/B-A: implemented (open topology, renderer, loopback adapter).
B-V 2026-10-04 battle graphics: actor sprites enlarged from 6x5 loose glyphs
(24x35px, smaller than one tile at default zoom) to outlined 9x9 player and 11x7
enemy silhouettes in browser/actors.js, with 4-way views, sword poses, slash arc,
hit flash, damage numbers, HP bar, death dissolve, depth sort, canopy occlusion,
x-ray and 130% default zoom. 153 unittest + 13 node tests pass; headless Chromium
1280x800 and 390x844 fight-to-defeat run with no console errors.
2026-10-04 auto-pilot: the character explores and resolves biome encounters by
itself; manual move/attack input is ignored until the take_control skill is
unlocked. Frame gained spots/target_kinds/expedition fields; see
world-autopilot.md for the additive transport contract.
2026-10-04 movement fix: taps only turned the player (a step needed 120ms of
continuous hold, and sub-poll taps never reached the server). Browser sessions
now step on press (Exploration.step_on_press) and the client queues taps. 154
unittest + 14 node tests; 6 headless taps of 30/80ms = 6 steps; holds unchanged.
