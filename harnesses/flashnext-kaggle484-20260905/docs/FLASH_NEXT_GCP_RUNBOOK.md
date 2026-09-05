# ARC-3 Flash-Next GCP runbook

Last updated: 2026-09-05 14:49 EDT

This is the fail-closed operational record for reproducing the Kaggle champion and its ARC Foundation 25 GCP experiments. Read this before launching or modifying any Flash-Next run.

## Ground truth

- The Kaggle 11.44 / ARC-AGI-3 4.84 champion uses **Flash-Next**.
- Model: `RadixArk/Qwen3.8-Flash-Next-NVFP4`
- Immutable revision: `7b719225242aacd3dbd3f9407468c2ee9a9d2594`
- Checkpoint size recorded by the proven launcher: `135253622894` bytes (about 135.3 GB decimal / 126.0 GiB).
- Container: `vllm/vllm-openai@sha256:fc120ece0a388cc0aa1caad4a9f1cd92113484ab7ec2fd0efadd62585be05bf8`
- Historical GCP runs, including direct-best22 R3, downloaded this pinned revision from Hugging Face. That was valid and produced successful runs; Hugging Face was a transport dependency, not a different model.
- Proven ARC Foundation 25 GCP direct-best22 R3 final score: `7.651224130951845` mean, 25/25 games reported, 36 levels, minute 132.
- Do not treat an approximate recollection of a 12-point score as verified. Locate its immutable `score-final.json` before naming it as the record.

## Canonical champion contract

- Bundle: `gs://cellens-ai-artifacts/arc3-duck/tufa-exact/bundle-q38-flashnext-rtdv12-cap14-kaggle-winner-gcp.tgz`
- Bundle MD5 (base64): `BAoDe9r+9Jvhc57/IBQV7A==`
- Runner: `gs://cellens-ai-artifacts/arc3-duck/code/baseline/v12-run-kaggle11p44-2fc2be2e8d0db29b23d588413603d5bc5f36096b5e9fe092f9a3a38f3f1d4ee2.py`
- Runner SHA-256: `2fc2be2e8d0db29b23d588413603d5bc5f36096b5e9fe092f9a3a38f3f1d4ee2`
- Games: ARC Foundation 25, one pass.
- Workers: 22.
- Base runtime: 6,480 seconds per game.
- Suite boundary: 132 minutes.
- Cumulative action cap: 14.
- Post-level uncapped turns: 0.
- Replay: disabled.
- Same-context reflection: absent/disabled in baseline.
- GPU world-model curator: enabled, top six.
- Serving: Best22, ModelOpt FP4, native FP8 CPU PLE with the pinned compatibility patch, prefix caching on, MTP off.

Every environment variable required by the runner must be exported even when its value is zero. In particular, always export:

```bash
export ARC3_POST_LEVEL_UNCAPPED_TURNS=0
```

The startup self-test must unpickle the benchmark and assert the complete live contract before gameplay.

## Durable GCS model mirror

Future experiments must use the verified GCS mirror after its `DONE` marker and manifest agree. Do not launch from an incomplete prefix.

- Prefix: `gs://cellens-ai-artifacts/arc3-duck/models/qwen3.8-flash-next-nvfp4-radixark/7b719225242aacd3dbd3f9407468c2ee9a9d2594/`
- State: `_mirror/STATE.json`
- Completion gate: `_mirror/DONE`
- Integrity manifest: `_mirror/MANIFEST.json`
- Failure marker: `_mirror/FAILED`
- Mirror worker: `arc3-flashnext-gcs-mirror-20260904-2215`, zone `us-central1-b`; completed and self-terminated.
- Worker sizing: `e2-highmem-8` (8 vCPU, 64 GB RAM) with a 400 GB `pd-balanced` boot disk.
- Downloader: four workers with `HF_XET_HIGH_PERFORMANCE=0`; retries are resumable.
- The worker uploads every repository file, records SHA-256, GCS generation, and CRC32C for each object, writes `DONE`, and shuts itself down.
- Verified completion at `2026-09-05T02:45:32.087058+00:00`: 419 model files and `135253622894` model bytes. `DONE`, `STATE.json`, and `MANIFEST.json` agree on revision, file count, and byte count.

Sizing is evidence-based. An `e2-standard-8` with 32 GB RAM OOM-killed a 12-worker high-performance Xet download at a measured 30.6 GB peak. Do not use that configuration again. The proven GPU experiment disks are also 400 GB.

The reusable Ubuntu 24.04 bootstrap package cache is at `gs://cellens-ai-artifacts/arc3-duck/bootstrap-cache/ubuntu2404-ab4/`. It was assembled from successfully booted AB4 nodes after two direct instances received abnormally slow Ubuntu-mirror routes. The launcher hydrates `/var/cache/apt/archives/` from this prefix before apt computes its download queue. GCS verifies object checksums during transfer, and apt independently verifies package contents against signed Ubuntu package metadata. This cache is a transport optimization only; it does not modify the model, container, bundle, runner, or harness settings.

## Golden runtime acceleration

