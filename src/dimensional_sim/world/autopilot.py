"""Auto-pilot expedition: the character lives, explores and survives by itself.

The player does not steer. Expedition turns world state into ordinary runtime
InputCommands (move, face, punch) and advances Exploration with them, so collision,
chunk streaming, attack timing and damage stay where they were. Every choice is a
pure function of saved state plus seeds from the world seed, the life number and
a saved decision counter: advancing 10 minutes at once or in 20ms ticks gives the
same expedition, byte for byte. Path fields are memoized pure results.

Loop: settle (death -> anchor interlude, rewards, eating, retreat) -> finish punch /
activity / rest / pause -> pick the nearest reachable spot or living target
(food first when hungry; home to rest when hurt with no food) -> otherwise walk
into an unvisited neighbor chunk -> step along a distance field -> perform or punch.

Lives (design: core-loop.md): attributes have regular XP (this life) and
dimensional XP (persists; 20% of gains). Speed from progression.py shortens
activities and punch pauses; Endurance slows hunger and softens hits. Hunger and
health are integer micro-points; every rate change ends a simulation step, so
vitals are partition-independent. Health 0 -> anchor interlude -> next life:
remaining inventory can become persistent dust before regular XP, inventory,
vitals, actors and encounter rolls reset. Dimensional XP, discovery and skills persist.

Prologue (first life of a new expedition): the screen starts dark while the
avatar wakes from the bandit ambush ("awaken"), then stands up ("stand_up") and
listens to the old man who found them ("listen"). These are ordinary timed tasks,
so the opening is as deterministic and save-safe as the rest of the expedition.

Spawn windows (encounters.py): at the start of every life each limited encounter
rolls how many of it may exist at once around the avatar (resident chunks). When a
chunk first becomes resident its spots and asset-spawned boars are screened: any
beyond the cap never appear this life. Completing or leaving one frees a slot for
new ground. Food is scarce on purpose. Rare boars pursue and interrupt work;
quiet thoughts often follow locations. Visible play can rarely start a timed prayer
after completing a location, granting one persistent blessing only when it ends.

Closed loop (docs/design/GAME_LOOP.md): spots come from the action bucket of
known actions (actions.py) in the chunk's region (regions.py). Food and enemy pity
forces a spot of a starved category after a few empty chunks. Crafting (self
actions) turns materials into gear or food. At death, items can be offered for
dust; whatever is still carried burns to ash at rebirth. Dust buys unlocks (new
actions), ash buys mastery (wider spawn windows), blessing buys the shrine unlock
or a next-life boon (economy.py).

Manual control is the locked skill "take_control"; adapters must ignore player
movement/attack input until it is unlocked.
"""
from collections import deque
from dataclasses import replace

from ..core import _softcapped_level
from . import economy
from .actions import Context, _requirement_reasons, bucket, outcome_chance, reasons_against
from .catalog import (BOONS, REGIONS, UNLOCKS, JOURNAL_TOGGLE_MASTERY,
                      JOURNAL_FAVOR_MASTERY)
from .equipment import equip_item, is_equipped, validate_equipped
from .generation import GENERATOR_VERSION
from .repository import WorldRepository
from .journal import new_journal, record_action, record_death, record_items, validate_journal
from .encounters import (ATTRIBUTES, BY_ID, ENCOUNTER_VERSION, ITEMS, EncounterSpot, chunk_spots,
                         forced_spot, lead_spot, roll_loot, roll_window, spot_id)
from .tuning import (BOUNTY_WINDOW_BONUS, COMFORT_DAMAGE_PERCENT, IRON_SKIN_HIT_PERCENT, PITY_CHUNKS,
                     STAFF_PUNCH_BONUS, UNARMED_REACH, WRAP_HIT_PERCENT)
from .models import DELTAS, DIRECTIONS, ChunkKey, fields, identifier, integer

DIRECTION_DELTAS = tuple(DELTAS[d] for d in DIRECTIONS)
from .progression import CONFIG, DIMENSIONAL_DIVISOR, dimensional_level, regular_level, scaled_ms, speed_permille
from .runtime import Exploration, InputCommand, Target
from .seeds import derive_seed

SKILLS = ("take_control",)
LOG_LIMIT = 16
ANCHOR_COUNTDOWN_MS = 30_000
# Dust is permanent; any unoffered inventory is lost when the next life starts.
DUST_VALUE = {item: ITEMS[item].dust for item in ITEMS}   # see catalog.ItemDef.dust
PAUSE_AFTER_ACTIVITY_MS = 450
PAUSE_BETWEEN_PUNCHES_MS = 220
MAX_EVENTS_PER_ADVANCE = 1_000_000

POINT = 1_000_000                  # one vital point in micro-units
VITAL_MAX = 100 * POINT
HUNGER_DRAIN = 750                 # micro/ms at base Endurance (0.75 points per second)
STARVATION = 1_500                 # health micro/ms at zero hunger (1.5 points/s)
REGEN = 200                        # health micro/ms while hunger is above half
REST_REGEN = 1_000                 # extra health micro/ms while resting at the camp
REGEN_ABOVE = 50 * POINT
EAT_AT = 40 * POINT                # auto-eat only after hunger is genuinely low
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
BOAR_ENCOUNTER = "bramble_boar"    # rare spot monsters use this spawn window
MONSTER_STEP_MS = 300             # boars take one step this often while they chase
BOAR_AGGRO_RADIUS = 9             # a live boar this close (in steps) charges the avatar
BOAR_PATH_LIMIT = 2 * BOAR_AGGRO_RADIUS + 2        # chasing boars path-find this far (steps) around obstacles
CAMP_SAFE_RADIUS = 5              # boars stop at the edge of the anchor camp
LEGACY_MONSTER_MAX_MS = 999       # saves before 2026-10-05 used a 1000 ms monster clock
PRAYER_MS = BY_ID["pray"].duration_ms
REFLECTION_MS = {"think": BY_ID["think"].duration_ms, "contemplate": BY_ID["contemplate"].duration_ms}
AFTER_LOCATION_REST_WEIGHT = 26   # weight of "just pause" inside the after-location bucket
REGION_IDS = tuple(REGIONS)
SELF_ACTIONS = tuple(a.id for a in BY_ID.values() if a.placement == "self")
SPOT_REQUIREMENT_ACTIONS = tuple(a for a in BY_ID.values() if a.placement == "spot" and a.requirements)
NEED_ACTIONS = tuple(sorted((a for a in BY_ID.values() if a.trigger == "need"),
                            key=lambda action: (action.need_priority, action.id)))
SCREEN_LOG_LIMIT = 40
STAT_KEYS = ("chunks", "food_spots", "enemy_spots", "pity", "rejected", "completed", "eaten",
             "crafted", "fights", "prayers")

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
LOG_TYPES = ("encounter", "eat", "rest", "life", "blessing", "lore", "trade", "ambush",
             "craft", "reflect", "purchase", "rebirth")
TASK_TYPES = ("perform", "pause", "rest", *SELF_ACTIONS, *PROLOGUE_MS)
SCHEMA_VERSION = 9


def _table():
    return {name: 0 for name in ATTRIBUTES}


