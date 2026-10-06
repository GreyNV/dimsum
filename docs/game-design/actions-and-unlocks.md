# Actions, locations, and unlocks

> **Status: design proposal / history.** The implemented Forest expedition differs: actions come from procedural
> region buckets and leads (docs/design/ACTION_SYSTEM.md), and the Journal only shapes odds; it never bypasses rolls.


## Action definition

Every action should specify:

- stable identifier and location;
- work required and base work rate;
- governing discipline and training rate;
- time and vitality cost;
- prerequisites;
- guaranteed outcome;
- encounter outcome table;
- discovery or story progress;
- failure or risk rules;
- persistence classification for every output;
- journal completion threshold and toggle behavior.

## Initial action set

### Village

- Rest: advances time with low vitality pressure.
- Practice movement: trains Agility with no material reward.
- Help the craftsman: trains Intelligence and may reveal a temporary encounter.
- Talk to father: advances the opening story and reveals the first lead.
- Investigate the village: reveals available characters and actions.

### Forest

- Walk the forest edge: Endurance progress and low vitality cost.
- Observe tracks: Perception progress and journal discovery chance.
- Explore the old trail: stage progress and encounter chance.

### First dimensional site

- Sense the rift: trains Perception and can grant dimensional shards.
- Observe the reflection: journal discovery and a chance of a recovery or combat encounter.

## Unlock categories

- **Encounter discovery:** records an action in the journal after it appears.
- **Journal unlock:** after the rarity-based completion threshold, makes the action available after its story action without another random roll. The player can enable or disable it for future queues.
- **Stage unlock:** completing the preceding story action makes the next story stage available. Discipline levels, equipment, and optional encounter completions are not prerequisites.
- **Rule unlock:** introduces a mechanic such as soulbound summoning or passive clone shards.

Disabling an encounter never deletes its journal entry or blocks the story chain. A stage schedules its story actions first, then eligible optional encounters. Story access is earned on story completion, independently of whether those optional encounters are completed.

Initial journal thresholds are provisional and rarity-based:

```text
Common encounter: 10 completions
Uncommon encounter: 100 completions
Rare encounter: 1,000 completions
```

Encounter outcomes can restore vitality, award regular or dimensional discipline experience, grant dimensional shards, cause a fight, advance lore, or contribute to story progress. They do not directly grant soulbound equipment; that equipment comes from shard summons at the anchor.

## Story structure

Acts are broad narrative gates rather than separate gameplay layers. Each act should introduce a location, conflict, or rule while reusing earlier actions at higher stakes.

- Act I: Awakening, anchor return, and village survival.
- Act II: Leaving the village and first forest route.
- Act III: The old trail, difficult encounters, and stronger softcaps.
- Act IV: Soulbound summoning and deeper dimensional understanding.
- Act V: Future dimensional shift and warrior-dimension foundations.


## Confirmed eligibility rule

- A story action requires only completion of the preceding story action in the
  current life. The first story action is available at the anchor.
- A bucket action requires completion of its associated story action AND either
  membership in the current life's rolled stage bucket OR an enabled journal
  unlock. Discovery alone is not a journal unlock.
- Disciplines change execution speed and training, not access. Vitality and work
  remain execution costs; they are not additional eligibility thresholds.
- Each stage's random bucket is rolled once per life, including empty results.
  Revisits and reloads reuse that roll. All enabled journal unlocks are merged
  into the stage queue without duplicates and execute after its story actions.
- A toggle affects later queues, never an already-running queue. Return clears
  rolled buckets and story completions; journal unlocks/settings persist.
  Dimensional-shift behavior remains outside this implementation.

The player chooses optional journal content without gambling on its reappearance.
There is no new currency, reward or time cost: actions retain their authored
work, XP and vitality outcomes. Unfinished actions grant no completion rewards.
The automatic runner processes eligible encounters before its next stage transfer;
that scheduling does not add an encounter requirement to the story unlock.

Deterministic verification: with all XP rates zero, completing a story action
unlocks the next stage. With encounter weights zero, an enabled journal unlock
still executes after its story action; an undiscovered action does not. Multiple
unlocks, disabled entries, cached rolls, and partial-save continuation are tested.
