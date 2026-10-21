# The story: bible, chapter 1 and the grey wall (2026-10-22)

## Andrew's request

- Explain the lore before the anchor shop.
- Add a main quest: chained actions in the world that tell the main story.
- Autoplay makes the hero stronger. At some ring a wall blocks the way, and only the quest
  opens it.
- Past the wall, old portals lead to other locations. Relics activate them.
- New locations have stronger enemies and longer actions, and may need summoned gear.

## Story bible (one page)

**The central question.** Why is this land closed in, and what are you now?

**History.** The player learns it in pieces and never all at once.
- This land once had **summoners**. They cut stone **gates** (rings of standing stones) to call
  help from other lands. They cut **anchors** (waystones) to call their own people back from death.
- One night the gates would not close, and things came through. The **pale lights** (wisps) are
  some of them. The **restless dead** at the mounds are summoners who fell holding the gates.
- The last summoners did two things:
  - They raised the **grey wall**, a ring of cold mist around the whole land.
  - They pulled the **keystones** out of the gates and carried each one away to another land, so
    no gate could be opened from one side alone.
- The **wall watch** kept towers along the old road (the fallen watchtowers). Its "scratched
  warnings" are their log.
- The **old carvings** on the road are summoners' marks. They all point out, towards the gates.
- One anchor was left asleep under the old road, in case a summoner ever rose again.

**You.**
- A traveller killed by bandits on the old road.
- *Something answered* the sleeping anchor, and the anchor bound that something to the body.
  That something is the player: the presence that can take the avatar's hands (possession).
- **Open thread:** who answered? It is never stated. Chapter 3 or later.

**Why the mechanics are what they are.**
- **Death:** the anchor calls the body back. What it carries cannot cross with it, so it burns to
  **dimensional ash**.
- **Ash:** the only thing the anchor can hold. That is why ash buys what outlasts a life (kept
  crafts, bound buildings, contact).
- **Rings:** the further from the anchor, the closer to the wall. More of what came through still
  roams there, so danger grows ring by ring.
- **The wall:** it lets through only what an anchor can call back. Only an avatar can pass, and
  only with a strong enough will (Willpower).
- **Summoning:** the title. The avatar relearns the summoners' art through the story. Summoned
  gear is the reward of chapter 2 and the key to the next lands.

**The gods.** Forest folk believe the gods spared you, and roadside shrines still take prayers.
The old man says plainly that it was not the gods but the stone. Both stay true to their speakers.

**Voice.** Everyday words, short sentences.
- Named things: the anchor, the grey wall, the old man, the gate, keystones, summoners.
- No invented proper nouns until a name earns its place.

## Chapter 1: The grey wall (built)

Each step:
- is a **story place**: a `placement="story"` action;
- appears **for sure** once it is the current step and its gate holds;
- is **kept across deaths**: its knowledge is permanent;
- glows gold in the world and on the minimap;
- logs its lore and keeps it on Journal › Story.

| # | Story place | Where | Gate (grown by autoplay) | What the player learns |
|---|---|---|---|---|
| 0 | Opening (anchor, 4 beats) | anchor | none | anchor, avatar, possession, ash and what it buys, the closed land, the old man |
| 0 | Prologue (existing; lines rewritten) | anchor | none | ambush, not the gods but the stone, possession, hunger, the old man's camp |
| 1 | The old man's camp | rings 1-3 | none (life 1) | the marks on the road were cut by the anchor's makers |
| 2 | Summoner's mark | rings 2-5 | Road lore (Endurance 3) | every mark points outward |
| 3 | Wall watchers' post | rings 4-5 | reach ring 4 | the wall, the watch, dark gates, taken keystones |
| 4 | The grey wall | ring 5 (the wall) | reach the wall | the wall is real and pushes back like the anchor |
| 5 | The old man | rings 1-2 | step 4 done | the whole history, and how to pass the wall |
| 6 | The grey wall (crossing) | ring 5 | **Willpower 3** | the wall opens for good |
| 7 | Dead gate | rings 6-7 | the wall is open | three empty keystone sockets; next: find the keystones |

**Gates in data.** Growth gates use the existing rules:
- `unlock` (dimensional levels);
- the new `Requirement("level", attr, n)`, which now reads dimensional levels;
- rings, through the frontier.

