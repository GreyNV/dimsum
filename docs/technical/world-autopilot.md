> 2026-10-05: the closed-loop iteration (action registry, regions, pity, crafting, dust/ash/blessing
> sinks, frontier) is documented in docs/design/. Sections below describe earlier states.

# World auto-pilot and biome encounters

## Direction (2026-10-04)
The character explores by itself, as the idle design intends: the player does not
pick actions. Each biome has a weighted pool of encounters that may spawn as spots
on the map. The first pool (dark_forest) needs no equipment: everything is done
bare-handed, and the attack is a punch. Manual WASD control is the locked skill
`take_control`, to be unlocked later in the game (as a skill or avatar).

## Modules
- world/encounters.py: EncounterDef catalog (validated), POOLS by biome,
  chunk_spots(chunk). Version tag ENCOUNTER_VERSION = encounters-v1.
- world/autopilot.py: Expedition(game). Drives Exploration with ordinary
  InputCommands; owns completed spots, attribute XP, log, skills, task and goal.
- browser_server.py: BrowserSession(game, expedition). Without an expedition the
  session is the original manual adapter (kept for tests and terminal parity).

## Dark forest pool (encounters-v1)
Superseded values: see "Lives, survival and items (encounters-v2)" below.

| id | kind | attribute | XP | time | weight | placement |
|---|---|---|---|---|---|---|
| bramble_berries | forage | perception | 4 | 2.4s | 30 | any |
| fallen_branches | gather | strength | 3 | 2.2s | 24 | any |
| animal_tracks | observe | perception | 5 | 3.0s | 20 | any |
| gnarled_tree | climb | agility | 6 | 3.2s | 12 | next to a tree |
| forest_spring | drink | endurance | 4 | 2.0s | 12 | any |
| mossy_stone | meditate | willpower | 6 | 4.0s | 8 | next to a rock |
| old_carvings (uncommon) | study | intelligence | 8 | 3.6s | 5 | any |
| bramble_boar | fight (3 HP) | strength | 10 | punches | 14 | any |
Values are provisional balance knobs, like the idle simulator's.

## Spawning rules
Per chunk: seed = derive_seed(chunk.seed, ENCOUNTER_VERSION). Spot count is
(0,1,2,2,3,3)[seed % 6] (an empty chunk is part of the chance). Each slot rolls the
weighted pool, then a cell among reachable walkable non-border, non-spawn cells
with a walkable neighbor, at least 4 cells (Manhattan) from other spots; climb and
meditate require an adjacent tree/rock glyph, else the slot stays empty. Spot IDs
are enc:<dimension>:<cx>:<cy>:<slot>. Fight spots become runtime Targets
(id = spot ID) once their chunk is initialized; asset-spawned enemies count as
bramble boars. Same world -> same spots regardless of visit order or reload.
Changing a pool or placement for existing worlds needs a new version tag.

## Auto-pilot loop
settle (materialize fight spots, reward defeated targets once) -> finish punch /
activity / pause -> choose the nearest reachable uncompleted spot or living target
among resident chunks (ties by ID) -> otherwise walk deep into an unvisited
neighbor chunk, else a seeded random neighbor (derive_seed(world seed,
"autopilot-v1", decisions)) -> step along a BFS distance field that honors
collision, chunk exits and living targets -> on arrival face it and perform for
duration_ms, or punch (rising edge) with 220ms between punches -> award XP + log.
A newly streamed reachable spot pre-empts wandering. Punches are sliced at damage
window starts so kills are logged at the same clock however time is divided.
Determinism: advance(60000) == 3000 x advance(20) == random slices == save at any
point + reload + continue (tested byte-for-byte on the save JSON).

