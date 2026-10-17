"""Discovery chains, temporary leads, Journal choices and first death."""
import copy
import unittest

from dimensional_sim.world.autopilot import ANCHOR_COUNTDOWN_MS, Expedition
from dimensional_sim.world.catalog import BY_ID
from dimensional_sim.world.journal import record_action
from tests.test_world_autopilot import expedition
from camp_fixture import to_camp


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

    def test_first_death_anchor_dialogue_and_automatic_ash(self):
        e = expedition()
        e.inventory = {"stick": 4}
        e.health, e.cause = 0, "starvation"
        e.advance(0)
        self.assertEqual(e.life, 1)
        self.assertEqual(e._player(), e.anchor)
        self.assertEqual(e.anchor_ms, ANCHOR_COUNTDOWN_MS)
        saved = Expedition.from_dict(e.to_dict())
        saved.advance(ANCHOR_COUNTDOWN_MS)
        self.assertEqual(saved.life, 1)
        self.assertEqual(saved.ash, 4)
        e.advance(5000)
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
        e.anchor_action({"type": "begin_life"})
        e.advance(ANCHOR_COUNTDOWN_MS + 30_000)
        self.assertEqual(e.life, 2)
        again = Expedition.from_dict(json.loads(canonical_json(e.to_dict())))
        self.assertEqual(canonical_json(again.to_dict()), canonical_json(e.to_dict()))


class AlternativeOutcomeTests(unittest.TestCase):
    def test_grouped_outcomes_pick_at_most_one_alternative_at_their_chances(self):
        from dataclasses import replace
        from dimensional_sim.world.catalog import OutcomeDef
        e = expedition()
        base = BY_ID["animal_tracks"]
        action = replace(base, outcomes=(
            OutcomeDef("note", "cold", chance=50, group="trail", text="The trail went cold."),
            OutcomeDef("knowledge", "deer_sign", chance=30, group="trail"),
            OutcomeDef("note", "always", text="Counted the hoofprints.")))
        record_action(e.journal, "animal_tracks")
        counts = {"cold": 0, "sign": 0, "none": 0}
        for n in range(400):
            e.log.clear()
            e.knowledge.discard("deer_sign")
            e._apply_outcomes(action, f"enc:test:{n}")
            texts = [row["text"] for row in e.log]
            self.assertIn("Counted the hoofprints.", texts, "ungrouped outcomes still roll on their own")
            cold, sign = "The trail went cold." in texts, "deer_sign" in e.knowledge
            self.assertFalse(cold and sign, "alternatives in one group never both happen")
            counts["cold" if cold else "sign" if sign else "none"] += 1
        self.assertTrue(160 <= counts["cold"] <= 240, counts)
        self.assertTrue(80 <= counts["sign"] <= 160, counts)
        self.assertTrue(40 <= counts["none"] <= 120, counts)

    def test_group_chances_cannot_exceed_certainty_and_placed_things_need_an_interaction(self):
        from dataclasses import replace
        from dimensional_sim.world.catalog import ACTIONS, OutcomeDef
        with self.assertRaises(ValueError):
            replace(BY_ID["animal_tracks"], outcomes=(OutcomeDef("note", "a", chance=60, group="g", text="a"),
                                                      OutcomeDef("note", "b", chance=60, group="g", text="b")))
        with self.assertRaises(ValueError):
            OutcomeDef("note", "silent")
        with self.assertRaises(ValueError):
            replace(BY_ID["animal_tracks"], interaction=None)
        for a in ACTIONS:
            if a.placement in ("spot", "lead", "site"):
                self.assertTrue(a.interaction and a.interaction != a.name, a.id)


class CraftingProgressionTests(unittest.TestCase):
    def test_branches_teach_crafting_and_a_camp_bedroll_teaches_the_jerkin(self):
        from dimensional_sim.world.catalog import ITEMS
        e = to_camp(expedition())
        e.inventory = {"cloth_scrap": 4, "rope": 1}
        self.assertIsNone(e._need_action(), "materials alone do not make crafting a starting skill")
        branches = BY_ID["fallen_branches"]
        at = next(o.at_count for o in branches.outcomes if o.id == "primitive_crafting")
        for n in range(1, at + 1):
            record_action(e.journal, "fallen_branches")
            e._apply_outcomes(branches, f"enc:test:{n}")
            self.assertEqual("primitive_crafting" in e.knowledge, n >= at)
        self.assertIsNone(e._need_action(), "the recipe comes from a site")
        record_action(e.journal, "camp_bedroll")
        e._apply_outcomes(BY_ID["camp_bedroll"], "enc:test:bedroll")
        self.assertIn("padded_jerkin", e.life_recipes)
        self.assertEqual(e._need_action().id, "craft_jerkin")
        e._start_self(e._need_action())
        e.advance(e.task["duration_ms"])
        self.assertEqual(ITEMS["padded_jerkin"].kind, "gear")
        self.assertEqual(e.equipped, {"body": "padded_jerkin"})
        self.assertEqual(e.inventory, {"padded_jerkin": 1, "cloth_scrap": 1})

    def test_knowledge_and_journal_persist_while_gear_and_leads_reset_at_death(self):
        e = tracks_with_lead()
        e.recipes.add("padded_jerkin")
        e.inventory["padded_jerkin"] = 1
        e.equipped = {"body": "padded_jerkin"}
        e.mastery["fallen_branches"] = 3
        e.journal_disabled.add("fallen_branches")
        e.journal_favor["fallen_branches"] = "suppress"
        saved = Expedition.from_dict(e.to_dict())
        self.assertEqual((saved.equipped, saved.leads), (e.equipped, e.leads))
        e.health, e.cause = 0, "starvation"
        e.advance(0)
        self.assertEqual(e.leads, [], "a lead belongs to the life that found it")
        e.anchor_action({"type": "begin_life"})
        self.assertEqual(e.life, 2)
        self.assertEqual((e.inventory, e.equipped, e.leads), ({}, {}, []))
        self.assertIn("deer_sign", e.knowledge)
        self.assertIn("padded_jerkin", e.recipes, "a kept recipe outlives the life")
        self.assertEqual(e.journal_disabled, {"fallen_branches"})
        self.assertEqual(e.journal_favor, {"fallen_branches": "suppress"})
