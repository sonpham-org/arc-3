# Debate five, picks 2 and 3: implementation and evaluation (25-Sep-2026)

Author: Claude Opus 5.5 (Bubba), for OpenMind (#arc-3, 25-Sep-2026 17:14 ET: "make copy into folder with random hash suffix,
then do 2 and 3. Then evaluate, then report"). Plan: ~/bubba-workspace/docs/2026-09-25-openmind-agent-expert-debate-5.md,
Round 7 (picks 2 and 3; judging from Round 6). Local only; nothing committed or pushed from this package. Backup before the
first edit: ../backupsOldVersions/rulediscovery1__fepInspired_a6980e8cb538 (verified identical to the folder). No
"switches off = old behaviour" check (OpenMind's rule); the d4_opt rerun equals debate four's d4_opt rows in all 60 plays
(clears, actions, presses per button), so the new switches are inert when off.

## Verdicts, per game

- **Warehouse (wa30):** pick 2 doubles interact at grab positions (17% -> 38%; random 19%) and a box rests on a target in
  14 plays instead of 7, but no play clears: the one d4_opt clear (seed 11) is lost with pick 2 on, in every arm that has
  it. Pick 3 alone keeps that clear and changes little else (17%, 9 plays with a box on a target). No level two anywhere.
- **Locksmith (ls20):** level one 20/20 in every arm, no level two in any arm. Pick 2 is slower: median first clear 50 vs 47
  (mean 58 vs 52; 6 seeds slower, 2 faster). Pick 3 alone: 46.5 (3 seeds changed). Both: 48.
- **Ghost Twin (g50t):** d4_opt 5 clears (seeds 4, 5, 7, 17, 19). Pick 2: 5 (loses 4, 5, 7, 19; gains 8, 9, 10, 13). Pick 3:
  3 (loses 4, 7, the two late clears at actions 403 and 494). Both: 7 (loses 4, 7; gains 8, 9, 10, 13).

| pick | measure (debate) | result | old per-seed guard | total clears, sign test (debate, Round 6) | Locksmith gate |
|---|---|---|---|---|---|
| 2 flat outcome preferences before the first clear | Warehouse interact at box positions above random; more Warehouse clears | above random (38% vs 19%); clears 0 vs 1 | FAIL (Ghost Twin 4, 5, 7, 19) | canaries 25 vs 25 (4 up, 4 down, p = 1); all three games 25 vs 26 | 20/20, but SLOWER (its kill rule says "or slower") |
| 3 rule library + reuse discount + self / move carry-over | second-level clears; fewer steps to re-learn | no level two anywhere; re-learning unchanged (below) | FAIL (Ghost Twin 4, 7) | canaries 23 vs 25 (0 up, 2 down, p = 0.5): its kill rule "total clears drop" TRIGGERED | 20/20, not slower |
| 2 + 3 together | both of the above | Warehouse as pick 2; Ghost Twin 7 vs 5 | FAIL (Ghost Twin 4, 7) | canaries 27 vs 25 (4 up, 2 down, p = 0.69); all three games 27 vs 26 | 20/20, one action slower at the median (7 slower, 5 faster) |

Which picks pass: under the old per-seed guard, none. Under the debate's totals rule with Locksmith 20/20 as the only hard
gate: pick 2 passes on clears (no change), pick 3 alone fails its own kill rule, picks 2 + 3 together pass (+2 clears, not
significant). Separately, pick 2's own kill rule ("Locksmith below 20/20 or slower") is triggered on its speed clause: median
first clear 50 against 47, 6 seeds slower and 2 faster (sign test on the paired first clears p = 0.29, not significant).
Whether three actions at the median counts as "slower" is OpenMind's call. None of the differences in clears is
statistically meaningful at 20 seeds per game. OpenMind decides which rule applies.

Does try-once still matter with pick 2 on? Hardly. With flat preferences, Locksmith and Ghost Twin plays are identical with
and without try-once (all 20 plays each: same clears, same presses of every button); on Warehouse, dropping try-once gives 36% vs 38% interact at grab
positions, the same 14 plays with a box on a target, no clears either way. Flat preferences make the ordinary comparison
interrupt trips about 82 times per Warehouse play (14 with d4_opt), so try-once's one press per new contact rarely adds
anything.

## What was built (each an AgentConfig switch, default off, on top of d4_opt; game-agnostic, no game internals, no language model)

| pick | switch | files | what it does |
|---|---|---|---|
| 2 | `flat_prefs` | goals.py (Preferences flat_until_clear, cleared), agent.py | Until the play's first clear every ordinary outcome's log preference is 0. The learned relative preference (p(clear soon given outcome) over the base rate, shrunk) has no hits before a clear, so it was log(prior_n / (n + prior_n)): the more often an outcome was seen, the less it was wanted, which priced interact's expected "nothing" as the worst outcome. Kept: the fixed clear and game-over preferences, the game-over aversion (outcomes seen before a game over), the budget run-out term (policy.py, from c_game_over), and the goal-progress term. Counts are kept all along, so after the first clear preferences are exactly the learned ones. |
| 3 | `carry_library` | library.py (new: RuleLibrary, LibraryConfig), beliefs.py (BeliefState.library in price()), agent.py (`_restart`, `_carry`) | On a level clear, a RESET (the agent's or an archive return's) and a lost life (a run-out the play survived, from the budget reader) the posterior's top rule sets that beat counts-only (the MAP always, a second if weight >= 0.1) go into a library of at most 6 sets, newest first. The MDL prior prices each library rule at half its description length (new rules pay full price), inside price(), so the per-step re-pricing and the proposer's greedy builder both see it. After each such event the library's sets re-enter the posterior by exact replay over the stored steps (their weight is earned). On a level change the self's learned moves are tempered to at most 4 presses per button (proportions kept), a starting belief the new level can overturn; a RESET or a lost life keeps the full counts. Within one play only. |

What already carried before pick 3 (probe on Locksmith seed 0 and Warehouse seed 11, and a test): the whole slow memory
survives clears and RESETs within a play: the rule-set posterior and its stored steps, the goal beliefs, the preferences,
the habits, the self's learned moves and the explorer's press counts. Only the per-level fast memory, the explorer's touch
set and the archive's cells are per level; a game over ends the play. So "each level is a fresh start" was not true of this
agent; what was missing was a memory of rule sets once pruned (the Warehouse seed-11 rule set that held at the clear was gone
10 actions after it) and any price advantage for rules that held before.

game_sweep.py: arms d5_flat (2), d5_lib (3), d5_both (2 + 3), d5_flat_notry (2 without try-once); every agent play also records
per restart the actions until the MAP rule set is right again (its predicted parts all occur) on 5 scored steps in a row, and
whether the rule set that was MAP just before is still a hypothesis / still MAP 10 actions later; the library's report.
Tests: 119 passed, 1 failed (the pre-existing test_salience_ranks_disagreement_first); tests/test_debate5.py has 10 new.

## How each pick behaved

**Pick 2.** On Warehouse the agent now presses interact at 771 of 2056 grab positions (d4_opt 218 of 1250); checks at grab
positions double (1409 vs 728) and comparison interruptions go from about 14 to about 82 per play. Grabs 771, drops 727. A box
rests on a target in 14 plays (the first one at a median of about action 110), but never more than 2 of the 3 at once, and the
seed-11 play that cleared with d4_opt (3 boxes) now reaches only 1. On Locksmith every arrow already has a learned move, so the
change works through the policy's choices between trips: the same 20 clears, a little later. Ghost Twin: game overs 3 -> 1,
RESETs per play 11 -> 14.5, the clearing seeds swap (4 lost, 4 gained): divergence, not a lasting effect we can name.

**Pick 3.** The library fills quickly (median 5-6 sets; about 55 sets re-seeded per Locksmith play, 21 Ghost Twin, 10
Warehouse). Re-learning after a restart does not change: after a RESET the MAP rule set was already still MAP 10 actions
later in 175 of 186 Locksmith restarts with d4_opt (179 of 189 with the library), and re-learning takes the minimum 5 actions
either way. After a lost life on Locksmith the old MAP is still MAP 10 actions later more often (34 of 44 vs 26 of 45).
After a Locksmith clear re-learning takes a median 12 actions vs 14.5 (both arms 15.5): no reliable change. No arm clears a
second level on any game, so the pick's main measure could not move. The two Ghost Twin seeds it lost (4 and 7) diverge
from d4_opt early: the library stores its first rule sets at an early RESET (actions 26 and 54) and the two plays differ at
their first explorer check (actions about 56-62), hundreds of actions before d4_opt's late clears there (403, 494); after
that the RESETs fall at different times and the plays never realign. The rows do not show a specific wrong prediction; the
discount changes the posterior in the opening and the play goes elsewhere (divergence, not a named defect, as far as the
rows can tell).

## Next

- Pick 2 does what the debate predicted on the behaviour (interact well above random, boxes on targets in twice the plays)
  but not on clears: no Warehouse play gets all 3 boxes on the targets. The missing piece is now the goal, not the button:
  after a box rests on a target nothing prefers keeping it there and adding the next.
- Pick 3 had little to add because the agent already carries its slow memory; its library mostly re-enters sets that were
  never lost. Level two is never reached on Locksmith (level one clears at about action 47, then 450 actions without a
  second clear) and that failure is not about forgetting: it needs its own look.
- Clear counts at 5-7 of 20 on Ghost Twin swing by several seeds under any change; 20 seeds cannot separate these arms. More
  seeds (debate five said 40 per game) would.

## Files and data

Raw rows: results/game_sweep/debate5/rows.json (300 plays: d4_opt, d5_flat, d5_lib, d5_both, d5_flat_notry x 3 games x 20
seeds; 500 actions, seeds 0-19, RESET offered, exact simulators, 10 workers, per-play limit 1800 s, no time-outs, median play
2-3 minutes); random arm results/game_sweep/dp_random/rows.json. Tables below: results/debate5/tables.md and tables.json,
generated from those rows by ~/bubba-workspace/scratch/debate5/debate5_report.py; Warehouse labeller
~/bubba-workspace/scratch/debate4/debate4_labels.py (unchanged); carry-over probe ~/bubba-workspace/scratch/debate5/carry_probe.py.
Key numbers re-checked against the raw rows by a separate script.

---

## Warehouse (wa30)

| arm | plays | levels | plays clearing level 1 | plays clearing level 2 | first clear (median action) | level 2 length (median) | game overs | RESETs per play | time-outs | play seconds (median) |
|---|---|---|---|---|---|---|---|---|---|---|
| random | 20 | 0 | 0 | 0 | None | None | 0 | 78.8 | 0 | 0.1 |
| d4_opt | 20 | 1 | 1 | 0 | 151 | None | 1 | 6.15 | 0 | 184.7 |
| d5_flat | 20 | 0 | 0 | 0 | None | None | 0 | 5.2 | 0 | 186.95 |
| d5_lib | 20 | 1 | 1 | 0 | 151 | None | 1 | 6.1 | 0 | 192.85 |
| d5_both | 20 | 0 | 0 | 0 | None | None | 0 | 5.1 | 0 | 195.9 |
| d5_flat_notry | 20 | 0 | 0 | 0 | None | None | 0 | 5.55 | 0 | 193.85 |

| arm | grab positions | interact there | grabs | drops | plays: box on target (seeds) | most on target |
|---|---|---|---|---|---|---|
| random | 214 | 41/214 (19%) | 41 | 20 | 0 (-) | 0 |
| d4_opt | 1250 | 218/1250 (17%) | 218 | 178 | 7 (0, 9, 11, 13, 16, 18, 19) | 3 |
| d5_flat | 2056 | 771/2056 (38%) | 771 | 727 | 14 (0, 1, 2, 5, 6, 8, 9, 10, 11, 12, 13, 14, 15, 17) | 2 |
| d5_lib | 1117 | 193/1117 (17%) | 193 | 149 | 9 (0, 2, 6, 9, 11, 13, 17, 18, 19) | 3 |
| d5_both | 2015 | 753/2015 (37%) | 753 | 709 | 14 (0, 1, 2, 5, 6, 8, 9, 10, 11, 12, 13, 14, 15, 17) | 2 |
| d5_flat_notry | 1942 | 692/1942 (36%) | 692 | 656 | 14 (0, 1, 2, 3, 5, 6, 7, 8, 9, 11, 12, 13, 16, 19) | 2 |

| arm | seeds clearing | seeds clearing level 2 | vs d4_opt: clears (arm / base), seeds up / down, sign p | lost | gained |
|---|---|---|---|---|---|
| d4_opt | 11 | - | - | - | - |
| d5_flat | - | - | 0 / 1, 0 / 1, 1.0 | 11 | - |
| d5_lib | 11 | - | 1 / 1, 0 / 0, 1.0 | - | - |
| d5_both | - | - | 0 / 1, 0 / 1, 1.0 | 11 | - |
| d5_flat_notry | - | - | 0 / 1, 0 / 1, 1.0 | 11 | - |

Re-learning after a restart (actions until the MAP rule set is right on 5 scored steps in a row; censored = the next restart or the end came first; kept / MAP = the rule set that was MAP just before is still a hypothesis / still MAP 10 actions later, restarts where it was not counts-only):

| arm | kind | restarts (per play) | re-learned (median actions) | censored | kept at +10 | MAP at +10 |
|---|---|---|---|---|---|---|
| d4_opt | clear | 1 (0.05) | 33 | 0 | 0/1 | 0/1 |
| d4_opt | reset | 123 (6.15) | 19 | 16 | 90/99 | 85/99 |
| d5_flat | reset | 104 (5.2) | 33 | 27 | 75/79 | 72/79 |
| d5_lib | clear | 1 (0.05) | 33 | 0 | 1/1 | 0/1 |
| d5_lib | reset | 122 (6.1) | 19 | 19 | 85/96 | 75/96 |
| d5_both | reset | 102 (5.1) | 35.0 | 26 | 69/78 | 64/78 |
| d5_flat_notry | reset | 111 (5.55) | 23 | 28 | 84/86 | 78/86 |

| arm | library sets (median) | library rules (median) | sets re-seeded per play |
|---|---|---|---|
| d5_lib | 6.0 | 13.0 | 10.3 |
| d5_both | 6.0 | 13.0 | 5.75 |

| arm | try-once presses | per play | would have pressed anyway (G button < G continuing) | comparison interruptions per play |
|---|---|---|---|---|
| d4_opt | 58 | 2.9 | 2 | 14.35 |
| d5_flat | 52 | 2.6 | 8 | 81.85 |
| d5_lib | 55 | 2.75 | 2 | 12.45 |
| d5_both | 52 | 2.6 | 9 | 80.2 |
| d5_flat_notry | 0 | 0.0 | 0 | 80.75 |

## Locksmith (ls20)

| arm | plays | levels | plays clearing level 1 | plays clearing level 2 | first clear (median action) | level 2 length (median) | game overs | RESETs per play | time-outs | play seconds (median) |
|---|---|---|---|---|---|---|---|---|---|---|
| d4_opt | 20 | 20 | 20 | 0 | 47.0 | None | 0 | 11.95 | 0 | 125.8 |
| d5_flat | 20 | 20 | 20 | 0 | 50.0 | None | 0 | 11.95 | 0 | 124.69999999999999 |
| d5_lib | 20 | 20 | 20 | 0 | 46.5 | None | 0 | 12.35 | 0 | 129.9 |
| d5_both | 20 | 20 | 20 | 0 | 48.0 | None | 0 | 12.3 | 0 | 125.65 |
| d5_flat_notry | 20 | 20 | 20 | 0 | 50.0 | None | 0 | 11.95 | 0 | 125.6 |

| arm | seeds clearing | seeds clearing level 2 | vs d4_opt: clears (arm / base), seeds up / down, sign p | lost | gained |
|---|---|---|---|---|---|
| d4_opt | 0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19 | - | - | - | - |
| d5_flat | 0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19 | - | 20 / 20, 0 / 0, 1.0 | - | - |
| d5_lib | 0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19 | - | 20 / 20, 0 / 0, 1.0 | - | - |
| d5_both | 0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19 | - | 20 / 20, 0 / 0, 1.0 | - | - |
| d5_flat_notry | 0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19 | - | 20 / 20, 0 / 0, 1.0 | - | - |

Re-learning after a restart (actions until the MAP rule set is right on 5 scored steps in a row; censored = the next restart or the end came first; kept / MAP = the rule set that was MAP just before is still a hypothesis / still MAP 10 actions later, restarts where it was not counts-only):

| arm | kind | restarts (per play) | re-learned (median actions) | censored | kept at +10 | MAP at +10 |
|---|---|---|---|---|---|---|
| d4_opt | clear | 20 (1.0) | 14.5 | 2 | 15/20 | 14/20 |
| d4_opt | reset | 239 (11.95) | 5 | 42 | 185/186 | 175/186 |
| d4_opt | life | 220 (11.0) | 5.0 | 176 | 39/45 | 26/45 |
| d5_flat | clear | 20 (1.0) | 11 | 1 | 15/20 | 12/20 |
| d5_flat | reset | 239 (11.95) | 5.0 | 43 | 188/188 | 177/188 |
| d5_flat | life | 219 (10.95) | 5 | 172 | 43/47 | 28/47 |
| d5_lib | clear | 20 (1.0) | 12 | 3 | 16/20 | 11/20 |
| d5_lib | reset | 247 (12.35) | 5.0 | 49 | 187/189 | 179/189 |
| d5_lib | life | 219 (10.95) | 5.0 | 177 | 39/44 | 34/44 |
| d5_both | clear | 20 (1.0) | 15.5 | 4 | 17/20 | 13/20 |
| d5_both | reset | 246 (12.3) | 5.0 | 46 | 190/192 | 187/192 |
| d5_both | life | 219 (10.95) | 5 | 176 | 43/46 | 36/46 |
| d5_flat_notry | clear | 20 (1.0) | 11 | 1 | 15/20 | 12/20 |
| d5_flat_notry | reset | 239 (11.95) | 5.0 | 43 | 188/188 | 177/188 |
| d5_flat_notry | life | 219 (10.95) | 5 | 172 | 43/47 | 28/47 |

| arm | library sets (median) | library rules (median) | sets re-seeded per play |
|---|---|---|---|
| d5_lib | 5.0 | 6.0 | 55.05 |
| d5_both | 5.0 | 6.0 | 53.45 |

| arm | try-once presses | per play | would have pressed anyway (G button < G continuing) | comparison interruptions per play |
|---|---|---|---|---|
| d4_opt | 4 | 0.2 | 0 | 0.0 |
| d5_flat | 0 | 0.0 | 0 | 0.15 |
| d5_lib | 2 | 0.1 | 0 | 0.05 |
| d5_both | 0 | 0.0 | 0 | 0.0 |
| d5_flat_notry | 0 | 0.0 | 0 | 0.15 |

First clears per seed (action of level 1, level 2):

- d4_opt: 0: [48]; 1: [47]; 2: [29]; 3: [47]; 4: [40]; 5: [89]; 6: [47]; 7: [28]; 8: [76]; 9: [38]; 10: [46]; 11: [39]; 12: [76]; 13: [90]; 14: [42]; 15: [50]; 16: [48]; 17: [45]; 18: [76]; 19: [46]
- d5_flat: 0: [48]; 1: [50]; 2: [29]; 3: [42]; 4: [88]; 5: [89]; 6: [47]; 7: [51]; 8: [76]; 9: [56]; 10: [38]; 11: [39]; 12: [76]; 13: [90]; 14: [44]; 15: [50]; 16: [48]; 17: [45]; 18: [76]; 19: [76]
- d5_lib: 0: [50]; 1: [47]; 2: [29]; 3: [47]; 4: [40]; 5: [36]; 6: [47]; 7: [28]; 8: [76]; 9: [38]; 10: [46]; 11: [39]; 12: [76]; 13: [90]; 14: [42]; 15: [50]; 16: [57]; 17: [45]; 18: [76]; 19: [46]
- d5_both: 0: [46]; 1: [50]; 2: [29]; 3: [42]; 4: [88]; 5: [36]; 6: [37]; 7: [51]; 8: [76]; 9: [40]; 10: [38]; 11: [39]; 12: [76]; 13: [90]; 14: [44]; 15: [50]; 16: [57]; 17: [45]; 18: [76]; 19: [76]
- d5_flat_notry: 0: [48]; 1: [50]; 2: [29]; 3: [42]; 4: [88]; 5: [89]; 6: [47]; 7: [51]; 8: [76]; 9: [56]; 10: [38]; 11: [39]; 12: [76]; 13: [90]; 14: [44]; 15: [50]; 16: [48]; 17: [45]; 18: [76]; 19: [76]

## Ghost Twin (g50t)

| arm | plays | levels | plays clearing level 1 | plays clearing level 2 | first clear (median action) | level 2 length (median) | game overs | RESETs per play | time-outs | play seconds (median) |
|---|---|---|---|---|---|---|---|---|---|---|
| d4_opt | 20 | 5 | 5 | 0 | 228 | None | 3 | 11.15 | 0 | 119.35 |
| d5_flat | 20 | 5 | 5 | 0 | 222 | None | 1 | 14.55 | 0 | 125.05000000000001 |
| d5_lib | 20 | 3 | 3 | 0 | 203 | None | 2 | 10.5 | 0 | 129.1 |
| d5_both | 20 | 7 | 7 | 0 | 222 | None | 1 | 14.05 | 0 | 135.4 |
| d5_flat_notry | 20 | 5 | 5 | 0 | 222 | None | 1 | 14.55 | 0 | 118.1 |

| arm | seeds clearing | seeds clearing level 2 | vs d4_opt: clears (arm / base), seeds up / down, sign p | lost | gained |
|---|---|---|---|---|---|
| d4_opt | 4, 5, 7, 17, 19 | - | - | - | - |
| d5_flat | 8, 9, 10, 13, 17 | - | 5 / 5, 4 / 4, 1.0 | 4, 5, 7, 19 | 8, 9, 10, 13 |
| d5_lib | 5, 17, 19 | - | 3 / 5, 0 / 2, 0.5 | 4, 7 | - |
| d5_both | 5, 8, 9, 10, 13, 17, 19 | - | 7 / 5, 4 / 2, 0.6875 | 4, 7 | 8, 9, 10, 13 |
| d5_flat_notry | 8, 9, 10, 13, 17 | - | 5 / 5, 4 / 4, 1.0 | 4, 5, 7, 19 | 8, 9, 10, 13 |

Re-learning after a restart (actions until the MAP rule set is right on 5 scored steps in a row; censored = the next restart or the end came first; kept / MAP = the rule set that was MAP just before is still a hypothesis / still MAP 10 actions later, restarts where it was not counts-only):

| arm | kind | restarts (per play) | re-learned (median actions) | censored | kept at +10 | MAP at +10 |
|---|---|---|---|---|---|---|
| d4_opt | clear | 5 (0.25) | 7 | 0 | 3/4 | 2/4 |
| d4_opt | reset | 223 (11.15) | 5.0 | 53 | 154/162 | 139/162 |
| d5_flat | clear | 5 (0.25) | 9 | 0 | 5/5 | 4/5 |
| d5_flat | reset | 291 (14.55) | 5.0 | 45 | 208/212 | 194/212 |
| d5_lib | clear | 3 (0.15) | 11 | 0 | 2/3 | 1/3 |
| d5_lib | reset | 210 (10.5) | 5 | 41 | 150/165 | 134/165 |
| d5_both | clear | 7 (0.35) | 9 | 0 | 6/7 | 4/7 |
| d5_both | reset | 281 (14.05) | 5.0 | 45 | 179/195 | 166/195 |
| d5_flat_notry | clear | 5 (0.25) | 9 | 0 | 5/5 | 4/5 |
| d5_flat_notry | reset | 291 (14.55) | 5.0 | 45 | 208/212 | 194/212 |

| arm | library sets (median) | library rules (median) | sets re-seeded per play |
|---|---|---|---|
| d5_lib | 6.0 | 10.5 | 21.0 |
| d5_both | 6.0 | 10.0 | 27.85 |

| arm | try-once presses | per play | would have pressed anyway (G button < G continuing) | comparison interruptions per play |
|---|---|---|---|---|
| d4_opt | 2 | 0.1 | 0 | 2.4 |
| d5_flat | 1 | 0.05 | 1 | 18.75 |
| d5_lib | 2 | 0.1 | 0 | 3.1 |
| d5_both | 1 | 0.05 | 1 | 14.45 |
| d5_flat_notry | 0 | 0.0 | 0 | 18.8 |

First clears per seed (action of level 1, level 2):

- d4_opt: 0: -; 1: -; 2: -; 3: -; 4: [403]; 5: [228]; 6: -; 7: [494]; 8: -; 9: -; 10: -; 11: -; 12: -; 13: -; 14: -; 15: -; 16: -; 17: [203]; 18: -; 19: [55]
- d5_flat: 0: -; 1: -; 2: -; 3: -; 4: -; 5: -; 6: -; 7: -; 8: [60]; 9: [467]; 10: [337]; 11: -; 12: -; 13: [222]; 14: -; 15: -; 16: -; 17: [186]; 18: -; 19: -
- d5_lib: 0: -; 1: -; 2: -; 3: -; 4: -; 5: [404]; 6: -; 7: -; 8: -; 9: -; 10: -; 11: -; 12: -; 13: -; 14: -; 15: -; 16: -; 17: [203]; 18: -; 19: [55]
- d5_both: 0: -; 1: -; 2: -; 3: -; 4: -; 5: [249]; 6: -; 7: -; 8: [60]; 9: [371]; 10: [337]; 11: -; 12: -; 13: [222]; 14: -; 15: -; 16: -; 17: [186]; 18: -; 19: [212]
- d5_flat_notry: 0: -; 1: -; 2: -; 3: -; 4: -; 5: -; 6: -; 7: -; 8: [60]; 9: [467]; 10: [337]; 11: -; 12: -; 13: [222]; 14: -; 15: -; 16: -; 17: [186]; 18: -; 19: -

## Judging

| arm | per-seed guard (canary seeds lost vs d4_opt) | canary clears arm / base (40 pairs), seeds up / down, sign p | clears per game arm / base (wa30, ls20, g50t) | Locksmith level one 20/20 | Locksmith speed: first clear median (mean) arm vs base, seeds slower / faster, sign p |
|---|---|---|---|---|---|
| d5_flat | FAIL (ls20: none; g50t: 4, 5, 7, 19) | 25 / 25, 4 / 4, 1.0 | 0/1, 20/20, 5/5 | PASS (20/20) | 50.0 (57.9) vs 47.0 (52.4), 6 / 2, 0.2891 -- SLOWER |
| d5_lib | FAIL (ls20: none; g50t: 4, 7) | 23 / 25, 0 / 2, 0.5 | 1/1, 20/20, 3/5 | PASS (20/20) | 46.5 (50.2) vs 47.0 (52.4), 2 / 1, 1.0 |
| d5_both | FAIL (ls20: none; g50t: 4, 7) | 27 / 25, 4 / 2, 0.6875 | 0/1, 20/20, 7/5 | PASS (20/20) | 48.0 (54.3) vs 47.0 (52.4), 7 / 5, 0.7744 -- SLOWER |
| d5_flat_notry | FAIL (ls20: none; g50t: 4, 5, 7, 19) | 25 / 25, 4 / 4, 1.0 | 0/1, 20/20, 5/5 | PASS (20/20) | 50.0 (57.9) vs 47.0 (52.4), 6 / 2, 0.2891 -- SLOWER |

Reproduction: d4_opt rerun vs debate four's d4_opt rows: 60 plays identical (clears, actions, presses), 0 differ [].
