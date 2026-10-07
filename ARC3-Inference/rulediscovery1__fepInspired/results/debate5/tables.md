## Warehouse (wa30)

| arm | plays | levels | plays clearing level 1 | plays clearing level 2 | first clear (median action) | level 2 length (median) | game overs | RESETs per play | time-outs | play seconds (median) |
|---|---|---|---|---|---|---|---|---|---|---|
| random | 20 | 0 | 0 | 0 | None | None | 0 | 78.8 | 0 | 0.1 |
| d4_opt | 20 | 1 | 1 | 0 | 151 | None | 1 | 6.15 | 0 | 184.7 |
| d5_flat | 20 | 0 | 0 | 0 | None | None | 0 | 5.2 | 0 | 186.95 |
| d5_lib | 20 | 1 | 1 | 0 | 151 | None | 1 | 6.1 | 0 | 192.85 |
| d5_both | 20 | 0 | 0 | 0 | None | None | 0 | 5.1 | 0 | 195.9 |
| d5_flat_notry | 20 | 0 | 0 | 0 | None | None | 0 | 5.55 | 0 | 193.85 |

| arm | grab positions | interact there | grabs | drops | plays: box on target (seeds) | most on target |
|---|---|---|---|---|---|---|
| random | 214 | 41/214 (19%) | 41 | 20 | 0 (-) | 0 |
| d4_opt | 1250 | 218/1250 (17%) | 218 | 178 | 7 (0, 9, 11, 13, 16, 18, 19) | 3 |
| d5_flat | 2056 | 771/2056 (38%) | 771 | 727 | 14 (0, 1, 2, 5, 6, 8, 9, 10, 11, 12, 13, 14, 15, 17) | 2 |
| d5_lib | 1117 | 193/1117 (17%) | 193 | 149 | 9 (0, 2, 6, 9, 11, 13, 17, 18, 19) | 3 |
| d5_both | 2015 | 753/2015 (37%) | 753 | 709 | 14 (0, 1, 2, 5, 6, 8, 9, 10, 11, 12, 13, 14, 15, 17) | 2 |
| d5_flat_notry | 1942 | 692/1942 (36%) | 692 | 656 | 14 (0, 1, 2, 3, 5, 6, 7, 8, 9, 11, 12, 13, 16, 19) | 2 |

| arm | seeds clearing | seeds clearing level 2 | vs d4_opt: clears (arm / base), seeds up / down, sign p | lost | gained |
|---|---|---|---|---|---|
| d4_opt | 11 | - | - | - | - |
| d5_flat | - | - | 0 / 1, 0 / 1, 1.0 | 11 | - |
| d5_lib | 11 | - | 1 / 1, 0 / 0, 1.0 | - | - |
| d5_both | - | - | 0 / 1, 0 / 1, 1.0 | 11 | - |
| d5_flat_notry | - | - | 0 / 1, 0 / 1, 1.0 | 11 | - |

Re-learning after a restart (actions until the MAP rule set is right on 5 scored steps in a row; censored = the next restart or the end came first; kept / MAP = the rule set that was MAP just before is still a hypothesis / still MAP 10 actions later, restarts where it was not counts-only):

| arm | kind | restarts (per play) | re-learned (median actions) | censored | kept at +10 | MAP at +10 |
|---|---|---|---|---|---|---|
| d4_opt | clear | 1 (0.05) | 33 | 0 | 0/1 | 0/1 |
| d4_opt | reset | 123 (6.15) | 19 | 16 | 90/99 | 85/99 |
| d5_flat | reset | 104 (5.2) | 33 | 27 | 75/79 | 72/79 |
| d5_lib | clear | 1 (0.05) | 33 | 0 | 1/1 | 0/1 |
| d5_lib | reset | 122 (6.1) | 19 | 19 | 85/96 | 75/96 |
| d5_both | reset | 102 (5.1) | 35.0 | 26 | 69/78 | 64/78 |
| d5_flat_notry | reset | 111 (5.55) | 23 | 28 | 84/86 | 78/86 |

| arm | library sets (median) | library rules (median) | sets re-seeded per play |
|---|---|---|---|
| d5_lib | 6.0 | 13.0 | 10.3 |
| d5_both | 6.0 | 13.0 | 5.75 |

| arm | try-once presses | per play | would have pressed anyway (G button < G continuing) | comparison interruptions per play |
|---|---|---|---|---|
| d4_opt | 58 | 2.9 | 2 | 14.35 |
| d5_flat | 52 | 2.6 | 8 | 81.85 |
| d5_lib | 55 | 2.75 | 2 | 12.45 |
| d5_both | 52 | 2.6 | 9 | 80.2 |
| d5_flat_notry | 0 | 0.0 | 0 | 80.75 |

