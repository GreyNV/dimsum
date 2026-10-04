# P2 asset registry and offline generation verification

## Scope and contract
Owned files: `world/assets.py`, `world/pipeline.py`, `tests/test_world_assets.py`.
No changes to idle logic, shared models/seeds, runtime, rendering, or other packages.

- `AssetRegistry(root=None)` validates adoption, sorts snapshots by ID, and exposes
  the same canonical catalog digest as world generation. Duplicate identical
  registration is idempotent; changed content needs a new ID. Stored records carry
  content digests and use SHA-256 ID filenames (including Windows-safe colon IDs).
- `builtin_assets(width,height)` returns dark_forest and ash_plain assets with
  geometry-qualified IDs, a clear center cross, four aligned exits, player spawn
  metadata and an enemy spawn. Player graphics are absent.
- `GenerationRequest(biome,seed,chunks=1,width=32,height=16,variants=1)` expands
  into chunks*variants deterministic jobs. Maximum 1024 jobs; dimensions match
  model bounds. The requested 24*6 example yields 144 distinct jobs.
- `GenerationProvider.generate(GenerationJob)->str|bytes` supplies asset-schema1
  JSON. `LocalProvider` is deterministic and offline, supporting the two bundled
  biomes. Future providers do not change the runtime.
- `AssetPipeline(root,registry,provider).run(request)` returns a schema1 manifest
  containing request and jobs with id/status/attempts/digest/error. Stable job IDs
  include the full versioned request digest. Repeating a request resumes it;
  accepted jobs never invoke the provider or rewrite accepted asset/stage bytes.
- Provider bytes are staged before parsing, then validated and registered.
  Exceptions, nontext, invalid UTF-8 and oversized output produce bounded rejection
  reports; oversized payloads are deliberately not retained in staging.
- Registry corruption, manifest/catalog mismatch and storage failure raise explicit
  errors. They never silently replace accepted content or fall back to new content.

## Verification ledger
Baseline before P2: shared model/seed tests 7/7 pass (0.386s).
Final focused command: Python -B unittest discovery of test_world_assets.py.
Result: **13/13 pass**, 0.535s. No existing tests modified.

Tests protect:
1. Both biome assets, minimum/default/maximum geometry, clear exit corridors.
2. Malformed, duplicate-key, deep, nonfinite/overflow, oversized and unsafe-cell JSON.
3. Direct registry adoption cannot bypass geometry/glyph validation; immutable copies.
4. Immutable same-ID behavior, sorted digest, disk reload, safe Windows filenames.
5. Tampered digest/geometry/filename/record rejection.
6. Failed atomic rename leaves catalog bytes/memory unchanged and removes temp files.
7. Deterministic local provider and 144-job request expansion.
8. Restart/retry invokes only failed jobs and preserves accepted bytes.
9. Provider exceptions and invalid metadata isolated within a batch.
10. Nontext/oversized payload rejection without registry adoption.
11. Missing accepted registry content causes explicit resume failure.
12. Corrupt manifest IDs rejected before provider execution.
13. Interruption after registration but before accepted manifest save reconciles
    by idempotent registration on retry.

Review performed: inspected all new module source against shared contracts; no
runtime/provider dependency introduced. Public docstrings contain usage examples,
invariants and explicit failure behavior. No network calls or external dependencies.

## Limitations and follow-up
Storage is single-writer. Atomic replacement + file fsync is verified using injected
rename failure; whole-machine power loss/directory-fsync durability is not claimed.
Real model/API providers and cost/rate-limit scheduling are out of scope.
Malformed raw payloads are retained only within the 2 MiB per-asset size bound.
New provider algorithms need a new request seed to create new immutable asset IDs.
The lead owns full-suite regression, CLI integration and runtime separation checks.
