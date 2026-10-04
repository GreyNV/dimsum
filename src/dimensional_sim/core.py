from __future__ import annotations

from dataclasses import asdict, dataclass, field
import json
import math
import random
from typing import Optional

from .persistence import decode_rng_state
from .equipment import EQUIPMENT_SLOTS, compare_items
from .summoning import RARITIES, SummonProgress, SummonedItem, level_range, update_level, roll_item, make_item


DISCIPLINES = ("strength", "endurance", "agility", "intelligence", "perception", "willpower")


@dataclass(frozen=True)
class Action:
    id: str
    name: str
    discipline: str
    base_seconds: float
    vitality_cost: float
    regular_xp_rate: float
    dimensional_xp_rate: float
    guaranteed: bool = True
    story_progress: float = 0.0


@dataclass(frozen=True)
class Encounter:
    id: str
    name: str
    rarity: str
    weight: float
    action: Action
    vitality_delta: float = 0.0
    shards: float = 0.0
    lore: str = ""


@dataclass(frozen=True)
class Stage:
    id: str
    name: str
    act: int
    guaranteed_actions: tuple[Action, ...]
    encounters: tuple[Encounter, ...]
    summon_weights: dict[str, float] = field(default_factory=dict)
    summon_level_caps: dict[str, int] = field(default_factory=dict)


@dataclass(frozen=True)
class SoulboundItem:
    id: str
    name: str
    rarity: str
    stat_per_level: float = 1.0
    slot: str = "charm"
    speed_bonus: float = 0.0
    softcap_bonus: float = 0.0
    shard_rate_bonus: float = 0.0
    discipline: Optional[str] = None


@dataclass
class JournalEntry:
    completions: int = 0
    unlocked: bool = False
    enabled: bool = True
    first_seen_at: Optional[float] = None


@dataclass
class GameConfig:
    disciplines: tuple[str, ...] = DISCIPLINES
    regular_xp_base: float = 100.0
    regular_xp_growth: float = 1.15
    dimensional_xp_base: float = 100.0
    dimensional_xp_growth: float = 1.35
    regular_speed_per_level: float = 0.10
    dimensional_speed_per_level: float = 0.01
    softcap_softness: float = 0.08
    starting_vitality: float = 100.0
    clone_shards_per_second: float = 0.02
    offline_efficiency: float = 0.65
    vitality_decay_per_second: float = 0.02
    base_softcap: float = 10.0
    softcap_per_stage: float = 5.0
    summon_weights: dict[str, float] = field(
        default_factory=lambda: {"common": 100, "uncommon": 0, "rare": 0, "legendary": 0}
    )
    summon_cost: float = 10.0
    summon_xp_per_pull: float = 1.0
    summon_xp_base: float = 10.0
    summon_xp_growth: float = 1.15
    initial_summon_max_level: int = 10
    item_speed_per_stat: float = 0.01
    journal_thresholds: dict[str, int] = field(
        default_factory=lambda: {"common": 10, "uncommon": 100, "rare": 1000}
    )


@dataclass
class RunState:
    vitality: float
    stage_index: int = 0
    action_queue: list[str] = field(default_factory=list)
    selected_encounter: Optional[str] = None
    encounter_bucket: list[str] = field(default_factory=list)
    stage_buckets: dict[str, list[str]] = field(default_factory=dict)
    completed_story_actions: list[str] = field(default_factory=list)
    completed_actions: int = 0
    life_seconds: float = 0.0
    action_work: float = 0.0
    action_seconds: float = 0.0


