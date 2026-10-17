"""Renderer-independent spatial simulation with integer-millisecond event timing.

Input is held over advance(ms, command). Movement repeats after each interval;
changing/releasing direction resets its partial interval. Attacks start on a rising
edge, never auto-repeat while held, and lock movement until recovery completes.
Animation rate affects idle/walk visuals; attack rate affects the complete attack
clip and its explicit damage windows. Render frequency has no simulation effect.
Snapshots pin animation assets/configuration and preserve partial clocks/hit sets.
"""
from dataclasses import asdict, dataclass

from .animation import (animations_from_dict, animations_to_dict, default_animations,
                        rotate, validate_animations)
from .models import Cell, ChunkKey, DELTAS, DIRECTIONS, fields, identifier, integer

# Manual movement also accepts the four diagonals. A diagonal is two cardinal half-steps taken
# together; it never cuts a corner between two blocked cells and slides along a wall when only
# one half-step is open. It takes DIAGONAL_PERCENT of the cardinal interval (about sqrt 2), so
# speed over ground stays even. Facing stays cardinal (the sprite has four facings).
DIAGONALS = {"northeast": ("north", "east"), "southeast": ("south", "east"),
             "southwest": ("south", "west"), "northwest": ("north", "west")}
MOVE_DIRECTIONS = DIRECTIONS + tuple(DIAGONALS)
DIAGONAL_PERCENT = 141
MAX_LOAD_PERCENT = 400   # carry load may stretch the movement interval up to 4x (owners cap it lower)
MIN_LOAD_PERCENT = 50    # a speed boost (possession) may shorten it to half
REVEAL_RADIUS = 5
from .seeds import derive_seed


@dataclass(frozen=True)
class InputCommand:
    move: str | None = None
    attack: bool = False
    face: str | None = None

    def __post_init__(self):
        if self.move is not None and self.move not in MOVE_DIRECTIONS:
            raise ValueError("move must be a cardinal or diagonal direction")
        if type(self.attack) is not bool:
            raise ValueError("attack input must be boolean")
        if self.face is not None and self.face not in DIRECTIONS:
            raise ValueError("face must be a cardinal direction")


@dataclass
class Player:
    chunk: ChunkKey
    x: int
    y: int
    facing: str = "north"
    animation: str = "idle"
    animation_elapsed_ms: int = 0


@dataclass
class Target:
    id: str
    chunk: ChunkKey
    x: int
    y: int
    hp: int = 3


def _key(raw):
    fields(raw, ("dimension", "x", "y"))
    return ChunkKey(**raw)


def _target_id(key, spawn_id):
    return f"spawn:{derive_seed(0, 'actor', key.dimension, key.x, key.y, spawn_id):016x}"


