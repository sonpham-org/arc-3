<!--
Author: Claude Opus 5 (Bubba)
Date: 15-September-2026
PURPOSE: Operator guide for the per-game dispatch tables built by pass B of
docs/plans/2026-09-15-step4-segment-and-label-execution.md - what a table contains, how an
annotator turns one into an action_role_source citation, and the measurement that settles the
sibling-build question the plan left open. The tables themselves are the data; this explains
their shape and carries the one finding that is cross-game rather than per-game.
SRP/DRY check: Pass - ../SCHEMA.md holds the record contract, ../README.md is the corpus
operator guide, this holds only the dispatch-table format and the sibling-build finding. No
per-game dispatch detail is duplicated here; it lives in the JSON.
-->

# Dispatch tables — action name to source line

One JSON file per game: `<game_id>.json`. Built once by reading the game source under
`docs/static/games/src/<game_id>/`, cited by every record for that game.

**What they are for.** `action_role_source` must cite a specific line in the game source
(plan of record §5 step 4). Without a table, every annotator re-derives the same citation and
they drift. With one, `action_role_source` is a lookup.

## Format

```
game_id, source_file, source_sha256_prefix, source_line_count
dispatch            the method that branches on the action id, its form, and the guards that
                    can swallow an action before it is ever dispatched
available_actions   declared (from source), observed (from a recording, or null), and the
                    runtime filter when the game overrides _get_valid_actions
actions             one entry per action name that has a branch:
                      branch              the line that selects this action
                      calls               what it calls, each with role, target def, condition
                      branch_conditions   the tests inside the branch that change the outcome
                      effect              what it does, in words, from the source
                      offered             is this action actually reachable through the API
unhandled_actions   actions with no branch, and why
sibling_builds      the per-game answer to the sibling-citation question
notes               findings that do not belong to one action
```

**Anchors.** Any object carrying both a `line` and a `text` key is an anchor: `text` is the
stripped content of that line in `source_file` at build time.
`scripts/test_dispatch_tables.py` re-reads every source file and fails if a cited line no
longer contains its cited text. Line numbers in prose (`effect`, `notes`) are **not** checked —
only anchors are, so prose citations are the weaker kind and should be read as pointers.

**Writing a citation.** The canonical form is the one the schema already requires,
`<path>:<line>[ note]`:

```
docs/static/games/src/bp35-0a0ad940/bp35.py:4524 GameAction.ACTION7 -> svmaaixutx()
```

Take `<path>` from `source_file`, `<line>` from `actions.<NAME>.branch.line` for "which branch
ran" or from a `calls[].line` for "what it did".

**Engine-level actions.** `RESET` is dispatched by the engine before the game's `step()` is
reached, so on the six games with no `RESET` branch of their own the citation comes from the
table's `engine` block instead, and points into `vendor/arcengine-0.9.3/`:

```
vendor/arcengine-0.9.3/arcengine/base_game.py:205 if action_input.id == GameAction.RESET: -> self.level_reset() [arcengine 0.9.3, engine-level: RESET is dispatched by the engine, not by this game]
```

The trailing bracket is not decoration: it names the engine build the line was read from,
because it is **not** verifiable from this repo that the hosted service runs that build. See
[`vendor/README.md`](../../../vendor/README.md). `tools/segment.py` writes this for you and
prefers a game's own branch when it has one — `bp35` and `lf52` still cite their own source,
which is the better citation because it is what distinguishes that build.

Engine anchors are drift-checked against the vendored file exactly as game anchors are, and the
vendored tree is sha256-guarded per file, by `scripts/test_dispatch_tables.py`.

## The sibling-build question — settled

Plan §1(a) found 16 of 36 manifest builds have no source in the repo, noted that several look
like build drift rather than missing games, and left open whether a record on one build may
cite a **sibling build's** source. Pass B was told to settle it.

