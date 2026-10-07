# Procedural generation

```
WORLD (seed) -> DIMENSION forest -> BIOME (generation.biome_for) -> REGION (regions.RegionField, per tile)
  -> WATER (water.WaterField, per tile, independent of regions)
  -> CHUNK (v4 region-shaped open terrain + rivers, 32x16)
PLAYER ENTERS CHUNK -> CURRENT BUCKET -> RUNTIME SPOT ROLL -> SCREENING -> AVAILABLE INTERACTIONS
```

## Order and seeds
1. Terrain: generator v3 (world schema 4) reads a per-tile region field (`regions.RegionField`): one jittered
   site per 3x3-chunk cell, region chosen by `regions-v2` adjacency weights, each tile assigned to the nearest
   of the 9 surrounding sites after a two-octave domain warp. Borders therefore wander through chunks instead
   of following chunk edges. Canopy, brush and landmarks are read per tile, trails meander (no fixed crossing
   grid; only every third chunk row/column carries one) and are drawn as roads only inside Old Road tiles.
   A chunk's region (spots, buckets, `region_for`) is the region under its centre tile; (0,0) is Old Road
   with the caravan ambush clearing. Generator v2 (rectangular cells, schema 2/3) and v1 worlds keep their
   terrain mid-life and are regrown with v3 at the next rebirth. Blocked-cell share by region is in BALANCING.md.
   Generator v4 (world schema 5) overlays water. Water is not a location: a river is the 50% contour of a
   low-frequency, domain-warped field over global tiles, so it crosses regions and always continues into
   the next chunk. River tiles ('w') block like trees; a trail over water is a ford ('%'), a road a bridge
   ('H'), so trails and exits stay connected. Bank tiles grow no trees. The field is shifted by a
   seed-chosen offset that keeps the anchor chunk dry. Still Glade marks are wildflowers ('*'), no longer
   '~', which read as water. v3 worlds keep their terrain mid-life and gain rivers at the next rebirth.
2. Region: `regions-v2` deterministic cell proposals combined with data-driven compatibility weights for
   shared edges. The anchor cell is Old Road. The save pins region version and definitions (region version 3
   = v2 choices + organic field). Schema 2 worlds retain their `regions-v1` geography.
3. Spots: no encounter is stored in generated geography. On first entry to a chunk during a life, the
   current action bucket rolls opportunities using a seed derived from world seed, life, entry order and
   chunk ID. The resulting plans are saved in expedition schema 9 for replay. Future entries see current
   unlocks, Journal choices and location modifiers. Old saves migrate to the new spot version.
4. Screening (on first entry to the current chunk): admit while the
   action's at-once cap allows; otherwise record `rejected: window full`.
5. Pity: if `PITY_CHUNKS[category]` consecutive newly screened chunks admitted no food (5) / enemy (4) spot,
   the next chunk gets one forced spot of that category (`encounters.forced_spot`, index 10+, saved in
   `forced`), chosen from that region's eligible bucket.
6. Asset-spawned enemies from the terrain recipe are always removed; enemies come from fight spots only.
7. Temporary leads are placed on reachable cells after declarative action outcomes. They have saved expiry,
   provenance and resolution, and never enter the global spot pool.

## Guarantees (tested)
Same seed + life + entry history + player state reproduces saved rolls; bulk/tick/save-reload are stable.
Eligibility and spawn windows prevent locked actions from appearing. Geography remains independent of
future encounter rolls.

## Extending
- New region: add a `RegionDef` (biome, weight, tint, action percents). No code.
- New biome: add assets for it, a DimensionSpec biome entry, `RegionDef`s with that biome and actions whose
  `biomes` include it. `ash_plain` assets exist and are the next candidate.
- New spot action / enemy: an `ActionDef` (fights need `hp`) + sprite.

## Inspecting
`python -m dimensional_sim.world.cli regions --seed S` prints the region layout around the anchor;
`cli inspect --seed S --x X --y Y` explains one chunk (region provenance, parameters, terrain profile, rolls,
every spot action's state).
