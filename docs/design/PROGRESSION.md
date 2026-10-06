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
- Possibility space (dust): climbing 15, scavenging 20, snares 25, meditation 30, mushroom lore 45
  (needs climbing), hide working 50, road lore 70 (needs meditation).
- Blessing: shrine path 3 (shrines on the old road: reliable prayer), boons 2 (bountiful path: +1 food
  windows; iron skin: boar hits x0.75) for the next life only.
- Ash: mastery levels 1-3 on any spot action (cost 3, 6, 9): wider spawn window where it has one; level 2
  lets the Journal disable/enable it in future rolls; level 3 lets the Journal favor (x1.5) or suppress (x0.5) it.

## Principle
Unlocks, knowledge and Journal settings add or shape actions in future buckets; they never force them to exist
(region pools, rolls and windows still apply). A new unlock is visible in the next life's debug bucket and in spawned spots.