@dataclass
class GameState:
    config: GameConfig
    stages: list[Stage]
    soulbound_items: list[SoulboundItem]
    seed: int = 1
    world_seconds: float = 0.0
    simulation_seconds: float = 0.0
    clone_shards_generated: float = 0.0
    life_count: int = 0
    current_run: Optional[RunState] = None
    regular_xp: dict[str, float] = field(default_factory=dict)
    dimensional_xp: dict[str, float] = field(default_factory=dict)
    journal: dict[str, JournalEntry] = field(default_factory=dict)
    journal_lore: set[str] = field(default_factory=set)
    unlocked_stage: int = 0
    shards: float = 1.0
    equipped_items: list[str] = field(default_factory=list)
    owned_items: list[str] = field(default_factory=list)
    summoned_items: dict[str, SummonedItem] = field(default_factory=dict)
    summon_progress: dict[str, SummonProgress] = field(default_factory=dict)
    completed_stages: list[str] = field(default_factory=list)
    pending_summon_reviews: list[str] = field(default_factory=list)
    event_log: list[dict] = field(default_factory=list)
    _rng: random.Random = field(init=False, repr=False)

    def __post_init__(self) -> None:
        self.validate_content()
        _integer(self.seed, "seed")
        self._rng = random.Random(self.seed)
        for discipline in self.config.disciplines:
            self.regular_xp.setdefault(discipline, 0.0)
            self.dimensional_xp.setdefault(discipline, 0.0)
        for rarity in RARITIES:
            self.summon_progress.setdefault(rarity, SummonProgress(max_level=self.config.initial_summon_max_level))
        if self.current_run is None:
            self.start_life()

    def validate_content(self) -> None:
        c = self.config
        if not c.disciplines or len(set(c.disciplines)) != len(c.disciplines):
            raise ValueError("disciplines must be nonempty and unique")
        for name in ("regular_xp_base", "dimensional_xp_base", "starting_vitality"):
            _number(getattr(c, name), name, positive=True)
        for name in ("regular_xp_growth", "dimensional_xp_growth"):
            _number(getattr(c, name), name)
            if getattr(c, name) < 1:
                raise ValueError(f"{name} must be at least one")
        for name in ("regular_speed_per_level", "dimensional_speed_per_level",
                     "softcap_softness", "clone_shards_per_second",
                     "vitality_decay_per_second", "base_softcap", "softcap_per_stage"):
            _number(getattr(c, name), name)
        _number(c.offline_efficiency, "offline_efficiency")
        if c.offline_efficiency > 1:
            raise ValueError("offline_efficiency must be between zero and one")
        for threshold in c.journal_thresholds.values():
            _integer(threshold, "journal threshold", minimum=1)
        self._validate_summon_weights(c.summon_weights)
        for name in ("summon_cost", "summon_xp_per_pull", "summon_xp_base"):
            _number(getattr(c, name), name, positive=True)
        _number(c.summon_xp_growth, "summon XP growth")
        if c.summon_xp_growth < 1:
            raise ValueError("summon XP growth must be at least one")
        _integer(c.initial_summon_max_level, "initial summon cap", minimum=10)
        _number(c.item_speed_per_stat, "item speed per stat")
        if not self.stages:
            raise ValueError("at least one stage is required")
        stage_ids, action_ids, encounter_ids, item_ids = set(), set(), set(), set()
        for stage in self.stages:
            _identifier(stage.id, stage_ids, "stage")
            _integer(stage.act, "act", minimum=1)
            if stage.summon_weights:
                self._validate_summon_weights(stage.summon_weights)
            for rarity, cap in stage.summon_level_caps.items():
                if rarity not in RARITIES:
                    raise ValueError("unknown summon cap rarity")
                _integer(cap, "summon cap", minimum=10)
            if not stage.guaranteed_actions:
                raise ValueError("each stage needs a guaranteed action to ensure progress")
            if sum(e.weight for e in stage.encounters) > 1 + 1e-12:
                raise ValueError("encounter probabilities must sum to at most one")
            actions = list(stage.guaranteed_actions)
            for encounter in stage.encounters:
                _identifier(encounter.id, encounter_ids, "encounter")
                _number(encounter.weight, "encounter probability")
                _number(encounter.shards, "encounter shards")
                _number(encounter.vitality_delta, "vitality delta", signed=True)
                if encounter.rarity not in c.journal_thresholds:
                    raise ValueError("encounter rarity needs a journal threshold")
                actions.append(encounter.action)
            for action in actions:
                _identifier(action.id, action_ids, "action")
                if action.discipline not in c.disciplines:
                    raise ValueError("unknown action discipline")
                _number(action.base_seconds, "action work", positive=True)
                for name in ("vitality_cost", "regular_xp_rate", "dimensional_xp_rate",
                             "story_progress"):
                    _number(getattr(action, name), name)
                if action.story_progress:
                    raise ValueError("per-action story requirements are not implemented")
        for item in self.soulbound_items:
            _identifier(item.id, item_ids, "item")
            _number(item.stat_per_level, "item stat per level", positive=True)
            if item.slot not in EQUIPMENT_SLOTS:
                raise ValueError("unknown equipment slot")
            if item.rarity not in RARITIES:
                raise ValueError("item rarity needs a summon weight")
            if item.discipline not in c.disciplines:
                raise ValueError("unknown item discipline")
            for name in ("speed_bonus", "softcap_bonus", "shard_rate_bonus"):
                _number(getattr(item, name), name)
            if item.rarity == "common" and any(
                (item.speed_bonus, item.softcap_bonus, item.shard_rate_bonus)
            ):
                raise ValueError("common templates must grant only their single base stat")

    @staticmethod
    def _validate_summon_weights(weights: dict[str, float]) -> None:
        if not weights or not set(weights) <= set(RARITIES):
            raise ValueError("invalid summon rarity row")
        for weight in weights.values():
            _number(weight, "summon weight")
        if sum(weights.values()) <= 0:
            raise ValueError("summon rarity row must have positive total weight")


    def regular_level(self, discipline: str) -> int:
        return _level_from_xp(self.regular_xp[discipline], self.config.regular_xp_base, self.config.regular_xp_growth)

    def dimensional_level(self, discipline: str) -> int:
        return _level_from_xp(
            self.dimensional_xp[discipline],
            self.config.dimensional_xp_base,
            self.config.dimensional_xp_growth,
        )

    def effective_level(self, discipline: str) -> float:
        regular = _softcapped_level(
            self.regular_level(discipline),
            self.softcap_for(discipline),
            self.config.softcap_softness,
        )
        dimensional = _softcapped_level(
            self.dimensional_level(discipline),
            self.softcap_for(discipline),
            self.config.softcap_softness,
        )
        return regular + dimensional

    def softcap_for(self, discipline: str) -> float:
        bonus = sum(
            item.softcap_bonus
            for item_id in self.equipped_items
            if (item := self.item_by_id(item_id)).discipline in (None, discipline)
        )
        return self.config.base_softcap + self.unlocked_stage * self.config.softcap_per_stage + bonus

    def speed_multiplier(self, discipline: str) -> float:
        regular = self._equipped_speed_bonus(discipline)
        return (
            1.0
            + self.config.regular_speed_per_level * _softcapped_level(
                self.regular_level(discipline), self.softcap_for(discipline), self.config.softcap_softness
            )
            + self.config.dimensional_speed_per_level * _softcapped_level(
                self.dimensional_level(discipline), self.softcap_for(discipline), self.config.softcap_softness
            )
            + regular
        )

    def _equipped_speed_bonus(self, discipline: str) -> float:
        return sum(
            item.speed_bonus + self.config.item_speed_per_stat * item.base_stats.get(discipline, 0)
            for item_id in self.equipped_items
            if (item := self.item_by_id(item_id)).discipline in (None, discipline)
        )

    def template_by_id(self, template_id: str) -> SoulboundItem:
        for item in self.soulbound_items:
            if item.id == template_id:
                return item
        raise KeyError(f"unknown soulbound template: {template_id}")

    def item_by_id(self, item_id: str) -> SummonedItem:
        if item_id not in self.summoned_items:
            raise KeyError(f"unknown summoned item: {item_id}")
        return self.summoned_items[item_id]

    def start_life(self) -> None:
        if self.current_run is not None:
            raise ValueError("a life is already running")
        self.regular_xp = {discipline: 0.0 for discipline in self.config.disciplines}
        self.life_count += 1
        self.current_run = RunState(vitality=self.config.starting_vitality)
        self._enter_stage(0)
        self._log("life_started", life=self.life_count)

    def _enter_stage(self, stage_index: int) -> None:
        if not 0 <= stage_index <= self.unlocked_stage or stage_index >= len(self.stages):
            raise ValueError("stage has not been reached through its preceding story action")
        run = self.current_run
        run.stage_index = stage_index
        stage = self.stages[stage_index]
        # A stage's random bucket is rolled only once per life, including an
        # empty roll. Journal unlocks provide a separate, reliable access path.
        if stage.id not in run.stage_buckets:
            rolled = self._roll_encounter(stage)
            run.stage_buckets[stage.id] = [rolled.id] if rolled else []
        rolled_ids = run.stage_buckets[stage.id]
        encounters = []
        for encounter in stage.encounters:
            entry = self.journal.get(encounter.id)
            if entry and entry.unlocked and not entry.enabled:
                continue
            if encounter.id in rolled_ids or (entry and entry.unlocked):
                encounters.append(encounter)
        run.encounter_bucket = [encounter.id for encounter in encounters]
        run.action_queue = (
            [action.id for action in stage.guaranteed_actions]
            + [encounter.action.id for encounter in encounters]
        )
        run.action_work = 0.0
        run.action_seconds = 0.0
        for encounter in encounters:
            entry = self.journal.setdefault(encounter.id, JournalEntry())
            if entry.first_seen_at is None:
                entry.first_seen_at = self.world_seconds
                self._log("encounter_discovered", encounter=encounter.id)
        run.selected_encounter = next((e.id for e in encounters if e.id in rolled_ids), None)
        self._log("stage_entered", stage=stage.id, encounter=run.selected_encounter,
                  bucket=list(run.encounter_bucket))

    def _roll_encounter(self, stage: Stage) -> Optional[Encounter]:
        # Unlocked encounters are supplied by the journal, never rerolled.
        choices = [e for e in stage.encounters
                   if e.weight > 0 and not (self.journal.get(e.id) and self.journal[e.id].unlocked)]
        total = sum(e.weight for e in choices)
        if not choices or self._rng.random() >= total:
            return None
        roll = self._rng.random() * total
        for encounter in choices:
            roll -= encounter.weight
            if roll < 0:
                return encounter
        return choices[-1]

    def advance(self, seconds: float, *, active: bool = True) -> dict:
        _number(seconds, "seconds")
        self.validate_content()
        efficiency = 1.0 if active else self.config.offline_efficiency
        remaining = seconds * efficiency
        target_world = self.world_seconds + seconds
        target_simulation = self.simulation_seconds + remaining
        completed = 0
        if efficiency == 0:
            self.world_seconds += seconds
            self._accrue_clone_shards(seconds)
            return self.summary(active=active, requested_seconds=seconds)
        while remaining > 0:
            action = self._current_action()
            if action is None:
                self._finish_stage()
                continue
            run = self.current_run
            discipline = action.discipline
            speed = self.speed_multiplier(discipline)
            to_completion = (action.base_seconds - run.action_work) / speed
            vitality_rate = (
                self.config.vitality_decay_per_second
                + action.vitality_cost * speed / action.base_seconds
            )
            to_death = run.vitality / vitality_rate if vitality_rate else math.inf
            regular_tick = _time_to_level(
                self.regular_xp[discipline], self.config.regular_xp_base,
                self.config.regular_xp_growth, action.regular_xp_rate,
            )
            dimensional_tick = _time_to_level(
                self.dimensional_xp[discipline], self.config.dimensional_xp_base,
                self.config.dimensional_xp_growth, action.dimensional_xp_rate,
            )
            step = min(remaining, to_completion, to_death, regular_tick, dimensional_tick)
            if step < 0 or not math.isfinite(step):
                raise ValueError("invalid simulation state")
            real_step = step / efficiency
            self.world_seconds += real_step
            self.simulation_seconds += step
            run.life_seconds += step
            run.action_work += speed * step
            run.action_seconds += step
            run.vitality = max(0.0, run.vitality - vitality_rate * step)
            self.regular_xp[discipline] += action.regular_xp_rate * step
            self.dimensional_xp[discipline] += action.dimensional_xp_rate * step
            self._accrue_clone_shards(real_step)
            remaining = max(0.0, remaining - step)
            # Death takes precedence over completion at the same instant.
            if to_death <= step + 1e-10:
                self._return_to_anchor("vitality_exhausted")
            elif to_completion <= step + 1e-10:
                run.action_work = 0.0
                self._complete_action(action)
                run.action_seconds = 0.0
                completed += 1
                if run.vitality <= 0:
                    self._return_to_anchor("encounter")
                elif not run.action_queue:
                    self._finish_stage()
        self.world_seconds = target_world
        self.simulation_seconds = target_simulation
        return self.summary(last_completed=completed, active=active, requested_seconds=seconds)

    def _current_action(self) -> Optional[Action]:
        if not self.current_run.action_queue:
            return None
        action_id = self.current_run.action_queue[0]
        for stage in self.stages:
            for action in stage.guaranteed_actions:
                if action.id == action_id:
                    return action
            for encounter in stage.encounters:
                if encounter.action.id == action_id:
                    return encounter.action
        raise KeyError(f"unknown action in queue: {action_id}")

    def _complete_action(self, action: Action) -> None:
        self.current_run.action_queue.pop(0)
        self.current_run.completed_actions += 1
        stage = self.stages[self.current_run.stage_index]
        if action.id in {a.id for a in stage.guaranteed_actions}:
            if action.id not in self.current_run.completed_story_actions:
                self.current_run.completed_story_actions.append(action.id)
            # Story completion, not optional encounters or discipline levels,
            # establishes access to the next stage.
            if action.id == stage.guaranteed_actions[-1].id:
                if stage.id not in self.completed_stages:
                    self.completed_stages.append(stage.id)
                    self._log("stage_completed", stage=stage.id, act=stage.act)
                    for rarity, cap in stage.summon_level_caps.items():
                        if cap > self.summon_progress[rarity].max_level:
                            self.raise_summon_cap(rarity, cap)
                next_index = self.current_run.stage_index + 1
                if next_index < len(self.stages) and next_index > self.unlocked_stage:
                    self.unlocked_stage = next_index
                    self._log("stage_unlocked", stage=self.stages[next_index].id,
                              preceding_action=action.id)
        encounter = self._encounter_for_action(action.id)
        if encounter is not None:
            self._complete_encounter(encounter)
        self._log("action_completed", action=action.id, discipline=action.discipline,
                  simulation_duration=self.current_run.action_seconds)

    def _encounter_for_action(self, action_id: str) -> Optional[Encounter]:
        stage = self.stages[self.current_run.stage_index]
        return next((e for e in stage.encounters
                     if e.id in self.current_run.encounter_bucket and e.action.id == action_id), None)

    def _complete_encounter(self, encounter: Encounter) -> None:
        entry = self.journal.setdefault(encounter.id, JournalEntry())
        entry.completions += 1
        entry.first_seen_at = self.world_seconds if entry.first_seen_at is None else entry.first_seen_at
        self.journal_lore.add(encounter.id)
        self.current_run.vitality = max(0.0, min(self.config.starting_vitality, self.current_run.vitality + encounter.vitality_delta))
        self.shards += encounter.shards
        threshold = self.config.journal_thresholds.get(encounter.rarity, 100)
        if not entry.unlocked and entry.completions >= threshold:
            entry.unlocked = True
            self._log("journal_unlocked", encounter=encounter.id, threshold=threshold)
        self._log("encounter_completed", encounter=encounter.id, shards=encounter.shards)

    def _finish_stage(self) -> None:
        if self.current_run.action_queue:
            raise ValueError("cannot transfer before finishing the queued actions")
        next_index = self.current_run.stage_index + 1
        self._enter_stage(next_index if next_index < len(self.stages) else 0)

    def _return_to_anchor(self, reason: str) -> None:
        self._log("returned_to_anchor", reason=reason, life=self.life_count)
        self.current_run = None
        self.start_life()

    def _accrue_clone_shards(self, real_seconds: float) -> None:
        bonus = sum(
            item.shard_rate_bonus
            for item_id in self.equipped_items
            if (item := self.item_by_id(item_id))
        )
        generated = real_seconds * self.config.clone_shards_per_second * (1.0 + bonus)
        self.shards += generated
        self.clone_shards_generated += generated

    def configure_journal(self, encounter_id: str, enabled: bool) -> None:
        if type(enabled) is not bool:
            raise ValueError("enabled must be a boolean")
        entry = self.journal.get(encounter_id)
        if entry is None or not entry.unlocked:
            raise ValueError("encounter is not journal-unlocked")
        entry.enabled = enabled
        self._log("journal_configured", encounter=encounter_id, enabled=enabled)

    def summon_rarity_weights(self) -> dict[str, float]:
        weights = self.config.summon_weights
        for stage in self.stages:
            if stage.id in self.completed_stages and stage.summon_weights:
                weights = stage.summon_weights
        total = sum(weights.values())
        return {rarity: weights.get(rarity, 0.0) / total for rarity in RARITIES}

    def raise_summon_cap(self, rarity: str, maximum: int) -> None:
        if rarity not in self.summon_progress:
            raise ValueError("unknown summon rarity")
        _integer(maximum, "summon cap", minimum=10)
        progress = self.summon_progress[rarity]
        if maximum <= progress.max_level:
            raise ValueError("summon cap must increase")
        progress.max_level = maximum
        update_level(progress, self.config.summon_xp_base, self.config.summon_xp_growth)
        self._log("summon_cap_raised", rarity=rarity, maximum=maximum)

    def summon(self) -> SummonedItem:
        self.validate_content()
        weights = self.summon_rarity_weights()
        pools = {rarity: [item for item in self.soulbound_items if item.rarity == rarity]
                 for rarity in RARITIES}
        if any(weight > 0 and not pools[rarity] for rarity, weight in weights.items()):
            raise ValueError("summon rarity table references an empty item pool")
        if self.shards < self.config.summon_cost:
            raise ValueError("not enough dimensional shards")
        # Rarity first: adding common templates must not dilute rare odds.
        pick = self._rng.random()
        rarity = next(r for r in reversed(RARITIES) if weights[r] > 0)
        for candidate, weight in weights.items():
            pick -= weight
            if weight > 0 and pick < 0:
                rarity = candidate
                break
        template = self._rng.choice(pools[rarity])
        progress = self.summon_progress[rarity]
        item = roll_item(template, progress, self._rng, f"summon:{len(self.summoned_items) + 1}")
        self.shards -= self.config.summon_cost
        self.summoned_items[item.id] = item
        self.owned_items.append(item.id)
        self.pending_summon_reviews.append(item.id)
        progress.xp += self.config.summon_xp_per_pull
        update_level(progress, self.config.summon_xp_base, self.config.summon_xp_growth)
        self._log("soulbound_summoned", item=item.id, template=item.template_id,
                  rarity=rarity, level=item.level, cost=self.config.summon_cost)
        return item

    def equip(self, item_id: str) -> None:
        item = self.item_by_id(item_id)
        if item_id not in self.owned_items:
            raise ValueError("item is not owned")
        if item_id not in self.equipped_items:
            self.equipped_items = [owned for owned in self.equipped_items
                                   if self.item_by_id(owned).slot != item.slot]
            self.equipped_items.append(item_id)
            self._log("item_equipped", item=item_id)

    def unequip(self, item_id: str) -> None:
        self.item_by_id(item_id)
        if item_id in self.equipped_items:
            self.equipped_items.remove(item_id)
            self._log("item_unequipped", item=item_id)

    def summon_review(self, item_id: str) -> dict:
        candidate = self.item_by_id(item_id)
        if item_id not in self.owned_items:
            raise ValueError("item is not owned")
        current = next((self.item_by_id(i) for i in self.equipped_items
                        if self.item_by_id(i).slot == candidate.slot), None)
        return compare_items(current, candidate)

    def resolve_summon_review(self, item_id: str, *, equip: bool) -> dict:
        if type(equip) is not bool or item_id not in self.pending_summon_reviews:
            raise ValueError("invalid or already resolved summon review")
        review = self.summon_review(item_id)
        if equip:
            self.equip(item_id)
        self.pending_summon_reviews.remove(item_id)
        self._log("summon_reviewed", item=item_id, equipped=equip,
                  changes=review["summary"] if equip else [])
        return {"equipped": equip, "review": review,
                "applied_changes": review["changes"] if equip else []}

    def summary(self, *, last_completed: int = 0, active: bool = True, requested_seconds: float = 0.0) -> dict:
        return {
            "world_seconds": self.world_seconds,
            "simulation_seconds": self.simulation_seconds,
            "clone_shards_generated": self.clone_shards_generated,
            "requested_seconds": requested_seconds,
            "active": active,
            "life_count": self.life_count,
            "unlocked_stage": self.unlocked_stage,
            "current_stage": self.current_run.stage_index if self.current_run else None,
            "selected_encounter": self.current_run.selected_encounter if self.current_run else None,
            "encounter_bucket": list(self.current_run.encounter_bucket) if self.current_run else [],
            "completed_story_actions": list(self.current_run.completed_story_actions) if self.current_run else [],
            "vitality": round(self.current_run.vitality, 4) if self.current_run else 0.0,
            "regular_levels": {d: self.regular_level(d) for d in self.config.disciplines},
            "dimensional_levels": {d: self.dimensional_level(d) for d in self.config.disciplines},
            "regular_xp": dict(self.regular_xp),
            "dimensional_xp": dict(self.dimensional_xp),
            "shards": round(self.shards, 4),
            "journal": {key: asdict(value) for key, value in self.journal.items()},
            "owned_items": list(self.owned_items),
            "summoned_items": {key: asdict(value) for key, value in self.summoned_items.items()},
            "summon_progress": {key: {**asdict(value), "item_level_range": list(level_range(value))}
                                for key, value in self.summon_progress.items()},
            "summon_rarity_chances": self.summon_rarity_weights(),
            "completed_stages": list(self.completed_stages),
            "pending_summon_reviews": list(self.pending_summon_reviews),
            "equipped_items": list(self.equipped_items),
            "last_completed_actions": last_completed,
        }

    def to_json(self) -> str:
        payload = {
            "schema_version": 5,
            "config": asdict(self.config),
            "content": self._content_manifest(),
            "seed": self.seed,
            "world_seconds": self.world_seconds,
            "simulation_seconds": self.simulation_seconds,
            "clone_shards_generated": self.clone_shards_generated,
            "life_count": self.life_count,
            "current_run": asdict(self.current_run) if self.current_run else None,
            "regular_xp": self.regular_xp,
            "dimensional_xp": self.dimensional_xp,
            "journal": {key: asdict(value) for key, value in self.journal.items()},
            "journal_lore": sorted(self.journal_lore),
            "unlocked_stage": self.unlocked_stage,
            "shards": self.shards,
            "owned_items": self.owned_items,
            "summoned_items": {key: asdict(value) for key, value in self.summoned_items.items()},
            "summon_progress": {key: asdict(value) for key, value in self.summon_progress.items()},
            "completed_stages": self.completed_stages,
            "pending_summon_reviews": self.pending_summon_reviews,
            "equipped_items": self.equipped_items,
            "event_log": self.event_log,
            "rng_state": self._rng.getstate(),
        }
        return json.dumps(payload, sort_keys=True, allow_nan=False)

    @classmethod
    def from_json(
        cls,
        raw: str,
        *,
        stages: list[Stage],
        soulbound_items: list[SoulboundItem],
        config: Optional[GameConfig] = None,
    ) -> "GameState":
        payload = json.loads(raw)
        if not isinstance(payload, dict) or payload.get("schema_version") not in (1, 2, 3, 4, 5):
            raise ValueError("unsupported save schema")
        version = payload["schema_version"]
        legacy_attributes = {"insight": "perception", "resonance": "willpower"}
        legacy_actions = {
            "talk_father": "willpower", "practice_movement": "agility",
            "village_mystery_action": "intelligence", "drink_spring": "endurance",
            "sense_rift": "perception", "read_echo": "intelligence", "fight_shade": "strength",
        }
        if version < 5:
            for track in ("regular_xp", "dimensional_xp"):
                previous = payload[track]
                if "insight" in previous or "resonance" in previous:
                    payload[track] = {d: 0.0 for d in DISCIPLINES}
                    for key, value in previous.items():
                        payload[track][legacy_attributes.get(key, key)] = value
        if version >= 2:
            saved_config = dict(payload["config"])
            if version < 4:
                saved_config["summon_weights"] = dict(GameConfig().summon_weights)
            if version < 5 and (
                "insight" in saved_config["disciplines"] or "resonance" in saved_config["disciplines"]
            ):
                saved_config["disciplines"] = list(DISCIPLINES)
            saved_config["disciplines"] = tuple(saved_config["disciplines"])
            restored_config = GameConfig(**saved_config)
            if config is not None and config != restored_config:
                raise ValueError("save configuration does not match")
            config = restored_config
            manifest = json.loads(json.dumps({
                "stages": [asdict(stage) for stage in stages],
                "items": [asdict(item) for item in soulbound_items],
            }))
            if version == 2:
                # This migration removes only the obsolete stat gates. Other
                # content changes still require a separate explicit migration.
                for saved_stage in payload["content"]["stages"]:
                    saved_stage.pop("min_dimensional_level", None)
                    saved_stage.pop("gate_discipline", None)
            if version < 4:
                expected_stages = {stage["id"]: stage for stage in manifest["stages"]}
                for saved_stage in payload["content"]["stages"]:
                    expected = expected_stages.get(saved_stage["id"], {})
                    saved_stage.setdefault("summon_weights", expected.get("summon_weights", {}))
                    saved_stage.setdefault("summon_level_caps", expected.get("summon_level_caps", {}))
                for saved_item in payload["content"]["items"]:
                    saved_item.pop("minimum_stage", None)
                    saved_item.pop("shard_cost", None)
                    saved_item.setdefault("stat_per_level", 1.0)
                    if saved_item["rarity"] == "common":
                        for name in ("speed_bonus", "softcap_bonus", "shard_rate_bonus"):
                            saved_item[name] = 0.0
                # New templates expand the pool; old template definitions must
                # still match after this explicitly scoped migration.
                old_ids = {item["id"] for item in payload["content"]["items"]}
                manifest["items"] = [item for item in manifest["items"] if item["id"] in old_ids]
            if version < 5:
                expected_templates = {item.id: item for item in soulbound_items}
                for saved_stage in payload["content"]["stages"]:
                    actions = list(saved_stage["guaranteed_actions"]) + [
                        encounter["action"] for encounter in saved_stage["encounters"]
                    ]
                    for action in actions:
                        action["discipline"] = legacy_actions.get(
                            action["id"], legacy_attributes.get(action["discipline"], action["discipline"])
                        )
                for saved_item in payload["content"]["items"]:
                    saved_item["discipline"] = (
                        "strength" if saved_item["id"] == "old_gauntlet" else
                        legacy_attributes.get(saved_item["discipline"], saved_item["discipline"])
                    )
                    template = expected_templates.get(saved_item["id"])
                    saved_item.setdefault("slot", template.slot if template else "charm")
                old_ids = {item["id"] for item in payload["content"]["items"]}
                manifest["items"] = [item for item in manifest["items"] if item["id"] in old_ids]
            if payload["content"] != manifest:
                raise ValueError("save content does not match")
        rng_state = decode_rng_state(payload["rng_state"], legacy=version == 1)
        run_payload = payload.get("current_run")
        if not isinstance(run_payload, dict):
            raise ValueError("save must contain a current life")
        if version < 3:
            index = run_payload["stage_index"]
            if type(index) is not int or not 0 <= index < len(stages):
                raise ValueError("invalid saved stage")
            stage = stages[index]
            selected = run_payload.get("selected_encounter")
            run_payload.setdefault("encounter_bucket", [selected] if selected else [])
            # Older saves have no per-life bucket map. Retain the last recorded
            # roll for each stage of the current life, without drawing new RNG.
            buckets = {}
            for event in payload.get("event_log", []):
                if event.get("event") == "returned_to_anchor":
                    buckets.clear()
                elif event.get("event") == "stage_entered":
                    buckets[event["stage"]] = [event["encounter"]] if event.get("encounter") else []
            buckets[stage.id] = [selected] if selected else []
            run_payload.setdefault("stage_buckets", buckets)
            completed = [
                a.id for earlier in stages[:index] for a in earlier.guaranteed_actions
            ] + [a.id for a in stage.guaranteed_actions if a.id not in run_payload["action_queue"]]
            run_payload.setdefault("completed_story_actions", completed)
            if stage.guaranteed_actions[-1].id in completed and index + 1 < len(stages):
                payload["unlocked_stage"] = max(payload["unlocked_stage"], index + 1)
        run = RunState(**run_payload)
        selected_config = config or GameConfig()
        for track in ("regular_xp", "dimensional_xp"):
            if set(payload[track]) != set(selected_config.disciplines):
                raise ValueError("save disciplines do not match")
        if version < 5:
            templates = {item.id: item for item in soulbound_items}
            for saved_item in payload.get("summoned_items", {}).values():
                template = templates.get(saved_item["template_id"])
                if template is None:
                    raise ValueError("unknown saved item template")
                saved_item.setdefault("slot", template.slot)
                mapped = legacy_attributes.get(saved_item["discipline"], saved_item["discipline"])
                if saved_item["template_id"] == "old_gauntlet":
                    mapped = "strength"
                saved_item["discipline"] = mapped
                saved_item["base_stats"] = {
                    (mapped if key in ("insight", "resonance") or saved_item["template_id"] == "old_gauntlet"
                     else key): value for key, value in saved_item["base_stats"].items()
                }
        game = cls(
            config=selected_config,
            stages=stages,
            soulbound_items=soulbound_items,
            seed=payload["seed"],
            world_seconds=payload["world_seconds"],
            simulation_seconds=payload.get("simulation_seconds", payload["world_seconds"]),
            clone_shards_generated=payload.get("clone_shards_generated", 0.0),
            life_count=payload["life_count"],
            current_run=run,
            regular_xp=dict(payload["regular_xp"]),
            dimensional_xp=dict(payload["dimensional_xp"]),
            journal={key: JournalEntry(**value) for key, value in payload["journal"].items()},
            journal_lore=set(payload["journal_lore"]),
            unlocked_stage=payload["unlocked_stage"],
            shards=payload["shards"],
            owned_items=list(payload["owned_items"]),
            summoned_items={key: SummonedItem(**value) for key, value in payload.get("summoned_items", {}).items()},
            summon_progress={key: SummonProgress(**value) for key, value in payload.get("summon_progress", {}).items()},
            completed_stages=list(payload.get("completed_stages", [])),
            pending_summon_reviews=list(payload.get("pending_summon_reviews", [])),
            equipped_items=list(payload["equipped_items"]),
            event_log=list(payload["event_log"]),
        )
        game._rng.setstate(rng_state)
        if version < 4:
            if "summoned_items" not in payload:
                legacy_equipped = set(game.equipped_items)
                old_owned = list(game.owned_items)
                game.owned_items, game.equipped_items = [], []
                for template_id in old_owned:
                    template = game.template_by_id(template_id)
                    item = make_item(template, 1, f"summon:{len(game.summoned_items) + 1}")
                    game.summoned_items[item.id] = item
                    game.owned_items.append(item.id)
                    if template_id in legacy_equipped:
                        game.equip(item.id)
            if "completed_stages" not in payload:
                completed_actions = {e.get("action") for e in game.event_log
                                     if e.get("event") == "action_completed"}
                game.completed_stages = [stage.id for stage in stages
                                         if stage.guaranteed_actions[-1].id in completed_actions]
                for stage in stages:
                    if stage.id in game.completed_stages:
                        for rarity, cap in stage.summon_level_caps.items():
                            if cap > game.summon_progress[rarity].max_level:
                                game.raise_summon_cap(rarity, cap)
        if version < 5:
            # Old loadouts allowed multiple templates in the same slot. Keep the
            # last equipped item in each slot while preserving every owned item.
            by_slot = {game.item_by_id(i).slot: i for i in game.equipped_items}
            game.equipped_items = list(by_slot.values())
        game._validate_save()
        return game

    def _content_manifest(self) -> dict:
        return {
            "stages": [asdict(stage) for stage in self.stages],
            "items": [asdict(item) for item in self.soulbound_items],
        }

    def _validate_save(self) -> None:
        for name in ("world_seconds", "simulation_seconds", "clone_shards_generated", "shards"):
            _number(getattr(self, name), name)
        _integer(self.life_count, "life count", minimum=1)
        _integer(self.unlocked_stage, "unlocked stage")
        if self.unlocked_stage >= len(self.stages):
            raise ValueError("invalid unlocked stage")
        for track in (self.regular_xp, self.dimensional_xp):
            if set(track) != set(self.config.disciplines):
                raise ValueError("save disciplines do not match")
            for value in track.values():
                _number(value, "experience")
        known_items = set(self.summoned_items)
        if known_items != {f"summon:{i + 1}" for i in range(len(known_items))}:
            raise ValueError("invalid summoned item identifiers")
        if set(self.owned_items) != known_items or len(self.owned_items) != len(known_items):
            raise ValueError("unknown owned item")
        if (not set(self.equipped_items) <= set(self.owned_items)
                or len(set(self.equipped_items)) != len(self.equipped_items)):
            raise ValueError("invalid equipped items")
        if set(self.summon_progress) != set(RARITIES):
            raise ValueError("invalid rarity progression")
        for progress in self.summon_progress.values():
            _integer(progress.level, "summon level", minimum=1)
            _integer(progress.max_level, "summon cap", minimum=10)
            _number(progress.xp, "summon XP")
            expected = SummonProgress(xp=progress.xp, max_level=progress.max_level)
            update_level(expected, self.config.summon_xp_base, self.config.summon_xp_growth)
            if progress.level != expected.level:
                raise ValueError("summon level disagrees with its XP or cap")
        equipped_slots = [self.item_by_id(i).slot for i in self.equipped_items]
        if len(equipped_slots) != len(set(equipped_slots)):
            raise ValueError("multiple equipped items in the same slot")
        if (len(self.pending_summon_reviews) != len(set(self.pending_summon_reviews))
                or not set(self.pending_summon_reviews) <= known_items):
            raise ValueError("invalid pending summon reviews")
        for key, item in self.summoned_items.items():
            _integer(item.level, "summoned item level", minimum=1)
            template = self.template_by_id(item.template_id)
            if key != item.id or item != make_item(template, item.level, key):
                raise ValueError("invalid rolled item")
            if item.level > self.summon_progress[item.rarity].max_level:
                raise ValueError("item exceeds its rarity cap")
        stage_ids = {stage.id for stage in self.stages}
        if (len(self.completed_stages) != len(set(self.completed_stages))
                or not set(self.completed_stages) <= stage_ids):
            raise ValueError("invalid completed stages")
        encounters = {e.id: e for stage in self.stages for e in stage.encounters}
        if not set(self.journal) <= encounters.keys() or not self.journal_lore <= encounters.keys():
            raise ValueError("unknown journal entry")
        for entry in self.journal.values():
            _integer(entry.completions, "journal completions")
            if type(entry.enabled) is not bool or type(entry.unlocked) is not bool:
                raise ValueError("invalid journal flags")
            if entry.first_seen_at is not None:
                _number(entry.first_seen_at, "journal discovery time")
        run = self.current_run
        _integer(run.stage_index, "current stage")
        if run.stage_index > self.unlocked_stage:
            raise ValueError("current stage is locked")
        _number(run.vitality, "vitality", positive=True)
        if run.vitality > self.config.starting_vitality:
            raise ValueError("vitality exceeds maximum")
        _number(run.life_seconds, "life time")
        _integer(run.completed_actions, "completed actions")
        _number(run.action_work, "action work")
        _number(run.action_seconds, "action time")
        stage = self.stages[run.stage_index]
        stage_encounters = {e.id: e for e in stage.encounters}
        if (not isinstance(run.encounter_bucket, list)
                or len(run.encounter_bucket) != len(set(run.encounter_bucket))
                or not set(run.encounter_bucket) <= stage_encounters.keys()):
            raise ValueError("invalid encounter bucket")
        if run.selected_encounter is not None and run.selected_encounter not in run.encounter_bucket:
            raise ValueError("selected encounter is absent from the bucket")
        stage_lookup = {stage.id: stage for stage in self.stages}
        for stage_id, rolled_ids in run.stage_buckets.items():
            if stage_id not in stage_lookup or not isinstance(rolled_ids, list) or len(rolled_ids) > 1:
                raise ValueError("invalid saved stage roll")
            if not set(rolled_ids) <= {e.id for e in stage_lookup[stage_id].encounters}:
                raise ValueError("unknown rolled encounter")
        if stage.id not in run.stage_buckets:
            raise ValueError("current stage has no persisted roll")
        story_ids = {a.id for stage in self.stages for a in stage.guaranteed_actions}
        if (len(run.completed_story_actions) != len(set(run.completed_story_actions))
                or not set(run.completed_story_actions) <= story_ids):
            raise ValueError("invalid completed story actions")
        for encounter_id in run.encounter_bucket:
            if encounter_id not in run.stage_buckets[stage.id]:
                entry = self.journal.get(encounter_id)
                if entry is None or not entry.unlocked:
                    raise ValueError("bucket encounter was neither rolled nor journal-unlocked")
        expected = ([a.id for a in stage.guaranteed_actions]
                    + [stage_encounters[e].action.id for e in run.encounter_bucket])
        if not any(run.action_queue == expected[i:] for i in range(len(expected) + 1)):
            raise ValueError("invalid saved action bucket")
        action = self._current_action()
        if (action is None and run.action_work != 0) or (
                action is not None and run.action_work >= action.base_seconds):
            raise ValueError("invalid saved action progress")

    def _log(self, event: str, **values: object) -> None:
        self.event_log.append({"event": event, "time": self.world_seconds, **values})


