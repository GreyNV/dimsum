"""Biome encounter pools and deterministic per-chunk encounter spots.

Each chunk rolls a few encounter spots from its biome's weighted pool, seeded only
by the canonical chunk seed and ENCOUNTER_VERSION: the same world always offers
the same spots, regardless of visit order, cache eviction or save/reload. Spots
sit on reachable walkable cells; collision stays authoritative. Fight entries
become ordinary runtime Targets at their spot. To change placement rules or a
pool for existing worlds, add a new versioned pool instead of editing in place.

The first pool is bare-handed: nothing here needs equipment. No providers, wall
clock, hash() or shared RNG.
"""
from collections import deque
from dataclasses import dataclass

from .models import DELTAS, ChunkKey, identifier, integer
from .seeds import derive_seed

ENCOUNTER_VERSION = "encounters-v2"  # v2: XP x10, loot, heal; spots re-roll per life
ATTRIBUTES = ("strength", "endurance", "agility", "intelligence", "perception", "willpower")
KINDS = ("forage", "gather", "observe", "climb", "drink", "meditate", "study", "fight")
RARITIES = ("common", "uncommon", "rare")
NEAR = (None, "T", "^")


ITEM_KINDS = ("food", "material")


@dataclass(frozen=True)
class ItemDef:
    """Gathered item (current-life inventory). Soulbound equipment is summon-only."""
    id: str
    name: str
    kind: str
    food: int = 0       # hunger points restored when eaten
    glyph: str = "*"

    def __post_init__(self):
        identifier(self.id, "item ID")
        if self.kind not in ITEM_KINDS or not isinstance(self.name, str) or not 1 <= len(self.name) <= 40:
            raise ValueError("invalid item kind/name")
        integer(self.food, "food value", 0, 100)
        if (self.kind == "food") != (self.food > 0):
            raise ValueError("food, and only food, restores hunger")
        if not isinstance(self.glyph, str) or len(self.glyph) != 1 or not 33 <= ord(self.glyph) <= 126:
            raise ValueError("item glyph must be one printable ASCII character")


