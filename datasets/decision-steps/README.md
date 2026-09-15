<!--
Author: Claude Opus 5 (Bubba)
Date: 15-September-2026
PURPOSE: Cold-start operator guide for the decision-step corpus tooling — what the record is,
why it exists, how to run the validator, what the next pipeline step is, and the verified
replay-API facts — both endpoints, the not-resumable download, the 250 published guids
found by step 3, and why the first-party replays are a second manifest rather than extra rows
in the first. Written so a
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
├── current-builds.json       the 25 live ARC-3 builds; a run is eligible only if its build is current
├── published-replays.json    250 blog-linked human replay guids + their run metadata
├── first-party-replays.json  the 23 replays the Boss played on his own account
├── fixtures/
│   ├── valid/             one file per tier plus a turn-0 record, all must pass
│   ├── invalid/           one file per failure mode, each must be rejected
│   ├── frame-resolution/  records exercising frame_ref lookup, flat and dotted
│   └── recordings/        stand-in NDJSONs so lookup has something to resolve: a 4-row
│                          flat one, and a 3-row one mirroring the live API row shape
└── v0/
    ├── recordings/<game_id>/<guid>.ndjson    70–140 MB apiece, gitignored, made by step 3
    └── episodes/<game_id>__<guid>__<seg>.jsonl   committed — the corpus itself
```

The scraper that fills `v0/recordings/` lives at [`tools/replay_scrape.py`](../../tools/replay_scrape.py).

## Running the validator

Requires **Python 3.13** (`/opt/homebrew/bin/python3.13` on the Mac Mini). Standard library
only — no `pip install`, no venv, no `jsonschema`. The system `python3` is 3.9 and will fail.

From the repo root:

```bash
# validate a directory of episodes (searched recursively for *.jsonl)
python3.13 datasets/decision-steps/validate.py datasets/decision-steps/v0/episodes

# or single files
python3.13 datasets/decision-steps/validate.py path/to/one.jsonl path/to/another.jsonl

# prove it works on the fixtures — shape only, frame resolution explicitly off
python3.13 datasets/decision-steps/validate.py datasets/decision-steps/fixtures/valid \
  --recordings-dir /nonexistent
python3.13 datasets/decision-steps/validate.py datasets/decision-steps/fixtures/invalid \
  --recordings-dir /nonexistent   # exits 1
```

**Why `--recordings-dir /nonexistent` on a fixture run.** Once step 3 has pulled the
recordings, the default recordings directory exists and resolution switches itself on. The
three gold fixtures cite the two real human-replay guids and do resolve against the re-pulled
files — that is asserted by `RealRecordingTests`. The silver and negative fixtures cite an
`agent_transcript` and a `synthetic_rollout` guid that have no recording *by design*, so a
fixture run with resolution on reports two `recording not found` errors. Pointing a shape-only
run at a directory that does not exist says which of the two things you are checking, instead
of letting the answer depend on whether the scraper has run on that machine.

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
5 file(s), 6 record(s), 0 error(s) | FRAME-REF RESOLUTION: SKIPPED (no recordings at ...)
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

Matches the existing `scripts/test_*.py` convention. 34 tests, stdlib only. Six of them
cover the two replay manifests (see [Two replay manifests](#two-replay-manifests-and-why-they-are-two));
those read the committed JSON only and never call the API, so the suite does not go red when
`three.arcprize.org` does.

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
3. ~~Write `tools/replay_scrape.py` and re-pull the recordings~~ — **done.** See
   [The replay scraper](#the-replay-scraper) below. Both known-good replays came back at
   their recorded counts (1,030 and 534, observed), the frame convention was settled
   (`data.frame`, last grid — [`SCHEMA.md`](SCHEMA.md#frame_reffield-is-a-dotted-path-and-the-frame-is-the-last-grid)),
   and **250 additional published human replay guids** were found and are listed in
   [`published-replays.json`](published-replays.json).
4. **Then: segment and label.** Boundaries are meaningful state changes, not fixed strides.
   Every record must pass `validate.py`; every gold record's `action_role` must cite a real
   line in the game source under `docs/static/games/src/`; every negative record must pair an
   observed failure with a corrected next decision.

## The replay scraper

`tools/replay_scrape.py` (plan §5 step 3). Stdlib only, Python 3.13, run from the repo root.

```bash
python3.13 tools/replay_scrape.py known          # re-pull the two known-good human wins
python3.13 tools/replay_scrape.py session <guid> # print /api/sessions/<guid>; downloads nothing
python3.13 tools/replay_scrape.py guid <guid>... # resolve game_id via /api/sessions, then pull
```

Two endpoints, **both verified live on 15-Sep-2026**, both on `https://three.arcprize.org`:

