# Tensor-logic overhaul: report (24-Sep-2026)

Agent: OpenMind's rule-discovery agent with relational perception and tensor-logic rule learning (rulediscovery1__fepInspired/tl/). No language model anywhere at run time. Arms: touch = the current agent (templates, explorer, curiosity); touch_tl = the same plus learned rules; tl_only = templates OFF, learned rules only (the explorer's mover also comes from the learned program). Exact local simulators, 500 actions, RESET offered, same seeds per arm. Per game, never aggregated.

Rules' gain = counts-only nats minus posterior nats per scored step, on the agent's own steps (arms walk different paths, so compare gains, not raw nats).

## Findings

- Levels: essentially unchanged; every gain or loss below is ONE seed of ten. Locksmith level one in every seed in all three arms (median first clear 48 / 49 / 48). Ghost Twin: templates-off cleared level one in seed 8 at action 183 (first Ghost Twin clear of this agent in any sweep; touch and touch_tl did not clear seed 8). Deck Control: touch and touch_tl clear seed 1 (actions 108 / 107), templates-off does not. Sigil Caster: one clear per arm, on different seeds (0 / 1 / 7) and later with learned rules (158 -> 308 / 378). Nothing else cleared.
- One lever behind both the Ghost Twin clear and the worst regression: the learned program gives the explorer a mover where the templates had none or a different one, which changes where the agent walks. On Toggle Runes the templates never found a mover (0 trips per play); the learned one produces ~110-120 trips per play and game overs go 3 -> 10 in both learned arms. Toggle Navigator templates-off 4 -> 8 game overs. The same lever cuts Skewer Kebabs game overs 9 -> 2 (templates-off) and plausibly bought the Ghost Twin clear (different mover and forward-chaining search); not separated from the rules' predictions yet -- that is the next experiment.
- Prediction (rules' gain over counts per step): learned rules ADDED to the templates raise it on 8 of 9 games (Locksmith 0.409 -> 0.559, Ghost Twin 0.313 -> 0.422, Warehouse Associates 0.234 -> 0.292, Mirror Rendezvous 0.165 -> 0.246, Sigil Caster 0.084 -> 0.208, Skewer Kebabs 0.032 -> 0.084, Deck Control 0.182 -> 0.203, Toggle Runes -0.02 -> 0.008; Toggle Navigator flat 0.02). Learned rules ALONE beat the templates on Locksmith (0.538), Ghost Twin (0.423), Mirror Rendezvous (0.202), Skewer Kebabs (0.088); worse on Deck Control (0.076), Warehouse Associates (0.058), Sigil Caster (0.070), Toggle Navigator (0.0).
- Offline on the recorded plays (same steps for every arm): added learned rules beat the templates on all three evaluation games; alone they win on Ghost Twin (best on ghost steps 1.24 -> 1.78 nats gained, door / toggle steps 1.09 -> 1.83) and lose on Locksmith (0.48 -> 0.39) and slightly on Warehouse Associates (0.95 -> 0.90). First-contact steps: added rules slightly better on all three; alone worse on Locksmith and Warehouse Associates.
- Rediscovered without templates (offline): Locksmith arrows right in 75 of 76 cases and both template wall colours found as walls in every play (as 'only floor colour 3 lets a move through'); step bars as 'a piece that shrank last step shrinks again'. Ghost Twin: the ghost equation switched on by itself in 5 of 19 plays; in 2 it chose the true lag (copies the previous run per player move, no shift) with the ghost found as the piece sharing the player's shape; the timer as 'shrinks every second step'. Warehouse Associates: pushing / carrying as 'a piece next to (or moved along with) the controlled piece moves with it' -- but the learned mover is right on only about half the arrows there.
- Cost: learned rules make plays 1.5-3.5x slower (Skewer Kebabs 47 -> 170 s per play, added-rules arm).
- Posterior adoption: learned rules reach the MAP rule set in most plays of most games (templates-off: 6-10 of 10 except Toggle Navigator / Toggle Runes); next to the templates, the MAP is often a mix (template d-pad + learned 'bar grows' modifier). Not built: invented predicates as a separate hidden layer (the thresholded Ahead weight is the only invented 'wall' predicate). Surprise-driven structure is in: 10 of ~150 equation switch-ons were triggered by a surprise spike.

## Live (S3)

### Deck Control (dc22)

| arm | levels | seeds clearing | first clear (median action) | game overs | rules' gain / step | learned rules ever MAP / play | plays with learned rule in final MAP | trips / play | s / play |
|---|---|---|---|---|---|---|---|---|---|
| touch | 1 | 1/10 | 108 | 9 | 0.182 | - | - | 37.3 | 22.9 |
| touch_tl | 1 | 1/10 | 107 | 10 | 0.203 | 0.8 | 0 | 35.9 | 53.0 |
| tl_only | 0 | 0/10 | - | 10 | 0.076 | 6.0 | 7 | 35.1 | 38.8 |

Morning reference (touch, earlier sweep): levels 1, seeds clearing 1/10, first clear 108, game overs 9.

Example learned rules (tl_only):
- when a colour-9 piece is clicked -> colour-9 pieces moves (-13,+9) [+5.0]
- when a colour-9 piece is clicked -> colour-9 pieces moves (-15,+11) [+5.0]
- colour 2 ahead of the controlled piece -> the move is favoured [+4.0]
- when a colour-9 piece is clicked -> colour-9 pieces moves (-14,+10) [+4.0]
- ACTION6: piece type 9/dcc4 -> moves (-14,+10) [+3.0]
- colour 4 ahead of a piece -> the move is favoured [+2.5]

### Ghost Twin (g50t)

| arm | levels | seeds clearing | first clear (median action) | game overs | rules' gain / step | learned rules ever MAP / play | plays with learned rule in final MAP | trips / play | s / play |
|---|---|---|---|---|---|---|---|---|---|
| touch | 0 | 0/10 | - | 7 | 0.313 | - | - | 112.8 | 65.8 |
| touch_tl | 0 | 0/10 | - | 6 | 0.422 | 2.2 | 7 | 106.4 | 122.3 |
| tl_only | 1 | 1/10 | 183 | 9 | 0.423 | 8.5 | 10 | 81.9 | 40.2 |

Morning reference (touch, earlier sweep): levels 0, seeds clearing 0/20, first clear -, game overs 14.

Example learned rules (touch_tl):
- ACTION3: the controlled piece -> moves (+0,-6) [+4.0]
- ACTION5: the controlled piece -> moves (+0,-24) [+4.0]
- ACTION5: piece type 9/1f51 -> moves (+0,+4) [+3.5]
- ACTION2: piece type 9/d63f -> moves (+6,+0) [+3.5]
- colour 5 ahead of the controlled piece -> the move is favoured [+3.5]
- ACTION5: piece type 9/06be -> moves (+0,+4) [+3.0]

Example learned rules (tl_only):
- colour 5 ahead of the controlled piece -> the move is favoured [+4.5]
- colour 5 ahead of a piece -> the move is favoured [+4.0]
- ACTION4: the controlled piece -> moves (+0,+6) [+3.5]
- ACTION5: a colour-9 piece -> moves (+0,+4) [+2.5]
- ACTION5: piece type 9/1f51 -> moves (+0,+4) [+2.5]
- ACTION5: piece type 9/06be -> moves (+0,+4) [+2.0]

### Mirror Rendezvous (m0r0)

| arm | levels | seeds clearing | first clear (median action) | game overs | rules' gain / step | learned rules ever MAP / play | plays with learned rule in final MAP | trips / play | s / play |
|---|---|---|---|---|---|---|---|---|---|
| touch | 0 | 0/10 | - | 0 | 0.165 | - | - | 0.0 | 19.8 |
| touch_tl | 0 | 0/10 | - | 1 | 0.246 | 2.5 | 9 | 0.0 | 62.1 |
| tl_only | 0 | 0/10 | - | 0 | 0.202 | 5.7 | 10 | 0.0 | 41.9 |

Morning reference (touch, earlier sweep): levels 0, seeds clearing 0/10, first clear -, game overs 0.

Example learned rules (touch_tl):
- colour 11 ahead of a piece -> the move is blocked [-7.0]
- colour 12 ahead of a piece -> the move is blocked [-7.0]
- ACTION1: a colour-10 piece -> moves (-5,+0) [+4.5]
- ACTION1: piece type 10/0fba -> moves (-5,+0) [+4.5]
- ACTION2: a colour-10 piece -> moves (+5,+0) [+4.0]
- ACTION2: piece type 10/0fba -> moves (+5,+0) [+4.0]

Example learned rules (tl_only):
- colour 11 ahead of a piece -> the move is blocked [-4.5]
- colour 12 ahead of a piece -> the move is blocked [-4.5]
- ACTION1: a colour-10 piece -> moves (-5,+0) [+3.0]
- ACTION1: piece type 10/0fba -> moves (-5,+0) [+3.0]
- colour 5 ahead of a piece -> the move is favoured [+1.0]
- colour 12 ahead of a piece -> the move is blocked [-7.0]

### Sigil Caster (sc25)

| arm | levels | seeds clearing | first clear (median action) | game overs | rules' gain / step | learned rules ever MAP / play | plays with learned rule in final MAP | trips / play | s / play |
|---|---|---|---|---|---|---|---|---|---|
| touch | 1 | 1/10 | 158 | 9 | 0.084 | - | - | 0.2 | 8.7 |
| touch_tl | 1 | 1/10 | 308 | 10 | 0.208 | 1.9 | 9 | 5.1 | 29.4 |
| tl_only | 1 | 1/10 | 378 | 9 | 0.07 | 4.8 | 6 | 0.0 | 31.3 |

Morning reference (touch, earlier sweep): levels 1, seeds clearing 1/10, first clear 158, game overs 9.

Example learned rules (touch_tl):
- when a colour-3 piece is clicked -> colour-14 pieces turns colour 2 [+4.0]
- ACTION6: piece type 14/2f0e -> turns colour 2 [+2.5]
- ACTION6: a colour-14 piece -> turns colour 2 [+0.5]
- colour 2 ahead of a piece -> the move is favoured [+8.0]

Example learned rules (tl_only):
- ACTION3: piece type 9/6a39 -> moves (+0,-2) [+4.0]
- ACTION3: piece type 10/6a39 -> moves (+0,-2) [+4.0]
- ACTION3: piece type 9/64f7 -> moves (+0,-4) [+3.5]
- ACTION3: piece type 10/64f7 -> moves (+0,-4) [+3.5]
- ACTION3: the controlled piece -> moves (+0,-4) [+3.5]
- colour 2 ahead of a piece -> the move is favoured [+3.5]

### Skewer Kebabs (sk48)

| arm | levels | seeds clearing | first clear (median action) | game overs | rules' gain / step | learned rules ever MAP / play | plays with learned rule in final MAP | trips / play | s / play |
|---|---|---|---|---|---|---|---|---|---|
| touch | 0 | 0/10 | - | 9 | 0.032 | - | - | 160.2 | 47.0 |
| touch_tl | 0 | 0/10 | - | 8 | 0.084 | 1.4 | 9 | 147.0 | 170.3 |
| tl_only | 0 | 0/10 | - | 2 | 0.088 | 1.0 | 10 | 154.9 | 227.1 |

Morning reference (touch, earlier sweep): levels 0, seeds clearing 0/10, first clear -, game overs 9.

Example learned rules (touch_tl):
- colour 4 ahead of a piece -> the move is favoured [+1.5]
- ACTION2: piece type 4/8840 -> vanishes [+8.0]
- ACTION2: a colour-4 piece -> vanishes [+2.5]
- when a colour-0 piece is run into -> colour-4 pieces vanishes [+2.0]
- when a colour-6 piece is run into -> colour-4 pieces vanishes [+2.0]
- a piece that moves (-6,+0) 2 step(s) ago -> moves (+6,+0) [+5.5]

Example learned rules (tl_only):
- a piece that moves (-6,+0) 2 step(s) ago -> moves (+6,+0) [+5.5]
- ACTION6: any piece -> moves (+6,+0) [-4.5]
- colour 3 ahead of a piece -> the move is favoured [+2.5]
- colour 4 ahead of a piece -> the move is favoured [+1.5]
- colour 3 ahead of a piece -> the move is favoured [+2.0]

### Toggle Navigator (tn36)

| arm | levels | seeds clearing | first clear (median action) | game overs | rules' gain / step | learned rules ever MAP / play | plays with learned rule in final MAP | trips / play | s / play |
|---|---|---|---|---|---|---|---|---|---|
| touch | 0 | 0/10 | - | 4 | 0.02 | - | - | 0.0 | 22.1 |
| touch_tl | 0 | 0/10 | - | 4 | 0.02 | 0.0 | 0 | 0.0 | 82.9 |
| tl_only | 0 | 0/10 | - | 8 | -0.0 | 0.1 | 0 | 0.0 | 39.0 |

Morning reference (touch, earlier sweep): levels 0, seeds clearing 0/10, first clear -, game overs 4.

### Toggle Runes (tr87)

| arm | levels | seeds clearing | first clear (median action) | game overs | rules' gain / step | learned rules ever MAP / play | plays with learned rule in final MAP | trips / play | s / play |
|---|---|---|---|---|---|---|---|---|---|
| touch | 0 | 0/10 | - | 3 | -0.02 | - | - | 0.0 | 40.3 |
| touch_tl | 0 | 0/10 | - | 10 | 0.008 | 0.2 | 1 | 109.5 | 23.7 |
| tl_only | 0 | 0/10 | - | 10 | 0.009 | 0.6 | 2 | 122.3 | 35.2 |

Morning reference (touch, earlier sweep): levels 0, seeds clearing 0/10, first clear -, game overs 3.

Example learned rules (touch_tl):
- ACTION4: a colour-0 piece -> moves (+0,+7) [+7.0]
- colour 3 ahead of a piece -> the move is favoured [+2.0]
- colour 3 ahead of the controlled piece -> the move is favoured [+2.0]
- ACTION3: a colour-0 piece -> moves (+0,-7) [+7.5]

Example learned rules (tl_only):
- colour 3 ahead of a piece -> the move is favoured [+3.0]
- colour 3 ahead of the controlled piece -> the move is favoured [+3.0]
- ACTION2: the board -> something appears [+8.0]
- colour 3 ahead of a piece -> the move is favoured [+1.5]
- when a colour-7 piece is stood on -> colour-0 pieces moves (+0,-7) [+1.0]

### Locksmith (ls20)

| arm | levels | seeds clearing | first clear (median action) | game overs | rules' gain / step | learned rules ever MAP / play | plays with learned rule in final MAP | trips / play | s / play |
|---|---|---|---|---|---|---|---|---|---|
| touch | 10 | 10/10 | 48 | 9 | 0.409 | - | - | 23.6 | 22.4 |
| touch_tl | 10 | 10/10 | 49 | 10 | 0.559 | 2.8 | 4 | 20.6 | 27.4 |
| tl_only | 10 | 10/10 | 48 | 10 | 0.538 | 6.7 | 10 | 21.7 | 19.9 |

Morning reference (touch, earlier sweep): levels 10, seeds clearing 10/10, first clear 48, game overs 9.

Example learned rules (touch_tl):
- a piece that grows 1 step(s) ago -> grows [+6.0]
- when a colour-9 piece is run into -> colour-3 pieces grows [-6.0]
- when a colour-11 piece changed on the last step -> colour-3 pieces grows [+6.0]
- when a colour-5 piece is next to the controlled piece -> colour-3 pieces grows [+5.5]
- when a colour-11 piece is run into -> colour-11 pieces grows [+4.5]
- when a colour-11 piece is run into -> colour-3 pieces grows [-3.5]

Example learned rules (tl_only):
- ACTION1: the controlled piece -> moves (-5,+0) [+4.0]
- colour 3 ahead of a piece -> the move is favoured [+4.0]
- colour 3 ahead of the controlled piece -> the move is favoured [+4.0]
- colour 3 ahead of a piece -> the move is favoured [+6.5]
- colour 3 ahead of the controlled piece -> the move is favoured [+4.5]
- ACTION4: the controlled piece -> moves (+0,+5) [+3.5]

### Warehouse Associates (wa30)

| arm | levels | seeds clearing | first clear (median action) | game overs | rules' gain / step | learned rules ever MAP / play | plays with learned rule in final MAP | trips / play | s / play |
|---|---|---|---|---|---|---|---|---|---|
| touch | 0 | 0/10 | - | 3 | 0.234 | - | - | 53.0 | 72.0 |
| touch_tl | 0 | 0/10 | - | 1 | 0.292 | 1.1 | 3 | 71.8 | 154.7 |
| tl_only | 0 | 0/10 | - | 5 | 0.058 | 5.2 | 9 | 54.6 | 55.1 |

Morning reference (touch, earlier sweep): levels 0, seeds clearing 0/10, first clear -, game overs 3.

Example learned rules (touch_tl):
- ACTION2: piece type 0/887f -> moves (+7,+0) [+5.5]
- ACTION2: piece type 14/8ba8 -> moves (+3,+0) [+5.5]
- colour 0 ahead of a piece -> the move is blocked [-5.5]
- colour 1 ahead of a piece -> the move is favoured [+5.0]
- colour edge ahead of a piece -> the move is blocked [-5.0]
- ACTION2: piece type 14/8ba8 -> moves (+4,+0) [+4.5]

Example learned rules (tl_only):
- ACTION3: a colour-14 piece -> moves (+0,-3) [+5.5]
- ACTION4: a colour-14 piece -> moves (+0,+3) [+5.5]
- ACTION2: piece type 14/8ba8 -> moves (+3,+0) [+5.0]
- ACTION4: a colour-0 piece -> moves (+0,+7) [+4.5]
- ACTION2: piece type 0/887f -> moves (+7,+0) [+4.5]
- colour 1 ahead of a piece -> the move is favoured [+4.5]

## Offline (S2)

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


## What changed, and where it is called

- **tl/engine.py (new)**: Sparse relations with named indices, join / projection / step with a temperature, forward chaining to fixpoint, learnable multilinear tensor equations with their own gradient equations, softmax loss, Adam with an L1 (description-length) step. Called by tl/learner.py, tl/rule.py, tl/plan.py.
- **tl/relations.py (new)**: Perception as a relational database: per-step relations over objects (colour, type, controlled, common-fate group, what lies ahead in each move direction, run into / stood on / next to / clicked / moved along with the controlled piece, changed last step, own history, the previous run's tape) and per-object effect targets from the tracker. TLState is made in agent.start_play (via tl/bridge.make_tl) and kept by rules.ContextBuilder: begin(), annotate() into RuleContext.tl, observe() after every step (training rows).
- **tl/learner.py (new)**: The join-shape bank (own x action, ahead, own relation, linked object, own history with a learned lag, previous run with a learned lag), gradient fit, structure switched on by the zero-gradient test (also on surprise spikes, with a backward-chaining explanation), thresholding + model reduction, export as rules, and the learned mover. Called through tl/bridge.TLSource by hypotheses.HypothesisProposer.propose, agent.observe (spikes) and explore.ObjectContactExplorer.mover_model.
- **tl/rule.py (new)**: TLRule: the thresholded program frozen into a rules.Rule (weights in its identity), priced in the templates' currency, predicted by forward chaining; scored and selected by beliefs.BeliefState like any rule; sits before the move templates in the decision list (rules.PRIMARY_ORDER).
- **tl/plan.py (new)**: Reachability as forward chaining over sprite offsets (free-space map by correlating the sprite with the learned walls); replaces explore.search when ExploreConfig.search == 'tl' (set by agent.start_play when use_tl and tl_plan).
- **tl/bridge.py (new)**: make_tl() and TLSource (propose / surprise / mover): the glue agent.py uses.
- **tl/offline.py, tl/report.py, tl/verify_default.py (new)**: Stage-two offline evaluation, this report, and the default-off action-for-action check against the backup.
- **tests/test_tl.py (new)**: Ten tests: engine, relations, learner, rule price and exact replay, planning, default off.
- **rules.py**: RuleContext.tl; ContextBuilder(hdc, tl) begins / annotates / observes the TLState; PRIMARY_ORDER gains 'tl'.
- **agent.py**: AgentConfig.use_tl / tl_templates / tl_plan / tl_cfg; start_play builds the TL state and source, turns the templates off when asked, and switches the explorer's search; observe() sends surprise spikes to the learner.
- **hypotheses.py**: HypothesisProposer.tl adds the learned rules to the candidates; .templates = False drops the template fitter.
- **explore.py**: ExploreConfig.search; the learned mover when there is no template mover (tl_only); the sprite's parts from the relational view's group; the forward-chaining search.
- **game_sweep.py**: Arms touch_tl and tl_only; per-play learned-rule adoption, active equations, learner time, learned clauses; trips for every arm.
