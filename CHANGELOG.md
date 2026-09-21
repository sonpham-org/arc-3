<!--
Author: Claude Opus 5 (Bubba)
Date: 15-September-2026
PURPOSE: Running changelog for the decision-step corpus work in this repo, newest first.
Exists so a reviewer joining cold can see where the work stands without reading fifteen pull
requests. Covers the corpus pipeline (datasets/decision-steps/, tools/replay_scrape.py,
scripts/test_decision_step_validator.py) and its trace findings. It does NOT change
the harnesses, which are frozen artifacts; where an entry documents a harness defect it is a
written finding about code this work leaves untouched, never a record of a change to it. The
in-tree `ARC3-Inference/` harness is a different matter: the 16-Sep RESET-guard entry below is
a real change to it, and further entries may be.
SRP/DRY check: Pass — plans live in docs/plans/ and docs/trace-findings/, schema semantics in
datasets/decision-steps/SCHEMA.md. This file only records what changed, when, and why.
-->

# Changelog

Newest first. Versioning is date-based; this work is pre-1.0 and the schema is pinned at
`0.2` — `run_ended` took that number in `7dcaa62`, and the per-game `boundary_reason` redesign
that had reserved it no longer has a number reserved.

---

## 21-Sep-2026 — Tuning panels for the rest of the catalog, measured by a script instead of by hand

`scripts/measure_game_params.py`, `scripts/verify_game_params.py`,
`scripts/serve_games_local.py`, and 60 new `docs/static/games/params/*.json`. No change to
`games-tuning.js` or any other shipped code: the runtime contract from 20-Sep is unchanged and
this only writes data for it.

The five specs from 20-Sep were hand-measured in a browser over about half an hour. That does
not reach the rest of the catalog, so the measuring is now a script. It parses each game's head
source, collects the module-level `NAME = <int>` assignments the patcher can actually rewrite,
and scans outward from each published value to find how far it can move before the game stops
loading, resetting, stepping or drawing a legal 64x64 frame. **60 games got a panel, 334
sliders now ship across 65 specs.** A full run is 71 seconds.

**The catalog is 191 trees; only 69 of them can ever show a panel.** This is the number worth
arguing with, and it is not a limit of the generator:

- **78 games are in blind families** (53 `arena`, 25 `research`). `games-tuning.js` refuses to
  attach a panel to a blind family at all, because a list of named constants is a second way to
  read a game's shape — the leak `BLIND_FAMILIES` exists to stop. Measuring them would produce
  files nothing renders, so they are skipped, and `--include-blind` is there for when that
  product decision changes. **It is a product decision, not a technical one.**
- **44 are retired** (`ai-generated`), already off the Games page.
- Of the 69 left: 60 got a spec, 5 are the hand-written ones, and 4 got nothing.

**The five hand-written specs are byte-identical.** They are on an explicit skip list with the
reason, not regenerated-and-compared, because this script's derived English is honestly worse
than a person's. They remain the quality bar.

**A measured range here is a safety band, not a taste band, and the two are different things.**
The 20-Sep specs record how far a constant can move and still *look right*. This records how far
it can move before it *breaks*, which is wider. Measured on br10, `CELL` loads cleanly from 4 to
24 with an unchanging colour count and a smoothly rising occupancy: there is no discontinuity
anywhere near the hand-chosen maximum of 10, so no headless check can find that edge. Clamping
to some fraction of the hand-written precedent would have been the guess the whole approach
exists to avoid, so the band is the honest one and it is looser. Against the two hand-measured
games the generator recovers **every** knob a person shipped — br10 9 of 9, hg51 5 of 5 — with
ranges that contain the hand-chosen ones.

One range rule is a contract decision rather than a measurement, and is labelled as such in the
script: no slider is handed a value below `min(0, default)`. Negative geometry constants pass
every check available — at hg51's `X0 = -6` the occupancy is *identical* to `X0 = 0` — because
numpy's negative indexing silently wraps the drawing to the far side of the screen instead of
raising. That is a bug surface, not a tuning range. Colour-named constants are likewise held to
the engine's sixteen colours; a padding colour survived to 45 only because it never reached a
frame to be validated.

**Labels and notes are mechanically derived, and that is a real drop from five hand-written
specs.** Stated plainly rather than slipped in:

- `note` is the author's own trailing comment on the assignment line, verbatim, and is **omitted
  entirely** when there is none. 117 of 300 generated sliders carry one. A missing note is
  honest; "Slot" is noise wearing a lab coat.
- `label` comes from the constant name through a small abbreviation map, so it reads like "Move
  frames" and "Gate colour" but will never read as well as a person's. A short unknown part stays
  upper-case (`GL`, `CW`) so an abbreviation looks like one instead of a mangled word.
- `group` is keyword-classified into the four groups the hand-written specs already use.
  Misgroupings survive: a few of ts01's colour names land in "Tuning" because they are not in the
  vocabulary. It puts a slider under the wrong heading and nothing worse.
- Panels are capped at 12 sliders — the size of the largest hand-written spec — with at most 4
  palette entries, so a colour-heavy game cannot crowd out its geometry and rules. 17 games hit
  the cap; 180 measured knobs were left out by it. Knobs a probe watched change the game take cap
  slots first, then commented ones.

**A knob that no probe saw do anything is still shipped when there is room, and that is
deliberate.** An earlier version dropped them and lost br10's `FALL` and hg51's `WIN_HOLD` — real
knobs the hand pass measured, invisible to a blind ten-action probe because `WIN_HOLD` only fires
on a won level. A filter that rejects known ground truth is a wrong filter, so the only rejection
on that axis is an AST one: a constant the module never reads cannot do anything. 159 shipped
sliders are unproven by probe in that sense. The exception is a panel where *nothing* moved,
which would be sliders that visibly do nothing: `cn04-2fe56bfb` is the catalog's only one and
gets no file. CPython flagged it and the browser independently agreed.

**Every slider was turned in a real browser, and that is the gate.** Ranges are measured in
CPython 3.13 against a locally installed arcengine; the site runs Pyodide, a different
interpreter and a different build, so a CPython measurement is a claim and not a result.
`verify_game_params.py` drives Chromium over the play view and checks four things per spec: every
declared knob renders, every declared minimum and maximum loads with no fault reported, turning a
knob changes the board, and "Reset to defaults" brings the opening board back. **65 of 65 specs
pass**, including the five hand-written ones. Two findings came out of it that a spot-check of ten
would have missed, and one non-finding:

- `cn04-2fe56bfb`'s inert panel, above.
- A run that reused one browser page produced **two** false results at once: slider counts
  belonging to the previous game, and three games "failing" because an earlier game's
  unrecoverable rollback had wedged the Pyodide worker for the rest of the session. Every game now
  gets a new page, closed after. The cost is a Pyodide boot each time.
- The non-finding: ts01's `DEFAULT_FPS = 1` appeared to fail in Pyodide but not CPython, which
  would have meant the whole measuring approach was unsound. On a fresh page it passes twice over.
  It was the wedged worker above, not a divergence.

**Pre-existing runtime finding, not a blocker.** On dw01, `T_WALL = 2` — one past its measured
maximum — hangs the engine hard enough that `games-tuning.js` cannot reload the last good values
either, and the panel correctly falls back to "Could not be put back — reload the page". It is
unreachable from the shipped slider, which stops at 1. Recorded because the rollback path has a
floor, not because anything here crosses it.

**The official 25 are their own bucket, easy to cut.** 21 of them have a spec and it is thin:
two template constants, `BACKGROUND_COLOR` and `PADDING_COLOR`, 44 sliders across all 21. Four
games have no spec at all — `bp35`, `ft09` and `lf52` declare no patchable scalar, and `cn04` is
the inert one. Deleting the 21 official specs would be one `rm` and would cost nothing else.

**Specs go stale by design, which is why the generator is committed and re-runnable.** The
evolution loop rewrites these sources continuously, so a spec written for v2 will meet v4. Each
file records the `sha256` it was measured from, so staleness can be spotted without re-measuring,
and the runtime already degrades safely: a knob that no longer resolves to one scalar assignment
is dropped from the panel rather than applied blind. An evolved game loses sliders, never breaks.
Measurements are cached under `scratch/` by `(gameId, sha256)`, so a re-run only measures what
moved. The full sequence, and note it spans two interpreters — the generator needs 3.13 for
arcengine and `match`, the verifier needs 3.14 for playwright:

```
python3.13 scripts/serve_games_local.py &          # docs/ locally, /api/ and /data/ proxied live
python3.13 scripts/measure_game_params.py          # 71s, writes the specs
python3.14 scripts/verify_game_params.py           # ~7min, exit 1 if any spec fails
```

`serve_games_local.py` exists because `docs/static/games/manifest.json` is a stale fallback
predating the evolution trees, so a purely static local server cannot reach a game the API knows
about. It serves the working tree's specs against the live catalog.

---

## 20-Sep-2026 — Games play view: a per-game tuning panel in the sidebar

`docs/static/games/params/*.json`, `docs/static/js/games-tuning.js`, wiring in
`games-play.js`, `index.html` and `games.css`. Five games only -- mx78, mc18, br10, mb64,
hg51 -- and no backend change, no new endpoint, no generator.

The panel turns a game's own module-level constants while it is on screen. A knob rewrites the
constant's line in the source text the player was loaded from and hands the whole module back
to `gameLoad()`, which re-execs it in the Pyodide worker; derived constants recompute for free
because the module is re-imported (hg51's `MAST = 3 * NOTCH + 2`). Which constants a game
offers is **data, not code** -- one JSON file per game, so controlled procedural generation can
later write these files rather than patch a renderer.

What keeps it from lying about a catalog that moves under it:

- **Drift.** The evolution loop rewrites these games (mx78 reached v2 and mc18 v3 while this
  was being written). Every knob is matched against the bytes actually fetched, and one that no
  longer resolves to exactly one line-anchored scalar assignment is dropped from the panel
  rather than applied blind. An evolved game degrades to fewer sliders, never to a broken panel.
- **What will not be patched.** Tuple unpacks (`CELL, GRID, CAP = 8, 8, 3`) and expressions
  (`CELL = 8 if hard else 6`) never match, so they cannot be silently rewritten into something
  that drops a branch. This is why **mc18 exposes no knobs at all**: it declares its geometry
  and palette entirely in tuple-unpack form. The panel says so instead of inventing one.
- **Rollback.** A bad value is a Python exception, not something we could have predicted. The
  last set of values that loaded is kept; a throw restores it, reloads with it, and prints the
  exception's last line in the panel. The player is never stranded on "FAILED TO LOAD" -- which
  is exactly why this path does not go through `loadVersion()`.

Ranges are measured, not guessed. Every knob in every spec was driven to each value in its
declared span in a real browser: all of them load. Three first guesses did not survive that and
were corrected -- hg51's `CELL` loads **only** at its published 5 (the level rows are written
five pixels per cell), `X0` gives out past 5, `HUD_Y` below 49 -- and hg51's `COLS` turned out
to be declared and never read, so it is not offered. Knob counts: mx78 8, br10 9, mb64 12,
hg51 5, mc18 0.

---

## 19-Sep-2026 — ARC-3 LoRA round 4 spec: train on the Boss's reasoning, not his moves

