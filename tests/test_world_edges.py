"""The edge of a land (generator v7): a ragged explorable area closed by thicket, fallen trees and
broken bridges - never a wall - with every reachable chunk connected to the anchor."""
import json
import unittest
from collections import deque
from dataclasses import replace
from unittest.mock import patch

from dimensional_sim.world.catalog import LANDS
from dimensional_sim.world.edges import chunk_open, sealed_sides
from dimensional_sim.world.models import ChunkKey
from dimensional_sim.world.open_terrain import BROKEN_BRIDGE, DEADFALL
from dimensional_sim.world.repository import WorldRepository
from dimensional_sim.world.seeds import canonical_json
from dimensional_sim.world.web import new_world

LAND = LANDS["forest"]
OPPOSITE = {"north": (0, -1), "south": (0, 1), "east": (1, 0), "west": (-1, 0)}


def reachable(world, seed, span):
    """Open chunks the anchor's chunk reaches by stepping across matching open boundary cells."""
    opens = {(x, y) for x in range(-span, span + 1) for y in range(-span, span + 1)
             if chunk_open(seed, ChunkKey("forest", x, y))}
    seen, queue = {(0, 0)}, deque([(0, 0)])
    while queue:
        x, y = queue.popleft()
        a = world.get(ChunkKey("forest", x, y)).asset
        for e in a.exits:
            dx, dy = OPPOSITE[e.direction]
            n = (x + dx, y + dy)
            if n in seen or n not in opens:
                continue
            b = world.get(ChunkKey("forest", *n)).asset
            px = e.x if dx == 0 else (0 if dx == 1 else a.width - 1)
            py = e.y if dy == 0 else (0 if dy == 1 else a.height - 1)
            if not b.collision[py][px]:
                seen.add(n)
                queue.append(n)
    return opens, seen


class EdgeTests(unittest.TestCase):
    def test_the_area_is_ragged_and_bounded(self):
        seed = 482910
        ring = lambda x, y: max(abs(x), abs(y))
        opens = {(x, y) for x in range(-9, 10) for y in range(-9, 10) if chunk_open(seed, ChunkKey("forest", x, y))}
        self.assertTrue(all(ring(x, y) <= LAND.lobe_ring for x, y in opens))
        self.assertTrue(all((x, y) in opens for x in range(-LAND.edge_ring, LAND.edge_ring + 1)
                            for y in range(-LAND.edge_ring, LAND.edge_ring + 1)))
        lobes = [c for c in opens if ring(*c) > LAND.edge_ring]
        self.assertTrue(lobes, "some of the next ring can be reached: the edge is not a square")
        self.assertLess(len(lobes), 8 * LAND.lobe_ring, "and not all of it")

    def test_sealed_sides_have_no_exit_and_every_open_chunk_is_reachable(self):
        for seed in (482910, 1, 3):
            world = new_world(seed)
            opens, seen = reachable(world, seed, LAND.lobe_ring + 1)
            self.assertEqual(opens, seen, f"seed {seed}: an open chunk cut off")
            for x, y in opens:
                key = ChunkKey("forest", x, y)
                directions = {e.direction for e in world.get(key).asset.exits}
                self.assertFalse(set(sealed_sides(seed, key)) & directions, key)

    def test_roads_end_in_fallen_trees_or_a_broken_bridge_at_the_edge(self):
        found = set()
        for seed in (482910, 3):
            world = new_world(seed)
            for x in range(-LAND.lobe_ring, LAND.lobe_ring + 1):
                for y in range(-LAND.lobe_ring, LAND.lobe_ring + 1):
                    key = ChunkKey("forest", x, y)
                    if not sealed_sides(seed, key):
                        continue
                    found |= {cell.glyph for row in world.get(key).asset.objects for cell in row
                              if cell is not None and cell.glyph in (DEADFALL, BROKEN_BRIDGE)}
        self.assertEqual(found, {DEADFALL, BROKEN_BRIDGE})

    def test_the_land_catalog_is_pinned_in_world_saves(self):
        world = new_world(482910)
        saved = json.loads(canonical_json(world.to_dict()))
        self.assertEqual(saved["land_catalog"][0]["edge_ring"], LAND.edge_ring)
        with patch.dict(LANDS, {"forest": replace(LAND, edge_ring=2)}):
            restored = WorldRepository.from_dict(saved)
            self.assertTrue(restored.chunk_open(ChunkKey("forest", LAND.edge_ring, 0)),
                            "a catalog edit never moves an existing world's edge")


if __name__ == "__main__":
    unittest.main()
