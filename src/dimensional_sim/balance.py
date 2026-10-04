from __future__ import annotations

from collections import defaultdict
from copy import deepcopy
from dataclasses import asdict, dataclass, field, replace
import json
from statistics import median
from typing import Iterable

from .core import GameState, new_demo_game


@dataclass
class ScenarioResult:
    seconds: float
    active: bool
    unlocked_stage: int
    life_count: int
    shards: float
    regular_levels: dict[str, int]
    dimensional_levels: dict[str, int]
    journal_entries: int
    journal_unlocks: int
    simulation_seconds: float = 0
    vitality: float = 0
    returns: int = 0
    returns_per_hour: float = 0
    clone_shards_generated: float = 0
    stage_first_entered: dict[str, float | None] = field(default_factory=dict)
    act_first_entered: dict[str, float] = field(default_factory=dict)
    encounter_completions: dict[str, int] = field(default_factory=dict)
    journal_progress: dict[str, dict] = field(default_factory=dict)
    action_timings: dict[str, dict] = field(default_factory=dict)
    summon_pools: list[dict] = field(default_factory=list)
    pending_story_actions: list[dict] = field(default_factory=list)
    balance_warnings: list[dict] = field(default_factory=list)
    summoned_items: list[dict] = field(default_factory=list)
    summon_progress: dict[str, dict] = field(default_factory=dict)
    summon_rarity_chances: dict[str, float] = field(default_factory=dict)
    summon_reviews: list[dict] = field(default_factory=list)


def diagnostics(game: GameState) -> dict:
    """Report actual story dependencies and viability warnings, never stat gates."""
    pending, warnings = [], []
    completed = set(game.current_run.completed_story_actions)
    preceding = None
    for stage in game.stages:
        for action in stage.guaranteed_actions:
            if preceding is not None and preceding not in completed:
                pending.append({"stage": stage.id, "action": action.id,
                                "preceding_action": preceding})
            preceding = action.id
        for action in (*stage.guaranteed_actions, *(e.action for e in stage.encounters)):
            if action.vitality_cost >= game.config.starting_vitality:
                warnings.append({
                    "action": action.id,
                    "reason": "action vitality cost exhausts a full life before reward",
                })
    return {"pending_story_actions": pending, "balance_warnings": warnings}


def run_scenario(
    seconds: float,
    *,
    active: bool,
    seed: int = 1,
    equipment_id: str | None = None,
    summons: int = 0,
    offline_efficiency: float | None = None,
    dimensional_speed_per_level: float | None = None,
) -> ScenarioResult:
    if type(summons) is not int or summons < 0:
        raise ValueError("summons must be a non-negative integer")
    game = new_demo_game(seed)
    if offline_efficiency is not None or dimensional_speed_per_level is not None:
        game.config = replace(
            game.config,
            offline_efficiency=offline_efficiency if offline_efficiency is not None else game.config.offline_efficiency,
            dimensional_speed_per_level=(
                dimensional_speed_per_level if dimensional_speed_per_level is not None
                else game.config.dimensional_speed_per_level
            ),
        )
        game.validate_content()
    if equipment_id is not None:
        template = game.template_by_id(equipment_id)
        initial_shards, rng_state = game.shards, game._rng.getstate()
        progress = deepcopy(game.summon_progress)
        templates = game.soulbound_items
        # Restrict this laboratory fixture to the requested template, then
        # restore the production pool and starting economy/progression.
        if template.rarity != "common":
            raise ValueError("starting equipment fixture must be common")
        try:
            game.soulbound_items = [template]
            game.shards += game.config.summon_cost
            summoned = game.summon()
        finally:
            game.soulbound_items = templates
        game.shards = initial_shards
        game.summon_progress = progress
        game._rng.setstate(rng_state)
        game.resolve_summon_review(summoned.id, equip=True)
    game.advance(seconds, active=active)
    for _ in range(summons):
        game.summon()
    summary = game.summary()
    stage_times = {stage.id: None for stage in game.stages}
    stage_unlocks = {game.stages[0].id: 0.0}
    act_times, timings = {}, defaultdict(list)
    stage_lookup = {stage.id: stage for stage in game.stages}
    returns = 0
    for event in game.event_log:
        if event["event"] == "stage_entered":
            stage_id = event["stage"]
            if stage_times[stage_id] is None:
                stage_times[stage_id] = event["time"]
            act_times.setdefault(str(stage_lookup[stage_id].act), event["time"])
        elif event["event"] == "stage_unlocked":
            stage_unlocks.setdefault(event["stage"], event["time"])
        elif event["event"] == "returned_to_anchor":
            returns += 1
        elif event["event"] == "action_completed":
            timings[event["action"]].append(event["simulation_duration"])
    journal_progress = {}
    for stage in game.stages:
        for encounter in stage.encounters:
            entry = game.journal.get(encounter.id)
            journal_progress[encounter.id] = {
                "completions": entry.completions if entry else 0,
                "threshold": game.config.journal_thresholds[encounter.rarity],
                "enabled": _encounter_enabled(game, encounter.id),
                "first_seen_at": entry.first_seen_at if entry else None,
            }
    clone_rate = game.config.clone_shards_per_second * (
        1 + sum(game.item_by_id(i).shard_rate_bonus for i in game.equipped_items)
    )
    chances = game.summon_rarity_weights()
    pools = [{
        "shard_cost": game.config.summon_cost,
        "available_items": [item.id for item in game.soulbound_items if chances[item.rarity] > 0],
        "rarity_chances": chances,
        "affordable_now": game.shards >= game.config.summon_cost,
        "clone_only_budget_seconds_from_opening": (
            max(0, game.config.summon_cost - 1) / clone_rate if clone_rate else None
        ),
    }]
    return ScenarioResult(
        seconds=seconds, active=active,
        unlocked_stage=summary["unlocked_stage"], life_count=summary["life_count"],
        shards=summary["shards"], regular_levels=summary["regular_levels"],
        dimensional_levels=summary["dimensional_levels"],
        journal_entries=len(game.journal),
        journal_unlocks=sum(entry.unlocked for entry in game.journal.values()),
        simulation_seconds=game.simulation_seconds, vitality=summary["vitality"],
        returns=returns, returns_per_hour=returns * 3600 / seconds if seconds else 0,
        clone_shards_generated=game.clone_shards_generated,
        stage_first_entered=stage_times, act_first_entered=act_times,
        encounter_completions={key: entry.completions for key, entry in game.journal.items()},
        journal_progress=journal_progress,
        action_timings={
            action: {"completions": len(values), "mean_simulation_seconds": sum(values) / len(values),
                     "total_simulation_seconds": sum(values)}
            for action, values in sorted(timings.items(), key=lambda pair: -sum(pair[1]))
        },
        summon_pools=pools,
        summoned_items=[asdict(item) for item in game.summoned_items.values()],
        summon_progress=summary["summon_progress"],
        summon_rarity_chances=chances,
        summon_reviews=[game.summon_review(i) for i in game.pending_summon_reviews],
        **diagnostics(game),
    )


