import copy
import json
import unittest
from dataclasses import replace

from dimensional_sim.world.animation import (
    Animation, Frame, animations_from_dict, animations_to_dict, default_animations, rotate)
from dimensional_sim.world.models import Cell, ChunkKey, DimensionSpec
from dimensional_sim.world.repository import WorldRepository
from dimensional_sim.world.runtime import Exploration, InputCommand, Target
from test_world_models import fixture_asset


def exploration(**options):
    world = WorldRepository(482910, (DimensionSpec("forest", width=8, height=6, danger=0),),
                            (fixture_asset(),), cache_limit=1)
    return Exploration(world, **options)


def snapshot(game):
    return json.loads(json.dumps(game.to_dict()))


class AnimationTests(unittest.TestCase):
    def test_all_clips_valid_and_roundtrip(self):
        clips = default_animations()
        self.assertEqual(set(clips), {"idle", "walk", "attack", "hit", "death"})
        self.assertEqual(animations_from_dict(json.loads(json.dumps(animations_to_dict(clips)))), clips)
        self.assertFalse(clips["attack"].sample(119).active)
        self.assertTrue(clips["attack"].sample(120).active)
        self.assertFalse(clips["attack"].sample(200).active)
        self.assertTrue(clips["attack"].sample(60, 200).active)

    def test_invalid_metadata_rejected(self):
        for make in (lambda: Frame(0, Cell("@")),
                     lambda: Frame(10, Cell("@"), active=True),
                     lambda: Frame(10, Cell("@"), hitbox=((0, -1),)),
                     lambda: Frame(10, Cell("@"), anchor=(True, 0)),
                     lambda: Animation("attack", (Frame(10, Cell("@")),), False)):
            with self.assertRaises(ValueError):
                make()

    def test_facing_rotation(self):
        self.assertEqual([rotate((0, -1), d) for d in ("north", "east", "south", "west")],
                         [(0, -1), (1, 0), (0, 1), (-1, 0)])


