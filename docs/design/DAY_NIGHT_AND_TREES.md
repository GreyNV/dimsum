# Day and night, wolves, tree kinds (schema 19, 2026-10-17)

Decisions (Andrew, 2026-10-17): a 12-minute day (8 day / 4 night); at night new night-only
creatures come to whoever explores; several tree kinds,
mixed by region, looks only (same collision and gameplay).

Revised 2026-10-20: wolves can enter the camp and campfire light and attack a resting avatar.

## Clock
- World clock = simulation time + `DAY_START_MS` (a new game starts a minute after dawn), so it
  runs through lives and the anchor and replays exactly. Numbers: `tuning.py` (DAY_MS, NIGHT_MS,
  TWILIGHT_MS, DAY_START_MS). Rules: `autopilot/night.py` (`time_of_day`, `is_night`,
  `darkness_permille`, `NightMixin.clock_view`).
- The frame carries `expedition.clock` {day, time_ms, day_ms, night_at_ms, night, phase
  (day/dusk/night/dawn), darkness 0-1000, until_ms}.

## Night creatures
- `EnemyDef("wolf")`: hit 9, aggro 10, quick (step 250 ms), `fears_fire=False` (pursues into
  the camp and campfire light). Bite and HP grow linearly with the deepest ring reached this life.
  Fight action `night_wolf` (placement
  "lead", tag "night", 60 Strength XP, wolf fang 45%).
- Night watch (`_night_watch`, from `_settle`): once per world-clock tick (`NIGHT_SPAWN_EVERY_MS`,
  30 s; `night_tick` saved), at night, outside the prologue and anchor interactions, below
  `NIGHT_FOES_BY_RING` (1 / 2 from maximum life ring 2 / 3 from ring 5), with a 60% first-day
  chance per tick that grows by 5 points per day to 90%: a wolf appears 7-13 steps away (`encounters.night_spot`)
  as a fight lead that expires at dawn ("slinks back into the trees"). Steps end at clock ticks
  (`night_step_cap`), so any slicing of time gives the same wolves.
- Logs: "Night falls..." (type `night`, nightfall chime) and "A wolf howls close by." (howl).

## Tree kinds
- `catalog.TREE_KINDS` (oak, pine, birch, dead tree, old mossy tree) and `REGION_TREES` weights per
  region: Old Road oak/birch/dead, Deep Woods pine/old/oak, Bramble Thicket oak/dead/birch, Still
  Glade birch/old/oak. Kept out of `RegionDef` on purpose: region definitions are pinned into world
  seeds, and trees are presentation only.
- The frame sends `chunk.trees`: one letter per tile (o p b d m, "." when no tree), picked from the
  tile's region mix and the chunk seed (`session._tree_kinds`). Client: `nature_art.js TREE_ART`
  (pine tiers, pale banded birch, bare forking dead limbs, a wide mossy crown with hanging strands).

## Client
Night darkness with holes of light (avatar, larger while possessed; warm flickering light at the
anchor camp and a campfire) in `scene_fx.js drawNight`; the HUD clock "☀ Day 2 · night in 3:10" /
"☾ Night · dawn in 1:12"; wolf sprite (`combat_art.js WOLF`).

The colour of the day (`scene_fx.js dayGrade`, `drawDayGrade`, cosmetic): smoothstepped keyframes
over the day - a rose dawn that warms to gold and pales into neutral daylight over about three
minutes (with a little morning haze lifting), a golden afternoon, a red sunset, a violet dusk, a cool
blue night and a grey-violet hour before dawn. A soft-light tint, a slight dim and a low sun glow
from the east (morning) or west (evening).

Wind (`wind.js`, cosmetic): one field of slow sway, gust fronts rolling west to east and a quick
flutter. Trees and undergrowth (bush, sapling, ferns) are drawn sheared about their base, so roots
stay put and tops lean downwind; stones, mushrooms, rocks and structures stand still. The canopy
repaint over actors uses the same field and frame clock, so the two passes never disagree. A few
leaves blow across the view. All of it is off under reduced motion.

## Save migration 18 -> 19
Adds `night_tick` = the current clock tick (no retroactive wolves).

Tests: tests/test_world_night.py, JS tree/night tests.
