# Character-grid world foundation
## Discovery and scope - 2026-10-04
Python >=3.10, standard library, setuptools and unittest. No spatial engine,
renderer, player or asset pipeline exists. Idle core is an automatic work/XP event
simulation with schema-5 JSON saves. equipment-review is an unfinished React
scaffold, preserved separately. No root AGENTS.md existed.
Baseline: 72 tests pass; isolated 0.5.0 wheel builds. Non-isolated wheel build
failed because the environment lacks bdist_wheel, not because of source changes.
The new explicit request authorizes spatial exploration; it does not replace
automatic lives or decide dimensional-shift reset rules.

## In scope
Opt-in dimensional_sim.world package, no runtime dependencies:
stable hierarchical seeds, dimensions, dark_forest/ash_plain biomes, validated
reusable full-chunk templates and seeded object/encounter composition, frozen
catalogs, bounded resident cache, deterministic regeneration, chunk discovery,
cardinal movement/collision/transitions, independent player animation and timed
combat, pure six-layer character/color renderer, camera, minimap, ANSI/plain
terminal input loop, scripted CLI, local offline generation pipeline with staged
validation and selective retry, separate self-contained exploration saves.

## Out of scope
Paid AI providers, credentials, multiplayer, enemy AI/pathfinding, production
browser/mobile UI, merged idle/spatial balance, loot rewards, weather, terrain
editing, unstable-dimension regeneration, portals and dimension-reset policy.
Effect overlays are supported; elaborate particles are deferred.

## Assumptions, constraints, risks
Printable ASCII glyphs are one terminal cell. Chunks are 8..128 by 6..64, with
aligned midpoint exits on all four sides. Movement is cardinal, locked during
attacks; blocked moves can change facing. Targets are stationary in this slice.
Only biome and danger parameters have gameplay meaning; defer unused climate knobs.
The mock provider supplies test content, not AI. Existing worlds pin their catalog;
registry edits affect new worlds. Generator version, specs and catalog are part of
world identity alongside seed/coordinates. Discovery is chunk-level.
Resident grids are bounded, but discovery metadata/save catalog grow with exploration.
Storage is single-writer; no distributed locking. Plain output covers terminals
without truecolor. Untrusted assets cannot execute code or terminal controls.

## Decisions
ADR-W1: Separate spatial module and schema1; preserve idle core/schema5.
ADR-W2: SHA-256 canonical JSON with version/domain prefix, unsigned 64-bit child
seeds. Never hash(). Typed signed coordinates, independent terrain/encounter/
loot-reserved/decoration labels; no global RNG or generation-order dependence.
ADR-W3: Frozen dataclasses and tuple grids; strict JSON parsing, colors, geometry,
reachable exits/spawns. Reject location glyph '@'. Registry and load paths validate.
ADR-W4: Runtime uses immutable catalog snapshots, never providers. Missing optional
catalog uses bundled assets for a NEW world. Corrupt pinned saves fail explicitly.
ADR-W5: Integer millisecond simulation; render samples clocks without advancing
time, damage or generation. Each attack damages each target at most once.
ADR-W6: Save world discovery/catalog plus player/combat clocks separately from idle
saves. Future unstable dimensions must explicitly preserve visited content.

## Boundaries, ownership and dependency direction
models+seeds <- assets <- generation/repository <- runtime <- renderer/CLI.
animation -> runtime. models+seeds <- pipeline -> assets.
Only CLI imports both pipeline and gameplay. Runtime must never import pipeline,
provider SDKs, network clients or ImageGen. No dependency back to idle core.

models.py: immutable geometry/data, validation/parsing.
seeds.py: canonical JSON and labeled stable seeds.
assets.py: validated registry and bundled content.
pipeline.py: provider Protocol, local provider, staging, per-job failures/retries.
generation.py: pure catalog selection/composition.
repository.py: owns frozen specs/catalog, cache, generated/visited metadata.
animation.py: validated clips/frames, hitboxes and time sampling.
runtime.py: owns player, targets, simulation clock, input/movement/damage events.
renderer.py: pure composition, camera, UI/minimap, ANSI/plain encoding.
cli.py: terminal/scripted adapters and generation commands.

