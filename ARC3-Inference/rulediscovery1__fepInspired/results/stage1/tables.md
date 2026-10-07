## Warehouse (wa30)

| arm | plays | levels | plays clearing | first clear (median action) | plays clearing level 2 | game overs | time-outs | median actions | RESETs per play |
|---|---|---|---|---|---|---|---|---|---|
| random | 20 | 0 | 0 | None | 0 | 0 | 0 | 500.0 | 78.8 |
| touch_tl | 20 | 0 | 0 | None | 0 | 2 | 0 | 500.0 | 8.8 |
| dp_all | 20 | 0 | 0 | None | 0 | 6 | 0 | 500.0 | 7.2 |
| s1_keep | 20 | 0 | 0 | None | 0 | 6 | 0 | 500.0 | 7.2 |
| s1_handoff | 20 | 0 | 0 | None | 0 | 4 | 0 | 500.0 | 7.2 |
| s1_budget | 20 | 0 | 0 | None | 0 | 0 | 0 | 500.0 | 8.55 |
| s1_both | 20 | 0 | 0 | None | 0 | 0 | 0 | 500.0 | 7.75 |

| arm | grab positions | interact there | plays with a grab | grabs | drops | box configs (median) | plays with a new config | plays: box on target | self kept (turn steps) |
|---|---|---|---|---|---|---|---|---|---|
| random | 214 | 41/214 (19%) | 17 | 41 | 20 | 3.5 | 13 | 0 | - |
| touch_tl | 551 | 18/551 (3%) | 11 | 18 | 12 | 5.0 | 11 | 0 | 79/5017 (2%) |
| dp_all | 757 | 62/757 (8%) | 16 | 62 | 16 | 12.0 | 16 | 0 | 3263/3809 (86%) |
| s1_keep | 757 | 62/757 (8%) | 16 | 62 | 16 | 12.0 | 16 | 0 | 3263/3809 (86%) |
| s1_handoff | 1156 | 92/1156 (8%) | 18 | 92 | 64 | 30.0 | 18 | 4 | 3736/4574 (82%) |
| s1_budget | 964 | 67/964 (7%) | 17 | 67 | 19 | 14.0 | 17 | 0 | 3736/4543 (82%) |
| s1_both | 1273 | 98/1273 (8%) | 18 | 98 | 68 | 30.5 | 18 | 4 | 4028/4866 (83%) |

Grab positions by who chose the step, and interact pressed there:

| arm | explorer trip (touch) | policy (efe) | archive replay (return) | planner (plan) |
|---|---|---|---|---|
| touch_tl | 0/323 (0%) | 18/228 (8%) | 0 | 0 |
| dp_all | 0/449 (0%) | 16/119 (13%) | 46/189 (24%) | 0 |
| s1_keep | 0/449 (0%) | 16/119 (13%) | 46/189 (24%) | 0 |
| s1_handoff | 0/182 (0%) | 72/780 (9%) | 20/194 (10%) | 0 |
| s1_budget | 0/543 (0%) | 18/123 (15%) | 49/298 (16%) | 0 |
| s1_both | 0/196 (0%) | 74/835 (9%) | 24/242 (10%) | 0 |

Steps by who chose them (share of all steps played):

| arm | explorer trips | policy | archive replays | planner |
|---|---|---|---|---|
| touch_tl | 25% | 75% | 0% | 0% |
| dp_all | 49% | 17% | 34% | 0% |
| s1_keep | 49% | 17% | 34% | 0% |
| s1_handoff | 38% | 45% | 17% | 0% |
| s1_budget | 50% | 15% | 35% | 0% |
| s1_both | 38% | 44% | 18% | 0% |

Hand-offs per play by trigger (explorer trip ended, policy given the choice):

| arm | all | arrival | surprise | arrival + surprise | blocked | trip end | trip steps | policy steps in a dwell |
|---|---|---|---|---|---|---|---|---|
| s1_handoff | 112.2 | 24.3 | 18.7 | 15.7 | 38.1 | 15.4 | 3569 | 2897 |
| s1_both | 119.2 | 25.9 | 20.1 | 16.6 | 40.2 | 16.6 | 3809 | 3051 |

Budget (all plays of the arm):

| arm | plays with a gauge found | found at (median step) | plays ever urgent | urgent steps | RESETs chosen while urgent | archive returns from them | trips / replays dropped | plays where the gauge ran out |
|---|---|---|---|---|---|---|---|---|
| s1_budget | 20/20 | 17.0 | 6 | 12 | 7 | 0 | 5 | 0 |
| s1_both | 20/20 | 17.0 | 5 | 15 | 5 | 3 | 2 | 0 |

## Locksmith (ls20)

| arm | plays | levels | plays clearing | first clear (median action) | plays clearing level 2 | game overs | time-outs | median actions | RESETs per play |
|---|---|---|---|---|---|---|---|---|---|
| touch_tl | 20 | 20 | 20 | 48.5 | 0 | 20 | 0 | 185.0 | 4.35 |
| dp_all | 20 | 20 | 20 | 47.0 | 0 | 0 | 0 | 500.0 | 12.0 |
| s1_keep | 20 | 20 | 20 | 47.0 | 0 | 0 | 0 | 500.0 | 12.0 |
| s1_handoff | 20 | 15 | 15 | 272 | 0 | 5 | 0 | 500.0 | 14.4 |
| s1_budget | 20 | 18 | 18 | 46.5 | 0 | 0 | 0 | 500.0 | 16.0 |
| s1_both | 20 | 13 | 13 | 349 | 0 | 0 | 0 | 500.0 | 24.3 |

