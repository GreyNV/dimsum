"""Manual play: stepping onto a spot starts it, moving again leaves it; skill buttons say
what they do and why they can't be used."""
import unittest

from dimensional_sim.world.catalog import BY_ID
from dimensional_sim.world.models import chunk_ident
from dimensional_sim.world.runtime import InputCommand
from dimensional_sim.world.session import snapshot
from tests.test_world_autopilot import expedition


def manual_beside_spot():
    """A started expedition with a berry bush admitted one step east of the player (open ground)."""
    e = expedition()
    while e.in_prologue:
        e.advance(500)
    e.goal = e.task = None
    here = e.game.player.chunk
    asset = e.game.current_chunk().asset
    for _ in range(40):   # walk until the cell east is open ground
        px, py = e.game.player.x, e.game.player.y
        if px + 2 < asset.width and not asset.collision[py][px + 1]:
            break
        e.game.player.x = (px + 3) % (asset.width - 4) + 1
    px, py = e.game.player.x, e.game.player.y
    ident = chunk_ident(here)
    e.spot_plans[ident] = [("bramble_berries", px + 1, py)]
    spot = next(s for s in e._spots(e.game.world.get(here)) if s.encounter == "bramble_berries")
    e.admitted[spot.id] = "bramble_berries"
    e.possess()   # manual play is possession
    e.step_cell = e._player()
    return e, spot


class StepOntoTests(unittest.TestCase):
    def test_walking_onto_a_spot_starts_it_and_holding_the_key_keeps_it(self):
        e, spot = manual_beside_spot()
        for _ in range(10):
            e.advance_manual(100, InputCommand("east"))
            if e.task:
                break
        self.assertEqual(e._player(), (e._global(spot.chunk, spot.x, spot.y)))
        self.assertEqual((e.task["type"], e.task["spot"]), ("perform", spot.id))
        e.advance_manual(200, InputCommand("east"))
        self.assertIsNotNone(e.task, "the key that carried you there does not cancel it")
        e.advance_manual(100, InputCommand())
        self.assertIsNotNone(e.task, "letting go keeps working")

    def test_moving_again_leaves_and_finishing_rewards(self):
        e, spot = manual_beside_spot()
        while not e.task:
            e.advance_manual(100, InputCommand("east"))
        e.advance_manual(100, InputCommand())
        e.advance_manual(100, InputCommand("east"))
        self.assertIsNone(e.task, "a new press walks on")
        self.assertNotIn(spot.id, e.completed)
        e2, spot2 = manual_beside_spot()
        while not e2.task:
            e2.advance_manual(100, InputCommand("east"))
        e2.advance_manual(e2.task["duration_ms"], InputCommand())
        self.assertIn(spot2.id, e2.completed)

    def test_fights_are_never_started_by_stepping(self):
        e, spot = manual_beside_spot()
        ident = chunk_ident(e.game.player.chunk)
        e.spot_plans[ident] = [("bramble_boar", spot.x, spot.y)]
        boar = next(s for s in e._spots(e.game.world.get(spot.chunk)) if s.encounter == "bramble_boar")
        e.admitted = {boar.id: "bramble_boar"}
        for _ in range(4):
            e.advance_manual(100, InputCommand("east"))
        self.assertFalse(e.task and e.task["type"] == "perform")


class SkillSlotTests(unittest.TestCase):
    def test_slots_explain_themselves(self):
        e, _ = manual_beside_spot()
        e.inventory = {"stick": 1}
        slots = snapshot(e.game, expedition=e)["expedition"]["skill_slots"]
        contact, fire, possess = slots
        self.assertEqual(contact["state"], "ready")
        self.assertIn("without dying", contact["hint"])
        self.assertEqual(fire["state"], "locked")
        self.assertIn("25 ash", fire["note"])
        self.assertIn("heal", fire["hint"])
        self.assertEqual((possess["state"], possess["note"]), ("active", "Possessing"))
        e.unlocked.add("campfire")
        fire = snapshot(e.game, expedition=e)["expedition"]["skill_slots"][1]
        self.assertEqual((fire["state"], fire["note"]), ("disabled", "Needs 3 sticks (have 1)"))
        e.inventory = {"stick": 3}
        self.assertEqual(snapshot(e.game, expedition=e)["expedition"]["skill_slots"][1]["state"], "ready")
        e.contact_ready_ms = e.total_ms + 60_000
        e.release()
        contact, _, possess = snapshot(e.game, expedition=e)["expedition"]["skill_slots"]
        self.assertEqual((contact["state"], contact["remaining_ms"], contact["cooldown_ms"]), ("cooldown", 60_000, 120_000))
        self.assertEqual((possess["state"], possess["remaining_ms"]), ("cooldown", 60_000))
        self.assertTrue(BY_ID["make_campfire"].cost)


if __name__ == "__main__":
    unittest.main()
