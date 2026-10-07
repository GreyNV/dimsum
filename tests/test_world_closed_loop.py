"""Closed-loop regression coverage: content catalog, action bucket, regions, spawn pity,
crafting, currencies, anchor purchases and observability (docs/design/DEFINITION_OF_DONE.md)."""
import json
import unittest
from dataclasses import replace

from dimensional_sim.world import autopilot as ap
from dimensional_sim.world import economy
from dimensional_sim.world.actions import Context, bucket, describe_bucket, explain
from dimensional_sim.world.autopilot import Expedition
from dimensional_sim.world.catalog import (ACTIONS, BOONS, BY_ID, ITEMS, REGIONS, UNLOCKS, ActionDef,
                                           validate_catalog)
from dimensional_sim.world.encounters import chunk_spots, forced_spot
from dimensional_sim.world.equipment import equip_item
from dimensional_sim.world.models import ChunkKey
from dimensional_sim.world.regions import region_for
from dimensional_sim.world.runtime import Exploration
from dimensional_sim.world.seeds import canonical_json
from dimensional_sim.world.session import BrowserSession, validate_input
from dimensional_sim.world.tuning import PITY_CHUNKS
from dimensional_sim.world.web import new_world

P = ap.POINT


def fresh(seed=482910):
    return Expedition(Exploration(new_world(seed), "forest"))


def past_prologue(e):
    while e.in_prologue:
        e.advance(500)
    return e


def dump(e):
    return canonical_json(e.to_dict())


def at_anchor(e):
    e.health = 0
    e.advance(0)
    assert e.anchor_ms is not None
    return e


