<!--
Author: Claude Opus 5 (Bubba)
Date: 15-September-2026
PURPOSE: Field-by-field contract for the decision-step corpus record. The machine-readable
form is schema.json; this file explains each field, records the choices made where the plan
was silent, and is what an annotator reads before labelling. Also carries the turn-0
(null last_action/last_result) contract, the evidence that settled row_index as zero-based
against the real 1,030-line bp35 recording, and the frame_ref dotted-path / frame[-1]
convention settled by step 3 against the same file. README.md covers why the corpus
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
| `schema_version` | `"0.1"` | yes | Constant. Any change to `schema.json` **after v0 lands on main** bumps it; edits made while the defining PR is still open are part of defining `0.1`. |
| `tier` | `"gold"` \| `"silver"` \| `"negative"` | yes | See [Tiers](#tiers). |
| `game_id` | non-empty string | yes | Opaque id, e.g. `bp35-0a0ad940`. Never a readable title. |
| `source.kind` | non-empty string | yes | Provenance of the trajectory. Only `"human_replay"` is pinned by the plan. |
| `source.recording_guid` | GUID | yes | Lowercase `8-4-4-4-12` hex. |
| `source.row_index` | integer ≥ 0 | yes | **Zero-based** line index into the NDJSON recording. Settled against a real recording — see [`row_index` is zero-based](#row_index-is-zero-based--settled-against-a-real-recording). |
| `segment.id` | non-empty string | yes | e.g. `bp35-l7-undo-compare-03`. |
| `segment.boundary_reason` | enum | yes | `camera_shift`, `bridge_edit`, `ghost_construction`, `death`, `reset`, `undo`. |
| `level` | integer ≥ 0 | yes | Level the decision was taken on. |
| `frame_ref.recording_guid` | GUID | yes | See [Frame references](#frame-references). |
| `frame_ref.row_index` | integer ≥ 0 | yes | Zero-based. |
| `frame_ref.field` | non-empty string | yes | **Dotted path** to the field on that row carrying the frame — `data.frame` on live API rows. A path with no dot is a top-level key. See [Frame references](#frame-references). |
| `ascii` | non-empty string or `null` | yes (may be `null`) | Optional ASCII rendering. |
| `memory_in.known_mechanics` | array of non-empty strings | yes | May be empty. |
| `memory_in.tested_actions` | array of action names | yes | May be empty. |
| `memory_in.hypotheses` | array of non-empty strings | yes | May be empty. |
| `memory_in.goal` | non-empty string | yes | |
| `memory_in.current_plan` | non-empty string | yes | |
| `last_action` | action object or `null` | yes (may be `null`) | `null` on a turn-0 record. See [Turn 0](#turn-0-the-first-decision-of-an-episode). |
| `last_action.action` | action name | yes when `last_action` is non-null | `ACTION1`–`ACTION7`, `RESET`. |
| `last_action.args` | `{row, col}` integers ≥ 0 | no | Present only for cell-addressed actions; both keys required when present. |
| `last_result` | object or `null` | yes (may be `null`) | `null` on a turn-0 record, and **only** when `last_action` is `null` too. |
| `last_result.board_changed` | boolean | yes when `last_result` is non-null | |
| `last_result.level_changed` | boolean | yes when `last_result` is non-null | |
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

## Turn 0: the first decision of an episode

The first decision of an episode has no predecessor, so `last_action` and `last_result` are
both `null` there. Both keys stay in `required`: the annotator writes `null` **on purpose**, so
a forgotten field is still an error rather than being silently read as "this was turn 0".

**Both-or-neither.** `last_action: null` with a non-null `last_result`, or the reverse, is an
invalid record — it describes a step that both did and did not have a predecessor. `schema.json`
enforces the pair with two `allOf` conditionals, and the validator reports it as
`$.last_result: expected type null, got object` (or the mirror image).

**How nullability is expressed, and why not `anyOf`.** `last_result` is a plain type array,
`["object", "null"]` — the same pattern `ascii` already uses in this document, and the
assertions that only apply to objects (`required`, `properties`, `additionalProperties`) are
no-ops on `null` in draft 2020-12. `last_action` needs one extra step, because its object form
is a `$ref`: `$ref` is evaluated independently of a sibling `type`, so the reference is guarded
by `"if": {"type": "object"}` and applied under `then`. Neither uses `anyOf` or `oneOf`.
`validate.py` hand-rolls the draft 2020-12 subset this schema uses and **refuses to run**
(`SCHEMA ERROR`, exit 2) on any keyword outside its implemented set, which is the guard that
makes a homegrown engine safe. Expressing nullability with keywords the engine already
enforces means that guard was neither extended nor weakened to land turn-0 support — zero new
surface in the evaluator.

**Turn 0 is not the same as "after a `RESET`".** On the real recording, line 0 is the engine's
boot reset (`data.full_reset: true`), which is not a decision anybody took — that record is the
`null`/`null` one. A decision taken after a *player-pressed* `RESET` has a predecessor and
carries `last_action: {"action": "RESET"}` with a real `last_result`.

### What else assumes a prior turn exists

- **`memory_in.tested_actions` does not.** It is an array that may be empty, and an empty array
  is exactly right at turn 0 — nothing has been tested yet. Same for `known_mechanics` and
  `hypotheses`. `goal` and `current_plan` are non-empty strings, which a turn-0 annotator can
  still fill in: the plan the record is about to test is what those fields hold.
- **`segment.boundary_reason` does assume one.** All six values — `camera_shift`,
  `bridge_edit`, `ghost_construction`, `death`, `reset`, `undo` — name a state *change*, so
  none of them describes "this is where the recording starts". The turn-0 fixture uses `reset`
  because line 0 of the recording is literally the boot reset row, which is the nearest honest
  fit. **Not fixed here:** adding an `episode_start` value would invent vocabulary the plan's
  §5 step 4 boundary list does not name. Flagged for the plan owner.
- `outcome` does not. It describes the *next* frame, which exists at turn 0.

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

### `row_index` is zero-based — settled against a real recording

Checked 15-Sep-2026 against the actual bp35 human-win recording, re-pulled from
`https://three.arcprize.org/api/recordings/bp35-0a0ad940/c935ca1b-dfee-4be1-9574-bf4cc80c5b89`
— 138 MB, **1,030 lines**, the same row count
`docs/trace-findings/2026-09-13-bp35-human-win-replay.md` recorded. Not a reading of the plan:

1. **The only authority that resolves a `row_index` is the validator**, and it indexes a
   Python list: `lines[row_index]` at `datasets/decision-steps/validate.py:322`, documented at
   `validate.py:281`. Run against that real file, indices `0` and `1029` both resolve and
   `1030` is rejected as out of range. One-based would make `0` unusable and `1030` the last
   valid index.
2. **Line 0 is a real observation, not a header.** It carries the engine's boot reset —
   `data.action_input.id: "RESET"`, `data.full_reset: true`, `data.levels_completed: 0` — so
   index `0` addresses the episode's first frame.
3. **The rows carry no index of their own.** Every row has exactly two top-level keys,
   `timestamp` and `data`, and nothing under `data` is an index or sequence number. A
   positional index is therefore the only meaning `row_index` can carry.
4. **Nothing else in the repo reads or writes these recordings**, so there is no competing
   convention to conform to: `ndjson` appears in one tracked file (`validate.py`), `row_index`
   only in the plan, this directory and its tests. (`tools/replay_scrape.py` did not exist when
   this was written; it now does, and it writes rows in file order with no header line.) The ambient repo convention is zero-based for programmatic line
   indexing (`ARC3-Inference/inference/utils/viewer_artifacts.py:68`) and 1-based only for
   human-facing line numbers (`validate.py:381`, `enumerate(..., start=1)`). `row_index` is
   programmatic.

**Constraint this puts on step 3.** The scraper writes rows in file order, one JSON object per
line, no header line. If it ever adds a self-describing index field, that field must equal the
zero-based line index.

### `frame_ref.field` is a dotted path, and the frame is the **last** grid

Settled by step 3 (`tools/replay_scrape.py`) against the re-pulled recordings, replacing the
"flagged, not fixed" note that stood here while only the schema existed.

**The path.** A live API row has exactly two top-level keys, `timestamp` and `data`, and the
frame lives at `data.frame`. The plan §6 example's flat `"field": "frame"` therefore resolves
against nothing — the validator reports `has no field 'frame' under 'row' (keys there: data,
timestamp)`. So `field` is read as a **dotted path** into the row:
`"field": "data.frame"`. A single-segment value is just a top-level key, so the flat form
still works and nothing that used it had to change.

This is a resolver change, not a schema change. `field` is still a plain non-empty string in
`schema.json`; the path is interpreted by `validate.py`'s `FrameResolver._walk`. No keyword
was added to the evaluator and the unsupported-keyword audit was not touched — the same
discipline the turn-0 work followed.

**Which grid.** `data.frame` is a **list of 64×64 grids** — the animation the engine emitted
in response to that action, not a single board. On the real bp35 recording the list runs from
0 to 57 grids long, most commonly 7 or 5.

> **The rule: the frame is `frame[-1]`, the last grid in the list.** It is the settled board
> after the action resolved.

That is the repo-wide convention and it is cited, not invented:

- `tufa-arc-agi-framework/src/taaf/game.py:175` — `return Frame(data=self.raw.frame[-1])`,
  which is how the agent framework turns an API response into the board it reasons about.
- `harnesses/baseline-v12/src/tufa-arc-agi-framework/src/taaf/game.py:170` — the vendored copy,
  same line.
- `docs/static/games/src/kd01/kd01.py:515` — a game-source comment stating it outright:
  *"Agents read `frame[-1]`"*.

Measured against the real recording: `frame[0]` is **not** the previous row's settled board —
0 of 1,024 rows match that way — so the list is the post-action animation and only its last
element is a state any consumer should read. There was no need to normalise at scrape time
(plan step-3 decision (c)); the rows stay verbatim.

**An empty list is rejected.** Five rows of the 1,030-row bp35 recording — indices 215, 370,
390, 572 and 807, all `action_input.id: "ACTION7"` with `state: "GAME_OVER"` — carry
`data.frame: []`. On those the path resolves and there is still no grid to select. The
resolver rejects an empty list at the resolved path with its own message, because a
"did the path resolve" check alone would pass them and every downstream consumer would then
fail on `frame[-1]`. Such a row cannot back a decision step.

## Choices made where the plan was silent

Each of these took the narrower reading. All are one-line schema edits if a reviewer disagrees.

1. ~~**`row_index` is zero-based** as a judgment call.~~ **No longer a choice — settled
   against the real 1,030-line recording on 15-Sep-2026.** See
   [`row_index` is zero-based](#row_index-is-zero-based--settled-against-a-real-recording) for
   the evidence and the constraint it puts on step 3.
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
6. ~~**`last_action` and `last_result` are required and non-null**, so a turn-0 record cannot
   be expressed.~~ **Fixed 15-Sep-2026:** both are still required and are now explicitly
   nullable, both-or-neither. See [Turn 0](#turn-0-the-first-decision-of-an-episode).
7. **`action_role_source` is required on every tier**, not just gold. Acceptance only pins it
   for tier 1.
8. **`corrected_decision` is permitted (not required) on gold and silver.** The plan requires
   it on tier 3 and is silent elsewhere.
9. **`source.kind` is a free non-empty string**, not an enum — only `"human_replay"` is named
   anywhere, so an enum here would be invention rather than narrowing.
10. **No cross-field consistency checks.** `frame_ref.recording_guid` is not required to equal
    `source.recording_guid`, and `frame_ref.row_index` is not required to equal
    `source.row_index`, because the plan does not say so. Adding them would broaden scope.
