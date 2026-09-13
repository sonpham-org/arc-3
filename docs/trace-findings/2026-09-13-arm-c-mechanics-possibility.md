# Arm C — the mechanics-possibility prompt

**Date:** 13-September-2026
**Author:** Claude Opus 5 (Bubba)
**Status:** built and verified, not launched. Runs after job 2 (arm B) and job 3 (null check).

## What it is

Six bullets appended to `GAME_OVERVIEW_ADDENDUM`, on top of the arm B deletions. Every
line is phrased as a *possibility*, never as a diagnosis of the game in front of it:

- the visible board may be a window onto a larger world, and that window can move
- what you control may change; an action may hand control to a different object
- deciding state may not be drawn on the board (carried, collected, or from an earlier attempt)
- order can matter as much as position
- a solved thing can come un-solved, and parts of the board may act on their own
- control may be indirect (drag-by-proxy, or values read together as a code)

Each names a mechanic the public 25 actually exercise and the prompt has no word for —
see `autoresearch-arena/arc3games/LATENT_MECHANICS_IN_THE_PUBLIC_25.md`. Six of the eight
mechanics in that doc sit in our bottom seven; our three best games exercise none of them.

## Why stacked on B rather than against the control

They fix different defects. Deletion removes false priors (the HUD rule, the 64x64
assertion, "puzzle"). Arm C removes a false *ceiling* — the prompt never admits these
regimes exist, so the agent never tests for them. lf52 is the proof case: reading level 1
as peg solitaire is correct; nothing tells it the world could be wider than the frame.

Cost of stacking: if C beats B we cannot attribute the gain to C alone without a
C-minus-deletion arm. Accepted deliberately — B is measured on its own in job 2, so
`A -> B -> C` is an ordered ladder, and the B-to-C delta is the quantity of interest.

## Why this survives the sparseness objection

The earlier "the bar is your move budget" idea died because it is a claim about the
screen, and it is false on four of the 25 games. These lines make no claim about any
particular game — they widen the hypothesis space instead of narrowing it. Risk is that
it becomes a checklist and the agent starts seeing ordered-carriage everywhere;
mitigation is possibility phrasing and a hard six-line cap.

## Build and verification

`kaggle/experiments/sparse-deletion/build_bundles.py` is new and now the single
definition of what each arm changes to the control bundle. Previously the arm B upload
was hand-patched with nothing in the repo recording the edit.

Verified before upload:

- the builder reproduces the **shipped arm B bundle byte-identically** from the control
  bundle, so the recorded deletion list is provably the one that ran in job 2
- arm B diff against control is exactly four edits: two HUD paragraphs, `64 x 64`,
  and `puzzle`/`puzzles` in two places. Nothing else. Nothing added.
- arm C diff against arm B is exactly the six added lines, +1,089 chars
- probes assert in-process before a game is played: all four deleted strings absent in
  B and C, present in A; the mechanics block present only in C, and the run raises
  rather than spend two hours producing a meaningless number

Bundle: `markbarney/taaf-duck-mechanics-possibility`. Notebook: `arc3-job4-mechanics`,
same shape as jobs 1-3 — bottom seven, 4 passes, 1980s per game, 7920s budget.

## Pre-registered prediction

The gain, if any, shows on the two moving-frame games (bp35, lf52) and the two
carried/contested games (ls20, wa30) before it shows anywhere else. g50t is the sharpest
single test: its mechanic is "your previous run replays against you," which is the
carried-state bullet almost verbatim, and it scored 0.00 on all four control passes.

## Known caveat carried forward from job 1

Pass 3 is truncated by the outer budget (4 x 1980 = 7920 exactly fills the 132 minutes,
leaving nothing for the ~9 minutes of vLLM boot on the same clock). Arms A, B, and C all
carry the same flaw, so the comparison stays honest; the primary A/B/C comparison uses
passes 0-2 only, n=3.
