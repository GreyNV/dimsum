"""Central balance values for the forest expedition's newer systems.

Older vitals/combat constants still live at the top of autopilot.py (and are
re-exported there for tests); everything added by the closed-loop iteration lives
here so a designer can rebalance without reading rules. Integers only.
See docs/design/BALANCING.md for measured effects and the simulate command.
"""
# Spot generation (encounters.chunk_spots): spots per chunk by a seeded roll over this table.
SPOTS_PER_CHUNK = (0, 1, 1, 2, 2, 3)

# Spawn pity (autopilot._screen): if this many newly screened chunks admitted no spot of a
# category, the next chunk with room gets one forced spot of that category.
PITY_CHUNKS = {"food": 5, "enemy": 4}

# Anchor offering: per stack, the first OFFER_FULL units give full dust, the rest half.
OFFER_FULL = 5
# Rebirth: unoffered items burn to ash at 1/ASH_DIVISOR of their dust value, plus
# ASH_PER_RING per ring of depth reached this life.
ASH_DIVISOR = 2
ASH_PER_RING = 1

# Crafted gear effects.
UNARMED_REACH = 1             # one cardinal cell; the default punch hitbox
STAFF_PUNCH_BONUS = 1
WRAP_HIT_PERCENT = 70          # hide wrap: boar hits deal 70%
IRON_SKIN_HIT_PERCENT = 75     # boon: boar hits deal 75%
BOUNTY_WINDOW_BONUS = 1        # boon: +1 low/high on food spawn windows

# Need-driven crafting thresholds (autopilot policy, not rules).
SNARE_WHEN_HUNGER_BELOW = 60   # points; only when no food is carried

# Exploration risk policy (autopilot.frontier): the auto-pilot only explores rings where
# one boar fight costs at most this percent of full health (one ring more when starving).
COMFORT_DAMAGE_PERCENT = 60
