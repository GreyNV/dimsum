# Simulation architecture direction

The first implementation should be a headless deterministic simulation with a thin UI on top.

## State boundaries

- `AnchorState`: persistent discoveries, soulbound equipment, journal toggles, dimensional experience, shards, and unlocked acts or stages.
- `EntityState`: current-life disciplines, regular experience, vitality, abilities, and current action bucket.
- `RunState`: current life time, act and stage, generated encounters, action progress, journal counts, and temporary outcomes.
- `CloneState`: passive dimensional-shard generation rate and accrual state.
- `WorldState`: simulation time, dimension conditions, scheduled events, and seeded random state.

## Data-driven content

Acts, stages, disciplines, actions, encounter tables, journal thresholds, soulbound items, summon pools, action dependencies, and softcap rules should be data definitions validated at load time. The engine should not require a code change for an ordinary new action, encounter, or item.

## Command and simulation model

The UI submits commands such as `start_life`, `configure_journal`, `summon_item`, `equip_item`, and `shift_dimension` when that future system is enabled. The automatic action runner advances time, resolves a persisted stage bucket, and returns a new state plus an event log. Anchor return is an automatic transition when vitality reaches zero.

Use one `advance_time(delta)` path for active play and offline progress. Resolve action completions, XP ticks, softcap calculations, loot rolls, and scheduled events in chronological order.

Regular and dimensional experience must be represented as separate values for every discipline. Anchor return clears regular experience while preserving dimensional experience. Dimensional-shift behavior must be isolated behind a future transition policy so Phase One does not accidentally encode a reset rule. Soulbound items can only enter the state through a validated summon command.

## Persistence and testing

Saves require a schema version and migration path. Random rolls use an explicit seed. Tests should cover deterministic replay, persisted encounter buckets, reset persistence, journal thresholds and toggles, soulbound summon validation, softcap monotonicity, offline equivalence, passive clone output, and invalid content definitions.


## Story and bucket eligibility

Story access follows the authored action sequence, with no discipline-level gates.
RunState records completed_story_actions, stage_buckets (one random roll per stage
per life), and encounter_bucket (the current queue's snapshot including journal
unlocks). The ordered queue runs story actions before optional encounters.
Persistent unlocked_stage records story access earned across lives; each new life
still replays its preceding actions.

Schema 3 introduced these fields; current idle saves use schema 5. Schemas 1 and 2 migrate without rerolling or
losing partial work. Schema 2 content comparison removes only obsolete
min_dimensional_level and gate_discipline fields; unrelated content mismatches
still fail. Legacy stage rolls are reconstructed from the latest recorded entries
of the current life, since older versions could reroll on a revisit.

## Implemented spatial boundary
The opt-in character-grid foundation is documented in [world-foundation.md](world-foundation.md).
It lives in dimensional_sim.world and does not replace the idle action runner.
WorldRepository owns frozen catalogs, chunks and discovery; Exploration owns player/
combat clocks; renderer is read-only; pipeline is offline only. Exploration schema1
embeds its own world/animation data and remains separate from idle schema5.
The conceptual state names above are responsibilities, not additional classes.
See [world-quickstart.md](world-quickstart.md) and root AGENTS.md.

## Current idle persistence
Schema5 persists six attributes, rolled item instances, independent rarity progress,
completed stages and pending equipment reviews. Schemas1..4 migrate under explicit
rules in core.py; persistence.py handles safe RNG decoding. No idle save migration
was introduced by the spatial feature.
