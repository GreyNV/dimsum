"""The anchor and possession (schema 18): a new game opens at the anchor, the anchor can be
contacted mid-life without dying (the world waits), and manual control is possession -
30 seconds of quicker hands, then a minute's recharge. Blessings and boons are gone."""
import json
import unittest

from dimensional_sim.world import autopilot as ap
from dimensional_sim.world.autopilot import Expedition
from dimensional_sim.world.catalog import BY_ID
from dimensional_sim.world.runtime import Exploration, InputCommand
from dimensional_sim.world.seeds import canonical_json
from dimensional_sim.world.session import BrowserSession
from dimensional_sim.world.web import new_world
from save_fixture import v17

IDLE = {"move": None, "attack": False, "paused": False, "known": []}


def dump(e):
    return canonical_json(e.to_dict())


def started(seed=482910):
    e = Expedition(Exploration(new_world(seed), "forest"))
    while e.in_prologue:
        e.advance(500)
    e.goal = e.task = None
    e.unlocked.add("return_anchor")
    return e


class OpeningTests(unittest.TestCase):
    def test_a_new_game_waits_at_the_anchor_then_plays_the_prologue(self):
        e = Expedition(Exploration(new_world(7), "forest"), opening=True)
        self.assertEqual((e.mode(), e.opening, e.life, e.in_prologue), ("anchor", True, 1, False))
        e.advance(120_000)
        self.assertEqual(e.total_ms, 0, "the anchor waits for the player")
        view = BrowserSession(e.game, e).state(0)["expedition"]
        self.assertEqual(view["anchor_space"]["kind"], "opening")
        self.assertEqual([r["id"] for r in view["shop"]], ["return_anchor", "campfire"], "the shop is shown before the first life")
        again = Expedition.from_dict(json.loads(dump(e)))
        self.assertEqual(dump(again), dump(e))
        e.anchor_action({"type": "begin_life"})
        self.assertEqual((e.opening, e.life, e.prologue()["stage"]), (False, 1, "awaken"))
        while e.in_prologue:
            e.advance(500)
        self.assertEqual(e.life, 1)

    def test_simulations_still_start_in_the_prologue(self):
        e = Expedition(Exploration(new_world(7), "forest"))
        self.assertEqual((e.opening, e.prologue()["stage"]), (False, "awaken"))


class ContactTests(unittest.TestCase):
    def test_contact_requires_the_ten_ash_skill_and_recharges_for_five_minutes(self):
        e = started()
        e.unlocked.remove("return_anchor")
        with self.assertRaisesRegex(ValueError, "locked"):
            e.anchor_action({"type": "contact"})
        e.health = 0
        e.advance(0)
        e.ash = 10
        e.anchor_action({"type": "unlock", "id": "return_anchor"})
        self.assertEqual(e.ash, 0)
        e.anchor_action({"type": "begin_life"})
        e.anchor_action({"type": "contact"})
        e.anchor_action({"type": "resume"})
        self.assertEqual(e.contact_ready_ms, e.total_ms + ap.CONTACT_COOLDOWN_MS)
        self.assertEqual(ap.CONTACT_COOLDOWN_MS, 300_000)
        with self.assertRaisesRegex(ValueError, "recharging"):
            e.anchor_action({"type": "contact"})

    def test_contacting_the_anchor_freezes_the_world_until_resumed(self):
        e = started()
        e.inventory, e.ash = {"stick": 3}, 40
        session = BrowserSession(e.game, e)
        frame = session.input({**IDLE, "action": {"type": "contact"}}, 0)
        ex = frame["expedition"]
        self.assertEqual((ex["anchor_space"]["kind"], ex["mode"]), ("contact", "anchor"))
        self.assertTrue(frame["spots"] is not None and ex["life"] == 1)
        clock, health, hunger = e.total_ms, e.health, e.hunger
        session.advance_ms(90_000, 1)
        self.assertEqual((e.total_ms, e.health, e.hunger), (clock, health, hunger))
        session.input({**IDLE, "action": {"type": "unlock", "id": "campfire"}}, 2)
        self.assertEqual((e.ash, e.inventory), (15, {"stick": 3}), "buying never touches the life")
        frame = session.input({**IDLE, "action": {"type": "begin_life"}}, 2)
        self.assertIn("anchor space", frame["expedition"]["action_error"])
        frame = session.input({**IDLE, "action": {"type": "resume"}}, 3)
        self.assertIsNone(frame["expedition"]["anchor_space"])
        self.assertEqual(frame["expedition"]["skill_slots"][0]["state"], "cooldown")
        session.advance_ms(1000, 4)
        self.assertEqual(e.total_ms, clock + 1000)

    def test_contact_is_not_saved_and_needs_a_life(self):
        e = started()
        e.anchor_action({"type": "contact"})
        loaded = Expedition.from_dict(json.loads(dump(e)))
        self.assertFalse(loaded.contact, "a reload steps back into the life")
        fresh = Expedition(Exploration(new_world(3), "forest"))
        with self.assertRaisesRegex(ValueError, "not yet"):
            fresh.anchor_action({"type": "contact"})
        e.health = 0
        e.anchor_action({"type": "resume"})
        e.advance(0)
        self.assertIsNotNone(e.anchor_ms)
        with self.assertRaisesRegex(ValueError, "already at the anchor"):
            e.anchor_action({"type": "contact"})


