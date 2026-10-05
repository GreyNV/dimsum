# Procedural generation

```
WORLD (seed) -> DIMENSION forest -> BIOME (generation.biome_for) -> REGION (regions.region_for, 3x3 chunks)
  -> CHUNK (open-terrain-v1 recipe, 32x16) -> SPOTS (encounters.chunk_spots from the region bucket)
  -> SCREENING (autopilot._screen: windows, pity) -> AVAILABLE INTERACTIONS (spots, fights, self actions)
```

## Order and seeds
1. Terrain: `derive_seed(world_seed, ...)` per chunk; unchanged.
2. Region: `derive_seed(world_seed, "regions-v1", biome, cell_x, cell_y)`; the anchor cell is always the Old Road.
3. Spots: `derive_seed(chunk_seed, ENCOUNTER_VERSION, life)` -> count, entries, cells; bucket depends on
   region and the unlocked set (both fixed for a life).
4. Screening (first time a chunk is resident in a life, deterministic resident order): admit while the
   action's at-once cap allows; otherwise record `rejected: window full`.
5. Pity: if `PITY_CHUNKS[category]` consecutive newly screened chunks admitted no food (5) / enemy (4) spot,
   the next chunk gets one forced spot of that category (`encounters.forced_spot`, index 10+, saved in
   `forced`), chosen from that region's eligible bucket.
6. Asset-spawned enemies from the terrain recipe are always removed; enemies come from fight spots only.

## Guarantees (tested)
Same seed + life + unlocks -> same spots; bulk/tick/save-reload identical; every seed admits food and a boar
within 18 chunks; starting food/enemy windows never roll 0; locked actions never spawn.

## Extending
- New region: add a `RegionDef` (biome, weight, tint, action percents). No code.
- New biome: add assets for it, a DimensionSpec biome entry, `RegionDef`s with that biome and actions whose
  `biomes` include it. `ash_plain` assets exist and are the next candidate.
- New spot action / enemy: an `ActionDef` (fights need `hp`) + sprite.
