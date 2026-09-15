# ACTION7 registration + animation metadata — port to `main`

**Date:** 14-September-2026
**Author:** Claude Opus 5 (Bubba)
**Branch:** `fix/action7-registration-and-animation-metadata`
**Source patch:** `harnesses/action7-anim/patch/action7-anim.diff`

This README documents the PR that lands two changes from the `action7-anim` harness onto
`main`'s live inference code. It is written to be read cold: everything needed to continue
the work is here or linked from here.

---

## 1. What ACTION7 is

The ARC-3 engine exposes seven game actions plus RESET. ACTION1–4 are the directional
moves, ACTION5 is the "space"/confirm-style key, ACTION6 is a click at a `(row, col)`, and
ACTION7 is a seventh, **game-specific** control with no fixed meaning across games — in one
game it may undo, in another it may cycle a mode or drop a piece. It is only present when a
game declares it; `valid_actions` is the authority.

Twenty-one game sources in this repo reference it — `grep -rlE '\bACTION7\b' docs/static/games/src/`
returns `ar25 bp35 eh01 g011 g028 g033 g034 g036 g037 g038 gh14 lf52 ml01 mr01 mt01 ps01 pw01
sb26 sk48 su15 td05`. That is a source-reference count, not a proof each one puts ACTION7 in
`valid_actions` at runtime; `valid_actions` is still the authority per game and per state.

**It was missing from the agent's action space.** `ARC3-Inference/inference/agent/action_names.py`
defined `ENGINE_TO_MODEL_ACTION` over ACTION1–6 and RESET only. The asymmetry that made this
easy to miss:

- `to_model_action("ACTION7")` returned `"ACTION7"` — the function falls through to the raw
  name on a miss, so ACTION7 **did** appear in the `valid_actions` the model was shown.
- `to_engine_action("ACTION7")` returned `None` — there was no reverse entry.

Verified against `origin/main` before the change:

```
origin/main to_engine_action('ACTION7') = None
origin/main to_model_action('ACTION7')  = 'ACTION7'
```

The consequence is worse than a silent no-op. `HarnessSolver._normalize_actions`
(`ARC3-Inference/inference/framework/solver.py:664`) resolves every requested action *before*
any of them execute, and returns an error on the first failure:

```python
action_name = to_engine_action(raw_action.get("action"))
if not action_name:
    return None, f"Unknown action at index {index}: {raw_action.get('action')!r}"
```

`step_env` turns that into an `_error_payload` for the whole call. So a batch of
`['LEFT', 'ACTION7', 'UP']` executed **nothing** — one advertised-but-unmapped action killed
the other two as well.

> Note: the comment inside the original source patch describes this as "silently no-op'd."
> That is inaccurate against current `main`; it is a whole-batch rejection with a visible
> error string. The commit message, the comment as landed in `action_names.py`, and this
> README all use the verified behaviour.

## 2. Why it matters

It is the blocker on the v0 decision-step corpus
(`docs/trace-findings/2026-09-14-decision-step-corpus-v0-plan.md`, §4(a) and §7(b)).

The corpus unit is a decision step: state → reasoning → action. An agent cannot emit, and
cannot reason about, an action it does not know is executable. With ACTION7 dead, every
trace scraped from our harness is missing the whole class of behaviour that ACTION7 carries
in the games that declare it — including undo/recovery, which `bp35`'s human WIN replay uses.
Traces collected in that state are incomplete as SFT targets, and the gap is systematic
rather than random, so it cannot be papered over by collecting more of them. The plan's §7(b)
is explicit that the fix lands **before** extraction, not after.

Separately, this is a plain correctness bug on `main` regardless of the corpus.

**On score: this is not a score win.** Job 10 ran the ACTION7 half as a one-variable arm
(`docs/trace-findings/2026-09-14-job10-action7-arm-result.md`, on branch
`docs/bp35-trace-findings`). The fix demonstrably took — **32 committed ACTION7 presses**
against zero in every prior arm, all 32 with `board_changed == true`, and zero
`Unknown action at index 1` in the run output — but the arm scored **11 levels against the
deletion arm's 15**, a negative result against the pre-registered criterion. Land this as a
correctness fix and a corpus unblocker, not as an expected scoring improvement.

## 3. What this PR changes

Two commits, deliberately separable.

### Commit (a) — `inference: register ACTION7 so the model can actually execute it`

| File | Change |
|---|---|
| `ARC3-Inference/inference/agent/action_names.py` | Add `"ACTION7": "ACTION7"` to `ENGINE_TO_MODEL_ACTION`, with a comment explaining the round-trip. This is the whole fix: `MODEL_TO_ENGINE_ACTION` is derived from it, so `to_engine_action` starts resolving. |
| `ARC3-Inference/inference/agent/prompts.py` | One bullet added to `STRUCTURED_RUNTIME_STATE_ADDENDUM`, telling the model ACTION7 is executable when it appears in `valid_actions` and that its meaning is game-specific — probe it, do not assume undo/confirm/back. |