`docs/plans/2026-09-19-arc3-lora-round4-spec.md`. Spec only — no training, no eval, no GPU
work. Rounds 1-3 all trained on teachers that carried no reasoning, and round 3's gameplay
collapsed on the held-out fence (7 levels -> 2, PR #59). The spec quantifies why from round
3's own `train_report.json`: **94,012 supervised tokens across 2,281 assistant turns, 41.2
per turn** — an action call and nothing else.

What it establishes, measured against the artifacts rather than recalled:

- **`arc-explainer/shared/arc3Games/playerObservations` has never been read by any trainer.**
  `recordings_to_sft.py` opens arc-explainer only for run identity; `extract_sft.py` never
  touches it; the sole consumer is the oracle prompt-injection path. No branch or PR through
  #59 has built this.
- **The join lands.** Round 3's 89 records join to per-game notes at **100% by game**
  (2,281/2,281 turns) but only **11% by game+level** (10/89). Game-scoped is the join.
- **The corpus is thinner than assumed.** 63 notes: 28 joinable, 18 fenced, 17 on games with
  no replay turns. `expected` — the field carrying a mental model — appears in **5 of 63**,
  and in **2** notes on trainable games. ~11-13 notes survive a structural rule-leak filter.
- **Round 3 honoured the fence by construction, via an optional flag.** `recordings_to_sft.py`
  has `--exclude-games`; the round-3 corpus was built with the full fence list (130 records
  unfenced → 89 fenced, per the converter write-up §9–10), and the trained corpus has 0 fence
  records. The flag has no default, so round 4's builder makes `--fence` required. (The first
  cut of this spec said there was no fence filter and the fence held by luck; that was wrong.)
- **Two corrections.** `mechanicsBreakdown` is 297 entries with **zero** `level:` fields — 200
  sit under `// ---- Level N ----` comments; level scoping there is convention, not schema.
  And PR #59's "deliberates half as long" is a **derived quantity**: every config has
  `max_steps: null`, and the two arms' total turn time agrees to **5.4 seconds out of 37,790**
  (37,785.6s base / 37,791.0s adapter) — a hard wall-clock deadline. Seconds-per-turn is
  therefore `budget / turns`, and the real finding is that the adapter took ~2x the turns and
  cleared 5 fewer levels.
- **Eval budget resolved against a108.** `a108.qwen38.baseline.json` (out of tree, on a108)
  and both round-3 `run_config.json` files say 90 min/game at 7 lanes, so one pass is 90 min
  and 3 arms × 3 passes is ~13.5h, consistent with PR #59's ~9h for two arms. The first cut
  of this spec priced a pass at 5.25–10.5h from the in-tree a108 configs, which are for a
  different model and did not run.
- **The ladder lesson is epoch-normalized.** Round 2's "gain done by step 16" was 29 records
  at 14.5 steps/epoch — about 1.1 epochs. Round 4's corpus runs 44.5 steps/epoch, so copying
  step 16 would stop at 0.36 epochs. Ladder is specced in epoch fractions, capped at 2.

Recommended primary arm: **rationale-conditioned SFT over round 3's 89 records**, gated behind
a prompt-time control arm that costs one eval pass and may answer the question without any
training. Primary metric is gameplay on the 7 fenced games, n=3 per arm with round 3 as an
arm; held-out CE is demoted to a smoke test, discredited by round 2 (CE win, gameplay
unmeasured) and round 3 (gameplay collapse). Falsifier stated: if round 4 again shortens
per-turn reasoning without improving clearance, the teacher is not the problem.

---

---

## 20-Sep-2026 (later) — one page, one field: the review is the comment

The review form asked for four ratings, eleven flags, five text boxes and a verdict, and the
game page had a second comment box beside it. Son: "I don't need all of this, just one big
comment field is enough." So a review is now one free-text comment (plus what the player did,
which is captured automatically), the separate comments table is dropped again, and a game's
page lists its reviews as its comments. The split "Play" and "Review" buttons are one action:
you open a game, play it, and the comment box is on the same page. The queue view keeps a
Previous game button, so you can step back without going home. (Claude Opus 5)

---

## 20-Sep-2026 — comments on a game, and a tick that feeds the training pipeline

The Games page now carries the team's comments on each game, newest first, stored in Postgres
(`arc3_game_comments`) and team-only like change notes. Beside them, a "Good to train" tick on
the version being played records that a person judged those exact bytes fit for training, with
who and when (`train_ok` on `arc3_game_versions`).

The training pipeline reads the ticked set through `GET /api/v1/games/training-set` with the
publish token, which answers each version's content-addressed source URL. The tick is per
version, not per game: the pipeline trains on exact bytes, and the next version of the same
game may not be fit at all. (Claude Opus 5)

---

## 19-Sep-2026 — the game evolution loop, recovered and reformed; uploads are vetted

Codex's pair glow-up loop had only ever lived in a local workspace. Its program, rubric,
QC, recovery and isolation rules were in two unpushed commits, and its job was paused.
They are now in `research/game-evolution/recovered/`. The September fix rounds and the
clarity loop that shaped them are summarised alongside. Game-specific records stay out,
because those games are shown blind. The loop is reformed as v4 (`research/game-evolution/README.md`)
into four steps: grow, pair far apart, glow up, and make it playable. The last step is new.
It makes the two fix rounds permanent: games must not die right away, level 1 must teach,
and objects move whole and briefly.

`scripts/vet_game.py` is the new vetting gate. Before this, the upload API accepted any
bytes and the CLI only tried to draw a thumbnail. The gate plays the game in the site's
engine and checks:
- a winning trace clears every level;
- determinism and Undo-safety;
- RESET;
- level-1 length and safety;
- early deaths;
- random-play resistance on levels 2 and up;
- frames per action.

It writes a report bound to the source's sha256. `publish_game_versions.py publish` now
refuses without a passing report for the same bytes, and records its summary in the
version's provenance. `scripts/play_game.py` is the cold-start play tool, and
`scripts/evolution_loop.py` does the pool arithmetic: status, nearest games, anchors, pairs,
and the ledger. (Claude Opus 5)

## 19-Sep-2026 — the slippery seven's documentation hole is marked closed

`docs/trace-findings/2026-09-17-the-slippery-seven.md` §7 still said dc22, m0r0 and tr87 had
no mechanic page. They got one the same day, in
`docs/trace-findings/2026-09-17-dc22-m0r0-tr87-what-they-are.md`. §7 now says so at the top;
the original text is left as written. (Claude Opus 5)

## 19-Sep-2026 — HARNESS-NOTES.md, the one page to read first

**What.** A single always-current page at the repo root: seven harness recommendations in
priority order, each citing the dated write-up that owns its evidence; what is known; what is
running or blocked; the open questions; where things are. Written because Son asked for one
place his local agents can read our feedback from, and seventy dated files is not that place.
Rule from here: every write-up that lands under `docs/` updates this page the same day.

## 18-Sep-2026 — the oracle marker guard was counting the log, not the prompt

## 18-Sep-2026 — the Games page shows every game as an evolution tree, and collects reviews

**What.** The Games tab is now one row per game tree instead of a grid of cards. Each row has
a big frozen thumbnail of the current version on the left and, to its right, the tree from seed
to latest version, scrolling sideways. Each node shows who made it (GPT, Claude, a person,
imported), when, its feedback and, for the signed-in team, the reason for the change. A new
**Feedback games** button runs a play-then-review loop, stored in a new database table.

- **Versions are uploaded, not deployed.** `PUT /api/v1/games/publication` (with
  `ARC3_PUBLISH_TOKEN`, like traces) stores one immutable, content-addressed version:
  `<game_id>@<sha12>`, the stamp arc-explainer already records as `source_version`. Rows go to
  Postgres (`railway/games_schema.sql`) and files to `/srv/data/_games/`.
  `scripts/publish_game_versions.py` handles `publish` (one evolution), `sync` (the whole
  catalog with its git history) and `feedback` (reviews for the next pass).
- **Seed, revision, branch.** A revision continues its parent's line even under a new id; a
  branch is a new game and starts its own line. A line's latest version is its current one.
- **Reviews.** Anyone can review. Signed-in reviews are `team` and always rank ahead of
  `public` ones; public ones are rate limited and hideable. Flag names reuse arc-explainer's
  six, so the two sites' data joins.
- **Access.** oauth2-proxy gains exactly four skip-auth routes: `^/api/v1/public/` (anonymous;
  never reads identity headers, never returns notes or review text), the two token routes, and
  `^/data/_games/` (game files). Everything else under `/api/v1/games/` needs sign-in.
- **Unchanged for mirrors.** `static/games/manifest.json` and `static/games/src/` are untouched;
  `/api/v1/public/games/manifest.json` serves the same shape for uploads that never touch Git.
- **Space is ACTION5.** Left unmapped, it scrolled the page away from the board.
- **Also 19-Sep, by request.** (1) theredbluepill's 252 games are off the page too, retired like
  the generator set. (2) Every version is credited to its **primary driver**: GPT-driven,
  Claude-driven, or Human-tuned. History is credited by family (`FAMILY_DRIVERS`): arena
  Claude-driven, glow-ups GPT-driven, in-house, research and official human-tuned. (3) The
  upload API takes **several parents** (`parent_version_ids`; the first places the version in
  its tree, the rest are dotted "also made from" links) and **idea links** (`idea_ids`). (4) An
  **ideas board** (team-only) on top of the Games page: 1,128 ideas from the GPT, Anthropic and
  Flash ledgers in `arc3_game_ideas`, as not explored yet / exploring / explored / dropped, with
  links to the games built from them. Machines load it with `PUT
  /api/v1/games/ideas/publication`, and the team moves cards. (5) `import-explainer` brings in
  arc.markbarney.net's 44 glow-ups, each under the generated game it came from, and its
  25-game research collection, with their git history from arc-explainer.
- **The 571 unreviewed `ai-generated` games are off the page** (19-Sep, by request: not worth
  playing). `sync` skips them and the static fallback drops them, which leaves 361 games: arena,
  in-house, official and community. They stay in `manifest.json`, so arc-explainer's "Fresh off
  the pipeline" mirror is unchanged.

**Why it matters.** Each change to a game now carries its reason, its author model and the
reviews of that exact build, which is the record an evolution loop needs. It still does not
measure whether a change moves the Kaggle score (AGENTS.md §5).



**What.** The oracle driver aborted itself 20 s into arm-O pass 1 on a108 (`max_occurrences_in_one_log=2`).
The second copy was `_write_prompt_log_snapshot`'s own `[TURN TRANSCRIPT SO FAR]` section
re-printing the same turn's `[USER PROMPT]`, so an arm-O log holds `1 + analysis_steps` copies — a
floor of 2 — and the assertion added in `67c03956d` was unsatisfiable by any arm-O pass. The wire
message lists (`*_requests.jsonl`, `message_count: 2`) carried exactly one copy on all seven games:
**the injection was never wrong.** `test_oracle_injection.py` missed it because it drove the real
writer with `transcript="(dry build)"`, a placeholder holding no rulebook.

- **`check_oracle_marker.sh`** now asks its two questions of two artifacts. *Treatment* (the
  missing-`export` check) still counts prompt-log files, `== expected`. *Retention* (the confound
  from build doc §3.3) moves to `*_requests.jsonl` and asserts no single request's message list
  carries the block more than once. The per-file figure is printed as `log_occurrences_max` with
  its construction stated, and is not asserted on.
