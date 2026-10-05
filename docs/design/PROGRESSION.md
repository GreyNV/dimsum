# Progression

## In a run (one life)
- Regular XP per attribute (resets) speeds actions (`progression.speed_permille`).
- Gear: staff (+1 punch), wrap (-30% boar damage).
- Frontier: the auto-pilot explores only rings where one boar fight costs <= 60% health
  (`tuning.COMFORT_DAMAGE_PERCENT`); damage, endurance, gear and boons push it outward. Starving adds one
  ring. Deeper rings = more ash at rebirth and stronger XP sources (boars).

## Between runs (meta)
- Dimensional XP (20% of every gain) persists and speeds later lives.
- Possibility space (dust): climbing 15, scavenging 20, snares 25, meditation 30, mushroom lore 45
  (needs climbing), hide working 50, road lore 70 (needs meditation).
- Blessing: shrine path 3 (shrines on the old road: reliable prayer), boons 2 (bountiful path: +1 food
  windows; iron skin: boar hits x0.75) for the next life only.
- Ash: mastery levels 1-3 on any windowed action (cost 3, 6, 9): +1 high and +1 low every 2nd level.

## Principle
Unlocks add actions to future buckets; they do not force them everywhere (region weights and windows
still apply). A new unlock is visible in the next life's debug bucket and in spawned spots.
