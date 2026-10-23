"""Content catalog for the forest expedition: biomes, enemies, effects, items, actions,
unlocks, regions and their presentation styles.

WHAT: every piece of world content the auto-pilot can meet, as validated data.
WHY: adding an item, action, recipe, unlock, enemy, biome or region must be a data
edit, not a change to generation, the auto-pilot or the client. The client draws by the
art keys declared here (tests check every key has art).
OWNS: definitions only. Rules that read them live in actions.py (eligibility and
buckets), regions.py (region per chunk), encounters.py (spot placement),
economy.py (currency conversion and anchor purchases) and autopilot/ (execution).
NEVER: reorder or rename ids that existing saves reference without bumping
encounters.ENCOUNTER_VERSION; use floats, wall clock or shared RNG in rules.
TESTS: tests/test_world_catalog.py validates every table and cross-reference.
"""
from dataclasses import dataclass, field

from .models import identifier, integer

ATTRIBUTES = ("strength", "endurance", "agility", "intelligence", "perception", "willpower", "building")

COLOR_DEFAULT = "#e7d7b0"


def _color(value, what):
    if not isinstance(value, str) or len(value) != 7 or value[0] != "#" or \
            any(c not in "0123456789abcdef" for c in value[1:]):
        raise ValueError(f"{what} must be #rrggbb")


# ----- biomes ------------------------------------------------------------------
@dataclass(frozen=True)
class BiomeDef:
    """A kind of land. Danger grows with distance from the anchor in rings: enemy hits
    scale by danger_num/danger_den per ring and enemies gain hp_per_ring hit points."""
    id: str
    name: str
    danger_num: int = 3
    danger_den: int = 2
    hp_per_ring: int = 1
    ring_cap: int = 40             # rings past this add no more danger
    spot_rarity_per_ring: int = 0  # percent added to non-common spot tier odds per ring (0 = depth-neutral)
    mastery_percent: int = 100     # how much work its locations need to be mastered (later lands need more)

    def __post_init__(self):
        identifier(self.id, "biome ID")
        integer(self.spot_rarity_per_ring, "spot rarity per ring", 0, 100)
        integer(self.danger_num, "danger growth numerator", 1, 100)
        integer(self.danger_den, "danger growth denominator", 1, 100)
        integer(self.hp_per_ring, "enemy HP per ring", 0, 100)
        integer(self.ring_cap, "danger ring cap", 0, 1000)
        integer(self.mastery_percent, "location mastery percent", 10, 10000)


BIOMES = {b.id: b for b in (
    BiomeDef("dark_forest", "Dark forest"),
    BiomeDef("ash_plain", "Ash plain", mastery_percent=300),   # terrain exists (assets.py); no content yet
)}


# ----- effects -----------------------------------------------------------------
# Gear changes numbers only through effects. "add" stats sum; "percent" stats
# multiply in turn (integer floor after each source, gear in slot order).
EFFECT_STATS = {
    "punch_damage": "add",          # extra damage per punch
    "enemy_hit_percent": "percent", # damage enemies deal to the avatar
    "food_window_bonus": "add",     # extra at-once cap (low and high) for every food source
    "wood_yield": "add",            # extra sticks from every wood harvest (an axe chops)
}
WOOD_YIELD_ITEM = "stick"           # what a wood_yield effect adds to each harvest tagged "wood"


# ----- attack profiles ------------------------------------------------------------
@dataclass(frozen=True)
class AttackDef:
    """How a weapon (or bare fists) strikes: authoritative reach along the facing, stopped by
    walls (trees, rocks, structures) and by the first enemy in the line. `shape` is the
    client's animation ("punch", "thrust", "swing"). Ranged fields are reserved: a future bow
    sets `projectile`, `ammo` (an item consumed per shot) and keeps `needs_sight`."""
    id: str
    name: str
    reach: int
    shape: str
    needs_sight: bool = True
    projectile: bool = False
    ammo: str | None = None

    def __post_init__(self):
        identifier(self.id, "attack ID")
        integer(self.reach, "attack reach", 1, 8)
        if self.shape not in ("punch", "thrust", "swing"):
            raise ValueError(f"unknown attack shape: {self.id}")
        if self.projectile or self.ammo is not None or not self.needs_sight:
            raise ValueError(f"ranged attacks are reserved, not implemented: {self.id}")


ATTACKS = {a.id: a for a in (
    AttackDef("fists", "Fists", 1, "punch"),
    AttackDef("staff", "Staff thrust", 2, "thrust"),
    AttackDef("spear", "Spear thrust", 3, "thrust"),
    AttackDef("axe", "Axe swing", 1, "swing"),
)}
DEFAULT_ATTACK = "fists"


@dataclass(frozen=True)
class Effect:
    stat: str
    amount: int

    def __post_init__(self):
        if self.stat not in EFFECT_STATS:
            raise ValueError(f"unknown effect stat: {self.stat}")
        if EFFECT_STATS[self.stat] == "percent":
            integer(self.amount, "effect percent", 1, 1000)
        else:
            integer(self.amount, "effect amount", 0, 100)


def _effects(value, what):
    if type(value) is not tuple or any(not isinstance(e, Effect) for e in value):
        raise ValueError(f"{what} effects must be a tuple of Effect")


# ----- rarity -------------------------------------------------------------------
# Cascading tier rolls (encounters.chunk_spots, drops.roll_table): try the rarest tier
# first at its odds; only a miss tries the next; the last tier (common) catches the rest.
# A tier with nothing eligible is skipped, not rolled. Odds are basis points (1/10000).
@dataclass(frozen=True)
class RarityDef:
    """One tier. `spot_odds` is its cascade chance for an encounter spot once `spot_full_weight`
    of its spot weight is eligible here; less eligible weight scales the chance down (so
    one unlocked uncommon is not a quarter of the forest), region/Journal boosts scale it up."""
    id: str
    name: str
    color: str
    spot_odds: int = 0             # basis points; ignored for the fallback tier
    spot_full_weight: int = 1

    def __post_init__(self):
        identifier(self.id, "rarity ID")
        _color(self.color, f"rarity {self.id} color")
        integer(self.spot_odds, "spot tier odds", 0, 10000)
        integer(self.spot_full_weight, "spot tier full weight", 1, 100000)


RARITY_ORDER = ("rare", "uncommon", "common")       # rarest first; the last is the fallback
FALLBACK_RARITY = RARITY_ORDER[-1]
RARITY = {r.id: r for r in (
    RarityDef("rare", "Rare", "#7fb4ff", spot_odds=600, spot_full_weight=10),
    RarityDef("uncommon", "Uncommon", "#8fd17a", spot_odds=2500, spot_full_weight=16),
    RarityDef("common", "Common", COLOR_DEFAULT),
)}
RARITIES = tuple(reversed(RARITY_ORDER))             # common -> rare (labels on items and actions)
TIER_ODDS_CAP = 9000                                 # no non-fallback tier may exceed 90%


def rarity_glint(tier):
    """Client highlight color for a tier (spot sparkle, reward reveal); None for the fallback."""
    return None if tier == FALLBACK_RARITY else RARITY[tier].color


# ----- items ------------------------------------------------------------------
ITEM_KINDS = ("food", "material", "gear", "treasure")   # treasure: no in-run use, carried home as ash
EQUIPMENT_SLOTS = ("weapon", "body")


@dataclass(frozen=True)
class ItemDef:
    """Current-life inventory item. `ash_value` is its prestige value per unit."""
    id: str
    name: str
    kind: str
    food: int = 0       # hunger points restored when eaten
    glyph: str = "*"
    ash_value: int = 1  # dimensional ash before duplicate-resource diminishing returns
    slot: str | None = None   # gear occupies an explicit equipment slot
    effects: tuple = ()       # gear: active while equipped
    color: str = COLOR_DEFAULT   # HUD text and reward popups
    rarity: str = "common"       # reward reveal and stats-page label (odds live in DropTables)
    attack: str | None = None    # weapons: their AttackDef (reach, shape)

    def __post_init__(self):
        identifier(self.id, "item ID")
        if self.rarity not in RARITY:
            raise ValueError(f"item {self.id} has unknown rarity {self.rarity}")
        _effects(self.effects, f"item {self.id}")
        if self.attack is not None and (self.attack not in ATTACKS or self.slot != "weapon"):
            raise ValueError(f"only weapons have an attack: {self.id}")
        if self.slot == "weapon" and self.attack is None:
            raise ValueError(f"a weapon needs an attack: {self.id}")
        _color(self.color, f"item {self.id} color")
        if self.effects and self.kind != "gear":
            raise ValueError(f"only gear has effects: {self.id}")
        if self.kind not in ITEM_KINDS or not isinstance(self.name, str) or not 1 <= len(self.name) <= 40:
            raise ValueError("invalid item kind/name")
        integer(self.food, "food value", 0, 100)
        integer(self.ash_value, "ash value", 0, 100)
        if (self.kind == "food") != (self.food > 0):
            raise ValueError("food, and only food, restores hunger")
        if (self.kind == "gear") != (self.slot in EQUIPMENT_SLOTS):
            raise ValueError("gear must have a valid equipment slot, other items must not")
        if not isinstance(self.glyph, str) or len(self.glyph) != 1 or not 33 <= ord(self.glyph) <= 126:
            raise ValueError("item glyph must be one printable ASCII character")


ITEMS = {item.id: item for item in (
    ItemDef("wild_berries", "Wild berries", "food", 12, "o", ash_value=1, color="#e0505e"),
    ItemDef("bird_egg", "Bird egg", "food", 20, "0", ash_value=2, color="#efe6cf"),
    ItemDef("boar_meat", "Boar meat", "food", 35, "%", ash_value=3, color="#d9776a"),
    ItemDef("venison", "Venison", "food", 28, "v", ash_value=3, color="#c9785a"),
    ItemDef("pale_mushroom", "Pale mushroom", "food", 15, "n", ash_value=2, color="#e8dcc0"),
    ItemDef("snared_hare", "Snared hare", "food", 30, "h", ash_value=3, color="#c7a27a"),
    ItemDef("river_fish", "River fish", "food", 25, "<", ash_value=2, color="#8fb8c8"),
    ItemDef("stick", "Stick", "material", glyph="/", ash_value=1, color="#c39a62"),
    ItemDef("bramble_thorn", "Bramble thorn", "material", glyph="^", ash_value=2, color="#a9c97a"),
    ItemDef("boar_hide", "Boar hide", "material", glyph="#", ash_value=4, color="#a6845d"),
    # Bonus drops (DROP_TABLES). Placeholder treasures: no use yet, worth ash at the anchor.
    ItemDef("boar_tusk", "Boar tusk", "treasure", glyph=")", ash_value=6, color="#efe2c4", rarity="uncommon"),
    ItemDef("deer_antler", "Deer antler", "treasure", glyph="Y", ash_value=6, color="#d8c39b", rarity="uncommon"),
    ItemDef("tarnished_coin", "Tarnished coin", "treasure", glyph="$", ash_value=8, color="#c9b46a",
            rarity="uncommon"),
    ItemDef("amber_charm", "Amber charm", "treasure", glyph="@", ash_value=20, color="#ffb347", rarity="rare"),
    # Gear is worth less than its inputs: crafting spends resources you could carry home.
    ItemDef("hide_wrap", "Hide wrap", "gear", glyph="]", ash_value=6, slot="body",
            effects=(Effect("enemy_hit_percent", 70),), color="#b58c62"),
    ItemDef("padded_jerkin", "Padded jerkin", "gear", glyph="[", ash_value=5, slot="body",
            effects=(Effect("enemy_hit_percent", 80),), color="#c9b48a"),
    ItemDef("studded_wrap", "Studded wrap", "gear", glyph="}", ash_value=9, slot="body",
            effects=(Effect("enemy_hit_percent", 55),), color="#9fa4a8"),
    # Weapons: reach and look (AttackDef) and a little damage. The axe also chops.
    ItemDef("walking_staff", "Walking staff", "gear", glyph="|", ash_value=3, slot="weapon",
            effects=(Effect("punch_damage", 1),), attack="staff", color="#c39a62"),
    ItemDef("spear", "Spear", "gear", glyph="t", ash_value=7, slot="weapon",
            effects=(Effect("punch_damage", 2),), attack="spear", color="#d9ddd0"),
    ItemDef("axe", "Axe", "gear", glyph="P", ash_value=7, slot="weapon",
            effects=(Effect("punch_damage", 3), Effect("wood_yield", 1)), attack="axe", color="#b9bfae"),
    # Site materials (abandoned camps, fallen watchtowers): crafting inputs.
    ItemDef("cloth_scrap", "Cloth scrap", "material", glyph='"', ash_value=2, color="#c8b8a0"),
    ItemDef("old_bone", "Carved bone", "treasure", glyph="=", ash_value=5, color="#d8d2bc"),
    ItemDef("rope", "Coil of rope", "material", glyph="&", ash_value=3, color="#b89a6a"),
    ItemDef("iron_nails", "Iron nails", "material", glyph="!", ash_value=3, color="#a8b0b8"),
    # River finds.
    ItemDef("river_scales", "River scales", "treasure", glyph="*", ash_value=5, color="#9fd0c8", rarity="uncommon"),
    # Night finds.
    ItemDef("wolf_fang", "Wolf fang", "treasure", glyph=">", ash_value=5, color="#e6e0cf"),
)}


@dataclass(frozen=True)
class Loot:
    item: str
    low: int
    high: int
    chance: int = 100   # percent

    def __post_init__(self):
        if self.item not in ITEMS:
            raise ValueError("unknown loot item")
        integer(self.low, "loot minimum", 1, 20)
        integer(self.high, "loot maximum", self.low, 20)
        integer(self.chance, "loot chance", 1, 100)


