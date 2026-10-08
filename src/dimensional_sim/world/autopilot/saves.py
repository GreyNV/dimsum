"""Save serialization, validation and upgrades from older schemas.

to_dict() is canonical (sorted where order is not meaningful) so a save, a reload
and a re-save are byte-identical. from_dict() validates every field before trusting
it. Older saves are migrated one schema at a time by MIGRATIONS; schemas 1-5
(before the hosted build) are no longer supported and are rejected.
"""
from ..catalog import BOONS, UNLOCKS
from ..catalog import ATTRIBUTES, BY_ID, ITEMS, REGIONS
from ..encounters import ENCOUNTER_VERSION
from ..equipment import validate_equipped
from ..journal import new_journal, validate_journal
from ..models import ChunkKey, chunk_ident, fields, identifier, integer
from ..runtime import Exploration
from ..tuning import PITY_CHUNKS
from .constants import (ANCHOR_COUNTDOWN_MS, FOOD_COOLDOWN_MS, INVENTORY_SLOTS, LEGACY_MONSTER_MAX_MS, LOG_LIMIT,
                        LOG_TYPES, MONSTER_STEP_MS, SCHEMA_VERSION, SELF_ACTIONS, STACK_LIMIT, STAT_KEYS,
                        TASK_TYPES, VITAL_MAX)

SAVE_FIELDS = ("schema_version", "encounters", "exploration", "life", "total_ms", "regular",
               "dimensional", "life_gain", "completed", "inventory", "hunger", "health",
               "food_cooldown_ms", "cause", "depth", "best_depth", "blessing", "ash", "unlocked",
               "mastery", "boon", "boon_next", "stats", "drought", "forced", "journal", "anchor_ms", "anchor_wait",
               "monster_ms", "prayers_this_life", "budget", "spawned",
               "admitted", "screened_chunks", "screened_targets", "log", "sequence",
               "decisions", "skills", "report", "task", "goal", "equipped", "knowledge",
               "recipes", "journal_disabled", "journal_favor", "leads", "lead_history", "spot_plans",
               "return_ready_ms", "journal_guarantee", "journal_guarantee_region", "guarantee_used", "converted")
V7_FIELDS = ("journal",)                       # added by schema 7
V8_FIELDS = ("equipped", "knowledge", "recipes", "journal_disabled", "journal_favor",
             "leads", "lead_history")         # added by schema 8
V9_FIELDS = ("spot_plans",)                    # added by schema 9
V10_FIELDS = ("return_ready_ms", "journal_guarantee", "journal_guarantee_region", "guarantee_used", "converted")
OLDEST_SUPPORTED_SCHEMA = 6


def _without(*groups):
    dropped = {name for group in groups for name in group}
    return tuple(name for name in SAVE_FIELDS if name not in dropped)


def _reroll_current_life(data):
    """Drop this life's encounter plans so the current encounter version re-rolls them
    on entry; earned progress, vitals and inventory are kept."""
    exploration = dict(data["exploration"])
    try:
        exploration["targets"] = [t for t in exploration["targets"] if not str(t["id"]).startswith("enc:")]
        exploration["hit_targets"] = [t for t in exploration["hit_targets"] if not str(t).startswith("enc:")]
        completed = [c for c in data["completed"] if not str(c).startswith("enc:")]
    except (TypeError, KeyError) as exc:
        raise ValueError("malformed expedition save") from exc
    task, goal = data["task"], data["goal"]
    if isinstance(task, dict) and task.get("type") == "perform":
        task = None
    if isinstance(goal, dict) and goal.get("kind") in ("spot", "target"):
        goal = None
    return {**data, "schema_version": 9, "encounters": ENCOUNTER_VERSION,
            "exploration": exploration, "completed": completed, "task": task, "goal": goal, "forced": {},
            "budget": None, "spawned": None, "admitted": None, "screened_chunks": None,
            "screened_targets": None, "spot_plans": {}}


