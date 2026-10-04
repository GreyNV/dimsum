"""Cross-boundary acceptance tests; use real world/runtime/renderer, no external API."""
from contextlib import contextmanager, redirect_stdout
from copy import deepcopy
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from dimensional_sim.world.cli import main, command_script
from dimensional_sim.world.models import ChunkKey, DimensionSpec, chunk_to_dict
from dimensional_sim.world.repository import WorldRepository
from dimensional_sim.world.renderer import render, to_text, minimap_cells
from dimensional_sim.world.runtime import Exploration, InputCommand
from dimensional_sim.world.seeds import canonical_json
from dimensional_sim.world.terminal import play


def game():
    return Exploration(WorldRepository(482910, (DimensionSpec("forest", width=12, height=8),)))


class WorldIntegrationTests(unittest.TestCase):
    def test_seed_world_render_attack_without_provider(self):
        with patch("dimensional_sim.world.pipeline.LocalProvider.generate",
                   side_effect=AssertionError("gameplay requested provider")) as provider:
            run = game()
            before = canonical_json(chunk_to_dict(run.current_chunk()))
            run.advance(120, InputCommand(move="east"))
            target = next(t for t in run.targets.values() if
                          t.chunk == run.player.chunk and (t.x,t.y) == (run.player.x+1,run.player.y))
            initial = target.hp
            run.advance(119, InputCommand(attack=True))
            self.assertEqual(target.hp, initial)
            run.advance(1, InputCommand(attack=True))
            self.assertEqual(target.hp, initial-1)
            frame = render(run, width=12, height=8, show_map=False)
            self.assertEqual(frame.cells[run.player.y][run.player.x].glyph, "@")
            self.assertEqual(frame.cells[target.y][target.x].glyph, "*")
            run.advance(1000, InputCommand(attack=True))
            self.assertEqual(target.hp, initial-1)
            self.assertEqual(before, canonical_json(chunk_to_dict(run.current_chunk())))
            provider.assert_not_called()

    def test_render_and_map_read_do_not_mutate_or_generate(self):
        run = game()
        before = canonical_json(run.to_dict())
        count = run.world.generation_count
        with patch.object(run.world._generator, "generate", side_effect=AssertionError("render generated")):
            for _ in range(20):
                render(run, width=9, height=6)
                minimap_cells(run.world, run.player.chunk, 2)
                run.player_cell()
                run.effect_cells()
        self.assertEqual(before, canonical_json(run.to_dict()))
        self.assertEqual(count, run.world.generation_count)

    def test_render_frequency_does_not_change_gameplay(self):
        bulk, split = game(), game()
        for run in (bulk, split): run.advance(120, InputCommand(move="east"))
        bulk.advance(700, InputCommand(attack=True))
        for _ in range(70):
            split.advance(10, InputCommand(attack=True))
            render(split)
        self.assertEqual(canonical_json(bulk.to_dict()), canonical_json(split.to_dict()))

    def test_terminal_fps_is_independent_from_simulation_ticks(self):
        states = []
        for fps in (3, 120):
            run = game()
            keys = iter([["d", " "]] + [[]]*100)
            @contextmanager
            def fake_keyboard():
                yield lambda: next(keys, [])
            @contextmanager
            def fake_display(plain):
                yield True
            clock = iter(range(0, 10_000_000_000, 20_000_000))
            with patch("dimensional_sim.world.terminal.keyboard", fake_keyboard), \
                 patch("dimensional_sim.world.terminal.display", fake_display), \
                 patch("dimensional_sim.world.terminal.time.monotonic_ns", side_effect=lambda: next(clock)), \
                 patch("dimensional_sim.world.terminal.time.sleep"), redirect_stdout(io.StringIO()):
                play(run, fps=fps, max_ticks=40)
            self.assertEqual(run.elapsed_ms, 800)
            states.append(canonical_json(run.to_dict()))
        self.assertEqual(*states)

    def test_save_after_partial_attack_continues_without_api_or_catalog_directory(self):
        run = game()
        run.advance(120, InputCommand(move="east"))
        run.advance(150, InputCommand(attack=True))
        raw = json.loads(canonical_json(run.to_dict()))
        resumed = Exploration.from_dict(raw)
        for actor in (run, resumed):
            actor.advance(10, InputCommand(attack=True))
            actor.advance(400, InputCommand())
            actor.advance(250, InputCommand(move="west"))
        self.assertEqual(canonical_json(run.to_dict()), canonical_json(resumed.to_dict()))

    def test_cli_demo_save_load_and_parse_before_apply(self):
        with tempfile.TemporaryDirectory() as folder:
            saved = Path(folder)/"exploration.json"
            out = io.StringIO()
            with redirect_stdout(out):
                self.assertEqual(main(["demo","--format","json","--save",str(saved)]), 0)
            report = json.loads(out.getvalue())
            self.assertEqual(report["player"]["facing"], "east")
            self.assertTrue(any(t["hp"] == 2 for t in report["targets"]))
            with redirect_stdout(io.StringIO()):
                self.assertEqual(main(["demo","--load",str(saved),"--commands","wait:0"]), 0)
            with self.assertRaises(ValueError): command_script("east:120,typo:100")
            with self.assertRaises(ValueError): command_script("east:-1")

    def test_cli_generation_retries_skip_all_accepted(self):
        with tempfile.TemporaryDirectory() as folder:
            args = ["generate-assets","--chunks","2","--variants","2","--size","8x6","--output",folder]
            with redirect_stdout(io.StringIO()) as output:
                self.assertEqual(main(args), 0)
            report = json.loads(output.getvalue())
            self.assertEqual(report["counts"], {"accepted":4})
            with patch("dimensional_sim.world.pipeline.LocalProvider.generate", side_effect=AssertionError), \
                 redirect_stdout(io.StringIO()):
                self.assertEqual(main(args), 0)
            self.assertTrue(Path(report["manifest"]).is_file())

    def test_runtime_import_does_not_load_provider_pipeline(self):
        code = ("import sys; from dimensional_sim.world.runtime import Exploration; "
                "from dimensional_sim.world.repository import WorldRepository; "
                "from dimensional_sim.world.renderer import render; "
                "g=Exploration(WorldRepository()); render(g); "
                "assert 'dimensional_sim.world.pipeline' not in sys.modules; print('offline')")
        result = subprocess.check_output([sys.executable,"-B","-c",code],
            env={**os.environ,"PYTHONPATH":"src"},text=True)
        self.assertEqual(result.strip(),"offline")
