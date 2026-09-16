<!--
Author: Claude Opus 5
Date: 15-September-2026
PURPOSE: A review request, not a status report. Four things landed or surfaced today that need a
senior engineer's judgment before more work is built on them, ranked by what it costs to be
wrong. Written for someone with no transcript of the day: each item states the evidence, the
decision required, and what I would do, so it can be answered without re-deriving anything.
SRP/DRY check: Pass - CHANGELOG.md records what changed, the step-5 plan holds the forward plan
and 2026-09-15-undo-is-not-a-platform-default.md holds the undo survey. This restates none of
them; it names the open decisions and cites where the evidence lives.
-->

# Review request — four things that need eyes before more is built on them

**For:** Dr. Fable. **Date:** 15-Sep-2026, end of day.
**Context if you want it:** `CHANGELOG.md`, newest section first. You should not need it to
answer these.

Ranked by what it costs to be wrong, not by how interesting they are.

---

## 1. The harness takes recovery out of the model's hands, and we are building a corpus that teaches recovery

**This is the one to read if you read one.**

Three facts, each verified against the tree today rather than taken from a summary:

- `inference/framework/solver.py:171` strips `RESET` out of `_engine_action_names()`, which is
  what builds the `valid_actions` list the model is shown. The model never sees it offered.
- `prompts.py` does not mention `RESET` anywhere. The model is not told it exists.
- `solver.py:345-352` auto-resets on `GAME_OVER` before the next analyzer turn, and
  `tool_agent.py:257` does tell the model this happened — *"the runner will auto-reset before
  the next analyzer turn"*.

So the model is **informed** of death but **never decides** to recover. That is a coherent
design and I am not calling it a bug. The problem is what it does to the work we are funding:

> `datasets/decision-steps/` exists to teach **recovery after falsification**. Its flagship
> record is a human choosing `RESET` after an undo failed. In this harness the model cannot make
> that choice — it is made for it.

And it collides with the day's other finding
([`undo-is-not-a-platform-default.md`](../trace-findings/2026-09-15-undo-is-not-a-platform-default.md)):
`ACTION7` exists on only **6 of 25** live builds, so on the other 19 `RESET` is the only recovery
verb there is — and it is the one we do not expose.

**The decision:** which of these three, and it is a design call, not an implementation detail.

| | what it means | risk |
|---|---|---|
| **a. Leave it.** Retarget the corpus | Teach what the model *can* act on: noticing the falsification earlier, and not re-entering the fatal move after the auto-reset. Drop "choose RESET" as a training target. | Cheapest. Costs us the cleanest records we have. |
| **b. Hand `RESET` back** | Expose it, let the model choose. | Real. `as66`'s agent ran **98 RESETs in 101 actions** when reset was its only verb. An agent that can reset freely may do nothing else. |
| **c. Expose it read-only** | Tell the model RESET exists and that the runner will fire it, without making it selectable. | Middle. Changes nothing mechanically; may improve planning around death. |

**What I would do:** (a) now, and (c) as a cheap prompt experiment, and treat (b) as gated behind
a measured reset-rate guard. But this is exactly the kind of call that should not be made by the
agent that noticed it.

---

## 2. The corpus ceiling is small, and we should decide now whether that is worth it

Measured today across the 13 in-scope recordings on disk, restricted to levels the player
actually cleared: **~10 recovery moments per run.** Extrapolated over all eligible material
(20 first-party + 100 published runs) that is **~1,200 moments, or roughly 2,500–3,500 records.**

That is small next to the synthetic SFT volume. It is the right size for a weighted mix-in or a
targeted eval, and the wrong size to expect a visible move in an all-25 average.

**The decision:** is a set that size worth the annotation spend, given item 1 may force a
retarget anyway? The step-5 plan
([`2026-09-15-step5-prove-it-moves-a-score.md`](2026-09-15-step5-prove-it-moves-a-score.md))
proposes a pilot on the recordings already on disk before any volume push, precisely so this
question gets answered cheaply. **I would not pull the other ~110 recordings until item 1 is
settled** — a retarget changes which moments are worth annotating.

Caveat on the estimate, stated rather than buried: it rests on 13 recordings, **most of them
wins**, so the cull barely bit (132 → 128). It will bite considerably harder on the 48 eligible
published runs that never won. Re-measure after the first ten pulls.

---

## 3. The measurement plan — please check this before we run it, not after

The all-25 average cannot detect a few thousand mixed-in examples. `ft09` alone swings it by
±1.0. If we measure this work on the overall score we will likely see nothing and wrongly
conclude it failed — **a false negative is the most probable bad outcome of the whole
programme**, and it is silent.

Proposed instead: hold out **whole games**, then ask the model one behavioural question per
held-out record — given a refuted expectation, does it change plan or repeat the refuted action?
The right answer is on tape; no scorecard needed. Reported *alongside* an ex-`ft09` run against
`baseline-v12`, never instead of it.

**The decision:** is that eval measuring the right thing, and is holding out whole games (rather
than random records) the correct guard against memorisation? I believe both, but this is the
number the programme will be judged on and it should not be designed by one agent unreviewed.

---

## 4. Two agents are editing one corpus in one checkout, and it has already cost us

Concrete, today: a schema change to `0.2` on one branch and six new records at `0.1` on another
landed within an hour of each other. Nothing was lost — the rebase caught it and the records were
migrated with **measured** values, not defaults — but it was caught by a test, not by a process.
Main moved four times during one session.

**The decision:** is a convention worth imposing? My suggestion is narrow: **schema and
validator changes go through a PR that names the migration, and never direct to `main`.** Records
and findings can keep landing directly — those are additive and have been fine. I have not
imposed this; it would constrain another agent's work and that is not mine to do.

---

## What is already settled — please don't spend time re-deriving these

- **`schema_version` is `0.2`.** `last_result.run_ended` was added so a record can say an action
  ended the run. Enum additions do not bump; field changes do. The `0.2`-reserved-for-
  `boundary_reason` note from `0.1` is **released** and recorded as such.
- **The cull is per level, not per run.** A stumble on a level later cleared is a recovery that
  worked; a stumble on the level the player died on is flailing. Same rule
  `extract_sft.py` already applies. `--keep-unsolved` exists and is off.
- **`args` row/col** is no longer an open assumption — the game source consumes `x` and `y` as
  separate keys, so `row=y, col=x` is the only reading the source supports.
- **Our prompt is already correct on undo** (`prompts.py:68` tells the model `ACTION7`'s meaning
  is not fixed and to probe). There is no harness fix to make there. The Retrodict comparison in
  the undo survey is about *their* harness, not ours.
- **146 tests green** on `main` as of `a83875f6a`. Every new guard this week was poison-checked.
