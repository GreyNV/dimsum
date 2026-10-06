"""Geography changes possibility; both control modes use the same expedition."""
from collections import Counter
import unittest

from dimensional_sim.world.actions import Context, explain, outcome_chance, weight
from dimensional_sim.world.autopilot import Expedition
from dimensional_sim.world.catalog import BY_ID, REGION_CELL, REGIONS
from dimensional_sim.world.models import ChunkKey
from dimensional_sim.world.repository import WorldRepository
from dimensional_sim.world.runtime import Exploration
from dimensional_sim.world.session import BrowserSession
from dimensional_sim.world.web import new_world


def region_sample(region_id, seeds=range(1, 6), per_seed=12):
    """Controlled first-entry trials through the actual expedition screening path."""
    tally = Counter()
    for seed in seeds:
        expedition = Expedition(Exploration(new_world(seed), "forest"), fresh=False)
        expedition.unlocked.update({"road_lore", "scavenging"})
        world = expedition.game.world
        found = 0
        for cy in range(-9, 10):
            for cx in range(-9, 10):
                key = ChunkKey("forest", cx * REGION_CELL, cy * REGION_CELL)
                if world.region_for(key).id != region_id:
                    continue
                world.stream(key)
                expedition.game.player.chunk = key
                expedition.game.player.x, expedition.game.player.y = 16, 8
                expedition._screen()
                tally.update(s.encounter for s in expedition._spots(world.peek(key)))
                found += 1
                if found >= per_seed:
                    break
            if found >= per_seed:
                break
        if found < per_seed:
            raise AssertionError("not enough region cells to sample")
    return tally


