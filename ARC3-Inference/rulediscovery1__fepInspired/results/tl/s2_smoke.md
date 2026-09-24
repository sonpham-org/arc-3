# S2: tensor-logic rule learning offline on recorded plays

Same recorded actions for every arm (passive replay through the exact simulator), so nats are comparable.
gain = counts-only nats minus posterior nats on the same steps (what the rules add). map hit = the MAP rule
set's predicted label equals the observed label. Engine labels choose the step subsets only.

## Locksmith (ls20)

| subset | arm | steps | nats/step | counts | gain | map hit |
|---|---|---|---|---|---|---|
| all | templates | 717 | 1.551 | 2.094 | 0.543 | 0.222 |
| all | touch_tl | 717 | 1.54 | 2.094 | 0.554 | 0.13 |
| all | tl_only | 717 | 1.653 | 2.094 | 0.441 | 0.004 |
| first_contact | templates | 16 | 2.835 | 4.392 | 1.558 | 0.0 |
| first_contact | touch_tl | 16 | 2.855 | 4.392 | 1.537 | 0.0 |
| first_contact | tl_only | 16 | 4.592 | 4.392 | -0.2 | 0.0 |
| blocked | templates | 78 | 2.688 | 2.29 | -0.398 | 0.423 |
| blocked | touch_tl | 78 | 2.628 | 2.29 | -0.338 | 0.308 |
| blocked | tl_only | 78 | 3.033 | 2.29 | -0.743 | 0.038 |

touch_tl: learned rule in MAP on 22% of steps; learned rules ever MAP per play 0.5; plays with a learned rule in the final MAP 2/4; learned mover arrows right 16/16 (vs the engine's modal player move); equations active (plays): {'A': 4, 'B': 4, 'H': 4, 'K': 4, 'P': 4, 'G': 1}; learner seconds 17.3

tl_only: learned rule in MAP on 90% of steps; learned rules ever MAP per play 6.25; plays with a learned rule in the final MAP 4/4; learned mover arrows right 16/16 (vs the engine's modal player move); equations active (plays): {'A': 4, 'B': 4, 'H': 4, 'K': 4, 'P': 4, 'G': 1}; learner seconds 18.1

## Ghost Twin (g50t)

| subset | arm | steps | nats/step | counts | gain | map hit |
|---|---|---|---|---|---|---|
| all | templates | 240 | 2.509 | 3.267 | 0.757 | 0.108 |
| all | touch_tl | 240 | 2.532 | 3.267 | 0.735 | 0.079 |
| all | tl_only | 240 | 2.381 | 3.267 | 0.886 | 0.108 |
| first_contact | templates | 10 | 4.081 | 3.773 | -0.308 | 0.0 |
| first_contact | touch_tl | 10 | 3.569 | 3.773 | 0.205 | 0.1 |
| first_contact | tl_only | 10 | 3.47 | 3.773 | 0.303 | 0.0 |
| blocked | templates | 43 | 1.888 | 2.21 | 0.323 | 0.419 |
| blocked | touch_tl | 43 | 2.293 | 2.21 | -0.083 | 0.256 |
| blocked | tl_only | 43 | 2.159 | 2.21 | 0.051 | 0.326 |
| ghost | templates | 58 | 3.542 | 5.121 | 1.579 | 0.034 |
| ghost | touch_tl | 58 | 3.333 | 5.121 | 1.788 | 0.017 |
| ghost | tl_only | 58 | 2.839 | 5.121 | 2.282 | 0.0 |
| push | templates | 10 | 3.709 | 5.486 | 1.776 | 0.0 |
| push | touch_tl | 10 | 3.194 | 5.486 | 2.292 | 0.0 |
| push | tl_only | 10 | 3.704 | 5.486 | 1.781 | 0.0 |
| toggle | templates | 20 | 3.662 | 4.825 | 1.163 | 0.0 |
| toggle | touch_tl | 20 | 2.836 | 4.825 | 1.989 | 0.0 |
| toggle | tl_only | 20 | 2.316 | 4.825 | 2.509 | 0.0 |

touch_tl: learned rule in MAP on 78% of steps; learned rules ever MAP per play 1.33; plays with a learned rule in the final MAP 3/3; learned mover arrows right 10/11 (vs the engine's modal player move); equations active (plays): {'A': 3, 'B': 3, 'H': 3, 'K': 3, 'P': 3, 'G': 1}; learner seconds 2.8

tl_only: learned rule in MAP on 77% of steps; learned rules ever MAP per play 4.33; plays with a learned rule in the final MAP 3/3; learned mover arrows right 10/11 (vs the engine's modal player move); equations active (plays): {'A': 3, 'B': 3, 'H': 3, 'K': 3, 'P': 3, 'G': 1}; learner seconds 2.9

## Warehouse (wa30)

| subset | arm | steps | nats/step | counts | gain | map hit |
|---|---|---|---|---|---|---|
| all | templates | 579 | 3.007 | 3.91 | 0.903 | 0.079 |
| all | touch_tl | 579 | 2.731 | 3.91 | 1.179 | 0.095 |
| all | tl_only | 579 | 3.007 | 3.91 | 0.903 | 0.009 |
| first_contact | templates | 14 | 4.825 | 5.146 | 0.322 | 0.071 |
| first_contact | touch_tl | 14 | 4.27 | 5.146 | 0.876 | 0.071 |
| first_contact | tl_only | 14 | 4.196 | 5.146 | 0.951 | 0.0 |
| blocked | templates | 104 | 3.654 | 4.532 | 0.878 | 0.048 |
| blocked | touch_tl | 104 | 3.354 | 4.532 | 1.177 | 0.048 |
| blocked | tl_only | 104 | 3.856 | 4.532 | 0.676 | 0.0 |
| push | templates | 186 | 2.602 | 3.627 | 1.025 | 0.038 |
| push | touch_tl | 186 | 2.418 | 3.627 | 1.209 | 0.038 |
| push | tl_only | 186 | 2.725 | 3.627 | 0.902 | 0.011 |

touch_tl: learned rule in MAP on 39% of steps; learned rules ever MAP per play 1.33; plays with a learned rule in the final MAP 2/3; learned mover arrows right 4/12 (vs the engine's modal player move); equations active (plays): {'A': 3, 'B': 3, 'H': 3, 'K': 3, 'P': 3}; learner seconds 10.0

tl_only: learned rule in MAP on 87% of steps; learned rules ever MAP per play 6.33; plays with a learned rule in the final MAP 3/3; learned mover arrows right 4/12 (vs the engine's modal player move); equations active (plays): {'A': 3, 'B': 3, 'H': 3, 'K': 3, 'P': 3}; learner seconds 10.2

wall 85 s
