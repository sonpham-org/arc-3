<!--
Author: Claude Opus 5 (Bubba)
Date: 15-September-2026
PURPOSE: One source-verified finding about cn04 that no agent run and no prior source read
caught: ACTION5 has two unrelated meanings, selected by an unrendered property of the part it
is applied to, and levels 1-4 teach the wrong one with perfect consistency before level 5
breaks it. Written here because it is a harness/agent finding, not a game-authoring one --
it names a failure mode the agent cannot recover from by trying harder, and it is the first
real falsified-prediction episode available to the decision-step corpus. Carries the cited
source lines so a fresh session does not re-derive them.
SRP/DRY check: Pass -- 2026-09-14-decision-step-corpus-v0-plan.md owns the corpus plan and
its build order; this owns one game's mechanic and what it implies for step 4. The mechanic
is also proposed as a vocabulary axis in autoresearch-arena arc3games/
LATENT_MECHANICS_IN_THE_PUBLIC_25.md (PR #29 there); this file is the source read, that one
is the axis proposal. Neither restates the other's content.
-->

# cn04: one action, two meanings, and four levels of training on the wrong one

**Status:** finding, source-verified 15-Sep-2026. Found by a human playthrough, then confirmed
against the game source. Not found by any of the 163 published agent runs, and not found by
either of the two prior source reads of this game — the second of which **deleted** the
observation as fabricated.

---

## 1. The finding

`ACTION5` in `cn04` is a 90° rotation of the held part. That is true of **every part in every
one of levels 1 through 4**, with no exceptions.

From level 5, some parts are built as a **stack of nested variants of the same shape sharing a
single spawn anchor**. On those parts `ACTION5` **never rotates the part at all**. It steps up
the stack, so the part **grows**.

The consequence that matters is not the animation. It is that **the larger variants carry marks
the smaller ones do not have**, and the stack always opens on its smallest variant. Level 5's
yellow part shows **3 marks at its starting size and 7 at full extent**. Four of the seven marks
that must be satisfied to clear the level **are not on the board** until the part has been grown
into them.

So a solver that forms a plan from level 5's opening frame is planning against a board that is
not the board.

## 2. Source, cited

All line numbers are `docs/static/games/src/cn04-2fe56bfb/cn04.py` in this repo.

| what | where | what it says |
|---|---|---|
| the branch | `:1066-1075` | `ACTION5` → `if len(group) > 1: cycle-the-stack else: rotate(90)` |
| stack construction | `:843-858` | sprites are grouped by **shared spawn anchor** `(x, y)`, then sorted by `layer` |
| the cycle | `:1111-1135` | steps one position, **bounces** at either end rather than wrapping |
| level table | `:677-775` | which parts exist, where they spawn |

Two details from `:843-858` are load-bearing. First, the group is ordered by `layer`, not by the
order parts appear in the level list — level 6 lists its stack largest-first, so list order is
not the cycle order. Second, in **every** stack the only member with `visible=True` is
`layer=1`, and `layer=1` is always the smallest variant. That is what makes "expand it fully"
literally correct rather than merely directional.

`ACTION6` carries the same overload: clicking the body of a stacked part you are already
holding steps it, where clicking a non-stacked part you are holding releases it (`:1040-1065`).

## 3. Measured, per level

Distinct spawn anchors per level — that is, parts you can actually pick up and move:

| level | sprite entries | distinct anchors | stacks |
|---|---|---|---|
| 1 | 2 | 2 | none |
| 2 | 4 | 4 | none |
| 3 | 3 | 3 | none |
| 4 | 4 | 4 | none |
| 5 | 8 | 4 | one, 5 deep, at `(7,4)` |
| 6 | 13 | 5 | two — 6 deep at `(6,6)`, 4 deep at `(9,14)` |

Level 5's stack, ordered by `layer`, with mark counts:

| layer | visible at start | extent | marks |
|---|---|---|---|
| 1 | **yes** | 4×4 | 3 |
| 2 | no | 5×4 | 4 |
| 3 | no | 6×6 | 5 |
| 4 | no | 7×6 | 6 |
| 5 | no | 7×6 | 7 |

Body colour is `11`, which is yellow — matching the human report exactly.

## 4. Why this is a rule inversion, not a rule extension

Levels 1–4 are **four consecutive levels of perfectly consistent evidence** that `ACTION5`
means rotate. Any inductive learner — human or agent — arrives at level 5 holding that rule
with high confidence, correctly earned.

On level 5 the rule is not incomplete. It is **false**, for that part, with:

- no visual marker distinguishing a stacked part from a plain one,
- no separate action to discover (the action set is unchanged: 1–6 throughout),
- and no way to observe the withheld marks before acting, because they do not exist yet.

This is not `hidden-state-reveal`. Hidden state has coordinates you can plan to uncover. Here
there is no cell to uncover until the action creates it. **The solver has to act before it can
know, and the action it needs is the one it has four levels of evidence against.**

## 5. What this means for the harness

Stated plainly, because it is a claim about our agent and not about the game:

1. **"Try harder" cannot fix this.** More retries on level 5 with the rule `ACTION5 = rotate`
   generate more evidence that `ACTION5` does nothing useful, which is exactly what the agent
   would conclude, and it is wrong. The defect is in the hypothesis, not in the effort.
2. **Per-level summarisation is a liability here, not a saving.** Anything that compresses
   levels 1–4 into "ACTION5 rotates the held piece" hard-codes the false rule into the context
   at the moment it stops being true.
3. **Not measured:** whether our agent actually fails level 5 of cn04 for this reason. cn04's
   standing in the per-game run scores was **not** looked up for this document, and the 163-run
   numbers were not re-derived. This file claims the mechanic exists and that the induced rule
   is false; it does **not** claim to have diagnosed a specific run. That check is worth doing
   and has not been done.

## 6. What this means for the v0 decision-step corpus

`2026-09-14-decision-step-corpus-v0-plan.md` §2 wants negative→corrected pairs, and §5 step 4
notes they have to be mined from our own arm transcripts. This is the first **naturally
occurring** falsification episode we have identified in a real human run:

- a stated expectation (`ACTION5` will turn this part),
- an observation that refutes it (the part changed size, not orientation),
- and a corrected action (keep pressing to full extent, *then* plan).

The run is `cn04-2fe56bfb` / `f714032e-914d-4bb5-bc95-386dfacebca0`, recorded in
`datasets/decision-steps/first-party-replays.json`: WIN, 6 levels, 454 actions, 4 resets,
under the per-level action baseline on all six levels. Its recording is 455 rows / 6,708,302
bytes, and `data.frame` on each row is a list of grids where the settled board is `frame[-1]`.

**Not done here:** no segmentation, no labelled records, no episode boundaries. Step 4 owns
that. Two things step 4 should know before it starts on this run:

- The level-5 `ACTION5` presses are not a single decision step. The interesting step is the
  **first** one, where the expectation is refuted; the remaining presses to reach full extent
  are execution, not decision.
- ~~`segment.boundary_reason` still has no value for "a held part changed extent", and it needs
  one if this run is segmented.~~ **Both closed 15-Sep-2026:** `extent_change` and
  `episode_start` were added, and a third value, `level_advance`, followed once the segmenter
  ran on this recording's six level transitions. See
  [SCHEMA.md — Boundary reasons](../../datasets/decision-steps/SCHEMA.md#boundary-reasons).

## 7. Method note

Both prior source reads of cn04 missed this, and the second one deleted the first one's correct
observation. The first read described the part as something you "slide, turn or stretch". The
second grepped the source for a resize primitive, found none, and struck "stretch" as invented.

**There is no resize primitive and the part grows anyway**, because the growth is a sprite swap
between stacked variants. The second read was implementation-true and observation-false, and it
destroyed a correct finding.

The generalisable rule: when a player reports observed behaviour and the source shows no
primitive for it, look for a **different mechanism producing the same observation** before
concluding the report was wrong. Of the six games read in
`autoresearch-arena arc3games/OFFICIAL_GAME_STUDIES.md`, `dc22` is the only one whose checker
played the game rather than reading it, and it is the only one that found a game's missing
second half. That is not a coincidence worth ignoring.
