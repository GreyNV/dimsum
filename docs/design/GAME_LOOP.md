# Game loop (shipped in this iteration)

Every arrow names the mechanic that implements it. "Before" marks what was missing.

```
EXPLORE   auto-pilot walks to unvisited chunks inside its frontier (autopilot.frontier)
  -> DISCOVER  each new chunk belongs to a generated region (terrain + action pool); it rolls spots from that
               region's bucket (actions.py, regions.py); some spots leave temporary leads (deer tracks)
  -> INTERACT  perform spot actions; boars pursue and fight; prayer/thought after a location
  -> ACQUIRE   loot items (food, materials), XP (regular + dimensional), heal, blessing
  -> SPEND     eat food (auto, cooldown); craft once learned: staff (recipe from 10 branch gathers, 3 sticks),
               snare (unlock, 2 sticks + thorn), wrap (unlock, 2 hides); crafted gear is equipped in a slot
  -> SURVIVE   gear raises damage / lowers hits -> frontier moves outward -> deeper rings, better XP
  -> DIE       starvation inside the frontier, or a boar
  -> ANCHOR    offer stacks -> dust (diminishing) | keep -> burned to ash at rebirth (+1 ash per ring)
  -> META      dust buys unlocks (new spot / craft actions); blessing buys the shrine unlock or a boon;
               ash buys mastery (wider spawn windows; Journal on/off at 2, favor/suppress odds at 3)
  -> NEXT RUN  unlocked / known actions join the buckets (still rolled, never guaranteed); knowledge and recipes
               persist; mastery/boon/Journal change odds and windows; dimensional XP speeds work
```

| Arrow | Before | Now |
|---|---|---|
| Explore -> discover | yes, but no context | region buckets, pity guarantees food and enemies |
| Interact -> acquire | yes | yes (+ crafting outputs) |
| Acquire -> spend | food only | food, three recipes |
| Spend -> survive | eating | eating, gear (damage, armor), snares (food from materials) |
| Survive -> progress | XP speed | XP speed + frontier depth (danger-aware exploration) |
| Die -> meta | dust (no sink) | dust, ash, blessing all have sinks |
| Meta -> unlock | none | 7 dust unlocks, 1 blessing unlock, 2 boons, mastery on 7 actions |
| Unlock -> next run | none | unlocked actions enter future buckets; mastery/boon change generation |

## Player questions and the in-game answer
- **What can I do?** Watch the task line; at the anchor, offer items and buy unlocks, boons, mastery.
- **Why explore?** New chunks roll new spots; regions differ (berries in thickets, boars in deep woods).
- **What are resources for?** Food is eaten; sticks/thorns/hides become a staff, snare or wrap; everything
  carried at death becomes dust (if offered) or ash (if kept).
- **Spend now or save?** Gear is worth less dust than its inputs, but keeps you alive longer (measured:
  crafting lives last longer - BALANCING.md).
- **What happens if I die?** The life report lists bounty, spots, crafts and what your items are worth.
- **What did I unlock?** Anchor shop and the debug overlay list owned unlocks; the next life's buckets include them.
- **How is the next life different?** New spot types, new recipes, wider windows, an optional boon.
