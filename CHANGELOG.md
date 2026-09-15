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
| 4 | segment and label the corpus | **started** — passes A and B on `main`; C/D/E not begun |

**What exists right now.** 94 tests. 273 human replay guids inventoried across two manifests
that are deliberately not merged. 6 recordings on disk plus 15 for as66. **5 labelled
records** — a demonstration of shape, not a corpus. `tools/segment.py` now emits the
mechanical portion of a record (cuts, frame refs, measured outcome, source citation) so that
annotation is three judgment fields rather than a whole record.

**The one rule that governs step 4.** A run counts only if its `game_id` is **still the live
build** — an early replay is a replay of a different game. That leaves **100 of the blog's 250**
and **20 of the Boss's 25**, and every current build has game source, so citation is no longer a
constraint. Execution plan, with the selection rule and the five passes:
`docs/plans/2026-09-15-step4-segment-and-label-execution.md`.

**Open questions carried, not closed.** (1) `last_result` cannot express "that action ended
the run", so post-death records read like ordinary steps. (2) `boundary_reason` carries
per-game values, which will not survive 25 games. (3) `level` is `levels_completed`, a count —
during play of the Nth level it reads N−1, so `"level": 5` means the 6th, and an episode
spanning a `level_advance` cut now shows it. All three are flagged in `SCHEMA.md` or the tool
docstrings; none has been quietly widened.

**Closed since the last entry.** `boundary_reason` had no value for a level transition and the
segmenter refused any window spanning one. `level_advance` closed it — see the entry directly
below, including what the refusal was hiding.

**Next.** Passes C (pull the selected recordings), D (annotate, one agent per game) and E (the
adversarial falsification gate) of the step-4 plan. E is the one that decides whether any of it
is worth having: a record whose `expected_observation` the cited next frame can neither confirm
nor refute gets cut, not softened.

---

## 2026-09-15 (latest)

### bp35 recovery mechanics, measured — and a correction to a labelled record

Committed direct to `main`. The Boss pushed back on this repo's reading of bp35's ACTION7/RESET
behaviour, and on a claim that it conflicted with the Retrodict harness's "prefer undo over RESET,
never two RESETs in a row" heuristic. He was right on every count. Going back to the traces turned
up something better than what was given up. Full write-up:
`docs/trace-findings/2026-09-15-bp35-undo-costs-a-move.md`.

**The find: bp35 has a per-level move budget and undo spends from it.** The move counter increments
on every action *including* ACTION7 (`bp35.py:4528`) and is zeroed only by RESET (`:4533`) and by a
level change (`:4543`). `render_interface` loses the level on exact equality with a level-dependent
budget — 64 for levels 1–6 (`:4413`, `:4421`), 128 for 7–9 (`:4436`), 192 for 10 (`:4404`).
Reconstructed across all 1,030 rows: **no row exceeds its budget**, and the counter reaches it
exactly twice, both `GAME_OVER` — row 806 (`ACTION6`) and row **936 (`ACTION7`), an undo that ended
the level**. So RESET refunds the whole level budget and undo does not, which makes "prefer undo
over RESET" a budget tradeoff rather than free advice.

**The correction: the empty ACTION7 rows are refusals, not undos that returned nothing.** The game
code cannot emit an empty frame list — `bp35.py:1455` always returns at least one grid. The five
rows carry `win_levels: 0` alongside `frame: []`, where all 1,029 other rows carry `win_levels: 9`;
that is an unpopulated envelope, so the action was refused in the engine layer above `bp35.py`. The
distinction is the difference between "retry the undo" and "this action is unavailable in this
state", so the negative record's `outcome.observed` and `action_role_source` were corrected. Its
`rationale` was **not** — it is a correct statement of what the player believed, which is the point
of a rationale.

**The RESET rule, sharpened.** Confirmed against all 302 non-initial RESET rows in the fifteen as66
recordings, zero exceptions: RESET restores the current level's start snapshot, and when the board is
*already* at that snapshot it escalates to a full restart to level 1. Retrodict's "never two RESETs
in a row" catches 2 of the 3 observed restarts and misses the third — a single RESET issued right
after completing a level. The correct guard is *never RESET a board you have not yet changed*.

**Also settled.** The preview set had no undo: January as66 rows carry
`"available_actions": [1, 2, 3, 4, 6]`, and RESET is present throughout as id 0. And bp35's 16
`GAME_OVER` rows decompose as **11 real deaths** (9 in-game, 2 budget) plus **5 refused envelopes** —
an earlier summary said "five", counting only the refusals.

**Not confirmed, and left that way.** RESET as a visible no-op has a source mechanism
(`bp35.py:447`) but **no instance in our six live-build recordings**; every RESET row's settled frame
differs from the one before it. Source explanation is not an observation.

**Guards.** +6 tests (88 → 94), each poison-checked: the budget holds on every row, only rows 806 and
936 reach it, row 936 is an `ACTION7`, the empty-frame rows are exactly the five known refusals and
carry `win_levels: 0`, and every other row carries 9.

**For step 4.** A budget death and an in-game death both land on `boundary_reason: death` today and
call for opposite corrections — "take a different route" versus "take a shorter one". Flagged, not
widened.

---

### `boundary_reason` gets a value for a level transition: `level_advance`

Committed direct to `main`. Passes A and B shipped with the level-transition gap **refused**
rather than papered over: `boundary_reason` had no value for one, so `tools/segment.py` rejected
any `--rows` window that spanned a level change and named the row to split at. That was the
honest move at the time. It was also hiding two wrong answers, not one.

