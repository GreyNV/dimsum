---
name: idle-game-engine
description: Build and verify a deterministic, data-driven idle-game simulation with actions, time advancement, loot, equipment, resets, dimensional shifts, and offline progress.
metadata:
  short-description: Idle game simulation engineering
---

# Idle game engineering

Use this skill when implementing or testing the game's simulation and content systems.

## Architecture

- Keep the simulation independent from the UI.
- Use one time-advance path for active play and offline progress.
- Represent content as validated data: actions, disciplines, items, stages, encounter tables, requirements, rewards, and unlocks.
- Keep current-life state, persistent anchor state, passive clone state, and future dimensional-shift state distinct.
- Use stable identifiers and versioned saves with migrations.
- Keep randomness behind an explicit seeded generator so outcomes can be reproduced.
- Resolve events in chronological order. If an action changes speed or requirements, apply the change at the correct event time.

## Simulation invariants

- The same state, commands, elapsed time, and random seed produce the same result.
- Experience, loot, and action completion cannot be duplicated by save/load or offline calculation.
- A reset changes only the state explicitly listed as temporary.
- The initial clone is a passive shard accumulator and must not create a second copy of permanent progression.
- Softcapped gains remain positive and converge according to the documented formula.

## Verification

Test deterministic replay, reset persistence, seeded loot, softcap monotonicity, offline/online equivalence, save migrations, invalid requirements, and multiple simultaneous projections. Add balance simulations before adding large content sets.

Read `docs/technical/architecture.md` and the relevant design document before changing the state model.
