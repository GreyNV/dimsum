"""Pure version-1 chunk composition; no provider, runtime state or shared RNG.

A world's identity includes seed, sorted dimension specs, generator version and
catalog digest. All cell decisions use labeled SHA-derived seeds. Paths connecting
template exits/spawns remain open; decoration may block only unreserved floor.
Loot has a reserved independent seed namespace, but this slice grants no loot.
"""
from collections import deque
from dataclasses import asdict, replace

from .models import (
    Cell, Chunk, ChunkAsset, ChunkKey, DELTAS, DimensionSpec, Spawn,
    asset_to_dict, integer, validate_asset,
)
from .seeds import canonical_json, content_digest, derive_seed

GENERATOR_VERSION = 1


def validated_dimensions(dimensions):
    """Return sorted immutable unique dimension specs, rejecting ambiguous input."""
    if type(dimensions) is not tuple or not dimensions or any(
        not isinstance(spec, DimensionSpec) for spec in dimensions
    ):
        raise ValueError("dimensions must be a nonempty tuple of DimensionSpec")
    if len({spec.id for spec in dimensions}) != len(dimensions):
        raise ValueError("duplicate dimension ID")
    return tuple(sorted(dimensions, key=lambda spec: spec.id))


def validated_catalog(assets):
    """Every accepted asset is immutable, validated and uniquely named."""
    if type(assets) is not tuple or not assets:
        raise ValueError("catalog must be a nonempty tuple")
    for asset in assets:
        validate_asset(asset)
    if len({asset.id for asset in assets}) != len(assets):
        raise ValueError("duplicate catalog asset ID")
    return tuple(sorted(assets, key=lambda asset: asset.id))


def _paths(asset):
    """Deterministic BFS tree; reserve routes to all required source points."""
    player = next(spawn for spawn in asset.spawns if spawn.kind == "player")
    origin = (player.x, player.y)
    parents, queue = {origin: None}, deque([origin])
    while queue:
        x, y = queue.popleft()
        for dx, dy in DELTAS.values():
            point = (x + dx, y + dy)
            if (0 <= point[0] < asset.width and 0 <= point[1] < asset.height
                    and point not in parents and not asset.collision[point[1]][point[0]]):
                parents[point] = (x, y)
                queue.append(point)
    protected = set()
    for point in [(e.x, e.y) for e in asset.exits] + [(s.x, s.y) for s in asset.spawns]:
        while point is not None and point not in protected:
            protected.add(point)
            point = parents[point]
    return protected


def _reachable(collision, origin):
    seen, queue = {origin}, deque([origin])
    width, height = len(collision[0]), len(collision)
    while queue:
        x, y = queue.popleft()
        for dx, dy in DELTAS.values():
            point = (x + dx, y + dy)
            if (0 <= point[0] < width and 0 <= point[1] < height
                    and point not in seen and not collision[point[1]][point[0]]):
                seen.add(point)
                queue.append(point)
    return seen


