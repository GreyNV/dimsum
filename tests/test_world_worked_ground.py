"""Worked ground around a camp (docs/design/WORKED_GROUND.md): rerolls, danger, dens, recovery, setting out."""

import json
import unittest

from dimensional_sim.world.actions import Context, weight
from dimensional_sim.world.autopilot import Expedition, saves
from dimensional_sim.world.catalog import BY_ID, STORY
from dimensional_sim.world.models import chunk_ident
from dimensional_sim.world.seeds import canonical_json
from dimensional_sim.world.tuning import (DANGER_FIGHT_PERCENT, DANGER_RINGS_PER_ROUND, DEN_ROUND,
                                          EXPLORED_RECOVER_MS, PRESSURE_RECOVER_MS)
from test_world_campfire import far_and_hurt


def camped(story=False):
    """Camped two chunks out. That chunk holds the story's first place; it is lifted unless `story`
    (a chunk holding the story is never rerolled)."""
    e = far_and_hurt()
    if not story:
        e.forced.pop(chunk_ident(e.game.player.chunk), None)
        e.knowledge |= {step.id for step in STORY}   # and is not placed here again
    e.health = 100 * 1_000_000
    e.anchor_action({"type": "location_focus", "id": e.location_here(), "mode": "searching"})
    e._place_fire()
    e._pitch_camp()
    assert e.camping()
    return e


def work(e, times=1):
    for _ in range(times):
        e._work_camp_area()
        e._screen()


class RerollTests(unittest.TestCase):
    def test_a_spent_area_is_rolled_again_one_round_more_explored(self):
        e = camped()
        key = e.game.player.chunk
        ident = chunk_ident(key)
        before = list(e.spot_plans[ident])
        rolls = len([r for r in e.roll_log if r["chunk"] == ident])
        for index in range(len(before)):
            e.completed.add(f"enc:{ident}:{index}")
        work(e)
        self.assertEqual(e.explored_rounds(key), 1)
        self.assertEqual(e.rolled[ident], [1, 1])
        self.assertIn(ident, e.screened_chunks, "rolled again on the spot")
        self.assertFalse(any(c.startswith(f"enc:{ident}:") for c in e.completed), "the new spots are open")
        self.assertEqual(len([r for r in e.roll_log if r["chunk"] == ident]), rolls + 1, "a new bucket rolled")

    def test_a_chunk_holding_the_story_is_left_as_it_is(self):
        e = camped(story=True)
        key = e.game.player.chunk
        self.assertTrue(any(BY_ID[a].placement == "story" for a in e.forced.get(chunk_ident(key), ())))
        e._reroll_camp_area()
        self.assertEqual(e.explored_rounds(key), 0)

    def test_rerolls_are_deterministic(self):
        a, b = camped(), camped()
        work(a, 2)
        work(b, 2)
        self.assertEqual(a.spot_plans, b.spot_plans)
        self.assertEqual(a.forced, b.forced)

    def test_a_chunk_with_a_fight_under_way_is_not_rolled_under_it(self):
        e = camped()
        key = e.game.player.chunk
        from dimensional_sim.world.runtime import Target
        ident = f"enc:{chunk_ident(key)}:0"
        e.game.targets[ident] = Target(ident, key, 1, 1, 5)
        e._reroll_camp_area()
        self.assertEqual(e.explored_rounds(key), 0)


