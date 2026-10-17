# Playtest and economy audit (2026-10-17)

Scope: what playing the game is like right now, where ash and blessing come from and go, the Supabase save database, and refactoring opportunities.
Sources:

- The local tree on the device, including the uncommitted feedback-round files (schema 17).
- 10 seeded simulations of 4 hours each with a "perfect shopper" bot that buys everything the moment it can. That is 87 lives.
- The live hosted save in Supabase: schema 16, life 213, 63 hours played.
- A local browser session with screenshots of the first 90 seconds.

---

## 1. The short version

1. **Ash has nowhere to go after about 2 hours.** Even a bot that buys everything instantly runs out of things to buy at a median of **140 minutes**. After that it banks about **+2.7 ash per minute of play**, and that never stops. The whole ash catalog is 10 (return) + 170 (keep all six recipes) + 120 (bind station) + 200 (bind chest) = **500 ash for the whole game**. In practice it is 300, because the chest is never built (see 3).
2. **The live save shows the problem is worse for a real player: 4,990 ash and 20 blessing unspent, nothing bound, no boon chosen.** This is after 213 lives. The money is there; the chance to spend it is not (see 2).
3. **The anchor is a 30-second window, and it is the only shop.** Offline catch-up and anyone who isn't watching skip through every anchor. Recipes found in a life that are not kept within those 30 seconds are lost.
4. **Blessing is earned without choice and spent without feedback.** It comes in at about 0.9 per life from one random prayer, which only happens while the tab is visible. It buys either a 2-blessing boon that you can't see until next life (only 2 boons exist) or a 3-blessing shrine path. Because the boon is always cheaper, the shrine path is never reached in sims (0/10 runs).
5. **The database is healthy but carries dead weight.** 32 of 55 rows can never load (schema below 6). Only 1 row is on a current schema. Most of a save's size is the fog-of-war masks.
6. **Refactoring hotspot:** `Expedition` is one object with about 75 attributes and a flat 60-field save that mixes "this life" and "forever" state. Splitting it into Soul and Life would simplify saves, rebirth, the hosted "new world" path, and any new shop.

---

## 2. Playtester walkthrough: what the player experiences

| # | Moment | What happens | Problem | Severity |
|---|---|---|---|---|
| P1 | Death → anchor | A 30 s countdown, then the next life starts by itself. It only waits on life 1 or after a purchase. | An idle game punishes the player for not watching. Keep offers (recipes found this life) disappear for good. | **High** |
| P2 | Coming back after time away | Catch-up replays every life with `allow_prayer=False`, and no anchor purchases are possible. The toast says "N lives ended, best ring X". | No ash gained, no recipes forgotten, no levels opened, no "you have 4,990 ash to spend". | **High** |
| P3 | Wanting to spend ash mid-life | There is no shop page. Stats › Character says "bind it with ash at the anchor", but there is no button. | Ash shows in the HUD as a number with no verb attached. | High |
| P4 | Binding the station | The bind offer only appears if the station was built in *that* life. | A life that dies before building it never sees the offer, even with thousands of ash. | Medium |
| P5 | Storage chest | It needs 10 sticks, 4 iron nails and 2 rope at the station. | Never built in 87 simulated lives; the live save has 8 rope and 0 nails converted in total. It is a 200-ash sink nobody reaches. | Medium |
| P6 | "Take control" | The button works for everyone (`session.input` never checks `manual_control`). The `take_control` skill can't be obtained and gates nothing. | Doesn't match the decision that manual control is a later unlock. It could also be a natural ash purchase (see 4). | Medium |
| P7 | Boon text | "Next life: +1 at-once cap for every food source." | Internal wording ("at-once cap"). The active boon isn't shown on the HUD, only deep in Stats › Character. | Medium |
| P8 | Life report | "Blessing 15 - dimensional ash 4990" | Reads like a subtraction. Better: "Blessing 15 · Ash 4,990". | Low |
| P9 | First 90 seconds | The location panel overlaps the vitals bar during the prologue (screenshot). By 90 s into life 1 the header says "Picked over this life: fewer berries around here". | The first message the player reads is a penalty. Hold the picked-over cue until later lives or later minutes. | Low |
| P10 | Journal controls | The live save has 6 encounters at grade 3, but favor and guarantee were never used. | The anchor shows only one small note about them. Powerful, but not found. | Low |
| P11 | How lives end | Sims: 46 boar, 38 starvation, 3 bones (44% starve). Live save: 79 boar, 39 starvation. | Food is still the big killer, and no currency can buy relief from it. That makes it a good candidate for a sink. | Note |

