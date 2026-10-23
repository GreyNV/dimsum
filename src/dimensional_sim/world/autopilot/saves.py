"""Save serialization, validation and upgrades from older schemas.

to_dict() is canonical (sorted where order is not meaningful) so a save, a reload
and a re-save are byte-identical. from_dict() validates every field before trusting
it. Older saves are migrated one schema at a time by MIGRATIONS; schemas 1-5
(before the hosted build) are no longer supported and are rejected.
"""
from ..catalog import RECIPE_KEEP_COST, DEATH_CAUSES, UNLOCKS
from ..catalog import ATTRIBUTES, BUILDINGS, BY_ID, ITEMS, LOCATION_FOCUS, LOCATIONS
from ..encounters import ENCOUNTER_VERSION
from ..equipment import validate_equipped
from ..journal import new_journal, validate_journal
from ..models import ChunkKey, chunk_ident, fields, identifier, integer
from ..runtime import Exploration
from ..tuning import CHEST_SLOTS, DAY_START_MS, NIGHT_SPAWN_EVERY_MS, PITY_CHUNKS
from .constants import (ANCHOR_COUNTDOWN_MS, CONTACT_COOLDOWN_MS, FOOD_COOLDOWN_MS, POSSESS_COOLDOWN_MS, INVENTORY_SLOTS, LEGACY_MONSTER_MAX_MS, LOG_LIMIT,
                        LOG_TYPES, MONSTER_STEP_MS, SCHEMA_VERSION, SELF_ACTIONS, STACK_LIMIT, STAT_KEYS,
                        TASK_TYPES, VITAL_MAX)
from .ecology import valid_pressure, valid_shimmer

V17_SAVE_FIELDS = ("schema_version", "encounters", "exploration", "life", "total_ms", "regular",
               "dimensional", "life_gain", "completed", "inventory", "hunger", "health",
               "food_cooldown_ms", "cause", "depth", "best_depth", "blessing", "ash", "unlocked",
               "mastery", "boon", "boon_next", "stats", "drought", "forced", "journal", "anchor_ms", "anchor_wait",
               "monster_ms", "prayers_this_life", "budget", "spawned",
               "admitted", "screened_chunks", "screened_targets", "log", "sequence",
               "decisions", "skills", "report", "task", "goal", "equipped", "knowledge",
               "recipes", "journal_disabled", "journal_favor", "leads", "lead_history", "spot_plans",
               "return_ready_ms", "journal_guarantee", "journal_guarantee_region", "guarantee_used", "converted",
               "buildings", "bound_buildings", "chest", "campfire", "pressure", "shimmer", "life_recipes")
# Schema 18 dropped blessing, boons, the random prayer, skills and the return-to-anchor
# cooldown, and added contacting the anchor, possession and the opening at the anchor.
V18_DROPPED = ("blessing", "boon", "boon_next", "prayers_this_life", "skills", "return_ready_ms")
V18_FIELDS = ("contact_ready_ms", "possess_end_ms", "possess_ready_ms", "opening")
V18_SAVE_FIELDS = tuple(f for f in V17_SAVE_FIELDS if f not in V18_DROPPED) + V18_FIELDS
V19_FIELDS = ("night_tick",)       # schema 19: the night watch's last world-clock tick
V19_SAVE_FIELDS = V18_SAVE_FIELDS + V19_FIELDS
V20_FIELDS = ("hunting",)          # schema 20: enemies hunting or fleeing the avatar
V20_SAVE_FIELDS = V19_SAVE_FIELDS + V20_FIELDS
V21_FIELDS = ("possess_charge", "possess_charge_at_ms", "possess_drain_duration_ms")
V21_SAVE_FIELDS = tuple(f for f in V20_SAVE_FIELDS if f != "possess_ready_ms") + V21_FIELDS
# Schema 22: encounter mastery and Journal favor/guarantee became location mastery and camp focus.
V22_DROPPED = ("mastery", "journal_favor", "journal_guarantee", "journal_guarantee_region", "guarantee_used")
V22_FIELDS = ("location_done", "location_focus", "camp")
SAVE_FIELDS = tuple(f for f in V21_SAVE_FIELDS if f not in V22_DROPPED) + V22_FIELDS
V7_FIELDS = ("journal",)                       # added by schema 7
V8_FIELDS = ("equipped", "knowledge", "recipes", "journal_disabled", "journal_favor",
             "leads", "lead_history")         # added by schema 8
