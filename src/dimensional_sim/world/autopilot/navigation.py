"""Global-cell geometry and memoized path fields over the resident 3x3 chunks.

Cells are global (chunk * size + local). Moves follow collision and cross chunks only
through exits; the reverse-move graph is cached per resident set and each distance
field per (goals, resident set, blocked cells), so repeated planning is cheap.
"""
from collections import deque

from ..models import DELTAS, ChunkKey
from .constants import DIRECTION_DELTAS


class NavigationMixin:
    def _clear_caches(self):
        """Drop every memo (all are pure functions of the world, so this never changes results)."""
        self._region_cache = {}
        self._spot_cache = {}
        self._field_cache = {}
        self._graph_cache = None
        self._chunk_moves_cache = {}
        self._grid_memo = None
        self._resident_memo = None

    def _dims(self):
        asset = self.game.current_chunk().asset
        return asset.width, asset.height

    def _global(self, key, x, y):
        w, h = self._dims()
        return key.x * w + x, key.y * h + y

    def _anchor(self):
        """The anchor camp: the player spawn of the origin chunk (global cell)."""
        key = ChunkKey(self.dimension, 0, 0)
        chunk = self.game.world.peek(key) or self.game.world.get(key)
        spawn = next(s for s in chunk.asset.spawns if s.kind == "player")
        return self._global(key, spawn.x, spawn.y)

    def _resident(self):
        """Resident 3x3 chunks around the avatar (memoized while the cache is unchanged)."""
        center, world = self.game.player.chunk, self.game.world
        memo_key = (center, world.generation_count, world.resident_count, id(world))
        memo = self._resident_memo
        if memo is not None and memo[0] == memo_key and all(world.peek(c.key) is c for c in memo[1]):
            return memo[1]
        result = self._resident_scan(center)
        self._resident_memo = (memo_key, result)
        return result

    def _resident_scan(self, center):
        result = []
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                chunk = self.game.world.peek(ChunkKey(center.dimension, center.x + dx, center.y + dy))
                if chunk is not None:
                    result.append(chunk)
        return result

    def _elder_cell(self):
        """Where the old man stands: two steps beside the anchor (one if cramped)."""
        key = ChunkKey(self.dimension, 0, 0)
        asset = (self.game.world.peek(key) or self.game.world.get(key)).asset
        w, h = asset.width, asset.height
        taken = {(s.x, s.y) for s in asset.spawns}
        ax, ay = self.anchor

        def free(x, y):
            return 0 <= x < w and 0 <= y < h and not asset.collision[y][x] and (x, y) not in taken
        for reach in (2, 1):
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                if all(free(ax + dx * step, ay + dy * step) for step in range(1, reach + 1)):
                    return ax + dx * reach, ay + dy * reach
        return ax, ay

    def _player(self):
        p = self.game.player
        return self._global(p.chunk, p.x, p.y)

    def _grid(self):
        resident = self._resident()
        memo = self._grid_memo
        if memo is not None and memo[0] is resident:   # same memoized resident list
            return memo[1]
        w, h = self._dims()
        chunks = {(c.key.x, c.key.y): c for c in resident}
        exits = {k: {(e.x, e.y, e.direction) for e in c.asset.exits} for k, c in chunks.items()}
        self._grid_memo = (resident, (w, h, chunks, exits))
        return self._grid_memo[1]

    def _can_move(self, grid, blocked, gx, gy, direction):
        w, h, chunks, exits = grid
        dx, dy = DELTAS[direction]
        cx, lx = divmod(gx, w)
        cy, ly = divmod(gy, h)
        nx, ny = gx + dx, gy + dy
        ncx, nlx = divmod(nx, w)
        ncy, nly = divmod(ny, h)
        target = chunks.get((ncx, ncy))
        if target is None or target.asset.collision[nly][nlx] or (nx, ny) in blocked:
            return False
        if (ncx, ncy) != (cx, cy) and (lx, ly, direction) not in exits.get((cx, cy), ()):
            return False
        return True

    def _walkable(self, grid, gx, gy):
        w, h, chunks, _ = grid
        cx, lx = divmod(gx, w)
        cy, ly = divmod(gy, h)
        chunk = chunks.get((cx, cy))
        return chunk is not None and not chunk.asset.collision[ly][lx]

    def _blocked(self):
        return frozenset(self._global(t.chunk, t.x, t.y) for t in self.game.targets.values()
                         if t.hp > 0 and t.chunk.dimension == self.game.player.chunk.dimension)

    def _chunk_moves(self, chunk, w, h):
        """Reverse moves inside one chunk (cached per chunk object: assets are immutable)."""
        cache = self._chunk_moves_cache
        hit = cache.get(chunk.key)
        if hit is not None and hit[0] is chunk:
            return hit[1]
        collision = chunk.asset.collision
        ox, oy = chunk.key.x * w, chunk.key.y * h
        rev = {}
        for ly in range(h):
            row = collision[ly]
            for lx in range(w):
                if row[lx]:
                    continue
                for dx, dy in DIRECTION_DELTAS:
                    nx, ny = lx + dx, ly + dy
                    if 0 <= nx < w and 0 <= ny < h and not collision[ny][nx]:
                        rev.setdefault((ox + nx, oy + ny), []).append((ox + lx, oy + ly))
        if len(cache) > 64:
            cache.clear()
        cache[chunk.key] = (chunk, rev)
        return rev

    def _graph(self):
        """Static reverse moves over the resident chunks: rev[cell] = cells that can step
        into `cell` (collision and chunk exits only; live targets are checked per search).
        Same rule as _can_move with nothing blocked; cached by the resident set."""
        grid = self._grid()
        if self._graph_cache is not None and self._graph_cache[0] is grid:
            return grid, self._graph_cache[1]
        w, h, chunks, exits = grid
        rev = {}
        for chunk in chunks.values():
            rev.update(self._chunk_moves(chunk, w, h))
        none = frozenset()
        for (cx, cy), chunk_exits in exits.items():   # chunk crossings: only through exits
            for lx, ly, direction in chunk_exits:
                gx, gy = cx * w + lx, cy * h + ly
                if chunks[(cx, cy)].asset.collision[ly][lx]:
                    continue
                dx, dy = DELTAS[direction]
                if (gx + dx) // w == cx and (gy + dy) // h == cy:
                    continue   # an exit that stays inside its chunk is already an inner move
                if self._can_move(grid, none, gx, gy, direction):
                    cell = (gx + dx, gy + dy)
                    rev[cell] = rev.get(cell, []) + [(gx, gy)]
        self._graph_cache = (grid, rev)
        return grid, rev

    def _field(self, goals, limit=None, until=None):
        """Distance-to-goal field over resident chunks (pure, memoized). With `limit`,
        only cells at most that many steps away are filled in (exact distances).
        With `until` (the walker's cell), the search stops once every cell up to one step
        farther than `until` is settled: exact for `until` and all its neighbours, which is
        all a step decision reads. As the walker closes in, the same partial field stays
        valid, so one search serves the whole walk."""
        grid, rev = self._graph()
        blocked = self._blocked()
        key = (tuple(sorted(goals)), tuple(sorted(grid[2])), self.game.player.chunk, blocked, limit,
               until is not None)
        cached = self._field_cache.get(key)
        if cached is not None:
            dist, reach = cached
            if reach is None or (until in dist and dist[until] + 1 <= reach):
                return dist
        if len(self._field_cache) > 32:
            self._field_cache.clear()
        dist, queue = {}, deque()
        for g in sorted(goals):
            if self._walkable(grid, *g) and g not in blocked:
                dist[g] = 0
                queue.append(g)
        empty = ()
        reach = None
        while queue:
            cell = queue.popleft()
            d = dist[cell] + 1
            if limit is not None and d > limit:
                continue
            if until is not None and until in dist and d > dist[until] + 1:
                reach = dist[until] + 1   # every cell at distance <= reach is already settled
                break
            for prev in rev.get(cell, empty):
                if prev not in dist and prev not in blocked:
                    dist[prev] = d
                    queue.append(prev)
        self._field_cache[key] = (dist, reach)
        return dist

    def _candidate_field(self):
        """Distances to the avatar for just the cells next to visible spots: the same BFS as
        _field({player}), stopped once every such cell is settled (BFS distances are final
        when first assigned, so the values that matter are identical, at a fraction of the cost)."""
        wanted = set()
        for kind, _, _, gx, gy in self._candidates():
            if kind != "target":
                wanted |= self._approach(gx, gy)
        grid, rev = self._graph()
        blocked = self._blocked()
        start = self._player()
        dist, queue = {}, deque()
        if self._walkable(grid, *start) and start not in blocked:
            dist[start] = 0
            queue.append(start)
        left = len(wanted - {start}) if start in dist else 0
        empty = ()
        while queue and left > 0:
            cell = queue.popleft()
            d = dist[cell] + 1
            for prev in rev.get(cell, empty):
                if prev not in dist and prev not in blocked:
                    dist[prev] = d
                    queue.append(prev)
                    if prev in wanted:
                        left -= 1
        return dist

    def _approach(self, gx, gy):
        return {(gx + dx, gy + dy) for dx, dy in DELTAS.values()}
