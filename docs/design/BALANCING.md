# Balancing

## Current first-life playtest adjustment

Base hunger drain is 0.85 points per second, a boar hit starts at 8 health, and
boars pursue from 11 steps. In a seeded 20-minute local trial, seed 482910's
first life ended at 6.76 simulated minutes (previously about 12.22). Across
seeds 1-5, this trial completed 9 lives versus 2 with the prior values. This is
a small sample; longer-run balance remains open.

All numbers live in `world/tuning.py` (systems), `world/catalog.py` (content values) and the vitals block at
`world/autopilot/constants.py`. Measure with:

```
PYTHONPATH=src python -m dimensional_sim.world.cli simulate --seeds 1-8 --minutes 45 --policy spend --lives
```

## Final measurement (2026-10-05, seeds 1-8, 45 simulated minutes each)
Policies: `spend` = auto-pilot crafts; at the anchor offer everything, buy the cheapest unlock, then a boon,
then mastery. `hoard` = same, but never crafts. `idle` = never acts at the anchor (absent player).

| policy | lives | life min mean (range) | first life min | starved / boar | depth | food / boar / pity spots per life | eaten | crafted | unlocks after 45 min | dust, ash, blessing left | dimensional XP |
|---|---|---|---|---|---|---|---|---|---|---|---|
| spend | 15 | 14.12 (4.93-28.33) | 13.3 | 13 / 2 | 5.33 | 29.2 / 20.6 / 23.67 | 27.2 | 1 | 2.5 | [15, 6.2, 1.2] | 2444 |
| hoard | 22 | 9.79 (2.77-26.07) | 7.9 | 18 / 4 | 3.68 | 20.91 / 13.14 / 15.27 | 17.14 | 0 | 2.62 | [14.8, 4.9, 1] | 2061 |
| idle | 23 | 12.85 (4.71-28.91) | 13.3 | 17 / 6 | 5.3 | 22.22 / 20.83 / 24.17 | 24.39 | 1 | 0 | [0, 71.9, 3.5] | 2254 |

## Reading
- **P0 restored:** zero lives without a food spot or a boar; pity supplies roughly a fifth of spots.
- **Pressure is mixed:** about 4 in 5 lives starve inside the frontier, 1 in 5 die to a boar.
- **Spending vs saving is a trade-off, not a rule:** crafting lives last ~45% longer, go ~1.6 rings deeper and
  earn ~19% more dimensional XP; hoarding dies sooner and so reaches the anchor more often, ending slightly
  ahead on unlocks (2.6 vs 2.5). Neither policy dominates.
- **Absent players still progress:** idle converts everything to ash (72 after 45 min) and dimensional XP.
- **Before this iteration** (same tool, old rules): every life starved at ~4 minutes; 25% of lives had no
  natural food source at all (see CURRENT_STATE.md).

## Knobs and their effect (measured while tuning)
| Change | Effect |
|---|---|
| No frontier (always push outward) | 98% of deaths by the first deep boar (ring 8-11), food irrelevant |
| `COMFORT_DAMAGE_PERCENT` 60 | lives 9.8-16 min, starvation-dominated |
| Unlock costs 4-10 dust | all 7 unlocks in ~5 lives (too fast); now 15-70 |
| `PITY_CHUNKS` food 3 -> 5 | food spots per life 33 -> 29, eaten -15% |
| Offer full value up to 5 units | stops 20-stick stacks from paying 20 dust |

## Open balance questions
- Snares and the hide wrap only matter after their unlocks; measure again once players own them.
- Boar damage x1.5 per ring is steep; the frontier currently sits at ring 2-6.
- Life length 10-15 min may be long for mobile sessions; shorten via `HUNGER_DRAIN` or food windows.

## 2026-10-06: regions, discovery chains, gated crafting, equipped gear

Reproduce: `python -m dimensional_sim.world.cli simulate --seeds 1-8 --minutes 60 --lives` (spend policy) and
`python -B tests/world_life_cohorts.py --seeds 1-12` (paired first lives, crafting off, only the weapon slot differs).

### Whole expeditions, seeds 1-8, 60 simulated minutes (completed lives only)

| | lives | life min mean | first life | starved / boar | eaten | boar fights | depth | regions visited / life |
|---|---|---|---|---|---|---|---|---|
| before (pushed `main` + speed work) | 17 | 18.3 | 13.5 | 16 / 1 | 30.0 | 6.4 | 5.4 | (labels only; terrain identical) |
| after (this iteration) | 14 | 18.5 | 17.4 | 8 / 6 | 31.9 | 6.6 | 5.3 | 3.9 of 4 |

