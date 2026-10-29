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
STRENGTH_LEVELS_PER_PUNCH = 5

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

# Day and night (autopilot/night.py). The world clock is the expedition's simulation time, so
# it runs through lives and the anchor alike. A new game starts DAY_START_MS into the day.
DAY_MS = 720_000              # one full day: 8 minutes of daylight, then 4 of night
NIGHT_MS = 240_000            # the last third of each day is night
TWILIGHT_MS = 60_000          # dusk and dawn: the light fades over this long (presentation only)
DAY_START_MS = 60_000         # where in the day a brand-new expedition begins (a minute after dawn)
NIGHT_SPAWN_EVERY_MS = 30_000 # at night, a wolf may come out of the dark this often...
NIGHT_SPAWN_PERCENT = 60      # first-night chance per tick, including at camp and campfires
NIGHT_SPAWN_GROWTH = 5        # extra percentage points per full day survived this life
NIGHT_SPAWN_MAX = 90         # cap the late-life pressure
NIGHT_FOES_BY_RING = ((0, 1), (2, 2), (5, 3))   # (from ring, wolves at once) - deeper is more dangerous
NIGHT_SPAWN_NEAR, NIGHT_SPAWN_FAR = 7, 13       # steps from the avatar a wolf appears (out of sight)
FIRE_LIGHT_RADIUS = 4         # daylight enemies fear this radius; night wolves ignore it

# XP from base time (docs/design/STATS_AND_ENEMIES_AUDIT.md, step 6). An action's XP is its base
# duration in seconds x XP_PER_SECOND, times its rarity's percent; self actions (crafts, building,
# the campfire) earn SELF_XP_PERCENT of that, the story's milestones STORY_XP_PERCENT. Because XP
# follows base time, not the time taken, a faster avatar earns more XP per hour.
XP_PER_SECOND = 14
RARITY_XP_PERCENT = {"common": 100, "uncommon": 110, "rare": 150}
SELF_XP_PERCENT = 40
STORY_XP_PERCENT = 150
# Fights pay per landed hit: XP per hit point taken off the enemy, and the finishing blow adds
# FINISH_XP_PERCENT of the whole enemy's worth. A starred enemy has more HP, so it pays more.
FIGHT_XP_PER_HP = 8
FINISH_XP_PERCENT = 25

# Walking pays per tile stepped, never per second, about a quarter of all XP. The avatar walks
# about 11,000 tiles an hour (the audit's first figure, 2,000, sampled once a second and missed
# most steps), so: about 1,100 Agility, 700-1,400 Endurance and 1,000 Perception XP an hour.
AGILITY_TILES_PER_XP = 10       # 1 Agility XP every 10 tiles
ENDURANCE_TILES_PER_XP = 15     # 1 Endurance XP every 15 tiles, twice as fast hungry or heavily loaded
ENDURANCE_HARD_HUNGER = 30      # points of hunger at or below which walking is "hungry"
PERCEPTION_CELLS_PER_XP = 100   # 1 Perception XP per 100 newly seen cells (exploring, not pacing)

# Movement: the whole Agility multiplier speeds walking on a log curve,
# bonus = MOVE_BONUS_PER_DECADE x log10(multiplier) permille: +3% at x2, +10% at x10.
MOVE_BONUS_PER_DECADE = 100

# The autopilot's dodge (combat.dodge_percent): walking trains Agility and Perception to about
# level 10 each within a life, so a level is worth one percent: 5% fresh, about 25-30% for a
# seasoned life, never past 40%. (At 2% a level, capped at 60%, it reached the cap in 40 minutes
# and no enemy killed anyone.)
DODGE_BASE_PERCENT = 5
DODGE_PERCENT_PER_LEVEL = 1
DODGE_MAX_PERCENT = 40