**What the refusal was hiding, measured on the 40 level transitions in the six live-build
recordings on disk** (bp35 9, g50t 7, cd82 6, cn04 6, dc22 6, ft09 6):

| what the segmenter would have said | count |
|---|---|
| `extent_change` — a cn04 word about a held part growing, applied to a whole new level | **25** |
| nothing at all — no boundary, a segment running straight through a level change | **15** |

So the choice was never "refuse or label correctly"; it was "refuse, or ship 25 plausible-looking
lies and 15 silent misses".

**The fix.**

- **`schema.json`** — `level_advance` added to the `boundary_reason` enum. `enum` is already in
  `validate.py`'s supported-keyword audit (`validate.py:49`), so this adds **zero new evaluator
  surface**, the same discipline the turn-0 fix and the dotted `frame_ref.field` followed.
- **`tools/segment.py` rule 6** — a rise in `levels_completed` on a settled row is
  `level_advance`, and it **outranks** the frame-delta heuristics. All 40 transitions now label
  correctly; nothing else on the 1,030-row bp35 recording is labelled `level_advance`, and there
  is a test that walks every row to prove it.
- **A falling level count is still refused.** Unobserved in all 40 transitions, and it should be
  impossible — `RESET` restores a level's opening snapshot, it does not un-complete a level. If
  one appears, the row schema means something other than what the tool reads, and that is worth
  stopping for rather than labelling.

**Stated as a decision, not a measurement:** where `level_advance` sits in the priority order —
below `death`/`reset`/`undo`, above `camera_shift`/`extent_change` — is unfalsified *and*
unexercised. Every one of the 40 transition rows carries `ACTION1`–`ACTION6` with state
`NOT_FINISHED` or `WIN`; never `RESET`, never `ACTION7`, never `GAME_OVER`. A test asserts that
claim so it fails loudly if it ever goes stale.

**`schema_version` stays `0.1`, and the rule is now written down** rather than implied and
quietly relied on. Adding a value to a closed enum does not bump it: no record already written
becomes invalid and `validate.py` rejects an unknown value under either version, so a reader
pinned to `0.1` cannot mis-read a `0.1` record. Adding, removing or retyping a **field** does
bump it. `0.2` is reserved for the per-game `boundary_reason` redesign, which is the real
version-worthy change — spending it on an enum value would leave nothing to call that.
Precedent named, not hidden: commit `73f512415` added `episode_start` and `extent_change` the
same way.

**Tests: 81 → 88.** Eight new, one deleted (the refusal test). Every new guard was
poison-checked the way pass B's nine were — the rule broken, the failure confirmed by its own
message, the file restored. The acceptance gate still holds: the four hand-built bp35 records
reproduce exactly.

**One thing this makes visible rather than causes.** `level` is `levels_completed`, a count, so
the records before a `level_advance` cut read one lower than the records after it. That is
correct and it still reads like an off-by-one. Flagged in `SCHEMA.md`, unchanged here — renaming
the field or switching it to a 1-based index is a field change and *would* bump
`schema_version`.

**Not touched:** `last_result` still cannot say "that action ended the run" — a different open
question, and the plan owner's call.

---

## 2026-09-15 (later still)

### Step 4 passes A and B: per-game dispatch tables, and `tools/segment.py`

PR #19. The premise, measured on the five hand-built records: most of a decision-step record is
**mechanical** — segment boundaries, frame references, the observed outcome, the source
citation. Only three fields need a mind: the rationale, the `expected_observation`, and the
memory delta. So automate the rest and spend the judgment where it counts.

- **`datasets/decision-steps/dispatch/` — 8 per-game tables** mapping action → handler →
  file:line, read once per game and reused by every record in it. Citation stops being the
  bottleneck.
- **`tools/segment.py`** emits candidate records with the judgment fields **absent**. Candidates
  are gitignored, are not collected by a directory walk, and are deliberately not schema-valid,
  so an unfinished record cannot be mistaken for a finished one.
- **Acceptance: the segmenter reproduced the four hand-built bp35 records exactly, first run** —
  cuts, frame refs, measured numbers, level, `last_action`/`last_result`. No disagreement to
  adjudicate.

Four corrections that came out of doing it, worth more than the code:

1. **Line numbers do not transfer between builds of the same game.** `ft09` settles it: two
   builds with byte-identical dispatch code, citation still off by 22 lines from an added
   licence header. Semantics transfer; citations must be re-derived per build.
2. **A branching action must not be cited at one of its branches.** Running the segmenter on
   cn04 found the segmenter citing `ACTION5`'s rotation call — when the entire cn04 finding is
   that ACTION5 rotates some parts and expands others. Citation now stops at the branch and
   lists the sites as `branch-dependent`.
3. **bp35 declares `available_actions = [3,4,6,7]`**, and its move handler reads only the sign
   of `dx` — so ACTION1, ACTION2 and ACTION3 are all a step left, and ACTION5 is literally
   `pass`. The earlier hand-written table implied otherwise.
4. **`arcengine` is not vendored**, so only bp35 and lf52 can cite `ACTION7`/`RESET` to a line.
   Elsewhere those rows are described, not cited — marked uncitable rather than faked.

**Not done:** passes C, D and E. No annotation, no recordings pulled for the selected runs, no
enum widened. `wa30`, `lp85`, `ls20` and `lf52` have source but **no recording on disk**, so
their tables are unchecked against play. The `camera_shift` / `extent_change` heuristics are the
weakest output and need pass D to confirm. `args` mapping `row=y, col=x` is an **unverified
assumption**, flagged in the docstring and covered by no test.

**81 tests pass**, up from 46. Nine guards were poison-checked — each made to fail, confirmed by
its message, then restored.

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