V9_FIELDS = ("spot_plans",)                    # added by schema 9
V10_FIELDS = ("return_ready_ms", "journal_guarantee", "journal_guarantee_region", "guarantee_used", "converted")
V13_FIELDS = ("buildings", "bound_buildings", "chest")
V14_FIELDS = ("campfire",)
V15_FIELDS = ("pressure",)
V16_FIELDS = ("shimmer",)
V17_FIELDS = ("life_recipes",)
SPOT_PLAN_LIMIT = 3 + 8          # wild spots per chunk plus the largest site bucket
OLDEST_SUPPORTED_SCHEMA = 6


def _without(*groups):
    dropped = {name for group in groups for name in group}
    return tuple(name for name in V17_SAVE_FIELDS if name not in dropped)


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
    fields(data, _without(V7_FIELDS, V8_FIELDS, V9_FIELDS, V10_FIELDS, V13_FIELDS, V14_FIELDS, V15_FIELDS, V16_FIELDS, V17_FIELDS) + ("dust",))
    return {**data, "schema_version": 7, "journal": new_journal()}


def _from_v7(data):
    """New action pool/regions: preserve earned progress, move carried gear into slots."""
    fields(data, _without(V8_FIELDS, V9_FIELDS, V10_FIELDS, V13_FIELDS, V14_FIELDS, V15_FIELDS, V16_FIELDS, V17_FIELDS) + ("dust",))
    if data["encounters"] != "encounters-v6":
        raise ValueError("unsupported expedition save")
    equipped = {ITEMS[item].slot: item for item in dict(data["inventory"]) if ITEMS[item].kind == "gear"}
    return {**_reroll_current_life(data), "equipped": equipped, "knowledge": [], "recipes": [],
            "journal_disabled": [], "journal_favor": {}, "leads": [], "lead_history": []}


def _from_v8(data):
    """Spots are now rolled on entry and saved as plans: affected plans re-roll."""
    fields(data, _without(V9_FIELDS, V10_FIELDS, V13_FIELDS, V14_FIELDS, V15_FIELDS, V16_FIELDS, V17_FIELDS) + ("dust",))
    if data["encounters"] != "encounters-v7":
        raise ValueError("unsupported expedition save")
    return _reroll_current_life(data)


def _from_v9(data):
    """Combine prestige balances and reroll old encounter plans; paid mastery is legacy credit."""
    fields(data, _without(V10_FIELDS, V13_FIELDS, V14_FIELDS, V15_FIELDS, V16_FIELDS, V17_FIELDS) + ("dust",))
    if data["encounters"] == "encounters-v8":
        data = _reroll_current_life(data)
    elif data["encounters"] not in ("encounters-v9", ENCOUNTER_VERSION):   # current = rerolled above
        raise ValueError("unsupported expedition save")
    ash = integer(data["ash"], "ash", 0) + integer(data["dust"], "dust", 0)
    favor = dict(data["journal_favor"])
    favor.update({ident: "suppress" for ident in data["journal_disabled"]})
    return {**{key: value for key, value in data.items() if key != "dust"},
            "schema_version": 10, "ash": ash, "journal_favor": favor,
            "journal_disabled": [], "return_ready_ms": 0,
            "journal_guarantee": None, "journal_guarantee_region": None, "guarantee_used": False,
            "converted": {}}


def _from_v10(data):
    """Rarity tiers change how new chunks roll; chunks already rolled keep their saved plans."""
    fields(data, _without(V13_FIELDS, V14_FIELDS, V15_FIELDS, V16_FIELDS, V17_FIELDS))
    if data["encounters"] not in ("encounters-v9", "encounters-v10", ENCOUNTER_VERSION):
        raise ValueError("unsupported expedition save")
    return {**data, "schema_version": 11, "encounters": "encounters-v10"}


# Content removed by schema 12: the camp and watchtower became landmark sites (their own
# encounters); the walking staff waits for weapon animations.
REMOVED_V12_ACTIONS = ("abandoned_camp", "craft_staff", "fallen_watchtower")   # what schema 12 dropped
REMOVED_V12_ITEMS = ("walking_staff",)
REMOVED_V12_RECIPES = ("walking_staff",)


