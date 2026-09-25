# Branch-replay results: 1173 finished branches, 167 checkpoints, 11 levels
replay fidelity: 1135/1173 branches reproduced the recorded action prefix exactly; mismatches: [('g50t-L3-i026-high0', None), ('g50t-L3-i026-medium0', None), ('lf52-L2-i130-high0', None), ('lf52-L2-i130-xhigh0', None), ('lf52-L2-i130-high1', None), ('lf52-L2-i130-low0', None), ('lf52-L2-i130-medium0', None), ('wa30-L2-i032-xhigh0', None)]
token calibration from 162 xhigh control branches: 0.334 completion tokens per generated char (applied to the recording's remaining reasoning+content+code chars to estimate its remaining tokens)

## All checkpoints

| effort | n | solved | action ratio (med) | token ratio (med) | turn ratio (med) | tokens/branch (mean) | RHAE level (mean, unsolved=0) | RHAE original |
|---|---|---|---|---|---|---|---|---|
| xhigh | 162 | 116/162 (72%) | 1.0 | 1.0 | 1.0 | 45244.35 | 1.02 | 1.29 |
| high | 323 | 220/323 (68%) | 1.0 | 1.01 | 1.0 | 42631.27 | 1.01 | 1.28 |
| medium | 323 | 229/323 (71%) | 1.0 | 1.0 | 1.0 | 39867.11 | 1.05 | 1.28 |
| low | 327 | 219/327 (67%) | 1.0 | 0.91 | 1.0 | 39654.67 | 0.93 | 1.27 |

ratios are branch / original for the remainder of the level, solved branches only; <1 = the branch was more efficient than the recording.

## Checkpoints in the early (first third of the level's turns)

| effort | n | solved | action ratio (med) | token ratio (med) | turn ratio (med) | tokens/branch (mean) | RHAE level (mean, unsolved=0) | RHAE original |
|---|---|---|---|---|---|---|---|---|
| xhigh | 68 | 48/68 (71%) | 1.0 | 1.08 | 0.91 | 71394.5 | 0.94 | 1.23 |
| high | 134 | 87/134 (65%) | 1.0 | 0.96 | 0.91 | 67081.31 | 0.91 | 1.21 |
| medium | 134 | 88/134 (66%) | 0.98 | 1.0 | 0.94 | 65464.55 | 0.95 | 1.21 |
| low | 135 | 76/135 (56%) | 1.1 | 1.04 | 1.05 | 66475.24 | 0.76 | 1.21 |

ratios are branch / original for the remainder of the level, solved branches only; <1 = the branch was more efficient than the recording.

## Checkpoints in the middle third

| effort | n | solved | action ratio (med) | token ratio (med) | turn ratio (med) | tokens/branch (mean) | RHAE level (mean, unsolved=0) | RHAE original |
|---|---|---|---|---|---|---|---|---|
| xhigh | 53 | 35/53 (66%) | 1.0 | 0.96 | 0.94 | 38602.45 | 0.95 | 1.3 |
| high | 107 | 66/107 (62%) | 1.0 | 1.02 | 1.0 | 37004.21 | 0.93 | 1.29 |
| medium | 104 | 77/104 (74%) | 1.0 | 0.97 | 1.0 | 32111.3 | 1.08 | 1.31 |
| low | 108 | 71/108 (66%) | 1.0 | 0.85 | 1.0 | 30784.56 | 0.91 | 1.28 |

ratios are branch / original for the remainder of the level, solved branches only; <1 = the branch was more efficient than the recording.

## Checkpoints in the last third

| effort | n | solved | action ratio (med) | token ratio (med) | turn ratio (med) | tokens/branch (mean) | RHAE level (mean, unsolved=0) | RHAE original |
|---|---|---|---|---|---|---|---|---|
| xhigh | 41 | 33/41 (80%) | 1.0 | 0.92 | 1.0 | 10459.24 | 1.24 | 1.39 |
| high | 82 | 67/82 (82%) | 1.0 | 1.01 | 1.0 | 10018.96 | 1.26 | 1.39 |
| medium | 85 | 64/85 (75%) | 1.0 | 1.0 | 1.0 | 9002.98 | 1.18 | 1.35 |
| low | 84 | 72/84 (86%) | 1.0 | 0.93 | 1.0 | 7954.63 | 1.24 | 1.36 |

ratios are branch / original for the remainder of the level, solved branches only; <1 = the branch was more efficient than the recording.

## Per level (solve rate by effort; median action ratio in parentheses)

| game | level | turns | orig actions | human | xhigh | high | medium | low |
|---|---|---|---|---|---|---|---|---|
| bp35 | 1 | 16 | 41 | 21 | 17/17 (0.92) | 27/34 (0.94) | 33/34 (0.87) | 27/34 (1.0) |
| g50t | 1 | 18 | 37 | 78 | 11/18 (1.0) | 25/36 (1.24) | 23/36 (1.0) | 23/36 (1.05) |
| g50t | 2 | 10 | 31 | 175 | 10/10 (1.0) | 19/20 (1.0) | 20/20 (1.0) | 20/20 (1.0) |
| g50t | 3 | 40 | 195 | 179 | 8/11 (1.25) | 11/21 (1.05) | 14/21 (1.05) | 15/22 (1.08) |
| lf52 | 1 | 11 | 13 | 32 | 9/12 (1.14) | 18/22 (1.0) | 19/22 (1.0) | 14/22 (1.0) |
| lf52 | 2 | 151 | 707 | 81 | 7/7 (0.59) | 7/14 (0.37) | 8/13 (0.19) | 9/14 (0.37) |
| ls20 | 1 | 10 | 31 | 22 | 6/10 (0.81) | 14/20 (1.0) | 14/20 (0.9) | 15/20 (1.0) |
| ls20 | 2 | 26 | 231 | 123 | 14/25 (0.99) | 34/52 (1.0) | 33/52 (1.0) | 32/51 (1.0) |
| sk48 | 1 | 35 | 133 | 61 | 5/16 (1.05) | 11/32 (0.88) | 13/32 (0.88) | 13/33 (0.98) |
| wa30 | 1 | 23 | 50 | 71 | 23/23 (1.03) | 43/46 (1.0) | 40/45 (1.0) | 37/46 (1.0) |
| wa30 | 2 | 35 | 281 | 119 | 6/13 (0.47) | 11/26 (0.69) | 12/28 (0.98) | 14/29 (0.9) |

## Oracle switch value

checkpoints: 164; a cheaper effort solved the level with no more actions than the recording at 127 of them (picked: {'low': 39, 'high': 44, 'medium': 44}); if a router made exactly those switches the remaining-level tokens would drop by 39% (2,846,539 of 7,335,785 reference tokens, reference = xhigh control where available).
