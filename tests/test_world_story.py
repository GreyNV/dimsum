"""The main story: placed for sure, kept across deaths, gated by growth."""
import json
import unittest

from dimensional_sim.world.actions import Context, bucket
from dimensional_sim.world.autopilot import Expedition
from dimensional_sim.world.catalog import ACTIONS, BY_ID, STORY, STORY_BY_ACTION, story_rings
from dimensional_sim.world.models import ChunkKey
from dimensional_sim.world.progression import dimensional_level
from dimensional_sim.world.seeds import canonical_json
from tests.test_world_autopilot import expedition, first_death



def started(seed=482910):
    e = expedition(seed)
    while e.in_prologue:
        e.advance(500)
    return e


def story_spots(e):
    return [s for s in e.visible_spots() if s["story"]]


def run_until(e, test, limit_ms=40 * 60_000, step=1000):
    end = e.total_ms + limit_ms
    while e.total_ms < end and not test(e):
        e.advance(step)
        if e.anchor_ms is not None and e.anchor_wait:
            e.anchor_action({"type": "begin_life"})
    return test(e)


class CatalogTests(unittest.TestCase):
    def test_story_actions_never_enter_a_bucket_and_each_step_teaches_its_own_knowledge(self):
        story = {a.id for a in ACTIONS if a.placement == "story"}
        self.assertEqual(story, set(STORY_BY_ACTION))
        for placement in ("spot", "lead", "site", "self"):
            self.assertFalse(story & {a.id for a, _ in bucket(Context(placement=placement))}, placement)
        for step in STORY:
            self.assertIn(step.id, {o.id for o in BY_ID[step.action].outcomes if o.kind == "knowledge"})
            low, high = story_rings(step)
            self.assertLessEqual(1, low)
            self.assertLessEqual(low, high)
        self.assertTrue(all(story_rings(step)[1] <= 6 for step in STORY), "the story stays inside the first land")


class PlacementTests(unittest.TestCase):
    def test_the_first_step_is_placed_and_found_in_life_one_and_its_lore_is_logged(self):
        e = started()
        self.assertEqual(e.story_step().id, "story_camp")
        self.assertTrue(run_until(e, lambda e: "story_camp" in e.knowledge, 20 * 60_000))
        self.assertEqual(e.story_step().id, STORY[1].id)
        lore = [row["text"] for row in e.log if row["type"] == "story" and row["encounter"] == "old_man_camp"]
        self.assertEqual(lore, list(STORY[0].lore))

    def test_story_progress_survives_death_and_reload_and_replays_exactly(self):
        e = started()
        run_until(e, lambda e: "story_camp" in e.knowledge, 20 * 60_000)
        first_death(e)
        self.assertIn("story_camp", e.knowledge, "a death never undoes the story")
        twin = Expedition.from_dict(json.loads(canonical_json(e.to_dict())))
        for x in (e, twin):
            x.advance(90_000)
        self.assertEqual(canonical_json(e.to_dict()), canonical_json(twin.to_dict()))

    def test_a_placed_step_is_saved_with_its_chunk_and_admitted_outside_the_spawn_windows(self):
        e = started()
        run_until(e, lambda e: bool(story_spots(e)), 20 * 60_000)
        spot = story_spots(e)[0]
        self.assertEqual(spot["encounter"], "old_man_camp")
        self.assertIn(spot["id"], e.admitted)
        restored = Expedition.from_dict(json.loads(canonical_json(e.to_dict())))
        self.assertEqual([s for s in restored.visible_spots() if s["story"]], [spot])

    def test_a_step_waits_for_its_requirement_and_says_why(self):
        e = started()
        e.knowledge |= {s.id for s in STORY[:-1]}   # up to the gate, which needs Willpower 3
        step = e.story_step()
        self.assertEqual(step.id, "story_gate")
        if dimensional_level(e.dimensional["willpower"]) < 3:
            waits = e.story_view()["current"]["waits"]
            self.assertTrue(any("Willpower 3" in w for w in waits), waits)
            self.assertTrue(e.story_reasons(step, ChunkKey(e.dimension, 4, 0)))

    def test_a_second_placement_left_behind_disappears_once_its_step_is_done(self):
        e = started()
        run_until(e, lambda e: bool(story_spots(e)), 20 * 60_000)
        spot = story_spots(e)[0]
        e.knowledge.add(STORY_BY_ACTION[spot["encounter"]].id)   # done elsewhere this life
        self.assertEqual(story_spots(e), [])
        self.assertNotIn(spot["id"], [c[1] for c in e._candidates()])


class ViewTests(unittest.TestCase):
    def test_story_view_lists_the_objective_and_what_was_found(self):
        e = started()
        view = e.story_view()
        self.assertEqual(view["current"]["id"], "story_camp")
        self.assertEqual(view["current"]["rings"], list(story_rings(STORY[0])))
        self.assertEqual(view["done"], [])
        e.knowledge |= {s.id for s in STORY}
        view = e.story_view()
        self.assertIsNone(view["current"])
        self.assertTrue(view["next"])
        self.assertEqual(len(view["done"]), len(STORY))


if __name__ == "__main__":
    unittest.main()
