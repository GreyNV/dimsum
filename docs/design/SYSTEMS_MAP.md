# Systems map (world expedition)

| Module | Owns | Reads | Writes |
|---|---|---|---|
| `world/catalog.py` | Items, actions, unlocks, boons, regions, mastery thresholds (validated data) | - | - |
| `world/tuning.py` | Balance numbers for spots, pity, offering, ash, gear, frontier | - | - |
| `world/regions.py` / `world/repository.py` | Adjacency-weighted region selection, organic per-tile region field (v3), pinned region catalog per world | catalog.REGIONS, seeds | world save schema 5 |
| `world/water.py` | River overlay (generator v4): one global contour field, fords/bridges where trails cross | seeds | nothing (pure function of world seed) |
| `world/actions.py` | Known/eligible/bucket/explain (pure) | catalog | - |
| `world/encounters.py` | Rolled spot, pity spot and temporary lead placement (pure) | actions, tuning | - |
| `world/equipment.py` | Validated current-life weapon/body slots | catalog.ITEMS | - |
| `world/economy.py` | Lifetime diminishing ash conversion, anchor shop rows, purchase | catalog, tuning | meta fields |
| `world/autopilot/` | Expedition (one mixin per concern): life loop, goals, navigation, screening (windows, pity, guarantee), combat, outcomes/crafting policy, vitals, anchor, saves | all above | expedition state (schema 10) |
| `world/session.py` | Snapshot projection (+ region, meta, shop, debug), input validation | expedition | - |
| `world/journal.py` | Lifetime journal (actions, items, deaths, longest life) and achievements derived from it | catalog.ACHIEVEMENTS | expedition.journal |
| `world/details.py` | Read-only page projections: character, stats, multipliers, rolls, journal | expedition | - |
| `world/simulate.py` | Seeded multi-run metrics (regions, leads, staff), chunk inspection, region map | autopilot | stdout |
| `world/browser/*.js` | Presentation only (no rules); `pages.js` = tab pages + collapsible panels | snapshot | localStorage UI prefs |

Data flow on entering a chunk: `region_for` -> `Context` -> `bucket` -> runtime `chunk_spots` -> `Expedition._screen`
(window caps, drought, pity) -> admitted spots -> goals -> tasks -> rewards -> inventory -> crafting / eating /
anchor economy -> meta (ash, blessing, unlocks, earned mastery, boon) -> next life's buckets and guarantee.

Determinism: every random choice is derived from saved seed and entry history. Screening order follows
player entry order. Runtime spot plans, stats, drought, forced pity spots and meta are saved.

Pages (2026-10-05): the client asks for `detail: true` (at most twice a second) only while a page other than
World/Settings is open; `session.snapshot` then adds `expedition.detail` from `details.detail()`. Achievements
are computed from the journal on demand, never stored, so thresholds can change without a save upgrade.
The journal itself is saved (expedition schema 9; schema 6 saves upgrade with an empty journal,
schema 7 saves migrate spot rolls and initialize discovery/Journal choice fields).

Boar behavior (2026-10-05): every live, admitted boar within `BOAR_AGGRO_RADIUS` (9 steps) charges the avatar one
step per `MONSTER_STEP_MS` (300 ms; the avatar walks a step per 120 ms, so it only gets caught while busy). On contact
the boar bites first (one `boar_hit`) and interrupts work; the avatar fights back unless that fight would kill it,
in which case it runs for the camp; a boar that catches the fleeing avatar gores it in passing (retreat is not free). Boars never chase within `CAMP_SAFE_RADIUS` (5) of the anchor. Bites are counted
per target (`strikes`, presentation only) so the client plays a lunge and a red damage number.

Action lifecycle (2026-10-06): `actions.explain()` returns one `state` per action (UNKNOWN, JOURNAL_DISABLED,
BUCKET_INELIGIBLE, BUCKET_ELIGIBLE, NOT_ROLLED, TEMPORARY_LEAD, RECIPE, CONTEXT_INELIGIBLE, AVAILABLE, RESOLVED);
see ACTION_SYSTEM.md for the pipeline and persistence table.
