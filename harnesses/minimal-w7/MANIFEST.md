# minimal-w7 — frozen minimal-only Flash-Next harness

This directory is the exact source snapshot used by the September 12, 2026
private Kaggle readiness run named **ARC3 Flash Next W7 Minimal Only**. It is the
current minimal harness baseline for follow-on modeling work.

## Identity

- Source family: `minimal_loop_a_noobs_v1__ple_readahead_v1`
- Player source SHA256: `1ccb47affc5ddba843f025eb937e9e96e1d2defd54332cbdf4cc37223c443e2b`
- Config ID: `763c5bea9a3725cfdd6dbe568e91c3178c440969152c6d6f190f75f83f5aae70`
- Model: `RadixArk/Qwen3.8-Flash-Next-NVFP4`
- Model revision: `7b719225242aacd3dbd3f9407468c2ee9a9d2594`
- Kaggle script version: `349333846` (private readiness only; not submitted)

`CANDIDATE_SOURCE_MANIFEST.json` is the machine-readable file/hash authority.
The full player and TAAF sources are vendored under `src/`, following the same
immutable-snapshot convention as `baseline-v12`.

## Active recipe

- Loop A enabled; input access disabled.
- Full-context history with 30 assistant turns.
- 102,985-token context and 94,281-token input budget.
- Seven lanes, action cap 14, full frames, FP8 KV cache.
- Budget reminder and legacy segmentation/animation APIs retained.
- Observer, reflection, memory, symbolic search, replay, curator, workspace,
  execution-mode, and other larger scaffolds disabled.
- The later `tiny-retry` experiment is deliberately **not** included.

See `CONFIG_FLAGS.json`, `EXPECTED_PROMPTS.json`, and `PROMPT_FLAGS.json` for
the complete resolved configuration and prompt surfaces.

## Validation status

The private readiness check passed on the exact snapshot in this directory:

- 53 local tests passed, including prompt delivery, input-off behavior, timing,
  lifecycle cleanup, and mutation-rejection checks.
- The private Kaggle check completed 384 real actions across seven games after
  a 900-second post-startup gameplay window.
- All six serving processes exited before the disposable runtime was removed.
- CPU PLE prefetch read 102,400,491,800 bytes and stopped cleanly.

The compact receipts are under `evidence/`. This was a readiness test, not a
competition submission or a matched performance comparison. The Kaggle build
uses preconverted BF16 CPU PLE; the GCP recipe used native FP8 CPU PLE.

## Rules

Treat this directory as immutable. Create any experiment as a copy plus a named
patch/manifest, and never edit `baseline-v12` or this snapshot in place.