| endpoint | what it gives |
|---|---|
| `/api/recordings/<game_id>/<guid>` | the NDJSON recording |
| `/api/sessions/<guid>` | run metadata — `game_id`, `state`, `levels_completed`, `actions`, `resets`, `score`, `published_at` |

`/api/sessions` had never been called before this step; it exists, it returns 200, and it is
the **only** way to turn a bare replay guid harvested off a public page into the `game_id` the
recordings path needs. `HEAD` on the recordings path is `405` (`allow: GET`).

**Rows are written verbatim.** No normalising, no reshaping, no re-serialising — the on-disk
NDJSON is the source of truth, so a downstream resolver bug never costs a 138 MB re-pull, and
the row-count acceptance criterion only means something if the bytes are the API's own. Proof
the committed tool does this: its output is byte-identical (`cmp`) to a plain `curl` of the
same URL.

**Not resumable, and honest about it.** The API ignores `Range` — a `Range: bytes=0-1023` GET
returns `200` and the whole 73,579,940-byte g50t body, no `206`, no `Content-Range`. So an
interrupted pull restarts from zero. What protects you is that the body lands on
`<guid>.ndjson.part` *in the destination directory*, is proved to parse line-by-line and to end
in a newline, and is only then `os.replace`d into place. A truncated file is never left behind
looking complete. A re-run skips a target that already exists and parses; `--force` re-pulls.
`429` and `5xx` back off using the API's own `x-ratelimit-reset` header.

**Never `git add -f` a recording.** They are ~202 MB combined and `datasets/decision-steps/v0/`
is gitignored for that reason.

## Published replay guids — 250 found

[`published-replays.json`](published-replays.json) lists every human replay guid linked from
the public ARC blog post *"ARC-AGI-3 human dataset"* — 10 per environment across 25
environments. Plan §5 braced for a zero here and §7(a) calls scraping more guids "step zero of
any real corpus", so the list is committed rather than left in a chat message.

**There is still no guid-enumeration endpoint.** What was probed on 15-Sep-2026, all of it
time-boxed, before the blog post turned out to carry the list:

| probed | result |
|---|---|
| `GET /api/games` (three.arcprize.org) | `401 unauthorized` |
| `GET /api/sessions` (no guid) | `404` |
| `GET /api/recordings` (no path) | `404` |
| `GET /api/cards/<card_id>`, `/api/scorecards/<card_id>` | `404` — a session document does carry a `card_id`, but nothing serves it |
| `GET /api/leaderboard` | `404` |
| `/openapi.json`, `/docs` on three.arcprize.org | `301` to the marketing page; no spec |
| `https://arcprize.org/sitemap.xml` | 60 URLs, **no** `/replay/` entries |
| `https://arcprize.org/replay/<guid>` HTML | contains only its own guid; no API paths in the markup |
| `https://arcprize.org/blog/arc-agi-3-human-dataset` | **250 replay links**, 10 per environment × 25 |

So the list is harvested from a published page and then resolved guid-by-guid through
`/api/sessions`; there is no endpoint that will hand you all of them.

