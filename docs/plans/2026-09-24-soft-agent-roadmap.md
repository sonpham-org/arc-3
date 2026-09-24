# Roadmap: moving the rule-discovery agent to soft computing (24-Sep-2026, 09:15 ET)

Asked by OpenMind in #arc-3 ("sounds all good ... tell me implementation roadmap"), for the five proposals of 09:07 ET.
Code: `~/GitHub/arc-3/ARC3-Inference/rulediscovery1__fepInspired/` (uncommitted).
Backup made first: `ARC3-Inference/backupsOldVersions/rulediscovery1__fepInspired_feef72470160/` (suffix = content hash, verified identical).

## Rules of the road (same as the ghost roadmap, they worked)
- One question, one number, one kill/redirect rule per stage; a stage starts only when the one it depends on passes.
- Recorded plays offline first, live simulator second. The simulator's internals only make test LABELS.
- Brute force before clever. Every new soft piece must beat the current explicit piece on its own number, or it does not replace it.
- Half-day timebox per stage; over = stop and write down why.
- After every stage: game sweep (`game_sweep.py`) + offline 30-play yardstick; nothing may get worse.
- New code in `rulediscovery1__fepInspired/soft/`; reuses `hdc/vsa.py`.

## Track A -- perception that learns (first: most of last night's bugs)
- A0 labels: extend `hdc/stage0_groundtruth.py` to Locksmith, Ghost Twin and 3 more local games: per step, true sprite membership of
  every moving part, true blocked/not for every move attempt, true gauge values (step bar, timer). Gate: labels for 20 plays per game.
- A1 common-fate objects: Hebbian affinity between components (same displacement on the same step), grouping by threshold.
  Gate: >= 95 % of moving parts grouped with their true sprite (Locksmith two-colour block, Ghost Twin centre dot).
- A2 co-change links: affinity for "changed on the same step" (appear / vanish / recolour). Gate: Ghost Twin switch<->door link found
  in most plays where the door toggles; false links rare. Redirect: if noisy, require the link to repeat twice.
- A3 soft wall map: bundle blocked attempts as place (x) colour, successful steps likewise; query by similarity.
  Gate: predicts blocked/not better than the current colour rule on all attempted moves, and never walls the Ghost Twin wire.
- A4 gauges: regions whose pixel count changes monotonically, value as a fractional-power scalar. Gate: Locksmith step bar and
  Ghost Twin timer found; next value predicted exactly >= 95 %.

## Track B -- predict vs plan
- B1 associative transition memory: (object type, action, local patch) -> effect vector, one-shot store, Hopfield-style cleanup.
  Gate: on FIRST-CONTACT steps (counts are blind there) it predicts the moved objects' displacement better than the counts.
- B2 imagined rollouts: breadth-first / beam search in the memory, replacing the hand-written offset search in `explore.py`.
  Gate: Locksmith level one still 10/10 seeds (today's explorer result) with the search running on the learned memory.
- B3 prior strength by empirical Bayes on other games' plays. Gate: offline 30-play not worse, movers adopted earlier.

## Track C -- rules with memory
- C1 tape rule as a real rule class; rule context gets the run history (temporal context vector + per-run tapes).
  Gate: Ghost Twin offline nats on ghost steps better than counts inside the agent's own posterior (today: 0.56 -> 0.41 standalone).
- C2 "copy, then stop when the path ends" beats "stands still"; ghost found in >= 90 % of ghost-making rewinds (today 53 %).
- C3 make vs erase: a rewind that removes the copier is learned as a different outcome (fixes stage 6's open problem).

## Track D -- goals
- D1 relations as bound vectors (player-on-X, same-shape(A,B), inside(A,B)); goal vector = bundle(pre-clear) - bundle(other).
  Gate: on held-out levels the goal vector ranks the actual pre-clear state in the top few of the play.
- D2 similarity climbing: key code vs lock picture code. Gate: offline, similarity rises with each correct Locksmith rotation.

## Track E -- budget
- E1 drain rate per action and refills per pickup, learned on A4 gauges. Gate: exact next-value prediction on both games.
- E2 survival preference in expected free energy; RESET and refill values learned from observed jumps.
  Gate: game overs per play clearly down on Locksmith and Ghost Twin, with no fewer levels.

## Live milestones (only after the offline gates they need)
- M1 Locksmith level two cleared in some seeds (needs A3, A4, B2, D2, E2).
- M2 Ghost Twin level one cleared in some seeds (needs A2, C2, C3, B2).
- M3 sweep: any new clears on other local games named; nothing worse.

## Order
A0 -> A1 -> A3 -> A4 -> B1 -> B2 -> C1-C3 -> E1-E2 -> D1-D2 -> M1, M2 -> M3. A2 alongside A1 (same machinery).
