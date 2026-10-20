# The anchor and possession (schema 18, 2026-10-17)

Decisions (Andrew, 2026-10-17): blessings are obsolete now that actions open by stats; ash is the one
currency. Start at the anchor so its explanation is seen. Return-to-anchor (a chosen death) becomes
"Contact anchor": the shop opens and the life resumes. The campfire is bought with ash. Manual control
is the player's god possessing the avatar: a full charge gives at least 30 s, an empty charge
refills in 60 s, and possession grants +20% movement and action speed.

## Flow
1. **New game** (browser, hosted and local): `Expedition(..., opening=True)` waits at the anchor
   (`anchor_space.kind = "opening"`) with the anchor's words, the skill keys and the shop. Time does not
   pass. "Begin your first life" starts the prologue (wake up, stand up, the old man). Simulations and
   tests keep `opening=False` (the prologue starts at once).
2. **Death**: unchanged - everything carried becomes ash, 30 s anchor countdown (`kind = "death"`).
3. **Contact anchor** (skill 1, action `contact`): buy for 10 ash, then use during a life after the prologue. The world
   waits (`advance` / `advance_manual` do nothing), the shop opens over the dimmed world
   (`kind = "contact"`), purchases work, `begin_life` is refused. "Resume this life" (`resume`) closes it
   and starts a 5-minute recharge (`CONTACT_COOLDOWN_MS`, saved as `contact_ready_ms`). The open contact
   itself is not saved: a reload steps back into the life.
4. **Possession** (skill 2, Q, or the Possess button; actions `possess` / `release`): a full meter grants
   `POSSESS_MS` = 30 s of simulation time before Willpower extends it. Partial charge can be used;
   releasing early preserves the unused charge. An empty meter refills over 60 s of simulation time,
   including while the avatar is under auto-pilot control. While possessed, `speed()` x1.2 (every task started is
   20% shorter, punches recharge faster) and the movement interval /1.2 (`load_percent`). It ends by
   itself (the step cap stops exactly at `possess_end_ms`), on release, on contact, on death, or when
   the auto-pilot drives (`advance`, e.g. after a reload or offline). `possess_charge` and its reference
   time are saved, so release and reload preserve the meter. Keys do nothing while the avatar is not possessed.
5. **Campfire**: `UnlockDef("campfire", ash 25, ability="make_campfire")`; `make_campfire`
   names `unlock="campfire"`, so the auto-pilot's emergency fire also needs it. The build
   action is contextual to the current location; skill 3 is the locked Dimensional Shift placeholder.

## Removed
Blessing, boons (`BoonDef`, `BOONS`), the random prayer (`pray` self action), `prayers_this_life`,
skills / `take_control`, the old death-on-return behavior, the "blessing" log type. Shrines stay as
Willpower encounters; the shrine path opens at willpower 3.

## Save migration 17 -> 18
Drops the removed fields; a purchased `return_anchor` now grants Contact anchor and retains its cooldown;
the campfire, free before, is granted;
"pray" leaves the journal counts; a running prayer task is dropped; blessing log entries become lore.
Test support: `tests/save_fixture.py` turns a current save back into its schema-17 shape so older
migration tests keep working.

## Client
`anchor_ui.js` (texts per kind, Resume vs Begin), skill bar (contact / possess / Dimensional Shift with a
charge meter), `scene_fx.js` possession art (ground ring of marks, halo, rising motes, a burst as it takes
hold, gold screen edges that fade in the last 5 s), sounds `possess` / `release`, a 0:30 clock in the
controls bar.

Tests: tests/test_world_anchor_possession.py (+ updates across the suite).
