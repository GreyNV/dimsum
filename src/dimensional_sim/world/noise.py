"""Integer lattice noise shared by every generator layer (open terrain, regions, rivers).

A lattice point's value is derive_seed(seed, label, qx, qy) % 101. Between points the value is
blended bilinearly, or with smoothstep weights for rounder shapes. Everything is integer maths,
so every platform and every access order agrees. These functions are pinned: worlds of every
generator version replay through them, so their results must never change. Only their cost may
change (tests/test_world_noise.py pins sample values).
"""
from functools import lru_cache

from .seeds import derive_seed


@lru_cache(maxsize=65536)
def lattice(seed, label, x, y):
    """The value 0..100 at one lattice point."""
    return derive_seed(seed, label, x, y) % 101


@lru_cache(maxsize=65536)
def corners(seed, label, qx, qy):
    """The four lattice values around cell (qx, qy): one cache hit instead of four."""
    return (lattice(seed, label, qx, qy), lattice(seed, label, qx + 1, qy),
            lattice(seed, label, qx, qy + 1), lattice(seed, label, qx + 1, qy + 1))


def bilinear(seed, x, y, scale, label, unit=1):
    """Bilinear lattice noise in 0..100*unit (floored), including negative coordinates."""
    qx, rx = divmod(x, scale)
    qy, ry = divmod(y, scale)
    a, b, c, d = corners(seed, label, qx, qy)
    return ((a * (scale - rx) + b * rx) * (scale - ry) +
            (c * (scale - rx) + d * rx) * ry) * unit // (scale * scale)


def smooth(seed, x, y, scale, label):
    """Value noise in 0..100 with smoothstep blending: round, organic blobs instead of the
    diamond lattice that bilinear blending shows at large scales."""
    qx, rx = divmod(x, scale)
    qy, ry = divmod(y, scale)
    cube = scale ** 3
    wx = rx * rx * (3 * scale - 2 * rx)          # smoothstep(rx / scale) * scale^3
    wy = ry * ry * (3 * scale - 2 * ry)
    a, b, c, d = corners(seed, label, qx, qy)
    top = a * (cube - wx) + b * wx
    bottom = c * (cube - wx) + d * wx
    return (top * (cube - wy) + bottom * wy) // (cube * cube)
