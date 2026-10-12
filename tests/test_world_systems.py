"""Content systems: enemies, biomes, effects, abilities and art keys come from the catalog.

These tests guard the rule "content is data": the engine must work for content it
has never seen by name, and every art key the catalog declares must have client art.
"""
import pathlib
import re
import unittest
from dataclasses import replace
from unittest.mock import patch

from dimensional_sim.world import effects
from dimensional_sim.world.autopilot import Expedition
from dimensional_sim.world.catalog import (
    ACTIONS, BIOMES, BOONS, BY_ID, CATEGORY_STYLES, ENEMIES, ITEMS, UNLOCKS, Effect, EnemyDef)
from dimensional_sim.world.models import ChunkKey
from dimensional_sim.world.runtime import Exploration, Target
from dimensional_sim.world.web import new_world

BROWSER = pathlib.Path(__file__).resolve().parents[1] / "src" / "dimensional_sim" / "world" / "browser"


def js_object_keys(source, name):
    """Top-level keys of `export const <name> = Object.freeze({...})` in a client module."""
    start = source.index(f"export const {name} = Object.freeze({{")
    body = source[start:source.index("});", start)]
    return set(re.findall(r"([a-z_]+):\s*(?:\{paint|[A-Z])", body))


def expedition(seed=482910):
    e = Expedition(Exploration(new_world(seed), "forest"))
    while e.in_prologue:
        e.advance(500)
    return e


class ArtCoverageTests(unittest.TestCase):
    def test_every_spot_and_lead_has_client_art(self):
        spots = js_object_keys((BROWSER / "place_art.js").read_text(encoding="utf-8"), "SPOTS")
        missing = sorted(a.sprite for a in ACTIONS if a.placement in ("spot", "lead") and a.enemy is None
                         and a.sprite not in spots)
        self.assertEqual(missing, [], "add these keys to place_art.js SPOTS")

    def test_every_enemy_has_client_art(self):
        sprites = js_object_keys((BROWSER / "combat_art.js").read_text(encoding="utf-8"), "ENEMY_SPRITES")
        self.assertEqual(sorted(e.sprite for e in ENEMIES.values() if e.sprite not in sprites), [])

    def test_every_category_has_a_style(self):
        self.assertEqual(set(CATEGORY_STYLES), {a.category for a in ACTIONS} | set(CATEGORY_STYLES))
        for action in ACTIONS:
            self.assertTrue(action.style.verb, action.id)