def batch(
    seconds: float, *, active: bool, seeds: Iterable[int] = range(1, 101),
    equipment_id: str | None = None,
) -> dict:
    results = [run_scenario(seconds, active=active, seed=seed, equipment_id=equipment_id)
               for seed in seeds]
    if not results:
        raise ValueError("a batch requires at least one seed")
    report = {
        "runs": len(results), "seconds": seconds, "active": active,
        "median_stage": median(r.unlocked_stage for r in results),
        "median_lives": median(r.life_count for r in results),
        "median_shards": median(r.shards for r in results),
        "median_journal_entries": median(r.journal_entries for r in results),
        "median_journal_unlocks": median(r.journal_unlocks for r in results),
        "median_returns_per_hour": median(r.returns_per_hour for r in results),
        "median_vitality": median(r.vitality for r in results),
        "stage_reach_rate": {
            stage: sum(r.stage_first_entered[stage] is not None for r in results) / len(results)
            for stage in results[0].stage_first_entered
        },
        "median_stage_first_entered": {
            stage: median(times) if (times := [
                r.stage_first_entered[stage] for r in results if r.stage_first_entered[stage] is not None
            ]) else None for stage in results[0].stage_first_entered
        },
        "sample": asdict(results[0]),
    }
    if equipment_id:
        report["variant"] = equipment_id
    return report


def compare(seconds: float, *, seeds: Iterable[int] = range(1, 101)) -> dict:
    seeds = tuple(seeds)
    return {
        "active": batch(seconds, active=True, seeds=seeds),
        "offline": batch(seconds, active=False, seeds=seeds),
        "active_with_lens": batch(seconds, active=True, seeds=seeds, equipment_id="lens_of_attention"),
        "offline_with_lens": batch(seconds, active=False, seeds=seeds, equipment_id="lens_of_attention"),
    }


def _encounter_enabled(game: GameState, encounter_id: str) -> bool:
    entry = game.journal.get(encounter_id)
    return not (entry and entry.unlocked and not entry.enabled)


def action_graph(game: GameState) -> dict:
    # Eligibility graph: edges describe prerequisites, not mutually exclusive
    # scheduling branches. Enabled journal actions may all be available together.
    nodes, edges = [], []
    preceding = None
    for stage in game.stages:
        for action in stage.guaranteed_actions:
            nodes.append({"id": action.id, "label": action.name,
                          "stage": stage.id, "kind": "story"})
            if preceding is not None:
                edges.append({"from": preceding, "to": action.id,
                              "requires": "preceding_story_action_completed"})
            preceding = action.id
        for encounter in stage.encounters:
            entry = game.journal.get(encounter.id)
            unlocked = bool(entry and entry.unlocked)
            nodes.append({"id": encounter.action.id, "label": encounter.name,
                          "stage": stage.id, "kind": "encounter",
                          "roll_probability": encounter.weight,
                          "journal_unlocked": unlocked,
                          "enabled": _encounter_enabled(game, encounter.id)})
            edges.append({
                "from": preceding, "to": encounter.action.id,
                "requires": {
                    "all": ["story_action_completed",
                            {"any": ["in_current_run_bucket", "journal_unlocked_and_enabled"]}],
                },
            })
    return {"kind": "eligibility", "nodes": nodes, "edges": edges}



if __name__ == "__main__":
    print(json.dumps(compare(24 * 60 * 60), indent=2, sort_keys=True))
