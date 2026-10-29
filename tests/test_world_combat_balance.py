"""Controlled, seeded boar fights: only equipped gear changes between cohorts."""

import unittest

from dimensional_sim.world import autopilot as ap
from dimensional_sim.world.autopilot import Expedition
from dimensional_sim.world.catalog import BY_ID, FIGHT_TIERS
from dimensional_sim.world.equipment import equip_item
from gear_fixture import test_weapon
from dimensional_sim.world.models import ChunkKey, DimensionSpec
from dimensional_sim.world.open_terrain import open_assets
from dimensional_sim.world.repository import WorldRepository
from dimensional_sim.world.runtime import Exploration, Target


def fight(seed, tier="common", *, staff=False, ring=2):
    """One adjacent boar ambush of a given FightTier (a +1 test staff stands in for any weapon)."""
    with test_weapon():
        return _fight(seed, tier, ring, staff=staff)


def _fight(seed, tier, ring, *, staff=False):
    """One adjacent boar ambush at full health, with no unrelated rolled spots."""
    spec = DimensionSpec("forest", ("dark_forest",), 32, 16, 25)
    world = WorldRepository(seed, (spec,), open_assets(32, 16), 9)
    e = Expedition(Exploration(world), fresh=False)
    key = ChunkKey("forest", ring, 0)
    chunk = world.get(key)
    e.game._enter(key)
    e.game.player.chunk = key
    spawn = next(s for s in chunk.asset.spawns if s.kind == "player")
    e.game.player.x, e.game.player.y = spawn.x, spawn.y
    px, py = e._player()
    e.anchor = (px + 40, py)  # keep the encounter beyond the camp's safe radius
    if staff:
        e.inventory["test_staff"] = 1
        e.equipped = equip_item(e.equipped, e.inventory, "test_staff")
    e.game.targets.clear()
    e.admitted.clear()
    e._screen = lambda: None  # hold all other seeded opportunities out of this duel
    e._reward = lambda ident, entry: e.completed.add(ident)  # exclude post-kill loot/progression
    candidates = ((spawn.x + dx, spawn.y + dy) for dx, dy in ((0, -1), (1, 0), (0, 1), (-1, 0)))
    tx, ty = next((x, y) for x, y in candidates if 0 <= x < chunk.asset.width and 0 <= y < chunk.asset.height
                  and not chunk.asset.collision[y][x])
    ident = "enc:forest:0:0:999"
    e.tier_of = lambda _: FIGHT_TIERS[tier]   # this duel's boar is of the tier under test
    hp = e.enemy_hp(BY_ID["bramble_boar"], key, FIGHT_TIERS[tier])
    e.game.targets[ident] = Target(ident, key, tx, ty, hp)
    e.admitted[ident] = "bramble_boar"
    e.task = {"type": "think", "spot": None, "elapsed_ms": 0, "duration_ms": 60_000}
    e.monster_ms = ap.MONSTER_STEP_MS
    e.advance(0)  # the boar attacks first and interrupts the thought
    engaged = (e.goal or {}).get("kind") == "target"
    killed = False
    for _ in range(1000):
        target = e.game.targets.get(ident)
        if target is None or e.anchor_ms is not None:
            break
        if target.hp == 0:
            killed = True
            break
        e.advance(20)
    return {"seed": seed, "tier": tier, "staff": staff, "engaged": engaged,
            "killed": killed, "boar_death": e.anchor_ms is not None and e.cause == "boar",
            "remaining_health": e.health // ap.POINT,
            "boar_bites": e.strikes.get(ident, 0), "duration_ms": e.total_ms}


class BoarBalanceTests(unittest.TestCase):
    def test_same_seed_repeats_the_same_duel(self):
        self.assertEqual(fight(482910, staff=True), fight(482910, staff=True))

    def test_staff_improves_but_does_not_erase_boar_risk(self):
        bitten, unhurt = 0, 0
        for seed in range(1, 9):
            with self.subTest(seed=seed):
                unarmed = fight(seed)
                staff = fight(seed, staff=True)
                self.assertTrue(unarmed["killed"] and staff["killed"])
                self.assertGreaterEqual(staff["remaining_health"], unarmed["remaining_health"])
                unhurt += unarmed["remaining_health"] == 100   # a sidestep, or a charge into a tree
                bitten += staff["boar_bites"]
        self.assertLessEqual(unhurt, 2, "a fresh avatar rarely beats a boar for free")
        self.assertGreater(bitten, 0, "even with a staff the charges land now and then")

    def test_an_elder_boar_remains_dangerous_with_a_staff(self):
        for seed in range(1, 9):
            with self.subTest(seed=seed):
                unarmed = fight(seed, "elder")
                staff = fight(seed, "elder", staff=True)
                self.assertFalse(unarmed["engaged"], "a fresh avatar runs from an elder")
                self.assertFalse(staff["engaged"], "a staff is not enough for an elder either")
                self.assertFalse(staff["killed"])

if __name__ == "__main__":
    unittest.main()
