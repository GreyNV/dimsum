import json
from dataclasses import replace
import unittest
from unittest.mock import patch

from dimensional_sim.balance import action_graph, diagnostics
from dimensional_sim.core import Action, Encounter, GameConfig, GameState, JournalEntry, Stage


def make_game(*, weights=(0.0, 0.0), journal=None):
    story = Action("story", "Story", "perception", 10, 0, 0, 0)
    next_story = Action("next_story", "Next", "endurance", 10, 0, 0, 0)
    encounters = tuple(
        Encounter("enc" + str(i), "Encounter", "common", weight,
                  Action("extra" + str(i), "Extra", "willpower", 5, 0, 0, 0))
        for i, weight in enumerate(weights)
    )
    return GameState(
        replace(GameConfig(), vitality_decay_per_second=0),
        [Stage("first", "First", 1, (story,), encounters),
         Stage("second", "Second", 2, (next_story,), ())],
        [], seed=1, journal=journal or {},
    )


class ProgressionTests(unittest.TestCase):
    def load(self, game, raw=None):
        return GameState.from_json(raw or game.to_json(), stages=game.stages,
                                   soulbound_items=game.soulbound_items)

    def test_story_progression_needs_no_xp(self):
        game = make_game()
        game.advance(10)
        self.assertEqual(game.current_run.stage_index, 1)
        self.assertEqual(game.unlocked_stage, 1)
        self.assertTrue(all(xp == 0 for xp in game.dimensional_xp.values()))
        self.assertEqual(game.current_run.action_queue, ["next_story"])

    def test_story_completion_unlocks_next_stage_before_optional_action(self):
        game = make_game(weights=(1, 0))
        game.advance(9)
        self.assertEqual(game.unlocked_stage, 0)
        self.assertEqual(game.journal["enc0"].completions, 0)
        game.advance(1)
        self.assertEqual(game.unlocked_stage, 1)
        self.assertEqual(game.current_run.stage_index, 0)
        self.assertEqual(game.current_run.action_queue, ["extra0"])
        self.assertEqual(game.journal["enc0"].completions, 0)

    def test_unrolled_locked_actions_are_absent(self):
        game = make_game()
        game.advance(10)
        self.assertEqual(game.journal, {})
        self.assertEqual(game.current_run.stage_index, 1)

    def test_journal_unlock_supplies_multiple_actions_without_roll(self):
        journal = {f"enc{i}": JournalEntry(10, True, True, 0) for i in range(2)}
        game = make_game(journal=journal)
        self.assertEqual(game.current_run.stage_buckets["first"], [])
        self.assertEqual(game.current_run.encounter_bucket, ["enc0", "enc1"])
        self.assertEqual(game.current_run.action_queue, ["story", "extra0", "extra1"])
        game.advance(9)
        self.assertEqual([e.completions for e in game.journal.values()], [10, 10])
        game.advance(11)
        self.assertEqual([e.completions for e in game.journal.values()], [11, 11])
        self.assertEqual(game.current_run.stage_index, 1)

    def test_journal_discovery_alone_does_not_grant_access(self):
        game = make_game(journal={"enc0": JournalEntry(1, False, True, 0)})
        self.assertEqual(game.current_run.encounter_bucket, [])

    def test_disabled_unlocked_action_is_omitted_even_at_full_probability(self):
        game = make_game(weights=(1, 0), journal={"enc0": JournalEntry(10, True, False, 0)})
        self.assertEqual(game.current_run.encounter_bucket, [])
        self.assertEqual(game.current_run.action_queue, ["story"])

    def test_toggle_does_not_rewrite_pending_bucket(self):
        game = make_game(journal={"enc0": JournalEntry(10, True, True, 0)})
        game.advance(10)
        game.configure_journal("enc0", False)
        self.assertEqual(game.current_run.action_queue, ["extra0"])
        game.advance(15)  # finish encounter and next story, then revisit first
        self.assertEqual(game.current_run.action_queue, ["story"])

    def test_roll_is_cached_for_life_and_resets_on_return(self):
        game = make_game(weights=(1, 0))
        with patch.object(game, "_roll_encounter", wraps=game._roll_encounter) as roll:
            game.advance(25)  # first -> encounter -> second -> first again
            self.assertEqual(roll.call_count, 1)  # second stage only
            self.assertEqual(game.current_run.encounter_bucket, ["enc0"])
            game._return_to_anchor("test")
            self.assertEqual(roll.call_count, 2)  # first stage gets a new life roll
            self.assertEqual(game.current_run.completed_story_actions, [])
            self.assertEqual(set(game.current_run.stage_buckets), {"first"})

    def test_partial_multi_encounter_bucket_survives_reload(self):
        game = make_game(journal={f"enc{i}": JournalEntry(10, True, True, 0) for i in range(2)})
        game.advance(12)
        restored = self.load(game)
        self.assertEqual(game.to_json(), restored.to_json())
        game.advance(100)
        restored.advance(100)
        self.assertEqual(game.to_json(), restored.to_json())

    def test_legacy_save_removes_only_numeric_gates_and_keeps_bucket(self):
        game = make_game(weights=(1, 0))
        game.advance(12)
        payload = json.loads(game.to_json())
        payload["schema_version"] = 2
        for stage in payload["content"]["stages"]:
            stage["min_dimensional_level"] = 12
            stage["gate_discipline"] = "willpower"
        for key in ("encounter_bucket", "stage_buckets", "completed_story_actions"):
            payload["current_run"].pop(key)
        payload["unlocked_stage"] = 0  # old engine waited until whole bucket finished
        rng = game._rng.getstate()
        restored = self.load(game, json.dumps(payload))
        self.assertEqual(restored.current_run.action_queue, ["extra0"])
        self.assertEqual(restored.current_run.action_work, 2)
        self.assertEqual(restored.unlocked_stage, 1)
        self.assertEqual(restored._rng.getstate(), rng)
        restored.advance(3)
        self.assertEqual(restored.current_run.stage_index, 1)
        payload["content"]["stages"][0]["name"] = "Unrelated changed content"
        with self.assertRaises(ValueError):
            self.load(game, json.dumps(payload))

    def test_invalid_bucket_injection_is_rejected(self):
        game = make_game()
        payload = json.loads(game.to_json())
        payload["current_run"]["encounter_bucket"] = ["enc0"]
        payload["current_run"]["action_queue"].append("extra0")
        with self.assertRaises(ValueError):
            self.load(game, json.dumps(payload))

    def test_reports_and_graph_explain_story_and_bucket_dependencies(self):
        game = make_game()
        report = diagnostics(game)
        self.assertEqual(report["pending_story_actions"],
                         [{"stage": "second", "action": "next_story", "preceding_action": "story"}])
        self.assertNotIn("required_level", json.dumps(report))
        graph = action_graph(game)
        self.assertEqual(graph["kind"], "eligibility")
        edge = next(e for e in graph["edges"] if e["to"] == "extra0")
        self.assertEqual(edge["from"], "story")
        self.assertIn("in_current_run_bucket", json.dumps(edge))
        self.assertIn("journal_unlocked_and_enabled", json.dumps(edge))
