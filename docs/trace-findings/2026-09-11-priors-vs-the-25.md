# What we tell the model, checked against all 25 official games

All 25 official game sources are in this repo under `docs/static/games/src/`. Every number
below was measured across those 25 files, not inferred from traces.

Prompt text quoted from the live system prompt in run
`g4run-cleanrem132-w11-r3-20260909`.

## 1. "boards are presented as 64 x 64 color grids"

> - In this environment, boards are presented as 64 x 64 color grids rendered with ARC
>   color symbols.

True of the **frame**. False of the **board**.

| | games |
|---|---|
| every level declares `grid_size=(64,64)` | **13 of 25** |
| coarser or mixed | 12 |
| grid size **changes between levels** | 7 (ka59, m0r0, tu93, vc33, lp85, dc22, sp80) |

Examples: `bp35` is **8×8** at every level. `lf52` is 8×8. `m0r0` runs 11×11 → 13×13 →
15×15. `ka59` runs 45×45 → 54×54 → 63×63. `lp85` uses five different sizes.

The frame handed to the model does appear to be 64×64 throughout — verified directly on
bp35, where every row of every frame is 64 characters. So an 8×8 board arrives as a 64×64
image at 8 frame-pixels per logical cell, and the model, told it is looking at a 64×64
grid, reasons at eight times the resolution of the actual game state.

This is not abstract. From the bp35 trace, turn 2:

> the player sprite moved from cols ~19-22 to cols ~25-28 → 6 columns to the RIGHT. ...
> Hmm, that's a big step. Maybe the sprite is 4x4 with black outline; moving 6 cols per
> action? **Or maybe the "sprite" is actually... hmm.**

It is rediscovering the cell pitch, by hand, mid-run, and is not confident when it
finishes. Nothing in the prompt tells it that a lattice exists, and seven games change
that lattice underneath it between levels.

Notably, the `astra-fctx` harness's `vision` library ships `lattice(): spacing/origin
proposals` — a lattice detector, present in exactly the variant that does best on sk48 and
absent from the others.

## 2. "do not get distracted by" the timer bar

> - In many games, a long horizontal or vertical line near an edge is a timer or
>   remaining-steps bar. It often shrinks or changes each step. If you identify such a bar,
>   do not get distracted by it or treat it as core gameplay state unless there is concrete
>   evidence that it interacts with the puzzle mechanics.

**21 of 25 games decrement a move budget and call `lose()` at zero.**

That bar is not a distraction. In 84% of the corpus it is the loss condition, and the
scoring function is `min(human_actions / agent_actions, 1.0)` squared — so the bar is also
a live readout of the thing the score is made of. "Do not treat it as core gameplay state"
is advice to ignore both the loss condition and the score.

sk48 makes it concrete: 196 moves per level, decremented only by the four direction
actions. Click and undo are free. An agent that knew that would explore differently.

## 3. Click: 19 of 25 games use it, and we say one sentence about it

> - For `MOUSE`, pass `row` and `col` integer arguments. `row` is vertical position, `col`
>   is horizontal position.

| | games |
|---|---|
| reference `ACTION6` (MOUSE/click) | **19 of 25** |
| contain sprites tagged `sys_click` (a specific thing that must be clicked) | 11 |

That single sentence is the entire guidance, and it describes the argument format, not the
semantics. Every trace read so far treats a click as "actuate the thing at this cell."
In sk48 a click does not actuate anything — it **transfers control to a different
skewer**, and one of its two legal targets is the head's twin down in the bottom strip,
which the same prompt block tells the model never to click through.

## 4. ACTION7: 6 of 25 games use it, and we say nothing at all

`ACTION7` appears in the source of 6 of the 25 games (ar25, bp35, lf52, sb26, sk48, su15).
The prompt never mentions it. In sk48 it is **undo**, and it costs no budget.

Every sk48 trace read so far had `ACTION7` in its advertised valid-action list. None
identified it. In a game whose difficulty is ordered, irreversible-looking stack
manipulation, free undo is the single most valuable affordance on the console, and it went
unused in every run.

## The pattern

The visual-game guidance is a list of appearance-based priors generalised from a few
games, asserted without evidence gates. Measured against the corpus they were written for:

| prompt claim | holds for |
|---|---|
| boards are 64×64 | 13 / 25 |
| the edge bar is a distraction | 4 / 25 (it is a loss condition in 21) |
| click semantics (unstated) | 19 / 25 games use click |
| `ACTION7` (unmentioned) | 6 / 25 games use it |

Three cheap changes, in order of expected value:

1. **Stop asserting 64×64. Tell it to find the lattice.** One instruction to estimate cell
   pitch and origin from the frame, and to re-estimate it on level change, addresses seven
   games that resize and every game whose logical board is coarser than its render.
2. **Reframe the bar.** It is the move budget and it kills you in 21 of 25 games. Say that,
   and say which actions consume it, rather than telling the model to look away.
3. **Document the action space honestly.** Click may select rather than actuate; `ACTION7`
   exists, may be undo, and may be free. Two sentences.

Everything here is checkable: sources in `docs/static/games/src/`, prompt text in
`ARC3-Inference/inference/agent/prompts.py`.