- **Strictly stronger, not looser.** The retention check now reads the bytes sent to vLLM, and it
  accumulates one line per request, so by turn 5 it exercises `_persistent_history_messages` on
  the live duck/graft path — which the 20 s check never could against an empty history.
- **`test_oracle_injection.py`** feeds the writer a real turn transcript and adds a deliberate
  double-injection case (block put back into a retained turn); the guard refuses it, rc=1.
- **Nothing under `ARC3-Inference/inference/` changed** — `git diff origin/main -- ARC3-Inference/inference/`
  is empty, which is the proof that arm B's rendered prompt is byte-identical and that the banked
  `20260918_161821_qwen38-27b-oracle-b-p1` (247 wire requests, 0 rulebook copies) stands unre-run.
- The aborted O run is fenced with an `INVALID_MARKER_GUARD_ABORT` file and unbanked; it was a
  valid arm-O pass, but 20 s and one request per game is not a result.

**Why it matters.** Loosening this guard on preference rather than evidence would have poisoned
every number the experiment produces. Write-up, with the per-artifact evidence and the list of
what is still unverified: `docs/trace-findings/2026-09-18-oracle-marker-guard-artifact.md`.

## 18-Sep-2026 (later) — the oracle test is launched on a108, and LoRA round 3 is queued on a424

**What.** Step 4 of `docs/plans/2026-09-18-oracle-test-plan.md` §6, plus the round-3 training
launch. The driver is running and pass 1 is playing; there are no results in this entry.

- **Driver** (`ARC3-Inference/scripts/run_oracle_multipass.sh`). Sequential B/O passes over the
  slippery seven at the multipass operating point — 7 lanes, 90 min/game, `n_passes 1`,
  `qwen38-27b-nvfp4` against the already-serving vLLM. Passes never overlap, because lane
  contention correlates with the treatment if they do. Resumable: finished passes bank and a
  re-run with an extended `PASS_PLAN` skips them.
  **Not a flag on `run_style_multipass.sh`**: that driver selects games with
  `--kaggle-duck-public-harness`, which `_resolve_game_ids` refuses to combine with `--game`, so
  a seven-game run cannot reuse it.
- **Four passes, not eight.** Boss's instruction, taken literally: two per arm. Consequence
  recorded rather than argued — plan §4's "any game whose four O passes disagree with each other"
  disqualifier is not computable on two O passes.
- **Guards, per pass, ledger'd.** vLLM pid/`/health` before and after; `run_config.json` parity
  against pass 1 with `games` compared as a sorted set; and the treatment marker checked **twice**
  — once in flight as soon as all seven prompt logs exist (20 s on pass 1), once at the end. The
  in-flight check kills the harness tree and aborts the driver on a mismatch, because the failure
  this experiment dies of is a missing `export` on one of four launches and finding that out 90
  minutes later wastes the pass.
- **Every run name contains `oracle`, arm B included** — the arms share this run tree, so
  `extract_sft.py`'s `*-oracle-*` refusal must cover both. Verified by running the tool against
  all four dated dir names (exit 2 each) plus a non-oracle negative control (exit 0).
- **a108's tree is not a git checkout.** It has no `.git`, lacks two modules the repo has, and its
  `tool_agent.py` was 98,140 bytes / 38 methods against main's 113,101 / 43, so `git apply` could
  not be used and syncing the repo's files over would have changed **arm B's prompt**. New
  `ARC3-Inference/scripts/apply_oracle_patch_to_deployment.py` lands the six edits by exact-anchor
  match, refusing rather than guessing; the resulting diff is six insertions, zero deletions, one
  file. `test_oracle_injection.py` then passes **on a108 against a108's patched file**, which is
  what carries the build write-up's compaction and one-copy claims to the code that actually runs.
- **Read side** (`ARC3-Inference/scripts/collect_oracle_passes.sh`). Ledger plus per-game
  `levels_completed` / `final_score` / `state` per banked pass. No totals, by design.
- **LoRA round 3** (`ARC3-Inference/scripts/run_lora_round3.sh`) on the windowed human-demo corpus
  from PR #52 — 89 records / 2,281 turns, matching the published figures exactly, and re-verified
  with a424's own tokenizer (`over_max_seq 0`, `tokens_max 13,495`). Round 2 was **not** killed:
  its corpus is 40 **model-trace** records, not a superseded cut of the human demos, it was at
  step 44/58, and the round-2 write-up §7 forbids concurrent GPU jobs while its own Results
  section is still `PLACEHOLDER`. So round 3 waits on that pid and then starts. Hyperparameters are
  round 2's unchanged; only the checkpoint cadence is rescaled to 178 steps.

**Write-up.** `docs/trace-findings/2026-09-18-oracle-test-launch.md`, including the not-verified
list and one mistake made on a108 (a bare `uv run` resynced the shared venv; nothing broke, and
it was checked rather than assumed).

---

## 18-Sep-2026 — the oracle arm is built: rulebook renderer, injection, and the fence that comes first

**What.** Steps 1–3 of `docs/plans/2026-09-18-oracle-test-plan.md` §6. Nothing has been run.

- **Rulebook renderer** (`tools/render_rulebooks.py`). Turns `datasets/explainer-games/games.json`
  into one plain-text rulebook per public game: the `newRules` of every level, in level order,
  grouped by the level each rule starts on. Rules and nothing else — no images, Boss play notes,
  run data, code citations, categories or editorial prose — because the plan allows exactly one
  difference between the arms. 25 games, 527 rules, 93,822 characters. `as66` is refused, not
  silently fenced.
- **Arm O** (`harnesses/oracle-rules/`, env toggle `ARC3_ORACLE_RULES_DIR`). The rulebook leads
  every user turn, headed `Rules of this game, from a verified source.`. Not the system prompt,
  which is built once with no game id; and re-sent rather than injected once, because
  `_trim_messages_for_context` evicts the first user turn. It is stripped from turns filed into
  history, so exactly one copy is in context at any time — thirty retained turns of a 5,700-character
  rulebook would otherwise exceed the whole 32,768-token window and arm O would be trading real
  history for repeated text, a second difference between the arms. Measured cost of the strip:
  95.7% of the previous request still reused. `prompts.py` is untouched.
- **Contamination fence** (`ARC3-Inference/distill/README.md`, `distill/extract_sft.py`). Oracle
  transcripts carry the answer key. `extract_sft.py` now refuses any `--run-dir` whose own or
  parent name matches `*-oracle-*`, exit code 2, nothing written, no override flag. Plan §5 puts
  this before the first run rather than after, so it is where the work started.

**Guards.** `scripts/check_oracle_marker.sh` counts prompt logs carrying the marker, the shape
`run_style_multipass.sh` uses for the compact-reasoning arms; `scripts/test_oracle_injection.py`
proves it fires with no model, server or engine, at 7/0 for the slippery seven and 25/0 for all 25.

**One regression fixed on the way.** `distill/recordings_to_sft.py` calls `_build_user_prompt`
unbound with a duck-typed `self`; its `_LedgerShim` now declares `_oracle_rules_block = ""`, which
both keeps the human-demo SFT builder working and guarantees human demonstrations can never carry
the answer key into a corpus.

Write-up: `docs/trace-findings/2026-09-18-oracle-test-build.md`.

---

## 18-Sep-2026 — the LoRA adapter is evaluated, and round 1's own verdict was wrong

**What.** Round 1 trained an adapter, saw a flat loss curve, and wrote down the honest
conclusion available to it: *"'does nothing' is the hypothesis to beat."* Round 2 built the
measurement round 1 skipped, and the hypothesis is beaten. On 40 held-out records from six
games the adapter never saw, the round-1 adapter improves loss on **40 of 40** — token-weighted
0.558503 -> 0.548397, paired mean delta -0.011662, t = -14.81. Not one record got worse.

The flat training curve was a measurement artifact. Round 1 read learning off 8 step-losses
whose accumulation windows held different records each time, and its own note that the
within-window spread exceeded any step-to-step difference was the tell. Eight optimiser steps
did move a 27B; the training curve had no power to see it.

- `distill/eval_lora.py` (new): scores N adapter arms plus base against the held-out corpus.
  One model load with adapters toggled, so base is this model with the delta switched off
  rather than a second model; records outer / arms inner for bit-identical batches and
  incremental paired output; a gate that aborts rather than publish a null if an arm scores
  bit-identically to base; a generation round-trip; and a token-weighted aggregate reported
  separately from the record mean.
- `distill/sft_batch.py` (new): the label mask and chunked CE, shared by the trainer and the
  evaluator so both score with identical code. Verified behaviour-preserving -- round 2's
  micro-step 1 loss is 0.5440, byte-identical to round 1's.
- `distill/extract_sft.py`: `--only-games`, the inverse of `--exclude-games`, sharing the same
  matcher. Returns exactly the complement of round 1's fence (40 records / 298 turns / 28
  game-pass pairs against 40 / 440 / 36), with zero overlap on game code or record id.
- `distill/train_lora.py`: per-micro-step logging into the JSON report, so the same record
  seen once per epoch is a paired comparison rather than a moving average.
- `docs/trace-findings/2026-09-18-arc3-lora-round2-heldout-eval.md` (new): the round-2
  write-up, with its own NOT-VERIFIED list.

**Caveat, stated in the write-up and worth repeating here.** The corpus is rejection-sampled
from the same 27B being fine-tuned. This is self-distillation, so held-out CE measures whether
the adapter sharpened the policy toward its own successful trajectories on unseen games -- not
whether the model got better at ARC-3. Held-out CE is not an ARC-3 score.

---

## 18-Sep-2026 — the 25 public games' write-ups, fetched from arc-explainer, never copied

**What.** `tools/fetch_explainer_games.py` pulls arc-explainer's curated write-ups of the 25
public games into `datasets/explainer-games/games.json` (gitignored). One document per game,
level by level: the rules that start on each level with the game-code lines they were checked
against, the level pictures, Boss's notes from play (saw / did / expected / happened), ARC's
baseline actions, and Boss's runs with their replay guids (the join key into
`datasets/decision-steps/v0/recordings/`). as66 is never in it.

**Why.** Those write-ups were being edited only in arc-explainer and read by nothing here.
Boss wants them in the training work with arc-explainer as the only place they are edited, so
this repo fetches rather than keeping a copy that drifts. The endpoint is private until the
dataset is curated: it takes `X-ARC3-Admin-Token` from `$ARC3_COMMUNITY_ADMIN_TOKEN` or, on the
Mac Mini, the login keychain. The gx10 boxes need the env var, or fetch on the Mac Mini.

**Files.** `tools/fetch_explainer_games.py`, `.gitignore`, `AGENTS.md` (repo map row).

---

## 17-Sep-2026 — the replay + scorecard tooling moves in from the workspace, and the two pullers become one

**What.** Six tools, three trace findings and ~9.8 GB of recordings that had been living loose
in `bubba-workspace` — a personal scratch repo, and in an *untracked* directory inside it — now
live here, where the corpus they belong to already lived.

- `tools/replay_scrape.py` gains a `bulk` subcommand: guid lists from a file and/or a
  `pull_boss_scorecards.py` runs JSON, cached `/api/sessions` documents written beside each
  recording, smallest-first ordering, and a disk guard (`--cap-gb`, `--min-free-gb`) that stops
  the pull before the volume fills.
