"""Auto-pilot lives, survival, items and encounters; no browser/AI required."""
import json
import random
import unittest
from dataclasses import replace

from dimensional_sim.core import new_demo_game
from dimensional_sim.world import autopilot as ap
from dimensional_sim.world.autopilot import Expedition
from dimensional_sim.world.browser_server import MANUAL_HOLD, BrowserSession
from dimensional_sim.world.encounters import (
    BY_ID, DARK_FOREST, ITEMS, ItemDef, Loot, chunk_spots, roll_loot, validate_pools)
from dimensional_sim.world.models import DELTAS, ChunkKey, DimensionSpec
from dimensional_sim.world.open_terrain import open_assets
from dimensional_sim.world.progression import attribute_report, scaled_ms, speed_permille
from dimensional_sim.world.repository import WorldRepository
from dimensional_sim.world.runtime import Exploration, Target
from dimensional_sim.world.seeds import canonical_json

P = ap.POINT


def world(seed=482910):
    spec = DimensionSpec("forest", ("dark_forest",), 32, 16, 25)
    return WorldRepository(seed, (spec,), open_assets(32, 16), 9)


def expedition(seed=482910):
    return Expedition(Exploration(world(seed)))


def dump(e):
    return canonical_json(e.to_dict())


def first_death(e, step=1000):
    life = e.life
    while e.life == life:
        e.advance(step)
    return e


