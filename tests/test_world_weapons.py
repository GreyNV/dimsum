"""Weapons: an attack profile per weapon (reach and shape), blows that stop at walls,
the staff -> spear / axe crafting line, and the axe that also chops."""
import unittest

from dimensional_sim.world.actions import reasons_against
from dimensional_sim.world.catalog import ATTACKS, BY_ID, DEFAULT_ATTACK, ITEMS, AttackDef
from dimensional_sim.world.runtime import InputCommand, Target
from tests.camp_fixture import to_camp
from tests.test_world_autopilot import expedition
from tests.test_world_runtime import exploration


def started():
    e = expedition()
    while e.in_prologue:
        e.advance(500)
    return e


def swing(game, ms=1000):
    game.advance(ms, InputCommand(attack=True))


class AttackProfileTests(unittest.TestCase):
    def test_every_weapon_has_a_profile_and_only_weapons_do(self):
        self.assertEqual(ATTACKS[DEFAULT_ATTACK].reach, 1)
        self.assertEqual({w: ATTACKS[ITEMS[w].attack].reach for w in ("walking_staff", "spear", "axe")},
                         {"walking_staff": 2, "spear": 3, "axe": 1})
        for item in ITEMS.values():
            self.assertEqual(item.attack is not None, item.slot == "weapon", item.id)
        self.assertEqual(ATTACKS["axe"].shape, "swing")
        punch = {w: sum(f.amount for f in ITEMS[w].effects if f.stat == "punch_damage") for w in ("spear", "axe")}
        self.assertGreater(punch["axe"], punch["spear"], "the axe trades reach for weight")

    def test_ranged_fields_are_reserved_not_live(self):
        for bad in (dict(projectile=True), dict(ammo="arrow"), dict(reach=0), dict(shape="arc")):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                AttackDef(**{"id": "x", "name": "X", "reach": 2, "shape": "thrust", **bad})


class RuntimeReachTests(unittest.TestCase):
    """The fixture player stands at (4, 3) facing north."""

    def test_fists_reach_one_cell(self):
        game = exploration()
        game.targets["far"] = Target("far", game.player.chunk, 4, 1)
        swing(game)
        self.assertEqual(game.targets["far"].hp, 3)

    def test_reach_two_hits_two_cells_away(self):
        game = exploration()
        game.attack_reach = 2
        game.targets["far"] = Target("far", game.player.chunk, 4, 1)
        swing(game)
        self.assertEqual(game.targets["far"].hp, 2)

    def test_the_first_enemy_shields_the_one_behind(self):
        game = exploration()
        game.attack_reach = 3
        game.targets["near"] = Target("near", game.player.chunk, 4, 2)
        game.targets["far"] = Target("far", game.player.chunk, 4, 1)
        swing(game)
        self.assertEqual((game.targets["near"].hp, game.targets["far"].hp), (2, 3))

    def test_a_wall_stops_the_blow(self):
        game = exploration()
        game.attack_reach = 3
        game.targets["far"] = Target("far", game.player.chunk, 4, 1)
        walls = {(4, 2)}
        game.wall_at = lambda gx, gy: (gx % 8, gy % 6) in walls
        swing(game)
        self.assertEqual(game.targets["far"].hp, 3, "weapons never hit through walls")


