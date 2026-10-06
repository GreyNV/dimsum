"""Deterministic per-chunk encounter spots (points of interest) from the action bucket.

Each chunk rolls 0..3 spots. The spot bucket (actions.bucket) holds every known
spot action eligible for the chunk's biome and region, weighted by base weight x
region multiplier. Rolls are seeded by the canonical chunk seed, ENCOUNTER_VERSION
and the life number; the unlocked set and region select the bucket, so the same
world, life and unlocks always offer the same spots, regardless of visit order,
cache eviction or save/reload. Spots sit on reachable walkable cells; collision
stays authoritative. Fight spots become runtime Targets at their spot.

Content (items, actions, regions) lives in catalog.py; this module only places it.
Spawn windows and pity are applied later by the auto-pilot's screening. No
providers, wall clock, hash() or shared RNG.
"""
from collections import deque
from dataclasses import dataclass, replace

from .actions import Context, bucket
from .catalog import ACTIONS, ATTRIBUTES, BY_ID, ITEMS, ITEM_KINDS, ActionDef, ItemDef, Loot  # noqa: F401 (re-exports)
from .models import DELTAS, ChunkKey, integer
from .seeds import derive_seed
from .tuning import SPOTS_PER_CHUNK

ENCOUNTER_VERSION = "encounters-v8"  # v8: roll when a chunk is entered, persist the resulting opportunities
EncounterDef = ActionDef            # compatibility name
KINDS = tuple(sorted({a.category for a in ACTIONS}))
NEAR = (None, "T", "^")
SPOT_ACTIONS = tuple(a for a in ACTIONS if a.placement == "spot")
POOLS = {"dark_forest": tuple(a for a in SPOT_ACTIONS if "dark_forest" in a.biomes)}
DARK_FOREST = POOLS["dark_forest"]


def validate_pools(pools=POOLS):
    seen = set()
    for biome, pool in pools.items():
        if type(pool) is not tuple or not pool:
            raise ValueError("encounter pool must be a nonempty tuple")
        for entry in pool:
            if not isinstance(entry, ActionDef) or entry.id in seen or entry.placement != "spot":
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


def spawn_window(entry, mastery=0, bonus=0):
    """(low, high) cap on how many of one encounter exist at once, or None (unlimited).

    Mastery (bought with ash) widens the window: +1 high per level and +1 low every
    second level. `bonus` (e.g. the bountiful-path boon) adds to both ends."""
    if entry.window is None:
        return None
    integer(mastery, "mastery", 0, 1000)
    integer(bonus, "window bonus", 0, 1000)
    low, high = entry.window
    return low + mastery // 2 + bonus, high + mastery + bonus


def roll_window(entry, seed, mastery=0, bonus=0):
    """This life's at-once cap for `entry` (None = unlimited), rolled at the anchor."""
    window = spawn_window(entry, mastery, bonus)
    if window is None:
        return None
    low, high = window
    return low + derive_seed(seed, "window", entry.id) % (high - low + 1)


def chunk_spots(chunk, life=1, *, unlocked=frozenset(), region=None, context=None, roll_seed=None):
    """Deterministic spots from the full action context (legacy unlock/region accepted).

    Callers with progression or Journal state pass ``context`` so roll eligibility
    is identical to the explanation shown to the player. The chunk's pinned biome
    is authoritative even if a caller supplies a stale context.
    """
    asset, key = chunk.asset, chunk.key
    ctx = (replace(context, biome=asset.biome, placement="spot") if context is not None else
           Context(biome=asset.biome, region=region, placement="spot", unlocked=frozenset(unlocked)))
    entries = bucket(ctx)
    if not entries:
        return ()
    seed = (derive_seed(chunk.seed, ENCOUNTER_VERSION, life) if roll_seed is None else
            integer(roll_seed, "encounter roll seed", 0, 2**64 - 1))
    reachable = _reachable(asset)
    count = SPOTS_PER_CHUNK[derive_seed(seed, "count") % len(SPOTS_PER_CHUNK)]
    total = sum(w for _, w in entries)
    spots, used, candidates = [], [], {}
    for index in range(count):
        roll = derive_seed(seed, "entry", index) % total
        for entry, w in entries:
            if roll < w:
                break
            roll -= w
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


FORCED_BASE = 10   # forced (pity) spots use indices FORCED_BASE.. so they never collide


def forced_spot(chunk, encounter, index, taken=()):
    """A pity spot of `encounter` in `chunk` (deterministic), or None if no cell fits."""
    entry = BY_ID[encounter]
    asset, key = chunk.asset, chunk.key
    options = [p for p in _candidates(asset, _reachable(asset), entry.near)
               if all(abs(p[0] - u[0]) + abs(p[1] - u[1]) >= 4 for u in taken)]
    if not options:
        return None
    x, y = options[derive_seed(chunk.seed, ENCOUNTER_VERSION, "forced", encounter, index) % len(options)]
    return EncounterSpot(spot_id(key, FORCED_BASE + index), encounter, key, x, y)


def lead_spot(chunk, action_id, life, source_id, index, source_xy):
    """Place a temporary follow-up on a reachable cell of its source chunk.

    This does not consult or alter the global procedural bucket. The caller owns
    the lead's expiry and resolution; its identity and position are deterministic
    for this life and source, including after save/reload or cache regeneration.
    """
    if action_id not in BY_ID or BY_ID[action_id].placement != "lead":
        raise ValueError("lead action required")
    integer(life, "life", 1)
    integer(index, "lead index", 0)
    if not isinstance(source_id, str) or not source_id:
        raise ValueError("lead source id required")
    if (type(source_xy) is not tuple or len(source_xy) != 2 or
            any(type(v) is not int for v in source_xy)):
        raise ValueError("lead source cell must be an (x, y) tuple")
    asset, key = chunk.asset, chunk.key
    sx, sy = source_xy
    if not 0 <= sx < asset.width or not 0 <= sy < asset.height:
        raise ValueError("lead source cell outside chunk")
    reachable = _reachable(asset)
    options = _candidates(asset, reachable, None)
    if not options:
        return None
    distant = [cell for cell in options if abs(cell[0] - sx) + abs(cell[1] - sy) >= 2]
    options = distant or [cell for cell in options if cell != source_xy] or options
    seed = derive_seed(chunk.seed, ENCOUNTER_VERSION, "lead", life, action_id, source_id, index)
    x, y = options[seed % len(options)]
    ident = f"lead:{key.dimension}:{key.x}:{key.y}:{action_id}:{index}:{seed}"
    return EncounterSpot(ident, action_id, key, x, y)
