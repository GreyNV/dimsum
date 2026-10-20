"""Attribute effects that change exploration and direct control."""
import unittest

from dimensional_sim.world.autopilot import Expedition
from dimensional_sim.world.runtime import Exploration, InputCommand
from dimensional_sim.world.web import new_world


class AttributeAffordanceTests(unittest.TestCase):
    def expedition(self):
        e = Expedition(Exploration(new_world(482910), "forest"))
        while e.in_prologue:
            e.advance(500)
        e.goal = e.task = None
        return e

    def test_perception_and_willpower_reveal_more_cells_without_erasing_fog(self):
        e = self.expedition()
        key = e.game.player.chunk
        before = [row for row in e.game.seen[key]]
        self.assertEqual(e.game.reveal_radius, 5)
        e.regular["perception"] = 500  # four regular levels
        e.advance(0)
        self.assertEqual(e.game.reveal_radius, 6)
        self.assertTrue(all(a & b == b for a, b in zip(e.game.seen[key], before)))
        self.assertGreater(sum(row.bit_count() for row in e.game.seen[key]),
                           sum(row.bit_count() for row in before))
        e.regular["willpower"] = 500
        e.advance(0)
        self.assertEqual(e.game.reveal_radius, 7)
        restored = Expedition.from_dict(e.to_dict())
        restored.advance(0)
        self.assertEqual(restored.game.reveal_radius, 7)
        self.assertEqual(restored.game.seen, e.game.seen)
        e.regular["perception"] = e.regular["willpower"] = 1_000_000
        e.advance(0)
        self.assertEqual(e.game.reveal_radius, 8)

    def test_willpower_extends_possession_and_survives_reload(self):
        e = self.expedition()
        e.regular["willpower"] = 500
        self.assertEqual(e.possession()["duration_ms"], 38_000)
        e.possess()
        self.assertEqual(e.possession()["remaining_ms"], 38_000)
        restored = Expedition.from_dict(e.to_dict())
        self.assertEqual(restored.possession()["remaining_ms"], 38_000)
        restored.advance_manual(37_999, InputCommand())
        self.assertTrue(restored.possessing)
        restored.advance_manual(1, InputCommand())
        self.assertFalse(restored.possessing)
        e.regular["willpower"] = 1_000_000
        self.assertEqual(e.possession()["duration_ms"], 60_000)


if __name__ == "__main__":
    unittest.main()
