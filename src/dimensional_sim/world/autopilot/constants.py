"""Expedition tunables, prologue text and save-schema identifiers.

Vitals and combat numbers live here; balance values added by the closed-loop
iteration live in ../tuning.py. All vitals are integer micro-points (POINT).
"""
from ..catalog import ATTRIBUTES, BY_ID
from ..models import DELTAS, DIRECTIONS

DIRECTION_DELTAS = tuple(DELTAS[d] for d in DIRECTIONS)
SKILLS = ("take_control",)
RETURN_COOLDOWN_MS = 300_000
LOG_LIMIT = 16
ANCHOR_COUNTDOWN_MS = 30_000
PAUSE_AFTER_ACTIVITY_MS = 450
PAUSE_BETWEEN_PUNCHES_MS = 220
MAX_EVENTS_PER_ADVANCE = 1_000_000

POINT = 1_000_000                  # one vital point in micro-units
VITAL_MAX = 100 * POINT
HUNGER_DRAIN = 750                 # micro/ms at base Endurance (0.75 points per second)
STARVATION = 1_500                 # health micro/ms at zero hunger (1.5 points/s)
REGEN = 200                        # health micro/ms while hunger is above half
REST_REGEN = 1_000                 # extra health micro/ms while resting at the camp
REGEN_ABOVE = 50 * POINT
EAT_AT = 40 * POINT                # auto-eat only after hunger is genuinely low
FOOD_COOLDOWN_MS = 15_000
BOAR_HIT = 6 * POINT               # per punch exchanged with a living boar, at the anchor
# Danger rises with distance from the anchor: hits x1.5 and +1 boar HP per ring.
DANGER_RING_CAP = 40
RETREAT_BELOW = 35 * POINT         # badly hurt -> go home and rest
FOOD_HEALS_DIVISOR = 3             # eating restores food/3 health points
RESTED_AT = 90 * POINT
REST_MS = 10_000
INVENTORY_SLOTS = 12
STACK_LIMIT = 20
BOAR_ENCOUNTER = "bramble_boar"    # rare spot monsters use this spawn window
MONSTER_STEP_MS = 300             # boars take one step this often while they chase
BOAR_AGGRO_RADIUS = 9             # a live boar this close (in steps) charges the avatar
BOAR_PATH_LIMIT = 2 * BOAR_AGGRO_RADIUS + 2        # chasing boars path-find this far (steps) around obstacles
CAMP_SAFE_RADIUS = 5              # boars stop at the edge of the anchor camp
LEGACY_MONSTER_MAX_MS = 999       # saves before 2026-10-05 used a 1000 ms monster clock
AFTER_LOCATION_REST_WEIGHT = 26   # weight of "just pause" inside the after-location bucket
SELF_ACTIONS = tuple(a.id for a in BY_ID.values() if a.placement == "self")
NEED_ACTIONS = tuple(sorted((a for a in BY_ID.values() if a.trigger == "need"),
                            key=lambda action: (action.need_priority, action.id)))
SCREEN_LOG_LIMIT = 40              # debug only: recent admissions/rejections kept
ROLL_LOG_LIMIT = 12                # debug only: recent chunk rolls kept
LEAD_HISTORY_LIMIT = 100
STAT_KEYS = ("chunks", "food_spots", "enemy_spots", "pity", "rejected", "completed", "eaten",
             "crafted", "fights", "prayers")

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
    "Go explore the world, and don't forget to pray. Maybe the gods will bestow blessings on you.",
    "Mind your hunger, too. This forest feeds only the lucky.",
    "May the path be smooth. Only you will know what destiny awaits.",
)
LOG_TYPES = ("encounter", "eat", "rest", "life", "blessing", "lore", "trade", "ambush",
             "craft", "reflect", "purchase", "rebirth")
TASK_TYPES = ("perform", "pause", "rest", *SELF_ACTIONS, *PROLOGUE_MS)
SCHEMA_VERSION = 10                # unified ash, earned mastery and manual return


def attribute_table():
    """A zeroed XP table with one entry per attribute."""
    return {name: 0 for name in ATTRIBUTES}


def ceil_div(a, b):
    """Integer ceiling division (exact for any sign of a, positive b)."""
    return -(-a // b)
