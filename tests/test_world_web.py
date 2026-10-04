"""Hosted web bridge (Pyodide) and the transport-independent session."""
import json
import unittest
from pathlib import Path

from dimensional_sim.world import session as session_module
from dimensional_sim.world.web import CATCH_UP_SLICE_MS, OFFLINE_CAP_MS, WebGame

IDLE = json.dumps({"move": None, "attack": False, "paused": False, "known": []})


class WebBridgeTests(unittest.TestCase):
    def test_new_game_frames_and_save_round_trip(self):
        game = WebGame(seed=7)
        frame = json.loads(game.input(IDLE, 0.0))
        self.assertEqual(len(frame["chunks"]), 9)
        self.assertEqual(frame["expedition"]["life"], 1)
        for i in range(25):
            game.advance(40, i * 0.04)
        save = game.save()
        restored = WebGame(save)
        self.assertEqual(restored.save(), save)
        self.assertEqual(json.loads(restored.summary())["total_ms"], 1000)
        known = [c["id"] for c in frame["chunks"]]
        self.assertEqual(json.loads(restored.input(json.dumps({**json.loads(IDLE), "known": known}), 9.0))["chunks"], [])

    def test_seeds_give_different_worlds_and_bad_saves_raise(self):
        a, b = json.loads(WebGame(seed=1).state(0)), json.loads(WebGame(seed=2).state(0))
        self.assertNotEqual(a["world_seed"], b["world_seed"])
        with self.assertRaises(ValueError):
            WebGame(json.dumps({"schema_version": 99}))

    def test_offline_progress_uses_efficiency_and_cap(self):
        self.assertEqual(WebGame.offline_ms(0), 0)
        self.assertEqual(WebGame.offline_ms(-5), 0)
        self.assertEqual(WebGame.offline_ms(10_000), 6_500)
        self.assertEqual(WebGame.offline_ms(10 ** 9), OFFLINE_CAP_MS)
        game = WebGame(seed=3)
        self.assertEqual(game.catch_up(60_000), CATCH_UP_SLICE_MS)
        self.assertEqual(json.loads(game.summary())["total_ms"], CATCH_UP_SLICE_MS)

    def test_bulk_advance_equals_ticks_and_pause_freezes(self):
        bulk, ticks = WebGame(seed=5), WebGame(seed=5)
        bulk.advance(4000, 4.0)
        for i in range(200):
            ticks.advance(20, i * 0.02)
        self.assertEqual(bulk.save(), ticks.save())
        paused = json.dumps({"move": None, "attack": False, "paused": True, "known": []})
        bulk.input(paused, 5.0)
        before = bulk.save()
        bulk.advance(5000, 10.0)
        self.assertEqual(bulk.save(), before)

    def test_browser_boot_waits_for_first_input_before_progress(self):
        game = WebGame(seed=3, start_paused=True)
        before = game.save()
        game.advance(5000, 5.0)
        self.assertEqual(game.save(), before)
        frame = json.loads(game.input(IDLE, 5.0))
        self.assertFalse(frame["paused"])
        game.advance(1000, 6.0)
        self.assertEqual(json.loads(game.summary())["total_ms"], 1000)


class SessionModuleTests(unittest.TestCase):
    def test_session_has_no_server_or_thread_imports(self):
        source = Path(session_module.__file__).read_text()
        for banned in ("import threading", "http.server", "import socket", "ThreadingHTTPServer"):
            self.assertNotIn(banned, source)


if __name__ == "__main__":
    unittest.main()
