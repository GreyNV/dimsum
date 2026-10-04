"""Auto-pilot expedition: the character lives, explores and survives by itself.

The player does not steer. Expedition turns world state into ordinary runtime
InputCommands (move, face, punch) and advances Exploration with them, so collision,
chunk streaming, attack timing and damage stay where they were. Every choice is a
pure function of saved state plus seeds from the world seed, the life number and
a saved decision counter: advancing 10 minutes at once or in 20ms ticks gives the
same expedition, byte for byte. Path fields are memoized pure results.

Loop: settle (death -> next life, rewards, eating, retreat) -> finish punch /
activity / rest / pause -> pick the nearest reachable spot or living target
(food first when hungry; home to rest when hurt with no food) -> otherwise walk
into an unvisited neighbor chunk -> step along a distance field -> perform or punch.

Lives (design: core-loop.md): attributes have regular XP (this life) and
dimensional XP (persists; 20% of gains). Speed from progression.py shortens
activities and punch pauses; Endurance slows hunger and softens hits. Hunger and
health are integer micro-points; every rate change ends a simulation step, so
vitals are partition-independent. Health 0 -> life report -> return to anchor:
regular XP, inventory, vitals, actors and encounter rolls reset; dimensional XP,
the discovery map and skills persist.

Prologue (first life of a new expedition): the screen starts dark while the
avatar wakes from the bandit ambush ("awaken"), then stands up ("stand_up") and
listens to the old man who found them ("listen"). These are ordinary timed tasks,
so the opening is as deterministic and save-safe as the rest of the expedition.

Spawn windows (encounters.py): at the start of every life each limited encounter
rolls how many of it may exist at once around the avatar (resident chunks). When a
chunk first becomes resident its spots and asset-spawned boars are screened: any
beyond the cap never appear this life. Completing or leaving one frees a slot for
new ground. Food is scarce on purpose: passing the first biome takes some luck.
Prayer at wayside shrines grants persistent blessing power and sometimes a boon.

Manual control is the locked skill "take_control"; adapters must ignore player
movement/attack input until it is unlocked.
"""
from collections import deque

from ..core import _softcapped_level
from .encounters import ATTRIBUTES, BY_ID, ENCOUNTER_VERSION, ITEMS, chunk_spots, roll_loot, roll_window
from .models import DELTAS, DIRECTIONS, ChunkKey, fields, identifier, integer
from .progression import CONFIG, DIMENSIONAL_DIVISOR, dimensional_level, regular_level, scaled_ms, speed_permille
from .runtime import Exploration, InputCommand, Target
from .seeds import derive_seed

SKILLS = ("take_control",)
LOG_LIMIT = 16
PAUSE_AFTER_ACTIVITY_MS = 450
PAUSE_BETWEEN_PUNCHES_MS = 220
MAX_EVENTS_PER_ADVANCE = 1_000_000

POINT = 1_000_000                  # one vital point in micro-units
VITAL_MAX = 100 * POINT
HUNGER_DRAIN = 500                 # micro/ms at base Endurance (0.5 points per second)
STARVATION = 1_000                 # health micro/ms at zero hunger (1 point/s)
REGEN = 200                        # health micro/ms while hunger is above half
REST_REGEN = 1_000                 # extra health micro/ms while resting at the camp
REGEN_ABOVE = 50 * POINT
EAT_AT = 60 * POINT                # auto-eat when hunger is at or below this
FOOD_COOLDOWN_MS = 15_000
BOAR_HIT = 6 * POINT               # per punch exchanged with a living boar, at the anchor
# Danger rises with distance from the anchor: hits x1.5 and +1 boar HP per ring.
DANGER_RING_CAP = 40
RETREAT_BELOW = 35 * POINT         # badly hurt -> go home and rest
AVOID_FIGHTS_BELOW = 50 * POINT    # hurt -> leave boars alone
FOOD_HEALS_DIVISOR = 3             # eating restores food/3 health points
RESTED_AT = 90 * POINT
REST_MS = 10_000
INVENTORY_SLOTS = 12
STACK_LIMIT = 20
BOON_CHANCE = 40                   # percent of prayers the gods answer at once
BOON = 15                          # health and hunger points restored by an answered prayer
BOAR_ENCOUNTER = "bramble_boar"    # asset-spawned enemies count against this spawn window

PROLOGUE_MS = {"awaken": 10_000, "stand_up": 3_500, "listen": 25_000}
PROLOGUE_NEXT = {"awaken": "stand_up", "stand_up": "listen"}
PROLOGUE_NAMES = {"awaken": "Wake up", "stand_up": "Stand up", "listen": "Listen to the old man"}
# Memory fragments shown on the dark screen while the avatar wakes up.
MEMORIES = (
    "The forest road. Wagon wheels, laughter, a song left half-finished.",
    "Arrows from the trees. Bandits. Steel and shouting, someone running.",
    "A blade, cold and very close. The ground rushing up to meet you.",
    "Silence. Then, from very far away, something old answers.",
)
# The old man who finds the newborn avatar beside the road.
ELDER_LINES = (
    "Why... I don't believe it. I witnessed the birth of an avatar - a dimensional avatar.",
    "The bandits left you for dead. The gods saved you, but now you have to worship them.",
    "Go explore the world, and don't forget to pray. Maybe the gods will bestow blessings on you.",
    "Mind your hunger, too. This forest feeds only the lucky.",
    "May the path be smooth. Only you will know what destiny awaits.",
)
LOG_TYPES = ("encounter", "eat", "rest", "life", "blessing", "lore")
TASK_TYPES = ("perform", "pause", "rest", *PROLOGUE_MS)
SCHEMA_VERSION = 3


