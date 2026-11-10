"""The full map (world/atlas.py): every seen chunk, sent only while the map is open."""

import json
import unittest

from dimensional_sim.world.atlas import atlas
from dimensional_sim.world.autopilot import Expedition
from dimensional_sim.world.catalog import LOCATIONS
from dimensional_sim.world.models import ChunkKey, chunk_ident
from dimensional_sim.world.runtime import Exploration
from dimensional_sim.world.seeds import canonical_json
from dimensional_sim.world.session import BrowserSession, validate_input
from dimensional_sim.world.web import new_world
from test_world_worked_ground import camped, work

BASE = {"move": None, "attack": False, "paused": False, "known": []}


def played(ms=600_000, seed=482910):
    e = Expedition(Exploration(new_world(seed), "forest"))
    e.advance(ms)
    return e


class AtlasTests(unittest.TestCase):
    def test_every_seen_chunk_and_only_those(self):
        e = played()
        view = atlas(e)
        seen = {(k.x, k.y) for k, _ in e.game.world.discovered(e.dimension)
                if e.game.visibility_rows(k) is not None}
        self.assertEqual({(c["x"], c["y"]) for c in view["chunks"]}, seen)
        self.assertIn(tuple(view["player"]), seen)
        for c in view["chunks"]:
            self.assertIn(c["status"], ("generated", "visited"))
            self.assertTrue(c["loc"] is None or c["loc"] in LOCATIONS)
        self.assertEqual(set(view["locations"]), set(LOCATIONS))
        json.loads(canonical_json(view))

    def test_the_atlas_is_read_only(self):
        e = played(120_000)
        before = canonical_json(e.to_dict())
        atlas(e)
        self.assertEqual(canonical_json(e.to_dict()), before)

    def test_streamed_but_unexplored_chunks_stay_hidden(self):
        e = played(5_000)
        far = ChunkKey(e.dimension, 8, 0)
        e.game.world.get(far)
        self.assertIsNone(e.game.visibility_rows(far))
        self.assertNotIn(chunk_ident(far), {c["id"] for c in atlas(e)["chunks"]})

    def test_a_landmark_in_a_partly_seen_chunk_stays_under_fog(self):
        e = played(5_000)
        village = ChunkKey(e.dimension, 8, 0)
        site = e.game.world.site_for(village)
        self.assertIsNotNone(site)
        e.game.world.get(village)
        height = e._dims()[1]
        e.game.seen[village] = [0] * height
        e.game.seen[village][0] = 1
        row = next(c for c in atlas(e)["chunks"] if c["id"] == chunk_ident(village))
        self.assertIsNone(row["site"])
        e.game.seen[village][site.y] |= 1 << site.x
        row = next(c for c in atlas(e)["chunks"] if c["id"] == chunk_ident(village))
        self.assertEqual(row["site"], "village")

    def test_it_shows_the_camp_area_and_worked_ground(self):
        e = camped()
        work(e, 2)
        view = atlas(e)
        here = [e.game.player.chunk.x, e.game.player.chunk.y]
        self.assertIn(here, view["camp"]["cells"])
        row = next(c for c in view["chunks"] if [c["x"], c["y"]] == here)
        self.assertEqual(row["ground"], 2)
        self.assertTrue(row["den"])

    def test_session_sends_the_atlas_only_on_request(self):
        e = played(5_000)
        s = BrowserSession(e.game, e)
        with self.assertRaises(ValueError):
            validate_input({**BASE, "atlas": 1})
        self.assertNotIn("atlas", s.input(dict(BASE), 0.0))
        self.assertIn("chunks", s.input({**BASE, "atlas": True}, 0.1)["atlas"])

    def test_tiles_are_the_minimaps_and_come_once_per_viewer(self):
        e = played(5_000)
        s = BrowserSession(e.game, e)
        first = s.input({**BASE, "atlas": "reset"}, 0.0)
        here = next(c for c in first["chunks"] if c["id"] == chunk_ident(e.game.player.chunk))
        row = next(c for c in first["atlas"]["chunks"] if c["id"] == here["id"])
        self.assertEqual(row["tiles"], here["tiles"], "the same glyph rows the minimap paints")
        self.assertEqual(row["fog"], e.game.visibility_rows(e.game.player.chunk))
        again = s.input({**BASE, "atlas": True}, 0.1)["atlas"]["chunks"]
        self.assertTrue(all(c["tiles"] is None for c in again), "tiles never change: sent once")
        self.assertTrue(all(c["fog"] is not None or c["status"] == "generated" for c in again))
        reset = s.input({**BASE, "atlas": "reset"}, 0.2)["atlas"]["chunks"]
        self.assertIsNotNone(next(c for c in reset if c["id"] == here["id"])["tiles"], "a fresh page gets them again")

    def test_far_chunks_are_painted_too_without_loading_them(self):
        e = played(600_000)
        resident = e.game.world.resident_count
        view = atlas(e)
        far = [c for c in view["chunks"] if e.game.world.peek(ChunkKey(e.dimension, c["x"], c["y"])) is None]
        self.assertTrue(far and any(c["tiles"] for c in far), "seen chunks away from the avatar have tiles")
        self.assertEqual(e.game.world.resident_count, resident, "the map never loads chunks")


if __name__ == "__main__":
    unittest.main()
