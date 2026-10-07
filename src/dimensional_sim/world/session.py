"""Transport-independent browser session: frame snapshots, input validation, leases.

Shared by the local HTTP adapter (browser_server.py) and the hosted web build, which
runs this module in the browser through Pyodide (world/web.py). No http, socket or
threading imports belong here; callers own any locking and should pass `now`.
"""
import time

from .animation import rotate
from .autopilot import INVENTORY_SLOTS, Expedition
from . import details, economy
from .catalog import BOONS, UNLOCKS
from .catalog import BY_ID
from .models import ChunkKey, chunk_ident, integer
from .progression import attribute_report
from .runtime import InputCommand
from .seeds import derive_seed
from .tuning import UNARMED_REACH

TICK_MS = 20
INPUT_LEASE = 0.3
MANUAL_HOLD = 2.5  # seconds of manual control before auto-pilot resumes
LOG_ENTRIES = 6


def _tile_tints(world, key, asset):
    """Per-tile region tints (generator v3 borders run through chunks): one code letter per
    tile plus a small legend, so the client can wash each tile in its own region's colour."""
    grid = world.region_grid(key) if hasattr(world, "region_grid") else None
    if grid is None:
        return None, None
    legend, rows = {}, []
    for y in range(asset.height):
        row = []
        for x in range(asset.width):
            region = grid[y][x]
            code = legend.setdefault(region.tint if region else "", "abcdefghijklmnop"[len(legend)])
            row.append(code)
        rows.append("".join(row))
    return rows, {code: tint for tint, code in legend.items() if tint}


