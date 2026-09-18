<!--
Author: Claude Opus 5 (Bubba)
Date: 15-September-2026
PURPOSE: Comparison of the 11 ARC-3 Kaggle prompt-arm notebooks (job0-job10, user markbarney)
that completed 12-14 Sep 2026. Records each arm's label, runtime settings, aggregate and per-game
scores, pass-level variance, and an honest verdict on whether any arm's lead is distinguishable
from noise. Also records two comparability traps found in the matrix. Raw numbers included so
nobody has to re-download from Kaggle.
SRP/DRY check: Pass - no prior arm-matrix comparison doc existed; checked docs/*arc3* first.
-->

# ARC-3 Kaggle arm matrix - 11 notebooks, read 15-Sep-2026

Model under test: `Qwen/Qwen3.8-Flash-Next-NVFP4` (offline vLLM, 7-way game concurrency).
All arms are **system-prompt variants**. None of them patch harness code.

## Runtime settings - identical across job1-job10

`lanes=7 passes=4 per_game_s=1980.0 budget_s=7920.0 concurrency=7`, verified from each
notebook's own `EXP_SETTINGS` log line. A stale comment in the sources claims 7920s/game against
a 32400s budget - that text is wrong, the printed settings are what ran.

## TRAP 1 - job3 and job5 ran a DIFFERENT, DISJOINT game set

Their high scores (6.00 and 4.99) are an easier board, not a better arm. Zero overlap:

- 8-job set: `bp35-0a0ad940`, `g50t-5849a774`, `lf52-271a04aa`, `ls20-9607627b`, `sk48-d8078629`, `tn36-ef4dde99`, `wa30-ee6fef47`
- job3/job5 set: `cd82-fb555c5d`, `cn04-2fe56bfb`, `ka59-38d34dbb`, `lp85-305b61c3`, `r11l-495a7899`, `sb26-7fbdac44`, `sc25-635fd71a`

Do not pool them. Within their own set, B(job3)=6.00 vs A(job5)=4.99, and that entire 1.01 gap
comes from one game (`lp85-305b61c3`: 20.76 vs 9.40). Every other game is tied or worse for B.
One game is not a result.

## TRAP 2 - slug names do not match arm labels

`job3-null-check` is actually `B-sparse-deletion`. `job5-null-control` is actually `A-control`.
Always read `ARM_LABEL` from the notebook source; never infer the arm from the slug.

## The comparable eight (same 7 games, same budget, 4 passes each)

| job | ARM_LABEL | aggregate | beats control | zero passes |
|---|---|---|---|---|
| job4 | C-mechanics | 1.550 | 5/7 | 12/28 |
| job2 | B-sparse-deletion | 1.216 | 5/7 | 14/28 |
| job8 | F-commit-prompt | 1.216 | 5/7 | 13/28 |
| job7 | E-image-first-turn | 1.178 | 2/7 | 15/28 |
| job9 | G-visual-first | 1.118 | 5/7 | 14/28 |
| job6 | D-glyph-consonants | 1.042 | 2/7 | 14/28 |
| job10 | H-action7-roundtrip | 0.995 | 4/7 | 16/28 |
| job1 | A-control | 0.864 | - | 17/28 |

### Per-game scores

| game | A | B | C | D | E | F | G | H |
|---|---|---|---|---|---|---|---|---|
| `bp35-0a0ad940` | 0.15 | 0.22 | 0.10 | 0.56 | 0.56 | 0.72 | 0.38 | 0.70 |
| `g50t-5849a774` | 0.00 | 1.05 | 0.63 | 0.00 | 0.00 | 0.00 | 2.16 | 0.00 |
| `lf52-271a04aa` | 1.82 | 2.41 | 2.07 | 1.82 | 1.82 | 2.73 | 2.27 | 2.73 |
| `ls20-9607627b` | 0.20 | 1.04 | 3.10 | 2.66 | 2.68 | 2.19 | 1.53 | 2.60 |
| `sk48-d8078629` | 0.14 | 0.00 | 1.08 | 0.00 | 0.00 | 0.69 | 0.69 | 0.16 |
| `tn36-ef4dde99` | 2.08 | 2.68 | 2.41 | 0.75 | 1.53 | 0.00 | 0.00 | 0.00 |
| `wa30-ee6fef47` | 1.67 | 1.11 | 1.47 | 1.51 | 1.67 | 2.18 | 0.79 | 0.77 |

## Verdict - one weak signal, the rest is noise

- Mean per-game pass-level SD: **0.90**. Standard error of an arm mean (28 trials): **0.17**.
- Standard error of a *difference* between two arms: **0.24**.
- Full spread across all eight arms: **0.69**.

**C-mechanics (job4, 1.550) over A-control (job1, 0.864)** is a gap of 0.69, roughly **2.9**
standard errors, and C beats control on 5 of 7 games. That is a real-looking but not decisive
signal - it is the only pair in the matrix worth a follow-up.

**Everything between B (1.216), F (1.216), E (1.178), G (1.118), H (0.995) and D (1.042) is
within about one standard error of a difference. Those six arms cannot be ranked against each
other at 4 passes.** Any ordering read off that block is noise. Roughly half of all trials score
exactly 0.0, so the aggregate is dominated by whether a single pass happened to catch a win.

To separate the middle pack, passes have to go up substantially or the scoring has to stop being
this zero-inflated. Re-running the same 4-pass design will produce a different ranking.

## job10 (H-action7-roundtrip) - ACTION7 already executes on Kaggle

This arm's system prompt tells the model ACTION7 is a 'valid, executable game action'.
It scored 0.995 - indistinguishable from control.

The notable part is in the transcripts, not the score: ACTION7 calls came back
`{'board_changed': True, 'done': False, ...}` with real scores. **On the Kaggle harness ACTION7
executed.** So the registration fix merged today in `sonpham-org/arc-3` PR #9 (commit `d5339da`)
addresses the local inference harness; the Kaggle notebook path was already able to fire ACTION7.
Worth confirming which harness revision the notebooks actually vendor before we claim the merge
changed anything about these numbers.

## job0

2-game, 1-pass smoke test (0.181). Not an experiment arm. Ignore it in any comparison.

## Not verified

- No check of which commit of the inference harness each notebook vendored.
- The SE figures treat the 28 trials as independent; with 7 games x 4 passes and heavy
  zero-inflation that is a rough approximation, not a proper test. It is good enough to show
  the middle pack is unseparable, which is the actual conclusion.