def _from_v6(data):
    """Schema 6 -> 7 adds the lifetime journal (empty: earlier lives were not counted)."""
    fields(data, _without(V7_FIELDS, V8_FIELDS, V9_FIELDS, V10_FIELDS) + ("dust",))
    return {**data, "schema_version": 7, "journal": new_journal()}


def _from_v7(data):
    """New action pool/regions: preserve earned progress, move carried gear into slots."""
    fields(data, _without(V8_FIELDS, V9_FIELDS, V10_FIELDS) + ("dust",))
    if data["encounters"] != "encounters-v6":
        raise ValueError("unsupported expedition save")
    equipped = {ITEMS[item].slot: item for item in dict(data["inventory"]) if ITEMS[item].kind == "gear"}
    return {**_reroll_current_life(data), "equipped": equipped, "knowledge": [], "recipes": [],
            "journal_disabled": [], "journal_favor": {}, "leads": [], "lead_history": []}


def _from_v8(data):
    """Spots are now rolled on entry and saved as plans: affected plans re-roll."""
    fields(data, _without(V9_FIELDS, V10_FIELDS) + ("dust",))
    if data["encounters"] != "encounters-v7":
        raise ValueError("unsupported expedition save")
    return _reroll_current_life(data)


def _from_v9(data):
    """Combine prestige balances and reroll old encounter plans; paid mastery is legacy credit."""
    fields(data, _without(V10_FIELDS) + ("dust",))
    if data["encounters"] == "encounters-v8":
        data = _reroll_current_life(data)
    elif data["encounters"] != ENCOUNTER_VERSION:
        raise ValueError("unsupported expedition save")
    ash = integer(data["ash"], "ash", 0) + integer(data["dust"], "dust", 0)
    favor = dict(data["journal_favor"])
    favor.update({ident: "suppress" for ident in data["journal_disabled"]})
    return {**{key: value for key, value in data.items() if key != "dust"},
            "schema_version": 10, "ash": ash, "journal_favor": favor,
            "journal_disabled": [], "return_ready_ms": 0,
            "journal_guarantee": None, "journal_guarantee_region": None, "guarantee_used": False,
            "converted": {}}


MIGRATIONS = {6: _from_v6, 7: _from_v7, 8: _from_v8, 9: _from_v9}


def upgrade(data):
    """Migrate a save dict to SCHEMA_VERSION, one step at a time."""
    while isinstance(data, dict) and data.get("schema_version") in MIGRATIONS:
        data = MIGRATIONS[data["schema_version"]](data)
    if isinstance(data, dict) and type(data.get("schema_version")) is int \
            and data["schema_version"] < OLDEST_SUPPORTED_SCHEMA:
        raise ValueError("expedition save is too old (schema "
                         f"{data['schema_version']}); start a new expedition")
    return data


def validated_lead(row, world, *, history=False):
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
    if row["chunk"] != chunk_ident(key):
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



def _load_progress(result, data):
    """Persistent and per-life progress: XP, completions, inventory, discoveries, leads."""
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
        setattr(result, name, [validated_lead(v, result.game.world, history=name == "lead_history")
                               for v in values])


