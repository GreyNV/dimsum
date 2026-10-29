"""Day and night: wolves grow likelier across a life and raid even firelit camps."""
import json
import pathlib
import re
import unittest

from dimensional_sim.world import tuning
from dimensional_sim.world.autopilot import Expedition, night, saves
from dimensional_sim.world.catalog import BY_ID, ENEMIES, REGION_TREES, REGIONS, TREE_KINDS
from dimensional_sim.world.models import ChunkKey
from dimensional_sim.world.runtime import Exploration
from dimensional_sim.world.seeds import canonical_json
from dimensional_sim.world.session import TREE_LETTERS, snapshot
from dimensional_sim.world.web import new_world
from save_fixture import v17, v21

BROWSER = pathlib.Path(__file__).resolve().parents[1] / "src" / "dimensional_sim" / "world" / "browser"
NIGHTFALL = tuning.DAY_MS - tuning.NIGHT_MS - tuning.DAY_START_MS   # first nightfall in total_ms


def started(seed=482910):
    e = Expedition(Exploration(new_world(seed), "forest"))
    while e.in_prologue:
        e.advance(500)
    e.goal = e.task = None
    return e


def out_in_the_dark(seed=482910):
    """An avatar two chunks east of the anchor, fed and well, a moment before nightfall."""
    e = started(seed)
    key = ChunkKey(e.dimension, 2, 0)
    chunk = e.game.world.get(key)
    e.game._enter(key)
    e.game.player.chunk = key
    spawn = next(s for s in chunk.asset.spawns if s.kind == "player")
    e.game.player.x, e.game.player.y = spawn.x, spawn.y
    e._screen()
    e.night_tick = night.world_clock(e.total_ms) // tuning.NIGHT_SPAWN_EVERY_MS
    return e


def wolves(e):
    return [lead for lead in e.leads if lead["action"] == night.NIGHT_ACTION]


