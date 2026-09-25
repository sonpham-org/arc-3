# Context-budget matrix

Ten new full-history FlashNext configurations were run for a maximum 264-minute suite. Each used one RTX PRO 6000, NVFP4 model weights, FP8 E4M3 KV, `.965` GPU allocation, and the same 25 games. Per-game limits follow `2 × floor(32,400 / ceil(110 / lanes))` seconds, matching the earlier competition-sizing convention. [`design.json`](design.json) records the exact contexts, lane counts, and limits.

| Aggregate context | Context/lane | Input ceiling | Lanes | Score at 132 min | Final score | Levels | Wins | Actions | Action-attached tokens |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 476,446 | 43,313 | 34,609 | 11 | 18.9853 | **27.6610** | 79 | 3 | 7,548 | 4,565,676 |
| 720,896 | 102,985 | 94,281 | 7 | 13.7133 | 24.6980 | 72 | 2 | 4,902 | 3,344,092 |
| 720,896 | 144,179 | 135,475 | 5 | 12.6285 | 22.9610 | 71 | 1 | 4,718 | 2,910,041 |
| 476,446 | 68,063 | 59,359 | 7 | 13.4096 | 21.4993 | 72 | 0 | 5,210 | 3,590,275 |
| 720,896 | 180,224 | 171,520 | 4 | 11.5809 | 20.5309 | 66 | 0 | 3,866 | 3,021,734 |
| 476,446 | 95,289 | 86,585 | 5 | 11.8324 | 17.9072 | 63 | 1 | 4,043 | 2,824,868 |
| 720,896 | 240,298 | 231,594 | 3 | 7.2976 | 16.6700 | 57 | 1 | 2,749 | 2,327,024 |
| 476,446 | 158,815 | 150,111 | 3 | 7.8293 | 15.0032 | 57 | 0 | 3,402 | 2,405,935 |
| 476,446 | 119,111 | 110,407 | 4 | 8.5160 | 14.0285 | 57 | 0 | 3,306 | 2,710,154 |
| 476,446 | 21,656 | 12,952 | 22 | 1.9925 | 3.4846 | 26 | 0 | 9,364 | 5,827,461 |

[`final-scores.json`](final-scores.json) preserves full precision and source-summary hashes. The minute-132 rows are exact observer samples without interpolation. Fewer than 25 games had reported by that time in every arm; missing games remain zero in the 25-game denominator.

## Interpretation

The result strongly favors the middle of the tested lane/context range. More context was useful up to a point, but the matrix does not prove that longer context itself reduces model quality: lane count, per-game time, request concurrency, prompt-rebuild work, and generated-token totals all move with the configuration.

The 22-lane row is specifically confounded. Its full-context reserve leaves 12,952 input tokens, versus roughly 31,744 under the earlier 32,768-context baseline policy. It completed 25 games and 9,364 actions without a recorded OOM, HTTP failure, scheduler preemption, or run failure. Its score remained nearly flat while actions continued, which rules out a simple dead run but does not identify the causal mechanism. A corrected 22-lane control needs a proportional output reserve or a larger context.
