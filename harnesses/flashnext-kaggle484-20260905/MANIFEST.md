# Flash-Next Kaggle 4.84 harness experiments — 2026-09-05

This review package preserves the code and compact operational evidence used
to recover and extend the ARC3 Flash-Next champion on GCP. It was copied into a
new harness directory; `harnesses/baseline-v12/` remains untouched.

## Start here

- `docs/FLASH_NEXT_GCP_RUNBOOK.md` is the chronological experiment record,
  including run IDs, scores, bundle hashes, GCS generations, machine choices,
  and failure/recovery notes.
- `launchers/launch_champion_stall_ab.ps1` is the authoritative GCP launcher.
- `states/` contains 92 launch-state records. Every record names the exact GCS
  prefix where the complete canonical run artifacts remain available.
- `evidence/gcp/` contains compact snapshots from the two live metadata/toolkit
  crossover runs: startup, vLLM, capacity-smoke, warm-up, score-observer,
  resource, and curator logs.
- `evidence/local-launch/` contains the local stdout/stderr retained from the
  context-sweep launches.

## Included source variants

| Directory | Variant |
|---|---|
| `variants/champion-source/` | downloaded Kaggle champion source |
| `variants/recovered-base/` | audited recovered launch base |
| `variants/dynamic-slack-reference/` | reference implementation used for the scheduler port |
| `variants/stall140/` | Stall-140 only |
| `variants/dynamic-slack/` | Dynamic Slack |
| `variants/stall140-dynamic-slack/` | Stall-140 plus Dynamic Slack |
| `variants/visual-transitions/` | control/metadata/additive/replace transition matrix |
| `variants/cpu-toolkit/` | CPU vision toolkit |
| `variants/visual-metadata/` | metadata-only transition evidence |
| `variants/toolkit-reminder/` | CPU toolkit plus budget reminder |
| `variants/metadata-toolkit/` | metadata plus CPU toolkit crossover |
| `variants/metadata-toolkit-reminder/` | metadata plus toolkit plus reminder crossover |

`tools/` contains the release builders, score observer, analyses, runners,
release verifier, and tests that were present in the launch workspace.

## Champion contract

- Model: `RadixArk/Qwen3.8-Flash-Next-NVFP4`
- Revision: `7b719225242aacd3dbd3f9407468c2ee9a9d2594`
- Model source: verified GCS mirror
- Context: 32,768 tokens
- Retained assistant turns: fixed 30
- Workers: 22
- Game cap: 6,480 seconds for standard runs
- Suite boundary: 132 minutes for standard runs
- Cumulative action cap: 14; post-level uncapped turns: 0
- Curator: persistent top-six GPU world-model curator
- Replay, reflection, refinement, and Dynamic Slack: off unless the named arm
  explicitly changes that single dimension

## Current crossover bundles

| Arm | Bundle SHA-256 | Live run |
|---|---|---|
| Metadata + Toolkit | `01c73733fdfc999182369da530542b1212e50007d5d8d3505f384f61cce9cfb2` | `g4run-q38-kwvmeta-tool-r1-20260905-165130` |
| Metadata + Toolkit + Reminder | `45526064bf9adb073e9d4fc1f0575d0dda4aa9eb158e102bbb7d4545144b3d8a` | `g4run-q38-kwvmeta-comb-r1-20260905-165238` |

Both merged trees passed 136/136 exact toolkit tests in metadata mode, plus
their visual-transition and reminder-specific tests. Both live runs passed the
golden-image attestation, 22-request capacity smoke, harness import check, and
arm-specific activation self-tests.

## Artifact policy

The repository intentionally does not duplicate model weights, deployment
images, generated game frames, or every raw transcript. Those durable objects
remain at the immutable GCS prefixes recorded in `states/`. Release archives
also remain in GCS and are identified by SHA-256 and generation in the runbook.
This package includes all locally retained source, launch/state records, and
the compact logs needed to audit configuration and startup behavior.