**Why these gates.** In the baseline cohort below, Endurance 3 arrives at 1.7-3.1 h and Willpower 3
at 3.2-4.4 h. The chapter therefore spans roughly the first 4-5 hours, with a beat every 30-90 min.

## The grey wall (built)

- **Data.** `catalog.WALLS["forest"] = WallDef(ring=5, opened_by="wall_open")`. It is per
  dimension, so every later land gets its own wall.
- **Movement (`runtime._step_target`).** While closed, a step never enters a chunk past the wall
  ring. The same rule is in the auto-pilot's movement graph (`navigation._can_move`), so paths
  never try. Stepping inward is always allowed, so a save already standing past the wall is never
  stuck.
- **Frontier.** `frontier()` is clamped to the wall ring while the wall is closed.
- **Client (`story_ui.js drawWall`).** Grey mist over every chunk past the wall, and drifting `~ : .`
  glyphs along the wall line. After it opens, only a faint haze stays at the line. The minimap
  greys those chunks out.
- **State.** The limit comes from knowledge and is never saved (like weapon reach). No save
  schema change.

## Where the wall goes, and why ring 5: measurements

**Baseline, before any story code.** Current main, 6 seeds × 10 h, autopilot, `spend` policy at
each anchor, 130 lives.

| Hours | Lives | Median deepest ring | Reached ring 6 | Reached ring 7 |
|---|---|---|---|---|
| 0-2 | 25 | 5 | 36% | 4% |
| 2-4 | 35 | 5 | 34% | 3% |
| 4-6 | 25 | 5 | 48% | 12% |
| 6-8 | 25 | 6 | 52% | 0% |
| 8-10 | 20 | 5 | 35% | 0% |

- **Overall:** deepest ring 2:1, 3:7, 4:19, 5:50, 6:48, 7:5.
- **Deaths:** starvation 65, boar 36, wolf 26.
- **The plateau:** dimensional levels roughly double over the 10 h (Strength 6 → 11), yet the
  deepest ring stays flat at 5-6. Danger grows ×1.5 per ring, and that outruns stat growth.
  Autoplay alone never gets meaningfully past ring 6.

**Why ring 5.** It is the ring most lives reach (85% reach 5 or deeper). The first ring past it
(6) is where autoplay stalls. So the wall stands just inside the natural ceiling, and the land
past it really is harder.

**Why not ring 6.** Then the gate would sit at ring 7. Only 4% of lives reached 7, and none after
hour 6, so the chapter would never end for most players.

**Verification cohort, with the story.** The same 6 seeds, about 7.5 h each, same policy.

| Seed | Mark | Watch post | Wall | Old man | Crossing (Willpower 3) | Gate: chapter done |
|---|---|---|---|---|---|---|
| 1 | 84 min | 90 | 105 | 109 | 218 | 228 |
| 2 | 166 | 168 | 173 | 178 | 239 | 240 |
| 3 | 131 | 134 | 146 | 149 | 215 | 218 |
| 4 | 78 | 89 | 92 | 95 | 133 | 179 |
| 5 | 81 | 81 | 81 | 82 | 179 | 295 |
| 6 | 68 | 68 | 68 | 70 | 172 | 181 |

- **Chapter 1:** every seed finished it, in 3.0-4.9 h. The camp is found at about 1 min of life 1.
- **The two waits:** the long ones are Road lore (the mark) and Willpower 3 (the crossing). Both
  are plain growth gates, shown in the HUD as "Waiting: needs Willpower 3 (now 2)".
- **The wall held:** seconds spent past the closed wall were 0 on every seed.
- **Economy is unchanged.** Ash and total dimensional levels at matched times, story vs baseline:

  | Time | Ash | Total dimensional levels |
  |---|---|---|
  | 2 h | 223 vs 214 | 18.2 vs 16.7 |
  | 4 h | 464 vs 476 | 30.3 vs 30.0 |
  | 6 h | 703 vs 666 | 38.2 vs 36.5 |
  | 7.5 h | 861 vs 860 | 42.0 vs 40.8 |

  Holding lives at ring 5 for the first hours costs nothing measurable.
- **Deaths:** starvation fell from 48 to 35 (boar 30 → 38).
- **After the wall opens:** lives reach rings 6-8 as before (6: 23, 7: 6, 8: 1 of 62 lives).

