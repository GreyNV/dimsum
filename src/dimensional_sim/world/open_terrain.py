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
from functools import lru_cache

from .models import Cell, ChunkAsset, DELTAS, Exit, Spawn, validate_asset
from .seeds import derive_seed


@lru_cache(maxsize=8192)
def _lattice(seed, label, x, y):
    # Bounded value memoization changes cost only, never generation output.
    return derive_seed(seed, label, x, y) % 101


def _noise(seed, x, y, scale, label):
    """Bilinear integer lattice noise, including negative global coordinates."""
    qx, rx = divmod(x, scale)
    qy, ry = divmod(y, scale)
    a = _lattice(seed, label, qx, qy)
    b = _lattice(seed, label, qx + 1, qy)
    c = _lattice(seed, label, qx, qy + 1)
    d = _lattice(seed, label, qx + 1, qy + 1)
    return ((a * (scale - rx) + b * rx) * (scale - ry) +
            (c * (scale - rx) + d * rx) * ry) // (scale * scale)


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


def _trail(seed, along, other, band, size, label, amplitude, scale):
    """Centre of a meandering trail inside its band (global integer noise)."""
    return size // 2 + (_noise(seed, along, band * other, scale, label) - 50) * max(1, amplitude) // 50


def compose_open(source, spec, key, seed, *, region=None, region_grid=None, water=None):
    if region_grid is not None:
        return _compose_v3(source, spec, key, seed, region, region_grid, water)
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


def _compose_v3(source, spec, key, seed, region, grid, water=None):
    """Generator v3: tile-level regions (organic borders) and narrow meandering game trails.

    Trails still cross every chunk north-south and east-west so all four exits connect,
    but outside road country they are one cell wide, wander further and draw as plain
    ground: a gap in the trees, not a painted grid. Each trail cell spans the step from
    the previous row/column, so a wandering trail never breaks into diagonal-only links,
    and both sides of a chunk border compute the same global positions.

    Generator v4 adds `water` (water.WaterField.grid: the chunk plus a one-tile border).
    Water blocks like a tree; a trail over it is a ford, a road over it a bridge, so the
    trail network (and every exit it reaches) stays connected. Banks grow no trees."""
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
            density = _noise(seed, gx, gy, 5, "canopy")
            if r is None:
                row.append(density > 49 and derive_seed(seed, "tree", gx, gy) % 100 < 76)
            else:
                row.append(density > 100 - r.canopy and derive_seed(seed, "tree", gx, gy) % 100 < r.canopy)
        collision.append(row)
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
            elif road[y][x]:
                env_row.append(trail)
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
            if wet(x, y):
                obj_row.append(None)
            elif collision[y][x]:
                obj_row.append(tree if forest and roll % 11 else rock)
            elif not paths[y][x] and not road[y][x] and (roll % 9 == 0 if r is None else roll % 100 < r.brush):
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
