"""The edge of a land (generator v7): which chunks can be reached, and which sides of a reachable
chunk are closed by the land itself.

A chunk is open when its ring (Chebyshev chunk distance from the anchor chunk) is at most the
land's edge ring, or within its lobe ring where the chunk's region cell (3x3 chunks) rolls under
the lobe percent and it touches an inner chunk - so the outline is ragged, never a square. An open chunk seals every side that
faces a closed chunk: open_terrain grows a band of thicket there, lays fallen trees across a road
and leaves a bridge broken over a river. Pure: world seed, dimension and coordinates only.
"""
from .catalog import LANDS, REGION_CELL
from .models import ChunkKey
from .seeds import derive_seed

EDGE_VERSION = "land-edge-v1"
SIDES = (("north", 0, -1), ("south", 0, 1), ("west", -1, 0), ("east", 1, 0))


def chunk_open(world_seed, key, lands=None):
    """Whether chunk `key` lies inside its land's explorable area (`lands`: a world's pinned
    land catalog; the current catalog by default)."""
    land = (LANDS if lands is None else lands).get(key.dimension)
    if land is None:
        return True
    ring = max(abs(key.x), abs(key.y))
    if ring <= land.edge_ring:
        return True
    if ring > land.lobe_ring:
        return False
    if all(max(abs(key.x + dx), abs(key.y + dy)) >= ring for _, dx, dy in SIDES):
        return False   # a corner touches no inner chunk: it could only be an island
    cell = (key.x // REGION_CELL, key.y // REGION_CELL)
    return derive_seed(world_seed, EDGE_VERSION, key.dimension, *cell) % 100 < land.lobe_percent


def sealed_sides(world_seed, key, lands=None):
    """Sides of an open chunk that face a closed one (none for a closed chunk itself)."""
    if not chunk_open(world_seed, key, lands):
        return ()
    return tuple(side for side, dx, dy in SIDES
                 if not chunk_open(world_seed, ChunkKey(key.dimension, key.x + dx, key.y + dy), lands))
