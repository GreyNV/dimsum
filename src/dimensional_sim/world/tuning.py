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
# Unarmed punches gain +1 damage per this many (softcapped) Strength levels. Was 5 while the
# walking staff gave +1; 3 restores the measured balance without a weapon (docs/design/BALANCING.md).
STRENGTH_LEVELS_PER_PUNCH = 3

# Need-driven crafting thresholds (autopilot policy, not rules).
SNARE_WHEN_HUNGER_BELOW = 60   # points; only when no food is carried

# Exploration risk policy (autopilot.frontier): the auto-pilot only explores rings where
# one boar fight costs at most this percent of full health (one ring more when starving).
COMFORT_DAMAGE_PERCENT = 60

# Anchor camp (autopilot/camp.py): the storage chest and carry load.
CHEST_SLOTS = 6                 # item stacks a storage chest holds (STACK_LIMIT each)
# % spawn weight an ecology loses per harvest in one region cell (one life). Food thins
# slowly (starvation must stay rare); wood thins fast (the crafting station is a milestone).
PRESSURE_STEP = {"wood": 20, "game": 15, "berries": 8, "fungi": 10, "eggs": 10, "fish": 12}
PRESSURE_FLOOR = 25            # % it never drops below: a worked area keeps a trickle
SHIMMER_RARITY_PERCENT = 250   # a shimmering region cell: odds of uncommon and rare spots x2.5 (capped per tier)
CAMPFIRE_AWAY = 20             # tiles: a badly hurt avatar this far from the anchor and any fire makes one
STOW_TRIP_AT = 30               # with a chest, carrying this many material units sends the avatar home
CARRY_FREE = 10                 # carried units that cost no speed
CARRY_PERCENT_PER_ITEM = 1      # +1% movement time per further unit, divided by the Endurance/Strength speed
CARRY_MAX_PERCENT = 60          # the load never slows walking by more than this
