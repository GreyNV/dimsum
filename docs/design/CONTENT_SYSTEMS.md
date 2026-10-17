# Content systems: how to add content without touching the engine

Since 2026-10-12 every piece of world content is a catalog entry in
`src/dimensional_sim/world/catalog.py`. The engine (auto-pilot, combat, stats pages,
client) reads the catalog and never names an enemy, item, unlock or biome.
If an idea needs a new *kind* of rule, add a field or an effect stat once; after that,
content using it is data only.

## The systems

| System | Catalog | Read by | What it controls |
|---|---|---|---|
| Biomes | `BIOMES` (`BiomeDef`) | `autopilot/combat.py` | danger growth per ring (`danger_num/danger_den`), enemy HP per ring, ring cap |
| Enemies | `ENEMIES` (`EnemyDef`) + a fight `ActionDef` with `enemy=` | `autopilot/combat.py`, `session.py` | bite damage, aggro radius, death cause and its report text, sprite |
| Site conditions | `SITE_CONDITIONS` (`SiteConditionDef`) | `sites.condition_for`, `encounters.chunk_spots`, the auto-pilot | how a landmark is this life: encounter count, an added den or bramble patch, slower work, no bonus drops |
| Effects | `Effect(stat, amount)` on `ItemDef.effects` (gear) | `effects.py` | `punch_damage` (add), `enemy_hit_percent` (multiply), `food_window_bonus` (add), `wood_yield` (add) |
| Abilities | `UnlockDef.ability` (one of `ABILITIES`) | `Expedition.has_ability` | engine capabilities that are not actions, e.g. `return_to_anchor` |
| Unlocks | `UNLOCKS` (`UnlockDef`: `level=(attribute, n)` or `currency`+`cost`) | `lives._grant_level_unlocks`, `economy.offers` | level unlocks open by permanent dimensional level and are never sold; priced ones are abilities and favours |
| Recipes | `ActionDef.recipe`, `RECIPE_KEEP_COST`, `RECIPE_NAMES`, recipe outcomes on actions | `outcomes.py`, `economy.offers` (keep) | a found recipe lasts the life (`life_recipes`); ash keeps it for good (`recipes`) |
| Styles | `CATEGORY_STYLES` (`CategoryStyle`), `ActionDef.color`, `ItemDef.color` | frames -> client | activity verb, body pose, work-mark color, completion seal, item text color |
| Rarity | `RARITY` (`RarityDef`), `RARITY_ORDER`, `ActionDef.rarity`, `ItemDef.rarity` | `drops.py`, `actions.spot_tiers`, `encounters.py` | cascading tier rolls for encounter spots and bonus drops; spot sparkle and reward reveal color |
| Drop tables | `DROP_TABLES` (`DropTable`, `Pick`), `ActionDef.drops` | `drops.roll_table` via `encounters.roll_loot` | one bonus roll per completion on top of fixed `loot`; tables can nest |
| Sites | `SITES` (`SiteDef`), `ActionDef(placement="site", site=...)` | `sites.py`, `open_terrain.py` (generator v5), `encounters.chunk_spots` | rare landmarks generated into the terrain: a clearing with structures and its own encounter bucket |
| Buildings | `BUILDINGS` (`BuildingDef`), build `ActionDef(category="build", builds=...)`, `ActionDef.workplace` | `autopilot/camp.py`, `actions.context_reasons`, `economy.offers` (bind) | structures at the anchor camp: built from carried resources, standing for the life, permanent once bound with ash |
| Art keys | `ActionDef.art` (default: the action id), `EnemyDef.sprite` | client `place_art.js SPOTS`, `combat_art.js ENEMY_SPRITES` | which sprite is drawn |

Effects apply gear in slot order (`EQUIPMENT_SLOTS`). Percent
stats floor after each source, so the order is part of the balance.

## Encounters: things, interactions, outcomes

A placed encounter (spot, lead or site action) separates four things:

