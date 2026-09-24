# Proposal: get the rule discovery agent to clear Locksmith (23-Sep-2026, 23:45 ET)

Asked by OpenMind in #arc-3 ("analyze how to improve score", "make proposal").
Code: `~/GitHub/arc-3/ARC3-Inference/rulediscovery1__fepInspired/` (uncommitted).
Test bed: `env.py` (exact Locksmith simulator), `locksmith_run.py` (10 seeds x 500 actions, RESET offered).

## Where we stand
- Level one: 89 reachable states, shortest clear 13 moves (rotation tile, then lock). Step bar: 42 moves per life, 3 lives.
- Language-model harness: level one cleared in 30 of 43 recorded plays, about 21 actions typical.
- Rule agent: 0 clears (one lucky curiosity clear earlier). It explores, it uses RESET, the movers now beat
  the counts on evidence, but the prior still prices them out and the planner never starts.

## Steps (each ends with a rerun of the Locksmith table; keep a step only if it helps)
1. **Plan to touch untouched objects.** New goal "reach the nearest object not yet touched this level";
   the planner walks the shortest path in the imagined board under the MAP movers. Lower the planning gate:
   plan whenever a mover for the controlled object is in the MAP rule set (drop the "posterior almost
   certain + goal p > 0.5" requirement for this goal). Fall back to curiosity when no path is known.
   *Done when:* level one cleared in most seeds, in well under 100 actions.
2. **One mover for all four arrows.** Template "each arrow moves the controlled sprite one step in its own
   direction, same walls" priced once, not four times. Or fit the prior strength by empirical Bayes on
   other games' plays. *Done when:* a mover is in the MAP rule set within the first ~10 moves in most seeds.
3. **Key-matches-lock goal.** Goal "make the key display equal the lock's picture, then enter the lock";
   rotation/colour/shape tiles learned as contact rules that change the key. *Done when:* levels two and
   three (several key changes in order) clear in some seeds.
4. **RESET only to survive.** A counter rule on the step bar (read before the HUD mask hides it, or from
   the life-loss event) predicts the next life loss; RESET's value comes from avoiding game over, not
   novelty. *Done when:* resets per play drop to a handful with no increase in game overs.
5. **Check it is not Locksmith-only.** Same table on two other button games with the same engine
   (sources in `docs/static/games/src/`), and the offline 30-play yardstick must not get worse.

## Guardrails
- Never train on the held-out seven; the EBUL encoder stays trained on other games only.
- Nothing committed or pushed to sonpham-org/arc-3 without Son's say-so.
- Every run logged in the analysis doc and in provenance (stream project:arc3).

## Status (24-Sep-2026, 00:25 ET)
- Step 1 done: explore.py. Locksmith level one cleared in 10 of 10 seeds (first clear at action 32-51).
- Step 2 done: PadMoveRule. Helps the offline yardstick (+0.053 nats/step vs chain); still not enough to
  win posterior weight within a play, so the explorer plans with the fitter's best mover directly.
- Step 3 not started. Step 4 not started (level two ends in game over 9-10 of 10).
- Step 5: Ghost Twin and Warehouse Associates show no gain (0 levels, all arms). Not general yet.
