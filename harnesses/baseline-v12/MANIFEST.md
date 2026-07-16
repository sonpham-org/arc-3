# baseline-v12 — FROZEN. Do not edit.

The known-good graft baseline (thtennant v12 duck-harness, `taaf_grafts` composite:
shortcircuit + efficiency + retry_guard). This vendored tree is the exact source the
`bundle-v12` GCS artifact runs.

## Why this exists as a vendored copy
The bundle was built from a **dirty working tree** (`git_status.txt` shows
`ARC3-Inference a2dddac DIRTY`), so **no clean git commit equals it** — its
`tool_agent.py` is +172 lines off git `a2dddac`, `solver.py` +90. This folder is the
only faithful, diffable record of the real baseline. It is what variants derive from.

## Provenance
- Source: `gs://cellens-ai-artifacts/arc3-duck/tufa-exact/bundle-v12.tgz` (re-downloaded
  pristine and vendored unmodified — verified no `frame_mode.py`, i.e. uncontaminated).
- Frozen copy (write-once): `gs://cellens-ai-artifacts/arc3-duck/tufa-exact/frozen/bundle-baseline-v12.tgz`.
- Model: `vrfai/Qwen3.6-27B-FP8`, single board image (`MULTIMODAL_CONTEXT=current_grid`),
  last-frame mode. Launch: `gcp/v12_startup.sh`.

## Validated scores (public 25 games, ex-`ft09`; use this metric, not raw all-25)
| run | all-25 | **ex-`ft09`** | `ft09` |
|---|---|---|---|
| baseline #1 (`v12-corrected-grafts`) | 2.127 | 1.224 | 23.81 |
| baseline #2 (`g4run-v12base2`) | 1.141 | 1.188 | 0.00 |
| **mean (the reference)** | — | **≈ 1.21** | — |

`ft09` is a coin-flip worth ±1.0 on the raw average (0 one run, 23.8 the next). The
ex-`ft09` metric is stable (1.19–1.22). Compare everything on it.

## Rules
- Read-only. To change behavior, make a variant folder (see `../README.md`).
- To run: pull the frozen bundle, `sys.path` picks up `src/ARC3-Inference` (via
  `v12_run.py`), grafts from `src/taaf-grafts`.
