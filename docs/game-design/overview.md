# Dimensional Summoner: game design overview

## Vision

An idle progression game that begins with an old man dying after a life in which his rare summoning power was dismissed as useless. At death, the power awakens and creates an anchor. The character returns to that anchor and automatically progresses through acts and stages of his earlier life. He develops disciplines, discovers encounters, receives dimensional experience, and uses passive dimensional shards to summon soulbound equipment.

The game should be approachable on mobile, playable in short visits, and rewarding over long periods. Its complexity should come from meaningful choices and interacting systems rather than a large number of currencies or menus.

## Opening sequence

Revised 2026-10-04. A traveller is ambushed by bandits on a forest road and left for dead. The character survives, but wakes with memories of the attack and something new inside: the gods have made them a dimensional avatar, bound to an anchor at the place where they woke.

The world build plays this as the first scene of the first life:

1. **Wake up.** The screen is black; only the current task, health and hunger show. Memories of the ambush surface one line at a time, then the eyes open.
2. **Stand up.** The forest appears around the anchor. The avatar rises.
3. **The old man.** A traveller standing nearby speaks: he has witnessed the birth of a dimensional avatar. The gods saved you, but now you must worship them. Explore the world, and don't forget to pray; maybe the gods will bestow blessings. May the path be smooth; only you will know what destiny awaits.

He walks off, the rest of the interface fades in and the auto-pilot begins. Prayer at shrines grants blessing power. Later lives return to the anchor with a life report, as before. The earlier "dies old, power dismissed" framing and its system report are superseded for the world build; the idle simulator text has not been changed yet.

The confirmed base attributes are Strength, Endurance, Agility, Intelligence, Perception and Willpower, each with regular and dimensional experience.

## Design pillars

1. **Actions are the foundation.** The player always has a clear action to perform.
2. **Progress compounds without mandatory busywork.** Better disciplines and equipment make known content faster while later acts demand stronger softcaps.
3. **Discovery matters.** Story, rare items, and dimensions reveal new rules instead of only larger numbers.
4. **The anchor gives resets meaning.** Returning to the awakening is an understandable fiction and a predictable mechanical boundary.
5. **Randomness creates discovery, not permanent-loss anxiety.** Encounters vary each life, while soulbound equipment comes only from deliberate shard summons.

## Progression systems

- **Acts and stages:** automatic story structure containing guaranteed actions and chance-based encounter buckets.
- **Disciplines:** improve action speed without imposing level prerequisites on actions. Each has regular and dimensional experience.
- **Encounters and journal:** chance-based actions provide rewards, fights, lore, and discovery counts. Repeated completions unlock journal toggles.
- **Soulbound equipment:** summoned with dimensional shards and persistent across ordinary anchor returns.
- **Narrative access:** story actions and stages become available by completing the preceding story action. Bucket actions additionally require a current-life roll or an enabled journal unlock.
- **Dimensional experience:** persistent experience for each discipline that survives ordinary anchor returns. Its behavior during a dimensional shift is intentionally unspecified for now.
- **Dimensional shifts:** a future system with separately designed reset rules and permanent bonuses.

These systems interact without forming a fixed checklist. A forest stage may grant discipline experience, dimensional experience, journal progress, vitality changes, and encounter rewards at the same time.

## First playable scope

The first prototype contains one village, one forest location, six attributes, approximately ten actions, automatic stage buckets, a journal, vitality decay, passive clone shard generation, a small soulbound summon pool, and several story milestones. It should support several complete lives before more content is added. Dimensional shift and multiplayer are deferred. Full inventory management, temporary equipment, and custom clone routes are not approved mechanics.

## Spatial foundation
The separately authorized exploration foundation adds seeded character-grid worlds,
independent player movement/animation and timed combat. It does not yet award idle
progression rewards or determine dimensional-shift reset rules. In the browser world the
character explores on auto-pilot, resolving chance-spawned biome encounters for
attribute experience; taking manual control is a skill to unlock later. See
[world scope](../technical/world-foundation.md).
