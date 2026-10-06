# Systems map (world expedition)

| Module | Owns | Reads | Writes |
|---|---|---|---|
| `world/catalog.py` | Items, actions, unlocks, boons, regions, mastery cost (validated data) | - | - |
| `world/tuning.py` | Balance numbers for spots, pity, offering, ash, gear, frontier | - | - |
| `world/regions.py` / `world/repository.py` | Adjacency-weighted region selection and pinned region catalog per world | catalog.REGIONS, seeds | world save schema 3 |
| `world/actions.py` | Known/eligible/bucket/explain (pure) | catalog | - |
| `world/encounters.py` | Rolled spot, pity spot and temporary lead placement (pure) | actions, tuning | - |
| `world/equipment.py` | Validated current-life weapon/body slots | catalog.ITEMS | - |
| `world/economy.py` | Offer value, rebirth ash, anchor shop rows, purchase | catalog, tuning | meta fields |
| `world/autopilot.py` | Expedition: lives, vitals, screening (windows, pity), goals, crafting policy, anchor, saves | all above | expedition state |
| `world/session.py` | Snapshot projection (+ region, meta, shop, debug), input validation | expedition | - |
| `world/journal.py` | Lifetime journal (actions, items, deaths, longest life) and achievements derived from it | catalog.ACHIEVEMENTS | expedition.journal |
| `world/details.py` | Read-only page projections: character, stats, multipliers, rolls, journal | expedition | - |
| `world/simulate.py` | Seeded multi-run metrics (regions, leads, staff), chunk inspection, region map | autopilot | stdout |
| `world/browser/*.js` | Presentation only (no rules); `pages.js` = tab pages + collapsible panels | snapshot | localStorage UI prefs |

Data flow on entering a chunk: `region_for` -> `Context` -> `bucket` -> runtime `chunk_spots` -> `Expedition._screen`
(window caps, drought, pity) -> admitted spots -> goals -> tasks -> rewards -> inventory -> crafting / eating /
anchor economy -> meta (dust, ash, blessing, unlocked, mastery, boon) -> next life's windows and buckets.

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
