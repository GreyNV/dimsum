---
name: idle-game-design
description: Design and balance repeatable idle-game loops with attributes, actions, loot, equipment, narrative gates, dimensional resets, and softcaps.
metadata:
  short-description: Idle game design and balance
---

# Idle game design

Use this skill when shaping the rules, progression, content, economy, or balance of the dimensional idle game.

## Design principles

- Treat actions as the foundation. Every progression system should be advanced by, modify, or create meaningful actions.
- Separate progression purposes: disciplines make actions faster; temporary resources are optional and must have a clear use; soulbound equipment changes action outcomes; narrative gates access; dimensional experience persists through ordinary anchor returns while dimensional shifts remain separately specified.
- Keep the first playable loop small. Add one mechanic only when it creates a new decision or removes repetitive friction.
- State what is temporary, persistent, or local to a dimension for every reward.
- Use softcaps to reduce returns without making progress stop. A softcap should redirect the player toward varied actions, equipment, discovery, or raising the cap.
- Avoid pure numerical inflation. Prefer equipment and unlocks that change available actions, routes, risks, or automation.
- Every random encounter needs a useful failure state, a pity or protection rule, or a reliable alternate path. Soulbound equipment is summoned through dimensional shards rather than randomly dropped during an ordinary life.

## Required specification for a mechanic

For each new mechanic, document:

1. Player decision and intended feeling.
2. Inputs, time cost, requirements, and outputs.
3. What persists through return, death, and dimensional shift.
4. Interaction with disciplines, temporary resources when present, equipment, and narrative gates.
5. Failure, randomness, and anti-exploit rules.
6. A measurable balance target and a deterministic test scenario.

## Balance workflow

Start with ratios and formulas, not large content lists. Simulate representative actions over several lives, including the fastest repeatable action and a mixed route. Check that one discipline cannot dominate all progress, that softcaps reduce but do not eliminate gains, and that equipment creates viable alternatives.

Keep balance values data-driven and versioned. Do not bury drop rates, softcap thresholds, or progression multipliers in UI code.

Read the project design documents in `docs/game-design/` before proposing changes. Update the relevant document when a rule becomes confirmed; put unresolved choices in `decisions-open.md`.
