"""Pure action eligibility and weighted procedural buckets.

Knowledge permits an action to enter a bucket; a roll creates a world spot.
Context then decides whether that concrete opportunity can be performed.
Self recipes use the same eligibility rules but need no terrain roll.
"""
from dataclasses import dataclass, field

from .catalog import ACTIONS, BY_ID, ITEMS, REGIONS, UNLOCKS
from . import catalog


@dataclass(frozen=True)
class Context:
    """Persistent progression, current place, and local action conditions."""

    biome: str = "dark_forest"
    region: str | None = None
    region_def: object | None = None
    placement: str = "spot"
    unlocked: frozenset = frozenset()
    knowledge: frozenset = frozenset()
    recipes: frozenset = frozenset()
    active_leads: frozenset = frozenset()
    action_counts: dict = field(default_factory=dict)
    item_counts: dict = field(default_factory=dict)
    levels: dict = field(default_factory=dict)
    mastery: dict = field(default_factory=dict)
    journal_disabled: frozenset = frozenset()
    journal_favor: dict = field(default_factory=dict)
    inventory: dict = field(default_factory=dict)
    gear: frozenset = frozenset()
    hunger: int = 0
    food_carried: bool = False
    trigger: str | None = None
    visible: bool = True
    flags: frozenset = frozenset()
    spawned: bool | None = None
    resolved: bool = False


def _ctx(value):
    """Accept the historical bare unlock set as well as a full Context."""
    return value if isinstance(value, Context) else Context(unlocked=frozenset(value))


def known(action, unlocked):
    """Whether permanent permission/knowledge permits this action to occur."""
    ctx = _ctx(unlocked)
    return (action.unlock is None or action.unlock in ctx.unlocked) and \
        (getattr(action, "knowledge", None) is None or action.knowledge in ctx.knowledge) and \
        (getattr(action, "recipe", None) is None or action.recipe in ctx.recipes)


def known_actions(unlocked):
    return tuple(a for a in ACTIONS if known(a, unlocked))


def _requirement_reasons(action, ctx):
    result = []
    for req in getattr(action, "requirements", ()):
        if req.kind == "action_count":
            have = ctx.action_counts.get(req.id, 0)
            if have < req.count:
                result.append(f"needs {req.count} completions of {req.id} (have {have})")
        elif req.kind == "item_count":
            have = ctx.item_counts.get(req.id, 0)
            if have < req.count:
                result.append(f"needs {req.count} collected {req.id} (have {have})")
        elif req.kind == "level":
            have = ctx.levels.get(req.id, 0)
            if have < req.count:
                result.append(f"needs {req.id} level {req.count} (have {have})")
        elif req.kind == "knowledge" and req.id not in ctx.knowledge:
            result.append(f"needs knowledge {req.id}")
        elif req.kind == "unlock" and req.id not in ctx.unlocked:
            result.append(f"needs unlock {req.id}")
        elif req.kind == "recipe" and req.id not in ctx.recipes:
            result.append(f"needs recipe {req.id}")
    return result


def bucket_reasons(action, ctx):
    """Why the definition cannot enter this place's procedural/action pool."""
    reasons = []
    if action.unlock is not None and action.unlock not in ctx.unlocked:
        unlock = UNLOCKS.get(action.unlock)
        reasons.append(f"locked: needs unlock '{unlock.name}' ({unlock.cost} {unlock.currency})"
                       if unlock else f"locked: needs unlock '{action.unlock}'")
    if getattr(action, "knowledge", None) is not None and action.knowledge not in ctx.knowledge:
        reasons.append(f"unknown: needs knowledge '{action.knowledge}'")
    if getattr(action, "recipe", None) is not None and action.recipe not in ctx.recipes:
        reasons.append(f"unknown: needs recipe '{action.recipe}'")
    reasons.extend(_requirement_reasons(action, ctx))
    if action.placement != ctx.placement:
        reasons.append(f"placement is {action.placement}, context is {ctx.placement}")
    if ctx.biome not in action.biomes:
        reasons.append(f"biome {ctx.biome} not in {list(action.biomes)}")
    region_id = ctx.region_def.id if ctx.region_def is not None else ctx.region
    if action.placement in ("spot", "lead") and action.regions is not None and region_id not in action.regions:
        reasons.append(f"region {region_id} not in {list(action.regions)}")
    if action.placement == "spot" and region_id is not None:
        region = ctx.region_def or REGIONS.get(region_id)
        if region is not None and region.multiplier(action.id) == 0:
            reasons.append(f"region {region_id} weight is 0")
    if action.placement == "lead" and action.id not in ctx.active_leads:
        reasons.append("no active temporary lead")
    toggle_level = getattr(catalog, "JOURNAL_TOGGLE_MASTERY", 2)
    if (action.placement == "spot" and action.id in ctx.journal_disabled
            and ctx.mastery.get(action.id, 0) >= toggle_level):
        reasons.append("journal disabled")
    return reasons


def context_reasons(action, ctx):
    """Why a known, placed opportunity cannot be performed right now."""
    reasons = []
    if action.placement == "self":
        if ctx.trigger is not None and action.trigger != ctx.trigger:
            reasons.append(f"trigger is {action.trigger}, context is {ctx.trigger}")
        for item, count in action.cost:
            if ctx.inventory.get(item, 0) < count:
                reasons.append(f"needs {count} {ITEMS[item].name.lower()} (have {ctx.inventory.get(item, 0)})")
        if action.effect is not None and action.effect in ctx.gear:
            reasons.append(f"already carrying {ITEMS[action.effect].name.lower()}")
        if action.visible_only and not ctx.visible:
            reasons.append("only during live play")
        if "once_per_life" in action.tags and f"done:{action.id}" in ctx.flags:
            reasons.append("already done this life")
        if action.trigger == "need" and ctx.trigger == "need":
            if action.need_hunger_below is not None and ctx.hunger >= action.need_hunger_below:
                reasons.append(f"hunger must be below {action.need_hunger_below}")
            if action.need_no_food and ctx.food_carried:
                reasons.append("food already carried")
    if ctx.resolved:
        reasons.append("opportunity resolved")
    return reasons


