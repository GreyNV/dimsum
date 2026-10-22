"""Landmark sites (generator v5): rare clearings with structures and their own encounters."""
import json
import unittest
from dataclasses import replace
from unittest.mock import patch

from dimensional_sim.world.actions import Context
from dimensional_sim.world.autopilot import Expedition
from dimensional_sim.world.catalog import BY_ID, LandDef, REGIONS, SITE_CELL, SITES, UNLOCKS
from dimensional_sim.world.encounters import _reachable, chunk_spots
from dimensional_sim.world.models import ChunkKey, DimensionSpec
from dimensional_sim.world.open_terrain import open_assets
from dimensional_sim.world.repository import WorldRepository
from dimensional_sim.world.runtime import Exploration
from dimensional_sim.world.seeds import canonical_json
from dimensional_sim.world.catalog import STRUCTURES
from dimensional_sim.world.sites import STRUCTURE_GLYPHS, bounded_site_plan, site_at
from dimensional_sim.world.web import new_world

SEED = 482910
AREA = [ChunkKey("forest", x, y) for y in range(-15, 16) for x in range(-15, 16)]


def sites(world):
    return {key: p for key in AREA if (p := world.site_for(key)) is not None}


def first(world, site_id):
    return next((key, p) for key, p in sorted(sites(world).items(), key=lambda kv: (abs(kv[0].x) + abs(kv[0].y),
                                                                                  kv[0].x, kv[0].y))
                if p.id == site_id)


