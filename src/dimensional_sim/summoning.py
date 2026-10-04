"""Persistent rolled items and independent rarity progression."""
from dataclasses import dataclass, field
import math

RARITIES = ("common", "uncommon", "rare", "legendary")


@dataclass
class SummonProgress:
    level: int = 1
    xp: float = 0.0
    max_level: int = 10


@dataclass(frozen=True)
class SummonedItem:
    id: str
    template_id: str
    name: str
    rarity: str
    level: int
    discipline: str
    slot: str
    base_stats: dict[str, float] = field(default_factory=dict)
    speed_bonus: float = 0.0
    softcap_bonus: float = 0.0
    shard_rate_bonus: float = 0.0


def level_range(progress: SummonProgress) -> tuple[int, int]:
    # Inclusive endpoints follow the design examples literally: 1..10 and
    # 90..100. The latter has eleven possible integer values.
    upper = min(progress.max_level, max(10, progress.level))
    return max(1, upper - 10), upper


def update_level(progress: SummonProgress, xp_base: float, xp_growth: float) -> None:
    remaining = progress.xp
    level, needed = 1, xp_base
    while level < progress.max_level and (
        remaining >= needed or math.isclose(remaining, needed, rel_tol=1e-12)
    ):
        remaining -= needed
        level += 1
        needed *= xp_growth
    progress.level = level


def roll_item(template, progress: SummonProgress, rng, instance_id: str) -> SummonedItem:
    low, high = level_range(progress)
    level = rng.randint(low, high)
    return make_item(template, level, instance_id)


def make_item(template, level: int, instance_id: str) -> SummonedItem:
    common = template.rarity == "common"
    return SummonedItem(
        id=instance_id, template_id=template.id, name=template.name,
        rarity=template.rarity, level=level, discipline=template.discipline, slot=template.slot,
        base_stats={template.discipline: level * template.stat_per_level},
        speed_bonus=0.0 if common else template.speed_bonus,
        softcap_bonus=0.0 if common else template.softcap_bonus,
        shard_rate_bonus=0.0 if common else template.shard_rate_bonus,
    )
