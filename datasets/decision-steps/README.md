<!--
Author: Claude Opus 5 (Bubba)
Date: 15-September-2026
PURPOSE: Cold-start operator guide for the decision-step corpus tooling — what the record is,
why it exists, how to run the validator, what the next pipeline step is, and the verified
replay-API facts step 3 inherits. Written so a
session with no transcript can act without asking anyone. SCHEMA.md holds the field-by-field
contract and is not restated here.
SRP/DRY check: Pass — schema.json is the executable contract, SCHEMA.md is its field gloss,
this is the operator guide. No field table is duplicated here.
-->

# Decision-step corpus — v0

## What this is

The **training target** for ARC-3 fine-tuning. Not a whole transcript, and not a bare winning
action sequence — one record per **decision point**:

```
frame/image + optional ASCII + structured memory + last action/result
  ->  memory update + next action + expected observation
```

Every record carries an `expected_observation` that the next frame either confirms or refutes.
That field is the whole point: a corpus of winning moves teaches imitation, and a corpus of
falsifiable predictions paired with what actually happened teaches **diagnosis**. The metric
this exists to move is *recovery after falsification*, which is structurally absent from every
trace we have today.

**Nothing here trains a model.** This directory is a schema, a validator, and fixtures. The
deliverable is a data spec that survives contact with real replays.

Plan of record, approved by the Boss 14-Sep-2026:
[`docs/trace-findings/2026-09-14-decision-step-corpus-v0-plan.md`](../../docs/trace-findings/2026-09-14-decision-step-corpus-v0-plan.md).

## Layout

```
datasets/decision-steps/
├── schema.json        JSON Schema draft 2020-12 — the machine-readable contract
├── SCHEMA.md          field-by-field gloss, tier definitions, choices made
├── validate.py        the validator CLI
├── README.md          this file
├── fixtures/
│   ├── valid/             one file per tier plus a turn-0 record, all must pass
│   ├── invalid/           one file per failure mode, each must be rejected
│   ├── frame-resolution/  records exercising frame_ref lookup
│   └── recordings/        a 4-row stand-in NDJSON so lookup has something to resolve
└── v0/                (not committed — created by step 3)
    ├── recordings/<game_id>/<guid>.ndjson    70–140 MB apiece, gitignored
    └── episodes/<game_id>__<guid>__<seg>.jsonl
```

## Running the validator

Requires **Python 3.13** (`/opt/homebrew/bin/python3.13` on the Mac Mini). Standard library
only — no `pip install`, no venv, no `jsonschema`. The system `python3` is 3.9 and will fail.

From the repo root:

```bash
# validate a directory of episodes (searched recursively for *.jsonl)
python3.13 datasets/decision-steps/validate.py datasets/decision-steps/v0/episodes

# or single files
python3.13 datasets/decision-steps/validate.py path/to/one.jsonl path/to/another.jsonl

# prove it works on the fixtures
python3.13 datasets/decision-steps/validate.py datasets/decision-steps/fixtures/valid
python3.13 datasets/decision-steps/validate.py datasets/decision-steps/fixtures/invalid   # exits 1
```

Exit codes: `0` all records valid · `1` at least one record rejected · `2` usage or schema
error. Bad rows are **rejected, never coerced** — one bad row fails the run.

Output is one line per failing field, prefixed with file, 1-based line number, and a path into
the record:

```
fixtures/invalid/empty-rationale.jsonl:1: $.decision.rationale: must not be an empty string
```

### Frame-reference resolution

`frame_ref` points into the NDJSON recordings, which are gitignored and large. Resolution is
therefore **opt-in on the recordings directory existing** (default
`datasets/decision-steps/v0/recordings`):

```bash
python3.13 datasets/decision-steps/validate.py <target> --recordings-dir <dir>
python3.13 datasets/decision-steps/validate.py <target> --require-frame-resolution
```

Every run ends with a summary line stating which mode it ran in:

```
4 file(s), 5 record(s), 0 error(s) | FRAME-REF RESOLUTION: SKIPPED (no recordings at ...)
```

**Read that line.** A green run with `SKIPPED` has checked the record's shape but has not
confirmed a single frame exists. Use `--require-frame-resolution` in any pipeline step that
must not pass on unresolved references. (This repo has been burned by exactly this shape of
false green before — see `AGENTS.md` on `probe_one.py` under Python 3.9.)

## Running the tests

```bash
cd <repo root>
python3.13 -m unittest scripts.test_decision_step_validator -v
```

Matches the existing `scripts/test_*.py` convention. 22 tests, stdlib only.

## Why the validator is hand-rolled

`schema.json` is the single source of truth; `validate.py` is a generic evaluator over the
draft 2020-12 keyword subset that document actually uses. It is not a reimplementation of the
schema's rules in Python — there is one contract, not two that can drift.

The evaluator **audits the whole schema document at load time, including `$defs`, and refuses
to run if it finds a keyword it does not enforce.** Adding, say, `uniqueItems` to `schema.json`
produces `SCHEMA ERROR` and exit 2 rather than a quietly weaker validation pass. That guard is
what makes a homegrown engine safe; without it, the dependency-free choice would be a liability.

That guard also constrains how the schema is allowed to grow. Turn-0 records — the first
decision of an episode, where `last_action` and `last_result` are both `null` — are expressed
with a `type` array rather than `anyOf`, precisely so the evaluator needed no new keyword and
the audit was neither extended nor relaxed to land them. See
[`SCHEMA.md`](SCHEMA.md#turn-0-the-first-decision-of-an-episode).

## Where this sits in the pipeline

Per plan §5:

1. ~~Land the ACTION7 round-trip on `main`~~ — **done**, PR #9, commit `d5339da`.
2. **Write the schema and validator** — this directory.
3. **Next: write `tools/replay_scrape.py`** and re-pull the recordings into
   `datasets/decision-steps/v0/recordings/`. Both known-good replays must come back at their
   recorded row counts — bp35 `c935ca1b-dfee-4be1-9574-bf4cc80c5b89` at 1,030 rows, g50t
   `4f0689d0-7d06-4be7-91ac-31cb9a800b85` at 534 — and the number of *additional* published
   guids found gets written down even if it is zero. A zero is a finding, not a failure.
   The host was verified by observation on 15-Sep-2026 while settling `row_index`:
   `https://three.arcprize.org/api/recordings/<game_id>/<guid>` returns the bp35 recording,
   138 MB and 1,030 lines. Two things the scraper must handle, found the same way and written
   up in [`SCHEMA.md`](SCHEMA.md#row_index-is-zero-based--settled-against-a-real-recording):
   the API ignores `Range` and serves the whole file, and each row nests the frame at
   `data.frame` as a *list* of grids, not at `frame`.
4. **Then: segment and label.** Boundaries are meaningful state changes, not fixed strides.
   Every record must pass `validate.py`; every gold record's `action_role` must cite a real
   line in the game source under `docs/static/games/src/`; every negative record must pair an
   observed failure with a corrected next decision.

**Known limit, stated plainly:** we own exactly one bp35 win and one g50t win. "10–20 episodes"
means 10–20 correlated segments of a single human session, which is fine for a schema shakedown
and is **not** a corpus. Step zero of any real corpus is scraping more published replay guids,
not slicing the two we have thinner.
