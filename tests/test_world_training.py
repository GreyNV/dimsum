"""Training (autopilot/training.py): XP from base time, per landed hit, per tile walked; movement
from the Agility multiplier on a log curve (docs/design/STATS_AND_ENEMIES_AUDIT.md)."""

import json
import unittest

from dimensional_sim.world import tuning
from dimensional_sim.world.autopilot import Expedition, saves
from dimensional_sim.world.autopilot.constants import SCHEMA_VERSION
from dimensional_sim.world.catalog import ACTIONS, BY_ID, action_xp
from dimensional_sim.world.runtime import Exploration
from dimensional_sim.world.web import new_world


def started(seed=482910, minutes=4):
    e = Expedition(Exploration(new_world(seed), "forest"))
    for _ in range(minutes):
        e.advance(60_000)
    return e


class XpRuleTests(unittest.TestCase):
    def test_action_xp_follows_base_time_and_rarity(self):
        for action in ACTIONS:
            if action.xp == 0 or action.category == "fight":
                continue
            with self.subTest(action=action.id):
                self.assertEqual(action.xp, action_xp(action))
        berries = BY_ID["bramble_berries"]   # 2.4 s, common
        self.assertEqual(berries.xp, 2400 * tuning.XP_PER_SECOND // 1000)

    def test_a_fight_is_worth_its_hit_points_and_the_finish(self):
        boar = BY_ID["bramble_boar"]
        self.assertEqual(boar.xp, boar.hp * tuning.FIGHT_XP_PER_HP * (100 + tuning.FINISH_XP_PERCENT) // 100)


class WalkingTests(unittest.TestCase):
    def test_walking_trains_agility_endurance_and_perception(self):
        e = started()
        self.assertGreater(e.game.moved_tiles + sum(e.walk.values()) + e.regular["agility"], 0)
        for attribute in ("agility", "endurance", "perception"):
            self.assertGreater(e.regular[attribute], 0, attribute)

    def test_time_slicing_never_changes_the_xp(self):
        a = Expedition(Exploration(new_world(7), "forest"))
        b = Expedition(Exploration(new_world(7), "forest"))
        a.advance(120_000)
        for _ in range(120):
            b.advance(1_000)
        self.assertEqual(a.regular, b.regular)
        self.assertEqual(a.walk, b.walk)

    def test_movement_bonus_is_ten_percent_per_decade_of_agility(self):
        e = started(minutes=0)
        self.assertEqual(e.move_bonus_permille(), 0)
        e.regular["agility"] = 10 ** 6   # far past the soft cap
        bonus = e.move_bonus_permille()
        self.assertGreater(bonus, 0)
        self.assertLessEqual(bonus, 100)   # the soft cap keeps a regular multiplier under x10
        self.assertLess(e.load_percent(), 100)


class SaveTests(unittest.TestCase):
    def test_walk_remainders_round_trip_and_v24_saves_load(self):
        e = started()
        data = json.loads(json.dumps(e.to_dict()))
        self.assertEqual(Expedition.from_dict(data).walk, e.walk)
        old = {k: v for k, v in data.items() if k not in saves.V25_FIELDS + saves.V26_FIELDS + saves.V27_FIELDS}
        old["schema_version"] = 24
        loaded = Expedition.from_dict(old)
        self.assertEqual(loaded.walk, {"agility": 0, "endurance": 0, "perception": 0})
        self.assertEqual(loaded.to_dict()["schema_version"], SCHEMA_VERSION)


class StarredPatternTests(unittest.TestCase):
    def test_an_elder_strikes_twice_and_warns_for_less_long(self):
        from dimensional_sim.world.catalog import FIGHT_PATTERNS, FIGHT_TIERS
        from dimensional_sim.world.runtime import Target
        e = started(minutes=0)
        key = e.game.player.chunk
        target = Target("enc:test:elder", key, e.game.player.x + 1, e.game.player.y, 30)
        e.game.targets[target.id] = target
        e.admitted[target.id] = "bramble_boar"
        e.tier_of = lambda ident: FIGHT_TIERS["elder"]
        e.hunting[target.id] = {"mode": "hunt", "since": 0, "ax": 0, "ay": 0, "ox": 0, "oy": 0, "left": 0, "n": 0}
        pattern = FIGHT_PATTERNS[e.enemy_of(target).pattern]
        px, py = e._player()
        e._after_strike(target, e.enemy_of(target), pattern, 0, px, py)
        self.assertEqual((e.hunting[target.id]["mode"], e.hunting[target.id]["n"]), ("windup", 1), "a second strike at once")
        e._after_strike(target, e.enemy_of(target), pattern, 1, px, py)
        self.assertEqual(e.hunting[target.id]["mode"], "recover", "then it is open to blows")
        self.assertLess(FIGHT_TIERS["elder"].windup_percent, FIGHT_TIERS["star"].windup_percent)
        self.assertLess(FIGHT_TIERS["star"].windup_percent, 100)


class EnduranceTests(unittest.TestCase):
    def test_endurance_slows_hunger_on_the_movement_curve_and_never_softens_bites(self):
        from dimensional_sim.world.catalog import ENEMIES
        e = started(minutes=0)
        key = e.game.player.chunk
        drain, bite = e._drain(), e.enemy_hit(key, ENEMIES["bramble_boar"])
        e.regular["endurance"] = 10 ** 6
        self.assertLess(e._drain(), drain)
        self.assertGreaterEqual(e._drain() * 110, drain * 100 - 110, "at most about 10% slower")
        self.assertEqual(e.enemy_hit(key, ENEMIES["bramble_boar"]), bite)


class PatternTests(unittest.TestCase):
    def _hunter(self, enemy_action, dx):
        from dimensional_sim.world.runtime import Target
        e = started(minutes=2)   # past the prologue: nothing hunts during it
        e.task = e.goal = None
        key = e.game.player.chunk
        px, py = e.game.player.x, e.game.player.y
        target = Target("enc:test:" + enemy_action, key, px + dx, py, 9)
        e.game.targets[target.id] = target
        e.admitted[target.id] = enemy_action
        return e, target

    def test_a_wolf_circles_round_the_avatar_before_it_lunges(self):
        e, wolf = self._hunter("night_wolf", 2)
        e.anchor = (e._player()[0] + 60, e._player()[1])   # far from the camp's safety
        start = e._global(wolf.chunk, wolf.x, wolf.y)
        e.hunting[wolf.id] = {"mode": "hunt", "since": e.total_ms, "ax": 0, "ay": 0, "ox": 0, "oy": 0, "left": 0, "n": 0}
        cells, modes = set(), []
        for _ in range(12):
            e.total_ms += 300
            e.monster_ms = 300
            e._pursue()
            modes.append(e.hunting[wolf.id]["mode"])
            cells.add(e._global(wolf.chunk, wolf.x, wolf.y))
        self.assertEqual(modes[0], "circle")
        self.assertGreater(len(cells), 2, "it moves round, not in")
        px, py = e._player()
        self.assertTrue(all(max(abs(x - px), abs(y - py)) >= 1 for x, y in cells))
        self.assertIn("hunt", modes[modes.index("circle"):], "then it comes in")
        self.assertNotEqual(start, e._global(wolf.chunk, wolf.x, wolf.y))

    def test_a_lurker_lies_hidden_until_it_notices_and_then_strikes_from_two_cells(self):
        from dimensional_sim.world.catalog import FIGHT_PATTERNS, ENEMIES
        from dimensional_sim.world.session import snapshot
        e, lurker = self._hunter("river_lurker", 2)
        pattern = FIGHT_PATTERNS[ENEMIES["river_lurker"].pattern]
        self.assertTrue(pattern.hidden)
        self.assertGreaterEqual(pattern.reach, 2)
        frame = snapshot(e.game, expedition=e, control="auto")
        self.assertTrue(next(t for t in frame["targets"] if t["id"] == lurker.id)["hidden"])
        e.anchor = (e._player()[0] + 60, e._player()[1])   # far from the camp's safety
        e.monster_ms = 300
        e._pursue()
        self.assertEqual(e.hunting[lurker.id]["mode"], "windup", "it strikes from where it lay")
        frame = snapshot(e.game, expedition=e, control="auto")
        self.assertFalse(next(t for t in frame["targets"] if t["id"] == lurker.id)["hidden"])


if __name__ == "__main__":
    unittest.main()
