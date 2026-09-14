<!--
Author: Claude Opus 5 (Bubba)
Date: 14-September-2026
PURPOSE: Executable plan for the v0 decision-step corpus — the data-spec prototype that has
to exist before any ARC-3 fine-tuning run. Written for a fresh session with no transcript:
carries Sherlock's decision-step spec and tier definitions, the segment/label rules, the
JSONL schema with frame references, the replay-scrape step, and per-step acceptance criteria.
Records verified repo state (ACTION7 unrepaired on main; the two human recordings are no
longer on disk) so the next session does not have to re-derive it.
SRP/DRY check: Pass — 2026-09-14-training-pipeline-proposal-and-ordering.md holds the
training-pipeline proposal and the arm-I-before-SFT ordering call; this holds only the v0
data spec and its build order. 2026-09-14-action7-is-unexecutable.md holds the harness
defect; this cites it and does not restate the evidence. Both of those live on the open
PR #7 branch docs/bp35-trace-findings, not yet on main.
-->

# The v0 decision-step corpus — plan, not a training run

**Status:** plan of record, approved by the Boss 14-Sep-2026, to be executed in a separate
session. **Nothing here trains a model.** The deliverable is a schema, a scraper, and a small
labelled corpus that proves the schema survives contact with real replays.

The spec below came from Sherlock in `#arc-3` on 14-Sep-2026 and is carried verbatim in
substance. The build order and the two corrections in §7 are Bubba's.

---

## 1. The unit of training is a decision step

Not a whole transcript, and not a bare winning action sequence.

```
frame/image + optional ASCII + structured memory + last action/result
  ->  memory update + next action + expected observation
```

The visible rationale stays short and falsifiable. The target shape is:

> "click here; if the bridge extends / camera rises, continue; otherwise undo."

A rationale that cannot be contradicted by the next frame is not a valid target. Every
example carries an `expected_observation` that the following frame either confirms or
refutes — that field is what makes the corpus teach diagnosis instead of imitation.

## 2. Dataset tiers

**Tier 1 — Gold (observational).** Successful human/researcher replays, retrospectively
annotated from the game source and the action stream.

> **Correction of record, Sherlock 14-Sep:** human replay rows are *observational* gold, not
> *reasoning* gold. There is no `<think>` channel in a replay. The rationale and the
> `expected_observation` are attached retrospectively, from source, by the annotator — they
> are labels, not recovered human thought, and must be marked as such
> (`rationale_provenance: "annotated"`).

**Tier 2 — Silver.** Source-verified synthetic trajectories from a strong teacher, covering
camera shifts, indirect controls, resets, and undo branches. Not built yet; the authored
games live in `~/GitHub/autoresearch-arena/arc3games/` and are environments, not trajectories
— they still need a competent player wired to them. Out of scope for v0.

**Tier 3 — Negative / counterfactual.** Failed probes paired with the observed result and the
**corrected next decision**. This tier is not optional: winning traces alone teach imitation,
not diagnosis.

> **Hard rule.** Raw failed 300-action agent transcripts are **never training targets**. They
> are mined for `(state, action, result)` triples only; each mined triple then gets a
> verified corrective next decision attached. Training on them as-is teaches confident
> failure — and per `2026-09-13-job1-control-baseline.md`, lf52 scoring 1.818 on four
> straight passes with zero variance is precisely the behaviour we would be distilling.

## 3. Split and metrics

- **Train** on synthetic games and mechanic compositions.
- **Evaluate** on held-out games and held-out mechanic compositions.
- Metrics, in this priority order:
  1. level depth
  2. valid-action rate
  3. recovery after falsification
  4. action efficiency

Metric 3 is the one this whole corpus exists to move, and it is the one that is structurally
absent today — see §4.

## 4. Verified repo state — read this before planning around it

Both facts below were checked on `main` at 14-Sep-2026. Do not assume either has changed.

**(a) ACTION7 is still unrepaired on `main`.**
`ARC3-Inference/inference/agent/action_names.py` maps ACTION1–6 and RESET. **ACTION7 is
absent**, on `main` and in the vendored copy at `harnesses/baseline-v12/src/`. The
consequence, established in `2026-09-14-action7-is-unexecutable.md`: ACTION7 is listed in
`valid_actions` on every step but `to_engine_action()` returns `None`, so the call is
rejected with `Unknown action at index 1: 'ACTION7'`.