What works well: the skill bar state notes ("Needs 3 sticks (have 0)"), the camp arrow, the log wording, the Character page "What opens as you grow", and the art and sound.

---

## 3. Economy audit

### 3.1 Currency flows today
```
carried items + depth ──(life ends)──► ASH ──► return skill 10 (once)
                                             ├► keep recipe 15–40 (6 total, only in the 30 s window, only if found this life)
                                             ├► bind crafting station 120 (only if built this life)
                                             └► bind storage chest 200 (unreachable in practice)
random prayer (visible tab, once per life) ─┐
roadside shrine / broken altar (shrine path)┴► BLESSING ──► boon 2 (next life only, 2 options)
                                                        └► shrine path 3 (once)
```

### 3.2 Measured (10 seeds × 4 h, bot buys the cheapest available thing every anchor)

| Measure | Value |
|---|---|
| Ash earned | 2.7 per minute of play (median 2.71) |
| Last ash purchase | minute 102–218, median **140** |
| Unspent ash at 1 h / 2 h / 3 h / 4 h | median ~68 / ~72 / ~154 / ~306, still rising |
| Mean life length | 25.6 min |
| Prayers per life | 0.91 |
| Boons bought | 36, all Bountiful path (the bot takes the first one listed) |
| Shrine path bought | **0 / 10** (blessing never reaches 3 because the boon eats it at 2) |
| Storage chest built or bound | **0 / 87 lives** |

Live save (schema 16): life 213, 63 h, **4,990 ash, 20 blessing**, bound buildings: none, boon: none. Converted items in total: 1,238 sticks, 568 thorns, 520 hides, 300 berries.

### 3.3 Diagnosis
1. **Small, capped catalog.** Every ash item is bought once. An idle game needs at least one *repeatable, scaling* sink.
2. **Access gate, not a price gate.** All spending happens in a 30 s window, so players don't spend even when they have the money.
3. **Purchases you can't feel.** Kept recipes only matter if the bot crafts them; binding saves materials invisibly; boons apply next life.
4. **Blessing has no agency on either side.** It comes from a random event and only buys favours you can't see right away.

---

## 4. Recommendations: ash sinks

All of these keep the 2026-10-17 rule: **actions open by dimensional level, never by ash.** Ash passes things on: knowledge, the camp, the soul's reach.

### Step 0: fix access first (biggest win, small work)
- **Anchor tab** (a 5th page or Stats subtab): the same `economy.offers()` rows, usable any time. Permanent things (keep, bind, skills) apply now; boons apply next life. Keep offers stay available until the *next* life ends rather than only during the anchor countdown, so `life_recipes` is cleared one life later.
- **Bind from memory:** list a building as bindable once it has *ever* been built (lifetime flag), not only this life.
- **Away summary:** extend the catch-up toast with ash gained, recipes found but not kept, levels opened, and a "Spend at the anchor" button.
- **Optional auto-keep:** a Settings toggle, "Keep new recipes automatically when I can afford them".

### Repeatable and scaling sinks (pick 2–3)