The canonical reusable image is `arc3-flashnext-7b719225-runtime-v1` in family `arc3-flashnext-runtime`, immutable image ID `8419973307372247581`. It was created from the stopped disk of successful exact-baseline run `g4run-q38-kwbase-r2e1-20260905-072058`, after that run had fully SHA-256-verified the GCS mirror, passed model smoke and the exact champion self-test, completed 25/25 games, and emitted a final score of `13.743310956367305`.

Use `-GoldenRuntimeImage arc3-flashnext-7b719225-runtime-v1` with `launch_champion_stall_ab.ps1`. The launcher fails closed on any image name, family, status, source-disk, or image-ID drift. At boot it clears all prior gameplay, bundle, curator, and telemetry state, while preserving the immutable model payload, Docker layers, OS packages, Python environments, and compilation caches. It skips apt refresh/install, the 135 GB GCS model transfer, and the duplicate host vLLM/PyTorch installation. It still verifies the live GCS `DONE` and manifest identity, validates all 419 local file sizes against that manifest, checks the pinned container and PLE patch, runs live text/vision/22-request capacity smoke, and executes the exact harness self-test before gameplay.

The first infrastructure-only technical baseline on this path is `g4run-q38-kwbase-golden-v1-r1-20260905-103620` in `us-east5-a`. Its behavioral contract is byte-identical to the exact recovered champion: 32,768 context, fixed-30 history, cap 14, PLU 0, no replay, no reflection, top-six curator, 22 workers. It passed all gates and emitted its first score at gameplay minute 1. At minute 8 it reported mean `0.4`, 4 positive games, 4 levels, 257 actions, 22 sidecars, and zero observer errors.

Measured readiness comparison:

| Exact baseline path | Startup script to gameplay | VM creation to gameplay |
|---|---:|---:|
| Cold GCS/bootstrap source (`kwbase-r2e1`) | 12m 27s | 13m 06s |
| Golden runtime v1 (`kwbase-golden-v1-r1`) | 6m 42s | 7m 56s |

The golden path removes about 5m45s (46%) from script-to-gameplay readiness. Its remaining dominant cost is the unavoidable Flash-Next weight load and PLE offload; first-read image-backed disk hydration made this load 165 seconds versus 93 seconds on the already hydrated cold-path disk.

Before any experiment launch, verify:

1. `DONE.revision == MANIFEST.revision == 7b719225...`.
2. `DONE.file_count == MANIFEST.file_count` and the count is at least 400.
3. `DONE.total_bytes == MANIFEST.total_bytes` and the total is greater than 130 GB.
4. GCS transfer checksum validation succeeds.
5. Cold-path restores must match every manifest size and SHA-256. Golden-path launches instead pin the immutable image ID built from a fully SHA-256-verified source disk and revalidate every local file size before vLLM startup.

## AB4/AB5 experiment matrix launched from the verified mirror

Fresh AB4 resources were launched on 2026-09-05 at approximately 00:00 EDT. Do not restart or score the invalid AB1, AB2, or AB3 attempts.

| Arm | Sole intended delta | Run ID |
|---|---|---|
| Baseline | None | `g4run-q38-kwbase-ab5-20260905-005421` |
| Stall-140 | Abandon a game at 140 actions on one unresolved level | `g4run-q38-kwstall140-ab4-20260904-235921` |
| Baseline + Dynamic Slack | Reallocate returned lane-seconds with the audited allocator | `g4run-q38-kwbase-ds-ab4-20260904-235925` |
| Stall-140 + Dynamic Slack | Both audited mechanisms | `g4run-q38-kwstall-ds-ab4-20260904-235923` |
| Baseline + Reflection V3 | Reflection V3 only | `g4run-q38-kwbase-refv3-ab4-20260904-235925` |
| Baseline + Refinement | Routed medium draft, independent medium critic, xhigh revision on hard turns only | `g4run-q38-kwbase-refine-ab4-20260904-235923` |

All six launch-state records identify `gcs_verified_mirror`, the pinned revision, 419 files, `135253622894` bytes, 22 workers, a 132-minute boundary, cumulative cap 14, and post-level uncapped turns 0. Their startup scripts overlay only `/opt/arc3/bundle/src/ARC3-Inference/inference/` onto the pinned deployment project, remove stale `.pyc` files, retain the deployment Makefile/lock/config, and assert that the imported `tool_agent.py` is byte-identical to the audited bundle copy.

Live validation at approximately 00:14 EDT established valid gameplay for four arms: Baseline + Dynamic Slack, Stall-140 + Dynamic Slack, Baseline + Reflection V3, and Baseline + Refinement. Each restored and SHA-256-verified the full mirror, loaded Flash-Next, passed the 22-stream and 25-stream capacity warmups, passed its arm-specific self-test, and launched the v12 runner with 22 sidecars. Their first score-observer artifacts appeared at gameplay minute 1. At gameplay minutes 3-4 the provisional means were `0.1111111111111111`, `0.2222222222222222`, `0.0`, and `0.1111111111111111`, respectively; these are early live observations, not final results. Direct Baseline and direct Stall-140 remained in unusually slow but byte-progressing Ubuntu package downloads and had not started gameplay at this checkpoint.