Generation: request -> stage -> validate -> accept/register or reject -> retry failed.
Runtime: input -> simulation -> collision/combat -> animation -> nearby streaming ->
camera/composition -> render. Minimap only reads existing metadata.
Provider exceptions/invalid data are isolated per job. Accepted files use atomic
replacement; changed content under an existing asset ID fails. Invalid saves/inputs
raise ValueError before adoption. No silent resets or corruption of accepted assets.

## Frozen shared contracts
All modules under src/dimensional_sim/world/.
- canonical_json(value)->str; derive_seed(parent:int,*parts:str|int)->int.
- Cell(glyph,fg="#c6c8bb",bg="#17211b"); Grid=tuple[tuple[Cell|None,...],...].
- Exit(direction,x,y); Spawn(id,kind,x,y); ChunkKey(dimension,x,y).
- ChunkAsset(id,biome,width,height,environment,objects,collision,exits,spawns,tags=()).
- Chunk(key,seed,asset_id,asset:ChunkAsset), with composed grids in asset.
- DimensionSpec(id,biomes=("dark_forest",),width=32,height=16,danger=25).
- validate_asset(asset); asset_to_dict/from_dict; chunk_to_dict/from_dict.
- AssetRegistry(root:Path|None=None): register(asset)->digest:str;
  snapshot()->tuple[ChunkAsset,...]; digest property. builtin_assets(width=32,height=16)
  returns both biomes. Registration always validates.
- ChunkGenerator(world_seed:int,dimensions:tuple,assets:tuple):
  generate(key)->Chunk; catalog_digest property.
- WorldRepository(world_seed=1,dimensions=None,assets=None,cache_limit=9):
  get(key)->Chunk (mark generated only); visit(key)->Chunk;
  peek(key)->Chunk|None (resident only, NEVER generate); stream(center,radius=1);
  status(key)->"unknown"|"generated"|"visited"; minimap(center,radius=2)->list[dict]
  with dimension,x,y,status,biome (None when unknown), never generate.
  to_dict()/from_dict(); resident_count/generation_count properties;
  public world_seed, dimensions tuple, catalog tuple. Save sorted discovery and
  embedded catalog, not resident cache. Cache misses regenerate byte-identically.
- Exploration(world:WorldRepository,dimension:str|None=None): at player Spawn in(0,0);
  advance(milliseconds:int,command:InputCommand)->None.
  InputCommand(move:str|None=None,attack:bool=False); north/east/south/west.
  player exposes chunk:ChunkKey,x,y,facing,animation,animation_elapsed_ms.
  targets:dict[str,Target], each id,chunk,x,y,hp.
  current_chunk()->Chunk uses peek (render MUST NOT call get).
  player_cell()->Cell; effect_cells()->dict[(x,y),Cell] in current chunk.
  to_dict()/from_dict() provide exact continuation.
P4 accepted additions: Exploration keyword configuration movement_interval_ms=120,
animation_rate_percent=100, attack_rate_percent=100, attack_damage=1, animations=None.
Attack triggers on a rising edge; release before another attack. Held movement takes
its first step after one interval. Attacks lock movement. Rates, clips and partial
clocks are saved. player_cell/effect_cells/current_chunk are read-only.
P2 accepted API: GenerationRequest(biome,seed,chunks=1,width=32,height=16,variants=1);
GenerationJob(id,biome,seed,width,height,chunk_index,variant_index);
GenerationProvider.generate(job)->str|bytes JSON; LocalProvider;
AssetPipeline(root,registry,provider).run(request)->per-job manifest. Re-running an
identical request skips accepted jobs and retries rejected/pending jobs only.
Animation agent documents its additional APIs near code. Shared interface changes
must update this contract and notify dependent agents before dependent edits.

