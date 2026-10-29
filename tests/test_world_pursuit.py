"""Pursuit (schema 20): an enemy that notices the avatar hunts it and cannot be outrun -
only left behind beyond the loaded area, where it is unloaded. Reaching the anchor camp or
a campfire frightens every hunter: it flees until it is out of range (or soon gone anyway)."""
import json
import unittest

from tests.save_fixture import v21

from dimensional_sim.world.autopilot import Expedition
from dimensional_sim.world.autopilot.combat import FLEE_UNLOAD_MS
from dimensional_sim.world.encounters import spot_id
from dimensional_sim.world.models import ChunkKey, chunk_ident
from dimensional_sim.world.runtime import Exploration, Target
from dimensional_sim.world.seeds import canonical_json
from dimensional_sim.world.web import new_world

HUNTING = ("hunt", "windup", "charge", "recover", "retreat")   # every mode of a fight pattern but flight


def boar_beside(seed=482910, gap=4, camp_far=True):
    """A started avatar on an open row with a boar `gap` steps east, the camp far away."""
    e = Expedition(Exploration(new_world(seed), "forest"))
    while e.in_prologue:
        e.advance(500)
    e.goal = e.task = None
    if camp_far:
        e.anchor = (10 ** 6, 10 ** 6)
    here = e.game.player.chunk
    asset = e.game.current_chunk().asset
    py = e.game.player.y
    row = [x for x in range(2, asset.width - gap - 2) if all(not asset.collision[py][x + d] for d in range(gap + 1))]
    if not row:
        raise unittest.SkipTest("no open row")
    e.game.player.x = row[-1]
    e.game._reveal()
    e.spot_plans[chunk_ident(here)] = [("bramble_boar", row[-1] + gap, py)]
    target = Target(spot_id(here, 0), here, row[-1] + gap, py, 9)
    for other in e.game.targets.values():   # map-placed enemies stay (saves need them) but sit this out
        e.admitted.pop(other.id, None)
    e.game.targets[target.id] = target
    e.admitted[target.id] = "bramble_boar"
    return e, target


def tick(e, n=1):
    for _ in range(n):
        e.monster_ms, e.total_ms = 300, e.total_ms + 300
        e._pursue()


class HuntTests(unittest.TestCase):
    def test_a_noticed_enemy_hunts_far_past_its_aggro_radius(self):
        e, boar = boar_beside()
        tick(e)
        self.assertIn(e.hunting[boar.id]["mode"], HUNTING)
        # the avatar is carried far off (beyond aggro) but stays in the loaded area: still hunted
        e.game.player.x = max(1, e.game.player.x - 9)
        start = e._steps_to(boar, *e._player())
        self.assertGreater(start, 11)
        tick(e, 3)
        self.assertIn(boar.id, e.hunting)
        self.assertLess(e._steps_to(boar, *e._player()), start, "it closes in")

    def test_out_of_the_loaded_area_it_is_unloaded_and_comes_back_home_later(self):
        e, boar = boar_beside()
        tick(e)
        home = boar.chunk
        boar.chunk = ChunkKey(home.dimension, home.x + 5, home.y)   # it fell far behind
        tick(e)
        self.assertNotIn(boar.id, e.game.targets)
        self.assertNotIn(boar.id, e.hunting)
        e._settle()   # its home chunk is still loaded: the boar is back at its spot, calm
        self.assertIn(boar.id, e.game.targets)
        self.assertNotIn(boar.id, e.hunting)

    def test_reaching_the_camp_frightens_hunters_away(self):
        e, boar = boar_beside()
        tick(e)
        e.anchor = e._player()   # the avatar made it to the camp
        tick(e)
        self.assertEqual(e.hunting[boar.id]["mode"], "flee")
        self.assertIn("slinks away", e.log[-1]["text"])
        before = e._steps_to(boar, *e._player())
        tick(e, 3)
        self.assertGreaterEqual(e._steps_to(boar, *e._player()), before, "it backs off")
        tick(e, FLEE_UNLOAD_MS // 300 + 1)
        self.assertNotIn(boar.id, e.game.targets, "a frightened enemy is soon gone")

    def test_a_campfire_frightens_hunters_too_and_nobody_notices_you_by_the_fire(self):
        e, boar = boar_beside()
        px, py = e._player()
        e.campfire = {"dimension": e.dimension, "x": px, "y": py, "fire_x": px - 1, "fire_y": py}
        tick(e)
        self.assertNotIn(boar.id, e.hunting, "nothing notices you in the firelight")
        e.campfire = None
        tick(e)
        e.campfire = {"dimension": e.dimension, "x": px, "y": py, "fire_x": px - 1, "fire_y": py}
        tick(e)
        self.assertEqual(e.hunting[boar.id]["mode"], "flee")

    def test_an_unloaded_wolf_is_gone_for_good(self):
        e, boar = boar_beside()
        here = boar.chunk
        lead = {"id": "lead:forest:0:0:night_wolf:night9:1", "action": "night_wolf", "source": "night",
                "dimension": here.dimension, "chunk_x": here.x, "chunk_y": here.y, "chunk": chunk_ident(here),
                "x": boar.x, "y": boar.y, "expires_ms": e.total_ms + 60_000}
        e.leads = [lead]
        del e.game.targets[boar.id]
        e.admitted[lead["id"]] = "night_wolf"
        e._settle()
        wolf = e.game.targets[lead["id"]]
        tick(e)
        self.assertIn(wolf.id, e.hunting)
        wolf.chunk = ChunkKey(here.dimension, here.x - 4, here.y)
        tick(e)
        self.assertEqual(e.leads, [])
        e._settle()
        self.assertNotIn(wolf.id, e.game.targets)

    def test_hunters_are_saved_and_a_chase_replays_in_any_slicing(self):
        a, boar = boar_beside()
        tick(a)
        loaded = Expedition.from_dict(json.loads(canonical_json(a.to_dict())))
        self.assertEqual(loaded.hunting, a.hunting)
        b, _ = boar_beside()
        b.monster_ms = 0
        a2, _ = boar_beside()
        a2.monster_ms = 0
        a2.advance(6_000)
        for _ in range(60):
            b.advance(100)
        self.assertEqual(canonical_json(a2.to_dict()), canonical_json(b.to_dict()))
        bad = a.to_dict()
        bad["hunting"] = {"enc:nowhere": {"mode": "hunt", "since": 0}}
        with self.assertRaises(ValueError):
            Expedition.from_dict(bad)

    def test_the_minimap_is_the_loaded_range_and_shows_hunters(self):
        from dimensional_sim.world.session import snapshot
        e, boar = boar_beside()
        tick(e)
        frame = snapshot(e.game, expedition=e)
        self.assertEqual({(m["x"], m["y"]) for m in frame["minimap"]},
                         {(c.key.x, c.key.y) for c in e._resident()}, "what the minimap shows is what is loaded")
        self.assertIn(next(t for t in frame["targets"] if t["id"] == boar.id)["hunting"], HUNTING)

    def test_schema_nineteen_saves_start_with_nobody_hunting(self):
        e, _ = boar_beside()
        old = {k: v for k, v in v21(e.to_dict()).items() if k not in ("hunting", "possess_charge",
               "possess_charge_at_ms", "possess_drain_duration_ms")}
        old.update(schema_version=19, possess_ready_ms=0)
        self.assertEqual(Expedition.from_dict(json.loads(json.dumps(old))).hunting, {})


if __name__ == "__main__":
    unittest.main()
