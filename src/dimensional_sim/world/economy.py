"""Currency rules: automatic dimensional ash conversion and anchor purchases.

    all carried items --(life ends)--> dimensional ash --(keep)--> recipes found this life, for good
    dimensional levels --(automatically)--> new actions (UnlockDef.level)
    a building at the anchor camp --(bind, a lot of ash)--> stands in every later life
    dimensional ash --(unlock)--> skills such as the campfire

Purchases happen at the anchor: between lives, or mid-life by contacting it (the world waits).
WHAT: pure value rules and purchase validation over an object with the meta fields
(ash, unlocked, recipes, life_recipes, buildings). WHY: one place answers "what
is this worth" and "why can't I buy this". The auto-pilot applies the results.
TESTS: tests/test_world_closed_loop.py.
"""
from .catalog import BUILDINGS, ITEMS, RECIPE_KEEP_COST, RECIPE_NAMES, UNLOCKS
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
        if unlock.level is not None:   # opened by dimensional levels, never sold
            continue
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
    for recipe in sorted(getattr(meta, "life_recipes", ()), key=lambda r: (RECIPE_KEEP_COST[r], r)):
        if recipe in meta.recipes:
            continue
        cost = RECIPE_KEEP_COST[recipe]
        reasons = [] if meta.ash >= cost else [f"needs {cost} ash"]
        rows.append({"kind": "keep", "id": recipe, "name": f"Keep: {RECIPE_NAMES[recipe]}",
                     "description": "Found this life. Keep the knowledge so every later life can craft it.",
                     "currency": "ash", "cost": cost, "owned": False, "available": not reasons, "reasons": reasons})
    for building in BUILDINGS.values():   # bind what this life built at the camp
        built = building.id in getattr(meta, "buildings", ())
        bound = building.id in getattr(meta, "bound_buildings", ())
        if not built and not bound:
            continue
        reasons = []
        if bound:
            reasons.append("already bound")
        if meta.ash < building.bind_cost:
            reasons.append(f"needs {building.bind_cost} ash")
        rows.append({"kind": "bind", "id": building.id, "name": f"Bind the {building.name.lower()}",
                     "description": f"{building.description} Binding keeps it standing in every later life.",
                     "currency": "ash", "cost": building.bind_cost, "owned": bound,
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
    elif kind == "bind":
        meta.bound_buildings.add(ident)
    elif kind == "keep":
        meta.recipes.add(ident)
    return row
