# HDC integration A/B -- rule agent with vs without the phasor / fractional-power / hyperdimensional pieces

24-Sep-2026, Claude Opus 5.5 (Bubba), for OpenMind (#arc-3, 10:17 ET). Nothing committed or pushed.
Backup of the untouched package: ../backupsOldVersions/rulediscovery1__fepInspired_5fe717f335a8

## Live A/B (exact local simulator, 10 seeds per game per arm, 500 actions, RESET offered, a game over ends the play -- the first sweep's settings)

Arms: `touch` = rule agent + object-contact explorer + curiosity (the first sweep's best arm); `touch_hdc` = the same with AgentConfig.use_hdc=True (all three pieces). Same code path, same seeds 0-9. Prediction quality is the agent's own prequential surprise on its own trajectory; 'rules' gain' = counts-only nats minus posterior nats on the same steps, so it is comparable across arms even though the arms walk different paths.

| game | arm | levels cleared | plays clearing | action of each clear | game overs | mean actions | nats/step posterior | nats/step counts | rules' gain/step | steps where the tape had an opinion | rules' gain/step on those steps (all rules, not the tape rule's own effect) |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Ghost Twin (g50t:5849a774) | touch | 0 | 0/10 | - | 7 | 370 | 1.525 | 1.838 | 0.313 | 0 | - |
| Ghost Twin (g50t:5849a774) | touch_hdc | 0 | 0/10 | - | 8 | 288 | 1.610 | 2.148 | 0.538 | 42 | 0.232 |
| Locksmith (ls20:9607627b) | touch | 10 | 10/10 | [[48], [42], [50], [47], [49], [32], [51], [50], [37], [32]] | 9 | 257 | 1.230 | 1.638 | 0.409 | 0 | - |
| Locksmith (ls20:9607627b) | touch_hdc | 10 | 10/10 | [[48], [50], [42], [47], [49], [32], [51], [50], [37], [32]] | 9 | 252 | 1.224 | 1.644 | 0.419 | 0 | - |
| Warehouse (wa30:ee6fef47) | touch | 0 | 0/10 | - | 3 | 460 | 1.740 | 1.975 | 0.234 | 0 | - |
| Warehouse (wa30:ee6fef47) | touch_hdc | 0 | 0/10 | - | 3 | 464 | 1.739 | 2.065 | 0.326 | 0 | - |

Paired by seed (rules' gain per step, touch_hdc minus touch):

- Ghost Twin (g50t:5849a774): touch_hdc ahead on 10 of 10 seeds, mean difference 0.271 nats/step
- Locksmith (ls20:9607627b): touch_hdc ahead on 4 of 10 seeds, mean difference 0.007 nats/step
- Warehouse (wa30:ee6fef47): touch_hdc ahead on 7 of 10 seeds, mean difference 0.104 nats/step

## Each piece alone (live, same settings)

| game | arm | levels cleared | plays clearing | action of each clear | game overs | mean actions | nats/step posterior | nats/step counts | rules' gain/step | steps where the tape had an opinion | rules' gain/step on those steps (all rules, not the tape rule's own effect) |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Ghost Twin (g50t:5849a774) | touch_tape | 0 | 0/10 | - | 7 | 370 | 1.525 | 1.838 | 0.313 | 58 | -0.576 |
| Ghost Twin (g50t:5849a774) | touch_walls | 0 | 0/10 | - | 6 | 343 | 1.555 | 1.889 | 0.333 | 0 | - |
| Ghost Twin (g50t:5849a774) | touch_fate | 0 | 0/10 | - | 6 | 342 | 1.436 | 1.929 | 0.493 | 0 | - |
| Locksmith (ls20:9607627b) | touch_tape | 10 | 10/10 | [[48], [50], [42], [47], [49], [32], [51], [50], [32], [37]] | 9 | 257 | 1.230 | 1.638 | 0.409 | 0 | - |
| Locksmith (ls20:9607627b) | touch_walls | 10 | 10/10 | [[48], [50], [42], [47], [49], [32], [51], [50], [37], [32]] | 9 | 252 | 1.224 | 1.644 | 0.419 | 0 | - |
| Locksmith (ls20:9607627b) | touch_fate | 10 | 10/10 | [[50], [48], [42], [47], [49], [32], [51], [50], [37], [32]] | 9 | 257 | 1.230 | 1.638 | 0.409 | 0 | - |
| Warehouse (wa30:ee6fef47) | touch_tape | 0 | 0/10 | - | 3 | 460 | 1.740 | 1.975 | 0.234 | 0 | - |
| Warehouse (wa30:ee6fef47) | touch_walls | 0 | 0/10 | - | 3 | 460 | 1.755 | 2.010 | 0.255 | 0 | - |
| Warehouse (wa30:ee6fef47) | touch_fate | 0 | 0/10 | - | 2 | 481 | 1.814 | 2.147 | 0.333 | 0 | - |

Paired by seed against `touch` from the A/B above (rules' gain per step):

- Ghost Twin (g50t:5849a774), touch_tape: ahead on 0 of 10 seeds, mean difference 0.000 nats/step
- Ghost Twin (g50t:5849a774), touch_walls: ahead on 4 of 10 seeds, mean difference -0.017 nats/step
- Ghost Twin (g50t:5849a774), touch_fate: ahead on 9 of 10 seeds, mean difference 0.215 nats/step
- Locksmith (ls20:9607627b), touch_tape: ahead on 0 of 10 seeds, mean difference 0.000 nats/step
- Locksmith (ls20:9607627b), touch_walls: ahead on 4 of 10 seeds, mean difference 0.007 nats/step
- Locksmith (ls20:9607627b), touch_fate: ahead on 0 of 10 seeds, mean difference -0.000 nats/step
- Warehouse (wa30:ee6fef47), touch_tape: ahead on 0 of 10 seeds, mean difference 0.000 nats/step
- Warehouse (wa30:ee6fef47), touch_walls: ahead on 5 of 10 seeds, mean difference 0.018 nats/step
- Warehouse (wa30:ee6fef47), touch_fate: ahead on 7 of 10 seeds, mean difference 0.104 nats/step

## Prediction quality per piece, offline (recorded plays, engine labels score only)

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

## What changed, where, and where it is called

| file | change | called from |
|---|---|---|
| agent.py | AgentConfig.use_hdc (default False) + hdc_pieces; start_play gives the ContextBuilder an hdc_bridge.HdcState and calls ctx.begin(first board) | every play; off = the old path, action-for-action equal to the first sweep on the three seeds spot-checked |
| hdc_bridge.py (new) | HdcState: GhostTape (phasor run tapes, stage-3/4 finder), WallMap/WallView (fractional-power place x colour memory, per-step snapshot, per-cell score map), revocable common fate; annotate() freezes the per-step values into the rule context | rules.ContextBuilder.context / observe, every step |
| rules.py | RuleContext gains tape / walls / fate; ContextBuilder builds them and advances HdcState; TapeRule (modifier: an object repeats an earlier run); RuleSet.predict gates it on the player-move clock; MoveRule asks the soft wall map where its colour sets are silent (colour first); group FATE takes the sprite's parts from common fate (sprite_parts / fate_partners / soft_wall) | beliefs scoring and replay, the policy's predictions, the planner, the fitter |
| hypotheses.py | TemplateFitter proposes TapeRule once the tape has explained an object; fit_moves uses the FATE group instead of co_movers when the fate piece is on (fate_riders drops parts riding on the sprite); track_record does not count the tape rule on steps where its clock did not tick | every proposal (every 5 steps, on surprise spikes and clears) and the explorer's mover lookup |
| explore.py | sprite() takes common-fate partners for a FATE mover; search() takes the soft wall snapshot and refuses a step whose new strip the colour sets cannot judge and the soft map calls blocked | every trip the touch explorer plans |
| hdc/stage4_real.py | Tracker.update_objects (parsed objects in, component per track kept) | hdc_bridge, so the board is parsed once |
| soft/a1_common_fate.py | optional decay (revocable fusion), update_objects, last_moves, prequential scoring | hdc_bridge (live), integration_offline (table) |
| soft/a3_walls.py | SoftWalls.score, ColourRule.verdict, guarded variants in run_game | integration_offline |
| game_sweep.py | arms touch_hdc / touch_tape / touch_walls / touch_fate, --arms, --tag, prediction-quality fields | this A/B |
| tests/test_hdc_bridge.py (new) | off = bare contexts; tape rule and clock gating; wall snapshot and linearity; exact replay with HDC on | pytest |

## Tests

Before any change: 36 passed, 1 failed (tests/test_policy.py::test_salience_ranks_disagreement_first). After: see the run recorded below.

## Reading of the results

**Headline (pre-committed): levels cleared do not move.** Locksmith: both arms clear level 1 in 10 of 10 plays at
the same action on every seed (9 of 10 seeds also end at the same action; seed 0 ends earlier with HDC), and both
lose level 2 the same way (9 game overs each). Ghost Twin and Warehouse: no level cleared by either arm, as in the
first sweep. Game overs: Ghost Twin 7 -> 8, Locksmith 9 -> 9, Warehouse 3 -> 3.

**What moves is prediction quality, and it comes from one piece: common-fate grouping.**
- Rules' gain over the counts (nats per step, higher = the rule sets explain more than the counts): Ghost Twin
  0.313 -> 0.538 (HDC ahead on 10 of 10 seeds), Warehouse 0.234 -> 0.326 (7 of 10), Locksmith 0.409 -> 0.419
  (4 of 10, i.e. no change). The fate piece alone gives almost all of it: Ghost Twin +0.215 (9 of 10 seeds),
  Warehouse +0.104 (7 of 10), Locksmith 0.000 (identical plays).
- Honest caveat: the arms walk different paths once a decision differs, so absolute surprise is not like for like.
  Absolute posterior nats per step: Ghost Twin 1.525 -> 1.610 (worse), Locksmith 1.230 -> 1.224, Warehouse
  1.740 -> 1.739. The HDC arm's Ghost Twin trajectories are harder for everyone (counts 1.838 -> 2.148), and its
  rules close more of that gap; the gain column is the like-for-like number, the absolute one is not.

**Per piece.**
- Tape rule (the only piece with a measured posterior win offline: ghost-step nats 0.559 -> 0.405 on decided steps,
  recorded plays): wired and exact under replay, but idle live. It never gained weight in the posterior: never in the
  final MAP rule set (0 of 60 plays with the tape on), and tape-only plays are identical to plain touch in every
  reported figure (lengths, game overs, surprise to three decimals, 0 of 10 seeds different on each game). The table
  column "rules' gain on steps where the tape had an opinion" measures the other rules on those steps, not the tape
  rule; it did nothing, it did not hurt. Why (seed 2 traced):
  the agent's own runs are short (it rewinds or resets often), so by the time the finder has 8 observations and
  decides, the copied run is used up and the tape predicts "stands still", which adds no event to the label and so
  cannot beat the counts; its description length then keeps it out. It also costs time on Locksmith (dying at the
  start position looks like a rewind: 20 s -> 61 s per play). Kept behind its sub-flag.
- Soft wall map (colour rule first, soft map fills the colour rule's silence, margin 0.05): offline it is the best (or tied
  best) guard on Ghost Twin (accuracy 0.769 -> 0.851, blocked recall 0.288 -> 0.703) and Locksmith (0.964 -> 0.987),
  and still slightly below the colour rule on Warehouse (0.837 -> 0.831, with 116 false walls against 17). Live it is
  about neutral: Ghost Twin -0.017 (4 of 10), Locksmith +0.007, Warehouse +0.018 (5 of 10). Soft-map-first with
  abstention was worse than colour-first on every game offline, so that guard was not used.
- Common fate, revocable (decay 0.8): Warehouse did NOT get worse live (rules' gain +0.104, game overs 3 -> 2, mean
  actions 460 -> 481), so it is not gated. Offline, revocable fusion does not fix Warehouse's grouping precision
  (0.359 -> 0.352 prequential; the carried box genuinely shares the player's fate while carried) and costs recall on
  every game (e.g. Ghost Twin 0.697 -> 0.613). So the live win is from instance-level grouping replacing the
  type-level co-mover rule (type rule recall 0.46 Ghost Twin / 0.05 Warehouse; revocable common fate 0.61 / 0.39 even
  scored step by step, which the type rule was not), not from revocability; the
  permanent version was not run live and may do as well or better.
- B1 associative transition memory: not done (time box; the file does not exist yet).

**Cost.** Mean seconds per play, touch -> touch_hdc: Ghost Twin 56 -> 64, Locksmith 20 -> 74 (the tape bookkeeping),
Warehouse 56 -> 61.

**Next.** (1) Fate: run the permanent (non-decaying) fusion live against the revocable one; it has the better offline
recall. (2) Tape: let the finder decide on summed evidence earlier, and let a decided "stands still" become a claim the
rule can make (a ghost that stays put is itself a prediction the counts lack); only then does the tape rule have
something to win with. Also stop treating a death respawn as a rewind (it costs time on Locksmith). (3) Walls:
the Ghost Twin wire/door colour problem from A3 still needs the door state bound into the query.

**Tests after the change** (python3 -m pytest rulediscovery1__fepInspired/tests): 40 passed, 1 failed -- the same
pre-existing failure (test_policy.py::test_salience_ranks_disagreement_first); no new failures. New file
tests/test_hdc_bridge.py: 4 tests, all pass (including exact replay with HDC on).

**Reproduce** (from ARC3-Inference/): `.venv/bin/python -m rulediscovery1__fepInspired.game_sweep --games
g50t:5849a774 ls20:9607627b wa30:ee6fef47 --arms touch touch_hdc --seeds 10 --budget 500 --tag hdc_ab` (and
`--arms touch_tape touch_walls touch_fate --tag hdc_pieces`), then `-m rulediscovery1__fepInspired.soft.integration_offline`
and `-m rulediscovery1__fepInspired.soft.integration_report`. Logs: results/game_sweep/hdc_ab/sweep.log.
