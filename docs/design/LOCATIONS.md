# Places: mastering locations, and making camp (2026-10-22)

## Andrew's direction

- Mastery belongs to **locations**, not to single actions. Examples: the old camp, old ruins, the
  road, the forest.
- Once a location is mastered, a camp can be made there, by the avatar or by the player through
  the avatar. The camp keeps the avatar exploring inside that location.
- The player chooses what the avatar concentrates on there: gathering resources (wood and so on),
  or exploring the place itself.
- The camp is not bought; mastering the place is what allows it.
- The first locations are easy to master. Lands reached later through the portals need more.

Decisions (2026-10-22):
- A location is a **kind of place**: mastering "Abandoned camp" counts for every abandoned camp.
- **The camp is the campfire**: it can only be lit in a mastered place, and it holds the avatar to
  that place.
- **Per-encounter mastery is replaced.** Journal favor/suppress/guarantee became the camp focus.

## The places (`catalog.LOCATIONS`)

| Place | Kind | Members | Grades (encounters: known / mastered / deep) |
|---|---|---|---|
| The Old Road, Deep Woods, Bramble Thicket, Still Glade | region | one region each | 10 / 40 / 400 |
| Abandoned camp | landmark | abandoned camp | 3 / 12 / 60 |
| Logging camp | landmark | logging camp | 3 / 12 / 60 |
| Hunter's cabin | landmark | hunter's cabin | 3 / 12 / 60 |
| Old ruins | landmark | fallen watchtower, ruined shrine, burial mound | 3 / 12 / 60 |

- **What counts where.** Wild spots and leads count for the region of their chunk; landmark
  encounters count for their landmark. Fights count too.
- **Lifetime.** Counts last forever: every past life shapes the next.
- **Later lands.** Thresholds are multiplied by the biome's `BiomeDef.mastery_percent`. The dark
  forest is 100; the ash plain, reserved for the land behind the first gate, is 300.
- **Why these numbers.** Measured on seed 3 over 5 h before the change:
  - about 100 encounters an hour on the Old Road, so it is mastered in the first life (about 15 min);
  - 25-90 an hour in the other regions, mastered in about 1-2 h;
  - 5-10 an hour at landmarks, mastered in about 2-4 h.

**Grades:**
1. **Known.** The Journal shows where that place's encounters appear and how often.
2. **Mastered.** A camp can be made there. The player picks the camp's focus.
3. **Deep.** Rare and uncommon finds there are 1.5× as likely (`LOCATION_DEEP_RARITY_PERCENT`).

## The camp

- **Making camp.** The campfire action is renamed "Make camp" (3 sticks). It is allowed only where
  the place the avatar stands in is mastered: `Requirement("location", "here", 2)`. Inside a
  landmark's clearing, the landmark counts; elsewhere, the region.
- **Who makes it:**
  - **The player**, while possessing the avatar or from the nearby choices ("Make camp").
  - **The avatar on its own**, when it stands in a mastered place for which the player chose a
    focus, away from the anchor camp, and not yet camped. It camps at most once per place per life.
- **What the camp does.** While it stands, the avatar keeps to the camp's place:
  - **Area.** A region camp covers its region cell (3×3 chunks, the parts of that region). A
    landmark camp covers its chunk and the neighbours.
  - **Targets.** The avatar only goes after encounters in that area that fit the focus. Food is
    always allowed when hungry; story places are always allowed.
  - **Rolls.** Spot rolls in the area weigh focus kinds ×2 and the others ×0.5 (danger is never
    focused away).
  - **Rest.** The avatar rests by the fire as at the anchor.
- **Breaking camp.** After 2 minutes with nothing to do in the area, the avatar breaks camp and
  moves on (`CAMP_IDLE_MS`).

**Focus** (Journal › Places, per mastered place; `location_focus` action, usable any time):

| Choice | Effect |
|---|---|
| No camp (default) | the avatar never camps there on its own; a camp made by hand there goes after everything |
| Everything | camps there, takes all it finds |
| Resources | foraging, gathering, hunting, water, climbing |
| Searching | studying, observing, scavenging, meditating, praying, and the landmark's own encounters |

## Removed

- **Per-encounter mastery grades** (10/100/1000) and the Journal controls tied to them:
  favor/suppress and the regional guarantee.
- **The Campfire skill** (25 ash) and its ability.

## UI

- **Journal › Places** is now the Journal's main view:
  - grades with progress;
  - "you are here";
  - focus buttons in mastered places;
  - this life's camp.
- **Encounters page.** Each encounter shows the places it belongs to. Its odds show once one of those
  places is known.
- **HUD region line:** "The Old Road · known 23/40." / "… · mastered: camp can be made here." /
  "Camped: The Old Road."
- **Anchor.** It lists mastered places and points to Journal › Places.

## Saves (schema 22)

- **Added:** `location_done`, `location_focus` and `camp` (`location`, `dimension`, `cx`, `cy`,
  `idle_since`, `left`).
- **Dropped:** `mastery`, `journal_favor`, `journal_guarantee`, `journal_guarantee_region` and
  `guarantee_used`.
- **Migration from 21.** Each encounter's lifetime count goes to its landmark, or to the region that
  favours it most (Old Road on ties). The old campfire unlock is removed without refund: schema 18
  granted it to every older save, so it cannot tell who paid.

Tests: `tests/test_world_places.py`, plus updates across the suite.
