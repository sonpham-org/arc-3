# Stage one (explorer hand-off + budget in EFE): implementation and evaluation (25-Sep-2026)

Author: Claude Opus 5.5 (Bubba), for OpenMind (#arc-3, 25-Sep-2026 02:38 ET: "yes proceed" to stage one of the plan from
the second simulated expert debate, ~/bubba-workspace/docs/2026-09-25-warehouse-expert-debate-2.md, Round 8 picks 1 and 2).
Local only; nothing here was committed or pushed. Backup before the change: ../backupsOldVersions/rulediscovery1__fepInspired_5cb06041153d.
A first helper started this at 02:38 ET and died at ~02:52 ET (expired login) after writing most of the code; this run
reviewed every line of its diff against the backup, fixed two things (below), finished the tests and ran the evaluation.

## What was built (two AgentConfig switches, default off)

| pick | switch | where | what it does |
|---|---|---|---|
| 1 explorer as an option | `explore_handoff` | explore.py (ExploreConfig.handoff, handoff_nats, dwell; `_handoff`); agent.py | an explorer trip is a temporally extended action that ENDS and gives the choice back to the EFE policy on: arrival (the self comes into new contact with any object; each object / self position once per level), surprise (the posterior's surprisal for the step reaches 2.5 nats, or a spike), blocked (the step did not move the self as the trip's mover predicted), or reaching the target. The policy then chooses among all actions, including buttons that do not move, for up to 3 steps while the self stays where the hand-off happened; the next trip starts once the self moves. A cut trip's target is not counted as touched. General termination: nothing about boxes. |
| 2 budget in EFE | `use_budget` | budget.py (new); policy.py (PolicyConfig.w_budget); agent.py; archive.py (start_return, abandon); rules.py (ContextBuilder.budget) | the learned gauge finder (soft/a4_gauges.GaugeFinder, run online on a ring of the last 96 raw boards, refreshed every 10 steps) finds draining bars from the screen; the forecast gives steps left (value / mean drain per action) and the value after a RESET (learned, else the level's first board). A game over is the existing dispreferred outcome (goals.Preferences.c_game_over): each action's G gains w_prag x risk x (-c_game_over), risk = P(game over when the bar runs out) x sigmoid((4 - steps left after the action) / 1). P(game over when the bar runs out) is a Beta(4, 1) belief updated only when the bar actually runs out. When the forecast has 7 or fewer steps left ("urgent"), explorer trips and archive replays give way to the policy, and a RESET the policy then chooses becomes an archive return whose replay fits the refilled budget. No game internals. |

Fixes to the first helper's code: (a) with the contingency self on, a sprite that redraws when it turns is not one matched
component move, so every turning step of a trip was judged "blocked" (and would have fired a false hand-off); with the
hand-off on, the self's own displacement now decides (explore.py). (b) Its RESET-to-archive-return conversion fired on
every policy RESET with the budget on, which would have bundled a second change into the budget arm; it now fires only
when the budget is urgent (agent.py).

Default off = old behaviour: 24 of 24 plays identical action for action to the backup (Locksmith, Ghost Twin, Warehouse;
seeds 0-1; arms touch, touch_tl, tl_only and last night's dp_all; 500 actions; results/stage1/verify_default.json). In the
sweep below the rerun touch_tl and dp_all plays equal last night's rows in all 120 plays, and s1_keep plays exactly like
dp_all in all 60 (facing and contrast still do nothing). Tests: 71 passed, 1 failed (the pre-existing
test_salience_ranks_disagreement_first); 12 new in tests/test_stage1.py.

## Evaluation

20 seeds x 500 actions per arm, seeds 0-19 as last night, RESET offered, exact simulators, per-play limit 1800 s (no
play timed out). Arms: s1_keep = touch_tl + self + epistemic + archive (last night's kept picks; no facing, no contrast);
s1_handoff, s1_budget, s1_both = s1_keep + each switch / both; baselines rerun in the same sweep: touch_tl and dp_all.
Warehouse random arm reused from results/game_sweep/dp_random/: the labeller for this sweep
(~/bubba-workspace/scratch/warehouse/stage1_labels.py) subclasses last night's debate_labels.WarehouseLabels and calls it
for every base measure, only adding a breakdown by decision mode, so the random arm's measures are the same measures.
Raw rows: results/game_sweep/s1_main/rows.json (+ dp_random/rows.json). All tables below are results/stage1/tables.md,
generated from those rows by ~/bubba-workspace/scratch/stage1/stage1_report.py.

### Warehouse (wa30:ee6fef47)

| arm | levels | game overs | median actions | RESETs per play |
|---|---|---|---|---|
| random | 0 | 0 | 500 | 78.8 |
| touch_tl | 0 | 2 | 500 | 8.8 |
| dp_all | 0 | 6 | 500 | 7.2 |
| s1_keep | 0 | 6 | 500 | 7.2 |
| s1_handoff | 0 | 4 | 500 | 7.2 |
| s1_budget | 0 | 0 | 500 | 8.55 |
| s1_both | 0 | 0 | 500 | 7.75 |

| arm | grab positions | interact there | plays with a grab | grabs | drops | box configs (median) | plays: box on target | self kept (turn steps) |
|---|---|---|---|---|---|---|---|---|
| random | 214 | 41/214 (19%) | 17 | 41 | 20 | 3.5 | 0 | - |
| touch_tl | 551 | 18/551 (3%) | 11 | 18 | 12 | 5 | 0 | 2% |
| s1_keep | 757 | 62/757 (8%) | 16 | 62 | 16 | 12 | 0 | 86% |
| s1_handoff | 1156 | 92/1156 (8%) | 18 | 92 | 64 | 30 | 4 | 82% |
| s1_budget | 964 | 67/964 (7%) | 17 | 67 | 19 | 14 | 0 | 82% |
| s1_both | 1273 | 98/1273 (8%) | 18 | 98 | 68 | 30.5 | 4 | 83% |

Grab positions by who chose the step, and interact pressed there:

| arm | explorer trip | policy | archive replay |
|---|---|---|---|
| touch_tl | 0/323 | 18/228 (8%) | - |
| s1_keep | 0/449 | 16/119 (13%) | 46/189 (24%) |
| s1_handoff | 0/182 | 72/780 (9%) | 20/194 (10%) |
| s1_budget | 0/543 | 18/123 (15%) | 49/298 (16%) |
| s1_both | 0/196 | 74/835 (9%) | 24/242 (10%) |

Steps by who chose them: s1_keep explorer 49%, policy 17%, archive replays 34%; s1_handoff 38% / 45% / 17%; s1_both 38% /
44% / 18%. Hand-offs per play (s1_handoff): 112, of which arrival 24, surprise 19, both 16, blocked 38, trip end 15.
Budget: the bar was found in 20 of 20 plays (median step 17); urgent in only 6 plays (s1_budget) / 5 (s1_both), with 7 /
5 RESETs chosen while urgent; the bar never ran out.

First boxes on a target: in 4 plays of s1_handoff (seeds 2, 5, 13, 14; first at actions 470, 130, 222, 45) a box came to
rest on a target, up to two of the level's three boxes at once in seeds 2 and 5. The same four plays, same steps, in
s1_both. None in any other arm here, none in last night's 220 Warehouse plays. No clear.

### Locksmith (ls20:9607627b)

| arm | plays clearing level 1 | median first clear (action) | game overs | RESETs per play |
|---|---|---|---|---|
| touch_tl | 20 | 48.5 | 20 | 4.35 |
| dp_all | 20 | 47 | 0 | 12.0 |
| s1_keep | 20 | 47 | 0 | 12.0 |
| s1_handoff | 15 | 272 | 5 | 14.4 |
| s1_budget | 18 | 46.5 | 0 | 16.0 |
| s1_both | 13 | 349 | 0 | 24.3 |

Hand-off: every seed got slower (s1_keep's median 47 -> 272); 5 plays lost the clear. Trace of seed 2 (29 -> 77): after
each hand-off the policy takes one step, almost always a move, which ends the dwell and often steps back; the explorer
then re-plans the same target. Trips are cut by "trip end", "arrival" at new wall pieces, and "surprise": Locksmith's
ordinary step surprisal sits around 2-3 nats, so the fixed 2.5-nat threshold cuts trips just short of their target again
and again. Budget: the bar holds about 42 steps (84 cells, 2 per step). The plays s1_budget lost or slowed are exactly the
ones s1_keep cleared late (seeds 3, 5, 8, 12, 13, 18: 47-90). Replayed: five of them cleared 61-71 steps after their last
RESET, i.e. they ran the bar out, lost a life and carried on; seed 3 cleared exactly 42 steps after it, at the bar's end.
Plays the budget did not touch (e.g. seeds 1, 2) cleared 24-34 steps after their last RESET, inside one bar
(~/bubba-workspace/scratch/stage1/resets_before_clear.py).
With the budget on the agent resets a few steps before the bar ends, so it never learns that running out is survivable
here: the belief P(game over when it runs out) is only updated when the bar actually runs out, which the budget prevents
(it ran out in 0 of 20 s1_budget plays, 1 of 20 s1_both plays). The prior stays at 0.8 and confirms itself.

### Ghost Twin (g50t:5849a774)

| arm | plays clearing level 1 | first clears at (action) | game overs |
|---|---|---|---|
| touch_tl | 0 | - | 13 |
| s1_keep (= dp_all) | 4 | 54, 228, 299, 461 | 4 |
| s1_handoff | 2 | 139, 317 | 7 |
| s1_budget | 4 | 54, 228, 299, 461 | 1 |
| s1_both | 2 | 139, 317 | 0 |

## Kill rules (debate 2, Round 8), applied

1. **Explorer as an option: measure FAILED, kill rule TRIGGERED.** Measure: interact pressed at grab positions at least as
   often as random. It was 8% (92 of 1156) against random's 19%. The hand-off did what it was built to do mechanically:
   the policy now chooses at 780 grab positions instead of 119, and grabs (62 -> 92), drops (16 -> 64), box configurations
   (median 12 -> 30) and the first boxes on a target followed. But when the policy has the choice at a grab position it
   presses interact only 9% of the time: it cannot tell a grab position from anywhere else (interact's context there is
   the same as everywhere, section 0a of the note). Cost: Locksmith 20 -> 15 plays clearing, first clear much later.
2. **Budget in EFE: measure PASSED, kill rule TRIGGERED.** Measure: Warehouse game overs back to baseline or lower with
   the self on: 0 against 6 for the same agent without it (s1_keep), with only a handful of well-timed RESETs. Ghost Twin game overs
   4 -> 1, clears unchanged. Kill rule: Locksmith first-clear rate drops: 20 -> 18 (and 13 with both), for the reason
   above (a survivable bar treated as fatal, never tested).

## Verdict: stage one FAILS

Passing needed all three: Warehouse interact-at-grab at least random's (8% vs 19%: no), Warehouse game overs no higher
than touch_tl with the self on (0 vs 2 in both budget arms: yes; 4 with the hand-off alone), and Locksmith level one 20 of
20 (15, 18 and 13 in the three new arms: no). Per the plan, stage two (goal babbling, contrast fix) does not start.
Worth keeping from it: the first boxes ever resting on a target (hand-off arms), and zero Warehouse game overs (budget).

## Next (for a re-debate)

- Hand-off: the policy has to be able to tell where interact is informative; the hand-off only delivers it there. And a
  hand-off should not throw away the trip: resume the same option after the dwell instead of re-planning, and make
  surprise relative to the play's running surprisal instead of a fixed 2.5 nats.
- Budget: the end belief has to be learnable without dying: e.g. read a lives counter / refill as evidence, or let the
  prior depend on whether a run-out was ever observed; urgency should also weigh what the level costs against what the
  bar holds.

## Files

New: budget.py, tests/test_stage1.py. Changed: agent.py, archive.py, explore.py, policy.py, rules.py, game_sweep.py (arms
s1_keep, s1_handoff, s1_budget, s1_both; per-play hand-off and budget fields), tl/verify_default.py (arm keywords from
each package's own game_sweep, so last night's arms can be compared). Scoring helpers outside the package:
~/bubba-workspace/scratch/warehouse/stage1_labels.py, ~/bubba-workspace/scratch/stage1/stage1_report.py (probe.py,
trace.py, trace_budget.py for the single-play checks).
