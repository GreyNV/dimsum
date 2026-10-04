import unittest

from dimensional_sim.core import JournalEntry, new_demo_game


class SimulationTests(unittest.TestCase):
    def test_seeded_runs_are_deterministic(self) -> None:
        left = new_demo_game(7)
        right = new_demo_game(7)
        left.advance(20_000)
        right.advance(20_000)
        self.assertEqual(left.summary(), right.summary())

    def test_anchor_return_resets_regular_but_not_dimensional_xp(self) -> None:
        game = new_demo_game(2)
        game.advance(20_000)
        dimensional_before = dict(game.dimensional_xp)
        game._return_to_anchor("test")
        self.assertTrue(all(value == 0 for value in game.regular_xp.values()))
        self.assertEqual(dimensional_before, game.dimensional_xp)

    def test_offline_progress_is_reduced_but_nonzero(self) -> None:
        active = new_demo_game(3)
        offline = new_demo_game(3)
        active.advance(100_000, active=True)
        offline.advance(100_000, active=False)
        self.assertGreater(offline.dimensional_xp["endurance"], 0)
        self.assertEqual(offline.world_seconds, active.world_seconds)
        self.assertLess(offline.simulation_seconds, active.simulation_seconds)
        self.assertAlmostEqual(offline.clone_shards_generated, active.clone_shards_generated)

    def test_journal_unlock_can_disable_future_encounters(self) -> None:
        game = new_demo_game(11)
        game.journal["village_mystery"] = JournalEntry(completions=10)
        game.journal["village_mystery"].unlocked = True
        game.journal["village_mystery"].enabled = False
        game.configure_journal("village_mystery", False)
        self.assertFalse(game.journal["village_mystery"].enabled)

    def test_soulbound_items_require_shards(self) -> None:
        game = new_demo_game(4)
        game.shards = 0
        with self.assertRaises(ValueError):
            game.summon()
        game.shards = 100
        item = game.summon()
        self.assertIn(item.id, game.owned_items)

    def test_stage_progress_follows_story_completion_and_persists(self) -> None:
        game = new_demo_game(5)
        game.advance(100_000)
        self.assertEqual(game.unlocked_stage, 2)
        game._return_to_anchor("test")
        self.assertEqual(game.unlocked_stage, 2)
        self.assertEqual(game.current_run.stage_index, 0)

    def test_save_load_preserves_bucket_and_future_seeded_results(self) -> None:
        original = new_demo_game(13)
        original.advance(1_000)
        restored = type(original).from_json(
            original.to_json(),
            stages=original.stages,
            soulbound_items=original.soulbound_items,
            config=original.config,
        )
        self.assertEqual(original.summary(), restored.summary())
        original.advance(20_000)
        restored.advance(20_000)
        self.assertEqual(original.summary(), restored.summary())


if __name__ == "__main__":
    unittest.main()
