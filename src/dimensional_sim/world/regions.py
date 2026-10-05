"""Region layer: WORLD -> BIOME -> REGION -> CHUNK.

WHAT: assigns every chunk a named region of its biome (catalog.REGIONS). Regions
span REGION_CELL x REGION_CELL chunks and change which spot actions are likely.
WHY: one biome with one terrain recipe gave no reason to prefer one direction;
regions add variation as data, without touching terrain generation.
INVARIANTS: pure function of (world seed, biome, chunk coordinates); the region
cell holding the anchor (0, 0) is always ORIGIN_REGION; no RNG, hash() or clock.
EXTEND: add a RegionDef to catalog.REGIONS (weight, tint, action multipliers).
TESTS: tests/test_world_catalog.py (determinism, origin, coverage).
"""
from .catalog import ORIGIN_REGION, REGION_CELL, REGIONS
from .seeds import derive_seed

REGION_VERSION = "regions-v1"


def region_cell(key):
    return key.x // REGION_CELL, key.y // REGION_CELL


def region_for(world_seed, biome, key):
    """The RegionDef for a chunk key in `biome` (None if the biome has no regions)."""
    options = sorted((r for r in REGIONS.values() if r.biome == biome), key=lambda r: r.id)
    if not options:
        return None
    cx, cy = region_cell(key)
    if (cx, cy) == (0, 0) and ORIGIN_REGION in {r.id for r in options}:
        return REGIONS[ORIGIN_REGION]
    roll = derive_seed(world_seed, REGION_VERSION, biome, cx, cy) % sum(r.weight for r in options)
    for region in options:
        if roll < region.weight:
            return region
        roll -= region.weight
    raise AssertionError("unreachable")
