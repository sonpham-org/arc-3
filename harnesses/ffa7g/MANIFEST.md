# ffa7g — frame-full + action7-anim + goal-guidance + no-impact (band ∪ LLM world-model)

The integrated feature stack on top of the frozen baseline. `g` = goal-guidance
prompt; the no-impact detector (`n`) is layered on the same env-toggle loop. Stored
as a patch on a **copy of `../baseline-v12/`** (never edited in place), per the
harness rules.

- **Derives from:** `../baseline-v12/` (bundle-v12), composing three earlier variants
  as real source edits: `../frame-full/` (`ARC3_FRAME_MODE=full`), `../action7-anim/`
  (ACTION7 round-trip + animation metadata), plus goal-guidance + no-impact (new here).
- **Patch:** `patch/ffa7g-full-stack.patch` — 7 files, applies `-p1` to a fresh copy of
  `baseline-v12/src/ARC3-Inference` (dry-run clean). Reconstructs the exact source the
  in-flight `g4run-v12ffa7g*` bundles run.
- **Bundle:** `gs://cellens-ai-artifacts/arc3-duck/tufa-exact/bundle-v12ffa7g*.tgz`
  (`g` = without no-impact, `gn` = with). Launch: `gcp/launch_ffa7g.sh`.

## Feature layers (7 files)
1. **frame-full** (`frame_mode.py`, `runtime_state.py`, `action_names.py`, `prompts.py`):
   full-frame images per action. Env `ARC3_FRAME_MODE=full`; also runs in `ascii`.
2. **action7-anim** (`action_names.py`, `solver.py`, `tool_agent.py`): ACTION7 round-trip
   fix + always-visible per-action animation metadata (animated objects rendered as
   strings, per-frame cell counts, bbox top-left; `show_animation_by_objects` /
   `show_animation_by_bbox` sandbox methods).
3. **goal-guidance** (`prompts.py`): `game_overview` rewritten so the agent does not
   mistake a once-per-turn incrementing HUD for the goal; action-efficiency mantra.
4. **no-impact detection** (`solver.py`, `tool_agent.py`, `python_tool_sandbox.py`,
   `prompts.py`): stop wasted actions (wall-presses in exploration) whose only board
   change is deterministic housekeeping (a HUD/timer band). Default `intent="explore"`
   (stops on no-impact); agent opts out with `intent="solve"`. Detect-and-stop, reported
   as `stop_reason="no_impact_action"`. Two overlaid detectors, union'd (never subtract):
   - **Statistical band** (`_HousekeepingBand`): online per-row/col change frequency,
     `window=20, threshold=0.9, warmup=8`, reset on level-increment. Per-*cell* frequency
     fails (a bar's frontier changes each cell once); per-row/col is the fix.
   - **LLM code world-model** (`_HudCodeModel`, CEGIS): the agent writes `advance_hud(frame,
     action) -> frame` in a `HUD model:` note; harness runs it inline (SIGALRM-guarded,
     restricted builtins), verifies the bar prediction each action, and unions the
     predicted cells into the housekeeping mask **only when verified**. Write-once /
     run-free: dropped (`stale`) after 2 consecutive mispredictions → nudge to rewrite →
     falls back to the band. Handles no-HUD games (model never registers → pure band).
     `no_impact_source` ∈ {exact, band, model, model+band}.

## Verification
- All 7 files compile. Patch dry-run applies clean to a pristine baseline copy.
- **End-to-end extraction bug (found + fixed via a live local run):** the agent emits
  `advance_hud` inside a fenced code block, but `_extract_scientist_note` routed it through
  the prose extractor, which `.strip()`s each line and collapses newlines to spaces — so the
  code arrived as ONE line and `_HudCodeModel.register` raised `SyntaxError`, silently no-op'ing
  the whole model path (permanent fallback to the band). Fixed with `_extract_hud_model_code`,
  which pulls the fenced `def advance_hud` block raw (indentation + newlines preserved).
  Re-tested through the real `_extract_scientist_note` → register → predict path: registers,
  predicts, prose fields unaffected. The dry-run had missed this because it fed `register` a
  clean code string, skipping the extractor.
- **no-impact on ls20** (112 recorded actions, 36 true housekeeping-only, replay dry-run):
  | detector | detected | false-positive | miss |
  |---|---|---|---|
  | band only | 35/36 | **0** | 1 (inside warm-up) |
  | band ∪ verified model | **36/36** | **0** | 0 |
  The union is provably ≥ band (model can only add masked cells), so a partial/under-
  predicting model cannot regress detection; here it strictly improves (covers the
  band's warm-up window from action 1). 0 false-positives = never stops a real move.
- **advance_hud end-to-end (agent actually authors + uses a model):** pending local
  qwen3.6:27b (Ollama) ls20 run.

## Validated score (public 25 games, ex-`ft09`, 2 passes each — FINAL)
Clean 1-variable ablation: same bundle ± the no-impact band. Both runs completed
2026-07-18.
| arm | pass A | pass B | **mean ex-`ft09`** | actions/pass |
|---|---|---|---|---|
| **without** no-impact (ffa7g, `-1845`) | 0.946 | 1.145 | **1.046** | ~3353 |
| **with** no-impact (ffa7gn, `-1948`) | 2.061 | 1.187 | **1.624** | ~2537 (**−24%**) |

Headline: the no-impact band lifts ex-`ft09` **1.046 → 1.624 (+0.58, ~55%)** while
cutting **~24%** of actions. Both with-passes beat both without-passes, and the gain is
broad (14/24 games score >0; vc33 +4.96, r11l +3.72, tu93 +2.70, sb26 +11.0). n=2 with
high pass-variance, so treat the magnitude as indicative, but the direction is consistent
on both axes. `ft09` excluded — it swings the all-25 mean by ±1.0 on its own. (My earlier
`−57%`/single-pass figures were partial-snapshot artifacts; these are the completed runs.)
