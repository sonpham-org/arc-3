<!--
Author: Claude Opus 5 (Bubba)
Date: 15-September-2026
PURPOSE: Running changelog for the decision-step corpus work in this repo, newest first.
Exists so a reviewer joining cold can see where the work stands without reading fifteen pull
requests. Covers the corpus pipeline (datasets/decision-steps/, tools/replay_scrape.py,
scripts/test_decision_step_validator.py) and its trace findings. It does NOT cover
ARC3-Inference or the harnesses, which predate it and are not changed by this work.
SRP/DRY check: Pass — plans live in docs/plans/ and docs/trace-findings/, schema semantics in
datasets/decision-steps/SCHEMA.md. This file only records what changed, when, and why.
-->

# Changelog

Newest first. Versioning is date-based; this work is pre-1.0 and the schema is pinned at
`0.1`.

---

## Where this stands — 15-Sep-2026

Read this first if you are picking the work up cold.

**The goal.** A corpus of *decision steps*, not winning move sequences. Each record pairs the
board a player saw with the action they chose, a short **falsifiable** rationale, and an
`expected_observation` that the next frame either confirms or refutes. The metric it exists to
move is **recovery after falsification**, which is structurally absent from every trace we
hold. Spec: `docs/trace-findings/2026-09-14-decision-step-corpus-v0-plan.md`.

**Status of the four planned steps.**

| step | what | state |
|---|---|---|
| 1 | ACTION7 executes end to end | **done**, on `main` |
| 2 | JSON schema + validator | **done**, on `main` |
| 3 | replay scraper + guid inventory | **done**, on `main` |
| 4 | segment and label the corpus | **started** — shape landed, volume not |

**What exists right now.** 46 tests. 273 human replay guids inventoried across two manifests
that are deliberately not merged. 6 recordings on disk plus 15 for as66. **5 labelled
records** — a demonstration of shape, not a corpus.

**The one rule that governs step 4.** A run counts only if its `game_id` is **still the live
build** — an early replay is a replay of a different game. That leaves **100 of the blog's 250**
and **20 of the Boss's 25**, and every current build has game source, so citation is no longer a
constraint. Execution plan, with the selection rule and the five passes:
`docs/plans/2026-09-15-step4-segment-and-label-execution.md`.

**Open questions carried, not closed.** (1) `last_result` cannot express "that action ended
the run", so post-death records read like ordinary steps. (2) `boundary_reason` carries
per-game values, which will not survive 25 games. Both are flagged in `SCHEMA.md` and neither
has been quietly widened.

**In flight, not merged as of this entry.** A branch off #16 building `tools/segment.py` and
the per-game dispatch tables — passes A and B of the step-4 plan.

---

## 2026-09-15 (later)

### Eligibility settled: only runs on a **current build** count

Boss directive. ARC Prize rebuilt these games as the benchmark firmed up, so an early replay is
a replay of a *different game* — ls20 in the preview is not the ls20 that ships now. Encoded as
**build-currency** rather than a date cutoff, because build id is the precise, checkable form of
that reasoning: date is the symptom, the build hash is the test.

- `datasets/decision-steps/current-builds.json` — dated snapshot of the 25 live builds, read
  **offline** by `CurrentBuildTests`; the tests never call the API.
- **The source-coverage constraint is gone.** All 25 current builds have a directory under
  `docs/static/games/src/`. The earlier "16 of 36 builds have no source" figure was counting
  *stale* builds, which this rule excludes anyway. `action_role_source` is no longer a limit on
  what can be labelled.
- **Eligible material:** 100 of the blog's 250 (the other 150 sit on 15 builds that have since
  been replaced) and 20 of the Boss's 25. Neither manifest is filtered — each is a record of
  what it claims to be, and filtering would make its own provenance false — so eligibility is
  applied at selection time and the counts are asserted by a test.
- **as66 leaves corpus scope.** Not in the live lineup, so none of its 15 recordings are corpus
  input. The finding stands on its own and the recordings stay on disk.