# ----- buildings (at the anchor camp) ----------------------------------------------
@dataclass(frozen=True)
class BuildingDef:
    """A structure built at the anchor camp from carried resources (a build ActionDef).
    It stands until the life ends; binding it at the anchor for `bind_cost` ash makes it
    permanent. `function`: "crafting" (crafts need it) or "storage" (a chest at the camp)."""
    id: str
    name: str
    description: str
    function: str
    bind_cost: int

    def __post_init__(self):
        identifier(self.id, "building ID")
        if self.function not in ("crafting", "storage"):
            raise ValueError(f"unknown building function: {self.id}")
        if not isinstance(self.name, str) or not 1 <= len(self.name) <= 40 or \
                not isinstance(self.description, str) or not 1 <= len(self.description) <= 160:
            raise ValueError(f"invalid building text: {self.id}")
        integer(self.bind_cost, "bind cost", 1, 100000)


BUILDINGS = {b.id: b for b in (
    BuildingDef("crafting_station", "Crafting station",
                "A workbench by the anchor stone. Every craft needs it, at the camp.", "crafting", 120),
    BuildingDef("storage_chest", "Storage chest",
                "Materials brought to the camp are stowed here. Once bound, they stay for later lives.",
                "storage", 200),
)}
WORKPLACES = ("camp",) + tuple(BUILDINGS)


@dataclass(frozen=True)
class Pick:
    """One entry of a drop-table tier pool: an item stack, or a nested table rolled in full."""
    item: str | None = None
    low: int = 1
    high: int = 1
    weight: int = 1
    table: str | None = None

    def __post_init__(self):
        if (self.item is None) == (self.table is None):
            raise ValueError("a pick names an item or a table")
        if self.item is not None and self.item not in ITEMS:
            raise ValueError(f"unknown pick item {self.item}")
        integer(self.low, "pick minimum", 1, 20)
        integer(self.high, "pick maximum", self.low, 20)
        integer(self.weight, "pick weight", 1, 10000)


@dataclass(frozen=True)
class DropTable:
    """A cascading bonus roll: `odds` per non-fallback tier (basis points), `pools` per tier.
    An empty or missing fallback pool means a miss drops nothing. Ring depth does not apply."""
    id: str
    odds: dict
    pools: dict

    def __post_init__(self):
        identifier(self.id, "drop table ID")
        for tier, value in self.odds.items():
            if tier not in RARITY or tier == FALLBACK_RARITY:
                raise ValueError(f"table {self.id}: odds only for non-fallback tiers")
            integer(value, "drop tier odds", 1, TIER_ODDS_CAP)
        for tier, pool in self.pools.items():
            if tier not in RARITY or type(pool) is not tuple or not pool or \
                    any(not isinstance(p, Pick) for p in pool):
                raise ValueError(f"table {self.id}: pools are nonempty tuples of Pick by tier")
            if tier != FALLBACK_RARITY and tier not in self.odds:
                raise ValueError(f"table {self.id}: tier {tier} has a pool but no odds")
        if set(self.odds) - set(self.pools):
            raise ValueError(f"table {self.id}: odds for a tier without a pool")


DROP_TABLES = {t.id: t for t in (
    DropTable("forest_trinkets", {"rare": 2500},
              {"rare": (Pick("amber_charm"),), "common": (Pick("tarnished_coin"),)}),
    DropTable("boar_spoils", {"rare": 200, "uncommon": 1500},
              {"rare": (Pick(table="forest_trinkets"),), "uncommon": (Pick("boar_tusk"),)}),
    DropTable("deer_spoils", {"rare": 200, "uncommon": 2000},
              {"rare": (Pick(table="forest_trinkets"),), "uncommon": (Pick("deer_antler"),)}),
    DropTable("traveller_cache", {"rare": 400, "uncommon": 2500},
              {"rare": (Pick("amber_charm"),), "uncommon": (Pick("tarnished_coin", 1, 2),)}),
    # Chain payoffs: often only the fixed loot; sometimes more (a common pool always gives).
    DropTable("wood_stash", {"uncommon": 2500}, {"uncommon": (Pick("rope"), Pick("iron_nails")),
                                                 "common": (Pick("stick", 1, 3),)}),
    DropTable("rotten_log", {"rare": 300, "uncommon": 1500},
              {"rare": (Pick("amber_charm"),), "uncommon": (Pick("tarnished_coin"),)}),
    DropTable("hidden_stash", {"rare": 600, "uncommon": 3500},
              {"rare": (Pick("amber_charm"),), "uncommon": (Pick("tarnished_coin", 1, 3), Pick("iron_nails", 1, 2))}),
    DropTable("lurker_spoils", {"rare": 200, "uncommon": 3000},
              {"rare": (Pick(table="forest_trinkets"),), "uncommon": (Pick("river_scales", 1, 2),)}),
    DropTable("bones_spoils", {"rare": 300, "uncommon": 3000},
              {"rare": (Pick("amber_charm"),), "uncommon": (Pick("tarnished_coin", 1, 2), Pick("iron_nails", 1, 2))}),
    DropTable("fishing_camp", {"rare": 300, "uncommon": 2500},
              {"rare": (Pick("amber_charm"),), "uncommon": (Pick("iron_nails", 1, 2), Pick("tarnished_coin"))}),
    DropTable("hunter_trophies", {"rare": 500, "uncommon": 6000},
              {"rare": (Pick(table="forest_trinkets"),),
               "uncommon": (Pick("deer_antler", weight=3), Pick("boar_tusk", weight=2)),
               "common": (Pick("boar_hide"),)}),
    DropTable("shrine_offerings", {"rare": 800, "uncommon": 5000},
              {"rare": (Pick("amber_charm"),), "uncommon": (Pick("tarnished_coin", 1, 3),)}),
    DropTable("barrow_hoard", {"rare": 1200, "uncommon": 4000},
              {"rare": (Pick("amber_charm", 1, 2),), "uncommon": (Pick("tarnished_coin", 2, 4),),
               "common": (Pick("iron_nails", 1, 2),)}),
)}


# ----- actions ----------------------------------------------------------------
# category = what the avatar does; placement = where the action comes from:
#   "spot": a generated point of interest in a chunk (rolled from the spot bucket);
#   "self": something the avatar does wherever it stands (after-location bucket or a need).
CATEGORIES = ("forage", "gather", "observe", "climb", "drink", "meditate", "study", "scavenge",
              "pray", "fight", "hunt", "craft", "reflect", "build", "camp")
PLACEMENTS = ("spot", "lead", "self", "site", "story")   # site: inside a landmark (SITES); story: main quest (STORY)
NEAR = (None, "T", "^", "w")   # spot needs a tree / rock / water (river or ford) beside its cell
TRIGGERS = (None, "after_location", "need")   # self actions only

POSES = ("crouch", "sit", "climb", "kneel")   # how the avatar's body looks while working


@dataclass(frozen=True)
class CategoryStyle:
    """How the client shows an action category: activity verb, body pose, work-mark
    color, and the color of the seal left when a spot is finished (None = default)."""
    verb: str
    pose: str | None = None
    color: str | None = None
    seal: str | None = None

    def __post_init__(self):
        if self.pose is not None and self.pose not in POSES:
            raise ValueError(f"unknown pose: {self.pose}")
        for value in (self.color, self.seal):
            if value is not None:
                _color(value, "category color")


CATEGORY_STYLES = {
    "forage": CategoryStyle("Foraging", "crouch", "#e96c75"),
    "gather": CategoryStyle("Gathering", "crouch", "#d6ac6a"),
    "observe": CategoryStyle("Studying", "crouch", "#e6d6a2"),
    "climb": CategoryStyle("Climbing", "climb", "#b5d58b"),
    "drink": CategoryStyle("Drinking at", "crouch", "#a9eaff", seal="#a9eaff"),
    "meditate": CategoryStyle("Meditating by", "sit", "#c8c5ff"),
    "study": CategoryStyle("Deciphering", "crouch", "#d3b6ff", seal="#d3b6ff"),
    "scavenge": CategoryStyle("Searching", "crouch"),
    "pray": CategoryStyle("Praying at", "kneel", "#fff0b4"),
    "fight": CategoryStyle("Fighting"),
    "hunt": CategoryStyle("Hunting", "crouch", "#c9785a"),
    "craft": CategoryStyle("Crafting", "crouch"),
    "reflect": CategoryStyle("Reflecting", "sit", "#c8c5ff"),
    "build": CategoryStyle("Building", "crouch", "#d9b27a"),
    "camp": CategoryStyle("Making camp", "crouch", "#ffb347"),
}


# ----- enemies -----------------------------------------------------------------
ENEMY_SOUND_PROFILES = ("impact", "beast", "water", "bone", "spectral", "canine")


@dataclass(frozen=True)
class EnemyDef:
    """A creature that hunts the avatar. Its fight spot (ActionDef.enemy) sets where it
    appears, its HP and its loot; this sets how it fights. `hit` is vital points per bite
    at ring 0 (the biome scales it); `cause` is the journal's death-cause id."""
    id: str
    name: str
    hit: int
    aggro_radius: int              # steps: a live enemy this close charges the avatar
    cause: str
    cause_text: str                # "Cause: <cause_text>" in the life report
    sprite: str                    # client art key (combat_art.js ENEMY_SPRITES)
    sound_profile: str = "impact"  # client sound shape, shared by creatures with similar voices
    step_ms: int = 300             # one chasing step this often (lower = faster)
    drains: str = "health"         # what a touch takes: "health" (a bite) or "hunger" (it feeds on you)
    fears_fire: bool = True        # stays out of the anchor camp and campfire light
    life_depth_hit_percent: int = 0  # linear bite growth per deepest ring this life; replaces biome curve
    life_depth_hp_per_ring: int = 0   # linear HP growth per deepest ring this life

    def __post_init__(self):
        identifier(self.id, "enemy ID")
        identifier(self.cause, "death cause")
        identifier(self.sprite, "enemy sprite")
        if self.sound_profile not in ENEMY_SOUND_PROFILES:
            raise ValueError(f"invalid enemy sound profile: {self.id}")
        integer(self.hit, "enemy hit", 1, 100)
        integer(self.aggro_radius, "aggro radius", 1, 30)
        integer(self.step_ms, "enemy step", 100, 2000)
        if type(self.fears_fire) is not bool:
            raise ValueError(f"fears_fire must be boolean: {self.id}")
        integer(self.life_depth_hit_percent, "life depth hit growth", 0, 100)
        integer(self.life_depth_hp_per_ring, "life depth HP growth", 0, 100)
        if self.drains not in ("health", "hunger"):
            raise ValueError(f"enemy drains health or hunger: {self.id}")
        if not 1 <= len(self.name) <= 40 or not 1 <= len(self.cause_text) <= 60:
            raise ValueError(f"invalid enemy text: {self.id}")


ENEMIES = {e.id: e for e in (
    EnemyDef("bramble_boar", "Wild boar", hit=8, aggro_radius=11, cause="boar",
             cause_text="a wild boar", sprite="boar", sound_profile="beast"),
    # Fast and fragile: hides by the water, bites lighter, notices you late (small aggro radius).
    EnemyDef("river_lurker", "River lurker", hit=4, aggro_radius=4, cause="lurker",
             cause_text="a river lurker", sprite="lurker", sound_profile="water", step_ms=200),
    # Slow and stubborn: rises at ruins, takes many blows, walks you down slowly.
    EnemyDef("restless_bones", "Restless bones", hit=6, aggro_radius=5, cause="bones",
             cause_text="restless bones", sprite="skeleton", sound_profile="bone", step_ms=450),
    # Gentle but draining: it does not bite, it feeds - each touch takes hunger, not health.
    EnemyDef("pale_wisp", "Pale wisp", hit=6, aggro_radius=6, cause="wisp",
             cause_text="a pale wisp", sprite="wisp", sound_profile="spectral", step_ms=350, drains="hunger"),
    # Night only: quick and keen-nosed, it follows the avatar into firelight.
    EnemyDef("wolf", "Wolf", hit=9, aggro_radius=10, cause="wolf", cause_text="a wolf in the night",
             sprite="wolf", sound_profile="canine", step_ms=250, fears_fire=False,
             life_depth_hit_percent=15, life_depth_hp_per_ring=1),
)}
# Enemies placed by map assets (not by spot rolls) count against this fight spot's window.
ASSET_ENEMY_ACTION = "bramble_boar"
DEATH_CAUSES = ("starvation", "exhaustion", "return", *dict.fromkeys(e.cause for e in ENEMIES.values()))


REQUIREMENT_KINDS = ("action_count", "item_count", "knowledge", "unlock", "recipe", "level", "gear",
                     "location")   # location: the place the avatar stands in has this mastery grade (id "here")
OUTCOME_KINDS = ("knowledge", "recipe", "lead", "note", "reveal", "shimmer", "renew")
# note: only logs its text (a trail gone cold); reveal: shows the map around the avatar;
# shimmer: rare spots roll more often in this region cell for the rest of the life (id = what caused it);
# renew: the region cell's exhaustion of one ECOLOGY (the id) is lifted
ECOLOGY = ("wood", "berries", "game", "fungi", "eggs", "fish")   # see autopilot/ecology.py
PLACEABLES = ("campfire",)   # things a self action sets down in the world for the rest of the life
NEED_FLAGS = ("camp_wanted",)   # camp_wanted: badly hurt far from any rest place, or in a mastered place whose focus calls for camp
ACTION_ROLES = ("base", "unlockable", "discovery", "lead", "contextual", "craft", "combat", "reflection", "site",
                "story")


@dataclass(frozen=True)
class Requirement:
    kind: str
    id: str
    count: int = 1

    def __post_init__(self):
        if self.kind not in REQUIREMENT_KINDS:
            raise ValueError("invalid requirement kind")
        identifier(self.id, "requirement ID")
        integer(self.count, "requirement count", 1, 10**9)


