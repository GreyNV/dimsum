"""Action registry views and the action bucket model.

    All actions (catalog.ACTIONS)
      -> known      : unlock is None or bought at the anchor
      -> eligible   : biome, region, placement, terrain and player conditions hold
      -> bucket     : eligible actions with weights (base x region multiplier)
      -> selected   : spot rolls (encounters.chunk_spots) or self-action choice (autopilot)

WHAT: pure functions that answer "which actions can happen here, how likely, and
why (not)". The generator and the auto-pilot both read these; nobody else decides
eligibility. WHY: unlocks must add possibilities, and designers must be able to
see why something did or did not appear (explain()).
INVARIANTS: no state, no randomness here; selection seeds belong to callers.
Weight math is integer: weight = base * region_percent // 100.
TESTS: tests/test_world_actions.py.
"""
from dataclasses import dataclass, field

from .catalog import ACTIONS, BY_ID, ITEMS, REGIONS, UNLOCKS


@dataclass(frozen=True)
class Context:
    """Where and who: everything eligibility may depend on."""
    biome: str = "dark_forest"
    region: str | None = None
    placement: str = "spot"
    unlocked: frozenset = frozenset()
    inventory: dict = field(default_factory=dict)     # self actions: items held
    gear: frozenset = frozenset()                     # gear items held
    trigger: str | None = None                        # self actions: "after_location" | "need"
    visible: bool = True                              # live play (prayer may start)
    flags: frozenset = frozenset()                    # e.g. {"prayed"}; {"hungry"}

    def __hash__(self):  # inventory dict is unhashable; hash the parts that matter
        return hash((self.biome, self.region, self.placement, self.unlocked,
                     tuple(sorted(self.inventory.items())), self.gear, self.trigger, self.visible, self.flags))


def known(action, unlocked):
    return action.unlock is None or action.unlock in unlocked


def known_actions(unlocked):
    return tuple(a for a in ACTIONS if known(a, unlocked))


def reasons_against(action, ctx):
    """Every reason `action` is not in the bucket for `ctx` (empty list = eligible)."""
    reasons = []
    if not known(action, ctx.unlocked):
        unlock = UNLOCKS[action.unlock]
        reasons.append(f"locked: needs unlock '{unlock.name}' ({unlock.cost} {unlock.currency})")
    if action.placement != ctx.placement:
        reasons.append(f"placement is {action.placement}, context is {ctx.placement}")
    if ctx.biome not in action.biomes:
        reasons.append(f"biome {ctx.biome} not in {list(action.biomes)}")
    if action.placement == "spot" and action.regions is not None and ctx.region not in action.regions:
        reasons.append(f"region {ctx.region} not in {list(action.regions)}")
    if action.placement == "spot" and ctx.region is not None:
        region = REGIONS.get(ctx.region)
        if region is not None and region.multiplier(action.id) == 0:
            reasons.append(f"region {ctx.region} weight is 0")
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
    return reasons


def weight(action, ctx):
    """Bucket weight for an eligible action (0 if not eligible)."""
    if reasons_against(action, ctx):
        return 0
    if action.placement == "spot" and ctx.region is not None:
        region = REGIONS.get(ctx.region)
        if region is not None:
            return action.weight * region.multiplier(action.id) // 100
    return action.weight


def bucket(ctx):
    """[(action, weight)] for every eligible action, in catalog order (weights > 0)."""
    return [(a, w) for a in ACTIONS if (w := weight(a, ctx)) > 0]


def explain(action_id, ctx):
    """Why an action is (not) in the bucket: {id, eligible, weight, share, reasons}."""
    action = BY_ID[action_id]
    entries = bucket(ctx)
    total = sum(w for _, w in entries)
    w = weight(action, ctx)
    return {"id": action.id, "name": action.name, "eligible": w > 0, "weight": w,
            "share_permille": w * 1000 // total if total and w else 0,
            "reasons": reasons_against(action, ctx) or ["eligible"]}


def describe_bucket(ctx):
    """Bucket rows with shares, for debug views and the CLI."""
    entries = bucket(ctx)
    total = sum(w for _, w in entries) or 1
    return [{"id": a.id, "name": a.name, "category": a.category, "weight": w,
             "share_permille": w * 1000 // total} for a, w in entries]