By approximately 01:09 EDT, all six intended arms were valid and playing. Direct Stall-140 AB4 and replacement Direct Baseline AB5 each restored and verified the full GCS mirror, passed both capacity-smoke stages, passed the exact arm self-test, and launched the v12 runner. Direct Baseline AB4 never reached model restore or gameplay: a clean reboot intended to make apt reconsider a newly hydrated cache triggered the direct-instance fail-closed shutdown trap. It is `TERMINATED`, has zero games started, and must not be scored. AB5 is the canonical direct-baseline run.

Synchronized live score snapshot around 01:07-01:09 EDT (not final):

| Arm | Gameplay minute | Mean score | Levels | Actions | Games reported |
|---|---:|---:|---:|---:|---:|
| Baseline AB5 | 1 | 0.0 | 0 | 10 | 22 |
| Stall-140 | 30 | 2.409001343826906 | 17 | 961 | 22 |
| Baseline + Dynamic Slack | 54 | 4.517883740335485 | 27 | 1512 | 22 |
| Stall-140 + Dynamic Slack | 54 | 6.341365939119033 | 32 | 1377 | 22 |
| Baseline + Reflection V3 | 54 | 3.062752936290201 | 22 | 1381 | 22 |
| Baseline + Refinement | 54 | 3.205741796751568 | 22 | 1346 | 22 |

Every row had 22 sidecars and zero observer read errors. The remaining three games are queued behind the 22 active workers. Compare final results only after the 132-minute suite boundary and `score-final.json`.

Immutable final results from `score-final.json` (25/25 games, gameplay minute 132, zero observer read errors for every arm):

| Arm | Mean score | Median | Levels | Actions | Positive games |
|---|---:|---:|---:|---:|---:|
| Baseline AB5 | **13.308641549799873** | 4.761904761904762 | 50 | 3377 | 23 |
| Stall-140 | 11.089175650662195 | 4.761904761904762 | 46 | 3725 | 21 |
| Baseline + Dynamic Slack | 9.264429633920487 | 7.164622081519589 | 45 | 4643 | 23 |
| Stall-140 + Dynamic Slack | 11.823916872637993 | 4.761904761904762 | 53 | 3526 | 22 |
| Baseline + Reflection V3 | 7.23349071599174 | 4.761904761904762 | 40 | 3155 | 22 |
| Baseline + Refinement | 4.89100475538213 | 3.0932756261337238 | 30 | 3136 | 21 |

The exact baseline recovered and exceeded the previously remembered 12-point result. In this single replicate, neither Stall-140 nor Dynamic Slack beat the baseline. Stall-140 + Dynamic Slack was the strongest modification and produced the most completed levels, but its mean was 1.48472467716188 below baseline.

## Doubled-replicate launch matrix

One fresh replica per arm was launched on 2026-09-05. The RTX PRO 6000 spot-GPU quota is regional, not per-zone: six originals in `us-central1-b` plus two replicas in `us-central1-f` consumed the region's quota of eight. Attempts in `us-east4-b` encountered physical capacity exhaustion, so the remaining four were placed in `us-east5`.

| Arm | Zone | Replica run ID |
|---|---|---|
| Baseline | `us-east5-a` | `g4run-q38-kwbase-r2e1-20260905-072058` |
| Stall-140 | `us-east5-a` | `g4run-q38-kwstall140-r2e1-20260905-072058` |
| Baseline + Dynamic Slack | `us-central1-f` | `g4run-q38-kwbase-ds-r2-20260905-015136` |
| Stall-140 + Dynamic Slack | `us-central1-f` | `g4run-q38-kwstall-ds-r2-20260905-015136` |
| Baseline + Reflection V3 | `us-east5-b` | `g4run-q38-kwbase-refv3-r2e1-20260905-072058` |
| Baseline + Refinement | `us-east5-b` | `g4run-q38-kwbase-refine-r2e1-20260905-072057` |

Second-replica snapshot at approximately 09:28 EDT. The Dynamic Slack rows are final; the other four are provisional. `Positive` means score greater than zero, not a terminally solved game.

| Arm | Gameplay minute | Mean score | Games reported | Positive | Levels | Actions | State |
|---|---:|---:|---:|---:|---:|---:|---|
| Baseline | 113 | 9.314739527795876 | 25 | 22 | 44 | 2,809 | provisional |
| Stall-140 | 113 | 9.821259451278578 | 25 | 23 | 46 | 3,085 | provisional |
| Baseline + Dynamic Slack | 132 | 9.638018503788313 | 25 | 23 | 47 | 3,531 | final |
| Stall-140 + Dynamic Slack | 132 | 10.349331059233364 | 25 | 23 | 48 | 3,571 | final |
| Baseline + Reflection V3 | 113 | 5.449668468430449 | 25 | 22 | 33 | 2,574 | provisional |
| Baseline + Refinement | 113 | 6.353742311601857 | 25 | 20 | 36 | 3,807 | provisional |

The observer's historical `wins` field is not the authoritative terminal-solve count. Derive full games solved from immutable per-game benchmark artifacts after finalization. The seed-1 audit found one full solve for baseline and zero for every modified arm; see `STALL140_REFINEMENT_AUDIT_20260905.md`.

