# S2: tensor-logic rule learning offline on recorded plays

Same recorded actions for every arm (passive replay through the exact simulator), so nats are comparable.
gain = counts-only nats minus posterior nats on the same steps (what the rules add). map hit = the MAP rule
set's predicted label equals the observed label. Engine labels choose the step subsets only.

## Locksmith (ls20)

| subset | arm | steps | nats/step | counts | gain | map hit |
|---|---|---|---|---|---|---|
| all | templates | 3520 | 1.595 | 2.076 | 0.482 | 0.174 |
| all | touch_tl | 3520 | 1.538 | 2.076 | 0.538 | 0.133 |
| all | tl_only | 3520 | 1.686 | 2.076 | 0.39 | 0.015 |
| first_contact | templates | 78 | 2.81 | 4.216 | 1.406 | 0.038 |
| first_contact | touch_tl | 78 | 2.787 | 4.216 | 1.429 | 0.026 |
| first_contact | tl_only | 78 | 4.001 | 4.216 | 0.215 | 0.013 |
| blocked | templates | 532 | 2.546 | 2.02 | -0.526 | 0.378 |
| blocked | touch_tl | 532 | 2.316 | 2.02 | -0.295 | 0.286 |
| blocked | tl_only | 532 | 2.498 | 2.02 | -0.478 | 0.102 |

touch_tl: learned rule in MAP on 30% of steps; learned rules ever MAP per play 0.95; plays with a learned rule in the final MAP 7/19; learned mover arrows right 75/76 (vs the engine's modal player move); equations active (plays): {'A': 19, 'B': 19, 'H': 19, 'K': 19, 'P': 19, 'G': 4}; learner seconds 107.2

tl_only: learned rule in MAP on 89% of steps; learned rules ever MAP per play 5.84; plays with a learned rule in the final MAP 19/19; learned mover arrows right 75/76 (vs the engine's modal player move); equations active (plays): {'A': 19, 'B': 19, 'H': 19, 'K': 19, 'P': 19, 'G': 5}; learner seconds 109.2

## Ghost Twin (g50t)

| subset | arm | steps | nats/step | counts | gain | map hit |
|---|---|---|---|---|---|---|
| all | templates | 1756 | 1.913 | 2.381 | 0.468 | 0.237 |
| all | touch_tl | 1756 | 1.807 | 2.381 | 0.574 | 0.228 |
| all | tl_only | 1756 | 1.883 | 2.381 | 0.498 | 0.157 |
| first_contact | templates | 67 | 3.334 | 3.516 | 0.182 | 0.03 |
| first_contact | touch_tl | 67 | 3.158 | 3.516 | 0.358 | 0.015 |
| first_contact | tl_only | 67 | 3.221 | 3.516 | 0.295 | 0.03 |
| blocked | templates | 508 | 1.536 | 1.665 | 0.129 | 0.402 |
| blocked | touch_tl | 508 | 1.542 | 1.665 | 0.123 | 0.382 |
| blocked | tl_only | 508 | 1.733 | 1.665 | -0.068 | 0.24 |
| ghost | templates | 241 | 2.92 | 4.162 | 1.242 | 0.145 |
| ghost | touch_tl | 241 | 2.505 | 4.162 | 1.657 | 0.104 |
| ghost | tl_only | 241 | 2.381 | 4.162 | 1.781 | 0.05 |
| push | templates | 86 | 3.109 | 4.253 | 1.144 | 0.0 |
| push | touch_tl | 86 | 2.589 | 4.253 | 1.664 | 0.0 |
| push | tl_only | 86 | 2.933 | 4.253 | 1.32 | 0.0 |
| toggle | templates | 88 | 3.414 | 4.499 | 1.085 | 0.0 |
| toggle | touch_tl | 88 | 2.986 | 4.499 | 1.513 | 0.0 |
| toggle | tl_only | 88 | 2.67 | 4.499 | 1.829 | 0.0 |

touch_tl: learned rule in MAP on 52% of steps; learned rules ever MAP per play 0.74; plays with a learned rule in the final MAP 12/19; learned mover arrows right 60/72 (vs the engine's modal player move); equations active (plays): {'A': 19, 'B': 19, 'H': 19, 'K': 19, 'P': 18, 'G': 5}; learner seconds 24.8

tl_only: learned rule in MAP on 76% of steps; learned rules ever MAP per play 4.11; plays with a learned rule in the final MAP 18/19; learned mover arrows right 60/72 (vs the engine's modal player move); equations active (plays): {'A': 19, 'B': 19, 'H': 19, 'K': 19, 'P': 18, 'G': 5}; learner seconds 24.2

## Warehouse (wa30)

| subset | arm | steps | nats/step | counts | gain | map hit |
|---|---|---|---|---|---|---|
| all | templates | 3493 | 2.967 | 3.913 | 0.946 | 0.091 |
| all | touch_tl | 3493 | 2.929 | 3.913 | 0.984 | 0.086 |
| all | tl_only | 3493 | 3.017 | 3.913 | 0.896 | 0.102 |
| first_contact | templates | 90 | 4.152 | 4.809 | 0.656 | 0.044 |
| first_contact | touch_tl | 90 | 4.091 | 4.809 | 0.717 | 0.044 |
| first_contact | tl_only | 90 | 4.419 | 4.809 | 0.39 | 0.033 |
| blocked | templates | 562 | 3.343 | 3.776 | 0.433 | 0.181 |
| blocked | touch_tl | 562 | 3.251 | 3.776 | 0.525 | 0.18 |
| blocked | tl_only | 562 | 3.295 | 3.776 | 0.481 | 0.162 |
| push | templates | 915 | 2.659 | 3.755 | 1.095 | 0.032 |
| push | touch_tl | 915 | 2.654 | 3.755 | 1.101 | 0.016 |
| push | tl_only | 915 | 2.688 | 3.755 | 1.066 | 0.126 |

touch_tl: learned rule in MAP on 16% of steps; learned rules ever MAP per play 0.47; plays with a learned rule in the final MAP 3/19; learned mover arrows right 35/76 (vs the engine's modal player move); equations active (plays): {'A': 19, 'B': 19, 'H': 19, 'K': 19, 'P': 19}; learner seconds 79.4

tl_only: learned rule in MAP on 81% of steps; learned rules ever MAP per play 6.84; plays with a learned rule in the final MAP 18/19; learned mover arrows right 34/76 (vs the engine's modal player move); equations active (plays): {'A': 19, 'B': 19, 'H': 19, 'K': 19, 'P': 19}; learner seconds 80.6

wall 469 s
