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


def compose_open(source, spec, key, seed, *, region=None):
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