After: 13 of 14 lives crafted and equipped a staff; deer chain: 50 follow leads created (2 expired), 29 hunt leads
(1 expired), 27 hunts. Intermediate tuning (55% lead, guaranteed hunt, 1-2 venison) gave 44-minute lives and
~13 hunts per life, which is why the chain was cut back (ACTION_ARCHITECTURE_AUDIT.md, follow-up decisions).

### Unarmed vs staff, paired first lives, seeds 1-12 (45 min cap, crafting off, same world and staff item)

| cohort | life min | boar bite encounters | boar kills | kills per encounter | boar deaths | starvation | depth |
|---|---|---|---|---|---|---|---|
| unarmed | 12.9 | 67 | 52 | 0.78 | 1 | 11 | 3.8 |
| staff equipped | 24.4 | 129 | 106 | 0.82 | 3 | 9 | 5.6 |

Reading: the staff roughly doubles the first life and lets the frontier policy go two rings deeper, where boars
hit harder; it therefore *raises* boar exposure and boar deaths rather than erasing them. Unarmed, the policy
mostly avoids fights it would lose (retreat now costs passing bites). Duel regression guard:
`tests/test_world_combat_balance.py` (staff leaves the avatar below 80 health at ring 2 and below 50 at ring 3,
where an unarmed avatar refuses the fight).

### World diversity (terrain per region, seeds 1-4, chunks -6..6)

| region | v1 blocked / brush / floor marks | v2 blocked / brush / floor marks |
|---|---|---|
| Old Road | 35% / 4% / none | 5% / 8% / debris near the ambush |
| Deep Woods | 35% / 5% / none | 62% / 2% / 18% moss `o` |
| Bramble Thicket | 35% / 4% / none | 51% / 12% / 24% bramble `;` |
| Still Glade | 35% / 5% / none | 0% / 5% / 24% water `~` |

Root cause of "forest, forest, forest": regions existed but only changed action weights and a 28% tint; terrain
generation (v1) never read them. Layouts per seed (`cli regions --seed N`, radius 2, O/D/B/G):
seed 1 `O D O O B | O B G G O | O D O O G | ...`, seed 2 `B G D O D | O D B G O | ...`, seed 3 `O O G O D | B D G B B | ...`.

### Offline catch-up cost
30 simulated minutes in CPython: 5.4 s before, 6.7 s after (denser Deep Woods/Thicket terrain means longer
routes). The hosted build shows the world first and fast-forwards in the background.

### Walking staff removed, Strength scaling retuned (2026-10-14)
The walking staff (+1 punch from the second life on) was removed until weapon animations exist.
Seeds 1-4, 90 simulated minutes each (`simulate.run`):

| variant | lives | starved | mean life |
|---|---|---|---|
| before (staff, +1 punch per 5 Strength levels) | 16 | 6 | 15.6 min |
| staff removed, nothing else | 26 | 25 | 12.5 min |
| staff removed, flat +1 punch from the start | 12 | 4 | 21 min (easier than before) |
| staff removed, +1 punch per 3 Strength levels (**chosen**) | 15 | 7 | 16 min |

The staff was load-bearing: faster boar kills mean more meat for less health and a deeper frontier.
`tuning.STRENGTH_LEVELS_PER_PUNCH = 3` restores the old curve through progression instead of a weapon.
A future weapon should come with a look at this number again.

### Camp crafting, buildings and carry load (2026-10-14)
All crafts now need a crafting station at the anchor camp (12 sticks, 2 hides; primitive crafting).
Seeds 1-4, 90 simulated minutes, `simulate` "spend" policy (binds buildings when it can afford them):

| variant | lives | starved | mean life | buildings built | crafts |
|---|---|---|---|---|---|
| before (craft anywhere) | 15 | 7 | 16 min | - | - |
| station-only crafting + carry load | 21 | 8 | 14 min | 17 | 14 |
| station-only crafting, no carry load | 21 | 9 | 15 min | 14 | 31 |

Lives are a little shorter: early gear (hide wrap) now waits for a station and a trip home. Carry load
costs little survival (mostly fewer crafts, since full packs walk slower). Knobs: the station cost
(catalog `build_station`), `CARRY_FREE` / `CARRY_PERCENT_PER_ITEM` / `CARRY_MAX_PERCENT` (tuning.py).

### Local exhaustion and fewer guaranteed sticks (2026-10-16)
Harvesting a wild spot thins its kind (wood, berries, game, fungi, eggs) in that region cell
for the rest of the life (`autopilot/ecology.py`). Fallen branches give 1 stick + 50% a second
(was 2-3); the logging camp's log pile 2-3 (was 2-4). Seeds 1-6, 90 simulated minutes,
"spend" policy, campfires on (`tools/measure_lives.py`, summarized with `tools/measure_report.py`):

