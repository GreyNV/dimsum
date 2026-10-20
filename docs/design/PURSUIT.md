# Pursuit: hunters, fright and unloading (schema 20, 2026-10-17)

Once an enemy notices you, it chases until it leaves the loaded area. Ordinary enemies
fear the anchor camp and campfires; night wolves can pursue and attack there.

- **Notice**: a live enemy within its `aggro_radius` becomes a hunter
  (`Expedition.hunting[id] = {"mode": "hunt"}`). Fire-fearing enemies do not notice an
  avatar in camp or firelight.
- **Hunt**: it follows the avatar anywhere in the loaded area - no aggro limit, no territory (the old
  `EnemyDef.leash` is gone). Near the avatar it walks the distance field around obstacles; further off
  it takes any step that closes in. Fire-fearing enemies avoid camp and firelight;
  none step onto the avatar.
- **Unload**: a hunting or fleeing enemy whose chunk leaves the loaded 3x3 chunks around the avatar is
  removed. A rolled spot enemy comes back, calm, at its spot when its chunk is entered again; a lead
  (a night wolf) is gone for good. The minimap shows exactly this loaded 3x3 (`session.MINIMAP_RADIUS = 1`), so an enemy that leaves the minimap is unloaded. Hunters show on the minimap with a pulsing red ring even in fog; fleeing ones are dimmed.
- **Fright**: when the avatar stands in the camp or a campfire's light, fire-fearing hunters flee
  ("The boar shies from the camp and slinks away."), stepping away each tick until it is out of
  range; one that is cornered is gone after `FLEE_UNLOAD_MS` (20 s). Night wolves ignore
  the light and can interrupt rest.
- Saved: `hunting` {target id: {mode, since}}; migration 19 -> 20 starts with nobody hunting.
- Code: `autopilot/combat.py` (`_pursue`, `_enemy_step`, `_unload_far_enemies`, `_unload`).
  Tests: tests/test_world_pursuit.py.
- Sims (8 seeds x 90 min): mean life 19.4 min (18.9 before); deaths boar 15, starvation 16.

## Cornered at the camp or a fire
Night wolves follow into the camp and firelight, so a retreat that ends where the avatar already
stands is no retreat: a hunter beside an avatar at its rest place makes it fight back, even when
the fight looks lost. Every bite also ends a rest, so healing never outpaces a biting wolf (before
this, rest healing and bites cancelled out and the two stood together for minutes at 1 health).
Test: `test_world_night.test_cornered_at_the_camp_the_avatar_fights_back_and_never_heals_through_bites`.
