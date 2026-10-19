"""Actions open by dimensional level; ash keeps the recipes a life found."""
import json
import unittest

from dimensional_sim.world.autopilot import Expedition, saves
from dimensional_sim.world.catalog import ACTIONS, RECIPE_KEEP_COST, UNLOCKS, UnlockDef
from dimensional_sim.world.progression import CONFIG
from dimensional_sim.world.seeds import canonical_json
from tests.test_world_autopilot import expedition
from save_fixture import v17


def xp_for_level(level):
    """Dimensional XP that reaches `level` (from the progression curve)."""
    from dimensional_sim.world.progression import dimensional_level
    xp = 0
    while dimensional_level(xp) < level:
        xp += 10
    return xp


class LevelUnlockTests(unittest.TestCase):
    def test_actions_open_by_level_and_only_abilities_are_sold(self):
        priced = {u.id for u in UNLOCKS.values() if u.currency}
        self.assertEqual(priced, {"return_anchor", "campfire"})
        for u in UNLOCKS.values():
            if u.level is None:
                continue
            attribute, level = u.level
            gated = [a.id for a in ACTIONS if a.unlock == u.id]
            self.assertTrue(gated, f"{u.id} opens something")
            growable = [a.id for a in ACTIONS if a.attribute == attribute and a.unlock != u.id
                        and a.placement in ("spot", "self") and a.xp > 0]   # possibly opened by another gate
            self.assertTrue(growable, f"{u.id}: {attribute} can be grown before it opens")
        with self.assertRaises(ValueError):
            UnlockDef("x", "X", "x", "ash", 5, level=("strength", 2))
        with self.assertRaises(ValueError):
            UnlockDef("x", "X", "x", level=("luck", 2))

    def test_reaching_a_level_opens_the_unlock_for_good(self):
        e = expedition()
        while e.in_prologue:
            e.advance(500)
        self.assertNotIn("climbing", e.unlocked)
        attribute, level = UNLOCKS["climbing"].level
        e.dimensional[attribute] = xp_for_level(level) - 1
        e._gain_xp(attribute, 50)
        self.assertIn("climbing", e.unlocked)
        self.assertTrue(any("Climbing" in row["text"] for row in e.log))
        again = Expedition.from_dict(json.loads(canonical_json(e.to_dict())))
        self.assertIn("climbing", again.unlocked)

    def test_found_recipes_last_one_life_unless_kept(self):
        e = expedition()
        while e.in_prologue:
            e.advance(500)
        from dimensional_sim.world.catalog import BY_ID
        from dimensional_sim.world.journal import record_action
        record_action(e.journal, "lodge_snares")
        e._apply_outcomes(BY_ID["lodge_snares"], "self:test")
        self.assertEqual(e.life_recipes, {"snare"})
        self.assertIn("snare", e.spot_context(e.game.player.chunk).recipes)
        self.assertTrue(any("anchor" in row["text"] for row in e.log), "the log says how to keep it")
        e.health, e.cause = 0, "starvation"
        e.advance(0)
        rows = [r for r in e.anchor_offers() if r["kind"] == "keep"]
        self.assertEqual([(r["id"], r["cost"]) for r in rows], [("snare", RECIPE_KEEP_COST["snare"])])
        e.anchor_action({"type": "begin_life"})
        self.assertEqual((e.recipes, e.life_recipes), (set(), set()), "not kept: forgotten")

    def test_old_saves_keep_what_they_paid_for(self):
        e = expedition()
        while e.in_prologue:
            e.advance(500)
        old = {k: v for k, v in v17(e.to_dict()).items() if k not in saves.V17_FIELDS}
        old["schema_version"] = 16
        old["unlocked"] = ["hide_working", "snares", "climbing"]
        loaded = Expedition.from_dict(old)
        self.assertEqual(loaded.unlocked, {"snares", "climbing", "campfire"}, "the free campfire is kept")
        self.assertEqual(loaded.recipes, {"hide_wrap", "snare"})
        bad = e.to_dict()
        bad["life_recipes"] = ["moon_boots"]
        with self.assertRaises(ValueError):
            Expedition.from_dict(bad)
        self.assertGreater(CONFIG.dimensional_xp_base, 0)


if __name__ == "__main__":
    unittest.main()
