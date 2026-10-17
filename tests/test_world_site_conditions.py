"""Site conditions: each landmark has one condition per life (quiet, already searched,
untouched, an animal den, overgrown) that shapes its encounters, loot and work."""
import unittest
from collections import Counter

from dimensional_sim.world.actions import Context
from dimensional_sim.world.autopilot import Expedition
from dimensional_sim.world.catalog import BY_ID, SITE_CONDITIONS, SITES, UNLOCKS, SiteConditionDef
from dimensional_sim.world.encounters import chunk_spots
from dimensional_sim.world.runtime import Exploration
from dimensional_sim.world.sites import condition_for
from dimensional_sim.world.web import new_world
from tests.test_world_sites import SEED, first, sites


def site_rows(chunk, ctx, p, condition):
    spots = chunk_spots(chunk, context=ctx, site=p, condition=condition)
    return [s for s in spots if p.contains(s.x, s.y) and (BY_ID[s.encounter].site == p.id
                                                          or s.encounter in condition.adds)]


class ConditionPickTests(unittest.TestCase):
    def test_one_condition_per_site_per_life_fitting_its_structure(self):
        w = new_world(SEED)
        found = sites(w)
        seen = Counter()
        for life in range(1, 41):
            for p in found.values():
                c = condition_for(SEED, p, life)
                self.assertIs(c, condition_for(SEED, p, life), "pure")
                self.assertTrue(c.structures is None or p.site.structure in c.structures)
                seen[c.id] += 1
        self.assertEqual(set(seen), set(SITE_CONDITIONS), "every condition shows up")
        self.assertEqual(seen.most_common(1)[0][0], "quiet", "most visits find a site as it was")
        any_site = next(iter(found.values()))
        self.assertGreater(len({condition_for(SEED, any_site, life).id for life in range(1, 30)}), 1,
                           "a site changes from life to life")

    def test_shrines_never_hold_a_den(self):
        self.assertNotIn("shrine", SITE_CONDITIONS["den"].structures)

    def test_bad_conditions_are_rejected(self):
        for bad in (dict(weight=0), dict(spots_delta=3), dict(structures=("castle",)), dict(duration_percent=20)):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                SiteConditionDef(**{"id": "x", "name": "X", "text": "x", "weight": 5, **bad})


class ConditionEffectTests(unittest.TestCase):
    def test_conditions_shape_the_site_encounters(self):
        w = new_world(SEED)
        key, p = first(w, "abandoned_camp")
        chunk, region = w.get(key), w.region_for(key)
        unlocks = frozenset(a.unlock for a in BY_ID.values() if a.site == p.id)
        ctx = Context(region=region.id, unlocked=unlocks)
        base = [s for s in site_rows(chunk, ctx, p, SITE_CONDITIONS["quiet"]) if BY_ID[s.encounter].site == p.id]
        fewer = site_rows(chunk, ctx, p, SITE_CONDITIONS["picked_over"])
        more = site_rows(chunk, ctx, p, SITE_CONDITIONS["untouched"])
        self.assertEqual(len(fewer), max(1, len(base) - 1))
        self.assertGreaterEqual(len(more), len(base))
        den = site_rows(chunk, ctx, p, SITE_CONDITIONS["den"])
        boars = [s for s in den if s.encounter == "bramble_boar"]
        self.assertEqual(len(boars), 1, "a den adds its animal inside the clearing")
        self.assertTrue(p.contains(boars[0].x, boars[0].y))

    def expedition_at(self, site_id, condition):
        e = Expedition(Exploration(new_world(SEED), "forest"))
        while e.in_prologue:
            e.advance(500)
        e.unlocked.update(UNLOCKS)
        key, p = first(e.game.world, site_id)
        e.site_condition = lambda k, c=SITE_CONDITIONS[condition]: c if k == key else None
        chunk = e.game.world.get(key)
        e.game._enter(key)
        e.game.player.chunk = key
        spawn = next(s for s in chunk.asset.spawns if s.kind == "player")
        e.game.player.x, e.game.player.y = spawn.x, spawn.y
        e.game._reveal()
        e._screen()
        return e, key

    def test_overgrown_sites_are_slow_and_searched_sites_give_no_bonus_drops(self):
        e, key = self.expedition_at("abandoned_camp", "overgrown")
        spot = next(s for s in e._spots(e.game.world.get(key)) if BY_ID[s.encounter].placement == "site")
        action = BY_ID[spot.encounter]
        e._start_perform(spot.id, action)
        slow = e.task["duration_ms"]
        e.site_condition = lambda k: SITE_CONDITIONS["quiet"]
        e._start_perform(spot.id, action)
        self.assertEqual(slow, e.task["duration_ms"] * 140 // 100)
        drops = next(a for a in BY_ID.values() if a.site == "abandoned_camp" and a.drops)
        from unittest.mock import patch
        from dimensional_sim.world.autopilot import outcomes
        seen = []
        real = outcomes.roll_loot
        with patch.object(outcomes, "roll_loot", lambda entry, seed: seen.append(entry.drops) or real(entry, seed)):
            for condition in ("picked_over", "quiet"):
                e.site_condition = lambda k, c=SITE_CONDITIONS[condition]: c
                e._reward(spot.id, drops)
        self.assertEqual(seen, [None, drops.drops], "an already-searched site skips the bonus drop roll")

    def test_the_hud_names_the_condition(self):
        from dimensional_sim.world.session import snapshot
        e, key = self.expedition_at("abandoned_camp", "den")
        region = snapshot(e.game, expedition=e)["expedition"]["region"]
        self.assertEqual(region["condition"], {"name": "Animal den", "text": "Something has made its den here."})
        e.site_condition = lambda k: SITE_CONDITIONS["quiet"]
        self.assertIsNone(snapshot(e.game, expedition=e)["expedition"]["region"]["condition"])

    def test_every_site_can_be_quiet_searched_and_untouched(self):
        for site in SITES.values():
            fits = {c.id for c in SITE_CONDITIONS.values() if c.structures is None or site.structure in c.structures}
            self.assertTrue({"quiet", "picked_over", "untouched"} <= fits)


if __name__ == "__main__":
    unittest.main()