def _from_v11(data):
    """Landmark sites and the staff's removal: this life's spots re-roll, and every reference
    to removed actions/items is dropped; earned progress otherwise stays."""
    fields(data, _without(V13_FIELDS, V14_FIELDS, V15_FIELDS, V16_FIELDS, V17_FIELDS))
    if data["encounters"] not in ("encounters-v10", ENCOUNTER_VERSION):
        raise ValueError("unsupported expedition save")
    gone_a, gone_i = set(REMOVED_V12_ACTIONS), set(REMOVED_V12_ITEMS)
    data = _reroll_current_life(data)
    inventory = [row for row in data["inventory"] if not (type(row) is list and row and row[0] in gone_i)]
    equipped = {slot: item for slot, item in dict(data["equipped"]).items() if item not in gone_i}
    journal = dict(data["journal"])
    journal["actions"] = {k: v for k, v in dict(journal["actions"]).items() if k not in gone_a}
    journal["items"] = {k: v for k, v in dict(journal["items"]).items() if k not in gone_i}
    guarantee = data["journal_guarantee"]
    log = [dict(entry, items=[i for i in entry["items"] if not (type(i) is list and i and i[0] in gone_i)])
           for entry in data["log"] if isinstance(entry, dict) and entry.get("encounter") not in gone_a]
    return {**data, "schema_version": 12, "encounters": ENCOUNTER_VERSION,
            "inventory": inventory, "equipped": equipped, "journal": journal, "log": log,
            "converted": {k: v for k, v in dict(data["converted"]).items() if k not in gone_i},
            "mastery": {k: v for k, v in dict(data["mastery"]).items() if k not in gone_a},
            "journal_favor": {k: v for k, v in dict(data["journal_favor"]).items() if k not in gone_a},
            "journal_disabled": [k for k in data["journal_disabled"] if k not in gone_a],
            "recipes": [k for k in data["recipes"] if k not in REMOVED_V12_RECIPES],
            "journal_guarantee": None if guarantee in gone_a else guarantee,
            "journal_guarantee_region": None if guarantee in gone_a else data["journal_guarantee_region"],
            "task": None, "goal": None}


def _from_v12(data):
    """Camp buildings, the chest, the Building discipline and the 'built' life stat."""
    fields(data, _without(V13_FIELDS, V14_FIELDS, V15_FIELDS, V16_FIELDS, V17_FIELDS))
    xp = {name: {**dict(data[name]), "building": 0} for name in ("regular", "dimensional", "life_gain")}
    return {**data, **xp, "schema_version": 13, "buildings": [], "bound_buildings": [], "chest": {},
            "stats": {**dict(data["stats"]), "built": 0}}


def _from_v13(data):
    """This life's campfire (none in older saves)."""
    fields(data, _without(V14_FIELDS, V15_FIELDS, V16_FIELDS, V17_FIELDS))
    return {**data, "schema_version": 14, "campfire": None}


def _from_v14(data):
    """Ecological pressure this life (none in older saves)."""
    fields(data, _without(V15_FIELDS, V16_FIELDS, V17_FIELDS))
    return {**data, "schema_version": 15, "pressure": {}}


def _from_v15(data):
    """Shimmering region cells this life (none in older saves)."""
    fields(data, _without(V16_FIELDS, V17_FIELDS))
    return {**data, "schema_version": 16, "shimmer": []}


# Unlocks that became recipes when actions started opening by dimensional level (schema 17):
# a soul that bought the old unlock keeps the craft for good.
UNLOCK_TO_RECIPE = {"hide_working": "hide_wrap", "snares": "snare"}


def _from_v16(data):
    """Recipes found this life (none in older saves); bought craft unlocks become kept recipes."""
    fields(data, _without(V17_FIELDS))
    unlocked = [u for u in data["unlocked"] if u != "hide_working"]
    recipes = sorted(set(data["recipes"]) | {r for u, r in UNLOCK_TO_RECIPE.items() if u in data["unlocked"]})
    return {**data, "schema_version": 17, "life_recipes": [], "unlocked": unlocked, "recipes": recipes}


