"""Forest chains: a find -> a clue that may lead on -> sometimes a payoff, danger or nothing."""
import json
import unittest

from dimensional_sim.world.autopilot import Expedition
from dimensional_sim.world.catalog import ACTIONS, BY_ID
from dimensional_sim.world.journal import record_action
from dimensional_sim.world.seeds import canonical_json
from tests.test_world_autopilot import expedition

CHAINS = {   # source -> its clue lead -> the payoffs that clue can lead to
    "fallen_branches": ("broken_branches", {"cut_wood"}),
    "bramble_berries": ("trampled_bushes", {"feeding_ground", "angry_boar"}),
    "mushroom_ring": ("mushroom_dust", {"rotten_log"}),
    "old_carvings": ("trail_marker", {"looping_path"}),
    "camp_packs": ("map_scrap", {"hidden_stash"}),
    "animal_tracks": ("follow_deer_tracks", {"hunt_deer"}),
}


def started(seed=482910):
    e = expedition(seed)
    while e.in_prologue:
        e.advance(500)
    return e


def lead_from(e, source, lead, tries=400):
    """Complete `source` with seeded ids until it creates `lead`; return that lead row."""
    record_action(e.journal, source)
    for n in range(tries):
        e._apply_outcomes(BY_ID[source], f"self:{source}:{n}")
        found = [row for row in e.leads if row["action"] == lead]
        if found:
            return found[-1]
    raise AssertionError(f"{source} never produced {lead}")


class ChainShapeTests(unittest.TestCase):
    def test_every_chain_is_wired_and_payoffs_are_never_certain(self):
        for source, (clue, payoffs) in CHAINS.items():
            to_clue = [o for o in BY_ID[source].outcomes if o.kind == "lead" and o.id == clue]
            self.assertEqual(len(to_clue), 1, source)
            self.assertLess(to_clue[0].chance, 50, f"{source}: a clue is a chance, not a given")
            onward = {o.id for o in BY_ID[clue].outcomes if o.kind == "lead"}
            self.assertEqual(onward, payoffs, clue)
            alternatives = [o for o in BY_ID[clue].outcomes if o.group is not None]
            self.assertTrue(any(o.kind == "note" for o in alternatives), f"{clue} can go nowhere")
            self.assertLess(sum(o.chance for o in alternatives if o.kind == "lead"), 100, clue)

    def test_every_lead_has_a_source_and_plain_names(self):
        sources = {o.id for a in ACTIONS for o in a.outcomes if o.kind == "lead"}
        for a in ACTIONS:
            if a.placement == "lead":
                self.assertIn(a.id, sources, f"{a.id} is never reached")
                self.assertTrue(a.interaction, a.id)


class ChainPlayTests(unittest.TestCase):
    def test_broken_branches_point_into_a_neighbouring_chunk_and_resolve_once(self):
        e = started()
        lead = lead_from(e, "fallen_branches", "broken_branches")
        here = e.game.player.chunk
        self.assertEqual(abs(lead["chunk_x"] - here.x) + abs(lead["chunk_y"] - here.y), 1, "the clue points away")
        chunk = e.game.world.get(type(here)(here.dimension, lead["chunk_x"], lead["chunk_y"]))
        self.assertFalse(chunk.asset.collision[lead["y"]][lead["x"]], "a lead stands on open ground")
        outcomes = {"cut_wood": 0, "nothing": 0}
        for seed in range(1, 40):
            e = started(seed)
            lead = lead_from(e, "fallen_branches", "broken_branches")
            before = len(e.leads)
            e._reward(lead["id"], BY_ID["broken_branches"])
            made = [row["action"] for row in e.leads[before - 1:] if row["action"] != "broken_branches"]
            outcomes["cut_wood" if "cut_wood" in made else "nothing"] += 1
        self.assertTrue(outcomes["cut_wood"] and outcomes["nothing"], outcomes)

    def test_trampled_bushes_can_hide_a_boar_that_fights_and_wanders_off(self):
        found = None
        for seed in range(1, 60):
            e = started(seed)
            clue = lead_from(e, "bramble_berries", "trampled_bushes")
            e._reward(clue["id"], BY_ID["trampled_bushes"])
            boar = [row for row in e.leads if row["action"] == "angry_boar"]
            if boar:
                found = (e, boar[0])
                break
        self.assertIsNotNone(found, "some trampled bushes hide a boar")
        e, boar = found
        self.assertEqual(e.admitted[boar["id"]], "angry_boar", "a danger lead is a live, admitted enemy")
        self.assertIn("Something grunts in the bushes.", [row["text"] for row in e.log])
        e._settle()
        self.assertIn(boar["id"], e.game.targets)
        self.assertEqual(e.enemy_of(e.game.targets[boar["id"]]).id, "bramble_boar")
        self.assertNotIn("angry_boar", [a.id for a in e.threats()], "chain danger adds no new threat type")
        again = Expedition.from_dict(json.loads(canonical_json(e.to_dict())))
        self.assertIn(boar["id"], [row["id"] for row in again.leads])
        e.total_ms = boar["expires_ms"]
        e._expire_leads()
        self.assertNotIn(boar["id"], e.game.targets, "an unfought danger lead wanders off")

    def test_the_looping_path_reveals_the_land_around_it(self):
        e = started()
        seen = lambda: sum(bin(v).count("1") for rows in e.game.seen.values() for v in rows)
        before = seen()
        record_action(e.journal, "looping_path")
        e._apply_outcomes(BY_ID["looping_path"], "lead:test:loop")
        self.assertGreater(seen(), before + 500)
        self.assertIn("You can see the paths around you now.", [row["text"] for row in e.log])

    def test_chain_payoffs_give_little_fixed_loot(self):
        for payoff in ("cut_wood", "feeding_ground", "rotten_log", "hidden_stash"):
            fixed = sum(entry.high for entry in BY_ID[payoff].loot)
            self.assertLessEqual(fixed, 5, f"{payoff}: payoffs are a find, not a flood")


if __name__ == "__main__":
    unittest.main()
