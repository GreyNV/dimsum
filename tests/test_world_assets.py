"""P2: offline registry/pipeline trust boundaries, durable retries and invariants."""
import json
from dataclasses import replace
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from dimensional_sim.world.assets import (
    AssetRegistry, MAX_ASSET_BYTES, builtin_assets, parse_asset,
)
from dimensional_sim.world.models import Cell, asset_to_dict, validate_asset
from dimensional_sim.world.pipeline import (
    AssetPipeline, GenerationRequest, LocalProvider, generation_jobs,
)
from dimensional_sim.world.seeds import canonical_json


class AssetTests(unittest.TestCase):
    def test_builtins_are_safe_reachable_and_geometry_qualified(self):
        identifiers = set()
        for width, height in ((8, 6), (32, 16), (128, 64)):
            assets = builtin_assets(width, height)
            self.assertEqual({a.biome for a in assets}, {"dark_forest", "ash_plain"})
            for asset in assets:
                validate_asset(asset)
                self.assertNotIn(asset.id, identifiers)
                identifiers.add(asset.id)
                self.assertTrue(all(not asset.collision[height//2][x] for x in range(width)))
                self.assertTrue(all(not asset.collision[y][width//2] for y in range(height)))
                self.assertNotIn("@", "".join(c.glyph for row in asset.environment for c in row))
        self.assertEqual(builtin_assets(), builtin_assets())

    def test_asset_parser_rejects_json_controls_dimensions_and_size(self):
        data = asset_to_dict(builtin_assets(8, 6)[0])
        wrong_dimensions = {**data, "width": 9}
        invalid_cell = json.loads(canonical_json(data))
        invalid_cell["environment"][1][1]["glyph"] = "\u001b"
        unknown = {**data, "unexpected": 1}
        invalid_inputs = [b"{", b'{"id":1,"id":2}', b'{"x":NaN}', b'{"x":1e999}', b"\xff",
                          b" " * (MAX_ASSET_BYTES + 1), b"[" * 10000,
                          canonical_json(wrong_dimensions), canonical_json(invalid_cell),
                          canonical_json(unknown)]
        for raw in invalid_inputs:
            with self.subTest(raw=str(raw)[:80]), self.assertRaises(ValueError):
                parse_asset(raw)
        self.assertEqual(parse_asset(canonical_json(data)), builtin_assets(8, 6)[0])

    def test_registry_validates_direct_adoption_and_copies(self):
        registry = AssetRegistry()
        original = builtin_assets(8, 6)[0]
        for invalid in (replace(original, id="../escape"), replace(original, collision=[]),
                        replace(original, environment=())):
            with self.assertRaises(ValueError):
                registry.register(invalid)
        # Deliberately bypass a nested frozen dataclass constructor to test the boundary.
        forged = Cell(".")
        object.__setattr__(forged, "glyph", "\x1b")
        bad = replace(original, environment=((forged,) + original.environment[0][1:],)
                      + original.environment[1:])
        with self.assertRaises(ValueError):
            registry.register(bad)
        self.assertEqual(registry.snapshot(), ())
        registry.register(original)
        self.assertEqual(registry.snapshot(), (original,))
        self.assertIsNot(registry.snapshot()[0], original)

    def test_registry_idempotent_immutable_order_and_reload(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            registry = AssetRegistry(root)
            assets = builtin_assets(8, 6)
            for asset in reversed(assets):
                registry.register(asset)
            before = {p.name: p.read_bytes() for p in root.iterdir()}
            original_digest = registry.digest
            registry.register(assets[0])
            self.assertEqual(before, {p.name: p.read_bytes() for p in root.iterdir()})
            with self.assertRaises(ValueError):
                registry.register(replace(assets[0], tags=("changed",)))
            reopened = AssetRegistry(root)
            self.assertEqual(reopened.digest, original_digest)
            self.assertEqual(reopened.snapshot(), tuple(sorted(assets, key=lambda a:a.id)))
            # Colon IDs are accepted, but filenames must be safe on Windows as well.
            reopened.register(replace(assets[0], id="forest:version.2"))
            self.assertTrue(all(":" not in p.name for p in root.iterdir()))

    def test_disk_tampering_rejected_even_for_otherwise_valid_assets(self):
        for mode in ("digest", "geometry", "filename", "extra"):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                registry = AssetRegistry(root)
                registry.register(builtin_assets(8, 6)[0])
                path = next(root.glob("*.json"))
                record = json.loads(path.read_text())
                if mode == "digest":
                    record["asset"]["tags"] = ["tampered"]
                elif mode == "geometry":
                    record["asset"]["width"] = 12
                elif mode == "filename":
                    path.rename(root/"wrong.json")
                else:
                    record["extra"] = 1
                if mode != "filename":
                    path.write_text(canonical_json(record))
                with self.assertRaises(ValueError):
                    AssetRegistry(root)


    def test_registry_failed_atomic_write_preserves_catalog(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            registry = AssetRegistry(root)
            assets = builtin_assets(8, 6)
            registry.register(assets[0])
            before = {p.name:p.read_bytes() for p in root.iterdir()}
            with patch("dimensional_sim.world.assets.os.replace", side_effect=OSError("disk failure")):
                with self.assertRaisesRegex(OSError, "disk failure"):
                    registry.register(assets[1])
            self.assertEqual(registry.snapshot(), (assets[0],))
            self.assertEqual(before, {p.name:p.read_bytes() for p in root.iterdir()})
            self.assertEqual(AssetRegistry(root).snapshot(), (assets[0],))

    def test_local_provider_request_job_count_and_determinism(self):
        request = GenerationRequest("dark_forest", 482910, chunks=24, width=64, height=32, variants=6)
        jobs = generation_jobs(request)
        self.assertEqual(len(jobs), 144)
        self.assertEqual(len({j.id for j in jobs}), 144)
        self.assertEqual(len({j.seed for j in jobs}), 144)
        provider = LocalProvider()
        first = provider.generate(jobs[0])
        self.assertEqual(first, provider.generate(jobs[0]))
        self.assertNotEqual(parse_asset(first).objects,
                            parse_asset(provider.generate(jobs[1])).objects)
        for kwargs in ({"seed": True}, {"width": 7}, {"height": 65},
                       {"chunks": 0}, {"variants": 17}, {"chunks": 256, "variants": 16},
                       {"biome": "../../x"}):
            with self.assertRaises(ValueError):
                GenerationRequest(**{**{"biome":"dark_forest","seed":1}, **kwargs})

    def test_pipeline_retries_only_rejected_after_process_reload(self):
        class Flaky:
            def __init__(self):
                self.calls = []
            def generate(self, job):
                self.calls.append(job.id)
                if job.chunk_index == 1:
                    return "{broken"
                return LocalProvider().generate(job)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            request = GenerationRequest("dark_forest", 9, chunks=3, width=8, height=6)
            provider = Flaky()
            registry = AssetRegistry(root/"catalog")
            pipeline = AssetPipeline(root/"work", registry, provider)
            report = pipeline.run(request)
            self.assertEqual([r["status"] for r in report["jobs"]], ["accepted","rejected","accepted"])
            failed_job = generation_jobs(request)[1]
            self.assertEqual(pipeline.stage_path(request, failed_job).read_bytes(), b"{broken")
            accepted_bytes = {p.name:p.read_bytes() for p in (root/"catalog").glob("*.json")}
            accepted_stages = {j.id:pipeline.stage_path(request,j).read_bytes()
                               for j in generation_jobs(request) if j.chunk_index != 1}
            class Tracking:
                calls = []
                def generate(self, job):
                    self.calls.append(job.id)
                    return LocalProvider().generate(job)
            fixed = Tracking()
            reopened = AssetRegistry(root/"catalog")
            again = AssetPipeline(root/"work", reopened, fixed)
            repaired = again.run(request)
            self.assertEqual(fixed.calls, [failed_job.id])
            self.assertEqual([r["status"] for r in repaired["jobs"]], ["accepted"]*3)
            self.assertEqual([r["attempts"] for r in repaired["jobs"]], [1,2,1])
            for name, raw in accepted_bytes.items():
                self.assertEqual((root/"catalog"/name).read_bytes(), raw)
            for j in generation_jobs(request):
                if j.id in accepted_stages:
                    self.assertEqual(again.stage_path(request,j).read_bytes(), accepted_stages[j.id])
            again.run(request)
            self.assertEqual(fixed.calls, [failed_job.id])

    def test_provider_exceptions_and_invalid_metadata_are_isolated(self):
        class Faulty:
            def generate(self, job):
                if job.chunk_index == 0:
                    raise RuntimeError("provider unavailable")
                if job.chunk_index == 1:
                    data = json.loads(LocalProvider().generate(job))
                    data["biome"] = "wrong_biome"
                    return canonical_json(data)
                if job.chunk_index == 2:
                    data = json.loads(LocalProvider().generate(job))
                    data["environment"][1][1]["glyph"] = "@"
                    return canonical_json(data)
                return LocalProvider().generate(job)
        with tempfile.TemporaryDirectory() as directory:
            registry = AssetRegistry()
            pipeline = AssetPipeline(Path(directory), registry, Faulty())
            result = pipeline.run(GenerationRequest("dark_forest", 1, chunks=4, width=8,height=6))
            self.assertEqual([r["status"] for r in result["jobs"]], ["rejected"]*3+["accepted"])
            self.assertEqual(len(registry.snapshot()), 1)
            self.assertIn("provider unavailable", result["jobs"][0]["error"])

    def test_oversized_and_nontext_provider_output_rejected(self):
        for payload in (42, b" "*(MAX_ASSET_BYTES+1), "\ud800"):
            with tempfile.TemporaryDirectory() as directory:
                class Invalid:
                    def generate(self, job): return payload
                registry = AssetRegistry()
                result = AssetPipeline(Path(directory), registry, Invalid()).run(
                    GenerationRequest("dark_forest", 1, width=8,height=6))
                self.assertEqual(result["jobs"][0]["status"], "rejected")
                self.assertEqual(registry.snapshot(), ())

    def test_accepted_manifest_missing_registry_is_explicit_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            request = GenerationRequest("dark_forest", 1, width=8,height=6)
            AssetPipeline(Path(directory), AssetRegistry(), LocalProvider()).run(request)
            with self.assertRaisesRegex(ValueError, "missing or changed"):
                AssetPipeline(Path(directory), AssetRegistry(), LocalProvider()).run(request)

    def test_manifest_tampering_fails_before_provider(self):
        with tempfile.TemporaryDirectory() as directory:
            request = GenerationRequest("dark_forest", 1, width=8,height=6)
            registry = AssetRegistry()
            pipeline = AssetPipeline(Path(directory), registry, LocalProvider())
            report = pipeline.run(request)
            report["jobs"][0]["id"] = "../escape"
            pipeline.manifest_path(request).write_text(canonical_json(report))
            with self.assertRaisesRegex(ValueError, "invalid manifest job"):
                pipeline.run(request)

    def test_crash_after_registration_reconciles_with_same_immutable_asset(self):
        with tempfile.TemporaryDirectory() as directory:
            request = GenerationRequest("ash_plain", 15, width=8,height=6)
            registry = AssetRegistry(Path(directory)/"catalog")
            pipeline = AssetPipeline(Path(directory)/"work", registry, LocalProvider())
            report = pipeline.run(request)
            report["jobs"][0].update(status="pending", digest=None, error=None)
            pipeline.manifest_path(request).write_text(canonical_json(report))
            before = {p.name:p.read_bytes() for p in (Path(directory)/"catalog").glob("*.json")}
            recovered = pipeline.run(request)
            self.assertEqual(recovered["jobs"][0]["status"],"accepted")
            self.assertEqual(recovered["jobs"][0]["attempts"],2)
            self.assertEqual(before, {p.name:p.read_bytes() for p in (Path(directory)/"catalog").glob("*.json")})


if __name__ == "__main__":
    unittest.main()
