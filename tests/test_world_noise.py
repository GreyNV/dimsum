"""The lattice noise is pinned: every generator version replays existing worlds through it."""
import hashlib
import json
import unittest

from dimensional_sim.world import noise

POINTS = [(x, y) for x in range(-70, 71, 3) for y in range(-40, 41, 3)]
SEEDS = (0, 1, 2**63 + 12345)
SCALES = ((3, "a"), (5, "canopy"), (12, "vertical-path"), (13, "grove"), (29, "warp-x-29"), (112, "river"))


def digest(function):
    values = [function(seed, x, y, scale, label)
              for seed in SEEDS for scale, label in SCALES for x, y in POINTS]
    return hashlib.sha256(json.dumps(values).encode()).hexdigest()[:16]


class PinnedNoiseTests(unittest.TestCase):
    # Recorded from the four implementations noise.py replaced (open terrain, regions, rivers,
    # groves) on 2026-10-26; a different digest means existing worlds would regrow.
    def test_bilinear_noise_is_unchanged(self):
        self.assertEqual(digest(noise.bilinear), "98051883f42a7d68")

    def test_fine_bilinear_noise_used_by_rivers_is_unchanged(self):
        self.assertEqual(digest(lambda s, x, y, sc, label: noise.bilinear(s, x, y, sc, label, 1000)),
                         "5f0e020db510f9a4")

    def test_smoothstep_noise_is_unchanged(self):
        self.assertEqual(digest(noise.smooth), "63e7981af24696d7")

    def test_values_stay_in_range(self):
        for x, y in POINTS:
            self.assertTrue(0 <= noise.bilinear(7, x, y, 5, "r") <= 100)
            self.assertTrue(0 <= noise.smooth(7, x, y, 5, "r") <= 100)


if __name__ == "__main__":
    unittest.main()
