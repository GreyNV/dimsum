# P3 verification ledger: deterministic world generation

## Delivered contract
Owned files: world/generation.py, world/repository.py,
tests/test_world_generation.py and this ledger. No idle systems or shared contracts
were changed. P1 model baseline: 7 tests passed before implementation.

ChunkGenerator validates a sorted immutable catalog and all requested biome/geometry
pools before accepting a world. Its identity includes world seed, generator version1,
dimension spec and catalog digest. Seeds derive world -> dimension -> signed chunk
coordinates -> terrain/encounter/decoration/loot-reserved. SHA-derived per-cell
choices avoid shared RNG state and access-order dependence. Biome and template
selection use sorted catalogs; source template geometry is preserved.

Composition reserves deterministic breadth-first paths from the player spawn to
every source exit/spawn. Objects may block only unreserved floor; all additional
encounter spawns are selected from reachable, unoccupied floor. Danger0 removes
enemy spawns; positive danger retains authored enemies and adds floor(danger/25)
reachable enemies where space permits. These are prototype content rules, not
idle-combat balance. Loot is a reserved seed domain without rewards.

WorldRepository owns read-only world identity, frozen catalog, LRU resident grids
and persistent generated/visited metadata. get marks generated; visit promotes to
visited; neither eviction nor regeneration erases discovery. peek/status/minimap
do not generate, discover, or change LRU order. stream chooses nearest keys up to
cache_limit, removes nonselected residents, and touches the center last. Radius is
bounded to0..32 and cache_limit to1..4096. Resident grids are bounded; discovery is
intentionally retained.

New worlds without an optional catalog use validated bundled biome/geometry assets.
A nonempty incomplete custom catalog raises ValueError; it is never silently merged.
Schema1 snapshots embed validated catalogs, digest, sorted specs and discovery.
They exclude resident grids, cache recency and generation instrumentation. Pinned
loads reject empty/corrupt catalogs, unsupported versions, inconsistent discovery,
unknown fields and malformed types. Registry changes affect only future worlds.

## Representative use
```python
from dimensional_sim.world.models import ChunkKey
from dimensional_sim.world.repository import WorldRepository

world = WorldRepository(world_seed=482910, cache_limit=9)
key = ChunkKey("forest", 4, -7)
chunk = world.visit(key)
world.stream(key)
map_cells = world.minimap(key)  # reads discovery; never generates
saved = world.to_dict()
restored = WorldRepository.from_dict(saved)
assert restored.get(key) == chunk
```

## Acceptance evidence
| Requirement | Evidence |
|---|---|
| D2 repeated/reverse-order/evicted generation | Full canonical chunk comparison for seed 482910, forest(4,-7); cache_limit1 eviction |
| D2 cross-process hashing | Full default-size chunk canonical JSON matches with PYTHONHASHSEED1 and92341 |
| D2 meaningful seed variation | Seeds1 and2 yield different environment cells |
| D3 valid composed chunks | 50 generated keys across negative/positive coordinates and both biomes pass shared flood-fill/geometry/spawn/player-glyph validator |
| D10 map truth and purity | Generated/visited/unknown map assertions; patched generator raises if called; snapshot and counts unchanged |
| D10 bounded cache | radius2/cache_limit3 across distant centers; center remains resident; repeated stream performs no generation |
| D11 world snapshot portion | Canonical JSON roundtrip, future generation equality, no builtin fallback on pinned load, malformed/future/corrupt saves rejected |
| Frozen catalog identity | Registry update cannot repin existing world; identity properties cannot be reassigned |
| Provider independence | Neither owned runtime module imports pipeline/provider/network; local catalog composition only |

## Tests and regressions
20 tests added; existing tests unchanged. Regressions explicitly protect
peek accidentally updating LRU, missing catalog fallback during pinned load,
catalog-order-dependent selection, boolean numeric inputs, duplicate discovery,
tampered catalog, unknown dimensions, malformed biome entries and world identity
reassignment. Existing model biome parsing TypeError found by self-review was
reported to the shared-contract owner; repository independently rejects malformed
biome entries before construction.

Focused command: python -B -c with src on sys.path and unittest discovery pattern
test_world_generation.py. Result: 20/20 passed in 0.997s.
Broad checkpoint: unittest discover tests,116/116 passed in2.786s.
This checkpoint included existing72 idle tests and available concurrent world tests;
final integration verification remains the lead's responsibility.

Manual verification: inspected generated/save public contracts and canonical output
through the automated reference-chunk and snapshot checks. No visual/manual gameplay
claim; renderer, transitions and combat belong to P4/P5.

## Limits and follow-up
No AI calls, loot rewards, terrain editing, unstable-dimension regeneration, enemy
AI, persistent disk cache, or discovery pruning. Save callers must bound raw JSON
size before decoding; this module receives parsed dictionaries. Catalogs and
discovery metadata grow with content/exploration while resident grids remain bounded.
No benchmark target claimed; tests cover caching behavior without timing thresholds.
When generator decisions change, increment generator version and explicitly decide
migration/legacy generator retention before loading old pinned worlds.

Lead integration review: 21 generation/repository tests pass in final 143-test suite.
Added regression for both legacy/numeric authored spawn-ID collisions; suffixes
are bounded numeric IDs. Reload test includes exact DoD coordinate(4,-7).