- `tools/pull_boss_scorecards.py` (new): the authenticated `/api/user/scorecards` surface, plus
  a per-game coverage report. Cookie path comes from `$ARC3_COOKIE_FILE`; the cookie itself
  stays outside this repo on purpose.
- `tools/replay_reasoning_report.py` (new): reasoning coverage, token usage, frame-change rate
  and actions-vs-human-baseline over the recordings tree.
- `tools/harvest_replays.py`, `distill_reasoning.py`, `analyze_coherence.py`,
  `coherence_on_corpus.py` (new): the vendor-agent coherence pipeline, with its corpus at
  `datasets/vendor-coherence/` and a README stating the boundary against the decision-step
  corpus.
- `datasets/decision-steps/v0/recordings/` goes from 26 recordings to 347. Gitignored, as
  before.

**Why.** A sub-agent built `pull_replays.py` in the workspace on 16-Sep without checking this
repo, which already had `replay_scrape.py` doing the same job better. That is the DRY failure
`AGENTS.md` names explicitly ("I'll write a tool to render/measure the games" — look first),
and it produced a second corpus in a second location under a second naming scheme. The
duplicate is deleted, not kept alongside.

**How the merge was decided, not assumed.** `ft09-0d8bbf25/99084b22-…` existed in both trees.
The two files are **byte-identical** (`cmp`, 1,932,098 bytes), which is what established that
the workspace corpus was the same artifact under a different filename rather than a different
record shape. 320 recordings moved, 17 dropped as verified-identical duplicates. Everything
`replay_scrape.py` already did well — atomic `.part` write, `count_rows` truncation guard,
rate-limit backoff — is reused; the deleted tool had no truncation guard at all.

**Verified, not asserted.** `bulk` was run end-to-end against the live API and pulled the one
recording the corpus was missing (`vc33-5430563c/1cd953c6-…`, 16.6 MB, 576 rows — 575 actions
plus the RESET). `pull_boss_scorecards.py` reproduces the September coverage in
`docs/trace-findings/2026-09-17-boss-scorecard-inventory.md` exactly: 17 games won, 7 played
and lost, `tr87` never cleared a level. `replay_reasoning_report.py` reproduces the numbers in
`docs/trace-findings/2026-09-17-replay-trace-corpus.md` off the new tree.

**The vendor corpus is NOT folded into the decision-step corpus.** Same endpoint, opposite
halves: `replay_scrape.py` keeps every byte the API served, `harvest_replays.py` drops the
frames and keeps the reasoning at ~50x smaller. `validate.py` and `SCHEMA.md` own the raw
contract and would correctly reject the compact records. Two tools, two trees, one README
(`datasets/vendor-coherence/README.md`) saying why.

---

## 17-Sep-2026 — the ARC-AGI-3 paper, read in full, and two stranded scripts landed

`docs/arc-agi-3-paper-reading.md` — all 23 pages of arXiv:2603.24621v2, checked against the
repo. Until now the paper was cited only second-hand, through the 31-Aug audit's read of §3.6
and §5. Three disagreements it surfaces, none fixed here:

- **Score cap.** The paper's text, `traces.py`, the vendored Tufa framework and `arc_agi`
  0.9.8+ cap a level at 115%. The agent prompt (`prompts.py:17`, and the frozen baseline-v12
  copy) tells the model 100%. Changing that is an experiment arm, not a fix.
- **Random-play gate.** ARC runs 50K and 1M random steps and wants each level won by chance
  less than 1 time in 10,000. `probe_one.py` runs 1,200 actions.
- **`baseline_actions`** is the scoring yardstick. The 5× budget is ARC's cost cap on its
  own leaderboard. `how-this-feeds-kaggle.md` treats the two as one number.

The PDF is not committed: arXiv's non-exclusive license doesn't cover a public repo. The doc
links both public copies.

Also landed, both unchanged except one header note:

- `scripts/ascii_symbol_token_bench.py`, which `docs/trace-findings/2026-09-11-bp35-astra-grid2-b476.md`
  cites. It lived only on the closed PR #7 branch, so that citation pointed at nothing on main.
- `scripts/compute_rhae.py` (14-Sep), which was never committed and sat untracked in a `/tmp`
  worktree. Its header now says its `rhae_level` is a cap-1.0 variant, not the paper's RHAE.

---

## 17-Sep-2026 — as66 is in the repo as a test-only game

**What.** `datasets/test-only-games/as66/v1/` (`as66.py`, `metadata.json`): a playable build of
as66, the 26th game that dropped out of the live 25. It was rebuilt in `82deutschmark/ARCEngine`
from the Boss's 27-Dec-2025 nine-level winning recording; every frame of that recording replays
exactly. This folder holds a copy; the canonical source stays in ARCEngine.

**The rule.** Boss, 17-Sep: hold it back for testing in our harness, never train on it. Written
where people will trip over it: the folder's `README.md` (rule, how to run it, baselines),
`AGENTS.md` section 0 and the repo map, `harnesses/README.md` (report it on its own line, never
in the ex-`ft09` average), the `--exclude-games` help text on `distill/extract_sft.py` (full
fence list with `as66`), and an update at the top of
`docs/trace-findings/2026-09-15-as66-the-withdrawn-26th-game.md` closing off the corpus use its
blocker 4(a) had been waiting on. No code behaviour changed; the fence is still a list the operator
passes.

**Checked.** With `python3.13`, `arc_agi.Arcade(OFFLINE, environments_dir="datasets/test-only-games")`
lists `as66-v1`, and the fewest-move route for each level plays all nine levels to `WIN`.

---

## 17-Sep-2026 — round-1 LoRA trainer, and a test-set fence the extractor could not enforce

`distill/train_lora.py` (new), `distill/corpus_adapter.py` (new), and `--exclude-games` on
`distill/extract_sft.py`.

**The fence.** Seven games — `vc33, ar25, sb26, re86, su15, tr87, tu93` — are the held-out test
set, and there was no way to keep them out of a training corpus short of filtering the JSONL
afterwards. Filtering afterwards is not good enough: an excluded record's regenerated board PNG
has already been written to the images directory by then, where a later job can pick it back up.
`--exclude-games` therefore drops at *game* granularity, before the renderer is ever reached.

It matches on the bare game code, not the full id. Artifacts name games `ar25-0c556536`; a
comparison of a 4-char fence list against full ids matches nothing and passes silently, which is
the failure mode most likely to void a round while looking clean. `game_code()` exists to make
that stripping explicit and testable rather than an inline `split` at the call site.

On the two 16-Sep rollout runs the fence drops 35 (game,pass) pairs — every one of the seven
codes is present, five passes each — leaving 40 records from 12 games.

**The memory floor was inconsistent with the allocator cap.** `set_per_process_memory_fraction(0.86)`
caps torch at 104.6 GiB of 121.63, so `MemAvailable` can never exceed ~17 GiB while torch is near
its cap — and ~13 GiB once resident system processes are counted. A 16.0 GiB floor was therefore
unreachable for long records, and it aborted round 1 at optimiser step 3 of 8, on a micro-step
that had just *completed* at 12.3 GiB. The floor is now 8.0 and, more importantly, **non-fatal**:
a trip skips one record and discards its accumulation window instead of killing the run. The cap,
not the floor, is what bounds the process.

Cached allocator blocks are now released before every micro-step. That helper deliberately does
not touch gradients — a `zero_grad` there would wipe the accumulation window and turn every
`grad_accum` window into a single-record step, with a loss curve that still looked normal.

**The trainer.** Single-GB10 LoRA SFT against the BF16 checkpoint, reusing the forward/backward
recipe the 17-Sep gradient census proved rather than a fresh one: `AutoModelForImageTextToText`
(the CausalLM class silently drops the vision tower), frozen vision tower, chunked
cross-entropy, and gradient checkpointing. The latter two are required and not tunable — naive
CE OOMs at ~20K tokens and checkpointing-off OOMs at 10K.

Two things in it are consequences of GB10 memory being *unified*, where an over-allocation
invokes the kernel OOM killer instead of raising a catchable torch error and takes unrelated
processes down with it: a `MemAvailable` floor checked before every allocation, and a hard
49,152-token sequence cap (65,536 killed the box on 16-Sep). Records over the cap are skipped
and counted, never truncated.

Corpus length is measured through the real processor, not a text tokenizer. One board PNG per
decision turn expands into a large vision-token block; a text-only count undercounts by enough
to admit a record that then blows the cap.

The gradient census from `assert_lora_gradients.py` is folded into the trainer's own step 0
rather than run as a separate pre-flight, so a silent gradient failure cannot appear between the
pre-flight and the run it was supposed to clear. Step 0 asserts 208/208 `lora_B` nonzero and
aborts otherwise; `lora_A` is expected to be 0/208 at step 0 because `lora_B` initialises to
zero, and only becomes nonzero once `lora_B` moves off it.

**Round 1 ran to completion**: 8/8 optimiser steps over 29 records / 882,826 tokens in 1.20 h at
204.4 tok/s, peak 98.74 GiB, zero OOMs. The saved adapter reads back as 416 tensors — 208/208
`lora_A` and 208/208 `lora_B` all nonzero, 39,583,744 params. The loss curve is **flat**
(0.5764 → 0.6033, oscillating 0.52–0.60): eight steps is not enough to move a 27B model, and
within-window record spread exceeds any step-to-step difference. The round demonstrates the
pipeline, not a capability gain. Full write-up, including what was *not* verified:
`docs/2026-09-17-arc3-lora-round1.md` in the operator's notes.

---

## 17-Sep-2026 — the LoRA run was training 64 of its 208 adapters, and why

`tools/assert_lora_gradients.py` — a pre-flight that fails a training round before it starts if
any LoRA `lora_B` parameter is not receiving a gradient — plus
`docs/trace-findings/2026-09-17-lora-gradient-rootcause.md`, the root cause it was written for.

A LoRA step measured on the `unsloth/Qwen3.8-27B-NVFP4` checkpoint on the DGX Spark a424 reached
`loss.backward()` cleanly, reported a falling loss, and delivered a gradient to **64 of 208
adapters**. The 144 dead ones were not slow — `lora_B` sat at its zero init with an exactly-zero
gradient, and since `dL/dA ∝ B` their `lora_A` could never start moving either. Permanently inert.

Cause: that checkpoint's `quantization_config` fake-quantizes **input activations** on precisely
the seven projections the adapter targets (`self_attn.q|k|v|o_proj`,
`linear_attn.in_proj_qkv|in_proj_z|out_proj`) plus `lm_head`. compressed-tensors implements
activation quantization by replacing the module's `forward`, and the quantize call it inserts runs
under `@torch.no_grad()` — so the input is detached and **no gradient can cross a targeted
module**. peft conceals it: its added `lora_B(lora_A(x))` branch keeps `requires_grad` alive, and
because `lora_B` is zero-initialised that branch carries exactly zero backwards. The 64 survivors
are `o_proj` and `out_proj` in every layer — the only targets whose output lands on the residual
stream, so gradient reaches them without traversing a quantized module. `dequantize=True` does not
help; it decompresses the weights and leaves the patched forward in place.

Established on CPU with a tiny randomly-initialised model of the same architecture: the failure
does **not** reproduce under any combination of `eager`/`sdpa`, `use_cache` on/off, gradient
checkpointing on/off, fp32/bf16 — and reproduces exactly, module for module, the moment the base
layers' inputs are detached. Confirmed against the compressed-tensors and transformers source.