| variant | lives | starved | mean life | sticks/min | station built | station minute (median) |
|---|---|---|---|---|---|---|
| before | 30 | 12 | 16.4 min | 1.87 | 21/30 | 6.5 |
| branches 1-2 (+50%), flat step 12% | 25 | 10 | 17.5 min | 1.58 | 16/25 | 8.9 |
| branches 1 (+50%), flat step 20% | 27 | **18** | 15.9 min | 1.29 | 13/27 | 9.2 |
| branches 1 (+50%), per-kind steps (**chosen**) | 26 | 12 | 18.1 min | 1.25 | 18/26 | 8.5 |

A flat 20% step starved the autopilot (berries thinned too fast). The chosen steps thin food
slowly and wood fast (`PRESSURE_STEP`: wood 20, game 15, fungi 10, eggs 10, berries 8; floor
`PRESSURE_FLOOR` 25%). Stick income is a third lower, starvation unchanged, and the station
moves from minute 6.5 to 8.5 of a life; about two lives in three still build one, so the path
is there but takes a real stretch of a life. Knobs: `PRESSURE_STEP`, `PRESSURE_FLOOR` (tuning.py),
the branches loot (catalog), the station cost.

### Weapons: staff, spear, axe (2026-10-17)
The walking staff is back (5 sticks at the station, reach 2, +1 punch) with the spear and axe after
it (recipes from sites, iron nails). Seeds 1-6 (then 1-12), 90 simulated minutes, `tools/measure_lives.py`:

| variant | seeds | lives | mean life | boar / starved | depth | campfires per life |
|---|---|---|---|---|---|---|
| no staff (Phase 4 rules) | 1-6 | 23 | 20.3 min | 11 / 12 | 4.9 | 3.1 |
| staff; frontier counts reach (one fewer bite per extra cell) | 1-6 | 34 | 14.3 min | 19 / 15 | 5.6 | 1.6 |
| same, frontier ignores reach | 1-6 | 26 | 17.4 min | 17 / 9 | 5.0 | 2.1 |
| no staff | 1-12 | 50 | 18.4 min | 24 / 26 | 5.1 | 2.6 |
| staff; frontier ignores reach; gear crafts keep a campfire's sticks (**chosen**) | 1-12 | 51 | 18.0 min | 28 / 23 | 5.1 | 2.5 |

Reading: counting reach in `fight_damage` sent lives a ring deeper and the staff ate the sticks
an emergency fire needs; both together cut a life by a quarter. With the frontier ignoring reach
and the staff waiting for 8 sticks (`FIRE_KIT`), lives match the no-staff baseline. The staff is
made in about one life in three; the spear and axe did not appear in 90 minutes (their recipes and
nails are rare finds), so they are a later-life goal. The pre-emptive strike (reach > 1 hits an
enemy already in a clear line) made no measurable difference to life length.

### Site conditions and rare phenomena (2026-10-17)
Seeds 1-12, 90 simulated minutes, `tools/measure_lives.py`:

| variant | lives | mean life | boar / starved | depth | station built | site encounters done |
|---|---|---|---|---|---|---|
| Phase 5 | 51 | 18.0 min | 28 / 23 | 5.1 | 26/51 | 98 |
| conditions + phenomena | 49 | 19.6 min | 26 / 23 | 5.2 | 30/49 | 98 |

No measurable change to survival (inside the run-to-run noise). Phenomena seen in 49 lives:
hanging leaf 20, backward ripple 5, double shadow 8, split-shadow tree 2 - roughly one strange
thing every 35 minutes, and the shimmer about once in 25 lives. Knobs: phenomenon weights and
windows (catalog), the double shadow's 12% and 60%, `SHIMMER_RARITY_PERCENT`, condition weights.

### Ruin guards and the final sweep (2026-10-17)
Restless bones at burial mounds and fallen watchtowers. Seeds 1-12, 90 simulated minutes:

| variant | lives | mean life | deaths: boar / starved / lurker / bones | site guards fought |
|---|---|---|---|---|
| Phase 6 | 49 | 19.6 min | 26 / 23 / 0 / 0 | - |
| with ruin guards | 53 | 17.6 min | 23 / 28 / 1 / 1 | 11 (4 mound, 7 tower) |

Ruins are deep (ring 3 and 5+) and rare, so guards add danger where the autopilot already pushes
its luck; the life-length difference is inside the run-to-run spread seen across phases
(16.7-20.3 min). Knobs: `restless_bones` hit/aggro/leash/step, the guards' HP and weights.
