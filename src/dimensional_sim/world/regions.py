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
    if version not in (1, 2, 3):
        raise ValueError("unsupported region version")
    if version == 3:
        version = 2   # v3 keeps v2's per-cell choice; RegionField only reshapes the borders
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


# ----- version 3: organic borders ------------------------------------------------------
# Every region cell (REGION_CELL x REGION_CELL chunks) still picks its region with the v2
# rule above, but instead of filling the whole rectangle it owns a jittered *site*; each
# tile belongs to the nearest site after its coordinates are bent by two octaves of
# integer value noise. Borders become curved and ragged, independent of chunk edges,
# while the anchor stays on the Old Road. Pure integer math, cached, order-independent.
from functools import lru_cache  # noqa: E402

WARP = ((24, 16), (7, 5))       # (lattice scale in tiles, max displacement in tiles)
JITTER_PERCENT = (20, 80)       # site position range inside its cell, per axis


@lru_cache(maxsize=65536)
def _lattice(seed, label, x, y):
    return derive_seed(seed, label, x, y) % 101


def _noise(seed, x, y, scale, label):
    qx, rx = divmod(x, scale)
    qy, ry = divmod(y, scale)
    a, b = _lattice(seed, label, qx, qy), _lattice(seed, label, qx + 1, qy)
    c, d = _lattice(seed, label, qx, qy + 1), _lattice(seed, label, qx + 1, qy + 1)
    return ((a * (scale - rx) + b * rx) * (scale - ry) + (c * (scale - rx) + d * rx) * ry) // (scale * scale)


class RegionField:
    """Tile-level regions of one biome in one world (generator v3)."""

    def __init__(self, world_seed, biome, catalog, chunk_width, chunk_height):
        self.world_seed, self.biome, self.catalog = world_seed, biome, catalog
        self.cw, self.ch = REGION_CELL * chunk_width, REGION_CELL * chunk_height
        self.chunk_width, self.chunk_height = chunk_width, chunk_height
        self.seed = derive_seed(world_seed, "regions-v3", biome)
        self._cells = {}

    def cell(self, cx, cy):
        """(site_x, site_y, RegionDef) of one region cell, in global tiles."""
        hit = self._cells.get((cx, cy))
        if hit is None:
            from .models import ChunkKey
            region = region_for(self.world_seed, self.biome, ChunkKey("forest", cx * REGION_CELL, cy * REGION_CELL),
                                self.catalog, version=2)
            if (cx, cy) == (0, 0):   # the anchor chunk's centre: the Old Road always reaches camp
                sx, sy = self.chunk_width // 2, self.chunk_height // 2
            else:
                lo, hi = JITTER_PERCENT
                roll = derive_seed(self.seed, "site", cx, cy)
                sx = cx * self.cw + self.cw * (lo + roll % (hi - lo)) // 100
                sy = cy * self.ch + self.ch * (lo + (roll >> 16) % (hi - lo)) // 100
            hit = (sx, sy, region)
            if len(self._cells) > 4096:
                self._cells.clear()
            self._cells[(cx, cy)] = hit
        return hit

    def at(self, gx, gy):
        """RegionDef owning global tile (gx, gy)."""
        wx, wy = gx, gy
        for scale, amp in WARP:
            wx += (_noise(self.seed, gx, gy, scale, f"warp-x-{scale}") - 50) * amp // 50
            wy += (_noise(self.seed, gx, gy, scale, f"warp-y-{scale}") - 50) * amp // 50
        cx, cy = wx // self.cw, wy // self.ch
        best = None
        for ny in (cy - 1, cy, cy + 1):
            for nx in (cx - 1, cx, cx + 1):
                sx, sy, region = self.cell(nx, ny)
                # Distances normalised by cell size so a 96x48-tile cell reads as round.
                d = ((wx - sx) * self.ch) ** 2 + ((wy - sy) * self.cw) ** 2
                if best is None or d < best[0]:
                    best = (d, region)
        return best[1]

    def grid(self, key):
        """Per-tile RegionDefs of one chunk (rows of tuples; memoized, pure)."""
        grids = self.__dict__.setdefault("_grids", {})
        hit = grids.get((key.x, key.y))
        if hit is None:
            ox, oy = key.x * self.chunk_width, key.y * self.chunk_height
            hit = tuple(tuple(self.at(ox + x, oy + y) for x in range(self.chunk_width))
                        for y in range(self.chunk_height))
            if len(grids) > 256:
                grids.clear()
            grids[(key.x, key.y)] = hit
        return hit

    def chunk(self, key):
        """The chunk's region for action buckets: its centre tile (anchor chunk: Old Road)."""
        if (key.x, key.y) == (0, 0):
            return self.cell(0, 0)[2]
        return self.at(key.x * self.chunk_width + self.chunk_width // 2,
                       key.y * self.chunk_height + self.chunk_height // 2)
