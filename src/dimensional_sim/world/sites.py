"""Landmark sites (generator v5): rare places generated into the terrain.

WHAT: which chunk holds a site (catalog.SITES), where its clearing sits and what
structures stand in it. Terrain (open_terrain) carves the clearing and places the
structures; encounters.chunk_spots rolls the site's own encounter bucket inside it.
INVARIANTS: a pure function of (world seed, chunk key, the chunk's region, the pinned
site catalog and the chunk size): no RNG, hash(), clock or generation order. The world
is divided into SITE_CELL x SITE_CELL blocks; one chunk per block is the natural-roll
candidate and rolls once against the per-mille weights of the sites allowed in its
region. Generator v8 fills missing landmark kinds in other empty blocks of a bounded
land, still at most one site per block.
EXTEND: add a SiteDef to catalog.SITES and site actions (placement "site") for it; a new
structure style needs a layout here, its glyphs in STRUCTURE_GLYPHS and client tile art
(art.js STRUCTURE_ART) for each glyph.
Each life a site also has a condition (catalog.SITE_CONDITIONS, `condition_for`).
TESTS: tests/test_world_sites.py, tests/test_world_site_conditions.py.
"""
from dataclasses import dataclass

from .catalog import SITE_CELL, SITE_CONDITIONS, SITES
from .seeds import derive_seed

SITE_VERSION = "sites-v1"
TENT, MASONRY, SCORCH, RUBBLE = "A", "M", ":", "x"   # object glyphs block; ground glyphs do not
LOGS, STUMP, HUT, RACK, PILLAR, ALTAR, MOUND, STONE = "L", "S", "U", "R", "P", "Q", "B", "I"
FLAGSTONE = "F"
STRUCTURE_GLYPHS = {"camp": (TENT,), "tower": (MASONRY,), "lumber": (LOGS, STUMP), "lodge": (HUT, RACK),
                    "shrine": (PILLAR, ALTAR), "barrow": (MOUND, STONE)}


@dataclass(frozen=True)
class SitePlacement:
    """One site in one chunk: the clearing is the ellipse around (x, y) with half-axes rx, ry."""
    site: object
    key: object
    x: int
    y: int
    rx: int
    ry: int

    @property
    def id(self):
        return self.site.id

    def contains(self, x, y):
        dx, dy = x - self.x, y - self.y
        return dx * dx * self.ry * self.ry + dy * dy * self.rx * self.rx <= self.rx * self.rx * self.ry * self.ry


def site_at(world_seed, key, region_id, width, height, catalog=None):
    """The SitePlacement in chunk `key` (its region id given), or None."""
    definitions = SITES if catalog is None else catalog
    bx, by = key.x // SITE_CELL, key.y // SITE_CELL
    pick = derive_seed(world_seed, SITE_VERSION, "cell", key.dimension, bx, by) % (SITE_CELL * SITE_CELL)
    if (key.x - bx * SITE_CELL) + (key.y - by * SITE_CELL) * SITE_CELL != pick:
        return None
    ring = max(abs(key.x), abs(key.y))
    roll = derive_seed(world_seed, SITE_VERSION, "roll", key.dimension, key.x, key.y) % 1000
    for site in sorted(definitions.values(), key=lambda s: s.id):
        if ring < site.min_ring:
            continue
        weight = site.weights.get(region_id, 0)
        if roll < weight:
            return place_site(world_seed, key, site, width, height)
        roll -= weight
    return None


def place_site(world_seed, key, site, width, height):
    """Place a chosen site using the same clearing coordinates as the original site roll."""
    rx, ry = site.size
    mx, my = rx + 2, ry + 2
    if width <= 2 * mx or height <= 2 * my:
        return None
    x = mx + derive_seed(world_seed, SITE_VERSION, "x", key.dimension, key.x, key.y) % (width - 2 * mx)
    y = my + derive_seed(world_seed, SITE_VERSION, "y", key.dimension, key.x, key.y) % (height - 2 * my)
    return SitePlacement(site, key, x, y, rx, ry)


