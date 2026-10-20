# Carryover and summoning: decision record (2026-10-20)

## Player decision and current evidence

At death, the player should decide which useful possessions survive instead of
turning into ash. At the anchor, ash should buy a persistent source of build variety.
Going deeper should improve summon quality without making early pulls feel wasted.

The current world already binds **buildings**, not crafted inventory items. A bound
crafting station (120 ash) remains in later lives. A bound storage chest (200 ash)
keeps materials stowed at the camp. Carried gear converts to ash at death. Strength
and Endurance already reduce the load movement penalty; Crafting is not currently an
attribute (Building is), and world summoning does not exist. The separate Phase One
idle simulator has persistent summoned items, six slots, and independent rarity XP,
but the world must keep its own save and catalog contracts.

Baseline command: `python -B -m dimensional_sim.world.cli simulate --seeds 1-12
--minutes 60 --policy spend --lives`, current main before the attribute changes in
this record. Twelve seeds produced 16 completed lives. Mean life was 24.77 minutes;
mean deepest ring was 5.81; mean ash converted was 108.25 per death. No completed
life reached ring 10 (maximum 8). One seed had not died after 60 minutes. This is a
small automated cohort, not a human playtest or a long-run estimate. At this rate,
1,000 ash alone costs about 9.2 average death payouts or 229 simulated minutes of
completed lives, before existing purchases. We should not ship a 1,000-ash gate
until a longer cohort shows that this is an intended wait and ring 10 is reachable.

## First implemented slice: attributes with visible consequences

The avatar reveals a five-cell radius initially. Every four effective combined
Perception and Willpower levels add one cell, up to radius eight. Willpower also
adds two seconds of possession per effective level, from 30 to 60 seconds. Effective
levels use the existing regular/dimensional softcap. These values are derived from
saved XP; no new persistent field or random roll is required. Revealed cells stay
revealed. Strength and Endurance's existing load relief remains the authoritative
formula; adding another multiplier would double-count the stats.

The intended result is a map a player can uncover sooner and more direct-control
time as those stats rise. The numbers are deliberately bounded so late levels do
not reveal whole chunks or grant permanent possession. Tests check radius growth,
remembered fog, possession end, reload, and old zero-level behavior. Human players
still need to report whether the effects are noticeable without a stats explanation.

## Proposed dimensional bag contract

The bag is an anchor purchase: 30 ash opens its first slot, then upgrades at 50,
75, 110, 165, and 250 ash open one slot each, to a maximum of six. These are
provisional prices (680 ash for all six slots), to be checked against the pacing
gates below. A slot holds one catalog item ID and at most
five units (gear: one); food and treasures are ineligible. During a life the player
pins eligible carried materials or crafted gear into slots. The pinned quantities
still occupy inventory and still incur load. On death they move into the persistent
bag **before** ash conversion; overflow converts normally. Bagged units never earn
ash or increment lifetime conversion counts. At the anchor, the player may withdraw
units to the next life's inventory; unwithdrawn units remain bagged. The bag cannot
feed crafting/building remotely. The bound chest retains its role as high-capacity
camp storage, while the bag protects a few items carried away from camp.

This needs a world save migration for slot count, pinned selections, and stored
contents, strict stack/ownership validation, rebirth and new-world transfer rules,
and an anchor/inventory UI. Pinning must be an explicit choice before death; a
death popup would remove the risk. Expansion prices should be calibrated with
observed ash income and compared to station/chest binding, not chosen by analogy.
Provisional target: the first slot should be affordable by the second death in at
least half of seeded runs, and a fully upgraded bag should still require a meaningful
choice against the 1,000-ash summoning unlock.

## Proposed summoning contract and exact odds

`Learn summoning` costs 1,000 ash once and opens a six-slot *summoned equipment*
loadout: head, body, hands, feet, weapon, charm. These slots are separate from
current-life crafted weapon/body slots. Summoned items persist across lives, do not
occupy inventory, and cannot be converted to ash. The provisional pull price is
25 ash; it must be rechecked against income after the 1,000-ash gate. Each rarity
has its own pull count and item-level progression. A pull advances only the rarity
actually obtained. A summoned item applies catalog-defined modifiers to existing
rules (for example, action speed, load relief, or fog radius), not flat attack or
health. Epic and higher tiers require at least one authored, testable rule change
before they can appear; a colored label alone is insufficient.

