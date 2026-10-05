"""Journal: lifetime counts across all lives, and achievements derived from them.

WHAT: what the avatar has done over every life (actions completed, items gathered,
deaths by cause, longest life). Achievements (catalog.ACHIEVEMENTS) are computed
from it on demand, never stored, so editing their thresholds never breaks saves.
OWNER: autopilot.Expedition writes through record_* ; details.py reads.
TESTS: tests/test_world_pages.py.
"""
from .catalog import ACHIEVEMENTS, BY_ID, ITEMS
from .models import integer

DEATH_CAUSES = ("starvation", "boar", "exhaustion")


def new_journal():
    return {"actions": {}, "items": {}, "deaths": {}, "best_life_ms": 0}


def record_action(journal, action_id):
    journal["actions"][action_id] = journal["actions"].get(action_id, 0) + 1


def record_items(journal, items):
    for item, count in items:
        if count > 0:
            journal["items"][item] = journal["items"].get(item, 0) + count


def record_death(journal, cause, life_ms):
    journal["deaths"][cause] = journal["deaths"].get(cause, 0) + 1
    journal["best_life_ms"] = max(journal["best_life_ms"], life_ms)


def validate_journal(data):
    if type(data) is not dict or set(data) != {"actions", "items", "deaths", "best_life_ms"}:
        raise ValueError("invalid journal")
    for name, keys in (("actions", BY_ID), ("items", ITEMS), ("deaths", DEATH_CAUSES)):
        if type(data[name]) is not dict or any(k not in keys for k in data[name]):
            raise ValueError(f"invalid journal {name}")
        for value in data[name].values():
            integer(value, f"journal {name} count", 0)
    integer(data["best_life_ms"], "journal best life", 0)
    return {"actions": dict(data["actions"]), "items": dict(data["items"]),
            "deaths": dict(data["deaths"]), "best_life_ms": data["best_life_ms"]}


def metric(expedition, name):
    j = expedition.journal
    kind, _, arg = name.partition(":")
    if kind == "action":
        return j["actions"].get(arg, 0)
    if kind == "category":
        return sum(n for a, n in j["actions"].items() if BY_ID[a].category == arg)
    if kind == "item":
        return j["items"].get(arg, 0)
    if kind == "deaths":
        return j["deaths"].get(arg, 0) if arg else sum(j["deaths"].values())
    if kind == "lives":
        return expedition.life
    if kind == "best_depth":
        return expedition.best_depth
    if kind == "best_life_min":
        return j["best_life_ms"] // 60000
    if kind == "unlocks":
        return len(expedition.unlocked)
    raise ValueError(f"unknown metric {name}")


def achievements(expedition):
    rows = []
    for a in ACHIEVEMENTS:
        value = metric(expedition, a.metric)
        rows.append({"id": a.id, "name": a.name, "description": a.description,
                     "progress": min(value, a.threshold), "threshold": a.threshold, "done": value >= a.threshold})
    return rows
