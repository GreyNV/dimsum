"""Content systems: enemies, biomes, effects, abilities and art keys come from the catalog.

These tests guard the rule "content is data": the engine must work for content it
has never seen by name, and every art key the catalog declares must have client art.
"""
import pathlib
import re
import unittest
from dataclasses import replace
from unittest.mock import patch

from dimensional_sim.world import drops, effects
from dimensional_sim.world.actions import Context, spot_shares, spot_tiers
from dimensional_sim.world.encounters import roll_loot
from dimensional_sim.world.autopilot import Expedition
from dimensional_sim.world.catalog import (
    ACTIONS, BIOMES, BY_ID, CATEGORY_STYLES, DROP_TABLES, ENEMIES, ITEMS, UNLOCKS, DropTable, Effect,
    EnemyDef, Pick, validate_catalog)
from dimensional_sim.world.models import ChunkKey
from gear_fixture import TEST_STAFF, test_weapon
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
        missing = sorted(a.sprite for a in ACTIONS if a.placement in ("spot", "lead", "site") and a.enemy is None
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
    def test_gear_effects_combine_in_slot_order(self):
        with test_weapon():
            self.assertEqual(effects.total({"weapon": "test_staff"}, "punch_damage"), 1)
        both = effects.scale(1000, {"body": "hide_wrap"}, "enemy_hit_percent")
        self.assertEqual(both, 1000 * 70 // 100)
        self.assertEqual(effects.scale(1000, {}, "enemy_hit_percent"), 1000)
        self.assertEqual(effects.breakdown({"body": "hide_wrap"}, "enemy_hit_percent"), [("Hide wrap", 70)])
        with self.assertRaises(ValueError):
            effects.total({}, "enemy_hit_percent")

    def test_a_new_gear_effect_needs_no_engine_change(self):
        spear = replace(TEST_STAFF, id="test_spear", name="Test spear",
                        effects=(Effect("punch_damage", 3),))
        with patch.dict(ITEMS, test_spear=spear):
            e = expedition()
            base = e.punch_damage()
            e.equipped = {"weapon": "test_spear"}
            self.assertEqual(e.punch_damage(), base + 3)

    def test_a_new_gear_effect_widens_food_windows(self):
        feast = replace(TEST_STAFF, id="test_feast", effects=(Effect("food_window_bonus", 2),))
        with patch.dict(ITEMS, test_feast=feast):
            self.assertEqual(effects.total({"weapon": "test_feast"}, "food_window_bonus"), 2)

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
            self.assertIn("test_wolf", [a.enemy for a in e.threats()])
            self.assertNotIn("bramble_boar", [a.enemy for a in e.threats()])

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
            self.assertEqual((target["name"], target["sprite"]), ("Wild boar", "boar"))
        for spot in frame["spots"]:
            self.assertEqual(spot["art"], BY_ID[spot["encounter"]].sprite)


class RarityTests(unittest.TestCase):
    EVERYTHING = frozenset(UNLOCKS)

    def test_cascade_tries_rarest_first_and_skips_empty_tiers(self):
        self.assertEqual(drops.tier_chances({"rare": 1000, "uncommon": 2000}, {"rare", "uncommon", "common"}),
                         {"rare": 1000, "uncommon": 1800, "common": 7200})
        self.assertEqual(drops.tier_chances({"rare": 1000, "uncommon": 2000}, {"uncommon", "common"}),
                         {"uncommon": 2000, "common": 8000}, "an empty tier is not rolled")
        self.assertEqual(drops.tier_chances({"uncommon": 2000}, {"uncommon"}), {"uncommon": 10000})
        self.assertIsNone(drops.cascade({}, set(), 1))
        hits = sum(drops.cascade({"rare": 1000, "uncommon": 2000}, {"rare", "uncommon", "common"}, s) == "rare"
                   for s in range(20000))
        self.assertAlmostEqual(hits / 20000, 0.10, delta=0.01)

    def test_spot_shares_sum_to_one_and_match_the_tiers(self):
        for region in (None, "old_road", "still_glade", "deep_woods"):
            ctx = Context(region=region, unlocked=self.EVERYTHING)
            shares = spot_shares(ctx)
            self.assertGreater(sum(shares.values()), 9900, region)
            uncommon = sum(v for k, v in shares.items() if BY_ID[k].rarity == "uncommon")
            self.assertGreater(uncommon, 0, region)

    def test_new_common_content_does_not_dilute_rarer_spots(self):
        ctx = Context(region="old_road", unlocked=self.EVERYTHING)
        before = {k: v for k, v in spot_shares(ctx).items() if BY_ID[k].rarity != "common"}
        extra = replace(BY_ID["bramble_berries"], id="test_weeds", weight=500)
        with patch("dimensional_sim.world.actions.ACTIONS", ACTIONS + (extra,)):
            after = {k: v for k, v in spot_shares(ctx).items() if BY_ID.get(k, extra).rarity != "common"}
        self.assertEqual(after, before)

    def test_tier_odds_grow_with_unlocked_tier_content(self):
        one = spot_tiers(Context(unlocked=frozenset({"road_lore"})))["uncommon"][1]
        more = spot_tiers(Context(unlocked=self.EVERYTHING))["uncommon"][1]
        self.assertGreater(more, one)
        self.assertNotIn("uncommon", spot_tiers(Context()), "nothing uncommon known: tier skipped")

    def test_depth_bonus_is_a_biome_field_and_off_by_default(self):
        ctx, deep = Context(unlocked=self.EVERYTHING), Context(unlocked=self.EVERYTHING, ring=6)
        self.assertEqual(spot_tiers(ctx)["uncommon"][1], spot_tiers(deep)["uncommon"][1])
        steep = replace(BIOMES["dark_forest"], spot_rarity_per_ring=10)
        with patch.dict(BIOMES, dark_forest=steep):
            self.assertEqual(spot_tiers(deep)["uncommon"][1], spot_tiers(ctx)["uncommon"][1] * 160 // 100)

    def test_drop_tables_cascade_nest_and_report_exact_chances(self):
        chances = drops.table_chances("boar_spoils")
        self.assertEqual(chances["boar_tusk"][2], 1470)
        self.assertEqual(chances["amber_charm"][2], 50, "rare 2% x the nested table's 25%")
        tally = {}
        for seed in range(40000):
            for item, count, tier in drops.roll_table("boar_spoils", seed):
                tally[item] = tally.get(item, 0) + 1
                self.assertEqual(tier, "rare" if item != "boar_tusk" else "uncommon")
        self.assertAlmostEqual(tally["boar_tusk"] / 40000, 0.147, delta=0.01)

    def test_bonus_drops_add_to_fixed_loot_without_changing_it(self):
        boar = BY_ID["bramble_boar"]
        plain = replace(boar, drops=None)
        bonus = 0
        for seed in range(3000):
            with_table, without = roll_loot(boar, seed), roll_loot(plain, seed)
            self.assertEqual(with_table[:len(without)], without)
            self.assertLessEqual(len(with_table) - len(without), 1, "one bonus roll, at most one item")
            bonus += len(with_table) > len(without)
            self.assertEqual(with_table, roll_loot(boar, seed))
        self.assertGreater(bonus, 300)

    def test_drop_tables_are_validated(self):
        with self.assertRaises(ValueError):
            DropTable("bad", {"common": 100}, {"common": (Pick("stick"),)})
        with self.assertRaises(ValueError):
            DropTable("bad", {"rare": 100}, {})
        with self.assertRaises(ValueError):
            Pick("stick", table="forest_trinkets")
        loop = DropTable("loop", {"rare": 100}, {"rare": (Pick(table="loop"),)})
        with patch.dict(DROP_TABLES, loop=loop), self.assertRaisesRegex(ValueError, "cycle"):
            validate_catalog()

    def test_frames_mark_rare_spots_and_rare_items(self):
        from dimensional_sim.world.session import ITEM_GLINTS
        self.assertEqual(set(ITEM_GLINTS), {i for i, d in ITEMS.items() if d.rarity != "common"})
        e = expedition()
        e.unlocked.update(UNLOCKS)
        for _ in range(40):
            e.advance(5000)
        for spot in e.visible_spots():
            self.assertEqual(spot["glint"] is None, BY_ID[spot["encounter"]].rarity == "common")


class AbilityTests(unittest.TestCase):
    def test_contact_is_an_ability_granted_by_an_unlock_and_camp_is_not_sold(self):
        e = expedition()
        self.assertFalse(e.has_ability("contact_anchor"))
        owner = next(u.id for u in UNLOCKS.values() if u.ability == "contact_anchor")
        self.assertEqual((UNLOCKS[owner].currency, UNLOCKS[owner].cost), ("ash", 10))
        e.unlocked.add(owner)
        self.assertTrue(e.has_ability("contact_anchor"))
        self.assertFalse(any(u.ability == "make_campfire" for u in UNLOCKS.values()))


if __name__ == "__main__":
    unittest.main()
