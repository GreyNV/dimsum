"""Seeded multi-run simulation and chunk inspection for design and balancing.

WHAT: runs whole expeditions headlessly with a scripted anchor policy and reports
per-life metrics; inspects one chunk's region, spots and action bucket.
WHY: balance by measurement (docs/design/BALANCING.md), and answer "why did / didn't
this appear" without reading code.
USE:
  python -m dimensional_sim.world.cli simulate --seeds 1-10 --minutes 30 --policy spend
  python -m dimensional_sim.world.cli inspect --seed 482910 --x 1 --y 0 --unlock climbing
  python -m dimensional_sim.world.cli regions --seed 482910 --radius 2
Policies (anchor behaviour; the auto-pilot plays the lives):
  spend - offer every stack, buy the cheapest available unlock, then a boon, then
          mastery of the first food action with ash; crafting on.
  hoard - same anchor buying, but never crafts (keeps materials for offering).
  idle  - never acts at the anchor (an absent player): everything burns to ash.
"""
from statistics import mean

from .actions import Context, describe_bucket, explain
from .autopilot import Expedition
from .catalog import BY_ID, ITEMS
from .models import ChunkKey
from .runtime import Exploration
from .web import new_world

POLICIES = ("spend", "hoard", "idle")
FOOD_FIRST = ("bramble_berries", "bramble_boar", "mushroom_ring", "gnarled_tree")


def anchor_policy(e, policy):
    """Spend at the anchor according to `policy`, then begin the next life."""
    if policy == "idle":
        return
    for item in sorted(e.inventory):
        e.anchor_action({"type": "trade", "item": item})
    while True:
        rows = [r for r in e.anchor_offers() if r["available"]]
        unlocks = sorted((r for r in rows if r["kind"] == "unlock"), key=lambda r: (r["cost"], r["id"]))
        boons = [r for r in rows if r["kind"] == "boon"]
        mastery = sorted((r for r in rows if r["kind"] == "mastery"),
                         key=lambda r: (FOOD_FIRST.index(r["id"]) if r["id"] in FOOD_FIRST else 9, r["id"]))
        choice = (unlocks or boons or mastery or [None])[0]
        if choice is None:
            break
        e.anchor_action({"type": choice["kind"], "id": choice["id"]})
    e.anchor_action({"type": "begin_life"})


def run(seed, minutes=30, policy="spend", step_ms=1000):
    """Play one expedition; returns {"lives": [...], "final": {...}}."""
    if policy not in POLICIES:
        raise ValueError(f"policy must be one of {POLICIES}")
    e = Expedition(Exploration(new_world(seed), "forest"))
    e.crafting_enabled = policy != "hoard"
    lives, start, total, recorded = [], 0, minutes * 60_000, 0
    lead_log, staff_before = set(), 0
    while e.total_ms < total:
        e.advance(step_ms)
        lead_log.update((row["id"], row["action"], row["status"]) for row in e.lead_history)
        if e.anchor_ms is not None and recorded != e.life:
            recorded = e.life
            report = e.report
            world = e.game.world
            visited = {world.region_for(ChunkKey(r["dimension"], r["x"], r["y"])).id
                       for r in world.to_dict()["discovery"] if r["status"] == "visited"}
            leads = {}
            for row in lead_log:
                leads[row[1] + ":" + row[2]] = leads.get(row[1] + ":" + row[2], 0) + 1
            lives.append({"life": e.life, "minutes": round((e.total_ms - start) / 60000, 2),
                          "cause": e.cause or "exhaustion", "depth": e.depth, **e.stats,
                          "regions_visited": len(visited), "leads": leads,
                          "staff": e.journal["actions"].get("craft_staff", 0) > staff_before,
                          "carried_dust": sum(ITEMS[i].dust * n for i, n in e.inventory.items()),
                          "title": report["title"]})
            lead_log, staff_before = set(), e.journal["actions"].get("craft_staff", 0)
            anchor_policy(e, policy)
            start = e.total_ms if policy != "idle" else e.total_ms + e.anchor_ms
    return {"seed": seed, "policy": policy, "lives": lives,
            "final": {"life": e.life, "dust": e.dust, "ash": e.ash, "blessing": e.blessing,
                      "unlocked": sorted(e.unlocked), "mastery": dict(e.mastery),
                      "dimensional_xp": sum(e.dimensional.values())}}