**Answer: no. Line-level citations never transfer between builds.** Not "probably not" —
measured, on every pair in the repo where both builds are present.

Three pairs have both builds under `docs/static/games/src/`, so three pairs could be diffed:

| pair (live / stale) | changed lines | dispatch line, live → stale | what changed |
|---|---|---|---|
| `ls20-9607627b` / `ls20-cb3b57cc` | 3,256 | 1921 → 1420 | re-obfuscated: different identifiers, `GameAction.ACTION1` → `self.action.id.value == 1`, 482 fewer lines |
| `vc33-5430563c` / `vc33-9851e02b` | 2,851 | 2085 → 2112 | 22-line MIT header added, and `GameAction.ACTION6` → `.value == 6` |
| `ft09-0d8bbf25` / `ft09-9ab2447a` | 43 | 2329 → 2351 | **identical dispatch code**, shifted +22 by an added MIT header; `_get_valid_actions` and `available_actions=[6]` dropped entirely |

In all three pairs exactly one build is live and one is stale, per
[`current-builds.json`](../current-builds.json).

`ft09` is the one that makes the rule airtight. Its dispatch is byte-for-byte the same code,
and the citation is still wrong by 22 lines, because a licence header moved every line beneath
it. A sibling citation can be wrong even when nothing about the game changed.

**What does transfer.** On `ls20` the *semantics* are identical: ACTION1 `dy=-1`, ACTION2
`dy=+1`, ACTION3 `dx=-1`, ACTION4 `dx=+1`, everything else a no-op. So `action_role` in words
survives a build change; `action_role_source` does not. That split is the usable form of this
finding — an annotator may reason about a sibling build's mechanics, and may not cite its
lines.

**Per game, for the eight in scope:**

| game | sibling in manifests | sibling source in repo | may cite sibling |
|---|---|---|---|
| `bp35-0a0ad940` | none | — | n/a |
| `g50t-5849a774` | none | — | n/a |
| `cd82-fb555c5d` | none | — | n/a |
| `cn04-2fe56bfb` | `cn04-65d47d14` | **no** | no — cannot even be diffed |
| `wa30-ee6fef47` | none | — | n/a |
| `lp85-305b61c3` | none | — | n/a |
| `ls20-9607627b` | `ls20-cb3b57cc` | **yes** | **no** — diffed, see above |
| `lf52-271a04aa` | none | — | n/a |

Six of the eight have no sibling at all, so the question the plan raised turns out not to
arise for most of this scope. It arises for `cn04` and `ls20`, and the answer is no in both.

**Added 16-Sep-2026: the four games with a recording on disk but no table** (pass B for the
pilot in `docs/plans/2026-09-16-pass-d-e-pilot.md`):

| game | sibling in manifests | sibling source in repo | may cite sibling |
|---|---|---|---|
| `dc22-fdcac232` | `dc22-4c9bff3e` | **no** | no — cannot be diffed |
| `ft09-0d8bbf25` | none | `ft09-9ab2447a` (no replay of it) | **no** — 43 lines differ, ACTION6 branch 22 lines apart |
| `ka59-38d34dbb` | `ka59-9f096b4a` | **no** | no — cannot be diffed |
| `m0r0-492f87ba` | `m0r0-dadda488` | **no** | no — cannot be diffed |

Three of the four have a stale build in `published-replays.json` (10 rows each) with no source,
the same situation as `cn04`; none is a live build. Worth knowing when reading these tables:
two games fall back to the level's starting layout **without a RESET row** — m0r0 when a piece
touches a hazard, dc22 when the player sinks (which also costs 20 steps) — and in ka59 a click
on nothing still spends a step, where in ft09 and lp85 it is free.

**The consequence plan §1(a) was bracing for holds.** The 16 source-less builds stay
ineligible: a run on `cn04-65d47d14` cannot produce a record meeting the acceptance criterion,
because the only source that could back its citation is not in this repo. That is a finding
about repo coverage, not a labelling problem to work around.

