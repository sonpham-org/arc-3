<!--
Author: Claude Opus 5 (Bubba)
Date: 13-September-2026
PURPOSE: Map the 13-Sep ARC-3 meeting summary (posted by the Boss in #arc-3) onto the
experiment queue already running on this branch. Records which meeting findings are already
confirmed by evidence on PR #7, which are new and unqueued, and what each would cost.
SRP/DRY check: Pass — no prior doc reconciles the meeting against the arm queue.
-->

# Meeting summary vs. the experiment queue

Source: meeting summary posted by the Boss, 13-Sep-2026, #arc-3. Reproduced verbatim in
provenance (`project:arc3`). This doc is the reconciliation, not a re-statement.

## Already confirmed by runs on this branch

**"System prompt hard-codes biases (objects, tiles, observe/reason/act) — likely
overspecified for Flash Next"** and **"Trim legacy Tufa system-prompt biases (HUD warnings,
object/tile assumptions)"**.

This is arm B, and it has a number. Job 1 (control) scored **0.864** overall on the bottom
seven; job 2 (pure deletion — two HUD paragraphs, the 64×64 assertion, the word "puzzle",
nothing added) scored **1.535** on the pre-registered window, **+60%**. g50t went from four
hard zeros to two scoring passes; lf52 broke its 1.818 ceiling for the first time.

Caveat unchanged: n=3, most per-game deltas are one lucky pass wide. Job 3 (null check on
cd82/lp85/sb26 plus four mid games) is on the card now and is what decides whether the effect
is real or a rising tide. **The meeting's recommendation and our first result agree; the
result is not yet load-bearing.**

**"Agent commits long action chains on weak hypotheses, no good unstuck mechanism."**
Confirmed across four independent traces:
- sc25: 354 clicks, **178 outside the nine legal click points** the game enumerates in
  `_get_valid_actions()`; one batch fired the same click 14×.
- lf52: level 1 costs 11–25 actions, then **339 actions on level 2** without clearing it —
  more than a human spends beating all ten levels (641 total).
- g50t: 279 actions on level 1, 295 on level 2, cancelled.
- r11l: 252 of 363 runs die on level 1.

**"Jagged intelligence, strong but overconfident."** The distribution is bimodal everywhere,
not a gradient. astra-grid2: three games ~100, the rest near zero, nothing between. Where the
hypothesis is right, execution is not the bottleneck — our r11l levels 1–4 ran 11/18/18/15
actions against human baselines of 22/33/51/26.

## New in the meeting, not yet queued

**1. ASCII force-feed may be net harmful early (Mark's ablation).**
Not tested here and not something our trace work touched. This is a separate arm from B: B
deletes *claims* from the prompt, this deletes a *channel*. Clean one-variable arm, same
seven lanes, 2.2h. Son's "ASCII bug should probably be cleaned up a bit" is the adjacent —
and cheaper — version: fix the representation before ablating it, so the ablation isn't
measuring a bug.

**2. Compaction drops learned world-model facts; re-inject via user prompt (Son).**
Called out in-meeting with a concrete case — *orange is the AI in wa30* — learned and then
lost. Son's phrasing in channel: **"User Input maintaining the current crucial hypothesis."**
This is the first proposal on the table that is *harness-side*, not prompt-text-side, and it
is aimed squarely at the failure our traces keep showing: a correct read appearing and then
being abandoned. Direct precedents in our data:
- cn04: step 15 says *"the weld broke, meaning no permanent weld"* — correct — and step 21
  reverts to *"the level completes when ALL objects are welded."*
- sc25: turn 21 writes *"the tip is now at cols 17-18, adjacent to the handle"*, the exact
  square a winning run cleared from one LEFT press later. It went back to typing codes.
- g50t: names ACTION5's effect only at step 73 of 109, after teleport / motion blur /
  second player.

A persisted-hypothesis slot is the intervention with the most direct trace evidence behind
it of anything currently proposed. **Recommend it as arm D, ahead of the ASCII ablation.**

**3. Force next-frame predictions, abort the chain on mismatch.**
Strongest structural idea in the meeting and the only one that attacks the long-chain failure
directly rather than hoping a better hypothesis prevents it. Costs turns, so it trades against
the ~108k output-token ceiling. Not cheap to build; no arm proposed yet.

**4. Fine-tuning a small-active MOE (Son; Unsloth or vLLM+PyTorch, RL on level-completion,
~$200).** Out of scope for the current 30h Kaggle GPU budget, which is an inference quota.
The stated bottleneck — synthetic data, 25 public games risks overfit — is exactly what
`autoresearch-arena/arc3games/LATENT_MECHANICS_IN_THE_PUBLIC_25.md` was written for: eight
mechanics the public 25 exercise, six of them in our bottom seven, plus five uncombined pairs
with no instance anywhere in the set. The synthetic-game track and the fine-tuning track are
the same track.

## Where arm C sits after this

Arm C (the mechanics-possibility lines — the view may be a moving window, what you control
may change, a solved thing may come un-solved) is built and stacked on B, unlaunched. The
meeting did not raise it and did not contradict it. It remains queued behind job 3.

Revised order, pending the Boss and Son:

| Arm | What | Source | Status |
|---|---|---|---|
| A | control, unmodified | — | done, 0.864 |
| B | pure deletion | our traces + meeting | done, 1.535 |
| — | null check | pre-registration | **running** |
| C | mechanics-possibility, stacked on B | our traces | built, unlaunched |
| D | persisted hypothesis across compaction | meeting (Son) | proposed here |
| E | ASCII ablation, early turns | meeting (Mark) | proposed, gate on ASCII fix |

Budget: 9,126s + job 2 + job 3 spent of 30h; refresh Thu 18-Sep 8pm ET. Arms C, D and E are
2.2h each, so all three fit inside the remaining quota with reserve.
