"""The round body (world/body.py): sub-tile positions over the cell rules, arcs round trunks,
leaning on walls, settling to the centre, saved with the exploration."""

import json
import unittest

from dimensional_sim.world.body import BODY_RADIUS, LEAN, SUB, body_target, ease, push_out
from dimensional_sim.world.runtime import Exploration, InputCommand
from dimensional_sim.world.seeds import canonical_json
from dimensional_sim.world.web import new_world


def exploration():
    return Exploration(new_world(482910), "forest")


def gx(game):
    return (game.player.chunk.x * game.current_chunk().asset.width + game.player.x) * SUB + game.player.ox


def clear_of(ox, oy, walls):
    half = SUB // 2
    for dx, dy in walls:
        nx = min(max(ox, dx * SUB - half), dx * SUB + half)
        ny = min(max(oy, dy * SUB - half), dy * SUB + half)
        if (ox - nx) ** 2 + (oy - ny) ** 2 < BODY_RADIUS ** 2:
            return False
    return True


class BodyMathTests(unittest.TestCase):
    def test_passing_a_trunk_corner_the_body_swings_round_it(self):
        walls = {(-1, 0)}   # the trunk beside the cell just entered, where the straight line would cut its corner
        ox, oy, carry, path = -SUB, SUB, 0, []
        for _ in range(60):
            ox, oy, carry = ease(ox, oy, carry, 8, (0, 0), walls)
            path.append((ox, oy))
            self.assertTrue(clear_of(ox, oy, walls), (ox, oy))
        self.assertEqual(path[-1], (0, 0), "it gets there")
        straight = [(-SUB + k, SUB - k) for k in range(SUB + 1)]
        self.assertNotEqual(path[:SUB], straight[1:SUB + 1], "not the straight cut through the corner")

    def test_against_a_wall_the_body_leans_on_its_surface(self):
        self.assertEqual(body_target((1, 0), {(1, 0)}), (LEAN, 0))
        self.assertEqual(body_target(None, {(1, 0)}), (0, 0))
        self.assertEqual(push_out(8, 0, {(1, 0)}), (SUB // 2 - BODY_RADIUS, 0))

    def test_easing_is_partition_free(self):
        a = ease(-SUB, SUB, 0, 200, (0, 0), {(-1, 0)})
        b = (-SUB, SUB, 0)
        for _ in range(25):
            b = ease(*b, 8, (0, 0), {(-1, 0)})
        self.assertEqual(a[:2], b[:2])


class BodyInGameTests(unittest.TestCase):
    def test_walking_the_body_travels_continuously_and_settles_at_the_centre(self):
        game = exploration()
        start = gx(game)
        positions = []
        for _ in range(30):
            game.advance(20, InputCommand("east"))
            positions.append(gx(game))
        moved = [b - a for a, b in zip(positions, positions[1:])]
        self.assertTrue(all(0 <= d <= 6 for d in moved), moved)   # no jumps of a whole tile
        self.assertGreater(positions[-1], start)
        game.advance(400, InputCommand())
        self.assertEqual((game.player.ox, game.player.oy), (0, 0), "standing still it settles")

    def test_walking_into_a_wall_leans_on_it(self):
        game = exploration()
        from dimensional_sim.world.models import ChunkKey
        found = None
        for cx in range(1, 6):
            if found:
                break
            key = ChunkKey("forest", cx, 0)
            asset = game.world.get(key).asset
            game._enter(key)
            game.player.chunk = key
            for y in range(1, asset.height - 1):
                for x in range(1, asset.width - 1):
                    if asset.collision[y][x]:
                        continue
                    for direction in ("north", "east", "south", "west"):
                        if game._step_target(key, x, y, direction) is None \
                                and game._corner_assist((key, x, y), direction) is None:
                            found = found or (x, y, direction)
        x, y, direction = found
        game.player.x, game.player.y = x, y
        game.player.ox = game.player.oy = 0
        for _ in range(20):
            game.advance(30, InputCommand(direction))
        self.assertEqual(game.player.lean, direction)
        off = {"north": (0, -LEAN), "south": (0, LEAN), "east": (LEAN, 0), "west": (-LEAN, 0)}[direction]
        self.assertEqual((game.player.ox, game.player.oy), off)

    def test_the_body_is_saved_and_an_old_save_stands_at_the_centre(self):
        game = exploration()
        game.advance(0, InputCommand("east"))
        game.advance(40, InputCommand("east"))
        data = json.loads(canonical_json(game.to_dict()))
        loaded = Exploration.from_dict(data)
        self.assertEqual((loaded.player.ox, loaded.player.oy, loaded.player.body_ms),
                         (game.player.ox, game.player.oy, game.player.body_ms))
        for name in ("ox", "oy", "body_ms", "lean", "tx", "ty"):
            data["player"].pop(name)
        old = Exploration.from_dict(data)
        self.assertEqual((old.player.ox, old.player.oy), (0, 0))


if __name__ == "__main__":
    unittest.main()


class BodyInPlayTests(unittest.TestCase):
    def test_in_a_real_run_the_body_never_overlaps_a_wall(self):
        from dimensional_sim.world.autopilot import Expedition
        e = Expedition(Exploration(new_world(5), "forest"))
        for _ in range(1500):
            e.advance(37)
            p = e.game.player
            if e.anchor_ms is None:
                self.assertTrue(clear_of(p.ox, p.oy, e.game._walls()), (p.ox, p.oy))
