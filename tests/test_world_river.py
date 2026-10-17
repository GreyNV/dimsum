"""The riverbank: encounters beside rivers and fords in any region, and the river lurker."""
import unittest

from dimensional_sim.world.actions import Context
from dimensional_sim.world.catalog import BY_ID, ENEMIES
from dimensional_sim.world.encounters import WATER, chunk_spots, features
from dimensional_sim.world.models import ChunkKey, DELTAS
from dimensional_sim.world.runtime import Target
from dimensional_sim.world.web import new_world
from tests.test_world_autopilot import expedition

RIVER = {a.id for a in BY_ID.values() if a.near == "w" and a.placement == "spot"}


def chunks(seed, radius=6):
    w = new_world(seed)
    for y in range(-radius, radius + 1):
        for x in range(-radius, radius + 1):
            key = ChunkKey("forest", x, y)
            yield w, key, w.get(key)


def beside_water(asset, x, y):
    return any(0 <= x + dx < asset.width and 0 <= y + dy < asset.height and
               asset.environment[y + dy][x + dx].glyph in WATER for dx, dy in DELTAS.values())


class RiverbankTests(unittest.TestCase):
    def test_river_encounters_roll_only_beside_water_in_any_region(self):
        wet = dry = 0
        regions = set()
        for seed in (1, 2, 482910):
            for world, key, chunk in chunks(seed):
                region = world.region_for(key)
                ctx = Context(region=region.id, region_def=region)
                spots = [s for life in (1, 2, 3) for s in chunk_spots(chunk, life, context=ctx)
                         if s.encounter in RIVER]
                if "water" in features(chunk.asset):
                    wet += 1
                else:
                    dry += 1
                    self.assertEqual(spots, [], f"no river encounter without water ({key})")
                for s in spots:
                    regions.add(region.id)
                    self.assertTrue(beside_water(chunk.asset, s.x, s.y), (key, s))
        self.assertGreater(wet, 10)
        self.assertGreater(dry, wet, "rivers are a feature of some chunks, not everywhere")
        self.assertGreater(len(regions), 1, "the riverbank is not a region of its own")

    def test_the_lurker_is_faster_lighter_and_frailer_than_the_boar(self):
        boar, lurker = ENEMIES["bramble_boar"], ENEMIES["river_lurker"]
        self.assertLess(lurker.step_ms, boar.step_ms)
        self.assertLess(lurker.hit, boar.hit)
        self.assertLess(BY_ID["river_lurker"].hp, BY_ID["bramble_boar"].hp)
        self.assertLess(lurker.aggro_radius, boar.aggro_radius, "it notices you late")
        e = expedition()
        steps = []
        for tick in range(6):
            e.total_ms = tick * 300
            steps.append(e._steps_this_tick(lurker))
        self.assertEqual(sum(steps), 9, "1.5 steps per boar step over time")
        self.assertEqual({e._steps_this_tick(boar)}, {1})

    def test_a_lurker_that_notices_you_keeps_chasing(self):
        e = expedition()
        while e.in_prologue:
            e.advance(500)
        e.anchor = (10 ** 6, 10 ** 6)   # no camp sanctuary in this test
        here = e.game.player.chunk
        grid, blocked = e._grid(), frozenset()
        px, py = e._player()
        # walk the avatar into open ground with room to retreat westward
        open_row = [x for x in range(2, e.game.current_chunk().asset.width - 8)
                    if all(not e.game.current_chunk().asset.collision[py % 16][x + d] for d in range(8))]
        if not open_row:
            self.skipTest("no open row here")
        start = open_row[-1]
        e.game.player.x = start
        from dimensional_sim.world.encounters import spot_id
        from dimensional_sim.world.models import chunk_ident
        e.spot_plans[chunk_ident(here)] = [("river_lurker", start + 4, e.game.player.y)]
        target = Target(spot_id(here, 0), here, start + 4, e.game.player.y, 2)
        e.game.targets[target.id] = target
        e.admitted[target.id] = "river_lurker"
        home = e._global(here, start + 4, e.game.player.y)
        lurker, farthest = ENEMIES["river_lurker"], 0
        for tick in range(12):
            e.monster_ms, e.total_ms = 300, e.total_ms + 300
            if tick % 2 and e.game.player.x > 2:
                e.game.player.x -= 1   # the avatar backs away
            e._pursue()
            tx, ty = e._global(target.chunk, target.x, target.y)
            farthest = max(farthest, abs(tx - home[0]) + abs(ty - home[1]))
        self.assertEqual(e.hunting[target.id]["mode"], "hunt")
        self.assertGreater(farthest, 3, "no territory any more: it follows the avatar")

    def test_a_trail_to_the_river_heads_for_a_chunk_with_water(self):
        from tests.test_world_chains import started
        from dimensional_sim.world.journal import record_action
        found = 0
        for seed in range(1, 8):
            e = started(seed)
            here = e.game.player.chunk
            wet = [ChunkKey(here.dimension, here.x + dx, here.y + dy)
                   for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))]
            wet = [k for k in wet if "water" in features(e.game.world.get(k).asset)]
            if not wet:
                continue
            record_action(e.journal, "fresh_footprints")
            for n in range(200):
                e._apply_outcomes(BY_ID["fresh_footprints"], f"self:prints:{n}")
                fords = [row for row in e.leads if row["action"] == "hidden_ford"]
                if fords:
                    self.assertIn(ChunkKey(here.dimension, fords[0]["chunk_x"], fords[0]["chunk_y"]), wet)
                    found += 1
                    break
        self.assertGreater(found, 0, "no seed had water next to the start; widen the search")

    def test_river_chains_are_wired(self):
        self.assertEqual({o.id for o in BY_ID["reed_bed"].outcomes}, {"fish_scales"})
        self.assertIn("busy_pool", {o.id for o in BY_ID["fish_scales"].outcomes})
        self.assertIn("lurker_burrow", {o.id for o in BY_ID["ripples"].outcomes})
        self.assertIn("fishing_platform", {o.id for o in BY_ID["float_line"].outcomes})
        self.assertIn("bootprints", {o.id for o in BY_ID["camp_firepit"].outcomes})
        self.assertIn("fishing_camp", {o.id for o in BY_ID["bootprints"].outcomes})
        self.assertIn("hidden_ford", {o.id for o in BY_ID["fresh_footprints"].outcomes})
        for lead in ("fish_scales", "busy_pool", "ripples", "float_line", "fishing_platform",
                     "fishing_camp", "hidden_ford"):
            self.assertEqual(BY_ID[lead].near, "w", f"{lead} stands by the water")
        self.assertEqual(BY_ID["fishing_pool"].ecology, "fish", "fishing thins out a stretch of river")


if __name__ == "__main__":
    unittest.main()
