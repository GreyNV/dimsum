"""Player pages: journal recording, achievements, detail projections, schema 6 -> 7,
and the hosted "New world, keep progress" rebuild."""
import json
import unittest

from dimensional_sim.world import autopilot as ap
from dimensional_sim.world.autopilot import Expedition
from dimensional_sim.world.catalog import ACHIEVEMENTS, BY_ID
from dimensional_sim.world.details import detail
from dimensional_sim.world.journal import achievements, metric, new_journal, validate_journal
from dimensional_sim.world.runtime import Exploration
from dimensional_sim.world.seeds import canonical_json
from dimensional_sim.world.session import BrowserSession, validate_input
from dimensional_sim.world.web import WebGame, new_world


def fresh(seed=482910):
    return Expedition(Exploration(new_world(seed), "forest"))


def played(ms=120_000, seed=482910):
    e = fresh(seed)
    e.advance(ms)
    return e


class JournalTests(unittest.TestCase):
    def test_actions_and_items_are_counted_and_survive_save(self):
        e = played()
        self.assertTrue(e.journal["actions"], "two minutes of play should complete some action")
        for ident, n in e.journal["actions"].items():
            self.assertIn(ident, BY_ID)
            self.assertGreater(n, 0)
        again = Expedition.from_dict(json.loads(canonical_json(e.to_dict())))
        self.assertEqual(again.journal, e.journal)

    def test_death_is_recorded_with_cause_and_life_length(self):
        e = played(30_000)
        e.hunger = 0
        e.health = ap.POINT
        e.advance(60_000)
        self.assertGreaterEqual(sum(e.journal["deaths"].values()), 1)
        self.assertGreater(e.journal["best_life_ms"], 0)

    def test_validation_rejects_unknown_keys(self):
        for bad in ({}, {**new_journal(), "extra": 1}, {**new_journal(), "actions": {"nope": 1}},
                    {**new_journal(), "deaths": {"boar": -1}}, {**new_journal(), "items": []}):
            with self.assertRaises(ValueError):
                validate_journal(bad)

    def test_achievements_cover_catalog_and_metrics_resolve(self):
        e = played(60_000)
        rows = achievements(e)
        self.assertEqual([r["id"] for r in rows], [a.id for a in ACHIEVEMENTS])
        for a, r in zip(ACHIEVEMENTS, rows):
            self.assertGreaterEqual(metric(e, a.metric), 0)
            self.assertLessEqual(r["progress"], r["threshold"])
            self.assertEqual(r["done"], r["progress"] >= r["threshold"])
        self.assertTrue(next(r for r in rows if r["id"] == "first_steps")["done"])


class DetailTests(unittest.TestCase):
    def test_detail_has_every_page_and_is_json(self):
        e = played(60_000)
        d = detail(e)
        self.assertEqual(set(d), {"character", "stats", "multipliers", "rolls", "journal"})
        json.dumps(d)
        self.assertEqual(len(d["stats"]), 6)
        for w in d["rolls"]["windows"]:
            self.assertLessEqual(w["min"], w["max"])
            if w["rolled"] is not None:
                self.assertTrue(w["min"] <= w["rolled"] <= w["max"], w)
        for a in d["multipliers"]["actions"]:
            self.assertGreater(a["effective_ms"], 0)

    def test_detail_shape_matches_the_browser_page_fixture(self):
        # tests/browser_pages.test.mjs builds the same shape by hand; keep them in step.
        d = detail(played(30_000))
        self.assertEqual(set(d["character"]), {
            "life", "depth", "best_depth", "frontier", "health", "hunger", "punch_damage", "gear", "boon",
            "boon_next", "boar_hit_at_frontier", "fight_cost_at_frontier", "hunger_per_minute", "regen_per_minute",
            "rest_regen_per_minute", "inventory_slots", "currencies", "unlocked"})
        self.assertEqual(set(d["multipliers"]), {"actions", "hunger_drain", "boar_hit", "punch_damage", "punch_parts"})
        self.assertEqual(set(d["rolls"]), {"life", "windows", "spots_per_chunk", "pity", "stats", "loot"})
        self.assertEqual(set(d["journal"]), {"actions", "items", "deaths", "best_life_min", "lives", "best_depth",
                                             "achievements"})
        self.assertTrue({"name", "level", "into", "next", "dim_level", "dim_into", "dim_next", "speed",
                         "speed_regular_only", "speed_dimensional_only", "life_gain", "xp"} <= set(d["stats"][0]))

    def test_detail_is_read_only(self):
        e = played(30_000)
        before = canonical_json(e.to_dict())
        detail(e)
        self.assertEqual(canonical_json(e.to_dict()), before)

    def test_session_sends_detail_only_on_request(self):
        e = played(5_000)
        s = BrowserSession(e.game, e)
        base = {"move": None, "attack": False, "paused": False, "known": []}
        validate_input({**base, "detail": True})
        with self.assertRaises(ValueError):
            validate_input({**base, "detail": "yes"})
        self.assertIsNone(s.input(dict(base), 0.0)["expedition"]["detail"])
        self.assertIn("journal", s.input({**base, "detail": True}, 0.1)["expedition"]["detail"])


class UpgradeAndRebuildTests(unittest.TestCase):
    def test_v6_save_upgrades_with_empty_journal(self):
        e = played(30_000)
        old = e.to_dict()
        old.pop("journal")
        old["schema_version"] = 6
        migrated = Expedition.from_dict(old)
        self.assertEqual(migrated.journal, new_journal())
        self.assertEqual(migrated.dimensional, e.dimensional)

    def test_rebuilt_world_keeps_meta_and_changes_seed(self):
        e = played(60_000)
        e.dust, e.ash, e.blessing = 7, 3, 2
        e.unlocked.add("climbing")
        new = Expedition.rebuilt(e, Exploration(new_world(1234), "forest"))
        self.assertEqual(new.game.world.world_seed, 1234)
        self.assertEqual((new.dust, new.ash, new.blessing), (7, 3, 2))
        self.assertEqual(new.dimensional, e.dimensional)
        self.assertEqual(new.journal, e.journal)
        self.assertIn("climbing", new.unlocked)
        self.assertEqual(new.life, e.life + 1)
        self.assertFalse(new.in_prologue)
        again = Expedition.from_dict(json.loads(canonical_json(new.to_dict())))
        self.assertEqual(canonical_json(again.to_dict()), canonical_json(new.to_dict()))
        new.advance(20_000)

    def test_web_rebuild(self):
        game = WebGame(seed=482910)
        game.advance(20_000, 0.0)
        before = json.loads(game.summary())
        after = json.loads(game.rebuild(99))
        self.assertEqual(game.world_seed(), "99")
        self.assertEqual(after["life"], before["life"] + 1)
        WebGame(game.save())   # the rebuilt world saves and loads


if __name__ == "__main__":
    unittest.main()
