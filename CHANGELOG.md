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
| 4 | segment and label the corpus | **started** — A and B on `main`, first D pass run on lp85 and blocked on `action_role_source` for RESET; C/E not begun |

**What exists right now.** 101 tests (59 + 11 + 31 across `test_decision_step_validator`,
`test_dispatch_tables`, `test_segment`). 278 human replay guids inventoried across two manifests
that are deliberately not merged, plus 250 leaderboard rows that carry no guid and never can be
fetched. 9 recordings on disk plus 15 for as66 — this line read `8` before the `ka59` and `lp85`
rows landed and the count was already one high; `ls */*.ndjson` reports 9 live-build recordings
now and reported 7 then. **6 labelled records** across 3 games — a demonstration of shape, not a corpus. A 7th pass produced 6 more that `validate.py` rejects for a reason no annotator can fix; see the lp85 entry below. `tools/segment.py` now emits the
mechanical portion of a record (cuts, frame refs, measured outcome, source citation) so that
annotation is three judgment fields rather than a whole record.

**The one rule that governs step 4.** A run counts only if its `game_id` is **still the live
build** — an early replay is a replay of a different game. That leaves **100 of the blog's 250**
and **23 of the Boss's 28**, and every current build has game source, so citation is no longer a
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

### Schema 0.2: `run_ended`, and the cull is per level not per run

**The gap is closed.** `last_result` gained `run_ended`, so a record can finally say "that action
ended the run". Without it a post-death record read exactly like an ordinary step, which in a
corpus built to teach recovery after being wrong was the one thing it must never fail to say.
Field add, so `schema_version` goes to **0.2**; 0.1 reserved that number for the per-game
`boundary_reason` redesign and the reservation is **released rather than quietly ignored** -
this arrived first, and versions are cheaper than two meanings for one number.

The segmenter measures it: a **flip** to `GAME_OVER`, not the presence of it. The five rows of
the bp35 recording that sit at `GAME_OVER` because the run was already over would otherwise each
be read as a fresh death - five markers on one death. Measured across the committed records, one
carries it: the row where the player has just been killed and is about to try the undo that
fails. Every fixture and record migrated; the version-drift fixture moved to 0.3 so it keeps
failing for the reason it is named for rather than quietly becoming valid.

**The cull, and the Boss's question that forced it.** Asked why we would want human runs that
don't win. Mostly right, and the flag was wrong: `teaches_recovery` marked any falsified
expectation, including the death spiral on the level the player never cleared. Weighting a
training mix towards those teaches flailing.

The unit is the **level**, not the run - the same rule the distiller already applies to its own
play. A stumble on a level that was then cleared is a recovery that demonstrably worked; a
stumble on the level the player died on is flailing. Measured on the eligible material: **only 2
of 100 published runs cleared nothing at all**, and the 48 that never won still hold **229 of the
615 solved levels** - 37% of the material. Culling those runs wholesale would throw away more
than a third of the corpus; culling the unsolved levels inside them throws away exactly the
flailing. `--keep-unsolved` exists and is off.

Tests 112 -> 121. Two more guards poison-checked: the recovery gate, and culling levels rather
than runs.

---

### The bridge: a finished record becomes a training example

`tools/build_sft.py`. Steps 1-4 built a labelling machine whose output nothing downstream read -
the distiller's own SFT builder has never heard of this corpus, so a finished record was a
document, not training data. This closes that, and it was built before more annotation on
purpose: annotating at volume without knowing a record can be trained on is the expensive way to
find out it cannot.

**What it is for.** The distiller rejection-samples the harness's own play and keeps only turns
on **solved** levels, so it structurally discards every moment where a player was wrong and then
fixed it. That moment is the one thing this corpus holds and nothing else in the tree can
produce. Examples carrying it are marked `teaches_recovery` so a training mix can weight them.
That flag is the payload, not a convenience.

**It runs.** All five committed records convert; three carry a falsified expectation and one
carries the full arc - a fatal step, an undo that returns nothing on a dead board, and the reset
that recovers - with the correction **observed in the recording**, not reasoned out by an
annotator.