@dataclass(frozen=True)
class OutcomeDef:
    """Declarative consequence after an action completes; `at_count` is lifetime completions.

    Outcomes without a `group` each roll their own `chance`. Outcomes sharing a `group`
    are alternatives: one roll per completion picks at most one of them, each with its own
    `chance` (they sum to at most 100; the rest is "nothing happens"). `text` is logged
    when the outcome happens (required for a "note")."""
    kind: str
    id: str
    at_count: int = 1
    chance: int = 100
    ttl_ms: int = 0
    group: str | None = None
    text: str | None = None

    def __post_init__(self):
        if self.kind not in OUTCOME_KINDS:
            raise ValueError("invalid outcome kind")
        identifier(self.id, "outcome ID")
        integer(self.at_count, "outcome threshold", 1, 10**9)
        integer(self.chance, "outcome chance", 1, 100)
        integer(self.ttl_ms, "lead lifetime", 0, 600_000)
        if (self.kind == "lead") != (self.ttl_ms > 0):
            raise ValueError("only leads have a positive lifetime")
        if self.group is not None:
            identifier(self.group, "outcome group")
        if self.text is not None and (not isinstance(self.text, str) or not 1 <= len(self.text) <= 120):
            raise ValueError("invalid outcome text")
        if self.kind == "note" and self.text is None:
            raise ValueError("a note outcome needs text")


@dataclass(frozen=True)
class ActionDef:
    id: str
    name: str
    category: str
    placement: str
    attribute: str
    xp: int
    duration_ms: int
    weight: int                       # base weight inside its bucket
    description: str
    log: str
    unlock: str | None = None         # UnlockDef id; None = known from the first life
    biomes: tuple = ("dark_forest",)
    regions: tuple | None = None      # None = every region of an eligible biome
    near: str | None = None
    rarity: str = "common"
    window: tuple | None = None       # (low, high) at-once cap, rolled per life; None = unlimited
    hp: int = 0                       # fights only
    loot: tuple = ()
    heal: int = 0
    cost: tuple = ()                  # ((item, count), ...) consumed (crafts)
    effect: str | None = None         # gear item granted / special outcome key
    trigger: str | None = None        # self actions: when the auto-pilot considers it
    visible_only: bool = False        # self actions that never start during offline catch-up
    tags: tuple = ()
    roles: tuple = ("base",)
    knowledge: str | None = None       # persistent understanding required for this action
    recipe: str | None = None          # persistent recipe discovery required for crafting
    requirements: tuple = ()          # all requirements must hold; see Requirement
    outcomes: tuple = ()              # generic discoveries and temporary leads
    need_priority: int = 0            # lower positive value is considered first
    need_hunger_below: int | None = None
    need_no_food: bool = False
    enemy: str | None = None          # fights: the EnemyDef that appears here
    art: str | None = None            # client sprite key (place_art.js SPOTS); default = id
    color: str | None = None          # overrides the category's work-mark color
    drops: str | None = None          # DropTable id: one bonus cascade roll on completion
    site: str | None = None           # SiteDef id: site actions roll only inside that landmark
    builds: str | None = None         # BuildingDef id this action constructs at the anchor camp
    workplace: str | None = None      # "camp" (at the anchor camp) or a BuildingDef id that must stand there
    interaction: str | None = None    # what the avatar does there ("Picking up sticks"); `name` is the thing
    lead_spread: int = 0              # leads: 0 = placed in the source's chunk, 1 = in a neighbouring chunk
    ecology: str | None = None        # wild spots: what harvesting it depletes nearby this life (ECOLOGY)
    places: str | None = None         # self actions: a thing set down in the world (PLACEABLES), e.g. a campfire
    need_flag: str | None = None      # need actions: a situation flag that must hold (NEED_FLAGS)

    def __post_init__(self):
        identifier(self.id, "action ID")
        if self.art is not None:
            identifier(self.art, "action art")
        if self.color is not None:
            _color(self.color, f"action {self.id} color")
        if (self.category == "fight") != (self.enemy is not None):
            raise ValueError(f"fights, and only fights, name an enemy: {self.id}")
        for name, value, limit in (("name", self.name, 60), ("description", self.description, 160),
                                   ("log", self.log, 120)):
            if not isinstance(value, str) or not 1 <= len(value) <= limit:
                raise ValueError(f"invalid action {name}: {self.id}")
        if self.category not in CATEGORIES or self.placement not in PLACEMENTS:
            raise ValueError(f"invalid category/placement: {self.id}")
        if self.attribute not in ATTRIBUTES or self.rarity not in RARITIES or self.near not in NEAR:
            raise ValueError(f"invalid attribute/rarity/near: {self.id}")
        integer(self.xp, "action XP", 0, 10000)
        integer(self.duration_ms, "action duration", 1, 600000)
        integer(self.weight, "action weight", 1, 10000)
        integer(self.need_priority, "need priority", 0, 1000)
        if self.need_hunger_below is not None:
            integer(self.need_hunger_below, "need hunger threshold", 0, 100)
        if type(self.need_no_food) is not bool:
            raise ValueError("need_no_food must be boolean")
        if self.trigger != "need" and (self.need_priority or self.need_hunger_below is not None or self.need_no_food):
            raise ValueError("only need actions have need policy")
        if self.trigger == "need" and not self.need_priority:
            raise ValueError("need actions require a priority")
        integer(self.hp, "action HP", 0, 6)
        integer(self.heal, "action heal", 0, 100)
        if type(self.biomes) is not tuple or not self.biomes:
            raise ValueError(f"action needs biomes: {self.id}")
        if self.regions is not None and (type(self.regions) is not tuple or not self.regions):
            raise ValueError(f"regions must be None or a nonempty tuple: {self.id}")
        if type(self.loot) is not tuple or any(not isinstance(l, Loot) for l in self.loot):
            raise ValueError(f"loot must be a tuple of Loot: {self.id}")
        if type(self.cost) is not tuple or any(type(c) is not tuple or len(c) != 2 or c[0] not in ITEMS
                                               or integer(c[1], "cost", 1, 20) is None for c in self.cost):
            raise ValueError(f"invalid cost: {self.id}")
        if (self.category == "fight") != (self.hp > 0):
            raise ValueError(f"fights, and only fights, have hit points: {self.id}")
        if (self.category in ("craft", "build", "camp")) != bool(self.cost):
            raise ValueError(f"crafts, buildings and camps, and only they, consume items: {self.id}")
        if self.effect is not None and (self.effect not in ITEMS or ITEMS[self.effect].kind != "gear"):
            raise ValueError(f"effect must name a gear item: {self.id}")
        if self.placement in ("spot", "site") and (self.trigger is not None or self.visible_only):
            raise ValueError(f"spot actions have no trigger: {self.id}")
        if (self.category == "build") != (self.builds is not None):
            raise ValueError(f"build actions, and only build actions, name a building: {self.id}")
        if (self.builds is not None or self.workplace is not None) and self.placement != "self":
            raise ValueError(f"buildings and workplaces are for self actions: {self.id}")
        if self.category == "build" and not self.cost:
            raise ValueError(f"building costs resources: {self.id}")
        if (self.placement == "site") != (self.site is not None):
            raise ValueError(f"site actions, and only site actions, name a site: {self.id}")
        if self.placement == "self" and (self.trigger not in TRIGGERS[1:] or self.near or self.window):
            raise ValueError(f"self actions need a trigger and no placement rules: {self.id}")
        if self.placement == "lead" and (self.trigger is not None or self.window
                                         or (self.hp and self.category != "fight")):
            raise ValueError(f"lead actions cannot use world placement rules: {self.id}")
        if self.workplace is not None and self.workplace not in WORKPLACES:
            raise ValueError(f"unknown workplace: {self.id}")
        if self.builds is not None and self.builds not in BUILDINGS:
            raise ValueError(f"unknown building: {self.id}")
        if self.recipe is not None and (self.category != "craft" or self.placement != "self"):
            raise ValueError(f"only self crafts require recipes: {self.id}")
        if self.knowledge is not None:
            identifier(self.knowledge, "action knowledge")
        if self.recipe is not None:
            identifier(self.recipe, "recipe ID")
        if type(self.requirements) is not tuple or any(not isinstance(r, Requirement) for r in self.requirements):
            raise ValueError(f"invalid requirements: {self.id}")
        if type(self.outcomes) is not tuple or any(not isinstance(o, OutcomeDef) for o in self.outcomes):
            raise ValueError(f"invalid outcomes: {self.id}")
        integer(self.lead_spread, "lead spread", 0, 1)
        if self.ecology is not None and (self.ecology not in ECOLOGY or self.placement != "spot"):
            raise ValueError(f"only wild spots deplete an ecology, from ECOLOGY: {self.id}")
        if self.places is not None and (self.places not in PLACEABLES or self.placement != "self"):
            raise ValueError(f"only self actions place things, from PLACEABLES: {self.id}")
        if self.need_flag is not None and (self.need_flag not in NEED_FLAGS or self.trigger != "need"):
            raise ValueError(f"need flags are for need actions, from NEED_FLAGS: {self.id}")
        if self.lead_spread and self.placement != "lead":
            raise ValueError(f"only leads spread to other chunks: {self.id}")
        groups = {}
        for o in self.outcomes:
            if o.group is not None:
                groups[o.group] = groups.get(o.group, 0) + o.chance
        if any(total > 100 for total in groups.values()):
            raise ValueError(f"outcome group chances exceed 100: {self.id}")
        if self.placement in ("spot", "lead", "site", "story"):   # placed things are named as things, done as interactions
            if not isinstance(self.interaction, str) or not 1 <= len(self.interaction) <= 60:
                raise ValueError(f"placed action needs an interaction: {self.id}")
        elif self.interaction is not None and (not isinstance(self.interaction, str)
                                               or not 1 <= len(self.interaction) <= 60):
            raise ValueError(f"invalid interaction: {self.id}")
        if type(self.roles) is not tuple or not self.roles or any(role not in ACTION_ROLES for role in self.roles):
            raise ValueError(f"invalid action roles: {self.id}")
        if self.window is not None:
            if type(self.window) is not tuple or len(self.window) != 2:
                raise ValueError(f"spawn window must be a (low, high) tuple: {self.id}")
            integer(self.window[0], "spawn window low", 0, 1000)
            integer(self.window[1], "spawn window high", self.window[0], 1000)
        if type(self.tags) is not tuple:
            raise ValueError(f"tags must be a tuple: {self.id}")

    @property
    def sprite(self):
        """Client art key for this action's spot."""
        return self.art or self.id

    @property
    def style(self):
        return CATEGORY_STYLES[self.category]

    @property
    def kind(self):
        """Compatibility name for `category` (older code and the browser client)."""
        return self.category

    @property
    def feeds(self):
        """True if completing it can yield food (the 'food' spawn category)."""
        return any(ITEMS[l.item].kind == "food" for l in self.loot)

    @property
    def spawn_category(self):
        """Category used by spawn pity: 'food', 'enemy' or None."""
        return "enemy" if self.category == "fight" else "food" if self.feeds else None


