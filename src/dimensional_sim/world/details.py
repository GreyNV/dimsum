"""Detail views for the browser's pages: character, stats, multipliers, journal, rolls.

WHAT: read-only projections of an Expedition, sent only when the client asks for
them (session input `detail: true`), so the 50 ms world polling stays small.
WHY: players and designers need to see, at a glance, what drives the numbers.
NEVER: change state or roll anything here.
TESTS: tests/test_world_pages.py.
"""
from .actions import Context, describe_bucket, known, spot_tiers
from .autopilot import INVENTORY_SLOTS, POINT, REGEN, REST_REGEN
from . import effects
from .catalog import (ACTIONS, BY_ID, ENEMIES, ITEMS, JOURNAL_FAVOR_MASTERY, JOURNAL_GROUPS, JOURNAL_GUARANTEE_MASTERY,
                      MASTERY_THRESHOLDS, RARITY, REGIONS, SITES, UNLOCKS)
from .drops import SCALE, table_chances, tier_chances
from .encounters import spawn_window
from .journal import achievements
from .models import ChunkKey
from .progression import attribute_report, dimensional_level, scaled_ms, sight_radius, speed_permille
from .tuning import CARRY_FREE, CARRY_MAX_PERCENT, CARRY_PERCENT_PER_ITEM, PITY_CHUNKS, SPOTS_PER_CHUNK


def _pts(micro):
    return round(micro / POINT, 1)


def _known_context(e):
    """Use the same permanent permission state as action generation."""
    return Context(unlocked=frozenset(e.unlocked), knowledge=frozenset(e.knowledge),
                   recipes=frozenset(e.recipes))


