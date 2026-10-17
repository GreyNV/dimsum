"""Per-life resource measurements (sticks, food, campfires, station timing) for balancing.

Usage: PYTHONPATH=src python tools/measure_lives.py <seed> <minutes> <out.json>
Summarize with tools/measure_report.py <prefix>... (files named <dir>/<prefix>_<seed>.json).
"""
import json, sys
from dimensional_sim.world.autopilot import Expedition
from dimensional_sim.world.progression import attribute_report
from dimensional_sim.world.runtime import Exploration
from dimensional_sim.world.simulate import anchor_policy
from dimensional_sim.world.web import new_world
seed, minutes, out = int(sys.argv[1]), int(sys.argv[2]), sys.argv[3]
e = Expedition(Exploration(new_world(seed), "forest"))
lives = []; start = 0; items0 = {}; acts0 = {}; station_at = None; recorded = 0
while e.total_ms < minutes * 60_000:
    e.advance(1000)
    if station_at is None and "crafting_station" in e.buildings and "crafting_station" not in e.bound_buildings and e.anchor_ms is None:
        station_at = (e.total_ms - start) / 60000
    if e.anchor_ms is not None and recorded != e.life:
        recorded = e.life
        items = {k: v - items0.get(k, 0) for k, v in e.journal["items"].items() if v - items0.get(k, 0)}
        acts = {k: v - acts0.get(k, 0) for k, v in e.journal["actions"].items() if v - acts0.get(k, 0)}
        lives.append({"life": e.life, "minutes": round((e.total_ms - start) / 60000, 2), "cause": e.cause,
                      "depth": e.depth, "items": items, "actions": acts, "station_min": station_at,
                      "bound": sorted(e.bound_buildings), "chunks": e.stats["chunks"],
                      "dim": {k: r["dim_level"] for k, r in attribute_report(e.regular, e.dimensional).items()},
                      "unlocked": sorted(e.unlocked), "recipes": sorted(e.recipes)})
        items0, acts0 = dict(e.journal["items"]), dict(e.journal["actions"]); station_at = None
        anchor_policy(e, "spend")
        start = e.total_ms
json.dump({"seed": seed, "lives": lives, "ash": e.ash, "bound": sorted(e.bound_buildings)}, open(out, "w"))
