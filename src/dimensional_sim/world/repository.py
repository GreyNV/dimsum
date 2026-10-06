"""World catalog/discovery ownership and bounded resident chunk storage.

Constructing a new world may use bundled assets; loading a pinned save never does.
peek/minimap/status are read-only and cannot generate or modify cache recency.
Snapshots omit grids and LRU order: generation reconstructs immutable chunks.
This module has no dependency on the offline pipeline or any generation provider.
"""
from collections import OrderedDict
from dataclasses import asdict

from .generation import (ChunkGenerator, GENERATOR_VERSION,
                         SUPPORTED_GENERATOR_VERSIONS, validated_dimensions)
from .models import (
    ChunkKey, DimensionSpec, asset_from_dict, asset_to_dict, fields, integer,
)

WORLD_SCHEMA_VERSION = 2
MAX_MAP_RADIUS = 32


def _bundled(dimensions):
    # Kept at the construction boundary so runtime never knows about providers.
    from .assets import builtin_assets
    by_id = {}
    for width, height in sorted({(d.width, d.height) for d in dimensions}):
        for asset in builtin_assets(width, height):
            if any((d.width, d.height) == (width, height) and asset.biome in d.biomes
                   for d in dimensions):
                if asset.id in by_id and by_id[asset.id] != asset:
                    raise ValueError("bundled catalog has conflicting asset IDs")
                by_id[asset.id] = asset
    return tuple(by_id.values())


