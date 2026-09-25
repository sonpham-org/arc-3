# Branch-replay results: 695 finished branches, 102 checkpoints, 11 levels
replay fidelity: 667/695 branches reproduced the recorded action prefix exactly; mismatches: [('g50t-L3-i026-high0', None), ('g50t-L3-i026-medium0', None), ('lf52-L2-i130-high0', None), ('lf52-L2-i130-xhigh0', None), ('lf52-L2-i130-high1', None), ('lf52-L2-i130-low0', None), ('lf52-L2-i130-medium0', None), ('wa30-L2-i032-xhigh0', None)]
token calibration from 99 xhigh control branches: 0.332 completion tokens per generated char (applied to the recording's remaining reasoning+content+code chars to estimate its remaining tokens)

## All checkpoints

| effort | n | solved | action ratio (med) | token ratio (med) | turn ratio (med) | tokens/branch (mean) | RHAE level (mean, unsolved=0) | RHAE original |
|---|---|---|---|---|---|---|---|---|
| xhigh | 99 | 69/99 (70%) | 1.0 | 1.08 | 0.93 | 59229.99 | 0.98 | 1.28 |
| high | 193 | 124/193 (64%) | 1.0 | 1.0 | 1.0 | 57699.41 | 0.97 | 1.28 |
| medium | 183 | 126/183 (69%) | 0.97 | 0.99 | 0.93 | 52228.99 | 1.06 | 1.31 |
| low | 192 | 112/192 (58%) | 1.02 | 0.99 | 1.0 | 54165.44 | 0.84 | 1.28 |

ratios are branch / original for the remainder of the level, solved branches only; <1 = the branch was more efficient than the recording.

## Checkpoints in the early (first third of the level's turns)

| effort | n | solved | action ratio (med) | token ratio (med) | turn ratio (med) | tokens/branch (mean) | RHAE level (mean, unsolved=0) | RHAE original |
|---|---|---|---|---|---|---|---|---|
| xhigh | 67 | 48/67 (72%) | 1.0 | 1.09 | 0.91 | 71070.88 | 0.95 | 1.24 |
| high | 132 | 85/132 (64%) | 1.0 | 0.96 | 0.91 | 67315.31 | 0.92 | 1.22 |
| medium | 128 | 86/128 (67%) | 0.97 | 1.0 | 0.94 | 63553.21 | 0.99 | 1.25 |
| low | 130 | 73/130 (56%) | 1.1 | 1.13 | 1.06 | 66867.42 | 0.77 | 1.24 |

ratios are branch / original for the remainder of the level, solved branches only; <1 = the branch was more efficient than the recording.

## Checkpoints in the middle third

| effort | n | solved | action ratio (med) | token ratio (med) | turn ratio (med) | tokens/branch (mean) | RHAE level (mean, unsolved=0) | RHAE original |
|---|---|---|---|---|---|---|---|---|
| xhigh | 30 | 19/30 (63%) | 0.98 | 0.96 | 0.94 | 36483.57 | 0.97 | 1.33 |
| high | 57 | 35/57 (61%) | 1.0 | 1.02 | 1.0 | 39293.58 | 1.01 | 1.35 |
| medium | 51 | 36/51 (71%) | 0.96 | 0.96 | 0.9 | 27704.53 | 1.19 | 1.43 |
| low | 57 | 35/57 (61%) | 1.0 | 0.89 | 1.0 | 29764.46 | 0.93 | 1.36 |

ratios are branch / original for the remainder of the level, solved branches only; <1 = the branch was more efficient than the recording.

## Checkpoints in the last third

| effort | n | solved | action ratio (med) | token ratio (med) | turn ratio (med) | tokens/branch (mean) | RHAE level (mean, unsolved=0) | RHAE original |
|---|---|---|---|---|---|---|---|---|
| xhigh | 2 | 2/2 (100%) | 1.05 | 1.46 | 1.5 | 3756.5 | 1.91 | 1.94 |
| high | 4 | 4/4 (100%) | 1.02 | 1.15 | 1.25 | 2658.0 | 1.92 | 1.94 |
| medium | 4 | 4/4 (100%) | 1.0 | 1.22 | 1.42 | 2540.75 | 1.96 | 1.94 |
| low | 5 | 4/5 (80%) | 1.0 | 1.05 | 1.17 | 2085.4 | 1.56 | 1.64 |

ratios are branch / original for the remainder of the level, solved branches only; <1 = the branch was more efficient than the recording.

## Per level (solve rate by effort; median action ratio in parentheses)

| game | level | turns | orig actions | human | xhigh | high | medium | low |
|---|---|---|---|---|---|---|---|---|
| bp35 | 1 | 16 | 41 | 21 | 10/10 (0.96) | 16/20 (0.83) | 20/20 (0.88) | 14/20 (1.05) |
| g50t | 1 | 18 | 37 | 78 | 6/11 (1.21) | 14/22 (1.42) | 11/22 (1.13) | 10/22 (1.42) |
| g50t | 2 | 10 | 31 | 175 | 6/6 (1.0) | 11/12 (1.0) | 12/12 (1.0) | 12/12 (1.0) |
| g50t | 3 | 40 | 195 | 179 | 7/10 (1.28) | 9/17 (1.04) | 11/17 (1.05) | 12/18 (1.09) |
| lf52 | 1 | 11 | 13 | 32 | 5/7 (1.0) | 11/12 (0.92) | 11/12 (0.92) | 8/12 (1.05) |
| lf52 | 2 | 151 | 707 | 81 | 7/7 (0.59) | 7/14 (0.37) | 8/13 (0.19) | 9/14 (0.37) |
| ls20 | 1 | 10 | 31 | 22 | 4/6 (0.79) | 9/12 (1.06) | 8/12 (0.83) | 8/12 (0.81) |
| ls20 | 2 | 26 | 231 | 123 | 6/13 (0.98) | 16/26 (0.98) | 16/26 (0.95) | 14/26 (1.01) |
| sk48 | 1 | 35 | 133 | 61 | 0/8 (None) | 2/16 (0.63) | 1/12 (0.65) | 2/15 (0.99) |
| wa30 | 1 | 23 | 50 | 71 | 14/14 (1.13) | 25/28 (1.02) | 22/26 (0.98) | 19/28 (1.16) |
| wa30 | 2 | 35 | 281 | 119 | 4/7 (0.46) | 4/14 (0.51) | 6/11 (0.99) | 4/13 (0.94) |

## Oracle switch value

checkpoints: 98; a cheaper effort solved the level with no more actions than the recording at 68 of them (picked: {'low': 17, 'high': 26, 'medium': 25}); if a router made exactly those switches the remaining-level tokens would drop by 34% (1,974,735 of 5,819,648 reference tokens, reference = xhigh control where available).
