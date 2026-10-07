"""Water layer (generator v4): rivers are an overlay on the land, not a region.

WORLD (seed) -> WATER FIELD (global tiles) -> CHUNK: water blocks like a tree, trails ford it.

A river is the level-50% contour of a low-frequency, domain-warped integer noise
field, so it never starts or stops at a chunk edge: a river leaving one chunk always
continues into the next, through every region it meets. Width is the distance to the
contour, measured with the field's local gradient, so banks stay roughly parallel.
The whole field is translated by a seed-chosen offset that keeps the anchor chunk
dry (the caravan wrecks never sit in a river). Pure integer math, no shared state:
partition- and access-order independent like the rest of generation.
"""
from functools import lru_cache
from math import isqrt

from .seeds import derive_seed

LEVEL = 50_000            # contour of the 0..100_000 field that becomes a river
SCALE = 112               # tiles per lattice cell of the main field (~3.5 x 7 chunks)
DETAIL = 37               # second octave: bends and meanders
WARP = ((29, 11), (11, 2))  # (scale, amplitude in tiles) of the domain warp
HALF_WIDTH = (11, 23)     # tenths of a tile either side of the contour: ~2-5 tiles wide
DRY_MARGIN = 6            # tiles around the anchor chunk kept free of water


@lru_cache(maxsize=16384)
def _lattice(seed, label, x, y):
    return derive_seed(seed, label, x, y) % 101


def _fine(seed, x, y, scale, label):
    """Bilinear lattice noise in 0..100_000 (fixed point, keeps a usable gradient)."""
    qx, rx = divmod(x, scale)
    qy, ry = divmod(y, scale)
    a = _lattice(seed, label, qx, qy)
    b = _lattice(seed, label, qx + 1, qy)
    c = _lattice(seed, label, qx, qy + 1)
    d = _lattice(seed, label, qx + 1, qy + 1)
    return ((a * (scale - rx) + b * rx) * (scale - ry) +
            (c * (scale - rx) + d * rx) * ry) * 1000 // (scale * scale)


class WaterField:
    """Deterministic river mask in global tile coordinates for one world."""

    def __init__(self, world_seed, chunk_width, chunk_height):
        self.seed = derive_seed(world_seed, "water-v1")
        self.width, self.height = chunk_width, chunk_height
        self._grids = {}
        self.offset = self._dry_offset()

    def _value(self, x, y):
        s = self.seed
        for scale, amplitude in WARP:
            x, y = (x + (_fine(s, x, y, scale, f"warp-x-{scale}") - 50_000) * amplitude // 50_000,
                    y + (_fine(s, x, y, scale, f"warp-y-{scale}") - 50_000) * amplitude // 50_000)
        return (_fine(s, x, y, SCALE, "river") * 6 + _fine(s, x, y, DETAIL, "bend")) // 7

    def _raw(self, x0, y0, w, h):
        values = [[self._value(x0 + x - 1, y0 + y - 1) for x in range(w + 2)] for y in range(h + 2)]
        rows = []
        for y in range(1, h + 1):
            row = []
            for x in range(1, w + 1):
                gx = values[y][x + 1] - values[y][x - 1]
                gy = values[y + 1][x] - values[y - 1][x]
                gradient = isqrt(gx * gx + gy * gy)
                half = HALF_WIDTH[0] + (_fine(self.seed, x0 + x - 1, y0 + y - 1, 29, "width")
                                        * (HALF_WIDTH[1] - HALF_WIDTH[0]) // 100_000)
                # distance to the contour (tiles) = |v - L| / (gradient / 2) <= half / 10
                row.append(gradient > 0 and abs(values[y][x] - LEVEL) * 20 <= half * gradient)
            rows.append(row)
        return rows

    def _mask(self, x0, y0, w, h):
        """Water mask of a w x h tile window at global (x0, y0), before the offset.
        A water tile with no 4-neighbour water is a speck where the field grazes the
        level, not a river; it stays dry (decided from the global field, so seamless)."""
        raw = self._raw(x0 - 1, y0 - 1, w + 2, h + 2)
        return tuple(tuple(raw[y][x] and (raw[y - 1][x] or raw[y + 1][x] or raw[y][x - 1] or raw[y][x + 1])
                           for x in range(1, w + 1)) for y in range(1, h + 1))

    def _dry_offset(self):
        w, h, m = self.width, self.height, DRY_MARGIN
        for attempt in range(64):
            ox = derive_seed(self.seed, "offset-x", attempt) % (SCALE * 8)
            oy = derive_seed(self.seed, "offset-y", attempt) % (SCALE * 8)
            if not any(any(row) for row in self._mask(ox - m, oy - m, w + 2 * m, h + 2 * m)):
                return ox, oy
        return 0, 0  # practically unreachable; the anchor clearing still overrides water

    def at(self, gx, gy):
        return self._mask(gx + self.offset[0], gy + self.offset[1], 1, 1)[0][0]

    def grid(self, key):
        """Water of one chunk with a one-tile border from its neighbours: (h+2) rows of
        (w+2) booleans, so banks along a chunk edge match on both sides. Memoized."""
        cached = self._grids.get((key.x, key.y))
        if cached is None:
            cached = self._mask(key.x * self.width + self.offset[0] - 1,
                                key.y * self.height + self.offset[1] - 1, self.width + 2, self.height + 2)
            if len(self._grids) > 512:
                self._grids.clear()
            self._grids[(key.x, key.y)] = cached
        return cached
