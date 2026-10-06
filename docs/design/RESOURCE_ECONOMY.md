# Resource economy

Every resource has a source, at least one in-run use and a death-time conversion. Values: `catalog.ITEMS`
(`dust`), rules: `world/economy.py`, numbers: `world/tuning.py`.

## Items
| Item | Source | In-run sink | Dust each | Notes |
|---|---|---|---|---|
| Wild berries | bramble berries | eat (+12) | 1 | |
| Bird egg | gnarled tree (unlock) | eat (+20) | 2 | |
| Boar meat | boar | eat (+35, +11 hp) | 3 | |
| Venison | deer hunt after temporary lead | eat (+28) | 3 | |
| Pale mushroom | mushroom ring (unlock) | eat (+15) | 2 | |
| Snared hare | snare craft (unlock) | eat (+30) | 3 | turns materials into food |
| Stick | branches, tree, camp | staff (3), snare (2) | 1 | |
| Bramble thorn | berries 35%, camp | snare (1) | 2 | |
| Boar hide | boar 60%, camp 20% | wrap (2, unlock) | 4 | |
| Walking staff | learned recipe + craft | weapon slot, +1 punch while equipped | 2 | worth less than its 3 sticks |
| Hide wrap | craft | body slot, boar hits x0.7 while equipped | 6 | worth less than its 2 hides (8) |

## Currencies
| Currency | Source | Sink | Timing | Purpose |
|---|---|---|---|---|
| Dimensional dust | offering stacks at the anchor; first 5 units full value, rest half | unlocks (new actions) | between lives | widen possibility space |
| Ash | rebirth burns every item still carried at 1/2 dust value + 1 per ring reached | spot mastery (wider windows where present; Journal toggle at level 2 and odds influence at level 3; 3/6/9 ash) | automatic at rebirth (works offline) | tune future rolls |
| Blessing | prayer (rare random, or wayside shrines once unlocked) | shrine_path unlock (3) or a next-life boon (2) | between lives | favour from the gods |

## Decisions this creates
- **Use or keep?** Eating and crafting keep the life going (more XP, depth, items); keeping maximises
  dust/ash at death. Gear converts at a loss, so crafting is a real cost.
- **Offer or burn?** Offering gives dust (unlocks, larger); burning gives ash (mastery, half value but
  automatic and boosted by depth). An absent player still progresses through ash.
- **Hoarding is not dominant:** diminishing offering past 5 units and the measured survival advantage of
  crafting (BALANCING.md).

## Failure modes guarded by tests
Refused purchases change nothing; duplicate offers cannot duplicate dust (stack is popped); a boon is one per
life; mastery needs the action unlocked; currencies and unlocks survive saves.
