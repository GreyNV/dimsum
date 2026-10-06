"""Content catalog for the forest expedition: items, actions, unlocks, boons, regions.

WHAT: every piece of world content the auto-pilot can meet, as validated data.
WHY: adding an item, action, recipe, unlock, boon or region must be a data edit,
not a change to generation, the auto-pilot or the client.
OWNS: definitions only. Rules that read them live in actions.py (eligibility and
buckets), regions.py (region per chunk), encounters.py (spot placement),
economy.py (currency conversion and anchor purchases) and autopilot.py (execution).
NEVER: reorder or rename ids that existing saves reference without bumping
encounters.ENCOUNTER_VERSION; use floats, wall clock or shared RNG in rules.
TESTS: tests/test_world_catalog.py validates every table and cross-reference.
"""
from dataclasses import dataclass, field

from .models import identifier, integer

ATTRIBUTES = ("strength", "endurance", "agility", "intelligence", "perception", "willpower")

# ----- items ------------------------------------------------------------------
ITEM_KINDS = ("food", "material", "gear")
EQUIPMENT_SLOTS = ("weapon", "body")


@dataclass(frozen=True)
class ItemDef:
    """Current-life inventory item. `dust` is its anchor offering value per unit."""
    id: str
    name: str
    kind: str
    food: int = 0       # hunger points restored when eaten
    glyph: str = "*"
    dust: int = 1       # dimensional dust per unit when offered at the anchor
    slot: str | None = None   # gear occupies an explicit equipment slot

    def __post_init__(self):
        identifier(self.id, "item ID")
        if self.kind not in ITEM_KINDS or not isinstance(self.name, str) or not 1 <= len(self.name) <= 40:
            raise ValueError("invalid item kind/name")
        integer(self.food, "food value", 0, 100)
        integer(self.dust, "dust value", 0, 100)
        if (self.kind == "food") != (self.food > 0):
            raise ValueError("food, and only food, restores hunger")
        if (self.kind == "gear") != (self.slot in EQUIPMENT_SLOTS):
            raise ValueError("gear must have a valid equipment slot, other items must not")
        if not isinstance(self.glyph, str) or len(self.glyph) != 1 or not 33 <= ord(self.glyph) <= 126:
            raise ValueError("item glyph must be one printable ASCII character")