class ChunkGenerator:
    """Select/combine a pinned catalog without access-order-dependent state.

    All requested biome/geometry combinations must exist in the catalog. Optional
    catalog fallback belongs to WorldRepository construction, never generation.
    """

    def __init__(self, world_seed: int, dimensions: tuple, assets: tuple):
        integer(world_seed, "world seed", 0, 2**64 - 1)
        self.world_seed = world_seed
        self.dimensions = validated_dimensions(dimensions)
        self.catalog = validated_catalog(assets)
        self.catalog_digest = content_digest([asset_to_dict(asset) for asset in self.catalog])
        self._specs = {spec.id: spec for spec in self.dimensions}
        self._pools = {}
        for spec in self.dimensions:
            for biome in spec.biomes:
                pool = tuple(asset for asset in self.catalog if
                             (asset.biome, asset.width, asset.height) ==
                             (biome, spec.width, spec.height))
                if not pool:
                    raise ValueError(f"no assets for {spec.id}/{biome}/{spec.width}x{spec.height}")
                self._pools[(spec.id, biome)] = pool

    def _spec(self, key):
        if not isinstance(key, ChunkKey) or key.dimension not in self._specs:
            raise ValueError("unknown dimension or invalid chunk key")
        return self._specs[key.dimension]

    def _seed(self, key):
        spec = self._spec(key)
        dimension_seed = derive_seed(
            self.world_seed, "generator", GENERATOR_VERSION, "catalog",
            self.catalog_digest, "dimension", canonical_json(asdict(spec)))
        return derive_seed(dimension_seed, "chunk", key.x, key.y)

    def _source(self, key):
        spec = self._spec(key)
        seed = self._seed(key)
        terrain_seed = derive_seed(seed, "terrain")
        # Authoring order is not a hidden weighting mechanism.
        biomes = tuple(sorted(spec.biomes))
        biome = biomes[derive_seed(terrain_seed, "biome") % len(biomes)]
        pool = self._pools[(spec.id, biome)]
        return pool[derive_seed(terrain_seed, "template") % len(pool)]

    def biome_for(self, key):
        """Read deterministic biome metadata without composing/residing a grid."""
        return self._source(key).biome

    def generate(self, key: ChunkKey) -> Chunk:
        spec, seed, source = self._spec(key), self._seed(key), self._source(key)
        if source.topology == "open":
            from .open_terrain import compose_open
            landscape_seed = derive_seed(self.world_seed, "open-terrain-v1", self.catalog_digest,
                                         canonical_json(asdict(spec)))
            return Chunk(key, seed, source.id, compose_open(source, spec, key, landscape_seed))
        terrain = derive_seed(seed, "terrain")
        decoration = derive_seed(seed, "decoration")
        encounter = derive_seed(seed, "encounter")
        # This reserved stream must not be reused for scenery or encounter decisions.
        derive_seed(seed, "loot")
        protected = _paths(source)
        env = [list(row) for row in source.environment]
        objects = [list(row) for row in source.objects]
        collision = [list(row) for row in source.collision]
        forest = source.biome == "dark_forest"
        blocker = Cell("T" if forest else "^", "#66885e" if forest else "#aa8b7b", "#17211b" if forest else "#2b2325")
        detail = Cell(";" if forest else "*", "#8b9b6b" if forest else "#b8a297", blocker.bg)
        for y in range(1, source.height - 1):
            for x in range(1, source.width - 1):
                if collision[y][x]:
                    continue
                # Preserve authored special terrain glyphs and both palette colors.
                if env[y][x].glyph in ".,`":
                    env[y][x] = replace(env[y][x], glyph=".,`"[derive_seed(terrain, "floor", x, y) % 3])
                if (x, y) in protected or objects[y][x] is not None:
                    continue
                roll = derive_seed(decoration, "object", x, y) % 100
                if roll < (10 if forest else 5):
                    objects[y][x], collision[y][x] = blocker, True
                elif roll < 18:
                    objects[y][x] = detail

        spawns = [spawn for spawn in source.spawns if spawn.kind == "player" or spec.danger > 0]
        player = next(spawn for spawn in spawns if spawn.kind == "player")
        occupied = {(s.x, s.y) for s in spawns} | {(e.x, e.y) for e in source.exits}
        candidates = sorted(
            (point for point in _reachable(collision, (player.x, player.y))
             if point not in occupied and objects[point[1]][point[0]] is None),
            key=lambda point: (derive_seed(encounter, "spawn", *point), point))
        used_ids = {spawn.id for spawn in spawns}
        for index, (x, y) in enumerate(candidates[:spec.danger // 25]):
            spawn_id = f"encounter-{index}"
            suffix = 0
            while spawn_id in used_ids:
                suffix += 1
                spawn_id = f"encounter-{index}-{suffix}"
            used_ids.add(spawn_id)
            spawns.append(Spawn(spawn_id, "enemy", x, y))
        composed = replace(source, environment=tuple(map(tuple, env)),
                           objects=tuple(map(tuple, objects)),
                           collision=tuple(map(tuple, collision)), spawns=tuple(spawns))
        return Chunk(key, seed, source.id, composed)