**Two things are taken from the harness rather than invented, because getting them wrong is
train/serve skew:** the board is rendered by the same function that renders it at serve time, and
actions are emitted in model vocabulary. The system prompt is deliberately **not** - the live one
is bound to the tool loop and is config-dependent, so it is a flag, and every example records
which prompt built it. Running a real fine-tune on the built-in stand-in would be a skewed
fine-tune, and the output says so on every row.

**A defect the tests found, not review.** Annotators write records against the game source, so
the remembered mechanics and the rationale say `ACTION3` - while the model must answer `LEFT` and
has never seen an engine name. The prose reads perfectly well either way, which is why nothing
but an assertion catches it. Engine names are now translated everywhere the model reads, and
`ACTION7`/`RESET` are left alone because those are already the model's own names for them.

`FrameResolver` gained `resolve()` - `check()` said whether a reference was sound but could not
hand back the grid, and the alternative was a second recording reader. Same cache, same path
walk, and it raises rather than returning a board from a row nobody asked for.

Tests 88 -> 112. Three guards poison-checked: prose translation, the unfinished-record refusal,
and taking the settled frame rather than the first.

**Not done:** no new annotation, no recordings pulled, no schema change. One real gap remains and
it is now the binding one - a record cannot say "that action ended the run", which is exactly the
signal the recovery examples exist to teach.

---


### The ka59 and lp85 wins, the undo survey, and a RESET that cannot be cited

Committed direct to `main` at the Boss's instruction. Three pieces of work; the third one
stopped short of its target on purpose and the stop is the interesting part.

**1. Two rows, both re-fetched rather than transcribed.** `ka59-38d34dbb` /
`1333b2ee-…` (WIN, 7 levels, 598 actions, 2 resets, 84.574) and `lp85-305b61c3` /
`129ddf21-…` (WIN, 8 levels, 415 actions, 6 resets, 76.389). Every field was pulled from
`/api/sessions` at ingest and compared against the analysis notes that proposed them; all
agreed. Attribution is a checked `card_id` match against a fresh `/api/user/scorecards` pull —
both cards carry `user_name: "Mark"`. Recordings on disk, gitignored, both reconciling:
`599 = 1 + 598 + 0` with 3 RESET rows, `416 = 1 + 415 + 0` with 7.

`lp85` pins the reconcile rule's third term from the side `g50t` could not. It holds the only
`GAME_OVER` row in any first-party recording (175), and the row after it is a `RESET` that
**executed**, so it counts as an action and the dead-row term stays 0. A rule that counted every
row following a `GAME_OVER` would read 415 as 414.

**Five derived fields were stranded by the row count, not three.** Two are new drift from this
change; three were already stale. `README.md`'s eligibility table read `20 | 25` against a test
asserting `21 | 26`, left behind by the 18:00 `g50t` row. The step-4 plan's §0 table read
`20 | 25 | 16 | 64`, and its `games` and `resets` columns count the *eligible* subset — which
nothing stated, recovered by replaying the definition against the 25-row manifest. This file's
own standing status said 8 recordings on disk when there were 7. Everything is recomputed from
the rows now.

**2. Undo is a per-game design axis, not a platform affordance.**
`docs/trace-findings/2026-09-15-undo-is-not-a-platform-default.md` surveys `ACTION7` across all
25 live builds with a `file:line` for every one. **6 offer it** — `ar25`, `bp35`, `lf52`,
`sb26`, `sk48`, `su15` — and **19 do not**, with zero occurrences of `GameAction.ACTION7` in all
nineteen sources. The Retrodict harness's "prefer undo over RESET" rule is therefore not risky
advice on 19 of 25 games; it is **unimplementable**. This also promotes the earlier `as66`
observation from a quirk of a withdrawn game to the majority case.

Derived twice, because static enumeration under-reports and we can prove it: `cn04` passes no
`available_actions` at all (`cn04.py:824`), `arcengine` is not vendored, and `:1171`'s
`[1,2,3,4,5]` is a filter *over* the offered set rather than the set. Static would have said
five actions; row 0 of its recording says six. The guard that makes the 19 negatives safe is the
whole-file `GameAction.ACTION7` grep, not the declaration. Two decoys are documented so a
word-search does not re-find them: `ls20`'s `_undo_x`/`_undo_y` is the engine rolling NPC movers
back on a blocked move (`ls20.py:1947`, its only call site), and `sc25`'s `_undo_state`
(`sc25.py:1833`) is assigned once and never read.