- **The thing** (`ActionDef.name`): what the player finds, in everyday words - "Fallen branches", "Deer tracks",
  "Deer". Never a verb. IDs stay stable when a name changes (saves, journals and
  stats key on IDs), so renames need no migration.
- **The interaction** (`ActionDef.interaction`, required for spot/lead/site): what the avatar
  does there, as a gerund - "Picking up sticks". The HUD shows it while working; the
  Journal lists it next to the thing. Self actions (reflect, craft, build) are interactions
  without a thing, so their names stay verbs.
- **Outcomes** (`OutcomeDef`): knowledge, recipes, leads and notes. Outcomes without a
  `group` roll their own `chance`. Outcomes sharing a `group` are alternatives: one roll per
  completion picks at most one of them by chance (they sum to at most 100; the rest is
  "nothing happens"). A `note` only logs its `text` ("The trail went cold."); any outcome
  may carry `text`. Region % scales lead chances as before.
- **Rewards**: fixed `loot` and the bonus `drops` roll (unchanged).

## Chains: a find, a clue, sometimes a payoff

A chain is plain catalog data: a source encounter has a `lead` outcome (a small chance);
the lead (a clue, `placement="lead"`) has grouped alternatives - another lead, danger, or
a `note` that ends it. Nothing is pre-rolled: each step rolls when the previous one is
finished, region % biases the lead chances, and every lead expires (`ttl_ms`).

- **Pointing away.** `ActionDef.lead_spread=1` places the lead in a neighbouring chunk
  (direction fixed by the seed), so following clues moves the player on.
- **Placement rules.** A lead may use `near` (e.g. beside water); with no fitting cell the
  lead never appears.
- **Danger.** A lead may be a fight (`category="fight"`, `enemy`, `hp`): it becomes a live,
  admitted enemy, and wanders off (its target is removed) if it expires unfought. Chain
  danger reuses existing enemies and adds no threat of its own to the frontier math.
- **Knowledge.** A `reveal` outcome uncovers the map around the avatar (`LOOK_RADIUS`).

| Source | Clue (chance) | Then |
|---|---|---|
| Fallen branches | Broken branches (15%, next chunk) | Cut wood 55% (sticks + `wood_stash`) / led nowhere 45% |
| Berry bush | Trampled bushes (15%) | Feeding ground 50% / Angry boar 25% / long gone 25% |
| Mushrooms | Mushroom dust (20%) | Rotten log 60% (mushrooms 70%, `rotten_log`) / blew away 40% |
| Animal tracks | Deer tracks (30%) | Deer 55% / vanished 30% / nothing 15% |
| Old carvings | Odd trail marker (30%) | Looping path 50% (next chunk; reveals the map) / just wrong 50% |
| Old backpacks | Hand-drawn map (35%) | Hidden stash 60% (next chunk; `hidden_stash`) / too faded 40% |

Measured (seeds 1-4, 90 minutes, autopilot): about 8 clue leads per seed; the autopilot
follows most of them, including into neighbouring chunks. Tests: `tests/test_world_chains.py`.

## Sites: unique locations

A site is a landmark generated into the world (generator v5), not a spot. The world is cut
into `SITE_CELL` x `SITE_CELL` chunk blocks; one chunk per block is the candidate and rolls
once against the per-mille `SiteDef.weights` of its region, so sites are rare (about one per
25 chunks today), never crowd each other, and stay at least `min_ring` from the anchor.

- **Terrain.** `sites.layout` gives the clearing (an ellipse, `size`) and its structures
  (`structure`, glyphs in `sites.STRUCTURE_GLYPHS`): `camp` = tents `A`; `tower` = masonry
  `M` and rubble; `lumber` = log stacks `L`, stumps `S` and wood chips; `lodge` = the lodge
  `U`, drying racks `R` and a firepit; `shrine` = an altar `Q`, pillars `P` on flagstones
  `F`; `barrow` = the mound `B` in a ring of standing stones `I`. The clearing has no trees
  or brush and joins the trails along its centre row (only its tips, if sealed off behind a
  structure, grow back). A structure is kept only if no exit is cut off by it. In a clearing
  3 tiles tall only the middle tile of the rows two off the centre is kept, so the main
  piece stands there; the lodge and mound art overhang their one blocking tile.
  Client art: `art.js STRUCTURE_ART`, outlined paint+glyph sprites like spots.