ITEMS = {item.id: item for item in (
    ItemDef("wild_berries", "Wild berries", "food", 12, "o"),
    ItemDef("bird_egg", "Bird egg", "food", 20, "0"),
    ItemDef("boar_meat", "Boar meat", "food", 35, "%"),
    ItemDef("stick", "Stick", "material", glyph="/"),
    ItemDef("bramble_thorn", "Bramble thorn", "material", glyph="^"),
    ItemDef("boar_hide", "Boar hide", "material", glyph="#"),
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


@dataclass(frozen=True)
class EncounterDef:
    id: str
    name: str
    kind: str
    attribute: str
    xp: int
    duration_ms: int
    weight: int
    rarity: str = "common"
    near: str | None = None
    log: str = ""
    hp: int = 0
    loot: tuple = ()
    heal: int = 0       # health points restored on completion

    def __post_init__(self):
        identifier(self.id, "encounter ID")
        if not isinstance(self.name, str) or not 1 <= len(self.name) <= 60:
            raise ValueError("invalid encounter name")
        if self.kind not in KINDS or self.attribute not in ATTRIBUTES or self.rarity not in RARITIES:
            raise ValueError("invalid encounter kind/attribute/rarity")
        if self.near not in NEAR:
            raise ValueError("invalid encounter placement")
        integer(self.xp, "encounter XP", 1, 10000)
        integer(self.duration_ms, "encounter duration", 1, 600000)
        integer(self.weight, "encounter weight", 1, 10000)
        if not isinstance(self.log, str) or not 1 <= len(self.log) <= 120:
            raise ValueError("invalid encounter log text")
        integer(self.hp, "encounter HP", 0, 3)
        integer(self.heal, "encounter heal", 0, 100)
        if type(self.loot) is not tuple or any(not isinstance(l, Loot) for l in self.loot):
            raise ValueError("loot must be a tuple of Loot")
        if (self.kind == "fight") != (self.hp > 0):
            raise ValueError("fights, and only fights, have hit points")


# Dark forest, no equipment: everything here is done with bare hands.
# XP is regular (current-life) XP; 20% also goes to the persistent dimensional track.
DARK_FOREST = (
    EncounterDef("bramble_berries", "Bramble berries", "forage", "perception", 40, 2400, 30,
                 log="Picked bramble berries without getting scratched (much).",
                 loot=(Loot("wild_berries", 2, 4), Loot("bramble_thorn", 1, 1, 30))),
    EncounterDef("fallen_branches", "Fallen branches", "gather", "strength", 30, 2200, 24,
                 log="Hauled a pile of fallen branches off the trail.", loot=(Loot("stick", 2, 3),)),
    EncounterDef("animal_tracks", "Animal tracks", "observe", "perception", 50, 3000, 20,
                 log="Read fresh tracks in the mud - something heavy passed here."),
    EncounterDef("gnarled_tree", "Gnarled tree", "climb", "agility", 60, 3200, 12, near="T",
                 log="Climbed a gnarled tree and scouted the canopy.",
                 loot=(Loot("bird_egg", 1, 1, 50), Loot("stick", 1, 1, 40))),
    EncounterDef("forest_spring", "Forest spring", "drink", "endurance", 40, 2000, 12, heal=10,
                 log="Drank from a cold spring and caught your breath."),
    EncounterDef("mossy_stone", "Mossy stone", "meditate", "willpower", 60, 4000, 8, near="^",
                 log="Sat by a mossy stone until the forest went quiet."),
    EncounterDef("old_carvings", "Old carvings", "study", "intelligence", 80, 3600, 5, "uncommon",
                 log="Traced old carvings - the marks look almost like a summoning circle."),
    EncounterDef("bramble_boar", "Bramble boar", "fight", "strength", 100, 1, 14, hp=3,
                 log="Drove off a bramble boar with your bare fists.",
                 loot=(Loot("boar_meat", 1, 2), Loot("boar_hide", 1, 1, 60))),
)
POOLS = {"dark_forest": DARK_FOREST}
BY_ID = {entry.id: entry for pool in POOLS.values() for entry in pool}


def validate_pools(pools=POOLS):
    seen = set()
    for biome, pool in pools.items():
        identifier(biome, "biome")
        if type(pool) is not tuple or not pool:
            raise ValueError("encounter pool must be a nonempty tuple")
        for entry in pool:
            if not isinstance(entry, EncounterDef) or entry.id in seen:
                raise ValueError("invalid or duplicate encounter definition")
            seen.add(entry.id)


validate_pools()


@dataclass(frozen=True)
class EncounterSpot:
    id: str
    encounter: str
    chunk: ChunkKey
    x: int
    y: int

    @property
    def definition(self):
        return BY_ID[self.encounter]


def spot_id(key, index):
    return f"enc:{key.dimension}:{key.x}:{key.y}:{index}"


def _glyph(asset, x, y):
    cell = asset.objects[y][x] or asset.environment[y][x]
    return cell.glyph


def _reachable(asset):
    """Walkable cells connected to the player spawn, exits or any spawn."""
    w, h = asset.width, asset.height
    starts = [(s.x, s.y) for s in asset.spawns] + [(e.x, e.y) for e in asset.exits]
    seen, queue = set(), deque(p for p in starts if not asset.collision[p[1]][p[0]])
    seen.update(queue)
    while queue:
        x, y = queue.popleft()
        for dx, dy in DELTAS.values():
            nx, ny = x + dx, y + dy
            if 0 <= nx < w and 0 <= ny < h and (nx, ny) not in seen and not asset.collision[ny][nx]:
                seen.add((nx, ny))
                queue.append((nx, ny))
    return seen


def _candidates(asset, reachable, near):
    w, h = asset.width, asset.height
    occupied = {(s.x, s.y) for s in asset.spawns}
    result = []
    for y in range(1, h - 1):
        for x in range(1, w - 1):
            if (x, y) not in reachable or (x, y) in occupied:
                continue
            neighbors = [(x + dx, y + dy) for dx, dy in DELTAS.values()]
            if not any(n in reachable for n in neighbors):
                continue
            if near and not any(_glyph(asset, nx, ny) == near for nx, ny in neighbors):
                continue
            result.append((x, y))
    return result


def roll_loot(entry, seed):
    """Deterministic loot for one completed encounter: [(item_id, count)]."""
    result = []
    for index, loot in enumerate(entry.loot):
        roll = derive_seed(seed, "loot", index)
        if roll % 100 < loot.chance:
            result.append((loot.item, loot.low + (roll // 100) % (loot.high - loot.low + 1)))
    return result


def chunk_spots(chunk, pools=POOLS, life=1):
    """Deterministic encounter spots for one chunk in one life (possibly none)."""
    pool = pools.get(chunk.asset.biome)
    if not pool:
        return ()
    asset, key = chunk.asset, chunk.key
    seed = derive_seed(chunk.seed, ENCOUNTER_VERSION, life)
    reachable = _reachable(asset)
    # 0..3 spots; an empty roll is part of the chance, like idle stage buckets.
    count = (0, 1, 2, 2, 3, 3)[derive_seed(seed, "count") % 6]
    total = sum(entry.weight for entry in pool)
    spots, used, candidates = [], [], {}
    for index in range(count):
        roll = derive_seed(seed, "entry", index) % total
        for entry in pool:
            if roll < entry.weight:
                break
            roll -= entry.weight
        if entry.near not in candidates:  # computed once per placement rule per chunk
            candidates[entry.near] = _candidates(asset, reachable, entry.near)
        options = [p for p in candidates[entry.near]
                   if all(abs(p[0] - u[0]) + abs(p[1] - u[1]) >= 4 for u in used)]
        if not options:
            continue  # e.g. no tree in this chunk for a climb: the slot stays empty
        x, y = options[derive_seed(seed, "cell", index) % len(options)]
        used.append((x, y))
        spots.append(EncounterSpot(spot_id(key, index), entry.id, key, x, y))
    return tuple(spots)