### The live-build rule reaches the same answer by a different route

Commit `649e53a` landed the Boss's eligibility rule while this pass was being built: a run
counts only if its `game_id` is still the live build, because ARC Prize rebuilt these games and
an early replay is a replay of a *different game*. That rule and the measurement above agree,
and each covers the other's gap:

- **The measurement** says a citation cannot cross a build boundary. That holds whatever the
  lineup does.
- **The rule** says you would never want to, because the other build's runs are out of scope.
  Every sibling named in these tables — `cn04-65d47d14`, `ls20-cb3b57cc`, and since 16-Sep
  `dc22-4c9bff3e`, `ka59-9f096b4a` and `m0r0-dadda488` — is a stale build. `sibling_is_a_live_build` records this per game and
  `test_no_sibling_named_in_a_table_is_a_live_build` asserts it, so a lineup change surfaces as
  a test failure rather than mid-labelling.

**A correction this forces.** An earlier draft of the `ls20` table said the first-party `ls20`
win (`6184a865…`, 7 levels, 378 actions, 0 resets) was eligible and simply had to cite
`ls20-cb3b57cc/ls20.py`. Under the live-build rule it is **not corpus input at all** —
`ls20-cb3b57cc` is not in the current lineup. The table now says so.

## Cross-game findings

Four things fell out of reading eight dispatch regions that no single table says:

1. **`arcengine` is vendored — this finding is RESOLVED, and it is kept because the resolution
   is the point.** Only `bp35` and `lf52` handle `ACTION7` and `RESET` in their own source. For
   the other six games that meant `RESET` had no citable line anywhere in this repo, so a
   `RESET` record on `g50t`, `cd82`, `cn04`, `wa30`, `lp85` or `ls20` could not be written at
   all — while `RESET` is the only recovery primitive on 19 of the 25 live builds and recovery
   is the metric the corpus exists to move. The corpus could record recovery only on the games
   least representative of it. **The engine is now vendored at `vendor/arcengine-0.9.3/`** and
   every table carries an `engine` block holding the citation; see
   [`../../../docs/trace-findings/2026-09-15-lp85-step-budget-and-the-uncitable-reset.md`](../../../docs/trace-findings/2026-09-15-lp85-step-budget-and-the-uncitable-reset.md)
   §5 for why that option and not the three alternatives. **`ACTION7` is NOT resolved by this**:
   it has no engine branch either, and on the 19 builds that do not offer it there is nothing to
   cite because there is nothing that runs.

2. **Dead dispatch branches are common.** `bp35` handles `ACTION1`, `ACTION2` and `ACTION5`
   but offers none of them; `lf52` handles `ACTION5` and does not offer it. A table entry with
   `"offered": false` must never back a record — there is no row in any recording that could
   have run it.

3. **An action can be swallowed before dispatch.** `g50t:2791`, `cd82:614` and `cd82:617`
   discard the submitted action while an animation drains; `lf52:5778` discards it and
   auto-undoes twice after a death. On those rows the board may not change *for a reason that
   has nothing to do with the action chosen*. A record that reads such a row as a falsified
   prediction is wrong about its own evidence.

4. **The object-dependent verb is not a cn04 quirk.** It appears three times in eight games:
   `cn04` `ACTION5` (rotate vs expand, on stack length), `wa30` `ACTION5` (drop vs attach vs
   pick up, on what overlaps), and `lf52` `ACTION6` (edit a cell vs **reset the level**, on
   where the click lands). `lf52`'s is the sharpest — the same action name either edits one
   cell or throws the level away, decided by whether the click was inside a 16×16 corner.
   This is the falsified-prediction material the corpus exists to hold.

## Running the drift test

```bash
python3.13 -m unittest scripts.test_dispatch_tables -v
```

It re-reads every `source_file` and checks every anchor. It does not need any recording, so it
runs on a machine that has never called the replay API.
