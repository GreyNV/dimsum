# The first land: what is there today, and how to make it systematic (review, 2026-10-22)

All numbers and tables below come from the catalog and from generated worlds (8 seeds). They are
not from memory.

## 1. The land's edge (built today; replaces the grey wall)

- **Size.** The forest can be explored to ring 5 everywhere. Parts of ring 6 can be reached too,
  where a 3×3 region cell rolls under 45%, so the outline is ragged. There are no single-chunk
  corner islands.
- **How it closes.** Past the edge the land closes itself (generator v7, `edges.py`, pinned per
  world as `LandDef`):
  - **Impassable thicket:** a ragged band, 2-4 tiles deep, of trees and boulders along every
    closed side.
  - **Fallen trees** ("K") where a road runs into the edge.
  - **A broken bridge** ("Y") where a road crosses a river at the edge.
  - A trail running *along* the edge stays open. Only the step out is closed.
- **Checks.**
  - Every reachable chunk connects to the anchor: 10 seeds checked, and covered by a test.
  - Sealed sides have no exits. Asset validation now allows a chunk without exits on a side.
- **Existing worlds.** They regrow with the edge at their next life, through the usual
  generator-upgrade path ("the forest grew back in a new shape").
- **No lore.** The edge is plain geography. The bandits live inside the forest; nothing claims
  the land was sealed.

**Measured** (8 seeds): 130-154 reachable chunks. Region share: Old Road 33%, Deep Woods 30%,
Still Glade 22%, Bramble Thicket 16%.

## 2. Biomes

| Biome | Danger growth | Content |
|---|---|---|
| Dark forest | ×1.5 hit per ring, +1 HP per ring | everything below |
| Ash plain | same | terrain only; no encounters, no regions; mastery ×3 (reserved for the next land) |

**Finding:** "biome" holds almost nothing today. Danger, regions, landmarks and encounters are all
forest-only. In practice the biome *is* the land. In the systematic model (section 7) a land owns
its biomes and each biome owns its regions.

## 3. Regions and what a spot rolls

The share of each encounter per spot draw, with every unlock open:

| Region | Dry ground | Beside a river (adds) |
|---|---|---|
| **The Old Road** | Berry bush 16, Fallen branches 16, Old tree 12, Spring 11, Old carvings 11, **Roadside shrine 9**, Mossy rock 9, Clear pool 8, Boar 7 | Fishing pool 7, Reeds 6, Net 5, Shallows 3, Lurker 2, Backward ripple 2 |
| **Deep Woods** | Fallen branches 19, Boar 15, Old tree 14, Animal tracks 12, **Mushrooms 11**, Clear pool 8, Carvings 8, Mossy rock 5, Berries 4, Spring 4, Hanging leaf 2 | same water set |
| **Bramble Thicket** | Berry bush 31, Fallen branches 22, Boar 10, Old tree 10, Clear pool 8, Carvings 8, Mossy rock 7, Spring 5 | same water set |
| **Still Glade** | Clear pool 23, Spring 17, Animal tracks 15, Mossy rock 14, Berries 10, Old tree 9, Carvings 8, Boar 3, Hanging leaf 2 | same water set |

**Findings:**
1. **Regions only re-weight one shared pool.** Ten of the thirteen dry-ground encounters can roll
   in every region. Only the roadside shrine (Old Road) and mushrooms (Deep Woods) belong to one
   region.
2. **The uncommon tier flattens identity.** Old carvings and the clear pool are about 8% in
   *every* region, because a tier's odds do not depend on the region.
3. **Wasted weights.** Still Glade weights `follow_deer_tracks` and `hunt_deer`, which are leads, so
   those spot weights do nothing. The Old Road's `mushroom_ring` weight has no effect either,
   because mushrooms are Deep Woods only.
4. **Rivers are a good overlay.** One set of water encounters is added beside water in every
   region. Keep it.

## 4. Landmarks (sites) inside the reachable land

| Landmark | Regions (per mille) | Min ring | Found per land (mean of 8 seeds) | Seeds with none |
|---|---|---|---|---|
| Abandoned camp | Road 350, Woods 150, Thicket 150, Glade 100 | 2 | 2.3 | 2 of 8 |
| Logging camp | Woods 200, Road 100 | 2 | 1.6 | 1 of 8 |
| Fallen watchtower | Road 300, Woods 150 | 3 | 1.5 | 2 of 8 |
| Hunter's cabin | Thicket 250, Woods 150 | 3 | 0.6 | **4 of 8** |
| Ruined shrine | Glade 250, Woods 100 | 4 | 0.8 | **4 of 8** |
| Burial mound | Thicket 150, Woods 100, Road 50 | 5 | 0.6 | **4 of 8** |