L = Loot
ACTIONS = (
    # --- known from the first life -------------------------------------------
    ActionDef("bramble_berries", "Berry bush", "forage", "spot", "perception", 40, 2400, 11,
              "Pick berries from a thorny bramble patch.", "Picked bramble berries without getting scratched (much).",
              window=(1, 2), loot=(L("wild_berries", 4, 4), L("bramble_thorn", 1, 1, 35)),
              roles=("base", "discovery"), outcomes=(OutcomeDef("lead", "trampled_bushes", chance=15, ttl_ms=90_000),),
              ecology="berries", interaction="Picking berries"),
    ActionDef("fallen_branches", "Fallen branches", "gather", "spot", "strength", 30, 2200, 18,
              "Gather sticks from branches across the trail.", "Hauled a pile of fallen branches off the trail.",
              regions=("old_road", "deep_woods", "bramble_thicket"), tags=("wood",),
              loot=(L("stick", 1, 1), L("stick", 1, 1, 50)), roles=("base", "discovery"), ecology="wood",
              outcomes=(OutcomeDef("knowledge", "primitive_crafting", at_count=5),
                        OutcomeDef("lead", "broken_branches", chance=15, ttl_ms=90_000)),
              interaction="Picking up sticks"),
    ActionDef("animal_tracks", "Animal tracks", "observe", "spot", "perception", 50, 3000, 12,
              "Read the tracks of what lives here.", "Read fresh tracks in the mud - something heavy passed here.",
              regions=("deep_woods", "still_glade"), roles=("base", "discovery"), ecology="game",
              outcomes=(OutcomeDef("knowledge", "deer_sign"),
                        OutcomeDef("lead", "follow_deer_tracks", chance=30, ttl_ms=90_000),
                        OutcomeDef("recipe", "snare", chance=15,
                                   text="A hare run through the brambles. A loop of thorny stem would catch it.")),
              interaction="Looking at the tracks"),
    ActionDef("follow_deer_tracks", "Deer tracks", "observe", "lead", "perception", 35, 3800, 1,
              "Follow a fresh trail before the deer moves on.", "Followed the tracks to a quiet deer crossing.",
              knowledge="deer_sign", roles=("lead", "contextual"),
              outcomes=(OutcomeDef("lead", "hunt_deer", chance=55, ttl_ms=60_000, group="trail"),
                        OutcomeDef("note", "deer_gone", chance=30, group="trail",
                                   text="The tracks crossed a stream and vanished.")), art="deer_trail",
              interaction="Following the tracks"),
    ActionDef("hunt_deer", "Deer", "hunt", "lead", "agility", 80, 5500, 1,
              "Approach the deer while this trail is still fresh.", "Brought down a deer at the crossing.",
              knowledge="deer_sign", roles=("lead", "combat", "contextual"),
              loot=(L("venison", 1, 1),), drops="deer_spoils", art="deer", interaction="Hunting the deer"),
    # --- forest chains: a find, a clue that leads on, sometimes a payoff ---------------
    ActionDef("broken_branches", "Broken branches", "observe", "lead", "perception", 30, 2600, 1,
              "Branches snapped off at the same height, in a line into the trees.",
              "Followed a line of broken branches.", roles=("lead", "contextual"), lead_spread=1,
              outcomes=(OutcomeDef("lead", "cut_wood", chance=55, ttl_ms=120_000, group="clue"),
                        OutcomeDef("note", "branches_nowhere", chance=45, group="clue",
                                   text="The broken branches led nowhere.")),
              interaction="Looking at the broken branches"),
    ActionDef("cut_wood", "Cut wood", "gather", "lead", "strength", 40, 3400, 1,
              "Wood someone cut and stacked, then left behind.", "Took what was left of a stack of cut wood.",
              roles=("lead", "contextual"), loot=(L("stick", 1, 2),), drops="wood_stash", tags=("wood",),
              interaction="Taking the wood"),
    ActionDef("trampled_bushes", "Trampled bushes", "observe", "lead", "perception", 30, 2400, 1,
              "Bushes pushed flat and stripped. Something big feeds here.",
              "Looked over the trampled bushes.", roles=("lead", "contextual"),
              outcomes=(OutcomeDef("lead", "feeding_ground", chance=50, ttl_ms=90_000, group="clue"),
                        OutcomeDef("lead", "angry_boar", chance=25, ttl_ms=60_000, group="clue",
                                   text="Something grunts in the bushes."),
                        OutcomeDef("note", "fed_and_gone", chance=25, group="clue",
                                   text="Whatever fed here is long gone.")),
              interaction="Looking at the marks"),
    ActionDef("feeding_ground", "Feeding ground", "forage", "lead", "perception", 40, 3000, 1,
              "Bushes the animals have not finished yet.", "Picked what the animals had left.",
              roles=("lead", "contextual"), loot=(L("wild_berries", 2, 3), L("bramble_thorn", 1, 2, 50)),
              interaction="Picking what is left"),
    ActionDef("angry_boar", "Angry boar", "fight", "lead", "strength", 100, 1, 1,
              "A boar guarding its feeding ground.", "Drove off a boar guarding its feeding ground.",
              hp=3, enemy="bramble_boar", loot=(L("boar_meat", 1, 1), L("boar_hide", 1, 1, 60)),
              drops="boar_spoils", roles=("lead", "combat", "contextual"), art="bramble_boar",
              interaction="Fighting the boar"),
    ActionDef("mushroom_dust", "Mushroom dust", "observe", "lead", "perception", 35, 2600, 1,
              "Pale dust on the leaves, drifting from somewhere nearby.", "Followed a trail of mushroom dust.",
              roles=("lead", "contextual"),
              outcomes=(OutcomeDef("lead", "rotten_log", chance=60, ttl_ms=90_000, group="clue"),
                        OutcomeDef("note", "dust_gone", chance=40, group="clue", text="The dust blew away.")),
              interaction="Following the dust"),
    ActionDef("rotten_log", "Rotten log", "forage", "lead", "perception", 45, 3200, 1,
              "A hollow log covered in mushrooms - not all of them safe.",
              "Picked the safe mushrooms off a rotten log.", roles=("lead", "contextual"),
              loot=(L("pale_mushroom", 1, 3, 70),), drops="rotten_log", interaction="Picking mushrooms"),
    ActionDef("trail_marker", "Odd trail marker", "study", "lead", "intelligence", 60, 3400, 1,
              "A marker that points the wrong way.", "Compared the odd marker with the carvings.",
              roles=("lead", "contextual"),
              outcomes=(OutcomeDef("lead", "looping_path", chance=50, ttl_ms=120_000, group="clue"),
                        OutcomeDef("note", "marker_wrong", chance=50, group="clue",
                                   text="The marker was just wrong.")),
              interaction="Comparing the marks"),
    ActionDef("looping_path", "Looping path", "observe", "lead", "intelligence", 80, 4000, 1,
              "A path that bends back on itself. From here you can see how the land lies.",
              "Walked the looping path and learned the lay of the land.", roles=("lead", "contextual"),
              lead_spread=1, outcomes=(OutcomeDef("reveal", "area", text="You can see the paths around you now."),),
              interaction="Walking the loop"),
    ActionDef("map_scrap", "Hand-drawn map", "study", "lead", "intelligence", 40, 3000, 1,
              "A scrap of map from an old backpack, with a mark on it.", "Worked out where the map points.",
              roles=("lead", "contextual"),
              outcomes=(OutcomeDef("lead", "hidden_stash", chance=60, ttl_ms=150_000, group="clue"),
                        OutcomeDef("note", "map_useless", chance=40, group="clue",
                                   text="The map was too faded to follow.")),
              interaction="Reading the map"),
    ActionDef("hidden_stash", "Hidden stash", "scavenge", "lead", "strength", 50, 3600, 1,
              "The spot marked on the map. Someone may have got here first.",
              "Dug up the spot marked on the map.", roles=("lead", "contextual"), lead_spread=1,
              loot=(L("cloth_scrap", 1, 2, 60), L("rope", 1, 1, 40)), drops="hidden_stash",
              interaction="Digging up the stash"),
    ActionDef("forest_spring", "Forest spring", "drink", "spot", "endurance", 40, 2000, 9,
              "Drink and catch your breath.", "Drank from a cold spring and caught your breath.",
              window=(1, 2), heal=10, roles=("base", "discovery"), interaction="Drinking water",
              outcomes=(OutcomeDef("lead", "fresh_footprints", chance=8, ttl_ms=90_000),)),
    # --- the riverbank: anything beside a river or ford, in any region ------------------
    ActionDef("reed_bed", "Reeds", "forage", "spot", "perception", 35, 2600, 7,
              "Tall reeds at the water's edge. Birds nest here, and fish hide below.",
              "Pushed through the reeds at the water's edge.", near="w", window=(1, 2), roles=("base", "discovery"),
              loot=(L("bird_egg", 1, 1, 50),),
              outcomes=(OutcomeDef("lead", "fish_scales", chance=30, ttl_ms=90_000),),
              interaction="Searching the reeds"),
    ActionDef("fishing_pool", "Fishing pool", "hunt", "spot", "agility", 45, 3600, 9,
              "A slow, deep pool under the bank. Fish - if you are patient.",
              "Waited at a deep pool for the fish to bite.", near="w", window=(0, 2), ecology="fish",
              roles=("base",), loot=(L("river_fish", 1, 1, 75),),
              outcomes=(OutcomeDef("lead", "lurker_burrow", chance=10, ttl_ms=60_000,
                                   text="Something big moves under the water."),),
              interaction="Fishing"),
    ActionDef("river_shallows", "Shallows", "observe", "spot", "perception", 40, 2400, 4,
              "Clear, shallow water over stones. Easy to read what lives here.",
              "Watched the shallows for a while.", near="w", roles=("base", "discovery"),
              outcomes=(OutcomeDef("lead", "ripples", chance=35, ttl_ms=60_000),),
              interaction="Looking into the water"),
    ActionDef("fishing_net", "Old fishing net", "scavenge", "spot", "strength", 40, 3000, 3,
              "A net caught on the bank, half rotten. The rope is still good.",
              "Untangled an old fishing net from the bank.", near="w", rarity="uncommon", window=(0, 1),
              roles=("base", "discovery"), loot=(L("rope", 1, 1), L("cloth_scrap", 1, 1, 50)),
              outcomes=(OutcomeDef("lead", "float_line", chance=35, ttl_ms=120_000),),
              interaction="Untangling the net"),
    ActionDef("river_lurker", "River lurker", "fight", "spot", "strength", 80, 1, 3,
              "A fast, slick thing that waits by the water. It bites lighter than a boar.",
              "Drove off a river lurker.", near="w", window=(0, 1), hp=2, enemy="river_lurker",
              loot=(L("river_fish", 1, 1, 50),), drops="lurker_spoils", roles=("base", "combat"),
              interaction="Fighting the lurker"),
    # --- river chains -------------------------------------------------------------------
    ActionDef("fish_scales", "Fish scales", "observe", "lead", "perception", 30, 2200, 1,
              "Silver scales caught in the reeds. Something feeds nearby.", "Followed the scales along the bank.",
              near="w", roles=("lead", "contextual"),
              outcomes=(OutcomeDef("lead", "busy_pool", chance=50, ttl_ms=90_000, group="clue"),
                        OutcomeDef("lead", "lurker_burrow", chance=20, ttl_ms=60_000, group="clue",
                                   text="Something big moves under the water."),
                        OutcomeDef("note", "scales_gone", chance=30, group="clue",
                                   text="Only scales - whatever left them has gone.")),
              interaction="Following the scales"),
    ActionDef("busy_pool", "Busy pool", "hunt", "lead", "agility", 50, 3400, 1,
              "Fish rising in a quiet pool.", "Caught fish in a quiet pool.", near="w",
              roles=("lead", "contextual"), loot=(L("river_fish", 1, 2, 80),), interaction="Fishing"),
    ActionDef("ripples", "Ripples", "observe", "lead", "perception", 35, 2400, 1,
              "Rings on the water that do not move with the current.", "Watched the strange ripples.",
              near="w", roles=("lead", "contextual"),
              outcomes=(OutcomeDef("lead", "lurker_burrow", chance=50, ttl_ms=60_000, group="clue",
                                   text="A burrow in the bank. Something is home."),
                        OutcomeDef("note", "just_current", chance=50, group="clue", text="Just the current.")),
              interaction="Watching the ripples"),
    ActionDef("lurker_burrow", "River lurker", "fight", "lead", "strength", 80, 1, 1,
              "A river lurker, out of its burrow and angry.", "Drove off a river lurker from its burrow.",
              hp=2, enemy="river_lurker", loot=(L("river_fish", 1, 1, 50),), drops="lurker_spoils",
              roles=("lead", "combat", "contextual"), art="river_lurker", interaction="Fighting the lurker"),
    # --- the night: wolves pursue the avatar even at camp (autopilot/night.py) ----
    ActionDef("night_wolf", "Wolf", "fight", "lead", "strength", 60, 1, 1,
              "A wolf out of the dark. It hunts at night and slinks away at dawn.", "Drove off a wolf in the dark.",
              hp=3, enemy="wolf", loot=(L("wolf_fang", 1, 1, 45),), tags=("night",),
              roles=("lead", "combat", "contextual"), interaction="Fighting the wolf"),
    ActionDef("float_line", "Torn float line", "observe", "lead", "perception", 35, 2600, 1,
              "Floats and line from the net, drifting downstream.", "Traced the float line downstream.",
              lead_spread=1, near="w", roles=("lead", "contextual"),
              outcomes=(OutcomeDef("lead", "fishing_platform", chance=60, ttl_ms=120_000, group="clue"),
                        OutcomeDef("note", "line_lost", chance=40, group="clue",
                                   text="The line snagged and sank.")),
              interaction="Following the line"),
    ActionDef("fishing_platform", "Broken fishing platform", "scavenge", "lead", "strength", 45, 3400, 1,
              "Planks and posts in the water. Someone fished from here.", "Pulled rope and bait off a broken platform.",
              near="w", roles=("lead", "contextual"), loot=(L("rope", 1, 2), L("river_fish", 1, 1, 40)),
              interaction="Pulling up the planks"),
    ActionDef("bootprints", "Muddy bootprints", "observe", "lead", "perception", 35, 2600, 1,
              "Bootprints from the old campfire, heading for water.", "Followed muddy bootprints.",
              lead_spread=1, roles=("lead", "contextual"),
              outcomes=(OutcomeDef("lead", "fishing_camp", chance=50, ttl_ms=150_000, group="clue"),
                        OutcomeDef("note", "camp_looted", chance=30, group="clue",
                                   text="The fishing camp was already picked clean."),
                        OutcomeDef("note", "prints_lost", chance=20, group="clue",
                                   text="The prints vanished on hard ground.")),
              interaction="Following the bootprints"),
    ActionDef("fishing_camp", "Fishing camp", "scavenge", "lead", "perception", 50, 3600, 1,
              "A fisherman's camp by the river, left in a hurry.", "Searched a fisherman's camp by the river.",
              near="w", lead_spread=1, roles=("lead", "contextual"), loot=(L("river_fish", 1, 2), L("rope", 1, 1, 50)),
              drops="fishing_camp", interaction="Searching the camp"),
    ActionDef("fresh_footprints", "Fresh footprints", "observe", "lead", "perception", 30, 2400, 1,
              "Footprints from the spring, heading upstream.", "Traced fresh footprints upstream.",
              roles=("lead", "contextual"),
              outcomes=(OutcomeDef("lead", "hidden_ford", chance=55, ttl_ms=120_000, group="clue"),
                        OutcomeDef("note", "prints_washed", chance=45, group="clue",
                                   text="The rain had washed the prints away.")),
              interaction="Following the footprints"),
    ActionDef("double_shadow", "Double shadow", "observe", "lead", "perception", 45, 3000, 1,
              "A second shadow on the moss, pointing where no sun could put it.",
              "Followed a shadow that did not belong to anything.", roles=("lead", "contextual"),
              outcomes=(OutcomeDef("lead", "split_shadow_tree", chance=60, ttl_ms=150_000, group="clue",
                                   text="The shadow slides away between the trees."),
                        OutcomeDef("note", "shadow_gone", chance=40, group="clue",
                                   text="The second shadow slipped under the rock and was gone.")),
              interaction="Following the shadow"),
    ActionDef("split_shadow_tree", "Split-shadow tree", "meditate", "lead", "willpower", 90, 4500, 1,
              "A tree that throws two shadows, one for a sun that is not there.",
              "Stood between the two shadows of a tree until the air hummed.", near="T", lead_spread=1,
              roles=("lead", "contextual"), interaction="Standing between the shadows",
              outcomes=(OutcomeDef("shimmer", "split_shadow", text="The air hums. Rare things feel closer here."),)),
    ActionDef("hidden_ford", "Hidden ford", "observe", "lead", "intelligence", 60, 3200, 1,
              "Stepping stones under the water. From here the river makes sense.",
              "Found a hidden ford and learned the lie of the river.", near="w", lead_spread=1,
              roles=("lead", "contextual"),
              outcomes=(OutcomeDef("reveal", "area", text="You can see the river and the paths around it now."),
                        OutcomeDef("lead", "lurker_burrow", chance=25, ttl_ms=60_000,
                                   text="Something was waiting at the ford.")),
              interaction="Crossing the stones"),
    ActionDef("bramble_boar", "Wild boar", "fight", "spot", "strength", 100, 1, 9,
              "A territorial boar that charges anything nearby. Meat and hide.",
              "Drove off a wild boar.", window=(1, 2), hp=3, enemy="bramble_boar",
              loot=(L("boar_meat", 1, 1), L("boar_hide", 1, 1, 60)), drops="boar_spoils",
              roles=("base", "combat"), interaction="Fighting the boar",
              outcomes=(OutcomeDef("recipe", "hide_wrap", chance=30,
                                   text="Skinning it, you see how the hide could be worn."),)),
    # --- opened by dimensional levels (UNLOCKS) ------------------------------------
    ActionDef("gnarled_tree", "Old tree", "climb", "spot", "agility", 60, 3200, 10,
              "Climb for bird eggs and a look over the canopy.", "Climbed a gnarled tree and scouted the canopy.",
              unlock="climbing", near="T", window=(1, 1),
              loot=(L("bird_egg", 1, 1, 60), L("stick", 1, 1, 40)), roles=("unlockable",), ecology="eggs",
              interaction="Climbing for eggs"),
    ActionDef("dead_tree", "Dead tree", "gather", "spot", "strength", 45, 3600, 8,
              "A standing dead tree, dry right through. Good firewood - with an axe.",
              "Chopped a dead tree into an armful of wood.", near="T", ecology="wood", tags=("wood",),
              requirements=(Requirement("gear", "axe"),), loot=(L("stick", 2, 3),),
              roles=("base", "contextual"), interaction="Chopping the dead tree"),
    ActionDef("mushroom_ring", "Mushrooms", "forage", "spot", "perception", 55, 3200, 8,
              "Pale mushrooms that are safe - if you know which ones.",
              "Gathered the safe mushrooms from a pale ring.", unlock="mushroom_lore",
              regions=("deep_woods",), window=(1, 1),
              loot=(L("pale_mushroom", 1, 2),), roles=("unlockable", "discovery"), ecology="fungi",
              outcomes=(OutcomeDef("lead", "mushroom_dust", chance=20, ttl_ms=90_000),), interaction="Picking mushrooms"),
    ActionDef("mossy_stone", "Mossy rock", "meditate", "spot", "willpower", 60, 4000, 7,
              "Sit with the stone until the forest goes quiet.", "Sat by a mossy stone until the forest went quiet.",
              unlock="meditation", near="^", roles=("unlockable",), interaction="Resting by the rock",
              outcomes=(OutcomeDef("lead", "double_shadow", chance=12, ttl_ms=90_000,
                                   text="Your shadow has company. A second one, cast the wrong way."),)),
    # --- rare phenomena: small impossible things, never currency -------------------------
    ActionDef("hanging_leaf", "Hanging leaf", "observe", "spot", "perception", 70, 3000, 3,
              "A leaf hangs in the air at eye level, not falling, not moving.",
              "Watched a leaf that would not fall.", regions=("deep_woods", "still_glade"), rarity="rare",
              window=(0, 1), roles=("base", "discovery"), interaction="Watching the leaf",
              outcomes=(OutcomeDef("reveal", "area", text="For a moment the whole forest held its breath, and you saw far."),)),
    ActionDef("backward_ripple", "Backward ripple", "observe", "spot", "perception", 70, 3000, 3,
              "For a few heartbeats the water here runs uphill.",
              "Watched the stream run backward, then right itself.", near="w", rarity="rare", window=(0, 1),
              roles=("base", "discovery"), interaction="Watching the water",
              outcomes=(OutcomeDef("renew", "fish", text="The pools around here are full of fish again."),)),
    ActionDef("moonlit_pool", "Clear pool", "drink", "spot", "endurance", 45, 2600, 5,
              "A still pool that steadies body and mind.", "Drank from a still pool beneath the branches.",
              unlock="meditation", rarity="uncommon", window=(0, 1), heal=12, roles=("unlockable",),
              interaction="Drinking water"),
    ActionDef("old_carvings", "Old carvings", "study", "spot", "intelligence", 80, 3600, 5,
              "Marks that look almost like a summoning circle.",
              "Traced old carvings - the marks look almost like a summoning circle.",
              unlock="road_lore", rarity="uncommon", roles=("unlockable", "discovery"),
              outcomes=(OutcomeDef("lead", "trail_marker", chance=30, ttl_ms=120_000),), interaction="Reading the carvings"),
    # --- opened by Willpower (shrine path) ------------------------------------------
    ActionDef("wayside_shrine", "Roadside shrine", "pray", "spot", "willpower", 50, 3600, 6,
              "A moss-grown shrine on the old road. Prayer here is always heard.",
              "Knelt at a wayside shrine and prayed to the gods who spared you.",
              unlock="shrine_path", regions=("old_road",), rarity="uncommon", window=(1, 1),
              roles=("unlockable",), interaction="Praying at the shrine"),
    # --- site actions: rolled only inside a landmark (SITES) ------------------------
    ActionDef("camp_packs", "Old backpacks", "scavenge", "site", "strength", 40, 3100, 10,
              "Packs left by travellers who never came back.",
              "Rummaged through packs the travellers left behind.", unlock="scavenging", site="abandoned_camp",
              loot=(L("stick", 1, 2), L("cloth_scrap", 1, 2, 70)), drops="traveller_cache",
              outcomes=(OutcomeDef("lead", "map_scrap", chance=35, ttl_ms=120_000),),
              roles=("site", "unlockable", "discovery"), interaction="Searching the bags"),
    ActionDef("camp_firepit", "Old campfire", "scavenge", "site", "perception", 35, 2600, 8,
              "Ashes, a cooking spit and whatever was left tied up nearby.",
              "Sifted a cold firepit and untied what was left.", unlock="scavenging", site="abandoned_camp",
              loot=(L("rope", 1, 1, 60), L("bramble_thorn", 1, 1, 40)), roles=("site", "unlockable", "discovery"),
              outcomes=(OutcomeDef("lead", "bootprints", chance=35, ttl_ms=120_000),),
              interaction="Searching the ashes"),
    ActionDef("camp_bedroll", "Torn blanket", "scavenge", "site", "endurance", 35, 2800, 7,
              "Bedding stuffed with wool - and a way to stitch it into something useful.",
              "Pulled the stuffing from a torn bedroll.", unlock="scavenging", site="abandoned_camp",
              loot=(L("cloth_scrap", 1, 3),), roles=("site", "unlockable", "discovery"),
              outcomes=(OutcomeDef("recipe", "padded_jerkin"),), interaction="Pulling out the stuffing"),
    ActionDef("tower_rubble", "Fallen stones", "scavenge", "site", "strength", 45, 3400, 10,
              "Fallen stones, rotten beams and the nails that held them.",
              "Dug nails and splinters out of the tower rubble.", unlock="road_lore", site="fallen_watchtower",
              loot=(L("iron_nails", 1, 2, 80), L("stick", 1, 1)), drops="traveller_cache",
              roles=("site", "unlockable"), interaction="Digging through the stones"),
    ActionDef("tower_stair", "Broken stairs", "climb", "site", "agility", 60, 3600, 6,
              "What is left of the stair still reaches a nest and the old lookout.",
              "Climbed the broken stair to the lookout.", unlock="road_lore", site="fallen_watchtower",
              loot=(L("bird_egg", 1, 1, 50),), roles=("site", "unlockable"), interaction="Climbing the stairs"),
    ActionDef("tower_armory", "Old weapon rack", "scavenge", "site", "strength", 55, 4000, 5,
              "Racks crushed under the wall. Studs and straps for whoever can use them.",
              "Pried studs and straps from the collapsed armory.", unlock="road_lore", site="fallen_watchtower",
              loot=(L("iron_nails", 2, 3),), roles=("site", "unlockable", "discovery"),
              outcomes=(OutcomeDef("recipe", "studded_wrap"),), interaction="Pulling out nails"),
    ActionDef("tower_marks", "Scratched warnings", "study", "site", "intelligence", 75, 4200, 6,
              "Faded warnings scratched into the tower wall.",
              "Studied the faded warning marks on the tower wall.", unlock="road_lore", site="fallen_watchtower",
              art="old_carvings", roles=("site", "unlockable"), interaction="Reading the warnings"),
    ActionDef("lumber_logs", "Log pile", "gather", "site", "strength", 40, 3000, 10,
              "Cut logs stacked to season - the loggers never came back for them.",
              "Split kindling and sticks off a stack of seasoned logs.", unlock="scavenging", site="woodcutters_clearing",
              loot=(L("stick", 2, 3),), tags=("wood",), roles=("site", "unlockable"), interaction="Breaking off sticks"),
    ActionDef("lumber_shed", "Tool shed", "scavenge", "site", "perception", 45, 3200, 8,
              "A lean-to of planks, its tools long gone. Some of the fittings are still there.",
              "Pried rope and nails from a woodcutters' tool shed.", unlock="scavenging", site="woodcutters_clearing",
              loot=(L("rope", 1, 1, 70), L("iron_nails", 1, 2, 60)), drops="traveller_cache",
              roles=("site", "unlockable", "discovery"), outcomes=(OutcomeDef("recipe", "axe"),),
              interaction="Searching the shed"),
    ActionDef("lumber_oak", "Fallen tree", "climb", "site", "agility", 50, 3000, 6,
              "A great oak left where it fell, its crown full of old nests.",
              "Climbed through the crown of a felled oak.", unlock="scavenging", site="woodcutters_clearing",
              loot=(L("bird_egg", 1, 2, 70), L("stick", 1, 2)), tags=("wood",), roles=("site", "unlockable"),
              interaction="Climbing the branches"),
    ActionDef("lodge_racks", "Hide racks", "scavenge", "site", "strength", 45, 3400, 9,
              "Frames of hides left to dry. Some are still good.",
              "Cut the sound hides down from a hunter's drying racks.", unlock="snares", site="hunters_lodge",
              loot=(L("boar_hide", 1, 2), L("rope", 1, 1, 40)), roles=("site", "unlockable"),
              interaction="Taking the hides"),
    ActionDef("lodge_snares", "Old traps", "hunt", "site", "perception", 45, 3000, 8,
              "A line of snares around the lodge, one of them still sprung.",
              "Walked the old snare line around the lodge.", unlock="snares", site="hunters_lodge",
              loot=(L("snared_hare", 1, 1, 70), L("bramble_thorn", 1, 2)), roles=("site", "unlockable"),
              outcomes=(OutcomeDef("recipe", "snare"),), interaction="Checking the traps"),
    ActionDef("lodge_trophies", "Antler wall", "scavenge", "site", "intelligence", 55, 3600, 5,
              "Antlers and tusks nailed above the lodge door.",
              "Took down what was worth keeping from the trophy wall.", unlock="snares", site="hunters_lodge",
              drops="hunter_trophies", roles=("site", "unlockable", "discovery"),
              outcomes=(OutcomeDef("recipe", "spear"),), interaction="Taking down the antlers"),
    ActionDef("shrine_altar", "Broken altar", "pray", "site", "willpower", 60, 4200, 8,
              "The altar is split in two, but someone still listens here.",
              "Prayed at the broken altar of a ruined shrine.", unlock="shrine_path", site="ruined_shrine",
              roles=("site", "unlockable"), interaction="Praying at the altar"),
    ActionDef("shrine_offerings", "Coin bowls", "scavenge", "site", "perception", 50, 3200, 7,
              "Bowls of green coins and beads, left for gods nobody remembers.",
              "Sifted the offering bowls of a ruined shrine.", unlock="meditation", site="ruined_shrine",
              drops="shrine_offerings", roles=("site", "unlockable"), interaction="Taking the coins"),
    ActionDef("shrine_pillars", "Carved pillars", "study", "site", "intelligence", 85, 4400, 6,
              "Pillars carved with circles inside circles - the same marks as the anchor stone.",
              "Traced the circles carved into the shrine pillars.", unlock="meditation", site="ruined_shrine",
              roles=("site", "unlockable"), interaction="Studying the carvings"),
    ActionDef("barrow_goods", "Old grave", "scavenge", "site", "strength", 60, 4200, 8,
              "The barrow's mouth has fallen in. Whatever was buried with them is within reach.",
              "Dug through the fallen mouth of an old barrow.", unlock="road_lore", site="old_barrow",
              loot=(L("cloth_scrap", 1, 2, 60),), drops="barrow_hoard", roles=("site", "unlockable"),
              interaction="Digging in the grave"),
    ActionDef("barrow_stones", "Stone circle", "meditate", "site", "willpower", 70, 4600, 7,
              "Standing stones around the mound. The air between them is very still.",
              "Sat inside the ring of standing stones until the stillness passed.", unlock="road_lore",
              site="old_barrow", heal=10, roles=("site", "unlockable"), interaction="Sitting in the circle"),
    ActionDef("barrow_bones", "Bone pile", "observe", "site", "perception", 50, 3000, 6,
              "Bones of animals that came to the barrow and never left.",
              "Picked through a pile of old bones by the barrow.", unlock="road_lore", site="old_barrow",
              loot=(L("boar_tusk", 1, 1, 30), L("stick", 1, 1)), roles=("site", "unlockable"),
              interaction="Searching the bones"),
    # Ruins are guarded: restless bones rise at burial mounds and fallen watchtowers, known
    # from the first life (a locked ruin is dangerous long before it is worth searching).
    ActionDef("barrow_dead", "Restless bones", "fight", "site", "strength", 110, 1, 9,
              "Bones that will not lie still. Slow, but hard to put down.",
              "Put the restless bones back to rest.", site="old_barrow", hp=5, enemy="restless_bones",
              loot=(L("old_bone", 1, 2),), drops="bones_spoils", roles=("site", "combat"),
              interaction="Fighting the bones"),
    ActionDef("tower_guard", "Fallen guard", "fight", "site", "strength", 90, 1, 5,
              "What is left of a watchman, still walking his round in rusted mail.",
              "Laid the fallen guard to rest.", site="fallen_watchtower", hp=4, enemy="restless_bones",
              loot=(L("old_bone", 1, 1), L("iron_nails", 1, 1, 50)), drops="bones_spoils", roles=("site", "combat"),
              interaction="Fighting the guard"),
    ActionDef("shrine_wisp", "Pale wisp", "fight", "site", "willpower", 90, 1, 6,
              "A cold light that drifts between the pillars. It does not bite - it feeds.",
              "Scattered the pale wisp.", site="ruined_shrine", hp=3, enemy="pale_wisp",
              loot=(L("tarnished_coin", 1, 1, 50),), roles=("site", "combat"), interaction="Scattering the wisp"),
    # --- self actions -----------------------------------------------------------
    ActionDef("think", "Think about the road", "reflect", "self", "intelligence", 0, 3000, 40,
              "A quiet thought after a task.", "Thought about the road behind you.", trigger="after_location",
              roles=("reflection", "contextual"), color="#b6bed1"),
    ActionDef("contemplate", "Contemplate the forest", "reflect", "self", "willpower", 0, 5000, 30,
              "A longer, wordless pause.", "Contemplated the forest for a while.", trigger="after_location",
              roles=("reflection", "contextual")),
    ActionDef("craft_jerkin", "Stitch a padded jerkin", "craft", "self", "endurance", 30, 6000, 1,
              "Cloth and rope become a jerkin: enemy hits hurt 20% less this life.",
              "Stitched cloth scraps into a padded jerkin.", cost=(("cloth_scrap", 3), ("rope", 1)),
              effect="padded_jerkin", trigger="need", need_priority=4, recipe="padded_jerkin",
              workplace="crafting_station",
              roles=("craft", "contextual"), requirements=(Requirement("knowledge", "primitive_crafting"),)),
    ActionDef("craft_studded", "Stud the hide wrap", "craft", "self", "strength", 40, 6000, 1,
              "Nails hammered into a hide wrap: enemy hits hurt 45% less this life.",
              "Hammered iron studs into the hide wrap.", cost=(("hide_wrap", 1), ("iron_nails", 3)),
              effect="studded_wrap", trigger="need", need_priority=2, recipe="studded_wrap",
              workplace="crafting_station",
              roles=("craft", "contextual"), requirements=(Requirement("knowledge", "primitive_crafting"),)),
    ActionDef("craft_snare", "Set a bramble snare", "craft", "self", "perception", 30, 6000, 1,
              "Sticks and a thorn become a snare that usually catches a hare.",
              "Set a bramble snare and checked it.", recipe="snare",
              cost=(("stick", 2), ("bramble_thorn", 1)), loot=(L("snared_hare", 1, 1, 75),), trigger="need",
              need_priority=3, need_hunger_below=60, need_no_food=True,
              workplace="crafting_station",
              roles=("craft", "contextual")),
    ActionDef("craft_wrap", "Wrap boar hide", "craft", "self", "endurance", 30, 5000, 1,
              "Two hides become a wrap: boar hits hurt 30% less this life.",
              "Wrapped boar hide around your arms and chest.", recipe="hide_wrap",
              cost=(("boar_hide", 2),), effect="hide_wrap", trigger="need",
              need_priority=1,
              workplace="crafting_station",
              roles=("craft", "contextual")),
    # Weapons (crafting station). The spear and the axe are built on a staff: crafting one
    # replaces the staff, and a worn weapon is never replaced by a craft that keeps it.
    ActionDef("craft_staff", "Cut a walking staff", "craft", "self", "strength", 25, 5000, 1,
              "A straight length of wood: hits from two steps away, a little harder.",
              "Cut and smoothed a walking staff.", cost=(("stick", 5),), effect="walking_staff",
              trigger="need", need_priority=5, workplace="crafting_station",
              roles=("craft", "contextual"), requirements=(Requirement("knowledge", "primitive_crafting"),)),
    ActionDef("craft_spear", "Make a spear", "craft", "self", "strength", 45, 7000, 1,
              "Nails and rope turn the staff into a spear: hits from three steps away.",
              "Bound an iron point to the staff - a spear.", cost=(("walking_staff", 1), ("iron_nails", 2), ("rope", 1)),
              effect="spear", trigger="need", need_priority=3, recipe="spear", workplace="crafting_station",
              roles=("craft", "contextual"), requirements=(Requirement("knowledge", "primitive_crafting"),)),
    ActionDef("craft_axe", "Make an axe", "craft", "self", "strength", 45, 7000, 1,
              "An iron head on the staff: heavy close blows, and it chops wood.",
              "Fixed an iron head to the staff - an axe.", cost=(("walking_staff", 1), ("iron_nails", 3)),
              effect="axe", trigger="need", need_priority=4, recipe="axe", workplace="crafting_station",
              roles=("craft", "contextual"), requirements=(Requirement("knowledge", "primitive_crafting"),)),
    # --- buildings at the anchor camp --------------------------------------------------
    ActionDef("make_campfire", "Make camp", "camp", "self", "building", 15, 4000, 1,
              "A campfire in a mastered place: rest by it as at the anchor, and the avatar keeps to this place.",
              "Made camp by a small fire.", cost=(("stick", 3),), places="campfire",
              trigger="need", need_flag="camp_wanted", need_priority=1, roles=("contextual",),
              requirements=(Requirement("location", "here", 2),), interaction="Making a campfire"),
    ActionDef("build_station", "Build a crafting station", "build", "self", "building", 120, 20000, 1,
              "A workbench by the anchor stone: crafting becomes possible at the camp.",
              "Built a crafting station beside the anchor stone.", cost=(("stick", 12), ("boar_hide", 2)),
              builds="crafting_station", workplace="camp", trigger="need", need_priority=1,
              roles=("craft", "contextual"), requirements=(Requirement("knowledge", "primitive_crafting"),)),
    ActionDef("build_chest", "Build a storage chest", "build", "self", "building", 150, 25000, 1,
              "A nailed chest at the camp that holds materials between trips.",
              "Built a storage chest at the camp.", cost=(("stick", 10), ("iron_nails", 4), ("rope", 2)),
              builds="storage_chest", workplace="crafting_station", trigger="need", need_priority=6,
              roles=("craft", "contextual"), requirements=(Requirement("knowledge", "primitive_crafting"),)),
)
# ----- the main story: placed, guaranteed, permanent ----------------------------------------
# Story actions (placement "story") never enter a bucket. The current step of STORY (the first
# whose knowledge is not yet held) is placed once a life in the first chunk entered inside its
# rings (autopilot/story.py); finishing it teaches the step's knowledge, which every later life
# keeps. Story text: docs/design/STORY.md.
STORY_ACTIONS = (
    ActionDef("old_man_camp", "The old man's camp", "study", "story", "intelligence", 60, 5000, 1,
              "A cold fire, a bedroll and a page pinned under a stone.",
              "Read the old man's notes by his cold fire.", art="camp_firepit", roles=("story",),
              outcomes=(OutcomeDef("knowledge", "story_camp"),), interaction="Reading the old man's notes"),
    ActionDef("summoner_mark", "Summoner's mark", "study", "story", "intelligence", 90, 6000, 1,
              "The anchor stone's circle, cut into a boulder by the road.",
              "Traced a summoner's mark. Its arrow points away from the anchor.", art="old_carvings",
              unlock="road_lore", roles=("story",),
              outcomes=(OutcomeDef("knowledge", "story_mark"),), interaction="Tracing the old mark"),
    ActionDef("old_man", "The old man", "observe", "story", "intelligence", 120, 12000, 1,
              "The old man from the road, waiting by a fallen log.",
              "Listened to the old man's story of the summoners.", art="elder", roles=("story",),
              outcomes=(OutcomeDef("knowledge", "story_elder"),), interaction="Listening to the old man"),
    ActionDef("dead_gate", "Dead gate", "study", "story", "intelligence", 250, 9000, 1,
              "A ring of standing stones taller than a house. Its keystone has three empty sockets.",
              "Studied the dead gate deep in the forest.", art="dead_gate", roles=("story",),
              requirements=(Requirement("level", "willpower", 3),),
              outcomes=(OutcomeDef("knowledge", "story_gate"),), interaction="Studying the dead gate"),
)
ACTIONS = ACTIONS + STORY_ACTIONS
BY_ID = {action.id: action for action in ACTIONS}


