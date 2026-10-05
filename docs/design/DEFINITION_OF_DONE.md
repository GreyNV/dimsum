# Definition of Done - "closed loop" iteration (2026-10-05)

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
