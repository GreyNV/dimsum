"""Attribute progression for the world, reusing the idle simulator's documented rules.

Each attribute has two tracks (design: dimensional-system.md, core-loop.md):
regular XP belongs to the current life and resets at the anchor; dimensional XP
persists. Levels, softcap and speed come from core.GameConfig so the idle sim and
the world agree. Speed is rounded to an integer per-mille once, so durations and
drain rates stay exact integers (partition-independent, platform-stable saves).
"""
from ..core import GameConfig, _level_from_xp, _softcapped_level
from .encounters import ATTRIBUTES

CONFIG = GameConfig()
DIMENSIONAL_DIVISOR = 5  # dimensional XP gained = regular XP gained // 5 (20%)


def regular_level(xp):
    return _level_from_xp(xp, CONFIG.regular_xp_base, CONFIG.regular_xp_growth)


def dimensional_level(xp):
    return _level_from_xp(xp, CONFIG.dimensional_xp_base, CONFIG.dimensional_xp_growth)


def _progress(xp, base, growth):
    level, required = 0, base
    while xp >= required:
        xp -= required
        level += 1
        required *= growth
    return level, int(xp), int(round(required))


def speed_permille(regular_xp, dimensional_xp):
    """1000 = base speed. Same formula as GameState.speed_multiplier (no items yet)."""
    soft = CONFIG.base_softcap
    value = (1.0 + CONFIG.regular_speed_per_level * _softcapped_level(
                 regular_level(regular_xp), soft, CONFIG.softcap_softness)
             + CONFIG.dimensional_speed_per_level * _softcapped_level(
                 dimensional_level(dimensional_xp), soft, CONFIG.softcap_softness))
    return int(round(value * 1000))


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
