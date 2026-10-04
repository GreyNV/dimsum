# Lives, survival, items and the anchor camp - plan (2026-10-04)

User request: transparent UI; stats that matter (speed scales with level); two
experience tracks per attribute; items collected from encounters; hunger and
health bars; auto-eaten food with a cooldown; inventory under the minimap; the
anchor and a home/intro location; a prestige loop. Planned, then executed.

## Decisions (made autonomously; revisit freely)
1. Progression reuses the idle simulator's documented rules (core.GameConfig):
   regular XP 100 x 1.15^n per level (resets each life), dimensional XP 100 x
   1.35^n (persists), softcap 10 with softness 0.08,
   speed = 1 + 0.10*soft(regular) + 0.01*soft(dimensional).
   Encounters grant regular XP; dimensional XP = 20% of it. Encounter XP values are
   rescaled x10 so levels arrive within the first lives.
2. Speed meaning: activity time = base / speed(attribute). Endurance slows
   hunger drain and softens boar hits. Strength shortens the pause between
   punches. Movement speed stays pinned by the runtime (later slice).
3. Survival: hunger and health 0..100, integer micro-units so any time slicing
   gives identical results. Hunger drains 0.4/s (divided by Endurance speed).
   At 0 hunger, health drains 1/s. Above 50 hunger, health regenerates 0.2/s.
   Boars hit back 6 HP (/ Endurance speed) after each punch while alive.
4. Items (design change, recorded in items-and-equipment.md): a small inventory
   of gathered materials and food. Soulbound equipment is still summon-only.
   Loot rolls are seeded per life and spot. Food is auto-eaten when hunger is low
   enough for the item to fit (or below 25), with a 15s cooldown.
   Inventory: 12 slot stacks of 20, lost at anchor return (a current-life state).
5. Prestige: health 0 -> life report -> return to anchor. Regular XP, inventory,
   vitals and the map's actors reset; dimensional XP, discovery map and skills
   persist. Each life re-rolls the encounter spots (seed includes the life).
6. Anchor camp: the player spawn of chunk (0,0) becomes the anchor camp (anchor
   stone, bedroll, fire pit; presentation is non-blocking). Low health with no
   food sends the auto-pilot home to rest (regen 1/s there). A first-run intro
   shows the opening system report from the design overview; future crafting and
   binding will live here.
7. UI: panels become translucent; top vitals bar (health, hunger, food cooldown);
   attribute grid shows level, dimensional level and XP progress; inventory grid
   under the minimap; life-report overlay.

## Work packages
P1 progression.py (levels/speed from core rules) + items/loot in encounters.py.
P2 autopilot: vitals, eating, loot, inventory, scaled durations, punches/hits,
   death -> new life, rest at camp, life reports, save schema 2 (1 migrates).
P3 server/transport: session follows the current life's game object; frame adds
   vitals, inventory, levels, life, report, anchor.
P4 client: translucent panels, vitals bar, inventory, attribute levels, camp
   sprite, intro/report overlay, food/eat popups.
P5 tests (determinism with vitals, death/persistence, eating cooldown, loot,
   durations, migration), docs, browser QA, write back.

## Result (executed 2026-10-04)
P1-P5 done. Balance iterations during execution: first pass lives lasted 2-3 min
(no retreat when food was held, food did not heal); second pass was immortal
(retreat + fight avoidance, linear danger). Final: exponential danger by ring,
softcapped punch damage, deepest-unvisited exploration. 169 unittest + 17 node
tests; browser QA at 1440x900 and 390x844 with intro, play, hurt and death
reports and no console errors.
