"""Cascading rarity rolls, shared by encounter spawns and bonus drops (and later the summon).

The rarest tier rolls first at its odds; only a miss tries the next tier; the fallback
tier (catalog.FALLBACK_RARITY) catches the rest. Tiers with nothing to give are skipped,
not rolled. Each tier draws its own seeded number, so tuning one tier never reshuffles
another's results. Integers only (basis points, 1/10000); no shared RNG.
"""
from .catalog import DROP_TABLES, FALLBACK_RARITY, RARITY_ORDER, TIER_ODDS_CAP
from .seeds import derive_seed

SCALE = 10000


def cascade(odds, available, seed, *salt):
    """The tier this draw lands in, or None when nothing is available.

    `odds`: {tier: basis points} for non-fallback tiers; `available`: tiers that have
    something to give. The last available tier in RARITY_ORDER catches every miss."""
    tiers = [t for t in RARITY_ORDER if t in available]
    for tier in tiers[:-1]:
        if derive_seed(seed, "tier", *salt, tier) % SCALE < min(odds.get(tier, 0), TIER_ODDS_CAP):
            return tier
    return tiers[-1] if tiers else None


def tier_chances(odds, available):
    """{tier: basis points} that `cascade` lands in each available tier (sums to 10000)."""
    tiers = [t for t in RARITY_ORDER if t in available]
    result, left = {}, SCALE
    for tier in tiers[:-1]:
        result[tier] = left * min(odds.get(tier, 0), TIER_ODDS_CAP) // SCALE
        left -= result[tier]
    if tiers:
        result[tiers[-1]] = left
    return result


def weighted(entries, roll):
    """Pick from [(value, weight), ...] with `roll` already reduced modulo the total."""
    for value, w in entries:
        if roll < w:
            return value
        roll -= w
    raise ValueError("roll outside the weighted total")


def _available(table):
    return set(table.pools) | ({FALLBACK_RARITY} if FALLBACK_RARITY not in table.pools else set())


def roll_table(table_id, seed):
    """One cascading roll of a drop table: [(item, count, tier)] (empty on a fallback miss).

    `tier` is the table tier that hit (for a nested table, the outer tier)."""
    table = DROP_TABLES[table_id]
    tier = cascade(table.odds, _available(table), seed)
    pool = table.pools.get(tier, ())
    if not pool:
        return []
    pick = weighted([(p, p.weight) for p in pool],
                    derive_seed(seed, "pick", tier) % sum(p.weight for p in pool))
    if pick.table is not None:
        return [(item, count, tier) for item, count, _ in roll_table(pick.table, derive_seed(seed, "nested", pick.table))]
    count = pick.low + derive_seed(seed, "count", tier) % (pick.high - pick.low + 1)
    return [(pick.item, count, tier)]


def table_chances(table_id, scale=SCALE):
    """{item: (low, high, basis points)} — each item's exact chance from one roll of the table."""
    table = DROP_TABLES[table_id]
    result = {}
    for tier, chance in tier_chances(table.odds, _available(table)).items():
        pool = table.pools.get(tier, ())
        total = sum(p.weight for p in pool)
        for pick in pool:
            share = chance * scale // SCALE * pick.weight // total
            nested = (table_chances(pick.table, share) if pick.table is not None
                      else {pick.item: (pick.low, pick.high, share)})
            for item, (low, high, bp) in nested.items():
                old = result.get(item)
                result[item] = (min(low, old[0]), max(high, old[1]), bp + old[2]) if old else (low, high, bp)
    return result