**3. `lp85`'s loss condition is a step budget — and its RESET steps cannot be labelled.**
`docs/trace-findings/2026-09-15-lp85-step-budget-and-the-uncitable-reset.md`.

The mechanic first, because it is the durable half. `lp85` has no hazard: you lose by running
out of steps on a level (`lp85.py:21416`, counter at `:21282-21284`). The counter **decrements
then tests**, so the step that zeroes it *is* the losing step — there is no state between "one
left" and `GAME_OVER` — and the win test runs first (`:21412`), so a final click that clears the
level still clears it. Column 0 of the frame is a 64-cell bar rendering the consumed
**fraction** of the budget — it advances by `64/StepCounter` cells per **effective** click and
never on a click that hit no button, which is 1 cell per click on levels 2–8 and **5 on level
1**, so cells read as steps only where the budget is 64. A first draft of the write-up claimed
1:1 generally; it was wrong and the correction is in the doc. Confirmed across the recording:
a no-op click does not advance the bar (rows 172 → 173), `63 → 64` at the death, and every one
of the six RESETs refills it to zero consumed. **20 of the 101 clicks on level 6 and 34 of the
157 on level 8 did nothing at all**, and the bar is the only feedback channel that distinguishes
them. This makes `lp85` the second game after `bp35` whose recovery
economics are measured rather than assumed, and the two agree where they overlap: RESET refunds
the whole level budget at no step cost. The undo doc's "not measured" line now points here.

It also reframes the five level-8 resets. At **11, 19, 13, 42 and 16 of 64** steps consumed,
none was under budget pressure — they are plans abandoned as unwinnable, on a game where RESET
is the only way to unwind an arrangement because there is no undo.

**The stop.** `tools/segment.py` cut all seven wanted rows without refusing anything, but six of
the seven are `RESET` steps, and it emits `UNCITABLE: RESET has no dispatch branch in …` for
every one — correctly: `Lp85.step` has exactly one branch, `ACTION6`, and RESET is handled by
`arcengine`, which is not vendored. `schema.json`'s `action_role_source` pattern
`^[^\s:]+:[0-9]+([ \t].*)?$` admits no spelling of "engine-level, source not in this repo", so
`validate.py` rejects all six. **Nothing was overridden and no schema or tool was changed** —
the standing rule is to stop and report. The six records are carried verbatim in the write-up,
because `*.candidate.jsonl` is gitignored and they would otherwise have been lost.

This is not an `lp85` quirk. The one RESET record the corpus already holds validates only
because `bp35` *happens* to carry its own `GameAction.RESET` branch (`bp35.py:4529`). Put beside
the undo survey it composes into a selection effect: on 19 of 25 builds RESET is the sole
recovery primitive, recovery-after-falsification is the metric this corpus exists to move, and
recovery steps can currently only be labelled on builds that happen to vendor a RESET branch.
Four options are listed for whoever owns the call; none is implemented.

**What did land from pass 3:** one record,
`lp85-305b61c3__129ddf21-…__l6-budget-exhaustion.jsonl`, row 175, tier `negative`, passing
`validate.py --require-frame-resolution`. It is the **falsified half of a pair whose corrected
half is blocked** and is not the pair that was asked for.


### A second g50t win, a caveat withdrawn, and the leaderboard that withdrew it

Committed direct to `main` at the Boss's instruction. Three things, one of which is a
correction to this repo's own prose rather than to anything upstream.

**1. The Boss won `g50t-5849a774` a second time** — guid `58483738-cfaf-4e57-8c55-4c9c593bbab5`,
7 levels, 536 actions, 8 resets, score 82.124. Row 26 of `first-party-replays.json`.
Attribution is a checked match, not an inference from the date: the session document's
`card_id` `475182c6-…` was looked up in a fresh `/api/user/scorecards` pull and that card carries
`user_name: "Mark"`. The 70 MB recording stays gitignored, verified with `git check-ignore`
before the commit.

That row made three things visible that nothing had checked:

