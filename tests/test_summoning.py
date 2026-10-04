from collections import Counter
from dataclasses import asdict, replace
import json
from unittest.mock import patch
import unittest

from dimensional_sim.core import DISCIPLINES, GameState, new_demo_game
from dimensional_sim.summoning import SummonProgress, level_range


def pull(game, template_id, level):
    templates, weights = game.soulbound_items, game.config.summon_weights
    template = game.template_by_id(template_id)
    try:
        game.soulbound_items = [template]
        game.config.summon_weights = {template.rarity: 1}
        game.shards += game.config.summon_cost
        with patch.object(game._rng, "randint", return_value=level):
            return game.summon()
    finally:
        game.soulbound_items, game.config.summon_weights = templates, weights


class SummoningTests(unittest.TestCase):
    def test_six_attributes_have_training_actions_and_common_items(self):
        game = new_demo_game()
        expected = {"strength", "endurance", "agility", "intelligence", "perception", "willpower"}
        self.assertEqual(set(DISCIPLINES), expected)
        actions = [a for stage in game.stages for a in (
            *stage.guaranteed_actions, *(e.action for e in stage.encounters))]
        self.assertEqual({a.discipline for a in actions}, expected)
        self.assertEqual({i.discipline for i in game.soulbound_items if i.rarity == "common"}, expected)

    def test_level_windows_match_examples_and_raised_caps(self):
        for level, cap, bounds in ((1, 10, (1, 10)), (100, 100, (90, 100)),
                                   (150, 200, (140, 150))):
            self.assertEqual(level_range(SummonProgress(level, 0, cap)), bounds)

    def test_each_rarity_has_independent_xp_and_item_levels(self):
        game = new_demo_game(3)
        game.config.summon_xp_base = 1
        game.config.summon_xp_growth = 1
        game.raise_summon_cap("common", 100)
        game.summon_progress["common"].xp = 99
        game.summon_progress["common"].level = 100
        game.shards = 200
        commons = [game.summon() for _ in range(10)]
        self.assertTrue(all(90 <= item.level <= 100 for item in commons))
        self.assertEqual(game.summon_progress["uncommon"].xp, 0)
        game.config.summon_weights = {"uncommon": 1}
        item = game.summon()
        self.assertEqual(item.rarity, "uncommon")
        self.assertTrue(1 <= item.level <= 10)
        self.assertEqual(game.summon_progress["uncommon"].xp, 1)
        self.assertEqual(game.summon_progress["rare"].xp, 0)
        self.assertEqual(game.summon_progress["common"].xp, 109)

    def test_pull_uses_level_before_awarding_its_xp(self):
        game = new_demo_game()
        game.config.summon_xp_base = game.config.summon_xp_growth = 1
        game.raise_summon_cap("common", 100)
        game.summon_progress["common"].xp = 9
        game.summon_progress["common"].level = 10
        game.shards = 10
        with patch.object(game._rng, "randint", wraps=game._rng.randint) as randint:
            game.summon()
        randint.assert_called_once_with(1, 10)
        self.assertEqual(game.summon_progress["common"].level, 11)

    def test_caps_preserve_xp_and_can_be_raised_for_one_rarity(self):
        game = new_demo_game()
        game.config.summon_xp_base = game.config.summon_xp_growth = 1
        game.shards = 200
        for _ in range(20):
            game.summon()
        self.assertEqual(game.summon_progress["common"].level, 10)
        self.assertEqual(game.summon_progress["common"].xp, 20)
        game.raise_summon_cap("common", 30)
        self.assertEqual(game.summon_progress["common"].level, 21)
        self.assertEqual(game.summon_progress["uncommon"].max_level, 10)
        with self.assertRaises(ValueError):
            game.raise_summon_cap("common", 20)

    def test_completed_stage_changes_matrix_not_just_entered_or_unlocked(self):
        game = new_demo_game(1)
        self.assertEqual(game.summon_rarity_weights()["common"], 1)
        for _ in range(200):
            if game.completed_stages:
                break
            game.advance(1)
        self.assertEqual(game.completed_stages, ["act1_village"])
        self.assertEqual(game.unlocked_stage, 1)
        self.assertEqual(game.summon_rarity_weights()["uncommon"], 0.1)
        self.assertEqual(game.summon_rarity_weights()["rare"], 0)
        self.assertEqual(game.summon_progress["common"].max_level, 20)
        self.assertEqual(game.summon_progress["common"].level, 1)
        game._return_to_anchor("test")
        self.assertEqual(game.summon_rarity_weights()["uncommon"], 0.1)

    def test_rarity_selection_precedes_item_selection(self):
        game = new_demo_game()
        game.config.summon_weights = {"common": 75, "rare": 25}
        common = game.template_by_id("worn_gauntlets")
        game.soulbound_items.extend(replace(common, id=f"extra_{i}") for i in range(50))
        game.shards = 10
        with patch.object(game._rng, "random", return_value=0.80):
            item = game.summon()
        self.assertEqual(item.rarity, "rare")

    def test_seeded_distribution_matches_authored_row(self):
        game = new_demo_game(123)
        game.config.summon_weights = {"common": 60, "uncommon": 30, "rare": 10}
        game.shards = 30000
        counts = Counter(game.summon().rarity for _ in range(3000))
        for rarity, expected in (("common", .6), ("uncommon", .3), ("rare", .1)):
            self.assertAlmostEqual(counts[rarity] / 3000, expected, delta=.035)

    def test_common_has_one_stat_and_no_extra_modifiers(self):
        game = new_demo_game()
        game.shards = 1000
        for _ in range(100):
            item = game.summon()
            self.assertEqual(item.rarity, "common")
            self.assertEqual(len(item.base_stats), 1)
            self.assertIn(item.discipline, DISCIPLINES)
            self.assertEqual(item.base_stats[item.discipline], item.level)
            self.assertEqual((item.speed_bonus, item.softcap_bonus, item.shard_rate_bonus), (0, 0, 0))

    def test_instances_are_distinct_and_summoning_never_equips(self):
        game = new_demo_game()
        one = pull(game, "worn_gauntlets", 6)
        two = pull(game, "worn_gauntlets", 9)
        self.assertNotEqual(one.id, two.id)
        self.assertEqual(one.template_id, two.template_id)
        self.assertEqual(game.equipped_items, [])
        self.assertEqual(game.pending_summon_reviews, [one.id, two.id])
        self.assertEqual(game.item_by_id(one.id).level, 6)

    def test_invalid_empty_or_negative_weight_pool_does_not_spend_or_roll(self):
        for weights in ({"legendary": 1}, {"common": 0}, {"common": -1}):
            game = new_demo_game()
            game.shards = 100
            game.config.summon_weights = weights
            before = game.to_json()
            with self.assertRaises(ValueError):
                game.summon()
            self.assertEqual(game.to_json(), before)

    def test_rolls_reviews_and_progress_survive_save_and_return(self):
        game = new_demo_game(5)
        game.shards = 500
        game.summon()
        game.advance(500)
        restored = GameState.from_json(game.to_json(), stages=game.stages, soulbound_items=game.soulbound_items)
        self.assertEqual(game.to_json(), restored.to_json())
        self.assertEqual([game.summon() for _ in range(10)], [restored.summon() for _ in range(10)])
        before = {r: asdict(p) for r, p in game.summon_progress.items()}
        reviews = list(game.pending_summon_reviews)
        game._return_to_anchor("test")
        self.assertEqual(before, {r: asdict(p) for r, p in game.summon_progress.items()})
        self.assertEqual(reviews, game.pending_summon_reviews)

    def test_invalid_rolled_item_or_review_in_save_is_rejected(self):
        game = new_demo_game()
        item = pull(game, "worn_gauntlets", 6)
        for corrupt in (
            lambda p: p["summoned_items"][item.id]["base_stats"].update(perception=99),
            lambda p: p["pending_summon_reviews"].append("missing"),
            lambda p: p["summon_progress"]["common"].update(level=100),
        ):
            payload = json.loads(game.to_json())
            corrupt(payload)
            with self.assertRaises(ValueError):
                GameState.from_json(json.dumps(payload), stages=game.stages, soulbound_items=game.soulbound_items)