- **Encounters.** Actions with `placement="site"` and `site=<id>` roll only there: each life
  the clearing gets `spots` of them (each at most once) on top of the normal wild spots.
  Their unlocks still apply: a locked site is scenery. They do not earn Journal grades.
- **The sites.**

  | Site | Regions (per mille) | Min ring | Unlock | Encounters |
  |---|---|---|---|---|
  | Abandoned camp | Old Road 350, Deep Woods 150, Bramble 150, Glade 100 | 2 | scavenging | packs, firepit, bedroll (padded jerkin recipe) |
  | Fallen watchtower | Old Road 300, Deep Woods 150 | 3 | road_lore | rubble, stair, armory (studded wrap recipe), warning marks |
  | Logging camp | Deep Woods 200, Old Road 100 | 2 | scavenging | stacked logs (sticks 2-4), tool shed (rope, nails, traveller cache), felled oak (eggs) |
  | Hunter's cabin | Bramble 250, Deep Woods 150 | 3 | snares (perception 3) | drying racks (boar hides, rope), snare line (hare, thorns), trophy wall (`hunter_trophies`) |
  | Ruined shrine (rare) | Glade 250, Deep Woods 100 | 4 | shrine_path / meditation | broken altar (Willpower), offering bowls (`shrine_offerings`), carved pillars (Int) |
  | Burial mound (rare) | Bramble 150, Deep Woods 100, Old Road 50 | 5 | road_lore | grave goods (`barrow_hoard`), ring of stones (heal 10), bone pile (tusk 30%) |

- **Drops.** Site actions use the normal `loot` and `drops`. Camps give cloth scraps and
  rope, watchtowers and tool sheds give iron nails, hunter's cabins give boar hides (the crafting
  station needs two); a bedroll teaches the padded jerkin recipe and the collapsed armory
  the studded wrap (both need `primitive_crafting`).
- **Saves.** World saves pin the site catalog (world schema 6), so editing a `SiteDef`
  never moves an existing world's sites. Worlds on an older generator get sites from
  their next life.

## The riverbank

Rivers are an overlay across every region (`water.py`), so the riverbank is a placement
context, not a region: `near="w"` puts an encounter beside a river or ford cell, and such
spots only enter the bucket of a chunk that has water (`encounters.features`,
`Context.features`). Existing worlds get them too.

- **Spots:** Reeds (eggs, clue: Fish scales), Fishing pool (fish, `ecology="fish"`, 10% a
  lurker surfaces), Shallows (clue: Ripples), Old fishing net (rope, clue: Torn float line),
  River lurker (fight).
- **Chains:** Fish scales -> Busy pool / River lurker / nothing; Ripples -> River lurker's
  burrow / just the current; Torn float line (next chunk) -> Broken fishing platform / sank;
  Old campfire (abandoned camp) -> Muddy bootprints (next chunk) -> Fishing camp (a
  neighbouring chunk with water) / picked clean / lost; Forest spring -> Fresh footprints ->
  Hidden ford (a neighbouring chunk with water; reveals the map; 25% a lurker waits) /
  washed away. A spreading lead with `near="w"` heads for a neighbouring chunk that has
  water when there is one; a water lead with nowhere to stand never appears.
- **River lurker** (`EnemyDef` `step_ms=200`, `leash=3`): faster than the boar (3 steps
  for its 2), lighter bite (4 vs 8), less HP (2 vs 3), short aggro (4); territorial - it
  never chases more than 3 tiles from where it appeared (`CombatMixin._target_home`), so
  walking away up the bank escapes it. Drops fish and `lurker_spoils` (river scales).
