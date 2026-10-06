import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest
from dataclasses import replace
from unittest.mock import patch

from dimensional_sim.world.assets import AssetRegistry, builtin_assets
from dimensional_sim.world.generation import ChunkGenerator
from dimensional_sim.world.open_terrain import open_assets
from dimensional_sim.world.regions import region_for
from dimensional_sim.world.catalog import REGIONS
from dimensional_sim.world.models import (
    ChunkKey, DimensionSpec, Spawn, chunk_to_dict, validate_asset,
)
from dimensional_sim.world.repository import WorldRepository
from dimensional_sim.world.seeds import canonical_json, content_digest


def make_world(seed=482910, cache_limit=3, danger=25):
    return WorldRepository(seed, (DimensionSpec("forest", width=8, height=6, danger=danger),),
                           builtin_assets(8, 6), cache_limit)


def canonical(chunk):
    return canonical_json(chunk_to_dict(chunk))


class GenerationTests(unittest.TestCase):
    def test_reference_chunk_repeat_reverse_order_and_eviction(self):
        key = ChunkKey("forest", 4, -7)
        world = make_world(cache_limit=1)
        expected = canonical(world.get(key))
        self.assertEqual(expected, canonical(world.get(key)))
        self.assertEqual(world.generation_count, 1)
        keys = [key, ChunkKey("forest", -1, 2), ChunkKey("forest", 0, 0)]
        forward = {key: canonical(world.get(key)) for key in keys}
        other = make_world(cache_limit=1)
        reverse = {key: canonical(other.get(key)) for key in reversed(keys)}
        self.assertEqual(forward, reverse)
        self.assertIsNone(world.peek(key))
        self.assertEqual(expected, canonical(world.get(key)))
        self.assertEqual(world.status(key), "generated")

    def test_full_chunk_canonical_output_ignores_process_hash_salt(self):
        code = (
            "from dimensional_sim.world.repository import WorldRepository;"
            "from dimensional_sim.world.models import ChunkKey,chunk_to_dict;"
            "from dimensional_sim.world.seeds import canonical_json;"
            "print(canonical_json(chunk_to_dict("
            "WorldRepository(482910).get(ChunkKey('forest',4,-7)))))"
        )
        outputs = [subprocess.check_output([sys.executable, "-B", "-c", code],
            env={**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[1] / "src"),
                 "PYTHONHASHSEED": salt}, text=True).strip()
            for salt in ("1", "92341")]
        self.assertEqual(outputs[0], outputs[1])
        self.assertEqual(outputs[0], canonical(WorldRepository(482910).get(ChunkKey("forest", 4, -7))))

    def test_fifty_chunks_validate_and_preserve_reachable_exits_spawns(self):
        world = WorldRepository(482910, (
            DimensionSpec("forest", biomes=("dark_forest", "ash_plain"), width=16, height=10),))
        seen_biomes = set()
        for x in range(-5, 5):
            for y in range(-2, 3):
                chunk = world.get(ChunkKey("forest", x, y))
                validate_asset(chunk.asset)  # Includes flood-fill and forbidden player glyph.
                seen_biomes.add(chunk.asset.biome)
                self.assertTrue(all(s.kind in ("player", "enemy") for s in chunk.asset.spawns))
        self.assertEqual(seen_biomes, {"dark_forest", "ash_plain"})

    def test_world_seed_changes_actual_cells(self):
        key = ChunkKey("forest", 4, -7)
        first, second = make_world(1).get(key), make_world(2).get(key)
        self.assertNotEqual(first.asset.environment, second.asset.environment)

    def test_catalog_input_order_does_not_change_selection(self):
        assets = builtin_assets(8, 6)
        assets += (replace(assets[0], id="forest.variant2"),)
        dims = (DimensionSpec("forest", biomes=("dark_forest", "ash_plain"), width=8, height=6),)
        left, right = ChunkGenerator(32, dims, assets), ChunkGenerator(32, dims, tuple(reversed(assets)))
        self.assertEqual(left.catalog_digest, right.catalog_digest)
        for x in range(8):
            self.assertEqual(left.generate(ChunkKey("forest", x, -2)),
                             right.generate(ChunkKey("forest", x, -2)))

    def test_catalog_digest_matches_registry(self):
        world = make_world()
        registry = AssetRegistry()
        for asset in world.catalog:
            registry.register(asset)
        self.assertEqual(world.catalog_digest, registry.digest)

    def test_missing_biome_or_geometry_fails_before_generation(self):
        assets = builtin_assets(8, 6)
        for dims in ((DimensionSpec("x", biomes=("missing",), width=8, height=6),),
                     (DimensionSpec("x", width=9, height=6),)):
            with self.assertRaises(ValueError):
                ChunkGenerator(1, dims, assets)

    def test_danger_zero_removes_enemies_and_higher_danger_adds_reachable_spawns(self):
        key = ChunkKey("forest", 0, 0)
        safe, dangerous = make_world(danger=0).get(key), make_world(danger=100).get(key)
        self.assertEqual([s.kind for s in safe.asset.spawns], ["player"])
        self.assertGreaterEqual(sum(s.kind == "enemy" for s in dangerous.asset.spawns), 4)
        validate_asset(dangerous.asset)

    def test_heavily_authored_spawn_ids_cannot_overflow_generated_identifier(self):
        source = builtin_assets(64, 32)[0]
        player = next(spawn for spawn in source.spawns if spawn.kind == "player")
        points = [(x, player.y) for x in range(1, source.width - 1) if x != player.x][:59]
        for suffix_style in ("legacy", "numeric"):
            enemies = tuple(Spawn(
                "encounter-0" + ("-x" * index if suffix_style == "legacy"
                                  else (f"-{index}" if index else "")),
                "enemy", x, y) for index, (x, y) in enumerate(points))
            asset = replace(source, spawns=(player,) + enemies)
            validate_asset(asset)
            generator = ChunkGenerator(482910,
                (DimensionSpec("forest", width=64, height=32, danger=25),), (asset,))
            key = ChunkKey("forest", 4, -7)
            with self.subTest(suffix_style=suffix_style):
                chunk = generator.generate(key)
                validate_asset(chunk.asset)
                self.assertEqual(len(chunk.asset.spawns), len(asset.spawns) + 1)
                self.assertEqual(len({s.id for s in chunk.asset.spawns}), len(chunk.asset.spawns))
                self.assertTrue(all(len(s.id) <= 128 for s in chunk.asset.spawns))
                self.assertEqual(chunk, generator.generate(key))

    def test_invalid_generator_inputs_rejected(self):
        assets, dims = builtin_assets(8, 6), (DimensionSpec("forest", width=8, height=6),)
        for seed in (True, -1, 2**64, "1"):
            with self.assertRaises(ValueError): ChunkGenerator(seed, dims, assets)
        for catalog in ((), [], (assets[0], assets[0]), (object(),)):
            with self.assertRaises(ValueError): ChunkGenerator(1, dims, catalog)
        for dimensions in ((), [], (dims[0], dims[0]), (object(),)):
            with self.assertRaises(ValueError): ChunkGenerator(1, dimensions, assets)
        with self.assertRaises(ValueError): ChunkGenerator(1, dims, assets).generate(ChunkKey("nope", 0, 0))


