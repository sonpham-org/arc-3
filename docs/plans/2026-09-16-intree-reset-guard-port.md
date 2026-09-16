<!--
Author: Claude Opus 5
Date: 16-September-2026
PURPOSE: Plan note for porting the arm-I RESET guard from the frozen bundle patch
(harnesses/reset-guard/patch/) onto the in-tree agent harness
(ARC3-Inference/inference/framework/solver.py and .../agent/prompts.py). Records why the
patch cannot be applied, what the port must preserve byte for byte, the call sites it has
to cover that the patch did not, and the verification floor before a PR is opened.
SRP/DRY check: Pass — the guard's rationale, run shape and decision rule live in
harnesses/reset-guard/MANIFEST.md and are not restated here; this note covers only the port.
-->

# Port the arm-I RESET guard into the in-tree harness

## Why this is a port, not a patch

`harnesses/reset-guard/patch/solver.py.patch` was authored against
`harnesses/baseline-v12/src/ARC3-Inference/inference/framework/solver.py`, 1277 lines. The
in-tree file is **1492 lines** — 215 lines ahead, mostly the animation-summary work
(`_animation_summary`, the per-batch animation merge in `step_env`) and the full-frame /
`frame_stats` additions. Every hunk's context has moved and two of them sit inside code the
patch's `step_env` did not contain. `git apply` would fail on all of them; the behaviour is
ported by hand instead.

`harnesses/`, `kaggle/` and `vendor/` are frozen artifacts and are **not touched** by this
work. The frozen patch stays the record of what ran as Kaggle job 11.

## What must not drift

- `_RESET_MIN_ACTION_GAP = 20`.
- Refuse when `last_engine_action in (None, "RESET")` — the game's opening and the harness
  auto-reset both count.
- `gap = action_count + 1 - model_reset_positions[-1]`, refuse when `gap < 20`. The
  position appended is the post-execution `action_count`, appended *after*
  `_execute_action` returns. Both halves of that off-by-one are load-bearing: a model RESET
  at action 2 makes action 22 the next allowed position.
- `action_count` is a read-only property over `len(run.history)` — not a counter to bump.
- The `prompts.py` line is 251 characters and goes in verbatim; arm I's provenance check is
  `system_prompt_chars == control + 251`.
- `taaf/game_api.py:222` (`ONLY_RESET_LEVELS=true`) is untouched. Without it
  `arcengine/base_game.py` full-resets whenever `_action_count == 0`, which `set_level`
  zeroes at the top of every level — a model RESET on a fresh level would zero the run.

## Call sites — the part the patch does not cover

The reference build asserts three guarded menu call sites. In-tree there are **four**:

| line (pre-port) | what | in the patch? |
|---|---|---|
| 373 | `log.info("solver turn start … valid_actions=%s")` | **no — new in-tree** |
| 387 | `analyzer.analyze(valid_actions=…)` | yes |
| 692 | `_error_payload` | yes |
| 928 | the executed-action payload | yes |

Line 373 is routed through the guard too. If it printed the raw menu while the model saw the
guarded one, the turn-start log — the primary forensic surface for this arm — would misreport
what was offered. `reset_refusal()` reads only `last_engine_action`,
`model_reset_positions` and `action_count`; it is side-effect free and safe to call there.

`include_reset` defaults to `False`, so a missed call site compiles cleanly and silently
keeps RESET hidden. The static check is therefore a grep for zero remaining
`_engine_action_names(self.game)`, not a compile.

## Batch semantics — unchanged from the reviewed arm

A RESET refused mid-batch sets `stop_reason="reset_rate_limited"` and breaks, dropping the
rest of the batch. This is deliberately left as the reference has it: in-tree `step_env`
already does exactly that for an unavailable action (`stop_reason="invalid_action"`), and
`stopped_early`, `requested_count`, `executed_count` and `requested_actions` all survive
into the payload, so the model can see what was dropped. Changing it here would diverge the
in-tree harness from the arm that was reviewed and shipped, for no gain.

## Logging sink

The reference uses `print(..., flush=True)`; in-tree code logs through `log`. The `print`
is kept, because `kaggle/experiments/sparse-deletion/count_resets.py` regex-scans job logs
for `RESET_GUARD refused game=… pass=…` and that file is frozen — a `log.info` would be
subject to the harness's logging configuration, `print` is not.

## Steps

1. This note. ✅
2. Port `solver.py`: `include_reset` parameter, `_RESET_MIN_ACTION_GAP`,
   `model_reset_positions` / `reset_refusals` fields, `reset_refusal()`,
   `model_action_names()`, `log_reset_guard()`, the `step_env` refusal, the accepted-RESET
   record, `stop_detail`, the per-game summary, and all four menu call sites.
3. Port the one `prompts.py` line.
4. Add `ARC3-Inference/tests/test_reset_guard_intree.py`, the frozen bundle test adapted to
   in-tree paths (`kaggle/`'s copy is left alone).
5. `py_compile` both edited files; grep for zero unguarded call sites; run the test against
   the real `ls20` build if the local interpreter can host it.
6. CHANGELOG entry at the top, then PR against `main`. **Do not merge.**

## Verification floor

- `python3 -m py_compile` on both edited files.
- `grep -c "_engine_action_names(self.game)"` → 0.
- Four `self.model_action_names()` call sites.
- The adapted guard test against `ls20` if `arcengine==0.9.3` + `arc_agi` + `taaf` can be
  imported locally. If they cannot, the report says *compiled, not exercised* — it does not
  claim behaviour was tested.