## Definition of Done
All criteria require evidence; no vague completion claims.
D1: Existing 72 tests pass; isolated wheel builds and zip-import CLI runs.
D2: Seed482910/dimension forest/chunk(4,-7) canonical output matches repeated,
reverse-order, evicted/reloaded and different PYTHONHASHSEED process generation.
At least two world seeds produce different cells.
D3: >=50 generated keys validate; all exits/spawns reachable; no baked player.
D4: Invalid JSON/geometry/provider exception rejected; retry only failed jobs;
accepted bytes unchanged; registry validation cannot be bypassed.
D5: No provider needed/called during movement/attack/animation/render/minimap.
D6: Walls block; aligned exits cross all four edges, including negative coordinates,
without blocked entry. Player remains independent from terrain.
D7: Active metadata window damages in-range targets once per attack; bulk/split
time and different render frequency produce identical state; facing rotates hitboxes;
out-of-range targets remain unharmed.
D8: Idle/walk/attack/hit/death assets validate; first three exercised;
changing animation/attack rates never regenerates terrain.
D9: environment<object<entity<player<effect<UI priority, both colors,
transparency and camera clipping verified; rendering is state-pure.
D10: Unknown/generated/visited map states correct; map reads do not generate/discover;
streaming never exceeds cache_limit.
D11: Exploration save preserves catalog/discovery/player/combat clocks and subsequent
outcomes; corrupt/future saves rejected; existing idle saves untouched.
D12: CLI exposes chunk/variant generation, rejection reports and retry; scripted
playable demo shows movement/combat/map; docs/AGENTS locate all systems.

## Packages and dependency graph
P0 discovery -> P1 models/seeds/contracts -> {P2 assets, P3 world, P4 gameplay};
{P2,P3,P4}->P5 renderer/CLI/integration -> P6 final review.
P2/P3/P4 share frozen interfaces and isolated fixtures, not independently designed APIs.

| ID | Goal/owner | Files | Acceptance/tests | Required documentation |
|---|---|---|---|---|
| P0 | discovery/lead | existing read-only | baseline 72 tests+wheel | this discovery |
| P1 | contracts/lead | models.py,seeds.py,__init__.py; test_world_models.py | D2 vectors, strict parser/reachability | this contract |
| P2 | assets/asset agent | assets.py,pipeline.py; test_world_assets.py | D3,D4 parsing/retry/tamper | module docs, ledger P2 |
| P3 | world/world agent | generation.py,repository.py; test_world_generation.py | D2,D3,D10 cache/save/map/negative coords | module docs, ledger P3 |
| P4 | gameplay/runtime agent | animation.py,runtime.py; test_world_runtime.py | D6,D7,D8,D11 timing/collision/save | module docs, ledger P4 |
| P5 | display/adapters/lead | renderer.py,cli.py; test_world_integration.py; pyproject | D5,D9,D12 input/camera/color/purity | quickstart, AGENTS |
| P6 | final review/lead | focused fixes, review docs | evidence for D1..D12, broad suite+wheel | final ledger/report |

## Verification ledger
Baseline 72/72 (1.185s), isolated wheel 0.5.0 built. Nonisolated build environment
failure: missing bdist_wheel. P1..P6 complete; see world-final-report.md for final acceptance evidence. Agents record tests/regressions/manual
checks/gaps in uniquely owned docs/technical/world-ledger-PN.md; lead consolidates.

## Integration decisions
Single-cell animation anchors must be (0,0); other anchors are rejected, not ignored.
Movement interval and animation/attack rate configuration is fixed per Exploration
instance (constructor/save data). Changing attack timing mid-attack is intentionally
not an API in this foundation. Create/load configured instances to compare rates.
Generated target IDs are bounded stable seed-derived identities; saves validate
required generated targets, positions and HP. Additional custom targets are validated
encounter state, not an anti-cheat boundary. Hit/death clips are supported assets;
only idle/walk/attack are driven by this playable slice.
