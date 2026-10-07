# Debate picks in the rule-discovery agent: implementation and evaluation (24/25-Sep-2026)

Author: Claude Opus 5.5 (Bubba), for OpenMind (#arc-3, 24-Sep-2026 22:49 ET: "change the code of my ARC agent
accordingly. Evaluate on at least warehouse environment. Tell me results.").
"Accordingly" = the five picks of the simulated expert debate, ~/bubba-workspace/docs/2026-09-24-warehouse-expert-debate.md
(Round 8 table: measures and kill rules). Local only; nothing here was committed or pushed.

## What was built (all five picks, each behind an AgentConfig switch, default off)

| pick | switch | where | what it does |
|---|---|---|---|
| 1 contingency self | `use_self` | selfmodel.py (new); rules.ContextBuilder; explore.py; tl/relations.py | self = the parts the agent's own actions move, tracked by location (not colour + shape), so it survives a sprite that redraws on turning; self colours pooled over time (a colour that travels with the self on at least half its moves); frozen into each step's context; the explorer's mover and sprite, the tensor-logic Ctl group and the self parts' training targets come from it |
| 2 facing relation | `tl_facing` | tl/relations.py, tl/learner.py, tl/rule.py | a sixth self relation in equation P: Facing(o) = o lies in the strip the self would cover by its facing move (facing = learned move of the last pressed button that has one; value = its confidence, a soft relation), so a rule can say "ACTION5 changes the object ahead of self" |
| 3 epistemic value | `use_epistemic` | epistemic.py (new); policy.py; agent.py | EFE gains (a) disagreement among rule sets drawn Thompson-style from the tempered MDL posterior about each action's outcome in the current context, (b) novelty over (action, soft local context) with phasor colour codes (hdc/vsa.py); a non-moving button that is informative here takes the step from the explorer |
| 4 archive | `use_archive` | archive.py (new); agent.py | Go-Explore-style archive of object configurations (self and clock lines left out); after 40 steps with nothing new: RESET and replay the path to a rare configuration, then explore from there |
| 5 goals from contrast | `goal_contrast` | goals.py | on a clear, each goal gains ln[(eps + p_win^k)/(eps + mean over the level's other boards of p^k)]: the goal distinctive of the clearing board wins |

Game-agnostic: nothing reads game internals. Default off = old behaviour: 18 of 18 plays identical action for action to
the pre-change backup (Locksmith, Ghost Twin, Warehouse; seeds 0-1; arms touch, touch_tl, tl_only; 500 actions;
`verify_default.json`). Tests: 59 passed, 1 failed (the pre-existing test_salience_ranks_disagreement_first); 9 new in
tests/test_debate_picks.py.

## Evaluation

20 seeds x 500 actions per arm, same seeds everywhere, RESET offered, exact simulators. Baselines rerun in the same
sweep: touch_tl (the base of every new arm) and tl_only. Arms: each pick alone on touch_tl (dp_self, dp_face, dp_epi,
dp_arch, dp_goal), in build order (dp_s12 = 1+2, dp_s123 = 1+2+3), all five (dp_all). Warehouse random arm (20 seeds)
from the same labeller for the "more often than random" comparison. No play timed out (limit 1800 s).
Raw rows: results/game_sweep/dp_main/rows.json, results/game_sweep/dp_random/rows.json. Tables below are
results/debate_picks/tables.md, generated from those rows by ~/bubba-workspace/scratch/warehouse/debate_report.py.
Warehouse labels (game internals, scoring only) come from ~/bubba-workspace/scratch/warehouse/debate_labels.py via
game_sweep --hook; a check showed the hook leaves the agent's actions unchanged.

### Warehouse (wa30:ee6fef47)

| arm | levels | plays clearing | game overs | median actions |
|---|---|---|---|---|
| random | 0 | 0 | 0 | 500 |
| touch_tl | 0 | 0 | 2 | 500 |
| tl_only | 0 | 0 | 9 | 500 |
| dp_self | 0 | 0 | 19 | 231.5 |
| dp_face | 0 | 0 | 2 | 500 |
| dp_epi | 0 | 0 | 5 | 500 |
| dp_arch | 0 | 0 | 1 | 500 |
| dp_goal | 0 | 0 | 2 | 500 |
| dp_s12 | 0 | 0 | 19 | 231.5 |
| dp_s123 | 0 | 0 | 20 | 212 |
| dp_all | 0 | 0 | 6 | 500 |

| arm | self kept (all steps) | self kept (right after a turn) | own move seen right | interact at grab positions | plays with a grab | MAP predicts change for interact at grab positions (after 1st grab) | plays: Facing clause in MAP | box configurations (median per play) | box ever resting on a target |
|---|---|---|---|---|---|---|---|---|---|
| random | - | - | - | 41/214 (19%) | 17 | - | - | 3.5 | 0 |
| touch_tl | 13% | 2% | 26% | 18/551 (3%) | 11 | 38/253 (15%) | - | 5 | 0 |
| tl_only | 9% | 2% | 21% | 4/224 (2%) | 4 | 42/107 (39%) | - | 1 | 0 |
| dp_self | 92% | 91% | 93% | 1/625 (0%) | 1 | 0/44 | - | 1 | 0 |
| dp_face | 13% | 2% | 26% | 18/579 (3%) | 11 | 38/253 (15%) | 0 | 5 | 0 |
| dp_epi | 12% | 2% | 23% | 19/430 (4%) | 10 | 52/322 (16%) | - | 4.5 | 0 |
| dp_arch | 13% | 2% | 25% | 26/563 (5%) | 12 | 46/284 (16%) | - | 8.5 | 0 |
| dp_goal | 13% | 2% | 26% | 18/551 (3%) | 11 | 38/253 (15%) | - | 5 | 0 |
| dp_s12 | 92% | 91% | 93% | 1/625 (0%) | 1 | 0/44 | 0 | 1 | 0 |
| dp_s123 | 79% | 82% | 84% | 19/526 (4%) | 19 | 69/422 (16%) | 0 | 12 | 0 |
| dp_all | 83% | 86% | 86% | 62/757 (8%) | 16 | 123/500 (25%) | 0 | 12 | 0 |

Archive: dp_arch median 49 cells per play, 25 returns (16 arrived); dp_all median 17.5 cells, 108 returns (56 arrived).
How the steps were spent (Warehouse, all plays of the arm): explorer trips 25% of steps in touch_tl, 65% in dp_self;
RESETs per play 8.8 in touch_tl, 2.6 in dp_self; in dp_all 34% of steps were archive replays.

### Locksmith (ls20:9607627b)

| arm | plays clearing level 1 | median first clear (action) | plays clearing level 2 | game overs |
|---|---|---|---|---|
| touch_tl | 20 | 48.5 | 0 | 20 |
| tl_only | 20 | 51.5 | 0 | 20 |
| dp_self | 20 | 48 | 0 | 20 |
| dp_face | 20 | 48.5 | 0 | 20 |
| dp_epi | 20 | 40.5 | 0 | 20 |
| dp_arch | 20 | 48.5 | 0 | 1 |
| dp_goal | 20 | 48.5 | 0 | 20 |
| dp_s12 | 20 | 48 | 0 | 20 |
| dp_s123 | 20 | 47 | 0 | 20 |
| dp_all | 20 | 47 | 0 | 0 |

The self is never lost on Locksmith (median 0 losses per play; colours 9 + 12, moves of 5).

### Ghost Twin (g50t:5849a774)

| arm | plays clearing level 1 | first clears at (action) | game overs |
|---|---|---|---|
| touch_tl | 0 | - | 13 |
| tl_only | 1 | 183 | 18 |
| dp_self | 3 | 80, 48, 92 | 17 |
| dp_face | 0 | - | 12 |
| dp_epi | 1 | 69 | 13 |
| dp_arch | 2 | 341, 256 | 5 |
| dp_goal | 0 | - | 13 |
| dp_s12 | 3 | 80, 48, 92 (same plays as dp_self) | 17 |
| dp_s123 | 1 | 54 | 17 |
| dp_all | 4 | 461, 228, 299, 54 | 4 |

The self is never lost on Ghost Twin (median 0; colours 5 + 9, moves of 6). Two different kinds of clear: dp_self's come
early (actions 48, 80, 92), before most baseline plays have ended, so survival does not explain them; dp_all's mostly come
late (228, 299, 461; one at 54) in plays that the archive's resets kept alive (4 game overs, median 500 actions, against
13 and 330 for touch_tl), so longer survival is a competing explanation there. Few either way.

## Kill rules (Round 8), applied

1. **Contingency self: PASSES.** Measure: the self is kept through turns on Warehouse, 91% of turn steps against 2%;
   the agent sees its own move right 93% of the time against 26%. Kill rule (worse Locksmith clears): not triggered,
   20 of 20 either way, same speed. Cost: on Warehouse the explorer now works, takes two thirds of the steps and the
   agent stops resetting, so the step bar runs out: game overs 19 of 20 against 2, plays end near action 230, and
   boxes are almost never picked up (1 play). On Ghost Twin it cleared 3 plays against none, all early.
2. **Facing relation: KILLED (does nothing measurable).** Kill rule (not learned in most seeds): triggered. The
   Facing clause was in the MAP rule set in 0 of 20 plays in every facing arm on Warehouse (1 of 20 on Locksmith). Of two
   dp_all plays inspected, the learner found "ACTION5 makes the colour-3 piece ahead (facing) vanish" in one; in both
   it found "ACTION5 makes a colour-3 piece vanish". Warehouse colours the faced box 3, so the colour clause says the
   same thing for fewer nats and wins; the rule sets that won MAP kept leaning on the templates. The posterior
   predicted a change for interact at later grab positions 15% of the time without the relation and 15-25% with it; in
   most plays it never did. dp_face played like touch_tl.
3. **Epistemic value: MEASURE FAILED, kill rule not triggered.** Interact at grab positions 4% alone, 8% with all
   picks, against the random player's 19%. Boxes were picked up (10 plays alone, 19 of 20 with picks 1-2), so the kill
   rule (no box ever picked up) does not fire. Most grab positions are reached by explorer trips, where the policy does
   not act. On Locksmith it made the first clear faster (median 40.5 against 48.5).
4. **Archive: PASSES weakly.** Measure: box configurations per play median 8.5 against 5 alone; on top of picks 1-3 no
   gain (12 against 12). No first Warehouse clear; no box ever rested on a target in any of the 220 Warehouse plays.
   Side effect worth keeping: its RESETs stop the run-out game overs (Warehouse 6 with all picks against 20 for picks
   1-3; Locksmith 0-1 against 20; Ghost Twin 4-5 against 13).
5. **Goals from contrast: DOES NOTHING; its own measure could not be run.** "Second level faster than first" needs a
   second level, and no arm cleared one in any game (Locksmith plays die on level two, or survive to 500 actions without
   clearing it when the archive is on). dp_goal played action for action like touch_tl in all 60 plays. Where the
   mechanism does fire (after the Locksmith clear) the goal it names is "convert every colour-11 cell", the step bar
   draining: it picks the clock, not the goal, and no action is predicted to change that, so it moves nothing. On
   Warehouse it cannot fire at all (no clear). It is a no-op waiting on a working planner and a clock filter.

## What to do next

- Budget: with a working self the agent has to learn that the bar is a resource and reset or return before it runs out;
  the archive's returns do this by accident. This is what now stops Warehouse plays early.
- The explorer should hand the step to the policy when it arrives next to something (or try non-moving buttons there):
  interact at grab positions is 0-8% because arrivals happen inside trips.
- Goal inference before the first clear is still the wall for Warehouse: no box ever rested on a target.
- Contrast needs to discount things that change with time (a bar) before it can name the right goal, and it can only be
  judged once something clears a second level.
- Ghost Twin: rerun dp_self / dp_all with more seeds to see whether the few clears hold.

## Files

New: selfmodel.py, epistemic.py, archive.py, tests/test_debate_picks.py. Changed: agent.py, rules.py, policy.py,
goals.py, explore.py, game_sweep.py, tl/relations.py, tl/learner.py, tl/rule.py, tl/verify_default.py (--backup /
--arms / --out). Backup before the change: ../backupsOldVersions/rulediscovery1__fepInspired_035d6b6c11ad.
Scoring helpers outside the package: ~/bubba-workspace/scratch/warehouse/debate_labels.py, debate_report.py.