`valid_actions` rendering is unchanged: `to_model_action("ACTION7")` returned `"ACTION7"`
before and returns `"ACTION7"` now.

### Commit (b) — `inference: surface compact animation metadata on every action result`

`current_frame` is the *settled* board, so any intermediate animation frames the engine
produced for an action are discarded before the model sees them. Full-frame mode exposes the
raw frames via `last_animation`, but that is opt-in, token-expensive, and off by default —
and we have measured that this agent does not reach for optional frame tools.

| File | Change |
|---|---|
| `ARC3-Inference/inference/framework/solver.py` | New module-level `_grid_from_frame(frame)` and `_animation_summary(new_state, previous_grid, board_changed)`. `_animation_summary` returns six scalars: `animation_frame_count`, `animation_changed`, `animation_only_changed`, `animation_changed_cell_count`, `animation_changed_bbox`, `animation_transition_count`. It is called by one added line in `_HarnessGameSession`'s per-action payload builder (`payload.update(_animation_summary(...))`, just before `_append_action_viewer_event`). A second block in the batch path merges the six across `executed_payloads` into `final_payload`, next to the existing `board_changed` merge. |
| `ARC3-Inference/inference/agent/tool_agent.py` | `ToolAgent._compact_action_result` copies the six keys through to `last_action_result` when present, so they reach the model without an opt-in. |
| `ARC3-Inference/inference/agent/prompts.py` | One bullet documenting the six keys and what `animation_only_changed` means. |

`animation_only_changed` is the load-bearing one: it separates "nothing happened" from
"something visibly happened and then reverted" — a blocked move, a toggle that flipped back —
which the settled frame cannot express. It also resolves a dangling reference in
`LAST_ANIMATION_ADDENDUM` ("Beyond the animation summary above"), which previously had no
summary above it.

## 4. Provenance

The source is `harnesses/action7-anim/patch/action7-anim.diff`, two in-memory fixes ported
from `boristown/agi-duck-harness-dark-agi-ver` (Kaggle, public 1.47) and captured against a
**8-July-2026 snapshot** of the tree. See `harnesses/action7-anim/MANIFEST.md` for the
harness-bundle context.

**It does not `git apply` onto current `main`.** Two reasons:

1. **Path prefixes.** Every hunk header reads `--- pristine/src/ARC3-Inference/...` /
   `+++ base/src/ARC3-Inference/...`. The real tree has no `pristine`/`base`/`src` prefix —
   the path is `ARC3-Inference/...`. No `-p` level fixes this, because the two sides differ.
2. **Line drift.** Two months of commits moved every anchor: `prompts.py` 64→66,
   `tool_agent.py` 1446→1643, `solver.py` 98→102, 654→747 (also a class-body move), 728→873.

Ported hunk by hunk instead. Adaptations, all of them:

- **`prompts.py` hunk was split across the two commits.** The source diff adds both prompt
  bullets in one adjacent pair. Commit (a) takes the ACTION7 bullet; commit (b) takes the
  animation-metadata bullet. Without the split neither commit is independently revertible,
  which defeats the point of separating them.
- **`_animation_summary` gained a `try/except` around `new_state.all_frames`.** `all_frames`
  is an engine-backed property; the adjacent full-frame block in `solver.py` already guards
  it the same way. This summary runs on **every** action with no opt-in, so an exception here
  would take down the whole harness rather than degrade one action result. On failure it
  falls back to `frames = []`, which yields the all-false summary. Not in the source patch.
- **The animation prompt bullet lists all six scalars.** The July patch's bullet named only
  five, omitting `animation_changed_cell_count` while the code passed it — the model was
  handed a field it was never told about. The omission carries no rationale in the patch, so
  the bullet was completed rather than reproduced. Revert is one word if a reviewer wants the
  asymmetry back.
- **Insertion points relocated, content unchanged**, for the four anchors listed above. The
  `solver.py` batch-merge block sits immediately after the existing `final_payload["board_changed"]`
  assignment, as in the patch.

Nothing was dropped. All four files in the source patch are represented.

## 5. How to verify

Run from the repo root on the PR branch. These are the exact commands run, with their actual
output.

**Syntax — all four touched files compile:**

```console
$ python3 -m py_compile \
    ARC3-Inference/inference/agent/action_names.py \
    ARC3-Inference/inference/agent/prompts.py \
    ARC3-Inference/inference/agent/tool_agent.py \
    ARC3-Inference/inference/framework/solver.py && echo "py_compile OK (4 files)"
py_compile OK (4 files)
```

