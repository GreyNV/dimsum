# Dimensional Summoner
Python >=3.10 standard-library idle simulator. Read docs/technical/world-foundation.md
before world edits; it defines scope, frozen APIs, owners and acceptance criteria.

## Run/test ? PowerShell
```powershell
$env:PYTHONPATH = "src"
python -B -m unittest discover -s tests -v
python -B -m dimensional_sim.cli --seconds 600 --seed 1
python -m pip wheel . --no-deps --wheel-dir .codex/artifacts/wheels
```
See docs/technical/world-quickstart.md for spatial CLI commands.
Quick play: python -B -m dimensional_sim.world.cli play --seed 482910.
Pipeline: python -B -m dimensional_sim.world.cli generate-assets --biome dark_forest --seed 482910 --chunks 24 --size 64x32 --variants 6.

## Map
core.py/content.py: idle lives, six attributes, schema5.
world/models.py,seeds.py: validated contracts/stable seeds.
world/assets.py,pipeline.py: registry vs OFFLINE asset provider.
world/generation.py,repository.py: composition/cache/discovery/world snapshots.
world/animation.py,runtime.py: player animation/movement/combat/timing.
world/renderer.py: pure layers/camera/map; world/cli.py: adapters.
world/browser_server.py, world/browser/: browser client (module map: docs/technical/world-browser.md).
  app.js = state/poll/render loop; actors.js re-exports sprites/player_art/combat_art/place_art;
  anchor_ui, page_ui, minimap, scene_fx, transport, dom = focused UI pieces.
world/encounters.py: biome encounter spots. world/autopilot/ (package): the auto-pilot
expedition (docs/technical/world-autopilot.md), one mixin per concern: expedition (loops),
planning, navigation, spawning, combat, outcomes, vitals, lives (anchor), saves (schema 6-9
migrations; older saves are rejected), presentation, constants. Manual control = locked skill.
world/progression.py: regular/dimensional levels, softcap and speed (owns its curve; no idle-sim import).
core.py/content.py/balance.py: the Phase One idle sim, standalone; the world does not depend on it.
world/catalog.py: ALL forest content as validated data (items, actions, recipes/knowledge/lead outcomes, unlocks, boons, regions).
world/equipment.py: current-life weapon/body slots. Leads, knowledge and Journal roll controls live in autopilot state.
world/actions.py: action bucket (known -> eligible -> weighted) and explain(); regions.py: chunk regions.
world/economy.py: dust/ash/blessing rules and anchor purchases; tuning.py: balance numbers.
world/simulate.py: `cli simulate` (seeded metrics), `cli inspect` (why a spot did/didn't appear, region provenance), `cli regions` (layout).
Action pipeline + lifecycle states: docs/design/ACTION_SYSTEM.md; per-action audit: ACTION_ARCHITECTURE_AUDIT.md.
Unlock/knowledge != always available: never add a permanent action button; extend buckets, outcomes or leads.
Design docs for the closed loop: docs/design/*.md (start with DEFINITION_OF_DONE.md, SYSTEMS_MAP.md).
Debug overlay in the browser: ?debug or the backquote key.
world/session.py: transport-free session (local server and hosted build share it).
world/web.py + web/ + vercel.json: hosted Pyodide build (docs/technical/hosting.md).
equipment-review/: unfinished unrelated React popup; preserve.

## Invariants and safe extensions
Never use hash(), wall clock or shared RNG for generation. Seed/version/specs/catalog/
coordinates reproduce canonical chunks. Runtime, renderer, animation and minimap
must never call providers/AI/network. Player graphics never belong in locations.
Add biomes as validated catalog assets, preserving reachable midpoint exits/spawns;
test negative transitions and snapshot replay. Add animations via validated frame
durations/active-window/hitbox metadata; test bulk/split timing, never infer damage
from pixels. Register only through validation; freeze catalog for existing worlds.
Content rules live in catalog/actions, never in generators or the auto-pilot by id.
Bump encounters.ENCOUNTER_VERSION + add a save upgrade when existing worlds' spot rolls change.
Run focused tests before/after a subsystem, then full unittest and `node --test tests/*.test.mjs`. Preserve existing
idle save/return/progression rules. No credentials or new runtime dependencies needed.
