"""Local ecological exhaustion: a worked stretch of forest thins out for the rest of the life."""
import json
import unittest

from dimensional_sim.world.actions import weight
from dimensional_sim.world.autopilot import Expedition, saves
from dimensional_sim.world.autopilot.ecology import cell_of, percent
from dimensional_sim.world.catalog import BY_ID, ECOLOGY, REGION_CELL
from dimensional_sim.world.models import ChunkKey
from dimensional_sim.world.seeds import canonical_json
from dimensional_sim.world.tuning import PRESSURE_FLOOR
from tests.test_world_autopilot import expedition
from save_fixture import v17


def started():
    e = expedition()
    while e.in_prologue:
        e.advance(500)
    return e


class PressureTests(unittest.TestCase):
    def test_each_harvest_thins_its_ecology_down_to_a_floor(self):
        self.assertEqual(percent(0), 100)
        self.assertLess(percent(1), 100)
        self.assertEqual(percent(1000), PRESSURE_FLOOR)
        self.assertGreater(PRESSURE_FLOOR, 0, "a worked area keeps a trickle: no soft-lock")

    def test_harvesting_lowers_that_ecology_in_its_region_cell_only(self):
        e = started()
        here = e.game.player.chunk
        before = weight(BY_ID["fallen_branches"], e.spot_context(here))
        for _ in range(3):
            e._deplete(BY_ID["fallen_branches"], here)
        ctx = e.spot_context(here)
        self.assertEqual(ctx.pressure, {"wood": percent(3)})
        self.assertLess(weight(BY_ID["fallen_branches"], ctx), before)
        self.assertEqual(weight(BY_ID["bramble_berries"], ctx), weight(BY_ID["bramble_berries"], e.spot_context(here)))
        far = ChunkKey(here.dimension, here.x + REGION_CELL, here.y)
        self.assertEqual(e.spot_context(far).pressure, {}, "fresh ground a region cell away")
        self.assertEqual(e.worked_here(), ["wood"])

    def test_finishing_a_wild_spot_depletes_but_leads_and_sites_do_not(self):
        e = started()
        here = e.game.player.chunk
        from dimensional_sim.world.models import chunk_ident
        e.spot_plans[chunk_ident(here)] = [("fallen_branches", 3, 3)]
        spot = next(s for s in e._spots(e.game.world.get(here)) if s.encounter == "fallen_branches")
        e._reward(spot.id, BY_ID["fallen_branches"])
        self.assertEqual(e.pressure, {f"{cell_of(here)}:wood": 1})
        e._reward("lead:x", BY_ID["cut_wood"])
        self.assertEqual(sum(e.pressure.values()), 1)

    def test_pressure_is_saved_validated_migrated_and_reset_each_life(self):
        e = started()
        e._deplete(BY_ID["bramble_berries"], e.game.player.chunk)
        again = Expedition.from_dict(json.loads(canonical_json(e.to_dict())))
        self.assertEqual(again.pressure, e.pressure)
        old = {k: v for k, v in v17(e.to_dict()).items() if k not in (*saves.V15_FIELDS, *saves.V16_FIELDS, *saves.V17_FIELDS)}
        old["schema_version"] = 14
        self.assertEqual(Expedition.from_dict(old).pressure, {})
        bad = e.to_dict()
        bad["pressure"] = {"forest:0:0:gold": 3}
        with self.assertRaises(ValueError):
            Expedition.from_dict(bad)
        e._new_life_state()
        self.assertEqual(e.pressure, {})

    def test_every_ecology_is_used_by_some_wild_spot(self):
        used = {a.ecology for a in BY_ID.values() if a.ecology}
        self.assertEqual(used, set(ECOLOGY))


if __name__ == "__main__":
    unittest.main()