- **One judgement call, reversible in a line:** build-currency keeps 100 March rows whose builds
  never changed. If the intent was strictly "September only", drop those and the eligible set is
  the Boss's 20 runs alone.
- **Reservation:** build id is the only version signal the API exposes; that it changes when and
  only when the game changes is **assumed, not verified**. Re-snapshot after any lineup change.

Also: episode globs now exclude `*.candidate.jsonl`, matching what `validate.py` already did.
Segmenter candidates carry no judgment fields and are deliberately not schema-valid, so an
unfinished record can never be mistaken for a finished one. 46 tests pass; the new build guard
was poison-checked.

---

## 2026-09-15

### as66 — an environment that is not in the live lineup, and 15 runs that still serve

`docs/trace-findings/2026-09-15-as66-the-withdrawn-26th-game.md`.

`as66-821a4dcad9c2` is absent from the authenticated `/api/games` list (25 games, none of them
as66) and absent from the blog's 250 published replays — but `/api/sessions` and
`/api/recordings` still return `200` for it. **15 runs pulled: 2 human, 13 agent, all 7–15
January 2026, 28 MB.** Why it is absent was *not* established and is not claimed.

Two findings worth a reviewer's time:

- **It is the only environment where we hold human and agent play on the same game.** The
  human reached level 6 of 9 using 9 resets; **11 of 13 agent runs never passed level 1**. Two
  agent runs are almost entirely RESET — `4a218928` is 98 RESETs in 101 actions, `75928ec9` is
  195 in 103. as66 offers **no ACTION7**, so reset is the only recovery verb, and the agent
  used it as its whole strategy.
- **The January recordings are an older row schema** and the reconcile rule below does **not**
  hold on any of them: integer `action_input.id` instead of strings, `score` instead of
  `levels_completed`, no `full_reset` boot marker, and a trailing all-null row. Candidate
  rules were tested; none covers all fifteen. **Recorded as unresolved.** Any segmenter must
  branch on schema version.

Blocked for the corpus by the same constraint as 143 other runs: no source in
`docs/static/games/src/`, and no sibling build to fall back on. If that source can be
obtained, this becomes the most valuable environment in the set.

### Refreshed the first-party replay manifest — 2 new wins, `dc22` becomes citable (#18)

Re-pulled the Boss's scorecards four hours after the first snapshot. Two wins played in
between: `dc22-fdcac232` (6 levels, 1320 actions, 8 resets) and `ft09-0d8bbf25` (6 levels, 133
actions, 4 resets, score 100, under baseline on every level). Manifest is now **25 rows, 20
builds, 8 WIN / 6 GAME_OVER / 11 NOT_FINISHED**, still disjoint from the published 250.

- **`dc22` level 5 is the densest exploration seam we hold** — 740 actions against a 324
  baseline, after being *under* baseline on the four levels before it.
- **`dc22` changes what is citable.** The blog's 250 carry `dc22-4c9bff3e`, which has no source
  directory; this build has one. A game that could not meet acceptance now can, because it was
  played on a current build. `ft09` is the opposite and equally useful: same build as the
  blog's ten ft09 rows, so the two are directly comparable.
- **Pagination settled.** `arcprize.org/api/user/scorecards` returns 50 items and its `next`
  field is a page size, not a cursor — `?at=50` returns the identical 50 `card_id`s. The
  50-card cap is real and the file remains a floor. All 50 resolved with zero failures, which
  **supersedes an earlier 429 report that could not be verified from the artefacts**. Per-card
  runs come from `GET /api/user/scorecards/<card_id>`; `/api/scorecard/<id>` is 401 and
  `/api/user/replays` is 404.

### Step 4 execution plan (#17)

`docs/plans/2026-09-15-step4-segment-and-label-execution.md`. The source-coverage constraint
(130 of 273 runs eligible), reset count as the selection rule (683 resets across those runs,
six games carrying 561), and five passes: segmenter → dispatch tables → pull → annotate →
**adversarial falsifiability gate**.

