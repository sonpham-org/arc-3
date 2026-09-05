# Kaggle champion Dynamic Slack arms

Status: **built, verified, uploaded, and launched on GCP; the AB1 launch was later invalidated before gameplay**.

> Incident update (2026-09-04): the AB1 launcher omitted the mandatory `ARC3_POST_LEVEL_UNCAPPED_TURNS=0` export, so its fail-closed startup check stopped the runs before gameplay. One arm also encountered a transient Hugging Face disconnect. See `FLASH_NEXT_GCP_RUNBOOK.md` and `FAILED_ATTEMPT_INVALIDATION_20260904.txt`. The bundles and their feature audits remain valid; the AB1 runtime attempts do not.

## Requested experiment cells

Two cells were added to the already-running champion baseline and Stall-140 cells:

| Cell | GCP instance | Run ID | Status at launch verification |
|---|---|---|---|
| Baseline | `arc3-g4-q38-kwbase-ab1` | `g4run-q38-kwbase-ab1-20260904-212054` | RUNNING |
| Stall-140 | `arc3-g4-q38-kwstall140-ab1` | `g4run-q38-kwstall140-ab1-20260904-212053` | RUNNING |
| Baseline + Dynamic Slack | `arc3-g4-q38-kwbase-ds-ab1` | `g4run-q38-kwbase-ds-ab1-20260904-213805` | RUNNING; attempt 1; resource sampler uploaded |
| Stall-140 + Dynamic Slack | `arc3-g4-q38-kwstall-ds-ab1` | `g4run-q38-kwstall-ds-ab1-20260904-213805` | RUNNING; attempt 1; resource sampler uploaded |

No recurring polling automation or regular interval loop was created.

## Locked champion semantics

Both new cells use the exact scored Kaggle 11.44 / ARC-AGI-3 4.84 champion runner:

`gs://cellens-ai-artifacts/arc3-duck/code/baseline/v12-run-kaggle11p44-2fc2be2e8d0db29b23d588413603d5bc5f36096b5e9fe092f9a3a38f3f1d4ee2.py`

The runner applies and asserts the post-unpickle champion settings: 22 workers, 6,480 seconds per game, request logs off, cumulative action cap 14, PLU0, reflection absent, and exactly 25 games. Replay is absent, the persistent top-six GPU curator is enabled, and the suite boundary is 132 minutes.

## Dynamic Slack policy

- Baseline allocation: 6,480 seconds/game.
- On completion, unused assigned seconds return to one shared lane-second bank.
- While games remain queued, 75% of the current bank is shared fairly across every unfinished game, including queued games.
- Per-game extra allocation is capped at 1,200 seconds.
- Once the queue is empty, active games may use their own safe wall-clock headroom up to the absolute suite deadline and the same 1,200-second cap.
- Scheduler decisions are written to `dynamic-slack-scheduler.jsonl`.

The combined cell additionally abandons an unresolved level at 140 actions, preserving a level completion that occurs on action 140, then releases that worker slot normally into the same scheduler.

## Canonical bundles

### Baseline + Dynamic Slack

- GCS: `gs://cellens-ai-artifacts/arc3-duck/tufa-exact/bundle-q38-flashnext-rtdv12-cap14-kaggle11p44-dynamicslack-gcp-r1-20260904.tgz`
- Generation: `1788572011788250`
- Size: 446,494 bytes
- SHA-256: `c70561f5ddab1c791acfbd8f2a3820285816bcae4a4cb1fd1bbf9302d8800ba7`
- MD5 (base64): `pFLbKtwbkojwhgzgasLX2g==`

### Stall-140 + Dynamic Slack

- GCS: `gs://cellens-ai-artifacts/arc3-duck/tufa-exact/bundle-q38-flashnext-rtdv12-cap14-kaggle11p44-stall140-dynamicslack-gcp-r1-20260904.tgz`
- Generation: `1788572017560239`
- Size: 447,067 bytes
- SHA-256: `6e1d8d21b871c3a1bf4efaeed121f0dd5f28a4c66b7af2e8c245547e64467ee6`
- MD5 (base64): `toRAZEU9DU4qZgPu4O+/4g==`

Each release has the exact champion GCP wrapper membership (78 files) and changes only `src/ARC3-Inference/inference/framework/solver.py`.

## Verification

- The Dynamic Slack implementation was AST-compared with the previously proven allocator.
- The Stall-140 implementation was AST-compared with the canonical Stall-only release.
- Every archive member was byte-compared with its audited candidate tree.
- 15 unit tests passed: five on Baseline + Dynamic Slack, five on Dynamic Slack in the combined tree, and five Stall-140/runner-contract tests.
- Both cloud preflights passed.
- Instance metadata confirms the exact bundle, locked runner, 22 workers, 6,480-second base cap, Dynamic Slack `1`, grant fraction `0.75`, max extra `1200`, curator `1`, replay `0`, and reflection `disabled`; only the combined cell has Stall-140 `1`.
- The startup payload includes fail-closed boot checks that unpickle `benchmark_initial.pkl` and assert Dynamic Slack activation; the combined cell also asserts `STALL_ACTION_LIMIT == 140`.

Launcher SHA-256: `ae2dcb36dcb3d1350aeefe75e8afd2f5d8ca86467e9315819c90fcc2f066eb85`.