- **New items:** River fish (food 25), River scales (treasure).

## Local exhaustion

Wild spots carry an `ActionDef.ecology` (`ECOLOGY`: wood, berries, game, fungi, eggs).
Finishing one adds a harvest to that kind in its region cell (`REGION_CELL` x `REGION_CELL`
chunks) for this life (`Expedition.pressure`, save schema 15). Chunks rolled later in that cell
weigh that kind down by `PRESSURE_STEP[kind]` percent per harvest, never below
`PRESSURE_FLOOR` - so a worked area keeps a trickle (no soft-lock) and fresh ground lies a
cell away. Already-rolled chunks keep their spots. Leads, sites and enemies never deplete;
pressure resets every life (persistent progress is knowledge, mastery and unlocks). The HUD
region line says "Picked over: fewer ... around here this life"; debug shows `pressure_here`.
Measurements: `BALANCING.md`. Tests: `tests/test_world_ecology.py`.

## Campfires

`make_campfire` (category `camp`, 3 sticks, Building XP) sets a campfire down beside the
avatar, anywhere, for the rest of the life (one at a time; a new fire replaces the old).
Resting by it is the same `rest` task as at the anchor camp, so it heals by the same
`REST_REGEN`. It is not a sanctuary: enemies still chase there.

- **Autopilot.** A need action gated by `need_flag="hurt_far"`: badly hurt (below
  `RETREAT_BELOW`), fed or without food, and more than `CAMPFIRE_AWAY` tiles from the anchor
  and from its fire. A hurt avatar then rests at whichever is nearer, fire or anchor.
- **Player.** Skill slot 2, "Make campfire" (ready with 3 sticks during a life). Standing
  still beside the fire, or in the anchor camp, rests while health is below 90.
- **State.** `Expedition.campfire` (seat cell + fire cell, global), save schema 14; the
  snapshot sends the fire cell; `place_art.drawCampfire` draws stones, sticks, a flickering
  flame and a warm glow.
- **Measured** (seeds 1-4, 90 minutes): mean life 15.0 -> 17.9 minutes, starvation deaths
  10 -> 7 of all lives, boar deaths unchanged.

## Site conditions

Each landmark has one condition per life (`SITE_CONDITIONS`, `SiteConditionDef`), picked by
`sites.condition_for(world seed, placement, life)` among the conditions whose `structures`
fit the site, by `weight`. Nothing is saved: the pick is a pure function, so it is the same
after a reload and new each life.

| condition | weight | effect |
|---|---|---|
| Quiet | 50 | as rolled |
| Already searched | 20 | one fewer site encounter (never below one); no bonus drop roll from site encounters |
| Untouched | 10 | one more site encounter (if the site has one left to give) |
| Animal den | 14 | a wild boar fight inside the clearing (not at shrines) |
| Overgrown | 12 | a berry bush inside the clearing; site work takes 140% as long |

- **Fields.** `spots_delta` (-2..2), `adds` (spot action ids placed inside the clearing first),
  `duration_percent` (site actions only), `drops` (False skips the action's `drops` table).
  Validation: `adds` must be spot actions; a `quiet` condition must exist.
- **Where it applies.** `encounters.chunk_spots(..., condition=)` when a chunk with a site is
  screened; `Expedition.site_condition(key)`; `_start_perform` (duration) and `_reward` (drops).
  Chunks rolled before an update keep their saved spot plans.
- **Player.** The HUD title reads "Abandoned camp (animal den) · Deep Woods" and the region
  line gives the condition's text. Quiet sites show nothing extra.
- Tests: `tests/test_world_site_conditions.py`.

## Ruin guards

Ruins are guarded by **restless bones** (`EnemyDef("restless_bones")`, sprite `skeleton`): a slow
(450 ms per step), stubborn skeleton that bites for 6 at ring 0, notices you at 5 steps and never
leaves its ruin (leash 5). Site fight actions (placement `site` with an `enemy`) put them inside
the clearing: **Restless bones** at burial mounds (5 HP + ring scaling, weight 9) and the **Fallen
guard** at fallen watchtowers (4 HP, weight 5). They need no unlock, so a ruin is dangerous long
before it is worth searching (a locked site shows only its guards). Loot: carved bones (treasure, 5 ash),
nails from the guard's mail, and the `bones_spoils` bonus roll (coins, nails, rarely an amber
charm). Death cause "bones". Fight HP per action may now go up to 6.

