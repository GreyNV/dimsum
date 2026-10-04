"""Versioned stable seeds, independent of process hash randomization and call order."""
import hashlib
import json

SEED_VERSION = "dimensional-world-seed-v1"


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
    raw = canonical_json([SEED_VERSION, parent, list(parts)]).encode("ascii")
    return int.from_bytes(hashlib.sha256(raw).digest()[:8], "big")


def content_digest(value) -> str:
    """SHA-256 of canonical data; useful for pinning catalogs and immutable assets."""
    return hashlib.sha256(canonical_json(value).encode("ascii")).hexdigest()