## Control and transport
Locked: /api/input move/attack are ignored (pause/zoom still work); the server
advances the expedition each 20ms tick, so it explores even with no tab open.
Unlocked (`--unlock-control`, development only for now): input takes over,
interrupts the plan and the auto-pilot resumes 2.5s after the last command.
Frame additions: spots[{id,encounter,name,kind,x,y}] (global cells, uncompleted
non-fight spots in resident chunks), target_kinds{target id: encounter id},
expedition{mode: explore|travel|encounter|fight, activity{encounter,name,kind,
x,y,progress 0..1000}|null, goal{x,y,kind}|null, xp{6 attributes}, log[last 6
{seq,clock_ms,encounter,text,attribute,xp}], skills[], control: auto|manual}.

## Saves
Browser --save writes {schema_version:1, encounters, exploration, completed, xp,
log (last 12), sequence, decisions, skills, task, goal}. --load accepts that or
a plain exploration save (which starts a fresh expedition). Exploration schema 1
is unchanged; auto-pilot targets use enc: IDs that it already accepts.

## Lives, survival and items (encounters-v2, 2026-10-04)
Plan and decisions: world-lives-plan.md. Code: progression.py, autopilot.py.
- Two tracks per attribute, reusing core.GameConfig: regular XP (100 x 1.15^n,
  resets each life) and dimensional XP (100 x 1.35^n, persists, 20% of gains).
  speed = 1 + 0.10*soft(regular) + 0.01*soft(dimensional), softcap 10/0.08,
  rounded once to per-mille. Activity time = base / speed(attribute); punch
  pause / speed(Strength); hunger drain and boar hits / speed(Endurance);
  punch damage = 1 + softcapped Strength levels (regular + dimensional) // 5.
- XP x10 vs v1: berries 40, branches 30, tracks 50, tree 60, spring 40 (+10
  health), stone 60, carvings 80, boar 100.
- Items (current life; 12 slots, stacks of 20): wild berries (food 12), bird egg
  (20), boar meat (35), stick, bramble thorn, boar hide. Loot is rolled per life
  and spot: berries 2-4 (+thorn 30%), branches 2-3 sticks, tree egg 50% / stick
  40%, boar meat 1-2 + hide 60%. Food is auto-eaten at hunger <= 60: the largest
  that fits, else the smallest; +food/3 health; 15s cooldown.
- Vitals in integer micro-points: hunger -0.5/s; at 0 hunger health -1/s; above
  50 hunger +0.2/s; resting at the camp +1/s. Every rate change ends a step.
- Danger rings = Chebyshev chunk distance from the anchor. Boar HP 3 + ring;
  boar hit after each exchanged punch 6 x 1.5^ring / Endurance speed. The
  explorer pushes into the deepest unvisited neighbor chunk; it skips boars
  below 50 health and goes home below 35 (rests in 10s blocks until 90).
- Death (health 0): life report (XP per attribute with dimensional gains,
  encounters, deepest ring, survival time, cause), new Exploration at the anchor,
  life + 1, encounter spots re-rolled. Persist: dimensional XP, discovery map,
  skills, best depth, log. Reset: regular XP, inventory, vitals, actors.
- Anchor camp = player spawn of chunk (0,0): drawn anchor stone, bedroll, fire.
  A new world shows the opening system report from overview.md.
- Frame expedition adds attributes{level,into,next,dim_level,dim_into,dim_next,
  speed}, vitals{hunger,health,max 10000,food_cooldown_ms,food_cooldown_total_ms},
  inventory[{id,name,kind,glyph,food,count}], inventory_slots, life, total_ms,
  depth, best_depth, punch_damage, report{seq,life,clock_ms,title,lines},
  anchor{x,y}. Log entries: {seq,clock_ms,life,type: encounter|eat|rest|life,
  encounter,text,attribute,xp,dim_xp,items[[id,count]]}.
- Saves: expedition schema 2 (encounters-v2). Schema 1 migrates: world kept,
  v1 fight targets removed, v1 XP x10 becomes regular XP.
- Soak (seed 482910, 120 simulated min): 17 lives of 1-23 min, best ring 5 -> 13.
  Byte-identical for bulk, 20ms ticks, random slices and save/reload across deaths.

