from __future__ import annotations

import argparse
from dataclasses import asdict
import json

from .balance import action_graph, compare, run_scenario
from .core import new_demo_game


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the Dimensional Summoner Phase One balance simulator")
    parser.add_argument("--seconds", type=float, default=24 * 60 * 60)
    parser.add_argument("--seed", type=int, default=1, help="seed, or first seed for comparison batches")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--compare", action="store_true")
    mode.add_argument("--graph", action="store_true")
    mode.add_argument("--offline", action="store_true")
    parser.add_argument("--runs", type=int, default=100, help="runs per comparison variant")
    parser.add_argument("--summons", type=int, default=0,
                        help="number of shard-funded pulls after a single simulation")
    args = parser.parse_args()
    try:
        if args.summons < 0 or (args.summons and (args.compare or args.graph)):
            raise ValueError("--summons requires a single run and a non-negative count")
        if args.runs < 1:
            raise ValueError("--runs must be at least one")
        if args.seed < 0:
            raise ValueError("--seed must be non-negative")
        if args.compare:
            report = compare(args.seconds, seeds=range(args.seed, args.seed + args.runs))
        elif args.graph:
            report = action_graph(new_demo_game(args.seed))
        else:
            report = asdict(run_scenario(args.seconds, active=not args.offline, seed=args.seed, summons=args.summons))
    except (ValueError, KeyError) as exc:
        parser.error(str(exc))
    print(json.dumps(report, indent=2, sort_keys=True, allow_nan=False))


if __name__ == "__main__":
    main()
