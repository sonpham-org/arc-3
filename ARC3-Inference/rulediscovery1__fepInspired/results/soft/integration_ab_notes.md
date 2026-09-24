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
