# The story: bible and chapter 1 (2026-10-22)

## Andrew's request

- Explain the lore before the anchor shop.
- Add a main quest: chained actions in the world that tell the main story.
- Autoplay makes the hero stronger. At some ring a wall blocks the way, and only the quest
  opens it.
- Past the wall, old portals lead to other locations. Relics activate them.
- New locations have stronger enemies and longer actions, and may need summoned gear.

## Story bible (one page)

**The central question.** What are you now, and what were the gates?

**Revised 2026-10-22 (Andrew).** The grey wall is gone. It made no sense: the bandits who killed
the traveller were here, so nothing had sealed the land. The forest is bounded by plain geography
instead: impassable thicket, fallen trees across a road, a broken bridge (`edges.py`,
docs/design/FIRST_LAND_REVIEW.md). Other lands are reached only through the old gates.

**History.** The player learns it in pieces and never all at once.
- This land once had **summoners**. They cut stone **gates** (rings of standing stones) to call
  help from other lands. They cut **anchors** (waystones) to call their own people back from death.
- One night the gates would not close, and things came through. The **pale lights** (wisps) are
  some of them. The **restless dead** at the mounds are summoners who fell holding the gates.
- The last summoners pulled the **keystones** out of the gates and carried each one away to
  another land, so no gate could open again.
- The **old carvings** on the road are summoners' marks. They all point the same way: to the gate.
- One anchor was left asleep under the old road. A god found it and used it (below).

**You (Andrew, 2026-10-22): the player is a god.**
- The god bound the soul of a traveller, killed by bandits on the forest road, to a **dimensional
  anchor**. That body is the avatar.
- The god watches the avatar live on its own (autoplay). The god can also take its hands for a
  while (possession).
- The avatar **cannot die**. When it falls, the anchor pulls it back and its life begins again from
  the start.
- **All past lives shape the new one:** dimensional experience, kept crafts, bound buildings, ash.
- The anchor does not speak; the opening is narration to the god.
- **Open thread:** why this god, and why this traveller. Chapter 3 or later.

**Why the mechanics are what they are.**
- **Death:** the anchor calls the body back. What it carries cannot cross with it, so it burns to
  **dimensional ash**.
- **Ash:** the only thing the anchor can hold. That is why ash buys what outlasts a life (kept
  crafts, bound buildings, contact).
- **Rings:** the further from the anchor, the wilder the forest, so danger grows ring by ring.
- **Summoning:** the title. The avatar relearns the summoners' art through the story. Summoned
  gear is the reward of chapter 2 and the key to the next lands.

**The gods.** Forest folk pray at roadside shrines. The old man knows what he saw: a god took the
traveller back from death and bound him to the anchor stone.

**Voice.** Everyday words, short sentences.
- Named things: the anchor, the old man, the gate, keystones, summoners.
- No invented proper nouns until a name earns its place.

## Chapter 1: The dead gate (built; reworked 2026-10-22)

Each step:
- is a **story place**: a `placement="story"` action;
- appears **for sure** once it is the current step and its gate holds;
- is **kept across deaths**: its knowledge is permanent;
- glows gold in the world and on the minimap;
- logs its lore and keeps it on Journal › Story.

| # | Story place | Where | Gate (grown by autoplay) | What the player learns |
|---|---|---|---|---|
| 0 | Opening (anchor, 4 beats) | anchor | none | anchor, avatar, possession, ash and what it buys, the closed land, the old man |
| 0 | Prologue (existing; lines rewritten) | anchor | none | ambush, a god and the stone, possession, hunger, the old man's camp |
| 1 | The old man's camp | rings 1-3 | none (life 1) | the marks on the road were cut by the anchor's makers |
| 2 | Summoner's mark | rings 2-5 | Road lore (Endurance 3) | every mark points deeper in |
| 3 | The old man | rings 1-2 | step 2 done | summoners, gates, keystones; one gate still stands in these woods |
| 4 | Dead gate | rings 4-6 | **Willpower 3** | three empty keystone sockets; next: find the keystones |

## Where the land's edge goes, and why ring 5: measurements

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

**Why ring 5 (lobes into 6).** It is the ring most lives reach (85% reach 5 or deeper), and
ring 6 is where autoplay stalls. So the land ends where autoplay levels off, and the whole land
stays worth exploring.

**Verification cohort, with the story and the old grey wall** (superseded; kept for the record).
The same 6 seeds, about 7.5 h each, same policy.

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

## Opening (built; revised 2026-10-22)

- **New games (`anchor_space.kind == "opening"`).** Everything starts in darkness, then:
  - the anchor stone fades in slowly (about 5 s);
  - the bound body fades in with the second beat;
  - the shop appears after the fourth beat.

  The art is `anchor_ui.openingReveal` and `story_ui.drawOpeningDark`.
- **Beats.** Narration to the player-god, not words of the anchor:
  1. darkness, and a stone that is yours;
  2. this is the dimensional anchor; you bound a dead traveller's soul to it; through that body you
     walk this world and can take its hands;
  3. the body cannot die: when it falls, the anchor pulls it back and its life begins again;
  4. nothing is lost: every past life shapes the next (what it learned stays, what it carried
     becomes ash for what lasts).
- **Mechanics.** Beats are client-only. Reduced motion skips the fade.
- **The old man (prologue).** A god took you back from death and bound you to the stone. That god
  looks out through your eyes. He points you to his camp, which is step 1.

## Phase 2 spec: keystones, gates and the second land (not built; needs Andrew's OK)

### Chapter 2: The keystones

1. **The summoner's tomb** (a placed landmark inside the land).
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
- **Its own edge.** A `LandDef` for its dimension, with its own edge features (cliffs, ash drifts).
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

- **Cohort.** With the story, every seed finishes chapter 1 within the measured hours; no avatar
  ever stands in a closed chunk; ash and levels stay near the baseline.
- **Tests.**
  - `tests/test_world_story.py`: placement for sure, lore, persistence through death and reload,
    exact replay, requirement reasons.
  - `tests/test_world_edges.py`: the edge is ragged, every open chunk is reachable, sealed sides
    have no exits, roads end in fallen trees or a broken bridge, and the land catalog is pinned.
  - `tests/browser_story.test.mjs`: the HUD line, the story cards and the opening beats.
- **Cold read (people, not us).** A friend who has never seen the game plays the opening and the
  first 10 minutes. Then they answer:
  1. Why are you here?
  2. What is ash?
  3. What happens when you die?
  4. What should you do next?

  Three or more right answers means the opening works.
