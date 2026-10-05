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
