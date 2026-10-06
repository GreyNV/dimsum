# Action system: permission, buckets, spawns, leads, recipes

Current as of the 2026-10-06 region/discovery iteration. The per-action inventory and the audit that
led here are in [ACTION_ARCHITECTURE_AUDIT.md](ACTION_ARCHITECTURE_AUDIT.md).

**Owner:** `world/catalog.py` (data), `world/actions.py` (pure rules), `world/encounters.py` (placement),
`world/autopilot.py` (execution, persistence). Generators and the auto-pilot never test action ids; every
content rule is a field on an `ActionDef`, `RegionDef`, `OutcomeDef` or `Requirement`.

## The rule

```
UNLOCK != ALWAYS AVAILABLE      JOURNAL ENABLED != SPAWNED      MASTERY != FREE ACTION
```

Progression gives the player *permission* and *influence*; the procedural roll decides what exists.

## Pipeline

```
BIOME (dark_forest)
  -> GENERATED LOCATION   region of the chunk (regions.py, pinned per world)
  -> LOCATION POOL        action.regions + RegionDef.weights (percent, 0 = never here)
  -> KNOWN / UNLOCKED     unlock bought, knowledge learned, recipe discovered      actions.known()
  -> JOURNAL / MASTERY    disabled (mastery 2+) removes it; favor/suppress (3+) x1.5 / x0.5
  -> BUCKET               positive effective weight                               actions.bucket()
  -> ROLL / SPAWN         chunk_spots: 0-3 spots per chunk from the bucket, seeded by chunk + life
  -> SCREENING            spawn windows (at-once caps) and pity                    autopilot._screen
  -> CONTEXT              ingredients, hunger, carried food, live play, once per life, live lead token
  -> AVAILABLE ACTION     the auto-pilot walks there / starts it
  -> OUTCOME              loot, XP, heal, blessing, gear (equipped), knowledge, recipe, temporary lead
```

Each placement keeps its own availability semantics while sharing the same eligibility code:

| Placement | Comes from | Needs a terrain roll? | Lifetime |
|---|---|---|---|
| `spot` | `chunk_spots` roll in a resident chunk, then screening | yes | until completed or the life ends |
| `lead` | an `OutcomeDef(kind="lead")` of a completed action, placed by `lead_spot` in the source chunk | no (it is the follow-up of a real spot) | until completed, expired (`ttl_ms`) or the life ends |
| `self` | `trigger="need"` (recipes/crafts, priority-ordered) or `trigger="after_location"` (reflection, prayer) | no | per use |

## Lifecycle states (debug overlay, `cli inspect`, `actions.explain()["state"]`)

`UNKNOWN` (no permission) -> `JOURNAL_DISABLED` | `BUCKET_INELIGIBLE` (wrong region/biome/placement, unmet
requirement, no live lead) -> `BUCKET_ELIGIBLE` (spawn state unknown) -> `NOT_ROLLED` | rolled ->
`CONTEXT_INELIGIBLE` / `RECIPE` (known craft, materials missing) | `TEMPORARY_LEAD` (live lead) | `AVAILABLE`;
`RESOLVED` once an opportunity is used. The debug overlay marks admitted spots with `*`; a rolled spot can still
be turned away by its spawn window (screening log says why).

## Definitions (catalog.py)

- `ActionDef`: id, name, category, placement, attribute, xp, duration, weight, `unlock`, `knowledge`, `recipe`,
  `requirements` (`Requirement(kind, id, count)`: action_count, item_count, knowledge, unlock, recipe, level),
  `outcomes` (`OutcomeDef(kind, id, at_count, chance, ttl_ms)`: knowledge, recipe, lead), biomes, regions,
  near, window, loot, heal, blessing, cost, effect (gear), need policy fields, roles (descriptive).
- `RegionDef`: biome, selection weight, tint, action weight percents, `canopy`, `brush`, `landmark` (terrain).
- `UnlockDef` (dust/blessing, anchor), `BoonDef` (next life), mastery (ash, `MASTERY_MAX` 3,
  `JOURNAL_TOGGLE_MASTERY` 2, `JOURNAL_FAVOR_MASTERY` 3).
- `validate_catalog()` checks every cross reference at import (leads point at lead actions, knowledge and
  recipes have a source, items have a source, regions exist).

## Discovery vs knowledge vs unlock vs lead vs spawn

| Concept | Meaning | Stored | Survives death |
|---|---|---|---|
| Discovery | an outcome fired (log line `Learned ...`, `Discovered ... recipe`) | log | log only |
| Knowledge | permanent understanding (`deer_sign`, `primitive_crafting`) | `knowledge` | yes |
| Recipe | permanent craft permission (`walking_staff`) | `recipes` | yes |
| Unlock | bought permission for actions to join future buckets | `unlocked` | yes |
| Lead | one temporary opportunity in this world/life (`follow_deer_tracks`, `hunt_deer`) | `leads`, `lead_history` | no |
| Spawn | a rolled spot in a chunk this life | derived from seeds; `completed`, `admitted` | no |

## Debugging

- `python -m dimensional_sim.world.cli inspect --seed S --x X --y Y [--unlock U] [--knowledge K] [--recipe R]`:
  region and how it was chosen, its generation parameters, the resulting terrain profile, rolled spots,
  the bucket, and every spot action's state, weight and modifiers.
- `python -m dimensional_sim.world.cli regions --seed S`: the region layout around the anchor.
- Browser `?debug` or backquote: states, knowledge/recipes, leads with expiry, buckets, windows, pity, screening.
- `Expedition.debug_info()`, `actions.explain(id, Context(...))`.

## Extending (data only)

- New chain: give an action an `OutcomeDef(kind="lead", id=..., chance, ttl_ms)` and add the follow-up
  `ActionDef(placement="lead", knowledge=...)`. Smoke -> camp, sound -> creature, ruins -> investigation all fit.
- New recipe: `ActionDef(category="craft", placement="self", trigger="need", recipe=..., cost=..., effect=...)`
  plus an outcome somewhere that grants the recipe.
- New location: `RegionDef` (biome, terrain parameters, action percents). Bump `ENCOUNTER_VERSION` and add a
  save upgrade when existing worlds' rolls change.

## Tests

`tests/test_world_actions.py` (stages, states, Journal, inspect), `tests/test_world_discovery.py` (deer chain,
lead expiry, crafting progression, persistence, v1 world regrowth), `tests/test_world_equipment.py`,
`tests/test_world_region_variety.py`, `tests/test_world_combat_balance.py`, `tests/test_world_closed_loop.py`.
