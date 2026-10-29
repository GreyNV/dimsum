"""Open terrain with a preserved v1 recipe and region-shaped v2 layout.

Room catalogs never enter this path. The catalog digest pins this recipe's palette
and identity. No float noise, shared RNG, neighbors, access order, or provider calls.
Path centers vary within each chunk band; all four paths intersect. Unreachable
floor pockets are filled before exits/spawns are derived, preserving validation.
The optional region is supplied only by generator v2. With no region, this function
retains the exact v1 decisions for worlds pinned to generator v1.
"""
from collections import deque
from dataclasses import replace

from .models import Cell, ChunkAsset, DELTAS, Exit, Spawn, validate_asset
from .noise import bilinear as _noise, smooth as _smooth_noise
from .seeds import derive_seed


def boundary_exits(collision):
    h, w = len(collision), len(collision[0])
    return tuple(Exit(direction, x, y)
                 for direction, points in (
                     ("north", ((x, 0) for x in range(w))),
                     ("east", ((w - 1, y) for y in range(h))),
                     ("south", ((x, h - 1) for x in range(w))),
                     ("west", ((0, y) for y in range(h))))
                 for x, y in points if not collision[y][x])


def open_assets(width=32, height=16):
    """Validated open recipe catalog. Room assets remain the terminal default."""
    collision = tuple((False,) * width for _ in range(height))
    result = []
    for biome, fg, bg in (("dark_forest", "#6c7950", "#111b16"),
                          ("ash_plain", "#93877a", "#242326")):
        asset = ChunkAsset(f"open-terrain-v1-{biome}-{width}x{height}", biome, width, height,
            tuple(tuple(Cell(".", fg, bg) for _ in range(width)) for _ in range(height)),
            tuple((None,) * width for _ in range(height)), collision, boundary_exits(collision),
            (Spawn("player", "player", width // 2, height // 2),),
            ("open-terrain-v1",), "open")
        validate_asset(asset)
        result.append(asset)
    return tuple(result)


def _flood(collision, origin):
    """Cells reachable from `origin` through open cells (four directions)."""
    h, w = len(collision), len(collision[0])
    seen, queue = {origin}, deque([origin])
    while queue:
        x, y = queue.popleft()
        for dx, dy in DELTAS.values():
            point = (x + dx, y + dy)
            if 0 <= point[0] < w and 0 <= point[1] < h and point not in seen and not collision[point[1]][point[0]]:
                seen.add(point)
                queue.append(point)
    return seen


def _trail(seed, along, other, band, size, label, amplitude, scale):
    """Centre of a meandering trail inside its band (global integer noise)."""
    return size // 2 + (_noise(seed, along, band * other, scale, label) - 50) * max(1, amplitude) // 50


def compose_open(source, spec, key, seed, *, region=None, region_grid=None, water=None, site=None, groves=False,
                 sealed=()):
    if region_grid is not None:
        return _compose_v3(source, spec, key, seed, region, region_grid, water, site, groves, sealed)
    if "open-terrain-v1" not in source.tags:
        raise ValueError("open generation requires a supported versioned recipe")
    w, h = source.width, source.height
    paths, collision = [], []
    for y in range(h):
        path_row, block_row = [], []
        gy = key.y * h + y
        # Vertical path stays inside this column band, but meanders across rows.
        cx = w // 2 + (_noise(seed, gy, key.x * 37, 12, "vertical-path") - 50) * max(1, w // 4) // 50
        for x in range(w):
            gx = key.x * w + x
            cy = h // 2 + (_noise(seed, gx, key.y * 41, 12, "horizontal-path") - 50) * max(1, h // 4) // 50
            path = abs(y - cy) <= 1 or abs(x - cx) <= 1
            density = _noise(seed, gx, gy, 5, "canopy")
            if region is None:
                block = not path and density > 49 and derive_seed(seed, "tree", gx, gy) % 100 < 76
            else:
                block = (not path and density > 100 - region.canopy and
                         derive_seed(seed, "tree", gx, gy) % 100 < region.canopy)
            path_row.append(path)
            block_row.append(block)
        paths.append(path_row)
        collision.append(block_row)
    # Start on the central trail, choose a stable reachable point near the center.
    origin = min(((x, y) for y in range(h) for x in range(w) if paths[y][x]),
                 key=lambda p: (abs(p[0] - w // 2) + abs(p[1] - h // 2), p[1], p[0]))
    ambush = region is not None and source.biome == "dark_forest" and key.x == key.y == 0
    if ambush:
        # A clear place to wake among the wreckage. v1 never enters this branch.
        for y in range(max(0, origin[1] - 1), min(h, origin[1] + 2)):
            for x in range(max(0, origin[0] - 1), min(w, origin[0] + 2)):
                collision[y][x] = False
                paths[y][x] = True
    seen, queue = {origin}, deque([origin])
    while queue:
        x, y = queue.popleft()
        for dx, dy in DELTAS.values():
            point = (x + dx, y + dy)
            if (0 <= point[0] < w and 0 <= point[1] < h and point not in seen
                    and not collision[point[1]][point[0]]):
                seen.add(point)
                queue.append(point)
    env, objects = [], []
    forest = source.biome == "dark_forest"
    floor = source.environment[0][0]
    # Equal immutable cells are shared instead of rebuilt per tile (same values, much faster).
    trail, ground = replace(floor, glyph="="), replace(floor, glyph=".")
    tree, rock, brush = (Cell(g, floor.fg, floor.bg) for g in ("T", "^", ";"))
    for y in range(h):
        env_row, obj_row = [], []
        for x in range(w):
            collision[y][x] = (x, y) not in seen
            roll = derive_seed(seed, "detail", key.x * w + x, key.y * h + y)
            if region is None or paths[y][x]:
                env_row.append(trail if paths[y][x] else ground)
            else:
                # Region identity is visible in the floor as well as its tree cover.
                # Terrain marks are walkable; path, exits and combat cells stay valid.
                if region.landmark == "grove" and roll % 4 == 0:
                    env_row.append(replace(ground, glyph="o"))
                elif region.landmark == "thicket" and roll % 3 == 0:
                    env_row.append(replace(ground, glyph=";"))
                elif region.landmark == "glade" and roll % 3 == 0:
                    env_row.append(replace(ground, glyph="~"))
                else:
                    env_row.append(ground)
            if ambush and not collision[y][x]:
                distance = abs(x - origin[0]) + abs(y - origin[1])
                if 2 <= distance <= 7:
                    remnant = derive_seed(seed, "ambush-ground", x, y) % 7
                    if remnant < 2:
                        env_row[-1] = replace(ground, glyph="x")  # scattered wagon debris
                    elif remnant == 2:
                        env_row[-1] = replace(ground, glyph=":")  # scorched earth
            if collision[y][x]:
                obj_row.append(tree if forest and roll % 11 else rock)
            elif not paths[y][x] and (roll % 9 == 0 if region is None else roll % 100 < region.brush):
                obj_row.append(brush)
            else:
                obj_row.append(None)
        env.append(tuple(env_row))
        objects.append(tuple(obj_row))
    spawns = [Spawn("player", "player", *origin)]
    candidates = sorted((p for p in seen if p != origin and
                         abs(p[0] - origin[0]) + abs(p[1] - origin[1]) >= 3),
                        key=lambda p: (derive_seed(seed, "encounter", key.x, key.y, *p), p))
    for i, point in enumerate(candidates[:spec.danger // 25]):
        spawns.append(Spawn(f"encounter-{i}", "enemy", *point))
    return replace(source, environment=tuple(env), objects=tuple(objects),
                   collision=tuple(map(tuple, collision)), exits=boundary_exits(collision),
                   spawns=tuple(spawns))


def _grove_block(seed, gx, gy, canopy):
    """Generator v6: does a tree stand here? Woods grow the way real ones do - in groves of
    many sizes with open clearings between, not as an even scatter: a broad grove field (scale 9)
    shaped by smaller clumps (scale 4) gives dense cores, a sparse rim of single trees round each
    grove, and now and then a lone tree out in the open. `canopy` (region) sets how much of the
    land is grove. Pure function of world seed and global cell, so chunk borders agree."""
    # three octaves, the middle one shifted so lattice lines never coincide
    d = (_smooth_noise(seed, gx, gy, 13, "grove") * 55 + _smooth_noise(seed, gx + 3, gy + 2, 6, "clump") * 30
         + _smooth_noise(seed, gx, gy, 3, "twig") * 15) // 100
    t = 74 - canopy * 55 // 100   # deep woods still keep glades; open country still grows groves
    roll = derive_seed(seed, "grove-tree", gx, gy) % 100
    if d > t + 10:
        return roll < 93          # grove core: nearly solid, a gap here and there
    if d > t + 3:
        return roll < 48          # inner rim
    if d > t - 4:
        return roll < 16          # outer rim: single trees thinning into the open
    return roll < 2               # a lone tree in a clearing


# The edge of a land (generator v7, edges.py): a sealed side grows a ragged band of thicket
# EDGE_DEPTH tiles deep; a road crossing it is blocked by fallen trees, a bridge is broken.
EDGE_DEPTH = (2, 4)
DEADFALL, BROKEN_BRIDGE = "K", "Y"


def _edge_band(seed, key, w, h, sealed):
    """{(x, y)} of the cells a land's edge closes in this chunk (ragged: depth varies per tile)."""
    band = set()
    low, high = EDGE_DEPTH
    for side in sealed:
        along = w if side in ("north", "south") else h
        for i in range(along):
            g = (key.x * w + i) if side in ("north", "south") else (key.y * h + i)
            depth = low + _smooth_noise(seed, g, 0, 3, f"edge-{side}") * (high - low + 1) // 101
            for d in range(depth):
                band.add({"north": (i, d), "south": (i, h - 1 - d),
                          "west": (d, i), "east": (w - 1 - d, i)}[side])
    return band


def _compose_v3(source, spec, key, seed, region, grid, water=None, site=None, groves=False, sealed=()):
    """Generator v3: tile-level regions (organic borders) and narrow meandering game trails.

    Trails still cross every chunk north-south and east-west so all four exits connect,
    but outside road country they are one cell wide, wander further and draw as plain
    ground: a gap in the trees, not a painted grid. Each trail cell spans the step from
    the previous row/column, so a wandering trail never breaks into diagonal-only links,
    and both sides of a chunk border compute the same global positions.

    Generator v4 adds `water` (water.WaterField.grid: the chunk plus a one-tile border).
    Water blocks like a tree; a trail over it is a ford, a road over it a bridge, so the
    trail network (and every exit it reaches) stays connected. Banks grow no trees.

    Generator v5 adds `site` (sites.SitePlacement): a treeless clearing with the site's
    structures, joined to the vertical trail along its centre row (a ford over water)."""
    w, h = source.width, source.height
    ox, oy = key.x * w, key.y * h
    vertical = lambda gy: _trail(seed, gy, key.x, 37, w, "trail-v3-vertical", w // 2 - 2, 7)
    horizontal = lambda gx: _trail(seed, gx, key.y, 41, h, "trail-v3-horizontal", h // 2 - 1, 7)
    # Only some trail bands are roads (and always the ones through the anchor), so road
    # country reads as a few long roads, not a grid. Pure function of world seed + band.
    road_v = key.x == 0 or derive_seed(seed, "road-v3-column", key.x) % 3 == 0
    road_h = key.y == 0 or derive_seed(seed, "road-v3-row", key.y) % 3 == 0
    paths = [[False] * w for _ in range(h)]
    roadway = [[False] * w for _ in range(h)]
    for y in range(h):
        a, b = vertical(oy + y - 1), vertical(oy + y)
        for x in range(max(0, min(a, b)), min(w, max(a, b) + 1)):
            paths[y][x] = True
            roadway[y][x] = roadway[y][x] or road_v
    for x in range(w):
        a, b = horizontal(ox + x - 1), horizontal(ox + x)
        for y in range(max(0, min(a, b)), min(h, max(a, b) + 1)):
            paths[y][x] = True
            roadway[y][x] = roadway[y][x] or road_h
    # Roads are wide: widen trail cells that lie in road country.
    road = [[False] * w for _ in range(h)]
    for y in range(h):
        for x in range(w):
            if roadway[y][x] and grid[y][x] is not None and grid[y][x].landmark == "road":
                for dy in (-1, 0, 1):
                    for dx in (-1, 0, 1):
                        if 0 <= x + dx < w and 0 <= y + dy < h:
                            road[y + dy][x + dx] = True
    wet = (lambda x, y: water[y + 1][x + 1]) if water is not None else (lambda x, y: False)
    bank = (lambda x, y: any(water[y + 1 + dy][x + 1 + dx] for dy in (-1, 0, 1) for dx in (-1, 0, 1))) \
        if water is not None else (lambda x, y: False)
    collision = []
    for y in range(h):
        row = []
        for x in range(w):
            gx, gy = ox + x, oy + y
            if paths[y][x] or road[y][x]:
                row.append(False)
                continue
            if wet(x, y):
                row.append(True)
                continue
            if bank(x, y):
                row.append(False)
                continue
            r = grid[y][x]
            if groves:
                row.append(_grove_block(seed, gx, gy, 51 if r is None else r.canopy))
                continue
            density = _noise(seed, gx, gy, 5, "canopy")
            if r is None:
                row.append(density > 49 and derive_seed(seed, "tree", gx, gy) % 100 < 76)
            else:
                row.append(density > 100 - r.canopy and derive_seed(seed, "tree", gx, gy) % 100 < r.canopy)
        collision.append(row)
    site_objects, site_ground = {}, {}
    if site is not None:
        from .sites import layout
        site_objects, site_ground = layout(site, seed)
        for y in range(h):
            for x in range(w):
                if site.contains(x, y) and not wet(x, y):
                    collision[y][x] = False
        trail_x = min(w - 1, max(0, vertical(oy + site.y)))
        for x in range(min(site.x, trail_x), max(site.x, trail_x) + 1):
            paths[site.y][x] = True
            collision[site.y][x] = False
        # A structure may cover a trail, but never cut a boundary (an exit) off from the
        # trails: each piece is kept only if every edge cell reachable before stays reachable.
        start = min(((x, y) for y in range(h) for x in range(w) if paths[y][x]),
                    key=lambda p: (abs(p[0] - w // 2) + abs(p[1] - h // 2), p[1], p[0]))
        edge = lambda cells: {(x, y) for x, y in cells if x in (0, w - 1) or y in (0, h - 1)}
        exits = edge(_flood(collision, start))
        kept = {}
        for (x, y) in sorted(site_objects, key=lambda p: (p[1], p[0])):
            if wet(x, y) or (x, y) == start:
                continue
            collision[y][x] = True
            if edge(_flood(collision, start)) == exits:
                kept[(x, y)] = site_objects[(x, y)]
                paths[y][x] = road[y][x] = False
            else:
                collision[y][x] = False
        site_objects = kept
    # v7: the edge of the land closes sealed sides (thicket; fallen trees on a road; a broken bridge).
    # A trail inside the band stays open unless it is within a tile of the closed boundary, so a
    # trail running along the edge still links the chunk's other sides; the one heading out ends
    # in thicket, fallen trees or a broken bridge right at the edge.
    barrier = {}
    near = lambda x, y: (("north" in sealed and y <= 1) or ("south" in sealed and y >= h - 2)
                         or ("west" in sealed and x <= 1) or ("east" in sealed and x >= w - 2))
    for (x, y) in sorted(_edge_band(seed, key, w, h, sealed)) if sealed else ():
        if (paths[y][x] or road[y][x]) and not near(x, y):
            continue
        if road[y][x]:
            barrier[(x, y)] = BROKEN_BRIDGE if wet(x, y) else DEADFALL
        collision[y][x] = True
        paths[y][x] = road[y][x] = False
    lanes = [(x, y) for y in range(h) for x in range(w) if paths[y][x]]
    origin = min(lanes, key=lambda p: (abs(p[0] - w // 2) + abs(p[1] - h // 2), p[1], p[0]))
    ambush = region is not None and source.biome == "dark_forest" and key.x == key.y == 0
    if ambush:
        for y in range(max(0, origin[1] - 1), min(h, origin[1] + 2)):
            for x in range(max(0, origin[0] - 1), min(w, origin[0] + 2)):
                collision[y][x] = False
                road[y][x] = True
    seen, queue = {origin}, deque([origin])
    while queue:
        x, y = queue.popleft()
        for dx, dy in DELTAS.values():
            point = (x + dx, y + dy)
            if (0 <= point[0] < w and 0 <= point[1] < h and point not in seen
                    and not collision[point[1]][point[0]]):
                seen.add(point)
                queue.append(point)
    env, objects = [], []
    forest = source.biome == "dark_forest"
    floor = source.environment[0][0]
    trail, ground = replace(floor, glyph="="), replace(floor, glyph=".")
    # v4: glade marks are wildflowers ('*'); the old '~' damp marks read as water.
    marks = {"grove": (4, replace(ground, glyph="o")), "thicket": (3, replace(ground, glyph=";")),
             "glade": (3, replace(ground, glyph="*" if water is not None else "~"))}
    river, ford, bridge = (replace(floor, glyph=g) for g in ("w", "%", "H"))
    tree, rock, brush = (Cell(g, floor.fg, floor.bg) for g in ("T", "^", ";"))
    for y in range(h):
        env_row, obj_row = [], []
        for x in range(w):
            collision[y][x] = (x, y) not in seen
            roll = derive_seed(seed, "detail", ox + x, oy + y)
            r = grid[y][x]
            if wet(x, y):
                env_row.append(bridge if road[y][x] else ford if paths[y][x] else river)
            elif (x, y) in barrier:
                env_row.append(trail)   # the road runs on under the fallen trees
            elif road[y][x]:
                env_row.append(trail)
            elif (x, y) in site_ground and not paths[y][x]:
                env_row.append(replace(ground, glyph=site_ground[(x, y)]))
            elif r is not None and r.landmark in marks and not paths[y][x] and roll % marks[r.landmark][0] == 0:
                env_row.append(marks[r.landmark][1])
            else:
                env_row.append(ground)
            if ambush and not collision[y][x]:
                distance = abs(x - origin[0]) + abs(y - origin[1])
                if 2 <= distance <= 7:
                    remnant = derive_seed(seed, "ambush-ground", x, y) % 7
                    if remnant < 2:
                        env_row[-1] = replace(ground, glyph="x")
                    elif remnant == 2:
                        env_row[-1] = replace(ground, glyph=":")
            if (x, y) in barrier:
                obj_row.append(Cell(barrier[(x, y)], floor.fg, floor.bg))
            elif wet(x, y):
                obj_row.append(None)
            elif (x, y) in site_objects and collision[y][x]:
                obj_row.append(Cell(site_objects[(x, y)], floor.fg, floor.bg))
            elif collision[y][x]:
                if groves:   # v6: boulders lie in piles, not one in eleven trees at random
                    pile = _smooth_noise(seed, ox + x, oy + y, 7, "boulders")
                    obj_row.append(rock if not forest or (pile > 74 and roll % 3) or roll % 41 == 0 else tree)
                else:
                    obj_row.append(tree if forest and roll % 11 else rock)
            elif site is not None and site.contains(x, y):
                obj_row.append(None)   # the clearing grows no brush
            elif not paths[y][x] and not road[y][x] and (
                    (_smooth_noise(seed, ox + x, oy + y, 5, "brush") > 62 and roll % 100 < 3 * (10 if r is None else r.brush))
                    if groves else (roll % 9 == 0 if r is None else roll % 100 < r.brush)):
                obj_row.append(brush)
            else:
                obj_row.append(None)
        env.append(tuple(env_row))
        objects.append(tuple(obj_row))
    spawns = [Spawn("player", "player", *origin)]
    candidates = sorted((p for p in seen if p != origin and
                         abs(p[0] - origin[0]) + abs(p[1] - origin[1]) >= 3),
                        key=lambda p: (derive_seed(seed, "encounter", key.x, key.y, *p), p))
    for i, point in enumerate(candidates[:spec.danger // 25]):
        spawns.append(Spawn(f"encounter-{i}", "enemy", *point))
    return replace(source, environment=tuple(env), objects=tuple(objects),
                   collision=tuple(map(tuple, collision)), exits=boundary_exits(collision),
                   spawns=tuple(spawns))
