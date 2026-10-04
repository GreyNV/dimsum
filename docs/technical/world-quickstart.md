# World foundation: run and extend
## Setup
Python 3.10+; no new runtime packages. From the repository in PowerShell:
```powershell
$env:PYTHONPATH = "src"
python -B -m dimensional_sim.world.cli play --seed 482910
```
WASD or Windows arrow keys move; Space attacks; Q/Ctrl-C exits and restores the
console. Movement needs one 120ms interval; the terminal holds key-repeat pulses
for 160ms. Attack locks movement for its windup, active window and recovery.
--fps changes display cadence only; simulation runs fixed 20ms ticks. --plain
disables ANSI colors. Frame encoding also supports noninteractive plain output.

```powershell
python -B -m dimensional_sim.world.cli demo --commands "east:120,attack:400,wait:120" --format json
python -B -m dimensional_sim.world.cli chunk --seed 482910 --dimension forest --x 4 --y -7
python -B -m dimensional_sim.world.cli demo --save .codex/artifacts/exploration.json
python -B -m dimensional_sim.world.cli play --load .codex/artifacts/exploration.json
```
Each script token is a discrete input gesture, with an explicit release between
tokens. Core advance(ms,InputCommand) instead holds input over that interval.
Targets are stationary; they do not attack the player. Hit/death graphics exist
as reusable assets, but player injury/death gameplay is outside this slice.
Map symbols: ? unknown, . generated, o visited, @ current chunk. Rendering the
map never generates or discovers chunks; movement streaming generates neighbors.

Optional installation: python -m pip install -e . exposes dimensional-world and
the existing dimensional-sim command. No Node/browser setup is required for worlds.

## Generate an offline reusable catalog
```powershell
python -B -m dimensional_sim.world.cli generate-assets --biome dark_forest --seed 482910 --chunks 24 --size 64x32 --variants 6 --output .codex/artifacts/world-assets
```
This requests 144 independent reusable templates: 24 chunk templates times 6 variants.
It does not generate a world of 24 fixed positions. Procedural selection/composition
later places these templates at any coordinates.
LocalProvider uses no AI/network/credentials. Supported local biomes: dark_forest,
ash_plain. Outputs:
- pipeline/staging/<request hash>/<chunk>-<variant>.json: untrusted staged output.
- pipeline/requests/<request hash>.json: per-job status, attempts, digest, error.
- registry/<hashed asset ID>.json: validated immutable accepted records.

Run the SAME command again to retry rejected/pending jobs only. Accepted jobs
are skipped; their registered bytes are not rewritten. A new seed is a new
request/content identity. Exit status1 means some jobs were rejected; errors are
in the returned manifest. A corrupt manifest/registry is an explicit error, not
an excuse to silently replace content. Storage is single-writer.

Play using that registry (size must match):
```powershell
python -B -m dimensional_sim.world.cli play --catalog .codex/artifacts/world-assets/registry --size 64x32 --seed 482910
```
A new world with no optional catalog uses bundled assets. A supplied nonempty
catalog must contain every requested biome/size. Saved worlds embed their catalog
and never fetch replacements or require the original registry directory.

## Provider integration
Implement pipeline.GenerationProvider.generate(job)->str|bytes. Return asset-schema1
JSON with the requested job.id/biome/width/height. Providers may fail; run() isolates
failure per job. Never register provider output directly and never import a provider
into runtime, renderer, animation or minimap code.
```python
from pathlib import Path
from dimensional_sim.world.assets import AssetRegistry
from dimensional_sim.world.pipeline import AssetPipeline, GenerationRequest, LocalProvider
p = AssetPipeline(Path("work"), AssetRegistry(Path("catalog")), LocalProvider())
report = p.run(GenerationRequest("dark_forest", 482910, chunks=24, width=64, height=32, variants=6))
```
No real service adapter, credential storage, concurrency or billing exists yet.

## Asset authoring and validation
ChunkAsset contains two immutable grids (dense environment, transparent objects),
per-cell foreground/background colors, authoritative boolean collision, four exits,
player/enemy spawn metadata and tags. Player graphics are separate.
Print-friendly glyphs are single ASCII characters; @ is forbidden in locations.
Width8..128, height6..64; borders block except aligned midpoint exits; all required
exits/spawns must be flood-fill reachable from the single player spawn.
```python
from dimensional_sim.world.assets import AssetRegistry, parse_asset
asset = parse_asset(raw_json_bytes)  # bounded 2MiB, strict fields/schema and colors
registry = AssetRegistry()
digest = registry.register(asset)  # validates again; changed existing IDs fail
catalog = registry.snapshot()      # sorted immutable assets, pin into a new world
```
New biome: author/register templates under a new biome ID; add it to a
DimensionSpec.biomes tuple; test exits, spawn reachability, seed variation and
catalog/save replay. LocalProvider's template factory must be extended if it should
produce the new biome. Current generic nonforest composition uses ash-style details;
a materially different composition rule needs a versioned generator change.

## Animation and combat
animation.Frame defines duration_ms, Cell, anchor=(0,0), active, hitbox offsets and
optional effect_origin. Offsets are authored facing north and rotated with facing.
Single-cell art requires a zero anchor; larger sprites need an explicit later schema.
An attack must be nonlooping and contain at least one active frame with hitboxes.
Default attack:120ms windup,80ms active,160ms recovery. Each target takes damage
at most once per attack, including a large advance that crosses the entire window.
Attack input is rising-edge triggered; release before starting the next attack.

Pass movement_interval_ms, animation_rate_percent or attack_rate_percent into the
Exploration constructor. These timing settings are read-only during an instance:
live changes could otherwise skip active windows or invalidate movement clocks.
Different configured rates do not affect chunk generation. Clips/rates are saved.
Add a clip/frame variant through validated data, keep idle/walk/attack/hit/death
keys, test boundaries/rotation/bulk-vs-split updates and mid-attack save continuation.

## Persistence and extension boundaries
Exploration schema1 embeds world schema1, generator version, frozen catalog/digest,
discovery, actors, clocks, rates, clips and already-hit targets. Resident chunk cache
is not saved. Loading revalidates data and regenerates needed chunks locally.
The CLI bounds exploration input/output at 64MiB; direct from_dict callers must
bound their own raw input. Atomic file replacement preserves an existing file on
write failure. There is no schema migration to make yet; unknown versions fail.

Existing idle schema5 remains separate. Do not grant idle XP/loot from exploration
or decide dimensional-shift resets without a new explicit design contract.
Unknown regions are distinguished from visited ones, but unstable regeneration is
not implemented. A future scheme must preserve visited content explicitly.

## Verification and common failures
```powershell
python -B -m unittest discover -s tests -v
python -m pip wheel . --no-deps --wheel-dir .codex/artifacts/wheels
```
Use isolated builds; this machine's global environment lacks wheel/bdist_wheel.
Wrong pool size/biome fails before runtime generation. Invalid colors, blocked
spawns, nonmidpoint exits, unknown fields/schemas and baked players are rejected.
Changed existing asset IDs fail; choose a new ID instead of overwriting.
A missing resident chunk is an integration error: stream it in simulation, never
repair it inside rendering. Future providers must handle their own timeouts offline.
