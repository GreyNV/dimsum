# Resource economy

Every resource has a source, at least one in-run use and a death-time conversion. Values: `catalog.ITEMS`
(`ash_value`), rules: `world/economy.py`, numbers: `world/tuning.py`.

## Items
| Item | Source | In-run sink | Ash each before diminishing | Notes |
|---|---|---|---|---|
| Wild berries | bramble berries | eat (+12) | 1 | |
| Bird egg | gnarled tree (strength 2) | eat (+20) | 2 | |
| Boar meat | boar | eat (+35, +11 hp) | 3 | |
| Venison | deer hunt after temporary lead | eat (+28) | 3 | |
| Pale mushroom | mushroom ring (perception 4) | eat (+15) | 2 | |
| Snared hare | snare craft (recipe) | eat (+30) | 3 | turns materials into food |
| Stick | branches, tree, camp | staff (3), snare (2) | 1 | |
| Bramble thorn | berries 35%, camp | snare (1) | 2 | |
| Boar hide | boar 60%, camp 20% | wrap (2, recipe) | 4 | |
| Walking staff | learned recipe + craft | weapon slot, +1 punch while equipped | 2 | worth less than its 3 sticks |
| Hide wrap | craft | body slot, boar hits x0.7 while equipped | 6 | worth less than its 2 hides (8) |

## Currencies
| Currency | Source | Sink | Timing | Purpose |
|---|---|---|---|---|
| Dimensional ash | all carried items convert when a life ends; first 5 lifetime copies of each item full value, later copies half value; +1 per ring reached | campfire skill (25), keeping recipes found this life (15-40), binding camp buildings (120 / 200) | at the anchor: between lives, or mid-life by contacting it (skill 1; the world waits) | pass knowledge and the camp to the next life |

## Decisions this creates
- **Use or keep?** Eating and crafting keep the life going (more XP, depth, items); keeping maximises
  ash at death. Gear converts at a loss, so crafting is a real cost.
- **Convert or use?** All remaining inventory converts automatically at return; spending it during life can
  extend survival and increase depth and XP.
- **Hoarding is not dominant:** diminishing conversion past 5 lifetime copies and the measured survival advantage of
  crafting (BALANCING.md).

## Failure modes guarded by tests
Refused purchases change nothing; a stack converts once at return; lifetime converted
counts, currencies, unlocks and earned mastery survive saves.