class EffectTests(unittest.TestCase):
    def test_gear_and_boons_combine_in_order(self):
        self.assertEqual(effects.total({"weapon": "walking_staff"}, None, "punch_damage"), 1)
        both = effects.scale(1000, {"body": "hide_wrap"}, "iron_skin", "enemy_hit_percent")
        self.assertEqual(both, 1000 * 70 // 100 * 75 // 100)
        self.assertEqual(effects.scale(1000, {}, None, "enemy_hit_percent"), 1000)
        self.assertEqual(effects.breakdown({"body": "hide_wrap"}, "iron_skin", "enemy_hit_percent"),
                         [("Hide wrap", 70), ("Iron skin boon", 75)])
        with self.assertRaises(ValueError):
            effects.total({}, None, "enemy_hit_percent")

    def test_a_new_gear_effect_needs_no_engine_change(self):
        spear = replace(ITEMS["walking_staff"], id="test_spear", name="Test spear",
                        effects=(Effect("punch_damage", 3),))
        with patch.dict(ITEMS, test_spear=spear):
            e = expedition()
            base = e.punch_damage()
            e.equipped = {"weapon": "test_spear"}
            self.assertEqual(e.punch_damage(), base + 3)

    def test_a_new_boon_effect_widens_food_windows(self):
        boon = replace(BOONS["bountiful_path"], id="test_feast", effects=(Effect("food_window_bonus", 2),))
        with patch.dict(BOONS, test_feast=boon):
            self.assertEqual(effects.total({}, "test_feast", "food_window_bonus"), 2)

    def test_effects_are_validated(self):
        with self.assertRaises(ValueError):
            Effect("flying", 1)
        with self.assertRaises(ValueError):
            Effect("enemy_hit_percent", 0)
        with self.assertRaises(ValueError):
            Effect("food_window_bonus", -1)
        with self.assertRaises(ValueError):
            Effect("punch_damage", -1)


class EnemyAndBiomeTests(unittest.TestCase):
    def test_enemy_numbers_come_from_the_catalog(self):
        e = expedition()
        key = ChunkKey("forest", 2, 0)
        boar = ENEMIES["bramble_boar"]
        stronger = replace(boar, hit=boar.hit * 2)
        self.assertGreater(e.enemy_hit(key, stronger), e.enemy_hit(key, boar))
        self.assertEqual(e.enemy_hp(BY_ID["bramble_boar"], key), BY_ID["bramble_boar"].hp + 2)

    def test_a_new_enemy_on_the_fight_spot_changes_combat_and_frontier(self):
        e = expedition()
        before = e.fight_damage(3, BY_ID["bramble_boar"])
        wolf = EnemyDef("test_wolf", "Test wolf", hit=30, aggro_radius=4, cause="boar",
                        cause_text="a test wolf", sprite="boar")
        fight = replace(BY_ID["bramble_boar"], enemy="test_wolf")
        with patch.dict(ENEMIES, test_wolf=wolf), patch.dict(BY_ID, bramble_boar=fight):
            self.assertGreater(e.fight_damage(3, fight), before)
            self.assertLessEqual(e.frontier(), 2, "a deadlier threat pulls the frontier in")
            self.assertEqual([a.enemy for a in e.threats()], ["test_wolf"])

    def test_enemy_identity_survives_eviction_of_its_origin_chunk(self):
        e = expedition()
        wolf = EnemyDef("test_wolf", "Test wolf", hit=30, aggro_radius=4, cause="boar",
                        cause_text="a test wolf", sprite="boar")
        fight = replace(BY_ID["bramble_boar"], id="test_wolf_fight", enemy="test_wolf")
        target_id = "enc:forest:20:0:999"
        target = Target(target_id, e.game.player.chunk, e.game.player.x + 1, e.game.player.y)
        e.game.targets[target_id] = target
        e.admitted[target_id] = fight.id
        self.assertIsNone(e._spot_by_id(target_id))
        with patch.dict(ENEMIES, test_wolf=wolf), patch.dict(BY_ID, test_wolf_fight=fight):
            self.assertEqual(e.target_action(target_id), fight)
            self.assertEqual(e.enemy_of(target), wolf)

    def test_biome_danger_curve_is_data(self):
        e = expedition()
        boar = ENEMIES["bramble_boar"]
        near, far = e.enemy_hit(ChunkKey("forest", 0, 0), boar), e.enemy_hit(ChunkKey("forest", 5, 0), boar)
        self.assertGreater(far, near)
        flat = replace(BIOMES["dark_forest"], danger_num=1, danger_den=1, hp_per_ring=0)
        with patch.dict(BIOMES, dark_forest=flat):
            self.assertEqual(e.enemy_hit(ChunkKey("forest", 5, 0), boar), near)
            self.assertEqual(e.enemy_hp(BY_ID["bramble_boar"], ChunkKey("forest", 5, 0)), BY_ID["bramble_boar"].hp)

    def test_frames_name_and_draw_enemies_from_the_catalog(self):
        from dimensional_sim.world.session import snapshot
        e = expedition()
        e.advance(120_000)
        frame = snapshot(e.game, expedition=e)
        for target in frame["targets"]:
            self.assertEqual((target["name"], target["sprite"]), ("Bramble boar", "boar"))
        for spot in frame["spots"]:
            self.assertEqual(spot["art"], BY_ID[spot["encounter"]].sprite)


class AbilityTests(unittest.TestCase):
    def test_return_to_anchor_is_an_ability_granted_by_an_unlock(self):
        e = expedition()
        self.assertFalse(e.has_ability("return_to_anchor"))
        owner = next(u.id for u in UNLOCKS.values() if u.ability == "return_to_anchor")
        e.unlocked.add(owner)
        self.assertTrue(e.has_ability("return_to_anchor"))


if __name__ == "__main__":
    unittest.main()