class PlacementTests(unittest.TestCase):
    def test_sites_are_rare_spaced_out_far_from_the_anchor_and_pure(self):
        w = new_world(SEED)
        found = sites(w)
        self.assertGreaterEqual(len(found), len(SITES))
        self.assertLess(len(found), len(AREA) // SITE_CELL ** 2, "at most one per block, most blocks stay wild")
        blocks = [(k.x // SITE_CELL, k.y // SITE_CELL) for k in found]
        self.assertEqual(len(blocks), len(set(blocks)))
        for key, p in found.items():
            self.assertGreaterEqual(max(abs(key.x), abs(key.y)), p.site.min_ring)
            self.assertIn(w.region_for(key).id, p.site.weights)
        self.assertEqual({p.id for p in found.values()}, set(SITES))
        self.assertEqual(found, sites(new_world(SEED)))
        self.assertNotEqual(set(found), set(sites(new_world(SEED + 1))))

    def test_terrain_has_a_reachable_clearing_with_its_structures(self):
        w = new_world(SEED)
        for site_id, site in SITES.items():
            key, p = first(w, site_id)
            asset = w.get(key).asset
            reachable = _reachable(asset)
            inside = [(x, y) for y in range(asset.height) for x in range(asset.width) if p.contains(x, y)]
            glyphs = {asset.objects[y][x].glyph for x, y in inside if asset.objects[y][x] is not None}
            self.assertTrue(glyphs & set(STRUCTURE_GLYPHS[site.structure]), site_id)
            # the clearing's top and bottom tips may be sealed off behind a structure and grow back
            body = {asset.objects[y][x].glyph for x, y in inside if asset.objects[y][x] is not None
                    and abs(y - p.y) < p.ry}
            self.assertFalse(body & {"T", ";"}, "a clearing has no trees or brush")
            open_cells = [c for c in inside if not asset.collision[c[1]][c[0]]]
            self.assertGreater(len([c for c in open_cells if c in reachable]), len(inside) // 2, site_id)
            self.assertIn((p.x, p.y), reachable, "the centre row links the clearing to the trails")

    def test_every_site_chunk_validates_and_keeps_most_of_its_structures(self):
        kept = total = 0
        for seed in (1, 2, 3, 77):
            w = new_world(seed)
            for key, p in sites(w).items():
                asset = w.get(key).asset   # construction validates exits on all four sides
                mine = STRUCTURE_GLYPHS[p.site.structure]
                glyphs = [asset.objects[y][x].glyph for y in range(asset.height) for x in range(asset.width)
                          if asset.objects[y][x] is not None and asset.objects[y][x].glyph in mine]
                kept += len(glyphs) > 0
                total += 1
        self.assertGreater(kept, total * 3 // 4)

    def test_site_catalog_is_pinned_in_world_saves_and_older_worlds_have_none(self):
        w = new_world(SEED)
        before = sites(w)
        saved = json.loads(canonical_json(w.to_dict()))
        self.assertEqual(saved["schema_version"], 9)
        moved = {k: replace(v, weights={r: 1 for r in v.weights}) for k, v in SITES.items()}
        with patch.dict(SITES, moved):
            self.assertEqual(sites(WorldRepository.from_dict(saved)), before, "a catalog edit never moves sites")
            self.assertNotEqual(sites(new_world(SEED)), before)
        spec = DimensionSpec("forest", ("dark_forest",), 32, 16, 0)
        old = WorldRepository(SEED, (spec,), open_assets(32, 16), 9, generator_version=4)
        self.assertEqual(sites(old), {})

    def test_older_worlds_pinning_retired_actions_still_load(self):
        from dimensional_sim.world.seeds import content_digest
        spec = DimensionSpec("forest", ("dark_forest",), 32, 16, 0)
        old = WorldRepository(SEED, (spec,), open_assets(32, 16), 9, generator_version=4)
        saved = json.loads(canonical_json(old.to_dict()))
        for raw in saved["region_catalog"]:   # the camp and watchtower were spot actions until v12
            if raw["id"] == "old_road":
                raw["weights"].update(abandoned_camp=300, fallen_watchtower=200)
        saved["region_catalog_digest"] = content_digest(saved["region_catalog"])
        loaded = WorldRepository.from_dict(saved)
        self.assertEqual(loaded.region_for(ChunkKey("forest", 0, 0)).weights["abandoned_camp"], 300)
        saved["region_catalog"][0]["weights"]["no_such_action"] = 100
        saved["region_catalog_digest"] = content_digest(saved["region_catalog"])
        with self.assertRaises(ValueError):
            WorldRepository.from_dict(saved)

    def test_every_structure_has_glyphs_and_client_art(self):
        import pathlib, re
        self.assertEqual(set(STRUCTURE_GLYPHS), set(STRUCTURES))
        art = (pathlib.Path(__file__).parents[1] / "src/dimensional_sim/world/browser/art.js").read_text()
        block = art[art.index("export const STRUCTURE_ART"):]
        drawn = set(re.findall(r"^  ([A-Z]): \{paint:", block, re.M))
        from dimensional_sim.world.open_terrain import BROKEN_BRIDGE, DEADFALL
        self.assertEqual(drawn, {g for glyphs in STRUCTURE_GLYPHS.values() for g in glyphs} | {DEADFALL, BROKEN_BRIDGE},
                         "every site structure and the edge of the land (fallen trees, broken bridge) has art")

    def test_site_at_respects_region_weights(self):
        key = next(k for k in AREA if site_at(SEED, k, "old_road", 32, 16) is not None)
        self.assertIsNone(site_at(SEED, key, "nowhere", 32, 16))

    def test_every_bounded_land_has_each_fitting_landmark_and_replays_its_plan(self):
        from dimensional_sim.world.edges import chunk_open
        for seed in range(1, 21):
            world = new_world(seed)
            found = {key: world.site_for(key) for key in AREA if world.chunk_open(key)}
            found = {key: placement for key, placement in found.items() if placement is not None}
            self.assertEqual({placement.id for placement in found.values()}, set(SITES), seed)
            for key, placement in found.items():
                self.assertTrue(chunk_open(seed, key), key)
                self.assertIn(world.region_for(key).id, placement.site.weights)
            restored = WorldRepository.from_dict(json.loads(canonical_json(world.to_dict())))
            self.assertEqual(found, {key: restored.site_for(key) for key in found})

    def test_v7_landmarks_stay_pinned_until_the_world_regrows(self):
        current = new_world(SEED)
        old = WorldRepository(SEED, current.dimensions, current.catalog, generator_version=7)
        key = next(key for key in AREA if old.site_for(key) is not None)
        saved = json.loads(canonical_json(old.to_dict()))
        self.assertEqual(saved["schema_version"], 8)
        self.assertEqual(WorldRepository.from_dict(saved).site_for(key), old.site_for(key))
        for key in AREA:
            if current.chunk_open(key) and old.site_for(key) is not None:
                self.assertEqual(current.site_for(key), old.site_for(key),
                                 "v8 keeps existing natural rolls and adds only missing kinds")

    def test_a_missing_preferred_region_still_gets_its_landmark(self):
        spec = DimensionSpec("forest")
        land = LandDef("forest", "Test forest", 2, 2, 0)
        site = replace(SITES["ruined_shrine"], weights={"missing_region": 1}, min_ring=1)
        plan = bounded_site_plan(4, spec, land, {site.id: site},
                                 lambda key: REGIONS["old_road"], lambda key: "dark_forest", 32, 16)
        self.assertEqual({placement.id for placement in plan.values()}, {site.id})


class EncounterTests(unittest.TestCase):
    def test_site_encounters_roll_inside_the_clearing_once_unlocked(self):
        w = new_world(SEED)
        for site_id in SITES:
            unlocks = {a.unlock for a in BY_ID.values() if a.site == site_id}
            key, p = first(w, site_id)
            chunk, region = w.get(key), w.region_for(key)
            locked = chunk_spots(chunk, context=Context(region=region.id), site=p)
            self.assertFalse([s for s in locked if BY_ID[s.encounter].placement == "site"
                              and BY_ID[s.encounter].category != "fight"],
                             "a locked site is scenery (and its guards, if it has any)")
            ctx = Context(region=region.id, unlocked=frozenset(unlocks))
            spots = chunk_spots(chunk, context=ctx, site=p)
            mine = [s for s in spots if BY_ID[s.encounter].placement == "site"]
            low, high = p.site.spots
            self.assertTrue(low <= len(mine) <= high, site_id)
            self.assertEqual(len({s.encounter for s in mine}), len(mine), "each site encounter at most once")
            for s in mine:
                self.assertEqual(BY_ID[s.encounter].site, site_id)
                self.assertTrue(p.contains(s.x, s.y))
            self.assertEqual(spots, chunk_spots(chunk, context=ctx, site=p))
            self.assertEqual(len({s.id for s in spots}), len(spots))

    def test_the_expedition_rolls_site_spots_and_a_bedroll_teaches_the_jerkin(self):
        e = Expedition(Exploration(new_world(SEED), "forest"))
        while e.in_prologue:
            e.advance(500)
        e.unlocked.update(UNLOCKS)
        key, p = first(e.game.world, "abandoned_camp")
        chunk = e.game.world.get(key)
        e.game._enter(key)
        e.game.player.chunk = key
        spawn = next(s for s in chunk.asset.spawns if s.kind == "player")
        e.game.player.x, e.game.player.y = spawn.x, spawn.y
        e.game._reveal()
        e._screen()
        plan = e.spot_plans[f"forest:{key.x}:{key.y}"]
        self.assertTrue(any(BY_ID[a].site == "abandoned_camp" for a, _, _ in plan))
        e.game.player.x, e.game.player.y = p.x, p.y
        context = e.location_context()
        self.assertEqual(context["kind"], "landmark")
        self.assertEqual(context["name"], p.site.name)
        self.assertTrue(all(BY_ID[e._spot_by_id(row["id"]).encounter].site == p.id
                            for row in context["actions"]))
        restored = Expedition.from_dict(json.loads(canonical_json(e.to_dict())))
        self.assertEqual(restored.spot_plans, e.spot_plans)
        from dimensional_sim.world.journal import record_action
        record_action(e.journal, "camp_bedroll")
        e._apply_outcomes(BY_ID["camp_bedroll"], "enc:test:bedroll")
        self.assertIn("padded_jerkin", e.life_recipes)


if __name__ == "__main__":
    unittest.main()
