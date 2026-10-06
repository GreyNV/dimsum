# Procedural generation

```
WORLD (seed) -> DIMENSION forest -> BIOME (generation.biome_for) -> REGION (repository.region_for, 3x3 chunks)
  -> CHUNK (v2 region-shaped open terrain, 32x16) -> SPOTS (encounters.chunk_spots from the region bucket)
  -> SCREENING (autopilot._screen: windows, pity) -> AVAILABLE INTERACTIONS (spots, fights, self actions)
```

## Order and seeds
1. Terrain: generator v2 uses a pinned `RegionDef` to shape canopy, brush and floor landmarks (measured in
   BALANCING.md: blocked cells range 0% in Still Glade to 62% in Deep Woods). Generator v1 worlds keep their
   byte-identical terrain mid-life and are regenerated from the same seed with v2 at the next rebirth. Origin (0,0) in v2 has a safe caravan ambush clearing,
   debris and scorch marks beneath the browser's wagon wrecks.
2. Region: `derive_seed(world_seed, "regions-v1", biome, cell_x, cell_y)`; the anchor cell is always the Old Road.
   World schema 2 pins region definitions and their digest, so later catalog edits do not change saved worlds.
3. Spots: `derive_seed(chunk_seed, ENCOUNTER_VERSION, life)` -> count, entries, cells; bucket depends on
   pinned region, permanent permissions and Journal modifiers. `encounters-v7` rerolls old uncompleted spots
   through expedition schema 8 migration. Unlocks and Journal state change future rolls, never materialize a spot.
4. Screening (first time a chunk is resident in a life, deterministic resident order): admit while the
   action's at-once cap allows; otherwise record `rejected: window full`.
5. Pity: if `PITY_CHUNKS[category]` consecutive newly screened chunks admitted no food (5) / enemy (4) spot,
   the next chunk gets one forced spot of that category (`encounters.forced_spot`, index 10+, saved in
   `forced`), chosen from that region's eligible bucket.
6. Asset-spawned enemies from the terrain recipe are always removed; enemies come from fight spots only.
7. Temporary leads are placed on reachable cells after declarative action outcomes. They have saved expiry,
   provenance and resolution, and never enter the global spot pool.

## Guarantees (tested)
Same seed + life + permissions + Journal choices -> same spots; bulk/tick/save-reload identical; every seed admits food and a boar
within 18 chunks; starting food/enemy windows never roll 0; locked actions never spawn.

## Extending
- New region: add a `RegionDef` (biome, weight, tint, action percents). No code.
- New biome: add assets for it, a DimensionSpec biome entry, `RegionDef`s with that biome and actions whose
  `biomes` include it. `ash_plain` assets exist and are the next candidate.
- New spot action / enemy: an `ActionDef` (fights need `hp`) + sprite.

## Inspecting
`python -m dimensional_sim.world.cli regions --seed S` prints the region layout around the anchor;
`cli inspect --seed S --x X --y Y` explains one chunk (region provenance, parameters, terrain profile, rolls,
every spot action's state).
