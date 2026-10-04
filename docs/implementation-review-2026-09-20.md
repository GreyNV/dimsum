# Implementation review - 2026-09-20

## Correction after the review

The user clarified that story stages require only the preceding story action,
and bucket actions require their story action plus a current-life roll or journal
unlock. The former level-12 gate was an implementation error, not a balance target.
It has been removed, along with all discipline-level access fields. Enabled
journal unlocks now guarantee eligibility without another roll. Story completions,
per-life rolls and multi-encounter queues persist in save schema 3.

The results below are historical measurements of the superseded gated prototype;
they must not be used as current pacing evidence. The gate-policy question below
is resolved by this clarification.

## Assessment

This is a Python headless simulation and balance laboratory with three disciplines,
three stages, ten actions including encounters, a passive clone and three
soulbound items. It follows the approved automatic-life direction. There is no
UI to audit; production presentation is excluded from phase one. The workspace
has no Git repository.

The original seven tests passed despite critical event-time and persistence
defects. Those defects are fixed; phase one is still in progress.

## Corrections

| Finding | Evidence | Correction |
| --- | --- | --- |
| Partial action loss | One 100-second call earned XP; 100 one-second calls earned none | Persist work; chronological completion and level events |
| Training depended on nominal work | Completion awarded baseline duration times rate | XP per effective training second |
| Delayed vitality exhaustion | Full action elapsed before checking cost | Continuous cost, configurable decay, immediate death |
| Restart bypassed resets | start_life healed/rerolled while preserving XP | Reject duplicate starts; clear temporary state on return |
| Journal auto-disabled encounters | Threshold set enabled to false | Preserve player choice; discover at bucket generation |
| Summons undercharged | Seed 1 got a 25-shard Anchor Thread for 10 shards | Equal-cost pools and atomic validation |
| Unsafe save deserialization | RNG restore called pickle.loads | JSON RNG and data-only legacy migration |
| Saves omitted rules/progress | Defaults could change replay | Persist/validate config, content, partial work and clocks |
| Invalid content could stall simulation | Empty stages, invalid curves, duplicate IDs accepted | Validate content/config/time |
| Offline clock hid real time | World clock used discounted life time | Separate clocks and clone telemetry |
| Reports lacked planned evidence | Limited medians and summaries | Timing, reach rates, vitality, journal and gate diagnostics |
| CLI ignored comparison seed | --seed had no effect on batches | Honor seed; add --runs, --offline, --graph |
| Isolated build omitted backend dependency | Empty requires with setuptools backend | Declare backend, src layout, console entry point |

Content authoring is separated from mechanics. Equipping is idempotent and
unequipping is supported.

## Verification and balance

All 40 tests pass, covering 2,000 short updates versus one long update in both
modes, partial-save continuation, mid-action levels, death ties, lethal/recovery
encounters, clone accrual, journal persistence, summon atomicity, migration,
malicious pickle rejection, invalid content, reporting and CLI validation.

An isolated version-0.2.0 wheel build succeeded. The wheel imported independently
of the source tree and ran a 100-second simulation. Its console entry point is
dimensional_sim.cli:main.

Seeds 1?100 were simulated for one day across four variants:

| Variant | Runs | Median lives started | Median total shards | Old Trail reach rate |
| --- | ---: | ---: | ---: | ---: |
| Active | 100 | 51 | 1,761 | 0% |
| Inactive | 100 | 33 | 1,749 | 0% |
| Active with Lens | 100 | 52 | 1,761 | 0% |
| Inactive with Lens | 100 | 33.5 | 1,749 | 0% |

All variants had median four discoveries and two unlocked journal toggles.
The clone generates 1,728 shards per day. Differences in total shards come from
encounters. One opening shard makes the first ten-shard pool's clone-only budget
450 seconds.

After seven active days, seed 1 had Resonance dimensional level 11, short of the
Old Trail's level-12 gate. This is a pacing bottleneck, not proof of impossibility.
The Lens did not improve first-day reach rates. No target time for this later
stage is approved; the threshold is preserved pending a balance choice.

## Remaining design and phase-one gaps

- Resolved: story access follows preceding story completion only; numeric stage gates were removed after user clarification.
- Demo act labels and initial summon access do not implement the illustrative
  five-act narrative. A general story/rule-unlock framework is unfinished.
- Fights are action costs and encounter damage, not a separate combat model.
  Equipment affects speed, softcaps and clone output; action/route unlocks,
  upgrades, risk modifiers and slots are unfinished.
- Pity, duplicate conversion, loadout limits and progression targets remain open.
  Cost pools and vitality/event rules are documented provisional simulator policy.
- Automated sweeps, observed first-affordability timelines, CSV/charts and
  exhaustive reachability analysis remain unfinished. No later clone feature
  has an implemented unlock to measure.
- Commands are developer APIs between advances; the player interface still needs
  anchor-only decisions.
- Event logs are unbounded laboratory traces. Production needs bounded telemetry.
- Historical schema-one partial work, real inactive time and clone totals cannot
  be reconstructed. Content changes require explicit migration.
- Shifts, multiplayer, temporary equipment, inventory economies and active clone
  routes remain outside approved scope.

## Engineering references

Python's [pickle documentation](https://docs.python.org/3/library/pickle.html)
documents arbitrary code execution when unpickling untrusted data. Saves now use
JSON; legacy numeric state is interpreted without pickle loading APIs.

The Python Packaging Authority's
[pyproject guide](https://packaging.python.org/en/latest/guides/writing-pyproject-toml/)
describes declaring backend dependencies. The package declares them and was
verified by an isolated build.
