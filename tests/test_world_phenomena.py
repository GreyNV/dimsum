"""Rare phenomena: a few small impossible things, never currency. The mossy rock's double
shadow leads to a split-shadow tree whose shimmer makes rare spots likelier nearby; a leaf
that will not fall opens the map; a backward ripple refills the fish."""
import json
import unittest

from dimensional_sim.world.actions import Context, spot_shares, spot_tiers
from dimensional_sim.world.autopilot import Expedition, saves
from dimensional_sim.world.autopilot.ecology import cell_of
from dimensional_sim.world.catalog import BY_ID, ECOLOGY, REGION_CELL
from dimensional_sim.world.models import ChunkKey
from dimensional_sim.world.seeds import canonical_json
from dimensional_sim.world.tuning import SHIMMER_RARITY_PERCENT
from tests.test_world_autopilot import expedition


def happen(e, action_id):
    """Complete `action_id` once (outcomes need a recorded completion)."""
    from dimensional_sim.world.journal import record_action
    record_action(e.journal, action_id)
    e._apply_outcomes(BY_ID[action_id], f"self:{action_id}")


def started():
    e = expedition()
    while e.in_prologue:
        e.advance(500)
    return e


class ChainTests(unittest.TestCase):
    def test_the_shadow_chain_is_wired_and_rare(self):
        rock = BY_ID["mossy_stone"]
        lead = next(o for o in rock.outcomes if o.id == "double_shadow")
        self.assertLessEqual(lead.chance, 15, "a rare follow-up, not every sitting")
        self.assertIn("split_shadow_tree", {o.id for o in BY_ID["double_shadow"].outcomes})
        tree = BY_ID["split_shadow_tree"]
        self.assertEqual(tree.lead_spread, 1)
        self.assertEqual([o.kind for o in tree.outcomes], ["shimmer"])
        for phenomenon in ("hanging_leaf", "backward_ripple", "split_shadow_tree", "double_shadow"):
            action = BY_ID[phenomenon]
            self.assertFalse(action.loot or action.drops or action.blessing, f"{phenomenon} pays no currency")
        for spot in ("hanging_leaf", "backward_ripple"):
            self.assertEqual(BY_ID[spot].rarity, "rare")
            self.assertEqual(BY_ID[spot].window, (0, 1))

    def test_phenomena_stay_out_of_the_old_road(self):
        ctx = Context(region="old_road", ring=3, features=frozenset({"water"}))
        shares = spot_shares(ctx)
        self.assertNotIn("hanging_leaf", shares)
        deep = spot_shares(Context(region="deep_woods", ring=3))
        self.assertIn("hanging_leaf", deep)
        self.assertLess(deep["hanging_leaf"], 300, "under 3% of spot draws even in the deep woods")


class ShimmerTests(unittest.TestCase):
    def test_a_shimmer_raises_rare_odds_in_its_cell_for_this_life(self):
        e = started()
        here = e.game.player.chunk
        before = spot_tiers(e.spot_context(here))
        happen(e, "split_shadow_tree")
        self.assertEqual(e.shimmer, {cell_of(here)})
        after = spot_tiers(e.spot_context(here))
        for tier in ("rare", "uncommon"):
            if tier in before:
                self.assertEqual(after[tier][1], before[tier][1] * SHIMMER_RARITY_PERCENT // 100)
        far = ChunkKey(here.dimension, here.x + REGION_CELL, here.y)
        self.assertEqual(e.spot_context(far).rarity_percent, 100)
        self.assertIn("The air hums. Rare things feel closer here.", [row["text"] for row in e.log])
        from dimensional_sim.world.session import snapshot
        self.assertTrue(snapshot(e.game, expedition=e)["expedition"]["region"]["shimmer"])
        e._new_life_state()
        self.assertEqual(e.shimmer, set())

    def test_shimmer_is_saved_validated_and_migrated(self):
        e = started()
        happen(e, "split_shadow_tree")
        again = Expedition.from_dict(json.loads(canonical_json(e.to_dict())))
        self.assertEqual(again.shimmer, e.shimmer)
        old = {k: v for k, v in e.to_dict().items() if k not in saves.V16_FIELDS}
        old["schema_version"] = 15
        self.assertEqual(Expedition.from_dict(old).shimmer, set())
        for bad in (["elsewhere:0:0"], ["forest:0"], "forest:0:0"):
            data = e.to_dict()
            data["shimmer"] = bad
            with self.assertRaises(ValueError):
                Expedition.from_dict(data)


class OtherPhenomenaTests(unittest.TestCase):
    def test_a_backward_ripple_refills_the_fish_here_only(self):
        e = started()
        here = e.game.player.chunk
        for _ in range(4):
            e._deplete(BY_ID["fishing_pool"], here)
        e._deplete(BY_ID["fallen_branches"], here)
        happen(e, "backward_ripple")
        self.assertEqual(set(e.spot_context(here).pressure), {"wood"}, "fish restored, wood still worked")
        self.assertIn("fish", ECOLOGY)

    def test_a_hanging_leaf_opens_the_map(self):
        e = started()
        called = []
        e.game.reveal_area = lambda radius: called.append(radius)
        happen(e, "hanging_leaf")
        self.assertEqual(len(called), 1)


if __name__ == "__main__":
    unittest.main()