class ClockTests(unittest.TestCase):
    def test_eight_minutes_of_day_then_four_of_night(self):
        self.assertFalse(night.is_night(0))
        self.assertEqual(night.time_of_day(0), tuning.DAY_START_MS)
        self.assertFalse(night.is_night(NIGHTFALL - 1))
        self.assertTrue(night.is_night(NIGHTFALL))
        self.assertTrue(night.is_night(NIGHTFALL + tuning.NIGHT_MS - 1))
        self.assertFalse(night.is_night(NIGHTFALL + tuning.NIGHT_MS))
        self.assertEqual(night.darkness_permille(NIGHTFALL), 1000)
        self.assertEqual(night.darkness_permille(NIGHTFALL - tuning.TWILIGHT_MS // 2), 500, "dusk fades in")
        self.assertEqual(night.darkness_permille(NIGHTFALL - tuning.TWILIGHT_MS - 1), 0)
        e = started()
        view = e.clock_view()
        self.assertEqual((view["day"], view["night"], view["phase"]), (1, False, "day"))

    def test_the_frame_carries_the_clock(self):
        e = started()
        clock = snapshot(e.game, expedition=e)["expedition"]["clock"]
        self.assertEqual(set(clock), {"day", "time_ms", "day_ms", "night_at_ms", "night", "phase", "darkness", "until_ms"})


class NightSpawnTests(unittest.TestCase):
    def test_wolves_come_only_at_night(self):
        e = out_in_the_dark()
        e.health = e.hunger = 10**9   # keep it alive; only spawning is under test
        e.total_ms = NIGHTFALL - 40_000
        e.night_tick = night.world_clock(e.total_ms) // tuning.NIGHT_SPAWN_EVERY_MS
        for tick in range(1):   # still day (one tick before nightfall)
            e.total_ms += tuning.NIGHT_SPAWN_EVERY_MS
            e._night_watch()
        self.assertEqual(wolves(e), [])
        found = None
        for _ in range(12):
            e.total_ms += tuning.NIGHT_SPAWN_EVERY_MS
            e._night_watch()
            if wolves(e):
                found = wolves(e)[0]
                break
        self.assertIsNotNone(found, "a wolf comes at night")
        self.assertIn("Night falls", " ".join(row["text"] for row in e.log))
        self.assertEqual(e.admitted[found["id"]], night.NIGHT_ACTION)
        self.assertEqual(night.time_of_day(found["expires_ms"]), 0, "it leaves at dawn")
        gx, gy = e._global(ChunkKey(found["dimension"], found["chunk_x"], found["chunk_y"]), found["x"], found["y"])
        px, py = e._player()
        self.assertGreaterEqual(abs(gx - px) + abs(gy - py), tuning.NIGHT_SPAWN_NEAR)

    def test_camp_and_campfire_can_be_raided_and_depth_sets_the_cap(self):
        camp = started()
        camp.total_ms = NIGHTFALL
        for _ in range(12):
            camp.total_ms += tuning.NIGHT_SPAWN_EVERY_MS
            camp._night_watch()
        self.assertTrue(wolves(camp), "the anchor camp can be raided")
        fire = out_in_the_dark()
        px, py = fire._player()
        fire.campfire = {"dimension": fire.dimension, "x": px, "y": py, "fire_x": px + 1, "fire_y": py}
        fire.total_ms = NIGHTFALL
        for _ in range(12):
            fire.total_ms += tuning.NIGHT_SPAWN_EVERY_MS
            fire._night_watch()
        self.assertTrue(wolves(fire), "a campfire can be raided")
        e = out_in_the_dark()
        e.total_ms = NIGHTFALL
        for _ in range(12):
            e.total_ms += tuning.NIGHT_SPAWN_EVERY_MS
            e._night_watch()
        self.assertLessEqual(len(e.night_foes()), night.night_cap(e.depth))
        self.assertEqual(night.night_cap(0), 1)
        self.assertEqual(night.night_cap(7), 3)
        self.assertEqual(night.night_chance(0), 60)
        self.assertEqual(night.night_chance(tuning.DAY_MS), 65)
        self.assertEqual(night.night_chance(20 * tuning.DAY_MS), 90)

    def test_wolves_ignore_fire_and_slink_off_at_dawn(self):
        self.assertFalse(ENEMIES["wolf"].fears_fire)
        self.assertEqual(BY_ID[night.NIGHT_ACTION].placement, "lead")
        e = out_in_the_dark()
        e.total_ms = NIGHTFALL
        for _ in range(12):
            e.total_ms += tuning.NIGHT_SPAWN_EVERY_MS
            e._night_watch()
            if wolves(e):
                break
        wolf = wolves(e)[0]
        e._settle()
        self.assertIn(wolf["id"], e.game.targets)
        e.total_ms = wolf["expires_ms"]
        e._expire_leads()
        self.assertNotIn(wolf["id"], e.game.targets)
        self.assertIn("slinks back", e.log[-1]["text"])

    def test_wolf_bites_a_resting_avatar_inside_camp_and_never_grows_with_life_depth(self):
        e = started()
        e.depth = 3
        e.total_ms = NIGHTFALL
        e.night_tick = night.world_clock(e.total_ms) // tuning.NIGHT_SPAWN_EVERY_MS
        for _ in range(8):
            e.total_ms += tuning.NIGHT_SPAWN_EVERY_MS
            e._night_watch()
            if wolves(e):
                break
        self.assertTrue(wolves(e))
        lead = wolves(e)[0]
        e._settle()
        target = e.game.targets[lead["id"]]
        deep = e.enemy_hit(target.chunk, ENEMIES["wolf"])
        e.depth = 0
        self.assertEqual(deep, e.enemy_hit(target.chunk, ENEMIES["wolf"]), "fixed numbers: depth never grows a bite")
        e.depth = 3
        px, py = e._player()
        target.chunk = e.game.player.chunk
        target.x, target.y = px % e.game.current_chunk().asset.width + 1, py % e.game.current_chunk().asset.height
        e.task = {"type": "rest", "spot": None, "elapsed_ms": 0, "duration_ms": 10_000}
        before = e.health
        e.monster_ms = 300
        e._pursue()
        self.assertEqual(e.hunting[lead["id"]]["mode"], "windup", "the wolf's tell comes first")
        self.assertIsNone(e.task, "the raid interrupts rest")
        for _ in range(4):   # the lunge lands after its wind-up unless the avatar steps away
            e.total_ms += 300
            e.monster_ms = 300
            e._pursue()
        self.assertLess(e.health, before)

    def test_cornered_at_the_camp_the_avatar_fights_back_and_never_heals_through_bites(self):
        """Regression: badly hurt at the camp, a wolf alongside, the auto-pilot kept "retreating"
        to where it already stood and rested; rest healing matched the bites, so for minutes
        nobody won (health hovered at 1)."""
        e = started()
        e.depth = 3
        e.total_ms = NIGHTFALL
        e.night_tick = night.world_clock(e.total_ms) // tuning.NIGHT_SPAWN_EVERY_MS
        for _ in range(8):
            e.total_ms += tuning.NIGHT_SPAWN_EVERY_MS
            e._night_watch()
            if wolves(e):
                break
        lead = wolves(e)[0]
        e._settle()
        target = e.game.targets[lead["id"]]
        px, py = e._player()
        target.chunk = e.game.player.chunk
        target.x, target.y = px % e.game.current_chunk().asset.width + 1, py % e.game.current_chunk().asset.height
        self.assertTrue(e.at_camp())
        e.health = 2 * e.enemy_hit(target.chunk, ENEMIES["wolf"])   # one bite from death's door
        e.goal, e.task = e._home_goal(), {"type": "rest", "spot": None, "elapsed_ms": 0, "duration_ms": 10_000}
        hp, life = target.hp, e.life
        e.advance(1000)
        self.assertTrue(e.life > life or e.anchor_ms is not None or (e.goal or {}).get("kind") == "target",
                        "cornered, it turns on the wolf")
        e.advance(60_000)
        self.assertTrue(e.anchor_ms is not None or e.life > life or target.hp < hp or lead["id"] in e.completed,
                        "a minute later somebody has won or lost")

    def test_a_night_replays_exactly_in_any_slicing_and_survives_reload(self):
        a, b = out_in_the_dark(), out_in_the_dark()
        for e in (a, b):
            e.total_ms = NIGHTFALL - 5_000
            e.night_tick = night.world_clock(e.total_ms) // tuning.NIGHT_SPAWN_EVERY_MS
        a.advance(90_000)
        for _ in range(90_000 // 333):
            b.advance(333)
        b.advance(90_000 - (90_000 // 333) * 333)
        self.assertEqual(canonical_json(a.to_dict()), canonical_json(b.to_dict()))
        again = Expedition.from_dict(json.loads(canonical_json(a.to_dict())))
        self.assertEqual(again.night_tick, a.night_tick)

    def test_schema_eighteen_saves_start_watching_from_now(self):
        e = started()
        old = {k: v for k, v in v21(e.to_dict()).items() if k not in ("night_tick", "hunting") + saves.V21_FIELDS}
        old["possess_ready_ms"] = 0
        old["schema_version"] = 18
        loaded = Expedition.from_dict(json.loads(json.dumps(old)))
        self.assertEqual(loaded.night_tick, night.world_clock(e.total_ms) // tuning.NIGHT_SPAWN_EVERY_MS)
        older = v17(e.to_dict())
        self.assertEqual(Expedition.from_dict(json.loads(json.dumps(older))).night_tick, loaded.night_tick)


class TreeKindTests(unittest.TestCase):
    def test_every_region_mixes_known_kinds_and_every_kind_has_art(self):
        self.assertEqual(set(REGION_TREES), set(REGIONS))
        source = (BROWSER / "nature_art.js").read_text(encoding="utf-8")
        art = set(re.findall(r"(\w):\s*draw\w+", source[source.index("export const TREE_ART"):]))
        self.assertEqual({TREE_LETTERS[k] for k in TREE_KINDS} - art, set())

    def test_tree_kinds_follow_regions_and_are_stable(self):
        e = started()
        frame = snapshot(e.game, expedition=e)
        letters, by_tint = {}, {r.tint: r.id for r in REGIONS.values()}
        for chunk in frame["chunks"]:
            for y, row in enumerate(chunk["trees"]):
                for x, letter in enumerate(row):
                    self.assertEqual(letter != ".", chunk["tiles"][y][x] == "T")
                    if letter != ".":
                        tint = chunk["tint_legend"][chunk["tint_rows"][y][x]] if chunk["tint_rows"] else chunk["tint"]
                        letters.setdefault(by_tint[tint], set()).add(letter)
        allowed = {r: {TREE_LETTERS[k] for k, _ in REGION_TREES[r]} for r in REGION_TREES}
        for region, seen in letters.items():
            self.assertLessEqual(seen, allowed[region], region)
        self.assertTrue(any(len(s) > 1 for s in letters.values()), "regions mix several kinds")
        again = snapshot(e.game, expedition=e)
        self.assertEqual([c["trees"] for c in frame["chunks"]], [c["trees"] for c in again["chunks"]])


if __name__ == "__main__":
    unittest.main()