class RegionTerrainTests(unittest.TestCase):
    def test_generator_versions_are_pinned_and_v1_worlds_still_replay(self):
        dimensions = (DimensionSpec("forest"),)
        assets = open_assets()
        old = WorldRepository(482910, dimensions, assets, generator_version=1)
        key = ChunkKey("forest", 4, -7)
        before = canonical(old.visit(key))
        self.assertEqual(content_digest(chunk_to_dict(old.get(key))),
                         "3226bb566c0c912eb4a38c7f24d493670a4c3c134645d1976c08e3febb4b6f3a")
        payload = json.loads(canonical_json(old.to_dict()))
        self.assertEqual(payload["generator_version"], 1)
        restored = WorldRepository.from_dict(payload)
        self.assertEqual(restored.generator_version, 1)
        self.assertEqual(canonical(restored.get(key)), before)
        self.assertEqual(json.loads(canonical_json(restored.to_dict())), payload)
        self.assertEqual(WorldRepository(482910, dimensions, assets).generator_version, 2)

    def test_v2_region_catalog_is_pinned_and_tampering_is_rejected(self):
        world = WorldRepository(91, (DimensionSpec("forest"),), open_assets())
        key = ChunkKey("forest", 0, 0)
        before = canonical(world.get(key))
        payload = json.loads(canonical_json(world.to_dict()))
        self.assertEqual(payload["schema_version"], 3)
        self.assertEqual(len(payload["region_catalog"]), 4)
        self.assertEqual(WorldRepository.from_dict(payload).region_for(key), world.region_for(key))
        self.assertEqual(canonical(WorldRepository.from_dict(payload).get(key)), before)
        with patch.dict(REGIONS, old_road=replace(REGIONS["old_road"], canopy=99)):
            restored = WorldRepository.from_dict(payload)
            self.assertEqual(restored.region_for(key), world.region_for(key))
            self.assertEqual(canonical(restored.get(key)), before)
        payload["region_catalog"][0]["canopy"] += 1
        with self.assertRaisesRegex(ValueError, "region catalog digest"):
            WorldRepository.from_dict(payload)

    def test_region_profiles_make_distinct_walkable_terrain(self):
        world = WorldRepository(482910, (DimensionSpec("forest"),), open_assets())
        first_by_region = {}
        for y in range(-9, 10):
            for x in range(-9, 10):
                key = ChunkKey("forest", x, y)
                region = region_for(world.world_seed, "dark_forest", key)
                first_by_region.setdefault(region.id, key)
        self.assertEqual(set(first_by_region), {"old_road", "deep_woods", "bramble_thicket", "still_glade"})
        glyphs = {}
        for region_id, key in first_by_region.items():
            chunk = world.get(key)
            validate_asset(chunk.asset)
            self.assertEqual(chunk, world.get(key))
            glyphs[region_id] = "".join(cell.glyph for row in chunk.asset.environment for cell in row)
        self.assertIn("o", glyphs["deep_woods"])
        self.assertIn(";", glyphs["bramble_thicket"])
        self.assertIn("~", glyphs["still_glade"])
        self.assertNotIn("~", glyphs["old_road"])

    def test_origin_ambush_marks_are_unique_safe_and_deterministic(self):
        dimensions = (DimensionSpec("forest"),)
        assets = open_assets()
        world = WorldRepository(482910, dimensions, assets)
        origin_key = ChunkKey("forest", 0, 0)
        origin = world.get(origin_key)
        validate_asset(origin.asset)
        marks = "".join(cell.glyph for row in origin.asset.environment for cell in row)
        self.assertIn("x", marks)
        self.assertIn(":", marks)
        spawn = next(s for s in origin.asset.spawns if s.kind == "player")
        for y in range(spawn.y - 1, spawn.y + 2):
            for x in range(spawn.x - 1, spawn.x + 2):
                self.assertFalse(origin.asset.collision[y][x])
        self.assertNotIn("@", marks)
        neighboring_road = world.get(ChunkKey("forest", 1, 0))
        other_marks = "".join(cell.glyph for row in neighboring_road.asset.environment for cell in row)
        self.assertNotIn("x", other_marks)
        self.assertNotIn(":", other_marks)
        legacy = WorldRepository(482910, dimensions, assets, generator_version=1).get(origin_key)
        legacy_marks = "".join(cell.glyph for row in legacy.asset.environment for cell in row)
        self.assertNotIn("x", legacy_marks)
        self.assertNotIn(":", legacy_marks)
        self.assertEqual(canonical(WorldRepository.from_dict(world.to_dict()).get(origin_key)),
                         canonical(origin))

    def test_new_region_layouts_change_with_seed_and_survive_reload(self):
        keys = [ChunkKey("forest", x, y) for y in range(-9, 10, 3) for x in range(-9, 10, 3)]
        layout = lambda seed: tuple(region_for(seed, "dark_forest", key).id for key in keys)
        self.assertEqual(layout(482910), layout(482910))
        self.assertNotEqual(layout(482910), layout(482911))
        world = WorldRepository(482910, (DimensionSpec("forest"),), open_assets(), cache_limit=1)
        first = canonical(world.get(keys[0]))
        for key in keys[1:]:
            world.get(key)
        self.assertEqual(canonical(WorldRepository.from_dict(world.to_dict()).get(keys[0])), first)


