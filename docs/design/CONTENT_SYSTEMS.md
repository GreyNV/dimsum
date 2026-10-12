# Content systems: how to add content without touching the engine

Since 2026-10-12 every piece of world content is a catalog entry in
`src/dimensional_sim/world/catalog.py`. The engine (auto-pilot, combat, stats pages,
client) reads the catalog and never names an enemy, item, boon, unlock or biome.
If an idea needs a new *kind* of rule, add a field or an effect stat once; after that,
content using it is data only.

## The systems

| System | Catalog | Read by | What it controls |
|---|---|---|---|
| Biomes | `BIOMES` (`BiomeDef`) | `autopilot/combat.py` | danger growth per ring (`danger_num/danger_den`), enemy HP per ring, ring cap |
| Enemies | `ENEMIES` (`EnemyDef`) + a fight `ActionDef` with `enemy=` | `autopilot/combat.py`, `session.py` | bite damage, aggro radius, death cause and its report text, sprite |
| Effects | `Effect(stat, amount)` on `ItemDef.effects` (gear) and `BoonDef.effects` | `effects.py` | `punch_damage` (add), `enemy_hit_percent` (multiply), `food_window_bonus` (add) |
| Abilities | `UnlockDef.ability` (one of `ABILITIES`) | `Expedition.has_ability` | engine capabilities that are not actions, e.g. `return_to_anchor` |
| Styles | `CATEGORY_STYLES` (`CategoryStyle`), `ActionDef.color`, `ItemDef.color` | frames -> client | activity verb, body pose, work-mark color, completion seal, item text color |
| Art keys | `ActionDef.art` (default: the action id), `EnemyDef.sprite` | client `place_art.js SPOTS`, `combat_art.js ENEMY_SPRITES` | which sprite is drawn |

Effects apply gear in slot order (`EQUIPMENT_SLOTS`), then the life's boon. Percent
stats floor after each source, so the order is part of the balance.

## Recipes

**A new enemy (e.g. a wolf)**
1. `ENEMIES`: `EnemyDef("grey_wolf", "Grey wolf", hit=6, aggro_radius=14, cause="wolf", cause_text="a grey wolf", sprite="wolf")`.
2. `ACTIONS`: a fight spot `ActionDef("grey_wolf", ..., "fight", "spot", ..., hp=2, enemy="grey_wolf", window=(0, 1), loot=...)`.
3. Weight it in regions (`RegionDef.weights`) if it belongs somewhere specific.
4. Art: add `wolf` to `ENEMY_SPRITES` in `combat_art.js` (until then the boar sprite is used).
5. Bump `encounters.ENCOUNTER_VERSION` and add a save migration (spot rolls change for existing worlds).
The frontier, pursuit, life report, journal death counts, stats pages and HUD pick it up automatically.

**New gear**
1. `ITEMS`: `ItemDef(..., "gear", slot="weapon", effects=(Effect("punch_damage", 2),), color="#rrggbb")`.
2. A craft `ActionDef` with `cost=` and `effect="<item id>"` (and a recipe or unlock to gate it).

**A new boon**: `BoonDef(id, name, description, cost, (Effect(...),))`.

**A new spot action**: an `ActionDef` with a category (style comes from `CATEGORY_STYLES`),
then a sprite under its id (or `art=`) in `place_art.js SPOTS`. Missing art shows a "?"
marker, and `tests/test_world_systems.py` fails until it is drawn.

**A new biome**: a `BiomeDef`, regions with `biome=` set to it, actions listing it in
`biomes=`, and terrain in `assets.py`/`open_terrain.py` (generation is still forest-shaped;
see "Still hard-coded").

**A new effect stat** (engine change, once): add it to `EFFECT_STATS`, then read it with
`effects.total(...)` or `effects.scale(...)` where the number is used.

## Still hard-coded (next candidates)
- Terrain generation styles per biome (`open_terrain.py`, `assets.py`): a second biome needs terrain code.
- One global monster clock (`MONSTER_STEP_MS`): all enemies move at the same speed.
- Activity interaction marks in `player_art.js` (which categories touch the spot, draw rings, etc.) are keyed by category.
- Asset-placed enemies count as `ASSET_ENEMY_ACTION`.
- The `walking_staff` recipe and `primitive_crafting` knowledge are content, but the crafting *policy* (need priority) is generic.
