"""The anchor camp: buildings, binding, the storage chest, camp crafting and carry load."""
import json
import unittest

from dimensional_sim.world import economy
from dimensional_sim.world.autopilot import SCHEMA_VERSION, Expedition, saves
from dimensional_sim.world.catalog import BY_ID
from dimensional_sim.world.runtime import Exploration
from dimensional_sim.world.session import BrowserSession
from dimensional_sim.world.simulate import location_policy
from dimensional_sim.world.seeds import canonical_json
from dimensional_sim.world.web import new_world
from camp_fixture import CHEST, STATION, away, to_camp
from save_fixture import v17


def fresh(seed=482910):
    e = Expedition(Exploration(new_world(seed), "forest"))
    while e.in_prologue:
        e.advance(500)
    e.knowledge.add("primitive_crafting")
    return e


def dump(e):
    return canonical_json(e.to_dict())


def finish(e, action):
    e._start_self(BY_ID[action])
    e.advance(e.task["duration_ms"])


def die(e):
    e.health = 0
    e.advance(0)
    assert e.anchor_ms is not None


class BuildingTests(unittest.TestCase):
    def test_a_station_is_built_at_the_camp_and_teaches_the_building_discipline(self):
        e = away(fresh())
        e.inventory = {"stick": 12, "boar_hide": 2}
        self.assertIsNone(e._need_action(), "buildings go up only at the camp")
        self.assertEqual(e._need_action(at_camp=True).id, "build_station")
        to_camp(e, station=False)
        self.assertEqual(e.regular["building"], 0)
        finish(e, "build_station")
        self.assertIn(STATION, e.buildings)
        self.assertEqual(e.inventory, {})
        self.assertGreater(e.regular["building"], 0, "the first building adds the Building discipline")
        self.assertEqual(e.log[-1]["type"], "build")
        self.assertIsNone(e._need_action(), "a second station is never built")

    def test_crafts_need_the_station_at_the_camp(self):
        e = fresh()
        e.recipes.add("hide_wrap")
        e.inventory = {"boar_hide": 2}
        to_camp(e, station=False)
        self.assertIsNone(e._need_action())
        e.buildings.add(STATION)
        self.assertEqual(e._need_action().id, "craft_wrap")

    def test_unbound_buildings_fall_with_the_life_and_bound_ones_stay(self):
        for bind in (False, True):
            e = to_camp(fresh())
            die(e)
            e.ash = 500
            rows = {r["id"]: r for r in economy.offers(e) if r["kind"] == "bind"}
            self.assertTrue(rows[STATION]["available"])
            if bind:
                e.anchor_action({"type": "bind", "id": STATION})
                self.assertEqual(e.ash, 500 - rows[STATION]["cost"])
            e.anchor_action({"type": "begin_life"})
            self.assertEqual(STATION in e.buildings, bind)
            restored = Expedition.from_dict(json.loads(dump(e)))
            self.assertEqual(restored.buildings, e.buildings)
            self.assertEqual(restored.bound_buildings, e.bound_buildings)

    def test_binding_needs_a_lot_of_ash_and_a_built_building(self):
        e = to_camp(fresh())
        die(e)
        e.ash = 10
        with self.assertRaisesRegex(ValueError, "needs"):
            e.anchor_action({"type": "bind", "id": STATION})
        with self.assertRaises(ValueError):
            e.anchor_action({"type": "bind", "id": CHEST})


class ChestTests(unittest.TestCase):
    def test_the_chest_stows_materials_feeds_crafts_and_converts_unless_bound(self):
        e = to_camp(fresh())
        e.inventory = {"stick": 10, "iron_nails": 4, "rope": 2, "wild_berries": 2}
        finish(e, "build_chest")
        self.assertIn(CHEST, e.buildings)
        e.inventory = {"boar_hide": 2, "stick": 5, "wild_berries": 2}
        moved = e._stow()
        self.assertEqual(sorted(i for i, _ in moved), ["boar_hide", "stick"])
        self.assertEqual(e.chest, {"boar_hide": 2, "stick": 5})
        self.assertEqual(e.inventory, {"wild_berries": 2}, "food stays in the pack")
        e.recipes.add("hide_wrap")
        self.assertEqual(e._need_action().id, "craft_wrap", "the chest counts at the camp")
        finish(e, "craft_wrap")
        self.assertEqual(e.chest, {"stick": 5})
        ash = e.ash
        die(e)
        self.assertGreater(e.ash, ash)
        self.assertEqual(e.chest, {}, "an unbound chest turns into ash with the pack")

    def test_a_bound_chest_keeps_its_contents_for_the_next_life(self):
        e = to_camp(fresh())
        e.buildings.add(CHEST)
        e.inventory = {"stick": 7}
        e._stow()
        die(e)
        self.assertEqual(e.chest, {}, "not bound yet when this life ended: it became ash")
        e.ash = 1000
        e.anchor_action({"type": "bind", "id": CHEST})
        e.anchor_action({"type": "begin_life"})
        to_camp(e, station=False)
        e.inventory = {"stick": 7}
        e._stow()
        die(e)
        e.anchor_action({"type": "begin_life"})
        self.assertEqual(e.chest, {"stick": 7})
        self.assertIn(CHEST, e.buildings)
        self.assertNotIn(STATION, e.buildings, "only the bound building stays")
        restored = Expedition.from_dict(json.loads(dump(e)))
        self.assertEqual(restored.chest, {"stick": 7})

    def test_the_auto_pilot_leaves_camp_work_to_the_player(self):
        e = away(fresh())
        e.buildings.add(STATION)
        e.recipes.add("hide_wrap")
        e.inventory = {"boar_hide": 1}
        self.assertNotEqual((e._choose_goal() or {}).get("kind"), "home", "nothing to make yet")
        e.goal = None
        e.inventory = {"boar_hide": 2}
        self.assertNotEqual(e._choose_goal()["kind"], "home")


