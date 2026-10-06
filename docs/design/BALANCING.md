# Balancing

All numbers live in `world/tuning.py` (systems), `world/catalog.py` (content values) and the vitals block at
the top of `world/autopilot.py`. Measure with:

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
