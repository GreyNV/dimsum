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
from .catalog import ORIGIN_REGION, REGION_CELL, REGIONS, REGION_ADJACENCY_V2
from .seeds import derive_seed

REGION_VERSION = 2


def region_cell(key):
    return key.x // REGION_CELL, key.y // REGION_CELL


def region_for(world_seed, biome, key, catalog=None, *, version=REGION_VERSION):
    """The RegionDef for a chunk key in `biome` (None if the biome has no regions)."""
    definitions = REGIONS if catalog is None else catalog
    options = sorted((r for r in definitions.values() if r.biome == biome), key=lambda r: r.id)
    if not options:
        return None
    cx, cy = region_cell(key)
    if (cx, cy) == (0, 0) and ORIGIN_REGION in {r.id for r in options}:
        return definitions[ORIGIN_REGION]
    if version not in (1, 2):
        raise ValueError("unsupported region version")
    if version == 1:
        weights = {r.id: r.weight for r in options}
        roll = derive_seed(world_seed, "regions-v1", biome, cx, cy) % sum(weights.values())
    else:
        # Each border has one shared proposal. Neighboring cells therefore respond
        # to some of the same seeded geography without depending on generation order.
        def edge_proposal(x, y, nx, ny):
            if (x, y) == (0, 0) or (nx, ny) == (0, 0):
                return ORIGIN_REGION
            edge = tuple(sorted(((x, y), (nx, ny))))
            value = derive_seed(world_seed, "regions-v2-edge", biome, *edge[0], *edge[1]) \
                % sum(r.weight for r in options)
            for item in options:
                if value < item.weight:
                    return item.id
                value -= item.weight
            raise AssertionError("unreachable")

        neighbors = [edge_proposal(cx, cy, cx + dx, cy + dy)
                     for dx, dy in ((0, -1), (-1, 0), (1, 0), (0, 1))]
        weights = {}
        for region in options:
            score = region.weight
            for neighbor in neighbors:
                score *= REGION_ADJACENCY_V2.get(region.id, {}).get(neighbor, 2)
            weights[region.id] = score
        roll = derive_seed(world_seed, "regions-v2", biome, cx, cy) % sum(weights.values())
    for region in options:
        if roll < weights[region.id]:
            return region
        roll -= weights[region.id]
    raise AssertionError("unreachable")
