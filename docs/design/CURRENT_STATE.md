# Current state audit (before the closed-loop iteration, 2026-10-05)

Source of truth: the code at commit `373ea93` (main) plus local Codex edits up to 2026-10-04 23:04 UTC.
Docs were not trusted; every statement below was checked in code or by running seeded simulations.

## Game loop as implemented
- **What the player does:** watches. The auto-pilot (`world/autopilot.py`, 1,180 lines) walks, performs spots,
  fights and eats. The only player decisions were at the anchor between lives: offer whole item stacks for
  "dimensional dust" or begin the next life. Manual control is a locked skill with no unlock path.
- **Pressure:** hunger drains 0.75/s; eating waits until 40/100; boars pursue within 6 cells. Danger grows x1.5
  per ring from the anchor.
- **Decisions:** none during a life. At the anchor: which stacks to offer.
- **Progression:** regular XP (resets) speeds actions; dimensional XP (20%, persists) speeds them in later lives.
- **Death:** starvation (measured: ~100% of lives, see below) or a boar.
- **After death:** 30 s anchor interlude; unoffered items are lost; dust accumulates.
- **Motivation for another run:** only dimensional XP. Dust and blessing had **no sink**.

## World generation as implemented
- WORLD seed -> one DimensionSpec `forest` with one biome `dark_forest` (`web.new_world`); the `ash_plain`
  biome exists in `open_terrain.open_assets` and `assets.py` but is unreachable (no pool, not in the spec).
- Chunks 32x16 from the `open-terrain-v1` recipe: one terrain recipe, so **one environment** everywhere.
- Each chunk: one asset `enemy` spawn (runtime Target) - **always zeroed** by `Expedition._screen` (hp=0).
- Spots: `encounters.chunk_spots` rolls `(0,0,1,1,2,2)` spots per chunk from a 12-entry weighted pool.
- Spawn windows: at each life start, each limited action rolls an at-once cap; `bramble_berries (0,1)`,
  `gnarled_tree (0,1)`, `moonlit_pool (0,1)`, `bramble_boar (1,1)` weight 4/126.
- No region/location layer, no POI structure beyond spots, no context-dependent eligibility.

## P0 regression: food and enemies missing (reproduced)
Seeds 1-8, 20 simulated minutes each (`/tmp` audit script, kept as `simulate` today):

| seed | lives (min) | food spots seen in 20 min | boars seen | (berries, tree, boar) caps per life |
|---|---|---|---|---|
| 4 | 4.4 3.8 3.9 4.3 | 9 | 6 | (1,1,1) (0,1,1) (0,0,1) (0,0,1) |
| 7 | 4.6 3.8 4.2 4.1 | 7 | 4 | (1,0,1) (0,0,1) (0,0,1) (1,0,1) |
| 8 | 3.9 4.0 3.9 4.1 3.9 | **1** | 6 | (0,0,1) (0,0,1) (0,1,1) (0,0,1) (0,0,1) |

Root causes (not probability alone):
1. **Spawn windows with low = 0** (`encounters.py`): `(0,1)` rolls 0 half the time, which disables the action
   for the entire life. When berries and trees both roll 0 (25% of lives) the only food is a boar.
2. **Filtering removed every generated enemy:** `_screen` sets every asset-spawned boar to hp 0. Enemies came
   only from boar spots at weight 4/126 x ~1 spot/chunk, capped at 1 at once.
3. **Count table** `(0,0,1,1,2,2)` made a third of chunks empty.
4. Combined with drain 0.75/s and eat-at-40, every life starved at ~4 min regardless of play; the run was
   effectively deterministic death by hunger.

## Content inventory (before)
| Kind | Content | Reachable? |
|---|---|---|
| Biomes | dark_forest; ash_plain | ash_plain unreachable |
| Locations/regions | none | - |
| Spots (POIs) | berries, branches, tracks, gnarled tree, spring, mossy stone, carvings, abandoned camp, moonlit pool, fallen watchtower, mushroom ring, boar | yes |
| Structures | anchor camp, ambush wagons (decor) | decor only |
| Enemies | bramble boar | spot only; asset boars removed |
| Items | berries, egg, boar meat, stick, thorn, hide | materials had no in-run use |
| Self actions | think, contemplate (no reward), prayer (4%, visible only) | yes |
| Currencies | blessing, dust | **no sinks** |
| Unlocks | `take_control` skill | no unlock path |
| Ash | - | not implemented anywhere |

## Loop dead ends found
- stick / thorn / hide -> nothing during life -> dust at death -> dust -> nothing.
- prayer -> blessing -> nothing.
- XP -> speed only; no change in possibilities between lives.

## Visual findings (audit agent, rendered in headless Chromium)
- Player walk: hands moved without outline, crossing legs left 1 px slivers, profile cloak detached, fills
  drawn under fractional camera transforms (186-219 blended colours per frame) -> "detached pixels".
- Crouch used `ctx.scale(3,2)`; working arms started at head height.
- Ambush wagons: free-drawn polygons/circles/rotations, antialiased, no outline - inconsistent with the
  outlined 4x7 cell sprites used by every other prop.
