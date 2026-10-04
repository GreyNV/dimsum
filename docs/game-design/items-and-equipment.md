# Items and equipment
## Confirmed behavior
Soulbound equipment is deliberately summoned using dimensional shards, not dropped
during ordinary lives. Items and loadout survive ordinary anchor returns; dimensional
shift persistence remains undecided. No material economy or temporary equipment
inventory is introduced.

A summon chooses rarity from an authored stage/act probability matrix, then a random
template and a level. Common items have exactly one base attribute bonus: Strength,
Endurance, Agility, Intelligence, Perception or Willpower. Items are separate
instances, so another copy can roll a different level.

## Rarity progress and tuning
Each rarity independently earns XP from its own summons. Completed story milestones
raise that rarity's cap; common level 100 does not raise uncommon.
Prototype levels use total XP, base 10 XP per level with 1.15 growth; each pull grants
1 XP after rolling. XP banks at cap and is realized when the cap rises.
These are tuning defaults, not additional user requirements.
Inclusive windows follow the requested examples: 1..10 initially, 90..100 at level 100.
The latter intentionally contains 11 integer outcomes. Initial caps are 10.
Common base stat equals item level times authored stat_per_level (default 1).
Higher-rarity templates may carry authored extra effects.

| Latest completed stage | Common | Uncommon | Rare | Legendary | Raised caps |
|---|---:|---:|---:|---:|---|
| Opening |100%|0%|0%|0%|10 each|
| Village |90%|10%|0%|0%|common 20|
| Forest |75%|20%|5%|0%|common 50, uncommon 20|
| Old Trail |60%|30%|10%|0%|common 100, uncommon 50, rare 20|

Rows/caps and the shared 10-shard cost are provisional authored content/config.
Completing the story adjusts the row, not merely entering the stage.
Invalid pools or insufficient funds spend no shards and advance no RNG.
Rarity is selected first, so adding common templates does not dilute rare chances.

## Equipment review
Summoning creates a pending decision; it never auto-equips. Review compares the
equipped item in the same slot (top) and summoned item (bottom).
Both panels use the union of stats, showing missing values as 0. Each panel's signed
delta equals its value minus the other panel's value. Gains are green and losses
red; signs remain visible independently of color.
The replacement summary always shows new minus current.
Keep current retains the new item. Equip new replaces only that slot and retains
the old item. Closing a future popup must preserve its pending decision.
Backend comparison/decision payloads exist; the separate dark-gray/copper UI is
unfinished.

Prototype slots: head, body, hands, feet, weapon, charm; one instance per slot.
Item bonuses affect relevant action speed; higher-rarity authored modifiers can
affect softcaps or passive shards. More complex route-changing effects and
dimensional relics remain future design work.

## Persistence and verification
Idle schema5 saves instances, loadout, pending reviews, rarity XP/caps and completed
stages. Tests cover seeded rolls, distributions, independent rarities, level windows,
common stat count, replace/keep, symmetric zero rows, signed deltas, reload and return.
Final pacing, pity, duplicate conversion and higher-rarity stat generation remain open.

## Design change 2026-10-04: gathered items
Approved by the user for the world auto-pilot: a small current-life inventory of
gathered food and materials (12 slots x 20). Food is auto-eaten with a cooldown;
materials are kept for future crafting/binding at the anchor camp. The inventory
is lost at anchor return. Soulbound equipment is still summon-only and persists.
