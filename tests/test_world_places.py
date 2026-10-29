"""Places: kinds of place mastered by finishing encounters there; camp only in a mastered place,
and a camp holds the avatar to that place and its focus."""
import json
import unittest

from dimensional_sim.world.autopilot import Expedition, saves
from dimensional_sim.world.autopilot.constants import SCHEMA_VERSION
from dimensional_sim.world.catalog import (BY_ID, CAMP_GRADE, CAMP_IDLE_MS, LOCATION_OF_REGION, LOCATION_OF_SITE,
                                           LOCATIONS, REGIONS, SITES, location_thresholds)
from dimensional_sim.world.models import ChunkKey
from dimensional_sim.world.runtime import Exploration
from dimensional_sim.world.seeds import canonical_json
from dimensional_sim.world.web import new_world
from tests.save_fixture import v21
from tests.test_world_campfire import far_and_hurt


def master_here(e):
    here = e.location_here()
    e.location_done[here] = location_thresholds(here)[CAMP_GRADE - 1]
    return here


class CatalogTests(unittest.TestCase):
    def test_every_region_and_site_belongs_to_exactly_one_place(self):
        self.assertEqual(set(LOCATION_OF_REGION), set(REGIONS))
        self.assertEqual(set(LOCATION_OF_SITE), set(SITES))
        for place in LOCATIONS:
            low, camp, deep = location_thresholds(place)
            self.assertLess(low, camp)
            self.assertLess(camp, deep)
        self.assertLess(location_thresholds("old_ruins")[1], location_thresholds("old_road")[1],
                        "landmarks are rarer, so they need fewer encounters")

    def test_deep_landmark_mastery_improves_wild_finds_at_the_landmark(self):
        e = Expedition(Exploration(new_world(1), "forest"))
        key = next(ChunkKey("forest", x, y) for y in range(-6, 7) for x in range(-6, 7)
                   if e.game.world.site_for(ChunkKey("forest", x, y)) is not None)
        site = e.game.world.site_for(key)
        location = LOCATION_OF_SITE[site.id]
        self.assertEqual(e.location_rarity_percent(key), 100)
        e.location_done[location] = location_thresholds(location)[2]
        self.assertEqual(e.location_rarity_percent(key), 150)
        neighbor = ChunkKey("forest", key.x + 1, key.y)
        if e.game.world.site_for(neighbor) is None:
            self.assertEqual(e.location_rarity_percent(neighbor), 100)


class CampTests(unittest.TestCase):
    def test_with_a_focus_chosen_the_avatar_makes_camp_on_its_own_and_keeps_to_the_place(self):
        e = far_and_hurt(mastered=False)
        e.health = 100 * 1_000_000
        here = master_here(e)
        self.assertFalse(e._wants_camp(), "no focus chosen: the avatar makes no camp on its own")
        e.anchor_action({"type": "location_focus", "id": here, "mode": "resources"})
        self.assertTrue(e._wants_camp())
        e.advance(1)
        self.assertEqual(e.task["type"], "make_campfire")
        e.advance(10_000)
        self.assertTrue(e.camping())
        self.assertEqual((e.camp["location"], e.camp_focus()), (here, "resources"))
        self.assertTrue(e.in_camp_area(e.game.player.chunk))
        far = ChunkKey(e.dimension, e.game.player.chunk.x + 9, e.game.player.chunk.y)
        self.assertFalse(e.camp_wants(BY_ID["bramble_berries"], far), "nothing outside the camp's place")
        self.assertTrue(e.camp_wants(BY_ID["bramble_berries"], e.game.player.chunk))
        self.assertFalse(e.camp_wants(BY_ID["old_carvings"], e.game.player.chunk), "only what fits the focus")
        again = Expedition.from_dict(json.loads(canonical_json(e.to_dict())))
        self.assertEqual(again.camp, e.camp)

    def test_an_idle_camp_is_broken_and_not_pitched_again_in_that_place_this_life(self):
        e = far_and_hurt()
        e.health = 100 * 1_000_000
        e.anchor_action({"type": "location_focus", "id": e.location_here(), "mode": "searching"})
        e._place_fire()
        e._pitch_camp()
        self.assertTrue(e.camping())
        e._camp_idle(False)
        e.total_ms += CAMP_IDLE_MS
        e._camp_idle(False)
        self.assertFalse(e.camping())
        self.assertFalse(e._wants_camp(), "it left this place: no second camp here this life")

    def test_the_player_can_make_camp_in_a_mastered_place_and_never_elsewhere(self):
        e = far_and_hurt(mastered=False)
        self.assertFalse(e.can_make_fire())
        with self.assertRaises(ValueError):
            e.anchor_action({"type": "campfire"})
        master_here(e)
        e.anchor_action({"type": "campfire"})
        e.advance(10_000)
        self.assertTrue(e.camping())
        self.assertEqual(e.camp_focus(), "all", "a camp made by hand goes after everything unless told otherwise")


class MigrationTests(unittest.TestCase):
    def test_schema_21_counts_become_place_mastery_and_the_campfire_skill_goes(self):
        e = far_and_hurt()
        old = v21(e.to_dict())
        old["journal"]["actions"] = {"bramble_berries": 7, "camp_packs": 4, "make_campfire": 3}
        old["unlocked"] = ["return_anchor", "campfire"]
        old["mastery"] = {"bramble_berries": 1}
        old["journal_favor"] = {"bramble_berries": "favor"}
        loaded = Expedition.from_dict(json.loads(json.dumps(old)))
        self.assertEqual(loaded.location_done, {"bramble_thicket": 7, "abandoned_camp": 4})
        self.assertEqual(loaded.unlocked, {"return_anchor"})
        self.assertEqual((loaded.location_focus, loaded.camp), ({}, None))
        self.assertEqual(loaded.to_dict()["schema_version"], SCHEMA_VERSION)

    def test_schema_22_keeps_rolled_encounters_when_the_new_odds_arrive(self):
        e = far_and_hurt()
        old = {k: v for k, v in e.to_dict().items() if k not in saves.V25_FIELDS}
        old["schema_version"] = 22
        old["encounters"] = "encounters-v11"
        loaded = Expedition.from_dict(json.loads(json.dumps(old)))
        self.assertEqual(loaded.spot_plans, e.spot_plans)
        self.assertEqual(loaded.to_dict()["schema_version"], SCHEMA_VERSION)


if __name__ == "__main__":
    unittest.main()