def summarize(results):
    lives = [life for r in results for life in r["lives"]]
    if not lives:
        return {"runs": len(results), "lives": 0}
    causes = {}
    for life in lives:
        causes[life["cause"]] = causes.get(life["cause"], 0) + 1
    return {"runs": len(results), "lives": len(lives),
            "life_minutes_mean": round(mean(l["minutes"] for l in lives), 2),
            "life_minutes_min": min(l["minutes"] for l in lives),
            "life_minutes_max": max(l["minutes"] for l in lives),
            "causes": causes,
            "per_life_mean": {k: round(mean(l[k] for l in lives), 2) for k in (
                "depth", "chunks", "food_spots", "enemy_spots", "pity", "rejected", "completed",
                "eaten", "crafted", "fights", "prayers", "carried_dust", "regions_visited")},
            "lives_with_staff": sum(1 for l in lives if l["staff"]),
            "leads": {k: sum(l["leads"].get(k, 0) for l in lives) for k in sorted(
                {k for l in lives for k in l["leads"]})},
            "boar_deaths_with_staff": sum(1 for l in lives if l["staff"] and l["cause"] == "boar"),
            "boar_deaths_without_staff": sum(1 for l in lives if not l["staff"] and l["cause"] == "boar"),
            "lives_without_food_spot": sum(1 for l in lives if l["food_spots"] == 0),
            "lives_without_enemy": sum(1 for l in lives if l["enemy_spots"] == 0),
            "unlocks_mean": round(mean(len(r["final"]["unlocked"]) for r in results), 2),
            "dust_ash_blessing_mean": [round(mean(r["final"][k] for r in results), 1)
                                       for k in ("dust", "ash", "blessing")]}


def _terrain_profile(chunk):
    a = chunk.asset
    cells = a.width * a.height
    blocked = sum(map(sum, a.collision))
    props = sum(1 for row in a.objects for o in row if o is not None and o.glyph == ";")
    marks = {}
    for row in a.environment:
        for cell in row:
            if cell.glyph not in ".=":
                marks[cell.glyph] = marks.get(cell.glyph, 0) + 1
    return {"blocked_percent": 100 * blocked // cells, "brush_percent": 100 * props // cells,
            "floor_marks": {g: 100 * n // cells for g, n in sorted(marks.items())}}


def inspect_chunk(seed, x, y, life=1, unlocked=(), knowledge=(), recipes=()):
    """Why this chunk looks and plays the way it does: its pinned region (and how it was
    chosen), the region's generation parameters and resulting terrain, the rolled spots,
    and every spot action's lifecycle state (UNKNOWN ... SPAWNED) with reasons."""
    from .encounters import chunk_spots
    from .regions import REGION_VERSION, region_cell
    world = new_world(seed)
    key = ChunkKey("forest", x, y)
    chunk = world.get(key)
    region = world.region_for(key)
    ctx = Context(biome=chunk.asset.biome, region=region.id, region_def=region, placement="spot",
                  unlocked=frozenset(unlocked), knowledge=frozenset(knowledge), recipes=frozenset(recipes))
    spots = chunk_spots(chunk, life, context=ctx)
    rolled = {s.encounter for s in spots}
    return {"seed": seed, "chunk": [x, y], "biome": chunk.asset.biome,
            "generator_version": world.generator_version,
            "region": region.id, "region_name": region.name,
            "region_provenance": {"cell": list(region_cell(key)), "version": REGION_VERSION,
                                  "rule": "origin cell" if region_cell(key) == (0, 0) else
                                  "weighted roll of derive_seed(world_seed, version, biome, cell)"},
            "region_parameters": {"canopy": region.canopy, "brush": region.brush, "landmark": region.landmark,
                                  "tint": region.tint, "action_weight_percent": dict(region.weights)},
            "terrain": _terrain_profile(chunk),
            "life": life, "unlocked": sorted(unlocked), "knowledge": sorted(knowledge), "recipes": sorted(recipes),
            "spots": [{"id": s.id, "action": s.encounter, "cell": [s.x, s.y]} for s in spots],
            "bucket": describe_bucket(ctx),
            "actions": [{k: v for k, v in explain(a.id, Context(**{**ctx.__dict__, "spawned": a.id in rolled})).items()
                         if k in ("id", "state", "weight", "share_permille", "bucket_reasons", "weight_modifiers")}
                        for a in BY_ID.values() if a.placement == "spot"],
            "note": "AVAILABLE here = rolled in this chunk; live play may still turn it away by its at-once cap."}


def region_map(seed, radius=2):
    """Region layout around the anchor, one letter per 3x3-chunk region cell (row = y)."""
    from .catalog import REGION_CELL, REGIONS
    world = new_world(seed)
    letters = {rid: rid[0].upper() if rid != "still_glade" else "G" for rid in REGIONS}
    rows = []
    for cy in range(-radius, radius + 1):
        rows.append(" ".join(letters[world.region_for(ChunkKey("forest", cx * REGION_CELL, cy * REGION_CELL)).id]
                             for cx in range(-radius, radius + 1)))
    return {"seed": seed, "legend": {v: k for k, v in letters.items()}, "rows": rows}


def parse_seeds(text):
    seeds = []
    for part in text.split(","):
        if "-" in part:
            low, high = map(int, part.split("-"))
            seeds.extend(range(low, high + 1))
        else:
            seeds.append(int(part))
    return seeds
