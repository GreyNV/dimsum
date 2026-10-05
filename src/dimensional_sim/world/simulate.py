"""Seeded multi-run simulation and chunk inspection for design and balancing.

WHAT: runs whole expeditions headlessly with a scripted anchor policy and reports
per-life metrics; inspects one chunk's region, spots and action bucket.
WHY: balance by measurement (docs/design/BALANCING.md), and answer "why did / didn't
this appear" without reading code.
USE:
  python -m dimensional_sim.world.cli simulate --seeds 1-10 --minutes 30 --policy spend
  python -m dimensional_sim.world.cli inspect --seed 482910 --x 1 --y 0 --unlock climbing
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
from .regions import region_for
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
    while e.total_ms < total:
        e.advance(step_ms)
        if e.anchor_ms is not None and recorded != e.life:
            recorded = e.life
            report = e.report
            lives.append({"life": e.life, "minutes": round((e.total_ms - start) / 60000, 2),
                          "cause": e.cause or "exhaustion", "depth": e.depth, **e.stats,
                          "carried_dust": sum(ITEMS[i].dust * n for i, n in e.inventory.items()),
                          "title": report["title"]})
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
                "eaten", "crafted", "fights", "prayers", "carried_dust")},
            "lives_without_food_spot": sum(1 for l in lives if l["food_spots"] == 0),
            "lives_without_enemy": sum(1 for l in lives if l["enemy_spots"] == 0),
            "unlocks_mean": round(mean(len(r["final"]["unlocked"]) for r in results), 2),
            "dust_ash_blessing_mean": [round(mean(r["final"][k] for r in results), 1)
                                       for k in ("dust", "ash", "blessing")]}


def inspect_chunk(seed, x, y, life=1, unlocked=()):
    """Region, rolled spots and full bucket explanation for one chunk."""
    from .encounters import chunk_spots
    world = new_world(seed)
    key = ChunkKey("forest", x, y)
    chunk = world.get(key)
    region = region_for(world.world_seed, chunk.asset.biome, key)
    ctx = Context(biome=chunk.asset.biome, region=region.id, placement="spot", unlocked=frozenset(unlocked))
    return {"seed": seed, "chunk": [x, y], "biome": chunk.asset.biome, "region": region.id,
            "region_name": region.name, "life": life, "unlocked": sorted(unlocked),
            "spots": [{"id": s.id, "action": s.encounter, "cell": [s.x, s.y]}
                      for s in chunk_spots(chunk, life, unlocked=frozenset(unlocked), region=region.id)],
            "bucket": describe_bucket(ctx),
            "not_eligible": [explain(a.id, ctx) for a in BY_ID.values()
                             if a.placement == "spot" and not explain(a.id, ctx)["eligible"]]}


def parse_seeds(text):
    seeds = []
    for part in text.split(","):
        if "-" in part:
            low, high = map(int, part.split("-"))
            seeds.extend(range(low, high + 1))
        else:
            seeds.append(int(part))
    return seeds