## Locksmith (ls20)

| arm | plays | levels | plays clearing level 1 | plays clearing level 2 | first clear (median action) | level 2 length (median) | game overs | RESETs per play | time-outs | play seconds (median) |
|---|---|---|---|---|---|---|---|---|---|---|
| d4_opt | 20 | 20 | 20 | 0 | 47.0 | None | 0 | 11.95 | 0 | 125.8 |
| d5_flat | 20 | 20 | 20 | 0 | 50.0 | None | 0 | 11.95 | 0 | 124.69999999999999 |
| d5_lib | 20 | 20 | 20 | 0 | 46.5 | None | 0 | 12.35 | 0 | 129.9 |
| d5_both | 20 | 20 | 20 | 0 | 48.0 | None | 0 | 12.3 | 0 | 125.65 |
| d5_flat_notry | 20 | 20 | 20 | 0 | 50.0 | None | 0 | 11.95 | 0 | 125.6 |

| arm | seeds clearing | seeds clearing level 2 | vs d4_opt: clears (arm / base), seeds up / down, sign p | lost | gained |
|---|---|---|---|---|---|
| d4_opt | 0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19 | - | - | - | - |
| d5_flat | 0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19 | - | 20 / 20, 0 / 0, 1.0 | - | - |
| d5_lib | 0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19 | - | 20 / 20, 0 / 0, 1.0 | - | - |
| d5_both | 0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19 | - | 20 / 20, 0 / 0, 1.0 | - | - |
| d5_flat_notry | 0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19 | - | 20 / 20, 0 / 0, 1.0 | - | - |

Re-learning after a restart (actions until the MAP rule set is right on 5 scored steps in a row; censored = the next restart or the end came first; kept / MAP = the rule set that was MAP just before is still a hypothesis / still MAP 10 actions later, restarts where it was not counts-only):

| arm | kind | restarts (per play) | re-learned (median actions) | censored | kept at +10 | MAP at +10 |
|---|---|---|---|---|---|---|
| d4_opt | clear | 20 (1.0) | 14.5 | 2 | 15/20 | 14/20 |
| d4_opt | reset | 239 (11.95) | 5 | 42 | 185/186 | 175/186 |
| d4_opt | life | 220 (11.0) | 5.0 | 176 | 39/45 | 26/45 |
| d5_flat | clear | 20 (1.0) | 11 | 1 | 15/20 | 12/20 |
| d5_flat | reset | 239 (11.95) | 5.0 | 43 | 188/188 | 177/188 |
| d5_flat | life | 219 (10.95) | 5 | 172 | 43/47 | 28/47 |
| d5_lib | clear | 20 (1.0) | 12 | 3 | 16/20 | 11/20 |
| d5_lib | reset | 247 (12.35) | 5.0 | 49 | 187/189 | 179/189 |
| d5_lib | life | 219 (10.95) | 5.0 | 177 | 39/44 | 34/44 |
| d5_both | clear | 20 (1.0) | 15.5 | 4 | 17/20 | 13/20 |
| d5_both | reset | 246 (12.3) | 5.0 | 46 | 190/192 | 187/192 |
| d5_both | life | 219 (10.95) | 5 | 176 | 43/46 | 36/46 |
| d5_flat_notry | clear | 20 (1.0) | 11 | 1 | 15/20 | 12/20 |
| d5_flat_notry | reset | 239 (11.95) | 5.0 | 43 | 188/188 | 177/188 |
| d5_flat_notry | life | 219 (10.95) | 5 | 172 | 43/47 | 28/47 |

| arm | library sets (median) | library rules (median) | sets re-seeded per play |
|---|---|---|---|
| d5_lib | 5.0 | 6.0 | 55.05 |
| d5_both | 5.0 | 6.0 | 53.45 |

| arm | try-once presses | per play | would have pressed anyway (G button < G continuing) | comparison interruptions per play |
|---|---|---|---|---|
| d4_opt | 4 | 0.2 | 0 | 0.0 |
| d5_flat | 0 | 0.0 | 0 | 0.15 |
| d5_lib | 2 | 0.1 | 0 | 0.05 |
| d5_both | 0 | 0.0 | 0 | 0.0 |
| d5_flat_notry | 0 | 0.0 | 0 | 0.15 |

First clears per seed (action of level 1, level 2):

