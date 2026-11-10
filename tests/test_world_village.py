"""The village slice (docs/design/VILLAGE.md): the farm, trades, folk quests and the inn's bed."""

import json
import unittest

from dimensional_sim.world.autopilot import Expedition
from dimensional_sim.world.catalog import BY_ID, FARM_GROW_MS, ITEMS, ROAD_SITE_IDS
from dimensional_sim.world.models import ChunkKey
from dimensional_sim.world.runtime import Exploration
from dimensional_sim.world.seeds import canonical_json
from dimensional_sim.world.web import new_world


def started(seed=482910, minutes=2):
    e = Expedition(Exploration(new_world(seed), "forest"))
    for _ in range(minutes):
        e.advance(60_000)
    e.task = e.goal = None
    return e


class FarmTests(unittest.TestCase):
    def test_the_farm_is_bought_in_the_village_and_feeds_every_life_once_bound(self):
        notes = BY_ID["builders_notes"]
        self.assertEqual(notes.site, "village")
        self.assertIn("farming", {o.id for o in notes.outcomes if o.kind == "knowledge"})
        self.assertIn("farming", {r.id for r in BY_ID["build_farm"].requirements})

    def test_crops_ripen_on_a_clock_and_a_hungry_avatar_harvests_them_at_the_camp(self):
        e = started()
        e.buildings.add("farm")
        self.assertTrue(e.farm_ripe(), "a farm is ripe as a life begins")
        e.game.player.chunk = ChunkKey("forest", 0, 0)
        gx, gy = e.anchor
        w, h = e._dims()
        e.game.player.x, e.game.player.y = gx % w, gy % h
        self.assertTrue(e.at_camp())
        e.inventory = {}
        harvest = e._harvest_wanted()
        self.assertEqual(harvest.id, "harvest_farm")
        e._start_self(harvest)
        e.advance(e.task["duration_ms"] + 10)
        self.assertGreater(sum(n for i, n in e.inventory.items() if ITEMS[i].kind == "food"), 0)
        self.assertFalse(e.farm_ripe(), "harvested: the next crop grows")
        e.total_ms += FARM_GROW_MS
        self.assertTrue(e.farm_ripe())

    def test_the_harvest_clock_is_saved(self):
        e = started()
        e.farm_harvest_ms = e.total_ms - 1000
        loaded = Expedition.from_dict(json.loads(canonical_json(e.to_dict())))
        self.assertEqual(loaded.farm_harvest_ms, e.farm_harvest_ms)


class TradeAndQuestTests(unittest.TestCase):
    def test_trades_and_quests_take_their_price_and_pay_in_coins(self):
        e = started()
        stall = BY_ID["bread_stall"]
        self.assertFalse(e.affordable(stall))
        e.inventory = {"tarnished_coin": 2}
        self.assertTrue(e.affordable(stall))
        e._reward("enc:test:stall", stall)
        self.assertEqual(e.inventory.get("tarnished_coin"), 1)
        self.assertEqual(e.inventory.get("bread"), 2)
        e.inventory = {"stick": 5}
        e._reward("enc:test:wood", BY_ID["widow_woodpile"])
        self.assertEqual(e.inventory, {"stick": 1, "tarnished_coin": 2})

    def test_an_unaffordable_trade_changes_nothing_and_stays(self):
        e = started()
        e.inventory = {}
        e._reward("enc:test:stall", BY_ID["bread_stall"])
        self.assertNotIn("enc:test:stall", e.completed)
        self.assertEqual(e.inventory, {})

    def test_every_quest_is_one_of_three_templates(self):
        quests = [a for a in BY_ID.values() if a.category == "quest"]
        self.assertGreaterEqual(len(quests), 3)
        for q in quests:
            deliver = bool(q.cost) and bool(q.loot)
            clear = any(o.kind == "lead" and BY_ID[o.id].category == "fight" for o in q.outcomes)
            self.assertTrue(deliver or clear, f"{q.id}: deliver/fetch (a price paid in items) or clear (a fight lead)")

    def test_the_builders_notes_are_sold_only_until_known(self):
        from dimensional_sim.world.actions import Context, reasons_against
        notes = BY_ID["builders_notes"]
        known = Context(placement="site", knowledge=frozenset({"farming"}))
        self.assertTrue(any("already knows" in r for r in reasons_against(notes, known)))


class InnTests(unittest.TestCase):
    def test_a_rented_bed_is_a_rest_place_and_a_camp_in_the_village(self):
        e = started()
        key = ChunkKey("forest", 8, 0)
        e.game.world.get(key)
        e.game._enter(key)
        site = e.game.world.site_for(key)
        self.assertEqual(site.id, "village")
        e.game.player.chunk, e.game.player.x, e.game.player.y = key, site.x, site.y
        e.game._reveal()
        e.inventory = {"tarnished_coin": 1}
        e._reward("enc:test:inn", BY_ID["village_inn"])
        self.assertTrue(e.campfire["bed"])
        self.assertTrue(e.at_rest_place())
        self.assertTrue(e.camping())
        self.assertEqual(e.camp["location"], "village")
        loaded = Expedition.from_dict(json.loads(canonical_json(e.to_dict())))
        self.assertTrue(loaded.campfire["bed"])


class RoadContentTests(unittest.TestCase):
    def test_road_sites_have_their_own_encounters_and_the_bandits_carry_the_story(self):
        for site in ROAD_SITE_IDS:
            self.assertTrue([a for a in BY_ID.values() if a.site == site], site)
        spoils = BY_ID["bandit_spoils"]
        self.assertTrue(any(o.kind == "note" and "satchel" in o.text for o in spoils.outcomes))


if __name__ == "__main__":
    unittest.main()