## Context/history sweep launched 2026-09-05

These five arms preserve the recovered Flash-Next Kaggle-winner harness and change only model context capacity and the fixed number of retained assistant turns. Bundle `bundle-q38-flashnext-rtdv12-cap14-kaggle11p44-context-sweep-r1-20260905.tgz` differs from the canonical baseline in one source file and makes the previous fixed value of 30 environment-configurable. Its SHA-256 is `a51dcddc23ceebb2fd45d7aaa81c4ef5167c5bdc545a93b3ced564f6a73b4363`; GCS MD5 is `E0eeWyhIHHgRyTMGORg/cg==`.

| Context / fixed history | Zone | Canonical run ID | Startup SHA-256 |
|---|---|---|---|
| 20,480 / 20 | `us-central1-c` | `g4run-q38-kwctx20k-f20-r2-20260905-085000` | `11C99C551C05904F102B5C849D4A3125B474034A6A83E46A987E6629FB7F3F2E` |
| 49,152 / 30 | `us-central1-c` | `g4run-q38-kwctx48k-f30-r2-20260905-085002` | `F9D9BD09C753DCE481D281D70991E7D1A7C2116C1A5DBFC8A8971971CB70D701` |
| 49,152 / 45 | `us-east5-c` | `g4run-q38-kwctx48k-f45-r2-20260905-085003` | `05AFFF08DE95BC5B41A09C750E53FE7767F0BB8CB166C0A610D35872BAC73FA2` |
| 61,440 / 30 | `us-central1-b` | `g4run-q38-kwctx60k-f30-r3-20260905-091227` | `E0F40BB0D0473745A25E63338798B0DFBE017442A5A2EA625FB2359974632E85` |
| 49,152 / 60 | `us-central1-f` | `g4run-q38-kwctx48k-f60-r5-20260905-085402` | `82DB713A74B82B83245BDA85D175F446942DB985AC8A6D1340E3E76075FE0602` |

The 20,480/20, 49,152/30, and 49,152/45 arms were admitted under their `r2` identities. The 49,152/60 arm encountered live stockout in all three `europe-west4` zones, then succeeded as `r5` in `us-central1-f`; its stockout-only `r1`, `r3`, and `r4` records contain zero gameplay. The first 61,440/30 VM (`r2`, `us-east5-c`) was Spot-preempted after model smoke but before its self-test and gameplay; its canonical replacement is `r3` above. All of those explicitly invalid attempts must remain unscored. Every canonical arm restored and manifest-verified all 419 model files, passed text/vision and 22-request capacity smoke, passed the two-stage 22/25-stream pre-harness warmup, printed its exact context/history self-test marker, and emitted a zero-error score artifact.

Initial synchronized snapshot at approximately 09:28 EDT. These scores are extremely early and not cross-arm comparable because the 61,440/30 replacement started later.

| Context / fixed history | Gameplay minute | Mean score | Games reported | Positive | Levels | Actions |
|---|---:|---:|---:|---:|---:|---:|
| 20,480 / 20 | 23 | 1.8198635889293329 | 22 | 12 | 14 | 652 |
| 49,152 / 30 | 23 | 1.5943322109988776 | 22 | 11 | 12 | 595 |
| 49,152 / 45 | 24 | 2.035439964433501 | 22 | 12 | 14 | 496 |
| 61,440 / 30 | 1 | 0.0 | 22 | 0 | 0 | 8 |
| 49,152 / 60 | 18 | 1.2036647040248147 | 22 | 9 | 10 | 502 |

### Context sweep second replicas

One fresh replica of every context/history arm was launched on 2026-09-05 around 09:39-09:42 EDT. These reuse the same audited context-sweep bundle, runner, GCS model revision, serving profile, worker count, time budget, action cap, and startup hashes as their matched first runs.

| Context / fixed history | Zone | Replica run ID |
|---|---|---|
| 20,480 / 20 | `us-central1-f` | `g4run-q38-kwctx20k-f20-rep2a1-20260905-093915` |
| 49,152 / 30 | `us-central1-b` | `g4run-q38-kwctx48k-f30-rep2a1-20260905-093915` |
| 49,152 / 45 | `us-east5-b` | `g4run-q38-kwctx48k-f45-rep2a2-20260905-094125` |
| 61,440 / 30 | `us-central1-c` | `g4run-q38-kwctx60k-f30-rep2a2-20260905-095049` |
| 49,152 / 60 | `us-east4-c` | `g4run-q38-kwctx48k-f60-rep2a1-20260905-093915` |

The first 49,152/45 replica create attempt (`rep2a1`, `us-east5-c`) encountered physical stockout and created no gameplay; `rep2a2` above is canonical. The first 61,440/30 replica (`rep2a1`, `us-east5-a`) failed closed during vLLM startup because `pynvml.nvmlInit()` returned a transient `NVMLError_Unknown`; it terminated before smoke/self-test/gameplay and must remain unscored. Its `rep2a2` replacement above passed the failed NVML gate and is canonical. At replacement admission the active regional counts remained below the eight-GPU quota. By final verification the running G4 counts were 7 in `us-central1`, 1 in `us-east5`, 1 in `us-east4`, and 1 unrelated run in `europe-west4`. Do not score a replica until its mirror verification, capacity smokes, exact context self-test, and score-observer artifact are present.