- d4_opt: 0: [48]; 1: [47]; 2: [29]; 3: [47]; 4: [40]; 5: [89]; 6: [47]; 7: [28]; 8: [76]; 9: [38]; 10: [46]; 11: [39]; 12: [76]; 13: [90]; 14: [42]; 15: [50]; 16: [48]; 17: [45]; 18: [76]; 19: [46]
- d5_flat: 0: [48]; 1: [50]; 2: [29]; 3: [42]; 4: [88]; 5: [89]; 6: [47]; 7: [51]; 8: [76]; 9: [56]; 10: [38]; 11: [39]; 12: [76]; 13: [90]; 14: [44]; 15: [50]; 16: [48]; 17: [45]; 18: [76]; 19: [76]
- d5_lib: 0: [50]; 1: [47]; 2: [29]; 3: [47]; 4: [40]; 5: [36]; 6: [47]; 7: [28]; 8: [76]; 9: [38]; 10: [46]; 11: [39]; 12: [76]; 13: [90]; 14: [42]; 15: [50]; 16: [57]; 17: [45]; 18: [76]; 19: [46]
- d5_both: 0: [46]; 1: [50]; 2: [29]; 3: [42]; 4: [88]; 5: [36]; 6: [37]; 7: [51]; 8: [76]; 9: [40]; 10: [38]; 11: [39]; 12: [76]; 13: [90]; 14: [44]; 15: [50]; 16: [57]; 17: [45]; 18: [76]; 19: [76]
- d5_flat_notry: 0: [48]; 1: [50]; 2: [29]; 3: [42]; 4: [88]; 5: [89]; 6: [47]; 7: [51]; 8: [76]; 9: [56]; 10: [38]; 11: [39]; 12: [76]; 13: [90]; 14: [44]; 15: [50]; 16: [48]; 17: [45]; 18: [76]; 19: [76]

## Ghost Twin (g50t)

| arm | plays | levels | plays clearing level 1 | plays clearing level 2 | first clear (median action) | level 2 length (median) | game overs | RESETs per play | time-outs | play seconds (median) |
|---|---|---|---|---|---|---|---|---|---|---|
| d4_opt | 20 | 5 | 5 | 0 | 228 | None | 3 | 11.15 | 0 | 119.35 |
| d5_flat | 20 | 5 | 5 | 0 | 222 | None | 1 | 14.55 | 0 | 125.05000000000001 |
| d5_lib | 20 | 3 | 3 | 0 | 203 | None | 2 | 10.5 | 0 | 129.1 |
| d5_both | 20 | 7 | 7 | 0 | 222 | None | 1 | 14.05 | 0 | 135.4 |
| d5_flat_notry | 20 | 5 | 5 | 0 | 222 | None | 1 | 14.55 | 0 | 118.1 |

| arm | seeds clearing | seeds clearing level 2 | vs d4_opt: clears (arm / base), seeds up / down, sign p | lost | gained |
|---|---|---|---|---|---|
| d4_opt | 4, 5, 7, 17, 19 | - | - | - | - |
| d5_flat | 8, 9, 10, 13, 17 | - | 5 / 5, 4 / 4, 1.0 | 4, 5, 7, 19 | 8, 9, 10, 13 |
| d5_lib | 5, 17, 19 | - | 3 / 5, 0 / 2, 0.5 | 4, 7 | - |
| d5_both | 5, 8, 9, 10, 13, 17, 19 | - | 7 / 5, 4 / 2, 0.6875 | 4, 7 | 8, 9, 10, 13 |
| d5_flat_notry | 8, 9, 10, 13, 17 | - | 5 / 5, 4 / 4, 1.0 | 4, 5, 7, 19 | 8, 9, 10, 13 |

Re-learning after a restart (actions until the MAP rule set is right on 5 scored steps in a row; censored = the next restart or the end came first; kept / MAP = the rule set that was MAP just before is still a hypothesis / still MAP 10 actions later, restarts where it was not counts-only):

| arm | kind | restarts (per play) | re-learned (median actions) | censored | kept at +10 | MAP at +10 |
|---|---|---|---|---|---|---|
| d4_opt | clear | 5 (0.25) | 7 | 0 | 3/4 | 2/4 |
| d4_opt | reset | 223 (11.15) | 5.0 | 53 | 154/162 | 139/162 |
| d5_flat | clear | 5 (0.25) | 9 | 0 | 5/5 | 4/5 |
| d5_flat | reset | 291 (14.55) | 5.0 | 45 | 208/212 | 194/212 |
| d5_lib | clear | 3 (0.15) | 11 | 0 | 2/3 | 1/3 |
| d5_lib | reset | 210 (10.5) | 5 | 41 | 150/165 | 134/165 |
| d5_both | clear | 7 (0.35) | 9 | 0 | 6/7 | 4/7 |
| d5_both | reset | 281 (14.05) | 5.0 | 45 | 179/195 | 166/195 |
| d5_flat_notry | clear | 5 (0.25) | 9 | 0 | 5/5 | 4/5 |
| d5_flat_notry | reset | 291 (14.55) | 5.0 | 45 | 208/212 | 194/212 |

