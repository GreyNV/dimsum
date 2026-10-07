"""Immutable character-grid contracts. Asset validation never interprets glyphs as code.

Environment is dense; objects are transparent where None. Collision is authoritative,
not inferred from visual glyphs. Location assets cannot contain the player glyph '@'.
All four aligned exits and every spawn must be reachable from the player spawn.
"""
from collections import deque
from dataclasses import asdict, dataclass
import re

DIRECTIONS = ("north", "east", "south", "west")
DELTAS = {"north": (0, -1), "east": (1, 0), "south": (0, 1), "west": (-1, 0)}
OPPOSITE = {"north": "south", "south": "north", "east": "west", "west": "east"}
_COLOR = re.compile(r"#[0-9a-fA-F]{6}\Z")
_ID = re.compile(r"[a-zA-Z0-9][a-zA-Z0-9_.:-]{0,127}\Z")


def integer(value, name, minimum=None, maximum=None):
    if type(value) is not int or (minimum is not None and value < minimum) or (
        maximum is not None and value > maximum
    ):
        raise ValueError(f"invalid {name}")
    return value


def identifier(value, name="identifier"):
    if not isinstance(value, str) or not _ID.fullmatch(value):
        raise ValueError(f"invalid {name}")
    return value


def fields(data, required, optional=()):
    if not isinstance(data, dict) or not set(required) <= data.keys() or (
        data.keys() - set(required) - set(optional)
    ):
        raise ValueError("invalid or unknown object fields")


@dataclass(frozen=True)
class Cell:
    glyph: str
    fg: str = "#c6c8bb"
    bg: str = "#17211b"

    def __post_init__(self):
        if not isinstance(self.glyph, str) or len(self.glyph) != 1 or not 32 <= ord(self.glyph) <= 126:
            raise ValueError("glyph must be one printable ASCII character")
        if any(not isinstance(c, str) or not _COLOR.fullmatch(c) for c in (self.fg, self.bg)):
            raise ValueError("colors must be #RRGGBB")


Grid = tuple[tuple[Cell | None, ...], ...]


@dataclass(frozen=True)
class Exit:
    direction: str
    x: int
    y: int

    def __post_init__(self):
        if self.direction not in DIRECTIONS:
            raise ValueError("invalid exit direction")
        integer(self.x, "exit x", 0)
        integer(self.y, "exit y", 0)


@dataclass(frozen=True)
class Spawn:
    id: str
    kind: str
    x: int
    y: int

    def __post_init__(self):
        identifier(self.id, "spawn ID")
        if self.kind not in ("player", "enemy"):
            raise ValueError("invalid spawn kind")
        integer(self.x, "spawn x", 0)
        integer(self.y, "spawn y", 0)


@dataclass(frozen=True)
class ChunkKey:
    dimension: str
    x: int
    y: int

    def __post_init__(self):
        identifier(self.dimension, "dimension")
        integer(self.x, "chunk x")
        integer(self.y, "chunk y")


def chunk_ident(key):
    """Canonical text id of a chunk key, e.g. "forest:-1:2" (saves, frames, logs)."""
    return f"{key.dimension}:{key.x}:{key.y}"


@dataclass(frozen=True)
class DimensionSpec:
    id: str
    biomes: tuple[str, ...] = ("dark_forest",)
    width: int = 32
    height: int = 16
    danger: int = 25

    def __post_init__(self):
        identifier(self.id, "dimension")
        if type(self.biomes) is not tuple or not self.biomes:
            raise ValueError("biomes must be a nonempty unique tuple")
        for biome in self.biomes:
            identifier(biome, "biome")
        if len(set(self.biomes)) != len(self.biomes):
            raise ValueError("duplicate biome")
        integer(self.width, "chunk width", 8, 128)
        integer(self.height, "chunk height", 6, 64)
        integer(self.danger, "danger", 0, 100)


