"""Attribute progression for the world: levels, softcap, speed and punch strength.

Each attribute has two tracks (design: dimensional-system.md, core-loop.md):
regular XP belongs to the current life and resets at the anchor; dimensional XP
persists. The curve numbers match the Phase One idle simulator's GameConfig
defaults (tests/test_world_autopilot.py guards that they agree), but the world owns
its copy so it does not depend on the idle simulator. Speed is rounded to an integer
per-mille once, so durations and drain rates stay exact integers
(partition-independent, platform-stable saves).
"""
from dataclasses import dataclass
import math

from .catalog import ATTRIBUTES


@dataclass(frozen=True)
class ProgressionConfig:
    regular_xp_base: float = 100.0
    regular_xp_growth: float = 1.15
    dimensional_xp_base: float = 100.0
    dimensional_xp_growth: float = 1.35
    regular_speed_per_level: float = 0.10
    dimensional_speed_per_level: float = 0.01
    softcap_softness: float = 0.08
    base_softcap: float = 10.0
    offline_efficiency: float = 0.65     # share of real time away that is simulated (hosted build)


CONFIG = ProgressionConfig()
DIMENSIONAL_DIVISOR = 5  # dimensional XP gained = regular XP gained // 5 (20%)


def level_from_xp(xp, base, growth):
    """Levels reached with `xp` when level n costs base * growth**n."""
    level = 0
    required = base
    while xp >= required or math.isclose(xp, required, rel_tol=1e-12, abs_tol=1e-10):
        xp -= required
        level += 1
        required *= growth
    return level


def softcapped_level(level, softcap=CONFIG.base_softcap, softness=CONFIG.softcap_softness):
    """Levels past the softcap count for progressively less."""
    if level <= softcap:
        return float(level)
    excess = level - softcap
    return softcap + excess / (1.0 + softness * excess)


def regular_level(xp):
    return level_from_xp(xp, CONFIG.regular_xp_base, CONFIG.regular_xp_growth)


def dimensional_level(xp):
    return level_from_xp(xp, CONFIG.dimensional_xp_base, CONFIG.dimensional_xp_growth)


def _progress(xp, base, growth):
    level, required = 0, base
    while xp >= required:
        xp -= required
        level += 1
        required *= growth
    return level, int(xp), int(round(required))


def speed_permille(regular_xp, dimensional_xp):
    """1000 = base speed. Same formula as the idle sim's GameState.speed_multiplier (no items)."""
    value = (1.0 + CONFIG.regular_speed_per_level * softcapped_level(regular_level(regular_xp))
             + CONFIG.dimensional_speed_per_level * softcapped_level(dimensional_level(dimensional_xp)))
    return int(round(value * 1000))


def combined_level(regular_xp, dimensional_xp):
    """Softcapped regular level + softcapped dimensional level (drives punch damage)."""
    return softcapped_level(regular_level(regular_xp)) + softcapped_level(dimensional_level(dimensional_xp))


def scaled_ms(base_ms, permille):
    """Duration at a speed: ceil(base / speed), never below 1 ms."""
    return max(1, -(-base_ms * 1000 // permille))


def attribute_report(regular, dimensional):
    """Presentation rows for every attribute (levels, progress, speed)."""
    rows = {}
    for name in ATTRIBUTES:
        level, into, need = _progress(regular[name], CONFIG.regular_xp_base, CONFIG.regular_xp_growth)
        dim, dim_into, dim_need = _progress(dimensional[name], CONFIG.dimensional_xp_base,
                                            CONFIG.dimensional_xp_growth)
        rows[name] = {"level": level, "xp": regular[name], "into": into, "next": need,
                      "dim_level": dim, "dim_xp": dimensional[name], "dim_into": dim_into,
                      "dim_next": dim_need, "speed": speed_permille(regular[name], dimensional[name])}
    return rows
