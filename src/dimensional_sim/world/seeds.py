"""Versioned stable seeds, independent of process hash randomization and call order."""
import hashlib
import json

SEED_VERSION = "dimensional-world-seed-v1"
_encode_str = json.encoder.encode_basestring_ascii
_PREFIX = "[" + _encode_str(SEED_VERSION) + ","


def canonical_json(value) -> str:
    """Portable data-only canonical form used for saves, hashes and comparison."""
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
                      allow_nan=False)


def derive_seed(parent: int, *parts: str | int) -> int:
    """Derive an unsigned 64-bit child seed; signed coordinates are typed JSON ints."""
    if type(parent) is not int or not 0 <= parent < 2**64:
        raise ValueError("seed must be an unsigned 64-bit integer")
    if any(type(part) not in (str, int) for part in parts):
        raise ValueError("seed labels must be strings or integers, not booleans")
    # Byte-for-byte the canonical_json of [SEED_VERSION, parent, parts], built directly:
    # this is the hottest call in chunk generation (tests/test_world_models.py pins it).
    raw = _PREFIX + str(parent) + ",[" + ",".join(
        str(p) if type(p) is int else _encode_str(p) for p in parts) + "]]"
    return int.from_bytes(hashlib.sha256(raw.encode("ascii")).digest()[:8], "big")


def content_digest(value) -> str:
    """SHA-256 of canonical data; useful for pinning catalogs and immutable assets."""
    return hashlib.sha256(canonical_json(value).encode("ascii")).hexdigest()
