"""Goal choice: which spot to walk to, when to go home, and where to wander next.

Every choice is a pure function of state plus seeds derived from the world seed and
the saved decision counter, so a reload replays the same decisions.
"""
from ..catalog import BY_ID, ITEMS
from ..models import ChunkKey
from ..seeds import derive_seed
from .constants import EAT_AT, RETREAT_BELOW


class PlanningMixin:
    def _home_goal(self):
        return {"kind": "home", "id": None, "x": self.anchor[0], "y": self.anchor[1]}

    def _has_food(self):
        return any(ITEMS[i].kind == "food" for i in self.inventory)

    def _candidates(self):
        found = []
        for chunk in self._resident():
            for spot in self._live(chunk):
                entry = BY_ID[spot.encounter]
                if spot.id in self.completed or entry.kind == "fight":
                    continue
                found.append(("spot", spot.id, entry, *self._global(spot.chunk, spot.x, spot.y)))
        kinds = self.target_kinds()
        for t in sorted(self.game.targets.values(), key=lambda t: t.id):
            if t.hp > 0 and t.chunk.dimension == self.game.player.chunk.dimension \
                    and self.game.world.peek(t.chunk) is not None:
                found.append(("target", t.id, BY_ID[kinds[t.id]], *self._global(t.chunk, t.x, t.y)))
        return found

    def _best_candidate(self, player_field):
        """Nearest reachable spot/target; food sources first while hungry with none."""
        hungry = self.hunger <= EAT_AT and not self._has_food()
        w, h = self._dims()
        limit = max(self.frontier(), self.ring(self.game.player.chunk))
        best = None
        for kind, ident, entry, gx, gy in self._candidates():
            if kind == "target":  # monsters initiate combat when they catch the avatar
                continue
            if max(abs(gx // w), abs(gy // h)) > limit:
                continue   # beyond the frontier this life can survive
            cells = [c for c in self._approach(gx, gy) if c in player_field]
            if not cells:
                continue
            d = min(player_field[c] for c in cells)
            rank = (0 if hungry and entry.feeds else 1, d, ident)
            if best is None or rank < best[0]:
                best = (rank, {"kind": kind, "id": ident, "x": gx, "y": gy})
        return best[1] if best else None

    def _choose_goal(self):
        if self.health < RETREAT_BELOW and (self.hunger > 0 or not self._has_food()):
            return self._home_goal()
        player_field = self._field({self._player()})
        return self._best_candidate(player_field) or self._wander_goal(player_field)

    def _wander_goal(self, reachable):
        w, h = self._dims()
        center = self.game.player.chunk
        frontier = self.frontier()
        by_chunk = {}
        for (gx, gy), d in reachable.items():
            ck = (gx // w, gy // h)
            if ck != (center.x, center.y) and max(abs(ck[0]), abs(ck[1])) <= max(frontier, self.ring(center)):
                by_chunk.setdefault(ck, []).append((d, gx, gy))
        if not by_chunk:
            return None
        self.decisions += 1
        roll = derive_seed(self.game.world.world_seed, "autopilot-v1", self.decisions)
        unvisited = sorted(ck for ck in by_chunk
                           if self.game.world.status(ChunkKey(center.dimension, *ck)) != "visited")
        if unvisited:  # push outward: the deepest unexplored neighbors first
            deepest = max(max(abs(x), abs(y)) for x, y in unvisited)
            unvisited = [ck for ck in unvisited if max(abs(ck[0]), abs(ck[1])) == deepest]
        pool = unvisited or sorted(by_chunk)
        cells = sorted(by_chunk[pool[roll % len(pool)]])
        deep = [c for c in cells if c[0] >= cells[0][0] + 6] or cells
        _, gx, gy = deep[derive_seed(roll, "cell") % len(deep)]
        return {"kind": "wander", "id": None, "x": gx, "y": gy}

    def _goal_valid(self):
        g = self.goal
        if g is None:
            return False
        if g["kind"] == "spot":
            return g["id"] not in self.completed and self._spot_by_id(g["id"]) is not None
        if g["kind"] == "target":
            t = self.game.targets.get(g["id"])
            return t is not None and t.hp > 0 and self.game.world.peek(t.chunk) is not None
        return True

    def _goal_cells(self, goal):
        """Cells that count as arriving at the goal (home crosses chunks stepwise)."""
        if goal["kind"] == "wander":
            return {(goal["x"], goal["y"])}
        if goal["kind"] != "home":
            return self._approach(goal["x"], goal["y"])
        w, h = self._dims()
        ax, ay = self.anchor
        acx, acy = ax // w, ay // h
        center = self.game.player.chunk
        if abs(acx - center.x) <= 1 and abs(acy - center.y) <= 1 and \
                self.game.world.peek(ChunkKey(self.dimension, acx, acy)) is not None:
            return {self.anchor}
        # Anchor beyond the resident area: walk into the neighbor chunk toward it.
        step = (acx > center.x) - (acx < center.x), (acy > center.y) - (acy < center.y)
        tx, ty = center.x + step[0], center.y + step[1]
        return {(tx * w + x, ty * h + y) for y in range(h) for x in range(w)}
