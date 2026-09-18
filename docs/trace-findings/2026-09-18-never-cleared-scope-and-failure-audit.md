<!--
Author: Claude Opus 5 (Bubba subagent)
Date: 18-September-2026
PURPOSE: Two things. (1) A cross-run check of which of the official 25 ARC-3 games have ever had a
level cleared, built from every executed run I can read: the four qwen38-27b runs on gx10-a108, the
nine Kaggle prompt-arm job outputs on disk, and the two full Flash-Next runs in a second run tree on
a108. This corrects an earlier claim that six games "never cleared a level" - no game of the 25 has
never cleared a level, and the honest answer depends entirely on which model and which runs you
scope to. Stated per scope below. (2) A per-game failure audit of the games that never
cleared on a108 under qwen38-27b, identifying the one turn where each run went wrong and assigning
one failure bucket, quoting the transcript line that forces the call.
Inputs: ARC3-Inference run artifacts and transcripts on a108 (read-only, no new inference),
~/arc3-job-output/* Kaggle job artifacts, kaggle/experiments/sparse-deletion/*.ipynb for the model
pin, humanPlay.generated.json for the Boss's level-1 action counts, and the source-cited
mechanicsBreakdown in arc-explainer/shared/arc3Games/<game>.ts.
SRP/DRY check: Pass - no existing per-game gameplay failure audit of these games. The cross-run
scope section overlaps docs/trace-findings/2026-09-17-the-slippery-seven.md, which established the
model-swap explanation; that finding is cited, and §0 adds the per-run clear table it does not have.
-->

# ARC-3 failure audit: which games have never cleared a level, and why the ones on a108 fail

**Snapshot: 18-September-2026, 14:06 ET.** One of the runs below (`20260918_113435_qwen38-27b-mp-compact-p1`)
was **still executing** when these numbers were read. Its unplayed games are marked, not counted.

## 0. Scope first - the "never cleared a level" claim, checked

### 0.1 What the claim was, and why it does not hold

The brief for this audit said six games - `dc22`, `g50t`, `sc25`, `sk48`, `tn36`, `tr87` - had
never cleared a level. A correction then arrived saying that was false because `g50t`, `sk48` and
`tn36` score on the Kaggle arms.

**Both statements need scoping, and the correction is wrong about what it proves.** The eleven
Kaggle prompt-arm notebooks pin a **different model**. Checked directly, the only `RadixArk/` or
`unsloth/` model string appearing in any of the thirteen notebooks in
`kaggle/experiments/sparse-deletion/` (jobs 0-12) is:

```
RadixArk/Qwen3.8-Flash-Next-NVFP4
```

Every a108 run below is `model=qwen38-27b-nvfp4` (`unsloth/Qwen3.8-27B-NVFP4`), read from each
run's own `run_config.json`. So a Kaggle clear on `g50t` is evidence that **Flash-Next** clears
`g50t`. It is not evidence that the 27B ever did. This was already established in
`docs/trace-findings/2026-09-17-the-slippery-seven.md` §3 ("the Kaggle arms run a different model
... Different checkpoint. The arm labels are not what moved these games"); I re-verified it from
the notebook sources rather than carry it over.

The original six-game claim was also wrong twice over, for reasons neither the brief nor the
correction had. **`tn36` cleared a level on a108, under the 27B, in the run that is executing right
now.** And a second run tree on a108 - `/home/son/flash-next-runs/`, missed on the first pass of
this audit - contains two full 25-game Flash-Next runs in which **every one of the 25 games clears
at least one level, `dc22` and `tr87` included** (§0.5). There is no game in the set that has never
cleared.

### 0.2 Method

Three corpora, all read the same way - each pass's `artifacts/<game>_p<N>_viewer_data.json`,
taking `levels_completed`, `final_score` and `sum(actions_per_level)`. A pass counts as **executed**
only if its action count is greater than zero.

| corpus | location | model |
|---|---|---|
| a108 27B runs | `a108:/home/son/GitHub/arc-3/ARC3-Inference/runs/` | `qwen38-27b-nvfp4` |
| Kaggle prompt arms | `~/arc3-job-output/<job>/` (9 jobs) | `RadixArk/Qwen3.8-Flash-Next-NVFP4` |
| **a108 Flash-Next runs** | `a108:/home/son/flash-next-runs/` (2 executed) | `RadixArk/Qwen3.8-Flash-Next-NVFP4` |

The third corpus is a separate run tree on the same box, found with
`find /home/son -maxdepth 6 -name '*_viewer_data.json'`. It is not under `ARC3-Inference/runs/` and
the first pass of this audit missed it. Its model is read from each run's served model list
(`harness/model-endpoint.json` -> `data[0].id`), not inferred from the directory name. That same
`find` turned up no other run tree on a108.

Runs excluded and why:

| run | why excluded |
|---|---|
| `20260915_230313_qwen38-27b-baseline-25g` | `games: 0`, duration 0s, no artifacts - launch failure |
| `20260916_101321_qwen38-27b-longrun-25g` | 19 of 25 games at 0 actions; the other 6 have `status=playing`, `final_score=null`, 1-5 actions. Aborted, scored nothing |
| eight `*-ft09` smoke runs (Jul + 15-Sep) | one game, `ft09`, 0-10 actions, not the 25-game catalog |

**Does `score > 0` imply at least one level cleared?** The correction asserted it; I checked it
rather than assume it. Across **459 finished pass-level rows** (157 a108 27B + 252 Kaggle + 50 a108
Flash-Next) the mapping is exact, with zero exceptions:

| | levels >= 1 | levels = 0 |
|---|---|---|
| score > 0 | **260** | 0 |
| score = 0 | 0 | **199** |

So on this corpus the two are interchangeable. Stated as an observed regularity over 459 rows, not
as a rule of the scoring function. Seven further rows - the games still in flight in the live
mp-compact run - carry `final_score: null` with `levels_completed` already populated; they are
excluded from this check and used only for the clear counts in §0.3, where they are marked.

### 0.3 a108, qwen38-27b - every executed pass, all 25 games

Cells are **levels cleared** per pass. `x` = pass exists but ran 0 actions; `-` = that game has not
been played in that run yet (the mp-compact run is live).

| game | baseline 15-Sep | massdata p0/p1/p2/p3 | compact 17-Sep | mp-compact 18-Sep (live) | cleared in |
|---|---|---|---|---|---|
| `ar25-0c556536` | 1 | 2/2/1/1 | 1 | 1 | all four |
| `bp35-0a0ad940` | 0 | 0/1/0/0 | 0 | 0 | massdata |
| `cd82-fb555c5d` | 0 | 1/1/1/0 | 0 | - | massdata |
| `cn04-2fe56bfb` | 1 | 0/0/1/1 | 1 | 0 | base, mass, compact |
| **`dc22-fdcac232`** | 0 | 0/0/0/0 | 0 | - | **none** |
| `ft09-0d8bbf25` | 0 | 2/2/2/2 | 1 | - | mass, compact |
| **`g50t-5849a774`** | 0 | 0/0/0/0 | 0 | - | **none** |
| `ka59-38d34dbb` | 0 | 0/0/1/1 | 1 | 0 | mass, compact |
| `lf52-271a04aa` | 0 | 1/1/1/0 | 1 | 1 | mass, compact, mp |
| `lp85-305b61c3` | 1 | 1/1/1/1 | 1 | 1 | all four |
| `ls20-9607627b` | 1 | 0/1/1/0 | 1 | - | base, mass, compact |
| `m0r0-492f87ba` | 0 | 0/0/0/0 | 1 | 0 | compact |
| `r11l-495a7899` | 1 | 1/1/0/1 | 0 | 1 | base, mass, mp |
| `re86-8af5384d` | 1 | 2/1/2/2 | 1 | - | base, mass, compact |
| `s5i5-18d95033` | 1 | 0/1/1/1 | 0 | - | base, mass |
| `sb26-7fbdac44` | 1 | 1/1/4/1 | 4 | - | base, mass, compact |
| **`sc25-635fd71a`** | 0 | 0/0/0/0 | 0 | 0 | **none** |
| **`sk48-d8078629`** | 0 | 0/0/0/0 | 0 | - | **none** |
| `sp80-589a99af` | 1 | 1/0/1/0 | 0 | 0 | base, mass |
| `su15-1944f8ab` | 1 | 1/1/1/1 | 1 | - | base, mass, compact |
| `tn36-ef4dde99` | 0 | 0/0/0/0 | 0 | **1** | **mp-compact only** |
| **`tr87-cd924810`** | 0 | 0/0/0/0 | 0 | - | **none** |
| `tu93-0768757b` | 0 | 1/1/0/1 | 0 | 1 | mass, mp |
| `vc33-5430563c` | 2 | 2/2/1/2 | 1 | 2 | all four |
| `wa30-ee6fef47` | 0 | 0/0/1/0 | 1 | 0 | mass, compact |

164 pass rows, every one with actions > 0; 157 are finished and scored, 7 are mid-game in the live
run (`ar25`, `ka59`, `m0r0`, `sc25`, `sp80`, `tu93`, `vc33` - their level counts can still rise).
**On a108 under the 27B, five games have never cleared a level: `dc22`,
`g50t`, `sc25`, `sk48`, `tr87`.** Of those five, four (`dc22`, `g50t`, `sk48`, `tr87`) have not yet
been reached by the live mp-compact run, so that statement is provisional for them and could change
within hours. `sc25` has already played in that run and scored 0 in 15 actions.

### 0.4 Kaggle, Flash-Next - every executed pass, nine jobs on disk

Same units. Jobs 1, 2, 4, 6, 7, 8, 9, 10 share one 7-game set; job 5 is the disjoint set.

| game | job1 A | job2 B | job4 C | job5 A' | job6 D | job7 E | job8 F | job9 G | job10 H | cleared |
|---|---|---|---|---|---|---|---|---|---|---|
| `bp35` | 1/0/0/0 | 1/0/1/0 | 1/0/0/0 | - | 1/1/0/0 | 0/1/0/0 | 1/1/1/0 | 1/1/1/0 | 1/0/1/0 | yes |
| `g50t` | 0/0/0/0 | **1/1/0/0** | 0/0/1/0 | - | 0/0/0/0 | 0/0/0/0 | 0/0/0/0 | **1/1/1/0** | 0/0/0/0 | **yes** |
| `lf52` | 1/1/1/1 | 1/2/1/1 | 1/2/1/1 | - | 1/1/1/1 | 1/1/1/1 | 1/2/1/1 | 1/1/2/0 | 1/1/2/1 | yes |
| `ls20` | 0/0/1/0 | 1/1/1/0 | 1/1/1/1 | - | 1/1/1/1 | 0/1/1/1 | 1/1/0/1 | 1/0/1/0 | 1/1/0/1 | yes |
| `sk48` | 0/0/1/0 | 0/0/0/0 | 0/1/1/0 | - | 0/0/0/0 | 0/0/0/0 | **1/0/0/0** | **1/0/0/0** | 1/0/0/0 | **yes** |
| `tn36` | **2/0/0/0** | 0/0/2/0 | **2/0/0/0** | - | 0/1/0/0 | 1/0/1/0 | 0/0/0/0 | 0/0/0/0 | 0/0/0/0 | **yes** |
| `wa30` | 1/1/0/1 | 1/1/0/0 | 1/1/1/0 | - | 1/1/1/0 | 1/1/1/0 | 1/1/1/1 | 1/0/1/0 | 0/1/1/0 | yes |
| `cd82` | - | - | - | 1/2/1/1 | - | - | - | - | - | yes |
| `cn04` | - | - | - | 1/1/1/1 | - | - | - | - | - | yes |
| `ka59` | - | - | - | 2/1/1/1 | - | - | - | - | - | yes |
| `lp85` | - | - | - | 1/1/4/2 | - | - | - | - | - | yes |
| `r11l` | - | - | - | 1/2/1/1 | - | - | - | - | - | yes |
| `sb26` | - | - | - | 1/1/1/1 | - | - | - | - | - | yes |
| **`sc25`** | - | - | - | **0/0/2/0** | - | - | - | - | - | **yes** |

**`dc22`, `m0r0` and `tr87` appear in no Kaggle job at all** - they are not in either 7-game set.
Jobs 3, 11 and 12 were not pulled to this machine and are not in this table; the job 11/12 per-pass
clears in `2026-09-16-jobs-11-12-reset-guard-result.md` add, across those two jobs, `g50t` 4 clears
(1/0/1/0 and 0/1/0/1), `sk48` 1 (0/0/0/0 and 0/0/1/0) and `tn36` 4 (0/1/2/0 and 0/1/0/0) - all
Flash-Next, all consistent with the rows above. Those three figures are read from that write-up,
not from artifacts on this machine.

### 0.5 a108, Flash-Next - the run tree that settles it

`/home/son/flash-next-runs/` holds seven timestamped directories; two of them executed a full
25-game pass (the other five have no `harness/artifacts`). Both are `duck-harness-kaggle`, one
pass, 25 games, 11-12 hours each, served model `RadixArk/Qwen3.8-Flash-Next-NVFP4`. Cells are
levels cleared, with total actions in parentheses.

| game | 05-Sep 03:07Z | 05-Sep 15:53Z |
|---|---|---|
| `ar25-0c556536` | 3 (273a) | 5 (181a) |
| `bp35-0a0ad940` | 1 (244a) | 1 (78a) |
| `cd82-fb555c5d` | 0 (101a) | 2 (133a) |
| `cn04-2fe56bfb` | 1 (119a) | 0 (124a) |
| **`dc22-fdcac232`** | **2 (133a)** | **2 (179a)** |
| `ft09-0d8bbf25` | 2 (143a) | 4 (220a) |
| `g50t-5849a774` | 1 (131a) | 0 (86a) |
| `ka59-38d34dbb` | 2 (240a) | 1 (275a) |
| `lf52-271a04aa` | 1 (269a) | 1 (289a) |
| `lp85-305b61c3` | 5 (172a) | 5 (76a) |
| `ls20-9607627b` | 1 (103a) | 1 (165a) |
| `m0r0-492f87ba` | 2 (109a) | 2 (151a) |
| `r11l-495a7899` | 2 (36a) | 1 (24a) |
| `re86-8af5384d` | 2 (600a) | 4 (273a) |
| `s5i5-18d95033` | 1 (42a) | 2 (80a) |
| `sb26-7fbdac44` | 1 (158a) | 1 (129a) |
| `sc25-635fd71a` | 3 (405a) | 2 (285a) |
| `sk48-d8078629` | 1 (134a) | 0 (95a) |
| `sp80-589a99af` | 1 (110a) | 1 (202a) |
| `su15-1944f8ab` | 3 (102a) | 1 (86a) |
| `tn36-ef4dde99` | 2 (453a) | 1 (132a) |
| **`tr87-cd924810`** | **2 (115a)** | 0 (39a) |
| `tu93-0768757b` | 4 (108a) | 4 (122a) |
| `vc33-5430563c` | 3 (66a) | 3 (151a) |
| `wa30-ee6fef47` | 1 (335a) | 3 (332a) |

**Every one of the 25 games clears at least one level in at least one of these two runs.** That
includes `dc22` and `tr87`, the two games that have never been run on Kaggle and never scored on the
27B. It also matches the catalog figures cited in `2026-09-17-the-slippery-seven.md` §3 (Flash-Next
`dc22` mean 9.10, `tr87` 13.46), which I could not re-fetch - these two runs are direct evidence for
the same thing.

Note the action counts against §0.3: Flash-Next spends 133-179 actions on `dc22` where the 27B
spends 20-86, and 115 on `tr87` where the 27B spends 17-126. The two runs here are also ~12 hours
for 25 games against the 27B runs' 90-230 minutes per game, so this is not a matched-clock
comparison and nothing about *why* should be read off it here.

### 0.6 The answer, stated per scope

- **No game of the 25 has never cleared a level.** Across all 459 executed passes in §0.3, §0.4 and
  §0.5, every one of the 25 games has at least one clear. The six-game claim in the brief does not
  survive at any scope wider than one model on one box.
- **Never cleared under `qwen38-27b` on a108:** `dc22`, `g50t`, `sc25`, `sk48`, `tr87` - five, not
  six, and provisional for four of them while the 18-Sep run is still executing. **This is the only
  scope at which anything like the original claim is true**, and it is a statement about the 27B,
  not about the games.
- **`tn36` is off that list too.** It cleared under the 27B on a108 on 18-Sep: 1 level, score 1.09,
  66 actions - see §0.7.
- **Under Flash-Next every one of the six clears**: `g50t`, `sc25`, `sk48`, `tn36` on Kaggle and on
  a108; `dc22` and `tr87` on a108 (§0.5), the only two that have never run on Kaggle at all.
- So the correct sentence is **"never cleared a level in the four qwen38-27b runs on gx10-a108"**,
  and it covers five games. Any shorter version of it is wrong.

`m0r0` failed the same way in the mass-data run and is not audited below because it cleared a level
in the compact run (1 level, score 3.31) - the same inclusion test, applied consistently.

### 0.7 What differs between the runs that cleared and the runs that did not

For `g50t`, `sk48`, `tn36` on Kaggle versus a108, the answer the data supports is **the model**:
`RadixArk/Qwen3.8-Flash-Next-NVFP4` against `qwen38-27b-nvfp4`, verified from the notebooks and the
run configs. It is **not** the prompt arm. Per `2026-09-15-arc3-kaggle-arm-matrix.md` the mean
per-game pass-level SD is 0.90 with a standard error of 0.24 on a difference between arms, and on
these three games clears appear and vanish between arms that are statistically indistinguishable -
`tn36` clears 2 levels on the *control* arm (job1 p0) and 0 in all four passes of arms F, G and H.
**The model is separable; the arms are not.** Anything more specific is not supported here.

For `tn36`'s clear on a108, the comparison is sharper and points somewhere else entirely. The
compact run (17-Sep, `tn36` 0 levels) and the mp-compact run (18-Sep, `tn36` 1 level) are the same
configuration:

- `diff -rq` of the two runs' vendored `src/` trees: **no differences** (the same command run
  against baseline-vs-compact does report differences, so the comparison is live).
- The `[SYSTEM]` prompt block extracted from each run's `prompts/<game>_p0.log`: **byte-identical**,
  md5 `33739607e360a73af309a5a66ed74b63`, checked on four games.
- Same `model`, `max_runtime_minutes_per_game=90`, `concurrent_jobs=7`, `n_passes=1`.

Identical harness, identical prompt, different sampler draw. That is the seed-variance result of
`2026-09-17-seed-variance-and-the-sb26-jackpot.md` landing on a second game. And the clear itself
does not show comprehension - the model wrote, on reaching level 2:

> "Level 2 reached! ... the last transition was a ball click (55,36) - level 1 completed with
> `MOUSE(row=55, col=36)`! So the ball click was the 'submit' action ... So the goal = make the
> tray all black (all B), then click the ball to submit!"

It learned the rule *from* the clear, after the fact. `run button`, `runs the program` and
`execute the program` return zero hits in that transcript, exactly as in the six passes audited
below. **`tn36` is off the never-cleared list; the failure analysis below still describes what
happens on the passes that do not clear.**

---

# Per-game failure audit

Scope of this half: the **six games named in the original brief**, on the a108 27B runs available
when the audit was done - the baseline pass, the four mass-data passes and the compact pass, six
passes each. Five of the six are the never-cleared-on-a108 set from §0.3. `tn36` is kept because
its six audited passes all failed and the analysis of them stands; its 18-Sep clear is in §0.7.
`m0r0` is excluded per §0.6.

## Conventions

**Turn numbering.** `analysis_step` repeats within a transcript (dc22 baseline has five blocks at `analysis_step=9`), so a bare analysis_step is not a unique address. Turns below are numbered **T1..Tn by transcript block order**, with the raw header given alongside: `T17 (analysis_step=9, 03:24:48)`. Grep the timestamp to find the line.

**Boss action counts.** `humanPlay.generated.json` holds several runs per game with a wide spread (tn36: 51 / 9 / 7; tr87: 24 / 24 / 30 / 37) - the later ones are replays of a game he already knew. Headline number below is the **first listed run**; the best run is given in parentheses where it differs. `games[gid].baselineActions[0]` (ARC's own level-1 baseline) is given for scale.

**Primary evidence** is the baseline pass (`20260915_230835_qwen38-27b-baseline-25g`), read in full. The compact pass and the four massdata passes were scanned to check whether the same failure repeats; where a pass diverges, it is said so.

## Structural fact that frames all six: every audited pass died on the wall clock

All 36 passes (6 games x 6 passes) ended the same way - mid-request, at level 1, with `request_error: HTTPConnectionPool ... Read timed out`. The harness sets the HTTP read timeout to exactly the run's remaining seconds, so the timeout value in the last line is the clock that was left. Checked arithmetic on the baseline pass:

| game | first turn | last turn | final read timeout | first + 5400s |
|---|---|---|---|---|
| dc22 | 02:08:36 | 03:34:56 | 219.7 | 03:38:36 (= 03:34:56 + 220) |
| g50t | 02:08:36 | 03:36:20 | 135.9 | 03:38:36 |
| sc25 | 00:38:36 | 01:53:58 | 877.9 | 02:08:36 |
| sk48 | 02:08:36 | 03:38:07 | 29.4 | 03:38:36 |
| tn36 | 23:08:36 | 00:37:03 | 93.5 | 00:38:36 |
| tr87 | 03:38:36 | 05:00:47 | 469.6 | 05:08:36 |

Baseline cap is 5400s (90 min) per game. Massdata ran four passes concurrently against one server under a 13800s cap and every pass in a batch died at the same absolute wall time (e.g. all four 10:27:25 starts terminated at 14:17:24), which is why several massdata transcripts show 3000+ second timeouts - that is one model still generating when the shared deadline hit, not spare budget.

So "the run ended" is true of all six and therefore classifies none of them. The bucket has to come from the **state of the world model at the last turn**. On that test, **no game qualifies for bucket A**.

The second structural number: the model burns most of its turns not acting. Inspection-only turns (the harness nags "inspected the frame but did not execute `action(...)`") were 12 of 20 turns on dc22 and 12 of 16 on g50t. At roughly 4-5 minutes of wall clock per turn, that is the throughput ceiling behind the low action counts.

---

## dc22 - Bucket C (GUESSED AND NEVER CHECKED)

**Turn that forces it: T3 (analysis_step=3, 02:17:53).**

Level-1 mechanics that were in play (`dc22.ts`, all with no `introducedOnLevel`, so all live on level 1): arrows move the small green square 2 cells onto floor only; the goal is to *step onto the small yellow square*; the black panel on the right holds a red and a blue button; the blue button flips blue tiles between solid blue (floor) and blue checkered (not floor); level 1 draws a white outline around both panel buttons as a hint, which disappears on the first press.

At T3 the model enumerated candidate goals and put the yellow square on the list:

> "Given the free 2D sliding, the goal might be: move the green block to specific target locations. Which targets? Candidates: the checker (goal), the yellow 2x2 (goal?), the red block, the blue block."

Over the remaining 17 turns and 18 actions it never ran the action that would test it. The only time it touched the yellow square was T11 (analysis_step=7, 02:59:14), where it clicked it - `MOUSE(row=20, col=24)` - which per the mechanics does nothing but cost a step. Not one arrow press in the run was aimed at reaching it, and the word "goal" never resolves in the transcript.

What makes this a near miss rather than a flat loss: the model *did* find both panel buttons and read the blue one correctly. At T19 (analysis_step=10, 03:30:52):

> "So all the 'c' cells of the checker became 'b' -> the entire 4x4 became solid blue!!"

That is the blue button turning the checkered tile above the green square into floor - the move that opens the pad the token was stuck on ("Token confined to pad (UP blocked at edge)", T8, analysis_step=5, 02:46:16). It made that move on its second-to-last action and the clock ran out. But it read the result as a puzzle about vanishing "white pedestals", never as "the way out is now floor", and it had no goal to walk to. That is the second half of bucket C - it *did* run the action that tested the mechanic, and misread what came back. Both clauses of C land here: the goal hypothesis sat untested for 18 actions, and the one probe that mattered was misread. **A is the runner-up but does not survive: at its own observed batching rate the model could have walked to the yellow square many times over, and chose not to try.**

- Boss level 1: **37 actions** (best run 31). ARC baseline 59. Model: **21 actions**, level 1.
- Repeats? Partly. The compact pass reached the correct goal statement - "the goal is: move the green dot to the yellow dot's position (collect), and then the level is complete?" - and still did not clear (84 steps). The baseline and massdata p2 passes never state it.
- **What would have to change:** when a goal candidate is named, spend the next action moving toward it. One arrow press is cheaper than another segmentation dump.

---

## g50t - Bucket C (GUESSED AND NEVER CHECKED)

**Turn that forces it: T12 (analysis_step=4, 02:59:47).**

Level-1 mechanics: arrows move your blue square one square along the corridors; **the fifth action is rewind** - it walks you back to the start and leaves a ghost that replays your moves; ghosts press plates; a plate holds its gate open only while something stands on it. Level 1 has two ghost slots, so it allows exactly one ghost. Without a ghost on the plate, the gate stays shut.

The model named the open question in its very first turn (T1, 02:08:36):

> "Actually, let me reconsider. The valid actions are UP, DOWN, LEFT, RIGHT, SPACE. This is a 4-directional movement game plus a space action. This strongly suggests there's a player/sprite that moves in 4 directions, and SPACE does something (maybe interact/collect/activate)."

It then solved the movement model correctly (1 logical cell = 6px, confirmed by two clean probes) and ran BFS. At T10 and again at T12 its own search told it the level was impossible as drawn:

> T10: `reachable goal? False`
> T12: `goal walkable? True reached? False`

and T13's floor map shows exactly where - the left corridor is sealed at rows 38-42, which is the gate. From that point the model had proof that no arrow sequence could win, a fifth verb it had flagged on turn 1 and never pressed, and four turns of clock left. It spent all four re-deriving the maze grid. **SPACE was never issued in the baseline pass. Total actions: 4.**

- Boss level 1: **43 actions** (best run 17). ARC baseline 78. Model: **4 actions**, level 1.
- Repeats? The mechanic is never understood in any pass, but the shape differs: 5 of 6 passes *did* press SPACE. The compact pass pressed it and misread it - "SPACE = full reset: player returns to (8,14) ... Not a red-eraser" - reading rewind-plus-ghost as a plain reset even after noting "the gray 5x5 with a black dot is a 'ghost/memory' of the player's starting position". So: baseline never tested it; the others tested it and misread it. Bucket C either way.
- **What would have to change:** a proof of unreachability should force the untested verb to the top of the queue, not trigger another pass over the map.

---

## sc25 - Bucket B (NEVER GOT THE CONTROLS)

**Turn that forces it: T5 (analysis_step=4, 00:56:35).**

Level-1 mechanics: arrows move the wizard (a 4x4 square, light blue over blue) through the maze toward a blue-bordered exit; **the wizard turns to face the way you pressed even when it cannot move**; the 3x3 dot grid at the bottom casts a spell the instant the lit dots exactly match an unlocked sigil; on level 1 the only unlocked sigil is grow/shrink (the four dots around the centre, centre off) and the grid starts with that sigil already shown in white.

The model read the maze corridor as a HUD bar and the wizard as a knob on it. At T5 it probed all four arrows and concluded:

> "So RIGHT = swapped the halves of the right knob (b/S -> S/b). Interesting."

That is the wizard being blocked and turning to face right. The evidence for the correct reading was on screen in the same output - after LEFT the probe printed `R:Sgggg|Sgggg`, i.e. the 4x4 object had vacated cols 40-42 and moved into the corridor - and the model logged it as a knob changing colour. It never recovered: "knob" appears 135 times in this transcript, "wizard" zero. At T6 it summarised: "the arrows are clearly affecting the upper bar and the green HUD bar". With no character to walk and no exit to walk to, the entire run went into the dot grid.

The bitter part is that it got the *other* level-1 mechanic exactly right. At T9 (analysis_step=7, 01:26:11) it deduced the sigil from the board's own hint - "the initial board is already telling you: paint the 4 white cells green" - and at T10 it executed a batch (left, right, bottom, undo TL, undo BR) whose final click left precisely the four dots around the centre lit. The spell fired. The model saw the grid clear to all-gray and wrote "Whoa. The matrix is now all 'g' ... something got reset." It cast the only spell on the level, did not know it, and could not have used it anyway because it had no idea a character existed.

- Boss level 1: **33 actions**. ARC baseline 36. Model: **21 actions**, level 1.
- Repeats? Yes in 4 of 6 passes - "knob" appears 135 / 129 / 72 / 10 times in baseline, massdata p2, compact and massdata p1. Massdata p0 and p3 avoid the knob framing entirely and still do not clear.
- **What would have to change:** when a 4x4 object changes its internal colour layout *and* its bounding box in the same probe, prefer "it moved and turned" over "its halves swapped". A bounding-box check on the largest non-background object after each arrow would have caught it on turn 5.

---

## sk48 - Bucket C (GUESSED AND NEVER CHECKED)

**Turn that forces it: T18 (analysis_step=13, 03:32:14).**

Level-1 mechanics: press the direction the rod points to extend it a segment, the opposite to pull it back; press a sideways direction to slide the whole rod along the rail; extending pushes a loose bead ahead of the tip, and a bead that cannot be pushed further gets skewered as the rod slides through it; the level clears when the beads on the rod, read outward from the handle, match the reference strip's colours in order (red, green, blue on level 1).

The model got partway - it saw the tip retract and drag ("LEFT both retracts the beam's endpoint AND drags the block on the beam's row leftward by 6", T16) - and then over-extrapolated from one observation. At T17 it ran `UP` twice; the printed before/after are byte-identical for every block. At T18 it read that as the rod sliding away and leaving the bead behind, which is roughly right:

> "Very interesting! The token moved up to the very top ... N stayed put (25-28, columns 18-21). So when N was docked (columns 18-21, adjacent to the token's left... or adjacent to the left edge), the beam was released from N! ... So the game is: carry blocks to the left edge and place them."

The near-correct observation is not the failure. The failure is what it built on top: a dock order ("the HUD's M, R, N, b = the desired order from top to bottom of the docked items"), committed untested as a 14-action batch - `DOWN, LEFT x4, DOWN x2, LEFT x4, UP x3` - in a single tool call without checking between steps. The result printed at the end of T18 shows every block in exactly its starting position:

> `start: {'R': (13, 16, 42, 45), 'b': (19, 22, 42, 45), 'N': (25, 28, 18, 21)}`
> `final: {'R': (13, 16, 42, 45), 'b': (19, 22, 42, 45), 'N': (25, 28, 18, 21)} 0.0 False False`

Fourteen actions, roughly a third of everything it spent on this game, moved nothing. The run ended on the next turn, so it never got to revise. The real goal - beads threaded on the rod in reference order - is never stated in the transcript.

- Boss level 1: **93 actions** (his only run; he was over ARC's baseline of 61 here too). Model: **44 actions**, level 1.
- Repeats? Yes. No pass reaches level 2; final steps across the six passes are 12 / 25 / 41 / 44 / 44 / 75, and the compact pass spent 11 of 26 turns on inspection-only calls.
- **What would have to change:** do not spend a third of the action budget on an untested world model in one batch. A two-action probe of the dock hypothesis costs 2 and refutes it just as well.

---

## tn36 - Bucket B (NEVER GOT THE CONTROLS)

> **Off the never-cleared list.** `tn36` cleared level 1 on a108 on 18-Sep in the live mp-compact
> run - 1 level, score 1.09, 66 actions - on a byte-identical harness and system prompt to the
> compact pass that scored 0. See §0.7. What follows is the six audited passes, all of which failed,
> and the mechanism is unchanged in the pass that cleared: it reached level 2 without ever
> identifying the run button, then inferred the rule from the clear.

**Turn that forces it: T18 (analysis_step=15, 00:09:09).**

Level-1 mechanics: click is the only action; the columns of switches under the board are the program (each column's switches read 1 and 2 from the top and sum to an instruction: 1 = move left, 2 = move right, 3 = move down); clicking the blue circle runs the program left to right; **a run that does not match the target sends the block straight back to its starting spot**; the budget is 60 clicks and the 61st loses.

The model found the two clickable things on the board and understood neither. It clicked the blue circle at `(55,36)` seven times across the run - that is the run button - and logged only the budget bar moving, because a failing run restores the board and the animation is gone by the next frame. It toggled the switch bars at rows 42 and 45 repeatedly. And at T18 it stated its complete control model:

> "Bottom strip: 5 'T' glyphs (bar + stem, each independently toggleable between B/w). Bottom: a blue circular blob. Only the T glyph parts respond to clicks."

Nothing in the run connects the strip to the block: it cycled through "5-slot display", "combination lock", "keypad", "5 digits to be set", "the T-strip is a keypad and the goal is a specific 10-bit pattern". The words "run button", "program" and "instruction" never appear in any of the six passes. This is the only one of the six where the model actually lost on budget rather than only on the clock - T23 (analysis_step=20, 00:27:17) reports `{'game_over': True, ...}` at step 62, one past the 61-click limit. (The harness kept issuing turns afterwards and later results read `NOT_FINISHED`; those last turns changed nothing material and the level was never cleared.)

- Boss level 1: **51 actions** (best run 7). ARC baseline 32. Model: **66 actions** and a loss at 61.
- Repeats? Yes, in all six audited passes, and it is the cleanest repeat of the set: `run button` / `runs the program` / `execute the program` return zero hits in every transcript - including the 18-Sep transcript that *did* clear a level.
- **What would have to change:** the game gives no feedback for a failing run, so the only way in is to notice that one object is a button and the strip is its argument. A probe that flips exactly one switch, presses the circle, and compares - repeated twice - discriminates. The model never ran that pairing; it always toggled and clicked in separate batches.

---

## tr87 - Bucket D (KNEW IT, FUMBLED IT)

**Turn that forces it: T14 (analysis_step=8, 04:46:53).**

Level-1 mechanics: the top half is the dictionary - each entry is a glyph on a coloured tile, a short gray line, and its translation on tiles of another colour; the bottom has the unchangeable phrase row and your answer row; left/right move the bracket, up/down cycle the glyph under it within its own 7-glyph alphabet; you win when the answer row is the phrase translated.

This run got closest of the six. By T12 it had mapped the cycle cleanly (`cycle closed after 7 UPs`, and it correctly reasoned the cycle length is 7, not 8). And at T14 it wrote down the actual mechanic:

> "Six example pairs showing a relation R (e.g., R(x) = some mapping between digit glyphs). And the player must set P_strip = R(S_strip)? That is, for each column i, the P glyph must equal the R-mapped version of the S glyph. The grid teaches R through 6 example pairs!"

That is the dictionary, correctly identified - and its per-column simplification is not merely close, it is exactly right on this level: the model's own segmentation found 12 dictionary glyphs in 6 "=" pairs, i.e. six 1-glyph-to-1-glyph entries, which is why the 5-glyph phrase maps to a 5-glyph answer column by column. It also had the reason why the phrase glyphs are never in the answer's cycle (different alphabets - it had already proved `S_in_cycle False` for slot 1 at T13 and read that as a refutation rather than as confirmation of a two-alphabet cipher). Then, having stated the right mechanic, it spent the whole of T14's tool call on a **33-action** scan - `RIGHT` plus seven `UP`s for each of slots 2 to 5 - re-measuring cycle lengths it had no further use for. That batch alone is more actions than the Boss needed for the entire level. The run ended on the next turn with the dictionary map never built and not one glyph set deliberately.

- Boss level 1: **24 actions** (his best is also 24; slowest replay 37). ARC baseline 54. Model: **55 actions**, level 1, budget 128 so budget was never the constraint - the clock was.
- Repeats? The near miss does not repeat. Other passes get further in raw steps (127, 88) but the compact pass spent 17 of 23 turns on inspection-only calls and none of the six ever assembles the glyph-to-glyph map.
- **What would have to change:** once the mechanic is stated, stop measuring. The next action after T14's paragraph should have been building the 6-entry map from pixels already in hand - zero game actions required - and then executing the translation.

---

## Summary

| game | bucket | forcing turn | model actions, level 1 | Boss, level 1 (best) | ARC baseline | one-line cause |
|---|---|---|---|---|---|---|
| dc22 | **C** guessed, never checked | T3 (analysis_step=3, 02:17:53) | 21 | 37 (31) | 59 | named the yellow square as a possible goal, never moved toward it in 18 actions |
| g50t | **C** guessed, never checked | T12 (analysis_step=4, 02:59:47) | 4 | 43 (17) | 78 | proved the goal unreachable by arrows, never pressed the fifth verb it flagged on turn 1 |
| sc25 | **B** never got the controls | T5 (analysis_step=4, 00:56:35) | 21 | 33 | 36 | read the wizard as a HUD knob and the maze as a bar; never looked for a character |
| sk48 | **C** guessed, never checked | T18 (analysis_step=13, 03:32:14) | 44 | 93 | 61 | turned a no-op into a "dock" mechanic, then bet 14 actions on it in one batch |
| tn36 | **B** never got the controls | T18 (analysis_step=15, 00:09:09) | 66 (lost at 61) | 51 (7) | 32 | pressed the run button seven times without ever recognising it, or the switches, as a program |
| tr87 | **D** knew it, fumbled it | T14 (analysis_step=8, 04:46:53) | 55 | 24 | 54 | stated the dictionary mechanic correctly, then spent 33 actions re-measuring instead of translating |

**Verdict: C dominates - three of six - and A is empty.**

Scope reminder before this is quoted anywhere: this is a verdict about **six passes each of six
games, on gx10-a108, under `qwen38-27b-nvfp4`**. It is not a verdict about the games. All six clear
levels under `Qwen3.8-Flash-Next-NVFP4` - four of them on Kaggle (§0.4), and all six, `dc22` and
`tr87` included, in the two a108 Flash-Next runs (§0.5). `tn36` has since cleared under the 27B as
well (§0.7). **No game in this set has never cleared a level**; the sections above explain why these
particular 27B passes lost, which is a different claim.

Nobody ran out of clock while on a correct line. The clock ended all six runs, but in every case the run was already lost: two games never established what the verbs do at all (sc25, tn36), three formed a specific hypothesis and spent their actions on anything except the probe that would settle it (dc22, g50t, sk48), and one stated the right answer and then spent its remaining budget measuring things it already knew (tr87).

The common shape across buckets is the same defect wearing three coats: **the model does not convert a stated uncertainty into the cheapest action that resolves it.** g50t is the purest form - one keypress, flagged on turn 1, never spent, while a proof of impossibility sat in its own output. tr87 is the same defect with the answer already written down.

Two secondary findings worth carrying forward:

1. **The low action counts are behavioural, not a physical ceiling.** Actions per turn across the six vary 15x: g50t 0.25, dc22 1.05, sc25 1.75, sk48 2.3, tn36 2.5, tr87 3.7. The model can and does batch heavily when it has a plan - tr87 issued 33 actions in a single turn and sk48 14 - so nothing stopped it reaching the Boss's level-1 counts. The low end is where it had no plan worth batching: g50t produced no game action at all on 12 of its 16 turns, dc22 on 12 of 20. Inspection-only turns are the symptom, not the cause.
2. **tn36 is close to unplayable for this harness, independent of reasoning quality.** A failing run restores the board, and the model only ever sees post-action frames, so the single most informative action in the game returns a frame identical to the one before it. Worth flagging before it is counted as a reasoning failure.

## Not verified

1. **The live run.** `20260918_113435_qwen38-27b-mp-compact-p1` was executing at the snapshot time.
   `dc22`, `g50t`, `sk48` and `tr87` had not been played in it yet. If any of them clears, §0.6's
   five-game list shrinks. Re-read `summary.txt` before quoting this.
2. **The 368-run site catalog was not re-checked.** `2026-09-17-the-slippery-seven.md` §3 cites
   `/data/runs-index.json` figures (27B `dc22` mean 1.41 / 68% zero, `tr87` 0.60 / 85% zero;
   Flash-Next `dc22` 9.10, `tr87` 13.46). Those imply the **27B** has cleared `dc22` and `tr87`
   somewhere - which, if true, would cut the five-game list in §0.6 further. I could not reach that
   catalog: `https://arc3.markbarney.net/data/runs-index.json` returns the SPA shell,
   `/api/v1/catalog` 404s, `guardian.markbarney.net` 404s, and no `runs-index.json` exists on disk
   locally or on a108. The Flash-Next half of those figures is now corroborated independently by
   §0.5; **the 27B half is UNCLEAR and would only shrink the list, never grow it.**
3. **Kaggle jobs 3, 11 and 12 are not in §0.4** - not pulled to this machine. Their per-pass clears
   are in `2026-09-16-jobs-11-12-reset-guard-result.md` and agree in direction, but I read that from
   the write-up, not from artifacts.
4. **Why the 27B collapses** on `dc22`/`tr87` specifically is not addressed. §0 establishes that it
   does; the per-game audit explains what each losing pass did, which is not the same claim.
5. **`tn36`'s a108 clear is one pass.** Identical-config replication is shown for the harness and
   prompt; a single clear does not measure a rate.
6. The per-game audit's forcing turns and quotes were taken from the baseline pass with the other
   five scanned for repeats, as stated in Conventions. The 18-Sep pass was read only for §0.7. The two
   a108 Flash-Next runs were read only for their scores; no transcript from them was opened.

## Reproduction

The §0 tables come from `artifacts/<game>_p<N>_viewer_data.json` in each run directory - fields
`levels_completed`, `final_score`, `actions_per_level` - on a108 under
`/home/son/GitHub/arc-3/ARC3-Inference/runs/` and locally under `~/arc3-job-output/<job>/`. The
model pin is `grep -oE '(RadixArk|unsloth)/[A-Za-z0-9._-]+' kaggle/experiments/sparse-deletion/*.ipynb`
in `~/GitHub/arc-3`. Run config fields are each run's `run_config.json`.

Transcripts are read-only on a108 at `son@100.118.4.20:/home/son/GitHub/arc-3/ARC3-Inference/runs/<run>/transcripts/<game>-<build>_p<N>.txt`. The baseline transcripts were copied to `~/bubba-workspace/tmp-arc3-audit/20260915_230835_qwen38-27b-baseline-25g/transcripts/` (the compact and massdata copies were deleted after scanning; re-pull them over ssh if needed). A turn-splitter is at `~/bubba-workspace/tmp-arc3-audit/extract.py` (`python3 extract.py <transcript> sum` for the action trace, `... turn <lo> <hi> <char-cap>` for reasoning). Nothing on a108 was modified and no new inference was run.

The frame-level recordings at `~/GitHub/arc-3/datasets/decision-steps/v0/recordings/<game>-<build>/<guid>.ndjson` were listed as a source but were **not** consulted: the Boss's level-1 action counts come straight from `runs[].levelActions[0]` in `humanPlay.generated.json`, and no verdict above turns on frame-level detail of his play. If any bucket is contested, those recordings are the next place to look.