For a first playable rule, an item's level is `min(50, 1 + prior pulls of its
rarity // 10)`, calculated **before** incrementing that rarity's count. Thus the
first 10 common pulls are level 1, the eleventh is level 2; uncommon counts do not
raise common levels. Template modifiers scale with that level through authored
integer formulas and caps. This deliberately makes levels predictable; random
template and rarity already provide variation. Compare the resulting power curve
to actual affordable pull counts before setting a per-pull price.

The roll uses the highest ring reached in the current life, or the life just ended
when at the death anchor. Returning to a lower ring does not reduce that life's
odds. The ring value must be shown next to the odds in the summon UI. The table is
summon-specific; existing encounter/drop rarity tables remain untouched.

Let `r = min(40, max(0, ring))`. Exact tier percentages, before choosing a
template within that tier, are:

```
uncommon  = min(r, 30)                     # 1% per ring, capped at 30%
rare      = 0.4 * min(max(r - 10, 0), 20) # starts after ring 10, caps at 8%
epic      = 0.1 * min(max(r - 20, 0), 20) # starts after ring 20, caps at 2%
legendary = 0.05 * min(max(r - 30, 0), 10) # starts after ring 30, caps at 0.5%
common    = 100 - uncommon - rare - epic - legendary
```

Implement as integer basis points to avoid float boundaries. Roll rarity first
using a dedicated seeded summon stream, then choose among the eligible templates
of that rarity. No tier may have positive odds without at least one validated
template; a refused pull must spend neither ash nor RNG state. This table gives:

| Ring | Common | Uncommon | Rare | Epic | Legendary |
|---:|---:|---:|---:|---:|---:|
| 0 | 100% | 0% | 0% | 0% | 0% |
| 10 | 90% | 10% | 0% | 0% | 0% |
| 20 | 76% | 20% | 4% | 0% | 0% |
| 30 | 61% | 30% | 8% | 1% | 0% |
| 40+ | 59.5% | 30% | 8% | 2% | 0.5% |

At ring 10, the requested uncommon chance is exactly 10%. As drafted, odds
improve with depth but do not yet have pity. Before implementation, compare expected
pulls per useful item against ash income and duplicate outcomes; a guaranteed
upgrade or duplicate recycling may be needed to prevent dead purchases.

## Crafting and Building gate

Building already earns XP from structures; crafting actions currently earn the
action's Strength, Endurance, or Perception XP. Introduce Crafting as a separate
attribute only with a save migration and a clear training path. Higher recipes
should require both retained knowledge and a Crafting/Building threshold, with
requirements in catalog data. Measure materials, action time, hunger consumed,
and survival during the craft. A recipe is viable only if a prepared avatar can
finish and use it before the cost of gathering/crafting forces starvation. The
first candidate should be a single upgraded gear recipe, not a full tier tree.

## Acceptance before enabling the next slice

1. A held-out seeded cohort reports deaths, ash earned and spent, ring distribution,
   time to the 1,000-ash unlock, and pulls per death under realistic spending.
2. Bag tests prove conservation: every unit is either carried, stored, consumed, or
   converted exactly once across death, reload, and new-world transfer. Load applies
   until deposit; no unowned item can be pinned or withdrawn.
3. Summon tests prove each odds row sums to 10,000 basis points, ring monotonicity,
   empty-pool refusal, independent rarity progress, six-slot validation, deterministic
   replay, and save migration.
4. Player tests ask whether the bag/chest difference and the current summon odds are
   understood without explanation. Track whether first useful summon arrives while
   players are still reaching new content, not after they have exhausted it.

Provisional pacing gates for that cohort: at least one quarter of runs reach ring 10
within two hours; at least half can buy summoning within three hours under a player
policy that sometimes buys recipes/buildings; and the first paid pull follows the
unlock within one further completed life. These are design targets, not properties
of the current build. Revise the prices, ash production, or ring progression if the
cohort misses them before shipping the shop offer.