Fix: train from the plain BF16 checkpoint, or call
`disable_compressed_tensors_fake_quant(model)` after `from_pretrained` and before
`get_peft_model`. **The fix has not been run against the 27B** — that needs a GPU, which was in
use by another job — so the pre-flight is the gate: run it first on the next GPU session.
`--self-test` proves the check on CPU in seconds, green on a healthy model and red on this defect.

---

## Where this stands — 16-Sep-2026

Read this first if you are picking the work up cold.

**The corpus's role changed on 15-Sep.** Son's no-teacher decision (`7074b67`) means the 27B
bootstraps from its own rollouts, so these records are **the recovery eval, plus at most a
small mix-in**, not SFT teacher data. The four review questions in PR #21 are answered in
`docs/plans/2026-09-16-dr-fable-calls-on-the-step5-review.md`; read that before the plan.

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
| 4 | segment and label the corpus | **started** — A and B on `main`; the first D pass ran on lp85, was blocked on `action_role_source` for RESET, and is now **unblocked and landed** (the engine is vendored); C/E not begun |

**A second work line opened 15-Sep-2026 (Son Pham).** Stand a Qwen3.8-27B baseline on the
pinned Kaggle duck harness, then SFT/RL until *held-out* games improve. The train/test
partition it needs is done and guarded — `datasets/splits/public25-train-test-split.json`,
18 training / 7 held out. The hardware it needs is not: see
`docs/trace-findings/2026-09-15-qwen27b-finetune-readiness.md` for the measured state of the
two Sparks and the checkpoint-format blocker. **Update 16-Sep: the base 27B baseline ran on a108 and 5 of the 7
held-out games score above zero, so the split stands** —
`docs/trace-findings/2026-09-16-qwen38-27b-baseline-result.md`. That line does not change this corpus work; the
corpus is its teacher data, which is why the three games carrying labelled episodes are
forced into the training half.

**What exists right now.** **156 tests, all passing** — 65 + 15 + 33 + 33 + 10 across
`test_decision_step_validator`, `test_dispatch_tables`, `test_segment`, `test_build_sft` and
`test_train_test_split`.
Run those four by name: `pytest scripts/` collects 58 errors from unrelated suites in this repo
and tells you nothing about this work. The validator file gained 6 when `ProvenanceProseTests`
landed in `1fdfb37`, `test_build_sft` is new in `2469e82`, and the dispatch and segment files
gained 4 and 2 with the engine vendoring.

**That 156 assumes the recordings are on disk, and no single total is reproducible without
them.** From a genuinely clean clone it is **65 (11 skipped) + 15 + 4-of-9 (5 skipped) + 33 (2
skipped) + 10**. `test_train_test_split` needs no recordings and runs clean either way. `test_segment` *collects a different number of tests* in the two cases — five of its
classes skip in `setUpClass`, which unittest reports as one skip per class rather than per test,
so 4 + 5 class-skips expands to 4 + 29 when the recordings are there. Both numbers are real;
quote the split rather than a bare total, or the next reader cannot reproduce either. **280** human replay guids
inventoried across two manifests that are deliberately not merged — 250 published plus **30**
first-party, the latter having gone 28 → 30 in `1fdfb37` with the `ls20/7537433d` and
`m0r0/2134c482` wins — plus 250 leaderboard rows that carry no guid and never can be
fetched. **11 live-build recordings on disk, plus 15 for as66** — counted as
`find v0/recordings -name '*.ndjson'`, partitioned on the as66 directory. Do not use the
`ls */*.ndjson` glob a previous revision of this line cited: run from `v0/recordings/` it sweeps
as66 in with the rest and reports 26. The 11 went 9 → 11 when the `ls20` and `m0r0` recordings
were pulled this evening. **12 labelled records** across 3 games — still a demonstration of shape, not a corpus, but it now holds a completed falsification/correction pair and the recovery-versus-abandonment distinction. The 6 that `validate.py` used to reject for a reason no annotator could fix have landed; see the entry directly below. `tools/segment.py` now emits the
mechanical portion of a record (cuts, frame refs, measured outcome, source citation) so that
annotation is three judgment fields rather than a whole record.

**The one rule that governs step 4.** A run counts only if its `game_id` is **still the live
build** — an early replay is a replay of a different game. That leaves **100 of the blog's 250**
and **25 of the Boss's 30**, and every current build has game source, so citation is no longer a
constraint. Execution plan, with the selection rule and the five passes:
`docs/plans/2026-09-15-step4-segment-and-label-execution.md`.

**Open questions carried, not closed.** (1) is **closed** — see below. (2) `boundary_reason` carries
per-game values, which will not survive 25 games. (3) `level` is `levels_completed`, a count —
during play of the Nth level it reads N−1, so `"level": 5` means the 6th, and an episode
spanning a `level_advance` cut now shows it. All three are flagged in `SCHEMA.md` or the tool
docstrings; none has been quietly widened.

**Closed since the last entry.** Two. `last_result` could not express "that action ended the
run", so post-death records read like ordinary steps; schema 0.2's `run_ended` closes it, and
the segmenter measures a *flip* to `GAME_OVER` rather than its presence, so one death yields one
marker. And `boundary_reason` had no value for a level transition, so the segmenter refused any
window spanning one; `level_advance` closed that — see the 15-Sep (earlier) entry, including
what the refusal was hiding.

**Read the entry directly below before anything else.** It records a defect in
`ARC3-Inference/inference/framework/solver.py:171-172` that filters `RESET` out of the action
menu the model is shown, on every game — which, on a game like ls20 whose only recovery
primitive is RESET, is a candidate mechanical explanation for the agent's scores. **Nothing was
changed on the strength of it**; it is a written proposal for the Boss and Dr. Fable. That entry
also withdraws an over-broad claim about the recording reconcile rule and corrects two figures.

**Next.** Passes D (annotate, one agent per game) and E (the adversarial falsification gate) on
the 13 recordings already on disk. Pass C (pull the rest) is **off** unless the eval needs more
rows. On the harness track, the RESET-guard arm is built and verified (`harnesses/reset-guard/`),
run as Kaggle jobs 11 and 12 with a same-cap arm-B control. **Update 16-Sep: D and E piloted,
see the entry below -- the gate cut 12 of 23 and the corpus holds 11 records.** E is the one that decides whether any of it
is worth having: a record whose `expected_observation` the cited next frame can neither confirm
nor refute gets cut, not softened.

---

## 2026-09-16 — the chat template was silently eating every chain of thought (Claude Opus 5)

`distill/extract_sft.py` emits `reasoning` on assistant messages. The 27B's
`chat_template.jinja` reads `message.reasoning_content`, and its jinja macro renders `''` for a
missing field instead of raising. So `processor.apply_chat_template()` over our corpus **drops
every chain of thought, silently** — and since 56 of the 113 baseline assistant turns carry no
`content` at all (reasoning plus a tool call, no prose), those 56 turns render as an *empty
assistant message*. Trained on as-is, the model is taught to say nothing on half its turns.

Nothing in the corpus is wrong; the loss is entirely at the record → template seam, which until
now lived nowhere and was being re-derived by each consumer. New `distill/chat_adapter.py` owns
it: maps `reasoning` → `reasoning_content`, coerces `tool_call.arguments` from a JSON string to
the mapping the template demands (it raises otherwise), normalises absent `content` to `''` so
it cannot render as the string `"None"`, and decodes the inline base64 PNG parts to PIL images
in template order. It deep-copies, so caller records are not mutated. `extract_sft.py` is
untouched.

Verified against the real `Qwen3VLProcessor` for Qwen3.8-27B on gx10-a424, not asserted:
a 6-assistant-turn record renders 6 `<think>` blocks with the reasoning text present in the
output, and its 5 image parts expand to 320 image tokens — **64 tokens/frame, confirming exactly
the estimate the extraction write-up flagged as unverified** ((256/16)²/4 for 256×256 frames at
`patch_size` 16 with spatial merge 2). Re-measured whole-corpus token lengths under the real
processor come in ~1% above the estimates (max 53,956 vs 53,258 estimated); the conclusion that
**0 of 41 records exceed a 64K budget** holds.

