"""The full map (atlas): every chunk seen so far as one cell, for planning where to camp.

WHAT: a read-only projection of an Expedition, sent only when the client asks for it
(session input `atlas: true`, while the map is open), so ordinary polling stays small.
Per seen chunk: its tiles and fog, painted exactly as the minimap paints them (a less detailed copy
of the world, only what was seen, anywhere - not just around the avatar), its kind of place (region location), a landmark if one stands there, its ring
and how worked its ground is this life (autopilot/explored.py). Per location: mastery grade and
whether a camp can be made there. Plus the avatar, the anchor camp, this life's fire and the
camp's area.
NEVER: change state, roll anything, or show chunks that were never seen.
TESTS: tests/test_world_atlas.py.
"""
from .catalog import LOCATION_OF_SITE, LOCATIONS, REGION_CELL
from .models import ChunkKey, chunk_ident as ident

TILE_BUDGET = 24   # chunks generated afresh per request (the rest arrive on later polls)


def tile_rows(asset):
    """A chunk's glyph rows, objects over ground: what the minimap paints (session._chunk_view too)."""
    return ["".join((obj or env).glyph for obj, env in zip(orow, erow))
            for orow, erow in zip(asset.objects, asset.environment)]


def _tiles(e, key, budget):
    """Glyph rows of chunk `key` (cached on the expedition, never saved), or None while waiting
    for this request's generation budget (a one-item list)."""
    cache = e.__dict__.setdefault("_atlas_tiles", {})
    rows = cache.get(key)
    if rows is None:
        fresh = e.game.world.look(key) is None
        chunk = e.game.world.look(key, generate=budget[0] > 0)
        if chunk is None:
            return None
        budget[0] -= fresh
        if len(cache) >= 4096:
            cache.clear()
        rows = cache[key] = tile_rows(chunk.asset)
    return rows


def atlas(e, sent=frozenset()):
    """`sent`: chunk ids whose tiles this viewer already holds (tiles never change; fog is always sent)."""
    w, h = e._dims()
    dimension = e.dimension
    chunks = []
    budget = [TILE_BUDGET]
    for key, status in sorted(e.game.world.discovered(dimension),   # nearest first: fresh sketches go there
                              key=lambda ks: max(abs(ks[0].x - e.game.player.chunk.x), abs(ks[0].y - e.game.player.chunk.y))):
        fog = e.game.visibility_rows(key)
        if fog is None:
            continue   # streaming may generate a chunk before any of its tiles are explored
        site = e.game.world.site_for(key)
        if site is not None and fog[site.y][site.x] != "1":
            site = None   # a partly seen chunk must not reveal a landmark still under fog
        ground = e.ground_view(key)
        chunks.append({"id": ident(key), "x": key.x, "y": key.y, "status": status, "loc": e.location_of_chunk(key),
                       "site": LOCATION_OF_SITE.get(site.site.id) if site is not None else None,
                       "site_name": site.site.name if site is not None else None,
                       "ring": e.ring(key), "ground": ground["rounds"] if ground else 0,
                       "den": bool(ground and ground["den"]), "fog": fog,
                       "tiles": None if ident(key) in sent else _tiles(e, key, budget)})
    places = e.places_view()
    locations = {row["id"]: {k: row[k] for k in ("name", "kind", "text", "grade", "grade_name", "can_camp",
                                                  "focus", "camped", "done", "next")}
                 for row in places["places"]}
    camp = None
    if e.camping():
        seen = {(c["x"], c["y"]) for c in chunks}
        cells = []
        c = e.camp
        if LOCATIONS[c["location"]].kind == "site":
            span = [(c["cx"] + dx, c["cy"] + dy) for dy in (-1, 0, 1) for dx in (-1, 0, 1)]
        else:
            span = [(c["cx"] * REGION_CELL + dx, c["cy"] * REGION_CELL + dy)
                    for dy in range(REGION_CELL) for dx in range(REGION_CELL)]
        cells = [list(p) for p in span if p in seen and e.in_camp_area(ChunkKey(dimension, *p))]
        camp = {"location": c["location"], "name": LOCATIONS[c["location"]].name, "cells": cells,
                "rounds": e.camp_rounds()}
    player = e.game.player.chunk
    fire = e.campfire
    return {"chunks": chunks, "locations": locations, "chunk_width": w, "chunk_height": h,
            "player": [player.x, player.y], "player_at": list(e._player()),   # chunk, and global tile
            "anchor": [e.anchor[0] // w, e.anchor[1] // h], "anchor_at": list(e.anchor),
            "fire": None if fire is None or fire["dimension"] != dimension
            else {"x": fire["x"] // w, "y": fire["y"] // h, "gx": fire["x"], "gy": fire["y"], "bed": bool(fire.get("bed"))},
            "camp": camp, "frontier": e.frontier()}