Client: an upright skeleton (roles g/o/i/j in sprites.js) with flickering cold eyes; hits and
kills rattle. Tests: `tests/test_world_ruins.py`.

The **Ruined shrine** has a gentler guard, the **Pale wisp** (`EnemyDef("pale_wisp")`, sprite
`wisp`, `drains="hunger"`): a cold floating light that does not bite but feeds - each touch takes
hunger, never health (`EnemyDef.drains`: "health" or "hunger"). The frontier counts no health
cost for it; staying near one too long ends in starvation, not a wound. It floats and glows,
its touch shows "-N hunger" and plays a falling chime.

Enemies at a glance: wild boar (anywhere, chases far), river lurker (beside water, fast, light,
short leash), restless bones (burial mounds and watchtowers, slow, tough, guards its stones),
pale wisp (ruined shrines, drains hunger).

## Rare phenomena

A few small impossible things in the first biome, never currency (no loot or drops).

| phenomenon | where | what it does |
|---|---|---|
| Hanging leaf | rare spot, Deep Woods and Still Glade, at most one at a time | `reveal`: shows the map around you |
| Backward ripple | rare spot beside water, at most one at a time | `renew` fish: lifts the area's fish exhaustion this life |
| Double shadow | 12% lead from a mossy rock (meditation unlock) | 60% leads on to the split-shadow tree, 40% fades |
| Split-shadow tree | lead in a neighbouring chunk, beside a tree | `shimmer`: rare and uncommon spots x2.5 in this region cell for the rest of the life |

- **Outcome kinds.** `shimmer` (id = what caused it) adds the source's region cell to
  `Expedition.shimmer`; `spot_context` then sets `Context.rarity_percent` to
  `SHIMMER_RARITY_PERCENT` and `actions.spot_tiers` scales every tier above common (the
  per-tier cap still applies). `renew` (id = an ECOLOGY kind) removes that cell's pressure.
- **State.** `Expedition.shimmer` (region cell ids), save schema 16; reset each life.
  The snapshot's region has `shimmer: true`; the client drifts violet motes and the region
  line says "The air hums here. Rare things are closer this life."; a low hum plays when it
  starts.
- Tests: `tests/test_world_phenomena.py`.

## Weapons and attack profiles

Every weapon item names an `AttackDef` (`ATTACKS`): `reach` (cells along the facing),
`shape` (`punch`, `thrust`, `swing`: the animation family) and fields reserved for ranged
attacks (`needs_sight`, `projectile`, `ammo`; validation rejects them until a ranged system
exists). Bare hands use `DEFAULT_ATTACK` (fists, reach 1). Only weapons carry an attack and
every weapon must.

| weapon | made from | reach | shape | effects |
|---|---|---|---|---|
| walking staff | 5 sticks at the station (primitive crafting) | 2 | thrust | +1 punch |
| spear | staff + 2 iron nails + rope; recipe from the hunter's lodge trophies | 3 | thrust | +2 punch |
| axe | staff + 3 iron nails; recipe from the logging camp's shed | 1 | swing | +3 punch, +1 `wood_yield` |

- **Blows never pass walls.** The runtime walks a straight line from each hitbox cell up to the
  reach; the first live enemy takes the blow (one per swing) and a blocking object (tree, rock,
  structure) or an unloaded chunk stops it. Water does not block a thrust.