class EquipmentReviewTests(unittest.TestCase):
    def setUp(self):
        self.game = new_demo_game()
        self.current = pull(self.game, "worn_gauntlets", 6)
        self.game.resolve_summon_review(self.current.id, equip=True)
        self.candidate = pull(self.game, "surveyor_wraps", 9)

    def test_union_rows_include_zero_and_opposite_signed_deltas(self):
        review = self.game.summon_review(self.candidate.id)
        top = {r["key"]: r for r in review["equipped"]["stats"]}
        bottom = {r["key"]: r for r in review["candidate"]["stats"]}
        self.assertEqual(list(top), list(bottom))
        self.assertEqual((top["strength"]["value"], top["strength"]["delta"]), (6, 6))
        self.assertEqual((top["perception"]["value"], top["perception"]["delta"]), (0, -9))
        self.assertEqual((bottom["strength"]["value"], bottom["strength"]["delta"]), (0, -6))
        self.assertEqual((bottom["perception"]["value"], bottom["perception"]["delta"]), (9, 9))
        self.assertEqual(review["summary"], ["Strength -6", "Perception +9"])

    def test_keep_current_spends_no_more_shards_and_retains_both_items(self):
        shards = self.game.shards
        result = self.game.resolve_summon_review(self.candidate.id, equip=False)
        self.assertEqual(result["applied_changes"], [])
        self.assertEqual(self.game.equipped_items, [self.current.id])
        self.assertIn(self.candidate.id, self.game.owned_items)
        self.assertEqual(self.game.shards, shards)
        self.assertNotIn(self.candidate.id, self.game.pending_summon_reviews)

    def test_equip_replaces_same_slot_and_returns_actual_changes(self):
        before = self.game.speed_multiplier("strength")
        result = self.game.resolve_summon_review(self.candidate.id, equip=True)
        self.assertEqual(self.game.equipped_items, [self.candidate.id])
        self.assertIn(self.current.id, self.game.owned_items)
        self.assertAlmostEqual(before - self.game.speed_multiplier("strength"), .06)
        self.assertAlmostEqual(self.game.speed_multiplier("perception"), 1.09)
        self.assertEqual([r["delta"] for r in result["applied_changes"]], [-6, 9])
        with self.assertRaises(ValueError):
            self.game.resolve_summon_review(self.candidate.id, equip=True)

    def test_equipping_does_not_remove_other_slots(self):
        boots = pull(self.game, "soft_boots", 3)
        self.game.resolve_summon_review(boots.id, equip=True)
        self.game.resolve_summon_review(self.candidate.id, equip=True)
        self.assertEqual(set(self.game.equipped_items), {boots.id, self.candidate.id})

    def test_empty_slot_has_zero_comparison_rows(self):
        boots = pull(self.game, "soft_boots", 3)
        review = self.game.summon_review(boots.id)
        self.assertIsNone(review["equipped"]["id"])
        self.assertEqual(review["equipped"]["stats"][0]["value"], 0)
        self.assertEqual(review["equipped"]["stats"][0]["delta"], -3)
        self.assertEqual(review["candidate"]["stats"][0]["delta"], 3)

    def test_decision_recomputes_against_current_loadout(self):
        self.game.summon_review(self.candidate.id)
        replacement = pull(self.game, "worn_gauntlets", 4)
        self.game.resolve_summon_review(replacement.id, equip=True)
        result = self.game.resolve_summon_review(self.candidate.id, equip=True)
        self.assertEqual(result["review"]["summary"], ["Strength -4", "Perception +9"])

    def test_invalid_review_decision_is_atomic(self):
        saved = self.game.to_json()
        with self.assertRaises(ValueError):
            self.game.resolve_summon_review(self.candidate.id, equip="yes")
        self.assertEqual(self.game.to_json(), saved)
