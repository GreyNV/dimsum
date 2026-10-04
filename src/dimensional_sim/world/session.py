"""Transport-independent browser session: frame snapshots, input validation, leases.

Shared by the local HTTP adapter (browser_server.py) and the hosted web build, which
runs this module in the browser through Pyodide (world/web.py). No http, socket or
threading imports belong here; callers own any locking and should pass `now`.
"""
import time

from .animation import rotate
from .autopilot import INVENTORY_SLOTS
from .encounters import BY_ID
from .models import ChunkKey, fields, integer
from .progression import attribute_report
from .runtime import InputCommand
from .seeds import derive_seed

TICK_MS = 20
INPUT_LEASE = 0.3
MANUAL_HOLD = 2.5  # seconds of manual control before auto-pilot resumes
LOG_ENTRIES = 6


def chunk_id(key):
    return f"{key.dimension}:{key.x}:{key.y}"


def snapshot(game, known=(), *, paused=False, expedition=None, control="manual"):
    """Read-only transport projection: no get/stream/generate or simulation calls."""
    asset = game.current_chunk().asset
    w, h = asset.width, asset.height
    center = game.player.chunk
    chunks, resident = [], []
    for y in range(center.y - 1, center.y + 2):
        for x in range(center.x - 1, center.x + 2):
            key = ChunkKey(center.dimension, x, y)
            chunk = game.world.peek(key)
            if chunk is None:
                continue
            identity = chunk_id(key)
            resident.append(identity)
            if identity in known:
                continue
            a = chunk.asset
            chunks.append({"id": identity, "x": x, "y": y,
                "width": a.width, "height": a.height, "biome": a.biome,
                "seed": derive_seed(chunk.seed, "browser-art-v1") % 2**32,
                "tiles": ["".join((obj or env).glyph for obj, env in zip(orow, erow))
                          for orow, erow in zip(a.objects, a.environment)],
                "collision": ["".join("1" if c else "0" for c in row) for row in a.collision]})
    targets = [{"id": t.id, "x": t.chunk.x * w + t.x, "y": t.chunk.y * h + t.y, "hp": t.hp}
               for t in game.targets.values() if chunk_id(t.chunk) in resident]
    p = game.player
    rate = game.attack_rate_percent if p.animation == "attack" else game.animation_rate_percent
    frame = game.animations[p.animation].sample(p.animation_elapsed_ms, rate)
    px, py = p.chunk.x * w + p.x, p.chunk.y * h + p.y
    effects = []
    if frame.active and frame.effect_origin is not None:
        dx, dy = rotate(frame.effect_origin, p.facing)
        effects.append({"x": px + dx, "y": py + dy})
    frame_extra = {}
    if expedition is not None:
        kinds = expedition.target_kinds()
        frame_extra = {"spots": expedition.visible_spots(), "target_kinds": {
            t["id"]: kinds.get(t["id"], "bramble_boar") for t in targets},
            "expedition": {"mode": expedition.mode(), "activity": expedition.activity(),
                "goal": None if expedition.goal is None else {
                    "x": expedition.goal["x"], "y": expedition.goal["y"], "kind": expedition.goal["kind"]},
                "attributes": attribute_report(expedition.regular, expedition.dimensional),
                "log": [dict(e) for e in expedition.log[-LOG_ENTRIES:]],
                "vitals": expedition.vitals(), "inventory": expedition.inventory_rows(),
                "inventory_slots": INVENTORY_SLOTS, "life": expedition.life, "total_ms": expedition.total_ms,
                "depth": expedition.depth, "best_depth": expedition.best_depth,
                "punch_damage": expedition.punch_damage(), "report": expedition.report,
                "anchor": {"x": expedition.anchor[0], "y": expedition.anchor[1]},
                "skills": sorted(expedition.skills), "control": control,
                "prologue": expedition.prologue(),
                "bounty": [{"id": i, "name": BY_ID[i].name, "spawned": n, "limit": limit}
                           for i, n, limit in expedition.bounty()]}}
    return {**frame_extra, "world_seed": str(game.world.world_seed), "clock_ms": game.elapsed_ms,
        "movement_interval_ms": game.movement_interval_ms,
        "player": {"x": px, "y": py, "facing": p.facing, "animation": p.animation,
                   "animation_ms": p.animation_elapsed_ms * rate // 100, "active": frame.active},
        "targets": targets,
        "effects": effects, "chunks": chunks, "resident": resident,
        "minimap": game.world.minimap(center, 2), "chunk_width": w, "chunk_height": h,
        "paused": paused}


def validate_input(data):
    fields(data, ("move", "attack", "paused", "known"))
    command = InputCommand(data["move"], data["attack"])
    if type(data["paused"]) is not bool:
        raise ValueError("paused must be boolean")
    known = data["known"]
    if (type(known) is not list or len(known) > 25 or
            any(type(k) is not str or len(k) > 200 for k in known) or len(set(known)) != len(known)):
        raise ValueError("known must contain at most 25 unique chunk IDs")
    return command, data["paused"], tuple(known)


class _NoLock:
    """Single-threaded default; the HTTP adapter swaps in a real lock."""
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class BrowserSession:
    """Input validation is atomic. step(now) allows deterministic lease tests.

    With an expedition, the auto-pilot drives the character. Player move/attack
    input is ignored until the "take_control" skill is unlocked; then input takes
    over and the auto-pilot resumes MANUAL_HOLD seconds after the last command.
    Without an expedition the session is the original manual adapter.
    """
    def __init__(self, game, expedition=None, *, start_paused=False):
        if game.world.cache_limit < 9:
            raise ValueError("browser view requires cache-limit >= 9")
        if expedition is not None and expedition.game is not game:
            raise ValueError("expedition must drive this game")
        self._game = game
        self.expedition = expedition
        game.step_on_press = True  # manual taps move one cell; holds repeat
        self.lock = _NoLock()
        self.command = InputCommand()
        self.paused = start_paused
        self.input_time = float("-inf")
        self.manual_until = float("-inf")

    @property
    def game(self):
        """The current life's simulation (a new life replaces the Exploration)."""
        return self.expedition.game if self.expedition is not None else self._game

    def _manual_allowed(self):
        return self.expedition is None or self.expedition.manual_control

    def _control(self, now):
        if self.expedition is None:
            return "manual"
        if not self.expedition.manual_control:
            return "auto"
        return "manual" if now < self.manual_until else "auto"

    def _frame(self, known=(), now=None):
        control = self._control(time.monotonic() if now is None else now)
        return snapshot(self.game, known, paused=self.paused, expedition=self.expedition, control=control)

    def input(self, data, now):
        command, paused, known = validate_input(data)
        with self.lock:
            if not self._manual_allowed():
                command = InputCommand()  # locked skill: the auto-pilot steers
            self.command = InputCommand() if paused else command
            self.paused, self.input_time = paused, now
            if self.command.move or self.command.attack:
                if self.expedition is not None and now >= self.manual_until:
                    self.expedition.interrupt()
                self.manual_until = now + MANUAL_HOLD
            if self.expedition is None or now < self.manual_until:
                # Applying an edge at zero duration preserves even brief attack presses.
                self.game.advance(0, self.command)
            return self._frame(known, now)

    def step(self, now):
        with self.lock:
            if self.paused:
                return
            if self.expedition is not None and now >= self.manual_until:
                self.expedition.advance(TICK_MS)
                return
            command = self.command if now - self.input_time <= INPUT_LEASE else InputCommand()
            self.game.advance(TICK_MS, command)

    def advance_ms(self, ms, now):
        """Advance by real elapsed milliseconds (hosted mode; timers may be throttled).
        The auto-pilot is partition-independent, so one bulk call equals many ticks."""
        integer(ms, "elapsed milliseconds", 0)
        with self.lock:
            if self.paused or ms == 0:
                return
            if self.expedition is not None and now >= self.manual_until:
                self.expedition.advance(ms)
                return
            command = self.command if now - self.input_time <= INPUT_LEASE else InputCommand()
            self.game.advance(ms, command)

    def state(self, now=None):
        with self.lock:
            return self._frame(now=now)