class LocationChoiceTests(unittest.TestCase):
    def test_camp_build_is_player_chosen_and_spot_work_stays_automatic(self):
        e = to_camp(fresh(), station=False)
        e.inventory = {"stick": 12, "boar_hide": 2}
        context = e.location_context()
        self.assertEqual(context["kind"], "anchor")
        row = next(row for row in context["actions"] if row["id"] == "build_station")
        self.assertFalse(row["reasons"])
        e._auto_step(1000, True)
        self.assertNotEqual((e.task or {}).get("type"), "build_station")
        e.anchor_action({"type": "location", "id": "build_station"})
        self.assertEqual(e.task["type"], "build_station")
        e.advance(e.task["duration_ms"])
        self.assertIn(STATION, e.buildings)
        self.assertNotIn("build_station", [row["id"] for row in e.location_context()["actions"] if not row["reasons"]])

    def test_anchor_visit_can_convert_now_without_converting_twice_at_death(self):
        e = to_camp(fresh())
        e.inventory = {"stick": 3}
        e.anchor_action({"type": "location", "id": "visit_anchor"})
        before = e.ash
        expected = economy.offer_value("stick", 2, e.converted.get("stick", 0))
        e.anchor_action({"type": "offer", "id": "stick", "count": 2})
        self.assertEqual(e.ash, before + expected)
        self.assertEqual(e.inventory["stick"], 1)
        self.assertEqual(e.converted["stick"], 2)
        e.anchor_action({"type": "resume"})
        self.assertGreater(e.contact_ready_ms, e.total_ms)
        with self.assertRaisesRegex(ValueError, "visiting"):
            e.anchor_action({"type": "offer", "id": "stick", "count": 1})
        expected_final = economy.rebirth_ash({"stick": 1}, e.depth, {"stick": 2})
        before_death = e.ash
        die(e)
        self.assertEqual(e.ash, before_death + expected_final)
        self.assertEqual(e.converted["stick"], 3)

    def test_wilderness_default_is_campfire(self):
        e = away(fresh())
        context = e.location_context()
        self.assertEqual(context["kind"], "wild")
        self.assertEqual(context["actions"][0]["name"], "Make a campfire")

    def test_browser_session_opens_anchor_and_offers_a_stack(self):
        e = to_camp(fresh())
        e.inventory = {"stick": 2}
        session = BrowserSession(e.game, e)
        base = {"move": None, "attack": False, "paused": True, "known": []}
        frame = session.input({**base, "action": {"type": "location", "id": "visit_anchor"}}, 0)
        self.assertTrue(frame["expedition"]["anchor_space"]["at_camp"])
        self.assertEqual(frame["expedition"]["anchor_offerings"][0]["count"], 2)
        frame = session.input({**base, "action": {"type": "offer", "id": "stick", "count": 2}}, 1)
        self.assertIsNone(frame["expedition"]["action_error"])
        self.assertFalse(frame["expedition"]["anchor_offerings"])

    def test_spend_simulator_policy_models_an_explicit_camp_choice(self):
        e = to_camp(fresh(), station=False)
        e.inventory = {"stick": 12, "boar_hide": 2}
        location_policy(e, "hoard")
        self.assertIsNone(e.task)
        location_policy(e, "spend")
        self.assertEqual(e.task["type"], "build_station")


class CarryLoadTests(unittest.TestCase):
    def test_load_slows_walking_and_strength_and_endurance_ease_it(self):
        e = fresh()
        e.inventory = {"stick": 10}
        self.assertEqual(e.load_percent(), 100)
        e.inventory = {"stick": 20, "boar_hide": 10}
        heavy = e.load_percent()
        self.assertEqual(heavy, 120)
        e.inventory = {item: 20 for item in ("stick", "boar_hide", "rope", "cloth_scrap", "iron_nails")}
        self.assertEqual(e.load_percent(), 160, "capped")
        e.inventory = {"stick": 20, "boar_hide": 10}
        e.regular["endurance"] = e.regular["strength"] = 5000
        self.assertLess(e.load_percent(), heavy)

    def test_movement_stretches_with_load_and_stays_partition_independent(self):
        a, b = fresh(), fresh()
        for e in (a, b):
            e.inventory = {"stick": 20, "boar_hide": 20, "rope": 10}
        a.advance(20_000)
        for _ in range(20):
            b.advance(1_000)
        self.assertEqual(dump(a), dump(b))
        a.advance(0)
        self.assertGreater(a.load_percent(), 100)
        self.assertEqual(a.game.step_interval_ms, a.game.movement_interval_ms * a.load_percent() // 100)
        self.assertEqual(dump(Expedition.from_dict(json.loads(dump(a)))), dump(a))


class SaveTests(unittest.TestCase):
    def test_schema_twelve_saves_gain_the_camp_and_the_building_discipline(self):
        e = fresh()
        gone = (*saves.V13_FIELDS, *saves.V14_FIELDS, *saves.V15_FIELDS, *saves.V16_FIELDS, *saves.V17_FIELDS)
        data = {k: v for k, v in v17(json.loads(dump(e))).items() if k not in gone}
        for name in ("regular", "dimensional", "life_gain"):
            data[name].pop("building")
        data["stats"].pop("built")
        data["schema_version"] = 12
        restored = Expedition.from_dict(data)
        self.assertEqual((restored.buildings, restored.bound_buildings, restored.chest), (set(), set(), {}))
        self.assertEqual(restored.regular["building"], 0)
        self.assertEqual(restored.to_dict()["schema_version"], SCHEMA_VERSION)


if __name__ == "__main__":
    unittest.main()