Steps by who chose them (share of all steps played):

| arm | explorer trips | policy | archive replays | planner |
|---|---|---|---|---|
| touch_tl | 78% | 22% | 0% | 0% |
| dp_all | 56% | 5% | 39% | 0% |
| s1_keep | 56% | 5% | 39% | 0% |
| s1_handoff | 52% | 31% | 16% | 0% |
| s1_budget | 59% | 10% | 31% | 0% |
| s1_both | 47% | 32% | 21% | 0% |

Hand-offs per play by trigger (explorer trip ended, policy given the choice):

| arm | all | arrival | surprise | arrival + surprise | blocked | trip end | trip steps | policy steps in a dwell |
|---|---|---|---|---|---|---|---|---|
| s1_handoff | 93.7 | 28.0 | 11.1 | 3.9 | 8.2 | 42.5 | 4766 | 2225 |
| s1_both | 95.3 | 30.8 | 4.3 | 3.3 | 4.7 | 52.2 | 4710 | 2101 |

Budget (all plays of the arm):

| arm | plays with a gauge found | found at (median step) | plays ever urgent | urgent steps | RESETs chosen while urgent | archive returns from them | trips / replays dropped | plays where the gauge ran out |
|---|---|---|---|---|---|---|---|---|
| s1_budget | 20/20 | 8.0 | 20 | 588 | 244 | 242 | 232 | 0 |
| s1_both | 20/20 | 8.0 | 20 | 554 | 160 | 159 | 67 | 1 |

First clears (action), per play that cleared:

- touch_tl: 32, 32, 32, 35, 37, 40, 42, 48, 48, 48, 49, 49, 51, 52, 53, 59, 60, 60, 60, 66
- dp_all: 28, 29, 38, 39, 40, 42, 45, 46, 46, 47, 47, 50, 52, 54, 54, 76, 76, 76, 89, 90
- s1_keep: 28, 29, 38, 39, 40, 42, 45, 46, 46, 47, 47, 50, 52, 54, 54, 76, 76, 76, 89, 90
- s1_handoff: 74, 75, 77, 77, 91, 106, 120, 272, 287, 310, 403, 409, 416, 433, 479
- s1_budget: 28, 29, 38, 39, 40, 42, 45, 46, 46, 47, 50, 52, 54, 54, 121, 162, 315, 327
- s1_both: 94, 208, 226, 253, 255, 258, 349, 360, 385, 403, 469, 474, 499

## Ghost Twin (g50t)

| arm | plays | levels | plays clearing | first clear (median action) | plays clearing level 2 | game overs | time-outs | median actions | RESETs per play |
|---|---|---|---|---|---|---|---|---|---|
| touch_tl | 20 | 0 | 0 | None | 0 | 13 | 0 | 330.0 | 9.15 |
| dp_all | 20 | 4 | 4 | 263.5 | 0 | 4 | 0 | 500.0 | 12.25 |
| s1_keep | 20 | 4 | 4 | 263.5 | 0 | 4 | 0 | 500.0 | 12.25 |
| s1_handoff | 20 | 2 | 2 | 228.0 | 0 | 7 | 0 | 500.0 | 10.85 |
| s1_budget | 20 | 4 | 4 | 263.5 | 0 | 1 | 0 | 500.0 | 13.35 |
| s1_both | 20 | 2 | 2 | 228.0 | 0 | 0 | 0 | 500.0 | 13.6 |

Steps by who chose them (share of all steps played):

| arm | explorer trips | policy | archive replays | planner |
|---|---|---|---|---|
| touch_tl | 30% | 70% | 0% | 0% |
| dp_all | 42% | 34% | 24% | 0% |
| s1_keep | 42% | 34% | 24% | 0% |
| s1_handoff | 36% | 46% | 18% | 0% |
| s1_budget | 41% | 30% | 30% | 0% |
| s1_both | 34% | 42% | 24% | 0% |

Hand-offs per play by trigger (explorer trip ended, policy given the choice):

| arm | all | arrival | surprise | arrival + surprise | blocked | trip end | trip steps | policy steps in a dwell |
|---|---|---|---|---|---|---|---|---|
| s1_handoff | 94.9 | 4.0 | 3.4 | 0.5 | 15.2 | 71.8 | 2770 | 2080 |
| s1_both | 118.2 | 4.5 | 4.0 | 0.5 | 16.7 | 92.5 | 3396 | 2580 |

Budget (all plays of the arm):

| arm | plays with a gauge found | found at (median step) | plays ever urgent | urgent steps | RESETs chosen while urgent | archive returns from them | trips / replays dropped | plays where the gauge ran out |
|---|---|---|---|---|---|---|---|---|
| s1_budget | 20/20 | 14.0 | 4 | 14 | 6 | 6 | 2 | 0 |
| s1_both | 20/20 | 14.0 | 9 | 21 | 10 | 7 | 2 | 0 |

First clears (action), per play that cleared:

- touch_tl: none
- dp_all: 54, 228, 299, 461
- s1_keep: 54, 228, 299, 461
- s1_handoff: 139, 317
- s1_budget: 54, 228, 299, 461
- s1_both: 139, 317

