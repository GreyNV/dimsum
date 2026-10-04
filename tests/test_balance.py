from contextlib import redirect_stderr, redirect_stdout
from dataclasses import replace
import io
import json
import unittest
from unittest.mock import patch

from dimensional_sim.balance import action_graph, batch, compare, diagnostics, run_scenario
from dimensional_sim.cli import main
from dimensional_sim.core import new_demo_game


class BalanceTests(unittest.TestCase):
    def test_reports_story_dependencies_and_vitality_warnings(self):
        game = new_demo_game()
        report = diagnostics(game)
        self.assertEqual(report["pending_story_actions"][0]["preceding_action"], "talk_father")
        self.assertEqual(report["balance_warnings"], [])
        stage = game.stages[1]
        game.stages[1] = replace(stage, guaranteed_actions=(
            replace(stage.guaranteed_actions[0], vitality_cost=100),))
        self.assertEqual(len(diagnostics(game)["balance_warnings"]), 1)

    def test_report_has_timing_journal_and_summon_evidence(self):
        result = run_scenario(1000, active=True)
        self.assertEqual(result.stage_first_entered["act1_village"], 0)
        self.assertIsNotNone(result.stage_first_entered["act1_forest"])
        self.assertIsNotNone(result.stage_first_entered["act2_old_trail"])
        self.assertTrue(result.action_timings)
        self.assertEqual(result.summon_pools[0]["clone_only_budget_seconds_from_opening"], 450)
        self.assertTrue(result.summon_pools[0]["affordable_now"])
        self.assertAlmostEqual(result.clone_shards_generated, 20)
        self.assertEqual(result.journal_progress["rift_glimpse"]["threshold"], 1000)

    def test_batch_handles_seed_generators_and_zero_time(self):
        result = compare(0, seeds=(s for s in (10, 11)))
        self.assertEqual(set(result), {"active", "offline", "active_with_lens", "offline_with_lens"})
        for variant in result.values():
            self.assertEqual(variant["runs"], 2)
            self.assertEqual(variant["median_shards"], 1)
            self.assertEqual(variant["sample"]["returns_per_hour"], 0)
        with self.assertRaises(ValueError):
            batch(10, active=True, seeds=[])

    def test_equipment_fixture_changes_speed_without_spending_baseline_shards(self):
        baseline = run_scenario(1000, active=True, seed=7)
        lens = run_scenario(1000, active=True, seed=7, equipment_id="echo_bead")
        self.assertAlmostEqual(baseline.clone_shards_generated, lens.clone_shards_generated)
        self.assertLess(lens.action_timings["talk_father"]["mean_simulation_seconds"],
                        baseline.action_timings["talk_father"]["mean_simulation_seconds"])
        with self.assertRaises(KeyError):
            run_scenario(10, active=True, equipment_id="unknown")

    def test_graph_edges_reference_valid_prerequisite_actions(self):
        graph = action_graph(new_demo_game())
        ids = {node["id"] for node in graph["nodes"]}
        self.assertEqual(len(ids), len(graph["nodes"]))
        self.assertEqual(graph["kind"], "eligibility")
        for edge in graph["edges"]:
            self.assertIn(edge["from"], ids)
            self.assertIn(edge["to"], ids)
            self.assertIn("requires", edge)
            self.assertNotIn("dimensional_level", str(edge))

    def test_cli_rejects_invalid_time_and_emits_offline_json(self):
        for args in (["--seconds", "nan"], ["--seconds", "-1"], ["--runs", "0"]):
            with patch("sys.argv", ["sim", *args]), redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit) as exc:
                    main()
            self.assertEqual(exc.exception.code, 2)
        output = io.StringIO()
        with patch("sys.argv", ["sim", "--offline", "--seconds", "10"]), redirect_stdout(output):
            main()
        report = json.loads(output.getvalue())
        self.assertFalse(report["active"])
        self.assertEqual(report["simulation_seconds"], 6.5)

    def test_cli_comparison_honors_seed_and_runs(self):
        output = io.StringIO()
        with patch("sys.argv", ["sim", "--compare", "--seed", "17", "--runs", "2", "--seconds", "1"]):
            with patch("dimensional_sim.cli.compare", return_value={}) as compare_mock:
                with redirect_stdout(output):
                    main()
        self.assertEqual(list(compare_mock.call_args.kwargs["seeds"]), [17, 18])
