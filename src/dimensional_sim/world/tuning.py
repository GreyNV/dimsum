"""Central balance values for the forest expedition's newer systems.

Older vitals/combat constants live in autopilot/constants.py (and are
re-exported by autopilot/__init__.py for tests); everything added by the closed-loop iteration lives
here so a designer can rebalance without reading rules. Integers only.
See docs/design/BALANCING.md for measured effects and the simulate command.
"""
# Spot generation (encounters.chunk_spots): spots per chunk by a seeded roll over this table.
SPOTS_PER_CHUNK = (0, 1, 1, 2, 2, 3)

# Spawn pity (autopilot._screen): if this many newly screened chunks admitted no spot of a
# category, the next chunk with room gets one forced spot of that category.
PITY_CHUNKS = {"food": 5, "enemy": 4}

# Ash conversion: for each resource, the first OFFER_FULL units give full value, then half.
OFFER_FULL = 5
# Each ring of depth also grants ASH_PER_RING at the end of a life.
ASH_PER_RING = 1

# Gear and boon numbers are catalog Effects (catalog.py ItemDef/BoonDef.effects).
UNARMED_REACH = 1             # one cardinal cell; the default punch hitbox

# Need-driven crafting thresholds (autopilot policy, not rules).
SNARE_WHEN_HUNGER_BELOW = 60   # points; only when no food is carried

# Exploration risk policy (autopilot.frontier): the auto-pilot only explores rings where
# one boar fight costs at most this percent of full health (one ring more when starving).
COMFORT_DAMAGE_PERCENT = 60