def snapshot(game, known=(), *, paused=False, expedition=None, control="manual", debug=False, detail=False):
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
            resident.append(chunk_ident(key))
            if chunk_ident(key) not in known:
                chunks.append(_chunk_view(game.world, chunk, expedition))
    in_anchor = expedition is not None and expedition.anchor_ms is not None
    strikes = expedition.strikes if expedition is not None else {}
    targets = [] if in_anchor else [{"id": t.id, "x": t.chunk.x * w + t.x, "y": t.chunk.y * h + t.y, "hp": t.hp,
                                     "strikes": strikes.get(t.id, 0)}
               for t in game.targets.values() if chunk_ident(t.chunk) in resident]
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
        frame_extra = {"spots": [] if in_anchor else expedition.visible_spots(),
                       "target_kinds": {t["id"]: kinds.get(t["id"], "bramble_boar") for t in targets},
                       "expedition": _expedition_view(expedition, control, debug=debug, detail=detail)}
    return {**frame_extra, "world_seed": str(game.world.world_seed), "clock_ms": game.elapsed_ms,
        "movement_interval_ms": game.movement_interval_ms,
        "player": {"x": px, "y": py, "facing": p.facing, "animation": p.animation,
                   "animation_ms": p.animation_elapsed_ms * rate // 100, "active": frame.active},
        "targets": targets,
        "effects": effects, "chunks": chunks, "resident": resident,
        "minimap": game.world.minimap(center, 2), "chunk_width": w, "chunk_height": h,
        "paused": paused}


def _chunk_view(world, chunk, expedition):
    """One resident chunk the client does not have yet: tiles, collision, region tint."""
    key, a = chunk.key, chunk.asset
    region = expedition.region(key) if expedition is not None else None
    tint_rows, tint_legend = _tile_tints(world, key, a) if region is not None else (None, None)
    return {"id": chunk_ident(key), "x": key.x, "y": key.y,
            "region": region.id if region else None, "tint": region.tint if region else None,
            "tint_rows": tint_rows, "tint_legend": tint_legend,
            "width": a.width, "height": a.height, "biome": a.biome,
            "seed": derive_seed(chunk.seed, "browser-art-v1") % 2**32,
            "tiles": ["".join((obj or env).glyph for obj, env in zip(orow, erow))
                      for orow, erow in zip(a.objects, a.environment)],
            "collision": ["".join("1" if c else "0" for c in row) for row in a.collision]}


def _expedition_view(e, control, *, debug, detail):
    """HUD state of the auto-pilot: vitals, activity, log, anchor shop, meta progress."""
    in_anchor = e.anchor_ms is not None
    unarmed_target = e.unarmed_target() if control == "manual" and not in_anchor else None
    return {"mode": e.mode(), "activity": e.activity(),
            "goal": None if e.goal is None else {"x": e.goal["x"], "y": e.goal["y"], "kind": e.goal["kind"]},
            "attributes": attribute_report(e.regular, e.dimensional),
            "log": [dict(entry) for entry in e.log[-LOG_ENTRIES:]],
            "vitals": e.vitals(), "inventory": e.inventory_rows(),
            "equipped": dict(e.equipped),
            "inventory_slots": INVENTORY_SLOTS, "life": e.life, "total_ms": e.total_ms,
            "depth": e.depth, "best_depth": e.best_depth,
            "dust": e.dust,
            "anchor_space": None if not in_anchor else {
                "remaining_ms": e.anchor_ms, "waiting": e.anchor_wait,
                "offer": {i: economy.offer_value(i, n) for i, n in e.inventory.items()},
                "ash_if_burned": economy.rebirth_ash(e.inventory, e.depth)},
            "punch_damage": e.punch_damage(), "report": e.report,
            "anchor": {"x": e.anchor[0], "y": e.anchor[1]},
            "skills": sorted(e.skills), "control": control,
            "attack_radius": UNARMED_REACH,
            "auto_target": unarmed_target[1] if unarmed_target else None,
            "skill_slots": [{"name": "Empty", "state": "locked"} for _ in range(3)],
            "prologue": e.prologue(),
            "region": _region_view(e),
            "meta": _meta_view(e),
            "shop": e.anchor_offers() if in_anchor else None,
            "stats": dict(e.stats),
            "debug": e.debug_info() if debug else None,
            "detail": details.detail(e) if detail else None,
            "bounty": [{"id": i, "name": BY_ID[i].name, "spawned": n, "limit": limit}
                       for i, n, limit in e.bounty()]}


def _meta_view(e):
    """Progress that survives death: currencies, unlocks, mastery, Journal controls, boons."""
    return {"dust": e.dust, "ash": e.ash, "blessing": e.blessing,
            "unlocked": [{"id": u, "name": UNLOCKS[u].name} for u in sorted(e.unlocked)],
            "mastery": dict(e.mastery),
            "knowledge": sorted(e.knowledge), "recipes": sorted(e.recipes),
            "journal": [{"id": ident, "name": BY_ID[ident].name, "mastery": level,
                         "enabled": ident not in e.journal_disabled,
                         "mode": e.journal_favor.get(ident, "normal")}
                        for ident, level in sorted(e.mastery.items()) if level >= 2],
            "boon": None if e.boon is None else BOONS[e.boon].name,
            "boon_next": None if e.boon_next is None else BOONS[e.boon_next].name}


def _region_view(expedition):
    region = expedition.region(expedition.game.player.chunk)
    return None if region is None else {"id": region.id, "name": region.name}


def validate_input(data):
    base = {"move", "attack", "paused", "known"}
    if type(data) is not dict or not base <= set(data) or not set(data) <= base | {"action", "debug", "detail", "control", "interact"}:
        raise ValueError("invalid input fields")
    if "control" in data and data["control"] not in ("auto", "active"):
        raise ValueError("invalid control mode")
    if "interact" in data and type(data["interact"]) is not bool:
        raise ValueError("interact must be boolean")
    for flag in ("debug", "detail"):
        if flag in data and type(data[flag]) is not bool:
            raise ValueError(f"{flag} must be boolean")
    if "action" in data:
        action = data["action"]
        if type(action) is not dict or action.get("type") not in Expedition.ANCHOR_ACTIONS:
            raise ValueError("invalid anchor action")
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
        self.active = False
        self.debug = False
        self.detail = False

    @property
    def game(self):
        """The current life's simulation (a new life replaces the Exploration)."""
        return self.expedition.game if self.expedition is not None else self._game

    def _manual_allowed(self):
        return self.expedition is None or self.expedition.manual_control

    def _control(self, now):
        if self.expedition is None:
            return "manual"
        if self.active:
            return "manual"
        if not self.expedition.manual_control:
            return "auto"
        return "manual" if now < self.manual_until else "auto"

    def _frame(self, known=(), now=None):
        control = self._control(time.monotonic() if now is None else now)
        return snapshot(self.game, known, paused=self.paused, expedition=self.expedition, control=control,
                        debug=self.debug and self.expedition is not None,
                        detail=self.detail and self.expedition is not None)

    def input(self, data, now):
        command, paused, known = validate_input(data)
        with self.lock:
            if self.expedition is not None and "control" in data:
                requested = data["control"] == "active"
                if requested and (self.expedition.anchor_ms is not None or self.expedition.in_prologue):
                    requested = False
                if requested != self.active:
                    self.command = InputCommand()
                    if requested:
                        self.expedition.interrupt()
                    self.active = requested
                    self.manual_until = float("-inf")
            self.debug = data.get("debug", False)
            self.detail = data.get("detail", False)
            action_error = None
            if "action" in data:
                if self.expedition is None:
                    raise ValueError("anchor action requires an expedition")
                try:
                    self.expedition.anchor_action(data["action"])
                except ValueError as exc:   # a refused purchase must not break the connection
                    action_error = str(exc)
            if not self.active and not self._manual_allowed():
                command = InputCommand()  # locked skill: the auto-pilot steers
            if self.expedition is not None and self.expedition.anchor_ms is not None:
                command = InputCommand()
                self.active = False
            self.command = InputCommand() if paused else command
            self.paused, self.input_time = paused, now
            if self.command.move or self.command.attack:
                if self.expedition is not None and not self.active and now >= self.manual_until:
                    self.expedition.interrupt()
                if not self.active:
                    self.manual_until = now + MANUAL_HOLD
            if self.active and data.get("interact"):
                self.expedition.begin_interaction()
            if self.expedition is None:
                # Applying an edge at zero duration preserves even brief attack presses.
                self.game.advance(0, self.command)
            elif self.active or now < self.manual_until:
                self.expedition.advance_manual(0, self.command, auto_attack=self.active)
            frame = self._frame(known, now)
            if frame.get("expedition") is not None:
                frame["expedition"]["action_error"] = action_error
            return frame

    def step(self, now):
        """One fixed TICK_MS tick (local server)."""
        with self.lock:
            if not self.paused:
                self._drive(TICK_MS, now, allow_prayer=True)

    def advance_ms(self, ms, now, *, allow_prayer=True):
        """Advance by real elapsed milliseconds (hosted mode; timers may be throttled).
        The auto-pilot is partition-independent, so one bulk call equals many ticks."""
        integer(ms, "elapsed milliseconds", 0)
        with self.lock:
            if not self.paused and ms:
                self._drive(ms, now, allow_prayer=allow_prayer)

    def _drive(self, ms, now, *, allow_prayer):
        """Auto-pilot unless the player holds control; held input expires after INPUT_LEASE."""
        expedition = self.expedition
        if expedition is not None and (not self.active and now >= self.manual_until
                                       or expedition.anchor_ms is not None):
            expedition.advance(ms, allow_prayer=allow_prayer)
        else:
            command = self.command if now - self.input_time <= INPUT_LEASE else InputCommand()
            if expedition is None:
                self.game.advance(ms, command)
                return
            expedition.advance_manual(ms, command, auto_attack=self.active)
        if expedition.anchor_ms is not None:
            self.active = False   # control returns to the auto-pilot at the anchor

    def state(self, now=None):
        with self.lock:
            return self._frame(now=now)