| Idea | Fit | Cost curve | Work |
|---|---|---|---|
| **Bigger bag**: +1 inventory slot per purchase (12 → 20) | Directly helps hauling, which is the core idle loop; easy to feel | 40, 80, 160 … (×2) | Small: `INVENTORY_SLOTS` → meta field |
| **Starting kit**: begin the next life carrying chosen items (3 sticks, a meal, a staff) | Answers the 44% starvation and "first minutes are slow"; the anchor "returns what you offered" | per life, priced at 3× the item's ash value | Small: reuses item ash values |
| **Practised crafts**: tiers on kept recipes (faster craft, −1 material, then a higher-quality version) | "Ash passes knowledge on", taken one step further | 50 / 150 / 450 per recipe | Medium |
| **More camp buildings to bind**: drying rack (meat lasts, +food at camp), fire pit (a permanent campfire at the anchor), lookout (reveals the map around camp), small shrine (one prayer per life at camp) | Uses the existing `BuildingDef` + bind flow; the camp grows across lives | 80–300 bind each; extend `function` | Medium |
| **Ash summoning** (your planned item summoning): spend ash at the anchor to summon a known item into the next life, at a rising price per summon | It's in the game's name; endless; a natural home for later rarer items | rising per summon in one life, resets at rebirth | Medium–Large |
| **Take control** as a 3rd-slot skill bought with ash (fixes P6) | Matches the "manual control unlocked later" decision | 150 once | Small |
| **Infuse**: turn ash into dimensional XP for one attribute, at a rising rate | Truly endless; still respects "opens by level" | steep, ×1.5 per use | Small, but watch balance (it could replace play) |

**Suggested order:** Step 0 → Bigger bag + Starting kit (cheap, felt right away, absorb the long tail) → camp buildings → ash summoning as the endgame sink.

---

## 5. Recommendations: blessings

### What's unclear today
- **Where it comes from:** a rare unplanned prayer after a task. It never happens offline or in a hidden tab, and that is never said.
- **What it's for:** two boons with internal wording, next life only. The shrine path is listed under "Skills and favours (ash / blessing)" next to ash items.
- **What it did:** the active boon is invisible during play.

### Make it clear (small)
1. HUD tooltip and Character row: "Blessing: earned by praying, which happens only while you watch, and at shrines. Spend it at the anchor." Make "only while you watch" an explicit selling point: blessing is the reward for watching.
2. Show the active boon as a chip on the life line ("✦ Iron skin").
3. Plain boon text: "Next life: one more berry bush, spring and fishing spot can be out at a time."
4. **Shrine path: make it cost 2 or open it by Willpower level**, so the first blessings lead to the only *source* upgrade before the boons compete for them.

### Make it a used feature (pick 1–2)
- **Use it during a life (recommended):** skill slot 3 is "Empty". Make it **Pray for help**: spend 1 blessing for an instant effect such as healing 50, making a boar give up, or a food spot appearing nearby. The auto-pilot can use it when close to death (a policy line, like campfire). It is immediate feedback, teaches the currency, and drains blessing once per life.
- **A real boon shelf:** 5–6 boons with a choice each life. For example: Long breath (hunger −20%), Keen eyes (rare spots ×1.5), Light pack (+3 free carry), Ash-blessed (+25% ash this life), the existing two. One "Ash-blessed" boon ties the two currencies together.
- **Offerings:** at a shrine or the camp shrine, offer ash to raise prayer odds for this life (an ash sink that feeds blessing).
- **Journal favour costs blessing:** a grade-3 guarantee costs 1 blessing per life. This gives the Journal a price and the player a reason to visit it.

---

## 6. Database (Supabase project `dimsum`, eu-west-1)

| Finding | Detail | Suggestion |
|---|---|---|
| One table, `public.dimsum_saves` (id, secret_hash, data jsonb, saved_at, updated_at), with RLS on, no policies, and access only through the RPCs `dimsum_save_game` / `dimsum_load_game` (SECURITY DEFINER, sha256 secret, 1 MB cap, newer-wins) | The design is sound. The advisor WARNs about anon-callable definer functions are expected for this model. | Keep it. Consider a per-IP or per-day insert limit if the link goes public. |
| 55 rows: schema 2–5 = **32 rows (can't load, oldest supported is 6)**, 7–10 = 22, 16 = 1 (the live save) | Dead rows. The live save is schema 16 and the local code is 17, so the next deploy migrates it (16→17 maps `hide_working` etc.). | A one-off cleanup of rows below schema 6, **with your OK** (they are other browsers' saves). |
| Save size: 45 KB stored, about 300 KB raw. `exploration.seen` (fog masks, 243 chunks) = 160 KB raw (54%), `exploration.world` = 115 KB, plus `animations` (static data) saved each time | Grows with chunks explored. It is far from the 1 MB cap but adds upload cost per autosave. | Encode `seen` as base64 bitsets or run lengths; drop static `animations` from the save. |
| No `created_at`; nothing to query for playtest metrics | Answering "how much ash do players hold" takes jsonb digging | A read-only view `dimsum_save_stats` (schema, life, total minutes, ash, blessing, best ring, deaths, bound buildings, boon). |
| The schema SQL lives only in `docs/technical/hosting.md` (one tracked migration) | The database isn't versioned with the code | Add `supabase/migrations/` to the repo. |

