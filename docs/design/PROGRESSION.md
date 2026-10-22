# Progression

## In a run (one life)
- Regular XP per attribute (resets) speeds actions (`progression.speed_permille`).
- Gear (equipped in `weapon` / `body` slots, current life only): staff (+1 punch), wrap (-30% boar damage).
- Discoveries during a life become permanent: `deer_sign` (tracks), `primitive_crafting` (5 branch gathers),
  `padded_jerkin` recipe (an abandoned camp's bedroll), `studded_wrap` recipe (a watchtower's armory).
  Leads (deer trail, deer) are temporary.
- Frontier: the auto-pilot explores only rings where one boar fight costs <= 60% health
  (`tuning.COMFORT_DAMAGE_PERCENT`); damage, endurance and gear push it outward. Starving adds one
  ring. Deeper rings = more ash at rebirth and stronger XP sources (boars).

## Between runs (meta)
- Dimensional XP (20% of every gain) persists and speeds later lives.
- Actions open by permanent dimensional level, never by ash (schema 17): climbing at strength 2,
  scavenging at perception 2, snare lines (hunter's cabins) at perception 3, meditation at endurance 2,
  road lore at endurance 3, mushroom lore at perception 4. The anchor log says when one opens; the
  Character page lists what is still ahead.
- Ash buys skills (contact 10) and keeps crafts: a recipe found in a life
  (snare from the hunter's cabin or animal tracks, hide wrap from skinning a boar, ...) lasts only that
  life unless it is kept at the anchor ("Keep: X"): snare 15, hide wrap 20, padded jerkin 25,
  spear 35, axe 35, studded wrap 40.
- Shrine path opens at willpower 3 like the other actions. Blessings and boons were removed (schema 18).
- The anchor can be contacted mid-life (skill 1, 2-minute recharge): the world waits while ash is spent.
- Possession (skill 3): 30 s of manual control, moving and actions 20% faster, then 60 s to recharge.
- Places, not actions, are mastered (2026-10-22, docs/design/LOCATIONS.md): every encounter finished in a
  region or kind of landmark counts for it, in every life. Known (Journal shows its odds), Mastered (camp can
  be made there: the avatar keeps to that place and the focus you choose), Deep (rare finds likelier).
- Ash no longer buys the campfire; mastering a place allows making camp there.

## Principle
Unlocks and knowledge add actions to future buckets. A camp's focus changes weights in its place.
