# Rule discovery agent vs exact Locksmith simulator (10 seeds, 500 actions, RESET offered)

| arm | levels (total) | game overs | cells visited (mean) | key changes (mean) | steps with matching key (mean) | resets (mean) | movement rule adopted |
|---|---|---|---|---|---|---|---|
| random | 0 | 0 | 24.2 | 0.5 | 1.7 | 102.9 | - |
| agent default | 0 | 3 | 23.3 | 1.2 | 3.4 | 16.3 | 0 |
| agent prior_quarter | 0 | 0 | 26.3 | 1.7 | 3.8 | 19.8 | 0 |
| agent prior_twentieth | 0 | 2 | 25.7 | 1.4 | 9.2 | 17.7 | 4 |
| agent curious | 0 | 2 | 25.8 | 2.3 | 4.7 | 41.8 | 0 |
| agent curious_only | 0 | 2 | 24.8 | 0.3 | 0.5 | 60.6 | 0 |
| agent touch | 10 | 9 | 49.2 | 4.0 | 7.0 | 6.5 | 10 |
| agent touch_fullprior | 10 | 10 | 43.7 | 3.1 | 7.0 | 6.2 | 8 |

wall 151 s