class WorldRepository:
    """Pinned world identity with LRU grids and persistent discovery metadata.

    get marks a key generated; visit promotes it to visited. Eviction removes only
    a grid, never discovery. stream loads at most cache_limit nearest keys and
    retains the center as most recently used. Radius inputs are bounded to 0..32.
    """

    def __init__(self, world_seed=1, dimensions=None, assets=None, cache_limit=9,
                 generator_version=GENERATOR_VERSION, region_catalog=None):
        integer(cache_limit, "cache limit", 1, 4096)
        self._world_seed = integer(world_seed, "world seed", 0, 2**64 - 1)
        self._dimensions = validated_dimensions(
            (DimensionSpec("forest"),) if dimensions is None else dimensions)
        if assets is not None and type(assets) is not tuple:
            raise ValueError("assets must be a tuple or None")
        catalog = _bundled(self.dimensions) if assets is None or assets == () else assets
        self._generator = ChunkGenerator(self.world_seed, self.dimensions, catalog,
                                         generator_version=generator_version,
                                         region_catalog=region_catalog)
        self._catalog = self._generator.catalog
        self._cache_limit = cache_limit
        self._resident = OrderedDict()
        self._recycled = OrderedDict()   # recently evicted chunks: identical on regeneration, so reuse them
        self._discovery = {}
        self._generation_count = 0

    @property
    def world_seed(self):
        return self._world_seed

    @property
    def dimensions(self):
        return self._dimensions

    @property
    def catalog(self):
        return self._catalog

    @property
    def cache_limit(self):
        return self._cache_limit

    @property
    def resident_count(self):
        return len(self._resident)

    @property
    def generation_count(self):
        return self._generation_count

    @property
    def catalog_digest(self):
        return self._generator.catalog_digest

    @property
    def generator_version(self):
        return self._generator.generator_version

    @property
    def region_catalog_digest(self):
        return self._generator.region_catalog_digest

    def region_for(self, key):
        """Read this world's pinned region without generating or residing a chunk."""
        from .regions import region_for
        biome = self.biome_for(key)
        return region_for(self.world_seed, biome, key, self._generator.region_catalog)

    def _key(self, key):
        self._generator._spec(key)
        return key

    def get(self, key):
        key = self._key(key)
        if key not in self._resident:
            chunk = self._recycled.pop(key, None) or self._generator.generate(key)
            self._resident[key] = chunk
            self._generation_count += 1
            self._discovery.setdefault(key, ("generated", chunk.asset.biome))
            while len(self._resident) > self.cache_limit:
                self._recycle(*self._resident.popitem(last=False))
        else:
            self._resident.move_to_end(key)
        return self._resident[key]

    RECYCLE_LIMIT = 256

    def _recycle(self, key, chunk):
        """Chunks are pure functions of seed/spec/catalog/key; keeping a few evicted ones
        only skips regeneration when the avatar walks back (residency rules are unchanged)."""
        self._recycled[key] = chunk
        while len(self._recycled) > self.RECYCLE_LIMIT:
            self._recycled.popitem(last=False)

    def visit(self, key):
        chunk = self.get(key)
        self._discovery[key] = ("visited", chunk.asset.biome)
        return chunk

    def biome_for(self, key):
        """Deterministic biome of a chunk without generating or residing it."""
        return self._generator.biome_for(key)

    def peek(self, key):
        return self._resident.get(self._key(key))

    def status(self, key):
        return self._discovery.get(self._key(key), ("unknown", None))[0]

    def stream(self, center, radius=1):
        self._key(center)
        integer(radius, "stream radius", 0, MAX_MAP_RADIUS)
        offsets = sorted(
            ((dx, dy) for dy in range(-radius, radius + 1) for dx in range(-radius, radius + 1)),
            key=lambda p: (max(abs(p[0]), abs(p[1])), abs(p[0]) + abs(p[1]), p[1], p[0]))
        selected = tuple(ChunkKey(center.dimension, center.x + dx, center.y + dy)
                         for dx, dy in offsets[:self.cache_limit])
        retained = set(selected)
        for key in tuple(self._resident):
            if key not in retained:
                self._recycle(key, self._resident.pop(key))
        # Center is last touched, never evicted by neighborhood prefetch.
        for key in reversed(selected):
            self.get(key)
        return tuple(self._resident[key] for key in selected)

    def minimap(self, center, radius=2):
        self._key(center)
        integer(radius, "map radius", 0, MAX_MAP_RADIUS)
        result = []
        for y in range(center.y - radius, center.y + radius + 1):
            for x in range(center.x - radius, center.x + radius + 1):
                key = ChunkKey(center.dimension, x, y)
                status, biome = self._discovery.get(key, ("unknown", None))
                result.append({"dimension": center.dimension, "x": x, "y": y,
                               "status": status, "biome": biome})
        return result

    def to_dict(self):
        data = {
            "schema_version": 1 if self.generator_version == 1 else WORLD_SCHEMA_VERSION,
            "generator_version": self.generator_version,
            "world_seed": self.world_seed,
            "cache_limit": self.cache_limit,
            "dimensions": [{**asdict(spec), "biomes": list(spec.biomes)} for spec in self.dimensions],
            "catalog": [asset_to_dict(asset) for asset in self.catalog],
            "catalog_digest": self.catalog_digest,
            "discovery": [
                {**asdict(key), "status": self._discovery[key][0], "biome": self._discovery[key][1]}
                for key in sorted(self._discovery, key=lambda key: (key.dimension, key.x, key.y))
            ],
        }
        if self.generator_version >= 2:
            data["region_catalog"] = [asdict(value) for value in self._generator.region_catalog.values()]
            data["region_catalog_digest"] = self.region_catalog_digest
        return data

    @classmethod
    def from_dict(cls, data):
        """Load v1 worlds unchanged and require pinned regions in v2 worlds."""
        if type(data) is not dict or type(data.get("schema_version")) is not int:
            raise ValueError("unsupported world schema")
        schema = data["schema_version"]
        if schema not in (1, WORLD_SCHEMA_VERSION):
            raise ValueError("unsupported world schema")
        required = ("schema_version", "generator_version", "world_seed", "cache_limit",
                    "dimensions", "catalog", "catalog_digest", "discovery")
        if schema == WORLD_SCHEMA_VERSION:
            required += ("region_catalog", "region_catalog_digest")
        fields(data, required)
        if (type(data["generator_version"]) is not int or
                data["generator_version"] not in SUPPORTED_GENERATOR_VERSIONS or
                data["generator_version"] != schema):
            raise ValueError("unsupported generator version")
        if any(type(data[name]) is not list for name in ("dimensions", "catalog", "discovery")):
            raise ValueError("world collections must be arrays")
        if not data["catalog"]:
            raise ValueError("pinned world catalog must not be empty")
        dimensions = []
        for raw in data["dimensions"]:
            fields(raw, ("id", "biomes", "width", "height", "danger"))
            if type(raw["biomes"]) is not list or any(type(b) is not str for b in raw["biomes"]):
                raise ValueError("dimension biomes must be an array")
            dimensions.append(DimensionSpec(**{**raw, "biomes": tuple(raw["biomes"])}))
        catalog = tuple(asset_from_dict(raw) for raw in data["catalog"])
        region_catalog = None
        if schema == WORLD_SCHEMA_VERSION:
            from .catalog import RegionDef
            if type(data["region_catalog"]) is not list or not data["region_catalog"]:
                raise ValueError("region catalog must be a nonempty array")
            try:
                regions = [RegionDef(**raw) for raw in data["region_catalog"]]
            except (TypeError, ValueError) as exc:
                raise ValueError("invalid pinned region catalog") from exc
            region_catalog = {r.id: r for r in regions}
            if len(region_catalog) != len(regions):
                raise ValueError("duplicate pinned region")
        result = cls(data["world_seed"], tuple(dimensions), catalog, data["cache_limit"],
                     generator_version=data["generator_version"], region_catalog=region_catalog)
        if data["catalog_digest"] != result.catalog_digest:
            raise ValueError("world catalog digest mismatch")
        if schema == WORLD_SCHEMA_VERSION and data["region_catalog_digest"] != result.region_catalog_digest:
            raise ValueError("world region catalog digest mismatch")
        for raw in data["discovery"]:
            fields(raw, ("dimension", "x", "y", "status", "biome"))
            key = result._key(ChunkKey(raw["dimension"], raw["x"], raw["y"]))
            if key in result._discovery or raw["status"] not in ("generated", "visited"):
                raise ValueError("duplicate key or invalid discovery status")
            if raw["biome"] != result._generator.biome_for(key):
                raise ValueError("discovery biome does not match pinned world")
            result._discovery[key] = (raw["status"], raw["biome"])
        return result
