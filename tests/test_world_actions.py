"""Pure availability stages: knowledge, pool, spawn, and local context."""
import unittest
from dataclasses import replace

from dimensional_sim.world.actions import (
    Context, bucket, bucket_reasons, context_reasons, explain, known, weight,
)
from dimensional_sim.world.catalog import BY_ID, Requirement
from dimensional_sim.world.catalog import REGIONS
from dimensional_sim.world.encounters import chunk_spots, lead_spot
from dimensional_sim.world.models import ChunkKey
from dimensional_sim.world.runtime import Exploration
from dimensional_sim.world.web import new_world


class ActionAvailabilityTests(unittest.TestCase):
    def test_temporary_lead_placement_is_deterministic_and_separate_from_rolls(self):
        world = new_world(284)
        chunk = world.get(ChunkKey("forest", 0, 0))
        source = chunk.asset.spawns[0]
        xy = source.x, source.y
        a = lead_spot(chunk, "follow_deer_tracks", 1, "enc:forest:0:0:0", 0, xy)
        self.assertEqual(a, lead_spot(chunk, "follow_deer_tracks", 1, "enc:forest:0:0:0", 0, xy))
        self.assertTrue(a.id.startswith("lead:forest:0:0:follow_deer_tracks:"))
        self.assertNotEqual(a.id, lead_spot(chunk, "follow_deer_tracks", 2, "enc:forest:0:0:0", 0, xy).id)
        self.assertGreaterEqual(abs(a.x - xy[0]) + abs(a.y - xy[1]), 2)
        self.assertFalse(chunk.asset.collision[a.y][a.x])
        with self.assertRaises(ValueError):
            lead_spot(chunk, "animal_tracks", 1, "enc:forest:0:0:0", 0, xy)

    def test_encounter_roll_uses_full_context_and_pinned_region_weight(self):
        world = new_world(284)
        chunk = world.get(ChunkKey("forest", 0, 0))
        pinned = replace(REGIONS["old_road"], weights={"fallen_branches": 0})
        ctx = Context(region="old_road", region_def=pinned)
        self.assertEqual(weight(BY_ID["fallen_branches"], ctx), 0)
        self.assertNotIn("fallen_branches", [spot.encounter for spot in chunk_spots(chunk, context=ctx)])
        suppressed = replace(ctx, journal_disabled=frozenset({"bramble_berries"}),
                             mastery={"bramble_berries": 2})
        self.assertNotIn("bramble_berries", [spot.encounter for spot in chunk_spots(chunk, context=suppressed)])
        self.assertEqual(chunk_spots(chunk, context=suppressed), chunk_spots(chunk, context=suppressed))

    def test_detail_known_state_uses_earned_knowledge_and_recipe(self):
        from dimensional_sim.world.autopilot import Expedition
        from dimensional_sim.world.details import multipliers, rolls

        expedition = Expedition(Exploration(new_world(284)))
        before = {row["id"] for row in multipliers(expedition)["actions"]}
        self.assertNotIn("craft_staff", before)
        expedition.knowledge.add("primitive_crafting")
        expedition.recipes.add("walking_staff")
        after = {row["id"] for row in multipliers(expedition)["actions"]}
        self.assertIn("craft_staff", after)
        self.assertNotIn("hunt_deer", {row["id"] for row in rolls(expedition)["loot"]})
        expedition.knowledge.add("deer_sign")
        self.assertIn("hunt_deer", {row["id"] for row in rolls(expedition)["loot"]})

    def test_unlock_permits_a_bucket_roll_but_does_not_spawn_an_action(self):
        locked = explain("gnarled_tree", Context(region="deep_woods"))
        self.assertFalse(locked["known"])
        self.assertFalse(locked["bucket_eligible"])
        permitted = explain("gnarled_tree", Context(region="deep_woods", unlocked=frozenset({"climbing"})))
        self.assertTrue(permitted["known"])
        self.assertTrue(permitted["bucket_eligible"])
        self.assertIsNone(permitted["spawned"])
        self.assertIsNone(permitted["available"])
        rolled = explain("gnarled_tree", Context(region="deep_woods", unlocked=frozenset({"climbing"}),
                                                  spawned=True))
        self.assertTrue(rolled["available"])
        self.assertFalse(explain("gnarled_tree", Context(region="deep_woods",
                                                       unlocked=frozenset({"climbing"}),
                                                       spawned=False))["available"])

    def test_knowledge_and_recipe_are_permanent_permission_not_immediate_context(self):
        observation = replace(BY_ID["animal_tracks"], knowledge="read_tracks")
        self.assertFalse(known(observation, frozenset()))
        self.assertFalse(known(observation, Context()))
        self.assertTrue(known(observation, Context(knowledge=frozenset({"read_tracks"}))))
        recipe = replace(BY_ID["craft_staff"], recipe="walking_staff", requirements=())
        self.assertFalse(known(recipe, Context(inventory={"stick": 3})))
        self.assertTrue(known(recipe, Context(recipes=frozenset({"walking_staff"}))))
        ctx = Context(placement="self", trigger="need", recipes=frozenset({"walking_staff"}))
        self.assertEqual(bucket_reasons(recipe, ctx), [])
        self.assertTrue(any("needs 3 stick" in reason for reason in context_reasons(recipe, ctx)))

    def test_declarative_progress_requirements_combine_without_special_cases(self):
        action = replace(BY_ID["bramble_berries"], requirements=(
            Requirement("action_count", "fallen_branches", 3),
            Requirement("item_count", "stick", 5),
            Requirement("level", "perception", 2),
            Requirement("knowledge", "forest_signs"),
            Requirement("unlock", "climbing"),
            Requirement("recipe", "field_notes"),
        ))
        self.assertEqual(len(bucket_reasons(action, Context())), 6)
        ctx = Context(action_counts={"fallen_branches": 3}, item_counts={"stick": 5},
                      levels={"perception": 2}, knowledge=frozenset({"forest_signs"}),
                      unlocked=frozenset({"climbing"}), recipes=frozenset({"field_notes"}))
        self.assertEqual(bucket_reasons(action, ctx), [])

    def test_temporary_lead_needs_its_current_world_token(self):
        lead = replace(BY_ID["bramble_berries"], placement="lead", window=None)
        self.assertIn("no active temporary lead", bucket_reasons(lead, Context(placement="lead")))
        self.assertEqual(bucket_reasons(lead, Context(placement="lead",
                                                      active_leads=frozenset({"bramble_berries"}))), [])
        existing = Context(placement="lead", active_leads=frozenset({"bramble_berries"}),
                           mastery={"bramble_berries": 3},
                           journal_disabled=frozenset({"bramble_berries"}))
        self.assertEqual(bucket_reasons(lead, existing), [],
                         "future-roll controls must not erase a lead already created")

    def test_journal_controls_require_mastery_and_modify_future_rolls(self):
        action = BY_ID["bramble_berries"]
        base = Context(region="bramble_thicket")
        base_weight = weight(action, base)
        disabled_early = replace(base, mastery={action.id: 1}, journal_disabled=frozenset({action.id}))
        self.assertEqual(weight(action, disabled_early), base_weight)
        disabled = replace(base, mastery={action.id: 2}, journal_disabled=frozenset({action.id}))
        self.assertEqual(weight(action, disabled), 0)
        self.assertIn("journal disabled", explain(action.id, disabled)["reasons"])
        self.assertEqual(weight(action, replace(disabled, journal_disabled=frozenset())), base_weight)
        premature_favor = replace(base, mastery={action.id: 2}, journal_favor={action.id: "favor"})
        self.assertEqual(weight(action, premature_favor), base_weight)
        favored = replace(base, mastery={action.id: 3}, journal_favor={action.id: "favor"})
        suppressed = replace(base, mastery={action.id: 3}, journal_favor={action.id: "suppress"})
        self.assertGreater(weight(action, favored), base_weight)
        self.assertLess(weight(action, suppressed), base_weight)
        self.assertIn(action.id, [entry.id for entry, _ in bucket(favored)])
        # Suppression changes odds; only disabling removes a valid action.
        one_weight = replace(action, weight=1)
        low_odds = Context(mastery={action.id: 3}, journal_favor={action.id: "suppress"})
        self.assertEqual(weight(one_weight, low_odds), 1)