def _ceil_div(a, b):
    return -(-a // b)


def _validated_lead(row, world, *, history=False):
    required = ("id", "action", "source", "dimension", "chunk_x", "chunk_y",
                "chunk", "x", "y", "expires_ms")
    fields(row, required, ("status",) if history else ())
    if type(row["id"]) is not str or not row["id"].startswith("lead:") or len(row["id"]) > 200:
        raise ValueError("invalid lead id")
    if row["action"] not in BY_ID or BY_ID[row["action"]].placement != "lead":
        raise ValueError("invalid lead action")
    if type(row["source"]) is not str or not 1 <= len(row["source"]) <= 200:
        raise ValueError("invalid lead source")
    key = ChunkKey(row["dimension"], integer(row["chunk_x"], "lead chunk x"),
                   integer(row["chunk_y"], "lead chunk y"))
    if row["chunk"] != f"{key.dimension}:{key.x}:{key.y}":
        raise ValueError("invalid lead chunk")
    spec = next((s for s in world.dimensions if s.id == key.dimension), None)
    if spec is None:
        raise ValueError("invalid lead dimension")
    integer(row["x"], "lead x", 0, spec.width - 1)
    integer(row["y"], "lead y", 0, spec.height - 1)
    integer(row["expires_ms"], "lead expiry", 1)
    if history and row["status"] not in ("created", "completed", "expired"):
        raise ValueError("invalid lead status")
    return dict(row)


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
        self.dust = 0
        self.ash = 0
        self.unlocked = set()      # UnlockDef ids bought with dust/blessing
        self.mastery = {}          # action id -> mastery level bought with ash
        self.knowledge = set()     # discoveries persist across lives
        self.recipes = set()       # learned recipes persist across lives
        self.journal_disabled = set()
        self.journal_favor = {}
        self.boon_next = None      # BoonDef id for the next life
        self.boon = None           # BoonDef id active this life
        self.journal = new_journal()   # lifetime counts (journal.py); persists across lives
        self.screen_log = []       # debug only, not saved: recent admissions/rejections
        self.roll_log = []         # debug only: bucket at the instant of each new roll
        self._region_cache = {}
        self.monster_ms = 0
        self.anchor_ms = None
        self.anchor_wait = False
        # No pop-up opening: the prologue tells the story in the world itself.
        self.report = {"seq": 0, "life": 0, "clock_ms": 0, "title": "", "lines": []}
        self._spot_cache = {}
        self._field_cache = {}
        self._graph_cache = None
        self._chunk_moves_cache = {}
        self.strikes = {}          # presentation only, not saved: boar attacks landed per target id
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
        self.equipped = {}
        self.leads = []
        self.lead_history = []
        self.hunger = VITAL_MAX
        self.health = VITAL_MAX
        self.food_cooldown_ms = 0
        self.prayers_this_life = 0
        self.monster_ms = 0
        self.cause = None
        self.depth = 0
        self.task = None   # {"type": TASK_TYPES, "spot", "elapsed_ms", "duration_ms"}
        self.goal = None   # {"kind": "spot"|"target"|"wander"|"home", "id", "x", "y"}
        self.stats = {key: 0 for key in STAT_KEYS}
        self.drought = {category: 0 for category in PITY_CHUNKS}
        self.forced = {}   # chunk id -> [encounter id, ...] pity spots, in order
        self._reset_spawns()

    def _reset_spawns(self):
        """Roll this life's spawn windows; nothing has been screened yet."""
        seed = derive_seed(self.game.world.world_seed, "spawn-window", self.life)
        bonus = BOUNTY_WINDOW_BONUS if self.boon == "bountiful_path" else 0
        self.budget = {entry.id: limit for entry in BY_ID.values()
                       if (limit := roll_window(entry, seed, self.mastery.get(entry.id, 0),
                                                bonus if entry.feeds else 0)) is not None}
        self.spawned = {ident: 0 for ident in self.budget}   # total admitted this life
        self.admitted = {}             # spot / asset-target id -> encounter id, this life
        self.screened_chunks = set()   # chunk ids whose spots were screened
        self.spot_plans = {}           # chunk id -> immutable runtime roll, saved for replay
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
        """Hand over steering without erasing an already-started encounter."""
        if self.task and self.task["type"] in ("pause", "rest"):
            self.task = None
        self.goal = None

    def begin_interaction(self):
        """Use the nearest admitted opportunity beside the player in either control mode."""
        if self.anchor_ms is not None or self.in_prologue or self.task:
            return False
        px, py = self._player()
        choices = []
        for chunk in self._resident():
            for spot in self._live(chunk):
                if spot.id in self.completed or BY_ID[spot.encounter].category == "fight":
                    continue
                sx, sy = self._global(spot.chunk, spot.x, spot.y)
                distance = abs(px - sx) + abs(py - sy)
                if distance <= 1:
                    choices.append((distance, spot.id, spot))
        if not choices:
            return False
        spot = min(choices)[2]
        action = BY_ID[spot.encounter]
        self.goal = {"kind": "spot", "id": spot.id, "x": px, "y": py}
        self.task = {"type": "perform", "spot": spot.id, "elapsed_ms": 0,
                     "duration_ms": scaled_ms(action.duration_ms, self.speed(action.attribute))}
        return True

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
        return 1 + int(level) // 5 + (STAFF_PUNCH_BONUS if is_equipped(self.equipped, "walking_staff") else 0)

    def boar_hit(self, key):
        ring = min(self.ring(key), DANGER_RING_CAP)
        hit = BOAR_HIT * 3 ** ring // 2 ** ring * 1000 // self.speed("endurance")
        if is_equipped(self.equipped, "hide_wrap"):
            hit = hit * WRAP_HIT_PERCENT // 100
        if self.boon == "iron_skin":
            hit = hit * IRON_SKIN_HIT_PERCENT // 100
        return hit

    def debug_info(self):
        """Design observability: why the world looks the way it does right now."""
        from .actions import describe_bucket, explain
        key = self.game.player.chunk
        spot_ctx, self_ctx = self.spot_context(key), self.self_context("after_location")
        lead_ctx = Context(biome=spot_ctx.biome, region=spot_ctx.region, region_def=spot_ctx.region_def,
                           placement="lead", unlocked=frozenset(self.unlocked),
                           knowledge=frozenset(self.knowledge), recipes=frozenset(self.recipes),
                           active_leads=frozenset(lead["action"] for lead in self.leads),
                           action_counts=self.journal["actions"], item_counts=self.journal["items"])
        region = self.region(key)
        current = self.game.world.peek(key)
        current_spots = self._spots(current) if current is not None else ()
        rolled = {spot.encounter for spot in current_spots}
        admitted = {spot.encounter for spot in current_spots if spot.id in self.admitted}
        screened = self.chunk_ident(key) in self.screened_chunks
        return {"world_seed": str(self.game.world.world_seed), "life": self.life,
                "chunk": self.chunk_ident(key), "region": region.id if region else None,
                "generator_version": self.game.world.generator_version,
                "region_parameters": {"canopy": region.canopy, "brush": region.brush,
                                      "landmark": region.landmark} if region else None,
                "knowledge": sorted(self.knowledge), "recipes": sorted(self.recipes),
                "journal": {"disabled": sorted(self.journal_disabled), "favor": dict(self.journal_favor)},
                "states": [{"id": r["id"], "state": r["state"], "admitted": r["id"] in admitted}
                           for r in (explain(a.id, replace(spot_ctx, spawned=a.id in rolled)
                                             if a.placement == "spot" else
                                             lead_ctx if a.placement == "lead" else
                                             self.self_context("need" if a.trigger == "need" else "after_location"))
                                     for a in BY_ID.values())],
                "unlocked": sorted(self.unlocked), "boon": self.boon, "mastery": dict(self.mastery),
                "spot_bucket": describe_bucket(spot_ctx),
                "spot_explanations": [explain(a.id, replace(spot_ctx, spawned=a.id in rolled,
                                                          admitted=(a.id in admitted) if screened else None))
                                      for a in BY_ID.values() if a.placement == "spot"],
                "leads": [dict(lead) for lead in self.leads],
                "lead_history": [dict(lead) for lead in self.lead_history[-12:]],
                "self_bucket": describe_bucket(self_ctx),
                "need": getattr(self._need_action(), "id", None),
                "why_not": [{"id": r["id"], "reasons": r["reasons"]}
                            for r in (explain(a.id, spot_ctx if a.placement == "spot" else
                                               lead_ctx if a.placement == "lead" else self_ctx)
                                      for a in BY_ID.values()) if not r["eligible"]],
                "windows": [{"id": i, "limit": limit, "active": self._active(i), "spawned": n}
                            for i, n, limit in self.bounty()],
                "drought": dict(self.drought), "pity_after": dict(PITY_CHUNKS),
                "screening": list(self.screen_log[-12:]), "stats": dict(self.stats),
                "recent_rolls": list(self.roll_log[-8:]),
                "currencies": {"dust": self.dust, "ash": self.ash, "blessing": self.blessing}}

    # ----- regions, known actions, contexts -----------------------------
    def region(self, key):
        """RegionDef of a chunk key (pure: world seed, biome, coordinates)."""
        cached = self._region_cache.get(key)
        if cached is None:
            chunk = self.game.world.peek(key)
            biome = chunk.asset.biome if chunk is not None else self.game.world.biome_for(key)
            cached = self.game.world.region_for(key)
            if len(self._region_cache) > 512:
                self._region_cache.clear()
            self._region_cache[key] = cached
        return cached

    def spot_context(self, key):
        chunk = self.game.world.peek(key)
        region = self.region(key)
        return Context(biome=chunk.asset.biome if chunk is not None else "dark_forest",
                       region=region.id if region else None, placement="spot",
                       region_def=region, unlocked=frozenset(self.unlocked),
                       knowledge=frozenset(self.knowledge), recipes=frozenset(self.recipes),
                       action_counts=self.journal["actions"], item_counts=self.journal["items"],
                       mastery=self.mastery, journal_disabled=frozenset(self.journal_disabled),
                       journal_favor=self.journal_favor)

    def self_context(self, trigger=None, visible=True):
        return Context(placement="self", unlocked=frozenset(self.unlocked),
                       knowledge=frozenset(self.knowledge), recipes=frozenset(self.recipes),
                       action_counts=self.journal["actions"], item_counts=self.journal["items"],
                       mastery=self.mastery, inventory=dict(self.inventory),
                       gear=frozenset(i for i in self.inventory if ITEMS[i].kind == "gear"),
                       hunger=self.hunger // POINT, food_carried=self._has_food(),
                       trigger=trigger, visible=visible,
                       flags=frozenset({"done:pray"} if self.prayers_this_life else ()))

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
        if task["type"] in SELF_ACTIONS:
            px, py = self._player()
            action = BY_ID[task["type"]]
            return {"encounter": action.id, "name": action.name, "kind": action.id if action.category == "reflect"
                    else action.category, "x": px, "y": py, "progress": progress}
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
        if self.anchor_ms is not None:
            return "anchor"
        if self.in_prologue:
            return "prologue"
        if self.task and self.task["type"] in SELF_ACTIONS:
            return "encounter"
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
                "blessing": self.blessing, "dust": self.dust, "ash": self.ash}

    def inventory_rows(self):
        return [{"id": item, "name": ITEMS[item].name, "kind": ITEMS[item].kind,
                 "glyph": ITEMS[item].glyph, "food": ITEMS[item].food, "count": count,
                 "slot": ITEMS[item].slot, "equipped": is_equipped(self.equipped, item)
                 if ITEMS[item].kind == "gear" else False}
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
        """Resident 3x3 chunks around the avatar (memoized while the cache is unchanged)."""
        center, world = self.game.player.chunk, self.game.world
        memo_key = (center, world.generation_count, world.resident_count, id(world))
        memo = getattr(self, "_resident_memo", None)
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

    @staticmethod
    def chunk_ident(key):
        return f"{key.dimension}:{key.x}:{key.y}"

    def _spots(self, chunk):
        """This life's rolled opportunities; geography itself holds no encounter map."""
        ident = self.chunk_ident(chunk.key)
        spots = tuple(EncounterSpot(spot_id(chunk.key, index), action, chunk.key, x, y)
                      for index, (action, x, y) in enumerate(self.spot_plans.get(ident, ())))
        extra = self.forced.get(self.chunk_ident(chunk.key))
        if not extra:
            return spots
        fkey = (chunk.key, self.life, tuple(extra), spots)
        hit = self._spot_cache.get(fkey)
        if hit is not None:
            return hit
        result = list(spots)
        for index, encounter in enumerate(extra):
            spot = forced_spot(chunk, encounter, index, taken=[(s.x, s.y) for s in result])
            if spot is not None:
                result.append(spot)
        self._spot_cache[fkey] = tuple(result)
        return self._spot_cache[fkey]

    def _live(self, chunk):
        """Spots this life's spawn windows admitted."""
        result = [spot for spot in self._spots(chunk) if spot.id in self.admitted]
        for lead in self.leads:
            if lead["chunk"] == self.chunk_ident(chunk.key) and lead["expires_ms"] > self.total_ms:
                result.append(EncounterSpot(lead["id"], lead["action"], chunk.key, lead["x"], lead["y"]))
        return result

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

    def _note(self, chunk_id, spot_id, encounter, result):
        self.screen_log.append({"life": self.life, "chunk": chunk_id, "spot": spot_id,
                                "action": encounter, "result": result})
        del self.screen_log[:-SCREEN_LOG_LIMIT]

    def _admit(self, ident, encounter, chunk_id="?"):
        limit = self.budget.get(encounter)
        if limit is not None:
            active = self._active(encounter)
            if active >= limit:
                self.stats["rejected"] += 1
                self._note(chunk_id, ident, encounter, f"rejected: window full ({active}/{limit} at once)")
                return False
            self.spawned[encounter] += 1
        self.admitted[ident] = encounter
        category = BY_ID[encounter].spawn_category
        if category:
            self.stats[f"{category}_spots"] += 1
        self._note(chunk_id, ident, encounter, "admitted")
        return True

    def _pity(self, chunk, chunk_id, category, taken):
        """Force one spot of a starved category into `chunk` (deterministic)."""
        ctx = self.spot_context(chunk.key)
        choices = [(a, w) for a, w in bucket(ctx) if a.spawn_category == category
                   and (self.budget.get(a.id) is None or self._active(a.id) < self.budget[a.id])]
        if not choices:
            self._note(chunk_id, None, None, f"pity {category}: nothing eligible (or its window is full)")
            return False
        roll = derive_seed(self.game.world.world_seed, "pity-v1", self.life, chunk_id, category) \
            % sum(w for _, w in choices)
        for action, w in choices:
            if roll < w:
                break
            roll -= w
        index = len(self.forced.get(chunk_id, ()))
        spot = forced_spot(chunk, action.id, index, taken=taken)
        if spot is None:
            self._note(chunk_id, None, action.id, f"pity {category}: no free cell")
            return False
        self.forced.setdefault(chunk_id, []).append(action.id)
        self.stats["pity"] += 1
        self._note(chunk_id, spot.id, action.id, f"pity {category} after {self.drought[category]} empty chunks")
        return self._admit(spot.id, action.id, chunk_id)

    def _screen(self):
        """Roll when the player enters a chunk, then apply windows and pity.
        Asset-spawned boars are always removed: enemies come only from fight spots."""
        for chunk in (self.game.current_chunk(),):
            ident = self.chunk_ident(chunk.key)
            if ident in self.screened_chunks:
                continue
            roll_seed = derive_seed(self.game.world.world_seed, "runtime-opportunity-v1",
                                    self.life, len(self.spot_plans), ident)
            context = self.spot_context(chunk.key)
            rolled = chunk_spots(chunk, life=self.life, context=context,
                                 roll_seed=roll_seed)
            self.spot_plans[ident] = [(s.encounter, s.x, s.y) for s in rolled]
            self.roll_log.append({"chunk": ident, "region": context.region,
                                  "bucket": [{"id": a.id, "base": a.weight,
                                              "region_percent": context.region_def.multiplier(a.id)
                                              if context.region_def else 100,
                                              "final": w} for a, w in bucket(context)],
                                  "result": [s.encounter for s in rolled]})
            del self.roll_log[:-12]
            self.screened_chunks.add(ident)
            self.stats["chunks"] += 1
            admitted = set()
            spots = self._spots(chunk)
            for spot in spots:
                if self._admit(spot.id, spot.encounter, ident):
                    admitted.add(BY_ID[spot.encounter].spawn_category)
            taken = [(s.x, s.y) for s in spots]
            for category in PITY_CHUNKS:
                if category in admitted:
                    self.drought[category] = 0
                    continue
                self.drought[category] += 1
                if self.drought[category] >= PITY_CHUNKS[category] and self._pity(chunk, ident, category, taken):
                    self.drought[category] = 0
                    taken = [(s.x, s.y) for s in self._spots(chunk)]
        for target in sorted(self.game.targets.values(), key=lambda t: t.id):
            if target.id.startswith("enc:") or target.id in self.screened_targets:
                continue
            self.screened_targets.add(target.id)
            target.hp = 0

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
        if isinstance(spot_id, str) and spot_id.startswith("lead:"):
            for lead in self.leads:
                if lead["id"] == spot_id and lead["expires_ms"] > self.total_ms:
                    key = ChunkKey(lead["dimension"], lead["chunk_x"], lead["chunk_y"])
                    if self.game.world.peek(key) is not None:
                        return EncounterSpot(spot_id, lead["action"], key, lead["x"], lead["y"])
            return None
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
        resident = self._resident()
        memo = getattr(self, "_grid_memo", None)
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

    def fight_damage(self, ring):
        """Health the avatar expects to lose beating one boar in `ring` (micro-points)."""
        hp = BY_ID["bramble_boar"].hp + min(ring, DANGER_RING_CAP)
        punches = _ceil_div(hp, self.punch_damage())
        return self.boar_hit(ChunkKey(self.dimension, ring, 0)) * (punches - 1)

    def frontier(self):
        """Deepest ring the auto-pilot is willing to explore: one boar fight there
        must cost at most COMFORT_DAMAGE_PERCENT of full health. Stronger lives
        (XP, gear, boons) push the frontier outward; hunger pushes one ring further."""
        ring = 1
        while ring < DANGER_RING_CAP and self.fight_damage(ring + 1) * 100 <= VITAL_MAX * COMFORT_DAMAGE_PERCENT:
            ring += 1
        if self.hunger <= EAT_AT and not self._has_food():
            ring += 1
        return ring

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

    def _apply_outcomes(self, action, source_id):
        """Resolve catalog outcomes after the journal count has advanced."""
        count = self.journal["actions"].get(action.id, 0)
        for index, outcome in enumerate(action.outcomes):
            if count < outcome.at_count:
                continue
            chance = outcome_chance(outcome, self.region(self.game.player.chunk))
            roll = derive_seed(self.game.world.world_seed, "action-outcome-v1", self.life,
                               action.id, source_id, index) % 100
            if roll >= chance:
                continue
            if outcome.kind == "knowledge":
                if outcome.id not in self.knowledge:
                    self.knowledge.add(outcome.id)
                    self._entry("lore", f"Learned {outcome.id.replace('_', ' ')}.", encounter=action.id)
            elif outcome.kind == "recipe":
                if outcome.id not in self.recipes:
                    self.recipes.add(outcome.id)
                    self._entry("lore", f"Discovered the {outcome.id.replace('_', ' ')} recipe.", encounter=action.id)
            elif outcome.kind == "lead":
                source = self._spot_by_id(source_id)
                if source is None:
                    key = self.game.player.chunk
                    sx, sy = self.game.player.x, self.game.player.y
                else:
                    key, sx, sy = source.chunk, source.x, source.y
                chunk = self.game.world.peek(key)
                if chunk is None:
                    continue
                spot = lead_spot(chunk, outcome.id, self.life, source_id, index, (sx, sy))
                if spot is None:
                    continue
                if any(row["id"] == spot.id for row in self.leads):
                    continue
                lead = {"id": spot.id, "action": outcome.id, "source": source_id,
                        "dimension": key.dimension, "chunk_x": key.x, "chunk_y": key.y,
                        "chunk": self.chunk_ident(key), "x": spot.x, "y": spot.y,
                        "expires_ms": self.total_ms + outcome.ttl_ms}
                self.leads.append(lead)
                self.lead_history.append({**lead, "status": "created"})
                self.lead_history = self.lead_history[-100:]
                self._entry("lore", f"A fresh {BY_ID[outcome.id].name.lower()} lead appeared.",
                            encounter=action.id)

    def _expire_leads(self):
        expired = [lead for lead in self.leads if lead["expires_ms"] <= self.total_ms]
        if not expired:
            return
        self.leads = [lead for lead in self.leads if lead["expires_ms"] > self.total_ms]
        for lead in expired:
            self.lead_history.append({**lead, "status": "expired"})
            self._entry("lore", f"The {BY_ID[lead['action']].name.lower()} lead went cold.")
        self.lead_history = self.lead_history[-100:]
        if self.task and self.task["type"] == "perform" and self.task["spot"] in {v["id"] for v in expired}:
            self.task = None
        if self.goal and self.goal.get("id") in {v["id"] for v in expired}:
            self.goal = None

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
        record_action(self.journal, entry.id)
        self._apply_outcomes(entry, ident)
        if ident.startswith("lead:"):
            for lead in self.leads:
                if lead["id"] == ident:
                    self.lead_history.append({**lead, "status": "completed"})
            self.leads = [lead for lead in self.leads if lead["id"] != ident]
            self.lead_history = self.lead_history[-100:]
        record_items(self.journal, items)
        self.stats["completed"] += 1
        if entry.category == "fight":
            self.stats["fights"] += 1
        if entry.category == "pray":
            self.stats["prayers"] += 1
        self._entry("encounter", entry.log, encounter=entry.id, attribute=entry.attribute,
                    xp=entry.xp, dim_xp=dim, items=items, blessing=entry.blessing)

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
        self.stats["eaten"] += 1
        self._entry("eat", f"Ate {ITEMS[item].name.lower()} (+{value} hunger, +{heal} health).",
                    items=[(item, -1)])
        return True

    def _die(self):
        lived = self.game.elapsed_ms // 1000
        lines = [f"{name.capitalize()} experience gained: {self.regular[name]}"
                 f" (dimensional +{self.life_gain[name]})" for name in ATTRIBUTES]
        cause = {"starvation": "Cause: starvation", "boar": "Cause: a bramble boar"}.get(self.cause, "Cause: exhaustion")
        bounty = ", ".join(f"{BY_ID[i].name.lower()} {n} (max {limit} at once)" for i, n, limit in self.bounty())
        carried = sum(economy.offer_value(i, n) for i, n in self.inventory.items())
        lines += [f"Forest bounty this life: {bounty}",
                  f"Spots found: {self.stats['food_spots']} food, {self.stats['enemy_spots']} boars"
                  f" ({self.stats['pity']} by pity), {self.stats['rejected']} turned away by caps",
                  f"Crafted {self.stats['crafted']}, ate {self.stats['eaten']}, prayed {self.stats['prayers']}",
                  f"Carrying items worth {carried} dust if offered, or "
                  f"{economy.rebirth_ash(self.inventory, self.depth)} ash if left to burn",
                  f"Blessing {self.blessing} - dust {self.dust} - ash {self.ash}",
                  f"Encounters completed: {len(self.completed)}",
                  f"Deepest ring reached: {self.depth} (best {self.best_depth})",
                  f"Survived: {lived // 60}m {lived % 60:02d}s", cause, "Returning to anchor..."]
        self.report = {"seq": self.sequence + 1, "life": self.life, "clock_ms": self.total_ms,
                       "title": f"Life {self.life} ends", "lines": lines}
        self._entry("life", f"Life {self.life} ended. The anchor pulls you back.")
        record_death(self.journal, self.cause or "exhaustion", self.game.elapsed_ms)
        config = {name: getattr(self.game, name) for name in (
            "movement_interval_ms", "animation_rate_percent", "attack_rate_percent", "attack_damage")}
        press = self.game.step_on_press
        previous_world = self.game.world
        world = self._current_generator_world(self.game.world)
        self.game = Exploration(world, self.dimension, animations=self.game.animations, **config)
        self.game.step_on_press = press
        if world is not previous_world:
            self.anchor = self._anchor()
            self._entry("rebirth", "While the anchor held you, the forest grew back in a new shape.")
        self.anchor_ms = ANCHOR_COUNTDOWN_MS
        self.anchor_wait = False
        self.leads = []
        self.task = None
        self.goal = None
        self._field_cache.clear()

    def _current_generator_world(self, world):
        """Worlds pinned to an older generator (homogeneous v1 Forest) are regenerated
        from the same seed with the current region-shaped generator between lives.
        Mid-life the pinned world never changes, so a save always replays exactly."""
        if world.generator_version >= GENERATOR_VERSION:
            return world
        fresh = WorldRepository(world.world_seed, world.dimensions, world.catalog, world.cache_limit)
        for cache in (self._region_cache, self._spot_cache, self._field_cache):
            cache.clear()
        self._graph_cache = None
        self._grid_memo = None
        self._resident_memo = None
        return fresh

    ANCHOR_ACTIONS = ("trade", "begin_life", "unlock", "boon", "mastery",
                      "journal_toggle", "journal_favor")

    def anchor_offers(self):
        """Anchor shop rows (economy.offers) for the UI and debugging."""
        return economy.offers(self)

    def anchor_action(self, action):
        """Between lives: offer an item stack, buy an unlock / boon / mastery, or begin."""
        if self.anchor_ms is None or type(action) is not dict:
            raise ValueError("anchor action requires the anchor space")
        kind = action.get("type")
        if kind == "begin_life" and set(action) == {"type"}:
            self._begin_life()
            return
        if kind == "journal_toggle" and set(action) == {"type", "id", "enabled"}:
            ident, enabled = action["id"], action["enabled"]
            if ident not in BY_ID or BY_ID[ident].placement != "spot" or type(enabled) is not bool \
                    or self.mastery.get(ident, 0) < JOURNAL_TOGGLE_MASTERY:
                raise ValueError("journal toggle requires spot mastery 2")
            if enabled:
                self.journal_disabled.discard(ident)
            else:
                self.journal_disabled.add(ident)
            self.anchor_wait = True
            self._entry("purchase", f"Journal: {BY_ID[ident].name} {'enabled' if enabled else 'disabled'}.")
            return
        if kind == "journal_favor" and set(action) == {"type", "id", "mode"}:
            ident, mode = action["id"], action["mode"]
            if ident not in BY_ID or BY_ID[ident].placement != "spot" \
                    or mode not in ("normal", "favor", "suppress") \
                    or self.mastery.get(ident, 0) < JOURNAL_FAVOR_MASTERY:
                raise ValueError("journal odds require spot mastery 3")
            if mode == "normal":
                self.journal_favor.pop(ident, None)
            else:
                self.journal_favor[ident] = mode
            self.anchor_wait = True
            self._entry("purchase", f"Journal: {BY_ID[ident].name} odds set to {mode}.")
            return
        if kind in ("unlock", "boon", "mastery") and set(action) == {"type", "id"} and type(action["id"]) is str:
            row = economy.purchase(self, kind, action["id"])
            self.anchor_wait = True
            self._entry("purchase", f"Bought {row['name']} for {row['cost']} {row['currency']}.")
            return
        if kind != "trade" or set(action) != {"type", "item"} or action["item"] not in ITEMS:
            raise ValueError("invalid anchor action")
        item = action["item"]
        count = self.inventory.pop(item, 0)
        if count:
            self.equipped = {slot: gear for slot, gear in self.equipped.items() if gear != item}
            gained = economy.offer_value(item, count)
            self.dust += gained
            self.anchor_wait = True
            self._entry("trade", f"Offered {count} {ITEMS[item].name.lower()} for {gained} dimensional dust.",
                        items=[(item, -count)])

    def _begin_life(self):
        burned = dict(self.inventory)
        ash = economy.rebirth_ash(burned, self.depth)
        self.ash += ash
        self.anchor_ms = None
        self.anchor_wait = False
        self.boon, self.boon_next = self.boon_next, None
        self.life += 1
        self._new_life_state()
        items = ", ".join(f"{n} {ITEMS[i].name.lower()}" for i, n in burned.items()) or "nothing"
        self._entry("rebirth", f"Rebirth: burned {items} and the road behind you into {ash} ash.",
                    items=[(i, -n) for i, n in burned.items()])

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
                if entry.category == "fight" and spot.id not in self.game.targets and spot.id not in self.completed:
                    hp = entry.hp + min(self.ring(spot.chunk), DANGER_RING_CAP)
                    self.game.targets[spot.id] = Target(spot.id, spot.chunk, spot.x, spot.y, hp)
        kinds = None
        for t in sorted(self.game.targets.values(), key=lambda t: t.id):
            if t.hp == 0 and t.id not in self.completed and t.id in self.admitted:
                kinds = kinds or self.target_kinds()
                self._reward(t.id, BY_ID[kinds[t.id]])
        self._pursue()
        self._eat()
        if not self._goal_valid():
            self.goal = None
        if self.goal and self.goal["kind"] == "wander" and not self.task and self._candidates():
            found = self._best_candidate(self._candidate_field())
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
        self.monster_ms += ms

    def unarmed_target(self):
        """The nearest admitted enemy within the current unarmed hitbox reach."""
        px, py = self._player()
        candidates = []
        for target in self.game.targets.values():
            if target.hp <= 0 or target.id not in self.admitted or target.chunk.dimension != self.dimension:
                continue
            tx, ty = self._global(target.chunk, target.x, target.y)
            distance = abs(tx - px) + abs(ty - py)
            if 0 < distance <= UNARMED_REACH:
                candidates.append((distance, target.id, tx, ty))
        return min(candidates) if candidates else None

    def _manual_combat_command(self, command, auto_attack):
        if not auto_attack or command.move or command.attack or self.task:
            return command
        target = self.unarmed_target()
        if target is None:
            return command
        _, _, tx, ty = target
        px, py = self._player()
        direction = next(d for d, delta in DELTAS.items() if delta == (tx - px, ty - py))
        # Release the attack edge during the animation; a later tick can punch again.
        return InputCommand(attack=self.game.player.animation != "attack" and not self.game.attack_held,
                            face=direction)

    def advance_manual(self, milliseconds, command=InputCommand(), *, auto_attack=False):
        """Player chooses movement; expedition still owns time, spots, vitals and enemies."""
        integer(milliseconds, "elapsed milliseconds", 0)
        if self.anchor_ms is not None:
            return self.advance(milliseconds)
        if self.in_prologue:
            return self.advance(milliseconds)
        if milliseconds == 0:
            self._settle()
            self.game.advance(0, self._manual_combat_command(command, auto_attack))
            return
        remaining = milliseconds
        while remaining:
            self._expire_leads()
            if self._settle():
                continue
            if self.anchor_ms is not None:
                self.advance(remaining)
                return
            cap = min(remaining, self._vitals_limit(), MONSTER_STEP_MS - self.monster_ms)
            if self.leads:
                cap = min(cap, min(lead["expires_ms"] - self.total_ms for lead in self.leads))
            task = self.task
            if task:
                cap = min(cap, task["duration_ms"] - task["elapsed_ms"])
            self._run(cap, InputCommand() if task else self._manual_combat_command(command, auto_attack))
            remaining -= cap
            if task:
                task["elapsed_ms"] += cap
                if task["elapsed_ms"] == task["duration_ms"]:
                    self.task = None
                    if task["type"] == "perform":
                        spot = self._spot_by_id(task["spot"])
                        if spot is not None and spot.id not in self.completed:
                            self._reward(spot.id, BY_ID[spot.encounter])
                            self._after_location(spot, True)
                    elif task["type"] in SELF_ACTIONS:
                        self._complete_self(BY_ID[task["type"]])
                    self.goal = None
        self._settle()

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
            self._boar_bites(target)

    def _near_camp(self, gx, gy):
        """Boars never chase into the anchor camp: it is where a hurt avatar recovers."""
        return self.anchor is not None and abs(gx - self.anchor[0]) + abs(gy - self.anchor[1]) <= CAMP_SAFE_RADIUS

    def _boar_bites(self, target):
        """One boar attack on the avatar (its counter feeds the client's lunge animation)."""
        self.health = max(0, self.health - self.boar_hit(target.chunk))
        self.strikes[target.id] = self.strikes.get(target.id, 0) + 1
        if self.health == 0:
            self.cause = "boar"

    def _pursue(self):
        """Live boars within BOAR_AGGRO_RADIUS charge the avatar one step per MONSTER_STEP_MS.
        Reaching it, a boar bites first and interrupts whatever the avatar was doing."""
        if self.monster_ms < MONSTER_STEP_MS:
            return
        self.monster_ms -= MONSTER_STEP_MS
        if self.in_prologue:
            return
        px, py = self._player()
        if self._near_camp(px, py) or not any(   # cheap check first: most steps nothing is close
                t.hp > 0 and t.id in self.admitted and t.chunk.dimension == self.dimension
                and sum(map(abs, (a - b for a, b in zip(self._global(t.chunk, t.x, t.y), (px, py))))) <= BOAR_AGGRO_RADIUS
                for t in self.game.targets.values()):
            return
        grid = self._grid()
        field = self._field({(px, py)}, limit=BOAR_PATH_LIMIT)
        for target in sorted(self.game.targets.values(), key=lambda t: t.id):
            if target.hp == 0 or target.id not in self.admitted or target.chunk.dimension != self.dimension:
                continue
            tx, ty = self._global(target.chunk, target.x, target.y)
            distance = abs(tx - px) + abs(ty - py)
            if distance > BOAR_AGGRO_RADIUS or self._near_camp(px, py) or self._near_camp(tx, ty):
                continue
            if distance > 1:
                choices = []
                blocked = self._blocked()
                for direction in DIRECTIONS:
                    dx, dy = DELTAS[direction]
                    nx, ny = tx + dx, ty + dy
                    w, h = self._dims()
                    key = ChunkKey(self.dimension, nx // w, ny // h)
                    if (nx, ny) != (px, py) and key in self.game.initialized_chunks and \
                            self._can_move(grid, blocked, tx, ty, direction) and (nx, ny) in field:
                        choices.append((field[nx, ny], direction, nx, ny, key))
                if choices:
                    _, _, tx, ty, key = min(choices)
                    target.chunk, target.x, target.y = key, tx % w, ty % h
                    self._field_cache.clear()
                    distance = abs(tx - px) + abs(ty - py)
            # A boar that catches a fleeing avatar gores it in passing but does not stop it;
            # retreat is safer than a losing fight, never free.
            if distance == 1 and (self.goal or {}).get("kind") == "home":
                self._boar_bites(target)
                if self.health == 0:
                    break
                continue
            # A second boar waits its turn.
            if distance == 1 and (self.goal or {}).get("kind") != "target":
                self.task = None
                self._boar_bites(target)
                if self.health > self.fight_damage(self.ring(target.chunk)):
                    self.goal = {"kind": "target", "id": target.id, "x": tx, "y": ty}
                    self._entry("ambush", "A bramble boar charges and gores you - fists up!")
                else:   # this fight would kill: outrun it to the camp (boars are slower)
                    self.goal = {"kind": "home", "id": None, "x": self.anchor[0], "y": self.anchor[1]}
                    self._entry("ambush", "A bramble boar gores you - too hurt to fight, you run for the camp!")
                break

    def _start_self(self, action):
        duration = action.duration_ms if action.category in ("reflect", "pray") \
            else scaled_ms(action.duration_ms, self.speed(action.attribute))
        self.task = {"type": action.id, "spot": None, "elapsed_ms": 0, "duration_ms": duration}

    crafting_enabled = True   # simulation policy switch (world/simulate.py "hoard"); not saved

    def _need_action(self, visible=True):
        """Need-driven crafting policy: the first eligible recipe whose need holds."""
        if not self.crafting_enabled:
            return None
        ctx = self.self_context("need", visible)
        for action in NEED_ACTIONS:
            if reasons_against(action, ctx):
                continue
            return action
        return None

    def _after_location(self, spot, allow_prayer):
        """A need-driven craft, else a roll in the after-location bucket (think,
        contemplate, a rare prayer during live play) or a short pause."""
        need = self._need_action(allow_prayer)
        if need is not None:
            self._start_self(need)
            return
        entries = bucket(self.self_context("after_location", allow_prayer))
        total = sum(w for _, w in entries) + AFTER_LOCATION_REST_WEIGHT
        roll = derive_seed(self.game.world.world_seed, "after-location-v6", self.life, spot.id) % total
        for action, w in entries:
            if roll < w:
                self._start_self(action)
                return
            roll -= w
        self.task = {"type": "pause", "spot": None, "elapsed_ms": 0,
                     "duration_ms": PAUSE_AFTER_ACTIVITY_MS}

    def _complete_self(self, action):
        """Finish a self action: pay costs, then XP, loot, gear, blessing, log."""
        if any(self.inventory.get(item, 0) < count for item, count in action.cost):
            return   # the ingredients were eaten or lost meanwhile: nothing happens
        for item, count in action.cost:
            self.inventory[item] -= count
            if not self.inventory[item]:
                del self.inventory[item]
        items = [(item, -count) for item, count in action.cost]
        if action.effect:
            if self._add_item(action.effect, 1):
                items.append((action.effect, 1))
                self.equipped = equip_item(self.equipped, self.inventory, action.effect)
        seed = derive_seed(self.game.world.world_seed, "self-loot", self.life, action.id, self.sequence)
        items += [(item, kept) for item, count in roll_loot(action, seed) if (kept := self._add_item(item, count))]
        record_action(self.journal, action.id)
        self._apply_outcomes(action, f"self:{self.sequence}")
        record_items(self.journal, [(i, n) for i, n in items if n > 0])
        dim = action.xp // DIMENSIONAL_DIVISOR
        if action.xp:
            self.regular[action.attribute] += action.xp
            self.dimensional[action.attribute] += dim
            self.life_gain[action.attribute] += dim
        if action.category == "craft":
            self.stats["crafted"] += 1
            text = action.log if len(items) > len(action.cost) else action.log + " Nothing came of it."
            self._entry("craft", text, attribute=action.attribute if action.xp else None,
                        xp=action.xp, dim_xp=dim, items=items)
        elif action.category == "pray":
            self.prayers_this_life += 1
            self.stats["prayers"] += 1
            self.blessing += action.blessing
            self._entry("blessing", action.log, blessing=action.blessing)

    def advance(self, milliseconds, *, allow_prayer=True):
        integer(milliseconds, "elapsed milliseconds", 0)
        if type(allow_prayer) is not bool:
            raise ValueError("allow_prayer must be boolean")
        saved_press = self.game.step_on_press
        self.game.step_on_press = False  # auto-pilot steps on interval boundaries only
        try:
            remaining, events = milliseconds, 0
            while True:
                events += 1
                if events > MAX_EVENTS_PER_ADVANCE:
                    raise RuntimeError("auto-pilot made no progress")
                if self.anchor_ms is not None:
                    if remaining == 0 or self.anchor_wait:
                        break
                    step = min(remaining, self.anchor_ms)
                    self.anchor_ms -= step
                    self.total_ms += step
                    remaining -= step
                    if self.anchor_ms == 0:
                        self._begin_life()
                    continue
                self._expire_leads()
                if self._settle():
                    self.game.step_on_press = False
                    continue
                if remaining == 0:
                    break
                game = self.game
                cap = min(remaining, self._vitals_limit(), MONSTER_STEP_MS - self.monster_ms)
                if self.leads:
                    cap = min(cap, min(lead["expires_ms"] - self.total_ms for lead in self.leads))
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
                            if spot is not None:
                                self._after_location(spot, allow_prayer)
                        elif done["type"] in SELF_ACTIONS:
                            self._complete_self(BY_ID[done["type"]])
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
                    need = self._need_action(allow_prayer)
                    if need is not None:
                        self._start_self(need)
                        continue
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
                field = self._field(goals, until=here)
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
                "equipped": dict(self.equipped), "knowledge": sorted(self.knowledge),
                "recipes": sorted(self.recipes), "journal_disabled": sorted(self.journal_disabled),
                "journal_favor": dict(sorted(self.journal_favor.items())),
                "leads": [dict(lead) for lead in self.leads],
                "lead_history": [dict(lead) for lead in self.lead_history],
                "hunger": self.hunger, "health": self.health,
                "food_cooldown_ms": self.food_cooldown_ms, "cause": self.cause,
                "depth": self.depth, "best_depth": self.best_depth, "blessing": self.blessing,
                "dust": self.dust, "ash": self.ash, "unlocked": sorted(self.unlocked),
                "mastery": dict(sorted(self.mastery.items())), "boon": self.boon, "boon_next": self.boon_next,
                "stats": dict(self.stats), "drought": dict(self.drought), "journal": validate_journal(self.journal),
                "forced": {k: list(v) for k, v in sorted(self.forced.items())},
                "spot_plans": {k: [list(row) for row in v] for k, v in sorted(self.spot_plans.items())},
                "anchor_ms": self.anchor_ms, "anchor_wait": self.anchor_wait,
                "monster_ms": self.monster_ms, "prayers_this_life": self.prayers_this_life,
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
                   "food_cooldown_ms", "cause", "depth", "best_depth", "blessing", "dust", "ash", "unlocked",
                   "mastery", "boon", "boon_next", "stats", "drought", "forced", "journal", "anchor_ms", "anchor_wait",
                   "monster_ms", "prayers_this_life", "budget", "spawned",
                   "admitted", "screened_chunks", "screened_targets", "log", "sequence",
                   "decisions", "skills", "report", "task", "goal", "equipped", "knowledge",
                   "recipes", "journal_disabled", "journal_favor", "leads", "lead_history", "spot_plans")

    V8_FIELDS = ("equipped", "knowledge", "recipes", "journal_disabled", "journal_favor",
                 "leads", "lead_history")
    V9_FIELDS = ("spot_plans",)

    @classmethod
    def from_dict(cls, data):
        if isinstance(data, dict) and data.get("schema_version") == 1:
            return cls._from_v1(data)
        if isinstance(data, dict) and data.get("schema_version") == 2:
            data = cls._upgrade_v2(data)
        if isinstance(data, dict) and data.get("schema_version") == 3:
            data = cls._upgrade_v3(data)
        if isinstance(data, dict) and data.get("schema_version") == 4:
            data = cls._upgrade_v4(data)
        if isinstance(data, dict) and data.get("schema_version") == 5:
            data = cls._upgrade_v5(data)
        if isinstance(data, dict) and data.get("schema_version") == 6:
            data = cls._upgrade_v6(data)
        if isinstance(data, dict) and data.get("schema_version") == 7:
            data = cls._upgrade_v7(data)
        if isinstance(data, dict) and data.get("schema_version") == 8:
            data = cls._upgrade_v8(data)
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
            result.equipped = validate_equipped(data["equipped"], inventory)
            for name in ("knowledge", "recipes", "journal_disabled"):
                values = data[name]
                if type(values) is not list or len(values) != len(set(values)) or any(
                        type(value) is not str for value in values):
                    raise ValueError(f"invalid {name}")
                setattr(result, name, set(values))
            if type(data["journal_favor"]) is not dict or any(
                    key not in BY_ID or value not in ("favor", "suppress")
                    for key, value in data["journal_favor"].items()):
                raise ValueError("invalid journal favor")
            result.journal_favor = dict(data["journal_favor"])
            if any(key not in BY_ID or BY_ID[key].placement != "spot" for key in result.journal_disabled):
                raise ValueError("invalid journal disabled")
            for name in ("leads", "lead_history"):
                values = data[name]
                if type(values) is not list or len(values) > 1000 or any(type(v) is not dict for v in values):
                    raise ValueError(f"invalid {name}")
                if name == "leads" and len({v.get("id") for v in values}) != len(values):
                    raise ValueError("duplicate leads")
                setattr(result, name, [_validated_lead(v, result.game.world, history=name == "lead_history")
                                       for v in values])
            result.hunger = integer(data["hunger"], "hunger", 0, VITAL_MAX)
            result.health = integer(data["health"], "health", 0, VITAL_MAX)
            result.food_cooldown_ms = integer(data["food_cooldown_ms"], "food cooldown", 0, FOOD_COOLDOWN_MS)
            if data["cause"] not in (None, "starvation", "boar"):
                raise ValueError("invalid death cause")
            result.cause = data["cause"]
            result.depth = integer(data["depth"], "depth", 0)
            result.best_depth = integer(data["best_depth"], "best depth", result.depth)
            result.blessing = integer(data["blessing"], "blessing power", 0)
            result.dust = integer(data["dust"], "dimensional dust", 0)
            result.ash = integer(data["ash"], "ash", 0)
            if type(data["unlocked"]) is not list or any(u not in UNLOCKS for u in data["unlocked"]) \
                    or len(set(data["unlocked"])) != len(data["unlocked"]):
                raise ValueError("invalid unlocks")
            result.unlocked = set(data["unlocked"])
            if type(data["mastery"]) is not dict or any(a not in economy.MASTERABLE for a in data["mastery"]):
                raise ValueError("invalid mastery")
            result.mastery = {a: integer(v, "mastery", 1, 3) for a, v in data["mastery"].items()}
            for name in ("boon", "boon_next"):
                if data[name] is not None and data[name] not in BOONS:
                    raise ValueError(f"invalid {name}")
            result.boon, result.boon_next = data["boon"], data["boon_next"]
            if type(data["stats"]) is not dict or set(data["stats"]) != set(STAT_KEYS):
                raise ValueError("invalid life stats")
            result.stats = {k: integer(v, "life stat", 0) for k, v in data["stats"].items()}
            if type(data["drought"]) is not dict or set(data["drought"]) != set(PITY_CHUNKS):
                raise ValueError("invalid drought counters")
            result.drought = {k: integer(v, "drought", 0, 1000) for k, v in data["drought"].items()}
            forced = data["forced"]
            if type(forced) is not dict or any(type(v) is not list or any(e not in BY_ID or BY_ID[e].placement != "spot"
                                                                          for e in v) for v in forced.values()):
                raise ValueError("invalid pity spots")
            result.forced = {k: list(v) for k, v in forced.items()}
            plans = data["spot_plans"]
            if type(plans) is not dict or len(plans) > 100000:
                raise ValueError("invalid spot plans")
            result.spot_plans = {}
            for ident, rows in plans.items():
                if type(ident) is not str or type(rows) is not list or len(rows) > 3:
                    raise ValueError("invalid spot plan")
                parts = ident.split(":")
                if len(parts) != 3 or parts[0] not in {d.id for d in result.game.world.dimensions}:
                    raise ValueError("invalid spot plan chunk")
                try:
                    key = ChunkKey(parts[0], int(parts[1]), int(parts[2]))
                except ValueError as exc:
                    raise ValueError("invalid spot plan chunk") from exc
                if result.chunk_ident(key) != ident:
                    raise ValueError("noncanonical spot plan chunk")
                spec = next(d for d in result.game.world.dimensions if d.id == key.dimension)
                for row in rows:
                    if (type(row) is not list or len(row) != 3 or row[0] not in BY_ID or
                            BY_ID[row[0]].placement != "spot"):
                        raise ValueError("invalid spot plan row")
                    integer(row[1], "spot x", 0, spec.width - 1)
                    integer(row[2], "spot y", 0, spec.height - 1)
                result.spot_plans[ident] = [tuple(row) for row in rows]
            result.journal = validate_journal(data["journal"])
            result.monster_ms = min(integer(data["monster_ms"], "monster clock", 0, LEGACY_MONSTER_MAX_MS),
                                    MONSTER_STEP_MS - 1)
            result.prayers_this_life = integer(data["prayers_this_life"], "prayers this life", 0, 1)
            result.anchor_ms = data["anchor_ms"]
            if result.anchor_ms is not None:
                integer(result.anchor_ms, "anchor countdown", 1, ANCHOR_COUNTDOWN_MS)
            if type(data["anchor_wait"]) is not bool or (data["anchor_wait"] and result.anchor_ms is None):
                raise ValueError("invalid anchor wait")
            result.anchor_wait = data["anchor_wait"]
            if data["budget"] is None:   # upgraded save: roll this life's windows now
                result._reset_spawns()
                result.forced = {}
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
                if set(result.spot_plans) != result.screened_chunks:
                    raise ValueError("spot plans must match screened chunks")
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
                if task["type"] not in TASK_TYPES or (task["type"] in SELF_ACTIONS and task["spot"] is not None):
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

    V6_FIELDS = ("ash", "unlocked", "mastery", "boon", "boon_next", "stats", "drought", "forced", "journal")

    @classmethod
    def _v6_defaults(cls):
        return {"ash": 0, "unlocked": [], "mastery": {}, "boon": None, "boon_next": None,
                "stats": {k: 0 for k in STAT_KEYS}, "drought": {k: 0 for k in PITY_CHUNKS}, "forced": {},
                "journal": new_journal()}

    @classmethod
    def _v8_defaults(cls):
        return {"equipped": {}, "knowledge": [], "recipes": [], "journal_disabled": [],
                "journal_favor": {}, "leads": [], "lead_history": []}

    @classmethod
    def _upgrade_v6(cls, data):
        """Schema 6 -> 7 adds the lifetime journal (empty: earlier lives were not counted)."""
        fields(data, tuple(name for name in cls.SAVE_FIELDS if name not in ("journal", *cls.V8_FIELDS,
                                                                            *cls.V9_FIELDS)))
        return {**data, "schema_version": 7, "journal": new_journal()}

    @classmethod
    def _upgrade_v7(cls, data):
        """New action pool/regions: preserve earned progress, reroll uncompleted spots."""
        fields(data, tuple(name for name in cls.SAVE_FIELDS if name not in (*cls.V8_FIELDS, *cls.V9_FIELDS)))
        if data["encounters"] != "encounters-v6":
            raise ValueError("unsupported expedition save")
        exploration = dict(data["exploration"])
        exploration["targets"] = [t for t in exploration["targets"] if not str(t["id"]).startswith("enc:")]
        exploration["hit_targets"] = [t for t in exploration["hit_targets"] if not str(t).startswith("enc:")]
        task = data["task"]
        if isinstance(task, dict) and task.get("type") == "perform":
            task = None
        goal = data["goal"]
        if isinstance(goal, dict) and goal.get("kind") in ("spot", "target"):
            goal = None
        inventory = dict(data["inventory"])
        equipped = {ITEMS[item].slot: item for item in inventory if ITEMS[item].kind == "gear"}
        return {**data, "schema_version": SCHEMA_VERSION, "encounters": ENCOUNTER_VERSION,
                "exploration": exploration, "completed": [c for c in data["completed"]
                                                        if not str(c).startswith("enc:")],
                "task": task, "goal": goal, "forced": {}, "budget": None, "spawned": None,
                "admitted": None, "screened_chunks": None, "screened_targets": None,
                "equipped": equipped, "knowledge": [], "recipes": [], "journal_disabled": [],
                "journal_favor": {}, "leads": [], "lead_history": [], "spot_plans": {}}

    @classmethod
    def _upgrade_v8(cls, data):
        """Existing v8 lives keep earned progress; affected encounter plans reroll on entry."""
        fields(data, tuple(name for name in cls.SAVE_FIELDS if name not in cls.V9_FIELDS))
        if data["encounters"] != "encounters-v7":
            raise ValueError("unsupported expedition save")
        exploration = dict(data["exploration"])
        exploration["targets"] = [t for t in exploration["targets"] if not str(t["id"]).startswith("enc:")]
        exploration["hit_targets"] = [t for t in exploration["hit_targets"] if not str(t).startswith("enc:")]
        task = data["task"]
        if isinstance(task, dict) and task.get("type") == "perform":
            task = None
        goal = data["goal"]
        if isinstance(goal, dict) and goal.get("kind") in ("spot", "target"):
            goal = None
        return {**data, "schema_version": SCHEMA_VERSION, "encounters": ENCOUNTER_VERSION,
                "exploration": exploration, "completed": [c for c in data["completed"]
                                                        if not str(c).startswith("enc:")],
                "task": task, "goal": goal, "forced": {}, "budget": None, "spawned": None,
                "admitted": None, "screened_chunks": None, "screened_targets": None,
                "spot_plans": {}}

    @classmethod
    def rebuilt(cls, old, game):
        """A brand-new world (`game`) for an existing expedition: keeps everything that
        persists across lives (dimensional XP, currencies, unlocks, mastery, journal,
        skills, the boon chosen for the next life) and starts the next life there,
        without the prologue. Used by the hosted "New world, keep progress" button."""
        new = cls(game, skills=old.skills, fresh=False)
        new.dimensional = dict(old.dimensional)
        for name in ("blessing", "dust", "ash", "best_depth", "total_ms", "sequence", "decisions"):
            setattr(new, name, getattr(old, name))
        new.unlocked, new.mastery = set(old.unlocked), dict(old.mastery)
        new.knowledge, new.recipes = set(old.knowledge), set(old.recipes)
        new.journal_disabled, new.journal_favor = set(old.journal_disabled), dict(old.journal_favor)
        new.journal = validate_journal(old.journal)
        new.log = [dict(e) for e in old.log]
        new.life = old.life + 1
        new.boon, new.boon_next = old.boon_next, None
        new._new_life_state()
        new._screen()
        new._entry("rebirth", "The world was rebuilt. A new forest, the same soul.")
        return new

    @classmethod
    def _upgrade_v5(cls, data):
        """encounters-v5 saves keep XP, blessing, dust, vitals and inventory; spots re-roll
        under the v6 action buckets (this life's spot plans and windows are rebuilt)."""
        fields(data, tuple(name for name in cls.SAVE_FIELDS if name not in (*cls.V6_FIELDS, *cls.V8_FIELDS,
                                                                            *cls.V9_FIELDS)))
        if data["encounters"] != "encounters-v5":
            raise ValueError("unsupported expedition save")
        exploration = dict(data["exploration"])
        try:
            exploration["targets"] = [t for t in exploration["targets"] if not str(t["id"]).startswith("enc:")]
            exploration["hit_targets"] = [t for t in exploration["hit_targets"] if not str(t).startswith("enc:")]
            completed = [c for c in data["completed"] if not str(c).startswith("enc:")]
            log = [dict(e, encounter=e["encounter"] if e["encounter"] in BY_ID else None) for e in data["log"]]
        except (TypeError, KeyError) as exc:
            raise ValueError("malformed expedition save") from exc
        task = data["task"]
        if isinstance(task, dict) and task.get("type") == "perform":
            task = None
        goal = data["goal"] if isinstance(data["goal"], dict) and data["goal"].get("kind") in ("wander", "home") else None
        return {**data, **cls._v6_defaults(), **cls._v8_defaults(), "schema_version": SCHEMA_VERSION, "encounters": ENCOUNTER_VERSION,
                "exploration": exploration, "completed": completed, "log": log, "task": task, "goal": goal,
                "budget": None, "spawned": None, "admitted": None, "screened_chunks": None,
                "screened_targets": None, "spot_plans": {}}

    @classmethod
    def _upgrade_v4(cls, data):
        """V4 locations and shrine rolls are replaced without erasing earned XP."""
        fields(data, tuple(name for name in cls.SAVE_FIELDS if name not in
                           ("monster_ms", "prayers_this_life", *cls.V6_FIELDS, *cls.V8_FIELDS,
                            *cls.V9_FIELDS)))
        if data["encounters"] != "encounters-v4":
            raise ValueError("unsupported expedition save")
        exploration = dict(data["exploration"])
        try:
            exploration["targets"] = [t for t in exploration["targets"] if not str(t["id"]).startswith("enc:")]
            exploration["hit_targets"] = [t for t in exploration["hit_targets"] if not str(t).startswith("enc:")]
            completed = [c for c in data["completed"] if not str(c).startswith("enc:")]
            log = [dict(entry, encounter=None if entry["encounter"] == "wayside_shrine" else entry["encounter"])
                   for entry in data["log"]]
        except (TypeError, KeyError) as exc:
            raise ValueError("malformed expedition save") from exc
        task = data["task"]
        if isinstance(task, dict) and task.get("type") == "perform":
            task = None
        return {**data, "schema_version": SCHEMA_VERSION, "encounters": ENCOUNTER_VERSION,
                "exploration": exploration, "completed": completed, "log": log,
                "task": task, "goal": None, "budget": None, "spawned": None,
                "admitted": None, "screened_chunks": None, "screened_targets": None,
                "monster_ms": 0, "prayers_this_life": 0, **cls._v6_defaults(), **cls._v8_defaults(),
                "spot_plans": {}}

    @classmethod
    def _upgrade_v3(cls, data):
        """New encounter locations change spot rolls; retain earned progress only."""
        fields(data, tuple(name for name in cls.SAVE_FIELDS if name not in
                           ("dust", "anchor_ms", "anchor_wait", "monster_ms", "prayers_this_life", *cls.V6_FIELDS,
                            *cls.V8_FIELDS, *cls.V9_FIELDS)))
        if data["encounters"] != "encounters-v3":
            raise ValueError("unsupported expedition save")
        exploration = dict(data["exploration"])
        try:
            exploration["targets"] = [t for t in exploration["targets"] if not str(t["id"]).startswith("enc:")]
            exploration["hit_targets"] = [t for t in exploration["hit_targets"] if not str(t).startswith("enc:")]
            completed = [c for c in data["completed"] if not str(c).startswith("enc:")]
            log = [dict(entry, encounter=None if entry["encounter"] == "wayside_shrine" else entry["encounter"])
                   for entry in data["log"]]
        except (TypeError, KeyError) as exc:
            raise ValueError("malformed expedition save") from exc
        task = data["task"]
        if isinstance(task, dict) and task.get("type") == "perform":
            task = None
        return {**data, "schema_version": SCHEMA_VERSION, "encounters": ENCOUNTER_VERSION,
                "exploration": exploration, "completed": completed, "log": log, "task": task, "goal": None,
                "budget": None, "spawned": None, "admitted": None,
                "screened_chunks": None, "screened_targets": None,
                "dust": 0, "anchor_ms": None, "anchor_wait": False,
                "monster_ms": 0, "prayers_this_life": 0, **cls._v6_defaults(), **cls._v8_defaults(),
                "spot_plans": {}}

    @classmethod
    def _upgrade_v2(cls, data):
        """encounters-v2 saves keep progress, vitals and inventory; this life's spots
        re-roll under v4 (no prologue, fresh spawn windows, spot plans dropped)."""
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
                "screened_chunks": None, "screened_targets": None,
                "dust": 0, "anchor_ms": None, "anchor_wait": False,
                "monster_ms": 0, "prayers_this_life": 0, **cls._v6_defaults(), **cls._v8_defaults(),
                "spot_plans": {}}

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