## Opening (built)

- **New games (`anchor_space.kind == "opening"`).** The anchor speaks in four beats before the
  shop shows (`anchor_ui.js ANCHOR_TEXT.opening.beats`).
- **What each beat sets up:**
  1. who it is;
  2. the body and possession;
  3. death, ash and what ash buys (this is when the shop appears);
  4. the closed land and the old man.
- **Mechanics.** Beats are client-only (Continue 1/4 … 4/4); nothing is asked of the server. A
  reload during the beats starts them again, which is harmless.
- **The old man (prologue).** His lines no longer tell you to worship the gods. He names the
  stone and points you to his camp, which is step 1.

## Phase 2 spec: keystones, gates and the second land (not built; needs Andrew's OK)

### Chapter 2: The keystones

1. **The summoner's tomb** (ring 6-7, past the wall).
   - A guarded story site: a summoner's barrow with a strong guardian.
   - It needs gear or possession to win.
   - Reward: the first **keystone** (a relic) and the summoner's last notes, which teach **summoning**.
2. **Summoning.**
   - The anchor offers "Learn summoning" (the contract in CARRYOVER_AND_SUMMONING.md).
   - Summoned gear persists across lives and changes rules (action speed, load relief, sight), not
     flat damage.
3. **The gate wakes.**
   - Set the keystone in the dead gate. One socket lights; skill 3 (today the locked "Dimensional
     Shift") becomes **Step through**.

### Relics

- New item kind `relic`.
- Never converted to ash.
- Moved to the anchor's keeping (`Expedition.relics`, permanent) the moment it reaches camp, or at
  death if it is carried.
- A gate's socket names the relic it takes and the land it opens: `GateDef(id, dimension, ring,
  sockets={socket: (relic, destination)})`.

### The second land

- **Dimension and biome.** A new `DimensionSpec` in the same world, `ash_plain`. Its terrain
  already exists; it has no content yet.
- **Arrival and death.** The avatar arrives at that land's gate. Death still returns it to the
  forest anchor; the gate stays lit, so going back costs a walk.
- **Its own wall.** `WALLS["ash_plain"]`, opened by chapter 3.
- **Stronger enemies.** Two new `BiomeDef` fields:
  - `base_hit_percent` (for example 180%) on top of the ring curve;
  - `base_hp` added to every fight.
- **Longer actions.**
  - `BiomeDef.duration_percent` (for example 250%) stretches every action there.
  - Summoned gear's action speed effect is what brings it back to a playable pace.
  - Same check as the frontier: "a typical action takes no more than about 3× forest time with
    starter summoned gear".
- **Save changes.**
  - World save: add the dimension to the pinned specs; migrate older worlds by appending it, so
    forest chunks are unchanged.
  - Expedition save: `relics`, lit `gates` and `dimension` (already saved).

### Decisions needed from Andrew before phase 2

1. **Death in the second land:** back to the forest anchor (proposed), or a second anchor there?
2. **Keystones:** permanent once found (proposed), or one-use?
3. **Summoning:** keep the 1,000-ash gate from CARRYOVER_AND_SUMMONING.md, or make the tomb's
   notes teach it, with ash paying only for pulls?
4. **Original ambush text:** the original from the earlier game should replace the placeholder
   memory lines if it still exists.

## How we know it is right

- **Cohort.** With the story, every seed:
  - reaches the wall;
  - finishes chapter 1 inside about 6 h;
  - never stands past the closed wall;
  - keeps ash and levels near the baseline at matched hours (the wall should not starve the
    economy).
- **Tests.** `tests/test_world_story.py` covers:
  - placement for sure;
  - lore;
  - persistence through death and reload;
  - exact replay;
  - requirement reasons;
  - the runtime and frontier wall, including stepping back in.
  
  `tests/browser_story.test.mjs` covers the HUD line, the wall edges and the opening beats. Both
  full suites must pass.
- **Cold read (people, not us).** A friend who has never seen the game plays the opening and the
  first 10 minutes. Then they answer:
  1. Why are you here?
  2. What is ash?
  3. What happens when you die?
  4. What should you do next?
  5. What is the grey wall?

  Three or more right answers means the opening works.
