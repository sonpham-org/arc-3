Wall map (blocked moves predicted before the outcome; accuracy / blocked recall / false walls)

| game | colour rule (before) | soft map alone | as wired: colour first, soft map fills silence |
|---|---|---|---|
| g50t | 0.769 / 0.288 / 18 | 0.850 / 0.678 / 79 | 0.851 / 0.703 / 88 |
| ls20 | 0.964 / 0.778 / 5 | 0.985 / 0.918 / 8 | 0.987 / 0.931 / 7 |
| wa30 | 0.837 / 0.244 / 17 | 0.821 / 0.397 / 115 | 0.831 / 0.448 / 116 |

Grouping parts into objects (pair recall / precision vs engine sprites; prequential = as the agent sees it)

| game | type-level rule (before) | common fate permanent (prequential) | common fate revocable, as wired (prequential) |
|---|---|---|---|
| g50t | 0.457 / 0.904 | 0.697 / 0.972 | 0.613 / 0.978 |
| ls20 | 0.578 / 1.000 | 0.930 / 1.000 | 0.896 / 1.000 |
| wa30 | 0.051 / 0.115 | 0.506 / 0.359 | 0.385 / 0.352 |

Ghost tape (Ghost Twin, 707 ghost steps in 20 recorded plays; nats per ghost step, lower is better): counts alone 1.004, posterior with the tape rule 0.948; on the 257 steps where the tape had decided: 0.559 -> 0.405.
