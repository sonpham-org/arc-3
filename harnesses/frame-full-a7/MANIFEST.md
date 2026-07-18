# frame-full-a7 — frame-full + the two a7 fixes combined

Combines our two strongest directions: **frame-full** (full-frame animation IMAGES
via `ARC3_FRAME_MODE=full`) **+** the two a7 fixes (ACTION7 round-trip + always-
visible compact animation metadata). The idea: the compact metadata is always seen
(Qwen ignores the opt-in images per our predict-check finding), the images are there
when the agent does look, and ACTION7 unlocks games neither could win before.

- **Derives from:** `../frame-full/` (bundle-v12ff3). Clean 4-file diff (the a7 edits
  land in different code regions than frame-full's changes).
- **Env:** `ARC3_FRAME_MODE=full`. Bundle `bundle-v12ffa7.tgz`; launch `gcp/v12ffa7_startup.sh`.
- **The change:** `patch/ffa7.diff` -- action_names (ACTION7), solver
  (`_animation_summary` + payload/batch merge), tool_agent (compact passthrough),
  prompts (ACTION7 + animation guidance).

## Validated score (public 25 games, ex-`ft09`, 2 seeds)
| run | ex-`ft09` | vs frame-full 1.44 / a7 ~1.24 |
|---|---|---|
| `g4run-v12ffa7-*`  | _pending_ | in flight |
| `g4run-v12ffa7b-*` | _pending_ | in flight |

NOTE ON NOISE: ex-`ft09` is high-variance (a7 seeds were 1.489 vs 0.987). Two seeds,
compare on the pair, not a single run. ACTION7 is a pure bug fix so ffa7 should be >=
frame-full; whether it beats it is likely noise-dominated.
