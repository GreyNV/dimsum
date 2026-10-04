"""Open topology and local adapter regressions; no browser/AI required."""
import copy
from dataclasses import replace
from http.client import HTTPConnection
import json
import re
import os
import subprocess
import sys
import threading
import unittest

from dimensional_sim.world.assets import AssetRegistry
from dimensional_sim.world.browser_server import BrowserSession, make_server, snapshot
from dimensional_sim.world.models import (ChunkKey, DimensionSpec, asset_from_dict,
    asset_to_dict, chunk_to_dict, validate_asset, DELTAS)
from dimensional_sim.world.open_terrain import open_assets
from dimensional_sim.world.repository import WorldRepository
from dimensional_sim.world.runtime import Exploration, InputCommand, Target
from dimensional_sim.world.seeds import content_digest


def game(seed=482910):
    return Exploration(WorldRepository(seed, (DimensionSpec("forest", danger=0),), open_assets()))


def crossing(g, direction):
    a = g.current_chunk().asset
    dx, dy = DELTAS[direction]
    key = ChunkKey("forest", g.player.chunk.x + dx, g.player.chunk.y + dy)
    dest = g.world.get(key).asset
    for e in a.exits:
        x, y = (e.x + dx) % a.width, (e.y + dy) % a.height
        midpoint = e.x == a.width // 2 if direction in ("north", "south") else e.y == a.height // 2
        if e.direction == direction and not midpoint and not dest.collision[y][x]:
            return e, key, x, y
    raise AssertionError("expected a walkable non-midpoint crossing")


class OpenWorldTests(unittest.TestCase):
    def test_legacy_asset_and_chunk_canonical_bytes_unchanged(self):
        # Recorded from the built 0.6.0 wheel before this slice.
        world = WorldRepository(482910)
        self.assertEqual(world.catalog_digest, "95c179d257ff6051703df2d430b910f7cb449a95ebedfb133ddc4e26d567895e")
        self.assertEqual(content_digest(chunk_to_dict(world.get(ChunkKey("forest", 4, -7)))),
                         "73b71e69f1e68b53c17b993812f70b3f6bf8d9babdf1f75cae7b080e477db536")
        self.assertTrue(all("topology" not in asset_to_dict(a) for a in world.catalog))

    def test_schema2_roundtrip_registration_and_boundary_validation(self):
        asset = open_assets()[0]
        self.assertEqual(asset_from_dict(asset_to_dict(asset)), asset)
        registry = AssetRegistry()
        registry.register(asset)
        for bad in (replace(asset, exits=asset.exits[:-1]), replace(asset, topology="future"),
                    replace(asset, exits=asset.exits + asset.exits[:1])):
            with self.assertRaises(ValueError): registry.register(bad)
        raw = asset_to_dict(asset)
        for changes in ({"schema_version": 1}, {"topology": "room"}, {"schema_version": 3}):
            with self.assertRaises(ValueError): asset_from_dict({**raw, **changes})

    def test_fifty_chunks_valid_reachable_and_order_independent(self):
        g = game()
        keys = [ChunkKey("forest", x, y) for x in range(-5, 5) for y in range(-2, 3)]
        first = {}
        for key in keys:
            chunk = g.world.get(key)
            validate_asset(chunk.asset)
            first[key] = content_digest(chunk_to_dict(chunk))
            self.assertGreater(len(chunk.asset.exits), 4)
            self.assertLessEqual(g.world.resident_count, 9)
        loaded = WorldRepository.from_dict(g.world.to_dict())
        for key in reversed(keys):
            self.assertEqual(first[key], content_digest(chunk_to_dict(loaded.get(key))))
        other = game(7)
        self.assertNotEqual(first[keys[0]], content_digest(chunk_to_dict(other.world.get(keys[0]))))

    def test_open_generation_hash_salt_independent(self):
        code = ("from dimensional_sim.world.open_terrain import open_assets; "
                "from dimensional_sim.world.repository import WorldRepository; "
                "from dimensional_sim.world.models import ChunkKey,chunk_to_dict; "
                "from dimensional_sim.world.seeds import content_digest; "
                "print(content_digest(chunk_to_dict(WorldRepository(482910,assets=open_assets()).get(ChunkKey('forest',4,-7)))))")
        outputs = [subprocess.check_output([sys.executable, "-B", "-c", code], text=True,
            env={**os.environ, "PYTHONPATH": "src", "PYTHONHASHSEED": salt}) for salt in ("1", "93")]
        self.assertEqual(*outputs)

    def test_non_midpoint_crossings_all_directions_and_collision(self):
        for direction in DELTAS:
            g = game()
            e, key, x, y = crossing(g, direction)
            g.player.x, g.player.y = e.x, e.y
            g.advance(120, InputCommand(direction))
            self.assertEqual((g.player.chunk, g.player.x, g.player.y), (key, x, y))
            a = g.current_chunk().asset
            tested = False
            for yy in range(1, a.height - 1):
                for xx in range(1, a.width - 1):
                    if a.collision[yy][xx]: continue
                    for move, (dx, dy) in DELTAS.items():
                        if a.collision[yy + dy][xx + dx]:
                            g.player.x, g.player.y = xx, yy
                            g.advance(120, InputCommand(move))
                            self.assertEqual((g.player.x, g.player.y), (xx, yy))
                            tested = True
                            break
                    if tested: break
                if tested: break
            self.assertTrue(tested)

    def test_cross_boundary_hit_timing_and_mid_attack_save(self):
        g = game()
        e, key, x, y = crossing(g, "east")
        g.player.x, g.player.y, g.player.facing = e.x, e.y, "east"
        g.world.visit(key)
        g.initialized_chunks.add(key)
        g.targets["neighbor"] = Target("neighbor", key, x, y)
        g.advance(119, InputCommand(attack=True))
        self.assertEqual(g.targets["neighbor"].hp, 3)
        g.advance(1, InputCommand(attack=True))
        self.assertEqual(g.targets["neighbor"].hp, 2)
        loaded = Exploration.from_dict(g.to_dict())
        for current in (g, loaded): current.advance(500, InputCommand(attack=True))
        self.assertEqual(g.to_dict(), loaded.to_dict())
        self.assertEqual(g.targets["neighbor"].hp, 2)


