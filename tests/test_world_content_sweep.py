"""Phase 7 sweep: every piece of content can actually happen and has what it needs to show.

Catalog validation catches broken references; this checks reachability and presentation:
nothing is defined that no roll, outcome, craft or site can ever produce."""
import pathlib
import re
import unittest

from dimensional_sim.world.actions import Context, spot_shares
from dimensional_sim.world.catalog import (ACTIONS, BY_ID, DROP_TABLES, ENEMIES, ITEMS, REGIONS, SITE_CONDITIONS,
                                           SITES, UNLOCKS)

BROWSER = pathlib.Path(__file__).parents[1] / "src/dimensional_sim/world/browser"


def table_items(table_id):
    """Every item a drop table (and the tables nested in it) can give."""
    if not table_id:
        return set()
    found = set()
    for pool in DROP_TABLES[table_id].pools.values():
        for pick in pool:
            found |= table_items(pick.table) if pick.table else {pick.item}
    return found


class ReachabilityTests(unittest.TestCase):
    def test_every_wild_spot_can_roll_somewhere(self):
        everything = frozenset(UNLOCKS)
        possible = set()
        for region in REGIONS.values():
            for features in (frozenset(), frozenset({"water"})):
                ctx = Context(region=region.id, region_def=region, unlocked=everything, ring=4, features=features,
                              knowledge=frozenset(a.knowledge for a in ACTIONS if a.knowledge),
                              gear=frozenset(ITEMS))
                possible |= {k for k, v in spot_shares(ctx).items() if v > 0}
        spots = {a.id for a in ACTIONS if a.placement == "spot"}
        self.assertEqual(spots - possible, set(), "spots no region can ever roll")

    def test_every_lead_has_a_source_and_every_site_has_encounters(self):
        sources = {o.id for a in ACTIONS for o in a.outcomes if o.kind == "lead"}
        sources |= {added for c in SITE_CONDITIONS.values() for added in c.adds}
        sources |= {a.id for a in ACTIONS if "night" in a.tags}   # autopilot/night.py creates these
        leads = {a.id for a in ACTIONS if a.placement == "lead"}
        self.assertEqual(leads - sources, set(), "leads nothing creates")
        for site in SITES:
            self.assertTrue([a for a in ACTIONS if a.site == site], site)

    def test_every_item_can_be_obtained(self):
        got = set()
        for a in ACTIONS:
            got |= {loot.item for loot in a.loot} | table_items(a.drops)
            if a.effect in ITEMS:
                got.add(a.effect)
        for table in DROP_TABLES:
            got |= table_items(table)
        self.assertEqual(set(ITEMS) - got, set(), "items no action, craft or drop can give")

    def test_every_enemy_fights_somewhere(self):
        used = {a.enemy for a in ACTIONS if a.enemy}
        self.assertEqual(set(ENEMIES) - used, set())

    def test_every_recipe_gate_can_be_learned(self):
        recipes = {o.id for a in ACTIONS for o in a.outcomes if o.kind == "recipe"}
        for a in ACTIONS:
            if a.recipe:
                self.assertIn(a.recipe, recipes, a.id)


class PresentationTests(unittest.TestCase):
    def test_every_action_describes_what_the_avatar_is_doing(self):
        for action in ACTIONS:
            with self.subTest(action=action.id):
                self.assertTrue(action.interaction, "active actions need a progress label")
                self.assertTrue(action.interaction.split()[0].endswith("ing"), action.interaction)

    def test_item_glyphs_are_unique(self):
        glyphs = [i.glyph for i in ITEMS.values()]
        dupes = {g for g in glyphs if glyphs.count(g) > 1}
        self.assertEqual(dupes, set(), "two items share an inventory glyph")

    def test_every_enemy_sprite_and_role_letter_is_drawn(self):
        import json
        import subprocess
        script = ("import('./combat_art.js').then(async m => { const s = await import('./sprites.js');"
                  "console.log(JSON.stringify({sprites: Object.keys(m.ENEMY_SPRITES), roles: Object.keys(s.ROLE),"
                  "letters: Object.values(m.ENEMY_SPRITES).map(x => x.paint.join(''))}))})")
        out = json.loads(subprocess.check_output(["node", "--input-type=module", "-e", script], cwd=BROWSER, text=True))
        self.assertEqual({e.sprite for e in ENEMIES.values()} - set(out["sprites"]), set())
        for letters in out["letters"]:
            self.assertEqual(set(letters) - {" "} - set(out["roles"]), set())

    def test_every_generated_ground_glyph_has_tile_art(self):
        art = (BROWSER / "art.js").read_text(encoding="utf-8")
        handled = set(re.search(r"const terrain = '([^']+)'\.includes", art).group(1)) | {"."}
        for glyph in ".;o*=:xFHw%":
            self.assertIn(glyph, handled)

    def test_new_systems_have_sounds(self):
        sound = (BROWSER / "sound.js").read_text(encoding="utf-8")
        for name in ("step", "swing", "hit", "kill", "enemy_alert", "enemy_attack", "ambush", "loot", "rare", "level", "shimmer", "kindle",
                     "death", "chop", "rattle"):
            self.assertIn(name, sound)


if __name__ == "__main__":
    unittest.main()