All five canonical replicas passed model smoke, emitted their exact context/history self-test marker, and began scoring. First captured score snapshots:

| Context / fixed history | Minute | Mean score | Games | Positive games | Levels | Actions |
|---|---:|---:|---:|---:|---:|---:|
| 20,480 / 20 | 12 | 0.7137804141 | 22 | 7 | 7 | 424 |
| 49,152 / 30 | 13 | 0.7739472649 | 22 | 7 | 7 | 408 |
| 49,152 / 45 | 10 | 0.5315972222 | 22 | 5 | 5 | 250 |
| 61,440 / 30 | 2 | 0.0 | 22 | 0 | 0 | 35 |
| 49,152 / 60 | 10 | 0.5960034014 | 22 | 7 | 7 | 351 |

Use `launch_champion_stall_ab.ps1`. It must fail closed if the GCS mirror is incomplete, the model revision drifts, a bundle/runner hash drifts, PLU0 is missing, or any arm activates an unintended feature.

## AB1 incident record

All six AB1 attempts are invalid and produced no gameplay score.

- Baseline, Stall-140, and Stall-140 + Dynamic Slack reached the pre-game champion self-test and failed because the launcher omitted `ARC3_POST_LEVEL_UNCAPPED_TURNS=0`.
- Baseline + Dynamic Slack encountered a transient Hugging Face disconnect during model download.
- Reflection V3 and Refinement were stopped before gameplay and carried the same missing-export defect.
- All six instances were terminated around 22:00 EDT on 2026-09-04.
- Never report their dashboard zero as a gameplay result. Correct wording: **no valid score; zero games started**.

## AB2 incident record

All six AB2 attempts are also invalid and produced no gameplay score.

- Five arms restored and SHA-256-verified all 419 model files, loaded Flash-Next, and passed both capacity-smoke stages.
- They then failed a new pre-game self-test whose final assertion incorrectly required `tool_agent.__file__` to live under the bundle extraction directory, while `make install-a108` imported it from the pinned base-runtime project directory.
- More importantly, the same path mismatch revealed that candidate source files were present in the bundle but had not been activated in the runtime project. Later launches must overlay the audited gameplay package and verify byte identity after import.
- The lagging AB2 baseline and its temporary replacement were stopped after the common defect was established. All other AB2 resources self-terminated through the cleanup path.
- Never report AB2 as a gameplay result. Correct wording: **pre-game validation failure; zero games started**.

## AB3 incident record

All six AB3 attempts are invalid and produced no gameplay score.

- The first three arms to reach the gate restored and verified the model, loaded Flash-Next, and passed 22-way capacity smoke.
- Whole-project bundle activation then overwrote the deployment-specific Makefile with the Kaggle bundle Makefile, which has no `install-a108` target. Startup failed before environment installation, self-test, or gameplay.
- The three slower AB3 arms were stopped once the shared defect was proven; the three leaders self-terminated through cleanup.
- AB4 narrows activation to the `inference/` gameplay package, deletes stale `.pyc` files, and preserves the pinned deployment Makefile, lockfile, and `tufa0.json`.
- Never report AB3 as a gameplay result. Correct wording: **pre-game deployment failure; zero games started**.

## Visual-transition four-arm matrix launched 2026-09-05

The visual-transition release is derived from the immutable recovered champion
bundle and preserves 32,768 context, fixed-30 retained assistant turns, 22
workers, 6,480 seconds per game, the 132-minute suite boundary, cap 14, PLU0,
no replay, no reflection, and the persistent top-six curator.

- Local bundle: `bundle-q38-flashnext-rtdv12-cap14-kaggle11p44-visual-transition-matrix-gcp-r1-20260905.tgz`
- SHA-256: `f56321bcff7f904adf573811119151996f4c161e944a5bf2a8da06c0346e70d6`
- MD5 (base64): `LQXQM19V7XBtBjPIE3FC9A==`
- Source champion SHA-256: `2ed1e758d07880fb4a9c764e57b4943e20c676cfdc881ce8bc1d8f2bcb1a5bd2`
- Structural audit: exact 78-file source membership; only both manifests,
  `prompts.py`, `tool_agent.py`, and `solver.py` differ.

`ARC3_VISUAL_TRANSITION_MODE` defines the four controlled arms:

| Mode | Transition metadata | Raw sampled images | Legacy ASCII/region tools |
|---|---|---|---|
| `control` | No | No | Retained; prompt bytes equal champion |
| `metadata` | Yes | No | Retained |
| `additive` | Yes | Yes | Retained |
| `replace` | Yes | Yes | Suppressed model-side |

For `n` returned animation frames, sample
`k=min(n,8,max(2,ceil(log2(n))))`, pin returned frames zero and `n-1`, and
uniformly spread the interior samples. The preceding user observation contains
the pre-action grid. The action-bearing assistant/tool exchange comes next.
The labeled sampled frames and settled current-grid image are then prepended to
the next analyzer user message, immediately before the next model reasoning.
They are observations in the visible conversation trace, never injected inside
hidden reasoning.

