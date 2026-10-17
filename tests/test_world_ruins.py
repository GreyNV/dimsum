"""Ruins are guarded: restless bones (a slow, stubborn, leashed skeleton) rise at burial
mounds and fallen watchtowers, known from the first life."""
import unittest

from dimensional_sim.world.autopilot import Expedition
from dimensional_sim.world.catalog import BY_ID, DEATH_CAUSES, ENEMIES, SITES
from dimensional_sim.world.runtime import Exploration
from dimensional_sim.world.web import new_world
from tests.test_world_sites import SEED, first


def at_site(site_id, life_tries=12):
    """An expedition standing in the first `site_id`, in a life whose roll placed a guard there."""
    e = Expedition(Exploration(new_world(SEED), "forest"))
    while e.in_prologue:
        e.advance(500)
    key, p = first(e.game.world, site_id)
    for _ in range(life_tries):
        e.site_condition = lambda k: None
        e.spot_plans.clear(); e.screened_chunks.clear()
        chunk = e.game.world.get(key)
        e.game._enter(key)
        e.game.player.chunk = key
        spawn = next(s for s in chunk.asset.spawns if s.kind == "player")
        e.game.player.x, e.game.player.y = spawn.x, spawn.y
        e.game._reveal()
        e._screen()
        guards = [s for s in e._spots(chunk) if BY_ID[s.encounter].enemy == "restless_bones"]
        if guards:
            return e, key, p, guards
        e.life += 1
    raise AssertionError("no guard rolled")


class RuinGuardTests(unittest.TestCase):
    def test_restless_bones_are_slow_tough_and_stay_home(self):
        bones, boar = ENEMIES["restless_bones"], ENEMIES["bramble_boar"]
        self.assertGreater(bones.step_ms, boar.step_ms, "slower than a boar: you can walk away")
        self.assertLess(bones.hit, boar.hit)
        self.assertIsNotNone(bones.leash, "it guards the ruin")
        self.assertGreater(BY_ID["barrow_dead"].hp, BY_ID["bramble_boar"].hp)
        self.assertIn("bones", DEATH_CAUSES)
        self.assertEqual(ENEMIES["restless_bones"].sprite, "skeleton")

    def test_only_the_ruins_have_guards(self):
        guarded = {a.site for a in BY_ID.values() if a.placement == "site" and a.category == "fight"}
        self.assertEqual(guarded, {"old_barrow", "fallen_watchtower", "ruined_shrine"})
        for a in BY_ID.values():
            if a.enemy == "restless_bones":
                self.assertEqual(a.placement, "site", "bones never roam the wild forest")
                self.assertIsNone(a.unlock, "a ruin is dangerous before it is worth searching")
        self.assertIn("old_barrow", SITES)

    def test_a_guard_rises_inside_the_clearing_and_fights(self):
        e, key, p, guards = at_site("old_barrow")
        guard = guards[0]
        self.assertTrue(p.contains(guard.x, guard.y))
        self.assertIn(guard.id, e.admitted)
        e.advance(1)
        target = e.game.targets.get(guard.id)
        self.assertIsNotNone(target, "an admitted guard becomes a live enemy")
        self.assertEqual(target.hp, e.enemy_hp(BY_ID[guard.encounter], key))
        self.assertGreater(target.hp, 5, "deep ruins make tough bones")

    def test_killing_a_guard_gives_bones(self):
        e, key, p, guards = at_site("fallen_watchtower")
        e.inventory = {}
        e._reward(guards[0].id, BY_ID[guards[0].encounter])
        self.assertIn("old_bone", e.inventory)


class WispTests(unittest.TestCase):
    def test_a_wisp_feeds_on_hunger_not_health(self):
        from dimensional_sim.world.runtime import Target
        from tests.test_world_autopilot import expedition
        e = expedition()
        while e.in_prologue:
            e.advance(500)
        here = e.game.player.chunk
        target = Target("enc:wisp", here, e.game.player.x + 1, e.game.player.y, 3)
        e.game.targets[target.id] = target
        e.admitted[target.id] = "shrine_wisp"
        health, hunger = e.health, e.hunger
        e._enemy_bites(target)
        self.assertEqual(e.health, health)
        self.assertLess(e.hunger, hunger)
        self.assertEqual(e.strikes[target.id], 1, "the client still sees the touch")
        self.assertEqual(e.fight_damage(5, BY_ID["shrine_wisp"]), 0, "it costs no health to fight")
        self.assertEqual(ENEMIES["pale_wisp"].drains, "hunger")
        self.assertIsNone(BY_ID["shrine_wisp"].unlock)

    def test_bad_drain_is_rejected(self):
        from dimensional_sim.world.catalog import EnemyDef
        with self.assertRaises(ValueError):
            EnemyDef("x", "X", 1, 1, "x", "x", "x", drains="mana")


if __name__ == "__main__":
    unittest.main()