def _level_from_xp(xp: float, base: float, growth: float) -> int:
    level = 0
    required = base
    while xp >= required or math.isclose(xp, required, rel_tol=1e-12, abs_tol=1e-10):
        xp -= required
        level += 1
        required *= growth
    return level


def _time_to_level(xp: float, base: float, growth: float, rate: float) -> float:
    if rate == 0:
        return math.inf
    level = _level_from_xp(xp, base, growth)
    threshold = sum(base * growth ** i for i in range(level + 1))
    return max(0.0, threshold - xp) / rate


def _number(value: float, name: str, *, positive: bool = False, signed: bool = False) -> None:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f"{name} must be finite")
    if not signed and (value < 0 or (positive and value == 0)):
        raise ValueError(f"{name} must be {'positive' if positive else 'non-negative'}")


def _integer(value: int, name: str, *, minimum: int = 0) -> None:
    if type(value) is not int or value < minimum:
        raise ValueError(f"{name} must be an integer >= {minimum}")


def _identifier(value: str, seen: set, name: str) -> None:
    if not isinstance(value, str) or not value or value in seen:
        raise ValueError(f"{name} identifiers must be nonempty and unique")
    seen.add(value)


def _softcapped_level(level: int, softcap: float, softness: float) -> float:
    if level <= softcap:
        return float(level)
    excess = level - softcap
    return softcap + excess / (1.0 + softness * excess)


def new_demo_game(seed: int = 1) -> GameState:
    from .content import new_demo_game as create
    return create(seed)
