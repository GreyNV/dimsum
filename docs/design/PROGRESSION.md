# Progression

## In a run (one life)
- Regular XP per attribute (resets) speeds actions (`progression.speed_permille`).
- Gear (equipped in `weapon` / `body` slots, current life only): staff (+1 punch), wrap (-30% boar damage).
- Discoveries during a life become permanent: `deer_sign` (tracks), `primitive_crafting` (5 branch gathers),
  `walking_staff` recipe (10 branch gathers). Leads (deer trail, deer) are temporary.
- Frontier: the auto-pilot explores only rings where one boar fight costs <= 60% health
  (`tuning.COMFORT_DAMAGE_PERCENT`); damage, endurance, gear and boons push it outward. Starving adds one
  ring. Deeper rings = more ash at rebirth and stronger XP sources (boars).

## Between runs (meta)
- Dimensional XP (20% of every gain) persists and speeds later lives.
- Possibility space (ash): manual return 10 (5-minute cooldown), climbing 15, scavenging 20, snares 25, meditation 30, mushroom lore 45
  (needs climbing), hide working 50, road lore 70 (needs meditation).
- Blessing: shrine path 3 (shrines on the old road: reliable prayer), boons 2 (bountiful path: +1 food
  windows; iron skin: boar hits x0.75) for the next life only.
- Repeating a spot action earns mastery at 10, 100 and 1,000 lifetime completions. Grade 1 reveals
  its Journal entry, location and current-run chance; grade 2 allows favor (x1.5) or suppress (x0.5);
  grade 3 adds one guaranteed encounter in a chosen eligible region per life, outside the usual roll bucket.

## Principle
Unlocks and knowledge add actions to future buckets. Journal favor changes weights; its grade-3 guarantee
places one extra spot in the first suitable chunk entered in the chosen region each life.
