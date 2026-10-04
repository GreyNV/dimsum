"""OFFLINE generation only: provider -> staging -> validation -> immutable registry.

Runtime/world/animation/renderer must never import this module. Provider exceptions
are isolated per job; invalid output never reaches the registry. Re-running the
same request retries only rejected or unfinished jobs, including after restart.

Example:
    pipeline = AssetPipeline(Path("work"), AssetRegistry(Path("catalog")), LocalProvider())
    report = pipeline.run(GenerationRequest("dark_forest", 482910, chunks=24, variants=6))

Single-writer filesystem semantics. IDs derive from the entire versioned request.
Changing provider behavior requires a new request seed to produce new immutable IDs.
"""
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import Protocol

from .assets import (AssetRegistry, MAX_ASSET_BYTES, _atomic_write, _read, _template,
                     parse_asset, parse_json)
from .models import asset_to_dict, fields, identifier, integer
from .seeds import canonical_json, content_digest, derive_seed

MAX_MANIFEST_BYTES = 4 * 1024 * 1024


@dataclass(frozen=True)
class GenerationRequest:
    biome: str
    seed: int
    chunks: int = 1
    width: int = 32
    height: int = 16
    variants: int = 1

    def __post_init__(self):
        identifier(self.biome, "biome")
        integer(self.seed, "seed", 0, 2**64 - 1)
        integer(self.chunks, "chunks", 1, 256)
        integer(self.width, "width", 8, 128)
        integer(self.height, "height", 6, 64)
        integer(self.variants, "variants", 1, 16)
        if self.chunks * self.variants > 1024:
            raise ValueError("at most 1024 jobs per request")


@dataclass(frozen=True)
class GenerationJob:
    id: str
    biome: str
    seed: int
    width: int
    height: int
    chunk_index: int
    variant_index: int


class GenerationProvider(Protocol):
    """Provider receives deterministic job metadata, returns asset-schema1 JSON."""
    def generate(self, job: GenerationJob) -> str | bytes: ...


class LocalProvider:
    """Deterministic fixture provider; no AI, network, credentials or mutable RNG."""
    def generate(self, job: GenerationJob) -> str:
        asset = replace(_template(job.biome, job.width, job.height, job.seed, job.id),
                        tags=("local_generated", "midpoint_exits"))
        return canonical_json(asset_to_dict(asset))


def request_id(request: GenerationRequest) -> str:
    return content_digest({"pipeline_version": 1, "request": asdict(request)})


def generation_jobs(request: GenerationRequest) -> tuple[GenerationJob, ...]:
    identity = request_id(request)
    return tuple(GenerationJob(f"generated.{identity}.{chunk}.{variant}", request.biome,
                              derive_seed(request.seed, "asset-v1", identity, chunk, variant),
                              request.width, request.height, chunk, variant)
                 for chunk in range(request.chunks) for variant in range(request.variants))


class AssetPipeline:
    """Durable job ledger. run returns schema1 manifest with jobs in stable order.

    Each job has id,status ('pending','accepted','rejected'), attempts,digest,error.
    Provider failures/rejections are results, not whole-batch exceptions. Corrupt
    manifests/accepted catalog mismatches and storage failures raise immediately.
    Accepted stage files and registry bytes are never rewritten on retry.
    """
    def __init__(self, root: Path, registry: AssetRegistry, provider: GenerationProvider):
        self.root = Path(root)
        self.registry = registry
        self.provider = provider

    def manifest_path(self, request: GenerationRequest) -> Path:
        return self.root / "requests" / (request_id(request) + ".json")

    def stage_path(self, request: GenerationRequest, job: GenerationJob) -> Path:
        return self.root / "staging" / request_id(request) / (
            f"{job.chunk_index}-{job.variant_index}.json")

    def _save(self, request, manifest):
        _atomic_write(self.manifest_path(request), canonical_json(manifest).encode("ascii"))

    def _load(self, request, jobs):
        path = self.manifest_path(request)
        if not path.exists():
            return {"schema_version": 1, "request": asdict(request),
                    "jobs": [{"id": j.id, "status": "pending", "attempts": 0,
                              "digest": None, "error": None} for j in jobs]}
        manifest = parse_json(_read(path, MAX_MANIFEST_BYTES), MAX_MANIFEST_BYTES)
        fields(manifest, ("schema_version", "request", "jobs"))
        if (type(manifest["schema_version"]) is not int or manifest["schema_version"] != 1 or
            canonical_json(manifest["request"]) != canonical_json(asdict(request)) or
            not isinstance(manifest["jobs"], list) or len(manifest["jobs"]) != len(jobs)):
            raise ValueError("manifest request or schema mismatch")
        assets = {a.id: content_digest(asset_to_dict(a)) for a in self.registry.snapshot()}
        for job, record in zip(jobs, manifest["jobs"]):
            fields(record, ("id", "status", "attempts", "digest", "error"))
            integer(record["attempts"], "attempts", 0)
            if record["id"] != job.id or record["status"] not in ("pending", "accepted", "rejected"):
                raise ValueError("invalid manifest job")
            if record["status"] == "accepted":
                if record["digest"] != assets.get(job.id) or record["digest"] is None:
                    raise ValueError("accepted manifest asset is missing or changed")
                if record["error"] is not None:
                    raise ValueError("invalid accepted manifest error")
            elif record["digest"] is not None or (
                record["error"] is not None and not isinstance(record["error"], str)
            ):
                raise ValueError("invalid rejected manifest data")
        return manifest

    def run(self, request: GenerationRequest) -> dict:
        if not isinstance(request, GenerationRequest):
            raise ValueError("expected GenerationRequest")
        # Frozen dataclasses still pass through validation at public adoption boundaries.
        request = GenerationRequest(**asdict(request))
        jobs = generation_jobs(request)
        manifest = self._load(request, jobs)
        self._save(request, manifest)
        for job, record in zip(jobs, manifest["jobs"]):
            if record["status"] == "accepted":
                continue
            record["attempts"] += 1
            record.update(status="pending", digest=None, error=None)
            self._save(request, manifest)
            try:
                raw = self.provider.generate(job)
            except Exception as exc:
                record.update(status="rejected", error=f"provider: {type(exc).__name__}: {str(exc)[:1000]}")
                self._save(request, manifest)
                continue
            try:
                if isinstance(raw, str):
                    raw = raw.encode("utf-8")
                if not isinstance(raw, bytes) or len(raw) > MAX_ASSET_BYTES:
                    raise ValueError("provider output is not bounded text/bytes")
            except (ValueError, UnicodeError) as exc:
                record.update(status="rejected", error=f"payload: {str(exc)[:1000]}")
                self._save(request, manifest)
                continue
            # Untrusted bytes are persisted before parsing; staging is never a catalog.
            _atomic_write(self.stage_path(request, job), raw)
            try:
                asset = parse_asset(raw)
                if (asset.id, asset.biome, asset.width, asset.height) != (
                    job.id, job.biome, job.width, job.height
                ):
                    raise ValueError("asset does not match requested job identity/geometry")
                digest = self.registry.register(asset)
            except ValueError as exc:
                record.update(status="rejected", error=f"validation: {str(exc)[:1000]}")
            else:
                record.update(status="accepted", digest=digest, error=None)
            self._save(request, manifest)
        return manifest