## Not yet
Not wired into the idle-life simulator (core.py), journal or shards. No enemy AI
(boars only strike back when punched), crafting/binding at the camp, equipment,
more biomes, or a real unlock path for take_control. All numbers are untuned.

## Browser presentation review (2026-10-04)
The current dark-forest pool contains seven non-combat spots and the bramble boar.
Each non-combat entry has a distinct larger spot silhouette; the boar has breathing
and horn highlights. The anchor has a rune ring, taller stone, soul tether,
floating fragments and fire sparks.
The hosted open-terrain recipe was sampled at seed 482910 across 400 chunks:
756 spots included all eight encounters (berries 179, branches 154, tracks 127,
tree 78, spring 61, stone 53, carvings 30, boar 74). Both tree and rock placement
rules had reachable candidates; carvings remain the rarest encounter. This is a
content review sample, not a new pool version or a change to existing saves.
These are client-only drawings from snapshot fields. Finished spots briefly show
a dissolving seal, and active encounters have a glint on their progress bar.

The player drawing now exposes independent body, chest, helmet, pants and boots
layers. Future equipment art can overlay a slot in standing and compact activity
poses without putting player graphics in locations or changing combat geometry.
Face and hands remain in the base body under those overlays. No equipment item is yet represented
in the forest save or granted by an encounter.

The earlier opening system report has been replaced by the prologue below. Life
reports still pause the expedition while they are visible. Food slots darken
after an automatic meal and brighten as the authoritative cooldown reaches zero.
The browser session starts paused until its first UI snapshot, so launching a
server before opening the page cannot spend the first life before the scene begins.
In a local loaded-save browser check of the previous opening, a 12-second food
cooldown stayed frozen at clock 0 while the report was open; after Continue, both
food slots brightened from CSS brightness 0.48 to about 0.67 and finally 1.0.

The [dark-forest sprite concept](../art/dark-forest-sprite-concept.png) records a
higher-detail direction for the summoner, anchor, boar and all seven props. It is
an art reference; the playable renderer uses the deterministic layered sprites
described above, so this sheet is not loaded at runtime.

## Prologue, prayer and spawn windows (encounters-v3, 2026-10-04)
The pop-up opening report is gone; the first life opens with a playable scene.
- Prologue (new expeditions only; deterministic timed tasks, saved like any task):
  `awaken` 10 s - the screen is black except the task line, health and hunger;
  memory fragments of the bandit ambush surface one by one, then the eyes open.
  `stand_up` 3.5 s - the world appears; the avatar rises beside the anchor.
  `listen` 25 s - the old man (two cells beside the anchor) speaks five lines
  (autopilot.ELDER_LINES) in a dialogue strip; the avatar faces him. Then he walks
  off, a "The road" log entry is written and the rest of the HUD fades in.
  Snapshot: expedition.prologue = {stage, progress 0..1000, elder{x,y}, lines}
  or null. The client draws the dark screen, eyelids, old man and typing text.
  New worlds start paused (local server and hosted worker) so the scene begins
  when the page is ready.
- Prayer: `wayside_shrine` (kind pray, Willpower 50 XP, 3.6 s, uncommon). Each
  prayer adds 1 blessing power (persists across lives, shown in the vitals bar and
  life report). 40% of prayers get an immediate boon: +15 health and +15 hunger
  ("The gods answer"). What blessing power buys is still open.
- Spawn windows: limited encounters roll, at the start of each life, how many may
  exist at once around the avatar (the 3x3 resident chunks):
  berries 0-2, gnarled tree 0-1, spring 1-2, shrine 1, boar 1-2 (spots and the
  one asset-spawned boar per chunk share the boar window). Non-food encounters
  are unlimited. When a chunk first becomes resident its spots and asset boars are
  screened in order; any beyond the cap never appear this life (a dropped asset
  boar is set to 0 HP and never rewards). Finishing or leaving one frees a slot
  for new ground. encounters.spawn_window(entry, mastery) is the hook for future
  action mastery (+1 high per level, +1 low every second level; nothing grants
  mastery yet). The life report lists "Forest bounty this life".
