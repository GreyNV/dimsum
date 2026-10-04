import base64
from dataclasses import asdict, replace
import json
import math
import pickle
import unittest
from unittest.mock import patch

from dimensional_sim.core import (
    Action, Encounter, GameConfig, GameState, JournalEntry, SoulboundItem,
    Stage, _softcapped_level, new_demo_game,
)


def simple_game(*, cost=0, seconds=1000, regular=1, dimensional=0,
                vitality=100, decay=0, encounter=None):
    action = Action("train", "Train", "endurance", seconds, cost, regular, dimensional)
    stage = Stage("start", "Start", 1, (action,), (encounter,) if encounter else ())
    return GameState(
        replace(GameConfig(), starting_vitality=vitality, vitality_decay_per_second=decay),
        [stage], [], seed=1,
    )


class RegressionTests(unittest.TestCase):
    def assert_nested_close(self, left, right):
        if isinstance(left, dict):
            self.assertEqual(set(left), set(right))
            for key in left:
                self.assert_nested_close(left[key], right[key])
        elif isinstance(left, (list, tuple)):
            self.assertEqual(len(left), len(right))
            for a, b in zip(left, right):
                self.assert_nested_close(a, b)
        elif isinstance(left, float):
            self.assertTrue(math.isclose(left, right, rel_tol=1e-9, abs_tol=1e-7),
                            (left, right))
        else:
            self.assertEqual(left, right)

    def load(self, game, raw=None, **kwargs):
        return GameState.from_json(
            raw or game.to_json(), stages=game.stages,
            soulbound_items=game.soulbound_items, **kwargs,
        )

    def test_short_updates_equal_one_long_update_across_returns(self):
        for active in (True, False):
            with self.subTest(active=active):
                bulk, split = new_demo_game(19), new_demo_game(19)
                bulk.advance(5000, active=active)
                for _ in range(2000):
                    split.advance(2.5, active=active)
                self.assert_nested_close(bulk.summary(), split.summary())
                self.assert_nested_close(asdict(bulk.current_run), asdict(split.current_run))
                self.assert_nested_close(bulk.event_log, split.event_log)
                self.assertEqual(bulk._rng.getstate(), split._rng.getstate())

    def test_partial_work_and_xp_survive_save_load(self):
        game = new_demo_game(4)
        game.advance(7.5)
        self.assertGreater(game.current_run.action_work, 0)
        self.assertGreater(sum(game.regular_xp.values()), 0)
        restored = self.load(game)
        game.advance(5000)
        restored.advance(5000)
        self.assertEqual(game.to_json(), restored.to_json())

    def test_speed_changes_at_xp_threshold_mid_action(self):
        game = simple_game()
        game.advance(110)
        # First 100 seconds at speed 1, then 10 seconds at speed 1.1.
        self.assertAlmostEqual(game.current_run.action_work, 111)
        self.assertAlmostEqual(game.regular_xp["endurance"], 110)

    def test_training_is_per_second_not_per_action_work(self):
        game = simple_game(seconds=100, regular=1)
        game.config.regular_speed_per_level = 0
        item = SoulboundItem("fast", "Fast", "uncommon", speed_bonus=1, discipline="endurance")
        game.soulbound_items = [item]
        game.config.summon_weights = {"uncommon": 1}
        game.config.summon_cost = 1
        game.config.item_speed_per_stat = 0
        summoned = game.summon()
        game.equip(summoned.id)
        game.advance(50)
        self.assertAlmostEqual(game.regular_xp["endurance"], 50)
        self.assertEqual(game.current_run.completed_actions, 1)

    def test_death_interrupts_action_and_resets_only_temporary_state(self):
        game = simple_game(cost=20, seconds=100, regular=0, dimensional=1, vitality=10)
        game.config.dimensional_speed_per_level = 0
        game.advance(50)
        self.assertEqual(game.life_count, 2)
        self.assertEqual(game.current_run.completed_actions, 0)
        self.assertEqual(game.current_run.action_work, 0)
        self.assertEqual(sum(game.regular_xp.values()), 0)
        self.assertAlmostEqual(game.dimensional_xp["endurance"], 50)
        self.assertAlmostEqual(game.clone_shards_generated, 1)

    def test_zero_vitality_wins_over_simultaneous_completion(self):
        game = simple_game(cost=10, seconds=10, regular=0, vitality=10)
        game.advance(10)
        self.assertEqual(game.life_count, 2)
        self.assertFalse(any(e["event"] == "action_completed" for e in game.event_log))

    def test_passive_vitality_decay(self):
        game = simple_game(regular=0, vitality=10, decay=1)
        game.advance(10)
        self.assertEqual(game.life_count, 2)

    def test_lethal_encounter_returns_immediately(self):
        encounter = Encounter("hazard", "Hazard", "common", 1,
                              Action("fight", "Fight", "endurance", 1, 0, 0, 0),
                              vitality_delta=-200)
        game = simple_game(seconds=1, regular=0, encounter=encounter)
        game.advance(2)
        self.assertEqual(game.life_count, 2)
        self.assertEqual(game.current_run.vitality, 100)
        self.assertEqual(game.journal["hazard"].completions, 1)

    def test_recovery_is_capped(self):
        encounter = Encounter("spring", "Spring", "common", 1,
                              Action("drink", "Drink", "endurance", 1, 0, 0, 0),
                              vitality_delta=200)
        game = simple_game(seconds=1, regular=0, encounter=encounter)
        game.advance(2)
        self.assertEqual(game.current_run.vitality, 100)

    def test_equivalent_effective_time_uses_same_action_path(self):
        active, offline = new_demo_game(4), new_demo_game(4)
        active.advance(650)
        offline.advance(1000, active=False)
        for name in ("regular_xp", "dimensional_xp", "life_count", "unlocked_stage"):
            self.assert_nested_close(getattr(active, name), getattr(offline, name))
        self.assert_nested_close(asdict(active.current_run), asdict(offline.current_run))
        self.assertEqual(active._rng.getstate(), offline._rng.getstate())
        self.assertAlmostEqual(offline.clone_shards_generated, 20)

    def test_efficiency_one_is_identical_to_active(self):
        active, offline = new_demo_game(4), new_demo_game(4)
        active.config.offline_efficiency = offline.config.offline_efficiency = 1
        active.advance(5000)
        offline.advance(5000, active=False)
        self.assertEqual(active.to_json(), offline.to_json())

    def test_zero_efficiency_still_accrues_clone_shards(self):
        game = new_demo_game()
        game.config.offline_efficiency = 0
        run = asdict(game.current_run)
        game.advance(500, active=False)
        self.assertEqual(asdict(game.current_run), run)
        self.assertEqual(game.world_seconds, 500)
        self.assertEqual(game.simulation_seconds, 0)
        self.assertEqual(game.shards, 11)

    def test_journal_discovery_precedes_completion_and_unlock_keeps_enabled(self):
        encounter = Encounter("discovery", "Discovery", "common", 1,
                              Action("discover", "Discover", "perception", 1, 0, 0, 0))
        game = simple_game(seconds=1, regular=0, encounter=encounter)
        self.assertEqual(game.journal["discovery"].first_seen_at, 0)
        self.assertEqual(game.journal["discovery"].completions, 0)
        game.config.journal_thresholds["common"] = 1
        game.advance(2)
        self.assertTrue(game.journal["discovery"].unlocked)
        self.assertTrue(game.journal["discovery"].enabled)
        current_bucket = list(game.current_run.action_queue)
        game.configure_journal("discovery", False)
        self.assertEqual(game.current_run.action_queue, current_bucket)
        game.advance(2)
        self.assertIsNone(game.current_run.selected_encounter)
        self.assertEqual(game.current_run.action_queue, ["train"])

    def test_restart_cannot_reroll_or_preserve_regular_xp(self):
        game = new_demo_game()
        game.advance(7)
        saved = game.to_json()
        with self.assertRaises(ValueError):
            game.start_life()
        self.assertEqual(game.to_json(), saved)

    def test_summons_charge_shared_cost_for_all_rarities(self):
        game = new_demo_game()
        game.shards = 100
        for rarity in ("common", "uncommon", "rare"):
            game.config.summon_weights = {rarity: 1}
            before = game.shards
            item = game.summon()
            self.assertEqual(item.rarity, rarity)
            self.assertEqual(before - game.shards, game.config.summon_cost)

    def test_failed_summon_is_atomic(self):
        game = new_demo_game()
        before = game.to_json()
        with self.assertRaises(ValueError):
            game.summon()
        self.assertEqual(game.to_json(), before)

    def test_seeded_summons_are_reproducible(self):
        left, right = new_demo_game(16), new_demo_game(16)
        for game in (left, right):
            game.soulbound_items.append(
                SoulboundItem("second", "Second", "common", discipline="perception"))
            game.shards = 200
        self.assertEqual([left.summon() for _ in range(20)],
                         [right.summon() for _ in range(20)])

    def test_duplicate_equipping_does_not_stack_and_can_be_undone(self):
        game = new_demo_game()
        game.shards = 10
        item = game.summon()
        initial_speed = game.speed_multiplier("perception")
        game.equip(item.id)
        equipped_speed = game.speed_multiplier("perception")
        game.equip(item.id)
        self.assertEqual(equipped_speed, game.speed_multiplier("perception"))
        game.unequip(item.id)
        self.assertEqual(initial_speed, game.speed_multiplier("perception"))

    def test_equipment_and_journal_survive_return(self):
        game = new_demo_game()
        game.shards = 10
        item = game.summon()
        game.equip(item.id)
        game.journal["village_mystery"] = JournalEntry(10, True, False, 0)
        game.advance(5)
        dimensional = dict(game.dimensional_xp)
        shards = game.shards
        game._return_to_anchor("test")
        self.assertEqual(game.equipped_items, [item.id])
        self.assertEqual(game.owned_items, [item.id])
        self.assertFalse(game.journal["village_mystery"].enabled)
        self.assertEqual(game.dimensional_xp, dimensional)
        self.assertEqual(game.shards, shards)

    def test_invalid_elapsed_time_does_not_mutate(self):
        game = new_demo_game()
        before = game.to_json()
        for seconds in (-1, float("nan"), float("inf")):
            with self.assertRaises(ValueError):
                game.advance(seconds)
            self.assertEqual(game.to_json(), before)

    def test_invalid_content_fails_before_simulation(self):
        game = new_demo_game()
        bad_configs = [
            replace(game.config, regular_xp_growth=0.5),
            replace(game.config, starting_vitality=0),
            replace(game.config, offline_efficiency=1.1),
            replace(game.config, clone_shards_per_second=float("nan")),
            replace(game.config, journal_thresholds={"common": 0}),
        ]
        for config in bad_configs:
            with self.subTest(config=config), self.assertRaises(ValueError):
                GameState(config, game.stages, game.soulbound_items)
        stage = game.stages[0]
        invalid_stages = [
            [replace(stage, guaranteed_actions=())],
            [stage, stage],
            [replace(stage, guaranteed_actions=(
                replace(stage.guaranteed_actions[0], base_seconds=0),))],
            [replace(stage, guaranteed_actions=(
                replace(stage.guaranteed_actions[0], discipline="missing"),))],
            [replace(stage, encounters=(replace(stage.encounters[0], weight=-1),))],
            [replace(stage, encounters=(replace(stage.encounters[0], weight=2),))],
        ]
        for stages in invalid_stages:
            with self.subTest(stages=stages), self.assertRaises(ValueError):
                GameState(game.config, stages, [])

    def test_softcap_is_monotonic_with_positive_diminishing_returns(self):
        values = [_softcapped_level(level, 10, 0.08) for level in range(10, 100)]
        gains = [b - a for a, b in zip(values, values[1:])]
        self.assertTrue(all(gain > 0 for gain in gains))
        self.assertTrue(all(a > b for a, b in zip(gains, gains[1:])))

    def test_save_embeds_balance_config_and_rejects_mismatch(self):
        game = new_demo_game()
        game.config.offline_efficiency = 0.3
        game.advance(13)
        restored = self.load(game)
        self.assertEqual(game.config, restored.config)
        with self.assertRaises(ValueError):
            self.load(game, config=GameConfig())
        with self.assertRaises(ValueError):
            GameState.from_json(game.to_json(),
                                stages=[replace(game.stages[0], name="Changed"), *game.stages[1:]],
                                soulbound_items=game.soulbound_items)

    def test_invalid_save_state_is_rejected(self):
        game = new_demo_game()
        for mutate in (
            lambda p: p.update(schema_version=99),
            lambda p: p.update(shards=-1),
            lambda p: p.update(equipped_items=["missing"]),
            lambda p: p["current_run"].update(stage_index=999),
            lambda p: p["current_run"].update(action_queue=["missing"]),
            lambda p: p["current_run"].update(action_work=99999),
            lambda p: p["regular_xp"].pop("endurance"),
            lambda p: p.update(rng_state=[3, [], None]),
        ):
            payload = json.loads(game.to_json())
            mutate(payload)
            with self.subTest(payload=payload), self.assertRaises(ValueError):
                self.load(game, json.dumps(payload))

    def test_schema_one_rng_migration_preserves_random_continuation(self):
        game = new_demo_game(14)
        game.advance(7)
        payload = json.loads(game.to_json())
        payload["schema_version"] = 1
        payload["rng_state"] = base64.b64encode(pickle.dumps(game._rng.getstate())).decode()
        payload.pop("config")
        payload.pop("content")
        payload["current_run"].pop("action_work")
        payload["current_run"].pop("action_seconds")
        restored = self.load(game, json.dumps(payload), config=game.config)
        self.assertEqual(game._rng.getstate(), restored._rng.getstate())
        self.assertEqual(restored.current_run.action_work, 0)
        self.assertEqual(json.loads(restored.to_json())["schema_version"], 5)

    def test_legacy_save_cannot_execute_pickle_reducers(self):
        class Exploit:
            def __reduce__(self):
                return eval, ("40 + 2",)
        game = new_demo_game()
        payload = json.loads(game.to_json())
        payload["schema_version"] = 1
        payload["rng_state"] = base64.b64encode(pickle.dumps(Exploit())).decode()
        with patch("builtins.eval") as evaluate, self.assertRaises(ValueError):
            self.load(game, json.dumps(payload))
        evaluate.assert_not_called()
