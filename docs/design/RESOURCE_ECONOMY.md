# Resource economy

Every resource has a source, at least one in-run use and a death-time conversion. Values: `catalog.ITEMS`
(`ash_value`), rules: `world/economy.py`, numbers: `world/tuning.py`.

## Items
| Item | Source | In-run sink | Ash each before diminishing | Notes |
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
| Dimensional ash | all carried items convert at return; first 5 lifetime copies of each item full value, later copies half value; +1 per ring reached | unlocks, starting with manual return (10) | automatic at return (works offline) | widen possibility space |
| Blessing | prayer (rare random, or wayside shrines once unlocked) | shrine_path unlock (3) or a next-life boon (2) | between lives | favour from the gods |

## Decisions this creates
- **Use or keep?** Eating and crafting keep the life going (more XP, depth, items); keeping maximises
  ash at death. Gear converts at a loss, so crafting is a real cost.
- **Convert or use?** All remaining inventory converts automatically at return; spending it during life can
  extend survival and increase depth and XP.
- **Hoarding is not dominant:** diminishing conversion past 5 lifetime copies and the measured survival advantage of
  crafting (BALANCING.md).

## Failure modes guarded by tests
Refused purchases change nothing; a stack converts once at return; a boon is one per life; lifetime converted
counts, currencies, unlocks and earned mastery survive saves.
