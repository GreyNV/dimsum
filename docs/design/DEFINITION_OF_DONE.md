# Definition of Done - "closed loop" iteration (2026-10-05)

> Historical acceptance record for the earlier closed-loop iteration. The
> region/discovery/Journal iteration is documented in
> [ACTION_ARCHITECTURE_AUDIT.md](ACTION_ARCHITECTURE_AUDIT.md).

Each item is checked by an automated test (T), the simulation report (S, `python -m dimensional_sim.world.cli simulate`)
or a recorded manual/headless browser check (B). "Seeds" means world seeds 1-20 unless stated.

| # | Area | Acceptance criteria | Check |
|---|---|---|---|
| 1 | Core loop | A fresh expedition reaches: prologue -> explore -> >=3 completed actions -> >=1 eat -> death -> anchor -> next life, on every seed within 30 simulated minutes. | T, S |
| 2 | World generation | Same seed + unlocks + life => byte-identical spots, regions and saves (bulk == 20 ms ticks == save/reload). | T |
| 3 | Enemies | Every life on every seed has >=1 boar admitted within the first 9 explored chunks; on average >=1 boar per 6 explored chunks. | T, S |
| 4 | Food | Every life on every seed has a food source (berries, snare materials or boar) admitted within the first 9 explored chunks; no life rolls a zero food window. Starvation is possible but not certain (some lives end by boar, some by starvation). | T, S |
| 5 | Interaction | Spots, crafting, eating, fighting, prayer and resting each occur on >=80% of seeds in 30 minutes. | S |
| 6 | Economy | Every item has >=1 in-run sink (eat or craft) and the death sink; every currency has >=1 spend. Table in RESOURCE_ECONOMY.md matches code (test reads catalog). | T |
| 7 | Action bucket | One registry (`world/actions.py`) holds every action with category, placement, unlock, context and weight. `explain()` answers why an action is/is not in a bucket. | T |
| 8 | Unlocks | Buying an unlock at the anchor makes that action eligible in the next life's buckets; a locked action never spawns. | T |
| 9 | Run progression | Within a life: XP raises speed, crafted gear changes punch damage or damage taken, depth raises danger. | T |
| 10 | Meta progression | Dust, ash, blessing, unlocks, mastery and dimensional XP persist across lives and saves. | T |
| 11 | Blessing | Earned by prayer; spent on shrine unlock or a next-life boon. | T |
| 12 | Dust / Ash | Dust = offered items (diminishing per stack); Ash = unoffered items burned at rebirth; dust buys unlocks, ash buys mastery. | T |
| 13 | Crafting | >=3 recipes; each consumes items and changes a later outcome (damage, hit taken, food). | T |
| 14 | Death conversion | Holding items to death yields currency, but hoarding does not dominate: in S, crafting must win on survival/XP while hoarding may win on raw unlock count by at most 10%. | S |
| 15 | Visual consistency | VISUAL_STYLE.md exists; the ambush wagons and spots use outlined cell sprites; no free-drawn solid shapes remain. | T, B |
| 16 | Player sprite | 4 facings x walk frames: one connected silhouette, no fill pixel touching transparency, constant frame and feet row; base sprite has no equipment baked in. | T |
| 17 | Content architecture | Adding a region, action, item or recipe is a data entry in `world/catalog.py` validated at import; no generator change needed (proved by the second region set). | T |
| 18 | Regression tests | Full Python + JS suites pass; new tests cover 3, 4, 7, 8, 11-13, 16. | T |
| 19 | Observability | `cli inspect` prints region, bucket, weights, admissions/rejections for a chunk; snapshot `debug` block and browser overlay (backquote key) show seed, region, unlocked, eligible, bucket, budget, last screenings. | T, B |
| 20 | Documentation | The 11 design documents exist in docs/design and describe the shipped code. | review |

## Status at hand-off (2026-10-05)
19 of 20 items pass; item 5 is partial. Evidence: Python suite (211 tests), JS suite (62 tests),
BALANCING.md tables (items 1, 3, 4, 14), headless browser screenshots of the prologue, anchor shop, debug
overlay, and the hosted build booting a fresh world and an upgraded schema-5 save (items 15, 16, 19).
Item 5 (seeds 1-8, 30 min, spend policy): spots, eating, crafting, boar fights and prayer occurred on 8/8
seeds; resting at the camp on 6/8 (75%) because it only triggers below 35 health.


# Definition of Done - regions, discovery chains, Journal control (2026-10-06)

| # | Criterion | Status | Evidence |
|---|---|---|---|
| 1 | Every reachable action has an explicit availability classification | done | ACTION_ARCHITECTURE_AUDIT.md inventory; `ActionDef.roles` |
| 2 | known / bucket-eligible / spawned / context-eligible / available are distinct | done | `actions.explain()` fields + `state`; test_world_actions LifecycleStateTests |
| 3 | Unlocks never make world actions permanently available | done | test_unlock_permits_a_bucket_roll_but_does_not_spawn_an_action |
| 4 | Buckets/spawns remain the main driver of world opportunities | done | spots only via chunk_spots + screening; leads only follow real spots |
| 5 | Journal enable/disable and odds influence without deciding world existence | done (anchor UI) | test_journal_controls_require_mastery_and_modify_future_rolls |
| 6 | Declarative discoveries/leads/follow-ups | done | `OutcomeDef`, `_apply_outcomes`, no action-id checks in infrastructure |
| 7 | Temporary leads separate from permanent unlocks | done | test_world_discovery (expiry, save, cleared at death) |
| 8 | animal_tracks -> deer lead -> hunt | done | test_tracks_lead_to_hunt_and_food_without_world_bucket_roll; BALANCING.md |
| 9 | Branch gathering drives crafting discovery; crafting not a starting capability | done | test_branches_teach_crafting_then_the_staff_recipe_and_staff_is_equipped_gear |
| 10 | Staff is equipment (weapon slot) and improves without trivializing boars | done | test_world_equipment, test_world_combat_balance, BALANCING.md cohorts |
| 11 | Forest generates distinct, perceptible, seed-varying regions; same seed deterministic | done | generator v2, test_region_profiles_make_distinct_walkable_terrain, test_new_region_layouts_change_with_seed_and_survive_reload, browser screenshots |
| 12 | Locations alter action pools; restrictions affect play; multiple regions reached | done | test_normal_expeditions_reach_distinct_regions_and_respect_local_pools (3.9 regions per life in S) |
| 13 | Chains interact with locations | done | tracks only in Deep Woods/Still Glade; branches not in Still Glade |
| 14 | Debug explains action availability and region generation | done | `cli inspect`, `cli regions`, overlay; test_inspect_explains_region_generation_and_every_spot_state |
| 15 | Save/load separates permanent progression from temporary state | done | schema 8 + world schema 2; persistence tests; v1 worlds regrow at rebirth |
| 16 | Regressions pass; docs match behavior | done | Python 258, JS 67 |

Known limits: region cells are an independent weighted patchwork (no adjacency rules yet); the deer hunt is a
lead action, not a runtime fight; equipment overlays on the player sprite are not drawn yet.
