"""Validated, immutable asset catalogs and bundled offline terrain.

Example: registry = AssetRegistry(); registry.register(builtin_assets()[0]).
snapshot() is sorted by asset ID and safe to pin into a world's save.
Disk records are atomic, content-digested JSON. Storage is single-writer.
No provider, network, runtime or renderer dependency belongs in this module.
"""
import hashlib
import json
import math
import os
from pathlib import Path
import random
import tempfile

from .models import (Cell, ChunkAsset, Exit, Spawn, asset_from_dict, asset_to_dict,
                     fields, integer, validate_asset)
from .seeds import canonical_json, content_digest, derive_seed

MAX_ASSET_BYTES = 2 * 1024 * 1024


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON field")
        result[key] = value
    return result


def _finite_float(value):
    result = float(value)
    if not math.isfinite(result):
        raise ValueError("nonfinite JSON number")
    return result


def _reject_constant(value):
    raise ValueError("nonfinite JSON number")


def parse_json(raw, maximum=MAX_ASSET_BYTES):
    """Bound UTF-8 JSON, rejecting duplicate keys, nonfinite values and deep input."""
    if isinstance(raw, str):
        try:
            raw = raw.encode("utf-8")
        except UnicodeError as exc:
            raise ValueError("invalid UTF-8 JSON") from exc
    if not isinstance(raw, bytes) or len(raw) > maximum:
        raise ValueError("JSON exceeds size limit or is not text/bytes")
    try:
        return json.loads(raw.decode("utf-8"), object_pairs_hook=_unique_object,
                          parse_float=_finite_float, parse_constant=_reject_constant)
    except (UnicodeError, json.JSONDecodeError, RecursionError) as exc:
        raise ValueError("invalid JSON") from exc


def parse_asset(raw) -> ChunkAsset:
    """The bounded, strict entry point for untrusted provider/file payloads."""
    return asset_from_dict(parse_json(raw))


def _read(path, maximum=MAX_ASSET_BYTES):
    with Path(path).open("rb") as stream:
        raw = stream.read(maximum + 1)
    if len(raw) > maximum:
        raise ValueError("JSON exceeds size limit")
    return raw


def _atomic_write(path, raw):
    """Replace only after a complete fsynced temporary file in the same directory."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    name = None
    try:
        with tempfile.NamedTemporaryFile(mode="wb", dir=path.parent, delete=False) as out:
            name = out.name
            out.write(raw)
            out.flush()
            os.fsync(out.fileno())
        os.replace(name, path)
        name = None
    finally:
        if name is not None:
            Path(name).unlink(missing_ok=True)


def _filename(asset_id):
    # Model IDs permit colon, which is unsuitable in Windows paths.
    return hashlib.sha256(asset_id.encode("ascii")).hexdigest() + ".json"


class AssetRegistry:
    """Adopt only validated copies. Existing IDs can never change content.

    A disk registry revalidates every record and its digest on construction.
    Corruption is an explicit ValueError; valid records are never silently reset.
    Do not modify registry files manually; add a new ID for a changed template.
    """
    def __init__(self, root: Path | None = None):
        self.root = Path(root) if root is not None else None
        self._assets = {}
        self._digests = {}
        if self.root is not None and self.root.exists():
            if not self.root.is_dir():
                raise ValueError("registry root must be a directory")
            for path in sorted(self.root.glob("*.json")):
                data = parse_json(_read(path))
                fields(data, ("schema_version", "digest", "asset"))
                if type(data["schema_version"]) is not int or data["schema_version"] != 1:
                    raise ValueError("unsupported registry record")
                asset = asset_from_dict(data["asset"])
                digest = content_digest(asset_to_dict(asset))
                if digest != data["digest"] or path.name != _filename(asset.id):
                    raise ValueError("registry digest or filename mismatch")
                if asset.id in self._assets:
                    raise ValueError("duplicate registry asset")
                self._assets[asset.id] = asset
                self._digests[asset.id] = digest

    def register(self, asset: ChunkAsset) -> str:
        validate_asset(asset)
        # Reparse a copy as a second boundary: also rechecks nested Cell constructors.
        raw = canonical_json(asset_to_dict(asset)).encode("ascii")
        asset = parse_asset(raw)
        digest = content_digest(asset_to_dict(asset))
        if asset.id in self._assets:
            if self._digests[asset.id] != digest:
                raise ValueError("asset ID already has different immutable content")
            return digest
        if self.root is not None:
            record = {"schema_version": 1, "digest": digest, "asset": asset_to_dict(asset)}
            _atomic_write(self.root / _filename(asset.id), canonical_json(record).encode("ascii"))
        self._assets[asset.id] = asset
        self._digests[asset.id] = digest
        return digest

    def snapshot(self) -> tuple[ChunkAsset, ...]:
        return tuple(self._assets[key] for key in sorted(self._assets))

    @property
    def digest(self) -> str:
        return content_digest([asset_to_dict(asset) for asset in self.snapshot()])


def _template(biome, width, height, seed, asset_id):
    integer(width, "width", 8, 128)
    integer(height, "height", 6, 64)
    if biome not in ("dark_forest", "ash_plain"):
        raise ValueError("local provider supports dark_forest and ash_plain")
    cx, cy = width // 2, height // 2
    exits = (Exit("north", cx, 0), Exit("east", width - 1, cy),
             Exit("south", cx, height - 1), Exit("west", 0, cy))
    openings = {(e.x, e.y) for e in exits}
    forest = biome == "dark_forest"
    ground = Cell("." if forest else ",", "#75876b" if forest else "#a89b91",
                  "#17211b" if forest else "#282322")
    wall = Cell("T" if forest else "#", "#55714a" if forest else "#6e625c", ground.bg)
    rng = random.Random(derive_seed(seed, "template", biome))
    environment, objects, collision = [], [], []
    for y in range(height):
        env_row, obj_row, blocked_row = [], [], []
        for x in range(width):
            boundary = x in (0, width - 1) or y in (0, height - 1)
            # A full center cross is reserved for exits, safe entry and spawning.
            blocked = ((boundary and (x, y) not in openings) or
                       (not boundary and x != cx and y != cy and rng.random() < 0.16))
            env_row.append(ground)
            obj_row.append(wall if blocked else None)
            blocked_row.append(blocked)
        environment.append(tuple(env_row))
        objects.append(tuple(obj_row))
        collision.append(tuple(blocked_row))
    asset = ChunkAsset(asset_id, biome, width, height, tuple(environment), tuple(objects),
                       tuple(collision), exits,
                       (Spawn("player", "player", cx, cy), Spawn("enemy", "enemy", cx + 2, cy)),
                       ("bundled", "midpoint_exits"))
    validate_asset(asset)
    return asset


def builtin_assets(width=32, height=16) -> tuple[ChunkAsset, ...]:
    """Both supported biomes, collision-authoritative, no player art in locations."""
    return tuple(_template(biome, width, height, 0, f"builtin.{biome}.{width}x{height}.v1")
                 for biome in ("dark_forest", "ash_plain"))
