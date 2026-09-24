# Roadmap: hyperdimensional (phasor VSA) time model for delayed copies (Ghost Twin first)

Asked by OpenMind in #arc-3, 24-Sep-2026 00:44 ET: implementation + testing roadmap, KISS, built to avoid dead ends.
Code home (when started): `~/GitHub/arc-3/ARC3-Inference/rulediscovery1__fepInspired/hdc/` (uncommitted).

## Rules of the road
- One question per stage, one number that answers it, one kill/redirect rule. No stage starts before the previous gate is met.
- Synthetic data before real data; real traces before live play.
- Brute force before clever: score a small explicit list of hypotheses before building resonator networks.
- The game's internals (simulator) are used only to make test labels, never inside the model.
- Timebox every stage (half a day). Over the box = stop and write down why before continuing.
- Every stage result goes into the analysis doc and provenance (stream project:arc3).

## Stages
0. **Ground truth.** From the 30 Ghost Twin plays already used, extract per step: action, player and ghost positions,
   rewind events (from the simulator, labels only). Gate: 30 plays extracted, ghost steps counted.
1. **VSA core, ~100 lines numpy.** Complex phasor vectors (D = 1024 / 4096): bind = multiply, unbind = conjugate,
   bundle = sum, permute = roll, fractional power encoding for x/y, cleanup = best cosine match.
   Tests: bind/unbind recovers the item; FPE shift is exact (encode(x) * X^dx == encode(x + dx)); measured capacity
   curve (retrieval accuracy vs items bundled, per D). Gate: tests pass, capacity curve saved.
2. **Tape on synthetic sequences.** Store random move sequences (length up to 200) as sum_k roll^k(D_k); read back step k.
   Gate: >= 99 % exact read-back at length 200 for the chosen D. Redirect: raise D or chunk the tape per run.
3. **Lag filter on a synthetic ghost.** Synthetic player path, a reset, then an object copying the previous run
   (plus distractor objects that move randomly or not at all). Score each (object, source run, lag) hypothesis by
   summed similarity. Gate: right object and lag within 5 steps after the reset; distractors never chosen.
   Kill: if it needs more than about 10 steps on clean synthetic data, the encoding is wrong -- fix before real data.
4. **Real Ghost Twin traces, offline.** Our perception gives object tracks; rewind = player jumps back to its start
   without RESET. Run the stage-3 filter. Gate: ghost and lag identified in >= 90 % of plays with a ghost; next ghost
   move predicted exactly on >= 90 % of ghost steps. Redirect: if tracks are the problem (ghost identity lost), fix
   perception, not the VSA.
5. **Tape rule inside the rule-discovery posterior.** A rule "object o repeats run r's moves from its start" that the
   existing belief machinery scores like any other rule. Gate: offline nats/step on Ghost Twin ghost steps clearly
   better than the chain back-off; the 30-play yardstick on other games not worse.
6. **Live on the simulator.** Planner simulates the ghost from the tape: search "walk to the switch, rewind, walk to
   the goal". Also give rewind a cost once it is learned to reset progress. Gate: Ghost Twin level one cleared in
   most seeds (language-model baseline: 10 of 30 plays).
7. **Only now the clever parts.** Resonator network for factoring unknown (object, run, lag, offset) when the explicit
   hypothesis list gets too big; spatial semantic pointers for positions/movement so walls and moves share one
   algebra. Each enters only if it beats the brute-force version on the stage-4/6 numbers.
8. **Generality.** Same pipeline on the game sweep (Locksmith, Warehouse Associates, others with the engine).
   Gate: no game gets worse; any new clears are named.

## Known dead ends to avoid
- Tuning dimensions and noise before the synthetic gate passes.
- Building the resonator network first.
- Testing on live play before the offline prediction is right.
- Encoding the whole board as one vector (tonight's whole-board EBUL code gave one code for every Locksmith board).

## Status (24-Sep-2026, ~02:45 ET)
- 0 done (20 plays). 1 pass. 2 pass (after the no-move fix). 3 pass on identification (197/200), decision at 8-9 actions not 5.
- 4: prediction 93 % (pass); finding 26/49 (fail). Summed-evidence rule tried, worse.
- 5: tape rule cuts nats on decided ghost steps 0.56 -> 0.41; overall 1.00 -> 0.95. Not in the agent's RuleSet yet.
- 6: 0 clears (fail). Rewind learned from perception; compulsion fixed; three perception/wall fixes; open: make-vs-erase rewind.
- 7: resonator loses to brute force at every tested size; not adopted. SSP walls not attempted.
