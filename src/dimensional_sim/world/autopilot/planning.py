"""Goal choice: which spot to walk to, when to go home, and where to wander next.

Every choice is a pure function of state plus seeds derived from the world seed and
the saved decision counter, so a reload replays the same decisions.
"""
from ..catalog import BY_ID, FOOD_TRADES, ITEMS
from ..models import ChunkKey, chunk_ident
from ..tuning import FOOD_TRIP_CHUNKS
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
                if spot.id in self.completed or entry.kind == "fight" or self.story_spent(entry):
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
            if entry.cost and not self.worth_paying(entry):
                continue   # a trade or a quest asks for what the avatar does not carry (or should keep)
            if max(abs(gx // w), abs(gy // h)) > limit and not (hungry and entry.feeds):
                continue   # beyond the frontier this life can survive (food is worth the risk when starving)
            if not (hungry and entry.feeds) and not self.camp_wants(
                    entry, ChunkKey(self.game.player.chunk.dimension, gx // w, gy // h)):
                continue   # camped: only what the camp's place and focus are about
            cells = [c for c in self._approach(gx, gy) if c in player_field]
            if not cells:
                continue
            d = min(player_field[c] for c in cells)
            rank = (0 if hungry and entry.feeds else 1 if entry.placement == "story" else 2, d, ident)
            if best is None or rank < best[0]:
                best = (rank, {"kind": kind, "id": ident, "x": gx, "y": gy})
        return best[1] if best else None

    def _choose_goal(self):
        if self.health < RETREAT_BELOW and (self.hunger > 0 or not self._has_food()):
            return self._rest_goal()
        if self._camp_work_ready():   # a full pack may be stowed at the camp
            return self._home_goal()
        if self.hunger <= EAT_AT and not self._has_food() and self.farm_ripe() and not self.at_camp():
            return self._home_goal()   # hungry with nothing to eat: the farm at the camp has a crop
        player_field = self._field({self._player()})
        best = self._best_candidate(player_field)
        self._camp_idle(best is not None)
        if self.hunger <= EAT_AT and not self._has_food() and not self._feeds_goal(best):
            trip = self._food_trade_trip()   # hungry with coins and no food in reach: walk to a food stall
            if trip is not None:
                return trip
        return best or self._wander_goal(player_field)

    def _feeds_goal(self, goal):
        if goal is None or goal["kind"] != "spot":
            return False
        spot = self._spot_by_id(goal["id"])
        return spot is not None and BY_ID[spot.encounter].feeds

    def _food_trade_trip(self):
        """A travel goal to the nearest food stall the avatar can pay at, within FOOD_TRIP_CHUNKS:
        one rolled this life (its spot), or a landmark seen before whose own encounters sell food."""
        w, h = self._dims()
        here = self.game.player.chunk
        best = None
        for chunk_id, plan in sorted(self.spot_plans.items()):
            for index, (encounter, x, y) in enumerate(plan):
                entry = BY_ID[encounter]
                if entry in FOOD_TRADES and self.worth_paying(entry):
                    _, cx, cy = chunk_id.rsplit(":", 2)
                    best = _nearer(best, here, int(cx), int(cy), int(cx) * w + x, int(cy) * h + y)
        for key, status in self.game.world.discovered(here.dimension):
            if status != "visited" or chunk_ident(key) in self.spot_plans:
                continue
            site = self.game.world.site_for(key)
            if site is not None and any(e.site == site.site.id and self.worth_paying(e) for e in FOOD_TRADES):
                best = _nearer(best, here, key.x, key.y, key.x * w + site.x, key.y * h + site.y)
        if best is None or best[0] > FOOD_TRIP_CHUNKS:
            return None
        return {"kind": "travel", "id": None, "x": best[1], "y": best[2]}

    def _wander_goal(self, reachable):
        w, h = self._dims()
        center = self.game.player.chunk
        frontier = self.frontier()
        by_chunk = {}
        for (gx, gy), d in reachable.items():
            ck = (gx // w, gy // h)
            if ck != (center.x, center.y) and max(abs(ck[0]), abs(ck[1])) <= max(frontier, self.ring(center)) \
                    and (not self.camp_holds() or self.in_camp_area(ChunkKey(center.dimension, *ck))):
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
        if g["kind"] in ("target", "dodge"):
            t = self.game.targets.get(g["id"])
            if t is None or t.hp <= 0 or self.game.world.peek(t.chunk) is None:
                return False
            if g["kind"] == "target":   # enemies move now (charge, retreat): follow where it is
                g["x"], g["y"] = self._global(t.chunk, t.x, t.y)
            return True
        return True

    def _goal_cells(self, goal):
        """Cells that count as arriving at the goal (home crosses chunks stepwise)."""
        if goal["kind"] in ("wander", "dodge"):
            return {(goal["x"], goal["y"])}
        if goal["kind"] == "target":   # anywhere a blow reaches it from
            return self.strike_cells(goal["x"], goal["y"])
        if goal["kind"] not in ("home", "travel"):
            return self._approach(goal["x"], goal["y"])
        w, h = self._dims()
        ax, ay = goal["x"], goal["y"]   # the anchor, this life's campfire, or a far place (travel)
        acx, acy = ax // w, ay // h
        center = self.game.player.chunk
        if abs(acx - center.x) <= 1 and abs(acy - center.y) <= 1 and \
                self.game.world.peek(ChunkKey(self.dimension, acx, acy)) is not None:
            return {(ax, ay)}
        # Anchor beyond the resident area: walk into the neighbor chunk toward it.
        step = (acx > center.x) - (acx < center.x), (acy > center.y) - (acy < center.y)
        tx, ty = center.x + step[0], center.y + step[1]
        return {(tx * w + x, ty * h + y) for y in range(h) for x in range(w)}


def _nearer(best, here, cx, cy, gx, gy):
    d = max(abs(cx - here.x), abs(cy - here.y))
    return (d, gx, gy) if best is None or (d, gx, gy) < best else best
