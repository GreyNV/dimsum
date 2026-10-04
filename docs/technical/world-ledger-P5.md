# P5/P6 verification ledger: integration and handoff
Renderer tests 3; integration tests 8; combined final suite 143/143.
Evidence: .codex/artifacts/world-verification/tests.txt,test-evidence.json,
smoke-evidence.json and generated-world-frame.txt/.ansi.

Tests protect six-layer precedence, transparency, both colors, viewport clamping,
pure rendering/map reads, offline provider independence, real chunk/player/attack
composition, exact active-frame damage, save continuation, discrete scripted input,
CLI generation/retry and terminal simulation equivalence at3 vs120 display FPS.

Manual verification: Windows PTY rendered truecolor environment/entities/player/
minimap, accepted D/Space, changed facing east, and Q exited at18660ms simulation.
Console cursor/mode cleanup executed. No GUI/browser surface was implemented.
Scripted packaged demo damages the expected adjacent target. Full144-template
64x32 generation took19.710s locally; rerun8.145s, accepted bytes identical.
These are observations, not performance thresholds. Runtime used9 resident chunks;
render/attack did not generate any more. Original idle seed 19/5000s state hash
matches the baseline0.5.0 wheel exactly.

Regressions discovered and fixed: malformed biome/tag input exception, identifier
overflow in heavily-authored encounter catalogs, long target IDs, ignored anchors,
unsafe mid-motion/mid-attack timing changes, impossible save hit/target metadata.
Duplicate spawn regression removed, retaining the test covering both suffix styles.

Known untested behavior: real external AI services, POSIX physical keyboard,
terminal resize/power-loss, distributed writers. They are outside the DoD.
No existing source regression:72 original tests pass; isolated wheel build succeeds.
The earlier non-isolated build error was environment-only (missing bdist_wheel).
