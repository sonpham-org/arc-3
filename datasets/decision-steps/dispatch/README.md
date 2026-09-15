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

## The sibling-build question — settled

Plan §1(a) found 16 of 36 manifest builds have no source in the repo, noted that several look
like build drift rather than missing games, and left open whether a record on one build may
cite a **sibling build's** source. Pass B was told to settle it.

**Answer: no. Line-level citations never transfer between builds.** Not "probably not" —
measured, on every pair in the repo where both builds are present.

Three pairs have both builds under `docs/static/games/src/`, so three pairs could be diffed:

| pair | changed lines | dispatch line, build A → B | what changed |
|---|---|---|---|
| `ls20-9607627b` / `ls20-cb3b57cc` | 3,256 | 1921 → 1420 | re-obfuscated: different identifiers, `GameAction.ACTION1` → `self.action.id.value == 1`, 482 fewer lines |
| `vc33-5430563c` / `vc33-9851e02b` | 2,851 | 2085 → 2112 | 22-line MIT header added, and `GameAction.ACTION6` → `.value == 6` |
| `ft09-0d8bbf25` / `ft09-9ab2447a` | 43 | 2329 → 2351 | **identical dispatch code**, shifted +22 by an added MIT header; `_get_valid_actions` and `available_actions=[6]` dropped entirely |

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

**The consequence plan §1(a) was bracing for holds.** The 16 source-less builds stay
ineligible: a run on `cn04-65d47d14` cannot produce a record meeting the acceptance criterion,
because the only source that could back its citation is not in this repo. That is a finding
about repo coverage, not a labelling problem to work around.

**One useful exception, in the other direction.** The first-party `ls20` win
(`6184a865…`, 7 levels, 378 actions) is on `ls20-cb3b57cc`, whose source **is** in the repo.
That run is eligible — it just has to cite `ls20-cb3b57cc/ls20.py`, not the `ls20-9607627b`
table in this directory. A table for it can be built when pass C pulls the recording.

## Cross-game findings

Four things fell out of reading eight dispatch regions that no single table says:

1. **`arcengine` is not vendored.** Only `bp35` and `lf52` handle `ACTION7` and `RESET` in
   their own source. For the other six games those actions have no citable line anywhere in
   this repo, so an `action_role_source` for a `RESET` record on `g50t`, `cd82`, `cn04`,
   `wa30`, `lp85` or `ls20` **cannot be written**. `cn04`'s recording contains 5 `RESET` rows
   and `cd82`'s contains 1; those rows can be described but not cited.

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
