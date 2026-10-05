"""Opt-in spatial CLI. Asset generation imports occur only in generate-assets.

Examples:
  python -m dimensional_sim.world.cli demo --seed 482910
  python -m dimensional_sim.world.cli play --seed 482910
  python -m dimensional_sim.world.cli generate-assets --biome dark_forest --seed 482910 --chunks 24 --size 64x32 --variants 6
"""
import argparse
from collections import Counter
from dataclasses import asdict
from pathlib import Path

from .assets import AssetRegistry, _atomic_write, _read, parse_json
from .models import ChunkKey, DimensionSpec, chunk_to_dict
from .repository import WorldRepository
from .renderer import render, to_ansi, to_text
from .runtime import Exploration, InputCommand
from .seeds import canonical_json

MAX_SAVE_BYTES = 64 * 1024 * 1024


def size(value):
    try:
        width, height = map(int, value.lower().split("x"))
        DimensionSpec("check", width=width, height=height)
        return width, height
    except (TypeError, ValueError):
        raise argparse.ArgumentTypeError("size must be WIDTHxHEIGHT, width8..128 and height6..64")


def command_script(value):
    """Parse the entire script before simulation, so typos cannot partly apply it."""
    result = []
    for token in value.split(","):
        parts = token.strip().split(":")
        if len(parts) > 2 or parts[0] not in ("north","east","south","west","attack","wait"):
            raise ValueError("commands: north/east/south/west/attack/wait[:milliseconds]")
        duration = int(parts[1]) if len(parts) == 2 else (400 if parts[0] == "attack" else 120)
        if not 0 <= duration <= 600000:
            raise ValueError("command duration must be 0..600000 ms")
        name = parts[0]
        result.append((duration, InputCommand(
            move=name if name in ("north","east","south","west") else None,
            attack=name == "attack")))
    return result


def _new_world(args):
    width, height = args.size
    assets = AssetRegistry(Path(args.catalog)).snapshot() if args.catalog else None
    if args.mode == "browser" and not args.catalog:
        from .open_terrain import open_assets
        assets = open_assets(width, height)
    spec = DimensionSpec(args.dimension, (args.biome,), width, height, args.danger)
    return WorldRepository(args.seed, (spec,), assets, args.cache_limit)