ITEMS = {item.id: item for item in (
    ItemDef("wild_berries", "Wild berries", "food", 12, "o", dust=1),
    ItemDef("bird_egg", "Bird egg", "food", 20, "0", dust=2),
    ItemDef("boar_meat", "Boar meat", "food", 35, "%", dust=3),
    ItemDef("venison", "Venison", "food", 28, "v", dust=3),
    ItemDef("pale_mushroom", "Pale mushroom", "food", 15, "n", dust=2),
    ItemDef("snared_hare", "Snared hare", "food", 30, "&", dust=3),
    ItemDef("stick", "Stick", "material", glyph="/", dust=1),
    ItemDef("bramble_thorn", "Bramble thorn", "material", glyph="^", dust=2),
    ItemDef("boar_hide", "Boar hide", "material", glyph="#", dust=4),
    # Gear is worth less than its inputs: crafting spends dust you could have offered.
    ItemDef("walking_staff", "Walking staff", "gear", glyph="|", dust=2, slot="weapon"),
    ItemDef("hide_wrap", "Hide wrap", "gear", glyph="]", dust=6, slot="body"),
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


# ----- actions ----------------------------------------------------------------
# category = what the avatar does; placement = where the action comes from:
#   "spot": a generated point of interest in a chunk (rolled from the spot bucket);
#   "self": something the avatar does wherever it stands (after-location bucket or a need).
CATEGORIES = ("forage", "gather", "observe", "climb", "drink", "meditate", "study", "scavenge",
              "pray", "fight", "hunt", "craft", "reflect")
PLACEMENTS = ("spot", "lead", "self")
RARITIES = ("common", "uncommon", "rare")
NEAR = (None, "T", "^")   # spot needs a tree / rock beside its cell
TRIGGERS = (None, "after_location", "need")   # self actions only

REQUIREMENT_KINDS = ("action_count", "item_count", "knowledge", "unlock", "recipe", "level")
OUTCOME_KINDS = ("knowledge", "recipe", "lead")
ACTION_ROLES = ("base", "unlockable", "discovery", "lead", "contextual", "craft", "combat", "reflection")


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
    """Declarative consequence after an action completes; `at_count` is lifetime completions."""
    kind: str
    id: str
    at_count: int = 1
    chance: int = 100
    ttl_ms: int = 0

    def __post_init__(self):
        if self.kind not in OUTCOME_KINDS:
            raise ValueError("invalid outcome kind")
        identifier(self.id, "outcome ID")
        integer(self.at_count, "outcome threshold", 1, 10**9)
        integer(self.chance, "outcome chance", 1, 100)
        integer(self.ttl_ms, "lead lifetime", 0, 600_000)
        if (self.kind == "lead") != (self.ttl_ms > 0):
            raise ValueError("only leads have a positive lifetime")


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
    blessing: int = 0                 # prayers only
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

    def __post_init__(self):
        identifier(self.id, "action ID")
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
        integer(self.hp, "action HP", 0, 3)
        integer(self.heal, "action heal", 0, 100)
        integer(self.blessing, "action blessing", 0, 10)
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
        if (self.category == "pray") != (self.blessing > 0):
            raise ValueError(f"prayers, and only prayers, grant blessings: {self.id}")
        if (self.category == "craft") != bool(self.cost):
            raise ValueError(f"crafts, and only crafts, consume items: {self.id}")
        if self.effect is not None and (self.effect not in ITEMS or ITEMS[self.effect].kind != "gear"):
            raise ValueError(f"effect must name a gear item: {self.id}")
        if self.placement == "spot" and (self.trigger is not None or self.visible_only):
            raise ValueError(f"spot actions have no trigger: {self.id}")
        if self.placement == "self" and (self.trigger not in TRIGGERS[1:] or self.near or self.window):
            raise ValueError(f"self actions need a trigger and no placement rules: {self.id}")
        if self.placement == "lead" and (self.trigger is not None or self.near or self.window or self.hp):
            raise ValueError(f"lead actions cannot use world placement rules: {self.id}")
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
    ActionDef("bramble_berries", "Bramble berries", "forage", "spot", "perception", 40, 2400, 11,
              "Pick berries from a thorny bramble patch.", "Picked bramble berries without getting scratched (much).",
              window=(1, 2), loot=(L("wild_berries", 1, 2), L("bramble_thorn", 1, 1, 35)), roles=("base",)),
    ActionDef("fallen_branches", "Fallen branches", "gather", "spot", "strength", 30, 2200, 18,
              "Gather sticks from branches across the trail.", "Hauled a pile of fallen branches off the trail.",
              regions=("old_road", "deep_woods", "bramble_thicket"),
              loot=(L("stick", 2, 3),), roles=("base", "discovery"),
              outcomes=(OutcomeDef("knowledge", "primitive_crafting", at_count=5),
                        OutcomeDef("recipe", "walking_staff", at_count=10))),
    ActionDef("animal_tracks", "Animal tracks", "observe", "spot", "perception", 50, 3000, 12,
              "Read the tracks of what lives here.", "Read fresh tracks in the mud - something heavy passed here.",
              regions=("deep_woods", "still_glade"), roles=("base", "discovery"),
              outcomes=(OutcomeDef("knowledge", "deer_sign"),
                        OutcomeDef("lead", "follow_deer_tracks", chance=30, ttl_ms=90_000))),
    ActionDef("follow_deer_tracks", "Follow deer tracks", "observe", "lead", "perception", 35, 3800, 1,
              "Follow a fresh trail before the deer moves on.", "Followed the tracks to a quiet deer crossing.",
              knowledge="deer_sign", roles=("lead", "contextual"),
              outcomes=(OutcomeDef("lead", "hunt_deer", chance=60, ttl_ms=60_000),)),
    ActionDef("hunt_deer", "Hunt deer", "hunt", "lead", "agility", 80, 5500, 1,
              "Approach the deer while this trail is still fresh.", "Brought down a deer at the crossing.",
              knowledge="deer_sign", roles=("lead", "combat", "contextual"),
              loot=(L("venison", 1, 1),)),
    ActionDef("forest_spring", "Forest spring", "drink", "spot", "endurance", 40, 2000, 9,
              "Drink and catch your breath.", "Drank from a cold spring and caught your breath.",
              window=(1, 2), heal=10, roles=("base",)),
    ActionDef("bramble_boar", "Bramble boar", "fight", "spot", "strength", 100, 1, 9,
              "A territorial boar that charges anything nearby. Meat and hide.",
              "Drove off a bramble boar with your bare fists.", window=(1, 2), hp=3,
              loot=(L("boar_meat", 1, 1), L("boar_hide", 1, 1, 60)), roles=("base", "combat")),
    # --- unlocked with dimensional dust ---------------------------------------
    ActionDef("gnarled_tree", "Gnarled tree", "climb", "spot", "agility", 60, 3200, 10,
              "Climb for bird eggs and a look over the canopy.", "Climbed a gnarled tree and scouted the canopy.",
              unlock="climbing", near="T", window=(1, 1),
              loot=(L("bird_egg", 1, 1, 60), L("stick", 1, 1, 40)), roles=("unlockable",)),
    ActionDef("abandoned_camp", "Abandoned camp", "scavenge", "spot", "strength", 40, 3100, 8,
              "Search what other travellers left behind.",
              "Searched an abandoned camp for anything the travellers left behind.",
              unlock="scavenging", rarity="uncommon",
              loot=(L("stick", 1, 2), L("bramble_thorn", 1, 2, 60), L("boar_hide", 1, 1, 20)),
              roles=("unlockable",)),
    ActionDef("mushroom_ring", "Mushroom ring", "forage", "spot", "perception", 55, 3200, 8,
              "Pale mushrooms that are safe - if you know which ones.",
              "Gathered the safe mushrooms from a pale ring.", unlock="mushroom_lore",
              regions=("deep_woods",), window=(1, 1),
              loot=(L("pale_mushroom", 1, 2),), roles=("unlockable",)),
    ActionDef("mossy_stone", "Mossy stone", "meditate", "spot", "willpower", 60, 4000, 7,
              "Sit with the stone until the forest goes quiet.", "Sat by a mossy stone until the forest went quiet.",
              unlock="meditation", near="^", roles=("unlockable",)),
    ActionDef("moonlit_pool", "Moonlit pool", "drink", "spot", "endurance", 45, 2600, 5,
              "A still pool that steadies body and mind.", "Drank from a still pool beneath the branches.",
              unlock="meditation", rarity="uncommon", window=(0, 1), heal=12, roles=("unlockable",)),
    ActionDef("old_carvings", "Old carvings", "study", "spot", "intelligence", 80, 3600, 5,
              "Marks that look almost like a summoning circle.",
              "Traced old carvings - the marks look almost like a summoning circle.",
              unlock="road_lore", rarity="uncommon", roles=("unlockable",)),
    ActionDef("fallen_watchtower", "Fallen watchtower", "study", "spot", "intelligence", 75, 4200, 5,
              "Ruins with faded warnings about the road.",
              "Studied the ruins of a watchtower and its faded warning marks.",
              unlock="road_lore", rarity="uncommon", regions=("old_road", "deep_woods"),
              roles=("unlockable",)),
    # --- unlocked with blessing ------------------------------------------------
    ActionDef("wayside_shrine", "Wayside shrine", "pray", "spot", "willpower", 50, 3600, 6,
              "A moss-grown shrine on the old road. Prayer here is always heard.",
              "Knelt at a wayside shrine and prayed to the gods who spared you.",
              unlock="shrine_path", regions=("old_road",), rarity="uncommon", window=(1, 1), blessing=1,
              roles=("unlockable",)),
    # --- self actions -----------------------------------------------------------
    ActionDef("think", "Think about the road", "reflect", "self", "intelligence", 0, 3000, 40,
              "A quiet thought after a task.", "Thought about the road behind you.", trigger="after_location",
              roles=("reflection", "contextual")),
    ActionDef("contemplate", "Contemplate the forest", "reflect", "self", "willpower", 0, 5000, 30,
              "A longer, wordless pause.", "Contemplated the forest for a while.", trigger="after_location",
              roles=("reflection", "contextual")),
    ActionDef("pray", "Pray to the gods", "pray", "self", "willpower", 0, 12000, 4,
              "A rare, unplanned prayer. Grants one blessing when it finishes.",
              "You finished a prayer. The gods grant one blessing.", trigger="after_location",
              visible_only=True, blessing=1, tags=("once_per_life",), roles=("reflection", "contextual")),
    ActionDef("craft_staff", "Carve a walking staff", "craft", "self", "agility", 20, 4000, 1,
              "Three sticks become a staff: +1 punch damage this life.",
              "Carved a walking staff from three sticks.", cost=(("stick", 3),), effect="walking_staff",
              trigger="need", need_priority=2, recipe="walking_staff", roles=("craft", "contextual"),
              requirements=(Requirement("knowledge", "primitive_crafting"),)),
    ActionDef("craft_snare", "Set a bramble snare", "craft", "self", "perception", 30, 6000, 1,
              "Sticks and a thorn become a snare that usually catches a hare.",
              "Set a bramble snare and checked it.", unlock="snares",
              cost=(("stick", 2), ("bramble_thorn", 1)), loot=(L("snared_hare", 1, 1, 75),), trigger="need",
              need_priority=3, need_hunger_below=60, need_no_food=True,
              roles=("craft", "unlockable", "contextual")),
    ActionDef("craft_wrap", "Wrap boar hide", "craft", "self", "endurance", 30, 5000, 1,
              "Two hides become a wrap: boar hits hurt 30% less this life.",
              "Wrapped boar hide around your arms and chest.", unlock="hide_working",
              cost=(("boar_hide", 2),), effect="hide_wrap", trigger="need",
              need_priority=1,
              roles=("craft", "unlockable", "contextual")),
)
BY_ID = {action.id: action for action in ACTIONS}


# ----- unlocks, boons, mastery ---------------------------------------------------
CURRENCIES = ("dust", "ash", "blessing")


@dataclass(frozen=True)
class UnlockDef:
    """A permanent new possibility, bought at the anchor between lives."""
    id: str
    name: str
    description: str
    currency: str
    cost: int
    requires: tuple = ()

    def __post_init__(self):
        identifier(self.id, "unlock ID")
        if self.currency not in CURRENCIES or not 1 <= len(self.name) <= 40 or not 1 <= len(self.description) <= 160:
            raise ValueError(f"invalid unlock: {self.id}")
        integer(self.cost, "unlock cost", 1, 10000)


UNLOCKS = {u.id: u for u in (
    UnlockDef("climbing", "Climbing", "Gnarled trees appear: bird eggs and sticks.", "dust", 15),
    UnlockDef("scavenging", "Scavenging", "Abandoned camps appear: thorns, sticks and old hide.", "dust", 20),
    UnlockDef("snares", "Snares", "Craft a bramble snare (2 sticks, 1 thorn) when hungry: usually a hare.", "dust", 25),
    UnlockDef("meditation", "Meditation", "Mossy stones and moonlit pools appear.", "dust", 30),
    UnlockDef("mushroom_lore", "Mushroom lore", "Mushroom rings become food.", "dust", 45, ("climbing",)),
    UnlockDef("hide_working", "Hide working", "Craft a hide wrap (2 hides): boar hits hurt 30% less.", "dust", 50),
    UnlockDef("road_lore", "Road lore", "Old carvings and watchtowers appear: Intelligence XP.", "dust", 70,
              ("meditation",)),
    UnlockDef("shrine_path", "Shrine path", "Wayside shrines appear on the old road: one prayer per shrine.",
              "blessing", 3),
)}


@dataclass(frozen=True)
class BoonDef:
    """A one-life favour bought with blessing at the anchor for the next life."""
    id: str
    name: str
    description: str
    cost: int

    def __post_init__(self):
        identifier(self.id, "boon ID")
        integer(self.cost, "boon cost", 1, 100)


BOONS = {b.id: b for b in (
    BoonDef("bountiful_path", "Bountiful path", "Next life: +1 at-once cap for every food source.", 2),
    BoonDef("iron_skin", "Iron skin", "Next life: boar hits hurt 25% less.", 2),
)}

# Ash buys mastery: each level widens one action's spawn window (encounters.spawn_window).
MASTERY_MAX = 3
JOURNAL_TOGGLE_MASTERY = 2
JOURNAL_FAVOR_MASTERY = 3
JOURNAL_FAVOR_PERCENT = 150
JOURNAL_SUPPRESS_PERCENT = 50


def mastery_cost(level):
    """Ash to raise mastery from `level` to `level + 1`."""
    return 3 * (level + 1)


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
            if action not in BY_ID:
                raise ValueError(f"region weight for unknown action: {self.id}/{action}")
            integer(percent, "region weight percent", 0, 1000)

    def multiplier(self, action_id):
        return self.weights.get(action_id, 100)


REGION_CELL = 3        # chunks per region side
ORIGIN_REGION = "old_road"   # the ambush road runs through the anchor's region
REGIONS = {r.id: r for r in (
    RegionDef("old_road", "The Old Road", "dark_forest", 3, "#2a2716",
              {"abandoned_camp": 300, "fallen_watchtower": 200, "old_carvings": 150,
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

# Compatibility of neighboring region cells. This affects geography only; action
# eligibility and odds remain on RegionDef. Keep versioned with regions.py so an
# existing world's saved geography is never silently changed by a tuning edit.
REGION_ADJACENCY_V2 = {
    "old_road": {"old_road": 5, "deep_woods": 2, "bramble_thicket": 2, "still_glade": 2},
    "deep_woods": {"old_road": 2, "deep_woods": 5, "bramble_thicket": 4, "still_glade": 3},
    "bramble_thicket": {"old_road": 2, "deep_woods": 4, "bramble_thicket": 5, "still_glade": 2},
    "still_glade": {"old_road": 2, "deep_woods": 3, "bramble_thicket": 2, "still_glade": 5},
}


def validate_catalog():
    """Cross-reference checks; raises ValueError on the first problem."""
    for action in ACTIONS:
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
        for requirement in action.requirements:
            choices = {"action_count": BY_ID, "item_count": ITEMS, "unlock": UNLOCKS,
                       "level": ATTRIBUTES}
            if requirement.kind in choices and requirement.id not in choices[requirement.kind]:
                raise ValueError(f"action {action.id} has invalid prerequisite {requirement.id}")
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
        if not any(a.unlock == unlock.id for a in ACTIONS):
            raise ValueError(f"unlock {unlock.id} opens no action")
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
    for item in ITEMS.values():
        sources = [a for a in ACTIONS if any(l.item == item.id for l in a.loot) or a.effect == item.id]
        if not sources:
            raise ValueError(f"item {item.id} has no source")


validate_catalog()


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
                 "deaths": {"starvation", "boar", "exhaustion", ""}}
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
    ("boar_breaker", "Boar breaker", "Drive off 10 bramble boars.", "action:bramble_boar", 10),
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
