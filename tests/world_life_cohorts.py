"""Paired first-life measurements for the world staff and discovery chains.

Run with PYTHONPATH=src: python -B tests/world_life_cohorts.py --seeds 1-8
Both cohorts carry the same staff item and have crafting disabled; only the
weapon slot differs. The scenario isolates its combat effect while retaining
ordinary procedural exploration, food, boar pursuit, and discovery outcomes.
"""

import argparse
import json
from statistics import mean
from time import perf_counter

from dimensional_sim.world.autopilot import Expedition
from dimensional_sim.world.equipment import equip_item
from dimensional_sim.world.runtime import Exploration
from dimensional_sim.world.simulate import parse_seeds
from dimensional_sim.world.web import new_world


CHAIN = ("animal_tracks", "follow_deer_tracks", "hunt_deer")


def run_first_life(seed, *, staff, max_minutes=45, step_ms=5000):
    e = Expedition(Exploration(new_world(seed), "forest"))
    e.crafting_enabled = False
    e.inventory["walking_staff"] = 1
    if staff:
        e.equipped = equip_item(e.equipped, e.inventory, "walking_staff")
    limit = max_minutes * 60_000
    lead_events = set()
    while e.anchor_ms is None and e.total_ms < limit:
        e.advance(min(step_ms, limit - e.total_ms))
        lead_events.update((row["id"], row["action"], row["status"])
                           for row in e.lead_history)
    died = e.anchor_ms is not None
    counts = e.journal["actions"]
    lead_counts = {kind: sum(status == "created" and action == kind
                             for _, action, status in lead_events)
                   for kind in ("follow_deer_tracks", "hunt_deer")}
    return {"seed": seed, "staff": staff, "censored": not died,
            "cause": e.cause if died else None,
            "life_ms": e.report["clock_ms"] if died else e.total_ms,
            "boar_bite_encounters": len(e.strikes),
            "boar_bites": sum(e.strikes.values()),
            "boar_kills": counts.get("bramble_boar", 0),
            "starvation_death": died and e.cause == "starvation",
            "boar_death": died and e.cause == "boar",
            "completed": e.stats["completed"], "crafted": e.stats["crafted"],
            "chunks": e.stats["chunks"], "depth": e.depth,
            "chain": {kind: counts.get(kind, 0) for kind in CHAIN},
            "lead_created": lead_counts,
            "knowledge": sorted(e.knowledge), "recipes": sorted(e.recipes)}


def summarize(rows):
    groups = {}
    for staff in (False, True):
        cohort = [row for row in rows if row["staff"] == staff]
        deaths = [row for row in cohort if not row["censored"]]
        engagements = sum(row["boar_bite_encounters"] for row in cohort)
        kills = sum(row["boar_kills"] for row in cohort)
        groups["equipped" if staff else "unarmed"] = {
            "seeds": len(cohort), "censored": len(cohort) - len(deaths),
            "life_minutes_mean": round(mean(row["life_ms"] for row in deaths) / 60_000, 2)
            if deaths else None,
            "boar_bite_encounters": engagements, "boar_kills": kills,
            "kills_per_bite_encounter": round(kills / engagements, 3) if engagements else None,
            "boar_deaths": sum(row["boar_death"] for row in cohort),
            "starvation_deaths": sum(row["starvation_death"] for row in cohort),
            "chunks_mean": round(mean(row["chunks"] for row in cohort), 1),
            "depth_mean": round(mean(row["depth"] for row in cohort), 1),
            "crafted": sum(row["crafted"] for row in cohort),
            "chain_completion_seeds": {kind: sum(row["chain"][kind] > 0 for row in cohort)
                                       for kind in CHAIN},
            "chain_completions": {kind: sum(row["chain"][kind] for row in cohort)
                                  for kind in CHAIN},
            "lead_created": {kind: sum(row["lead_created"][kind] for row in cohort)
                             for kind in ("follow_deer_tracks", "hunt_deer")},
            "craft_knowledge_seeds": sum("primitive_crafting" in row["knowledge"] for row in cohort),
            "staff_recipe_seeds": sum("walking_staff" in row["recipes"] for row in cohort),
        }
    return groups


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seeds", default="1-8")
    parser.add_argument("--max-minutes", type=int, default=45)
    parser.add_argument("--step-ms", type=int, default=5000)
    args = parser.parse_args()
    if args.max_minutes < 1 or args.step_ms < 1:
        parser.error("minutes and step must be positive")
    started = perf_counter()
    rows = [run_first_life(seed, staff=staff, max_minutes=args.max_minutes, step_ms=args.step_ms)
            for seed in parse_seeds(args.seeds) for staff in (False, True)]
    print(json.dumps({"scenario": "paired_first_life_staff_slot_only", "rows": rows,
                      "summary": summarize(rows), "wall_seconds": round(perf_counter() - started, 2)},
                     sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
