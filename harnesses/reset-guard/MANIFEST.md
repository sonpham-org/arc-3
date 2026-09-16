<!--
Author: Claude Opus 5
Date: 16-September-2026
PURPOSE: Registry entry for arm I, the RESET-guard arm Dr. Fable called for in
docs/plans/2026-09-16-dr-fable-calls-on-the-step5-review.md section 1.2. Records what it
derives from, the exact diff, what the guard does and why, the run shape (including a cap
correction and the paired control it forces), the decision rule written before any number
exists, and how the build was verified.
SRP/DRY check: Pass - harnesses/README.md requires one MANIFEST per variant; the patch lives
in kaggle/experiments/sparse-deletion/build_bundles.py and patch/ here is its rendered diff.
-->

# reset-guard — arm I

## In one paragraph

The harness never lets the model choose RESET: it hides it from the list of moves and resets
automatically after a death. On ls20 a human wins by pressing RESET on purpose (it refills
lives and the step meter), so hiding it removes a winning move. This arm offers RESET again,
behind a guard so the model cannot spam it: never twice in a row, and at most once in any 20
actions. It runs on the bottom seven, four passes, next to a fresh arm-B control at the same
time cap.

## Derives from

Arm B, `markbarney/taaf-duck-sparse-deletion` (`harnesses/sparse-deletion/`), exactly as
jobs 2 and 10 ran it. Rebuilt from `/tmp/armctl` with `build_bundles.py`, arm B reproduces
job 2's in-log `prompts_py_sha256=81a04005…` and arm H reproduces job 10's `8192f5e8…`, so the
builder still makes what ran.

Published bundle: `markbarney/taaf-duck-reset-guard` (private).

## The diff — two files against arm B

`patch/solver.py.patch` and `patch/prompts.py.patch`. They apply to a copy of arm B and
reproduce the built bundle byte for byte; `diff -rq` against arm B shows no other file.

1. **`solver.py`** — the guard.
   - `_engine_action_names` takes `include_reset`; every menu the model sees (the analyzer
     turn, the action payload, the error payload) now asks the guard whether to list RESET.
   - `step_env` refuses a RESET the guard does not allow, before it executes, with
     `stop_reason="reset_rate_limited"` and a one-line reason. A refusal spends no action. In
     a batch, the actions before it run and the batch stops there.
   - Every accepted and refused RESET prints a `RESET_GUARD` line, and each game prints a
     `RESET_GUARD_SUMMARY`, so the rate is in the log as well as the artifacts.
2. **`prompts.py`** — one line, after the `action()` contract bullets:
   > `RESET` restarts the current level from its starting state; completed levels stay
   > completed, and it counts as an action. It is rate-limited: never twice in a row, at most
   > once per 20 actions, and it is absent from `valid_actions` while unavailable.

   251 characters. It says nothing about what RESET refills, because that differs by game.

## Three facts from the source that shaped the patch

**RESET was hidden, not blocked.** TAAF's `available_actions` always includes RESET (id 0),
`to_engine_action("RESET")` resolves, and `step_env` checks nothing else. In arms A–H a model
that typed RESET would have executed it. So the guard has to live in `step_env`; filtering the
menu alone would guard nothing. `test_reset_guard.py` shows it on arm B's own bundle.

**The model never did.** Every RESET in jobs 1–10 followed a `GAME_OVER` — all automatic.
Model-chosen RESETs, measured with `count_resets.py`: **0** in each of jobs 1, 2, 3, 5, 6, 7, 8,
9 and 10 (job 4: 0 by the same rule). That is the baseline rate this arm is measured against.

**On Kaggle every RESET is a level reset.** arcengine restarts the whole game from level 1
when RESET is pressed with no move made on the current level, unless `ONLY_RESET_LEVELS=true`.
The duck notebook sets it in cell 3, so the guard needs no rule for that case. The provenance
cell now asserts it; if the pin ever goes, the job stops before a game is played.

## The guard, exactly

- **Never twice in a row.** RESET is refused when the previous executed action was a RESET.
  That includes the harness's own auto-reset after a death and the game's opening, because a
  RESET on a level already at its start only spends an action.
- **At most one per 20 actions.** Any 20 consecutive actions hold at most one model-chosen
  RESET: after one at action 2, the next is allowed at action 22. Auto-resets do not count
  against this, so a death never uses up the model's budget.
