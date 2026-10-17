"""Summarize tools/measure_lives.py output: python tools/measure_report.py DIR PREFIX [PREFIX...]"""
import json, sys, glob
from statistics import mean, median
for tag in sys.argv[2:]:
    runs = [json.load(open(f)) for f in sorted(glob.glob(f"{sys.argv[1]}/{tag}_*.json"))]
    lives = [l for r in runs for l in r["lives"]]
    if not lives: continue
    g = lambda l, k: l["items"].get(k, 0)
    st = [l["station_min"] for l in lives if l["station_min"] is not None]
    print(f"== {tag}: {len(runs)} seeds, {len(lives)} lives, mean life {mean(l['minutes'] for l in lives):.1f} min, causes",
          {c: sum(1 for l in lives if l['cause'] == c) for c in {l['cause'] for l in lives}})
    print("   per life: sticks %.1f  hides %.1f  berries %.1f  food items %.1f  campfires %.2f  chunks %.1f  depth %.1f" % (
        mean(g(l, 'stick') for l in lives), mean(g(l, 'boar_hide') for l in lives), mean(g(l, 'wild_berries') for l in lives),
        mean(sum(v for k, v in l['items'].items() if k in ('wild_berries','bird_egg','boar_meat','venison','pale_mushroom','snared_hare')) for l in lives),
        mean(l['actions'].get('make_campfire', 0) for l in lives), mean(l['chunks'] for l in lives), mean(l['depth'] for l in lives)))
    print("   sticks per minute %.2f" % (sum(g(l,'stick') for l in lives) / sum(l['minutes'] for l in lives)))
    print(f"   station built in {len(st)}/{len(lives)} lives; minute median {median(st) if st else '-'}; bound by end:",
          [r['bound'] for r in runs], "ash", [r['ash'] for r in runs])