def _from_v17(data):
    """Drop blessings, boons, prayer and old skill fields; keep a paid anchor return."""
    fields(data, V17_SAVE_FIELDS)
    return_ready_ms = data["return_ready_ms"]
    data = {k: v for k, v in data.items() if k not in V18_DROPPED}
    unlocked = set(data["unlocked"])
    log = [{**{k: v for k, v in e.items() if k != "blessing"},
            "type": "lore" if e.get("type") == "blessing" else e.get("type")} for e in data["log"]]
    journal = dict(data["journal"])
    if isinstance(journal.get("actions"), dict):
        journal["actions"] = {a: n for a, n in journal["actions"].items() if a != "pray"}
    task, goal = data["task"], data["goal"]
    if isinstance(task, dict) and task.get("type") == "pray":
        task, goal = None, None
    return {**data, "schema_version": 18, "unlocked": sorted(unlocked | {"campfire"}),
            "log": log, "journal": journal, "task": task, "goal": goal,
            "contact_ready_ms": return_ready_ms, "possess_end_ms": None, "possess_ready_ms": 0, "opening": False}


def _from_v18(data):
    """The night watch starts at the save's current clock tick (no retroactive wolves)."""
    fields(data, V18_SAVE_FIELDS)
    total = integer(data["total_ms"], "total time", 0)
    return {**data, "schema_version": 19, "night_tick": (total + DAY_START_MS) // NIGHT_SPAWN_EVERY_MS}


def _from_v19(data):
    """Nobody is hunting yet: enemies notice the avatar again under the new rules."""
    fields(data, V19_SAVE_FIELDS)
    total = integer(data["total_ms"], "total time", 0)   # early schema-19 saves used a 20 s tick
    tick = min(integer(data["night_tick"], "night tick", 0), (total + DAY_START_MS) // NIGHT_SPAWN_EVERY_MS)
    return {**data, "schema_version": 20, "hunting": {}, "night_tick": tick}


def _from_v20(data):
    """Preserve remaining control or cooldown as charge in the reusable meter."""
    fields(data, V20_SAVE_FIELDS)
    total = integer(data["total_ms"], "total time", 0)
    ready = integer(data["possess_ready_ms"], "possession cooldown", 0, total + POSSESS_COOLDOWN_MS)
    end = data["possess_end_ms"]
    if end is None:
        charge = POSSESS_COOLDOWN_MS - max(0, ready - total)
        drain = 0
    else:
        end = integer(end, "possession end", total + 1, total + 60_000)
        drain = max(30_000, end - total)  # old saves did not freeze activation duration
        charge = min(POSSESS_COOLDOWN_MS,
                     -(-(end - total) * POSSESS_COOLDOWN_MS // drain))
    return {**{k: v for k, v in data.items() if k != "possess_ready_ms"},
            "schema_version": 21, "possess_charge": charge,
            "possess_charge_at_ms": total, "possess_drain_duration_ms": drain}


def _from_v21(data):
    """Encounter counts become location mastery: each encounter's lifetime count goes to the place
    it most likely happened (its landmark, or the region that favours it most). The campfire skill
    is gone (a mastered place allows camp); schema 18 had granted it to every older save, so there
    is no telling who paid for it, and nothing is refunded."""
    fields(data, V21_SAVE_FIELDS)
    from .places import home_location
    done = {}
    actions = data["journal"].get("actions", {}) if type(data["journal"]) is dict else {}
    for ident, count in sorted(actions.items()):
        location = home_location(ident)
        if location is not None and type(count) is int and count > 0:
            done[location] = done.get(location, 0) + count
    unlocked = [u for u in data["unlocked"] if u != "campfire"]
    # Story places of the retired grey wall (never on GitHub main, but in bundles that were shared).
    retired = ("watch_post", "grey_wall", "wall_crossing")
    forced = {k: [e for e in v if e not in retired] for k, v in data["forced"].items()} \
        if type(data["forced"]) is dict else data["forced"]
    admitted = [row for row in data["admitted"] if not (type(row) is list and len(row) == 2 and row[1] in retired)] \
        if type(data["admitted"]) is list else data["admitted"]
    return {**{k: v for k, v in data.items() if k not in V22_DROPPED}, "schema_version": 22,
            "unlocked": unlocked, "forced": forced, "admitted": admitted,
            "location_done": done, "location_focus": {}, "camp": None}


def _from_v22(data):
    """New chunks use encounter v12; already rolled plans remain fixed through this life."""
    fields(data, SAVE_FIELDS)
    if data["encounters"] not in ("encounters-v11", ENCOUNTER_VERSION):
        raise ValueError("unsupported expedition encounter version")
    return {**data, "schema_version": 23, "encounters": ENCOUNTER_VERSION}


MIGRATIONS = {6: _from_v6, 7: _from_v7, 8: _from_v8, 9: _from_v9, 10: _from_v10, 11: _from_v11, 12: _from_v12,
              13: _from_v13, 14: _from_v14, 15: _from_v15, 16: _from_v16,
              17: _from_v17, 18: _from_v18, 19: _from_v19, 20: _from_v20, 21: _from_v21,
              22: _from_v22}


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
    for name in ("knowledge", "recipes", "life_recipes", "journal_disabled"):
        values = data[name]
        if type(values) is not list or len(values) != len(set(values)) or any(
                type(value) is not str for value in values):
            raise ValueError(f"invalid {name}")
        setattr(result, name, set(values))
    done = data["location_done"]
    if type(done) is not dict or any(key not in LOCATIONS for key in done):
        raise ValueError("invalid location mastery")
    result.location_done = {k: integer(v, "location mastery", 0) for k, v in done.items()}
    focus = data["location_focus"]
    if type(focus) is not dict or any(key not in LOCATIONS or value not in LOCATION_FOCUS
                                      for key, value in focus.items()):
        raise ValueError("invalid location focus")
    result.location_focus = dict(focus)
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
    _load_vitals(result, data)
    _load_anchor_camp(result, data)
    result.pressure = valid_pressure(data["pressure"], result.dimension)
    result.shimmer = valid_shimmer(data["shimmer"], result.dimension)
    if type(data["converted"]) is not dict or any(item not in ITEMS for item in data["converted"]):
        raise ValueError("invalid converted resources")
    result.converted = {item: integer(count, "converted resources", 1)
                        for item, count in data["converted"].items()}
    _load_anchor_powers(result, data)
    _load_night(result, data)
    if type(data["unlocked"]) is not list or any(u not in UNLOCKS for u in data["unlocked"]) \
            or len(set(data["unlocked"])) != len(data["unlocked"]):
        raise ValueError("invalid unlocks")
    result.unlocked = set(data["unlocked"])
    _load_camp(result, data)
    _load_counters(result, data)
    _load_spot_plans(result, data)
    _load_anchor_clock(result, data)


def _load_vitals(result, data):
    """Hunger, health, death cause, depth and ash."""
    result.hunger = integer(data["hunger"], "hunger", 0, VITAL_MAX)
    result.health = integer(data["health"], "health", 0, VITAL_MAX)
    result.food_cooldown_ms = integer(data["food_cooldown_ms"], "food cooldown", 0, FOOD_COOLDOWN_MS)
    if data["cause"] is not None and data["cause"] not in DEATH_CAUSES:
        raise ValueError("invalid death cause")
    result.cause = data["cause"]
    result.depth = integer(data["depth"], "depth", 0)
    result.best_depth = integer(data["best_depth"], "best depth", result.depth)
    result.ash = integer(data["ash"], "ash", 0)


def _load_anchor_camp(result, data):
    """Buildings at the anchor camp, the storage chest and a lit campfire."""
    for name in ("buildings", "bound_buildings"):
        values = data[name]
        if type(values) is not list or len(set(values)) != len(values) or any(v not in BUILDINGS for v in values):
            raise ValueError(f"invalid {name}")
    if not set(data["bound_buildings"]) <= set(data["buildings"]) and data["anchor_ms"] is None:
        raise ValueError("a bound building must stand at the camp")
    result.buildings, result.bound_buildings = set(data["buildings"]), set(data["bound_buildings"])
    chest = data["chest"]
    if type(chest) is not dict or len(chest) > CHEST_SLOTS or any(
            item not in ITEMS for item in chest) or (chest and not any(
            BUILDINGS[b].function == "storage" for b in result.buildings | result.bound_buildings)):
        raise ValueError("invalid storage chest")
    result.chest = {item: integer(count, "chest count", 1, STACK_LIMIT) for item, count in chest.items()}
    fire = data["campfire"]
    if fire is not None:
        if type(fire) is not dict or set(fire) != {"dimension", "x", "y", "fire_x", "fire_y"} \
                or fire["dimension"] != result.dimension:
            raise ValueError("invalid campfire")
        for name in ("x", "y", "fire_x", "fire_y"):
            integer(fire[name], f"campfire {name}")
        if abs(fire["x"] - fire["fire_x"]) + abs(fire["y"] - fire["fire_y"]) > 1:
            raise ValueError("a campfire stands beside its seat")
        fire = dict(fire)
    result.campfire = fire


def _load_anchor_powers(result, data):
    """Contact and possession timers, and the opening flag."""
    result.contact_ready_ms = integer(data["contact_ready_ms"], "contact cooldown", 0,
                                      result.total_ms + CONTACT_COOLDOWN_MS)
    result.possess_charge = integer(data["possess_charge"], "possession charge", 0, POSSESS_COOLDOWN_MS)
    result.possess_charge_at_ms = integer(data["possess_charge_at_ms"], "possession charge time", 0,
                                          result.total_ms)
    result.possess_drain_duration_ms = integer(data["possess_drain_duration_ms"], "possession drain", 0, 60_000)
    if data["possess_end_ms"] is not None:
        integer(data["possess_end_ms"], "possession end", result.total_ms + 1,
                result.total_ms + 60_000)
        if not result.possess_charge or result.possess_drain_duration_ms < 30_000:
            raise ValueError("invalid active possession charge")
    elif result.possess_drain_duration_ms:
        raise ValueError("inactive possession cannot drain charge")
    result.possess_end_ms = data["possess_end_ms"]
    if type(data["opening"]) is not bool or (data["opening"] and (data["anchor_ms"] is None or result.life != 1)):
        raise ValueError("invalid opening")
    result.opening = data["opening"]


def _load_night(result, data):
    """The night clock and the enemies hunting the avatar."""
    result.night_tick = integer(data["night_tick"], "night tick", 0,
                                (result.total_ms + DAY_START_MS) // NIGHT_SPAWN_EVERY_MS)
    hunting = data["hunting"]
    if type(hunting) is not dict:
        raise ValueError("invalid hunting enemies")
    result.hunting = {}
    for ident, row in hunting.items():
        fields(row, ("mode", "since"))
        if ident not in result.game.targets or row["mode"] not in ("hunt", "flee"):
            raise ValueError("invalid hunting enemy")
        result.hunting[ident] = {"mode": row["mode"], "since": integer(row["since"], "hunt start", 0, result.total_ms)}


def _load_camp(result, data):
    """A camp held in a mastered place (Places)."""
    camp = data["camp"]
    if camp is not None:
        fields(camp, ("location", "dimension", "cx", "cy", "idle_since", "left"))
        if type(camp["left"]) is not bool:
            raise ValueError("invalid camp")
        if camp["location"] not in LOCATIONS:
            raise ValueError("invalid camp")
        identifier(camp["dimension"], "camp dimension")
        integer(camp["cx"], "camp x"); integer(camp["cy"], "camp y")
        if camp["idle_since"] is not None:
            integer(camp["idle_since"], "camp idle", 0, result.total_ms)
        camp = dict(camp)
    result.camp = camp


def _load_counters(result, data):
    """Life stats, drought counters and pity spots."""
    if type(data["stats"]) is not dict or set(data["stats"]) != set(STAT_KEYS):
        raise ValueError("invalid life stats")
    result.stats = {k: integer(v, "life stat", 0) for k, v in data["stats"].items()}
    if type(data["drought"]) is not dict or set(data["drought"]) != set(PITY_CHUNKS):
        raise ValueError("invalid drought counters")
    result.drought = {k: integer(v, "drought", 0, 1000) for k, v in data["drought"].items()}
    forced = data["forced"]
    if type(forced) is not dict or any(type(v) is not list or any(e not in BY_ID or BY_ID[e].placement not in ("spot", "story")
                                                                  for e in v) for v in forced.values()):
        raise ValueError("invalid pity spots")
    result.forced = {k: list(v) for k, v in forced.items()}


def _load_spot_plans(result, data):
    """Rolled spot plans per chunk, checked against the world's dimensions."""
    plans = data["spot_plans"]
    if type(plans) is not dict or len(plans) > 100000:
        raise ValueError("invalid spot plans")
    result.spot_plans = {}
    for ident, rows in plans.items():
        if type(ident) is not str or type(rows) is not list or len(rows) > SPOT_PLAN_LIMIT:
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
                    BY_ID[row[0]].placement not in ("spot", "site")):
                raise ValueError("invalid spot plan row")
            integer(row[1], "spot x", 0, spec.width - 1)
            integer(row[2], "spot y", 0, spec.height - 1)
        result.spot_plans[ident] = [tuple(row) for row in rows]


def _load_anchor_clock(result, data):
    """Journal, monster clock and the anchor countdown."""
    result.journal = validate_journal(data["journal"])
    result.monster_ms = min(integer(data["monster_ms"], "monster clock", 0, LEGACY_MONSTER_MAX_MS),
                            MONSTER_STEP_MS - 1)
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
                       "xp", "dim_xp", "items"))
        if entry["type"] not in LOG_TYPES or (entry["encounter"] is not None and entry["encounter"] not in BY_ID) \
                or (entry["attribute"] is not None and entry["attribute"] not in ATTRIBUTES):
            raise ValueError("invalid log entry")
        if type(entry["items"]) is not list or any(type(i) is not list or len(i) != 2 or i[0] not in ITEMS
                                                   for i in entry["items"]):
            raise ValueError("invalid log items")
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
                "recipes": sorted(self.recipes), "life_recipes": sorted(self.life_recipes), "journal_disabled": sorted(self.journal_disabled),
                "location_done": dict(sorted(self.location_done.items())),
                "location_focus": dict(sorted(self.location_focus.items())),
                "camp": dict(self.camp) if self.camp else None,
                "leads": [dict(lead) for lead in self.leads],
                "lead_history": [dict(lead) for lead in self.lead_history],
                "hunger": self.hunger, "health": self.health,
                "food_cooldown_ms": self.food_cooldown_ms, "cause": self.cause,
                "depth": self.depth, "best_depth": self.best_depth,
                "ash": self.ash, "converted": dict(sorted(self.converted.items())),
                "buildings": sorted(self.buildings), "bound_buildings": sorted(self.bound_buildings),
                "chest": dict(sorted(self.chest.items())),
                "campfire": dict(self.campfire) if self.campfire else None,
                "pressure": dict(sorted(self.pressure.items())), "shimmer": sorted(self.shimmer),
                "unlocked": sorted(self.unlocked),
                "stats": dict(self.stats), "drought": dict(self.drought), "journal": validate_journal(self.journal),
                "forced": {k: list(v) for k, v in sorted(self.forced.items())},
                "spot_plans": {k: [list(row) for row in v] for k, v in sorted(self.spot_plans.items())},
                "anchor_ms": self.anchor_ms, "anchor_wait": self.anchor_wait,
                "contact_ready_ms": self.contact_ready_ms, "possess_end_ms": self.possess_end_ms,
                "possess_charge": self.possess_charge, "possess_charge_at_ms": self.possess_charge_at_ms,
                "possess_drain_duration_ms": self.possess_drain_duration_ms,
                "opening": self.opening, "night_tick": self.night_tick,
                "hunting": {k: dict(v) for k, v in sorted(self.hunting.items())},
                "monster_ms": self.monster_ms,
                "budget": dict(self.budget), "spawned": dict(self.spawned),
                "admitted": sorted([i, e] for i, e in self.admitted.items()), "screened_chunks": sorted(self.screened_chunks),
                "screened_targets": sorted(self.screened_targets),
                "log": [dict(entry, items=[list(i) for i in entry["items"]]) for entry in self.log],
                "sequence": self.sequence, "decisions": self.decisions,
                "report": {**self.report, "lines": list(self.report["lines"])},
                "task": dict(self.task) if self.task else None,
                "goal": dict(self.goal) if self.goal else None}

    @classmethod
    def from_dict(cls, data):
        data = upgrade(data)
        fields(data, SAVE_FIELDS)
        if data["schema_version"] != SCHEMA_VERSION or data["encounters"] != ENCOUNTER_VERSION:
            raise ValueError("unsupported expedition save")
        result = cls(Exploration.from_dict(data["exploration"]), fresh=False)
        try:
            _load_progress(result, data)
            _load_life(result, data)
            _load_spawns(result, data)
            _load_log(result, data)
            _load_plan(result, data)
        except (TypeError, KeyError) as exc:
            raise ValueError("malformed expedition save") from exc
        if result.life_recipes - set(RECIPE_KEEP_COST):
            raise ValueError("invalid life recipes")
        result._grant_level_unlocks()   # gates reached before this rule existed open on load
        return result
