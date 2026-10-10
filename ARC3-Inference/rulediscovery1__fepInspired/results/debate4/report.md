# Debate four picks: implementation and evaluation (25-Sep-2026)

Author: Claude Opus 5.5 (Bubba), for OpenMind (#arc-3, 25-Sep-2026 11:24 ET: "do a copy with random hash, then implement
these ideas, then evaluate, then tell me results"). Plan: ~/bubba-workspace/docs/2026-09-25-warehouse-expert-debate-4.md,
Round 8 (goal-babbling design: debate two, Rounds 4-5). Local only; nothing committed or pushed from this package. Backup
before the first edit: ../backupsOldVersions/rulediscovery1__fepInspired_834899e85ac8 (verified identical to the folder).
No "switches off = old behaviour" check (OpenMind's rule); the rerun d3_hb equals debate three's rows in all 60 plays
(last table).

## Verdicts, per game

- **Warehouse (wa30):** one clear, the first of this agent on Warehouse, in 1 play of 20: pick 1 (d4_opt), seed 11, level one at action 151 (the
  same play in d4_both); it then put 3 boxes on level two's targets and ran out of steps there (the arm's one game over).
  Pick 1: interact at grab positions 10% -> 17% (random 19%), grabs 95 -> 218, drops 53 -> 178, plays with a box resting on
  a target 2 -> 7. Pick 3 on top: 18% alone with pick 1 (d4_opt3), 22% with picks 1 + 2 (d4_all); boxes on a target in 10
  and 12 plays; neither kept the seed-11 clear. Pick 2 alone: 16%, boxes on a target in 2 plays (as d3_hb), no clear.
- **Locksmith (ls20):** 20/20 in every arm, median first clear 47 everywhere; no seed lost. Pick 1 changes three openings
  (seeds 0, 6, 16 clear a little sooner). Pick 3 changes nothing (plays identical with and without it).
- **Ghost Twin (g50t):** d3_hb 5 clears (seeds 4, 5, 7, 17, 19). Pick 1: the same 5 seeds. Pick 2: loses seeds 5, 7, 17
  alone (4 clears), loses 5 and 7 with pick 1 (7 clears, gaining 8, 11, 13, 15). Pick 3: one play changes (seed 14, no clear
  either way).

| pick | measure (debate) | result | kill rule / guard rule | verdict |
|---|---|---|---|---|
| 1. option-value interruption + try-once per new contact class (+ check log) | Warehouse interact at grab positions >= random's (~19%) | 17% (218/1250); random 19% (41/214); first Warehouse clear (1 play); boxes on a target 7 plays vs 2 | Locksmith or Ghost Twin loses a clear vs d3_hb: NOT triggered (Locksmith 20/20, Ghost Twin same 5 seeds) | **KEPT** (measure narrowly missed; that is what triggered building pick 3) |
| 2. goal babbling over tied goals + contrast on action-caused change | a box stays on a target in more plays; first Warehouse clear | 2 plays (d3_hb 2); no clear (the clear in d4_both is pick 1's play) | canary loses a clear: TRIGGERED (Ghost Twin seeds 5, 7, 17 alone; 5, 7 with pick 1). GUARD RULE triggered | **DROPPED** |
| 3. gated contact novelty (every button pressed 10 times, button still moveless) | adds to pick 1's interact rate | +1 point with pick 1 alone (17% -> 18%), +5 with picks 1 + 2 (17% -> 22%) | Ghost Twin changes at all: TRIGGERED (seed 14 in both arms that carry it; the gate opened at step 91, then a button momentarily without a learned move got presses; no clear lost or gained) | **DROPPED** (by the letter of its rule) |

Kept configuration = d4_opt = d3_hb + option_value + try_once.

## What was built (each an AgentConfig switch, default off; game-agnostic, no game internals, no language model)

| pick | switch | files | what it does |
|---|---|---|---|
| 1 | `option_value` (needs handoff_efe) | agent.py (`_interrupt`, `_option_value`, `check_log`), explore.py (`peek`, `_find`) | At an explorer check, continuing is valued as the trip's option: G_cont = c + (G_target - c) / k, k = remaining trip steps (the next trip's, planned without committing, when the check came at a trip's end or a block), c = a button's cost, G_target = the EFE of the trip's arriving move with its local novelty taken at the target's colour. k = 1 is the arriving move's own G. No trip to continue: debate three's best-move comparison. Every check logged (step, trigger, winner, action, k, the three G values). |
| 1 | `try_once` (needs handoff_efe) | explore.py (`contact_classes`, `try_pending`), agent.py | The first time a trip brings the self into contact with a colour it never touched this play, the check presses the best non-moving button (pressed at least 3 times, still no learned move) once, whatever the comparison says. |
| 2 | `goal_babble` | babble.py (new: GoalBabbler, CausedChange), goals.py (soft_reach, last_prog), policy.py (w_babble, planner goal override), agent.py (`_babble_plan`, `_idle`), rules.py (ContextBuilder.babble) | Before the first clear and while the budget is not urgent: sample a goal from the tied goal hypotheses (at least 1/8 of the top), among those the agent's actions change and not satisfied now, weighted by a babble weight, the caused share and a small compression tie-breaker. It is a preference in EFE (weight 2, as the existing goal term) and the beam planner tries to reach it under a rule set drawn from the tempered posterior every 20 steps. Reached without a clear: weight x 0.5 (floor 0.05); new progress: x 1.25 (cap 4); 40 steps without progress: x 0.8. The goal posterior's false alarm becomes soft: once per stretch of being satisfied, x 0.5, total floored at 0.05 (the Warehouse trap: its target is covered one step before the win). |
| 2 | `caused_contrast` (with goal_contrast) | babble.py (CausedChange), goals.py | Per goal: progress changes on ACTIVE steps (the contingency self moved) vs IDLE steps (a button with a learned move did not move it); caused share = 1 - P(change | idle) / P(change | active), idle rate shrunk toward 0. A goal whose progress changes on at least 30% of counted steps is a clock (share 0), the ambient convention of the contact memory; this was added after a probe showed Locksmith's bar drains only when the agent moves. On a clear, each goal's progress is multiplied by its share before the clear likelihood and the contrast use it. |
| 3 | `contact_gated` (needs use_epistemic) | agent.py (GATE_TRIES = 10, `presses`), epistemic.py (ContactContext.open / open_at / open_presses), policy.py | Debate three's contact-neighbourhood novelty, used only once every button has been pressed 10 times this play, and then only for a button with no learned move. The 10 comes from a probe of Ghost Twin seeds 0, 4, 7: every button's move was learned by its 7th press, before every button reached 10 presses. |

game_sweep.py: arms d4_opt, d4_goal, d4_both, d4_all, d4_opt3 (picks 1 + 3; added after the main sweep because pick 2 had
cost Ghost Twin clears), and d4_ov / d4_try (pick 1's halves, not run: pick 1 lost no clear, so no attribution was needed);
per-play fields: check log, try-once presses / contact classes, babbling episodes / plans / weights / log, caused shares,
gate opening. Tests: 109 passed, 1 failed (the pre-existing test_salience_ranks_disagreement_first); tests/test_debate4.py
has 18 new.

## How each pick behaved

**Pick 1.** On Warehouse the explorer raises about 190 checks per play. Checks interrupt the trip about 17 times per
play (14 by the comparison, 3 by try-once; d3_hb about 7.5), and every interruption at a grab position presses
interact (124 of 124). Try-once fires about 3
times per play (first contacts with new colours), almost never at a grab position (1 of 58), so it is not what raised the
rate. Still, of 728 checks at grab positions the trip won 589. Most grab-position checks are raised by walking into
the box (512 of 699 counted were "blocked"), and where the trip won, interact's G was high (median 0.99 against
continuing 0.14): the agent predicts interact does nothing, and before any clear its learned preferences mark the most
common outcome as the least wanted. 522 grab positions had no check at all (archive replays alone stood at 330). At compared checks the trip has a median of 2 steps
left; a third have exactly 1, where the option value is the arriving move's own G. On Locksmith every check finds no
non-moving button (133.6 of 134 per play); the few that compare are in the opening, before every arrow's move is learned,
and change three plays (seeds 0, 6, 16). Ghost Twin: about 2.5 interruptions per play; 11 of 20 plays change, the same 5
seeds clear.

**Pick 2.** Babbling runs: on Warehouse about 17 episodes per play, 24 planning attempts, 3 plans found (4 plan steps per
play), 70 policy decisions with the goal on. Goals tried most: remove the colour-14 objects, fill the colour-2 cells (the
true level-one goal, 43 episodes), fill colour 9. Weights: fill colour 2 rose in at least half of the 16 plays where its weight
moved (median 1.25, up to 2.4); the others mostly fell to 0.8 or below. Reaching a goal without a clear was rare (0.1 per play). On Locksmith a
clear ends babbling in every play; after it the goal named is no longer the step bar (0 of 20 plays; the probe before the
clock test named the bar in both seeds tried). On Ghost Twin a goal on the bar's colour (remove the colour-9 objects) is
still named after 2 of 4 clears, probably because that goal's progress rarely changes, so neither test catches it. The
Ghost Twin losses look like divergence: the preference is on in about 134 policy decisions per play there and the plays go
elsewhere; with pick 1 the same divergence gains four seeds and loses two.

**Pick 3.** The gate opens at a median step of about 85 on Warehouse and 62 on Locksmith, never for a button with a move.
On Warehouse it adds contact-driven interact presses: 635 presses of the moveless button while open with pick 1, 770 with
picks 1 + 2. On Locksmith every play is identical to the arm without it. On Ghost Twin 19 of 20 plays are identical; in
seed 14 a button was momentarily without a learned move after the gate opened, got contact-driven presses, and the play
changed (no clear before or after).

## Next

- Interact at grab positions is 17% with the kept configuration, just under random's 19%. The remaining gap is the
  pre-clear preference: interact's expected "nothing" is the most common outcome and is priced as the least wanted. A
  button whose outcome in THIS contact is still uncertain should not carry that penalty; and a block against an object
  could count as an arrival for try-once.
- Pick 3's gate should require that a button NEVER had a learned move, not that it has none right now (seed 14).
- Pick 2 changes Ghost Twin through divergence, not a lasting behaviour; the guard counts seeds, and at 4-7 clears of 20
  that is noisy. A decision for OpenMind: keep the per-seed guard, or judge on clear counts over more seeds.
- The Warehouse clear ran out of steps on level two; the budget flagged it for 4 steps and did not avoid it.

## Files and data

Raw rows: results/game_sweep/debate4/rows.json (240 plays: d3_hb, d4_opt, d4_goal, d4_both x 3 games x 20 seeds),
results/game_sweep/debate4_all/rows.json (60), results/game_sweep/debate4_opt3/rows.json (60); random arm
results/game_sweep/dp_random/rows.json (same labeller measures); a six-seed Warehouse smoke test in d4_smoke/ (not used
below). 500 actions, seeds 0-19, RESET offered, exact simulators, 12 workers, per-play limit 1800 s (no time-outs; median
play 2-4 minutes). Tables below: results/debate4/tables.md and tables.json, generated from those rows by
~/bubba-workspace/scratch/debate4/debate4_report.py; labeller ~/bubba-workspace/scratch/debate4/debate4_labels.py (subclass of
stage1_labels, adds the check / grab-position join); probes goal_probe.py (scratch) and the Ghost Twin gate probe.

---

## Warehouse (wa30)

| arm | plays | levels | plays clearing | first clear (median action) | plays clearing level 2 | game overs | time-outs | RESETs per play | play seconds (median) |
|---|---|---|---|---|---|---|---|---|---|
| random | 20 | 0 | 0 | None | 0 | 0 | 0 | 78.8 | 0.1 |
| d3_hb | 20 | 0 | 0 | None | 0 | 0 | 0 | 7.2 | 180.64999999999998 |
| d4_opt | 20 | 1 | 1 | 151 | 0 | 1 | 0 | 6.15 | 204.45 |
| d4_goal | 20 | 0 | 0 | None | 0 | 0 | 0 | 6.65 | 189.05 |
| d4_both | 20 | 1 | 1 | 151 | 0 | 1 | 0 | 6.0 | 216.2 |
| d4_all | 20 | 0 | 0 | None | 0 | 0 | 0 | 6.4 | 229.65 |
| d4_opt3 | 20 | 0 | 0 | None | 0 | 0 | 0 | 5.8 | 259.9 |

| arm | grab positions | interact there | plays with a grab | grabs | drops | box configs (median) | plays: box on target (seeds) | most boxes on target at once | first box on target (actions) |
|---|---|---|---|---|---|---|---|---|---|
| random | 214 | 41/214 (19%) | 17 | 41 | 20 | 3.5 | 0 (-) | 0 | - |
| d3_hb | 964 | 95/964 (10%) | 18 | 95 | 53 | 28.0 | 2 (10, 13) | 1 | 53, 95 |
| d4_opt | 1250 | 218/1250 (17%) | 18 | 218 | 178 | 36.5 | 7 (0, 9, 11, 13, 16, 18, 19) | 3 | 59, 90, 114, 116, 201, 245, 306 |
| d4_goal | 777 | 125/777 (16%) | 19 | 125 | 83 | 35.0 | 2 (7, 13) | 1 | 76, 95 |
| d4_both | 1047 | 180/1047 (17%) | 18 | 180 | 144 | 37.5 | 6 (0, 9, 11, 16, 18, 19) | 3 | 59, 90, 114, 116, 201, 306 |
| d4_all | 1275 | 279/1275 (22%) | 19 | 279 | 221 | 50.0 | 12 (0, 1, 2, 3, 7, 9, 10, 11, 13, 16, 18, 19) | 2 | 46, 59, 71, 81, 103, 136, 137, 223, 289, 410, 448, 494 |
| d4_opt3 | 1208 | 213/1208 (18%) | 19 | 213 | 173 | 41.0 | 10 (0, 1, 9, 10, 11, 12, 13, 16, 18, 19) | 2 | 46, 59, 71, 81, 88, 126, 136, 139, 270, 351 |

Grab positions by who chose the step, and interact pressed there:

| arm | explorer trip | policy | interruption | try-once | archive replay | planner | babbling plan |
|---|---|---|---|---|---|---|---|
| d3_hb | 0/501 (0%) | 16/202 (8%) | 40/40 (100%) | 0 | 39/221 (18%) | 0 | 0 |
| d4_opt | 0/618 (0%) | 18/177 (10%) | 124/124 (100%) | 1/1 (100%) | 75/330 (23%) | 0 | 0 |
| d4_goal | 0/367 (0%) | 18/139 (13%) | 41/41 (100%) | 0 | 66/228 (29%) | 0 | 0/2 (0%) |
| d4_both | 0/500 (0%) | 17/172 (10%) | 101/101 (100%) | 1/1 (100%) | 61/270 (23%) | 0 | 0/3 (0%) |
| d4_all | 0/559 (0%) | 25/208 (12%) | 182/182 (100%) | 2/2 (100%) | 70/319 (22%) | 0 | 0/5 (0%) |
| d4_opt3 | 0/562 (0%) | 23/204 (11%) | 130/130 (100%) | 1/1 (100%) | 59/311 (19%) | 0 | 0 |

Pick 1 diagnostic: checks joined to grab positions (all plays; won = what the check chose):

| arm | checks | checks at a grab position | at grab: button / trip / try-once / other | elsewhere: button / trip / try-once / other | grab positions with no check | not joined |
|---|---|---|---|---|---|---|
| d4_opt | 3794 | 728 | 124 / 589 / 1 / 14 | 163 / 2835 / 57 / 11 | 522 | 0 |
| d4_both | 4154 | 586 | 101 / 471 / 1 / 13 | 137 / 3366 / 56 / 9 | 461 | 0 |
| d4_all | 4032 | 720 | 182 / 509 / 2 / 27 | 219 / 3019 / 47 / 27 | 555 | 0 |
| d4_opt3 | 4365 | 673 | 130 / 525 / 1 / 17 | 209 / 3418 / 47 / 18 | 535 | 0 |

At grab-position checks: median G of continuing / of the best non-moving button / of the best move, by what won (the labeller keeps each play's first 60 grab-position check steps), and the triggers:

| arm | trip won: n, G_cont / G_button / G_move | button won: n, G_cont / G_button / G_move | triggers | plays over the 60 cap |
|---|---|---|---|---|
| d4_opt | 566, 0.137 / 0.988 / 0.033 | 120, 1.182 / 0.728 / 0.06 | blocked 512, arrival 122, end 34, arrival+surprise 29, surprise 2 | 4 |
| d4_both | 466, 0.111 / 0.917 / -0.049 | 99, 0.834 / 0.622 / 0.017 | blocked 412, arrival 105, end 38, arrival+surprise 23, surprise 1 | 1 |
| d4_all | 485, 0.135 / 0.934 / 0.063 | 169, 1.238 / 0.87 / 0.279 | blocked 478, arrival 128, end 40, arrival+surprise 33, surprise 1 | 3 |
| d4_opt3 | 499, 0.117 / 0.859 / 0.063 | 124, 1.117 / 0.764 / 0.169 | blocked 460, arrival 103, end 40, arrival+surprise 33, surprise 4 | 2 |

Steps by who chose them (share of all steps):

| arm | explorer trips | policy | interruptions | try-once | archive replays | planner | babbling plans |
|---|---|---|---|---|---|---|---|
| d3_hb | 58.3% | 14.9% | 1.5% | 0.0% | 25.2% | 0.0% | 0.0% |
| d4_opt | 55.7% | 13.7% | 3.0% | 0.6% | 27.1% | 0.0% | 0.0% |
| d4_goal | 62.1% | 14.2% | 1.4% | 0.0% | 21.4% | 0.0% | 0.8% |
| d4_both | 58.3% | 13.8% | 2.4% | 0.6% | 24.1% | 0.0% | 0.8% |
| d4_all | 54.2% | 17.7% | 4.0% | 0.5% | 22.6% | 0.0% | 1.0% |
| d4_opt3 | 57.7% | 19.5% | 3.4% | 0.5% | 19.0% | 0.0% | 0.0% |

Pick 1, the check log (per play): checks, what won, remaining trip steps k at compared checks:

| arm | checks | won (per play) | interruptions + try-once presses | plays with one | k (median) | share of compared checks with k = 1 | try-once presses (all plays) | new contact classes (median) |
|---|---|---|---|---|---|---|---|---|
| d4_opt | 189.7 | button 14.3, dwell 1.2, trip 171.2, try_once 2.9 | 17.25 | 20/20 | 2 | 0.338 | 58 | 3.0 |
| d4_both | 207.7 | button 11.9, dwell 1.1, trip 191.8, try_once 2.9 | 14.75 | 20/20 | 3 | 0.304 | 57 | 3.0 |
| d4_all | 201.6 | button 20.1, dwell 2.7, trip 176.4, try_once 2.5 | 22.5 | 20/20 | 2 | 0.35 | 49 | 3.0 |
| d4_opt3 | 218.2 | button 16.9, dwell 1.8, trip 197.2, try_once 2.4 | 19.35 | 20/20 | 3.0 | 0.293 | 48 | 3.0 |

Pick 2, goal babbling (per play unless noted):

| arm | episodes | reached (no clear) | stalled | plan attempts | plans found | plays with a plan | plan steps | policy decisions with the goal on | plays where a clear ended it | idle share of counted steps |
|---|---|---|---|---|---|---|---|---|---|---|
| d4_goal | 16.6 | 0.1 | 8.8 | 23.8 | 2.9 | 15/20 | 4.0 | 70.5 | 0 | 0.432 |
| d4_both | 15.6 | 0.2 | 8.4 | 22.4 | 3.5 | 17/20 | 3.7 | 65.8 | 1 | 0.372 |
| d4_all | 15.7 | 0.1 | 8.2 | 23.8 | 4.6 | 20/20 | 4.8 | 87.7 | 0 | 0.287 |

d4_goal, goals tried (episodes, all plays): remove every colour-14 object 47; convert every colour-2 cell 43; convert every colour-9 cell 38; remove every colour-9 object 37; remove every colour-2 object 32; remove every colour-4 object 30; remove every colour-7 object 29; convert every colour-4 cell 23; convert every colour-14 cell 19; convert every colour-0 cell 15
d4_goal, weights that moved (goal: plays, median / min / max final weight; start 1): remove every colour-14 object: 17, 0.8 / 0.512 / 0.8; convert every colour-2 cell: 16, 1.25 / 0.8 / 2.441; convert every colour-9 cell: 16, 1.0 / 0.512 / 1.562; remove every colour-2 object: 13, 0.64 / 0.512 / 0.8; remove every colour-7 object: 12, 0.8 / 0.64 / 0.8; remove every colour-4 object: 11, 0.8 / 0.512 / 0.8; remove every colour-9 object: 10, 0.64 / 0.512 / 0.8; convert every colour-14 cell: 9, 0.8 / 0.512 / 1.25; convert every colour-4 cell: 8, 0.8 / 0.64 / 1.25; remove every colour-0 object: 6, 0.8 / 0.5 / 0.8

d4_both, goals tried (episodes, all plays): convert every colour-9 cell 46; remove every colour-4 object 37; remove every colour-14 object 34; convert every colour-2 cell 32; remove every colour-9 object 29; remove every colour-2 object 29; remove every colour-7 object 26; convert every colour-14 cell 22; convert every colour-0 cell 21; remove every colour-0 object 17
d4_both, weights that moved (goal: plays, median / min / max final weight; start 1): remove every colour-4 object: 17, 0.8 / 0.41 / 1.0; convert every colour-9 cell: 16, 1.0 / 0.64 / 4.0; remove every colour-9 object: 14, 0.8 / 0.512 / 0.8; remove every colour-14 object: 13, 0.8 / 0.512 / 0.8; remove every colour-7 object: 12, 0.8 / 0.5 / 0.8; convert every colour-2 cell: 12, 0.9 / 0.8 / 3.052; remove every colour-2 object: 9, 0.8 / 0.512 / 0.8; convert every colour-14 cell: 9, 0.8 / 0.512 / 1.25; convert every colour-4 cell: 8, 0.8 / 0.64 / 0.8; remove every colour-0 object: 7, 0.64 / 0.5 / 0.8

d4_all, goals tried (episodes, all plays): convert every colour-9 cell 52; remove every colour-14 object 34; remove every colour-9 object 31; convert every colour-2 cell 29; remove every colour-7 object 28; remove every colour-4 object 28; remove every colour-2 object 25; convert every colour-14 cell 23; remove every colour-0 object 22; convert every colour-4 cell 19
d4_all, weights that moved (goal: plays, median / min / max final weight; start 1): convert every colour-9 cell: 19, 1.25 / 0.64 / 3.815; convert every colour-2 cell: 15, 1.25 / 0.8 / 1.953; remove every colour-7 object: 15, 0.8 / 0.64 / 0.8; remove every colour-4 object: 13, 0.8 / 0.64 / 0.8; remove every colour-9 object: 12, 0.8 / 0.512 / 0.8; remove every colour-2 object: 11, 0.8 / 0.64 / 0.8; remove every colour-14 object: 10, 0.72 / 0.512 / 0.8; convert every colour-14 cell: 9, 0.8 / 0.512 / 1.25; remove every colour-0 object: 9, 0.8 / 0.5 / 0.8; convert every colour-4 cell: 7, 0.8 / 0.512 / 1.0

Goal named after the first clear (contrast log), and plays where it is the step bar's colour:

| arm | plays with a clear | names the bar | most named |
|---|---|---|---|
| d4_both | 1 | 0 | convert every colour-9 cell (1) |

## Locksmith (ls20)

| arm | plays | levels | plays clearing | first clear (median action) | plays clearing level 2 | game overs | time-outs | RESETs per play | play seconds (median) |
|---|---|---|---|---|---|---|---|---|---|
| d3_hb | 20 | 20 | 20 | 47.0 | 0 | 0 | 0 | 12.0 | 123.95 |
| d4_opt | 20 | 20 | 20 | 47.0 | 0 | 0 | 0 | 11.95 | 122.1 |
| d4_goal | 20 | 20 | 20 | 47.0 | 0 | 0 | 0 | 12.15 | 121.6 |
| d4_both | 20 | 20 | 20 | 47.0 | 0 | 0 | 0 | 11.95 | 125.45 |
| d4_all | 20 | 20 | 20 | 47.0 | 0 | 0 | 0 | 11.95 | 129.7 |
| d4_opt3 | 20 | 20 | 20 | 47.0 | 0 | 0 | 0 | 11.95 | 145.1 |

Steps by who chose them (share of all steps):

| arm | explorer trips | policy | interruptions | try-once | archive replays | planner | babbling plans |
|---|---|---|---|---|---|---|---|
| d3_hb | 55.8% | 5.1% | 0.0% | 0.0% | 39.1% | 0.0% | 0.0% |
| d4_opt | 56.9% | 4.5% | 0.0% | 0.0% | 38.5% | 0.0% | 0.0% |
| d4_goal | 55.8% | 5.2% | 0.0% | 0.0% | 38.9% | 0.0% | 0.1% |
| d4_both | 56.8% | 4.5% | 0.0% | 0.0% | 38.6% | 0.0% | 0.1% |
| d4_all | 56.8% | 4.5% | 0.0% | 0.0% | 38.6% | 0.0% | 0.1% |
| d4_opt3 | 56.9% | 4.5% | 0.0% | 0.0% | 38.5% | 0.0% | 0.0% |

Pick 1, the check log (per play): checks, what won, remaining trip steps k at compared checks:

| arm | checks | won (per play) | interruptions + try-once presses | plays with one | k (median) | share of compared checks with k = 1 | try-once presses (all plays) | new contact classes (median) |
|---|---|---|---|---|---|---|---|---|
| d4_opt | 134.0 | none 133.6, trip 0.2, try_once 0.2 | 0.2 | 4/20 | 4.0 | 0.0 | 4 | 2.0 |
| d4_both | 133.8 | none 133.4, trip 0.2, try_once 0.2 | 0.2 | 4/20 | 4.0 | 0.0 | 4 | 2.0 |
| d4_all | 133.8 | none 133.4, trip 0.2, try_once 0.2 | 0.2 | 4/20 | 4.0 | 0.0 | 4 | 2.0 |
| d4_opt3 | 134.0 | none 133.6, trip 0.2, try_once 0.2 | 0.2 | 4/20 | 4.0 | 0.0 | 4 | 2.0 |

Pick 2, goal babbling (per play unless noted):

| arm | episodes | reached (no clear) | stalled | plan attempts | plans found | plays with a plan | plan steps | policy decisions with the goal on | plays where a clear ended it | idle share of counted steps |
|---|---|---|---|---|---|---|---|---|---|---|
| d4_goal | 4.3 | 0.5 | 0.2 | 5.4 | 0.7 | 6/20 | 0.7 | 23.9 | 20 | 0.081 |
| d4_both | 4.0 | 0.5 | 0.2 | 5.1 | 0.5 | 5/20 | 0.5 | 22.6 | 20 | 0.076 |
| d4_all | 4.0 | 0.5 | 0.2 | 5.1 | 0.5 | 5/20 | 0.5 | 22.6 | 20 | 0.076 |

d4_goal, goals tried (episodes, all plays): convert every colour-1 cell 12; remove every colour-12 object 11; convert every colour-8 cell 8; convert every colour-5 cell 8; convert every colour-0 cell 7; remove every colour-9 object 7; convert every colour-12 cell 6; remove every colour-11 object 6; remove every colour-0 object 5; remove every colour-5 object 5
d4_goal, weights that moved (goal: plays, median / min / max final weight; start 1): convert every colour-5 cell: 6, 1.25 / 1.0 / 1.25; convert every colour-1 cell: 4, 0.5 / 0.5 / 0.5; remove every colour-0 object: 3, 0.5 / 0.5 / 0.5; convert every colour-0 cell: 2, 0.5 / 0.5 / 0.5; convert every colour-8 cell: 2, 1.4060000000000001 / 1.25 / 1.562; convert every colour-11 cell: 2, 4.0 / 4.0 / 4.0; remove every colour-1 object: 1, 0.5 / 0.5 / 0.5; remove every colour-9 object: 1, 0.8 / 0.8 / 0.8; convert every colour-12 cell: 1, 0.8 / 0.8 / 0.8; remove every colour-12 object: 1, 0.8 / 0.8 / 0.8

d4_both, goals tried (episodes, all plays): convert every colour-1 cell 11; remove every colour-12 object 10; convert every colour-8 cell 8; remove every colour-9 object 7; convert every colour-5 cell 7; convert every colour-12 cell 6; convert every colour-0 cell 6; remove every colour-5 object 6; remove every colour-11 object 4; remove every colour-0 object 4
d4_both, weights that moved (goal: plays, median / min / max final weight; start 1): convert every colour-1 cell: 6, 0.5 / 0.5 / 0.5; convert every colour-5 cell: 5, 1.25 / 1.0 / 1.25; remove every colour-0 object: 2, 0.5 / 0.5 / 0.5; convert every colour-8 cell: 2, 1.4060000000000001 / 1.25 / 1.562; convert every colour-11 cell: 2, 4.0 / 4.0 / 4.0; convert every colour-0 cell: 1, 0.5 / 0.5 / 0.5; remove every colour-1 object: 1, 0.5 / 0.5 / 0.5; remove every colour-9 object: 1, 0.8 / 0.8 / 0.8; convert every colour-12 cell: 1, 0.8 / 0.8 / 0.8; remove every colour-12 object: 1, 0.8 / 0.8 / 0.8

d4_all, goals tried (episodes, all plays): convert every colour-1 cell 11; remove every colour-12 object 10; convert every colour-8 cell 8; remove every colour-9 object 7; convert every colour-5 cell 7; convert every colour-12 cell 6; convert every colour-0 cell 6; remove every colour-5 object 6; remove every colour-11 object 4; remove every colour-0 object 4
d4_all, weights that moved (goal: plays, median / min / max final weight; start 1): convert every colour-1 cell: 6, 0.5 / 0.5 / 0.5; convert every colour-5 cell: 5, 1.25 / 1.0 / 1.25; remove every colour-0 object: 2, 0.5 / 0.5 / 0.5; convert every colour-8 cell: 2, 1.4060000000000001 / 1.25 / 1.562; convert every colour-11 cell: 2, 4.0 / 4.0 / 4.0; convert every colour-0 cell: 1, 0.5 / 0.5 / 0.5; remove every colour-1 object: 1, 0.5 / 0.5 / 0.5; remove every colour-9 object: 1, 0.8 / 0.8 / 0.8; convert every colour-12 cell: 1, 0.8 / 0.8 / 0.8; remove every colour-12 object: 1, 0.8 / 0.8 / 0.8

Goal named after the first clear (contrast log), and plays where it is the step bar's colour:

| arm | plays with a clear | names the bar | most named |
|---|---|---|---|
| d4_goal | 20 | 0 | convert every colour-8 cell (11); convert every colour-5 cell (9) |
| d4_both | 20 | 0 | convert every colour-8 cell (11); convert every colour-5 cell (9) |
| d4_all | 20 | 0 | convert every colour-8 cell (11); convert every colour-5 cell (9) |

First clear per seed (action; - = no clear), and seeds where an arm lost / gained a clear vs d3_hb:

| arm | 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 | 11 | 12 | 13 | 14 | 15 | 16 | 17 | 18 | 19 | lost vs d3_hb | gained vs d3_hb |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| d3_hb | 54 | 47 | 29 | 47 | 40 | 89 | 52 | 28 | 76 | 38 | 46 | 39 | 76 | 90 | 42 | 50 | 54 | 45 | 76 | 46 | none | none |
| d4_opt | 48 | 47 | 29 | 47 | 40 | 89 | 47 | 28 | 76 | 38 | 46 | 39 | 76 | 90 | 42 | 50 | 48 | 45 | 76 | 46 | none | none |
| d4_goal | 65 | 47 | 29 | 47 | 40 | 89 | 52 | 28 | 76 | 38 | 46 | 39 | 77 | 83 | 42 | 50 | 54 | 45 | 76 | 46 | none | none |
| d4_both | 48 | 47 | 29 | 47 | 40 | 89 | 53 | 28 | 76 | 38 | 46 | 39 | 77 | 83 | 42 | 50 | 48 | 45 | 76 | 46 | none | none |
| d4_all | 48 | 47 | 29 | 47 | 40 | 89 | 53 | 28 | 76 | 38 | 46 | 39 | 77 | 83 | 42 | 50 | 48 | 45 | 76 | 46 | none | none |
| d4_opt3 | 48 | 47 | 29 | 47 | 40 | 89 | 47 | 28 | 76 | 38 | 46 | 39 | 76 | 90 | 42 | 50 | 48 | 45 | 76 | 46 | none | none |

## Ghost Twin (g50t)

| arm | plays | levels | plays clearing | first clear (median action) | plays clearing level 2 | game overs | time-outs | RESETs per play | play seconds (median) |
|---|---|---|---|---|---|---|---|---|---|
| d3_hb | 20 | 5 | 5 | 323 | 0 | 2 | 0 | 12.95 | 139.25 |
| d4_opt | 20 | 5 | 5 | 228 | 0 | 3 | 0 | 11.15 | 127.85 |
| d4_goal | 20 | 4 | 4 | 428.0 | 0 | 3 | 0 | 13.45 | 140.65 |
| d4_both | 20 | 7 | 7 | 329 | 0 | 3 | 0 | 12.15 | 136.89999999999998 |
| d4_all | 20 | 7 | 7 | 329 | 0 | 3 | 0 | 12.5 | 124.85 |
| d4_opt3 | 20 | 5 | 5 | 228 | 0 | 3 | 0 | 11.35 | 148.8 |

Steps by who chose them (share of all steps):

| arm | explorer trips | policy | interruptions | try-once | archive replays | planner | babbling plans |
|---|---|---|---|---|---|---|---|
| d3_hb | 41.2% | 30.7% | 0.2% | 0.0% | 28.0% | 0.0% | 0.0% |
| d4_opt | 37.9% | 27.2% | 0.5% | 0.0% | 34.3% | 0.0% | 0.0% |
| d4_goal | 41.3% | 30.3% | 0.2% | 0.0% | 26.3% | 0.0% | 1.9% |
| d4_both | 42.5% | 26.3% | 0.5% | 0.0% | 29.2% | 0.0% | 1.6% |
| d4_all | 43.0% | 27.7% | 0.4% | 0.0% | 27.2% | 0.0% | 1.6% |
| d4_opt3 | 37.9% | 27.8% | 0.5% | 0.0% | 33.7% | 0.0% | 0.0% |

Pick 1, the check log (per play): checks, what won, remaining trip steps k at compared checks:

| arm | checks | won (per play) | interruptions + try-once presses | plays with one | k (median) | share of compared checks with k = 1 | try-once presses (all plays) | new contact classes (median) |
|---|---|---|---|---|---|---|---|---|
| d4_opt | 114.3 | button 2.4, dwell 0.2, none 99.3, trip 12.3, try_once 0.1 | 2.5 | 13/20 | 2.0 | 0.16 | 2 | 0.0 |
| d4_both | 117.9 | button 2.1, dwell 0.3, none 102.8, trip 12.6, try_once 0.1 | 2.25 | 13/20 | 1 | 0.163 | 2 | 0.0 |
| d4_all | 120.8 | button 2.0, dwell 0.3, none 106.0, trip 12.3, try_once 0.1 | 2.15 | 13/20 | 2.0 | 0.132 | 2 | 0.0 |
| d4_opt3 | 114.8 | button 2.3, dwell 0.2, none 100.2, trip 12.1, try_once 0.1 | 2.4 | 13/20 | 2 | 0.129 | 2 | 0.0 |

Pick 2, goal babbling (per play unless noted):

| arm | episodes | reached (no clear) | stalled | plan attempts | plans found | plays with a plan | plan steps | policy decisions with the goal on | plays where a clear ended it | idle share of counted steps |
|---|---|---|---|---|---|---|---|---|---|---|
| d4_goal | 20.1 | 0.0 | 6.2 | 22.8 | 5.7 | 17/20 | 8.8 | 133.9 | 4 | 0.232 |
| d4_both | 17.4 | 0.0 | 5.4 | 19.9 | 4.7 | 18/20 | 7.2 | 119.8 | 7 | 0.226 |
| d4_all | 17.6 | 0.0 | 5.2 | 20.5 | 4.6 | 17/20 | 7.2 | 126.5 | 7 | 0.221 |

d4_goal, goals tried (episodes, all plays): remove every colour-9 object 67; remove every colour-8 object 62; convert every colour-5 cell 61; remove every colour-5 object 60; remove every colour-1 object 60; convert every colour-8 cell 53; convert every colour-1 cell 34; convert every colour-9 cell 5
d4_goal, weights that moved (goal: plays, median / min / max final weight; start 1): remove every colour-1 object: 16, 0.8 / 0.64 / 0.8; remove every colour-8 object: 15, 0.8 / 0.512 / 0.8; remove every colour-9 object: 14, 0.72 / 0.512 / 0.8; convert every colour-8 cell: 14, 1.0 / 0.64 / 1.953; convert every colour-5 cell: 14, 0.8 / 0.512 / 0.8; convert every colour-1 cell: 13, 1.25 / 0.64 / 2.441; remove every colour-5 object: 11, 0.64 / 0.512 / 0.8; convert every colour-9 cell: 4, 2.9765 / 1.953 / 4.0

d4_both, goals tried (episodes, all plays): remove every colour-9 object 60; remove every colour-5 object 57; remove every colour-1 object 51; convert every colour-5 cell 51; convert every colour-8 cell 50; remove every colour-8 object 46; convert every colour-1 cell 27; convert every colour-9 cell 5
d4_both, weights that moved (goal: plays, median / min / max final weight; start 1): convert every colour-8 cell: 16, 1.0 / 0.64 / 1.25; remove every colour-1 object: 15, 0.8 / 0.512 / 0.8; remove every colour-9 object: 14, 0.8 / 0.512 / 0.8; remove every colour-5 object: 12, 0.8 / 0.64 / 0.8; convert every colour-1 cell: 12, 1.25 / 0.64 / 2.441; convert every colour-5 cell: 12, 0.8 / 0.512 / 0.8; remove every colour-8 object: 10, 0.8 / 0.512 / 0.8; convert every colour-9 cell: 4, 2.9765 / 1.953 / 4.0

d4_all, goals tried (episodes, all plays): remove every colour-9 object 61; remove every colour-5 object 57; convert every colour-5 cell 54; remove every colour-1 object 53; convert every colour-8 cell 47; remove every colour-8 object 46; convert every colour-1 cell 28; convert every colour-9 cell 5
d4_all, weights that moved (goal: plays, median / min / max final weight; start 1): remove every colour-1 object: 15, 0.8 / 0.512 / 0.8; convert every colour-8 cell: 15, 1.0 / 0.64 / 1.25; convert every colour-1 cell: 13, 1.25 / 0.64 / 2.441; remove every colour-9 object: 13, 0.8 / 0.512 / 0.8; remove every colour-5 object: 12, 0.8 / 0.64 / 0.8; convert every colour-5 cell: 12, 0.8 / 0.512 / 0.8; remove every colour-8 object: 10, 0.8 / 0.64 / 0.8; convert every colour-9 cell: 4, 2.9765 / 1.953 / 4.0

Goal named after the first clear (contrast log), and plays where it is the step bar's colour:

| arm | plays with a clear | names the bar | most named |
|---|---|---|---|
| d4_goal | 4 | 2 | convert every colour-8 cell (2); remove every colour-9 object (2) |
| d4_both | 7 | 3 | convert every colour-8 cell (4); remove every colour-9 object (3) |
| d4_all | 7 | 3 | convert every colour-8 cell (4); remove every colour-9 object (3) |

First clear per seed (action; - = no clear), and seeds where an arm lost / gained a clear vs d3_hb:

| arm | 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 | 11 | 12 | 13 | 14 | 15 | 16 | 17 | 18 | 19 | lost vs d3_hb | gained vs d3_hb |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| d3_hb | - | - | - | - | 427 | 228 | - | 494 | - | - | - | - | - | - | - | - | - | 323 | - | 54 | none | none |
| d4_opt | - | - | - | - | 403 | 228 | - | 494 | - | - | - | - | - | - | - | - | - | 203 | - | 55 | none | none |
| d4_goal | - | - | - | - | 419 | - | - | - | - | - | - | 455 | - | - | - | 437 | - | - | - | 54 | 5, 7, 17 | 11, 15 |
| d4_both | - | - | - | - | 484 | - | - | - | 329 | - | - | 212 | - | 458 | - | 437 | - | 72 | - | 55 | 5, 7 | 8, 11, 13, 15 |
| d4_all | - | - | - | - | 484 | - | - | - | 329 | - | - | 212 | - | 458 | - | 437 | - | 72 | - | 55 | 5, 7 | 11, 8, 13, 15 |
| d4_opt3 | - | - | - | - | 403 | 228 | - | 494 | - | - | - | - | - | - | - | - | - | 203 | - | 55 | none | none |

Pick 3's kill rule: plays with the gated contact novelty that differ from the same arm without it (levels, clears, actions, end state or presses), presses of a button with no learned move while the gate was open, and the step the gate opened (median):

| comparison | plays | seeds that differ | moveless presses while open | gate opened at (median step) |
|---|---|---|---|---|
| wa30/d4_all vs d4_both | 20 | 0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19 | 770 | 85.0 |
| ls20/d4_all vs d4_both | 20 | none | 0 | 61.5 |
| g50t/d4_all vs d4_both | 20 | 14 | 34 | 106 |
| wa30/d4_opt3 vs d4_opt | 20 | 0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19 | 635 | 83.0 |
| ls20/d4_opt3 vs d4_opt | 20 | none | 0 | 61.5 |
| g50t/d4_opt3 vs d4_opt | 20 | 14 | 41 | 114 |

Rerun d3_hb vs debate three's rows (results/game_sweep/debate3_hb), plays equal in levels, clears, actions, end state and presses:

- g50t/d3_hb: 20/20
- ls20/d3_hb: 20/20
- wa30/d3_hb: 20/20

