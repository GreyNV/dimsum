# Core loops

> **Status: design proposal / history.** The implemented Forest expedition differs: actions come from procedural
> region buckets and leads (docs/design/ACTION_SYSTEM.md), and the Journal only shapes odds; it never bypasses rolls.


## Moment-to-moment loop

1. Begin a life at the current act and stage.
2. Generate that stage's guaranteed actions and chance-based encounter bucket.
3. Perform the resulting actions automatically.
4. Gain regular discipline XP, dimensional discipline XP, journal progress, and encounter rewards.
5. Continue through stage transfers until vitality reaches zero.

## Life loop

1. Begin at the awakening anchor with the current persistent state.
2. The character automatically performs the current act and stage action buckets.
3. Gain regular discipline XP, persistent dimensional discipline XP, journal progress, and temporary rewards.
4. Resolve encounters and stage transfers; no branch is permanently lost by not receiving an encounter.
5. Vitality reaches zero and the character returns to the anchor.
6. Regular discipline XP and current-life state reset; dimensional discipline XP persists.

In the browser expedition, death first opens a 30-second anchor interlude. The
player may offer whole stacks of remaining current-life resources for persistent
dimensional dust (berries/stick 1, egg/thorn 2, meat 3, hide 4 each). The first
offer holds the next life until the player chooses Begin; no action lets the
countdown start it automatically. Unoffered inventory is lost at the transition.
Dust has no purchase use yet. This adds one optional choice to the otherwise
automatic life loop; it does not alter the separate idle core's return API.

In the forest expedition, completing a location often leads to a 3-second thought
or 5-second contemplation with no loot, XP or blessing. A 4% seeded chance during
visible play instead starts a 12-second prayer, at most once per life. One blessing
is earned only when that prayer finishes; offline catch-up cannot start it. Prayer
is not a map location. Rare boars pursue nearby and interrupt the current action
when they reach the avatar; the auto-pilot then fights. Food locations and drops
are scarcer, hunger drains at 0.75 points/second and automatic eating waits until
40/100 hunger. These temporary vitals and inventory reset each life; blessing and
dimensional XP persist. The balance target is a first life of roughly 3-6 minutes
at seed 482910 with no passive overnight blessing accumulation.

## Long-term loop

```text
Automatic actions -> discipline and dimensional experience
                  -> journal discoveries and stage progress
                  -> passive shards -> soulbound summons
                  -> stronger softcaps and faster acts -> repeat
```

The player does not select individual actions or training modes. Anchor decisions are limited to configuring journal encounter toggles, summoning soulbound equipment, equipping a loadout, and later deciding whether to perform a dimensional shift.

## Time model

Actions require a fixed amount of work. Disciplines and modifiers determine work completed per second. Regular and dimensional experience are awarded according to the action's configured training rate, and encounter or stage outcomes are awarded when the work reaches its requirement.

This keeps action duration, training, and loot separate. A fast action is not automatically the best training action, and a slow action can be worthwhile because of its unique reward table.

Regular discipline XP belongs to the current life and resets on anchor return. Dimensional discipline XP is the persistent experience layer and survives ordinary anchor returns. Dimensional-shift behavior is a later design decision and is not part of the first implementation.

Each stage bucket is rolled at its first entry in a life and reused for that life, including empty rolls. Revisiting or reloading cannot reroll it. Completing the preceding story action is the only story prerequisite. An optional action needs its story action completed and either a place in the rolled bucket or an enabled journal unlock. Journal unlocks provide reliable access without another roll; completions count toward their rarity threshold.

## Softcaps

Softcaps reduce returns after a discipline reaches configured thresholds without making progress stop. A simple initial formula is:

```text
effectiveGain = baseGain / (1 + softness * max(0, level - softcap))
```

The exact function remains data-driven. Softcaps may apply separately to discipline XP, action speed, vitality efficiency, or encounter progress; they should not silently affect every output. Raising a softcap becomes a meaningful reward from equipment, story, or dimensional experience.

The intended effect is that later acts remain technically possible but become inefficient without dimensional experience and soulbound equipment. The player is encouraged to continue ordinary progress, improve softcaps, summon equipment, or eventually shift dimensions rather than being hard-blocked. Inactivity limits remain balance parameters to be tested in the simulator.


## Provisional simulator contract (2026-09-20)

Partial work persists across updates and saves. Training applies per effective
second, and level changes affect speed immediately. Vitality cost accrues in
proportion to work, with configurable passive decay (currently 0.02 per effective
second). Death interrupts actions and takes precedence over simultaneous
completion; no completion reward is granted in that tie.

These are laboratory policies for measuring curves, not final balance values.
Return resets regular XP and current-life state while preserving dimensional XP,
journal, equipment and shards. Restarting a running life cannot heal or reroll.

The measurable correctness target is equivalent event order, progression and RNG
when elapsed time is split into updates, within floating-point tolerance.
Tests compare 2,000 updates with one bulk advance in both modes. Clone accrual
uses real time even at zero life efficiency.