- **Autopilot.** The weapon's reach is handed to the runtime each step (`_arm`, never saved).
  With reach above 1 it strikes first at an enemy already in a clear line. The frontier does not
  count reach when it estimates a fight (`fight_damage`). A craft never spends the materials of
  an emergency campfire (`FIRE_KIT`), so the staff waits for 8 sticks in the pack.
- **The axe chops.** `wood_yield` adds sticks once per harvest of a wood-tagged action
  (`ActionDef.tags=("wood",)`), and a `Requirement("gear", "axe")` lets the dead tree (a new
  wood spot) appear only while an axe is carried.
- **Client.** The snapshot sends `weapon: {item, attack, reach, shape}` and `attack_radius`;
  `player_art.drawWeapon` carries the weapon upright, thrusts the staff and spear and swings
  the axe; manual play marks the reach along the four lines.
- **Saves.** No schema change (the craft_staff id is kept; it was retired earlier and is back).
  Tests: `tests/test_world_weapons.py`.

## The anchor camp: buildings and camp crafting

- **Workplaces.** `ActionDef.workplace` is `"camp"` (done at the anchor camp) or a building id
  that must stand there. Every craft has `workplace="crafting_station"`: nothing is crafted
  until a station is built, and then only at the camp. Building the station itself needs only
  the camp (and `primitive_crafting`).
- **Buildings.** A build action (`category="build"`, `builds=<BuildingDef id>`) consumes its
  `cost` and raises the building. It stands until the life ends. At the anchor, each building
  this life raised can be **bound** for `BuildingDef.bind_cost` ash; bound buildings stand in
  every later life. Build actions train the **Building** discipline (the 7th attribute).
- **Storage chest** (`function="storage"`): at the camp, carried materials are stowed in it
  (`CHEST_SLOTS` stacks); crafting and building at the camp draw on it. An unbound chest's
  contents become ash with the pack when the life ends; a bound chest keeps them.
- **Auto-pilot.** It walks home when a craft or building is ready but needs the camp, or when
  it carries `STOW_TRIP_AT` materials and a chest stands there.
- **Carry load.** Every carried unit beyond `CARRY_FREE` adds `CARRY_PERCENT_PER_ITEM`% to the
  walking time, divided by the average Endurance/Strength speed and capped at
  `CARRY_MAX_PERCENT` (`tuning.py`).

**A new building**: a `BuildingDef` (function `crafting` or `storage`, `bind_cost`), a build
`ActionDef` with `builds=` and `cost=`, and a sprite in `place_art.js BUILDING_SPRITES`.

## Rarity: how a roll works

Encounter spots and bonus drops both use a **cascading tier roll** (`drops.cascade`):
rare rolls first at its odds, only a miss tries uncommon, and common catches the rest.
A tier with nothing to give is skipped, not rolled. Then one entry is picked by weight
inside the tier. Each tier draws its own seeded number.

- **Spots.** A tier's odds are `RarityDef.spot_odds` scaled by how much of its spot weight
  is eligible here (regions and Journal choices included) against `spot_full_weight`.
  So one unlocked uncommon is not a quarter of the forest, a region that favors an
  uncommon raises the whole tier, and new *common* content never dilutes rarer spots.
  `BiomeDef.spot_rarity_per_ring` can make depth raise non-common odds (0 = off; ring
  depth is reserved for the item summon for now). Spawn pity and the Journal guarantee
  still force by category/action, outside the cascade.
- **Drops.** `ActionDef.loot` stays as fixed, independent rolls (food and crafting inputs
  the auto-pilot plans around). `ActionDef.drops` adds one roll of a `DropTable`: `odds`
  per non-common tier in basis points, `pools` of `Pick`s per tier (an item stack or a
  nested table). A missing common pool means a miss drops nothing. Ring depth does not
  apply to drops.
- **Showing it.** The Journal page lists rarity odds where the avatar stands and every
  bonus drop's exact chance (`drops.table_chances`). Frames carry `glint` on uncommon and
  rarer spots and `item_glints` for reward reveals.