if __name__ == "__main__":
    unittest.main()


class LifecycleStateTests(unittest.TestCase):
    def test_each_pipeline_stage_has_its_own_state(self):
        deep = dict(region="deep_woods")
        self.assertEqual(explain("gnarled_tree", Context(**deep))["state"], "UNKNOWN")
        climb = dict(deep, unlocked=frozenset({"climbing"}))
        self.assertEqual(explain("gnarled_tree", Context(**climb))["state"], "BUCKET_ELIGIBLE")
        self.assertEqual(explain("gnarled_tree", Context(**climb, spawned=False))["state"], "NOT_ROLLED")
        self.assertEqual(explain("gnarled_tree", Context(**climb, spawned=True))["state"], "AVAILABLE")
        self.assertEqual(explain("fallen_branches", Context(region="still_glade"))["state"], "BUCKET_INELIGIBLE")
        disabled = Context(region="old_road", mastery={"fallen_branches": 2},
                           journal_disabled=frozenset({"fallen_branches"}))
        self.assertEqual(explain("fallen_branches", disabled)["state"], "JOURNAL_DISABLED")
        lead = Context(placement="lead", knowledge=frozenset({"deer_sign"}))
        self.assertEqual(explain("hunt_deer", lead)["state"], "BUCKET_INELIGIBLE")
        live = Context(placement="lead", knowledge=frozenset({"deer_sign"}), active_leads=frozenset({"hunt_deer"}))
        self.assertEqual(explain("hunt_deer", live)["state"], "TEMPORARY_LEAD")
        recipe = Context(placement="self", trigger="need", knowledge=frozenset({"primitive_crafting"}),
                         recipes=frozenset({"walking_staff"}), inventory={"stick": 1})
        self.assertEqual(explain("craft_staff", recipe)["state"], "RECIPE")
        self.assertEqual(explain("craft_staff", replace(recipe, inventory={"stick": 3}))["state"], "AVAILABLE")
        self.assertEqual(explain("craft_staff", Context(placement="self", trigger="need"))["state"], "UNKNOWN")
        self.assertEqual(explain("hunt_deer", replace(live, resolved=True))["state"], "RESOLVED")

    def test_inspect_explains_region_generation_and_every_spot_state(self):
        from dimensional_sim.world.simulate import inspect_chunk, region_map
        report = inspect_chunk(1, 3, 0)
        self.assertEqual(report["generator_version"], 2)
        self.assertIn(report["region"], REGIONS)
        self.assertEqual(set(report["region_parameters"]) >= {"canopy", "brush", "landmark"}, True)
        self.assertIn("blocked_percent", report["terrain"])
        states = {row["id"]: row["state"] for row in report["actions"]}
        self.assertEqual(states["gnarled_tree"], "UNKNOWN")
        rolled = {spot["action"] for spot in report["spots"]}
        for action, state in states.items():
            self.assertEqual(state == "AVAILABLE", action in rolled, (action, state))
        self.assertEqual(region_map(1), region_map(1))
        self.assertNotEqual(region_map(1)["rows"], region_map(2)["rows"])
