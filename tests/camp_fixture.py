"""Put an expedition's avatar in the anchor camp (where crafting and building happen)."""
from dimensional_sim.world.catalog import BUILDINGS
from dimensional_sim.world.models import ChunkKey

STATION = next(b for b in BUILDINGS.values() if b.function == "crafting").id
CHEST = next(b for b in BUILDINGS.values() if b.function == "storage").id


def to_camp(e, *, station=True):
    w, h = e._dims()
    gx, gy = e.anchor
    key = ChunkKey(e.dimension, gx // w, gy // h)
    if e.game.player.chunk != key:
        e.game._enter(key)
    e.game.player.chunk = key
    e.game.player.x, e.game.player.y = gx % w, gy % h
    e.game._reveal()
    if station:
        e.buildings.add(STATION)
    assert e.at_camp()
    return e


def away(e, tiles=8):
    """Stand the avatar outside the camp (position only: for planning and need checks)."""
    w, _ = e._dims()
    gx, _ = e.anchor
    e.game.player.x = min(w - 1, gx % w + tiles) if gx % w + tiles < w else gx % w - tiles
    assert not e.at_camp()
    return e