# ----- unlocks, mastery ---------------------------------------------------
CURRENCIES = ("ash",)
ABILITIES = ("contact_anchor",)   # engine capabilities an unlock can grant


@dataclass(frozen=True)
class UnlockDef:
    """A permanent new possibility. Actions open by themselves as the soul grows: `level` is
    (attribute, dimensional level) and is granted when reached (dimensional levels carry across
    lives). Abilities and favours are still bought at the anchor (`currency`, `cost`)."""
    id: str
    name: str
    description: str
    currency: str | None = None
    cost: int = 0
    requires: tuple = ()
    ability: str | None = None     # a capability the engine checks (ABILITIES), not an action
    level: tuple | None = None     # (attribute, dimensional level) that opens it, instead of a price

    def __post_init__(self):
        identifier(self.id, "unlock ID")
        if self.ability is not None and self.ability not in ABILITIES:
            raise ValueError(f"unknown ability: {self.ability}")
        if not 1 <= len(self.name) <= 40 or not 1 <= len(self.description) <= 160:
            raise ValueError(f"invalid unlock: {self.id}")
        if self.level is not None:
            if (type(self.level) is not tuple or len(self.level) != 2 or self.level[0] not in ATTRIBUTES
                    or self.currency is not None or self.cost):
                raise ValueError(f"a level unlock names (attribute, level) and has no price: {self.id}")
            integer(self.level[1], "unlock level", 1, 100)
        else:
            if self.currency not in CURRENCIES:
                raise ValueError(f"invalid unlock: {self.id}")
            integer(self.cost, "unlock cost", 1, 10000)


