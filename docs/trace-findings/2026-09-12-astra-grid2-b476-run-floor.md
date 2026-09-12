<!--
Author: Claude Opus 5 (Bubba)
Date: 12-September-2026
PURPOSE: Run-level findings for g4run-astra-grid2-b476-w11-recovery-r2-20260906 — why the same
agent, same prompt, same session scores 100 on three games and ~0 on seven. Focuses on the two
floor cases the Boss pulled: sc25-635fd71a (0.0) and g50t-5849a774 (0.28). Every figure is
recomputed from the published run artifacts; every mechanic is cited to the game source in
docs/static/games/src/.
SRP/DRY check: Pass — sibling docs cover bp35, sk48 (×4), wa30 and the six-run sc25 comparison.
This one is the first run-level (not game-level) analysis and the first to trace a prompt line
back to a dropped engine field.
-->

# astra-grid2-b476 — the floor of a good run

Run: `g4run-astra-grid2-b476-w11-recovery-r2-20260906`, pass 0, 25 games.
Artifacts: `/data/<run>/run-overview.json`, `game-<i>.json`, `game-<i>-step-<n>.json`.

## 1. The run is bimodal

Scores as published, sorted:

| game | status | score | levels | actions |
|---|---|---|---|---|
| sc25 | gave_up | **0.00** | 0/6 | 634 |
| sk48 | gave_up | 0.15 | 1/8 | 445 |
| g50t | cancelled | 0.28 | 1/7 | 574 |
| bp35 | gave_up | 0.51 | 1/9 | 92 |
| cn04 | gave_up | 0.98 | 1/6 | 135 |
| lf52 | gave_up | 1.82 | 1/10 | 352 |
| wa30 | gave_up | 2.22 | 1/9 | 524 |
| su15 | gave_up | 6.95 | 3/9 | 157 |
| s5i5 | gave_up | 8.33 | 2/8 | 431 |
| ls20 | gave_up | 9.35 | 2/7 | 357 |
| ka59 | gave_up | 10.40 | 3/7 | 446 |
| tu93 | gave_up | 11.57 | 4/9 | 233 |
| tn36 | gave_up | 13.16 | 3/7 | 182 |
| m0r0 | gave_up | 14.29 | 2/6 | 139 |
| vc33 | gave_up | 21.43 | 3/7 | 301 |
| dc22 | gave_up | 21.93 | 3/6 | 300 |
| re86 | cancelled | 27.78 | 4/8 | 514 |
| sp80 | gave_up | 28.57 | 3/6 | 125 |
| ft09 | cancelled | 47.62 | 4/6 | 383 |
| r11l | gave_up | 47.62 | 4/6 | 84 |
| ar25 | gave_up | 58.33 | 6/8 | 308 |
| tr87 | gave_up | 59.50 | 5/6 | 380 |
| sb26 | **won** | 98.75 | 8/8 | 186 |
| cd82 | **won** | 100.00 | 6/6 | 104 |
| lp85 | **won** | 100.00 | 8/8 | 162 |

The three wins are also the three cheapest runs (104–186 actions). The floor games spend
352–634 actions to clear at most one level. Spend does not buy levels here; it tracks
confusion.

One property the three winners share: the **goal is rendered on screen as a reference the
agent can diff against** — cd82's reference pattern, lp85's target slots, sb26's required
colour sequence. That is a narrow observation about these three, not a theory of the whole
board. lp85 and sb26 are both sequential games, so "winners are single-frame games" is false
and is not claimed here.

## 2. sc25 — the game exposes nine legal clicks; the prompt says "MOUSE"

`sc25.py:1727-1737` enumerates the entire legal click set as `ActionInput`s with coordinates:

```python
self.bmmtkvkbcdd: list[ActionInput] = [
    ActionInput(id=GameAction.ACTION6, data={"x": 25, "y": 50}),
    ...  # nine entries: x ∈ {25,30,35} × y ∈ {50,55,60}
]
```

`_get_valid_actions()` (`:2518`) returns ACTION1-4 plus those nine. That is the whole answer
set, written down by the game, refreshed every step.

What the model is told, verbatim from this run's turn prompts:

> Valid actions right now: UP, DOWN, LEFT, RIGHT, MOUSE.

The coordinates never reach it. Trace:

- `ARC3-Inference/inference/agent/tool_agent.py:1408` formats the line via
  `_format_valid_action_line` (`:233`), whose parameter is typed `list[str] | None` —
  names only. `_normalize_valid_actions` (`:223`) only maps names between engine and model
  vocabularies; it has no coordinate path.
- The names come from `framework/solver.py:641` / `:859`, which call
  `_engine_action_names(self.game)`. That helper reads
  `game.current_state.available_actions` — the game-level id list, `[1,2,3,4,6]` for sc25 —
  and converts ids to names.
- `_get_valid_actions` appears **nowhere** in `ARC3-Inference/`. The solver already holds
  `self.game`; the coordinate-bearing set is one method call away and is not asked for.

The same `_format_valid_action_line` call site exists in five sibling harness variants
(`harnesses/baseline-v12`, `frame-full`, `ffa7g`, `ffa7g-hudpixel`, `predict-check`). Which
variant produced this run is **not recorded in the trace** — the reading above is of
`ARC3-Inference/inference/agent/tool_agent.py` on `main`.

### What that cost, measured

354 MOUSE actions executed across 176 turns. Classified against the nine legal points:

