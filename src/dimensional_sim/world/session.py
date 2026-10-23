"""Transport-independent browser session: frame snapshots, input validation, leases.

Shared by the local HTTP adapter (browser_server.py) and the hosted web build, which
runs this module in the browser through Pyodide (world/web.py). No http, socket or
threading imports belong here; callers own any locking and should pass `now`.
"""

from .animation import rotate
from .autopilot import INVENTORY_SLOTS, Expedition
from .autopilot.constants import CONTACT_COOLDOWN_MS, POSSESS_COOLDOWN_MS, POSSESS_SPEED_PERCENT
from . import details
from .autopilot.ecology import cell_of
from .catalog import BY_ID, DEFAULT_TREES, ENEMIES, ITEMS, REGION_TREES, TREE_KINDS, UNLOCKS, rarity_glint
from .models import ChunkKey, chunk_ident, integer
from .progression import attribute_report
from .runtime import InputCommand
from .seeds import derive_seed

TICK_MS = 20
INPUT_LEASE = 0.3
LOG_ENTRIES = 6
# The minimap shows exactly the loaded 3x3 chunks around the avatar: what is on it is what is
# simulated, so a hunter that leaves the minimap is unloaded (combat._unload_far_enemies).
MINIMAP_RADIUS = 1
ITEM_COLORS = {item.id: item.color for item in ITEMS.values()}   # reward popups and HUD text
ITEM_GLINTS = {item.id: glint for item in ITEMS.values() if (glint := rarity_glint(item.rarity))}  # reveal burst


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


TREE_LETTERS = {kind: kind[0] if kind != "old" else "m" for kind in TREE_KINDS}   # o p b d m
if len(set(TREE_LETTERS.values())) != len(TREE_LETTERS):
    raise ValueError("tree kinds need distinct letters")