class BrowserAdapterTests(unittest.TestCase):
    def test_frame_projection_is_pure_and_transmits_only_missing_chunks(self):
        g = game()
        before, count = g.to_dict(), g.world.generation_count
        first = snapshot(g)
        self.assertEqual(len(first["chunks"]), 9)
        self.assertEqual(snapshot(g, first["resident"])["chunks"], [])
        self.assertEqual({m["status"] for m in first["minimap"]}, {"unknown", "generated", "visited"})
        for _ in range(10): snapshot(g)
        self.assertEqual(g.world.generation_count, count)
        self.assertEqual(g.to_dict(), before)
        self.assertEqual(first["player"]["x"], g.player.x)
        self.assertTrue(all(c["seed"] < 2**32 for c in first["chunks"]))

    def test_input_validation_atomic_lease_expiry_and_pause(self):
        session = BrowserSession(game())
        good = {"move": "east", "attack": False, "paused": False, "known": []}
        before = session.game.to_dict()
        for change in ({"move": "diagonal"}, {"paused": 1}, {"known": ["x"] * 30}, {"dt": 100000}):
            with self.assertRaises(ValueError): session.input({**good, **change}, 0)
        self.assertEqual(before, session.game.to_dict())
        session.input(good, 0)
        for i in range(6): session.step(i * .02)
        stopped = (session.game.player.chunk, session.game.player.x, session.game.player.y)
        for i in range(20): session.step(1 + i * .02)
        self.assertEqual((session.game.player.chunk, session.game.player.x, session.game.player.y), stopped)
        session.input({**good, "paused": True}, 3)
        clock = session.game.elapsed_ms
        session.step(3.02)
        self.assertEqual(session.game.elapsed_ms, clock)

    def test_input_attack_uses_fixed_ticks_not_request_or_render_frequency(self):
        a, b = BrowserSession(game()), BrowserSession(game())
        command = {"move": None, "attack": True, "paused": False, "known": []}
        for session in (a, b): session.input(command, 0)
        for i in range(20):
            a.step(i * .02)
            b.step(i * .02)
            for _ in range(8): b.state()
        self.assertEqual(a.game.to_dict(), b.game.to_dict())

    def test_http_serves_game_rejects_foreign_origin_and_malformed_input(self):
        session = BrowserSession(game())
        server = make_server(session, 0)
        worker = threading.Thread(target=server.serve_forever, daemon=True)
        worker.start()
        try:
            connection = HTTPConnection("127.0.0.1", server.server_port, timeout=3)
            connection.request("GET", "/api/state")
            response = connection.getresponse()
            self.assertEqual(response.status, 200)
            self.assertEqual(len(json.loads(response.read())["chunks"]), 9)
            for body, headers, status in (
                ("{}", {"Content-Type": "application/json"}, 400),
                ("{}", {"Content-Type": "application/json", "Origin": "https://example.com"}, 403),
                ("{}", {"Content-Type": "text/plain"}, 415)):
                connection.request("POST", "/api/input", body, headers)
                response = connection.getresponse()
                self.assertEqual(response.status, status)
                response.read()
            # Every ES module imported by a served module must itself be served.
            pending, seen = ["/app.js"], set()
            while pending:
                path = pending.pop()
                if path in seen:
                    continue
                seen.add(path)
                connection.request("GET", path)
                response = connection.getresponse()
                self.assertEqual(response.status, 200, path)
                source = response.read().decode()
                pending += ["/" + name for name in re.findall(r"from '\./([\w.-]+\.js)'", source)]
            self.assertIn("/actors.js", seen)
            connection.request("GET", "/../../pyproject.toml")
            response = connection.getresponse()
            self.assertEqual(response.status, 404)
            response.read()
            connection.close()
        finally:
            server.shutdown()
            server.server_close()
            worker.join()
