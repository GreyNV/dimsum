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

The opening system report explains the auto-pilot, encounter experience, hunger,
food cooldown and anchor return. It remains open until the player continues and
the browser pauses the expedition while it is visible. Food slots darken after
an automatic meal and brighten as the authoritative cooldown reaches zero.
The browser session now starts paused until its first UI snapshot, so launching a
server before opening the page cannot spend the first life behind the tutorial.
In a local loaded-save browser check, a 12-second food cooldown stayed frozen at
clock 0 while the report was open; after Continue, both food slots brightened
from CSS brightness 0.48 to about 0.67 and finally 1.0 when ready.

The [dark-forest sprite concept](../art/dark-forest-sprite-concept.png) records a
higher-detail direction for the summoner, anchor, boar and all seven props. It is
an art reference; the playable renderer uses the deterministic layered sprites
described above, so this sheet is not loaded at runtime.
