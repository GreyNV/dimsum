# Implementation plan and decision record (closed-loop iteration)

Priorities followed P0 -> P4 as requested, with one reorder: the action registry (P1) had to exist before the
P0 food/enemy fix could be expressed without hard-coded conditions, so the fix shipped together with it.

| Batch | Scope | Acceptance | Status |
|---|---|---|---|
| B0 | Audit, Definition of Done, design docs | CURRENT_STATE.md reproduces the regression with seeds | done |
| B1 (P0) | Food/enemy restoration: windows low >= 1, count table, pity, region weights | every seed: food + boar within 18 chunks; mixed death causes | done |
| B2 (P1) | Action registry + bucket + explain; regions; crafting recipes; need policy | ActionBucket/Crafting tests | done |
| B3 (P2) | Economy: offering (diminishing), rebirth ash, unlocks, boons, mastery; schema 6 + v5 upgrade | Economy tests, save round trips | done |
| B4 (P1/P2) | Frontier risk policy (danger-aware exploration) | lives end by starvation and boars; crafting extends lives | done |
| B5 | Observability: `cli inspect`, `cli simulate`, snapshot `debug`, browser overlay | Observability tests, screenshots | done |
| B6 (P4) | Visual: walk artifacts, crouch frame, wagons as cell sprites, style spec | pixel-player tests, contact sheets | done (parallel agent, merged) |
| B7 | Balancing runs and documentation | BALANCING.md tables | done |
| B8 (2026-10-06) | Region-shaped terrain (generator v2), knowledge/recipe/lead outcomes, deer chain, gated staff, equipment slots, Journal roll controls, lifecycle states, schema 8 | DEFINITION_OF_DONE.md (2026-10-06) | done |
| B9 (2026-10-06) | Organic per-tile regions + meandering trails (generator v3, world schema 4), 8-way movement (stick sectors, combined keys, 141% diagonal time, no corner cutting) | test_world_generation OrganicRegionTests, test_world_runtime DiagonalMovementTests | done |
| B10 (2026-10-06) | Rivers as an overlay, not a region (generator v4, world schema 5): continuous across chunks, impassable, fords/bridges on trails | test_world_generation RiverTests | done |
| Next | ash_plain biome via RegionDefs + pool; pixel-tier equipment overlays; region adjacency rules; more chains | - | not started |

## Architectural decisions
1. **Content as validated data (catalog.py).** EncounterDef became ActionDef with placement/trigger/unlock;
   `encounters.EncounterDef` remains as an alias for compatibility.
2. **Eligibility is pure (actions.py).** Generators and the auto-pilot never test content ids for rules.
3. **Regions are a layer over chunks.** (2026-10-05) They first only changed action weights, which left every
   run looking the same. Since 2026-10-06 the versioned generator v2 reads the pinned RegionDef (canopy, brush,
   landmark); v1 worlds replay unchanged and regrow with v2 at the next rebirth. Adding a region is still data.
4. **Pity over probability hikes.** Starvation of a category is fixed with an explicit, logged, saved forced
   spot, so balance stays scarce but never broken.
5. **Two death currencies with different sinks.** Offer -> dust (possibilities), keep -> ash (mastery).
   Offline players still progress via ash.
6. **Risk-aware exploration (frontier).** Without it every life ended at the first deep boar, making food and
   gear irrelevant. The frontier ties run progression (XP, gear, boons) to how far a life can go.
7. **Save schema 6 with upgrades from 1-5.** Spots re-roll (encounters-v6); earned progress is kept.
8. **Shared architecture was decided centrally; agents did audits and isolated visual work in a worktree.**
