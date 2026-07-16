# frame-full — variant of baseline-v12

Full-frame / agent-decides `last_animation`: the harness captures every engine frame per
action and exposes it to the agent's Python sandbox, plus a `frame_stats` gauge. The agent
decides per-turn whether the motion is signal or noise (non-prescriptive prompt). A single
env-toggle; shares the baseline loop.

- **Derives from:** `../baseline-v12/` (baseline bundle, unmodified except the patch below).
- **Env:** `ARC3_FRAME_MODE=full` (that is the source default; set explicitly).
  `MULTIMODAL_CONTEXT=current_grid` (single image, same as baseline).
- **The change:** 6 files — `patch/frame_mode.py.new` (new) + `patch/frame-mode.diff`
  (edits to runtime_state / python_tool_sandbox / prompts / tool_agent / solver).
- **Bundle:** `gs://cellens-ai-artifacts/arc3-duck/tufa-exact/bundle-v12ff3.tgz`.
  Launch: `gcp/v12ff3_startup.sh`.

## To rebuild the bundle
```
cp -r baseline-v12 build && cd build/src/ARC3-Inference
cp ../../../frame-full/patch/frame_mode.py.new inference/agent/frame_mode.py
patch -p1 < ../../../frame-full/patch/frame-mode.diff
# re-tar build/ -> bundle-v12ff3.tgz ; diff vs baseline must be exactly the 6 files
```

## Validated score (public 25 games, ex-`ft09`)
| run | all-25 | **ex-`ft09`** | vs baseline ≈1.21 |
|---|---|---|---|
| `g4run-v12ff3` | 1.381 | **1.439** | **+0.23 (~+19%)** |

Single run so far; the ex-`ft09` metric is stable, so this is a real positive signal, but
a 2nd seed would confirm. The raw "1.38 < 2.127" is an `ft09` mirage — see baseline MANIFEST.
Submitted to the Kaggle competition (`sonphamorg/tufa-duck-fullframe`, `ARC3_FRAME_MODE=full`).
