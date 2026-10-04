"""UI-independent summon review payloads."""
from .summoning import SummonedItem

ATTRIBUTE_ORDER = ("strength", "endurance", "agility", "intelligence", "perception", "willpower")
EQUIPMENT_SLOTS = ("head", "body", "hands", "feet", "weapon", "charm")


def item_stats(item: SummonedItem | None) -> dict[str, float]:
    if item is None:
        return {}
    stats = dict(item.base_stats)
    if item.speed_bonus:
        stats[item.discipline + "_speed"] = item.speed_bonus
    if item.softcap_bonus:
        stats[item.discipline + "_softcap"] = item.softcap_bonus
    if item.shard_rate_bonus:
        stats["clone_shard_rate"] = item.shard_rate_bonus
    return stats


def compare_items(current: SummonedItem | None, candidate: SummonedItem) -> dict:
    before, after = item_stats(current), item_stats(candidate)
    keys = sorted(before.keys() | after.keys(),
                  key=lambda key: (ATTRIBUTE_ORDER.index(key) if key in ATTRIBUTE_ORDER else 99, key))

    def label(key):
        return key.replace("_", " ").title()

    def rows(values, other):
        return [{
            "key": key, "label": label(key), "value": values.get(key, 0),
            "delta": values.get(key, 0) - other.get(key, 0),
            "direction": ("gain" if values.get(key, 0) > other.get(key, 0) else
                          "loss" if values.get(key, 0) < other.get(key, 0) else "unchanged"),
            "unit": "percent" if key.endswith("_speed") or key == "clone_shard_rate" else "points",
        } for key in keys]

    def panel(item, values, other):
        return {
            "id": item.id if item else None,
            "name": item.name if item else "Empty slot",
            "level": item.level if item else None,
            "rarity": item.rarity if item else None,
            "slot": candidate.slot,
            "stats": rows(values, other),
        }

    changes = [{
        **row, "before": before.get(row["key"], 0), "after": row["value"],
    } for row in rows(after, before) if row["delta"] != 0]
    return {
        "slot": candidate.slot,
        "equipped": panel(current, before, after),
        "candidate": panel(candidate, after, before),
        "changes": changes,
        "has_changes": bool(changes),
        "summary": [
            f"{row['label']} {row['delta'] * (100 if row['unit'] == 'percent' else 1):+g}"
            + ("%" if row["unit"] == "percent" else "")
            for row in changes
        ],
    }
