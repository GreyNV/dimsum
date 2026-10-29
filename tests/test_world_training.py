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
        old = {k: v for k, v in data.items() if k not in saves.V25_FIELDS}
        old["schema_version"] = 24
        loaded = Expedition.from_dict(old)
        self.assertEqual(loaded.walk, {"agility": 0, "endurance": 0, "perception": 0})
        self.assertEqual(loaded.to_dict()["schema_version"], SCHEMA_VERSION)


if __name__ == "__main__":
    unittest.main()
