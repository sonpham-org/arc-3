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