@dataclass(frozen=True)
class ChunkAsset:
    id: str
    biome: str
    width: int
    height: int
    environment: Grid
    objects: Grid
    collision: tuple[tuple[bool, ...], ...]
    exits: tuple[Exit, ...]
    spawns: tuple[Spawn, ...]
    tags: tuple[str, ...] = ()
    topology: str = "room"


@dataclass(frozen=True)
class Chunk:
    key: ChunkKey
    seed: int
    asset_id: str
    asset: ChunkAsset

    def __post_init__(self):
        if not isinstance(self.key, ChunkKey):
            raise ValueError("invalid chunk key")
        integer(self.seed, "chunk seed", 0, 2**64 - 1)
        identifier(self.asset_id, "source asset ID")
        validate_asset(self.asset)


def validate_asset(asset: ChunkAsset) -> None:
    """Reject invalid, mutable, unsafe or unreachable content before registry adoption."""
    if not isinstance(asset, ChunkAsset):
        raise ValueError("expected ChunkAsset")
    identifier(asset.id, "asset ID")
    identifier(asset.biome, "biome")
    integer(asset.width, "width", 8, 128)
    integer(asset.height, "height", 6, 64)
    w, h = asset.width, asset.height
    for name, grid in (("environment", asset.environment), ("objects", asset.objects),
                       ("collision", asset.collision)):
        if type(grid) is not tuple or len(grid) != h:
            raise ValueError(f"invalid {name} height")
        for row in grid:
            if type(row) is not tuple or len(row) != w:
                raise ValueError(f"invalid {name} width")
            for cell in row:
                if name == "collision":
                    if type(cell) is not bool:
                        raise ValueError("collision cells must be booleans")
                elif cell is None and name == "objects":
                    continue
                elif not isinstance(cell, Cell) or cell.glyph == "@":
                    raise ValueError("invalid location cell or baked player")
    if asset.topology not in ("room", "open"):
        raise ValueError("unsupported topology")
    if type(asset.exits) is not tuple or not asset.exits or any(
        not isinstance(e, Exit) for e in asset.exits
    ):
        raise ValueError("immutable exits required")
    expected = {"north": (w // 2, 0), "east": (w - 1, h // 2),
                "south": (w // 2, h - 1), "west": (0, h // 2)}
    if asset.topology == "room":
        if len(asset.exits) != 4 or {e.direction: (e.x, e.y) for e in asset.exits} != expected:
            raise ValueError("exits must be unique aligned midpoints")
    else:
        required = {(direction, x, y)
                    for direction, points in (
                        ("north", ((x, 0) for x in range(w))),
                        ("east", ((w - 1, y) for y in range(h))),
                        ("south", ((x, h - 1) for x in range(w))),
                        ("west", ((0, y) for y in range(h))))
                    for x, y in points if not asset.collision[y][x]}
        actual = {(e.direction, e.x, e.y) for e in asset.exits}
        if actual != required or len(actual) != len(asset.exits) or {e.direction for e in asset.exits} != set(DIRECTIONS):
            raise ValueError("open exits must describe every walkable boundary in all four directions")
    if type(asset.spawns) is not tuple or any(not isinstance(s, Spawn) for s in asset.spawns):
        raise ValueError("spawns must be an immutable tuple")
    if len({s.id for s in asset.spawns}) != len(asset.spawns) or len({
        (s.x, s.y) for s in asset.spawns
    }) != len(asset.spawns):
        raise ValueError("spawn IDs and positions must be unique")
    players = [s for s in asset.spawns if s.kind == "player"]
    if len(players) != 1:
        raise ValueError("one player spawn required")
    points = [(e.x, e.y) for e in asset.exits] + [(s.x, s.y) for s in asset.spawns]
    if any(not 0 <= x < w or not 0 <= y < h or asset.collision[y][x] for x, y in points):
        raise ValueError("blocked or out-of-bounds exit/spawn")
    exits = {(e.x, e.y) for e in asset.exits}
    for y in range(h):
        for x in range(w):
            if (x in (0, w - 1) or y in (0, h - 1)) and (x, y) not in exits and not asset.collision[y][x]:
                raise ValueError("non-exit boundary must block movement")
    start = (players[0].x, players[0].y)
    seen, pending = {start}, deque([start])
    while pending:
        x, y = pending.popleft()
        for dx, dy in DELTAS.values():
            p = (x + dx, y + dy)
            if 0 <= p[0] < w and 0 <= p[1] < h and p not in seen and not asset.collision[p[1]][p[0]]:
                seen.add(p)
                pending.append(p)
    if not set(points) <= seen:
        raise ValueError("exit/spawn unreachable from player spawn")
    if type(asset.tags) is not tuple:
        raise ValueError("tags must be an immutable unique tuple")
    for tag in asset.tags:
        identifier(tag, "tag")
    if len(set(asset.tags)) != len(asset.tags):
        raise ValueError("duplicate asset tag")


def asset_to_dict(asset: ChunkAsset) -> dict:
    validate_asset(asset)
    data = asdict(asset)
    if asset.topology == "room":
        del data["topology"]
        return {"schema_version": 1, **data}
    return {"schema_version": 2, **data}


def _cell(raw):
    if raw is None:
        return None
    fields(raw, ("glyph", "fg", "bg"))
    return Cell(**raw)


def asset_from_dict(data: dict) -> ChunkAsset:
    """Strict schema1 parser. Callers must bound raw file size before JSON decoding."""
    fields(data, ("schema_version", "id", "biome", "width", "height", "environment",
                  "objects", "collision", "exits", "spawns", "tags"), ("topology",))
    version = data["schema_version"]
    if type(version) is not int or version not in (1, 2):
        raise ValueError("unsupported asset schema")
    if (version == 1 and "topology" in data) or (version == 2 and data.get("topology") != "open"):
        raise ValueError("asset topology does not match schema")
    integer(data["width"], "width", 8, 128)
    integer(data["height"], "height", 6, 64)
    for name in ("environment", "objects", "collision"):
        grid = data[name]
        if not isinstance(grid, (list, tuple)) or len(grid) != data["height"] or any(
            not isinstance(row, (list, tuple)) or len(row) != data["width"] for row in grid
        ):
            raise ValueError("invalid grid dimensions")
    for name in ("exits", "spawns", "tags"):
        if not isinstance(data[name], (list, tuple)):
            raise ValueError("asset collections must be arrays")
    try:
        env = tuple(tuple(_cell(c) for c in row) for row in data["environment"])
        obj = tuple(tuple(_cell(c) for c in row) for row in data["objects"])
        collision = tuple(tuple(row) for row in data["collision"])
        exits = []
        for raw in data["exits"]:
            fields(raw, ("direction", "x", "y"))
            exits.append(Exit(**raw))
        spawns = []
        for raw in data["spawns"]:
            fields(raw, ("id", "kind", "x", "y"))
            spawns.append(Spawn(**raw))
        asset = ChunkAsset(data["id"], data["biome"], data["width"], data["height"],
                           env, obj, collision, tuple(exits), tuple(spawns), tuple(data["tags"]),
                           data.get("topology", "room"))
        validate_asset(asset)
        return asset
    except (TypeError, KeyError, AttributeError) as exc:
        raise ValueError("malformed asset data") from exc


def chunk_to_dict(chunk: Chunk) -> dict:
    return {"schema_version": 1, "key": asdict(chunk.key), "seed": chunk.seed,
            "asset_id": chunk.asset_id, "asset": asset_to_dict(chunk.asset)}


def chunk_from_dict(data: dict) -> Chunk:
    fields(data, ("schema_version", "key", "seed", "asset_id", "asset"))
    if type(data["schema_version"]) is not int or data["schema_version"] != 1:
        raise ValueError("unsupported chunk schema")
    fields(data["key"], ("dimension", "x", "y"))
    return Chunk(ChunkKey(**data["key"]), data["seed"], data["asset_id"], asset_from_dict(data["asset"]))
