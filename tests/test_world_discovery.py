"""Discovery chains, temporary leads, Journal choices and first death."""
import copy
import unittest

from dimensional_sim.world.autopilot import ANCHOR_COUNTDOWN_MS, Expedition
from dimensional_sim.world.catalog import BY_ID
from dimensional_sim.world.journal import record_action
from tests.test_world_autopilot import expedition


def tracks_with_lead(seed=482910):
    e = expedition(seed)
    record_action(e.journal, "animal_tracks")
    for number in range(100):
        e._apply_outcomes(BY_ID["animal_tracks"], f"self:tracks:{number}")
        if e.leads:
            return e
    raise AssertionError("seeded track outcomes never produced a lead")


class DiscoveryTests(unittest.TestCase):
    def test_tracks_lead_to_hunt_and_food_without_world_bucket_roll(self):
        e = None
        for seed in range(1, 30):
            candidate = tracks_with_lead(seed)
            follow = candidate.leads[0]
            candidate._reward(follow["id"], BY_ID[follow["action"]])
            if candidate.leads:
                e = candidate
                break
        self.assertIsNotNone(e, "seeded follow-up rolls must sometimes yield a hunt")
        self.assertIn("deer_sign", e.knowledge)
        self.assertEqual(e.lead_history[-1]["action"], "follow_deer_tracks")
        self.assertEqual(Expedition.from_dict(e.to_dict()).leads, e.leads)
        self.assertEqual([row["action"] for row in e.leads], ["hunt_deer"])
        hunt = e.leads[0]
        e._reward(hunt["id"], BY_ID[hunt["action"]])
        self.assertFalse(e.leads)
        self.assertGreaterEqual(e.inventory.get("venison", 0), 1)
        self.assertEqual(e.journal["actions"]["hunt_deer"], 1)

    def test_lead_expiry_is_save_safe_and_partition_independent(self):
        original = tracks_with_lead()
        original.leads[0]["expires_ms"] = original.total_ms + 2000
        bulk = Expedition.from_dict(original.to_dict())
        split = Expedition.from_dict(copy.deepcopy(original.to_dict()))
        bulk.advance(3000)
        for _ in range(30):
            split.advance(100)
        self.assertEqual(bulk.to_dict(), split.to_dict())
        self.assertFalse(bulk.leads)
        self.assertEqual(bulk.lead_history[-1]["status"], "expired")

    def test_first_death_anchor_auto_rebirth_and_trade_pause(self):
        e = expedition()
        e.inventory = {"stick": 4}
        e.health, e.cause = 0, "starvation"
        e.advance(0)
        self.assertEqual(e.life, 1)
        self.assertEqual(e._player(), e.anchor)
        self.assertEqual(e.anchor_ms, ANCHOR_COUNTDOWN_MS)
        saved = Expedition.from_dict(e.to_dict())
        saved.advance(ANCHOR_COUNTDOWN_MS)
        self.assertEqual(saved.life, 2)
        e.advance(5000)
        e.anchor_action({"type": "trade", "item": "stick"})
        self.assertEqual(e.dust, 4)
        self.assertTrue(e.anchor_wait)
        e.advance(ANCHOR_COUNTDOWN_MS)
        self.assertEqual(e.life, 1)
        e.anchor_action({"type": "begin_life"})
        self.assertEqual(e.life, 2)


if __name__ == "__main__":
    unittest.main()


class WorldGeneratorUpgradeTests(unittest.TestCase):
    def test_v1_world_keeps_replaying_mid_life_and_regrows_with_regions_at_rebirth(self):
        import json
        from dimensional_sim.world.autopilot import ANCHOR_COUNTDOWN_MS
        from dimensional_sim.world.generation import GENERATOR_VERSION
        from dimensional_sim.world.repository import WorldRepository
        from dimensional_sim.world.runtime import Exploration
        from dimensional_sim.world.seeds import canonical_json
        from dimensional_sim.world.web import new_world
        template = new_world(5)
        old = WorldRepository(5, template.dimensions, template.catalog, 9, generator_version=1)
        e = Expedition(Exploration(old, "forest"))
        e.advance(60_000)
        saved = canonical_json(e.to_dict())
        self.assertEqual(Expedition.from_dict(json.loads(saved)).game.world.generator_version, 1)
        e.health, e.cause = 0, "starvation"
        e.advance(0)
        self.assertEqual(e.game.world.generator_version, GENERATOR_VERSION)
        self.assertEqual(e.game.world.world_seed, 5)
        self.assertEqual(e._player(), e.anchor)
        self.assertIn("new shape", e.log[-1]["text"])
        e.advance(ANCHOR_COUNTDOWN_MS + 30_000)
        self.assertEqual(e.life, 2)
        again = Expedition.from_dict(json.loads(canonical_json(e.to_dict())))
        self.assertEqual(canonical_json(again.to_dict()), canonical_json(e.to_dict()))


class CraftingProgressionTests(unittest.TestCase):
    def test_branches_teach_crafting_then_the_staff_recipe_and_staff_is_equipped_gear(self):
        from dimensional_sim.world.catalog import ITEMS
        e = expedition()
        e.inventory = {"stick": 6}
        self.assertIsNone(e._need_action(), "sticks alone do not make crafting a starting skill")
        branches = BY_ID["fallen_branches"]
        thresholds = {o.kind: o.at_count for o in branches.outcomes}
        for n in range(1, thresholds["recipe"] + 1):
            record_action(e.journal, "fallen_branches")
            e._apply_outcomes(branches, f"enc:test:{n}")
            self.assertEqual("primitive_crafting" in e.knowledge, n >= thresholds["knowledge"])
            self.assertEqual("walking_staff" in e.recipes, n >= thresholds["recipe"])
        self.assertEqual(e._need_action().id, "craft_staff")
        e._start_self(e._need_action())
        e.advance(e.task["duration_ms"])
        self.assertEqual(ITEMS["walking_staff"].kind, "gear")
        self.assertEqual(e.equipped, {"weapon": "walking_staff"})
        self.assertEqual(e.inventory, {"walking_staff": 1, "stick": 3})

    def test_knowledge_and_journal_persist_while_gear_and_leads_reset_at_death(self):
        e = tracks_with_lead()
        e.recipes.add("walking_staff")
        e.inventory["walking_staff"] = 1
        e.equipped = {"weapon": "walking_staff"}
        e.mastery["fallen_branches"] = 3
        e.journal_disabled.add("fallen_branches")
        e.journal_favor["fallen_branches"] = "suppress"
        saved = Expedition.from_dict(e.to_dict())
        self.assertEqual((saved.equipped, saved.leads), (e.equipped, e.leads))
        e.health, e.cause = 0, "starvation"
        e.advance(0)
        self.assertEqual(e.leads, [], "a lead belongs to the life that found it")
        e.advance(ANCHOR_COUNTDOWN_MS)   # carried items wait at the anchor, then the next life starts empty
        self.assertEqual(e.life, 2)
        self.assertEqual((e.inventory, e.equipped, e.leads), ({}, {}, []))
        self.assertIn("deer_sign", e.knowledge)
        self.assertIn("walking_staff", e.recipes)
        self.assertEqual(e.journal_disabled, {"fallen_branches"})
        self.assertEqual(e.journal_favor, {"fallen_branches": "suppress"})
