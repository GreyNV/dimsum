# Procedural generation

```
WORLD (seed) -> DIMENSION forest -> BIOME (generation.biome_for) -> REGION (repository.region_for, 3x3 chunks)
  -> CHUNK (v2 region-shaped open terrain, 32x16)
PLAYER ENTERS CHUNK -> CURRENT BUCKET -> RUNTIME SPOT ROLL -> SCREENING -> AVAILABLE INTERACTIONS
```

## Order and seeds
1. Terrain: generator v2 uses a pinned `RegionDef` to shape canopy, brush and floor landmarks (measured in
   BALANCING.md: blocked cells range 0% in Still Glade to 62% in Deep Woods). Generator v1 worlds keep their
   byte-identical terrain mid-life and are regenerated from the same seed with v2 at the next rebirth. Origin (0,0) in v2 has a safe caravan ambush clearing,
   debris and scorch marks beneath the browser's wagon wrecks.
2. Region: world schema 3 uses `regions-v2`: deterministic cell proposals combined with data-driven
   compatibility weights for shared edges. The anchor cell is Old Road. The save pins region version and
   definitions. Schema 2 worlds retain their `regions-v1` geography.
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