The meaningful-animation batch pause remains active in every mode. Context
bookkeeping assigns 72 tokens per transition PNG (64 visual tokens plus a small
wrapper allowance) instead of treating PNG base64 as language text. Six focused
unit tests pass, all four mode guards pass, and `control` reproduces the exact
champion prompt/tool-description hash.

The release was uploaded create-only to the canonical GCS path at generation
`1788625922940666`; the remote MD5 is `LQXQM19V7XBtBjPIE3FC9A==`.

| Mode | Final zone | Run ID | Startup SHA-256 |
|---|---|---|---|
| `control` | `us-east5-a` | `g4run-q38-kwvtrans-ctl-r1-20260905-124517` | `BA60B1424CB8539E4B0CC60C402CDD3DA51BABB5E46ECA52F0C7600144EF9AA7` |
| `metadata` | `us-east4-c` | `g4run-q38-kwvtrans-meta-r1-20260905-124722` | `F3EAD9375A63DB843053C07EBA9622664A0899D24BC3CCAE2D53C0F62FC10574` |
| `additive` | `us-central1-b` | `g4run-q38-kwvtrans-add-r1-20260905-144312` | `C85D8CCDFB01B72BE137322401730E9DAEA1E9F2EFED7A4D77132C9A0B068709` |
| `replace` | `us-central1-c` | `g4run-q38-kwvtrans-repl-r1-20260905-143416` | `85ADCFA4025BDE1871DB35E992CA16BCB6452F659A8E97994F55E977E62A7101` |

The initial `replace` request in `us-central1-f` and three `additive` requests
across `europe-west4-b`, `-a`, then `-b` ended in explicit G4 stockout before
an instance existed. Their local state records are retained and must not be
scored. The table above contains the only canonical live identities.

First bounded snapshot at `2026-09-05T18:48Z`: `control` minute 114 mean
`7.229691307296224` (25 games, 41 levels), `metadata` minute 113 mean
`10.467864664757606` (25 games, 48 levels), and `replace` minute 5 mean
`0.4126984126984127` (22 games, 3 levels), all with zero observer errors.
`additive` was still in startup. These are provisional and not synchronized.

Final 132-minute results for the completed matched pair: `control` mean
`9.340802418407335`, median `3.731715744615503`, 45 levels, 3,035 actions,
25 games, and 23 positive games; `metadata` mean `12.578975775868717`, median
`8.1640625`, 52 levels, 3,180 actions, 25 games, and 23 positive games.
Metadata therefore gained `3.238173357461382` mean-score points and seven
levels in this seed. These completed results are still single-replica evidence;
fresh R2 replicas were launched afterward but have not yet scored the effect.
The `additive` and `replace` R1 arms remain
separate later-starting runs and must not be treated as synchronized with this
completed pair.

The full visual-transition matrix was doubled on 2026-09-05:

| Mode | R2 zone | R2 run ID | Startup SHA-256 |
|---|---|---|---|
| `control` | `us-east5-a` | `g4run-q38-kwvtrans-ctl-r2-20260905-162436` | `154F8F674EC13972ACA6099F4C472CA29B671A2695ABF8EB906FE209370554D9` |
| `metadata` | `us-east5-b` | `g4run-q38-kwvtrans-meta-r2a1-20260905-162918` | `12C8F84C77932DD4D00FF9B19A3B6EC3E2C3914A6BE9A5103E6D573B2E94BC56` |
| `additive` | `us-central1-b` | `g4run-q38-kwvtrans-add-r2-20260905-163026` | `567D57E7BB0FC3875BD1DD38E581A5B8B0554E74FBEFFB03237006526602E8F2` |
| `replace` | `us-east5-a` | `g4run-q38-kwvtrans-repl-r2a1-20260905-163536` | `8C705830E407B9205DF4CEEB31BBDEDE757CA4BD74785FD7C7D25A45E3C07B27` |

All four R2 instances were confirmed `RUNNING`. The first metadata R2 request
in `us-east5-c` ended in explicit G4 stockout before instance creation; its
canonical relocation is `r2a1` in `us-east5-b`. The first replace R2 request
in `us-central1-c` exceeded the regional Hyperdisk Balanced storage quota
before instance creation; its canonical relocation is `r2a1` in `us-east5-a`.
Neither failed provisioning request is scoreable. No recurring polling loop
was created.

## Metadata-toolkit crossover launched 2026-09-05

Two crossover arms combine the strongest animation treatment with the optional
CPU toolkit. Both retain metadata-only transition evidence, legacy ASCII
storyboards and region inspection, the bounded toolkit cache, persistent
helpers, and the exact champion scheduler. Raw transition PNGs remain off.
The only difference between the arms is the advisory budget reminder.

| Arm | Bundle | SHA-256 | MD5 (base64) |
|---|---|---|---|
| Metadata + Toolkit | `arc3-kaggle484-metadata-toolkit-20260905.tgz` | `01c73733fdfc999182369da530542b1212e50007d5d8d3505f384f61cce9cfb2` | `1yUmaMz5WWLF5qw2YxOWQw==` |
| Metadata + Toolkit + Reminder | `arc3-kaggle484-metadata-toolkit-reminder-20260905.tgz` | `45526064bf9adb073e9d4fc1f0575d0dda4aa9eb158e102bbb7d4545144b3d8a` | `+0SSHTax7cJIn7e/g5YhLQ==` |

