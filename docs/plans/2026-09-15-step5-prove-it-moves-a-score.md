<!--
Author: Claude Opus 5
Date: 15-September-2026
PURPOSE: What happens after the bridge. Step 4 is now unblocked end to end - a finished record
becomes a training example - and the open question stops being "can we build a corpus" and
becomes "does this corpus move a score". This plan answers that with a pilot before a volume
push, and names the measurement that would detect the effect if it exists.
SRP/DRY check: Pass - the v0 plan (docs/trace-findings/2026-09-14-decision-step-corpus-v0-plan.md)
holds the spec; 2026-09-15-step4-segment-and-label-execution.md holds passes A-E of labelling.
This holds only what comes after a record exists, and does not restate either.
-->

# Step 5 — prove it moves a score, before building volume

**Status:** plan, 15-Sep-2026. The bridge landed in PR #20, so every piece from a human replay
to a training example now exists. Nothing here is started.

> **Amended 16-Sep-2026.** Son's no-teacher decision (`7074b67`, readiness doc §9) removed the
> corpus's role as SFT teacher data: any bootstrap comes from the 27B's own rollouts. **The
> corpus's job is now the recovery eval in §3, plus at most a small weighted mix-in.** Read §2
> and §4 with that in mind: §4's volume push is gated on the eval needing more rows, not on the
> eval showing an effect, and the answer is expected to be no. The two gates added to §3 and
> the RESET call are in
> [`2026-09-16-dr-fable-calls-on-the-step5-review.md`](2026-09-16-dr-fable-calls-on-the-step5-review.md).

---

## 0. The question this plan exists to answer

Everything built so far assumes something nobody has tested: that a modest number of
**recovery** examples, mixed into the existing distillation run, changes how the model behaves
after it is wrong. That assumption is worth more scrutiny than the corpus is, because if it is
false the correct move is to stop annotating, not to annotate faster.

So the order is deliberately **pilot, measure, then scale** — not scale and hope.

---

## 1. The ceiling, measured rather than hoped

Counted on the 13 in-scope recordings on disk, restricted to levels the player actually cleared
(the cull rule in `tools/build_sft.py`): deaths, RESET rows and ACTION7 rows.

| | per run | source |
|---|---|---|
| recovery moments, after the cull | **~10** | 128 across 13 recordings |
| lost to the cull | ~3% | 132 before, 128 after |

The cull barely bites on this sample **because the sample is mostly winning runs** — nearly
every level in them was cleared. It will bite considerably harder on the 48 eligible published
runs that never won, which is exactly where it should.

Extrapolated over eligible material (20 first-party runs + 100 published):

- **~1,200 recovery moments**, and a moment spans 2–3 records (the mistake, the failed fix, the
  correction), so **roughly 2,500–3,500 records** is the honest ceiling for v0.

**State that plainly:** that is a small set next to the synthetic SFT volume. It is the right
size for a weighted mix-in or a targeted eval, and the wrong size to expect a visible move in an
all-25 average on its own. Which leads directly to §3.

One measured asymmetry worth carrying: **bp35 contributes 37 of the 51 undo rows in the whole
sample.** That is not a quirk of one run — it is
[`undo-is-not-a-platform-default`](../trace-findings/2026-09-15-undo-is-not-a-platform-default.md)
showing up in the data. On 19 of 25 live builds RESET is the only recovery verb there is, so a
corpus built across the lineup will be **reset-heavy and undo-light**, and any claim about
"recovery behaviour" that generalises from bp35 alone is generalising from the exception.

---

## 2. The pilot

**Annotate only what is already on disk.** Thirteen recordings, ~128 recovery moments, no new
pulls, no storage question. Passes D and E of the step-4 plan, run small.

1. **Annotate by model, one game at a time.** The bridge fixed what was vague: three judgment
   fields per record, and the mechanical rest is already filled. Feed the annotator the board,
   the dispatch table entry and the measured outcome — never the game source beyond the
   citation, or the record teaches clairvoyance.
