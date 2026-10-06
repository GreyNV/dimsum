"""Normal expedition evidence that Forest regions affect reachable play."""
import unittest

from dimensional_sim.world.autopilot import Expedition
from dimensional_sim.world.catalog import BY_ID
from dimensional_sim.world.models import ChunkKey
from dimensional_sim.world.runtime import Exploration
from dimensional_sim.world.web import new_world


class RegionVarietyTests(unittest.TestCase):
    def test_normal_expeditions_reach_distinct_regions_and_respect_local_pools(self):
        collective = set()
        for seed in (1, 2, 3):
            with self.subTest(seed=seed):
                expedition = Expedition(Exploration(new_world(seed), "forest"))
                expedition.advance(240_000)
                world = expedition.game.world
                visited = {world.region_for(ChunkKey(row["dimension"], row["x"], row["y"])).id
                           for row in world.to_dict()["discovery"] if row["status"] == "visited"}
                self.assertGreaterEqual(len(visited), 2)
                collective.update(visited)
                for entry in expedition.screen_log:
                    if entry["result"] != "admitted":
                        continue
                    dimension, x, y = entry["chunk"].split(":")
                    region = world.region_for(ChunkKey(dimension, int(x), int(y))).id
                    allowed = BY_ID[entry["action"]].regions
                    self.assertTrue(allowed is None or region in allowed,
                                    (seed, entry["action"], region))
        self.assertEqual(collective, {"old_road", "deep_woods", "bramble_thicket", "still_glade"})


if __name__ == "__main__":
    unittest.main()