The bundles were uploaded create-only to GCS generations `1788641325201657`
and `1788641334047878`. Validation passed compileall for both sources, the
136-test toolkit suite for both variants, six visual-transition tests, 11
reminder unit tests, explicit metadata/toolkit/reminder activation smokes, and
both launcher cloud preflights.

| Arm | Zone | Run ID | Startup SHA-256 |
|---|---|---|---|
| Metadata + Toolkit | `us-east4-c` | `g4run-q38-kwvmeta-tool-r1-20260905-165130` | `84780C4DCF1EFBAC4DCC21F23D1E8C84D1A8B732B280DFBE704CAA3D8365CEB4` |
| Metadata + Toolkit + Reminder | `us-east4-c` | `g4run-q38-kwvmeta-comb-r1-20260905-165238` | `9101732D6F6005115EE7630AD7137B8C0261811F75380007F264A9E808620DB3` |

Both direct Spot G4 instances were confirmed `RUNNING`. Both passed the golden
image attestation, 22-request capacity smoke, harness import check, visual
metadata activation self-test, and their arm-specific toolkit activation
self-test. The Reminder arm's first vLLM process encountered a transient
`cudaErrorNotPermitted` during CUDA-graph warm-up; the launcher's same-settings
retry recovered and completed every startup gate. They preserve
Flash-Next revision `7b719225242aacd3dbd3f9407468c2ee9a9d2594`, context
32,768, fixed-30 history, 22 workers, 6,480 seconds per game, 132 suite
minutes, cap 14, PLU0, no replay/reflection/refinement/Dynamic Slack, and the
persistent top-six curator. Initial bounded score snapshot: Metadata + Toolkit
minute 5, mean `0.2222222222222222`, two levels, 117 actions; Reminder arm
minute 1, mean `0.0`, zero levels, nine actions. Both observers reported zero read errors. No
recurring polling loop was created.

## Exact-baseline six-hour reasoning-limit replicas

These two arms are the recovered champion with one resource-only delta:
`max_runtime_s_per_game` rises from 6,480 to 21,600 seconds. The 132-minute
suite boundary is scaled by the same `360/108` factor to 440 minutes. Context
32,768, fixed-30 history, 22 workers, cap 14, PLU0, no replay, no reflection,
no refinement, no Stall-140, no Dynamic Slack, and the top-six curator remain
locked. The hard VM lifetime is 31,800 seconds.

- Runner GCS generation: `1788625917051796`
- Runner SHA-256: `1f37464a2c115aa1f68fcf54e4024ba80f3bcc957fff07ff52bc1025e9c565fe`
- Runner MD5: `pt3+gMNZqM7PVUMgOPft2g==`
- Sole-delta audit: substituting the four 21,600/440 time literals back to
  6,480/132 makes the runner byte-for-byte identical to the champion runner.

| Replica | Final zone | Run ID | Startup SHA-256 |
|---|---|---|---|
| R1 | `us-east4-c` | `g4run-q38-kwbase-long6h-r1-20260905-124512` | `476865A9EACE32F14904E79A848E44FC59C10C7C1541CA6590033259CC9E9B6E` |
| R2 | `us-east5-b` | `g4run-q38-kwbase-long6h-r2-20260905-143835` | `476865A9EACE32F14904E79A848E44FC59C10C7C1541CA6590033259CC9E9B6E` |

R2 requests in `europe-west4-b` and `europe-west4-c` ended in explicit G4
stockout before instance creation and remain unscored audit records. First
bounded snapshot: R1 gameplay minute 113 mean `9.244083706686823`, 22 games
reported, 45 levels, 3,733 actions, and zero observer errors. R2 was still in
startup. No recurring polling loop was created.

## Curator-on toolkit 2x2 launched and doubled 2026-09-05

The toolkit handoff must be evaluated on the recovered champion contract, not
the canceled curator-off exploratory launch configuration. All four arms lock
Flash-Next revision `7b719225242aacd3dbd3f9407468c2ee9a9d2594`, context
32,768, fixed-30 retained assistant turns, 22 workers, 6,480 seconds per game,
the 132-minute suite boundary, cap 14, PLU0, no replay, no reflection, no
refinement, no Dynamic Slack, and the persistent top-six curator.

| Mode | Bundle | SHA-256 | CPU toolkit | Budget reminder |
|---|---|---|---|---|
| `control` | `bundle-q38-flashnext-rtdv12-cap14-kaggle-winner-gcp.tgz` | `2ed1e758d07880fb4a9c764e57b4943e20c676cfdc881ce8bc1d8f2bcb1a5bd2` | No | No |
| `toolkit` | `arc3-kaggle484-cpu-toolkit-20260905.tgz` | `8841edbce38075456a6451252be79ba55ea1871f8b47161b7f8f932622989e25` | Yes | No |
| `reminder` | `arc3-kaggle484-baseline-reminder-20260905.tgz` | `e5d2851317a3644565cff595b8670619e06b2b34aad2e033528264fcbd7421e1` | No | Yes |
| `combined` | `arc3-kaggle484-toolkit-reminder-20260905.tgz` | `bd41632163c14736d7bdae596cd6bd4b4e206d9a664812cb12459aa0986b290b` | Yes | Yes |