2. **Run the falsifiability gate** (pass E) with an agent that did not write the record. It
   deletes rather than softens, and reports the cut count. **A high cut rate here is the most
   valuable result the pilot can produce** — it would mean annotation quality, not volume, is
   the binding constraint, and that is worth knowing before 100 more recordings are pulled.
3. **Build the training file** with `tools/build_sft.py`, pinned to the **real** system prompt
   via `--system-prompt-file`. The built-in default is a stand-in; shipping a fine-tune on it
   would be train/serve skew, which is why every row records which prompt built it.

*Acceptance:* a training file whose every row survived an adversarial pass, and a stated cut
rate.

---

## 3. The measurement — a recovery eval, not the all-25 average

The overall score is too noisy to detect this. `ft09` alone swings the all-25 average by ±1.0
([harness baseline discipline](../../harnesses/)), and a few thousand mixed-in examples will not
clear that on a single run. Reporting "no change in the average" would be a **false negative**,
and it is the most likely way this work gets wrongly abandoned.

So build the metric that is actually sensitive to the thing:

- **Hold out** a slice of the corpus before training — whole games, not random records, so the
  eval measures transfer rather than memorisation.
- **The eval asks one question per held-out record:** given the board, the stated expectation,
  and a tool result that refutes it, does the model change its plan, or does it repeat the
  refuted action? That is a **behavioural** check with a right answer on tape, and it needs no
  scorecard.
- **Report it alongside, never instead of,** an ex-`ft09` run against `baseline-v12`. The
  behavioural number is the sensitive one; the score is the one that matters commercially. Both,
  labelled.

*Acceptance:* the recovery eval separates the fine-tuned model from the incumbent, or it does
not — and either answer is reported at the same volume of words.

Two hard gates, added 16-Sep: (1) the seven held-out games must score above zero on the base
27B, or the split is redrawn on measured agent difficulty; (2) the result is labelled as
transfer within the public 25, with `as66` run and reported as the one out-of-lineup probe.
**Gate 1 met, 16-Sep:** 5 of the 7 held-out games score above zero on the base 27B, so the split
stands. See [`2026-09-16-qwen38-27b-baseline-result.md`](../trace-findings/2026-09-16-qwen38-27b-baseline-result.md).

---

## 4. Only after the pilot: volume

Gated on §3 showing an effect.

- **Pull the remaining eligible recordings** (step-4 pass C), highest recovery-density first.
  ~120 runs; sizes on disk run 1.8 MB to 132 MB, so budget a few GB and pull incrementally,
  checking free space between games. Do not fetch all of them at once.
- **Re-annotate at volume** with whatever the pilot learned about the gate's cut rate.
- **Re-measure.** Same two numbers, same labelling.

---

## 5. Separate track, not part of this: the harness

Worth stating because it is the likelier source of a score move and should not be blocked behind
a corpus.

Our own prompt is **already correct** on the undo question — it tells the model `ACTION7`'s
meaning is not fixed and to probe rather than assume (`inference/agent/prompts.py:68`). No fix
needed. What the new findings add is a *general* rule that costs nothing to state and does not
overfit the public 25:

> a recovery action is not free — it may spend a move, refill a life, or be refused outright.
> Probe its cost before relying on it.

That is a conventions-level claim, not a per-game fact, so it does not walk into the trap the
public set is designed to expose ([public-25-are-not-the-target]). It is **one line in a prompt
and two runs at Kaggle load** — cheaper than everything above it in this document.

**Proposed, not started.** Plan owner's call, per the standing rule that experiments get
brainstormed before anything is launched.

---

## 6. What would make this plan wrong

- **If the gate cuts most of the pilot's records**, the constraint is annotation quality and
  §4's volume push is premature. Fix annotation first.
- **If the recovery eval cannot separate the models even on the training distribution**, the
  record shape is wrong, not the quantity. Revisit the shape.
- **If the ceiling in §1 is overstated** — the extrapolation rests on 13 recordings, most of them
  wins — the honest response is to re-measure after pass C's first ten pulls, not to carry the
  estimate forward unchallenged.