class CatalogTests(unittest.TestCase):
    def test_first_biome_has_distinct_location_set(self):
        locations = {"abandoned_camp", "moonlit_pool", "fallen_watchtower", "mushroom_ring"}
        self.assertTrue(locations <= set(BY_ID))
        self.assertEqual(len({BY_ID[i].name for i in locations}), len(locations))
        w = world()
        rolled = {spot.encounter for y in range(-5, 6) for x in range(-5, 6)
                  for spot in chunk_spots(w.get(ChunkKey("forest", x, y)))}
        self.assertTrue(locations <= rolled)

    def test_pool_items_and_loot_validate(self):
        validate_pools()
        self.assertEqual(len(BY_ID), len(DARK_FOREST))
        good = DARK_FOREST[0]
        for change in ({"attribute": "charisma"}, {"kind": "smithing"}, {"xp": 0}, {"weight": 0},
                       {"near": "?"}, {"hp": 3}, {"log": ""}, {"loot": [Loot("stick", 1, 1)]}, {"heal": 101}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                replace(good, **change)
        for bad in (lambda: Loot("gold", 1, 1), lambda: Loot("stick", 3, 2), lambda: Loot("stick", 1, 1, 0),
                    lambda: ItemDef("x", "X", "food"), lambda: ItemDef("x", "X", "material", food=5),
                    lambda: ItemDef("x", "X", "weapon")):
            with self.assertRaises(ValueError):
                bad()
        # Every encounter is bare-handed; food comes from foraging, climbing and boars.
        food_sources = {e.id for e in DARK_FOREST if any(ITEMS[l.item].kind == "food" for l in e.loot)}
        self.assertEqual(food_sources, {"bramble_berries", "gnarled_tree", "bramble_boar"})

    def test_loot_is_deterministic_and_in_range(self):
        entry = BY_ID["bramble_berries"]
        for seed in range(200):
            loot = dict(roll_loot(entry, seed))
            self.assertEqual(loot, dict(roll_loot(entry, seed)))
            self.assertEqual(loot["wild_berries"], 1)
        thorns = sum("bramble_thorn" in dict(roll_loot(entry, s)) for s in range(1000))
        self.assertTrue(200 < thorns < 400)  # 30% chance

    def test_spots_deterministic_per_life_and_placed_legally(self):
        a, b = world(), world()
        keys = [ChunkKey("forest", x, y) for y in range(-3, 3) for x in range(-3, 3)]
        differs = False
        for key in keys:
            self.assertEqual(chunk_spots(a.get(key)), chunk_spots(b.get(key)))
            differs |= chunk_spots(a.get(key), life=1) != chunk_spots(a.get(key), life=2)
            chunk = a.get(key)
            for spot in chunk_spots(chunk):
                asset = chunk.asset
                self.assertFalse(asset.collision[spot.y][spot.x])
                near = BY_ID[spot.encounter].near
                if near:
                    glyphs = {(asset.objects[spot.y + dy][spot.x + dx] or asset.environment[spot.y + dy][spot.x + dx]).glyph
                              for dx, dy in DELTAS.values()}
                    self.assertIn(near, glyphs)
        self.assertTrue(differs, "each life re-rolls the encounters")


class ProgressionTests(unittest.TestCase):
    def test_speed_matches_idle_simulator_rules(self):
        game = new_demo_game(1)
        for regular, dimensional in ((0, 0), (100, 0), (999, 250), (40000, 9000)):
            game.regular_xp["strength"], game.dimensional_xp["strength"] = regular, dimensional
            self.assertEqual(speed_permille(regular, dimensional),
                             round(game.speed_multiplier("strength") * 1000))
        self.assertEqual(scaled_ms(2400, 1000), 2400)
        self.assertEqual(scaled_ms(2400, 1600), 1500)
        self.assertEqual(scaled_ms(1, 5000), 1)
        row = attribute_report({a: 0 for a in BY_ID["bramble_boar"].attribute.split()} | {
            "strength": 250, "endurance": 0, "agility": 0, "intelligence": 0, "perception": 0, "willpower": 0},
            {"strength": 0, "endurance": 0, "agility": 0, "intelligence": 0, "perception": 0, "willpower": 0})["strength"]
        self.assertEqual((row["level"], row["into"], row["next"]), (2, 35, 132))

    def test_higher_levels_finish_encounters_faster(self):
        slow, fast = expedition(), expedition()
        fast.regular = {a: 3000 for a in fast.regular}
        durations = []
        for e in (slow, fast):
            while not (e.task and e.task["type"] == "perform"):
                e.advance(20)
            entry = BY_ID[e._spot_by_id(e.task["spot"]).encounter]
            self.assertEqual(e.task["duration_ms"], scaled_ms(entry.duration_ms, e.speed(entry.attribute)))
            durations.append((entry.id, e.task["duration_ms"]))
        self.assertEqual(durations[0][0], durations[1][0])
        self.assertLess(durations[1][1], durations[0][1] * 0.6)
        self.assertGreater(fast.punch_damage(), slow.punch_damage())


class SurvivalTests(unittest.TestCase):
    def test_auto_eat_respects_threshold_fit_and_cooldown(self):
        e = expedition()
        e.inventory = {"wild_berries": 2, "boar_meat": 1}
        e.hunger, e.health = 41 * P, 50 * P
        e._settle()
        self.assertEqual(e.inventory, {"wild_berries": 2, "boar_meat": 1}, "above the threshold: no eating")
        e.hunger = 40 * P
        e._settle()
        self.assertEqual(e.inventory, {"wild_berries": 2}, "the biggest food that fits")
        self.assertEqual((e.hunger, e.health, e.food_cooldown_ms), (75 * P, 61 * P, ap.FOOD_COOLDOWN_MS))
        e.hunger = 10 * P
        e._settle()
        self.assertEqual(e.inventory["wild_berries"], 2, "cooldown blocks the next bite")
        e.food_cooldown_ms = 0
        e._settle()
        self.assertEqual(e.inventory["wild_berries"], 1)
        self.assertEqual(e.log[-1]["type"], "eat")

    def test_hunger_drains_and_starvation_hurts_exactly(self):
        e = expedition()
        e.hunger, e.health = ap.HUNGER_DRAIN * 1000, 80 * P   # 1 second of hunger left
        e._apply_vitals(1000)
        self.assertEqual(e.hunger, 0)
        e._apply_vitals(2000)
        self.assertEqual(e.health, 77 * P)
        self.assertEqual(e.cause, "starvation")
        tough = expedition()
        tough.regular["endurance"] = 3000
        self.assertLess(tough._drain(), e._drain())

    def test_badly_hurt_goes_home_and_avoids_fights(self):
        e = expedition()
        e.health = 30 * P
        self.assertEqual(e._choose_goal()["kind"], "home")
        e.health = 45 * P
        goal = e._best_candidate(e._field({e._player()}))
        self.assertTrue(goal is None or goal["kind"] != "target")

    def test_danger_rises_with_depth(self):
        e = expedition()
        near, far = e.boar_hit(ChunkKey("forest", 0, 1)), e.boar_hit(ChunkKey("forest", 4, -2))
        self.assertGreater(far, near * 3)  # x1.5 per ring: ring 4 vs ring 1


class LifeTests(unittest.TestCase):
    def test_anchor_countdown_trade_and_explicit_next_life(self):
        e = expedition()
        e.inventory = {"stick": 3, "boar_hide": 1}
        e.regular["strength"] = 70
        e.dimensional["strength"] = 14
        e.health = 0
        e.cause = "boar"
        e.advance(0)
        self.assertEqual(e.mode(), "anchor")
        self.assertEqual(e.life, 1)
        self.assertEqual(e.anchor_ms, ap.ANCHOR_COUNTDOWN_MS)
        self.assertEqual(e._player(), e.anchor)
        with self.assertRaises(ValueError):
            e.anchor_action({"type": "trade", "item": "gold"})
        e.advance(9000)
        self.assertEqual(e.anchor_ms, ap.ANCHOR_COUNTDOWN_MS - 9000)
        e.anchor_action({"type": "trade", "item": "stick"})
        self.assertEqual((e.dust, e.inventory), (3, {"boar_hide": 1}))
        self.assertTrue(e.anchor_wait)
        restored = Expedition.from_dict(json.loads(dump(e)))
        self.assertEqual(dump(restored), dump(e))
        restored.advance(90_000)
        self.assertEqual(restored.life, 1)
        self.assertEqual(restored.anchor_ms, e.anchor_ms)
        restored.anchor_action({"type": "trade", "item": "boar_hide"})
        self.assertEqual(restored.dust, 7)
        restored.anchor_action({"type": "begin_life"})
        self.assertEqual((restored.life, restored.dust, restored.inventory), (2, 7, {}))
        self.assertEqual(restored.regular["strength"], 0)
        self.assertEqual(restored.dimensional["strength"], 14)

    def test_anchor_auto_begins_and_splits_match(self):
        a, b = expedition(), expedition()
        for e in (a, b):
            e.health = 0
            e.advance(0)
        a.advance(ap.ANCHOR_COUNTDOWN_MS + 1000)
        for _ in range((ap.ANCHOR_COUNTDOWN_MS + 1000) // 100):
            b.advance(100)
        self.assertEqual(dump(a), dump(b))
        self.assertEqual(a.life, 2)

    def test_anchor_session_snapshot_and_trade_input(self):
        e = expedition()
        e.inventory = {"stick": 2}
        e.health = 0
        e.advance(0)
        session = BrowserSession(e.game, e)
        frame = session.state(now=1)
        self.assertEqual(frame["expedition"]["anchor_space"]["remaining_ms"], ap.ANCHOR_COUNTDOWN_MS)
        self.assertEqual((frame["spots"], frame["targets"]), ([], []))
        body = {"move": None, "attack": False, "paused": False, "known": [],
                "action": {"type": "trade", "item": "stick"}}
        frame = session.input(body, now=1)
        self.assertEqual(frame["expedition"]["dust"], 2)
        self.assertTrue(frame["expedition"]["anchor_space"]["waiting"])
        session.input(body, now=2)  # a retried whole-stack offer cannot duplicate dust
        self.assertEqual(e.dust, 2)

    def test_v3_save_migrates_to_new_location_pool(self):
        e = expedition()
        e.advance(40_000)
        old = json.loads(dump(e))
        for key in ("dust", "anchor_ms", "anchor_wait", "monster_ms", "prayers_this_life"):
            del old[key]
        old.update(schema_version=3, encounters="encounters-v3")
        migrated = Expedition.from_dict(old)
        self.assertEqual((migrated.regular, migrated.dimensional), (e.regular, e.dimensional))
        self.assertEqual((migrated.life, migrated.dust), (e.life, 0))
        self.assertEqual(migrated.to_dict()["encounters"], "encounters-v5")

    def test_v4_save_keeps_progress_when_shrines_become_active_prayer(self):
        e = expedition()
        e.advance(40_000)
        old = json.loads(dump(e))
        old.pop("monster_ms")
        old.pop("prayers_this_life")
        old.update(schema_version=4, encounters="encounters-v4", task=None, goal=None, blessing=23)
        old["budget"]["wayside_shrine"] = 1
        old["spawned"]["wayside_shrine"] = 0
        migrated = Expedition.from_dict(old)
        self.assertEqual((migrated.regular, migrated.dimensional, migrated.blessing),
                         (e.regular, e.dimensional, 23))
        self.assertEqual(migrated.to_dict()["encounters"], "encounters-v5")

    def test_bulk_ticks_slices_and_reload_identical_across_a_death(self):
        T = 360000
        bulk, ticks, odd = expedition(), expedition(), expedition()
        bulk.advance(T)
        self.assertGreaterEqual(bulk.life, 2)
        for _ in range(T // 20):
            ticks.advance(20)
        rng, left = random.Random(9), T
        while left:
            step = min(left, rng.choice([0, 1, 13, 120, 777, 4321]))
            odd.advance(step)
            left -= step
        self.assertEqual(dump(bulk), dump(ticks))
        self.assertEqual(dump(bulk), dump(odd))
        first = expedition()
        first.advance(123457)
        resumed = Expedition.from_dict(json.loads(dump(first)))
        resumed.advance(T - 123457)
        self.assertEqual(dump(resumed), dump(bulk))

    def test_death_returns_to_anchor_keeping_dimensional_progress(self):
        e = expedition()
        old_game = e.game
        while e.life == 1:
            e.advance(20)
            before = (dict(e.dimensional), e.depth, e.best_depth)
        self.assertIsNot(e.game, old_game)
        self.assertEqual(e.report["title"], "Life 1 ends")
        self.assertIn("Returning to anchor...", e.report["lines"])
        self.assertTrue(any(line.startswith("Cause:") for line in e.report["lines"]))
        self.assertEqual(e.dimensional, before[0])
        self.assertTrue(any(e.dimensional.values()))
        self.assertEqual(set(e.regular.values()), {0})
        self.assertEqual((e.inventory, e.completed, e.depth), ({}, set(), 0))
        self.assertGreater(e.hunger, 99 * P)  # fresh life; at most one tick has drained
        self.assertEqual(e.best_depth, before[2])
        self.assertEqual(e._player(), e.anchor)
        self.assertEqual(e.log[-1]["type"], "life")

    def test_saves_migrate_v1_and_reject_malformed(self):
        e = expedition()
        e.advance(5000)
        v1 = {"schema_version": 1, "encounters": "encounters-v1", "exploration": e.game.to_dict(),
              "completed": [], "xp": {a: 7 for a in e.regular}, "log": [], "sequence": 0,
              "decisions": 3, "skills": [], "task": None, "goal": None}
        migrated = Expedition.from_dict(json.loads(canonical_json(v1)))
        self.assertEqual(set(migrated.regular.values()), {70})
        self.assertEqual(migrated.life, 1)
        for mutate in (lambda d: d.update(schema_version=6), lambda d: d.update(encounters="v0"),
                       lambda d: d.update(blessing=-1), lambda d: d.update(dust=-1),
                       lambda d: d.update(anchor_ms=-1), lambda d: d.update(anchor_wait=True),
                       lambda d: d["budget"].pop("bramble_boar"),
                       lambda d: d.update(admitted=[["enc:x", "dragon"]]),
                       lambda d: d.update(screened_chunks=[1]),
                       lambda d: d["regular"].update(charisma=1), lambda d: d.update(skills=["fly"]),
                       lambda d: d.update(hunger=ap.VITAL_MAX + 1), lambda d: d.update(inventory=[["gold", 1]]),
                       lambda d: d.update(inventory=[["stick", 21]]), lambda d: d.update(cause="dragon"),
                       lambda d: d.update(best_depth=-1),
                       lambda d: d.update(task={"type": "dance", "spot": None, "elapsed_ms": 0, "duration_ms": 1})):
            data = json.loads(dump(e))
            mutate(data)
            with self.assertRaises(ValueError):
                Expedition.from_dict(data)


def skip_prologue(e):
    while e.in_prologue:
        e.advance(500)
    return e


class PrologueTests(unittest.TestCase):
    def test_new_expedition_opens_with_wake_stand_listen_not_a_report(self):
        e = expedition()
        self.assertEqual(e.report["lines"], [])
        stages, seen = [], set()
        while e.in_prologue:
            p = e.prologue()
            if p["stage"] not in seen:
                seen.add(p["stage"])
                stages.append(p["stage"])
                self.assertEqual(e.activity()["name"], ap.PROLOGUE_NAMES[p["stage"]])
                self.assertEqual(e.mode(), "prologue")
            self.assertEqual(e._player(), e.anchor, "the avatar does not wander during the opening")
            e.advance(250)
        self.assertEqual(stages, ["awaken", "stand_up", "listen"])
        self.assertEqual(e.total_ms, sum(ap.PROLOGUE_MS.values()))
        self.assertEqual(e.log[-1]["type"], "lore")
        ex, ey = e.elder
        self.assertIn(abs(ex - e.anchor[0]) + abs(ey - e.anchor[1]), (1, 2), "the old man stands beside you")
        self.assertIsNone(e.prologue())
        e.advance(20000)
        self.assertNotEqual(e.mode(), "prologue")

    def test_prologue_lines_and_snapshot(self):
        e = expedition()
        frame = BrowserSession(e.game, e).state(0)
        p = frame["expedition"]["prologue"]
        self.assertEqual((p["stage"], p["lines"]), ("awaken", list(ap.MEMORIES)))
        self.assertTrue(any("andit" in line for line in ap.MEMORIES))
        while e.prologue()["stage"] != "listen":
            e.advance(500)
        self.assertEqual(e.prologue()["lines"], list(ap.ELDER_LINES))
        self.assertIn("avatar", ap.ELDER_LINES[0])
        self.assertIn("pray", ap.ELDER_LINES[2])
        from dimensional_sim.world.models import DELTAS as D
        dx, dy = e.elder[0] - e.anchor[0], e.elder[1] - e.anchor[1]
        self.assertEqual(D[e.game.player.facing], ((dx > 0) - (dx < 0), (dy > 0) - (dy < 0)),
                         "the avatar turns to the old man")

    def test_prologue_is_partition_independent_and_save_safe(self):
        a, b = expedition(), expedition()
        a.advance(41000)
        for _ in range(41000 // 20):
            b.advance(20)
        self.assertEqual(dump(a), dump(b))
        c = expedition()
        c.advance(7777)
        c = Expedition.from_dict(json.loads(dump(c)))
        self.assertEqual(c.prologue()["stage"], "awaken")
        c.advance(41000 - 7777)
        self.assertEqual(dump(c), dump(a))


class SpawnWindowTests(unittest.TestCase):
    def test_windows_validate_and_roll_inside_their_range(self):
        from dimensional_sim.world.encounters import roll_window, spawn_window
        for bad in ({"window": (3, 1)}, {"window": [1, 2]}, {"window": (-1, 2)}):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                replace(BY_ID["bramble_berries"], **bad)
        with self.assertRaises(ValueError):
            replace(BY_ID["mossy_stone"], blessing=1)  # only prayers bless
        boar = BY_ID["bramble_boar"]
        rolls = {roll_window(boar, seed) for seed in range(200)}
        self.assertEqual(rolls, set(range(boar.window[0], boar.window[1] + 1)))
        self.assertIsNone(roll_window(BY_ID["animal_tracks"], 1), "non-food stays unlimited")
        low, high = boar.window
        self.assertEqual(spawn_window(boar, 3), (low + 1, high + 3), "mastery widens the window")
        food = {e.id for e in DARK_FOREST if any(ITEMS[l.item].kind == "food" for l in e.loot)}
        self.assertTrue(all(BY_ID[i].window for i in food), "every food source is capped")

    def test_caps_limit_new_ground_and_reroll_each_life(self):
        e = skip_prologue(expedition())
        decisions, original = [], e._admit

        def admit(ident, encounter):
            limit = e.budget.get(encounter)
            active = e._active(encounter) if limit is not None else None
            result = original(ident, encounter)
            decisions.append((encounter, limit, active, result))
            return result
        e._admit = admit
        budgets, life = [dict(e.budget)], e.life
        for _ in range(900):
            e.advance(400)
            if e.life != life:
                life = e.life
                budgets.append(dict(e.budget))
        for encounter, limit, active, admitted in decisions:
            if limit is not None:
                self.assertEqual(admitted, active < limit, encounter)
        self.assertGreaterEqual(len(budgets), 2)
        refused = {d[0] for d in decisions if not d[3]}
        self.assertTrue(refused & {"bramble_berries", "gnarled_tree"}, "scarce food is turned away when capped")
        respawned = [d for d in decisions if d[3] and d[1] is not None]
        self.assertGreater(len(respawned), sum(budgets[0].values()), "finished spots free their slot")

    def test_screened_boars_never_reward(self):
        e = expedition()
        rejected = [t for t in e.game.targets.values() if t.id in e.screened_targets and t.id not in e.admitted]
        e.budget["bramble_boar"] = 0
        e.screened_targets.clear()
        for t in e.game.targets.values():
            if not t.id.startswith("enc:"):
                t.hp = 3
                e.admitted.pop(t.id, None)
        e._screen()
        dropped = [t for t in e.game.targets.values() if not t.id.startswith("enc:")]
        self.assertTrue(dropped and all(t.hp == 0 for t in dropped))
        xp = dict(e.regular)
        e._settle()
        self.assertEqual(e.regular, xp, "a boar that never appeared gives nothing")
        self.assertIsInstance(rejected, list)


class PrayerTests(unittest.TestCase):
    def test_prayer_is_rare_timed_active_action_not_a_map_spot(self):
        from types import SimpleNamespace
        from dimensional_sim.world.seeds import derive_seed
        self.assertNotIn("wayside_shrine", BY_ID)
        e = skip_prologue(expedition())
        spot = next(SimpleNamespace(id=f"enc:forest:9:9:{i}") for i in range(1000)
                    if derive_seed(e.game.world.world_seed, "after-location-v5", e.life,
                                   f"enc:forest:9:9:{i}") % 100 < ap.PRAYER_CHANCE)
        e._after_location(spot, False)
        self.assertNotEqual(e.task["type"], "pray", "offline actions cannot grant prayer")
        e._after_location(spot, True)
        self.assertEqual(e.task["type"], "pray")
        self.assertEqual(e.blessing, 0, "prayer pays only after its full duration")
        e.advance(ap.PRAYER_MS - 1)
        self.assertEqual(e.blessing, 0)
        e.advance(1)
        self.assertEqual(e.blessing, 1)
        self.assertEqual(e.log[-1]["type"], "blessing")
        e._after_location(spot, True)
        self.assertNotEqual(e.task["type"], "pray", "one prayer at most per life")

    def test_quiet_actions_are_common_and_grant_nothing(self):
        from types import SimpleNamespace
        e = skip_prologue(expedition())
        before = (dict(e.regular), dict(e.dimensional), e.blessing, dict(e.inventory))
        quiet = 0
        for i in range(100):
            e._after_location(SimpleNamespace(id=f"enc:forest:8:8:{i}"), False)
            quiet += e.task["type"] in ("think", "contemplate")
        self.assertGreaterEqual(quiet, 55)
        self.assertEqual((e.regular, e.dimensional, e.blessing, e.inventory), before)

    def test_blessing_persists_across_lives_and_saves(self):
        e = expedition()
        e.blessing = 1
        first_death(e)
        self.assertGreaterEqual(e.blessing, 1)
        self.assertIn(f"Blessing power: {e.blessing}", e.report["lines"])
        self.assertTrue(any(line.startswith("Forest bounty") for line in e.report["lines"]))
        self.assertEqual(Expedition.from_dict(json.loads(dump(e))).blessing, e.blessing)

    def test_v2_saves_upgrade_without_the_prologue(self):
        e = skip_prologue(expedition())
        e.advance(60000)
        data = json.loads(dump(e))
        for key in ("blessing", "budget", "spawned", "admitted", "screened_chunks", "screened_targets",
                    "dust", "anchor_ms", "anchor_wait", "monster_ms", "prayers_this_life"):
            del data[key]
        for entry in data["log"]:
            del entry["blessing"]
        data["log"] = [entry for entry in data["log"] if entry["type"] in ("encounter", "eat", "rest", "life")]
        data.update(schema_version=2, encounters="encounters-v2", task=None)
        upgraded = Expedition.from_dict(data)
        self.assertFalse(upgraded.in_prologue)
        self.assertEqual((upgraded.regular, upgraded.inventory), (e.regular, e.inventory))
        self.assertFalse(any(i.startswith("enc:") for i in upgraded.completed))
        upgraded.advance(30000)
        self.assertEqual(Expedition.from_dict(json.loads(dump(upgraded))).to_dict(), upgraded.to_dict())


class PursuitTests(unittest.TestCase):
    def test_rare_boar_interrupts_a_thought_and_survives_reload(self):
        e = skip_prologue(expedition())
        px, py = e._player()
        position = next((px + dx, py + dy) for dx, dy in DELTAS.values()
                        if e._walkable(e._grid(), px + dx, py + dy))
        key = e.game.player.chunk
        w, h = e._dims()
        ident = "enc:forest:0:0:99"
        e.game.targets[ident] = Target(ident, key, position[0] % w, position[1] % h, 3)
        e.admitted[ident] = "bramble_boar"
        e.task = {"type": "think", "spot": None, "elapsed_ms": 1000, "duration_ms": 3000}
        e.monster_ms = ap.MONSTER_STEP_MS
        e._settle()
        self.assertIsNone(e.task)
        self.assertEqual(e.goal["id"], ident)
        self.assertEqual(e.log[-1]["type"], "ambush")
        self.assertEqual(dump(Expedition.from_dict(json.loads(dump(e)))), dump(e))


class AutopilotSessionTests(unittest.TestCase):
    MOVE = {"move": "east", "attack": False, "paused": False, "known": []}

    def test_locked_take_control_ignores_player_input(self):
        e = expedition()
        session = BrowserSession(e.game, e)
        reference = expedition()
        for i in range(50):
            frame = session.input(self.MOVE, i * .02)
            session.step(i * .02)
            reference.advance(20)
        self.assertEqual(frame["expedition"]["control"], "auto")
        self.assertEqual(dump(e), dump(reference))
        ex = frame["expedition"]
        for key in ("vitals", "inventory", "attributes", "life", "depth", "best_depth", "report", "anchor", "total_ms"):
            self.assertIn(key, ex)

    def test_session_follows_new_lives(self):
        e = expedition()
        session = BrowserSession(e.game, e)
        first_death(e, step=20)
        self.assertIs(session.game, e.game)
        frame = session.state()
        self.assertEqual(frame["expedition"]["life"], 2)
        self.assertEqual(frame["player"]["x"], e.anchor[0])

    def test_unlocked_control_takes_over_then_autopilot_resumes(self):
        e = expedition()
        e.unlock("take_control")
        session = BrowserSession(e.game, e)
        start = e.game.player.x
        self.assertEqual(session.input(self.MOVE, 0)["expedition"]["control"], "manual")
        for i in range(10):
            session.input(self.MOVE, i * .02)
            session.step(i * .02)
        self.assertGreater(e.game.player.x, start)
        clock = e.total_ms
        session.step(MANUAL_HOLD + 1)
        self.assertEqual(session.state()["expedition"]["control"], "auto")
        self.assertEqual(e.total_ms, clock + 20)


if __name__ == "__main__":
    unittest.main()