The fix exists only as `harnesses/action7-anim/patch/action7-anim.diff` and inside the job-10
Kaggle bundle. **It has not landed on `main`.** The diff also carries an unrelated
always-visible animation-metadata change; the repair step below takes the ACTION7 hunks only.

**This blocks corpus extraction, and it does not wait on job 10.** Job 10 measures whether
the fix moves our *scores*; that is a separate question from whether the corpus can contain
recovery behaviour at all. With ACTION7 dead, undo/recovery is absent from both the model's
experience and the labels, and metric 3 has nothing to measure. The bp35 human pressed undo
35 times from level 1; our arm-C passes pressed it zero times in 166 actions.

**(b) The two human recordings are no longer on disk.** A filesystem search for `c935ca1b`
and `4f0689d0` returns nothing. The 138 MB and 73.6 MB NDJSON files analysed in
`2026-09-13-bp35-human-win-replay.md` and `2026-09-13-g50t-human-win-vs-our-zero.md` are
gone. **Step 3 must re-pull even the two known guids**; it cannot assume local copies.

**(c) No scrape tooling exists in-repo.** The two endpoint path forms appear only as prose in
those two docs. Nothing executable was committed. Step 3 writes it.

## 5. Build order

Run in this order. Each step has an acceptance criterion; do not advance on a step that has
not met it.

### Step 1 — Land the ACTION7 round-trip on `main`

Apply the `action_names.py` hunk (`"ACTION7": "ACTION7"`) and the single ACTION7 prompt line
from `harnesses/action7-anim/patch/action7-anim.diff` to `ARC3-Inference/`. **Take nothing
from the animation half of the patch** — that is a second variable and it belongs to arm H's
measurement, not to the harness repair.

*Acceptance:* `to_engine_action("ACTION7") == "ACTION7"`, and a single bp35 step that issues
`action(['ACTION7'])` returns a frame instead of `Unknown action at index 1`.

*Guardrail:* this is a source change to Son's repo — own branch, own PR, nothing else in the
diff. Do not touch arm H's bundle or job 10.

### Step 2 — Write the JSONL schema

One file, `datasets/decision-steps/SCHEMA.md`, plus a validator at
`datasets/decision-steps/validate.py`. Schema in §6. Frames are **referenced, never
duplicated as pixels**.

*Acceptance:* `validate.py` accepts a hand-written example of each tier and rejects (i) a
record with an inline pixel array, (ii) a record whose `frame_ref` does not resolve, (iii) a
tier-3 record with no `corrected_decision`.

### Step 3 — Write the replay scraper and re-pull

`tools/replay_scrape.py`, writing to `datasets/decision-steps/v0/recordings/`.

Endpoints — only the **path forms** are recorded in our docs; the base host is inferred from
the public replay URL `https://arcprize.org/replay/<guid>` and **must be verified by the
session, not asserted**:

- `/api/sessions/<guid>`
- `/api/recordings/<game_id>/<guid>`

Known-good pairs to re-pull first:

| game | game_id | replay guid |
|---|---|---|
| bp35 | `bp35-0a0ad940` | `c935ca1b-dfee-4be1-9574-bf4cc80c5b89` |
| g50t | `g50t-5849a774` | `4f0689d0-7d06-4be7-91ac-31cb9a800b85` |

Then enumerate further published guids. **This is the step that actually matters** — see §7.

*Acceptance:* both known recordings re-pulled, row counts matching the recorded 1,030 (bp35)
and 534 (g50t); plus a written count of how many *additional* published guids were found,
even if that number is zero. A zero is a finding, not a failure — record it and say so.

### Step 4 — Segment and label the v0 corpus

Segment at meaningful state changes, not at fixed strides. Boundaries:

- camera shift
- bridge edit (bp35) / ghost construction (g50t)
- death or reset
- undo

Attach source-verified labels for **the action's role** — what the action was for, checked
against the game source under `docs/static/games/src/`, not guessed from the frame.

Target v0 volume:

- **bp35:** 10–20 episodes covering bridge construction, camera shift, undo comparison, reset.
- **g50t:** 10–20 episodes covering ghost construction and retry.
- **A few negative→corrected pairs from each**, mined from our own arm transcripts per the
  §2 hard rule.

*Acceptance:* every record passes `validate.py`; every tier-1 record's `action_role` cites a
specific line or rule in the game source; every tier-3 record pairs an observed failure with
a corrected next decision.

## 6. The JSONL schema