---

## 7. Refactoring opportunities (ranked by payoff)

1. **Split `Expedition` state into `Soul` (forever) and `Life` (reset each life).** Today one object holds about 75 attributes across 13 mixins, and `SAVE_FIELDS` lists 60 flat keys. `Expedition.rebuilt()` hand-copies about 20 forever-fields, so each new meta field means editing rebuilt, saves, migrations and the views. With a Soul object, rebirth is `Life.new()`, rebuilt is `Soul` + new world, and an anytime shop only touches Soul. Do this **before** adding sinks.
2. **One view model for meta.** Currencies, unlocks and boons are assembled in `session._meta_view`, `presentation.py` (twice) and `details.py`. Build one `soul_view()` and reuse it.
3. **Split `catalog.py` (1,576 lines).** Move the dataclass schemas and validation into `catalog/defs.py` and the data into `catalog/forest.py`, `catalog/economy.py` (UNLOCKS, BOONS, BUILDINGS, RECIPE_KEEP_COST, a future SINKS) and `catalog/journal.py` (ACHIEVEMENTS). Economy numbers then sit in one short file with `tuning.py`.
4. **Generic offers.** `economy.offers()` has four hand-written blocks (unlock, keep, boon, bind). A small `OfferDef` (kind, currency, cost or cost curve, `repeatable`, a check function) would let bag slots, kits and summons be data, following your "data-driven before more content" rule.
5. **Remove or archive the Phase One idle sim** (`core.py` 1,006 lines, plus `balance.py`, `content.py`, `summoning.py`, `persistence.py`, `equipment.py`, `cli.py` and 5 test files). The world doesn't import it, but it is still built into the hosted bundle and kept in tests.
6. **Stale docs and docstrings:** `autopilot/__init__.py` still says "Ash buys unlocks (new actions)" and "migrations 6 → 9"; `RESOURCE_ECONOMY.md` is missing rope, nails, fish, cloth, coins, spear and axe; `docs/technical/world-ledger-P*.md` are history. Refresh or move to `docs/archive/`.
7. **Vestigial `take_control` skill:** either gate the button on it (and sell it) or delete it, along with the `SKILLS` constant and `--unlock-control`.
8. **Save compaction** (see 6): fog bitsets and no static animations.
9. **`app.js` (716 lines)** owns state, polling, rendering and input. Split out an `input.js` and a `pages_dom.js` the next time the UI is touched.

---

## 8. Proposed next phases (for your OK)

| Phase | Contents | Size |
|---|---|---|
| A | Soul/Life split + one meta view (refactors 1–2), no gameplay change | M |
| B | Anchor tab + longer keep window + bind from memory + away summary (Step 0) | S–M |
| C | Blessing clarity (tooltips, boon chip, plain text, shrine path at 2) + **Pray for help** in slot 3 | S |
| D | Repeatable ash sinks: bigger bag + starting kit, via a generic `OfferDef` | M |
| E | More camp buildings; chest recipe made reachable (nails from logging camps) | M |
| F | Ash summoning (endgame sink) | L |
| G | Database: stats view, migrations folder, save compaction, cleanup of old rows (with your OK) | S |

Re-measure after B and D with `tools/measure_lives.py` and the shopper bot used here (`sims/econ.py`, minutes 240). Targets: unspent ash at 4 h below 100, and at least one blessing spent every life.
