# Kaggle champion + Stall-140 canonical release

Status: **built, verified, and uploaded**. No GCP evaluation was launched by this operation.

## Provenance

This release was made from the immutable champion artifact, not reconstructed from the current repository:

- Champion source: `bundle-q38-flashnext-rtdv12-cap14-reflection-v3.tgz`
  - SHA-256: `04a25a5b6cc8a22891fcb81ca26a7d56626f0d51ecfaef7ed0d5153d868f2d62`
- Exact GCP wrapper: `bundle-q38-flashnext-rtdv12-cap14-kaggle-winner-gcp.tgz`
  - SHA-256: `2ed1e758d07880fb4a9c764e57b4943e20c676cfdc881ce8bc1d8f2bcb1a5bd2`
  - The wrapper differs from the champion source only by adding `pre_harness_warmup.py`.
  - Warmup SHA-256: `758453bcbf5776c27705e9bf8ad8a174db4980e62a75d5db7c0e26d908d09156`

The bundle's serialized benchmark contains construction-time values of 28 workers and 7,920 seconds per game. The scored notebook changed the live solver after unpickling. Therefore this release requires the locked runner:

`v12-run-kaggle11p44-2fc2be2e8d0db29b23d588413603d5bc5f36096b5e9fe092f9a3a38f3f1d4ee2.py`

Runner SHA-256: `2fc2be2e8d0db29b23d588413603d5bc5f36096b5e9fe092f9a3a38f3f1d4ee2`

After unpickling, that runner sets and asserts 22 workers, 6,480 seconds per game, request logs off, action cap 14, PLU0, reflection absent, and exactly 25 games. The solver itself contains no replacement runtime/concurrency override.

## Sole gameplay change

Exact GCP wrapper → release tree:

- Added files: none
- Removed files: none
- Changed files: `src/ARC3-Inference/inference/framework/solver.py`

The changed solver adds only the Stall-140 mechanism:

- Count actions on the current unresolved level using the framework's native `actions_per_level` counter.
- At 140 actions without completing that level, stop the game and allow normal finalization/reallocation.
- If action 140 completes the level, keep the win because the level counter advances before the stop check.
- Emit one `<game>_p<pass>_stall_guard.json` audit event.

No replay, dynamic slack, compaction, reflection, or solver-side runtime restoration was added.

## Verification

`verify_release.py` passed fail-closed checks for:

- all source, wrapper, runner, and release hashes;
- the exact source → wrapper and wrapper → release tree deltas;
- all 78 release archive members matching the audited candidate tree byte-for-byte;
- five Stall-140 and runner-contract unit tests.

## Canonical release

- GCS: `gs://cellens-ai-artifacts/arc3-duck/tufa-exact/bundle-q38-flashnext-rtdv12-cap14-kaggle11p44-stall140-only-gcp-r1-20260904.tgz`
- Generation: `1788570368316748`
- Size: `444107` bytes
- SHA-256: `b38dcb598f27f5031a32b014f0bed7e3dbf2c80ff710a758252579371aa952eb`
- MD5 (base64): `52oe1haOORcOAMZyPrgEvg==`

The three exploratory R1/R2/runtime-fix objects were marked `superseded` and point to this canonical object.