def _load_life(result, data):
    """Vitals, currencies, purchases, per-life counters, pity spots and spot plans."""
    result.hunger = integer(data["hunger"], "hunger", 0, VITAL_MAX)
    result.health = integer(data["health"], "health", 0, VITAL_MAX)
    result.food_cooldown_ms = integer(data["food_cooldown_ms"], "food cooldown", 0, FOOD_COOLDOWN_MS)
    if data["cause"] not in (None, "starvation", "boar", "return"):
        raise ValueError("invalid death cause")
    result.cause = data["cause"]
    result.depth = integer(data["depth"], "depth", 0)
    result.best_depth = integer(data["best_depth"], "best depth", result.depth)
    result.blessing = integer(data["blessing"], "blessing power", 0)
    result.ash = integer(data["ash"], "ash", 0)
    if type(data["converted"]) is not dict or any(item not in ITEMS for item in data["converted"]):
        raise ValueError("invalid converted resources")
    result.converted = {item: integer(count, "converted resources", 1)
                        for item, count in data["converted"].items()}
    result.return_ready_ms = integer(data["return_ready_ms"], "return cooldown", 0)
    if type(data["unlocked"]) is not list or any(u not in UNLOCKS for u in data["unlocked"]) \
            or len(set(data["unlocked"])) != len(data["unlocked"]):
        raise ValueError("invalid unlocks")
    result.unlocked = set(data["unlocked"])
    if type(data["mastery"]) is not dict or any(a not in BY_ID or BY_ID[a].placement != "spot"
                                                  for a in data["mastery"]):
        raise ValueError("invalid mastery")
    result.mastery = {a: integer(v, "mastery", 1, 3) for a, v in data["mastery"].items()}
    selected = data["journal_guarantee"]
    if selected is not None and (selected not in BY_ID or BY_ID[selected].placement != "spot"
                                 or result.mastery.get(selected, 0) < 3):
        raise ValueError("invalid journal guarantee")
    result.journal_guarantee = selected
    region = data["journal_guarantee_region"]
    if (selected is None and region is not None) or (selected is not None and
            (region not in REGIONS or REGIONS[region].biome not in BY_ID[selected].biomes or
             (BY_ID[selected].regions is not None and region not in BY_ID[selected].regions) or
             REGIONS[region].multiplier(selected) == 0)):
        raise ValueError("invalid journal guarantee region")
    result.journal_guarantee_region = region
    if type(data["guarantee_used"]) is not bool:
        raise ValueError("invalid guarantee state")
    result.guarantee_used = data["guarantee_used"]
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
        if chunk_ident(key) != ident:
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


def _load_spawns(result, data):
    """This life's spawn windows and screening (None after an upgrade: roll now)."""
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


def _load_log(result, data):
    """Recent log, counters and the last life report."""
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


def _load_plan(result, data):
    """The running task and current goal."""
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


class SavesMixin:
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
                "ash": self.ash, "converted": dict(sorted(self.converted.items())),
                "unlocked": sorted(self.unlocked),
                "mastery": dict(sorted(self.mastery.items())), "boon": self.boon, "boon_next": self.boon_next,
                "stats": dict(self.stats), "drought": dict(self.drought), "journal": validate_journal(self.journal),
                "forced": {k: list(v) for k, v in sorted(self.forced.items())},
                "spot_plans": {k: [list(row) for row in v] for k, v in sorted(self.spot_plans.items())},
                "anchor_ms": self.anchor_ms, "anchor_wait": self.anchor_wait,
                "return_ready_ms": self.return_ready_ms,
                "journal_guarantee": self.journal_guarantee,
                "journal_guarantee_region": self.journal_guarantee_region,
                "guarantee_used": self.guarantee_used,
                "monster_ms": self.monster_ms, "prayers_this_life": self.prayers_this_life,
                "budget": dict(self.budget), "spawned": dict(self.spawned),
                "admitted": sorted([i, e] for i, e in self.admitted.items()), "screened_chunks": sorted(self.screened_chunks),
                "screened_targets": sorted(self.screened_targets),
                "log": [dict(entry, items=[list(i) for i in entry["items"]]) for entry in self.log],
                "sequence": self.sequence, "decisions": self.decisions, "skills": sorted(self.skills),
                "report": {**self.report, "lines": list(self.report["lines"])},
                "task": dict(self.task) if self.task else None,
                "goal": dict(self.goal) if self.goal else None}

    @classmethod
    def from_dict(cls, data):
        data = upgrade(data)
        fields(data, SAVE_FIELDS)
        if data["schema_version"] != SCHEMA_VERSION or data["encounters"] != ENCOUNTER_VERSION:
            raise ValueError("unsupported expedition save")
        result = cls(Exploration.from_dict(data["exploration"]), skills=data["skills"], fresh=False)
        try:
            _load_progress(result, data)
            _load_life(result, data)
            _load_spawns(result, data)
            _load_log(result, data)
            _load_plan(result, data)
        except (TypeError, KeyError) as exc:
            raise ValueError("malformed expedition save") from exc
        return result