| | count |
|---|---|
| on a legal pad point | 176 |
| off the legal set | **178** |

Half of every click this run made was at a coordinate the game had already declared invalid.
The single most repeated was `MOUSE(row=3, col=3)` — a dead board corner — executed **35
times** (written 36 times in tool code). Others cluster one cell off a real pad: `(50,31)`,
`(55,31)`, `(60,31)`, `(50,37)`, `(55,37)` — 44 actions spent missing by one.

This is not a discovery problem. Its **first** click, turn 2, landed on a legal pad
`MOUSE(row=50, col=30)`. It found the pad immediately and then kept firing outside it for
another 174 turns.

From the source, off-pad clicks are the worst possible waste: the budget counter
`rrinmfkkstu` increments only inside the branch that actually toggles a pad cell
(`sc25.py:2666`), so a missed click costs **no** budget — it just burns an action against a
score that is action-efficiency weighted, and burns a turn. Nothing in the result tells the
model the click was illegal.

Two more shapes worth naming, both visible in `actionDisplay`:

- Turn 38 and turn 41 each issue `MOUSE(row=60, col=25)` **fourteen times in a row** in one
  batch; turn 34 issues `MOUSE(row=50, col=30)` twelve times. Pad cells toggle, so an even
  repeat count is a no-op by construction.
- Turns 19 and 32 sweep all nine legal points in a single batch — the model can enumerate the
  set when it chooses to; it just has no reason to believe the set is closed.

### The cheapest fix in this document

Pass the coordinate-bearing valid actions through. `_get_valid_actions()` already returns
them; `solver.py` already holds the game. Rendering
`MOUSE at (row,col) ∈ {(50,25),(50,30),…}` would have deleted 178 wasted actions from this
one game.

## 3. g50t — 73 turns to say "rewind"

Score 0.28, 1 of 7 levels, 574 actions split **279 on level 1, 295 on level 2**
(`actions_per_level`). 271,914 characters of thinking.

Mechanics from `g50t-5849a774/g50t.py`:

- `available_actions=[1,2,3,4,5]` (`:2771`). ACTION5 calls `pmlawcgvcp()` — rewind.
- `step()` (`:2782`): while an animation is playing (`jqpwhiraaj`), the agent's action is
  consumed by `vgwycxsxjz.step()` and the move counter `ucorwtereb` is **not** incremented.
- `tmwgfkaqxj()` advances the timer sprite one cell on every *even* counted action — one cell
  per two counted actions, with animation-consumed actions free.

First mention of each concept in the reasoning stream, by viewer step (of 109):

| concept | first step | level | count |
|---|---|---|---|
| "teleport" | 15 | 1 | 42 |
| "ghost" | 27 | 1 | 31 |
| "motion blur" / "debris" | 35 | 1 | 3 |
| "second player" | 61 | 2 | 2 |
| **"rewind"** | **73** | **2** | 14 |

The model's own words, in order:

> SPACE teleported the box to (8,14) — the starting position! So SPACE = … *(step 15)*

> the gray block is at rows 32-36 … So gray = "ghost/mark" of where the box has been? Or a
> "key slot"?? *(step 27)*

> This looks like animation debris of the teleporting box (motion blur trail of 'g' gray
> fading out)! … Not a hole!!! My interpretation of a "gray hole" was a mistake *(step 35)*

> The gray box is probably a second player?? *(step 61)*

> it's jumping backward to cells it previously visited, maybe reversing along its trail like
> some kind of temporal rewind *(step 73)*

It reached a correct name for the core verb on level 2, roughly 380 actions in, having spent
level 1 calling it a teleport. "Teleport to start" is not a useless model — rewind does move
the box back — but it predicts nothing about the replaying trail, which is why the gray
sprite got four successive wrong labels.

## 4. What these two share

Neither game is hard to *perceive*. Both are hard to **name**, and in both cases the name is
already written down somewhere the agent cannot see:

- sc25's legal action set is enumerated in the engine and dropped by the solver.
- g50t's verb is one of five advertised actions, and the harness names it `ACTION5` with no
  semantics. Same gap the sk48 doc found for `ACTION7`-as-undo.

Proposed, in cost order:

1. **Surface coordinate-bearing valid actions** (`solver.py` → `_get_valid_actions()`).
   Mechanical, no prompt change, deletes half of sc25's actions.
2. **Tell the model when an action was rejected or was a no-op.** Nothing currently
   distinguishes "clicked a dead corner" from "clicked a pad".
3. **Name the non-directional actions as unknown verbs to be identified early**, rather than
   leaving `ACTION5`/`ACTION6`/`ACTION7` as opaque ids. Three games now (sk48, sc25, g50t)
   lost their run to an unnamed verb.

## Caveats

- n = 1 run for both games. The six-run sc25 comparison is the sibling doc
  `2026-09-12-sc25-sigil-caster-six-runs.md`.
- Harness variant for this run is unrecorded; line numbers are from
  `ARC3-Inference/inference/agent/tool_agent.py` and `framework/solver.py` on `main`.
- Whether the arcengine API exposes the coordinate-bearing valid actions over the wire was
  **not** verified — only that this repo never calls `_get_valid_actions()` and that the game
  objects define it (13 of the 25 public games do).
- Click classification counts executed actions parsed from `actionDisplay`, not tool-source
  text; the two differ (35 executed vs 36 written for `(3,3)`).