class DangerTests(unittest.TestCase):
    def test_worked_ground_rolls_deeper_and_weighs_fights_up(self):
        e = camped()
        key = e.game.player.chunk
        ring = e.spot_context(key).ring
        work(e, 2)
        ctx = e.spot_context(key)
        self.assertEqual(ctx.danger, 2)
        self.assertEqual(ctx.ring, ring + 2 * DANGER_RINGS_PER_ROUND)
        fight = next(a for a in BY_ID.values() if a.category == "fight" and a.placement == "spot"
                     and weight(a, Context(biome="dark_forest", ring=ring)) > 0)
        plain = weight(fight, Context(biome="dark_forest", ring=ring))
        self.assertEqual(weight(fight, Context(biome="dark_forest", ring=ring, danger=2)),
                         plain * (100 + 2 * DANGER_FIGHT_PERCENT) // 100)

    def test_from_the_den_round_a_reroll_opens_an_animal_den(self):
        e = camped()
        key = e.game.player.chunk
        ident = chunk_ident(key)
        work(e, DEN_ROUND)
        self.assertTrue(e.has_den(key))
        den = e.forced.get(ident, [])
        self.assertTrue(any(BY_ID[a].category == "fight" for a in den))
        self.assertTrue(any(r["result"].startswith("den") for r in e.screen_log if r["chunk"] == ident))
        self.assertTrue(e.ground_view(key)["den"])

    def test_a_rerolled_fight_keeps_its_tier_while_its_plan_stands(self):
        e = camped()
        key = e.game.player.chunk
        work(e, 3)
        ident = f"enc:{chunk_ident(key)}:0"
        tier = e.tier_of(ident)
        e.total_ms += 10 * EXPLORED_RECOVER_MS   # the ground recovers, the rolled plan does not change
        self.assertEqual(e.tier_of(ident), tier)
        self.assertEqual(e.explored_rounds(key), 0)


class RecoveryTests(unittest.TestCase):
    def test_untouched_ground_forgets_its_rounds(self):
        e = camped()
        key = e.game.player.chunk
        work(e, 2)
        e.total_ms += EXPLORED_RECOVER_MS
        self.assertEqual(e.explored_rounds(key), 1)
        e.total_ms += EXPLORED_RECOVER_MS
        self.assertEqual(e.explored_rounds(key), 0)
        self.assertIsNone(e.ground_view(key) if not e.has_den(key) else None)

    def test_harvested_ecologies_recover_when_left_alone(self):
        e = camped()
        key = e.game.player.chunk
        wood = next(a for a in BY_ID.values() if a.ecology == "wood" and a.placement == "spot")
        for _ in range(3):
            e._deplete(wood, key)
        low = e.pressure_percents(key)["wood"]
        e.total_ms += PRESSURE_RECOVER_MS
        self.assertGreater(e.pressure_percents(key)["wood"], low)
        e.total_ms += 2 * PRESSURE_RECOVER_MS
        self.assertNotIn("wood", e.pressure_percents(key), "fully recovered")
        e._deplete(wood, key)
        self.assertEqual(e.harvests(next(iter(e.pressure))), 1, "a harvest after recovery counts from what showed")


class SetOutTests(unittest.TestCase):
    def test_the_player_sets_out_from_a_camp(self):
        e = camped()
        e.task = None
        context = e.location_context()
        row = next(r for r in context["actions"] if r["id"] == "set_out")
        self.assertFalse(row["reasons"])
        e.anchor_action({"type": "location", "id": "set_out"})
        self.assertFalse(e.camping())
        self.assertIsNone(e.campfire, "the fire is left behind")
        self.assertFalse(any(r["id"] == "set_out" for r in (e.location_context() or {}).get("actions", [])))
        with self.assertRaises(ValueError):
            e.anchor_action({"type": "location", "id": "set_out"})


class SaveTests(unittest.TestCase):
    def test_worked_ground_is_saved(self):
        e = camped()
        wood = next(a for a in BY_ID.values() if a.ecology == "wood" and a.placement == "spot")
        e._deplete(wood, e.game.player.chunk)
        work(e, 2)
        loaded = Expedition.from_dict(json.loads(canonical_json(e.to_dict())))
        for name in ("explored", "rolled", "pressure", "pressure_at", "spot_plans", "forced"):
            self.assertEqual(getattr(loaded, name), getattr(e, name), name)

    def test_a_schema_26_save_counts_its_harvests_as_fresh(self):
        e = camped()
        wood = next(a for a in BY_ID.values() if a.ecology == "wood" and a.placement == "spot")
        e._deplete(wood, e.game.player.chunk)
        data = json.loads(canonical_json(e.to_dict()))
        old = {k: v for k, v in data.items() if k not in saves.V27_FIELDS}
        old["schema_version"] = 26
        loaded = Expedition.from_dict(old)
        self.assertEqual(loaded.pressure_at, {k: e.total_ms for k in e.pressure})
        self.assertEqual((loaded.explored, loaded.rolled), ({}, {}))


if __name__ == "__main__":
    unittest.main()