def _save(path, state):
    raw = canonical_json(state).encode("ascii")
    if len(raw) > MAX_SAVE_BYTES:
        raise ValueError("exploration save exceeds 64MiB limit")
    _atomic_write(Path(path), raw)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Dimensional Summoner character-grid foundation")
    subs = parser.add_subparsers(dest="mode", required=True)
    gen = subs.add_parser("generate-assets", help="offline staged generation; rerun to retry failed jobs")
    gen.add_argument("--biome", default="dark_forest")
    gen.add_argument("--seed", type=int, default=482910)
    gen.add_argument("--chunks", type=int, default=1)
    gen.add_argument("--size", type=size, default=(32,16))
    gen.add_argument("--variants", type=int, default=1)
    gen.add_argument("--output", default=".codex/artifacts/world-assets")
    sim = subs.add_parser("simulate", help="run seeded headless expeditions and print metrics JSON")
    sim.add_argument("--seeds", default="1-10")
    sim.add_argument("--minutes", type=int, default=30)
    sim.add_argument("--policy", choices=("spend", "hoard", "idle"), default="spend")
    sim.add_argument("--lives", action="store_true", help="include every life, not only the summary")
    ins = subs.add_parser("inspect", help="explain one chunk: region, spots, action bucket, exclusions")
    ins.add_argument("--seed", type=int, default=482910)
    ins.add_argument("--x", type=int, default=0)
    ins.add_argument("--y", type=int, default=0)
    ins.add_argument("--life", type=int, default=1)
    ins.add_argument("--unlock", action="append", default=[], help="unlock id (repeatable)")
    for name in ("chunk", "demo", "play", "browser"):
        sub = subs.add_parser(name)
        sub.add_argument("--seed", type=int, default=482910)
        sub.add_argument("--dimension", default="forest")
        sub.add_argument("--biome", default="dark_forest")
        sub.add_argument("--size", type=size, default=(32,16))
        sub.add_argument("--danger", type=int, default=25)
        sub.add_argument("--catalog", help="validated registry directory; new worlds only")
        sub.add_argument("--cache-limit", type=int, default=9)
        if name == "chunk":
            sub.add_argument("--x", type=int, default=0)
            sub.add_argument("--y", type=int, default=0)
        else:
            sub.add_argument("--load", help="resume a self-contained exploration save")
            sub.add_argument("--save", help="atomic exploration save on completion")
            if name == "demo":
                sub.add_argument("--commands", default="east:120,attack:400,wait:120")
                sub.add_argument("--format", choices=("text","ansi","json"), default="text")
                sub.add_argument("--no-map", action="store_true")
            elif name == "browser":
                sub.add_argument("--port", type=int, default=8765)
                sub.add_argument("--unlock-control", action="store_true",
                                 help="development: unlock the take_control skill (manual WASD)")
            else:
                sub.add_argument("--fps", type=int, default=20)
                sub.add_argument("--plain", action="store_true")
    args = parser.parse_args(argv)
    try:
        if args.mode == "generate-assets":
            from .pipeline import AssetPipeline, GenerationRequest, LocalProvider
            root = Path(args.output)
            request = GenerationRequest(args.biome, args.seed, args.chunks, *args.size, args.variants)
            pipeline = AssetPipeline(root / "pipeline", AssetRegistry(root / "registry"), LocalProvider())
            report = pipeline.run(request)
            print(canonical_json({"counts": dict(Counter(j["status"] for j in report["jobs"])),
                                  "manifest": str(pipeline.manifest_path(request)), **report}))
            return 1 if any(j["status"] != "accepted" for j in report["jobs"]) else 0
        if args.mode in ("simulate", "inspect"):
            import json
            from . import simulate
            if args.mode == "inspect":
                print(json.dumps(simulate.inspect_chunk(args.seed, args.x, args.y, args.life, args.unlock), indent=1))
                return 0
            results = [simulate.run(seed, args.minutes, args.policy) for seed in simulate.parse_seeds(args.seeds)]
            out = {"summary": simulate.summarize(results)}
            if args.lives:
                out["runs"] = results
            print(json.dumps(out, indent=1))
            return 0
        if args.mode == "chunk":
            print(canonical_json(chunk_to_dict(_new_world(args).get(
                ChunkKey(args.dimension, args.x, args.y)))))
            return 0
        script = command_script(args.commands) if args.mode == "demo" else None
        raw = parse_json(_read(args.load, MAX_SAVE_BYTES), MAX_SAVE_BYTES) if args.load else None
        expedition = None
        if args.mode == "browser":
            from .autopilot import Expedition
            if raw is not None and "exploration" in raw:
                expedition = Expedition.from_dict(raw)
                game = expedition.game
            else:
                game = Exploration.from_dict(raw) if raw is not None else Exploration(_new_world(args), args.dimension)
                expedition = Expedition(game)
            if args.unlock_control:
                expedition.unlock("take_control")
        else:
            game = Exploration.from_dict(raw) if raw is not None else Exploration(_new_world(args), args.dimension)
        if script is not None:
            for duration, command in script:
                # Each comma-separated token is a discrete input gesture.
                game.advance(0, InputCommand())
                game.advance(duration, command)
            frame = render(game, show_map=not args.no_map)
            if args.format == "json":
                print(canonical_json({"player": asdict(game.player),
                    "targets": [asdict(t) for t in game.targets.values()],
                    "minimap": game.world.minimap(game.player.chunk),
                    "frame": to_text(frame), "resident_chunks": game.world.resident_count}))
            else:
                print(to_text(frame) if args.format == "text" else to_ansi(frame))
                print(f"{game.player.chunk.dimension} ({game.player.chunk.x},{game.player.chunk.y}) "
                      f"facing {game.player.facing}; {game.player.animation}")
        elif args.mode == "browser":
            from .browser_server import serve
            serve(game, args.port, expedition)
        else:
            from .terminal import play
            play(game, fps=args.fps, plain=args.plain)
        if args.save:
            _save(args.save, expedition.to_dict() if expedition is not None else game.to_dict())
        return 0
    except (ValueError, OSError) as exc:
        parser.error(str(exc))


if __name__ == "__main__":
    raise SystemExit(main())
