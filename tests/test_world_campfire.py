"""Campfires: made anywhere from 3 sticks; resting by one heals like resting at the anchor camp."""
import json
import unittest

from dimensional_sim.world.autopilot import REST_REGEN, RETREAT_BELOW, Expedition
from dimensional_sim.world.autopilot import saves
from dimensional_sim.world.catalog import BY_ID
from dimensional_sim.world.models import ChunkKey
from dimensional_sim.world.runtime import InputCommand
from dimensional_sim.world.seeds import canonical_json
from tests.test_world_autopilot import expedition
from save_fixture import v17

POINT = 1_000_000


def far_and_hurt(seed=482910, sticks=5, bought=True):
    """An avatar two chunks from the anchor, badly hurt, fed, carrying sticks (campfire bought)."""
    e = expedition(seed)
    if bought:
        e.unlocked.add("campfire")
    while e.in_prologue:
        e.advance(500)
    key = ChunkKey(e.dimension, 2, 0)
    chunk = e.game.world.get(key)
    e.game._enter(key)
    e.game.player.chunk = key
    spawn = next(s for s in chunk.asset.spawns if s.kind == "player")
    e.game.player.x, e.game.player.y = spawn.x, spawn.y
    e.game._reveal()
    e._screen()
    e.health = RETREAT_BELOW - 5 * POINT
    e.hunger = 100 * POINT  # food should wait until it restores its full hunger value
    e.inventory = {"stick": sticks, "wild_berries": 2}
    e.goal = e.task = None
    return e


class CampfireTests(unittest.TestCase):
    def test_a_badly_hurt_avatar_far_from_camp_makes_a_fire_only_then(self):
        e = far_and_hurt()
        self.assertEqual(e._need_action().id, "make_campfire")
        healthy = far_and_hurt()
        healthy.health = 80 * POINT
        self.assertNotEqual(getattr(healthy._need_action(), "id", None), "make_campfire")
        poor = far_and_hurt(sticks=2)
        self.assertNotEqual(getattr(poor._need_action(), "id", None), "make_campfire", "a fire costs 3 sticks")
        unbought = far_and_hurt(bought=False)
        self.assertNotEqual(getattr(unbought._need_action(), "id", None), "make_campfire", "the skill is bought with ash")
        self.assertFalse(unbought.can_make_fire())

    def test_the_fire_heals_like_the_anchor_and_the_autopilot_rests_there(self):
        e = far_and_hurt()
        e._start_self(e._need_action())
        e.advance(e.task["duration_ms"])
        self.assertIsNotNone(e.campfire)
        self.assertEqual(e.inventory["stick"], 2)
        seat = (e.campfire["x"], e.campfire["y"])
        fire = (e.campfire["fire_x"], e.campfire["fire_y"])
        self.assertEqual(abs(seat[0] - fire[0]) + abs(seat[1] - fire[1]), 1, "the fire burns beside the avatar")
        self.assertEqual(e._rest_goal()["id"], "campfire")
        e.advance(1)
        self.assertEqual(e.task["type"], "rest")
        self.assertEqual(e._player(), seat)
        resting = e._health_rate()
        e.task = None
        self.assertEqual(resting - e._health_rate(), REST_REGEN, "the same rest bonus as the anchor camp")
        for _ in range(30):
            e.advance(5_000)
            if "Rested by the campfire." in [row["text"] for row in e.log]:
                break
        self.assertIn("Rested by the campfire.", [row["text"] for row in e.log])
        self.assertGreater(e.health, 85 * POINT)
        self.assertFalse(e._hurt_far(), "no second fire next to the first")

    def test_the_fire_is_saved_migrated_and_gone_next_life(self):
        e = far_and_hurt()
        e._start_self(BY_ID["make_campfire"])
        e.advance(e.task["duration_ms"])
        again = Expedition.from_dict(json.loads(canonical_json(e.to_dict())))
        self.assertEqual(again.campfire, e.campfire)
        old = {k: v for k, v in v17(e.to_dict()).items() if k not in (*saves.V14_FIELDS, *saves.V15_FIELDS, *saves.V16_FIELDS, *saves.V17_FIELDS)}
        old["schema_version"] = 13
        self.assertIsNone(Expedition.from_dict(old).campfire)
        bad = e.to_dict()
        bad["campfire"] = {**bad["campfire"], "fire_x": bad["campfire"]["x"] + 5}
        with self.assertRaises(ValueError):
            Expedition.from_dict(bad)
        e._new_life_state()
        self.assertIsNone(e.campfire)

    def test_the_skill_makes_a_fire_and_standing_still_by_it_rests(self):
        e = far_and_hurt()
        e.health = 60 * POINT
        e.anchor_action({"type": "campfire"})
        self.assertEqual(e.task["type"], "make_campfire")
        e.possess()   # the player holds the avatar still beside the fire
        e.advance_manual(e.task["duration_ms"])
        self.assertIsNotNone(e.campfire)
        e.advance_manual(1000)
        self.assertEqual(e.task["type"], "rest", "standing still beside the fire rests")
        e.advance_manual(0, InputCommand("east"))
        self.assertIsNone(e.task, "walking away stops resting")
        e.inventory = {}
        with self.assertRaises(ValueError):
            e.anchor_action({"type": "campfire"})

    def test_the_snapshot_shows_the_fire_and_the_context_choice(self):
        from dimensional_sim.world.session import snapshot
        e = far_and_hurt()
        view = snapshot(e.game, expedition=e)["expedition"]
        self.assertEqual(view["skill_slots"][1]["name"], "Possess")
        self.assertEqual(view["skill_slots"][2]["name"], "Dimensional Shift")
        self.assertEqual(view["location_context"]["actions"][0]["name"], "Make a campfire")
        self.assertFalse(view["location_context"]["actions"][0]["reasons"])
        self.assertIsNone(view["campfire"])
        e._start_self(BY_ID["make_campfire"])
        e.advance(e.task["duration_ms"])
        view = snapshot(e.game, expedition=e)["expedition"]
        self.assertEqual(view["campfire"], {"x": e.campfire["fire_x"], "y": e.campfire["fire_y"]})


if __name__ == "__main__":
    unittest.main()