class GeographyStrategyTests(unittest.TestCase):
    def test_v2_adjacency_biases_neighbors_without_fixed_routes(self):
        def sameness(version):
            same = total = 0
            for seed in range(1, 21):
                for y in range(-5, 6):
                    for x in range(-5, 6):
                        here = ChunkKey("forest", x * REGION_CELL, y * REGION_CELL)
                        first = REGIONS["old_road"] if (x, y) == (0, 0) else None
                        from dimensional_sim.world.regions import region_for
                        first = first or region_for(seed, "dark_forest", here, version=version)
                        for dx, dy in ((1, 0), (0, 1)):
                            other = region_for(seed, "dark_forest",
                                               ChunkKey("forest", (x + dx) * REGION_CELL,
                                                        (y + dy) * REGION_CELL), version=version)
                            same += first.id == other.id
                            total += 1
            return same / total
        self.assertGreater(sameness(2), sameness(1) + .03)
        layouts = {tuple(new_world(seed).region_for(ChunkKey("forest", x * REGION_CELL, 0)).id
                         for x in range(-3, 4)) for seed in range(1, 8)}
        self.assertGreaterEqual(len(layouts), 6)

    def test_region_filters_and_weights_are_separate(self):
        road = Context(region="old_road")
        woods = Context(region="deep_woods")
        glade = Context(region="still_glade")
        self.assertEqual(weight(BY_ID["animal_tracks"], road), 0)
        self.assertIn("region", " ".join(explain("animal_tracks", road)["bucket_reasons"]))
        self.assertGreater(weight(BY_ID["bramble_boar"], woods),
                           weight(BY_ID["bramble_boar"], glade))
        row = explain("bramble_boar", woods)
        self.assertEqual(row["weight"], row["base_weight"] * 250 // 100)
        self.assertEqual(row["weight_modifiers"][0], {"source": "region", "percent": 250})
        follow = next(o for o in BY_ID["animal_tracks"].outcomes if o.kind == "lead")
        self.assertEqual(outcome_chance(follow, REGIONS["deep_woods"]), 30)
        self.assertEqual(outcome_chance(follow, REGIONS["still_glade"]), 39)

    def test_runtime_region_distributions_differ_without_becoming_certain(self):
        woods = region_sample("deep_woods")
        glade = region_sample("still_glade")
        road = region_sample("old_road")
        self.assertGreater(woods["bramble_boar"], glade["bramble_boar"])
        self.assertGreater(glade["forest_spring"], woods["forest_spring"])
        self.assertGreater(road["fallen_watchtower"], woods["fallen_watchtower"])
        self.assertGreater(woods["fallen_branches"], road["fallen_branches"])
        self.assertEqual(road["animal_tracks"], 0)
        for tally in (woods, glade, road):
            self.assertGreaterEqual(len(tally), 5)

    def test_auto_active_auto_keeps_world_and_switches_region_context(self):
        expedition = Expedition(Exploration(new_world(1), "forest"))
        expedition.advance(40_000)  # complete the prologue
        session = BrowserSession(expedition.game, expedition)
        body = {"move": None, "attack": False, "paused": False, "known": []}
        origin = expedition.game.world
        first = session.input(body, 0)
        self.assertEqual(first["expedition"]["control"], "auto")
        first_spots = dict(expedition.spot_plans)
        old_position = (expedition.game.player.chunk, expedition.game.player.x, expedition.game.player.y)
        active = session.input({**body, "control": "active"}, .01)
        self.assertEqual(active["expedition"]["control"], "manual")
        self.assertIs(expedition.game.world, origin)
        self.assertEqual((expedition.game.player.chunk, expedition.game.player.x,
                          expedition.game.player.y), old_position)
        self.assertEqual(expedition.spot_plans, first_spots)
        exit_west = next(x for x in expedition.game.current_chunk().asset.exits if x.direction == "west")
        expedition.game.player.x, expedition.game.player.y = exit_west.x, exit_west.y
        session.input({**body, "control": "active", "move": "west"}, .02)
        session.step(.04)
        self.assertEqual(expedition.game.player.chunk.x, -1)
        self.assertEqual(expedition.region(expedition.game.player.chunk).id, "still_glade")
        self.assertEqual(expedition.debug_info()["region"], "still_glade")
        self.assertIn("forest:-1:0", expedition.spot_plans)
        clock = expedition.total_ms
        back = session.input({**body, "control": "auto"}, .05)
        self.assertEqual(back["expedition"]["control"], "auto")
        self.assertIs(expedition.game.world, origin)
        self.assertEqual(expedition.game.player.chunk.x, -1)
        session.step(.06)
        self.assertEqual(expedition.total_ms, clock + 20)

    def test_geography_does_not_predetermine_neighbor_opportunities(self):
        expedition = Expedition(Exploration(new_world(3), "forest"), fresh=False)
        origin = expedition.game.player.chunk
        neighbor = ChunkKey("forest", origin.x - 1, origin.y)
        expedition.game.world.get(neighbor)
        self.assertNotIn("forest:-1:0", expedition.spot_plans)
        self.assertEqual(expedition._spots(expedition.game.world.peek(neighbor)), ())
        expedition.game.player.chunk = neighbor
        expedition.game.world.stream(neighbor)
        expedition._screen()
        self.assertIn("forest:-1:0", expedition.spot_plans)
        normal = Expedition(Exploration(new_world(3), "forest"), fresh=False)
        normal._screen()
        restored = Expedition.from_dict(normal.to_dict())
        self.assertEqual(restored.spot_plans, normal.spot_plans)
        self.assertEqual(restored._spots(restored.game.current_chunk()),
                         normal._spots(normal.game.current_chunk()))

    def test_take_control_preserves_running_encounter_and_uses_one_clock(self):
        expedition = Expedition(Exploration(new_world(1), "forest"), fresh=False)
        expedition._screen()
        spot = next(s for s in expedition._live(expedition.game.current_chunk())
                    if BY_ID[s.encounter].category != "fight")
        expedition.task = {"type": "perform", "spot": spot.id,
                           "elapsed_ms": 400, "duration_ms": 1000}
        session = BrowserSession(expedition.game, expedition)
        body = {"move": None, "attack": False, "paused": False, "known": []}
        session.input({**body, "control": "active"}, 0)
        self.assertEqual(expedition.task["spot"], spot.id)
        before = expedition.total_ms
        session.step(.02)
        self.assertEqual(expedition.total_ms, before + 20)
        self.assertEqual(expedition.task["elapsed_ms"], 420)
        session.input({**body, "control": "auto"}, .03)
        self.assertEqual(expedition.task["spot"], spot.id)
        session.step(.04)
        self.assertEqual(expedition.total_ms, before + 40)

    def test_legacy_region_save_retains_v1_geography(self):
        old = WorldRepository(19, region_version=1)
        key = ChunkKey("forest", -3, 0)
        before = old.get(key)
        data = old.to_dict()
        self.assertEqual(data["schema_version"], 2)
        restored = WorldRepository.from_dict(data)
        self.assertEqual(restored.region_version, 1)
        self.assertEqual(restored.get(key), before)


if __name__ == "__main__":
    unittest.main()
