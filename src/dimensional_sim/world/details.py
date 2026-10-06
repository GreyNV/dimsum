"""Detail views for the browser's pages: character, stats, multipliers, journal, rolls.

WHAT: read-only projections of an Expedition, sent only when the client asks for
them (session input `detail: true`), so the 50 ms world polling stays small.
WHY: players and designers need to see, at a glance, what drives the numbers.
NEVER: change state or roll anything here.
TESTS: tests/test_world_pages.py.
"""
from . import autopilot as ap
from .actions import Context, known
from .catalog import ACTIONS, BOONS, BY_ID, ITEMS, UNLOCKS
from .equipment import is_equipped
from .encounters import spawn_window
from .journal import achievements
from .progression import attribute_report, scaled_ms, speed_permille
from .tuning import BOUNTY_WINDOW_BONUS, PITY_CHUNKS, SPOTS_PER_CHUNK

POINTS = ap.POINT


def _pts(micro):
    return round(micro / POINTS, 1)


def _known_context(e):
    """Use the same permanent permission state as action generation."""
    return Context(unlocked=frozenset(e.unlocked),
                   knowledge=frozenset(getattr(e, "knowledge", ())),
                   recipes=frozenset(getattr(e, "recipes", ())))


def character(e):
    frontier = e.frontier()
    gear = [ITEMS[i].name for i in e.equipped.values()]
    return {
        "life": e.life, "depth": e.depth, "best_depth": e.best_depth, "frontier": frontier,
        "health": _pts(e.health), "hunger": _pts(e.hunger),
        "punch_damage": e.punch_damage(), "gear": gear,
        "boon": BOONS[e.boon].name if e.boon else None,
        "boon_next": BOONS[e.boon_next].name if e.boon_next else None,
        "boar_hit_at_frontier": _pts(e.boar_hit(ap.ChunkKey(e.dimension, frontier, 0))),
        "fight_cost_at_frontier": _pts(e.fight_damage(frontier)),
        "hunger_per_minute": _pts(e._drain() * 60_000),
        "regen_per_minute": _pts(ap.REGEN * 60_000), "rest_regen_per_minute": _pts(ap.REST_REGEN * 60_000),
        "inventory_slots": [len(e.inventory), ap.INVENTORY_SLOTS],
        "currencies": {"dust": e.dust, "ash": e.ash, "blessing": e.blessing},
        "unlocked": [UNLOCKS[u].name for u in sorted(e.unlocked)],
    }


def stats(e):
    report = attribute_report(e.regular, e.dimensional)
    rows = []
    for name, row in report.items():
        rows.append({**row, "name": name,
                     "speed_regular_only": speed_permille(e.regular[name], 0),
                     "speed_dimensional_only": speed_permille(0, e.dimensional[name]),
                     "life_gain": e.life_gain[name]})
    return rows


def multipliers(e):
    """Effective durations for every known action, plus combat/vital multipliers."""
    known_ctx = _known_context(e)
    actions = []
    for a in ACTIONS:
        if a.category in ("fight",) or not known(a, known_ctx):
            continue
        speed = e.speed(a.attribute)
        base = a.duration_ms
        effective = base if a.category in ("reflect", "pray") and a.placement == "self" else scaled_ms(base, speed)
        actions.append({"id": a.id, "name": a.name, "attribute": a.attribute, "speed": speed,
                        "base_ms": base, "effective_ms": effective})
    endurance = e.speed("endurance")
    hit_parts = [["Endurance", round(1000 / endurance, 3)]]
    if is_equipped(e.equipped, "hide_wrap"):
        hit_parts.append(["Hide wrap", 0.7])
    if e.boon == "iron_skin":
        hit_parts.append(["Iron skin boon", 0.75])
    return {"actions": actions,
            "hunger_drain": round(1000 / endurance, 3),
            "boar_hit": hit_parts,
            "punch_damage": e.punch_damage(),
            "punch_parts": [["Base", 1], ["Strength levels", e.punch_damage() - 1 - (1 if is_equipped(e.equipped, "walking_staff") else 0)],
                            *([["Walking staff", 1]] if is_equipped(e.equipped, "walking_staff") else [])]}


def rolls(e):
    """This life's rolled caps against the possible range, spot counts and pity."""
    known_ctx = _known_context(e)
    bonus = BOUNTY_WINDOW_BONUS if e.boon == "bountiful_path" else 0
    windows = []
    for ident, spawned, limit in e.bounty():
        action = BY_ID[ident]
        low, high = spawn_window(action, e.mastery.get(ident, 0), bonus if action.feeds else 0)
        windows.append({"id": ident, "name": action.name, "rolled": limit, "min": low, "max": high,
                        "active": e._active(ident), "spawned": spawned, "mastery": e.mastery.get(ident, 0),
                        "known": known(action, known_ctx)})
    loot = []
    for a in ACTIONS:
        if a.loot and known(a, known_ctx):
            loot.append({"id": a.id, "name": a.name,
                         "drops": [{"item": ITEMS[l.item].name, "min": l.low, "max": l.high, "chance": l.chance}
                                   for l in a.loot]})
    return {"life": e.life, "windows": windows, "spots_per_chunk": [min(SPOTS_PER_CHUNK), max(SPOTS_PER_CHUNK)],
            "pity": [{"category": c, "drought": e.drought[c], "after": PITY_CHUNKS[c]} for c in PITY_CHUNKS],
            "stats": dict(e.stats), "loot": loot}


def journal(e):
    j = e.journal
    return {"actions": sorted(([BY_ID[a].name, BY_ID[a].category, n] for a, n in j["actions"].items()),
                              key=lambda r: (-r[2], r[0])),
            "items": sorted(([ITEMS[i].name, n] for i, n in j["items"].items()), key=lambda r: (-r[1], r[0])),
            "deaths": dict(j["deaths"]), "best_life_min": round(j["best_life_ms"] / 60000, 1),
            "lives": e.life, "best_depth": e.best_depth,
            "achievements": achievements(e),
            "knowledge": sorted(e.knowledge), "recipes": sorted(e.recipes),
            "disabled": sorted(e.journal_disabled), "favor": dict(e.journal_favor),
            "leads": [dict(row) for row in e.leads],
            "lead_history": [dict(row) for row in e.lead_history[-20:]]}


def detail(e):
    return {"character": character(e), "stats": stats(e), "multipliers": multipliers(e),
            "rolls": rolls(e), "journal": journal(e)}