def _table():
    return {name: 0 for name in ATTRIBUTES}


def _ceil_div(a, b):
    return -(-a // b)


class Expedition:
    def __init__(self, game, *, skills=(), fresh=True):
        """fresh=True starts a new expedition (prologue first); loaders pass False."""
        self.game = game
        self.dimension = game.player.chunk.dimension
        self.skills = set()
        for skill in skills:
            self.unlock(skill)
        # Persistent across lives.
        self.dimensional = _table()
        self.life = 1
        self.total_ms = 0
        self.log = []
        self.sequence = 0
        self.decisions = 0
        self.best_depth = 0
        self.blessing = 0
        # No pop-up opening: the prologue tells the story in the world itself.
        self.report = {"seq": 0, "life": 0, "clock_ms": 0, "title": "", "lines": []}
        self._spot_cache = {}
        self._field_cache = {}
        self._new_life_state()
        self.anchor = self._anchor()
        self.elder = self._elder_cell()
        if fresh:
            self.task = {"type": "awaken", "spot": None, "elapsed_ms": 0, "duration_ms": PROLOGUE_MS["awaken"]}
            self._screen()

    def _new_life_state(self):
        self.regular = _table()
        self.life_gain = _table()     # dimensional XP gained this life (report)
        self.completed = set()
        self.inventory = {}
        self.hunger = VITAL_MAX
        self.health = VITAL_MAX
        self.food_cooldown_ms = 0
        self.cause = None
        self.depth = 0
        self.task = None   # {"type": TASK_TYPES, "spot", "elapsed_ms", "duration_ms"}
        self.goal = None   # {"kind": "spot"|"target"|"wander"|"home", "id", "x", "y"}
        self._reset_spawns()

    def _reset_spawns(self):
        """Roll this life's spawn windows; nothing has been screened yet."""
        seed = derive_seed(self.game.world.world_seed, "spawn-window", self.life)
        self.budget = {entry.id: limit for entry in BY_ID.values()
                       if (limit := roll_window(entry, seed)) is not None}
        self.spawned = {ident: 0 for ident in self.budget}   # total admitted this life
        self.admitted = {}             # spot / asset-target id -> encounter id, this life
        self.screened_chunks = set()   # chunk ids whose spots were screened
        self.screened_targets = set()  # asset-spawned target ids screened

    # ----- public state -------------------------------------------------
    def unlock(self, skill):
        if skill not in SKILLS:
            raise ValueError("unknown skill")
        self.skills.add(skill)

    @property
    def manual_control(self):
        return "take_control" in self.skills

    def interrupt(self):
        """Manual input took over: drop the plan; a running punch still completes."""
        self.task, self.goal = None, None

    @property
    def in_prologue(self):
        return bool(self.task) and self.task["type"] in PROLOGUE_MS

    def prologue(self):
        """Presentation of the opening scene, or None once it is over."""
        if not self.in_prologue:
            return None
        stage = self.task["type"]
        lines = MEMORIES if stage == "awaken" else ELDER_LINES if stage == "listen" else ()
        return {"stage": stage, "progress": self.task["elapsed_ms"] * 1000 // self.task["duration_ms"],
                "elder": {"x": self.elder[0], "y": self.elder[1]}, "lines": list(lines)}

    def bounty(self):
        """This life's spawn caps: [(encounter id, spawned so far, at-once limit)]."""
        return [(ident, self.spawned[ident], self.budget[ident]) for ident in BY_ID if ident in self.budget]

    def ring(self, key):
        """Danger ring: Chebyshev chunk distance from the anchor chunk."""
        return max(abs(key.x), abs(key.y))

    def punch_damage(self):
        """1 + softcapped (regular + dimensional) Strength levels / 5."""
        soft = CONFIG.base_softcap
        level = (_softcapped_level(regular_level(self.regular["strength"]), soft, CONFIG.softcap_softness)
                 + _softcapped_level(dimensional_level(self.dimensional["strength"]), soft, CONFIG.softcap_softness))
        return 1 + int(level) // 5

    def boar_hit(self, key):
        ring = min(self.ring(key), DANGER_RING_CAP)
        return BOAR_HIT * 3 ** ring // 2 ** ring * 1000 // self.speed("endurance")

    def speed(self, attribute):
        return speed_permille(self.regular[attribute], self.dimensional[attribute])

    def activity(self):
        """Current activity for presentation: name/kind/progress 0..1000."""
        task = self.task
        if not task or task["type"] == "pause":
            return None
        progress = task["elapsed_ms"] * 1000 // task["duration_ms"]
        if task["type"] in PROLOGUE_MS:
            px, py = self._player()
            return {"encounter": task["type"], "name": PROLOGUE_NAMES[task["type"]], "kind": task["type"],
                    "x": px, "y": py, "progress": progress}
        if task["type"] == "rest":
            return {"encounter": "anchor_rest", "name": "Resting at the anchor camp", "kind": "rest",
                    "x": self.anchor[0], "y": self.anchor[1], "progress": progress}
        spot = self._spot_by_id(task["spot"])
        if spot is None:
            return None
        entry = BY_ID[spot.encounter]
        gx, gy = self._global(spot.chunk, spot.x, spot.y)
        return {"encounter": entry.id, "name": entry.name, "kind": entry.kind,
                "x": gx, "y": gy, "progress": progress}

    def mode(self):
        if self.in_prologue:
            return "prologue"
        if self.task and self.task["type"] == "rest":
            return "rest"
        if self.game.player.animation == "attack" or (self.goal or {}).get("kind") == "target":
            return "fight"
        if self.task and self.task["type"] == "perform":
            return "encounter"
        if self.goal and self.goal["kind"] in ("spot", "home"):
            return "travel" if self.goal["kind"] == "spot" else "home"
        return "explore"

    def vitals(self):
        return {"hunger": self.hunger // 10_000, "health": self.health // 10_000, "max": 10_000,
                "food_cooldown_ms": self.food_cooldown_ms, "food_cooldown_total_ms": FOOD_COOLDOWN_MS,
                "blessing": self.blessing}

    def inventory_rows(self):
        return [{"id": item, "name": ITEMS[item].name, "kind": ITEMS[item].kind,
                 "glyph": ITEMS[item].glyph, "food": ITEMS[item].food, "count": count}
                for item, count in self.inventory.items()]

    def visible_spots(self):
        """Uncompleted spots in resident chunks (fight spots appear as targets)."""
        result = []
        for chunk in self._resident():
            for spot in self._live(chunk):
                entry = BY_ID[spot.encounter]
                if spot.id in self.completed or entry.kind == "fight":
                    continue
                gx, gy = self._global(spot.chunk, spot.x, spot.y)
                result.append({"id": spot.id, "encounter": spot.encounter, "name": entry.name,
                               "kind": entry.kind, "x": gx, "y": gy})
        return result

    def target_kinds(self):
        """Encounter id behind each target (asset-spawned enemies are boars)."""
        kinds = {}
        for target_id in self.game.targets:
            spot = self._spot_by_id(target_id) if target_id.startswith("enc:") else None
            kinds[target_id] = spot.encounter if spot else "bramble_boar"
        return kinds

    # ----- geometry -----------------------------------------------------
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
        center = self.game.player.chunk
        result = []
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                chunk = self.game.world.peek(ChunkKey(center.dimension, center.x + dx, center.y + dy))
                if chunk is not None:
                    result.append(chunk)
        return result

    def _spots(self, chunk):
        key = (chunk.key, self.life)
        cached = self._spot_cache.get(key)
        if cached is None or cached[0] != chunk.seed:
            if len(self._spot_cache) > 256:
                self._spot_cache.clear()
            cached = (chunk.seed, chunk_spots(chunk, life=self.life))
            self._spot_cache[key] = cached
        return cached[1]

    def _live(self, chunk):
        """Spots this life's spawn windows admitted."""
        return [spot for spot in self._spots(chunk) if spot.id in self.admitted]

    def _active(self, encounter):
        """Admitted, unfinished instances of an encounter around the avatar now."""
        count = 0
        for chunk in self._resident():
            count += sum(1 for spot in self._live(chunk)
                         if spot.encounter == encounter and spot.id not in self.completed)
        if encounter == BOAR_ENCOUNTER:
            resident = {chunk.key for chunk in self._resident()}
            count += sum(1 for t in self.game.targets.values() if not t.id.startswith("enc:")
                         and t.hp > 0 and t.chunk in resident and t.id in self.admitted)
        return count

    def _admit(self, ident, encounter):
        limit = self.budget.get(encounter)
        if limit is not None:
            if self._active(encounter) >= limit:
                return False
            self.spawned[encounter] += 1
        self.admitted[ident] = encounter
        return True

    def _screen(self):
        """Admit or drop newly resident spots and new asset boars (zero time, saved)."""
        for chunk in self._resident():
            ident = f"{chunk.key.dimension}:{chunk.key.x}:{chunk.key.y}"
            if ident in self.screened_chunks:
                continue
            self.screened_chunks.add(ident)
            for spot in self._spots(chunk):
                self._admit(spot.id, spot.encounter)
        for target in sorted(self.game.targets.values(), key=lambda t: t.id):
            if target.id.startswith("enc:") or target.id in self.screened_targets:
                continue
            self.screened_targets.add(target.id)
            if target.hp > 0 and not self._admit(target.id, BOAR_ENCOUNTER):
                target.hp = 0   # beyond this life's window: the boar never shows up

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

    def _spot_by_id(self, spot_id):
        parts = (spot_id or "").split(":")
        if len(parts) != 5 or parts[0] != "enc":
            return None
        try:
            key = ChunkKey(parts[1], int(parts[2]), int(parts[3]))
        except ValueError:
            return None
        chunk = self.game.world.peek(key)
        if chunk is None:
            return None
        return next((s for s in self._spots(chunk) if s.id == spot_id), None)

    def _player(self):
        p = self.game.player
        return self._global(p.chunk, p.x, p.y)

    def _grid(self):
        w, h = self._dims()
        chunks = {(c.key.x, c.key.y): c for c in self._resident()}
        exits = {k: {(e.x, e.y, e.direction) for e in c.asset.exits} for k, c in chunks.items()}
        return w, h, chunks, exits

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

    def _field(self, goals):
        """Distance-to-goal field over resident chunks (pure, memoized)."""
        grid = self._grid()
        blocked = self._blocked()
        key = (tuple(sorted(goals)), tuple(sorted(grid[2])), self.game.player.chunk, blocked)
        cached = self._field_cache.get(key)
        if cached is not None:
            return cached
        if len(self._field_cache) > 32:
            self._field_cache.clear()
        dist, queue = {}, deque()
        for g in sorted(goals):
            if self._walkable(grid, *g) and g not in blocked:
                dist[g] = 0
                queue.append(g)
        while queue:
            x, y = queue.popleft()
            for direction in DIRECTIONS:
                dx, dy = DELTAS[direction]
                px, py = x - dx, y - dy
                if (px, py) in dist or (px, py) in blocked:
                    continue
                if self._walkable(grid, px, py) and self._can_move(grid, blocked, px, py, direction):
                    dist[(px, py)] = dist[(x, y)] + 1
                    queue.append((px, py))
        self._field_cache[key] = dist
        return dist

    def _approach(self, gx, gy):
        return {(gx + dx, gy + dy) for dx, dy in DELTAS.values()}

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

    # ----- planning -----------------------------------------------------
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
        best = None
        for kind, ident, entry, gx, gy in self._candidates():
            if kind == "target" and self.health < AVOID_FIGHTS_BELOW:
                continue
            cells = [c for c in self._approach(gx, gy) if c in player_field]
            if not cells:
                continue
            d = min(player_field[c] for c in cells)
            feeds = any(ITEMS[loot.item].kind == "food" for loot in entry.loot)
            rank = (0 if hungry and feeds else 1, d, ident)
            if best is None or rank < best[0]:
                best = (rank, {"kind": kind, "id": ident, "x": gx, "y": gy})
        return best[1] if best else None

    def _choose_goal(self):
        if self.health < RETREAT_BELOW and (self.hunger > 0 or not self._has_food()):
            return {"kind": "home", "id": None, "x": self.anchor[0], "y": self.anchor[1]}
        player_field = self._field({self._player()})
        return self._best_candidate(player_field) or self._wander_goal(player_field)

    def _wander_goal(self, reachable):
        w, h = self._dims()
        center = self.game.player.chunk
        by_chunk = {}
        for (gx, gy), d in reachable.items():
            ck = (gx // w, gy // h)
            if ck != (center.x, center.y):
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

    # ----- rewards, food, death -----------------------------------------
    def _entry(self, kind, text, *, encounter=None, attribute=None, xp=0, dim_xp=0, items=(), blessing=0):
        self.sequence += 1
        self.log.append({"seq": self.sequence, "clock_ms": self.total_ms, "life": self.life,
                         "type": kind, "encounter": encounter, "text": text,
                         "attribute": attribute, "xp": xp, "dim_xp": dim_xp,
                         "items": [[item, count] for item, count in items], "blessing": blessing})
        del self.log[:-LOG_LIMIT]

    def _add_item(self, item, count):
        have = self.inventory.get(item)
        if have is None and len(self.inventory) >= INVENTORY_SLOTS:
            return 0
        kept = min(count, STACK_LIMIT - (have or 0))
        if kept > 0:
            self.inventory[item] = (have or 0) + kept
        return max(0, kept)

    def _reward(self, ident, entry):
        self.completed.add(ident)
        dim = entry.xp // DIMENSIONAL_DIVISOR
        self.regular[entry.attribute] += entry.xp
        self.dimensional[entry.attribute] += dim
        self.life_gain[entry.attribute] += dim
        seed = derive_seed(self.game.world.world_seed, "loot", self.life, ident)
        items = [(item, kept) for item, count in roll_loot(entry, seed)
                 if (kept := self._add_item(item, count))]
        if entry.heal:
            self.health = min(VITAL_MAX, self.health + entry.heal * POINT)
        self.blessing += entry.blessing
        self._entry("encounter", entry.log, encounter=entry.id, attribute=entry.attribute,
                    xp=entry.xp, dim_xp=dim, items=items, blessing=entry.blessing)
        if entry.blessing and derive_seed(seed, "boon") % 100 < BOON_CHANCE:
            self.health = min(VITAL_MAX, self.health + BOON * POINT)
            self.hunger = min(VITAL_MAX, self.hunger + BOON * POINT)
            self._entry("blessing", f"The gods answer: warmth spreads through you (+{BOON} health, +{BOON} hunger).",
                        encounter=entry.id)

    def _eat(self):
        """Auto-eat: the food that restores the most without wasting, else the smallest."""
        foods = sorted((ITEMS[i].food, i) for i in self.inventory if ITEMS[i].kind == "food")
        if not foods or self.food_cooldown_ms or self.hunger > EAT_AT:
            return False
        room = (VITAL_MAX - self.hunger) // POINT
        fitting = [f for f in foods if f[0] <= room]
        value, item = fitting[-1] if fitting else foods[0]
        self.inventory[item] -= 1
        if not self.inventory[item]:
            del self.inventory[item]
        self.hunger = min(VITAL_MAX, self.hunger + value * POINT)
        heal = value // FOOD_HEALS_DIVISOR
        self.health = min(VITAL_MAX, self.health + heal * POINT)
        self.food_cooldown_ms = FOOD_COOLDOWN_MS
        self._entry("eat", f"Ate {ITEMS[item].name.lower()} (+{value} hunger, +{heal} health).",
                    items=[(item, -1)])
        return True

    def _die(self):
        lived = self.game.elapsed_ms // 1000
        lines = [f"{name.capitalize()} experience gained: {self.regular[name]}"
                 f" (dimensional +{self.life_gain[name]})" for name in ATTRIBUTES]
        cause = {"starvation": "Cause: starvation", "boar": "Cause: a bramble boar"}.get(self.cause, "Cause: exhaustion")
        bounty = ", ".join(f"{BY_ID[i].name.lower()} {n} (max {limit} at once)" for i, n, limit in self.bounty())
        lines += [f"Forest bounty this life: {bounty}", f"Blessing power: {self.blessing}",
                  f"Encounters completed: {len(self.completed)}",
                  f"Deepest ring reached: {self.depth} (best {self.best_depth})",
                  f"Survived: {lived // 60}m {lived % 60:02d}s", cause, "Returning to anchor..."]
        self.report = {"seq": self.sequence + 1, "life": self.life, "clock_ms": self.total_ms,
                       "title": f"Life {self.life} ends", "lines": lines}
        self._entry("life", f"Life {self.life} ended. The anchor pulls you back.")
        config = {name: getattr(self.game, name) for name in (
            "movement_interval_ms", "animation_rate_percent", "attack_rate_percent", "attack_damage")}
        press = self.game.step_on_press
        self.game = Exploration(self.game.world, self.dimension, animations=self.game.animations, **config)
        self.game.step_on_press = press
        self.life += 1
        self._new_life_state()
        self._field_cache.clear()

    def _settle(self):
        """Zero-time bookkeeping before each step. Returns True if a life ended."""
        if self.health == 0:
            self._die()
            return True
        here = self.ring(self.game.player.chunk)
        if here > self.depth:
            self.depth = here
            self.best_depth = max(self.best_depth, here)
        self._screen()
        for chunk in self._resident():
            if chunk.key not in self.game.initialized_chunks:
                continue
            for spot in self._live(chunk):
                entry = BY_ID[spot.encounter]
                if entry.kind == "fight" and spot.id not in self.game.targets and spot.id not in self.completed:
                    hp = entry.hp + min(self.ring(spot.chunk), DANGER_RING_CAP)
                    self.game.targets[spot.id] = Target(spot.id, spot.chunk, spot.x, spot.y, hp)
        kinds = None
        for t in sorted(self.game.targets.values(), key=lambda t: t.id):
            if t.hp == 0 and t.id not in self.completed and t.id in self.admitted:
                kinds = kinds or self.target_kinds()
                self._reward(t.id, BY_ID[kinds[t.id]])
        self._eat()
        if not self._goal_valid():
            self.goal = None
        if self.goal and self.goal["kind"] == "wander" and not self.task and self._candidates():
            found = self._best_candidate(self._field({self._player()}))
            if found:
                self.goal = found
        return False

    # ----- vitals -------------------------------------------------------
    def _drain(self):
        return HUNGER_DRAIN * 1000 // self.speed("endurance")

    def _health_rate(self):
        rate = 0
        if self.hunger == 0:
            rate -= STARVATION
        elif self.hunger > REGEN_ABOVE:
            rate += REGEN
        if self.task and self.task["type"] == "rest":
            rate += REST_REGEN
        return rate

    def _vitals_limit(self):
        """Milliseconds until the next vitals event (rate change, eating, death)."""
        limits = []
        drain = self._drain()
        if self.hunger > 0:
            limits.append(_ceil_div(self.hunger, drain))
            if self.hunger > REGEN_ABOVE:
                limits.append(_ceil_div(self.hunger - REGEN_ABOVE, drain))
            if self.hunger > EAT_AT:
                limits.append(_ceil_div(self.hunger - EAT_AT, drain))
        if self.food_cooldown_ms:
            limits.append(self.food_cooldown_ms)
        rate = self._health_rate()
        if rate < 0 and self.health > 0:
            limits.append(_ceil_div(self.health, -rate))
        elif rate > 0 and self.health < VITAL_MAX:
            limits.append(_ceil_div(VITAL_MAX - self.health, rate))
        return max(1, min(limits)) if limits else 1 << 40

    def _apply_vitals(self, ms):
        rate = self._health_rate()
        if self.hunger == 0:
            self.cause = "starvation"
        self.hunger = max(0, self.hunger - self._drain() * ms)
        self.health = max(0, min(VITAL_MAX, self.health + rate * ms))
        self.food_cooldown_ms = max(0, self.food_cooldown_ms - ms)
        self.total_ms += ms

    def _run(self, ms, command):
        self.game.advance(ms, command)
        self._apply_vitals(ms)

    # ----- simulation ---------------------------------------------------
    def _face(self, gx, gy):
        px, py = self._player()
        toward = ((gx > px) - (gx < px), (gy > py) - (gy < py))
        direction = next((d for d, delta in DELTAS.items() if delta == toward), None)
        if direction and self.game.player.facing != direction:
            self.game.advance(0, InputCommand(direction))
        self.game.advance(0, InputCommand())

    def _boar_strikes_back(self):
        goal = self.goal
        target = self.game.targets.get(goal["id"]) if goal and goal["kind"] == "target" else None
        if target is not None and target.hp > 0:
            self.health = max(0, self.health - self.boar_hit(target.chunk))
            if self.health == 0:
                self.cause = "boar"

    def advance(self, milliseconds):
        integer(milliseconds, "elapsed milliseconds", 0)
        saved_press = self.game.step_on_press
        self.game.step_on_press = False  # auto-pilot steps on interval boundaries only
        try:
            remaining, events = milliseconds, 0
            while True:
                events += 1
                if events > MAX_EVENTS_PER_ADVANCE:
                    raise RuntimeError("auto-pilot made no progress")
                if self._settle():
                    self.game.step_on_press = False
                    continue
                if remaining == 0:
                    break
                game = self.game
                cap = min(remaining, self._vitals_limit())
                if game.player.animation == "attack":
                    clip = game.animations["attack"].duration_ms * 100
                    done = game.player.animation_elapsed_ms * game.attack_rate_percent
                    left = _ceil_div(clip - done, game.attack_rate_percent)
                    for start, _, _ in game.animations["attack"].active_intervals():
                        if done < start * 100:  # stop where damage lands: same clock for any slicing
                            left = min(left, _ceil_div(start * 100 - done, game.attack_rate_percent))
                            break
                    step = max(1, min(cap, left))
                    self._run(step, InputCommand(attack=True))
                    remaining -= step
                    if game.player.animation != "attack":
                        self._boar_strikes_back()
                        self.task = {"type": "pause", "spot": None, "elapsed_ms": 0,
                                     "duration_ms": scaled_ms(PAUSE_BETWEEN_PUNCHES_MS, self.speed("strength"))}
                    continue
                if self.task:
                    step = min(cap, self.task["duration_ms"] - self.task["elapsed_ms"])
                    self._run(step, InputCommand())
                    remaining -= step
                    self.task["elapsed_ms"] += step
                    if self.task["elapsed_ms"] >= self.task["duration_ms"]:
                        done, self.task = self.task, None
                        if done["type"] == "perform":
                            spot = self._spot_by_id(done["spot"])
                            if spot is not None and spot.id not in self.completed:
                                self._reward(spot.id, BY_ID[spot.encounter])
                            self.goal = None
                            self.task = {"type": "pause", "spot": None, "elapsed_ms": 0,
                                         "duration_ms": PAUSE_AFTER_ACTIVITY_MS}
                        elif done["type"] in PROLOGUE_MS:
                            stage = PROLOGUE_NEXT.get(done["type"])
                            if stage == "listen":
                                self._face(*self.elder)   # turn to the old man
                            if stage:
                                self.task = {"type": stage, "spot": None, "elapsed_ms": 0,
                                             "duration_ms": PROLOGUE_MS[stage]}
                            else:
                                self._entry("lore", "The old man walks off down the road. Explore - and don't forget to pray.")
                        elif done["type"] == "rest":
                            if self.health < RESTED_AT and (self.hunger > 0 or self._has_food()):
                                self.task = {"type": "rest", "spot": None, "elapsed_ms": 0,
                                             "duration_ms": REST_MS}   # keep resting
                            else:
                                self.goal = None
                                self._entry("rest", "Rested at the anchor camp.")
                    continue
                if self.goal is None:
                    self.goal = self._choose_goal()
                    if self.goal is None:
                        self._run(cap, InputCommand())
                        remaining -= cap
                        continue
                here, g = self._player(), self.goal
                goals = self._goal_cells(g)
                if here in goals and (g["kind"] != "home" or here == self.anchor):
                    if g["kind"] == "wander":
                        self.goal = None
                    elif g["kind"] == "home":
                        self.task = {"type": "rest", "spot": None, "elapsed_ms": 0, "duration_ms": REST_MS}
                    elif g["kind"] == "spot":
                        self._face(g["x"], g["y"])
                        entry = BY_ID[self._spot_by_id(g["id"]).encounter]
                        self.task = {"type": "perform", "spot": g["id"], "elapsed_ms": 0,
                                     "duration_ms": scaled_ms(entry.duration_ms, self.speed(entry.attribute))}
                    else:
                        self._face(g["x"], g["y"])
                        game.attack_damage = self.punch_damage()
                        game.advance(0, InputCommand(attack=True))  # rising edge: punch
                    continue
                field = self._field(goals)
                grid, blocked = self._grid(), self._blocked()
                best = None
                for direction in DIRECTIONS:
                    dx, dy = DELTAS[direction]
                    nxt = (here[0] + dx, here[1] + dy)
                    if nxt in field and self._can_move(grid, blocked, *here, direction):
                        if best is None or field[nxt] < best[0]:
                            best = (field[nxt], direction)
                if best is None or best[0] >= field.get(here, 1 << 30):
                    self.goal = None  # unreachable now: wait one interval, then replan
                    step = min(cap, game.movement_interval_ms)
                    self._run(step, InputCommand())
                    remaining -= step
                    continue
                direction = best[1]
                left = (game.movement_interval_ms - game.move_elapsed_ms
                        if game.last_move == direction else game.movement_interval_ms)
                step = min(cap, left)
                self._run(step, InputCommand(direction))
                remaining -= step
        finally:
            self.game.step_on_press = saved_press

    # ----- persistence --------------------------------------------------
    def to_dict(self):
        return {"schema_version": SCHEMA_VERSION, "encounters": ENCOUNTER_VERSION,
                "exploration": self.game.to_dict(), "life": self.life, "total_ms": self.total_ms,
                "regular": dict(self.regular), "dimensional": dict(self.dimensional),
                "life_gain": dict(self.life_gain), "completed": sorted(self.completed),
                "inventory": [[item, count] for item, count in self.inventory.items()],
                "hunger": self.hunger, "health": self.health,
                "food_cooldown_ms": self.food_cooldown_ms, "cause": self.cause,
                "depth": self.depth, "best_depth": self.best_depth, "blessing": self.blessing,
                "budget": dict(self.budget), "spawned": dict(self.spawned),
                "admitted": sorted([i, e] for i, e in self.admitted.items()), "screened_chunks": sorted(self.screened_chunks),
                "screened_targets": sorted(self.screened_targets),
                "log": [dict(entry, items=[list(i) for i in entry["items"]]) for entry in self.log],
                "sequence": self.sequence, "decisions": self.decisions, "skills": sorted(self.skills),
                "report": {**self.report, "lines": list(self.report["lines"])},
                "task": dict(self.task) if self.task else None,
                "goal": dict(self.goal) if self.goal else None}

    SAVE_FIELDS = ("schema_version", "encounters", "exploration", "life", "total_ms", "regular",
                   "dimensional", "life_gain", "completed", "inventory", "hunger", "health",
                   "food_cooldown_ms", "cause", "depth", "best_depth", "blessing", "budget", "spawned",
                   "admitted", "screened_chunks", "screened_targets", "log", "sequence",
                   "decisions", "skills", "report", "task", "goal")

    @classmethod
    def from_dict(cls, data):
        if isinstance(data, dict) and data.get("schema_version") == 1:
            return cls._from_v1(data)
        if isinstance(data, dict) and data.get("schema_version") == 2:
            data = cls._upgrade_v2(data)
        fields(data, cls.SAVE_FIELDS)
        if data["schema_version"] != SCHEMA_VERSION or data["encounters"] != ENCOUNTER_VERSION:
            raise ValueError("unsupported expedition save")
        result = cls(Exploration.from_dict(data["exploration"]), skills=data["skills"], fresh=False)
        try:
            result.life = integer(data["life"], "life", 1)
            result.total_ms = integer(data["total_ms"], "total time", 0)
            for name in ("regular", "dimensional", "life_gain"):
                fields(data[name], ATTRIBUTES)
                for attribute in ATTRIBUTES:
                    integer(data[name][attribute], f"{name} XP", 0)
                setattr(result, name, dict(data[name]))
            if type(data["completed"]) is not list:
                raise ValueError("invalid completed encounters")
            for ident in data["completed"]:
                identifier(ident, "encounter spot")
            result.completed = set(data["completed"])
            if type(data["inventory"]) is not list or len(data["inventory"]) > INVENTORY_SLOTS:
                raise ValueError("invalid inventory")
            inventory = {}
            for row in data["inventory"]:
                if type(row) is not list or len(row) != 2 or row[0] not in ITEMS or row[0] in inventory:
                    raise ValueError("invalid inventory row")
                inventory[row[0]] = integer(row[1], "item count", 1, STACK_LIMIT)
            result.inventory = inventory
            result.hunger = integer(data["hunger"], "hunger", 0, VITAL_MAX)
            result.health = integer(data["health"], "health", 0, VITAL_MAX)
            result.food_cooldown_ms = integer(data["food_cooldown_ms"], "food cooldown", 0, FOOD_COOLDOWN_MS)
            if data["cause"] not in (None, "starvation", "boar"):
                raise ValueError("invalid death cause")
            result.cause = data["cause"]
            result.depth = integer(data["depth"], "depth", 0)
            result.best_depth = integer(data["best_depth"], "best depth", result.depth)
            result.blessing = integer(data["blessing"], "blessing power", 0)
            if data["budget"] is None:   # upgraded save: roll this life's windows now
                result._reset_spawns()
            else:
                limited = {entry.id for entry in BY_ID.values() if entry.window is not None}
                if type(data["budget"]) is not dict or set(data["budget"]) != limited \
                        or type(data["spawned"]) is not dict or set(data["spawned"]) != limited:
                    raise ValueError("invalid spawn windows")
                result.budget = {k: integer(v, "spawn window", 0, 2000) for k, v in data["budget"].items()}
                result.spawned = {k: integer(v, "spawned count", 0) for k, v in data["spawned"].items()}
                admitted = data["admitted"]
                if type(admitted) is not list or any(type(row) is not list or len(row) != 2 or row[1] not in BY_ID
                                                     for row in admitted):
                    raise ValueError("invalid admitted spawns")
                for ident, _ in admitted:
                    identifier(ident, "admitted spawn")
                result.admitted = dict(admitted)
                if len(result.admitted) != len(admitted):
                    raise ValueError("duplicate admitted spawn")
                for name in ("screened_chunks", "screened_targets"):
                    values = data[name]
                    if type(values) is not list or len(set(values)) != len(values) or any(
                            type(v) is not str or not 1 <= len(v) <= 200 for v in values):
                        raise ValueError(f"invalid {name}")
                    setattr(result, name, set(values))
            if type(data["log"]) is not list or len(data["log"]) > LOG_LIMIT:
                raise ValueError("invalid expedition log")
            for entry in data["log"]:
                fields(entry, ("seq", "clock_ms", "life", "type", "encounter", "text", "attribute",
                               "xp", "dim_xp", "items", "blessing"))
                if entry["type"] not in LOG_TYPES or (entry["encounter"] is not None and entry["encounter"] not in BY_ID) \
                        or (entry["attribute"] is not None and entry["attribute"] not in ATTRIBUTES):
                    raise ValueError("invalid log entry")
                if type(entry["items"]) is not list or any(type(i) is not list or len(i) != 2 or i[0] not in ITEMS
                                                           for i in entry["items"]):
                    raise ValueError("invalid log items")
                integer(entry["blessing"], "log blessing", 0)
            result.log = [dict(e) for e in data["log"]]
            result.sequence = integer(data["sequence"], "log sequence", 0)
            result.decisions = integer(data["decisions"], "decision counter", 0)
            report = data["report"]
            fields(report, ("seq", "life", "clock_ms", "title", "lines"))
            if type(report["lines"]) is not list or any(not isinstance(l, str) for l in report["lines"]):
                raise ValueError("invalid report")
            result.report = {**report, "lines": list(report["lines"])}
            task = data["task"]
            result.task = None
            if task is not None:
                fields(task, ("type", "spot", "elapsed_ms", "duration_ms"))
                if task["type"] not in TASK_TYPES:
                    raise ValueError("invalid task")
                integer(task["duration_ms"], "task duration", 1)
                integer(task["elapsed_ms"], "task elapsed", 0, task["duration_ms"] - 1)
                result.task = dict(task)
            goal = data["goal"]
            if goal is not None:
                fields(goal, ("kind", "id", "x", "y"))
                if goal["kind"] not in ("spot", "target", "wander", "home"):
                    raise ValueError("invalid goal")
                integer(goal["x"], "goal x")
                integer(goal["y"], "goal y")
                result.goal = dict(goal)
        except (TypeError, KeyError) as exc:
            raise ValueError("malformed expedition save") from exc
        return result

    @classmethod
    def _upgrade_v2(cls, data):
        """encounters-v2 saves keep progress, vitals and inventory; this life's spots
        re-roll under v3 (no prologue, fresh spawn windows, spot plans dropped)."""
        fields(data, ("schema_version", "encounters", "exploration", "life", "total_ms", "regular",
                      "dimensional", "life_gain", "completed", "inventory", "hunger", "health",
                      "food_cooldown_ms", "cause", "depth", "best_depth", "log", "sequence",
                      "decisions", "skills", "report", "task", "goal"))
        if data["encounters"] != "encounters-v2":
            raise ValueError("unsupported expedition save")
        exploration = dict(data["exploration"])
        try:
            exploration["targets"] = [t for t in exploration["targets"] if not str(t["id"]).startswith("enc:")]
            exploration["hit_targets"] = [t for t in exploration["hit_targets"] if not str(t).startswith("enc:")]
            log = [dict(entry, blessing=0) for entry in data["log"]]
            completed = [c for c in data["completed"] if not str(c).startswith("enc:")]
        except (TypeError, KeyError) as exc:
            raise ValueError("malformed expedition save") from exc
        task = data["task"]
        if isinstance(task, dict) and task.get("type") == "perform":
            task = None
        return {**data, "schema_version": SCHEMA_VERSION, "encounters": ENCOUNTER_VERSION,
                "exploration": exploration, "completed": completed, "log": log, "task": task,
                "goal": None, "blessing": 0, "budget": None, "spawned": None, "admitted": None,
                "screened_chunks": None, "screened_targets": None}

    @classmethod
    def _from_v1(cls, data):
        """encounters-v1 saves: keep the world and actor state, start life 1 fresh.
        v1 XP (one track, x10 smaller scale) becomes regular XP x10."""
        fields(data, ("schema_version", "encounters", "exploration", "completed", "xp", "log",
                      "sequence", "decisions", "skills", "task", "goal"))
        if data["encounters"] != "encounters-v1":
            raise ValueError("unsupported expedition save")
        game = Exploration.from_dict(data["exploration"])
        for target_id in [t for t in game.targets if t.startswith("enc:")]:
            del game.targets[target_id]  # v1 fight spots: v2 re-rolls encounters
        result = cls(game, skills=data["skills"], fresh=False)
        fields(data["xp"], ATTRIBUTES)
        for name in ATTRIBUTES:
            result.regular[name] = integer(data["xp"][name], "attribute XP", 0) * 10
        result.decisions = integer(data["decisions"], "decision counter", 0)
        return result
