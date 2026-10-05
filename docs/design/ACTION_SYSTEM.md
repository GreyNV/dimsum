# Action system and action bucket

**What it does:** one registry (`world/catalog.py: ACTIONS`) describes every action; `world/actions.py`
derives, for a context, which actions are known, eligible and how likely they are.
**Why:** unlocks must add possibilities, generation must be data-driven, and designers must be able to
see why something did or did not appear.
**Owner:** catalog.py (data), actions.py (rules). Generators and the auto-pilot only *read* buckets.

## Pipeline
```
All actions -> known (unlock None or bought) -> eligible (Context) -> weighted bucket -> selection
```
- Spot actions (`placement="spot"`): `encounters.chunk_spots` rolls 0-3 spots per chunk from the spot bucket
  of that chunk's biome and region (weight = base x region percent // 100). Then `Expedition._screen`
  applies at-once caps (windows) and pity.
- Self actions (`placement="self"`): `trigger="need"` (crafts, chosen by the need policy in priority
  wrap > staff > snare) or `trigger="after_location"` (think, contemplate, rare prayer; plus a
  `AFTER_LOCATION_REST_WEIGHT` chance of a plain pause).

## Schema (ActionDef)
`id, name, category, placement, attribute, xp, duration_ms, weight, description, log, unlock, biomes,
regions, near, rarity, window, hp, loot, heal, blessing, cost, effect, trigger, visible_only, tags`.
Validation runs at import; `validate_catalog()` checks cross references (unknown unlocks, regions, items
without a source, unlocks that open nothing).

## Eligibility rules (`actions.reasons_against`)
locked (needs unlock X) | wrong placement | biome | region list | region weight 0 | wrong trigger |
missing ingredients | gear already carried | live play only | once per life (`tags`).

## Current registry
| Action | Category | Placement | Unlock | Window | Notes |
|---|---|---|---|---|---|
| bramble_berries | forage | spot | - | 1-2 | food 1-2 berries, 35% thorn |
| fallen_branches | gather | spot | - | - | 2-3 sticks |
| animal_tracks | observe | spot | - | - | Perception XP |
| forest_spring | drink | spot | - | 1-2 | +10 health |
| bramble_boar | fight | spot | - | 1-2 | meat, 60% hide; pursues |
| gnarled_tree | climb | spot (near tree) | climbing | 1 | 60% egg |
| abandoned_camp | scavenge | spot | scavenging | - | sticks, thorns, 20% hide |
| mushroom_ring | forage | spot | mushroom_lore | 1 | 1-2 mushrooms |
| mossy_stone | meditate | spot (near rock) | meditation | - | Willpower |
| moonlit_pool | drink | spot | meditation | 0-1 | +12 health |
| old_carvings / fallen_watchtower | study | spot | road_lore | - | Intelligence |
| wayside_shrine | pray | spot, old road only | shrine_path (3 blessing) | 1 | +1 blessing |
| think / contemplate | reflect | self, after location | - | - | no reward |
| pray | pray | self, after location, live play, once/life | - | - | +1 blessing |
| craft_staff | craft | self, need | - | - | 3 sticks -> staff (+1 punch) |
| craft_snare | craft | self, need, hungry, no food | snares | - | 2 sticks + thorn -> 75% hare |
| craft_wrap | craft | self, need | hide_working | - | 2 hides -> wrap (-30% boar hits) |

## Debugging "why did / didn't it appear?"
- Chunk: `python -m dimensional_sim.world.cli inspect --seed S --x X --y Y [--unlock id]` prints the region,
  rolled spots, the bucket with shares, and `not_eligible` with reasons.
- Live: open the browser with `?debug` or press the backquote key. The overlay shows the current spot and
  self buckets with weights, windows (active/limit/spawned), drought vs pity thresholds, the last screening
  decisions (`admitted`, `rejected: window full (1/1 at once)`, `pity food after 5 empty chunks`) and every
  ineligible action with its reasons.
- Code: `actions.explain(action_id, Context(...))`, `Expedition.debug_info()`.

## How to extend
Add an `ActionDef` (and an `UnlockDef` if it should start locked). Spot actions need a sprite in
`browser/actors.js: SPOTS` (or they render as nothing but still work). Bump `ENCOUNTER_VERSION` when existing
worlds' rolls change and add a save upgrade. Never put content-specific conditions in generators.

## Invariants
Pure functions; integer weights; buckets are in catalog order; selection seeds belong to callers;
a locked action never spawns; a refused purchase never changes state.

## Tests
`tests/test_world_closed_loop.py` (ActionBucketTests, CatalogTests), `tests/test_world_autopilot.py`.