- as66's run of 98 RESETs in 101 actions would be stopped on its second action.

What the guard does not stop: a RESET as the first move on a freshly cleared level. Under the
pinned harness that only costs one action, and Dr. Fable's rule does not forbid it.

## Run shape — and why there are two jobs, not one

7 lanes (bottom seven) × 4 passes, `concurrency=7`, outer budget 7920s, **per-game cap 1620s**.

**The cap.** Dr. Fable asked for n=4 "with the corrected per-pass cap". Jobs 1–10 ran 1980s and
lost pass 3 every time. The repair on record, ~1840s, is wrong: it allowed for vLLM boot but
not for TAAF's 600s soft-deadline buffer (`taaf/deploy_inline.py`, `_SOFT_DEADLINE_BUFFER_S`).
In jobs 1, 2, 9 and 10 every lane was cancelled at 7321–7346s into the notebook (7920 − 600
= 7320), whatever time vLLM came up (521–613s). At 1840s pass 3 would still get ~1260s. At
1620s: 616 + 4 × 1620 + ~90s of lane drift ≈ 7186s, under 7320s.

**The paired control.** Arm B's 15 clears were measured at 1980s over passes 0–2. A guard arm
at 1620s cannot be compared with that: two things would differ. So job 12 re-runs arm B,
unchanged, at 1620s, launched alongside job 11 (Kaggle runs two GPU jobs at once). **Job 11
against job 12 is the comparison.** Job 2 stays on record and is not compared with either.

| job | kernel | bundle | arm | cap |
|---|---|---|---|---|
| 11 | `markbarney/arc3-job11-reset-guard` | `taaf-duck-reset-guard` | I-reset-guard | 1620s |
| 12 | `markbarney/arc3-job12-deletion-cap1620` | `taaf-duck-sparse-deletion` | B-sparse-deletion | 1620s |

Quota: about 21 of 30 GPU hours were used by jobs 0–10 (2.04h each by their own logs); the two
jobs take ~4.4h, and the week's allowance resets 18-Sep 20:00 ET.

## Decision rule — Dr. Fable's, copied before any number exists

Report, per game, model RESETs per 100 actions and refusals, next to level clears. Both jobs,
all four passes; passes 0–2 as well, for continuity with the older arms.

- **Clears up on ls20 or wa30 with the rate held** (not pinned at the guard) → expose RESET in
  the RL harness.
- **Clears down, or the rate at the cap** → option (a) wins: RESET stays hidden, and the
  corpus's "chose RESET on a live board" rows are retargeted to noticing the refutation earlier.
- The 27B baseline is not touched by this arm either way. It runs on the pinned harness, RESET
  hidden.

Stated limits: n=4 per game on a benchmark where a single pass often carries a game's whole
score. A one-pass difference on one game is noise and gets called noise.

## Provenance to check in the job 11 log

- `ARM_PROVENANCE marker[I-reset-guard] present=True`, every other marker `False`, the four
  deleted probes `False`
- `ARM_PROVENANCE reset_min_action_gap=20`, `only_reset_levels='true'`, an RTX PRO 6000 line
- `system_prompt_chars` = job 12's value + 251 (locally: 11,919 against arm B's 11,668; on
  Kaggle arm B has logged 11,991, so expect 12,242)
- `EXP_SETTINGS … per_game_s=1620.0 budget_s=7920.0`, and no lane in pass 3 `cancelled`

## Verification before upload

- `build_bundles.py /tmp/armctl I`: every solver anchor found the expected number of times,
  the solver compiles, three guarded menu call sites, none unguarded.
- `test_reset_guard.py /tmp/bundle-I /tmp/bundle-B <environment_files>`: 21 checks against the
  real ls20 build through TAAF's offline `GameAPI`, all passing — opening refused, one move then
  accepted, level reset (not full), counts as an action, twice-in-a-row refused, the 20-action
  window at both edges, a batch stopping at a refused RESET, auto-reset refusing the next RESET
  without using the window; and on arm B, a typed RESET executing.
- The job 11 and job 12 provenance cells, run locally: pass on their own bundles, and raise when
  job 11's cell runs on arm B or without `ONLY_RESET_LEVELS`.

## Score

Pending.
