# Pursuit: hunters, fright and unloading (schema 20, 2026-10-17)

Decision (Andrew): once an enemy notices you, you can't run from it - it chases until it is out of
range, then it is unloaded. Reaching the anchor camp or a campfire scares it: it roams off until it
is out of range and unloaded.

- **Notice**: a live enemy within its `aggro_radius`, the avatar out of the camp and firelight
  (`NightMixin.in_firelight`), becomes a hunter (`Expedition.hunting[id] = {"mode": "hunt"}`).
- **Hunt**: it follows the avatar anywhere in the loaded area - no aggro limit, no territory (the old
  `EnemyDef.leash` is gone). Near the avatar it walks the distance field around obstacles; further off
  it takes any step that closes in. It never steps into the camp or firelight, or onto the avatar.
- **Unload**: a hunting or fleeing enemy whose chunk leaves the loaded 3x3 chunks around the avatar is
  removed. A rolled spot enemy comes back, calm, at its spot when its chunk is entered again; a lead
  (a night wolf) is gone for good. The minimap shows exactly this loaded 3x3 (`session.MINIMAP_RADIUS = 1`), so an enemy that leaves the minimap is unloaded. Hunters show on the minimap with a pulsing red ring even in fog; fleeing ones are dimmed.
- **Fright**: when the avatar stands in the camp or a campfire's light, every hunter turns to flee
  ("The boar shies from the camp and slinks away."), stepping away each tick until it is out of
  range; one that is cornered is gone after `FLEE_UNLOAD_MS` (20 s). Nothing notices the avatar
  while it is in the camp or firelight.
- Saved: `hunting` {target id: {mode, since}}; migration 19 -> 20 starts with nobody hunting.
- Code: `autopilot/combat.py` (`_pursue`, `_enemy_step`, `_unload_far_enemies`, `_unload`).
  Tests: tests/test_world_pursuit.py.
- Sims (8 seeds x 90 min): mean life 19.4 min (18.9 before); deaths boar 15, starvation 16.
