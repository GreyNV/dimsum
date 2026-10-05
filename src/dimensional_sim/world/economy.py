"""Currency rules: anchor offering, rebirth ash, and anchor purchases.

    items --(offer at the anchor)--> dimensional dust --(unlock)--> new actions
    items --(left unoffered, burned at rebirth)--> ash --(mastery)--> wider spawn windows
    prayer --> blessing --(shrine unlock | next-life boon)--> new spot / one-life favour

WHAT: pure value rules and purchase validation over an object with the meta fields
(dust, ash, blessing, unlocked, mastery, boon_next). WHY: one place answers "what
is this worth" and "why can't I buy this". The auto-pilot applies the results.
TESTS: tests/test_world_economy.py.
"""
from .catalog import BOONS, BY_ID, ITEMS, MASTERY_MAX, UNLOCKS, mastery_cost
from .tuning import ASH_DIVISOR, ASH_PER_RING, OFFER_FULL


def offer_value(item, count):
    """Dust for offering a whole stack: full value for OFFER_FULL units, half after."""
    value = ITEMS[item].dust
    full = min(count, OFFER_FULL)
    return value * full + value * (count - full) // 2


def rebirth_ash(inventory, depth):
    """Ash from everything still carried when the next life begins, plus depth."""
    burned = sum(ITEMS[item].dust * count for item, count in inventory.items())
    return burned // ASH_DIVISOR + depth * ASH_PER_RING


MASTERABLE = tuple(a.id for a in BY_ID.values() if a.window is not None)


def offers(meta):
    """Everything purchasable at the anchor, with cost and blocking reasons."""
    rows = []
    for unlock in UNLOCKS.values():
        reasons = []
        if unlock.id in meta.unlocked:
            reasons.append("already unlocked")
        missing = [UNLOCKS[r].name for r in unlock.requires if r not in meta.unlocked]
        if missing:
            reasons.append("requires " + ", ".join(missing))
        if getattr(meta, unlock.currency) < unlock.cost:
            reasons.append(f"needs {unlock.cost} {unlock.currency}")
        rows.append({"kind": "unlock", "id": unlock.id, "name": unlock.name, "description": unlock.description,
                     "currency": unlock.currency, "cost": unlock.cost, "owned": unlock.id in meta.unlocked,
                     "available": not reasons, "reasons": reasons})
    for boon in BOONS.values():
        reasons = []
        if meta.boon_next is not None:
            reasons.append("a boon is already chosen for the next life")
        if meta.blessing < boon.cost:
            reasons.append(f"needs {boon.cost} blessing")
        rows.append({"kind": "boon", "id": boon.id, "name": boon.name, "description": boon.description,
                     "currency": "blessing", "cost": boon.cost, "owned": meta.boon_next == boon.id,
                     "available": not reasons, "reasons": reasons})
    for action_id in MASTERABLE:
        action, level = BY_ID[action_id], meta.mastery.get(action_id, 0)
        reasons = []
        if action.unlock is not None and action.unlock not in meta.unlocked:
            reasons.append(f"unlock {UNLOCKS[action.unlock].name} first")
        if level >= MASTERY_MAX:
            reasons.append("mastered")
        cost = mastery_cost(level)
        if level < MASTERY_MAX and meta.ash < cost:
            reasons.append(f"needs {cost} ash")
        rows.append({"kind": "mastery", "id": action_id, "name": f"{action.name} mastery {level + 1}",
                     "description": f"+1 high (and +1 low every 2nd level) on the at-once cap. Level {level}/{MASTERY_MAX}.",
                     "currency": "ash", "cost": cost, "owned": level >= MASTERY_MAX,
                     "available": not reasons, "reasons": reasons})
    return rows


def purchase(meta, kind, ident):
    """Apply one purchase to `meta` or raise ValueError with the blocking reasons."""
    row = next((r for r in offers(meta) if r["kind"] == kind and r["id"] == ident), None)
    if row is None:
        raise ValueError("unknown anchor purchase")
    if not row["available"]:
        raise ValueError("; ".join(row["reasons"]))
    setattr(meta, row["currency"], getattr(meta, row["currency"]) - row["cost"])
    if kind == "unlock":
        meta.unlocked.add(ident)
    elif kind == "boon":
        meta.boon_next = ident
    else:
        meta.mastery[ident] = meta.mastery.get(ident, 0) + 1
    return row