def reasons_against(action, ctx):
    """Compatibility API: all bucket and immediate context blockers."""
    return bucket_reasons(action, ctx) + context_reasons(action, ctx)


def weight(action, ctx):
    """Effective pool weight, after region and earned Journal influence."""
    if reasons_against(action, ctx):
        return 0
    weight_value = action.weight
    if action.placement == "spot" and (ctx.region is not None or ctx.region_def is not None):
        region = ctx.region_def or REGIONS.get(ctx.region)
        if region is not None:
            weight_value = weight_value * region.multiplier(action.id) // 100
    favor_level = getattr(catalog, "JOURNAL_FAVOR_MASTERY", 3)
    if action.placement == "spot" and ctx.mastery.get(action.id, 0) >= favor_level:
        choice = ctx.journal_favor.get(action.id)
        if choice in ("favor", "favour"):
            weight_value = max(1, weight_value * getattr(catalog, "JOURNAL_FAVOR_PERCENT", 150) // 100)
        elif choice == "suppress":
            weight_value = max(1, weight_value * getattr(catalog, "JOURNAL_SUPPRESS_PERCENT", 50) // 100)
    return weight_value


def bucket(ctx):
    """Eligible definitions in catalog order, with positive effective weights."""
    return [(a, w) for a in ACTIONS if (w := weight(a, ctx)) > 0]


def explain(action_id, ctx):
    """Separate permanent knowledge, pool, local context, and concrete spawn."""
    action = BY_ID[action_id]
    b_reasons = bucket_reasons(action, ctx)
    c_reasons = context_reasons(action, ctx)
    entries = bucket(ctx)
    total = sum(w for _, w in entries)
    w = weight(action, ctx)
    eligible = w > 0
    spawned = ctx.spawned if action.placement == "spot" else \
        action.id in ctx.active_leads if action.placement == "lead" else True
    available = eligible and bool(spawned) if spawned is not None else None
    return {"id": action.id, "name": action.name, "known": known(action, ctx),
            "state": lifecycle_state(action, ctx, b_reasons, c_reasons, spawned),
            "bucket_eligible": not b_reasons, "context_eligible": not c_reasons,
            "eligible": eligible, "weight": w,
            "share_permille": w * 1000 // total if total and w else 0,
            "spawned": spawned, "available": available,
            "reasons": b_reasons + c_reasons or ["eligible"],
            "bucket_reasons": b_reasons, "context_reasons": c_reasons,
            "weight_modifiers": _weight_modifiers(action, ctx)}


STATES = ("UNKNOWN", "JOURNAL_DISABLED", "BUCKET_INELIGIBLE", "BUCKET_ELIGIBLE", "NOT_ROLLED",
          "TEMPORARY_LEAD", "RECIPE", "CONTEXT_INELIGIBLE", "AVAILABLE", "RESOLVED")


def lifecycle_state(action, ctx, b_reasons, c_reasons, spawned):
    """One label for where an action stops in the pipeline (debug overlay and `cli inspect`).

    UNKNOWN -> (JOURNAL_DISABLED | BUCKET_INELIGIBLE) -> BUCKET_ELIGIBLE -> NOT_ROLLED | rolled
    -> CONTEXT_INELIGIBLE | AVAILABLE (a rolled spot still needs spawn-window admission in play). Leads report TEMPORARY_LEAD while their token is live;
    recipes report RECIPE when known but not currently affordable. BUCKET_ELIGIBLE means the
    spawn state was not supplied, so whether a spot exists is unknown."""
    if ctx.resolved:
        return "RESOLVED"
    if not known(action, ctx):
        return "UNKNOWN"
    if any(r == "journal disabled" for r in b_reasons):
        return "JOURNAL_DISABLED"
    if b_reasons:
        return "BUCKET_INELIGIBLE"
    if action.placement == "spot" and spawned is None:
        return "BUCKET_ELIGIBLE"
    if action.placement == "spot" and not spawned:
        return "NOT_ROLLED"
    if c_reasons:
        return "RECIPE" if action.category == "craft" else "CONTEXT_INELIGIBLE"
    if action.placement == "lead":
        return "TEMPORARY_LEAD"
    return "AVAILABLE"


def _weight_modifiers(action, ctx):
    modifiers = []
    region = ctx.region_def or REGIONS.get(ctx.region)
    if action.placement == "spot" and region is not None:
        modifiers.append({"source": "region", "percent": region.multiplier(action.id)})
    if action.placement == "spot" and ctx.mastery.get(action.id, 0) >= getattr(catalog, "JOURNAL_FAVOR_MASTERY", 3):
        choice = ctx.journal_favor.get(action.id)
        if choice in ("favor", "favour"):
            modifiers.append({"source": "journal", "percent": getattr(catalog, "JOURNAL_FAVOR_PERCENT", 150)})
        elif choice == "suppress":
            modifiers.append({"source": "journal", "percent": getattr(catalog, "JOURNAL_SUPPRESS_PERCENT", 50)})
    return modifiers


def describe_bucket(ctx):
    entries = bucket(ctx)
    total = sum(w for _, w in entries) or 1
    return [{"id": a.id, "name": a.name, "category": a.category, "weight": w,
             "share_permille": w * 1000 // total} for a, w in entries]