class RepositoryTests(unittest.TestCase):
    def test_new_world_empty_optional_catalog_uses_builtins_and_supports_multiple_sizes(self):
        default, empty = WorldRepository(), WorldRepository(assets=())
        self.assertEqual(default.catalog, empty.catalog)
        world = WorldRepository(dimensions=(
            DimensionSpec("large"), DimensionSpec("small", biomes=("ash_plain",), width=8, height=6)))
        self.assertEqual(world.get(ChunkKey("large", 0, 0)).asset.width, 32)
        self.assertEqual(world.get(ChunkKey("small", 0, 0)).asset.width, 8)
        self.assertEqual(world.get(ChunkKey("small", 0, 0)).asset.biome, "ash_plain")

    def test_world_identity_is_read_only_and_registry_changes_do_not_repin(self):
        registry = AssetRegistry()
        for asset in builtin_assets(8, 6):
            registry.register(asset)
        world = WorldRepository(482910, (DimensionSpec("forest", width=8, height=6),), registry.snapshot())
        before = canonical(world.get(ChunkKey("forest", 4, -7)))
        digest = world.catalog_digest
        registry.register(replace(registry.snapshot()[0], id="new.template"))
        self.assertNotEqual(registry.digest, digest)
        self.assertEqual(world.catalog_digest, digest)
        self.assertEqual(before, canonical(world.get(ChunkKey("forest", 4, -7))))
        for name, value in (("world_seed", 4), ("dimensions", ()), ("catalog", ()), ("cache_limit", 0)):
            with self.assertRaises(AttributeError):
                setattr(world, name, value)

    def test_map_unknown_generated_and_visited_without_side_effects(self):
        world = make_world()
        center, generated = ChunkKey("forest", 0, 0), ChunkKey("forest", 1, 0)
        self.assertEqual(world.status(center), "unknown")
        self.assertIsNone(world.peek(center))
        world.get(generated)
        world.visit(center)
        before, count, resident = world.to_dict(), world.generation_count, world.resident_count
        with patch.object(world._generator, "generate", side_effect=AssertionError("map generated")):
            cells = world.minimap(center, 1)
        lookup = {(c["x"], c["y"]): c for c in cells}
        self.assertEqual(lookup[(0, 0)]["status"], "visited")
        self.assertEqual(lookup[(1, 0)]["status"], "generated")
        self.assertEqual(lookup[(-1, 0)]["status"], "unknown")
        self.assertIsNone(lookup[(-1, 0)]["biome"])
        self.assertEqual(before, world.to_dict())
        self.assertEqual((count, resident), (world.generation_count, world.resident_count))

    def test_read_only_peek_does_not_change_lru(self):
        world = make_world(cache_limit=2)
        a, b, c = (ChunkKey("forest", x, 0) for x in range(3))
        world.get(a)
        world.get(b)
        world.peek(a)
        world.get(c)
        self.assertIsNone(world.peek(a))
        self.assertIsNotNone(world.peek(b))

    def test_stream_bounds_cache_retains_center_and_does_not_visit(self):
        world = make_world(cache_limit=3)
        for x in (-9, 0, 20):
            center = ChunkKey("forest", x, -7)
            chunks = world.stream(center, 2)
            self.assertEqual(len(chunks), 3)
            self.assertLessEqual(world.resident_count, 3)
            self.assertIsNotNone(world.peek(center))
            self.assertTrue(all(world.status(c.key) == "generated" for c in chunks))
            self.assertTrue(all(abs(c.key.x-center.x) <= 2 and abs(c.key.y-center.y) <= 2 for c in chunks))
        count = world.generation_count
        world.stream(center, 2)
        self.assertEqual(world.generation_count, count)
        world.stream(center, 0)
        self.assertEqual(world.resident_count, 1)

    def test_visited_discovery_survives_eviction(self):
        world = make_world(cache_limit=1)
        key = ChunkKey("forest", -2, -3)
        original = world.visit(key)
        world.stream(ChunkKey("forest", 100, 100))
        self.assertIsNone(world.peek(key))
        self.assertEqual(world.status(key), "visited")
        self.assertEqual(original, world.get(key))
        self.assertEqual(world.status(key), "visited")

    def test_snapshot_roundtrip_no_resident_grids_and_identical_future(self):
        world = make_world()
        center = ChunkKey("forest", -4, -7)
        world.visit(center)
        world.stream(center)
        payload = json.loads(canonical_json(world.to_dict()))
        restored = WorldRepository.from_dict(payload)
        self.assertEqual(restored.resident_count, 0)
        self.assertEqual(restored.generation_count, 0)
        self.assertEqual(restored.to_dict(), world.to_dict())
        self.assertEqual(restored.status(center), "visited")
        for key in (center, ChunkKey("forest", 4, -7), ChunkKey("forest", 999, -123)):
            self.assertEqual(canonical(world.get(key)), canonical(restored.get(key)))

    def test_loading_pinned_world_does_not_use_bundled_fallback(self):
        payload = json.loads(canonical_json(make_world().to_dict()))
        with patch("dimensional_sim.world.assets.builtin_assets", side_effect=AssertionError("fallback")):
            restored = WorldRepository.from_dict(payload)
        self.assertEqual(restored.catalog_digest, payload["catalog_digest"])
        payload["catalog"] = []
        with self.assertRaises(ValueError): WorldRepository.from_dict(payload)

    def test_corrupt_future_and_malformed_snapshots_rejected(self):
        world = make_world()
        world.visit(ChunkKey("forest", 0, 0))
        snapshot = json.loads(canonical_json(world.to_dict()))
        changes = (
            lambda p: p.update(schema_version=4),
            lambda p: p.update(schema_version=True),
            lambda p: p.update(generator_version=3),
            lambda p: p.update(generator_version=True),
            lambda p: p.update(world_seed=True),
            lambda p: p.update(cache_limit=0),
            lambda p: p.update(catalog_digest="tampered"),
            lambda p: p.update(unexpected=1),
            lambda p: p.update(dimensions=[]),
            lambda p: p.update(discovery={}),
            lambda p: p["discovery"].append(p["discovery"][0]),
            lambda p: p["discovery"][0].update(status="unknown"),
            lambda p: p["discovery"][0].update(biome="ash_plain"),
            lambda p: p["discovery"][0].update(dimension="missing"),
            lambda p: p["discovery"][0].update(x=True),
            lambda p: p["dimensions"][0].update(width=100),
            lambda p: p["dimensions"][0].update(biomes=[{}]),
            lambda p: p["catalog"][0]["environment"][0][0].update(glyph="@"),
        )
        for change in changes:
            payload = copy.deepcopy(snapshot)
            change(payload)
            with self.subTest(payload=str(payload)[:70]):
                with self.assertRaises(ValueError): WorldRepository.from_dict(payload)

    def test_tampered_catalog_without_recomputed_digest_rejected(self):
        payload = json.loads(canonical_json(make_world().to_dict()))
        payload["catalog"][0]["environment"][1][1]["fg"] = "#ffffff"
        with self.assertRaises(ValueError): WorldRepository.from_dict(payload)

    def test_invalid_cache_radius_and_keys_rejected_without_mutation(self):
        for limit in (True, 0, -1, 4097, 1.2):
            with self.assertRaises(ValueError): make_world(cache_limit=limit)
        world = make_world()
        before = world.to_dict()
        for radius in (True, -1, 33, 1.2):
            with self.assertRaises(ValueError): world.stream(ChunkKey("forest", 0, 0), radius)
            with self.assertRaises(ValueError): world.minimap(ChunkKey("forest", 0, 0), radius)
        for operation in (world.get, world.peek, world.visit, world.status):
            with self.assertRaises(ValueError): operation(ChunkKey("missing", 0, 0))
            with self.assertRaises(ValueError): operation("not a key")
        self.assertEqual(before, world.to_dict())


if __name__ == "__main__":
    unittest.main()
