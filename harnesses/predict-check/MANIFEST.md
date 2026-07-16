# predict-check — variant of frame-full (OPINE idea grafted onto 1.38)

Predict-then-check: the agent may state, **before** an action, what it expects
that action to do (`predict(...)` in the python sandbox). The harness scores the
claim against the frame the engine actually produced — for free, from the
`board_changed` + next frame the sandbox already receives back — and keeps a
running `prediction_stats` gauge plus a per-action `last_prediction_result` with
a `surprise` flag when the world disagreed with the model. A `surprise` is the
CEGIS counterexample: exactly where the agent's dynamics model is wrong and
worth re-probing. Non-prescriptive: predicting is always optional.

This is the first OPINE-World idea grafted onto our proven structure (the graft
loop + full-frame that scored 1.38 / 1.44 ex-`ft09`), rather than the separate
world-model harness. It is **one added variable** on top of full-frame.

- **Derives from:** `frame-full` (bundle-v12ff3, the validated full-frame source),
  NOT re-derived from baseline — parent is the artifact that scored 1.44.
- **Env:** `ARC3_PREDICT_CHECK=1` (the added variable). `ARC3_FRAME_MODE=full`
  stays (predict-check builds on full-frame). `MULTIMODAL_CONTEXT=current_grid`.
- **The change (4 files, verified 1-variable diff vs frame-full):**
  - `patch/predict_check.py.new` (new) — `ARC3_PREDICT_CHECK` toggle, default OFF.
  - `patch/predict-check.diff` — edits to `prompts.py` (non-prescriptive
    `PREDICT_ADDENDUM` + tool clause), `python_tool_sandbox.py` (a `predict(...)`
    sandbox fn + auto-check against the actual next frame; `prediction_stats` in
    the final payload), `tool_agent.py` (seed flag + gauge into sandbox state,
    carry the gauge game-long on `self`, gate the addendum).
  - No `solver.py` / no protocol changes — the sandbox already receives
    `board_changed` + the new frame per action, so the check is self-contained.
- **Bundle:** `gs://cellens-ai-artifacts/arc3-duck/tufa-exact/bundle-v12pc.tgz`.
  Launch: `gcp/v12pc_startup.sh`.
- **Toggle safety:** with `ARC3_PREDICT_CHECK` unset the `predict` global is not
  even injected, so a v12pc bundle runs **identically to frame-full** — verified
  by an end-to-end sandbox test (see below).

## Verification (before launch)
End-to-end test drove the real sandbox subprocess through predict→action→check
(`scratchpad/e2e_predict.py`), all pass: change-correct, surprise-on-no-change,
exact-grid match (0 mismatches), grid-mismatch (2 cells), game-long accrual, and
predict-check-OFF leaves no `predict` global. Caught + fixed a real bug: an empty
`prediction_stats` seed (every game's first turn) would `KeyError` on the first
prediction — the bootstrap now `setdefault`s the gauge keys.

## To rebuild the bundle
```
mkdir build && tar xzf <bundle-v12ff3.tgz> -C build
cd build/src/ARC3-Inference/inference/agent
cp <predict-check/patch/predict_check.py.new> predict_check.py
patch -p1 < <predict-check/patch/predict-check.diff>   # from build/src/ARC3-Inference
# re-tar build/ -> bundle-v12pc.tgz ; diff vs frame-full must be exactly the 4 files
```

## Validated score (public 25 games, ex-`ft09`)
| run | all-25 | **ex-`ft09`** | vs frame-full 1.44 / baseline ≈1.21 |
|---|---|---|---|
| `g4run-v12pc-20260716-1326` | _pending_ | _pending_ | first run in flight |

Compare on ex-`ft09` only (raw all-25 swings ±1.0 on `ft09` alone). Replicate a
2nd seed before trusting a positive.