class RuntimeTests(unittest.TestCase):
    def test_idle_walk_and_blocking_changes_facing(self):
        game = exploration()
        start = (game.player.x, game.player.y)
        game.advance(119, InputCommand("north"))
        self.assertEqual((game.player.x, game.player.y), start)
        self.assertEqual(game.player.animation, "walk")
        game.advance(1, InputCommand("north"))
        self.assertEqual((game.player.x, game.player.y), (4, 2))
        game.player.x, game.player.y = 1, 1
        game.advance(120, InputCommand("west"))
        self.assertEqual((game.player.x, game.player.y), (1, 1))
        self.assertEqual(game.player.facing, "west")
        game.advance(20)
        self.assertEqual(game.player.animation, "idle")

    def test_step_on_press_taps_move_once_and_holds_repeat_partition_free(self):
        game = exploration()
        game.step_on_press = True
        start = (game.player.x, game.player.y)
        game.advance(0, InputCommand("north"))
        self.assertEqual((game.player.x, game.player.y), (start[0], start[1] - 1))
        game.advance(119, InputCommand("north"))
        self.assertEqual(game.player.y, start[1] - 1)
        game.advance(0, InputCommand())
        game.advance(0, InputCommand("south"))
        self.assertEqual(game.player.y, start[1])
        bulk, split = exploration(), exploration()
        for g in (bulk, split): g.step_on_press = True
        bulk.advance(240, InputCommand("east"))
        split.advance(0, InputCommand("east"))
        for _ in range(12): split.advance(20, InputCommand("east"))
        self.assertEqual(bulk.to_dict(), split.to_dict())
        default = exploration()
        default.advance(0, InputCommand("north"))
        self.assertEqual((default.player.x, default.player.y), start)
        default.step_on_press = "yes"
        with self.assertRaises(ValueError):
            default.advance(0)

    def test_all_edges_and_negative_coordinates(self):
        cases = [("north", (4, 0), (0, -1), (4, 5)),
                 ("east", (7, 3), (1, 0), (0, 3)),
                 ("south", (4, 5), (0, 1), (4, 0)),
                 ("west", (0, 3), (-1, 0), (7, 3))]
        for direction, start, chunk, end in cases:
            with self.subTest(direction=direction):
                game = exploration()
                game.player.x, game.player.y = start
                game.advance(120, InputCommand(direction))
                self.assertEqual((game.player.chunk.x, game.player.chunk.y), chunk)
                self.assertEqual((game.player.x, game.player.y), end)
                self.assertFalse(game.current_chunk().asset.collision[end[1]][end[0]])
                self.assertEqual(game.world.status(game.player.chunk), "visited")

    def test_damage_active_only_once_and_out_of_range_untouched(self):
        game = exploration()
        game.targets = {"near": Target("near", game.player.chunk, 4, 2, 5),
                        "far": Target("far", game.player.chunk, 4, 0, 5)}
        game.advance(119, InputCommand(attack=True))
        self.assertEqual(game.targets["near"].hp, 5)
        self.assertEqual(game.effect_cells(), {})
        game.advance(1, InputCommand(attack=True))
        self.assertEqual(game.targets["near"].hp, 4)
        self.assertIn((4, 2), game.effect_cells())
        game.advance(1000, InputCommand(attack=True))
        self.assertEqual(game.targets["near"].hp, 4)
        self.assertEqual(game.targets["far"].hp, 5)
        game.advance(0)
        game.advance(360, InputCommand(attack=True))
        self.assertEqual(game.targets["near"].hp, 3)

    def test_facing_command_turns_without_moving_before_attack(self):
        game = exploration()
        game.targets["east"] = Target("east", game.player.chunk, game.player.x + 1, game.player.y, 3)
        start = (game.player.chunk, game.player.x, game.player.y)
        game.advance(120, InputCommand(attack=True, face="east"))
        self.assertEqual((game.player.chunk, game.player.x, game.player.y), start)
        self.assertEqual(game.player.facing, "east")
        self.assertEqual(game.targets["east"].hp, 2)
        with self.assertRaises(ValueError):
            InputCommand(face="northeast")

    def test_all_facing_hitboxes_and_attack_locks_movement(self):
        for facing, offset in zip(("north", "east", "south", "west"),
                                  ((0, -1), (1, 0), (0, 1), (-1, 0))):
            game = exploration()
            game.player.facing = facing
            game.targets["target"] = Target("target", game.player.chunk,
                                            4 + offset[0], 3 + offset[1])
            game.advance(200, InputCommand(facing, True))
            self.assertEqual((game.player.x, game.player.y), (4, 3))
            self.assertEqual(game.targets["target"].hp, 2)

    def test_bulk_split_and_render_frequency_equivalent(self):
        bulk, split = exploration(attack_rate_percent=137), exploration(attack_rate_percent=137)
        for game in (bulk, split):
            game.targets["target"] = Target("target", game.player.chunk, 4, 2)
        commands = [(263, InputCommand(attack=True)), (677, InputCommand("west")),
                    (63, InputCommand()), (450, InputCommand("east", True))]
        for duration, command in commands:
            bulk.advance(duration, command)
            for _ in range(duration):
                split.advance(1, command)
                split.player_cell()
                split.effect_cells()
                split.current_chunk()
        self.assertEqual(snapshot(bulk), snapshot(split))

    def test_rates_and_custom_metadata_are_data_driven_without_regeneration(self):
        slow, fast = exploration(), exploration(attack_rate_percent=200, animation_rate_percent=200)
        for game in (slow, fast):
            game.targets["target"] = Target("target", game.player.chunk, 4, 2)
        generations = fast.world.generation_count
        slow.advance(60, InputCommand(attack=True))
        fast.advance(60, InputCommand(attack=True))
        self.assertEqual(slow.targets["target"].hp, 3)
        self.assertEqual(fast.targets["target"].hp, 2)
        fast.advance(120, InputCommand(attack=True))
        self.assertEqual(fast.player.animation, "idle")
        fast.player_cell()
        self.assertEqual(generations, fast.world.generation_count)
        clips = default_animations()
        clips["attack"] = Animation("attack", (
            Frame(40, Cell("@")), Frame(10, Cell("@"), active=True, hitbox=((0, -2),)),
            Frame(20, Cell("@"))), loop=False)
        custom = exploration(animations=clips)
        custom.targets["far"] = Target("far", custom.player.chunk, 4, 1)
        custom.advance(70, InputCommand(attack=True))
        self.assertEqual(custom.targets["far"].hp, 2)

    def test_enemy_hp_survives_eviction_and_reentry(self):
        game = exploration()
        key = game.player.chunk
        game.targets["target"] = Target("target", key, 4, 2, 0)
        game.player.x, game.player.y = 0, 3
        game.advance(120, InputCommand("west"))
        self.assertIsNone(game.world.peek(key))
        game.advance(120, InputCommand("east"))
        self.assertEqual(game.player.chunk, key)
        self.assertEqual(game.targets["target"].hp, 0)

    def test_snapshot_partial_move_and_mid_attack_continuation(self):
        game = exploration(attack_rate_percent=137)
        game.targets["target"] = Target("target", game.player.chunk, 4, 2)
        game.advance(100, InputCommand(attack=True))
        loaded = Exploration.from_dict(snapshot(game))
        self.assertEqual(snapshot(game), snapshot(loaded))
        for duration, command in [(200, InputCommand(attack=True)), (59, InputCommand("west"))]:
            game.advance(duration, command)
            loaded.advance(duration, command)
        reloaded = Exploration.from_dict(snapshot(loaded))
        for current in (game, loaded, reloaded):
            current.advance(61, InputCommand("west"))
        self.assertEqual(snapshot(game), snapshot(loaded))
        self.assertEqual(snapshot(game), snapshot(reloaded))

    def test_corrupt_snapshots_rejected(self):
        game = exploration()
        game.targets["target"] = Target("target", game.player.chunk, 4, 2)
        base = snapshot(game)
        mutations = [
            lambda s: s.update(schema_version=2),
            lambda s: s["player"].update(x=0, y=0),
            lambda s: s["player"].update(animation_elapsed_ms=-1),
            lambda s: s.update(move_elapsed_ms=120),
            lambda s: s["config"].update(attack_rate_percent=0),
            lambda s: s["targets"][0].update(hp=-1),
            lambda s: s["targets"].append(copy.deepcopy(s["targets"][0])),
            lambda s: s.update(hit_targets=["missing"]),
            lambda s: s.update(attack_held=1),
            lambda s: s["animations"]["attack"]["frames"][1].update(hitbox=[]),
            lambda s: s.update(initialized_chunks=[]),
            lambda s: s.update(unexpected=True),
        ]
        for mutation in mutations:
            bad = copy.deepcopy(base)
            mutation(bad)
            with self.assertRaises(ValueError):
                Exploration.from_dict(bad)
        self.assertEqual(snapshot(game), base)

    def test_invalid_input_is_atomic_and_render_reads_pure(self):
        game = exploration()
        before = snapshot(game)
        for value in (-1, True, 1.5):
            with self.assertRaises(ValueError):
                game.advance(value)
        for _ in range(10):
            game.player_cell()
            game.effect_cells()
            game.current_chunk()
        self.assertEqual(snapshot(game), before)


    def test_direct_snapshot_api_and_single_cell_anchor_contract(self):
        game = exploration()
        self.assertEqual(game.to_dict(), Exploration.from_dict(game.to_dict()).to_dict())
        with self.assertRaises(ValueError):
            Frame(10, Cell("@"), anchor=(1, 0))

    def test_movement_interval_cannot_invalidate_partial_clock(self):
        game = exploration()
        game.advance(100, InputCommand("north"))
        with self.assertRaises(AttributeError):
            game.movement_interval_ms = 60
        game.advance(20, InputCommand("north"))
        self.assertEqual((game.player.x, game.player.y), (4, 2))
        self.assertEqual(game.elapsed_ms, 120)

    def test_generated_target_identity_validation_and_long_dimension(self):
        dimension = "f" * 128
        world = WorldRepository(482910,
            (DimensionSpec(dimension, width=8, height=6, danger=25),),
            (fixture_asset(),), cache_limit=1)
        game = Exploration(world)
        self.assertTrue(game.targets)
        self.assertTrue(all(len(t.id) < 128 for t in game.targets.values()))
        self.assertEqual(game.to_dict(), Exploration.from_dict(game.to_dict()).to_dict())
        for mutation in (lambda s: s.update(targets=[]),
                         lambda s: s["targets"][0].update(hp=4),
                         lambda s: s["targets"][0].update(id="invented")):
            data = game.to_dict()
            mutation(data)
            with self.assertRaises(ValueError):
                Exploration.from_dict(data)

    def test_impossible_hit_set_rejected(self):
        game = exploration()
        game.targets["far"] = Target("far", game.player.chunk, 4, 0)
        game.advance(130, InputCommand(attack=True))
        data = game.to_dict()
        data["hit_targets"] = ["far"]
        with self.assertRaises(ValueError):
            Exploration.from_dict(data)
        game.targets["near"] = Target("near", game.player.chunk, 4, 2)
        game.advance(0)
        # Merely putting a target nearby before the active window cannot claim a hit.
        data = game.to_dict()
        data["player"]["animation_elapsed_ms"] = 10
        data["hit_targets"] = ["near"]
        with self.assertRaises(ValueError):
            Exploration.from_dict(data)



class RateConfigurationRegressionTests(unittest.TestCase):
    def test_attack_and_animation_rates_cannot_skip_active_windows_mid_attack(self):
        game = exploration()
        game.targets["near"] = Target("near", game.player.chunk, 4, 2)
        game.advance(119, InputCommand(attack=True))
        for name in ("attack_rate_percent", "animation_rate_percent"):
            with self.assertRaises(AttributeError):
                setattr(game, name, 200)
        game.advance(1, InputCommand(attack=True))
        self.assertEqual(game.targets["near"].hp, 2)