def character(e):
    frontier = e.frontier()
    gear = [ITEMS[i].name for i in e.equipped.values()]
    return {
        "life": e.life, "depth": e.depth, "best_depth": e.best_depth, "frontier": frontier,
        "health": _pts(e.health), "hunger": _pts(e.hunger),
        "punch_damage": e.punch_damage(), "gear": gear,
        "threats": [{"id": a.id, "name": ENEMIES[a.enemy].name,
                     "hp": e.enemy_hp(a, ChunkKey(e.dimension, frontier, 0)),
                     "hit_at_frontier": _pts(e.enemy_hit(ChunkKey(e.dimension, frontier, 0), ENEMIES[a.enemy])),
                     "fight_cost_at_frontier": _pts(e.fight_damage(frontier, a))} for a in e.threats()],
        "hunger_per_minute": _pts(e._drain() * 60_000),
        "regen_per_minute": _pts(REGEN * 60_000), "rest_regen_per_minute": _pts(REST_REGEN * 60_000),
        "inventory_slots": [len(e.inventory), INVENTORY_SLOTS],
        "currencies": {"ash": e.ash},
        "unlocked": [UNLOCKS[u].name for u in sorted(e.unlocked)],
        "openings": [{"name": u.name, "description": u.description, "attribute": u.level[0], "level": u.level[1],
                      "have": dimensional_level(e.dimensional[u.level[0]]), "open": u.id in e.unlocked}
                     for u in sorted((u for u in UNLOCKS.values() if u.level), key=lambda u: (u.level[1], u.id))],
        "camp": e.camp_view(),
        "load": {"percent": e.load_percent(), "carried": e.carried_units(), "free": CARRY_FREE,
                 "per_item": CARRY_PERCENT_PER_ITEM, "max": CARRY_MAX_PERCENT,
                 "relief_permille": (e.speed("endurance") + e.speed("strength")) // 2},
        "sight_radius": sight_radius(e.regular, e.dimensional),
        "possession_seconds": e.possess_duration_ms() // 1000,
    }


def stats(e):
    report = attribute_report(e.regular, e.dimensional)
    rows = []
    for name, row in report.items():
        rows.append({**row, "name": name, "used": bool(row["xp"] or row["dim_xp"]),
                     "speed_regular_only": speed_permille(e.regular[name], 0),
                     "speed_dimensional_only": speed_permille(0, e.dimensional[name]),
                     "life_gain": e.life_gain[name]})
    return rows


def multipliers(e):
    """Effective durations for every known action, plus combat/vital multipliers."""
    known_ctx = _known_context(e)
    actions = []
    for a in ACTIONS:
        if a.category == "fight" or not known(a, known_ctx):
            continue
        speed = e.speed(a.attribute)
        base = a.duration_ms
        effective = base if a.category in ("reflect", "pray") and a.placement == "self" else scaled_ms(base, speed)
        actions.append({"id": a.id, "name": a.name, "attribute": a.attribute, "speed": speed,
                        "base_ms": base, "effective_ms": effective})
    endurance = e.speed("endurance")
    hit_parts = [["Endurance", round(1000 / endurance, 3)]]
    hit_parts += [[name, percent / 100] for name, percent in effects.breakdown(e.equipped,
                                                                               "enemy_hit_percent")]
    punch = e.punch_damage()
    bonuses = effects.breakdown(e.equipped, "punch_damage")
    return {"actions": actions,
            "hunger_drain": round(1000 / endurance, 3),
            "enemy_hit": hit_parts,
            "punch_damage": punch,
            "punch_parts": [["Base", 1], ["Strength levels", punch - 1 - sum(n for _, n in bonuses)],
                            *[[name, n] for name, n in bonuses]]}


def rolls(e):
    """This life's rolled caps against the possible range, spot counts and pity."""
    known_ctx = _known_context(e)
    bonus = effects.total({}, "food_window_bonus")
    windows = []
    for ident, spawned, limit in e.bounty():
        action = BY_ID[ident]
        low, high = spawn_window(action, e.mastery.get(ident, 0), bonus if action.feeds else 0)
        windows.append({"id": ident, "name": action.name, "rolled": limit, "min": low, "max": high,
                        "active": e._active(ident), "spawned": spawned, "mastery": e.mastery.get(ident, 0),
                        "known": known(action, known_ctx)})
    loot = []
    for a in ACTIONS:
        if (a.loot or a.drops) and known(a, known_ctx):
            drops = [{"item": ITEMS[l.item].name, "min": l.low, "max": l.high, "chance": l.chance,
                      "roll": "fixed"} for l in a.loot]
            bonus = table_chances(a.drops) if a.drops else {}
            drops += [{"item": ITEMS[item].name, "min": low, "max": high, "chance": bp / 100,
                       "roll": RARITY[ITEMS[item].rarity].name, "color": ITEMS[item].color}
                      for item, (low, high, bp) in sorted(bonus.items(), key=lambda kv: -kv[1][2])]
            loot.append({"id": a.id, "name": a.name, "drops": drops})
    tiers = spot_tiers(e.spot_context(e.game.player.chunk))
    chances = tier_chances({t: odds for t, (_, odds) in tiers.items()}, set(tiers))
    tier_rows = [{"tier": t, "name": RARITY[t].name, "permille": chances[t] * 1000 // SCALE,
                  "actions": len(tiers[t][0])} for t in RARITY if t in chances]
    return {"life": e.life, "windows": windows, "spots_per_chunk": [min(SPOTS_PER_CHUNK), max(SPOTS_PER_CHUNK)],
            "tiers": tier_rows,
            "pity": [{"category": c, "drought": e.drought[c], "after": PITY_CHUNKS[c]} for c in PITY_CHUNKS],
            "stats": dict(e.stats), "loot": loot}


def encounter_tree(known_ids):
    """The Journal's encounter tree: [{id, title, known, total, nodes, groups}].

    Wild spots sit in JOURNAL_GROUPS by what you do there; landmark encounters under their site;
    every lead hangs under the encounters whose outcomes open it (chains nest); night creatures
    get their own branch; a known lead nothing known opens goes to "Other trails". A node is
    {id, children, hidden} - `hidden` counts follow-ups not found yet (names stay secret)."""
    opens = {a.id: list(dict.fromkeys(o.id for o in a.outcomes if o.kind == "lead")) for a in ACTIONS}
    placed = set()

    def node(ident, path=()):
        placed.add(ident)
        kids = [k for k in opens[ident] if k not in path and k != ident]
        return {"id": ident, "hidden": sum(1 for k in kids if k not in known_ids),
                "children": [node(k, path + (ident,)) for k in kids if k in known_ids]}

    def branch(ident, title, members):
        return {"id": ident, "title": title, "known": sum(1 for a in members if a.id in known_ids),
                "total": len(members), "nodes": [node(a.id) for a in members if a.id in known_ids], "groups": []}

    tree = []
    for ident, title, categories in JOURNAL_GROUPS:
        tree.append(branch(ident, title, [a for a in ACTIONS if a.placement == "spot" and a.category in categories]))
    sites = [branch(f"site:{site.id}", site.name, [a for a in ACTIONS if a.placement == "site" and a.site == site.id])
             for site in SITES.values()]
    tree.append({"id": "landmarks", "title": "Landmarks", "known": sum(g["known"] for g in sites),
                 "total": sum(g["total"] for g in sites), "nodes": [], "groups": [g for g in sites if g["known"]]})
    night = [a for a in ACTIONS if a.placement == "lead" and "night" in a.tags]
    tree.append(branch("night", "The night", night))
    others = [a for a in ACTIONS if a.placement == "lead" and a.id in known_ids and a.id not in placed
              and "night" not in a.tags]
    if others:
        tree.append(branch("trails", "Other trails", others))
    return tree


def journal(e):
    """Lifetime record plus every known encounter with its tier, grade, odds here and Journal
    control state (favor/suppress at grade 2, a regional guarantee at grade 3)."""
    j = e.journal
    current = {row["id"]: row["share_permille"] for row in describe_bucket(e.spot_context(e.game.player.chunk))}
    known_ctx = _known_context(e)
    encounters = []
    for action in ACTIONS:
        if action.placement not in ("spot", "lead", "site") or not known(action, known_ctx):
            continue
        ident, level = action.id, e.mastery.get(action.id, 0)
        locations = sorted(chunk_id for chunk_id, plan in e.spot_plans.items()
                           if any(row[0] == ident for row in plan))
        regions = [{"id": region.id, "name": region.name} for region in REGIONS.values()
                   if region.biome in action.biomes and (action.regions is None or region.id in action.regions)
                   and region.multiplier(ident) > 0]
        encounters.append({"id": ident, "name": action.name, "interaction": action.interaction, "rarity": action.rarity,
                           "placement": action.placement, "level": level,
                           "site": SITES[action.site].name if action.site else None,
                           "done": j["actions"].get(ident, 0),
                           "next": MASTERY_THRESHOLDS[level] if action.placement == "spot"
                           and level < len(MASTERY_THRESHOLDS) else None,   # only wild spots earn grades
                           "regions": regions, "current_share_permille": current.get(ident, 0),
                           "locations": locations, "mode": e.journal_favor.get(ident, "normal"),
                           "can_favor": action.placement == "spot" and level >= JOURNAL_FAVOR_MASTERY,
                           "can_guarantee": action.placement == "spot" and level >= JOURNAL_GUARANTEE_MASTERY})
    return {"actions": sorted(([BY_ID[a].name, BY_ID[a].category, n] for a, n in j["actions"].items()),
                              key=lambda r: (-r[2], r[0])),
            "items": sorted(([ITEMS[i].name, n] for i, n in j["items"].items()), key=lambda r: (-r[1], r[0])),
            "deaths": dict(j["deaths"]), "best_life_min": round(j["best_life_ms"] / 60000, 1),
            "lives": e.life, "best_depth": e.best_depth,
            "achievements": achievements(e),
            "knowledge": sorted(e.knowledge), "recipes": sorted(e.recipes),
            "life_recipes": sorted(e.life_recipes - e.recipes),
            "disabled": sorted(e.journal_disabled), "favor": dict(e.journal_favor),
            "encounters": encounters,
            "tree": encounter_tree({row["id"] for row in encounters if row["placement"] != "lead" or row["done"]
                                     or any(lead["action"] == row["id"] for lead in e.leads + e.lead_history)}),
            "guarantee": {"id": e.journal_guarantee, "region": e.journal_guarantee_region,
                          "used": e.guarantee_used},
            "leads": [dict(row) for row in e.leads],
            "lead_history": [dict(row) for row in e.lead_history[-20:]]}


def detail(e):
    return {"character": character(e), "stats": stats(e), "multipliers": multipliers(e),
            "rolls": rolls(e), "journal": journal(e)}
