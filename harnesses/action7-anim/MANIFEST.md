# action7-anim — baseline + 2 fixes from the 1.47 "dark-agi" notebook

Two surgical fixes ported from `boristown/agi-duck-harness-dark-agi-ver` (Kaggle,
public **1.47**) — which is our *exact* base (same Qwen3.6-27B-FP8, same taaf
framework/wheelhouse) + only these two in-memory patches. We apply them as real
source edits on a **copy of the frozen baseline** (not frame-full), so it's a
clean 1-variable delta from our best-ever submission.

- **Derives from:** `../baseline-v12/` (bundle-v12, unmodified except the 2 fixes).
- **Bundle:** `gs://cellens-ai-artifacts/arc3-duck/tufa-exact/bundle-v12a7.tgz`.
  Launch: `gcp/v12a7_startup.sh`. No `ARC3_FRAME_MODE`, no predict — pure baseline
  + the 2 fixes. `MULTIMODAL_CONTEXT=current_grid` (single image, as baseline).

## The two fixes (4 files: action_names, prompts, tool_agent, solver)
1. **ACTION7 round-trip (real bug fix).** Our `ENGINE_TO_MODEL_ACTION` mapped
   ACTION1–6 + RESET but **not ACTION7** — so the model saw `ACTION7` in
   `valid_actions` yet `to_engine_action("ACTION7")` returned `None` and it
   **silently no-op'd**. Every game that needs ACTION7 (tn36/vc33/lp85/ar25 all
   expose it) was handicapped. Fix: add the neutral `ACTION7 -> ACTION7` round-trip
   + a prompt line telling the model it's executable and *game-specific* (probe it,
   don't assume undo/confirm/back).
2. **Compact always-visible animation metadata.** `solver._animation_summary`
   computes scalars from the intermediate frames and adds them to every action
   result (surfaced via `_compact_action_result` into `last_action_result`):
   `animation_frame_count`, `animation_changed`, **`animation_only_changed`**,
   `animation_changed_cell_count`, `animation_changed_bbox`,
   `animation_transition_count` (merged across a batch in `step_env`).
   - Cheaper than our full-frame IMAGES (`frame-full`), and **always visible** —
     no opt-in. This directly addresses our own finding that Qwen ignores optional
     frame tools (see `../predict-check`: 0 `predict()` calls). `animation_only_changed`
     flags an action that flashed a real transient change but left the same final
     board (a blocked move, a toggle that reverted) — a signal last-frame misses.

## Verification (before launch)
Syntax OK (4 files); ACTION7 now round-trips (`to_engine("ACTION7")=="ACTION7"`,
was `None`); `_animation_summary` unit-tested — flash-revert → `only_changed=True`,
real move → `only_changed=False`, no-anim → all False. Diff vs pristine baseline is
exactly the 4 files.

## Validated score (public 25 games, ex-`ft09`)
| run | all-25 | **ex-`ft09`** | vs baseline ≈1.21 / frame-full 1.44 |
|---|---|---|---|
| `g4run-v12a7-20260717-2356` | _pending_ | _pending_ | in flight |

Reference: the source notebook scored **1.47** (raw). Compare on ex-`ft09`.