def _tree_kinds(world, key, asset, chunk_seed, fallback):
    """One letter per tile: the kind of tree on each "T" cell ("." elsewhere), from the tile's
    region tree mix (catalog.REGION_TREES) and the chunk seed - stable for the world."""
    grid = world.region_grid(key) if hasattr(world, "region_grid") else None
    rows = []
    for y in range(asset.height):
        row = []
        for x in range(asset.width):
            obj = asset.objects[y][x]
            if (obj or asset.environment[y][x]).glyph != "T":
                row.append(".")
                continue
            region = grid[y][x] if grid is not None else fallback
            mix = REGION_TREES.get(region.id, DEFAULT_TREES) if region is not None else DEFAULT_TREES
            roll = derive_seed(chunk_seed, "tree-kind-v1", x, y) % sum(w for _, w in mix)
            for kind, weight in mix:
                if roll < weight:
                    row.append(TREE_LETTERS[kind])
                    break
                roll -= weight
        rows.append("".join(row))
    return rows


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
    in_anchor = expedition is not None and expedition.anchor_ms is not None   # between lives (contact keeps the world)
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
        for t in targets:   # how to draw and name each enemy (catalog EnemyDef)
            enemy = ENEMIES[BY_ID[kinds[t["id"]]].enemy]
            t["name"], t["sprite"], t["sound_profile"] = enemy.name, enemy.sprite, enemy.sound_profile
            t["hunting"] = expedition.hunting.get(t["id"], {}).get("mode")   # "hunt" | "flee" | None
        frame_extra = {"spots": [] if in_anchor else expedition.visible_spots(),
                       "target_kinds": {t["id"]: kinds[t["id"]] for t in targets},
                       "expedition": _expedition_view(expedition, control, debug=debug, detail=detail)}
    minimap = game.world.minimap(center, MINIMAP_RADIUS)
    fog = {}
    for entry in minimap:
        key = ChunkKey(entry["dimension"], entry["x"], entry["y"])
        rows = game.visibility_rows(key)
        if rows is not None:
            fog[f"{key.x}:{key.y}"] = rows
    return {**frame_extra, "world_seed": str(game.world.world_seed), "clock_ms": game.elapsed_ms,
        "movement_interval_ms": game.step_interval_ms,
        "player": {"x": px, "y": py, "facing": p.facing, "animation": p.animation,
                   "animation_ms": p.animation_elapsed_ms * rate // 100, "active": frame.active},
        "targets": targets,
        "effects": effects, "chunks": chunks, "resident": resident,
        "minimap": minimap, "fog": fog, "chunk_width": w, "chunk_height": h,
        "paused": paused}


def _chunk_view(world, chunk, expedition):
    """One resident chunk the client does not have yet: tiles, collision, region tint."""
    key, a = chunk.key, chunk.asset
    region = expedition.region(key) if expedition is not None else None
    tint_rows, tint_legend = _tile_tints(world, key, a) if region is not None else (None, None)
    return {"id": chunk_ident(key), "x": key.x, "y": key.y,
            "region": region.id if region else None, "tint": region.tint if region else None,
            "tint_rows": tint_rows, "tint_legend": tint_legend,
            "trees": _tree_kinds(world, key, a, chunk.seed, region),
            "width": a.width, "height": a.height, "biome": a.biome,
            "seed": derive_seed(chunk.seed, "browser-art-v1") % 2**32,
            "tiles": ["".join((obj or env).glyph for obj, env in zip(orow, erow))
                      for orow, erow in zip(a.objects, a.environment)],
            "collision": ["".join("1" if c else "0" for c in row) for row in a.collision]}


def _expedition_view(e, control, *, debug, detail):
    """HUD state of the auto-pilot: vitals, activity, log, anchor shop, meta progress."""
    in_anchor = e.anchor_ms is not None
    shop_open = in_anchor or e.contact
    unarmed_target = e.unarmed_target() if control == "manual" and not in_anchor else None
    return {"mode": e.mode(), "activity": e.activity(),
            "goal": None if e.goal is None else {"x": e.goal["x"], "y": e.goal["y"], "kind": e.goal["kind"]},
            "attributes": attribute_report(e.regular, e.dimensional),
            "log": [dict(entry) for entry in e.log[-LOG_ENTRIES:]],
            "vitals": e.vitals(), "inventory": e.inventory_rows(),
            "equipped": dict(e.equipped),
            "inventory_slots": INVENTORY_SLOTS, "life": e.life, "total_ms": e.total_ms,
            "depth": e.depth, "best_depth": e.best_depth,
            "last_strike": dict(e.last_strike) if e.last_strike else None,
            "anchor_space": None if not shop_open else {
                "kind": "contact" if e.contact else "opening" if e.opening else "death",
                "at_camp": bool(e.contact and e.at_camp()),
                "remaining_ms": e.anchor_ms or 0, "waiting": e.anchor_wait or e.contact,
                "first_return": e.life == 1 and not e.opening and not e.contact},
            "location_context": e.location_context(),
            "anchor_offerings": ([{"id": item, "name": ITEMS[item].name, "count": count,
                                   "ash": e.camp_offer_value(item, count),
                                   "ash_one": e.camp_offer_value(item, 1)}
                                  for item, count in sorted(e.camp_stock().items())]
                                 if e.contact and e.at_camp() else []),
            "punch_damage": e.punch_damage(), "report": e.report,
            "anchor": {"x": e.anchor[0], "y": e.anchor[1]},
            "control": control, "possession": e.possession(), "clock": e.clock_view(),
            "attack_radius": e.attack().reach,
            "weapon": _weapon_view(e),
            "auto_target": unarmed_target[1] if unarmed_target else None,
            "skill_slots": _skill_slots(e, shop_open),
            "campfire": None if in_anchor or e.campfire is None or e.campfire["dimension"] != e.dimension
            else {"x": e.campfire["fire_x"], "y": e.campfire["fire_y"]},
            "prologue": e.prologue(),
            "story": None if e.opening else e.story_view(),
            "region": _region_view(e),
            "meta": _meta_view(e),
            "shop": e.anchor_offers() if shop_open else None,
            "stats": dict(e.stats),
            "debug": e.debug_info() if debug else None,
            "detail": details.detail(e) if detail else None,
            "bounty": [{"id": i, "name": BY_ID[i].name, "spawned": n, "limit": limit}
                       for i, n, limit in e.bounty()],
            "opponent": e.opponent(), "item_colors": ITEM_COLORS,
            "load": {"percent": e.load_percent(), "carried": e.carried_units()},
            "camp": e.camp_view(),
            "item_glints": ITEM_GLINTS}


def _skill_slots(e, in_anchor):
    """The three skill buttons: what each does (`hint`), why it can't be used now (`note`),
    and the cooldown or time left (`remaining_ms` of `cooldown_ms`) so the client can draw a timer.
    Slot 1 contacts the anchor once bought, slot 2 possesses, slot 3 is reserved."""
    busy = in_anchor or e.in_prologue
    contact_unlock = next((u for u in UNLOCKS.values() if u.ability == "contact_anchor"), None)
    if not e.has_ability("contact_anchor"):
        contact = {"state": "locked", "note": f"Unlock at the anchor ({contact_unlock.cost} ash)" if contact_unlock else "Locked"}
    elif busy:
        contact = {"state": "disabled", "note": "Not now"}
    elif e.total_ms < e.contact_ready_ms:
        contact = {"state": "cooldown", "note": "Recharging"}
    else:
        contact = {"state": "ready", "note": "Ready"}
    contact.update(name="Contact anchor", remaining_ms=max(0, e.contact_ready_ms - e.total_ms),
                   cooldown_ms=CONTACT_COOLDOWN_MS,
                   hint="Reach the anchor without dying: the world waits while you spend ash, then the life "
                        f"goes on. Recharges for {CONTACT_COOLDOWN_MS // 60_000} minutes after.")
    p = e.possession()
    if p["active"]:
        possess = {"state": "active", "note": f"{(p['remaining_ms'] + 999) // 1000}s left",
                   "remaining_ms": p["remaining_ms"], "cooldown_ms": p["duration_ms"]}
    elif busy:
        possess = {"state": "disabled", "note": "Not now", "remaining_ms": 0, "cooldown_ms": POSSESS_COOLDOWN_MS}
    elif not p["charge_ms"]:
        possess = {"state": "cooldown", "note": "Charging", "remaining_ms": 1,
                   "cooldown_ms": POSSESS_COOLDOWN_MS}
    else:
        available = p["available_ms"]
        possess = {"state": "ready", "note": "<1s available" if available < 1000 else
                   f"{(available + 999) // 1000}s available",
                   "remaining_ms": 0, "cooldown_ms": POSSESS_COOLDOWN_MS}
    possess["charge_ms"] = p["charge_ms"]
    possess["charge_max_ms"] = p["charge_max_ms"]
    possess.update(name="Possess", hint=f"Take the avatar's hands for up to {p['duration_ms'] // 1000} seconds at full charge: move with WASD, "
                   f"act with Space and E; it moves and works {POSSESS_SPEED_PERCENT - 100}% faster with you. "
                   "Release early to save charge. An empty meter refills in one minute.")
    shift = {"name": "Dimensional Shift", "state": "locked", "note": "Coming later",
             "hint": "A future skill for entering a fighting dimension.",
             "remaining_ms": 0, "cooldown_ms": 0}
    return [contact, possess, shift]


def _meta_view(e):
    """Progress that survives death: ash, unlocks, knowledge, the places mastered."""
    view = e.places_view()
    return {"ash": e.ash,
            "unlocked": [{"id": u, "name": UNLOCKS[u].name} for u in sorted(e.unlocked)],
            "knowledge": sorted(e.knowledge), "recipes": sorted(e.recipes),
            "places": [{k: row[k] for k in ("id", "name", "grade", "grade_name", "done", "next", "can_camp", "focus")}
                       for row in view["places"] if row["done"]],
            "here": view["here"], "camp": view["camp"]}


def _weapon_view(expedition):
    """What the avatar holds, for the client's overlay and animation (fists: no item)."""
    attack = expedition.attack()
    item = expedition.equipped.get("weapon")
    return {"item": item, "attack": attack.id, "reach": attack.reach, "shape": attack.shape}


def _region_view(expedition):
    key = expedition.game.player.chunk
    region = expedition.region(key)
    site = expedition.game.world.site_for(key)
    condition = expedition.site_condition(key)
    return None if region is None else {"id": region.id, "name": region.name,
                                        "site": None if site is None else site.site.name,
                                        "condition": None if condition is None or condition.id == "quiet"
                                        else {"name": condition.name, "text": condition.text},
                                        "worked": expedition.worked_here(),
                                        "shimmer": cell_of(key) in expedition.shimmer,
                                        "place": _place_view(expedition)}


def _place_view(e):
    """The kind of place the avatar stands in and how well it is known (HUD line)."""
    here = e.location_here()
    if here is None:
        return None
    row = next(r for r in e.places_view()["places"] if r["id"] == here)
    return {k: row[k] for k in ("name", "grade", "grade_name", "done", "next", "can_camp", "camped", "focus")}


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
    input steers only while the avatar is possessed (the Possess skill, an anchor
    action); possession ends after its current Willpower based duration.
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
        self.debug = False
        self.detail = False

    @property
    def game(self):
        """The current life's simulation (a new life replaces the Exploration)."""
        return self.expedition.game if self.expedition is not None else self._game

    @property
    def active(self):
        """The player steers: no expedition (plain manual adapter) or a possessed avatar."""
        return self.expedition is None or self.expedition.possessing

    def _control(self, now=None):
        return "manual" if self.active else "auto"

    def _frame(self, known=(), now=None):
        return snapshot(self.game, known, paused=self.paused, expedition=self.expedition, control=self._control(),
                        debug=self.debug and self.expedition is not None,
                        detail=self.detail and self.expedition is not None)

    def input(self, data, now):
        command, paused, known = validate_input(data)
        with self.lock:
            self.debug = data.get("debug", False)
            self.detail = data.get("detail", False)
            action_error = None
            if "action" in data:
                if self.expedition is None:
                    raise ValueError("anchor action requires an expedition")
                was = self.active
                try:
                    self.expedition.anchor_action(data["action"])
                except ValueError as exc:   # a refused purchase must not break the connection
                    action_error = str(exc)
                if self.active != was:
                    self.command = InputCommand()   # possession began or ended: start from rest
            if not self.active:
                command = InputCommand()   # the auto-pilot steers; keys do nothing
            self.command = InputCommand() if paused else command
            self.paused, self.input_time = paused, now
            if self.active and self.expedition is not None and data.get("interact"):
                self.expedition.begin_interaction()
            if self.expedition is None:
                # Applying an edge at zero duration preserves even brief attack presses.
                self.game.advance(0, self.command)
            elif self.active:
                self.expedition.advance_manual(0, self.command, auto_attack=True)
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
        """Auto-pilot unless the avatar is possessed; held input expires after INPUT_LEASE."""
        expedition = self.expedition
        command = self.command if now - self.input_time <= INPUT_LEASE else InputCommand()
        if expedition is None:
            self.game.advance(ms, command)
        elif expedition.possessing:
            expedition.advance_manual(ms, command, auto_attack=True)
        else:
            expedition.advance(ms, allow_prayer=allow_prayer)

    def state(self, now=None):
        with self.lock:
            return self._frame(now=now)
