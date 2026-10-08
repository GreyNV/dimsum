"""Currency rules: automatic dimensional ash conversion and anchor purchases.

    all carried items --(return to anchor)--> dimensional ash --(unlock)--> new actions
    prayer --> blessing --(shrine unlock | next-life boon)--> new spot / one-life favour

WHAT: pure value rules and purchase validation over an object with the meta fields
(ash, blessing, unlocked, boon_next). WHY: one place answers "what
is this worth" and "why can't I buy this". The auto-pilot applies the results.
TESTS: tests/test_world_closed_loop.py.
"""
from .catalog import BOONS, ITEMS, UNLOCKS
from .tuning import ASH_PER_RING, OFFER_FULL


def offer_value(item, count, previous=0):
    """Ash gained from this stack, accounting for all earlier lives' conversions."""
    value = ITEMS[item].ash_value
    def cumulative(n):
        full = min(n, OFFER_FULL)
        return value * full + value * (n - full) // 2
    return cumulative(previous + count) - cumulative(previous)


def rebirth_ash(inventory, depth, converted=None):
    """All carried resources convert automatically when a life ends."""
    converted = converted or {}
    return sum(offer_value(item, count, converted.get(item, 0))
               for item, count in inventory.items()) + depth * ASH_PER_RING


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
    return row
