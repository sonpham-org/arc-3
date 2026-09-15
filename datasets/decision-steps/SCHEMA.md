<!--
Author: Claude Opus 5 (Bubba)
Date: 15-September-2026
PURPOSE: Field-by-field contract for the decision-step corpus record. The machine-readable
form is schema.json; this file explains each field, records the choices made where the plan
was silent, and is what an annotator reads before labelling. README.md covers why the corpus
exists and how to run the validator; it deliberately does not restate this table.
SRP/DRY check: Pass — schema.json is the only executable contract, this is its prose gloss,
README.md is the operator guide. No field definition is duplicated between them.
-->

# Decision-step record — v0 field contract

**Contract of record:** `docs/trace-findings/2026-09-14-decision-step-corpus-v0-plan.md` §6.
Where that plan and this file disagree, the plan wins and this file is the bug.

One JSON object per line. One file per episode segment, at
`datasets/decision-steps/v0/episodes/<game_id>__<guid>__<seg>.jsonl`.

Machine-readable: [`schema.json`](schema.json) (JSON Schema draft 2020-12).
`additionalProperties: false` everywhere — see [Choices](#choices-made-where-the-plan-was-silent).

## The unit

```
frame/image + optional ASCII + structured memory + last action/result
  ->  memory update + next action + expected observation
```

The rationale must be short and **falsifiable**. Every record carries an
`expected_observation` that the following frame either confirms or refutes. A rationale the
next frame cannot contradict is not a valid target — that field is what makes the corpus
teach diagnosis instead of imitation.

## Fields

| field | type | required | notes |
|---|---|---|---|
| `schema_version` | `"0.1"` | yes | Constant. Any change to `schema.json` bumps it. |
| `tier` | `"gold"` \| `"silver"` \| `"negative"` | yes | See [Tiers](#tiers). |
| `game_id` | non-empty string | yes | Opaque id, e.g. `bp35-0a0ad940`. Never a readable title. |
| `source.kind` | non-empty string | yes | Provenance of the trajectory. Only `"human_replay"` is pinned by the plan. |
| `source.recording_guid` | GUID | yes | Lowercase `8-4-4-4-12` hex. |
| `source.row_index` | integer ≥ 0 | yes | **Zero-based** line index into the NDJSON recording. |
| `segment.id` | non-empty string | yes | e.g. `bp35-l7-undo-compare-03`. |
| `segment.boundary_reason` | enum | yes | `camera_shift`, `bridge_edit`, `ghost_construction`, `death`, `reset`, `undo`. |
| `level` | integer ≥ 0 | yes | Level the decision was taken on. |
| `frame_ref.recording_guid` | GUID | yes | See [Frame references](#frame-references). |
| `frame_ref.row_index` | integer ≥ 0 | yes | Zero-based. |
| `frame_ref.field` | non-empty string | yes | Name of the field on that row carrying the frame. |
| `ascii` | non-empty string or `null` | yes (may be `null`) | Optional ASCII rendering. |
| `memory_in.known_mechanics` | array of non-empty strings | yes | May be empty. |
| `memory_in.tested_actions` | array of action names | yes | May be empty. |
| `memory_in.hypotheses` | array of non-empty strings | yes | May be empty. |
| `memory_in.goal` | non-empty string | yes | |
| `memory_in.current_plan` | non-empty string | yes | |
| `last_action.action` | action name | yes | `ACTION1`–`ACTION7`, `RESET`. |
| `last_action.args` | `{row, col}` integers ≥ 0 | no | Present only for cell-addressed actions; both keys required when present. |
| `last_result.board_changed` | boolean | yes | |
| `last_result.level_changed` | boolean | yes | |
| `decision.memory_out` | memory delta | yes | Same five keys as `memory_in`, all optional. A partial update, not a full restatement. |
| `decision.action` | action object | yes | |
| `decision.rationale` | non-empty string | yes | Short and falsifiable. |
| `decision.expected_observation` | non-empty string | yes | The concrete thing the next frame confirms or refutes. |
| `corrected_decision` | same shape as `decision` | **tier `negative` only** | What should have been done. |
| `outcome.observed` | non-empty string | yes | What the next frame actually showed. |
| `outcome.expectation_held` | boolean | yes | Must be `false` on tier `negative`. |
| `action_role` | non-empty string | yes | What the action was for, e.g. `falsification probe`. |
| `action_role_source` | `<path>:<line>[ note]` | yes | Citation into the game source under `docs/static/games/src/`. Checked against source, not guessed from the frame. |
| `rationale_provenance` | `"annotated"` | yes | Replays carry no `<think>` channel. |

**Action names:** `ACTION1` … `ACTION7`, `RESET`. `ACTION7` is included because PR #9
(commit `d5339da`) registered it; before that it was listed in `valid_actions` but rejected by
the engine, which is why recovery behaviour is absent from every trace predating it.

## Tiers

- **`gold`** — observational human/researcher replay, retrospectively annotated from the game
  source and the action stream. Observational, **not** reasoning gold: the rationale and
  `expected_observation` are labels attached by the annotator, not recovered human thought.
- **`silver`** — source-verified synthetic trajectory from a strong teacher. Explicitly out of
  scope for v0; the schema admits it so step 4 does not need a version bump.
- **`negative`** — a failed probe paired with the observed result and a verified
  `corrected_decision`. Requires `outcome.expectation_held: false`.

**Hard rule from the plan §2:** raw failed 300-action agent transcripts are never training
targets. They are mined for `(state, action, result)` triples only, and each mined triple gets
a verified corrective next decision attached.

## Frame references

A frame is referenced by the tuple `(recording_guid, row_index, field)` and resolves to line
`row_index` of `datasets/decision-steps/v0/recordings/<game_id>/<recording_guid>.ndjson`.

**No pixels are ever copied into the corpus.** `validate.py` enforces this twice: structurally,
because `additionalProperties: false` rejects any field not in the table above, and explicitly,
with a scan that flags any nested array anywhere in a record. If a rendered image is needed it
is materialised into a gitignored cache keyed by the same tuple; the JSONL still carries only
the reference.

The recordings are 70–140 MB apiece and are gitignored. The scraper is what gets committed,
not its output.

## Choices made where the plan was silent

Each of these took the narrower reading. All are one-line schema edits if a reviewer disagrees.

1. **`row_index` is zero-based.** §6 says "line `row_index`" and the example (412 against a
   1,030-row recording) does not disambiguate. It is named an *index*, so zero-based. This one
   matters most: getting it wrong silently misaligns every frame lookup in step 3.
2. **`additionalProperties: false` everywhere.** Not stated, but acceptance criterion (i)
   — reject a record with an inline pixel array — only holds if unknown fields are rejected.
3. **`tier` enum is `gold` / `silver` / `negative`.** §2 names the three tiers; only `"gold"`
   is pinned by the §6 example.
4. **`segment.boundary_reason` is a closed enum** drawn from the §5 step 4 boundary list, with
   bp35's bridge edit and g50t's ghost construction as separate values. Only `"undo"` is
   pinned by the example. A new boundary kind needs a schema edit — deliberate, so boundary
   vocabulary cannot drift silently across annotators.
5. **`rationale_provenance` is a closed enum of `"annotated"`.** §2 pins it for human replays
   and nothing else is named. Silver carries `"annotated"` too on the reading that a
   source-verified synthetic rationale is still attached and verified by the annotator.
6. **`last_action` and `last_result` are required and non-null.** The first decision of an
   episode has no prior action; the schema as written cannot express that record. Flagged
   rather than pre-solved.
7. **`action_role_source` is required on every tier**, not just gold. Acceptance only pins it
   for tier 1.
8. **`corrected_decision` is permitted (not required) on gold and silver.** The plan requires
   it on tier 3 and is silent elsewhere.
9. **`source.kind` is a free non-empty string**, not an enum — only `"human_replay"` is named
   anywhere, so an enum here would be invention rather than narrowing.
10. **No cross-field consistency checks.** `frame_ref.recording_guid` is not required to equal
    `source.recording_guid`, and `frame_ref.row_index` is not required to equal
    `source.row_index`, because the plan does not say so. Adding them would broaden scope.
