# Phase One simulator

The balance laboratory and runtime share one core. Ordinary content is authored
in src/dimensional_sim/content.py; mechanics live in core.py and save migration
in persistence.py.

## Run and verify

~~~powershell
$env:PYTHONPATH = "src"
python -B -m unittest discover -s tests -v
python -B -m dimensional_sim.cli --seconds 86400 --seed 1
python -B -m dimensional_sim.cli --offline --seconds 86400 --seed 1
python -B -m dimensional_sim.cli --compare --seconds 86400 --seed 1 --runs 100
python -B -m dimensional_sim.cli --graph
~~~

Alternatively install with python -m pip install -e . and use dimensional-sim.
There are no runtime dependencies; setuptools is the isolated build dependency.
All comparison variants use matching seeds, starting at --seed.

Equipment variants obtain an Echo Bead through validated summoning, then restore the
baseline budget and RNG. This controlled fixture isolates equipment effects;
it is not a simulated player purchase.

## Time and events

- world_seconds measures real time; simulation_seconds and life_seconds measure
  effective life time, discounted by offline_efficiency when inactive.
- Clone shards accrue per real second even at zero life efficiency.
  clone_shards_generated separates them from encounter rewards.
- Action.base_seconds is baseline work. action_work and action_seconds preserve
  partial progress across updates and saves.
- XP accrues per effective training second. Level thresholds change speed at
  that instant, including during an action.
- Vitality costs accrue proportionally to work, plus configurable passive decay
  (provisional default 0.02 per effective second).
- Death interrupts immediately and wins a tie with completion, granting no
  completion reward. A completed lethal encounter grants its configured outcome
  and then returns.
- Return clears regular XP and current-life state; dimensional XP, journal,
  equipment, unlocked stages and shards persist.
- Stage completion resolves in the same update, including its endpoint.
  Starting an already-running life is rejected to prevent healing/rerolls.
- Discovery occurs at bucket generation. Journal unlock preserves enabled state;
  toggle changes affect future buckets.

Softcaps currently affect speed only. Thresholds, softness, XP curves, speed
coefficients, summon weights, clone rate and offline efficiency are config data.
Story access depends only on the preceding story action; no level gates exist.

## Summoning

game.summon() spends the configured shared cost (prototype 10 shards), chooses
rarity from the latest completed-stage row, then a template and a rolled level.
Each rarity earns its own summon XP and has milestone-raised caps. Common items
have exactly one bonus from the six approved attributes. Inclusive level windows
follow 1..10 initially and 90..100 at rarity level100.
Each pull creates an owned instance and pending review; it never auto-equips.
summon_review(instance_id) supplies matching rows with missing stats represented
by zero. resolve_summon_review(instance_id,equip=True/False) applies the choice.
Equipping replaces the same slot while retaining both items in the collection.
See [items-and-equipment](../game-design/items-and-equipment.md).

## Reports

Reports include stage/act entry times, batch stage reach rates, discipline levels,
vitality, returns, encounter counts, journal thresholds, action timings, clone
output, summon pool unlocks and affordability.

clone_only_budget_seconds_from_opening excludes encounter rewards and spending:
it is an estimate, not observed first affordability. Action timings exclude
unfinished/interrupted actions. pending_story_actions lists incomplete preceding story actions in this life.
balance_warnings reports execution-cost issues, not additional access requirements. Graphs describe future buckets,
including story dependencies and the bucket-or-journal eligibility rule. Graph edges are prerequisites, not mutually exclusive scheduling probabilities.

## Saves

Schema 5 uses JSON RNG data and embeds config, content, clocks and partial work.
Rule/content mismatches require explicit migration. Future schemas are rejected.

Schema 1 migration interprets only numeric/tuple opcodes, never unpicklers,
globals or reducers. Missing partial work defaults to zero. Historical real
inactive time and clone telemetry cannot be recovered: the old clock is the
baseline and clone telemetry starts at zero. Supply original config/content
when available. Migrated saves continue under corrected rules.

Identically partitioned save/load continuation is exact. Split/bulk floating-point
accumulation is tested with small tolerances, preserving event order and RNG.

See [implementation review](../implementation-review-2026-09-20.md) for measured
balance and outstanding phase-one work.


## Eligibility correction

Story completion unlocks the next stage immediately, even while optional encounters
remain queued. Enabled journal unlocks supply actions regardless of roll chance.
Multiple eligible encounters execute once each in authored order after the story.
Stage rolls, including empty ones, are cached for the life and saved.

The schema3 eligibility migration, preserved in schema5, migrates schemas1/2 with the current queue, partial work and RNG
preserved. Only obsolete numeric gate fields are removed from legacy content.
Reports now use pending_story_actions and balance_warnings instead of
unmet_requirements and unreachable_requirements. The former level-12 requirement
and the old review's pacing results do not describe the corrected game.

## Spatial exploration
Run python -B -m dimensional_sim.world.cli play for the separate spatial prototype.
Its world/actor schema1 is not an idle-save replacement. See world-quickstart.md.
