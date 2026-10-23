"""Determinism guards: a save loaded from disk decides exactly like the run that wrote it.

Found by the golden master of the 2026-10-23 refactoring pass: a loaded save started with the
anchor's chunk in the world cache, which pushed one of the avatar's 3x3 neighbours out; the
auto-pilot then picked wander goals from eight chunks instead of nine and drifted from the
original run. Decisions now read only the full 3x3 (navigation._resident_scan)."""
import json
import unittest

from dimensional_sim.world.autopilot import Expedition
from dimensional_sim.world.runtime import Exploration
from dimensional_sim.world.seeds import canonical_json
from dimensional_sim.world.simulate import anchor_policy
from dimensional_sim.world.web import new_world


class ReloadTests(unittest.TestCase):
    def test_a_reloaded_save_replays_the_original_run_at_every_checkpoint(self):
        for seed in (1, 2):
            e = Expedition(Exploration(new_world(seed), "forest"))
            for checkpoint in range(5):
                end = e.total_ms + 180_000
                while e.total_ms < end:
                    e.advance(997)
                    if e.anchor_ms is not None:
                        anchor_policy(e, "spend")
                twin = Expedition.from_dict(json.loads(canonical_json(e.to_dict())))
                for _ in range(60):
                    twin.advance(1000)
                e.advance(60_000)
                self.assertEqual(canonical_json(e.to_dict()), canonical_json(twin.to_dict()),
                                 f"seed {seed} checkpoint {checkpoint}: a loaded save drifted from its run")

    def test_the_avatar_always_decides_from_its_full_three_by_three(self):
        e = Expedition(Exploration(new_world(1), "forest"))
        e.advance(120_000)
        loaded = Expedition.from_dict(json.loads(canonical_json(e.to_dict())))
        center = loaded.game.player.chunk
        self.assertEqual(sorted((c.key.x - center.x, c.key.y - center.y) for c in loaded._resident()),
                         sorted((dx, dy) for dx in (-1, 0, 1) for dy in (-1, 0, 1)))


if __name__ == "__main__":
    unittest.main()
