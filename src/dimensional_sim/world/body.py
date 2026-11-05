"""The avatar's round body: where in and around its cell the body actually is (docs/design/MOVEMENT.md).

WHAT: a sub-tile offset (`ox`, `oy` in 1/SUB of a tile from the cell's centre) layered on the
cell-stepping simulation. The cell stays the rule for everything (collision, reach, spots,
saves of the cell); the body is how it gets there:
- a step moves the cell at once and the body travels after it, a stride per BODY_TICK_MS,
  so the drawn figure moves continuously; walking, it aims half a step behind its cell, so a
  staircase of steps (east, north, east...) is walked as the straight line through their midpoints;
- the body is a circle of BODY_RADIUS: it never overlaps a blocked tile, so passing a trunk's
  corner it swings round it (an arc), and walking into a wall it leans on its surface;
- standing still it settles back to the centre.
WHY: straight cell-to-cell glides cut through trunk corners and stopped dead at cell centres.
NEVER: decide a rule from the body. Integer only; deterministic in time, like the rest.
TESTS: tests/test_world_body.py.
"""
from math import isqrt

SUB = 16              # sub-units per tile
BODY_RADIUS = 5       # the body's radius in sub-units (about a third of a tile)
BODY_TICK_MS = 8      # the body strides this often: one sub-unit, more when behind (a tile in about 128 ms)
CATCH_UP = 12         # one more sub-unit per stride for every CATCH_UP it is behind its target
LEAN = SUB // 2 - BODY_RADIUS   # how far a body pressed against a wall sits off its centre
MAX_OFFSET = 2 * SUB  # farther than this behind its cell (a respawn, a load) the body jumps


def _toward(value, target):
    return value + (target > value) - (target < value)


def push_out(ox, oy, walls):
    """The body moved out of every blocked tile around its cell. `walls` holds (dx, dy) of the
    blocked neighbours (-1..1); each is the square [dx*SUB-SUB/2, dx*SUB+SUB/2] (same for y)."""
    half = SUB // 2
    for _ in range(3):   # a corner can push twice; settle in a few passes
        moved = False
        for dx, dy in sorted(walls):
            x0, x1, y0, y1 = dx * SUB - half, dx * SUB + half, dy * SUB - half, dy * SUB + half
            nx, ny = min(max(ox, x0), x1), min(max(oy, y0), y1)
            ex, ey = ox - nx, oy - ny
            if ex * ex + ey * ey >= BODY_RADIUS * BODY_RADIUS:
                continue
            if ex == 0 and ey == 0:   # the centre inside a wall (a teleport): push straight back
                ex, ey = -dx, -dy
            if abs(ex) >= abs(ey):
                need = isqrt(max(0, BODY_RADIUS * BODY_RADIUS - ey * ey - 1)) + 1
                ox = nx + (need if ex > 0 else -need)
            else:
                need = isqrt(max(0, BODY_RADIUS * BODY_RADIUS - ex * ex - 1)) + 1
                oy = ny + (need if ey > 0 else -need)
            moved = True
        if not moved:
            break
    return ox, oy


def body_target(lean, walls, trail=None):
    """Where the body heads: leaning on the wall it pushes against; while walking, half a step
    behind its cell (`trail`, the last step), so a staircase of steps is walked as the line
    through their midpoints; else the centre."""
    if lean is not None:
        dx, dy = lean
        return push_out(dx * LEAN, dy * LEAN, walls)
    if trail is not None and trail != (0, 0):
        return push_out(-trail[0] * SUB // 2, -trail[1] * SUB // 2, walls)
    return 0, 0


def _stride(ox, oy, tx, ty):
    """One tick toward the target in a straight line (not axis by axis): a run of quick
    turns (east, north, east...) becomes one smooth diagonal instead of a staircase. Faster the
    farther behind it is (CATCH_UP), so it never falls behind a quick walker."""
    dx, dy = tx - ox, ty - oy
    m = max(abs(dx), abs(dy))
    s = min(m, 1 + m // CATCH_UP)

    def part(d):
        q = abs(d) * s
        return (q + m // 2) // m * (1 if d > 0 else -1) if d else 0
    return ox + part(dx), oy + part(dy)


def ease(ox, oy, carry_ms, ms, target, walls):
    """Move the body toward `target` for `ms` (plus `carry_ms` left from before), a stride per
    BODY_TICK_MS, staying out of the walls. Returns (ox, oy, carry_ms)."""
    total = carry_ms + ms
    ticks, carry = divmod(total, BODY_TICK_MS)
    tx, ty = target
    for _ in range(ticks):
        if (ox, oy) == (tx, ty):
            return ox, oy, 0
        nx, ny = push_out(*_stride(ox, oy, tx, ty), walls)
        if (nx, ny) == (ox, oy):   # pushed straight back by a corner: step round it axis by axis
            nx, ny = push_out(_toward(ox, tx), oy, walls)
            if (nx, ny) == (ox, oy):
                nx, ny = push_out(ox, _toward(oy, ty), walls)
        ox, oy = nx, ny
    return ox, oy, carry if (ox, oy) != (tx, ty) else 0