class AutopilotWeaponTests(unittest.TestCase):
    def armed(self, weapon):
        e = started()
        e.inventory[weapon] = 1
        e.equipped = {"weapon": weapon}
        e._arm()
        return e

    def test_arming_hands_the_runtime_reach_and_damage(self):
        e = self.armed("spear")
        self.assertEqual(e.game.attack_reach, 3)
        self.assertEqual(e.game.attack_damage, e.punch_damage())
        e.equipped = {}
        e._arm()
        self.assertEqual(e.game.attack_reach, 1)

    def test_strike_target_follows_reach_and_line_of_sight(self):
        e = self.armed("spear")
        here = e.game.player.chunk
        px, py = e.game.player.x, e.game.player.y
        e.game.wall_at = lambda gx, gy: False
        target = Target("boar", here, px, py - 3 if py >= 3 else py + 3, 3)
        e.game.targets = {"boar": target}
        e.admitted = {"boar": "bramble_boar"}
        self.assertEqual(e.strike_target()[1], "boar")
        e.equipped = {}
        self.assertIsNone(e.strike_target(), "fists reach one cell")
        e.equipped = {"weapon": "spear"}
        e.game.wall_at = lambda gx, gy: True
        self.assertIsNone(e.strike_target(), "no strike through a wall")

    def test_the_frontier_does_not_plan_on_reach(self):
        fists = started()
        spear = self.armed("spear")
        boar = BY_ID["bramble_boar"]
        spear.punch_damage = fists.punch_damage   # same blow: reach alone changes nothing
        self.assertEqual(spear.fight_damage(3, boar), fists.fight_damage(3, boar))

    def test_a_craft_keeps_the_sticks_for_an_emergency_fire(self):
        e = to_camp(started())
        e.knowledge.add("primitive_crafting")
        e.inventory = {"stick": 7}
        self.assertNotEqual(getattr(e._need_action(), "id", None), "craft_staff", "5 + 3 for a fire")
        e.inventory = {"stick": 8}
        self.assertEqual(e._need_action().id, "craft_staff")

    def test_snapshot_reports_the_weapon(self):
        from dimensional_sim.world.session import snapshot
        e = self.armed("axe")
        view = snapshot(e.game, expedition=e)["expedition"]
        self.assertEqual(view["weapon"], {"item": "axe", "attack": "axe", "reach": 1, "shape": "swing"})
        self.assertEqual(view["attack_radius"], 1)
        e.equipped = {}
        self.assertEqual(snapshot(e.game, expedition=e)["expedition"]["weapon"]["attack"], "fists")


class CraftingLineTests(unittest.TestCase):
    def at_station(self):
        e = to_camp(started())
        e.knowledge.add("primitive_crafting")
        return e

    def test_the_staff_needs_the_station_and_five_sticks(self):
        e = self.at_station()
        e.inventory = {"stick": 5}
        self.assertEqual(reasons_against(BY_ID["craft_staff"], e.self_context("need", True)), [])
        e.inventory = {"stick": 4}
        self.assertTrue(reasons_against(BY_ID["craft_staff"], e.self_context("need", True)))

    def test_spear_and_axe_need_their_recipe_and_use_up_the_staff(self):
        for craft, weapon, recipe in (("craft_spear", "spear", "spear"), ("craft_axe", "axe", "axe")):
            with self.subTest(craft=craft):
                e = self.at_station()
                e.inventory = {"walking_staff": 1, "iron_nails": 3, "rope": 1}
                e.equipped = {"weapon": "walking_staff"}
                self.assertTrue(reasons_against(BY_ID[craft], e.self_context("need", True)), "recipe first")
                e.recipes.add(recipe)
                self.assertEqual(reasons_against(BY_ID[craft], e.self_context("need", True)), [])
                e._complete_self(BY_ID[craft])
                self.assertNotIn("walking_staff", e.inventory)
                self.assertEqual(e.equipped, {"weapon": weapon})

    def test_recipes_come_from_sites(self):
        self.assertIn("spear", {o.id for o in BY_ID["lodge_trophies"].outcomes if o.kind == "recipe"})
        self.assertIn("axe", {o.id for o in BY_ID["lumber_shed"].outcomes if o.kind == "recipe"})


class AxeChopsTests(unittest.TestCase):
    def test_the_axe_adds_a_stick_to_wood_harvests_only(self):
        bare, axe = started(), started()
        axe.inventory["axe"] = 1
        axe.equipped = {"weapon": "axe"}
        for e in (bare, axe):
            e.inventory["stick"] = 0
            e._reward("lead:a", BY_ID["cut_wood"])
        self.assertEqual(axe.inventory["stick"] - bare.inventory["stick"], 1)
        bare.inventory["wild_berries"] = axe.inventory["wild_berries"] = 0
        for e in (bare, axe):
            e._reward("lead:b", BY_ID["bramble_berries"])
        self.assertEqual(axe.inventory["wild_berries"], bare.inventory["wild_berries"])

    def test_dead_trees_appear_only_for_an_axe_carrier(self):
        e = started()
        here = e.game.player.chunk
        self.assertIn("needs a axe carried", reasons_against(BY_ID["dead_tree"], e.spot_context(here)))
        e.inventory["axe"] = 1
        self.assertNotIn("needs a axe carried", reasons_against(BY_ID["dead_tree"], e.spot_context(here)))
        self.assertEqual(BY_ID["dead_tree"].ecology, "wood")


if __name__ == "__main__":
    unittest.main()
