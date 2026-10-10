# Debate three picks: implementation and evaluation (25-Sep-2026)

Author: Claude Opus 5.5 (Bubba), for OpenMind (#arc-3, 25-Sep-2026 05:47 ET: "make copy of the directory of my agent as
usual. then implement the changes proposed by the expert debate, then evaluate all 3 environments"). Plan:
~/bubba-workspace/docs/2026-09-25-warehouse-expert-debate-3.md, Round 8. Local only; nothing committed or pushed.
Backup before the change: ../backupsOldVersions/rulediscovery1__fepInspired_cbdb7b7d729a (verified identical to the
folder before the first edit). No "switches off = old behaviour" check (OpenMind's rule since 25-Sep 04:34 ET); the rerun
s1_keep and s1_both happened to equal the stage-one sweep's plays in all 120 cases (last table).

## Verdicts, per game

- **Locksmith (ls20):** picks 1 + 3 (d3_hb): 20/20, median first clear 47, no game overs; every play equal to s1_keep's
  in clears, actions, end state and press counts. All three new (d3_all): 20/20, median 43. Arms that keep the stage-one hand-off still lose clears (d3_budget
  15/20, d3_contact 8/20). d3_handoff 18/20: its two lost seeds (5, 13) are exactly the stage-one budget's, and its plays
  equal s1_budget's (stage-one sweep) in 18 of 20 seeds; pick 1 never interrupts on Locksmith.
- **Ghost Twin (g50t):** d3_hb 5 clears (s1_keep's four seeds 4, 5, 17, 19 plus seed 7), 2 game overs (s1_keep 4). Every
  arm carrying pick 2 cleared nothing (d3_contact 0, d3_all 0).
- **Warehouse (wa30):** no clears in any arm. Interact pressed at grab positions: random 19%, s1_keep 8%, s1_both 8%,
  d3_handoff = d3_hb 10%, d3_contact 10%, d3_all 13%. Game overs 0 in every budget arm. Boxes resting on a target: s1_both
  4 plays (up to 2 at once), d3_hb 2 plays, d3_contact 2, d3_all 3 (1 at once).

| pick | measure (debate) | result | kill rule / guard rule | verdict |
|---|---|---|---|---|
| 1. hand-off by EFE comparison, relative surprise, resume | Locksmith 20/20 at baseline speed; Ghost Twin clears >= s1_keep's; Warehouse boxes-on-target kept | Locksmith 20/20 at 47 with pick 3 (18/20 with the old budget, whose losses they are); Ghost Twin 5 >= 4; boxes on target in 2 plays against stage one's 4 | Locksmith below 20/20: not triggered with pick 3; no Locksmith or Ghost Twin clear lost vs s1_keep | **KEPT** (with pick 3). Boxes on target: stage one's 4 plays not reproduced (2 plays, one seed in common); too rare to call either way |
| 2. contact-neighbourhood context for buttons | interact at grab positions >= random's | 10% alone, 13% with the others; random 19% | own kill rule (no gain over stage one) not triggered: 8% -> 10%; GUARD RULE triggered: Ghost Twin 4 -> 0 in both arms, Locksmith 8/20 in its arm | **DROPPED** |
| 3. learnable run-out belief + plan-aware urgency | Locksmith 20/20 with the budget on; Warehouse game overs stay 0 | Locksmith 20/20 (d3_hb, d3_all); Warehouse 0 game overs in every arm | Locksmith below 20/20: not triggered with pick 1 (d3_budget 15/20 is the stage-one hand-off's thrash) | **KEPT** (with pick 1) |

The kept configuration (s1_keep + picks 1 and 3, arm d3_hb) passes both canaries against s1_keep and keeps Warehouse game
overs at zero, but it does not move Warehouse: interact at grab positions is still half of random's. Per the debate,
stage two (goal babbling, contrast fix) waits.

## What was built (each an AgentConfig switch, default off; game-agnostic, no game internals, no language model)

| pick | switch | files | what it does |
|---|---|---|---|
| 1 | `handoff_efe` | explore.py (ExploreConfig.interrupt, z_surprise, min_sur_n; `_check`, `_relative_surprise`, resume_target), agent.py (`_interrupt`) | The trip is an interrupting option. Arrival (new contact), relative surprise (surprisal >= 2 standard deviations above this play's running mean after 20 scored steps, or a spike), blocked and trip end only raise a CHECK; the trip is not cut. At a check every candidate is scored by the EFE policy; the trip is interrupted only if the best action that does not move the self (a button with no learned move, a click; not RESET) has lower G than every moving action (continuing the trip is worth at least the best one-step move). Up to 3 interrupting actions per check, then the same trip resumes: the remaining path if the self stayed, else a new path to the same target first. Blocked keeps its old meaning (the target counts as touched). |
| 2 | `contact_context` (needs use_epistemic) | epistemic.py (ContactContext, beta_eig), policy.py (PolicyConfig.w_ceig; `epistemic`), rules.py (ContextBuilder.contact), agent.py | For a button with no learned move: the context is the soft phasor code of the colours in the self's contact neighbourhood (the strips one learned move away on every side; the facing strip bound with a FACE role; floor left out; touching nothing = its own code). Novelty = 1 / (1 + soft visit count of that code for that button). Effect belief "this button changes something here" = Beta(1 + soft changed, 1 + soft nothing); a similar contact inherits the evidence; its one-press information gain is added to the disagreement term. "Changed" ignores ambient label parts (parts seen on >= 30% of all scored steps, e.g. a ticking bar). |
| 3 | `budget_learn` (needs use_budget) | budget.py (LivesReader; BudgetConfig.learn_end, eps, lr_counter, w_info; p_fatal, p_over, info, urgency), policy.py, agent.py | Lives reader: on a level's first board, >= 2 identical small items (<= 9 cells, one row, gaps <= 3) inside the draining gauge's own rows = a counter; its value = items still shown. End belief as two hypotheses, FATAL vs LIFE; prior mean 0.8 fatal (stage one's); a survived run-out (refill without a RESET) multiplies the odds of FATAL by 0.05/0.95; a counter showing spare lives counts as evidence for LIFE with likelihood ratio 30 (a stated prior, not fitted). P(game over when the bar runs out) = P(FATAL) + P(LIFE) x (0 with spare lives, 1 on the last life, 1/2 with no counter). Information value (only while spare lives show, never for RESET): the belief's entropy, weighted like the risk; G gains w x (risk x -c_game_over - info). Urgent only if the current trip's / replay's remaining steps do not fit in the steps left and running out costs more than a RESET. |

game_sweep.py: arms d3_handoff (new pick 1 + stage-one budget), d3_contact (s1_both + pick 2), d3_budget (stage-one
hand-off + pick 3), d3_all (all three new), and d3_hb (picks 1 + 3, added after the main sweep because pick 2 had
cost every Ghost Twin clear); per-play fields for checks / interruptions / resumes, contact presses, lives / tests /
plan-fits / cheap-end steps / final P(fatal). Tests: 91 passed, 1 failed (the pre-existing
test_salience_ranks_disagreement_first); tests/test_debate3.py has 20 new.

## How each pick behaved

**Pick 1.** On Locksmith every button moves the self, so no check can ever interrupt (0 interruptions in 20 plays of
d3_handoff and d3_hb; 4 in d3_all, in the opening, before every arrow's move was learned): the Locksmith repair is
structural. The trip is no
longer cut, which is exactly what stage one's thrash needed; d3_hb's Locksmith plays equal s1_keep's in clears, actions,
end state and press counts on all 20 seeds.
Relative surprise: a play's step surprisal averages ~0.6-0.7 nats (sd ~0.9) on Locksmith and ~1.9 (sd ~2.2) on
Warehouse, so the fixed 2.5 nats meant very different things in the two games. Surprise checks per play (alone or with
arrival) fell on Warehouse from ~37 (stage one's cuts) to ~12; on Locksmith and Ghost Twin they were few either way
(~7 and ~5). On Warehouse
~200 checks per play led to ~7.5 interruptions; where an interruption happened at a grab position it pressed interact
every time (40 of 40 in d3_hb, 69 of 69 in d3_all), and trips were resumed after interruptions (13 in d3_hb). But the
explorer walked through 501 grab positions without being interrupted: the best one-step move's G usually beats
interact's, so the comparison says "go on". Ghost Twin: interrupts rarely (8 of 20 plays, <1 per play).

**Pick 2.** On Warehouse it raises interact at grab positions a little (8% -> 10%; 13% with pick 1, where the explorer
preempted more often: 1093 preemptions vs 717) and grabs / drops rise (98 -> 131 grabs; 189 with all three). On Ghost
Twin every button (including the fifth) ends up with a learned move in every play, so the contact context acts only in
the opening steps before that (~15 presses per play); the plays diverge from there and the four late clears were lost
in both arms that carry it. That is a trajectory effect, not a lasting behaviour, but the guard rule is the guard rule.

**Pick 3.** The lives reader found Locksmith's three-life counter in 20 of 20 plays and nothing on Warehouse or Ghost
Twin (checked also on random play boards). On Locksmith the agent now lets the bar run out (216 run-outs met with
spare lives in d3_hb, 0 game overs; P(fatal) ends at ~0; a RESET gives the lives back); it was never urgent. Because the
counter prior already makes running out cheap there, the first test happens at once; the information term only adds to
that. On Warehouse and Ghost Twin (no counter) it made no decision differently from the stage-one budget: d3_budget
equals s1_both in all 40 plays there, and d3_hb equals d3_handoff in 38 of 40.

## Next

- Warehouse is still the problem: interact at grab positions is half of random's. The interruption test compares
  interact with the best MOVE's one-step G, and the moves' own novelty usually wins. Candidates: compare against the
  trip's next step only, or give the trip a value from its target instead of the best move; measure where checks fire
  relative to grab positions.
- Pick 2 might come back if it only switches on once every button has been tried and still has no learned move (then it
  cannot touch the opening of games whose buttons all move, which is what cost Ghost Twin).
- Ghost Twin clears are few and late (4-5 of 20); more seeds before reading anything into one more or one less.

## Files and data

Raw rows: results/game_sweep/debate3/rows.json (360 plays: 6 arms x 3 games x 20 seeds), results/game_sweep/debate3_hb/
rows.json (60 plays), random arm results/game_sweep/dp_random/rows.json (same labeller measures: the labeller
stage1_labels subclasses debate_labels.WarehouseLabels). 500 actions, seeds 0-19, RESET offered, exact simulators, 12
workers, per-play limit 1800 s (no play timed out; median play ~2 minutes). Tables below: results/debate3/tables.md and
tables.json, generated from those rows by ~/bubba-workspace/scratch/debate3/debate3_report.py. Probe:
~/bubba-workspace/scratch/debate3/lives_probe.py.

---

## Warehouse (wa30)

| arm | plays | levels | plays clearing | first clear (median action) | plays clearing level 2 | game overs | time-outs | RESETs per play |
|---|---|---|---|---|---|---|---|---|
| random | 20 | 0 | 0 | None | 0 | 0 | 0 | 78.8 |
| s1_keep | 20 | 0 | 0 | None | 0 | 6 | 0 | 7.2 |
| s1_both | 20 | 0 | 0 | None | 0 | 0 | 0 | 7.75 |
| d3_handoff | 20 | 0 | 0 | None | 0 | 0 | 0 | 7.2 |
| d3_contact | 20 | 0 | 0 | None | 0 | 0 | 0 | 7.85 |
| d3_budget | 20 | 0 | 0 | None | 0 | 0 | 0 | 7.75 |
| d3_all | 20 | 0 | 0 | None | 0 | 0 | 0 | 6.8 |
| d3_hb | 20 | 0 | 0 | None | 0 | 0 | 0 | 7.2 |

| arm | grab positions | interact there | plays with a grab | grabs | drops | box configs (median) | plays: box on target (seeds) | most boxes on target at once |
|---|---|---|---|---|---|---|---|---|
| random | 214 | 41/214 (19%) | 17 | 41 | 20 | 3.5 | 0 (-) | 0 |
| s1_keep | 757 | 62/757 (8%) | 16 | 62 | 16 | 12.0 | 0 (-) | 0 |
| s1_both | 1273 | 98/1273 (8%) | 18 | 98 | 68 | 30.5 | 4 (2, 5, 13, 14) | 2 |
| d3_handoff | 964 | 95/964 (10%) | 18 | 95 | 53 | 28.0 | 2 (10, 13) | 1 |
| d3_contact | 1356 | 131/1356 (10%) | 20 | 131 | 91 | 34.0 | 2 (3, 10) | 1 |
| d3_budget | 1273 | 98/1273 (8%) | 18 | 98 | 68 | 30.5 | 4 (2, 5, 13, 14) | 2 |
| d3_all | 1432 | 189/1432 (13%) | 20 | 189 | 138 | 24.5 | 3 (0, 11, 17) | 1 |
| d3_hb | 964 | 95/964 (10%) | 18 | 95 | 53 | 28.0 | 2 (10, 13) | 1 |

Grab positions by who chose the step, and interact pressed there:

| arm | explorer trip | policy | interruption (pick 1) | archive replay | planner |
|---|---|---|---|---|---|
| s1_keep | 0/449 (0%) | 16/119 (13%) | 0 | 46/189 (24%) | 0 |
| s1_both | 0/196 (0%) | 74/835 (9%) | 0 | 24/242 (10%) | 0 |
| d3_handoff | 0/501 (0%) | 16/202 (8%) | 40/40 (100%) | 39/221 (18%) | 0 |
| d3_contact | 0/207 (0%) | 82/878 (9%) | 0 | 49/271 (18%) | 0 |
| d3_budget | 0/196 (0%) | 74/835 (9%) | 0 | 24/242 (10%) | 0 |
| d3_all | 0/810 (0%) | 29/130 (22%) | 69/69 (100%) | 91/423 (22%) | 0 |
| d3_hb | 0/501 (0%) | 16/202 (8%) | 40/40 (100%) | 39/221 (18%) | 0 |

Steps by who chose them (share of all steps):

| arm | explorer trips | policy | interruptions | archive replays | planner | explorer preemptions (all plays) |
|---|---|---|---|---|---|---|
| s1_keep | 49% | 17% | 0% | 34% | 0% | 624 |
| s1_both | 38% | 44% | 0% | 18% | 0% | 623 |
| d3_handoff | 58% | 15% | 2% | 25% | 0% | 717 |
| d3_contact | 37% | 43% | 0% | 20% | 0% | 1179 |
| d3_budget | 38% | 44% | 0% | 18% | 0% | 623 |
| d3_all | 58% | 15% | 2% | 25% | 0% | 1093 |
| d3_hb | 58% | 15% | 2% | 25% | 0% | 717 |

Stage-one hand-offs per play by trigger (trip cut, policy dwell):

| arm | all | arrival | surprise | arrival + surprise | blocked | trip end |
|---|---|---|---|---|---|---|
| s1_both | 119.2 | 25.9 | 20.1 | 16.6 | 40.2 | 16.6 |
| d3_contact | 113.8 | 26.9 | 20.4 | 17.1 | 35.8 | 13.6 |
| d3_budget | 119.2 | 25.9 | 20.1 | 16.6 | 40.2 | 16.6 |

Pick 1, EFE checks per play by trigger (checks raised / interruptions taken):

| arm | all | arrival | surprise | arrival + surprise | blocked | trip end | plays with an interruption | resumed trips | surprisal mean / sd (median play) |
|---|---|---|---|---|---|---|---|---|---|
| d3_handoff | 199.8 / 7.45 | 38.5 / 2.1 | 4.5 / 0.15 | 7.9 / 0.3 | 117.0 / 3.45 | 32.0 / 1.45 | 18/20 | 13 | 1.936 / 2.1765 |
| d3_all | 186.6 / 9.15 | 41.8 / 3.8 | 4.8 / 0.05 | 8.7 / 0.6 | 103.0 / 3.45 | 28.2 / 1.25 | 18/20 | 36 | 1.9205 / 2.2005 |
| d3_hb | 199.8 / 7.45 | 38.5 / 2.1 | 4.5 / 0.15 | 7.9 / 0.3 | 116.9 / 3.45 | 32.0 / 1.45 | 18/20 | 13 | 1.936 / 2.1765 |

Pick 2, presses of non-moving buttons recorded by the contact memory (all plays):

| arm | presses | changed something |
|---|---|---|
| d3_contact | 863 | 306 |
| d3_all | 959 | 362 |

Budget (all plays of the arm):

| arm | gauge found | plays ever urgent | urgent steps | RESETs while urgent | plays where the gauge ran out | lives counter found | run-out tests (plays) | game overs at a run-out with spare lives | near-end steps: plan fits / cheap | P(fatal) at the end (median) |
|---|---|---|---|---|---|---|---|---|---|---|
| s1_both | 20/20 | 5 | 15 | 5 | 0 | - | - | - | - | - |
| d3_handoff | 20/20 | 7 | 15 | 10 | 0 | - | - | - | - | - |
| d3_contact | 20/20 | 4 | 5 | 4 | 0 | - | - | - | - | - |
| d3_budget | 20/20 | 5 | 15 | 5 | 0 | 0/20 | 0 (0) | 0 | 0 / 0 | 0.8 |
| d3_all | 20/20 | 6 | 7 | 7 | 0 | 0/20 | 0 (0) | 0 | 1 / 0 | 0.8 |
| d3_hb | 20/20 | 6 | 13 | 10 | 0 | 0/20 | 0 (0) | 0 | 3 / 0 | 0.8 |

## Locksmith (ls20)

| arm | plays | levels | plays clearing | first clear (median action) | plays clearing level 2 | game overs | time-outs | RESETs per play |
|---|---|---|---|---|---|---|---|---|
| s1_keep | 20 | 20 | 20 | 47.0 | 0 | 0 | 0 | 12.0 |
| s1_both | 20 | 13 | 13 | 349 | 0 | 0 | 0 | 24.3 |
| d3_handoff | 20 | 18 | 18 | 46.5 | 0 | 0 | 0 | 15.6 |
| d3_contact | 20 | 8 | 8 | 276.5 | 0 | 0 | 0 | 22.2 |
| d3_budget | 20 | 15 | 15 | 217 | 0 | 0 | 0 | 16.6 |
| d3_all | 20 | 20 | 20 | 43.0 | 0 | 0 | 0 | 12.7 |
| d3_hb | 20 | 20 | 20 | 47.0 | 0 | 0 | 0 | 12.0 |

Steps by who chose them (share of all steps):

| arm | explorer trips | policy | interruptions | archive replays | planner | explorer preemptions (all plays) |
|---|---|---|---|---|---|---|
| s1_keep | 56% | 5% | 0% | 39% | 0% | 55 |
| s1_both | 47% | 32% | 0% | 21% | 0% | 29 |
| d3_handoff | 61% | 8% | 0% | 31% | 0% | 55 |
| d3_contact | 45% | 30% | 0% | 25% | 0% | 19 |
| d3_budget | 51% | 31% | 0% | 18% | 0% | 29 |
| d3_all | 55% | 5% | 0% | 40% | 0% | 13 |
| d3_hb | 56% | 5% | 0% | 39% | 0% | 55 |

Stage-one hand-offs per play by trigger (trip cut, policy dwell):

| arm | all | arrival | surprise | arrival + surprise | blocked | trip end |
|---|---|---|---|---|---|---|
| s1_both | 95.3 | 30.8 | 4.3 | 3.3 | 4.7 | 52.2 |
| d3_contact | 92.2 | 29.4 | 4.5 | 2.6 | 4.6 | 51.0 |
| d3_budget | 103.1 | 34.0 | 11.7 | 4.2 | 8.4 | 44.7 |

Pick 1, EFE checks per play by trigger (checks raised / interruptions taken):

| arm | all | arrival | surprise | arrival + surprise | blocked | trip end | plays with an interruption | resumed trips | surprisal mean / sd (median play) |
|---|---|---|---|---|---|---|---|---|---|
| d3_handoff | 141.6 / 0.0 | 79.0 / 0.0 | 2.0 / 0.0 | 1.7 / 0.0 | 38.6 / 0.0 | 20.2 / 0.0 | 0/20 | 0 | 0.6094999999999999 / 0.9305000000000001 |
| d3_all | 137.4 / 0.2 | 87.2 / 0.0 | 2.9 / 0.0 | 3.1 / 0.15 | 32.6 / 0.05 | 11.6 / 0.0 | 4/20 | 3 | 0.666 / 0.8825000000000001 |
| d3_hb | 137.7 / 0.0 | 85.2 / 0.0 | 3.6 / 0.0 | 3.1 / 0.0 | 33.2 / 0.0 | 12.4 / 0.0 | 0/20 | 0 | 0.6815 / 0.894 |

Pick 2, presses of non-moving buttons recorded by the contact memory (all plays):

| arm | presses | changed something |
|---|---|---|
| d3_contact | 150 | 129 |
| d3_all | 150 | 129 |

Budget (all plays of the arm):

| arm | gauge found | plays ever urgent | urgent steps | RESETs while urgent | plays where the gauge ran out | lives counter found | run-out tests (plays) | game overs at a run-out with spare lives | near-end steps: plan fits / cheap | P(fatal) at the end (median) |
|---|---|---|---|---|---|---|---|---|---|---|
| s1_both | 20/20 | 20 | 554 | 160 | 1 | - | - | - | - | - |
| d3_handoff | 20/20 | 20 | 564 | 242 | 0 | - | - | - | - | - |
| d3_contact | 20/20 | 20 | 484 | 162 | 0 | - | - | - | - | - |
| d3_budget | 20/20 | 7 | 23 | 7 | 20 | 20/20 | 97 (20) | 0 | 148 / 998 | 0.0 |
| d3_all | 20/20 | 0 | 0 | 0 | 20 | 20/20 | 214 (20) | 0 | 227 / 1377 | 0.0 |
| d3_hb | 20/20 | 0 | 0 | 0 | 20 | 20/20 | 216 (20) | 0 | 247 / 1365 | 0.0 |

First clear per seed (action; - = no clear), and seeds where an arm lost a clear s1_keep had:

| arm | 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 | 11 | 12 | 13 | 14 | 15 | 16 | 17 | 18 | 19 | lost vs s1_keep | gained vs s1_keep |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| s1_keep | 54 | 47 | 29 | 47 | 40 | 89 | 52 | 28 | 76 | 38 | 46 | 39 | 76 | 90 | 42 | 50 | 54 | 45 | 76 | 46 | none | none |
| s1_both | - | 360 | 255 | 253 | 349 | 403 | 94 | - | 226 | 499 | 385 | - | 208 | 469 | - | - | 258 | - | - | 474 | 0, 7, 11, 14, 15, 17, 18 | none |
| d3_handoff | 54 | 47 | 29 | 315 | 40 | - | 52 | 28 | 121 | 38 | 46 | 39 | 162 | - | 42 | 50 | 54 | 45 | 327 | 46 | 5, 13 | none |
| d3_contact | - | 327 | - | - | - | 329 | - | - | - | - | 41 | - | 439 | 198 | - | - | 125 | 226 | 366 | - | 0, 2, 3, 4, 6, 7, 8, 9, 11, 14, 15, 19 | none |
| d3_budget | - | - | 77 | 217 | 77 | 433 | - | 120 | 416 | 403 | 91 | 74 | - | 409 | 75 | 106 | 310 | 272 | - | 479 | 0, 1, 6, 12, 18 | none |
| d3_all | 35 | 97 | 42 | 41 | 45 | 44 | 68 | 46 | 46 | 35 | 39 | 39 | 34 | 42 | 45 | 48 | 31 | 36 | 46 | 46 | none | none |
| d3_hb | 54 | 47 | 29 | 47 | 40 | 89 | 52 | 28 | 76 | 38 | 46 | 39 | 76 | 90 | 42 | 50 | 54 | 45 | 76 | 46 | none | none |

## Ghost Twin (g50t)

| arm | plays | levels | plays clearing | first clear (median action) | plays clearing level 2 | game overs | time-outs | RESETs per play |
|---|---|---|---|---|---|---|---|---|
| s1_keep | 20 | 4 | 4 | 263.5 | 0 | 4 | 0 | 12.25 |
| s1_both | 20 | 2 | 2 | 228.0 | 0 | 0 | 0 | 13.6 |
| d3_handoff | 20 | 5 | 5 | 323 | 0 | 2 | 0 | 13.0 |
| d3_contact | 20 | 0 | 0 | None | 0 | 1 | 0 | 15.05 |
| d3_budget | 20 | 2 | 2 | 228.0 | 0 | 0 | 0 | 13.6 |
| d3_all | 20 | 0 | 0 | None | 0 | 2 | 0 | 12.95 |
| d3_hb | 20 | 5 | 5 | 323 | 0 | 2 | 0 | 12.95 |

Steps by who chose them (share of all steps):

| arm | explorer trips | policy | interruptions | archive replays | planner | explorer preemptions (all plays) |
|---|---|---|---|---|---|---|
| s1_keep | 42% | 34% | 0% | 24% | 0% | 193 |
| s1_both | 34% | 42% | 0% | 24% | 0% | 179 |
| d3_handoff | 41% | 31% | 0% | 28% | 0% | 177 |
| d3_contact | 32% | 44% | 0% | 23% | 0% | 193 |
| d3_budget | 34% | 42% | 0% | 24% | 0% | 179 |
| d3_all | 40% | 33% | 0% | 27% | 0% | 205 |
| d3_hb | 41% | 31% | 0% | 28% | 0% | 177 |

Stage-one hand-offs per play by trigger (trip cut, policy dwell):

| arm | all | arrival | surprise | arrival + surprise | blocked | trip end |
|---|---|---|---|---|---|---|
| s1_both | 118.2 | 4.5 | 4.0 | 0.5 | 16.7 | 92.5 |
| d3_contact | 120.4 | 1.8 | 5.2 | 0.6 | 14.8 | 98.2 |
| d3_budget | 118.2 | 4.5 | 4.0 | 0.5 | 16.7 | 92.5 |

Pick 1, EFE checks per play by trigger (checks raised / interruptions taken):

| arm | all | arrival | surprise | arrival + surprise | blocked | trip end | plays with an interruption | resumed trips | surprisal mean / sd (median play) |
|---|---|---|---|---|---|---|---|---|---|
| d3_handoff | 133.6 / 0.75 | 4.0 / 0.25 | 4.2 / 0.1 | 1.1 / 0.0 | 48.9 / 0.25 | 75.5 / 0.15 | 8/20 | 4 | 1.3079999999999998 / 1.565 |
| d3_all | 141.9 / 0.9 | 2.4 / 0.25 | 3.4 / 0.05 | 0.9 / 0.0 | 48.5 / 0.2 | 86.8 / 0.4 | 10/20 | 0 | 1.1400000000000001 / 1.5165 |
| d3_hb | 133.3 / 0.75 | 4.0 / 0.25 | 4.2 / 0.1 | 1.1 / 0.0 | 48.4 / 0.25 | 75.7 / 0.15 | 8/20 | 4 | 1.3079999999999998 / 1.565 |

Pick 2, presses of non-moving buttons recorded by the contact memory (all plays):

| arm | presses | changed something |
|---|---|---|
| d3_contact | 281 | 146 |
| d3_all | 297 | 141 |

Budget (all plays of the arm):

| arm | gauge found | plays ever urgent | urgent steps | RESETs while urgent | plays where the gauge ran out | lives counter found | run-out tests (plays) | game overs at a run-out with spare lives | near-end steps: plan fits / cheap | P(fatal) at the end (median) |
|---|---|---|---|---|---|---|---|---|---|---|
| s1_both | 20/20 | 9 | 21 | 10 | 0 | - | - | - | - | - |
| d3_handoff | 20/20 | 4 | 15 | 5 | 0 | - | - | - | - | - |
| d3_contact | 20/20 | 2 | 8 | 3 | 0 | - | - | - | - | - |
| d3_budget | 20/20 | 9 | 21 | 10 | 0 | 0/20 | 0 (0) | 0 | 0 / 0 | 0.8 |
| d3_all | 20/20 | 3 | 6 | 3 | 0 | 0/20 | 0 (0) | 0 | 1 / 0 | 0.8 |
| d3_hb | 20/20 | 4 | 10 | 4 | 0 | 0/20 | 0 (0) | 0 | 2 / 0 | 0.8 |

First clear per seed (action; - = no clear), and seeds where an arm lost a clear s1_keep had:

| arm | 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 | 11 | 12 | 13 | 14 | 15 | 16 | 17 | 18 | 19 | lost vs s1_keep | gained vs s1_keep |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| s1_keep | - | - | - | - | 461 | 228 | - | - | - | - | - | - | - | - | - | - | - | 299 | - | 54 | none | none |
| s1_both | - | - | - | - | - | 139 | - | - | - | - | - | - | - | - | - | - | - | 317 | - | - | 4, 19 | none |
| d3_handoff | - | - | - | - | 427 | 228 | - | 494 | - | - | - | - | - | - | - | - | - | 323 | - | 54 | none | 7 |
| d3_contact | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | 4, 5, 17, 19 | none |
| d3_budget | - | - | - | - | - | 139 | - | - | - | - | - | - | - | - | - | - | - | 317 | - | - | 4, 19 | none |
| d3_all | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | 4, 5, 17, 19 | none |
| d3_hb | - | - | - | - | 427 | 228 | - | 494 | - | - | - | - | - | - | - | - | - | 323 | - | 54 | none | 7 |

Rerun baselines vs the stage-one sweep (results/game_sweep/s1_main), plays equal in levels, clears, actions, end state and presses:

- g50t/s1_both: 20/20
- g50t/s1_keep: 20/20
- ls20/s1_both: 20/20
- ls20/s1_keep: 20/20
- wa30/s1_both: 20/20
- wa30/s1_keep: 20/20