class PossessionTests(unittest.TestCase):
    def test_possession_lasts_thirty_seconds_then_recharges_for_a_minute(self):
        e = started()
        e.anchor_action({"type": "possess"})
        self.assertTrue(e.possessing)
        self.assertEqual(e.log[-1]["type"], "possess")
        e.advance_manual(ap.POSSESS_MS - 1)
        self.assertTrue(e.possessing)
        e.advance_manual(1)
        self.assertFalse(e.possessing)
        self.assertEqual(e.possession()["ready_in_ms"], ap.POSSESS_COOLDOWN_MS)
        with self.assertRaisesRegex(ValueError, "recharging"):
            e.possess()
        e.advance(ap.POSSESS_COOLDOWN_MS)
        e.possess()
        e.release()
        self.assertEqual(e.possession()["ready_in_ms"], ap.POSSESS_COOLDOWN_MS, "an early release recharges from then")

    def test_possession_is_partition_independent_and_crosses_into_the_autopilot(self):
        a, b = started(), started()
        for e in (a, b):
            e.possess()
        a.advance_manual(ap.POSSESS_MS + 5_000, InputCommand())
        for _ in range((ap.POSSESS_MS + 5_000) // 20):
            b.advance_manual(20, InputCommand())
        self.assertEqual(dump(a), dump(b))
        self.assertFalse(a.possessing)

    def test_possessed_hands_move_and_work_twenty_percent_faster(self):
        e = started()
        walk, work = e.game.step_interval_ms, e.speed("perception")
        e.possess()
        e.game.load_percent = e.load_percent()
        self.assertEqual(e.game.step_interval_ms, e.game.movement_interval_ms * (100 * 100 // ap.POSSESS_SPEED_PERCENT) // 100)
        self.assertLess(e.game.step_interval_ms, walk)
        self.assertEqual(e.speed("perception"), work * ap.POSSESS_SPEED_PERCENT // 100)
        action = BY_ID["bramble_berries"]
        from dimensional_sim.world.progression import scaled_ms
        self.assertLess(scaled_ms(action.duration_ms, e.speed(action.attribute)), scaled_ms(action.duration_ms, work))

    def test_input_steers_only_a_possessed_avatar(self):
        e = started()
        session = BrowserSession(e.game, e)
        self.assertEqual(session.input({**IDLE, "move": "east"}, 0)["expedition"]["control"], "auto")
        frame = session.input({**IDLE, "move": "east", "action": {"type": "possess"}}, 0)
        self.assertEqual(frame["expedition"]["control"], "manual")
        slot = frame["expedition"]["skill_slots"][1]
        self.assertEqual((slot["name"], slot["state"], slot["remaining_ms"]), ("Possess", "active", ap.POSSESS_MS))
        frame = session.input({**IDLE, "action": {"type": "release"}}, 1)
        self.assertEqual(frame["expedition"]["control"], "auto")

    def test_death_contact_and_reload_end_possession(self):
        e = started()
        e.possess()
        e.anchor_action({"type": "contact"})
        self.assertFalse(e.possessing)
        e.anchor_action({"type": "resume"})
        e.advance(ap.POSSESS_COOLDOWN_MS)
        e.possess()
        loaded = Expedition.from_dict(json.loads(dump(e)))
        self.assertTrue(loaded.possessing, "possession is saved")
        loaded.advance(10)   # nobody holds the avatar after a reload: the auto-pilot drives
        self.assertFalse(loaded.possessing)
        e.health = 0
        e.advance_manual(10)
        self.assertIsNotNone(e.anchor_ms)
        self.assertFalse(e.possessing)


class MigrationTests(unittest.TestCase):
    def test_schema_seventeen_preserves_the_paid_return_skill(self):
        e = started()
        old = v17(e.to_dict())
        old.update(blessing=20, boon="iron_skin", boon_next="bountiful_path", return_ready_ms=5, ash=3,
                   unlocked=["return_anchor", "climbing"], skills=["take_control"])
        old["log"].append({**old["log"][-1], "seq": old["log"][-1]["seq"] + 1, "type": "blessing", "blessing": 1})
        old["journal"]["actions"]["pray"] = 4
        loaded = Expedition.from_dict(json.loads(json.dumps(old)))
        self.assertEqual(loaded.ash, 3)
        self.assertEqual(loaded.unlocked, {"return_anchor", "climbing", "campfire"})
        self.assertEqual(loaded.contact_ready_ms, 5)
        self.assertNotIn("pray", loaded.journal["actions"])
        self.assertEqual(loaded.log[-1]["type"], "lore")
        saved = loaded.to_dict()
        self.assertEqual(saved["schema_version"], ap.SCHEMA_VERSION)
        for gone in ("blessing", "boon", "boon_next", "skills", "return_ready_ms", "prayers_this_life"):
            self.assertNotIn(gone, saved)


if __name__ == "__main__":
    unittest.main()
