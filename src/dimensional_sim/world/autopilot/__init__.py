"""Auto-pilot expedition: the character lives, explores and survives by itself.

The player does not steer. Expedition turns world state into ordinary runtime
InputCommands (move, face, punch) and advances Exploration with them, so collision,
chunk streaming, attack timing and damage stay where they were. Every choice is a
pure function of saved state plus seeds from the world seed, the life number and
a saved decision counter: advancing 10 minutes at once or in 20ms ticks gives the
same expedition, byte for byte. Path fields are memoized pure results.

Loop: settle (death -> anchor interlude, rewards, eating, retreat) -> finish punch /
activity / rest / pause -> pick the nearest reachable spot or living target
(food first when hungry; home to rest when hurt with no food) -> otherwise walk
into an unvisited neighbor chunk -> step along a distance field -> perform or punch.

Lives (design: core-loop.md): attributes have regular XP (this life) and
dimensional XP (persists; 20% of gains). Speed from progression.py shortens
activities and punch pauses; Endurance slows hunger and softens hits. Hunger and
health are integer micro-points; every rate change ends a simulation step, so
vitals are partition-independent. Health 0 -> anchor interlude -> next life:
remaining inventory can become persistent dust before regular XP, inventory,
vitals, actors and encounter rolls reset. Dimensional XP, discovery and skills persist.

Prologue (first life of a new expedition): the screen starts dark while the
avatar wakes from the bandit ambush ("awaken"), then stands up ("stand_up") and
listens to the old man who found them ("listen"). These are ordinary timed tasks,
so the opening is as deterministic and save-safe as the rest of the expedition.

Spawn windows (encounters.py): at the start of every life each limited encounter
rolls how many of it may exist at once around the avatar (resident chunks). When a
chunk first becomes resident its spots and asset-spawned boars are screened: any
beyond the cap never appear this life. Completing or leaving one frees a slot for
new ground. Food is scarce on purpose. Rare boars pursue and interrupt work;
quiet thoughts often follow locations. Visible play can rarely start a timed prayer
after completing a location, granting one persistent blessing only when it ends.

Closed loop (docs/design/GAME_LOOP.md): spots come from the action bucket of
known actions (actions.py) in the chunk's region (regions.py). Food and enemy pity
forces a spot of a starved category after a few empty chunks. Crafting (self
actions) turns materials into gear or food. At death, items can be offered for
dust; whatever is still carried burns to ash at rebirth. Dust buys unlocks (new
actions), ash buys mastery (wider spawn windows), blessing buys the shrine unlock
or a next-life boon (economy.py).

Manual control is the locked skill "take_control"; adapters must ignore player
movement/attack input until it is unlocked.

Package layout (Expedition is assembled from one mixin per concern):
    expedition.py    life state, settle, advance() / advance_manual() loops
    planning.py      goal choice: spots, home, wander
    navigation.py    global cells, resident grid, memoized distance fields
    spawning.py      spot rolls, spawn windows, pity, action contexts
    combat.py        punch damage, danger by ring, frontier, boar pursuit
    outcomes.py      rewards, loot, leads, eating, self actions
    vitals.py        hunger/health integer rates
    lives.py         death, anchor interlude and purchases, rebirth
    saves.py         to_dict/from_dict and schema migrations (6 -> 9)
    presentation.py  read-only HUD/page/debug views
    constants.py     tunables, prologue text, schema version
"""
from .constants import (
    ANCHOR_COUNTDOWN_MS, BOAR_AGGRO_RADIUS, BOAR_HIT, CAMP_SAFE_RADIUS, DANGER_RING_CAP, EAT_AT, ELDER_LINES,
    FOOD_COOLDOWN_MS, HUNGER_DRAIN, INVENTORY_SLOTS, LOG_TYPES, MEMORIES, MONSTER_STEP_MS, POINT, PROLOGUE_MS,
    PROLOGUE_NAMES, REGEN, REST_REGEN, RETREAT_BELOW, SCHEMA_VERSION, SKILLS, STACK_LIMIT, STARVATION,
    VITAL_MAX)
from .expedition import Expedition
from .saves import OLDEST_SUPPORTED_SCHEMA, upgrade

__all__ = [
    "ANCHOR_COUNTDOWN_MS",
    "BOAR_AGGRO_RADIUS",
    "BOAR_HIT",
    "CAMP_SAFE_RADIUS",
    "DANGER_RING_CAP",
    "EAT_AT",
    "ELDER_LINES",
    "FOOD_COOLDOWN_MS",
    "HUNGER_DRAIN",
    "INVENTORY_SLOTS",
    "LOG_TYPES",
    "MEMORIES",
    "MONSTER_STEP_MS",
    "POINT",
    "PROLOGUE_MS",
    "PROLOGUE_NAMES",
    "REGEN",
    "REST_REGEN",
    "RETREAT_BELOW",
    "SCHEMA_VERSION",
    "SKILLS",
    "STACK_LIMIT",
    "STARVATION",
    "VITAL_MAX",
    "Expedition",
    "OLDEST_SUPPORTED_SCHEMA",
    "upgrade",
]