## Recipes

**A new enemy (e.g. a wolf)**
1. `ENEMIES`: `EnemyDef("grey_wolf", "Grey wolf", hit=6, aggro_radius=14, cause="wolf", cause_text="a grey wolf", sprite="wolf")`.
2. `ACTIONS`: a fight spot `ActionDef("grey_wolf", ..., "fight", "spot", ..., hp=2, enemy="grey_wolf", window=(0, 1), loot=...)`.
3. Weight it in regions (`RegionDef.weights`) if it belongs somewhere specific.
4. Art: add `wolf` to `ENEMY_SPRITES` in `combat_art.js` (until then the boar sprite is used).
5. Bump `encounters.ENCOUNTER_VERSION` and add a save migration (spot rolls change for existing worlds).
The frontier, pursuit, life report, journal death counts, stats pages and HUD pick it up automatically.

**New gear**
1. `ITEMS`: `ItemDef(..., "gear", slot="weapon", effects=(Effect("punch_damage", 2),), color="#rrggbb")`.
2. A craft `ActionDef` with `cost=` and `effect="<item id>"` (and a recipe or unlock to gate it).

**A bonus drop**
1. `ITEMS`: the item with `rarity=` (a `"treasure"` kind needs no in-run use; it is carried home as ash).
2. `DROP_TABLES`: add it to a tier pool, or a new `DropTable(id, {"rare": 200, "uncommon": 1500}, {...})`.
3. Point actions at the table with `drops="<table id>"`. No version bump: spot rolls do not change.

**A rarer encounter**: give the spot `ActionDef` `rarity="uncommon"` or `"rare"`. It joins that
tier's pool and raises the tier's odds by its weight. Bump `ENCOUNTER_VERSION` (spot rolls change).

**A new tier** (e.g. legendary): a `RarityDef` in `RARITY` and its place in `RARITY_ORDER`.

**A new site**
1. `SITES`: `SiteDef(id, name, biome, {region: per_mille}, structure, spots=(2, 4), size=(6, 3))`
   (a new `structure` style needs a layout in `sites.layout`, its glyphs in
   `sites.STRUCTURE_GLYPHS` and an `art.js STRUCTURE_ART` sprite per glyph; tests check both).
2. `ACTIONS`: its encounters with `placement="site", site=<id>` and sprites in `place_art.js SPOTS`.
3. Bump `encounters.ENCOUNTER_VERSION` (spot rolls change).

**A new ash skill**: `UnlockDef(id, name, description, "ash", cost, ability=...)` plus an engine check of the ability (catalog.ABILITIES).

**A new spot action**: an `ActionDef` with a category (style comes from `CATEGORY_STYLES`),
then a sprite under its id (or `art=`) in `place_art.js SPOTS`. Missing art shows a "?"
marker, and `tests/test_world_systems.py` fails until it is drawn.

**A new biome**: a `BiomeDef`, regions with `biome=` set to it, actions listing it in
`biomes=`, and terrain in `assets.py`/`open_terrain.py` (generation is still forest-shaped;
see "Still hard-coded").

**A new effect stat** (engine change, once): add it to `EFFECT_STATS`, then read it with
`effects.total(...)` or `effects.scale(...)` where the number is used.

## Still hard-coded (next candidates)
- Terrain generation styles per biome (`open_terrain.py`, `assets.py`): a second biome needs terrain code.
- One global monster clock (`MONSTER_STEP_MS`): all enemies move at the same speed.
- Activity interaction marks in `player_art.js` (which categories touch the spot, draw rings, etc.) are keyed by category.
- Asset-placed enemies count as `ASSET_ENEMY_ACTION`.
- Crafting *policy* (need priority, never replace worn gear unless the craft consumes it) is generic; recipes and knowledge are content.
- Weapons: the `weapon` slot and `punch_damage` stat stay in the engine, but no weapon item exists until weapon attack animations do (the walking staff was removed).
