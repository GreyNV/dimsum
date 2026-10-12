"""Effects: how gear and boons change numbers.

WHAT: the active effect sources of an expedition (equipped gear in slot order, then the
life's boon) and the rules that combine them per stat (catalog.EFFECT_STATS):
"add" stats sum; "percent" stats multiply in turn with an integer floor after each.
WHY: a new item or boon is a catalog entry with effects; no engine code names it.
TESTS: tests/test_world_systems.py.
"""
from .catalog import BOONS, EFFECT_STATS, EQUIPMENT_SLOTS, ITEMS


def sources(equipped, boon):
    """[(source name, (Effect, ...))] in application order."""
    result = [(ITEMS[equipped[slot]].name, ITEMS[equipped[slot]].effects)
              for slot in EQUIPMENT_SLOTS if equipped.get(slot)]
    if boon is not None:
        result.append((f"{BOONS[boon].name} boon", BOONS[boon].effects))
    return result


def total(equipped, boon, stat):
    """Sum of an "add" stat over every active source."""
    if EFFECT_STATS[stat] != "add":
        raise ValueError(f"{stat} is not an additive stat")
    return sum(e.amount for _, effects in sources(equipped, boon) for e in effects if e.stat == stat)


def scale(value, equipped, boon, stat):
    """`value` after every active "percent" effect on `stat`, in order."""
    if EFFECT_STATS[stat] != "percent":
        raise ValueError(f"{stat} is not a percent stat")
    for _, effects in sources(equipped, boon):
        for effect in effects:
            if effect.stat == stat:
                value = value * effect.amount // 100
    return value


def breakdown(equipped, boon, stat):
    """[(source name, amount)] for one stat, for the stats pages."""
    return [(name, e.amount) for name, effects in sources(equipped, boon) for e in effects if e.stat == stat]