One record per decision step. One file per episode, under
`datasets/decision-steps/v0/episodes/<game_id>__<guid>__<seg>.jsonl`.

```json
{
  "schema_version": "0.1",
  "tier": "gold",
  "game_id": "bp35-0a0ad940",
  "source": {
    "kind": "human_replay",
    "recording_guid": "c935ca1b-dfee-4be1-9574-bf4cc80c5b89",
    "row_index": 412
  },
  "segment": {"id": "bp35-l7-undo-compare-03", "boundary_reason": "undo"},
  "level": 7,
  "frame_ref": {
    "recording_guid": "c935ca1b-dfee-4be1-9574-bf4cc80c5b89",
    "row_index": 412,
    "field": "frame"
  },
  "ascii": null,
  "memory_in": {
    "known_mechanics": ["ACTION6 places a bridge segment at the clicked cell"],
    "tested_actions": ["ACTION3", "ACTION4", "ACTION6"],
    "hypotheses": ["ACTION7 reverts the last bridge segment"],
    "goal": "reach the right platform",
    "current_plan": "extend the bridge one segment, verify, repeat"
  },
  "last_action": {"action": "ACTION6", "args": {"row": 12, "col": 31}},
  "last_result": {"board_changed": true, "level_changed": false},
  "decision": {
    "memory_out": {"hypotheses": ["ACTION7 reverts the last bridge segment"]},
    "action": {"action": "ACTION7"},
    "rationale": "undo the last segment; if the bridge shortens by one, ACTION7 is undo; otherwise it is not",
    "expected_observation": "bridge length decreases by exactly one segment"
  },
  "outcome": {"observed": "bridge shortened by one segment", "expectation_held": true},
  "action_role": "falsification probe",
  "action_role_source": "docs/static/games/src/bp35-0a0ad940/bp35.py:4524 GameAction.ACTION7",
  "rationale_provenance": "annotated"
}
```

**Frame-reference scheme — decided, do not re-invent.** A frame is referenced by the tuple
`(recording_guid, row_index, field)`. Frames resolve out of the NDJSON recording at
`datasets/decision-steps/v0/recordings/<game_id>/<guid>.ndjson`, line `row_index`. No pixels
are copied into the corpus. If a rendered image is ever needed, it is materialised into a
gitignored cache keyed by that same tuple — the JSONL still carries only the reference. The
recordings themselves are 70–140 MB apiece and are gitignored; the scraper is the thing that
gets committed, not its output.

**Tier-3 records** add `corrected_decision`, same object shape as `decision`, and set
`outcome.expectation_held: false`. `decision` holds what was actually done and failed;
`corrected_decision` holds what should have been done. Both are required.

## 7. Two corrections that are part of this plan

**(a) "10–20 episodes" out of bp35 means 10–20 correlated segments of one human session, not
10–20 independent runs.** We own exactly one bp35 win and one g50t win. Segments from a single
player share that player's habits, priors, and mistakes. That is fine for a **schema
shakedown** — which is all v0 claims to be — and it is not fine as a corpus. **Step zero of
any real corpus is scraping more published replay guids, not slicing the two we have
thinner.** Stated to Sherlock and the Boss on 14-Sep; uncontested.

**(b) ACTION7 before extraction, not after.** Per §4(a). Extract first and both the
experiences and the labels ship with the recovery branch missing, and metric 3 has nothing to
measure.

## 8. Relationship to the training-pipeline proposal

`2026-09-14-training-pipeline-proposal-and-ordering.md` holds the Qwen3-27B pipeline proposal
and the ordering call that **arm I (structured memory across compaction) runs before any SFT
spend**. Nothing here changes that. This document is the narrowed v0 data-spec prototype the
Boss asked for on 14-Sep — a schema and a small labelled corpus, deliberately upstream of the
training question. If arm I lands and moves nothing, this corpus still has value as the spec;
if arm I moves level clears, this corpus is what the SFT is seeded from.

## 9. Guardrails for the executing session

- **No Kaggle jobs launched.** Experiments are winding down by the Boss's instruction.
- **Cron untouched.**
- **Job 10 (arm H) left alone** — do not cancel it, do not re-queue it, do not read the
  ACTION7 repair as a reason to stop it.
- Step 1 and steps 2–4 are **two separate PRs**: the harness repair is a source change to
  Son's repo and does not belong in a docs/dataset diff.
- Report counts as found. If only two replay guids exist publicly, that is the answer and it
  gets written down plainly.
