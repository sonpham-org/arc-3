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

## Contents
- `baseline-v12/` — FROZEN reference. Validated ex-`ft09` ≈ **1.21** (2 runs: 1.224, 1.188).
- `frame-full/` — variant (env-toggle `ARC3_FRAME_MODE=full`). ex-`ft09` **1.44 (+19%)**.
- `predict-check/` — variant of `frame-full` (env-toggle `ARC3_PREDICT_CHECK=1`): OPINE
  predict-then-check / counterexample signal grafted onto the graft loop. Score pending.
- `world-model/` — stub for the OPINE-style verified-world-model harness (new loop).