Two commitments made up front: pass E **deletes** records rather than softening them and
reports the cut count, and `memory_in` may never contain game-source knowledge — the source is
for `action_role_source` only, or the record teaches clairvoyance.

### Step 4 opens: `boundary_reason` widened, row counts reconciled, first real records (#16)

- **`boundary_reason` gained `episode_start` and `extent_change`.** The six original values all
  name a state *change*, so none could say "the episode opens here"; and cn04 has an event none
  covered — `ACTION5` dispatches on the selected part, stepping it through its sprite stack at
  `cn04.py:1070` when it has more than one entry and only rotating at `:1072` when it does not.
  `SCHEMA.md` gained a **Boundary reasons** section and states the real limit: per-game values
  do not scale to 25 games. Flagged, not redesigned.
- **`boundary_reason` is a property of the segment, not the record.** Decided here, because the
  field name admits either reading; every record sharing a `segment.id` must carry the same
  value, and a test enforces it.
- **Session `actions` versus recording rows — reconciled exactly, on every recording:**

  ```
  recording rows = 1 + session.actions + rows submitted while the board was already GAME_OVER
  RESET rows     = 1 + session.resets
  ```

  The leading `1` is row 0, which carries `full_reset: true` and the API counts as neither. The
  third term is non-zero only on bp35, where it is **5** — rows 215, 370, 390, 572, 807 each
  submit `ACTION7` to a board the preceding row already flipped to `GAME_OVER`, returning
  `data.frame: []`. The README previously said there was "no clean rule"; there is, and
  `RecordingRowReconcileTests` asserts it. **A record must never point `frame_ref` at one of
  those five rows** — the frame list is empty and the resolver rejects it.
- **First labelled records**, in `datasets/decision-steps/v0/episodes/`, validated with frame
  resolution *required*. The bp35 episode is the **tier-3 shape taken from human play**: a step
  that kills the run, `ACTION7` failing on the dead board, and the `RESET` that recovers — the
  corrected decision is *observed*, not invented. `ACTION7` is the one dispatch branch that
  does not first push an undo snapshot (`bp35.py:4524` against `:4496 :4501 :4506 :4511 :4516
  :4521`); `RESET` restores the level-start snapshot (`:4529` → `:447`). That triple occurs
  five times in one recording.

### cn04 `ACTION5` has two meanings, and levels 1–4 teach the wrong one (#15)

`docs/trace-findings/2026-09-15-cn04-object-dependent-verb.md`. Measured: all 12 `ACTION5`
presses on level indices 0–2 conserved the painted-cell count exactly; from level index 3 on,
39 of 65 did not. A re-verification pass on 12-Sep had deleted this observation as fabricated;
it was not, and the correction is in the study docs.

### Earlier the same day

- **#14** — the Boss's cn04 win added to the first-party manifest, the run that found the
  level-5 rule inversion.
- **#13** — first-party manifest corrected to 22 rows, all attributed to the Boss. **#12 was
  merged into an already-merged branch and its content never reached `main`**; #13 re-targeted
  it. Check `git merge-base --is-ancestor` before trusting a green merge badge.
- **#11** — `tools/replay_scrape.py`, the dotted `frame_ref.field` path, and
  `published-replays.json`: **250 blog-linked human replay guids**, 139 WIN across 25 games.
  `data.frame` is a *list* of grids and the settled board is `frame[-1]`, cited to
  `taaf/game.py:175` and `kd01.py:515`.
- **#10** — the JSON schema, `validate.py`, and the fixture corpus. `row_index` is **zero-based**,
  settled against a real recording. Turn-0 records are expressible: `last_action` and
  `last_result` are required and explicitly nullable, both-or-neither.
- **#9** — ACTION7 round-trip landed, unblocking recovery behaviour in both traces and labels.
