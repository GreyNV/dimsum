import json
import os
import subprocess
import sys
import unittest
from dataclasses import replace

from dimensional_sim.world.models import (
    Cell, ChunkAsset, ChunkKey, DimensionSpec, Exit, Spawn, asset_from_dict,
    asset_to_dict, validate_asset,
)
from dimensional_sim.world.seeds import canonical_json, derive_seed


def fixture_asset():
    w, h = 8, 6
    exits = (Exit("north", 4, 0), Exit("east", 7, 3), Exit("south", 4, 5), Exit("west", 0, 3))
    points = {(e.x, e.y) for e in exits}
    return ChunkAsset("fixture", "dark_forest", w, h,
        tuple(tuple(Cell(".") for _ in range(w)) for _ in range(h)),
        tuple(tuple(None for _ in range(w)) for _ in range(h)),
        tuple(tuple((x in (0, w-1) or y in (0, h-1)) and (x,y) not in points
                    for x in range(w)) for y in range(h)),
        exits, (Spawn("player", "player", 4, 3),))


class ModelTests(unittest.TestCase):
    def test_seed_stable_across_process_hash_salts(self):
        code = "from dimensional_sim.world.seeds import derive_seed; print(derive_seed(482910,'forest',4,-7))"
        outputs = [subprocess.check_output([sys.executable, "-B", "-c", code],
            env={**os.environ, "PYTHONPATH": "src", "PYTHONHASHSEED": salt}, text=True).strip()
            for salt in ("1", "9876")]
        self.assertEqual(outputs[0], outputs[1])
        self.assertEqual(int(outputs[0]), 9855991639341736724)

    def test_seed_domains_and_types_do_not_alias(self):
        values = [derive_seed(5, *parts) for parts in [
            ("forest", 4, -7), ("forest", -7, 4), ("forest", "4", -7),
            ("forest", 4, 7), ("forest", 4, -7, "terrain"), ("forest", 4, -7, "loot")]]
        self.assertEqual(len(values), len(set(values)))
        for invalid in (-1, True, 2**64, 1.5):
            with self.assertRaises(ValueError): derive_seed(invalid)
        with self.assertRaises(ValueError): derive_seed(1, True)

    def test_asset_roundtrip_and_canonical_order(self):
        asset = fixture_asset()
        self.assertEqual(asset, asset_from_dict(json.loads(canonical_json(asset_to_dict(asset)))))
        self.assertEqual(canonical_json({"b": 2, "a": 1}), '{"a":1,"b":2}')

    def test_invalid_geometry_glyphs_colors_and_baked_player(self):
        asset = fixture_asset()
        for bad in ("\x1b", "\n", "xx", "\u6811"):
            with self.assertRaises(ValueError): Cell(bad)
        with self.assertRaises(ValueError): Cell(".", "red")
        row = (Cell("@"),) + asset.environment[0][1:]
        invalids = [replace(asset, width=True), replace(asset, objects=[]),
            replace(asset, environment=(row,) + asset.environment[1:]),
            replace(asset, spawns=(Spawn("player","player",0,0),))]
        for item in invalids:
            with self.assertRaises(ValueError): validate_asset(item)

    def test_unreachable_spawn_and_exit_rejected(self):
        asset = fixture_asset()
        blocked = [list(row) for row in asset.collision]
        for x,y in ((3,3),(5,3),(4,2),(4,4)): blocked[y][x] = True
        with self.assertRaises(ValueError):
            validate_asset(replace(asset, collision=tuple(map(tuple, blocked))))

    def test_parsing_rejects_unknown_fields_and_future_schema(self):
        for update in ({"schema_version": 2}, {"schema_version": True}, {"unexpected": 1}):
            with self.assertRaises(ValueError):
                asset_from_dict({**asset_to_dict(fixture_asset()), **update})

    def test_parser_rejects_string_collections_and_boolean_dimensions(self):
        for update in ({"tags": "abc"}, {"tags": [{}]}, {"width": True}, {"objects": "bad"}):
            with self.assertRaises(ValueError):
                asset_from_dict({**asset_to_dict(fixture_asset()), **update})

    def test_dimension_and_coordinate_validation(self):
        self.assertEqual(ChunkKey("forest", -4, -7).x, -4)
        for build in (lambda: DimensionSpec("x", width=2), lambda: DimensionSpec("x", danger=101), lambda: DimensionSpec("x", biomes=({},)),
                      lambda: ChunkKey("x", True, 0), lambda: ChunkKey("../x", 0, 0)):
            with self.assertRaises(ValueError): build()


class FastSeedTests(unittest.TestCase):
    def test_derive_seed_equals_canonical_json_hash(self):
        import hashlib
        import random
        from dimensional_sim.world.seeds import SEED_VERSION, canonical_json, derive_seed
        rng = random.Random(7)
        labels = ["tree", "detail", "a\"b", "back\\slash", "", "enc:forest:-1:3:10", "☃", "\n\t"]
        for _ in range(3000):
            parent = rng.randrange(2**64)
            parts = [rng.choice([rng.randint(-10**12, 10**12), rng.choice(labels)]) for _ in range(rng.randint(0, 6))]
            raw = canonical_json([SEED_VERSION, parent, parts]).encode("ascii")
            self.assertEqual(derive_seed(parent, *parts), int.from_bytes(hashlib.sha256(raw).digest()[:8], "big"))
        with self.assertRaises(ValueError):
            derive_seed(1, True)