| arm | library sets (median) | library rules (median) | sets re-seeded per play |
|---|---|---|---|
| d5_lib | 6.0 | 10.5 | 21.0 |
| d5_both | 6.0 | 10.0 | 27.85 |

| arm | try-once presses | per play | would have pressed anyway (G button < G continuing) | comparison interruptions per play |
|---|---|---|---|---|
| d4_opt | 2 | 0.1 | 0 | 2.4 |
| d5_flat | 1 | 0.05 | 1 | 18.75 |
| d5_lib | 2 | 0.1 | 0 | 3.1 |
| d5_both | 1 | 0.05 | 1 | 14.45 |
| d5_flat_notry | 0 | 0.0 | 0 | 18.8 |

First clears per seed (action of level 1, level 2):

- d4_opt: 0: -; 1: -; 2: -; 3: -; 4: [403]; 5: [228]; 6: -; 7: [494]; 8: -; 9: -; 10: -; 11: -; 12: -; 13: -; 14: -; 15: -; 16: -; 17: [203]; 18: -; 19: [55]
- d5_flat: 0: -; 1: -; 2: -; 3: -; 4: -; 5: -; 6: -; 7: -; 8: [60]; 9: [467]; 10: [337]; 11: -; 12: -; 13: [222]; 14: -; 15: -; 16: -; 17: [186]; 18: -; 19: -
- d5_lib: 0: -; 1: -; 2: -; 3: -; 4: -; 5: [404]; 6: -; 7: -; 8: -; 9: -; 10: -; 11: -; 12: -; 13: -; 14: -; 15: -; 16: -; 17: [203]; 18: -; 19: [55]
- d5_both: 0: -; 1: -; 2: -; 3: -; 4: -; 5: [249]; 6: -; 7: -; 8: [60]; 9: [371]; 10: [337]; 11: -; 12: -; 13: [222]; 14: -; 15: -; 16: -; 17: [186]; 18: -; 19: [212]
- d5_flat_notry: 0: -; 1: -; 2: -; 3: -; 4: -; 5: -; 6: -; 7: -; 8: [60]; 9: [467]; 10: [337]; 11: -; 12: -; 13: [222]; 14: -; 15: -; 16: -; 17: [186]; 18: -; 19: -

## Judging

| arm | per-seed guard (canary seeds lost vs d4_opt) | canary clears arm / base (40 pairs), seeds up / down, sign p | clears per game arm / base (wa30, ls20, g50t) | Locksmith level one 20/20 | Locksmith speed: first clear median (mean) arm vs base, seeds slower / faster, sign p |
|---|---|---|---|---|---|
| d5_flat | FAIL (ls20: none; g50t: 4, 5, 7, 19) | 25 / 25, 4 / 4, 1.0 | 0/1, 20/20, 5/5 | PASS (20/20) | 50.0 (57.9) vs 47.0 (52.4), 6 / 2, 0.2891 -- SLOWER |
| d5_lib | FAIL (ls20: none; g50t: 4, 7) | 23 / 25, 0 / 2, 0.5 | 1/1, 20/20, 3/5 | PASS (20/20) | 46.5 (50.2) vs 47.0 (52.4), 2 / 1, 1.0 |
| d5_both | FAIL (ls20: none; g50t: 4, 7) | 27 / 25, 4 / 2, 0.6875 | 0/1, 20/20, 7/5 | PASS (20/20) | 48.0 (54.3) vs 47.0 (52.4), 7 / 5, 0.7744 -- SLOWER |
| d5_flat_notry | FAIL (ls20: none; g50t: 4, 5, 7, 19) | 25 / 25, 4 / 4, 1.0 | 0/1, 20/20, 5/5 | PASS (20/20) | 50.0 (57.9) vs 47.0 (52.4), 6 / 2, 0.2891 -- SLOWER |

Reproduction: d4_opt rerun vs debate four's d4_opt rows: 60 plays identical (clears, actions, presses), 0 differ [].