UNLOCKS = {u.id: u for u in (
    UnlockDef("return_anchor", "Contact anchor", "Reach the anchor mid-life to spend ash, then resume where you left off. Recharges in 5 minutes.",
              "ash", 10, ability="contact_anchor"),
    # Opened by dimensional levels (permanent), roughly in the order a soul grows into them.
    UnlockDef("climbing", "Climbing", "Gnarled trees appear: bird eggs and sticks.", level=("strength", 2)),
    UnlockDef("scavenging", "Scavenging", "Abandoned camps and logging camps open up: sticks, rope, nails.",
              level=("perception", 2)),
    UnlockDef("snares", "Snare lines", "Hunter's cabins open up: hides, snares and their traps.",
              level=("perception", 3)),
    UnlockDef("meditation", "Meditation", "Mossy stones and moonlit pools appear; ruined shrines open up.",
              level=("endurance", 2)),
    UnlockDef("mushroom_lore", "Mushroom lore", "Mushroom rings become food.", level=("perception", 4)),
    UnlockDef("road_lore", "Road lore", "Old carvings, watchtowers and burial mounds open up: Intelligence XP.",
              level=("endurance", 3)),
    UnlockDef("shrine_path", "Shrine path", "Roadside shrines appear on the old road; ruined shrines' altars open.",
              level=("willpower", 3)),
)}


# Journal tree (details.encounter_tree): wild spots are grouped by what you do there; landmark
# encounters by their site; leads hang under whatever opens them; night creatures have their own branch.
JOURNAL_GROUPS = (
    ("food", "Food and water", ("forage", "drink", "hunt")),
    ("wood", "Wood and finds", ("gather", "climb", "scavenge")),
    ("signs", "Signs and lore", ("observe", "study")),
    ("quiet", "Quiet places", ("meditate", "pray")),
    ("danger", "Danger", ("fight",)),
)
_grouped = {c for _, _, cats in JOURNAL_GROUPS for c in cats}
for _a in ACTIONS:
    if _a.placement == "spot" and _a.category not in _grouped:
        raise ValueError(f"journal group missing for category {_a.category} ({_a.id})")



# Actions removed from the catalog that older pinned world saves may still name (region
# weights are pinned with the world). They are accepted there and never rolled.
RETIRED_ACTIONS = frozenset({"abandoned_camp", "fallen_watchtower"})   # craft_staff came back with weapons


# ----- regions ---------------------------------------------------------------------
@dataclass(frozen=True)
class RegionDef:
    """A named stretch of a biome spanning REGION_CELL x REGION_CELL chunks.
    `weights` multiplies spot-action weights in percent (100 = unchanged, 0 = never)."""
    id: str
    name: str
    biome: str
    weight: int
    tint: str
    weights: dict = field(default_factory=dict)
    canopy: int = 50               # density of blocking trees off the connecting paths
    brush: int = 10                # density of walkable region props
    landmark: str = "road"         # visual/terrain grammar within the biome

    def __post_init__(self):
        identifier(self.id, "region ID")
        integer(self.weight, "region weight", 1, 1000)
        if not isinstance(self.tint, str) or len(self.tint) != 7 or self.tint[0] != "#":
            raise ValueError(f"region tint must be #rrggbb: {self.id}")
        integer(self.canopy, "region canopy", 0, 100)
        integer(self.brush, "region brush", 0, 100)
        if self.landmark not in ("road", "grove", "thicket", "glade"):
            raise ValueError(f"invalid region landmark: {self.id}")
        for action, percent in self.weights.items():
            if action not in BY_ID and action not in RETIRED_ACTIONS:
                raise ValueError(f"region weight for unknown action: {self.id}/{action}")
            integer(percent, "region weight percent", 0, 1000)

    def multiplier(self, action_id):
        return self.weights.get(action_id, 100)


# Tree kinds: how a blocking tree ("T") looks - presentation only, the same collision for all,
# and kept out of RegionDef on purpose (region definitions are pinned into world seeds).
# session.py picks one kind per tree cell from the chunk seed and these weights; client art:
# nature_art.js TREE_ART (tests check every kind has art).
TREE_KINDS = {"oak": "Oak", "pine": "Pine", "birch": "Birch", "dead": "Dead tree", "old": "Old mossy tree"}
REGION_TREES = {
    "old_road": (("oak", 5), ("birch", 3), ("dead", 1)),
    "deep_woods": (("pine", 5), ("old", 3), ("oak", 2)),
    "bramble_thicket": (("oak", 3), ("dead", 3), ("birch", 1)),
    "still_glade": (("birch", 5), ("old", 2), ("oak", 2)),
}
DEFAULT_TREES = (("oak", 1),)
for _region, _mix in REGION_TREES.items():
    if not _mix or any(kind not in TREE_KINDS or integer(weight, "tree weight", 1, 100) is None
                       for kind, weight in _mix):
        raise ValueError(f"invalid tree mix: {_region}")

