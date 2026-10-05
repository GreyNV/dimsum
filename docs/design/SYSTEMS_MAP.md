# Systems map (world expedition)

| Module | Owns | Reads | Writes |
|---|---|---|---|
| `world/catalog.py` | Items, actions, unlocks, boons, regions, mastery cost (validated data) | - | - |
| `world/tuning.py` | Balance numbers for spots, pity, offering, ash, gear, frontier | - | - |
| `world/regions.py` | Region of a chunk (pure) | catalog.REGIONS, seeds | - |
| `world/actions.py` | Known/eligible/bucket/explain (pure) | catalog | - |
| `world/encounters.py` | Spot placement per chunk + pity spot placement (pure) | actions, tuning | - |
| `world/economy.py` | Offer value, rebirth ash, anchor shop rows, purchase | catalog, tuning | meta fields |
| `world/autopilot.py` | Expedition: lives, vitals, screening (windows, pity), goals, crafting policy, anchor, saves | all above | expedition state |
| `world/session.py` | Snapshot projection (+ region, meta, shop, debug), input validation | expedition | - |
| `world/journal.py` | Lifetime journal (actions, items, deaths, longest life) and achievements derived from it | catalog.ACHIEVEMENTS | expedition.journal |
| `world/details.py` | Read-only page projections: character, stats, multipliers, rolls, journal | expedition | - |
| `world/simulate.py` | Seeded multi-run metrics, chunk inspection | autopilot | stdout |
| `world/browser/*.js` | Presentation only (no rules); `pages.js` = tab pages + collapsible panels | snapshot | localStorage UI prefs |

Data flow per chunk: `region_for` -> `Context` -> `bucket` -> `chunk_spots` -> `Expedition._screen`
(window caps, drought, pity) -> admitted spots -> goals -> tasks -> rewards -> inventory -> crafting / eating /
anchor economy -> meta (dust, ash, blessing, unlocked, mastery, boon) -> next life's windows and buckets.

Determinism: every random choice is `derive_seed(world_seed | chunk_seed, label, ...)`. Screening order follows
the deterministic resident-chunk order. All new state (stats, drought, forced pity spots, meta) is saved.

Pages (2026-10-05): the client asks for `detail: true` (at most twice a second) only while a page other than
World/Settings is open; `session.snapshot` then adds `expedition.detail` from `details.detail()`. Achievements
are computed from the journal on demand, never stored, so thresholds can change without a save upgrade.
The journal itself is saved (expedition schema 7; schema 6 saves upgrade with an empty journal).