class CatalogTests(unittest.TestCase):
    def test_catalog_validates_and_every_resource_has_a_source_and_sinks(self):
        validate_catalog()
        crafted_from = {item for a in ACTIONS for item, _ in a.cost}
        for item in ITEMS.values():
            with self.subTest(item=item.id):
                self.assertGreater(item.dust, 0, "every item is worth something at the anchor")
                in_run = {"food": item.food > 0, "material": item.id in crafted_from,
                          "gear": any(a.effect == item.id for a in ACTIONS)}[item.kind]
                self.assertTrue(in_run, "every item has an in-run use: eat, craft or wear")
        self.assertEqual({u.currency for u in UNLOCKS.values()} | {"blessing", "ash"},
                         {"dust", "ash", "blessing"}, "dust, ash and blessing all have sinks")

    def test_invalid_definitions_are_rejected(self):
        good = BY_ID["bramble_berries"]
        for change in ({"category": "dance"}, {"placement": "sky"}, {"unlock": None, "window": (3, 1)},
                       {"cost": (("stick", 1),)}, {"trigger": "need"}, {"effect": "stick"}, {"weight": 0}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                replace(good, **change)
        with self.assertRaises(ValueError):
            ActionDef("x", "X", "craft", "self", "strength", 1, 1, 1, "d", "l", trigger="need")

    def test_regions_are_deterministic_cover_all_and_anchor_is_the_old_road(self):
        seen = set()
        for seed in (1, 2, 482910):
            for y in range(-12, 13):
                for x in range(-12, 13):
                    key = ChunkKey("forest", x, y)
                    region = region_for(seed, "dark_forest", key)
                    self.assertIs(region, region_for(seed, "dark_forest", key))
                    seen.add(region.id)
            for x in (-1, 0, 1, 2):
                self.assertEqual(region_for(seed, "dark_forest", ChunkKey("forest", x % 3, 0)).id, "old_road")
        self.assertEqual(seen, set(REGIONS))


class ActionBucketTests(unittest.TestCase):
    def test_unlocking_adds_a_possibility_and_explain_says_why(self):
        ctx = Context(region="deep_woods")
        why = explain("gnarled_tree", ctx)
        self.assertFalse(why["eligible"])
        self.assertIn("locked", why["reasons"][0])
        unlocked = explain("gnarled_tree", replace(ctx, unlocked=frozenset({"climbing"})))
        self.assertTrue(unlocked["eligible"])
        self.assertGreater(unlocked["share_permille"], 0)
        self.assertIn("region", explain("wayside_shrine", Context(region="deep_woods",
                                                                  unlocked=frozenset({"shrine_path"})))["reasons"][0])

    def test_region_multipliers_shape_the_bucket(self):
        thicket = {r["id"]: r["weight"] for r in describe_bucket(Context(region="bramble_thicket"))}
        glade = {r["id"]: r["weight"] for r in describe_bucket(Context(region="still_glade"))}
        self.assertGreater(thicket["bramble_berries"], glade.get("bramble_berries", 0))
        self.assertGreater(glade["forest_spring"], thicket["forest_spring"])

    def test_self_bucket_checks_ingredients_gear_and_live_play(self):
        ctx = Context(placement="self", trigger="need", inventory={"stick": 2},
                      knowledge=frozenset({"primitive_crafting"}), recipes=frozenset({"walking_staff"}))
        self.assertIn("needs 3 stick", explain("craft_staff", ctx)["reasons"][0])
        ok = replace(ctx, inventory={"stick": 3})
        self.assertTrue(explain("craft_staff", ok)["eligible"])
        self.assertFalse(explain("craft_staff", replace(ok, gear=frozenset({"walking_staff"})))["eligible"])
        after = Context(placement="self", trigger="after_location", visible=False)
        self.assertNotIn("pray", [a.id for a, _ in bucket(after)])
        self.assertIn("pray", [a.id for a, _ in bucket(replace(after, visible=True))])

    def test_locked_actions_never_spawn_and_spots_are_deterministic(self):
        world = new_world(7)
        for y in range(-3, 4):
            for x in range(-3, 4):
                chunk = world.get(ChunkKey("forest", x, y))
                for region in REGIONS:
                    spots = chunk_spots(chunk, 2, region=region)
                    self.assertEqual(spots, chunk_spots(chunk, 2, region=region))
                    for spot in spots:
                        self.assertIsNone(BY_ID[spot.encounter].unlock)
        chunk = world.get(ChunkKey("forest", 1, 1))
        a = forced_spot(chunk, "bramble_boar", 0)
        self.assertEqual(a, forced_spot(chunk, "bramble_boar", 0))
        self.assertTrue(a.id.endswith(":10"))


class PlayableWorldTests(unittest.TestCase):
    """P0 regression: valid worlds must offer food and enemies early in every life."""

    def test_every_seed_offers_food_and_a_boar_within_eighteen_chunks(self):
        for seed in range(1, 13):
            with self.subTest(seed=seed):
                e = past_prologue(fresh(seed))
                while e.stats["chunks"] < 18 and e.life == 1:
                    e.advance(2000)
                self.assertGreaterEqual(e.stats["food_spots"], 1)
                self.assertGreaterEqual(e.stats["enemy_spots"], 1)
                self.assertTrue(all(e.budget[i] >= 1 for i in ("bramble_berries", "bramble_boar")),
                                "starting food and enemy windows never roll zero")

    def test_pity_forces_a_starved_category_and_says_so(self):
        e = past_prologue(fresh(3))
        e.drought["enemy"] = PITY_CHUNKS["enemy"] - 1
        e.screened_chunks = {c for c in e.screened_chunks if c != "forest:1:1"}
        chunk = e.game.world.get(ChunkKey("forest", 1, 1))
        before = e.stats["pity"]
        e.budget["bramble_boar"] = 9
        forced = e._pity(chunk, "forest:1:1", "enemy", [])
        self.assertTrue(forced)
        self.assertEqual(e.stats["pity"], before + 1)
        self.assertIn("pity enemy", e.screen_log[-2]["result"])
        # Forced spots use indices from 10 up (a food pity may already hold :10 in this chunk).
        self.assertTrue(any(s.encounter == "bramble_boar" and int(s.id.rsplit(":", 1)[1]) >= 10
                            for s in e._spots(chunk)))

    def test_new_run_reaches_eating_crafting_and_the_anchor(self):
        e = fresh(2)
        self.assertNotIn("walking_staff", e.recipes, "crafting is discovered, not a starting capability")
        while e.anchor_ms is None and e.total_ms < 60 * 60_000:
            e.advance(2000)
        self.assertIsNotNone(e.anchor_ms, "a life ends within 60 minutes")
        self.assertGreater(e.stats["completed"], 3)
        self.assertGreater(e.stats["eaten"], 0)
        # Branch gathering discovered primitive crafting and the staff recipe during this life.
        self.assertIn("primitive_crafting", e.knowledge)
        self.assertIn("walking_staff", e.recipes)
        self.assertGreater(e.stats["crafted"], 0)
        self.assertEqual(e.report["title"], "Life 1 ends")


class CraftingTests(unittest.TestCase):
    def test_staff_raises_damage_and_frontier_wrap_softens_hits(self):
        e = past_prologue(fresh())
        damage, frontier = e.punch_damage(), e.frontier()
        e.inventory = {"stick": 3}
        e.knowledge.add("primitive_crafting")
        e.recipes.add("walking_staff")
        e._start_self(BY_ID["craft_staff"])
        e.advance(e.task["duration_ms"])
        self.assertEqual(e.inventory, {"walking_staff": 1})
        self.assertEqual(e.punch_damage(), damage + 1)
        self.assertGreaterEqual(e.frontier(), frontier)
        hit = e.boar_hit(ChunkKey("forest", 2, 0))
        e.inventory["hide_wrap"] = 1
        e.equipped = equip_item(e.equipped, e.inventory, "hide_wrap")
        self.assertEqual(e.boar_hit(ChunkKey("forest", 2, 0)), hit * 70 // 100)

    def test_snare_turns_materials_into_food_only_when_needed(self):
        e = past_prologue(fresh())
        e.inventory = {"stick": 2, "bramble_thorn": 1}
        self.assertIsNone(e._need_action(), "snares need the unlock")
        e.unlocked.add("snares")
        e.hunger = 90 * P
        self.assertIsNone(e._need_action(), "not hungry: keep the materials")
        e.hunger = 30 * P
        self.assertEqual(e._need_action().id, "craft_snare")
        e._start_self(BY_ID["craft_snare"])
        e.hunger = 30 * P
        e.advance(e.task["duration_ms"])
        self.assertNotIn("stick", e.inventory)
        self.assertEqual(e.log[-1]["type"] if e.log[-1]["type"] != "eat" else e.log[-2]["type"], "craft")

    def test_interrupted_or_starved_craft_gives_nothing(self):
        e = past_prologue(fresh())
        e.inventory = {"stick": 1}
        e._complete_self(BY_ID["craft_staff"])
        self.assertEqual(e.inventory, {"stick": 1})


class EconomyTests(unittest.TestCase):
    def test_offer_has_diminishing_returns_and_rebirth_burns_to_ash(self):
        self.assertEqual(economy.offer_value("stick", 5), 5)
        self.assertEqual(economy.offer_value("stick", 9), 5 + 2)
        self.assertEqual(economy.offer_value("boar_hide", 2), 8)
        self.assertEqual(economy.rebirth_ash({"stick": 4, "boar_hide": 1}, 3), (4 + 4) // 2 + 3)

    def test_anchor_trade_unlock_mastery_boon_flow_changes_the_next_life(self):
        e = at_anchor(past_prologue(fresh()))
        e.inventory = {"stick": 3, "boar_hide": 1}
        e.anchor_action({"type": "trade", "item": "stick"})
        self.assertEqual(e.dust, 3)
        with self.assertRaises(ValueError) as err:
            e.anchor_action({"type": "unlock", "id": "climbing"})
        self.assertIn("needs 15 dust", str(err.exception))
        e.dust, e.blessing, e.ash = 100, 5, 20
        e.anchor_action({"type": "unlock", "id": "climbing"})
        e.anchor_action({"type": "boon", "id": "bountiful_path"})
        e.anchor_action({"type": "mastery", "id": "bramble_berries"})
        with self.assertRaises(ValueError):
            e.anchor_action({"type": "boon", "id": "iron_skin"})  # one boon per life
        self.assertEqual((e.dust, e.blessing, e.ash, e.mastery), (85, 3, 17, {"bramble_berries": 1}))
        restored = Expedition.from_dict(json.loads(dump(e)))
        self.assertEqual(dump(restored), dump(e))
        e.anchor_action({"type": "begin_life"})
        self.assertEqual((e.boon, e.boon_next, e.life), ("bountiful_path", None, 2))
        self.assertEqual(e.ash, 17 + economy.rebirth_ash({"boar_hide": 1}, 0))
        self.assertEqual(e.log[-1]["type"], "rebirth")
        low, high = BY_ID["bramble_berries"].window
        self.assertTrue(low + 1 <= e.budget["bramble_berries"] <= high + 1 + 1)
        ctx = e.spot_context(ChunkKey("forest", 0, 0))
        self.assertTrue(explain("gnarled_tree", ctx)["eligible"], "the unlock is in this life's bucket")

    def test_idle_rebirth_converts_unoffered_items_and_depth_to_ash(self):
        e = at_anchor(past_prologue(fresh()))
        e.inventory, e.depth = {"boar_meat": 2}, 4
        e.advance(ap.ANCHOR_COUNTDOWN_MS)
        self.assertEqual((e.life, e.ash, e.dust), (2, 3 + 4, 0))

    def test_shop_rows_explain_requirements(self):
        e = fresh()
        rows = {(r["kind"], r["id"]): r for r in economy.offers(e)}
        self.assertIn("requires Climbing", rows[("unlock", "mushroom_lore")]["reasons"])
        self.assertIn("unlock Climbing first", rows[("mastery", "gnarled_tree")]["reasons"])
        self.assertEqual(len([r for r in rows if r[0] == "boon"]), len(BOONS))


class ObservabilityTests(unittest.TestCase):
    def test_debug_info_and_session_debug_flag(self):
        e = past_prologue(fresh())
        e.advance(5000)
        info = e.debug_info()
        for key in ("world_seed", "region", "spot_bucket", "self_bucket", "why_not", "windows",
                    "drought", "screening", "stats", "currencies"):
            self.assertIn(key, info)
        self.assertTrue(any(r["id"] == "gnarled_tree" for r in info["why_not"]))
        session = BrowserSession(e.game, e)
        body = {"move": None, "attack": False, "paused": False, "known": [], "debug": True}
        frame = session.input(body, now=1)
        self.assertIsNotNone(frame["expedition"]["debug"])
        self.assertIn(frame["expedition"]["region"]["id"], REGIONS)
        self.assertTrue(all(c["region"] in REGIONS for c in frame["chunks"]))
        body["debug"] = False
        self.assertIsNone(session.input(body, now=2)["expedition"]["debug"])
        with self.assertRaises(ValueError):
            validate_input({**body, "action": {"type": "steal"}})
        at_anchor(e)
        refused = session.input({**body, "action": {"type": "unlock", "id": "road_lore"}}, now=3)
        self.assertIn("requires Meditation", refused["expedition"]["action_error"])
        self.assertIsNotNone(refused["expedition"]["shop"])
        self.assertIn("ash_if_burned", refused["expedition"]["anchor_space"])
        validate_input({**body, "action": {"type": "unlock", "id": "climbing"}})


if __name__ == "__main__":
    unittest.main()