REGION_CELL = 3        # chunks per region side
ORIGIN_REGION = "old_road"   # the ambush road runs through the anchor's region
REGIONS = {r.id: r for r in (
    RegionDef("old_road", "The Old Road", "dark_forest", 3, "#2a2716",
              {"old_carvings": 150,
               "bramble_berries": 120, "bramble_boar": 70, "mushroom_ring": 50,
               "fallen_branches": 75}, 34, 12, "road"),
    RegionDef("deep_woods", "Deep Woods", "dark_forest", 3, "#101a10",
              {"bramble_boar": 250, "gnarled_tree": 200, "mushroom_ring": 200, "animal_tracks": 150,
               "bramble_berries": 60, "forest_spring": 70, "fallen_branches": 160,
               "hunt_deer": 90}, 78, 22, "grove"),
    RegionDef("bramble_thicket", "Bramble Thicket", "dark_forest", 2, "#22180f",
              {"bramble_berries": 300, "bramble_boar": 130, "fallen_branches": 130, "forest_spring": 60},
              68, 58, "thicket"),
    RegionDef("still_glade", "Still Glade", "dark_forest", 2, "#13201d",
              {"forest_spring": 220, "moonlit_pool": 300, "mossy_stone": 220, "bramble_boar": 40,
               "animal_tracks": 140, "follow_deer_tracks": 130, "hunt_deer": 125}, 18, 8, "glade"),
)}

# ----- recipes: found during a life, kept for later lives with ash -------------------------
# A recipe outcome teaches a craft for the rest of that life; at the anchor the soul can keep it
# (pass the knowledge on) for this much ash. Every recipe a craft names must be here.
RECIPE_KEEP_COST = {"snare": 15, "hide_wrap": 20, "padded_jerkin": 25, "spear": 35, "axe": 35, "studded_wrap": 40}
RECIPE_NAMES = {"snare": "Bramble snare", "hide_wrap": "Hide wrap", "padded_jerkin": "Padded jerkin",
                "spear": "Spear", "axe": "Axe", "studded_wrap": "Studded wrap"}

# ----- sites (landmarks) --------------------------------------------------------------
SITE_CELL = 3          # at most one site per SITE_CELL x SITE_CELL chunks (one candidate chunk each)
STRUCTURES = ("camp", "tower", "lumber", "lodge", "shrine", "barrow")   # terrain layout styles in open_terrain (client tile art by glyph)


@dataclass(frozen=True)
class SiteDef:
    """A rare landmark generated into the terrain (generator v5): a clearing with structures
    and its own encounter bucket (ActionDef placement "site"). `weights` are per-mille chances,
    per region, that the block's candidate chunk holds this site. Pinned in world saves, so
    changing placement fields never moves an existing world's sites."""
    id: str
    name: str
    biome: str
    weights: dict
    structure: str
    spots: tuple = (2, 4)          # site encounters rolled per life
    size: tuple = (6, 3)           # clearing half-width, half-height in tiles
    min_ring: int = 2              # never this close to the anchor
    rarity: str = "uncommon"       # label and map color only

    def __post_init__(self):
        identifier(self.id, "site ID")
        if not isinstance(self.name, str) or not 1 <= len(self.name) <= 40:
            raise ValueError(f"invalid site name: {self.id}")
        if self.structure not in STRUCTURES:
            raise ValueError(f"unknown site structure: {self.id}")
        if type(self.weights) is not dict or not self.weights:
            raise ValueError(f"site needs region weights: {self.id}")
        for region, permille in self.weights.items():
            identifier(region, "site region")
            integer(permille, "site weight", 1, 1000)
        for name, pair, low, high in (("spots", self.spots, 0, 8), ("size", self.size, 2, 7)):
            if type(pair) is not tuple or len(pair) != 2:
                raise ValueError(f"site {name} must be a pair: {self.id}")
            integer(pair[0], f"site {name}", low, high)
            integer(pair[1], f"site {name}", pair[0] if name == "spots" else low, high)
        integer(self.min_ring, "site minimum ring", 0, 1000)
        if self.rarity not in RARITY:
            raise ValueError(f"unknown site rarity: {self.id}")


SITES = {s.id: s for s in (
    SiteDef("abandoned_camp", "Abandoned camp", "dark_forest",
            {"old_road": 350, "deep_woods": 150, "bramble_thicket": 150, "still_glade": 100}, "camp", spots=(2, 3)),
    SiteDef("fallen_watchtower", "Fallen watchtower", "dark_forest",
            {"old_road": 300, "deep_woods": 150}, "tower", spots=(2, 4), size=(6, 3), min_ring=3),
    SiteDef("woodcutters_clearing", "Logging camp", "dark_forest",
            {"deep_woods": 200, "old_road": 100}, "lumber", spots=(2, 3), size=(6, 3)),
    SiteDef("hunters_lodge", "Hunter's cabin", "dark_forest",
            {"bramble_thicket": 250, "deep_woods": 150}, "lodge", spots=(2, 3), size=(5, 3), min_ring=3),
    SiteDef("ruined_shrine", "Ruined shrine", "dark_forest",
            {"still_glade": 250, "deep_woods": 100}, "shrine", spots=(2, 3), size=(5, 3), min_ring=4,
            rarity="rare"),
    SiteDef("old_barrow", "Burial mound", "dark_forest",
            {"bramble_thicket": 150, "deep_woods": 100, "old_road": 50}, "barrow", spots=(2, 3), size=(6, 3),
            min_ring=5, rarity="rare"),
)}


@dataclass(frozen=True)
class SiteConditionDef:
    """How a landmark is this life (one per site per life, `sites.condition_for`). `weight` is
    relative among the conditions that fit the site's structure. A condition changes how many
    of the site's own encounters roll (`spots_delta`, never below one), may `add` spot actions
    inside the clearing (an animal's den, a bramble patch), stretches site work
    (`duration_percent`) and can turn off the bonus drop roll of site encounters (`drops`)."""
    id: str
    name: str
    text: str
    weight: int
    structures: tuple | None = None    # None = any site
    spots_delta: int = 0
    adds: tuple = ()
    duration_percent: int = 100
    drops: bool = True

    def __post_init__(self):
        identifier(self.id, "site condition ID")
        for value, what, top in ((self.name, "name", 30), (self.text, "text", 90)):
            if not isinstance(value, str) or not 1 <= len(value) <= top:
                raise ValueError(f"invalid site condition {what}: {self.id}")
        integer(self.weight, "site condition weight", 1, 1000)
        integer(self.spots_delta, "site spots delta", -2, 2)
        integer(self.duration_percent, "site duration percent", 50, 300)
        if self.structures is not None and (type(self.structures) is not tuple
                                            or any(st not in STRUCTURES for st in self.structures)):
            raise ValueError(f"site condition structures must be known: {self.id}")
        if type(self.adds) is not tuple or type(self.drops) is not bool:
            raise ValueError(f"invalid site condition: {self.id}")


SITE_CONDITIONS = {c.id: c for c in (
    SiteConditionDef("quiet", "Quiet", "Nothing has disturbed this place.", 50),
    SiteConditionDef("picked_over", "Already searched", "Someone has been through here already.", 20,
                     spots_delta=-1, drops=False),
    SiteConditionDef("untouched", "Untouched", "No one has been here in a long time.", 10, spots_delta=1),
    SiteConditionDef("den", "Animal den", "Something has made its den here.", 14,
                     structures=("camp", "tower", "lumber", "lodge", "barrow"), adds=("bramble_boar",)),
    SiteConditionDef("overgrown", "Overgrown", "Brambles have grown over everything.", 12,
                     structures=("camp", "tower", "lumber", "lodge", "shrine", "barrow"),
                     adds=("bramble_berries",), duration_percent=140),
)}


# Compatibility of neighboring region cells. This affects geography only; action
# eligibility and odds remain on RegionDef. Keep versioned with regions.py so an
# existing world's saved geography is never silently changed by a tuning edit.
REGION_ADJACENCY_V2 = {
    "old_road": {"old_road": 5, "deep_woods": 2, "bramble_thicket": 2, "still_glade": 2},
    "deep_woods": {"old_road": 2, "deep_woods": 5, "bramble_thicket": 4, "still_glade": 3},
    "bramble_thicket": {"old_road": 2, "deep_woods": 4, "bramble_thicket": 5, "still_glade": 2},
    "still_glade": {"old_road": 2, "deep_woods": 3, "bramble_thicket": 2, "still_glade": 5},
}


def _check_nesting(table_id, path):
    if table_id not in DROP_TABLES:
        raise ValueError(f"unknown nested drop table {table_id}")
    if table_id in path:
        raise ValueError(f"drop table cycle: {' -> '.join(path + (table_id,))}")
    for pool in DROP_TABLES[table_id].pools.values():
        for pick in pool:
            if pick.table is not None:
                _check_nesting(pick.table, path + (table_id,))


def validate_catalog():
    """Cross-reference checks; raises ValueError on the first problem."""
    if set(CATEGORY_STYLES) != set(CATEGORIES):
        raise ValueError("every action category needs a CategoryStyle")
    if ASSET_ENEMY_ACTION not in BY_ID or BY_ID[ASSET_ENEMY_ACTION].enemy is None:
        raise ValueError("ASSET_ENEMY_ACTION must be a fight spot")
    if WOOD_YIELD_ITEM not in ITEMS:
        raise ValueError("WOOD_YIELD_ITEM must name an item")
    for region in REGIONS.values():
        if region.biome not in BIOMES:
            raise ValueError(f"region {region.id} names unknown biome {region.biome}")
    for site in SITES.values():
        if site.biome not in BIOMES or any(r not in REGIONS or REGIONS[r].biome != site.biome for r in site.weights):
            raise ValueError(f"site {site.id} names an unknown biome or region")
    for biome in BIOMES:
        for region in REGIONS:
            if sum(site.weights.get(region, 0) for site in SITES.values() if site.biome == biome) > 1000:
                raise ValueError(f"site weights in {region} exceed 1000 per mille")
    if tuple(RARITY) != RARITY_ORDER:
        raise ValueError("RARITY must list every tier in RARITY_ORDER (rarest first)")
    for table in DROP_TABLES.values():
        _check_nesting(table.id, ())
    for action in ACTIONS:
        if action.site is not None and (action.site not in SITES or SITES[action.site].biome not in action.biomes):
            raise ValueError(f"action {action.id} names an unknown site or one outside its biomes")
        if action.drops is not None and action.drops not in DROP_TABLES:
            raise ValueError(f"action {action.id} names unknown drop table {action.drops}")
        if action.enemy is not None and action.enemy not in ENEMIES:
            raise ValueError(f"action {action.id} names unknown enemy {action.enemy}")
        if any(biome not in BIOMES for biome in action.biomes):
            raise ValueError(f"action {action.id} names an unknown biome")
        if action.unlock is not None and action.unlock not in UNLOCKS:
            raise ValueError(f"action {action.id} names unknown unlock {action.unlock}")
        for region in action.regions or ():
            if region not in REGIONS:
                raise ValueError(f"action {action.id} names unknown region {region}")
        if action.placement == "spot":
            for region_id in action.regions or ():
                if REGIONS[region_id].biome not in action.biomes:
                    raise ValueError(f"action {action.id} region outside its biomes")
        for outcome in action.outcomes:
            if outcome.kind == "lead" and (outcome.id not in BY_ID or BY_ID[outcome.id].placement != "lead"):
                raise ValueError(f"action {action.id} names invalid lead {outcome.id}")
            if outcome.kind == "renew" and outcome.id not in ECOLOGY:
                raise ValueError(f"action {action.id} renews unknown ecology {outcome.id}")
        for requirement in action.requirements:
            choices = {"action_count": BY_ID, "item_count": ITEMS, "unlock": UNLOCKS, "gear": ITEMS,
                       "level": ATTRIBUTES}
            if requirement.kind in choices and requirement.id not in choices[requirement.kind]:
                raise ValueError(f"action {action.id} has invalid prerequisite {requirement.id}")
    recipe_sources = {o.id for a in ACTIONS for o in a.outcomes if o.kind == "recipe"}
    for action in ACTIONS:
        if action.recipe is not None and (action.recipe not in RECIPE_KEEP_COST or action.recipe not in recipe_sources):
            raise ValueError(f"recipe {action.recipe} needs a keep cost and something that teaches it")
    if set(RECIPE_KEEP_COST) != set(RECIPE_NAMES):
        raise ValueError("every kept recipe needs a name")
    for condition in SITE_CONDITIONS.values():
        for added in condition.adds:
            if added not in BY_ID or BY_ID[added].placement != "spot":
                raise ValueError(f"site condition {condition.id} adds a non-spot action {added}")
    if "quiet" not in SITE_CONDITIONS:
        raise ValueError("site conditions need a plain 'quiet' default")
    knowledge_sources = {o.id for action in ACTIONS for o in action.outcomes if o.kind == "knowledge"}
    recipe_sources = {o.id for action in ACTIONS for o in action.outcomes if o.kind == "recipe"}
    for action in ACTIONS:
        if action.knowledge is not None and action.knowledge not in knowledge_sources:
            raise ValueError(f"action {action.id} has no knowledge source")
        if action.recipe is not None and action.recipe not in recipe_sources:
            raise ValueError(f"action {action.id} has no recipe source")
    for unlock in UNLOCKS.values():
        for required in unlock.requires:
            if required not in UNLOCKS or required == unlock.id:
                raise ValueError(f"unlock {unlock.id} requires unknown {required}")
        if unlock.ability is None and not any(a.unlock == unlock.id for a in ACTIONS):
            raise ValueError(f"unlock {unlock.id} opens no action or ability")
    if ORIGIN_REGION not in REGIONS:
        raise ValueError("origin region missing")
    if set(REGION_ADJACENCY_V2) != set(REGIONS):
        raise ValueError("region adjacency rows must cover the catalog")
    for region, neighbors in REGION_ADJACENCY_V2.items():
        if set(neighbors) != set(REGIONS):
            raise ValueError(f"region adjacency row incomplete: {region}")
        for neighbor, value in neighbors.items():
            integer(value, "region adjacency weight", 1, 100)
            if value != REGION_ADJACENCY_V2[neighbor][region]:
                raise ValueError("region adjacency must be symmetric")
    table_items = {}
    for table in DROP_TABLES.values():
        table_items[table.id] = {p.item for pool in table.pools.values() for p in pool if p.item}
    reachable = set()
    for action in ACTIONS:
        pending = [action.drops] if action.drops else []
        while pending:
            table = pending.pop()
            reachable |= table_items[table]
            pending += [p.table for pool in DROP_TABLES[table].pools.values() for p in pool if p.table]
    for item in ITEMS.values():
        sources = [a for a in ACTIONS if any(l.item == item.id for l in a.loot) or a.effect == item.id] or \
            ([item.id] if item.id in reachable else [])
        if not sources:
            raise ValueError(f"item {item.id} has no source")