- Balance sample (6 seeds x 30 min, auto-pilot): mean life 6.0 min with no caps,
  5.1 min with these caps; every death was still a boar fight, never starvation.
  Tighter food (all caps at 1) gave 4.0 min. Food is now scarcer; boars remain
  the main killer, so starvation pressure needs further tuning.
- Saves: expedition schema 3 adds blessing, budget, spawned, admitted
  ([id, encounter]), screened_chunks, screened_targets and log.blessing.
  Schema 2 (encounters-v2) saves upgrade: progress, vitals and inventory stay;
  spot plans, enc: targets and spot completions drop; no prologue; this life's
  windows are rolled on load.
- The bandit-ambush memories were written fresh for this build; the original
  ambush text from the earlier game was not available here.

## Ambush site and the space between lives (encounters-v4, 2026-10-05)
The origin of the dark forest is visibly the caravan ambush site: two ruined
wagons, torn canopy, broken wheels, crates, planks and arrows surround the anchor.
This art is drawn below actors without changing collision or exit geometry. Four
more distinct encounter locations can appear across the forest: an abandoned camp,
moonlit pool, fallen watchtower and mushroom ring. They have their own art, logs,
activities and balanced rewards. Encounter version v4 rerolls current-life spots
when loading a v3 save; earned XP, inventory, blessing and world discovery remain.

Death now enters an anchor space before the next life. The map and encounters are
hidden; only the anchor, avatar, and trade panel appear. A 30-second simulation
countdown starts immediately. With no action, the next life begins automatically.
Offering a whole inventory stack stops the countdown; the player may offer more
stacks and presses Begin next life when ready. All unoffered inventory disappears
at the next life. Dust rates per item: berries/stick 1, egg/thorn 2, meat 3,
hide 4. Dust and dimensional XP persist; regular XP and vitals reset. Each stack
can be offered once, so a retried request cannot award duplicate dust. The
countdown and choice are saved and use the same deterministic advance path in
local and hosted play. The measurable target is identical saves for bulk/split
time across death and countdown; focused tests cover this, trading, retry and
schema-3 migration. Dust currently accumulates for future anchor progression;
there is no dust purchase action yet.

## Scarce forest, active prayer and pursuit (encounters-v5)
The character reference guides a 16x20 pixel browser sprite with four-direction
views and timed idle/walk frames. The origin remains the caravan ambush site.

The first biome now rolls 0-2 location spots per chunk. Berries appear at weight
8 (previously 30), give one berry and have a 0-1 resident window. Tree eggs drop
15% of the time; boars give one meat. Eating waits until hunger <=40, hunger drains
0.75 points/s, and starvation costs 1.5 health/s. At seed 482910, the first life
ends at about 287 simulated seconds in the current tuning sample.

The shrine location is removed. After a completed location, a seed and spot ID
roll a 4% prayer opportunity during visible play, at most once per life. Prayer is
a visible 12-second kneeling task; only completion grants one persistent blessing
and a prayer log entry. Offline catch-up passes `allow_prayer=False`; hidden hosted
tabs also pass false. Otherwise a 70% seeded roll starts a 3-second thought or
5-second contemplation, both without XP, items or blessing.

Generated asset boars are screened out. Rare bramble-boar spot rolls pursue one
walkable cell per second within six cells of the avatar, only through initialized
chunks. Contact interrupts the current task and starts an auto-pilot fight. These
targets are `enc:` actors, so moved positions save and reload under Exploration's
custom-target rules. Encounter version v5 and expedition schema 5 migrate v4
saves by retaining progression/inventory and rerolling current-life spots; the
old shrine log keeps its earned blessing with no new map shrine.
