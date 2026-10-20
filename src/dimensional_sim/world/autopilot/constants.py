"""Expedition tunables, prologue text and save-schema identifiers.

Vitals and combat numbers live here; balance values added by the closed-loop
iteration live in ../tuning.py. All vitals are integer micro-points (POINT).
"""
from ..catalog import ATTRIBUTES, BY_ID
from ..models import DELTAS, DIRECTIONS

DIRECTION_DELTAS = tuple(DELTAS[d] for d in DIRECTIONS)
CONTACT_COOLDOWN_MS = 300_000     # contacting the anchor mid-life (the world waits while it is open)
# Possession: the god takes the avatar's hands for a while (manual control).
POSSESS_MS = 30_000
POSSESS_COOLDOWN_MS = 60_000      # counted from the moment possession ends
POSSESS_SPEED_PERCENT = 120       # moving and every action are this much faster while possessed
LOG_LIMIT = 16
ANCHOR_COUNTDOWN_MS = 30_000
PAUSE_AFTER_ACTIVITY_MS = 450
PAUSE_BETWEEN_PUNCHES_MS = 220
MAX_EVENTS_PER_ADVANCE = 1_000_000

POINT = 1_000_000                  # one vital point in micro-units
VITAL_MAX = 100 * POINT
HUNGER_DRAIN = 850                 # micro/ms at base Endurance (0.85 points per second)
STARVATION = 1_500                 # health micro/ms at zero hunger (1.5 points/s)
REGEN = 50                         # slow passive healing; food and resting carry recovery
REST_REGEN = 1_000                 # extra health micro/ms while resting at the camp
REGEN_ABOVE = 50 * POINT
EAT_AT = 40 * POINT                # no food carried: seek food once hunger falls this low
FOOD_COOLDOWN_MS = 15_000          # legacy save field; eating no longer waits for a cooldown
RETREAT_BELOW = 35 * POINT         # badly hurt -> go home and rest
FOOD_HEALS_DIVISOR = 3             # eating restores food/3 health points
RESTED_AT = 90 * POINT
REST_MS = 10_000
INVENTORY_SLOTS = 12
STACK_LIMIT = 20
# Enemy numbers (hit, aggro radius) live on catalog.EnemyDef; danger growth on catalog.BiomeDef.
LOOK_RADIUS = 18                  # tiles a 'reveal' outcome uncovers around the avatar
MONSTER_STEP_MS = 300             # chasing enemies take one step this often
CAMP_SAFE_RADIUS = 5              # enemies stop at the edge of the anchor camp
LEGACY_MONSTER_MAX_MS = 999       # saves before 2026-10-05 used a 1000 ms monster clock
AFTER_LOCATION_REST_WEIGHT = 26   # weight of "just pause" inside the after-location bucket
SELF_ACTIONS = tuple(a.id for a in BY_ID.values() if a.placement == "self")
NEED_ACTIONS = tuple(sorted((a for a in BY_ID.values() if a.trigger == "need"),
                            key=lambda action: (action.need_priority, action.id)))
# An emergency campfire's materials: need crafts (not builds) never spend into them.
FIRE_KIT = dict(next(a.cost for a in BY_ID.values() if a.places == "campfire"))
SCREEN_LOG_LIMIT = 40              # debug only: recent admissions/rejections kept
ROLL_LOG_LIMIT = 12                # debug only: recent chunk rolls kept
LEAD_HISTORY_LIMIT = 100
STAT_KEYS = ("chunks", "food_spots", "enemy_spots", "pity", "rejected", "completed", "eaten",
             "crafted", "fights", "prayers", "built")

PROLOGUE_MS = {"awaken": 10_000, "stand_up": 3_500, "listen": 25_000}
PROLOGUE_NEXT = {"awaken": "stand_up", "stand_up": "listen"}
PROLOGUE_NAMES = {"awaken": "Wake up", "stand_up": "Stand up", "listen": "Listen to the old man"}
# Memory fragments shown on the dark screen while the avatar wakes up.
MEMORIES = (
    "The forest road. Wagon wheels, laughter, a song left half-finished.",
    "Arrows from the trees. Bandits. Steel and shouting, someone running.",
    "A blade, cold and very close. The ground rushing up to meet you.",
    "Silence. Then, from very far away, something old answers.",
)
# The old man who finds the newborn avatar beside the road.
ELDER_LINES = (
    "Why... I don't believe it. I witnessed the birth of an avatar - a dimensional avatar.",
    "The bandits left you for dead. The gods saved you, but now you have to worship them.",
    "Something old looks out through your eyes. When it takes your hands, let it - you will be quicker for it.",
    "Mind your hunger, too. This forest feeds only the lucky.",
    "May the path be smooth. Only you will know what destiny awaits.",
)
LOG_TYPES = ("encounter", "eat", "rest", "life", "possess", "night", "lore", "trade", "ambush",
             "craft", "reflect", "purchase", "rebirth", "build", "stow")
TASK_TYPES = ("perform", "pause", "rest", *SELF_ACTIONS, *PROLOGUE_MS)
SCHEMA_VERSION = 20                # 20: hunting enemies; 19: night watch tick; 18: no blessing/boons/skills, contact + possession, campfire bought, opening at the anchor; 17: recipes found this life, level unlocks; 16: shimmer cells; 15: ecological pressure (14: campfire; 13: camp buildings, chest; 12: sites)


def attribute_table():
    """A zeroed XP table with one entry per attribute."""
    return {name: 0 for name in ATTRIBUTES}


def ceil_div(a, b):
    """Integer ceiling division (exact for any sign of a, positive b)."""
    return -(-a // b)