validate_catalog()


# ----- lands: how far each land can be explored (generator v7, edges.py) ----------------------
@dataclass(frozen=True)
class LandDef:
    """The explorable area of one dimension (a land). Every chunk up to `edge_ring` can be reached;
    a chunk in rings edge_ring+1..`lobe_ring` can be too where its region cell rolls under
    `lobe_percent`, so the edge is ragged, not a square. Past that the land is closed by what is
    there: impassable thicket in the woods, fallen trees across a road, a broken bridge over a river."""
    dimension: str
    name: str
    edge_ring: int
    lobe_ring: int
    lobe_percent: int

    def __post_init__(self):
        identifier(self.dimension, "land dimension")
        integer(self.edge_ring, "land edge ring", 1, 1000)
        integer(self.lobe_ring, "land lobe ring", self.edge_ring, 1000)
        integer(self.lobe_percent, "land lobe percent", 0, 100)


# Rings 5-6: where auto-pilot lives level off (docs/design/STORY.md measurements).
LANDS = {land.dimension: land for land in (
    LandDef("forest", "The forest", edge_ring=5, lobe_ring=6, lobe_percent=45),
)}

# ----- locations: kinds of place the avatar masters (docs/design/LOCATIONS.md) ----------------
@dataclass(frozen=True)
class LocationDef:
    """A kind of place. Every encounter finished in it (wild spots and leads by the region of their
    chunk, landmark encounters by their site) adds to its lifetime mastery. At CAMP_GRADE a camp
    (the campfire) can be made there, and the camp holds the avatar to that place with a focus."""
    id: str
    name: str
    kind: str          # "region" or "site"
    members: tuple     # RegionDef ids or SiteDef ids
    text: str

    def __post_init__(self):
        identifier(self.id, "location ID")
        if self.kind not in ("region", "site") or type(self.members) is not tuple or not self.members:
            raise ValueError(f"invalid location: {self.id}")
        if not 1 <= len(self.name) <= 40 or not 1 <= len(self.text) <= 120:
            raise ValueError(f"invalid location text: {self.id}")


LOCATIONS = {loc.id: loc for loc in (
    LocationDef("old_road", "The Old Road", "region", ("old_road",), "The road through the woods, and the open ground beside it."),
    LocationDef("deep_woods", "Deep Woods", "region", ("deep_woods",), "Old pines and big trees: wood, game and mushrooms."),
    LocationDef("bramble_thicket", "Bramble Thicket", "region", ("bramble_thicket",), "Thorns and berries, and the boars that eat them."),
    LocationDef("still_glade", "Still Glade", "region", ("still_glade",), "Springs, pools and deer in the quiet clearings."),
    LocationDef("abandoned_camp", "Abandoned camp", "site", ("abandoned_camp",), "Tents left standing, and whatever their owners dropped."),
    LocationDef("logging_camp", "Logging camp", "site", ("woodcutters_clearing",), "Log piles and a tool shed the loggers never came back for."),
    LocationDef("hunters_cabin", "Hunter's cabin", "site", ("hunters_lodge",), "Racks, traps and trophies of a hunter long gone."),
    LocationDef("old_ruins", "Old ruins", "site", ("fallen_watchtower", "ruined_shrine", "old_barrow"),
                "Fallen watchtowers, ruined shrines and burial mounds, and what guards them."),
)}
LOCATION_OF_REGION = {m: loc.id for loc in LOCATIONS.values() if loc.kind == "region" for m in loc.members}
LOCATION_OF_SITE = {m: loc.id for loc in LOCATIONS.values() if loc.kind == "site" for m in loc.members}
# Lifetime encounters finished there for each grade, at a biome's mastery_percent of 100. Measured
# (seed 3, 5 h, before locations): about 100 encounters an hour on the Old Road, 25-90 in the other
# regions, 5-10 at landmarks - so the Old Road is mastered in the first life or two, landmarks in hours.
# 1 Known: the Journal shows what is found there; 2 Mastered: you or the avatar can make camp there;
# 3 Deep: rare and uncommon finds there are LOCATION_DEEP_RARITY_PERCENT as likely.
LOCATION_GRADE_NAMES = ("New", "Known", "Mastered", "Deep")
LOCATION_GRADES = {"region": (10, 40, 400), "site": (3, 12, 60)}
CAMP_GRADE = 2
LOCATION_DEEP_RARITY_PERCENT = 150
# A camp's focus: what the avatar goes after while camped there. Spot rolls in the camp's area
# weigh focus categories FOCUS_PERCENT and the rest UNFOCUS_PERCENT. Choosing any focus for a
# mastered place also tells the avatar to make camp there on its own; with none chosen only the
# player makes camp there (while possessing it), and the camp then goes after everything.
LOCATION_FOCUS = {
    "all": ("Everything", None),
    "resources": ("Resources", ("forage", "gather", "hunt", "drink", "climb")),
    "searching": ("Searching", ("observe", "study", "scavenge", "meditate", "pray")),
}
FOCUS_PERCENT = 200
UNFOCUS_PERCENT = 50
CAMP_IDLE_MS = 120_000   # nothing to do in the camp's area this long: the avatar breaks camp


def location_thresholds(location_id):
    """Encounters needed for grades 1-3 of a location (its biome's mastery_percent applied)."""
    loc = LOCATIONS[location_id]
    biome = REGIONS[loc.members[0]].biome if loc.kind == "region" else SITES[loc.members[0]].biome
    percent = BIOMES[biome].mastery_percent
    return tuple(-(-need * percent // 100) for need in LOCATION_GRADES[loc.kind])


def location_grade(location_id, done):
    return sum(done >= need for need in location_thresholds(location_id))


def _validate_locations():
    if set(LOCATION_OF_REGION) != set(REGIONS):
        raise ValueError("every region needs exactly one location")
    if set(LOCATION_OF_SITE) != set(SITES):
        raise ValueError("every site needs exactly one location")
    for loc in LOCATIONS.values():
        table = REGIONS if loc.kind == "region" else SITES
        if any(m not in table for m in loc.members):
            raise ValueError(f"location {loc.id} names an unknown {loc.kind}")
    for grades in LOCATION_GRADES.values():
        if list(grades) != sorted(set(grades)) or len(LOCATION_GRADE_NAMES) != len(grades) + 1:
            raise ValueError("location grades must rise")
    for _, cats in LOCATION_FOCUS.values():
        if cats is not None and any(c not in CATEGORIES for c in cats):
            raise ValueError("location focus names an unknown category")


_validate_locations()

# ----- story steps ---------------------------------------------------------------------------
@dataclass(frozen=True)
class StoryStepDef:
    """One step of the main story. `action` is its story ActionDef (placement "story"), whose
    knowledge outcome must be `id`. `rings` is (lowest, highest) chunk ring where it may be placed.
    `objective` is the HUD line while it is the
    current step; `lore` lines are logged when it is finished and kept on the Story page."""
    id: str
    chapter: int
    action: str
    rings: tuple
    objective: str
    lore: tuple

    def __post_init__(self):
        identifier(self.id, "story step ID")
        integer(self.chapter, "story chapter", 1, 99)
        if type(self.rings) is not tuple or len(self.rings) != 2:
            raise ValueError(f"story rings must be a pair: {self.id}")
        if not isinstance(self.objective, str) or not 1 <= len(self.objective) <= 90:
            raise ValueError(f"invalid story objective: {self.id}")
        if type(self.lore) is not tuple or not self.lore or any(
                not isinstance(line, str) or not 1 <= len(line) <= 220 for line in self.lore):
            raise ValueError(f"invalid story lore: {self.id}")


STORY_CHAPTERS = {1: "The dead gate"}
STORY_NEXT = "Chapter 2 is not written yet: find the keystones."
STORY = (
    StoryStepDef("story_camp", 1, "old_man_camp", (1, 3), "Find the old man's camp along the road",
                 ("A cold fire, a bedroll, and a page pinned under a stone: a rubbing of the anchor stone's carvings.",
                  "Under it, in a shaky hand: \"The marks on the old road were cut by the same hands. Follow them.\"")),
    StoryStepDef("story_mark", 1, "summoner_mark", (2, 5), "Find a summoner's mark on the old road",
                 ("The same circle as on the anchor stone, cut deep into a boulder by the road.",
                  "An arrow under it points deeper into the forest. Every mark points the same way.")),
    StoryStepDef("story_elder", 1, "old_man", (1, 2), "Tell the old man what the marks show",
                 ("\"So the marks still point the way. Then you've earned the rest.\"",
                  "\"This forest had summoners once. They raised stone gates to call help from other lands, "
                  "and anchors to call their own back from death.\"",
                  "\"One night the gates would not close. What came through still walks: the pale lights, "
                  "the dead at the mounds.\"",
                  "\"The last summoners pulled the keystones out of the gates and carried each one away to "
                  "another land, so no gate could open again.\"",
                  "\"One gate still stands deep in these woods. Go and look at it - when your will is strong "
                  "enough to bear it.\"")),
    StoryStepDef("story_gate", 1, "dead_gate", (4, 6), "Find the dead gate deep in the forest (needs Willpower 3)",
                 ("A ring of standing stones taller than a house, carved with the summoning circle.",
                  "The keystone has three sockets, all empty: one for each land the summoners closed it to.",
                  "\"Find the keystones,\" the old man said. \"Then you will see what a summoner can call.\"")),
)
STORY_BY_ID = {step.id: step for step in STORY}
STORY_BY_ACTION = {step.action: step for step in STORY}


def story_rings(step):
    """(lowest, highest) chunk ring of a story step."""
    return step.rings


def _validate_story():
    if len(STORY_BY_ID) != len(STORY) or len(STORY_BY_ACTION) != len(STORY):
        raise ValueError("story steps and their actions must be unique")
    for step in STORY:
        action = BY_ID.get(step.action)
        if action is None or action.placement != "story":
            raise ValueError(f"story step {step.id} needs a story action")
        if not any(o.kind == "knowledge" and o.id == step.id for o in action.outcomes):
            raise ValueError(f"story action {action.id} must teach its step's knowledge")
        if step.chapter not in STORY_CHAPTERS:
            raise ValueError(f"story step {step.id} names an unknown chapter")
        for value in step.rings:
            integer(value, "story ring", 1, 1000)
        low, high = story_rings(step)
        if low > high:
            raise ValueError(f"story rings out of order: {step.id}")
    for action in ACTIONS:
        if action.placement == "story" and action.id not in STORY_BY_ACTION:
            raise ValueError(f"story action {action.id} belongs to no story step")


_validate_story()


# ----- journal achievements ------------------------------------------------------
# Metrics (journal.metric): "action:<id>", "category:<category>", "item:<id>", "deaths:<cause>",
# "deaths", "lives", "best_depth", "best_life_min", "unlocks".
@dataclass(frozen=True)
class AchievementDef:
    id: str
    name: str
    description: str
    metric: str
    threshold: int

    def __post_init__(self):
        identifier(self.id, "achievement ID")
        integer(self.threshold, "achievement threshold", 1, 10**9)
        kind, _, arg = self.metric.partition(":")
        valid = {"action": BY_ID, "category": set(CATEGORIES), "item": ITEMS,
                 "deaths": set(DEATH_CAUSES)}
        if kind in valid:
            if arg not in valid[kind] and not (kind == "deaths" and arg == ""):
                raise ValueError(f"achievement {self.id}: unknown metric argument {arg}")
        elif kind not in ("lives", "best_depth", "best_life_min", "unlocks") or arg:
            raise ValueError(f"achievement {self.id}: unknown metric {self.metric}")


ACHIEVEMENTS = tuple(AchievementDef(*row) for row in (
    ("first_steps", "First steps", "Complete your first task in the forest.", "category:gather", 1),
    ("berry_picker", "Berry picker", "Forage bramble berries 25 times.", "action:bramble_berries", 25),
    ("woodsman", "Woodsman", "Gather fallen branches 50 times.", "action:fallen_branches", 50),
    ("tracker", "Tracker", "Read animal tracks 25 times.", "action:animal_tracks", 25),
    ("boar_breaker", "Boar breaker", "Drive off 10 wild boars.", "action:bramble_boar", 10),
    ("toolmaker", "Toolmaker", "Craft 5 times.", "category:craft", 5),
    ("devout", "Devout", "Finish 5 prayers.", "category:pray", 5),
    ("deep_walker", "Deep walker", "Reach ring 5.", "best_depth", 5),
    ("far_walker", "Far walker", "Reach ring 10.", "best_depth", 10),
    ("survivor", "Survivor", "Live 15 minutes in one life.", "best_life_min", 15),
    ("returner", "Returner", "Begin your fifth life.", "lives", 5),
    ("hunger_lesson", "A hungry lesson", "Starve once.", "deaths:starvation", 1),
    ("possibilities", "New possibilities", "Own 3 unlocks.", "unlocks", 3),
))
ACHIEVEMENT_IDS = {a.id for a in ACHIEVEMENTS}
if len(ACHIEVEMENT_IDS) != len(ACHIEVEMENTS):
    raise ValueError("duplicate achievement ids")