**ACTION7 round-trips (load by file path — `action_names.py` imports only `typing`):**

```console
$ python3 -c "
import importlib.util as u
s=u.spec_from_file_location('an','ARC3-Inference/inference/agent/action_names.py')
m=u.module_from_spec(s); s.loader.exec_module(m)
print('to_engine_action(ACTION7) =', repr(m.to_engine_action('ACTION7')))
print('to_model_action(ACTION7)  =', repr(m.to_model_action('ACTION7')))
print('to_model_actions([ACTION1,ACTION7]) =', m.to_model_actions(['ACTION1','ACTION7']))"
to_engine_action(ACTION7) = 'ACTION7'
to_model_action(ACTION7)  = 'ACTION7'
to_model_actions([ACTION1,ACTION7]) = ['UP', 'ACTION7']
```

The before-state, against `origin/main`:

```console
$ git show origin/main:ARC3-Inference/inference/agent/action_names.py > /tmp/an_main.py
$ python3 -c "
import importlib.util as u
s=u.spec_from_file_location('an','/tmp/an_main.py')
m=u.module_from_spec(s); s.loader.exec_module(m)
print('origin/main to_engine_action(ACTION7) =', repr(m.to_engine_action('ACTION7')))
print('origin/main to_model_action(ACTION7)  =', repr(m.to_model_action('ACTION7')))"
origin/main to_engine_action(ACTION7) = None
origin/main to_model_action(ACTION7)  = 'ACTION7'
```

**`_animation_summary` behaviour.** `taaf` is **not installed on this machine**
(`python3 -c "import taaf"` → `ModuleNotFoundError: No module named 'taaf'`), so `solver.py`
cannot be imported as a module here. The two added functions were instead extracted by AST
and exec'd standalone — they touch nothing but `typing.Any` — and exercised against fake
frame sequences (output below is column-padded for width; values verbatim):

```console
flash-revert  : {'animation_frame_count': 2, 'animation_changed': True,  'animation_only_changed': True,  'animation_changed_cell_count': 1, 'animation_changed_bbox': [0, 0, 0, 0], 'animation_transition_count': 2}
real move     : {'animation_frame_count': 1, 'animation_changed': True,  'animation_only_changed': False, 'animation_changed_cell_count': 1, 'animation_changed_bbox': [0, 0, 0, 0], 'animation_transition_count': 1}
no animation  : {'animation_frame_count': 0, 'animation_changed': False, 'animation_only_changed': False, 'animation_changed_cell_count': 0, 'animation_changed_bbox': None,      'animation_transition_count': 0}
all_frames err: {'animation_frame_count': 0, 'animation_changed': False, 'animation_only_changed': False, 'animation_changed_cell_count': 0, 'animation_changed_bbox': None,      'animation_transition_count': 0}
```

The fourth case uses a `new_state` stub whose `all_frames` property raises, confirming the
guard added in §4 swallows it rather than propagating.

**What was NOT run here, and is the honest gap:** no live game, no harness run, no engine.
The end-to-end evidence that ACTION7 actually executes comes from job 10, which ran the
commit-(a) edits as an arm on the real bundle — 32 accepted presses, all `board_changed`,
zero `Unknown action at index 1`. **The commit-(b) animation metadata has never been run
against a live engine.** It has been syntax-checked and unit-exercised only. A reviewer with
a `taaf` environment should run one real game before trusting the six scalars in anger.

## 6. What's not done / next

Out of scope for this PR. In order, from the corpus plan:

1. **Schema + validator** — `datasets/decision-steps/SCHEMA.md` and a validator at the path
   the plan names. Plan §5 step 2 / §6.
2. **Re-scrape both replays** — neither human recording is on disk any more, so both known
   guids must be re-pulled from the replay API, and the endpoint shape verified by
   observation rather than assumed. The two known pairs are bp35 `bp35-0a0ad940` /
   `c935ca1b-dfee-4be1-9574-bf4cc80c5b89` (1,030 rows) and g50t `g50t-5849a774` /
   `4f0689d0-7d06-4be7-91ac-31cb9a800b85` (534 rows). Plan §5 step 3, which the plan calls the step that actually
   matters — the yield is in enumerating *additional* published guids, not in re-slicing the
   two we have.
3. **Segment and label the v0 corpus** — plan §5 step 4.
4. **Live-run the animation metadata**, per §5 above.

Also worth flagging for the reviewer: the corpus plan's §5 step 1 scopes the repair to "the
ACTION7 hunks only" and explicitly holds the animation half. This PR ships both, as two
commits. If that is not wanted, commit (b) reverts cleanly on its own — that is why the
`prompts.py` hunk was split.