The CPU toolkit exposes optional crop, mask, topology, relations, path,
reachable, groups, background, HUD, lattice, cells, symmetry, tracking, and
pattern-find operations. It includes the lazy per-game 128-entry/4 MiB encoded
result cache and persistent helper registry. Nothing is automatically dumped
into context. The reminder is advisory only: before each completion it shows
the fresh minimum of game/suite remaining time and cumulative backend-reported
generated tokens against a 108,000-token soft target. It adds no hard cutoff.

The champion launcher now accepts `ToolkitMatrixMode` and requires curator-on,
the corrected champion runner, exact bundle SHA/MD5/member identities, and an
arm-specific pre-game activation self-test. Local validation passed 136 toolkit
regressions, 11 reminder unit tests, and all four activation checks.

| Mode | Replica | Zone | Run ID | Startup SHA-256 |
|---|---|---|---|---|
| `control` | R1 | `us-east5-a` | `g4run-q38-tk2x2-ctl-r1-20260905-154351` | `F9782C871FBA8B369CA9A15B5EF693BD3AAC158F4564CC87A22563B905F39AAA` |
| `control` | R2 | `us-east5-a` | `g4run-q38-tk2x2-ctl-r2-20260905-155735` | `F9782C871FBA8B369CA9A15B5EF693BD3AAC158F4564CC87A22563B905F39AAA` |
| `toolkit` | R1 | `us-east5-b` | `g4run-q38-tk2x2-tool-r1-20260905-154353` | `5FFEEB2416BFEDB401B361B7066FCCBA053BF83F50618EAEB44188C906716FAF` |
| `toolkit` | R2 | `us-east5-b` | `g4run-q38-tk2x2-tool-r2-20260905-155904` | `5FFEEB2416BFEDB401B361B7066FCCBA053BF83F50618EAEB44188C906716FAF` |
| `reminder` | R1 | `us-central1-b` | `g4run-q38-tk2x2-rem-r1-20260905-154350` | `7BE837035FBBDED99B3C77E69F2718BDB6CAFBA7A4570F827C8B741F5E78AF6C` |
| `reminder` | R2 | `us-central1-b` | `g4run-q38-tk2x2-rem-r2-20260905-160043` | `7BE837035FBBDED99B3C77E69F2718BDB6CAFBA7A4570F827C8B741F5E78AF6C` |
| `combined` | R1 | `us-central1-c` | `g4run-q38-tk2x2-comb-r1-20260905-154352` | `C9E357844BA6FA643E09C6005A6EE86B9BFE32ED2C72BC6EC6C0B0B8C88D92FD` |
| `combined` | R2 | `us-central1-c` | `g4run-q38-tk2x2-comb-r2-20260905-160210` | `C9E357844BA6FA643E09C6005A6EE86B9BFE32ED2C72BC6EC6C0B0B8C88D92FD` |

All eight direct Spot G4 instances were confirmed `RUNNING`. Every R1 arm
restored the GCS-mirrored Flash-Next runtime, passed its mode-specific
activation self-test, and started 22-game concurrent gameplay. First bounded
R1 snapshot: control minute 10 mean `0.6204861111111112` (6 levels, 311
actions); toolkit minute 11 mean `0.5650793650793651` (5 levels, 317 actions);
reminder minute 12 mean `0.6489654579824712` (7 levels, 336 actions); combined
minute 13 mean `0.4636423405654175` (5 levels, 338 actions). All reported 22
games and zero observer read errors. These are early, asynchronously sampled
scores and are not comparative results. The initial concurrent R2 submissions
hit a local Cloud SDK configuration-read race before instance creation; all four
were then submitted sequentially and launched successfully. No recurring
polling loop was created.

## Operational order

1. Wait for the mirror `DONE` marker.
2. Validate `DONE` and `MANIFEST.json` against the pinned revision and each other.
3. Run the launcher parser/unit checks and cloud preflight for every distinct arm.
4. Launch fresh experiment instances/MIGs with a new attempt identifier; the current valid attempt is AB4. Never reuse AB1, AB2, or AB3.
5. Confirm model restore, manifest verification, PLE conversion, vLLM health, champion self-test, and 25-game harness start.
6. Report score only from `runs/score-observer/score-latest.json` or `score-final.json`, always with games reported and elapsed minute.
7. Preserve immutable launch state, startup log, model manifest identity, and score artifacts in GCS.

## Related audit records

- `AUDIT_FINAL.md`: canonical Stall-140 release provenance.
- `AUDIT_DYNAMIC_SLACK_ARMS_20260904.md`: Dynamic Slack implementation and bundle identities.
- `FAILED_ATTEMPT_INVALIDATION_20260904.txt`: AB1 invalidation.
- `test_champion_reasoning_arms.py`: static exact-baseline reasoning-arm checks.
