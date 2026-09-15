<!--
Author: Claude Opus 5 (Bubba)
Date: 15-September-2026
PURPOSE: Execution plan for step 4 of the v0 decision-step corpus - segmenting and labelling
real replay recordings into the corpus itself. Written for a fresh session with no transcript:
carries the measured source-coverage constraint, the reset-density selection rule, the five
passes and their order, and the acceptance gate. The plan of record is
docs/trace-findings/2026-09-14-decision-step-corpus-v0-plan.md section 5 step 4; this is how
that step gets executed, not a redefinition of it.
SRP/DRY check: Pass - the v0 plan holds the spec, the schema and the build order; this holds
only the execution of its final step. Schema semantics live in datasets/decision-steps/SCHEMA.md
and are not restated here.
-->

# Step 4 execution — segment and label the v0 corpus

**Status:** plan, 15-Sep-2026. Steps 1–3 are merged on `main`. Step 4 has one episode pair
landed as a shape demonstration (PR #16) and no volume.

The acceptance criterion is unchanged and comes from the plan of record §5 step 4:

> every record passes `validate.py`; every tier-1 record's `action_role` cites a specific line
> or rule in the game source; every tier-3 record pairs an observed failure with a corrected
> next decision.

---

## 0. Eligibility — settled by the Boss, 15-Sep-2026

**A run is eligible only if its `game_id` is still the live build.**

The Boss's reasoning: ARC Prize did not have this settled early on, and the games themselves
changed underneath the early replays — *ls20 in the preview is not the ls20 that ships now*. A
replay of a replaced build is a replay of a different game, whatever its date.

**Build id is the checkable form of that rule, and it is stricter and more precise than a date
cutoff.** Date is the symptom; the build hash is the test. The live set is snapshotted at
`datasets/decision-steps/current-builds.json` and asserted by `CurrentBuildTests`, which reads
the snapshot offline and never calls the API.

What this does to §1 below, which was written before the rule existed:

- **The source-coverage constraint disappears.** All **25** current builds have a directory
  under `docs/static/games/src/`. The "16 of 36 builds have no source" measurement was counting
  *stale* builds, which this rule excludes anyway. `action_role_source` is no longer a
  constraint on what can be labelled — it is simply a step in labelling it.
- **Eligible material, recounted under the rule:**

  | manifest | eligible | total | games | resets |
  |---|---|---|---|---|
  | `published-replays.json` (blog) | **100** | 250 | 10 | 603 |
  | `first-party-replays.json` (Boss) | **20** | 25 | 16 | 64 |

  The blog's 250 are all from March 2026 and **15 of the 25 builds they used have since been
  replaced**, so 150 of those rows document games that no longer exist.

- **One judgement call, stated so it can be reversed in a line.** The rule is applied as
  *build-currency*, not as a date cutoff, which keeps 100 March rows whose builds never changed.
  If the intent was strictly "September only", drop those 100 and the eligible set becomes the
  Boss's 20 runs alone.
- **as66 leaves corpus scope entirely.** It is not in the live lineup, so no as66 run is
  eligible under this rule. The finding stands on its own —
  `docs/trace-findings/2026-09-15-as66-the-withdrawn-26th-game.md` — and its 15 recordings stay
  on disk, but they are not corpus input.

**Reservation, stated not buried:** build id is the only version signal the API exposes. That it
changes when and only when the game changes was **not** verified; it is assumed. Re-snapshot
`current-builds.json` after any lineup change.

---

## 1. Two measurements that shape everything

> **Superseded in part by §0.** The source-coverage constraint below no longer binds, because
> every current build has source. The reset-density selection rule in §1(b) stands, and is the
> part that still drives which recordings get pulled. Kept as written, with §0 taking precedence,
> rather than rewritten — the measurement was real and the reasoning from it is worth keeping.


Both taken 15-Sep-2026 against the two committed manifests and `docs/static/games/src/`.

### (a) Source coverage is the binding constraint — 130 of 273 runs

`action_role_source` must cite a line in the game source. **16 of the 36 `game_id` builds
across the two manifests have no directory under `docs/static/games/src/`**, so runs on those
builds cannot produce a record that meets acceptance, no matter how good the play is.

| | runs | games |
|---|---|---|
| in `published-replays.json` + `first-party-replays.json` | 273 | 36 |
| **on builds with source in the repo** | **130** | **20** |
| on builds with no source | 143 | 16 |

Builds with no source: `ar25-e3c63847`, `as66-821a4dcad9c2`, `cn04-65d47d14`,
`dc22-4c9bff3e`, `ka59-9f096b4a`, `m0r0-dadda488`, `r11l-aa269680`, `re86-4e57566e`,
`s5i5-a48e4b1d`, `sc25-f9b21a2f`, `sk48-41055498`, `sp80-0605ab9e5b2a`, `sp80-0ee2d095`,
`su15-4c352900`, `tn36-ab4f63cc`, `tu93-2b534c15`.

**Several of these are almost certainly build drift, not missing games** — `sk48-41055498`
has no source while `sk48-d8078629` does; likewise `cn04`, `sc25`, `tn36`, `r11l`, `re86`,
`m0r0`, `sp80`, `ls20`. Whether a record may cite a *sibling build's* source is an open
question and is **not** assumed here: pass B settles it per game by diffing the dispatch
region, and until it does, only same-build runs are eligible.

### (b) Resets are the tier-3 seam — 683 of them are reachable

Tier 3 is the tier the corpus exists to create and the one we have almost none of. A `RESET`
row is preceded by a death or a stuck board, and on bp35 each death was also preceded by a
*failed* recovery attempt. So reset count is the best available proxy for tier-3 density, and
it is already in the manifests — no recording needs pulling to rank on it.

**683 resets across the 130 eligible runs.** Six games carry 561 of them (82%):

| game | eligible runs | resets | recording on disk |
|---|---|---|---|
| `bp35-0a0ad940` | 12 | 136 | yes |
| `wa30-ee6fef47` | 11 | 130 | no |
| `g50t-5849a774` | 11 | 117 | yes |
| `lp85-305b61c3` | 10 | 88 | no |
| `ls20-9607627b` | 11 | 54 | no |
| `lf52-271a04aa` | 11 | 36 | no |

`cd82-fb555c5d` (12 runs, 23 resets) and `cn04-2fe56bfb` (1 run, 4 resets) are already on
disk and stay in scope because they are already paid for, not because they are dense.

**v0 scope: those six games, plus the two already on disk.**

---

## 2. What is mechanical and what needs judgment

This is the reason step 4 is a pipeline rather than pure annotation hours. Building the five
records in PR #16 by hand established which fields are derivable from the recording plus the
game source, and which are not.

**Derivable — pass A fills these, measured, never guessed:**

- `segment.boundary_reason` and segment cuts — `death` from a `state` flip to `GAME_OVER`,
  `reset` from a `RESET` row, `undo` from `ACTION7`, `level_advance` from a rise in
  `levels_completed` (added 15-Sep-2026; a window spanning a level change was refused before
  that, and the refusal was hiding 25 transitions the heuristics would have mislabelled
  `extent_change` and 15 they would have missed entirely),
  `camera_shift` and `extent_change` from frame deltas (a painted-cell count that changes is
  an extent change; a whole-board delta with a conserved histogram is a camera shift).
- `frame_ref` — including the rule that it must never point at a row whose frame list is
  empty; point at the preceding row, which is the board the player was looking at.
- `outcome.observed` — cells changed between settled frames, state transition, level
  transition, painted-count delta. Numbers, not prose.
- `source`, `level`, `game_id`, `schema_version`, `rationale_provenance`.
- `action_role_source` — from the per-game dispatch table built in pass B.

**Needs a mind — passes D and E:**

- `decision.rationale`
- `decision.expected_observation`
- `memory_in` / `decision.memory_out`
- `corrected_decision` on negative records
- `action_role` in words

That split is the whole plan: mechanise the first list so the annotators spend their attention
only on the second.

---

## 3. The passes, in order

### Pass A — `tools/segment.py`

Reads one recording plus a per-game dispatch table, writes candidate episode files to
`datasets/decision-steps/v0/episodes/` with every derivable field filled and the judgment
fields absent.

Candidates are **not** schema-valid on purpose: a candidate missing `rationale` must fail
`validate.py` so an unfinished record can never be mistaken for a finished one. Candidates are
written with a `.candidate.jsonl` suffix, which `validate.py` does not collect, and are
gitignored.

*Acceptance:* run against the bp35 recording, `tools/segment.py` reproduces the segment cuts,
frame refs and `outcome.observed` numbers of the four hand-built records in
`bp35-0a0ad940__c935ca1b…__l5-death-undo-reset-00.jsonl` — including the five dead-board rows
at 215, 370, 390, 572, 807 being skipped as frame targets. A test asserts the reproduction.

### Pass B — one dispatch table per game

One read of each game's source, producing `datasets/decision-steps/dispatch/<game_id>.json`:
action name → function called → file and line number, plus any branch conditions. Built once,
cited by every record in that game.

Worked example, bp35 (`docs/static/games/src/bp35-0a0ad940/bp35.py`):

| action | line | effect |
|---|---|---|
| ACTION1–4 | 4494, 4499, 4504, 4509 | `oreuzgjmdx(dx, dy)` — move one cell; each pushes an undo snapshot first via `vlyikbzinq()` |
| ACTION5 | 4514 | `uatdugrwtx()` |
| ACTION6 | 4519 | `gwfodrkvzx(x, y)` — act on the clicked cell |
| ACTION7 | 4524 | `svmaaixutx()` — pop the undo stack. **The one branch that does not push a snapshot first.** |
| RESET | 4529 | `eubgwokpez()` at `:447` — clear the undo stack, restore the `on_set_level` snapshot |

And cn04, where the branch itself is the finding (`cn04.py:1067`): ACTION5 steps the selected
part through its sprite stack at `:1070` when that part has more than one entry, and only
rotates 90° at `:1072` when it does not.

*Acceptance:* a table for each of the eight in-scope games; every action offered in that game's
`available_actions` has an entry; each entry's line number is verified to still contain the
cited call. A test re-reads the source and fails on drift. **Pass B also settles the sibling-build
question from §1(a)** by diffing the dispatch region between builds and recording, per game,
whether a sibling build's source may be cited.

### Pass C — pull recordings

Highest-reset eligible runs first, for the six selected games, via `tools/replay_scrape.py`.
Roughly 70–140 MB each and gitignored. Pull incrementally and check free space between games;
do not fetch all 130.

*Acceptance:* row counts reconcile under the rule in
`datasets/decision-steps/README.md` — `rows = 1 + api.actions + rows submitted while GAME_OVER`
— for every recording pulled. A mismatch is a finding, recorded, not smoothed over.

### Pass D — annotate

One agent per game, in parallel, filling only the judgment fields on pass A's candidates.

Rules, from the plan of record §1 and §2:

- A rationale that the next frame cannot contradict is **not a valid target**. If the
  expectation cannot be refuted by the cited next frame, the record does not ship.
- Rationale and `expected_observation` are **labels attached retrospectively**, never
  recovered human thought. `rationale_provenance` stays `"annotated"`.
- Tier 3 requires a **verified** corrected next decision. Prefer corrections that are
  *observed* in the recording — the player's actual next move, where it worked — over
  corrections the annotator reasons out. The bp35 death → failed undo → reset triple is the
  model: the correction is on tape.
- The annotator writes `memory_in` as what a player could know *at that row from that run
  alone*, never from the game source. The source is for `action_role_source` only. Leaking
  source knowledge into `memory_in` produces a record that teaches clairvoyance.

*Acceptance:* every record passes `validate.py --require-frame-resolution`.

### Pass E — the falsifiability gate

An adversarial pass over every finished record, by an agent that did not write it.

For each record: resolve the cited next frame and ask whether it *actually* confirms or refutes
the stated `expected_observation`, and whether `outcome.expectation_held` matches that
resolution. Anything unfalsifiable, vacuous ("something changes"), or whose recorded outcome
does not follow from the frames is cut and sent back to pass D.

This is the only pass that stands between a pipeline and a large pile of confident mush, and it
is the plan's own criterion — §1 says a rationale that cannot be contradicted by the next frame
is not a valid target. **A record that fails pass E is deleted, not softened.**

*Acceptance:* the count of records cut is reported, not hidden. A pass E that cuts nothing is
reported as suspicious rather than as success.

---

## 4. Order and parallelism

A and B **before** C, D and E. Without the segmenter and the dispatch tables, every annotation
agent invents its own segmentation and its own citation format, and the corpus drifts between
games — which is exactly the failure `boundary_reason` was made a closed enum to prevent.

C, D and E then run per game and can overlap across games: game *n* can be in pass D while
game *n+1* is still in pass C.

## 5. Volume target and what it is honestly worth

The plan of record asks for 10–20 episodes per game. At eight games that is 80–160 episodes,
several records each.

Stated plainly so nobody oversells it downstream: this is **one annotator's retrospective
reading of other people's play**, not recovered reasoning, and the tier-3 records depend on
humans having made recoverable mistakes on camera. It is a data spec that survived contact with
real replays and a first corpus to train nothing but the pipeline. It is not a benchmark and it
is not a training set anyone should cite as one.

## 6. Open schema questions, carried not closed

All are flagged in `datasets/decision-steps/SCHEMA.md` and none is settled here:

1. `last_result` has only `board_changed` and `level_changed`, so it cannot express "that
   action ended the run". Post-death records currently read like ordinary steps.
2. `boundary_reason` carries per-game values (`bridge_edit`, `ghost_construction`,
   `extent_change`). That does not survive 25 games; the likely shape is a generic reason plus
   a per-game qualifier.
3. `level` is `levels_completed`, a count, so during play of the *N*th level it reads *N*−1.
   Latent until now; visible inside any episode that spans a `level_advance` cut.

**Closed since this plan was written:** `boundary_reason` had no value for a level transition,
so the segmenter refused any window spanning one. `level_advance` was added 15-Sep-2026 and the
refusal is gone — a *falling* level count is still refused, being unobserved on every recording
on disk.

Pass D will hit the rest at volume. Whichever bites first gets a schema change of its own
rather than a quiet widening mid-grind.
