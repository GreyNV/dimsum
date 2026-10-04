# P1 ? shared contracts and seeds
Implemented frozen cells/keys/specs/assets/chunks, strict schema1 parsing, aligned
exit and reachability checks, canonical JSON and SHA-256 child seeds.
Focused baseline: 7 tests passed. Regression protection: typed coordinates, process
hash salts, unsafe glyph/control characters, colors, mutable grids, inaccessible
spawns/exits, unknown/future schema. No provider, browser or manual gameplay checks.
Seed hash version is explicit; changing it requires a new generator/save contract.

Final count 8: added malformed collection/tag/biome and boolean-dimension coverage;
seed service now has a fixed numeric vector as well as cross-process equality.