**Finding at the time of the review:** with generator v7, landmark luck decided whole systems:
- the spear recipe and snare traps (hunter's cabin);
- the altar (ruined shrine);
- the restless bones and their spoils (burial mound).

In half the sampled worlds the player never saw them. **Implemented in generator v8:** natural
rolls remain, then each missing landmark kind is placed once in a reachable chunk of
the bounded land. A preferred region is used where possible; an exceptional layout may use
another region or replace a duplicate site. Existing v7 worlds retain their pinned layout until rebirth. The land stays
at rings 5-6; adding another biome or enlarging the map is a separate content decision.

## 5. Encounter chains, enemies, gates

- **Chains (leads).**
  - Branches → cut wood.
  - Berries → feeding ground or angry boar.
  - Mushrooms → rotten log.
  - Tracks → deer.
  - Carvings → looping path (reveals the map).
  - Backpacks → map → stash.
  - Riverside → busy pool, lurker burrow, fishing platform, fishing camp, hidden ford.
  - Mossy rock → double shadow → split-shadow tree (rare finds ×2.5 for the life).
- **Enemies.**
  - Boar (anywhere).
  - River lurker (water).
  - Restless bones (mounds, watchtower guard).
  - Pale wisp (shrine; drains hunger).
  - Wolf (night raids; grows with the deepest ring of the life).
- **Growth gates (dimensional levels).**
  - Climbing: Strength 2.
  - Scavenging: Perception 2 (camps).
  - Snares: Perception 3 (cabin).
  - Meditation: Endurance 2 (stones, pools, shrine).
  - Mushroom lore: Perception 4.
  - Road lore: Endurance 3 (carvings, watchtower, mound).
  - Shrine path: Willpower 3.

## 6. Main quest and lore as they stand now

The grey wall and everything written around it is removed: its steps, the watch log, the crossing,
and the summoners "raising a wall".

**What remains:**
- **Opening (anchor, 4 beats, narrated to the god).** Darkness, then your stone. The dimensional
  anchor, and the traveller's soul you bound to it. The body cannot die: it returns and begins
  again. Every past life shapes the next.
- **Prologue.** Ambush memories (still placeholders until your original text). The old man:
  - a god took you back and bound you to the stone;
  - that god looks through your eyes, so let it take your hands;
  - mind your hunger;
  - find his camp, there's much to know about these woods.
- **Chapter 1, "The dead gate"** (4 steps, guaranteed, kept across deaths):
  1. The old man's camp (rings 1-3): his notes and a rubbing of the anchor's carvings.
  2. Summoner's mark (rings 2-5, needs Road lore / Endurance 3): the marks point deeper in.
  3. The old man (rings 1-2): summoners made gates and anchors; the gates would not close; wisps
     and the restless dead came through; the keystones were carried to other lands; one gate still
     stands in these woods.
  4. Dead gate (rings 4-6, needs Willpower 3): three empty keystone sockets. "Find the
     keystones."
- **Loose ends to settle with you.**
  - **The god.** Roadside shrine text says the avatar "prayed to the gods who spared you", but the
    player *is* that god now. What does a shrine mean to the avatar of a god?
  - **The bandits.** They ambushed the traveller and live in this forest (abandoned camps?), but
    are never met.
  - **The old man.** He has no name and no reason to know what he knows.
  - **The scratched warnings** at the watchtower now warn about nothing.

## 7. Proposal: one systematic shape for every land

```
Land (dimension: edge rings, edge features, mastery scale, danger)
 └─ Biomes (ground rules: danger growth, action duration %, enemy strength)
     └─ Regions (share of the land; trees; canopy)
         ├─ signature encounters: only here (2-3)
         ├─ shared encounters: the biome's commons, re-weighted
         ├─ landmarks: placed by quota per land, each with its own encounters and guard
         └─ overlays: rivers, roads (their own encounters wherever they run)
 └─ Edge features: thicket / deadfall / broken bridge, or the land's own (cliff, ash drift)
 └─ Story: the land's chapter, its gate and keystone
```

**For the forest, a first cut:**

| Region | Signature (only here) | Landmarks placed |
|---|---|---|
| Old Road | old carvings, roadside shrine, wagon wreck (new: rope, nails, coins) | abandoned camp ×2, fallen watchtower ×1 |
| Deep Woods | mushrooms, old tree, animal tracks | logging camp ×1, burial mound ×1 |
| Bramble Thicket | berry bush (big), boar den (new fight + hides) | hunter's cabin ×1 |
| Still Glade | clear pool, mossy rock, spring | ruined shrine ×1, the dead gate (story) |

Shared commons (all regions, low weight): fallen branches, berries (small), boar.

**What this needs in code** (small, all data-driven):
- landmark minimums per bounded land (built in generator v8: existing per-chunk rolls remain,
  with one deterministic placement for each kind still missing);
- per-region tier odds (uncommon and rare picked from the region's own pool);
- a `signature` flag that makes an encounter's other-region weights zero;
- a validation that every region has at least 2 signatures and the land holds every landmark kind
  it lists.

## 8. Next land (after this one is settled)

- **Land:** the ash plain behind the dead gate, reached when the first keystone is set. It gets
  the same table: its biomes and regions, signatures, landmark quotas, edge features (ash drifts,
  cliffs), mastery ×3, longer actions, stronger enemies, and the summoned-gear dependency.
- **Chapter 2:** the keystone.

## Decisions for Andrew

1. Adopt the land → biome → region → signature/landmark structure and the forest table above (or
   change it)?
2. For a future land, should each landmark kind have only the one guaranteed placement, or
   should some kinds have a larger minimum? The forest currently guarantees one of each.
3. Lore: who are the bandits and the old man, and what is a shrine to a god's avatar?
4. Edge: ring 5 with ragged lobes into 6 (now), or another size?
