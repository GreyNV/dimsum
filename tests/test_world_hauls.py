"""Hauls (docs/design/HAULS.md): one encounter gives different amounts each time, drawn from its
outcome bucket (poor, usual, good, rich), tipped by skill; prices and made things never vary.
And the hungry avatar's trip to a food stall."""

import collections
import json
import unittest

from dimensional_sim.world.autopilot import Expedition
from dimensional_sim.world.catalog import ACTIONS, BY_ID, FOOD_TRADES, HAULS, ITEMS
from dimensional_sim.world.encounters import haul_weights, roll_haul, roll_loot, steady
from dimensional_sim.world.models import ChunkKey, chunk_ident
from dimensional_sim.world.seeds import canonical_json
from test_world_village import started

FIXED = next(a for a in ACTIONS if a.loot and not steady(a) and a.loot[0].low >= 3
             and all(l.low == l.high for l in a.loot) and a.loot[0].chance == 100)


def stand(e, x, y):
    key = ChunkKey("forest", x, y)
    e.game.world.get(key)
    e.game._enter(key)
    e.game.player.chunk = key


class HaulTests(unittest.TestCase):
    def test_a_fixed_amount_now_varies_from_one_completion_to_the_next(self):
        counts = collections.Counter()
        for n in range(400):
            haul = roll_haul(FIXED, n)
            counts[sum(c for _, c in roll_loot(FIXED, n, haul) if _ == FIXED.loot[0].item)] += 1
        self.assertGreaterEqual(len(counts), 3, f"{FIXED.id}: several amounts, got {dict(counts)}")
        usual = FIXED.loot[0].low
        self.assertEqual(counts.most_common(1)[0][0], usual, "the usual haul is still the most common")

    def test_every_haul_is_drawn_and_the_bucket_follows_its_weights(self):
        drawn = collections.Counter(roll_haul(FIXED, n).id for n in range(2000))
        self.assertEqual(set(drawn), {h.id for h in HAULS})
        for h in HAULS:
            self.assertAlmostEqual(drawn[h.id] / 2000, h.weight / 100, delta=.04)

    def test_skill_moves_weight_from_poor_to_good_hauls_within_limits(self):
        base, seasoned = haul_weights(0), haul_weights(40)
        self.assertEqual(sum(base.values()), sum(seasoned.values()), "the bucket keeps its size")
        self.assertLess(seasoned["poor"], base["poor"])
        self.assertGreater(seasoned["good"] + seasoned["rich"], base["good"] + base["rich"])
        self.assertEqual(seasoned["usual"], base["usual"])
        self.assertEqual(haul_weights(1000), seasoned, "capped")

    def test_prices_made_things_and_the_story_never_vary(self):
        for a in ACTIONS:
            if a.placement in ("self", "story") or a.category in ("trade", "quest"):
                self.assertIsNone(roll_haul(a, 7), a.id)

    def test_a_named_haul_heads_the_log_line(self):
        e = started()
        texts = set()
        for n in range(40):
            e.inventory = {}
            e._reward(f"enc:test:{n}", FIXED)
            texts.add(e.log[-1]["text"].split(":")[0])
        self.assertTrue({"A poor haul", "A good haul"} <= texts, texts)


class FoodStallTests(unittest.TestCase):
    def test_the_stall_keeps_selling_and_food_is_bought_only_when_hungry(self):
        e = started()
        stall = FOOD_TRADES[0]
        price_item, price = stall.cost[0]
        e.inventory = {price_item: 3}
        self.assertFalse(e.worth_paying(stall), "fed: no bread bought")
        e.hunger = 0
        self.assertTrue(e.worth_paying(stall))
        e._reward("enc:test:stall", stall)
        self.assertNotIn("enc:test:stall", e.completed, "a stall is not used up")

    def test_other_purchases_keep_back_the_price_of_food(self):
        e = started()
        stall = FOOD_TRADES[0]
        price_item, price = stall.cost[0]
        dear = next(a for a in ACTIONS if a.cost and a.placement != "self" and a not in FOOD_TRADES
                    and price_item in dict(a.cost) and price_item not in {l.item for l in a.loot})
        need = dict(dear.cost)[price_item]
        e.inventory = {price_item: need}
        for item, n in dear.cost:
            e.inventory[item] = max(e.inventory.get(item, 0), n)
        self.assertFalse(e.worth_paying(dear), "it would spend the last coin")
        e.inventory[price_item] = need + price
        self.assertTrue(e.worth_paying(dear))

    def test_a_hungry_avatar_with_coins_walks_to_a_village_it_has_seen(self):
        e = started()
        stall = FOOD_TRADES[0]
        village = ChunkKey("forest", 8, 0)
        self.assertEqual(e.game.world.site_for(village).site.id, stall.site)
        e.game.world._discovery[village] = ("visited", "dark_forest")   # seen in an earlier life
        stand(e, 5, 0)
        e.inventory = {stall.cost[0][0]: 2}
        e.hunger = 0
        trip = e._food_trade_trip()
        self.assertEqual((trip["kind"], trip["x"] // e._dims()[0]), ("travel", 8))
        e.spot_plans[chunk_ident(ChunkKey("forest", -8, 0))] = [(stall.id, 0, 0)]
        trip = e._food_trade_trip()
        self.assertEqual(trip["x"] // e._dims()[0], 8,
                         "a distant rolled stall does not hide a nearby known village")
        stand(e, 1, 0)
        self.assertIsNone(e._food_trade_trip(), "too far to walk starving")
        stand(e, 5, 0)
        e.inventory = {}
        self.assertIsNone(e._food_trade_trip(), "no coin, no trip")

    def test_a_travel_goal_is_saved(self):
        e = started()
        e.goal = {"kind": "travel", "id": None, "x": 300, "y": 20}
        loaded = Expedition.from_dict(json.loads(canonical_json(e.to_dict())))
        self.assertEqual(loaded.goal, e.goal)


if __name__ == "__main__":
    unittest.main()