- **`_provenance.total_actions` had drifted.** It read `5480` against rows summing to `6933` —
  the sum through the `cn04` row. The 15:20 ET refresh that appended `dc22` and `ft09` updated
  `count`, `games` and `state_counts` and left `total_actions` behind. The three that stayed
  correct are exactly the three `ReplayManifestTests` asserted; the one that drifted is the one
  nothing asserted. The file's own doctrine — *"a summary nobody checks is just a comment that
  looks like data"* — was true of the file. Now `7469`, recomputed, with a test.
- **The reconcile rule's third term is not a bp35 quirk.** This recording carries one of its
  own: row 347, an `ACTION2` sent to a board the previous row had already flipped to
  `GAME_OVER`, empty frame list, uncounted by the API. `538 − 1 boot − 1 dead = 536` actions and
  `9 RESET rows − 1 = 8` resets; the rule holds exactly. One recording had the behaviour, so it
  got attributed to that recording's game *and* that recording's action — a second game and a
  second action is the cheapest possible correction of a sample-size-one generalisation.
  `RecordingRowReconcileTests.EXPECTED` is keyed by guid now, since g50t is the first game with
  two recordings on disk.
- **It is the only same-player-same-build pair either manifest holds.** Against the shared
  baseline `[78,175,179,230,96,54,67]`, `level_actions` went `[43,67,68,55,173,62,65]` →
  `[17,31,74,94,186,91,43]`. Levels 1, 2 and 7 improved, 3, 4 and 6 got worse, and the total
  barely moved — 533 → 536 — because the two cancelled. **Levels 5 and 6 are the only ones over
  baseline on either run**, 1.80× then 1.94× and 1.15× then 1.69×, and the API's own
  `level_scores` name the same two: 26.6 and 35.2 against 115 everywhere else. Learning showed
  up as *redistribution*, not net reduction.

**2. A caveat in `published-replays.json` was wrong and is withdrawn.** It said the blog's 250
were *"a curated best-of, not a random sample of human play."* The best-of half was an inference
from the list's shape and nobody had measured it. The blog's own heading was **not** re-read and
is not asserted either way; what is claimed is a comparison.

**3. `datasets/decision-steps/human-leaderboards.json`** is what that comparison is against —
`POST arcprize.org/api/leaderboards/<4-char id>`, **unauthenticated**, pulled for all 25 current
builds plus `as66`. A corrected caveat citing numbers nobody can re-read is not a correction, so
the numbers are committed.

| | leaderboard (250 rows) | blog set (250 rows) |
|---|---|---|
| wins | 250 / 250 | 139 / 250 |
| score | 100 on every row | — |
| resets | non-zero on 24, max 6 | max 30 |
| median actions, on the 10 comparable builds | 29,179 total | 64,425 total — **2.21×** |

Higher on *every one* of the ten, 1.55× to 2.93×. **The consequence cuts the opposite way to
the caveat it replaces: the blog set is not speedrun play.** 111 of its 250 rows are not wins
and its wins take about twice the actions — exploration, wrong turns and recovery, which is
exactly what this corpus wants and exactly what a best-of would have stripped out. It is still
not a *random* sample; nothing measured says how the 250 were chosen, only that it was not for
speed.

**Disjointness is by timestamp, not action count**, because there is no id to match on: every
blog row is `published_at 2026-03-22` and no leaderboard row is. That settles all 25 games at
once. Action ranges do not — `g50t`, `cd82` and `lp85` are disjoint, `bp35`, `ft09` and `sb26`
overlap. The first framing tried was the ranges; it does not generalise, and the file says so.

Three limits are written into the new file rather than left to be rediscovered: a leaderboard
row carries a `user_name` and **no guid**, so those 250 runs are visible and permanently
unfetchable and nothing may try to label or join them; `baseline_total_actions` is a per-**game**
constant, established by the Boss's two g50t runs reporting identical
`level_baseline_actions` while their `level_actions` differed on all seven levels; and
`as66-821a4dcad9c2` returns **zero** rows while all 25 current builds return exactly ten — HTTP
200, well-formed, empty — recorded as observed, with *why* explicitly not guessed at. That last
is now a row in the as66 finding doc as an independent surface that omits the game.

`scripts.test_decision_step_validator`: **52 tests → 59**, all passing. Both new guards
poison-checked — a planted `guid` on a leaderboard row fails with the intended message, an
`as66` `row_count` of 1 fails the zero-rows assertion — and both restored.

---

## 2026-09-15

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