def bounded_site_plan(world_seed, dimension, land, sites, region_for, biome_for, width, height):
    """Keep natural rolls, then fill missing site kinds inside a finite land.

    Every site whose biome belongs to this dimension gets at least one reachable
    chunk. Prefer fitting regions and unused site cells; a rare world without one
    may use another region or replace a duplicate site. The plan is pure and
    independent of visit/generation order.
    """
    from .edges import chunk_open
    from .models import ChunkKey

    keys = [ChunkKey(dimension.id, x, y)
            for y in range(-land.lobe_ring, land.lobe_ring + 1)
            for x in range(-land.lobe_ring, land.lobe_ring + 1)
            if chunk_open(world_seed, ChunkKey(dimension.id, x, y), {dimension.id: land})]
    regions = {key: region_for(key) for key in keys}
    all_fits = {site.id: [key for key in keys
                          if biome_for(key) == site.biome and max(abs(key.x), abs(key.y)) >= site.min_ring
                          and regions[key] is not None
                          and place_site(world_seed, key, site, width, height) is not None]
                for site in sites.values() if site.biome in dimension.biomes}
    fits = {ident: [key for key in candidates if regions[key].id in sites[ident].weights]
            for ident, candidates in all_fits.items()}
    plan = {}
    for key in keys:
        region = regions[key]
        if region is None:
            continue
        biome_sites = {name: site for name, site in sites.items() if site.biome == biome_for(key)}
        placement = site_at(world_seed, key, region.id, width, height, biome_sites)
        if placement is not None:
            plan[key] = placement
    present = {placement.site.id for placement in plan.values()}
    counts = {ident: sum(placement.site.id == ident for placement in plan.values()) for ident in all_fits}
    used_cells = {(key.x // SITE_CELL, key.y // SITE_CELL) for key in plan}
    for ident in sorted(fits, key=lambda name: (len(fits[name]), name)):
        if ident in present:
            continue
        def free(candidates):
            return [key for key in candidates
                    if (key.x // SITE_CELL, key.y // SITE_CELL) not in used_cells]

        def replaceable(candidates):
            return [key for key in candidates if key in plan and counts[plan[key].site.id] > 1]

        # A rare layout can lack a preferred region, or fill every fitting site cell.
        # Keep content reachable: use a free cell elsewhere in the same biome, then
        # replace a duplicate natural site only if no free cell can hold this kind.
        available = (free(fits[ident]) or free(all_fits[ident])
                     or replaceable(fits[ident]) or replaceable(all_fits[ident]))
        if not available:
            raise ValueError(f"no reachable place for landmark {ident} in {dimension.id}")
        key = min(available, key=lambda k: derive_seed(world_seed, "site-quota-v1", dimension.id, ident, k.x, k.y))
        if key in plan:
            counts[plan[key].site.id] -= 1
        plan[key] = place_site(world_seed, key, sites[ident], width, height)
        counts[ident] += 1
        present.add(ident)
        used_cells.add((key.x // SITE_CELL, key.y // SITE_CELL))
    return plan


def layout(placement, seed):
    """({(x, y): object glyph}, {(x, y): ground glyph}) for a site's structures.

    In a clearing 3 tiles tall the rows two off the centre keep only their middle tile
    (the `inner` rule below), so the main piece of a site stands there.

    Structures never stand on the clearing's centre row, which links it to the trails, and
    only where all four neighbours are inside the clearing: whatever a structure covers
    (a trail included), the open clearing around it always leads past."""
    p, cx, cy = placement, placement.x, placement.y
    objects, ground = {}, {}
    if p.site.structure == "camp":
        for x, y in ((cx - 4, cy - 1), (cx - 3, cy - 1), (cx + 3, cy + 1), (cx + 4, cy + 1),
                     (cx, cy - 2), (cx + 1, cy - 2)):
            objects[(x, y)] = TENT
        for dx in (-1, 0, 1):
            ground[(cx + dx, cy)] = SCORCH
    elif p.site.structure == "tower":
        for x, y in ((cx - 1, cy - 2), (cx, cy - 2), (cx - 1, cy - 1), (cx, cy - 1),   # the stump of the tower
                     (cx - 5, cy - 1), (cx - 4, cy - 2), (cx + 4, cy + 1), (cx + 5, cy + 1), (cx + 5, cy + 2)):
            objects[(x, y)] = MASONRY
        for y in range(cy - p.ry, cy + p.ry + 1):
            for x in range(cx - p.rx, cx + p.rx + 1):
                if p.contains(x, y) and (x, y) not in objects and derive_seed(seed, "site-rubble", x, y) % 4 == 0:
                    ground[(x, y)] = RUBBLE
    elif p.site.structure == "lumber":
        for dx, dy in ((-4, -1), (-3, -1), (-2, -1), (2, 1), (3, 1)):
            objects[(cx + dx, cy + dy)] = LOGS
        for dx, dy in ((0, -2), (4, -1), (-3, 1), (0, 2), (-4, 1)):
            objects[(cx + dx, cy + dy)] = STUMP
        _scatter(p, seed, ground, RUBBLE, "site-chips", 5)
    elif p.site.structure == "lodge":
        objects[(cx, cy - 2)] = HUT   # one blocking tile; its art overhangs the neighbours
        for dx, dy in ((3, -1), (-3, -1), (-3, 1), (3, 1)):
            objects[(cx + dx, cy + dy)] = RACK
        for dx in (0, 1):
            ground[(cx + dx, cy + 1)] = SCORCH
    elif p.site.structure == "shrine":
        objects[(cx, cy - 2)] = ALTAR
        for dx, dy in ((-3, -1), (3, -1), (-3, 1), (3, 1), (0, 2)):
            objects[(cx + dx, cy + dy)] = PILLAR
        for y in range(cy - 2, cy + 3):
            for x in range(cx - 3, cx + 4):
                ground[(x, y)] = FLAGSTONE
    elif p.site.structure == "barrow":
        objects[(cx, cy - 2)] = MOUND   # one blocking tile; its art overhangs the neighbours
        for dx, dy in ((-3, -1), (3, -1), (-4, 1), (4, 1), (0, 2)):
            objects[(cx + dx, cy + dy)] = STONE
        _scatter(p, seed, ground, RUBBLE, "site-bones", 6)
    inner = lambda x, y: all(p.contains(x + dx, y + dy) for dx, dy in ((0, 0), (1, 0), (-1, 0), (0, 1), (0, -1)))
    return ({k: v for k, v in objects.items() if inner(*k) and k[1] != cy},
            {k: v for k, v in ground.items() if p.contains(*k)})


def _scatter(p, seed, ground, glyph, salt, one_in):
    """Sparse ground marks across the clearing (deterministic per cell)."""
    for y in range(p.y - p.ry, p.y + p.ry + 1):
        for x in range(p.x - p.rx, p.x + p.rx + 1):
            if p.contains(x, y) and derive_seed(seed, salt, x, y) % one_in == 0:
                ground[(x, y)] = glyph


def condition_for(world_seed, placement, life, catalog=None):
    """This life's SiteConditionDef for a placed site: a weighted pick among the conditions
    that fit its structure, fixed by world seed, life and the site's chunk (pure)."""
    conditions = SITE_CONDITIONS if catalog is None else catalog
    fits = [c for c in sorted(conditions.values(), key=lambda c: c.id)
            if c.structures is None or placement.site.structure in c.structures]
    key = placement.key
    roll = derive_seed(world_seed, "site-condition-v1", life, key.dimension, key.x, key.y, placement.id) \
        % sum(c.weight for c in fits)
    for condition in fits:
        if roll < condition.weight:
            return condition
        roll -= condition.weight
    raise AssertionError("unreachable")