class Exploration:
    """Own all mutable actor/input clocks; repository owns immutable world chunks."""

    attack_reach = 1   # cells along the facing (the weapon); the owner sets it each step, never saved

    def __init__(self, world, dimension=None, *, movement_interval_ms=120,
                 animation_rate_percent=100, attack_rate_percent=100,
                 attack_damage=1, animations=None):
        self._configure(movement_interval_ms, animation_rate_percent, attack_rate_percent,
                        attack_damage, default_animations() if animations is None else animations)
        self.world = world
        dimension = dimension if dimension is not None else world.dimensions[0].id
        if dimension not in {spec.id for spec in world.dimensions}:
            raise ValueError("unknown initial dimension")
        key = ChunkKey(dimension, 0, 0)
        chunk = world.visit(key)
        spawn = next(s for s in chunk.asset.spawns if s.kind == "player")
        self.player = Player(key, spawn.x, spawn.y)
        self.targets = {}
        self.initialized_chunks = set()
        self.seen = {}
        self.elapsed_ms = 0
        self.move_elapsed_ms = 0
        self.last_move = None
        self.attack_held = False
        self.hit_targets = set()
        # Adapter presentation choice, not saved: a new move press steps at once.
        self.step_on_press = False
        self._enter(key)
        self._reveal()

    def _reveal(self):
        """Remember nearby cells, including those across a chunk edge, without generating terrain."""
        asset = self.current_chunk().asset
        width, height = asset.width, asset.height
        gx = self.player.chunk.x * width + self.player.x
        gy = self.player.chunk.y * height + self.player.y
        for dy in range(-REVEAL_RADIUS, REVEAL_RADIUS + 1):
            for dx in range(-REVEAL_RADIUS, REVEAL_RADIUS + 1):
                if dx * dx + dy * dy > REVEAL_RADIUS * REVEAL_RADIUS:
                    continue
                x, y = gx + dx, gy + dy
                key = ChunkKey(self.player.chunk.dimension, x // width, y // height)
                if self.world.status(key) == "unknown":
                    continue
                rows = self.seen.setdefault(key, [0] * height)
                rows[y % height] |= 1 << (x % width)

    def reveal_area(self, radius):
        """Remember every cell within `radius` tiles (a map-reading reward). Generates the
        chunks it covers so their cells exist; deterministic like all generation."""
        asset = self.current_chunk().asset
        width, height = asset.width, asset.height
        gx = self.player.chunk.x * width + self.player.x
        gy = self.player.chunk.y * height + self.player.y
        for dy in range(-radius, radius + 1):
            for dx in range(-radius, radius + 1):
                if dx * dx + dy * dy > radius * radius:
                    continue
                x, y = gx + dx, gy + dy
                key = ChunkKey(self.player.chunk.dimension, x // width, y // height)
                if self.world.status(key) == "unknown":
                    self.world.get(key)
                rows = self.seen.setdefault(key, [0] * height)
                rows[y % height] |= 1 << (x % width)

    def visibility_rows(self, key):
        """Browser-safe row strings; absent cells remain hidden."""
        rows = self.seen.get(key)
        if rows is None:
            return None
        width = next(spec.width for spec in self.world.dimensions if spec.id == key.dimension)
        return ["".join("1" if row & (1 << x) else "0" for x in range(width)) for row in rows]

    @property
    def movement_interval_ms(self):
        """Pinned movement interval; construct another runtime to change this rate."""
        return self._movement_interval_ms

    @property
    def animation_rate_percent(self):
        return self._animation_rate_percent

    @property
    def attack_rate_percent(self):
        return self._attack_rate_percent

    def _configure(self, movement_interval_ms, animation_rate_percent,
                   attack_rate_percent, attack_damage, animations):
        integer(movement_interval_ms, "movement interval", 1, 60000)
        integer(animation_rate_percent, "animation rate", 1, 10000)
        integer(attack_rate_percent, "attack rate", 1, 10000)
        integer(attack_damage, "attack damage", 1, 1000000)
        if not hasattr(self, "load_percent"):
            self.load_percent = 100
        integer(self.load_percent, "carry load percent", MIN_LOAD_PERCENT, MAX_LOAD_PERCENT)
        validate_animations(animations)
        self._movement_interval_ms = movement_interval_ms
        self._animation_rate_percent = animation_rate_percent
        self._attack_rate_percent = attack_rate_percent
        self.attack_damage = attack_damage
        self.animations = dict(animations)

    def _enter(self, key):
        chunk = self.world.visit(key)
        if key not in self.initialized_chunks:
            self.initialized_chunks.add(key)
            for spawn in chunk.asset.spawns:
                if spawn.kind == "enemy":
                    target_id = _target_id(key, spawn.id)
                    self.targets[target_id] = Target(target_id, key, spawn.x, spawn.y)
        self.world.stream(key)
        # A small cache may evict neighbors; the center is always resident for rendering.
        self.world.get(key)

    def current_chunk(self):
        chunk = self.world.peek(self.player.chunk)
        if chunk is None:
            raise ValueError("current chunk is not resident; stream it before rendering")
        return chunk

    def _set_animation(self, name):
        if self.player.animation != name:
            self.player.animation = name
            self.player.animation_elapsed_ms = 0

    def player_cell(self):
        rate = self.attack_rate_percent if self.player.animation == "attack" else self.animation_rate_percent
        return self.animations[self.player.animation].sample(self.player.animation_elapsed_ms, rate).cell

    def effect_cells(self):
        if self.player.animation != "attack":
            return {}
        frame = self.animations["attack"].sample(self.player.animation_elapsed_ms, self.attack_rate_percent)
        if not frame.active or frame.effect_origin is None:
            return {}
        dx, dy = rotate(frame.effect_origin, self.player.facing)
        x, y = self.player.x + dx, self.player.y + dy
        asset = self.current_chunk().asset
        return {(x, y): Cell("*", "#efc385")} if 0 <= x < asset.width and 0 <= y < asset.height else {}

    def _damage(self, before, after):
        # Clocks are integer hundredths of authored ms: no fractional carry is lost.
        for start, end, frame in self.animations["attack"].active_intervals():
            if before < end * 100 and after >= start * 100:
                asset = self.current_chunk().asset
                px = self.player.chunk.x * asset.width + self.player.x
                py = self.player.chunk.y * asset.height + self.player.y
                live = {}
                for target in self.targets.values():
                    if target.chunk.dimension == self.player.chunk.dimension and target.hp > 0:
                        live.setdefault((target.chunk.x * asset.width + target.x,
                                         target.chunk.y * asset.height + target.y), target)
                for dx, dy in (rotate(p, self.player.facing) for p in frame.hitbox):
                    # The frame's hitbox cell starts the line; a weapon extends it along the
                    # facing. The first enemy in the line takes the blow; a wall stops it.
                    for step in range(1, self.attack_reach + 1):
                        cell = (px + dx * step, py + dy * step)
                        target = live.get(cell)
                        if target is not None:
                            if target.id not in self.hit_targets:
                                target.hp = max(0, target.hp - self.attack_damage)
                                self.hit_targets.add(target.id)
                            break
                        if self.wall_at(*cell):
                            break

    def wall_at(self, gx, gy):
        """A cell a blow cannot pass: a blocking object (tree, rock, structure) or an
        unloaded chunk. Water blocks walking but not a thrust over it."""
        asset = self.current_chunk().asset
        key = ChunkKey(self.player.chunk.dimension, gx // asset.width, gy // asset.height)
        chunk = self.world.peek(key)
        if chunk is None:
            return True
        x, y = gx % asset.width, gy % asset.height
        return chunk.asset.collision[y][x] and chunk.asset.objects[y][x] is not None

    def _step_target(self, key, x, y, direction):
        """Where one cardinal step from (key, x, y) lands, or None if blocked (pure)."""
        dx, dy = DELTAS[direction]
        # peek first: reading the source chunk must not reorder the world's LRU cache.
        asset = (self.world.peek(key) or self.world.get(key)).asset
        nx, ny = x + dx, y + dy
        if 0 <= nx < asset.width and 0 <= ny < asset.height:
            return None if asset.collision[ny][nx] else (key, nx, ny)
        if not any(e.direction == direction and (x, y) == (e.x, e.y) for e in asset.exits):
            return None
        nkey = ChunkKey(key.dimension, key.x + dx, key.y + dy)
        destination = self.world.get(nkey).asset
        nx, ny = nx % destination.width, ny % destination.height
        return None if destination.collision[ny][nx] else (nkey, nx, ny)

    def _place(self, key, x, y):
        entered = key != self.player.chunk
        self.player.chunk, self.player.x, self.player.y = key, x, y
        if entered:
            self._enter(key)
        self._reveal()

    @staticmethod
    def facing_for(direction, current):
        """Cardinal sprite facing for a move: a diagonal keeps a matching current facing,
        otherwise shows its east/west side."""
        if direction in DIAGONALS:
            vertical, horizontal = DIAGONALS[direction]
            return current if current in (vertical, horizontal) else horizontal
        return direction

    @property
    def step_interval_ms(self):
        """The movement interval after carry load (`load_percent`, set each step by its owner)."""
        return self.movement_interval_ms * self.load_percent // 100

    def interval_for(self, direction):
        if direction in DIAGONALS:
            return self.step_interval_ms * DIAGONAL_PERCENT // 100
        return self.step_interval_ms

    def _move(self, direction):
        self.player.facing = self.facing_for(direction, self.player.facing)
        start = (self.player.chunk, self.player.x, self.player.y)
        if direction not in DIAGONALS:
            landing = self._step_target(*start, direction)
            if landing is not None:
                self._place(*landing)
            return
        vertical, horizontal = DIAGONALS[direction]
        via_h = self._step_target(*start, horizontal)
        via_v = self._step_target(*start, vertical)
        if via_h is not None and via_v is not None:
            landing = self._step_target(*via_h, vertical)
            if landing is not None and landing == self._step_target(*via_v, horizontal):
                self._place(*landing)
                return
        # Corner blocked: slide along whichever half-step is open (horizontal first).
        for landing in (via_h, via_v):
            if landing is not None:
                self._place(*landing)
                return

    def advance(self, milliseconds, command=InputCommand()):
        integer(milliseconds, "elapsed milliseconds", 0)
        if not isinstance(command, InputCommand):
            raise ValueError("expected InputCommand")
        # Validate public knobs at the boundary; invalid settings cannot partially advance.
        self._configure(self.movement_interval_ms, self.animation_rate_percent,
                        self.attack_rate_percent, self.attack_damage, self.animations)
        if type(self.step_on_press) is not bool:
            raise ValueError("step_on_press must be boolean")
        # Press edge: a newly pressed direction (not a continued hold). With
        # step_on_press, it steps immediately and then repeats every interval, so a
        # short tap moves one cell instead of only turning. Partition-independent:
        # the edge belongs to the advance call where the command changes.
        press = bool(command.move) and command.move != self.last_move
        if command.move != self.last_move:
            self.move_elapsed_ms = 0
        self.last_move = command.move
        if command.move and self.player.animation != "attack":
            self.player.facing = self.facing_for(command.move, self.player.facing)
        if command.face and self.player.animation != "attack":
            self.player.facing = command.face
        if command.attack and not self.attack_held and self.player.animation != "attack":
            self._set_animation("attack")
            self.move_elapsed_ms = 0
            self.hit_targets.clear()
            self._damage(0, 0)
        self.attack_held = command.attack
        if press and self.step_on_press and self.player.animation != "attack":
            self._set_animation("walk")
            self._move(command.move)
        remaining = milliseconds
        while remaining:
            if self.player.animation == "attack":
                duration = self.animations["attack"].duration_ms * 100
                before = self.player.animation_elapsed_ms * self.attack_rate_percent
                until_done = max(0, (duration - before + self.attack_rate_percent - 1) // self.attack_rate_percent)
                step = min(remaining, until_done)
                self.player.animation_elapsed_ms += step
                self._damage(before, self.player.animation_elapsed_ms * self.attack_rate_percent)
                if step == until_done:
                    self._set_animation("walk" if command.move else "idle")
                    self.hit_targets.clear()
            else:
                self._set_animation("walk" if command.move else "idle")
                interval = self.interval_for(command.move) if command.move else 0
                # max(0, ...): a lighter load can shorten the interval below the time already walked
                step = min(remaining, max(0, interval - self.move_elapsed_ms)) if command.move else remaining
                self.player.animation_elapsed_ms += step
                if command.move:
                    self.move_elapsed_ms += step
                    if self.move_elapsed_ms >= interval:
                        self.move_elapsed_ms = 0
                        self._move(command.move)
            remaining -= step
            self.elapsed_ms += step
        if self.player.animation != "attack":
            self._set_animation("walk" if command.move else "idle")

    def to_dict(self):
        """Schema2 saves cell discovery; resident cache and renderer state are not saved."""
        return {"schema_version": 2, "world": self.world.to_dict(),
                "config": {name: getattr(self, name) for name in (
                    "movement_interval_ms", "animation_rate_percent", "attack_rate_percent", "attack_damage")},
                "animations": animations_to_dict(self.animations), "player": asdict(self.player),
                "targets": [asdict(t) for _, t in sorted(self.targets.items())],
                "initialized_chunks": [asdict(k) for k in sorted(self.initialized_chunks,
                    key=lambda k: (k.dimension, k.x, k.y))],
                "elapsed_ms": self.elapsed_ms, "move_elapsed_ms": self.move_elapsed_ms,
                "last_move": self.last_move, "attack_held": self.attack_held,
                "hit_targets": sorted(self.hit_targets),
                "seen": [{"dimension": key.dimension, "x": key.x, "y": key.y,
                          "rows": self.visibility_rows(key)} for key in sorted(self.seen,
                              key=lambda k: (k.dimension, k.x, k.y))]}

    @classmethod
    def from_dict(cls, data):
        """Reject corrupt/future saves before returning a newly owned simulation."""
        from .repository import WorldRepository
        if type(data) is not dict or type(data.get("schema_version")) is not int or data["schema_version"] not in (1, 2):
            raise ValueError("unsupported exploration schema")
        version = data["schema_version"]
        fields(data, ("schema_version", "world", "config", "animations", "player",
                      "targets", "initialized_chunks", "elapsed_ms", "move_elapsed_ms",
                      "last_move", "attack_held", "hit_targets") + (("seen",) if version == 2 else ()))
        try:
            fields(data["config"], ("movement_interval_ms", "animation_rate_percent",
                                    "attack_rate_percent", "attack_damage"))
            result = cls.__new__(cls)
            result.step_on_press = False
            result._configure(**data["config"], animations=animations_from_dict(data["animations"]))
            result.world = WorldRepository.from_dict(data["world"])
            fields(data["player"], ("chunk", "x", "y", "facing", "animation", "animation_elapsed_ms"))
            p = data["player"]
            result.player = Player(_key(p["chunk"]), p["x"], p["y"], p["facing"],
                                   p["animation"], p["animation_elapsed_ms"])
            if p["facing"] not in DIRECTIONS or p["animation"] not in ("idle", "walk", "attack"):
                raise ValueError("invalid player facing/animation")
            integer(p["animation_elapsed_ms"], "animation elapsed", 0)
            integer(data["elapsed_ms"], "simulation elapsed", 0)
            integer(data["move_elapsed_ms"], "movement elapsed", 0,
                    result.movement_interval_ms * MAX_LOAD_PERCENT // 100 * DIAGONAL_PERCENT // 100 - 1)
            if p["animation_elapsed_ms"] > data["elapsed_ms"]:
                raise ValueError("animation clock exceeds simulation")
            if p["animation"] == "attack" and p["animation_elapsed_ms"] * result.attack_rate_percent >= result.animations["attack"].duration_ms * 100:
                raise ValueError("completed attack cannot remain active")
            if type(data["initialized_chunks"]) is not list or type(data["targets"]) is not list or type(data["hit_targets"]) is not list:
                raise ValueError("actor collections must be arrays")
            keys = [_key(k) for k in data["initialized_chunks"]]
            if len(keys) != len(set(keys)) or result.player.chunk not in keys:
                raise ValueError("invalid initialized chunk set")
            result.initialized_chunks = set(keys)
            if any(result.world.status(key) != "visited" for key in keys):
                raise ValueError("actors require visited chunks")
            result.targets = {}
            for raw in data["targets"]:
                fields(raw, ("id", "chunk", "x", "y", "hp"))
                identifier(raw["id"], "target ID")
                integer(raw["hp"], "target HP", 0, 1000000)
                target = Target(raw["id"], _key(raw["chunk"]), raw["x"], raw["y"], raw["hp"])
                if target.id in result.targets or target.chunk not in result.initialized_chunks:
                    raise ValueError("duplicate target or unvisited target chunk")
                result.targets[target.id] = target
            generated_targets = set()
            for key in keys:
                for spawn in result.world.get(key).asset.spawns:
                    if spawn.kind != "enemy":
                        continue
                    target_id = _target_id(key, spawn.id)
                    generated_targets.add(target_id)
                    target = result.targets.get(target_id)
                    if target is None or (target.chunk, target.x, target.y) != (key, spawn.x, spawn.y) or target.hp > 3:
                        raise ValueError("missing or modified generated target identity")
            if any(t.id.startswith("spawn:") and t.id not in generated_targets for t in result.targets.values()):
                raise ValueError("invented generated target")
            for actor in [result.player, *result.targets.values()]:
                asset = result.world.get(actor.chunk).asset
                integer(actor.x, "actor x", 0, asset.width - 1)
                integer(actor.y, "actor y", 0, asset.height - 1)
                if asset.collision[actor.y][actor.x]:
                    raise ValueError("actor inside blocking cell")
            InputCommand(data["last_move"], data["attack_held"])
            result.last_move, result.attack_held = data["last_move"], data["attack_held"]
            result.elapsed_ms, result.move_elapsed_ms = data["elapsed_ms"], data["move_elapsed_ms"]
            hits = data["hit_targets"]
            if any(not isinstance(h, str) for h in hits) or len(hits) != len(set(hits)) or not set(hits) <= result.targets.keys():
                raise ValueError("invalid hit target set")
            if p["animation"] != "attack" and hits:
                raise ValueError("inactive attack has hit targets")
            if (result.last_move is None or p["animation"] == "attack") and result.move_elapsed_ms:
                raise ValueError("inactive movement has partial clock")
            elapsed_attack = p["animation_elapsed_ms"] * result.attack_rate_percent
            active_positions = set()
            for start, _, frame in result.animations["attack"].active_intervals():
                if elapsed_attack >= start * 100:
                    asset = result.world.get(result.player.chunk).asset
                    active_positions.update((result.player.chunk.x * asset.width + result.player.x + dx,
                                             result.player.chunk.y * asset.height + result.player.y + dy)
                        for dx, dy in (rotate(point, p["facing"]) for point in frame.hitbox))
            for target_id in hits:
                target = result.targets[target_id]
                asset = result.world.get(result.player.chunk).asset
                position = (target.chunk.x * asset.width + target.x, target.chunk.y * asset.height + target.y)
                if (target.chunk.dimension != result.player.chunk.dimension or position not in active_positions
                        or (target_id in generated_targets and target.hp >= 3)):
                    raise ValueError("impossible already-hit target")
            result.hit_targets = set(hits)
            result.world.stream(result.player.chunk)
            result.world.get(result.player.chunk)
            result.seen = {}
            if version == 1:
                # Old saves revealed every visited chunk. Keep that progress on upgrade.
                specs = {spec.id: spec for spec in result.world.dimensions}
                for raw in data["world"]["discovery"]:
                    if raw["status"] == "visited":
                        key = ChunkKey(raw["dimension"], raw["x"], raw["y"])
                        spec = specs[key.dimension]
                        result.seen[key] = [(1 << spec.width) - 1] * spec.height
            else:
                if type(data["seen"]) is not list:
                    raise ValueError("seen must be an array")
                specs = {spec.id: spec for spec in result.world.dimensions}
                for raw in data["seen"]:
                    fields(raw, ("dimension", "x", "y", "rows"))
                    key = ChunkKey(raw["dimension"], raw["x"], raw["y"])
                    if key in result.seen or key.dimension not in specs or result.world.status(key) == "unknown":
                        raise ValueError("invalid seen chunk")
                    spec = specs[key.dimension]
                    rows = raw["rows"]
                    if type(rows) is not list or len(rows) != spec.height or any(
                            type(row) is not str or len(row) != spec.width or set(row) - {"0", "1"}
                            for row in rows):
                        raise ValueError("invalid seen rows")
                    result.seen[key] = [sum(1 << x for x, bit in enumerate(row) if bit == "1") for row in rows]
                rows = result.seen.get(result.player.chunk)
                if rows is None or not rows[result.player.y] & (1 << result.player.x):
                    raise ValueError("player cell must be seen")
            return result
        except (KeyError, TypeError, AttributeError, StopIteration) as exc:
            raise ValueError("malformed exploration save") from exc