Found while standing up the LoRA training path on a424. Full measurement record, including a
separate and more serious finding — that gradient reaches only 64 of 208 LoRA adapters on that
stack — is in `2026-09-16-a424-lora-step-measurement.md` (Bubba's workspace, not this repo).

---

## 2026-09-16 — the SFT extractor is verified against captured frames, and two alignment bugs are out (Claude Opus 5)

`ARC3-Inference/distill/extract_sft.py` was conceptually right and factually wrong in two
places. Both are fixed, and the fix is now checkable rather than argued.

**The board each turn was trained on was the wrong board.** `_analysis_events` attached an
analysis event's own `board` to that event's user message. That board is the state the event's
actions *produced*. The observation a step was decided from is the *previous* event's board —
`initial.board` for the first step. Verified against the run's own request logs: the step-1
request carries exactly one image and it is the `initial` board, never `analysis[0].board`. In
two of four spot-checked games the first action left the board unchanged, which is how this
survived. The chain is now built from the whole ordered event list before level grouping, so a
level's first step correctly takes its observation from the previous level. `traces.py` is
untouched. Baseline regression holds at 12 records / 113 assistant turns / 11 games; unique
rendered images move 73 → 69, which is the expected fingerprint.

**Records collided across passes.** `build_records` globs every `*_viewer_data.json`, and
`game_id` carries no pass suffix, so `ar25 p0 L1` and `ar25 p1 L1` emitted the same `id` and the
contributing-games counter deduped two real trajectories into one. `pass_index` is now part of
the `id` and a record field. This only bites multi-pass runs — i.e. the massdata corpus.

**New: `distill/verify_frames.py`.** Runs with `save_request_logs: true` store the exact
multimodal payload the model received, inline base64 and all. This decodes those frames and
compares them to what the extractor regenerates. Compare **pixels, not bytes** — the serving path
and Pillow pick different PNG encoder settings for the same raster, so identical images differ in
file size and byte comparison reports 0/17 on frames that are pixel-identical.

The run configs carry no multimodal block, so the `--upscale 4 --style plain` defaults were
unverified. A sweep settles it: that combination reproduces 55/58 frames, every other combination
of `upscale ∈ {1,2,3,4,6,8} × style ∈ {plain, outline}` reproduces 0. Coverage is complete — all
25 baseline games and both passes of all 14 contributing massdata games, i.e. every image part in
the corpus. Baseline: 399/415 frames overall, **102/102 of the frames that reach the corpus**.
Massdata: 480/511 and 251/253. Across the combined corpus that is **353/355 (99.4%)**. The two
exceptions are isolated single frames (`sp80-589a99af_p0` index 12, `tu93-0768757b_p0` index 1)
with matching frames either side; cause not established. Nearly all other divergence is in games
and levels the rejection sampler discards, where the harness emitted fewer images than analysis
events. The module's `FIDELITY CAVEAT` (`save_request_logs: false`, "exact image bytes are not
stored") was stale and is rewritten.

**New: `distill/corpus_stats.py`.** Token and shape measurement over an emitted corpus. Text is
tokenized; base64 image payloads are excluded and image tokens reported separately as a labelled
estimate, because running a text tokenizer over a data URL produces a number with no
relationship to what the vision encoder charges.

**What the corpus actually is.** Baseline plus both massdata passes on disk: 41 records, **381
trainable assistant turns**, 355 image parts, 1,270,599 measured text tokens. Nothing exceeds the
~64K trainer budget — largest record 53,258 tokens, median 34,829, **0 of 41 over**, and that
holds regardless of the vision-token estimate (that record carries 27 frames; at 4× the estimate
it reaches ~58.4K). Yield by
pass: baseline 23.9% (233/973 env actions at cleared levels, 11/25 games), massdata p0 34.8%
(411/1,182, 12/25), massdata p1 in progress 30.5% (267/875, 12/25).

Two notes for whoever reads a target number off this. The widely-quoted "233 usable turns" is an
**env-action** count, `sum(actions_per_level[:levels_completed])`; it reproduces exactly, but the
trainable figure from those same 11 games is 113 assistant turns, roughly 2:1. And four full
massdata passes plus the baseline project to ~600–700 turns against a 2–5K first-LoRA target. No
extractor change closes that: 11–12 of 25 games clearing exactly one level each is the ceiling.
The lever is game count and difficulty spread, or accepting lower-credit data — not the pipeline.

Findings write-up with the full tables: `docs/2026-09-16-arc3-sft-extraction.md` in the Bubba
workspace.

---

## 2026-09-16 — The recovery eval runner

`tools/recovery_eval.py`, questions in `datasets/decision-steps/v0/recovery-eval/items.jsonl`, how
to run and read it in that directory's `README.md`. The step-5 plan's §3 check, built.

**One question per fork.** A player chose X on a board and the attempt failed; later, on the same
board, chose Y and cleared the level. The model gets the board and is asked for one action, once
told that X failed here and once not told. **The answer is played on the real game.** The
recording is replayed in the offline engine to the fork and the answer applied, and the result is
compared with the boards X and Y leave. So it scores choices, not action text. Every recording on
disk replays frame for frame.

**23 questions, 7 of them with a pass-E-kept record.** The other 16 come straight from the
recordings, so they need no annotation and no review calls. They include the 9 forks in dc22, ft09,
ka59 and m0r0. The reading is fixed in the README before any full run: the paired difference in
how often the model repeats X, with history against without. `scripts/test_recovery_eval.py` (18
tests) holds the prompts to showing no Y and no record judgments, and checks that each recorded
choice scores as itself in the engine. `frame_evidence.diff_text` now delegates to `diff_grids`,
with identical output.

---

## 2026-09-16 — The Qwen3.8-27B baseline lands in the repo, and gate 1 is met

`docs/trace-findings/2026-09-16-qwen38-27b-baseline-result.md`. The baseline Son directed ran on
a108 overnight, but its report existed only on that machine. All 25 public games, one pass each:
mean score 1.55, no wins, 11 games cleared a level. **5 of the 7 held-out games score above zero
(vc33 8.99), so Dr. Fable's hard gate 1 is met and the split is not redrawn.** Every game stopped
on the 90-minute wall at about 30% of its token budget, so the numbers are a floor. The per-game
scores were checked against the harness's own `score.json`. The step-5 plan's gate line now
points to the result.

---

## 2026-09-16 — Passes D and E, piloted on the recordings on disk

`docs/plans/2026-09-16-pass-d-e-pilot.md`. Dr. Fable's item 2.

**Pass E is built and it cuts about half.** `tools/pass_e_review.py` sends each record to a
separate headless Opus reviewer with no tools and no project context, with evidence rendered from
the recording by `tools/frame_evidence.py`. On the 12 records already on `main` it cut 8, all
for source knowledge in `memory_in` (all seven lp85 records, and bp35 row 214). A control of
three planted defects was cut 3 of 3. Cut records are deleted.

**Pass D writes fork records.** `tools/find_retries.py` finds where the attempt that cleared a
level chose differently from a failed attempt on the identical board. 11 written, 7 survived pass
E. The corpus now holds 11 records. The recount of the material (11 recordings, 117 moments, no
cull) does not match the step-5 plan's 13 / 132 / 128.

The segmenter's acceptance test now reads a frozen copy of the four bp35 records under
`fixtures/segmenter/`, since one of them was cut. The split's pinned-game list gains g50t and ls20;
the partition itself is unchanged.

---

## 2026-09-16 — the RESET guard lands in the in-tree harness (Claude Opus 5)

`docs/plans/2026-09-16-intree-reset-guard-port.md`. The in-tree agent harness could not press
RESET: `_engine_action_names` dropped it from every menu the model sees. Arm I built and
verified that guard against a frozen bundle (`harnesses/reset-guard/`, PR #23); this ports the
behaviour onto `ARC3-Inference/inference/framework/solver.py` and
`ARC3-Inference/inference/agent/prompts.py`, so the harness this repo actually runs has it too.

**RESET was hidden, not blocked.** `taaf/game.py` injects RESET (id 0) into
`available_actions` unconditionally, and `step_env`'s availability gate has always passed it,
so a model that typed `RESET` in arms A–H executed one. The new
`scripts/test_reset_guard_intree.py` demonstrates that against a pre-port checkout, not from
argument. Filtering the menu alone would therefore have guarded nothing; the refusal lives in
`step_env`.

**The guard, unchanged from the reviewed arm.** `_RESET_MIN_ACTION_GAP = 20`. A model RESET is
refused when the previous executed action was a RESET — which covers the game's opening and the
harness's own auto-reset after a death — and when it would land within 20 actions of the last
model-chosen RESET. Auto-resets never consume that window. A refusal spends no action and
returns `stop_reason="reset_rate_limited"`; mid-batch it stops the batch, which is what
`step_env` already did for an unavailable action. Accepted and refused RESETs print
`RESET_GUARD` lines and each game prints a `RESET_GUARD_SUMMARY`, the shape
`kaggle/experiments/sparse-deletion/count_resets.py` reads.

**A call site the bundle patch never had to cover.** The frozen patch guards three menus; in
tree there are **four** — the analyzer turn, the error payload, the executed-action payload,
and the `solver turn start` log line, which is new since the patch was written. It is routed
through the guard too, so the log cannot report a menu the model was not offered. `include_reset`
defaults to `False`, so a missed site would compile and silently keep RESET hidden; the check
that matters is zero remaining `_engine_action_names(self.game)`, and there are zero.

**`prompts.py`** gains the arm's one 251-character bullet, verbatim, after the
`action(actions)` contract lines.

**Verified, not assumed.** `py_compile` on all three files; 0 unguarded and 4 guarded menu call
sites by grep; and 22 assertions in `scripts/test_reset_guard_intree.py` passing against the
live `ls20-9607627b` build through TAAF's offline `GameAPI` with `ONLY_RESET_LEVELS=true` —
opening refused, one move then accepted, level reset rather than full reset, counts as an
action, twice-in-a-row refused, both edges of the 20-action window, a batch stopping at a
refused RESET and reporting `stopped_early`, and an auto-reset refusing the next RESET without
spending the window.

This file's `PURPOSE` header claimed it records no changes to `ARC3-Inference`. That is no
longer true, so the header is amended to say so; no other prose in the file is altered. The
section heading stays date-only, per this file's stated date-based versioning — `0.2` belongs
to the corpus schema and is not bumped here.

`harnesses/`, `kaggle/` and `vendor/` are untouched, including
`taaf/game_api.py`'s process-wide `ONLY_RESET_LEVELS=true` — without that pin arcengine
full-resets whenever its action counter is zero, which `set_level` zeroes at the top of every
level, so a model RESET on a fresh level would zero the run.

---

## 2026-09-16 — Dr. Fable's calls on the step-5 review, and the corpus changes job

`docs/plans/2026-09-16-dr-fable-calls-on-the-step5-review.md`. PR #21 asked four questions;
these are the answers, posted as the PR review and then written down because a review is not
a document the next session reads.

**The corpus is the eval now, not the teacher.** Son's no-teacher decision removed the role
the corpus was specified for. `README.md`'s first line, the step-5 plan's status block and the
"Where this stands" section above now say so. The split's training-only constraint on bp35,
cn04 and lp85 is left in place as harmless; drop it on any redraw.

**RESET: measured, not argued.** The 27B baseline runs pinned with RESET hidden. One Kaggle arm
on the bottom seven exposes RESET behind a guard (never twice in a row, at most one per 20
actions) and reports reset rate next to level clears. The review's option (c) is dropped; the
"chose RESET on a live board" records stay as eval rows. The ls20 fact that decides it: RESET
on a live board refills three lives and the step meter, so on four 21-step levels it is how a
human wins, and the harness cannot make that move on any game.

**Ceiling: pilot only.** Passes D and E on the 13 recordings on disk; pass C is off.

**Measurement: two gates.** Held-out games must score above zero on the base 27B or the split
is redrawn on measured agent difficulty; the 18/7 result is labelled as transfer within the
public 25, with as66 as the one out-of-lineup probe.

**Convention: imposed.** Schema and validator changes go through a PR that names the migration
and ships the script. `validate.py` already refuses a stale `schema_version`; that stays.

**Also fixed:** `SCHEMA.md`'s field table still said `schema_version` was `"0.1"`; it is `"0.2"`.

---

## 2026-09-15 (newest) — the 18/7 split for the Qwen3.8-27B experiment

Son Pham's directive of 21:03 EDT opens a second line of work in this repo: stand a
Qwen3.8-27B baseline on the pinned Kaggle duck harness, then SFT and RL until *held-out*
games improve. That requires a train/test partition of the 25 live public builds, and it
requires the two DGX Sparks cleared of Flash Next first. This entry covers the split, which
is done, and records the measured state of the hardware, which is not.

### `datasets/splits/public25-train-test-split.json` — 18 training, 7 held out

Generated by `tools/make_train_test_split.py`; no RNG, no seed, same inputs produce the same
file, and `scripts/test_train_test_split.py` asserts that by regenerating and comparing.

**Training (18):** bp35 cd82 cn04 dc22 ft09 g50t ka59 lf52 lp85 ls20 m0r0 r11l s5i5 sc25
sk48 sp80 tn36 wa30
**Held out (7):** ar25 re86 sb26 su15 tr87 tu93 vc33

Difficulty is the mean of three z-scored human-derived signals — `baseline_total_actions`
(the dominant cost axis under a 108K generated-token per-game cap), level count, and the
median actions the ten fastest human *winners* spent — cut into terciles. The ranking passes
inspection at both ends: cd82 easiest (6 levels, 171 baseline), lf52 hardest (10 levels,
1,339 baseline, 792 median).

**Stratified on two axes, not one.** Difficulty alone would have leaked input modality. The
lineup is 13 `keyboard_click`, 7 `click`, 4 `keyboard` and one untagged; a test set drawn on
difficulty alone can take every `click` game into training, at which point "improvement on
held-out games" is confounded with interface transfer and a reasoning gain is not separable
from an interface gain. The held-out seven hold the proportional quota — 4 / 2 / 1 — and
terciles 2 easy / 3 medium / 2 hard, against train's 6 / 6 / 6. Mean difficulty agrees to
1e-4. Every test set meeting the modality quota was enumerated exhaustively (29,700 of them)
and scored on tercile match, then mean gap, then spread; ties break on sorted game id.

**A leak was found and closed rather than noted.** The unconstrained split put bp35, cn04 and
lp85 — every game with labelled decision-step records — into the held-out set. That corpus is
the SFT teacher data this repo exists to produce, so the held-out measurement would have been
contaminated before a step was trained. Games carrying episodes in
`datasets/decision-steps/v0/episodes/` are now training-only, derived from what is on disk so
the constraint tracks the corpus as it grows rather than going stale as a hardcoded list.

A property that fell out rather than being aimed at: six of the seven held-out games are ones
the Boss has never played, and the seventh (re86) he has never won. There are no first-party
human recordings behind the held-out set at all, so there is no human-trace contamination
route into it either.

**The caveat that matters, and it is written into the file, not just here.** This is *human*
difficulty. Nothing in this repo measures per-game agent difficulty — `ARC3-Inference/runs`
is empty — so the model's ordering may differ. After the base-27B baseline lands, check that
the held-out seven are not uniformly zero. **A test set the base model scores zero on cannot
show improvement no matter what training does**, and in that case the split must be redrawn
against measured scores.

Ten tests. The two load-bearing guards were poison-checked: moving lp85 into the held-out set
fails the leakage guard, and deleting one id from `DUCK_HARNESS_PUBLIC_GAME_IDS` fails the
lineup guard with the message telling the reader to regenerate rather than edit the
assertion. That lineup guard exists because the split is only meaningful over the games the
harness actually runs — verified byte-identical between `kaggle.py` and
`current-builds.json` at the time of writing.

### `docs/trace-findings/2026-09-15-qwen27b-finetune-readiness.md` — measured, and one blocker

Written against the boxes, not against the runbook. Three findings worth carrying:

1. **The two Sparks are one cluster, and Flash Next held every GPU on it.** `ray status`
   reports 2 active nodes and `2.0/2.0 GPU (2.0 used of 2.0 reserved in placement groups)`.
   Nothing in the directive could have started while it was up, so the teardown is the
   unblocker rather than housekeeping. It was idle when measured — 0 running, 0 waiting, and
   54 requests across its whole 2d18h lifetime, all finishing on `length` at ~65 prompt tokens
   each, i.e. smoke probes. **The a108 container has been stopped** (`docker stop`, restart
   policy `no`); a108's GPU now shows zero compute processes. The 126G of weights, the image
   and the hand-written PLE patches in `~/flash-next-work/` were all left in place, and
   `docker start arc3-flashnext-ray-head-04a25` puts it back. a424's worker container still
   holds its GPU and needs access this account does not have.
2. **Sherlock is not on Flash Next**, so the removal and the model repoint are independent
   changes and neither gates the other. Its config points at Ollama on `:11434`; that is a
   file read, and the effective runtime backend should be confirmed against the process
   before weights are deleted.
3. **The 27B on disk cannot be trained as-is.** `~/models/Qwen3.8-27B-NVFP4` is a
   compressed-tensors checkpoint — the format vLLM serves — while the runbook's learner path
   is Unsloth's bitsandbytes NF4. Different formats, not interchangeable, and the Unsloth
   entry in the HF cache is a 12K metadata stub with no weights. The learner needs the pinned
   BF16 upstream at ≈54G, against 178G free. **That is the concrete reason the 126G teardown
   is a prerequisite and not housekeeping.**

Also recorded: the committed a108/a424 configs diverge from the Kaggle pins on exactly the
axes the directive named — context 32,768 against 102,985, lanes 2 or 25 against 7,
temperature 0.6 against 1.0 — and 7 lanes at ~103K context on one GB10 is the likeliest
failure point. The directive authorised adapting the time limit and nothing else, so maximum
feasible lanes × context is to be measured and reported, not quietly reduced.

**No teacher — settled at 21:19 EDT, and Son was right.** The runbook proposed Flash Next as an
SFT teacher; the directive said remove it. Son's objection is that RL is on-policy, so a second
model has no role in the loop, and the runbook concedes the point three times over: teacher
traces are off-policy demonstrations (§5), their token ids cannot be reused across a different
tokenizer and template (§6), and they must not be used as current-policy GRPO samples (§10).
They were only ever an SFT *bootstrap*.

The one thing a bootstrap buys is **reward variance**, not game knowledge: group-relative RL
learns from differences within a group, so a game the base model never scores on contributes
zero gradient and pure spend. Whether that bootstrap is needed is what the baseline measures —
which is why the directive's own ordering is right. And if it is needed, the better source is
the 27B's own successful rollouts by rejection sampling: same tokenizer, same template, no
train/serve skew, collected during a run that has to happen anyway.

So the weights went. 206 shards, 126G, removed from a108 — **178G free → 304G free**, which
clears the ~54G BF16 learner checkpoint with room for adapters, optimizer state and trace logs.
The 58MB of non-weight files were preserved first at
`~/models/flash-next-nvfp4-conversion-record/` — config, chat template, tokenizer, shard index,
`conversion_environment.json`, the unchanged-audit report and the aime26/gsm8k metrics. All 549
were counted at source and re-counted at the destination before a shard was touched, with a
mismatch set to abort. That record is what makes the model re-creatable from a fresh weight
download instead of from scratch. a424 still holds its own GPU and probably its own copy.

Nothing in `ARC3-Inference` was touched.

---

## 2026-09-15 (latest)

### ls20: three lives a level, a 42 that is often 21, and a RESET that refills both

`docs/trace-findings/2026-09-15-ls20-lives-and-the-filtered-reset.md`. The game mechanic behind
the Boss's ls20 win, written because `first-party-replays.json`'s ls20 attribution cites it and
because the step-budget half was not written down anywhere. The harness half is **not**
duplicated — it is owned by the evening-session entry below and cited from section 4.

**Lives are per LEVEL.** `ls20.py:1821` sets three, inside `on_set_level` (`:1778`); budget
exhaustion spends one (`:1950`, `:1961`); the third ends the run (`:1962-1963`). RESET re-enters
the hook through the engine (`base_game.py:205 → :305 → :326 → :328 → :164`) and so refills
lives *and* the step meter.

**Measured, not inferred.** The pips render at frame row 61, x=56/59/62, colour 8. Across all
562 rows they take exactly three states — 419 rows at three lives, 140 at two, 3 at one — and
never reach zero, which is the same fact as the recording carrying no `GAME_OVER` row. **Row 454
is the mechanic in one row:** one life left, RESET pressed, three lives back, `levels_completed`
unchanged. All three of that run's resets were taken on a *live* board, so RESET on ls20 is a
life refill bought for a level restart, not recovery from death.

**The "42-step budget" is 42 on three levels and 21 on four.** All seven declare
`StepCounter: 42`, but the meter drains by `StepsDecrement`, default **2** (`ls20.py:1771`),
overridden to 1 only on levels 1, 4 and 6 (`:724`, `:1088`, `:1324`). Derived by *parsing the
level objects*, not by reading line proximity in `LEVELS_SPEC` — the partial-read mistake
`AGENTS.md` warns about, which would have mapped the overrides to the wrong levels. A record
claiming "42 moves on this level" is wrong on four of seven.

**Three of the line numbers this was asked to check were wrong, and section 5 lists them.** Two
off-by-ones (`:1962` is the test, `:1963` is the `lose()`; the harness filter is
`solver.py:171-172`, not `:170-171`), and one substantive: the claim that `solver.py:752` would
reject a RESET anyway is **false** — `taaf/game.py:188-193` always re-adds RESET (0) to
`available_actions`, so that gate passes. It is one filter, not two, which makes the proposed
harness fix a one-place change. Verified in this tree, not relayed.

---


### The RESET blocker is cleared: arcengine is vendored, and six stranded records land

Committed direct to `main` at the Boss's instruction.

**The blocker, restated in one line.** `action_role_source` must cite a `<path>:<line>`, `RESET`
is dispatched by the engine rather than by the games, and the engine was not in this repo — so a
`RESET` step could only be labelled on the 2 of 8 in-scope games (`bp35`, `lf52`) that happen to
carry their own branch. `RESET` is the only recovery primitive on **19 of the 25 live builds**,
and recovery after falsification is the metric this corpus exists to move. The corpus could
record recovery only on the games least representative of how recovery works. That is a
selection effect introduced by a regex.

**Resolved by option 3 of the four the lp85 doc listed: vendor the engine.** That doc called it
"the largest change"; measured, it is the smallest. `arcengine` is **2,342 lines**, **MIT**, the
**only release ever published** on PyPI, already declared at
`tufa-arc-agi-framework/pyproject.toml:9` and already pinned in `uv.lock` — whose sdist sha256
the downloaded tarball matched exactly, a chain that predates this work. It is unpacked
unmodified at `vendor/arcengine-0.9.3/`; `vendor/README.md` carries the provenance and the scope
limit. Why not the other three, in one line each: relaxing the pattern (1) permanently weakens
the field for every record to fix one action on six games; citing the dispatch table (2) cites
*an absence* and would have been the only citation class with no drift guard; accepting the bias
(4) writes the selection effect down permanently instead of removing it. Full argument:
`docs/trace-findings/2026-09-15-lp85-step-budget-and-the-uncitable-reset.md` §5.

**What landed.** `tools/segment.py`'s `citation()` gained an engine fallback — game source
first, because a game's own branch is what distinguishes that build, then the engine. All eight
dispatch tables gained an `engine` block with 13 anchors each, drift-checked against the
vendored file exactly as game anchors already were, plus a per-file sha256 guard and a check
that `uv.lock` still pins the sdist the tree came from. And the six records that had been
carried verbatim in that doc because they could not be written are now at
`v0/episodes/lp85-305b61c3__129ddf21…__reset-recovery-and-abandonment.jsonl`, 6 records, 0
errors, frame resolution **ON**. They were re-emitted by the segmenter and compared
field-for-field against the doc's transcription before landing rather than pasted; every
mechanical field agreed.

**The five level-8 rows are the reason this was worth doing.** Every `RESET` record before them
followed a death. These follow none — the board is alive, 11 to 42 of 64 budget cells spent — so
`action_role` now separates *recovery from a dead board* from *abandoning a plan on a live one*.
A corpus that cannot tell those apart teaches "reset when dead", which is the easy half. Row 176
is also the first completed falsification/correction pair whose halves are separate records: the
negative record on row 175 is the falsified decision, and 176 is the correction the player
actually made.

**A defect on `main` that this uncovered, and that was stopping everything.** Schema 0.2
migrated every fixture and every committed record and added `run_ended` to the segmenter's
output — but left `tools/segment.py`'s `SCHEMA_VERSION` at `"0.1"`. **Every record pass A
emitted was rejected by `validate.py` on the version alone.** A whole-pipeline stop, invisible
because no test compared the two constants. Fixed; `SchemaVersionTests` now asserts they agree.

**An apparent contradiction the vendored source resolved rather than left hanging.**
`base_game.py:278` skips the action-count increment for `RESET`, which looks like it contradicts
the reconcile rule in `datasets/decision-steps/README.md`, where `RESET` rows *are* counted as
actions. They are two different counters: `ls20` reports 561 actions over 562 rows containing 3
non-boot `RESET`s, where `ARCBaseGame._action_count` would give 558. The session API's counter is
not the engine's, and `vendor/README.md` says so.

**Scope limit, stated not implied.** It is **not** verifiable from this repo that
`three.arcprize.org` runs 0.9.3 — the service exposes no engine version. 0.9.3 is the only
arcengine ever published and the one this repo pins, so a citation into it is a citation into
the only arcengine anyone can read. Every emitted citation carries
`[arcengine 0.9.3, engine-level: …]` so it claims that and not more.

**Not done, deliberately.** No harness code was touched. `ACTION7` is **not** resolved by this —
it has no engine branch either, and on the 19 builds that do not offer it there is nothing to
cite because there is nothing that runs. Five new guards were poison-checked: vendored-file
edit, engine anchor drift, a note reverting to "not vendored", segmenter/schema version drift,
and the `uv.lock` pin.

---

## 2026-09-15

### Evening session: five human wins, and a harness defect that says the agent cannot press RESET

Written for a reviewer picking this up cold. Every file:line below was opened in this tree
before it was written down; where a claim is not verifiable from this tree it says so.

**No ARC3-Inference or harness code was changed by this entry, and none should be on the
strength of it.** The `solver.py:171` item is a written proposal. Whether to act on it is the
Boss's and Dr. Fable's call.

#### The headline: the agent is never shown RESET

`ARC3-Inference/inference/framework/solver.py:171-172` contains `if name == "RESET": continue`,
inside `_engine_action_names()` (`:164`). That function builds the `valid_actions` list on both
payload paths — the error payload at `:692` and the per-action payload at `:928` — and
`valid_actions` is what gets rendered into the model's prompt as "Valid actions right now"
(`agent/tool_agent.py:1408`). **RESET is filtered out before the model ever sees it.**

The only RESET the harness issues is `_execute_auto_reset()` (`:825-827`), fired by the runner
loop at `:347-352` *after* `_is_engine_game_over()` is already true. That is cleanup, not
strategy: by then the run is over and the reset cannot be used to recover from anything.

**Correction to an earlier reading of this, from Sherlock, re-verified here and accepted.** It
was originally called a two-gate problem, on the claim that the execution-side membership check
at `solver.py:752` (`if action.id.value not in self.game.current_state.available_actions`) would
also reject a RESET. That is wrong. `tufa-arc-agi-framework/src/taaf/game.py:188-193` defines
`available_actions` as "Legal action ids, with RESET (0) always present" and re-adds `0`
unconditionally when it is absent. The execution gate passes. **Deleting the one filter at
`:171-172` is the whole fix.**

Sherlock also correctly noted that `taaf/game_api.py:222` sets
`os.environ["ONLY_RESET_LEVELS"] = "true"` process-wide immediately after `arcade.make`, which
is what stops an at-level-start RESET from restarting the entire run; the code comment at
`:215-221` describes precisely the arcengine behaviour we had independently observed on as66.
One nit for the record: Sherlock cited the filter at `solver.py:119-120`; in this tree it is
`:171-172`.

#### Why it matters, measured on ls20

`docs/static/games/src/ls20-9607627b/ls20.py` gives a per-level life budget the agent has no
way to refill:

- `:1821` — `self.aqygnziho = 3`, inside `on_set_level` (`:1778`). Three lives **per level**,
  not per run.
- `:1950` + `:1961` — running the per-level step meter out (`not _step_counter_ui.mfyzdfvxsm()`,
  the decrement-then-test at `:1487-1490`) costs one life.
- `:1962-1963` — `if self.aqygnziho == 0: self.lose()`. The **third** loss on a single level
  ends the whole run.
- `:1525-1529` — the three pips render at frame rows 61–62, x = 56/59/62, colour
  `tqogkgimes` = 8 (`:1458`), lit while `aqygnziho > i`.
- `:1778-1782` → `:1794` → `:1773-1776` — RESET re-runs `on_set_level`, which re-clones the
  pristine level (`:1780`), resets lives to 3 (`:1821`), and calls `wbcenorpju()` (`:1794`),
  which refills the step meter via `nzukewekzr()` (`:1492-1493`). Note the hop: `:1773-1776`
  lives in `wbcenorpju`, not in `on_set_level` — an earlier draft of this entry cited it as
  though it were inline, and it is not. RESET is the only mid-level refill that exists.

Confirmed on tape, not just in source. Tracking `frame[61][56|59|62] == 8` across all 562 rows
of the Boss's winning run (`ls20-9607627b/7537433d-…`), the pip count changes exactly seven
times: 3→2 at row 36, 2→3 at 81, 3→2 at 225, 2→3 at 277 (all level advances), then **3→2 at
408 and 2→1 at 451** on the final level — one timeout from `lose()` — and **1→3 at row 454, a
RESET**. He went on to win, at score 100. The run's other mid-run RESET, at row 135, left the
pip count at 3: a reset spent purely to refill the step meter, with no life lost.

ls20 is also one of the **19 live builds with no ACTION7** — checked across
`docs/static/games/src/*/`, where the six that do carry it are ar25, bp35, lf52 (conditionally,
`[7] if STORES_UNDO`), sb26, sk48 and su15. So on ls20 the agent's only recovery primitive is
the one the harness filters out. That is a plausible mechanical cause for ls20 scoring badly,
and it costs one line to test.

#### Five human wins from the Boss, all re-derived from tape

| game | guid | state | levels | actions | baseline | resets | score |
|---|---|---|---|---|---|---|---|
| ka59 | `1333b2ee` | WIN | 7 | 598 | 730 | 2 | 84.57 |
| lp85 | `129ddf21` | WIN | 8 | 415 | 388 | 6 | 76.39 |
| ls20 | `7537433d` | WIN | 7 | 561 | 776 | 3 | **100** |
| m0r0 | `2134c482` | WIN | 6 | 752 | 1107 | 10 | **100** |
| g50t | `58483738` | WIN | 7 | 536 | 879 | 8 | 82.12 |

Every cell checked against the 18:50 EDT scorecard snapshot
(`arc3-run/boss-replays/boss-runs-2245.json`); `baseline` is the sum of
`level_baseline_actions`. The g50t row carried two blanks in draft — they are filled here, not
dropped. All five recordings are on disk and gitignored
(`.gitignore:34`, `datasets/decision-steps/v0/recordings/`).

**lp85 is the best tier-3 source in the corpus.** It is a one-action game — `available_actions`
is `(6,)` on all 416 rows of the tape, a click carrying x/y — with no undo, so its single death
(row 175, `state: GAME_OVER` on level 6) followed by a working RESET at row 176 is a falsified
prediction with an observed correction and *no* alternative recovery to argue about. It carries
five further resets, at rows 269, 294, 311, 365 and 386, every one of them at
`levels_completed: 7` (the 8th level, per the `level` note at `SCHEMA.md:213`) and every one
preceded by a `NOT_FINISHED` row — plans abandoned as unwinnable, not boards that killed the
player.

#### The reconcile rule, stated with its exceptions

The rule is `rows = 1 + api.actions` (plus any rows recorded past the terminal state) and
`RESET rows = 1 + api.resets`. A previous draft said it "holds exactly on every recording we
hold." **It does not, and the claim is withdrawn.** Measured across all 26 recordings on disk:

- **Holds exactly on 9 of the 11 live-build recordings** — cd82, cn04, dc22, ft09,
  `g50t/4f0689d0`, ka59, lp85, ls20, m0r0. Each ends on a single terminal row, so the
  post-terminal term is zero.
- **Fails on `bp35/c935ca1b`**: 1030 rows against `1 + 1024 = 1025`. The tape ends cleanly on
  one `WIN` row, so this is not trailing junk — the API's `actions` is **5 short of the tape**.
- **Fails on `g50t/58483738`** — a row in the table above: 538 rows against `1 + 536 = 537`,
  again ending on one clean `WIN` row. The API is **1 short**. Its RESET side still reconciles
  (9 rows = 1 + 8).
- **Does not apply to the 15 as66 recordings at all**: they contain **zero** `RESET` rows while
  the API reports up to 9, and four of them are not in the scorecard snapshot. That is a
  different recorder, and it should not be counted as agreement or as disagreement.

#### A rule we were following that nobody wrote down

In `arc-explainer`, three consecutive CHANGELOG entries kept the session `score` off the game
pages, each citing the one before it: 9.74.0 (cd82, 59.9), 9.78.0 (ka59, 84.57) and 9.79.0
(lp85, 76.39). The stated justification in 9.74.0 is that the score "sits on a different scale
from the Human Records card." **It does not** — the leaderboard endpoint feeding that card
returns the same scale, and the ka59 and lp85 entries *say so in writing* while omitting the
score anyway, attributing the omission to "the owner's direction." The Boss's position, as given
to this session, is that no such direction was given; that is his account and cannot be
established from any tree, so it is recorded as his and not as verified.

Two corrections to how this was first written up. **The rule did not suppress two perfect 100s
— both are on the page.** 9.80.0 prints ls20's `score: 100` and 9.81.0 prints m0r0's, each
breaking the precedent on the record and explaining why. **And the backfill is promised, not
landed:** 9.81.0 defers the reconciliation to "9.82.0, immediately below this entry," and
`### Version 9.82.0` does not exist in `arc-explainer/CHANGELOG.md`. That forward reference is
dangling as of this commit. cd82, ka59 and lp85 are still without their scores.

Standing note for future agents, which is the durable part: do not carry an editorial omission
forward as policy because a previous entry did. If an entry says "at the owner's direction,"
verify that before inheriting it.

#### Inventory, from the 18:50 EDT scorecard pull

Scorecards via `arcprize.org/api/user/scorecards` (browser cookie), detail via
`arcprize.org/api/user/scorecards/<card_id>` — that second path is the working one;
`/api/scorecard/<id>` and `/api/scorecards/<id>` both 404. 50 cards, which is a hard cap: `next`
is a page size, not a cursor.

**The threshold matters, so it is stated.** "Real play" below means `levels_completed > 0`.
On that threshold: **25 live-build runs with real play, across 18 of the 25 live games; 11 games
won** (bp35, cd82, cn04, dc22, ft09, g50t, ka59, lp85, ls20, m0r0, r11l); **7 never played on a
live build** (ar25, s5i5, sb26, su15, tr87, tu93, vc33); **7 played but not won** — sk48 reached
level 6, tn36 5, sc25 4, lf52 2, and re86 / sp80 / wa30 one each. Switching the threshold to
`actions > 0` gives 34 runs across 19 games and moves tr87 out of "never played" into "played,
zero levels," which is why the threshold is written down rather than assumed.

Caveat worth carrying: **110 of the Boss's 144 live-build run rows have zero recorded actions** —
sessions opened and batch-published. An earlier draft said 117 of 144; 144 is right, 110 is the
figure the snapshot supports and 117 could not be reproduced from any snapshot on disk. ar25 and
the live vc33 build (`vc33-5430563c`) look played but are empty shells; vc33's 358-action
`GAME_OVER` run is on `vc33-9851e02b`, a superseded build.

#### Still open, carried deliberately rather than quietly closed

- RESET has no citable `action_role_source` in most games — `arcengine` is not vendored, so only
  bp35 and lf52 have citable in-source RESET/ACTION7 implementations. This is what blocked the
  first D pass on lp85.
- The two reconcile exceptions above: the API's `actions` undercounts the tape on
  `bp35/c935ca1b` by 5 and on `g50t/58483738` by 1. Cause unknown; not investigated here.
- Whether to change `solver.py:171`. Not ours to decide.

---

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

## 2026-09-15 (earlier)

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
