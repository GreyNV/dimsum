"""The main story and the grey wall: placed for sure, kept across deaths, the wall holds until opened."""
import json
import unittest

from dimensional_sim.world.actions import Context, bucket
from dimensional_sim.world.autopilot import Expedition
from dimensional_sim.world.catalog import ACTIONS, BY_ID, STORY, STORY_BY_ACTION, WALLS, story_rings
from dimensional_sim.world.models import ChunkKey
from dimensional_sim.world.progression import dimensional_level
from dimensional_sim.world.seeds import canonical_json
from tests.test_world_autopilot import expedition, first_death

WALL = WALLS["forest"]


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
            low, high = story_rings(step, WALL.ring)
            self.assertLessEqual(1, low)
            self.assertLessEqual(low, high)
        self.assertIn(WALL.opened_by, {s.id for s in STORY})
        crossing = STORY[[s.id for s in STORY].index(WALL.opened_by)]
        self.assertEqual(story_rings(crossing, WALL.ring), (WALL.ring, WALL.ring), "the wall opens at the wall")
        last = STORY[-1]
        self.assertGreater(story_rings(last, WALL.ring)[0], WALL.ring, "the chapter ends past the wall")


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
        e.knowledge |= {s.id for s in STORY[:5]}   # up to the old man: next is the crossing
        step = e.story_step()
        self.assertEqual(step.id, WALL.opened_by)
        if dimensional_level(e.dimensional["willpower"]) < 3:
            waits = e.story_view()["current"]["waits"]
            self.assertTrue(any("Willpower 3" in w for w in waits), waits)
            key = ChunkKey(e.dimension, WALL.ring, 0)
            self.assertTrue(e.story_reasons(step, key))


    def test_a_second_placement_left_behind_disappears_once_its_step_is_done(self):
        e = started()
        run_until(e, lambda e: bool(story_spots(e)), 20 * 60_000)
        spot = story_spots(e)[0]
        e.knowledge.add(STORY_BY_ACTION[spot["encounter"]].id)   # done elsewhere this life
        self.assertEqual(story_spots(e), [])
        self.assertNotIn(spot["id"], [c[1] for c in e._candidates()])


class WallTests(unittest.TestCase):
    def test_the_runtime_refuses_steps_past_a_closed_wall_but_always_allows_stepping_in(self):
        e = started()
        game = e.game
        game.ring_limit = 0
        here = game.player
        # every crossing out of the anchor chunk is refused; inside it moving works
        for exit_ in game.current_chunk().asset.exits:
            self.assertIsNone(game._step_target(here.chunk, exit_.x, exit_.y, exit_.direction))
        game.ring_limit = None
        crossings = [game._step_target(here.chunk, x.x, x.y, x.direction) for x in game.current_chunk().asset.exits]
        self.assertTrue(any(c is not None for c in crossings), "no limit: the exits work again")

    def test_the_frontier_and_the_limit_follow_the_wall_knowledge(self):
        e = started()
        self.assertEqual(e.ring_limit(), WALL.ring)
        self.assertLessEqual(e.frontier(), WALL.ring)
        e.knowledge.add(WALL.opened_by)
        self.assertIsNone(e.ring_limit())
        e.advance(1)
        self.assertIsNone(e.game.ring_limit)
        self.assertTrue(e.story_view()["wall"]["open"])

    def test_an_avatar_already_past_the_wall_can_walk_back_in(self):
        e = started()
        game = e.game
        game.ring_limit = 0
        outer = ChunkKey(e.dimension, 1, 0)   # pretend the avatar stands one ring past the wall
        chunk = game.world.get(outer)
        exits = [x for x in chunk.asset.exits if x.direction == "west"]
        self.assertTrue(exits)
        landing = game._step_target(outer, exits[0].x, exits[0].y, "west")
        self.assertIsNotNone(landing)
        self.assertEqual(landing[0], ChunkKey(e.dimension, 0, 0))
        east = [x for x in chunk.asset.exits if x.direction == "east"]
        if east:
            self.assertIsNone(game._step_target(outer, east[0].x, east[0].y, "east"), "but never further out")

    def test_long_run_never_enters_a_chunk_past_the_closed_wall(self):
        e = started(7)
        deepest = 0
        end = e.total_ms + 45 * 60_000
        while e.total_ms < end:
            e.advance(1000)
            if e.anchor_ms is not None and e.anchor_wait:
                e.anchor_action({"type": "begin_life"})
            if e.ring_limit() is not None:
                deepest = max(deepest, e.ring(e.game.player.chunk))
        self.assertLessEqual(deepest, WALL.ring)


class ViewTests(unittest.TestCase):
    def test_story_view_lists_the_objective_the_wall_and_what_was_found(self):
        e = started()
        view = e.story_view()
        self.assertEqual(view["current"]["id"], "story_camp")
        self.assertEqual(view["current"]["rings"], list(story_rings(STORY[0], WALL.ring)))
        self.assertEqual(view["wall"], {"name": WALL.name, "ring": WALL.ring, "open": False})
        self.assertEqual(view["done"], [])
        e.knowledge |= {s.id for s in STORY}
        view = e.story_view()
        self.assertIsNone(view["current"])
        self.assertTrue(view["next"])
        self.assertEqual(len(view["done"]), len(STORY))


if __name__ == "__main__":
    unittest.main()