Read the caveats in that file's `_provenance` block before treating it as 250 gold episodes.
The short version: `tags: ["human"]` covers losses as well as wins, and the replays we
already had are **not** in this set — they were published 2026-09-13/14, the blog set on
2026-03-22. Ours are listed separately in
[`first-party-replays.json`](first-party-replays.json); see
[Two replay manifests](#two-replay-manifests-and-why-they-are-two) for why they are not merged
into one file.

**Known limit, stated plainly:** we own 5 wins across 17 environments, and no
recording has been pulled for any of them but bp35, cd82 and g50t. Every other row in the
first-party manifest is metadata only — a guid we are entitled to pull, not a trace we hold.
Until those recordings exist, "10–20 episodes" still means correlated segments of a handful of
human sessions: fine for a schema shakedown, **not** a corpus.

## Two replay manifests and why they are two

| file | rows | what every row in it is |
|---|---|---|
| [`published-replays.json`](published-replays.json) | 250 | a guid linked from the public ARC blog post *"ARC-AGI-3 human dataset"* |
| [`first-party-replays.json`](first-party-replays.json) | 23 | a replay the Boss played on his own arcprize.org account, not harvested from a page |

**They are not merged, and the reason is the whole point of having either.**
`published-replays.json`'s provenance is one sentence — "linked from the ARC blog post" — and
that sentence is only worth anything while it is true of *every* row in the file. None of our 23
replays is in the blog's 250. Appending them would buy one file and cost the ability to say
where any given row came from. So they sit in a sibling with the same row shape and their own `_provenance`.

The invariant that keeps this honest — **no guid appears in both files** — is asserted by
`ReplayManifestTests` in `scripts/test_decision_step_validator.py`, not merely intended.

### What is in the first-party file

23 runs across 18 environments, all played by the Boss on his own
arcprize.org account: **6 `WIN`, 6 `GAME_OVER`,
11 `NOT_FINISHED`**, 5,480 actions in total. The wins:

| game | guid | levels | actions | resets |
|---|---|---|---|---|
| `bp35-0a0ad940` | `c935ca1b…` | 9 | 1024 | 13 |
| `g50t-5849a774` | `4f0689d0…` | 7 | 533 | 9 |
| `ls20-cb3b57cc` | `6184a865…` | 7 | 378 | 0 |
| `r11l-495a7899` | `60c0af00…` | 6 | 316 | 6 |
| `cn04-2fe56bfb` | `f714032e…` | 6 | 454 | 4 |
| `cd82-fb555c5d` | `496ee425…` | 6 | 216 | 0 |

The `cn04` row is the one exception to everything the next two paragraphs say about where these
rows came from: it was played *after* the 2026-09-15 scorecard snapshot and was fetched by a
single direct `/api/sessions` call, not from the inventory. It is also the most useful single row
in the file so far. `ACTION5` rotates the held part across the whole of levels 1–4 of `cn04`, and
on level 5's yellow part it never rotates at all — it steps up a 5-deep stack of nested growing
variants, and the small variants carry fewer marks than the large ones (3 at starting size, 7
fully expanded), so marks that must be satisfied are **absent from the board** until the part is
expanded. Verified against `docs/static/games/src/cn04-2fe56bfb/cn04.py:1066-1075`. An agent that
induced `ACTION5 = rotate` from levels 1–4 arrives at level 5 holding a hypothesis that is false
rather than incomplete, with nothing on screen to signal the change — which is the
falsified-prediction material this corpus exists to capture, in a real human run.

"First-party" now means **both** *this project pulled it directly* **and** *the Boss played it*.
An earlier version of the manifest said only the cd82 row had a named player and that bp35 and
g50t carried `tags: ["human"]` and nothing finer. That was wrong: all three guids appear on the
Boss's own scorecards, which all carry `user_name: "Mark"`. The attribution was missing because nobody
had gone looking, not because it did not exist.

The set is a **floor, not a complete history**. It came from an authenticated
`/api/user/scorecards` pull on 2026-09-15, and that endpoint returns only the 50 most recent
cards with no way to page past them. Runs that made no progress (`levels == 0`) are excluded, and
so are 11 `gpt-5-nano` *agent* runs on `as66-821a4dcad9c2` — this file's row shape has no field
that could mark a row as agent-played, so carrying them would make the file's own "human" claim
false. Their guids are listed under `_provenance.excluded_agent_guids` so the exclusion is
auditable. Read that file's `_provenance` block before treating these rows as a corpus.

`cd82-fb555c5d` is an environment the rest of the corpus tooling has never seen, which makes it
the first real test of the scraper against a guid it was not written around:

```bash
python3.13 tools/replay_scrape.py guid 496ee425-9705-409f-8410-463a2229627e
```

pulled clean on 2026-09-15 — **217 rows, 10,487,262 bytes** — and its rows carry the same
`data.frame` shape (a list of 64×64 grids) that the
[frame convention](SCHEMA.md#frame_reffield-is-a-dotted-path-and-the-frame-is-the-last-grid)
assumes. No episode cites cd82 yet. Step 4 has started — see [The corpus so far](#the-corpus-so-far).

### Session `actions` versus recording rows — reconciled

The counts differ (1024→1030, 533→534, 216→217, 454→455) and the rule is exact:

```
recording rows = 1 + session.actions + rows submitted while the board was already GAME_OVER
RESET rows     = 1 + session.resets
```

The leading `1` in both is row 0, which carries `full_reset: true` — the boot reset, which the
session API counts as neither an action nor a reset. The third term is only non-zero on bp35,
where it is **5**: rows 215, 370, 390, 572 and 807 each submit `ACTION7` to a board that the
preceding row already flipped to `GAME_OVER`. Each returns `data.frame: []`, changes nothing,
is not counted by the API, and is followed immediately by a `RESET`. Verified against all four
recordings on disk — bp35, g50t, cd82, cn04 — both numbers matching on every one, and asserted
by `RecordingRowReconcileTests` in `scripts/test_decision_step_validator.py`.

Two consequences for labelling. A record must never point `frame_ref` at one of those five
rows: the frame list is empty and the resolver rejects it — point at the preceding row, which
is the board the player was actually looking at. And the row count still comes from the
scraper's observed output; the formula explains the gap, it does not replace the count.

## The corpus so far

`v0/episodes/` holds the labelled records. Every one cites a real row of a real recording and
is validated with frame resolution **required**, so a bad row index is a test failure rather
than a quiet pass.

| episode | records | tiers | what it covers |
|---|---|---|---|
| `bp35-0a0ad940__c935ca1b…__l5-death-undo-reset-00` | 4 | 3 gold, 1 negative | two segments: `bp35-l5-approach-00` (`episode_start`) is the traversal step that kills the run; `bp35-l5-recovery-01` (`death`) is `ACTION7` failing on the dead board and the `RESET` that recovers |
| `cn04-2fe56bfb__f714032e…__l4-extent-change-00` | 1 | 1 gold | `ACTION5` growing a part instead of rotating it |

Both are worth reading before adding more, because they are the two shapes this corpus exists
to hold. `boundary_reason` is a property of the **segment**, so every record sharing a
`segment.id` carries the same value — see
[SCHEMA.md](SCHEMA.md#boundary_reason-is-a-property-of-the-segment-not-of-the-record).

**The bp35 episode is the tier-3 shape, taken from human play rather than mined.** The plan §2
requires a negative record to pair a failed probe with a *verified corrected next decision*,
and warns that our own failed agent transcripts cannot supply one. Here the correction is
observed: the player pressed `ACTION7`, got nothing, and pressed `RESET`, which worked. The
source says why — `ACTION7` is the one branch of `bp35.py`'s dispatch that does not first push
an undo snapshot (`bp35.py:4524`, against `:4496`, `:4501`, `:4506`, `:4511`, `:4516`, `:4521`),
and `RESET` restores the level-start snapshot instead (`bp35.py:4529` → `:447`). The same
death → failed undo → reset triple appears five times in that one recording.

**The cn04 record is a refuted rule, and the refutation is measurable.** `ACTION5` dispatches on
the *selected part*: `cn04.py:1070` steps that part through its sprite stack when it has more
than one entry, and only `cn04.py:1072` rotates it 90°. Measured across the recording, all 12
`ACTION5` presses on level indices 0–2 conserved the painted-cell count exactly; from level
index 3 on, 39 of 65 did not (77 ACTION5 presses in the recording, 12 + 65). Three levels teach "this action is a rotation" before the
rule stops holding — full write-up in
[`docs/trace-findings/2026-09-15-cn04-object-dependent-verb.md`](../../docs/trace-findings/2026-09-15-cn04-object-dependent-verb.md).

### Known limit

Five records is not a corpus. The plan's §5 step 4 target is 10–20 episodes per game, and
`expected_observation` and `rationale` on every record are **annotated** — attached
retrospectively from the game source, never recovered human thought
(`rationale_provenance: "annotated"`, and the tier definitions in
[`SCHEMA.md`](SCHEMA.md#tiers) say so).

## Eligibility — only runs on a current build

**Boss directive, 15-Sep-2026.** ARC Prize rebuilt these games as the benchmark firmed up, so an
early replay is a replay of a *different game* — ls20 in the preview is not the ls20 that ships
now. A run is eligible for this corpus only when its `game_id` is still the live build.

`current-builds.json` is a dated snapshot of `GET /api/games`, read offline by
`CurrentBuildTests`. Under it:

| manifest | eligible | total |
|---|---|---|
| `published-replays.json` | **100** | 250 |
| `first-party-replays.json` | **20** | 25 |

Neither manifest is filtered — `published-replays.json` is a record of what the blog linked and
`first-party-replays.json` of what the Boss played, and filtering either would make its own
provenance claim false. Eligibility is applied when selecting what to *label*, and the counts
above are asserted by a test so a lineup change surfaces here rather than mid-labelling.

Two consequences worth stating. **All 25 current builds have game source in the repo**, so
`action_role_source` is no longer a constraint on what can be labelled. And **as66 is not in the
live lineup at all**, so none of its 15 recordings are corpus input — see
[`docs/trace-findings/2026-09-15-as66-the-withdrawn-26th-game.md`](../../docs/trace-findings/2026-09-15-as66-the-withdrawn-26th-game.md).
