# harnesses/ — frozen baseline + variant registry

The rule that keeps us from re-living the drift mess (where `main` diverged from the
known-good baseline and we had to reconstruct it): **the baseline is an immutable
artifact; experiments copy from it and never edit it in place.**

## The rules
1. **`baseline-v12/` is FROZEN.** Do not edit its files. It is the exact source the
   `bundle-v12` GCS artifact runs (which is *not* any clean git commit — the bundle was a
   dirty tree, so this vendored copy is the only faithful record). Tagged `baseline-v12`.
2. **`main` is "latest integration," never "the baseline."** Always benchmark a variant
   against `baseline-v12/`, not HEAD.
3. **A variant = `copy of baseline-v12` + `its own patch` → its own new-named bundle.**
   Never mutate the baseline or overwrite a shared GCS bundle; always a new name.
4. **Every folder has a `MANIFEST.md`**: what it derives from, the diff, env config, and
   its **validated ex-`ft09` score(s)**. So nothing good is ever un-findable again.
5. **Score on ex-`ft09`, never raw all-25.** Two baseline runs proved a single game
   (`ft09`) swings the all-25 average by ±1.0. Replicate 2–3× anything promising.

## Two kinds of variant
- **Small / additive / shares the agent loop** (full-frame, click heuristics, prompt
  scaffolds) → an **env-toggle**, stored here as a `patch/` + `MANIFEST.md`. Build it by
  patching a *copy* of `baseline-v12`.
- **Fundamentally different code** (a two-agent world-model harness, a vision-VLM policy)
  → its **own folder** with full source, because it doesn't share the loop. Don't force
  it into a toggle.

## Shared across every harness (so N harnesses stay comparable)
- The metric (ex-`ft09`), the runs scoreboard (`docs/`), and the launch/monitor infra
  (`gcp/` — isolated bundle + smoke-gate + watchers).
- The test-only game `as66` ([`datasets/test-only-games/`](../datasets/test-only-games/README.md)):
  run it with `environments_dir=datasets/test-only-games`, report it on its own line (never in
  the ex-`ft09` or all-25 average), and never train on its runs.

## Contents
- `baseline-v12/` — FROZEN reference. Validated ex-`ft09` ≈ **1.21** (2 runs: 1.224, 1.188).
- `frame-full/` — variant (env-toggle `ARC3_FRAME_MODE=full`). ex-`ft09` **1.44 (+19%)**.
- `predict-check/` — variant of `frame-full` (env-toggle `ARC3_PREDICT_CHECK=1`): OPINE
  predict-then-check / counterexample signal grafted onto the graft loop. Score pending.
- `action7-anim/` — variant of `baseline-v12`: ACTION7 round-trip fix + compact
  always-visible animation metadata (ported from the 1.47 dark-agi notebook). Score pending.
- `world-model/` — stub for the OPINE-style verified-world-model harness (new loop).
- `sparse-deletion/` — Kaggle prompt arm B (four false assertions deleted), bottom seven, and the
  base every Kaggle arm since stacks on. Builder: `kaggle/experiments/sparse-deletion/`.
- `reset-guard/` — arm I on arm B: RESET offered to the model behind a rate guard (never twice
  in a row, one per 20 actions). Jobs 11-12, paired with an arm-B control at the same cap. Pending.
- `oracle-rules/` — arm O on arm B (env-toggle `ARC3_ORACLE_RULES_DIR`): the game's own
  rulebook injected into every user turn, to split "never had the idea" from "could not play
  it" on the games the 27B never clears. Local a108 arm, scored per game against a paired arm-B
  control, not ex-`ft09`. Not run.
