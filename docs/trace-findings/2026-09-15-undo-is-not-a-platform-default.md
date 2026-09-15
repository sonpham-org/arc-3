<!--
Author: Claude Opus 5 (Bubba)
Date: 15-September-2026
PURPOSE: The per-game availability of ACTION7 (undo) across all 25 live ARC-3 builds, read off
the game sources with a file:line citation for every one of the 25, and cross-checked against
the runtime available_actions in every recording on disk. Written because the Retrodict
harness's prompt rule "prefer undo over RESET" is not a tuning choice on most of the lineup --
it names an action 19 of the 25 games do not offer. Companion to
2026-09-15-bp35-undo-costs-a-move.md, which measured what undo COSTS on a game that has it;
this one measures where it EXISTS at all.
SRP/DRY check: Pass -- the bp35 finding owns the move-budget economics of undo on bp35, and
2026-09-15-cn04-object-dependent-verb.md owns cn04's ACTION5 overload. Neither surveys the
lineup. This file surveys the lineup and restates neither's content; it cites the bp35 finding
where the two meet rather than repeating its numbers.
-->

# Undo is not a platform default: ACTION7 exists on 6 of the 25 live builds

**Status:** finding, source-verified 15-Sep-2026 against every one of the 25 builds in
`datasets/decision-steps/current-builds.json`, and cross-checked against the runtime
`available_actions` in all 9 live-build recordings on disk. Every per-game claim below carries
a `file:line` in `docs/static/games/src/`.

---

## 1. The finding

`ACTION7` — undo — is **a per-game design decision, not a platform affordance**. Six of the 25
live builds offer it. Nineteen do not, and in those nineteen the string `ACTION7` does not
appear in the game source at all: not in a dispatch branch, not behind a flag, not in a UI
table. There is nothing to enable.

The consequence is stated plainly because it is a claim about our harness comparison and not
about the games: the Retrodict harness (`ryanbbrown/Retrodict`) coaches its agent to **prefer
undo over RESET**. On 19 of 25 games that rule is not risky advice, or costly advice, or advice
that needs a budget caveat. It is **unimplementable** — it ranks an action that cannot be
submitted above the only recovery primitive that can.

This also generalises an earlier one-off. `as66` was noted as declaring `[1,2,3,4,6]` with no
undo, and that read as a quirk of a withdrawn game
([`2026-09-15-as66-the-withdrawn-26th-game.md`](2026-09-15-as66-the-withdrawn-26th-game.md)).
It is not a quirk. It is the majority case.

---

## 2. The survey, cited

All paths below are relative to `docs/static/games/src/`. "runtime" is
`data.available_actions` on row 0 of that build's recording under
`datasets/decision-steps/v0/recordings/`, where one exists; it was checked against **every**
row of each recording, not only row 0, and is constant in all nine.

### 2a. The six that offer undo

| game | declaration | `ACTION7` handler | runtime |
|---|---|---|---|
| `ar25-0c556536` | `ar25-0c556536/ar25.py:1255` — `available_actions=[1, 2, 3, 4, 5, 6, 7],` | `ar25.py:1694` — `if self.action.id == GameAction.ACTION7:` | no recording |
| `bp35-0a0ad940` | `bp35-0a0ad940/bp35.py:4457` — `self.available_actions: List[int] = [3, 4, 6, 7]`, passed at `:4468` | `bp35.py:4524` — `case GameAction.ACTION7:` | `[3, 4, 6, 7]` |
| `lf52-271a04aa` | `lf52-271a04aa/lf52.py:5723` — `self.available_actions: List[int] = [1, 2, 3, 4, 6] + ([7] if STORES_UNDO else [])`, with `STORES_UNDO = True` at `lf52.py:144` | `lf52.py:5831` — `case GameAction.ACTION7:` | no recording |
| `sb26-7fbdac44` | `sb26-7fbdac44/sb26.py:697` — `available_actions=[5, 6, 7]` | `sb26.py:879` — `elif self.action.id == GameAction.ACTION7:` (also listed at `:760`) | no recording |
| `sk48-d8078629` | `sk48-d8078629/sk48.py:631` — `available_actions=[1, 2, 3, 4, 6, 7],` | `sk48.py:735` — `elif self.action.id == GameAction.ACTION7:` | no recording |
| `su15-1944f8ab` | `su15-1944f8ab/su15.py:936` — `available_actions=[6, 7]` | `su15.py:1107` — `if self.action.id == GameAction.ACTION7:` | no recording |

`lf52` is the only one of the six whose offer is **conditional in source**. `STORES_UNDO` is a
module constant set `True` at `lf52.py:144` and is not reassigned anywhere in the file, so the
`+ ([7] if STORES_UNDO else [])` at `:5723` resolves to `+ [7]` for this build. It is counted as
offering undo on that resolution, and the resolution is stated rather than assumed.

### 2b. The nineteen that do not

Every row: zero occurrences of `GameAction.ACTION7` in the file, verified by grep over the whole
source, and no `7` in the declared set.

| game | declaration | runtime |
|---|---|---|
| `cd82-fb555c5d` | `cd82.py:422` — `available_actions=[1, 2, 3, 4, 5, 6],` | `[1, 2, 3, 4, 5, 6]` |
| `cn04-2fe56bfb` | **no declaration** — `cn04.py:824` calls `super().__init__(game_id="cn04", levels=levels, camera=yrrliudnw)` with no `available_actions` argument; see 2c | `[1, 2, 3, 4, 5, 6]` |
| `dc22-fdcac232` | `dc22.py:9948` — `available_actions=[1, 2, 3, 4, 6],` | `[1, 2, 3, 4, 6]` |
| `ft09-0d8bbf25` | `ft09.py:2284` — `available_actions=[6]` | `[6]` |
| `g50t-5849a774` | `g50t.py:2771` — `available_actions=[1, 2, 3, 4, 5],` | `[1, 2, 3, 4, 5]` |
| `ka59-38d34dbb` | `ka59.py:41111` — `available_actions=[1, 2, 3, 4, 6],` | `[1, 2, 3, 4, 6]` |
| `lp85-305b61c3` | `lp85.py:21330` — `available_actions=[6]` | `[6]` |
| `ls20-9607627b` | `ls20.py:1765` — `available_actions=[1, 2, 3, 4]` | `[1, 2, 3, 4]` |
| `m0r0-492f87ba` | `m0r0.py:671` — `available_actions=[1, 2, 3, 4, 5, 6],` | no recording |
| `r11l-495a7899` | `r11l.py:1418` — `available_actions=[6]` | no recording |
| `re86-8af5384d` | `re86.py:1858` — `available_actions=[1, 2, 3, 4, 5],` | no recording |
| `s5i5-18d95033` | `s5i5.py:2020` — `available_actions=[6]` | no recording |
| `sc25-635fd71a` | `sc25.py:1742` — `available_actions=[1, 2, 3, 4, 6],` | no recording |
| `sp80-589a99af` | `sp80.py:513` — `available_actions=[1, 2, 3, 4, 5, 6],` | no recording |
| `tn36-ef4dde99` | `tn36.py:2581` — `available_actions=[6]` | no recording |
| `tr87-cd924810` | `tr87.py:886` — `available_actions=[1, 2, 3, 4]` | no recording |
| `tu93-0768757b` | `tu93.py:978` — `available_actions=[1, 2, 3, 4]` | no recording |
| `vc33-5430563c` | `vc33.py:1820` — `available_actions=[6]` | no recording |
| `wa30-ee6fef47` | `wa30.py:874` — `available_actions=[1, 2, 3, 4, 5],` | no recording |

**6 with, 19 without, 25 total.** Eight of the nine recordings on disk agree with their source
declaration exactly; the ninth is `cn04`, which has no declaration to agree with.

### 2c. The one build static reading cannot answer, and why that matters

`cn04` never passes `available_actions`. Its `super().__init__` at `cn04.py:824` omits the
argument entirely, so the offered set comes from `ARCBaseGame`'s default — and `arcengine` is an
external package with **no source in this repo** (`cn04.py:4-12` imports it; `find . -name
'arcengine*'` returns nothing and `import arcengine` fails). The nearest thing to an enumeration
in the file is `cn04.py:1171`, `[... for a in [1, 2, 3, 4, 5] if a in self._available_actions]`,
which is a **filter over** the offered set, not the offered set: it can only narrow, and it reads
`self._available_actions` as an input.

Row 0 of `cn04`'s recording settles it: `[1, 2, 3, 4, 5, 6]`. Static reading of `:1171` alone
would have said five actions; the true answer is six.

That is the methodological point, and it is the reason this survey was derived twice rather than
once. **Static enumeration under-reports.** A game that took its action set from the engine
default, or assembled it behind a flag as `lf52` does, could have hidden an `ACTION7` from a
grep for `available_actions=`. The guard used here is the second grep — `GameAction.ACTION7`
over the whole file — which returns **zero hits on all nineteen**. A build cannot dispatch an
action it never names, whatever its declared list says, so the nineteen are safe on the
under-report risk in a way the declaration alone would not establish.

### 2d. Two internal "undo" helpers that are not ACTION7

Both are in the 19, and both would be mis-scored by a grep for the word `undo`:

- `ls20-9607627b/ls20.py:1660-1662` declares `_undo_x` / `_undo_y` / `_undo_dir`, and
  `ls20.py:1708-1717` restores them. This is **not player-addressable**. Its only call site is
  `ls20.py:1947`, inside the move handler: when the player's move is blocked, the engine rolls
  the NPC movers back one step. `ls20` declares `[1, 2, 3, 4]` and its recording confirms it.
- `sc25-635fd71a/sc25.py:1833` assigns `self._undo_state = None`. That is the **only**
  occurrence of the name in the file — it is never read and never set to anything else. Dead.

Searching the lineup for the *concept* of undo therefore returns a different, larger set than
searching for the *action*. Only the action is submittable through the API, and only the action
is what a harness prompt can prefer.

---

## 3. The worked example: `lp85`, where RESET is the whole recovery vocabulary

`lp85-305b61c3` is the clearest case in the lineup because it is a **one-action game**.

- `lp85.py:21330` declares `available_actions=[6]`. Constant across all 416 rows of
  `129ddf21-d7ba-4ca0-9577-0cea2af042b6` — measured, not assumed.
- That run is 409 `ACTION6` plus 7 `RESET` and nothing else.
- `ACTION6` carries coordinates: `action_input.data` is `{game_id, x, y}`. It is a click.
  `lp85.py:21374` is the branch; `lp85.py:21377` resolves the click to a grid cell; a click that
  hits no button is a total no-op and does not even run the level-complete test
  (`lp85.py:21409`). Full dispatch: `datasets/decision-steps/dispatch/lp85-305b61c3.json`.

So on `lp85` there is exactly one thing to do and exactly one way to take it back. **RESET is
not the worse of two recovery options. It is the only one.**

The run makes that concrete at row 175 — the only `GAME_OVER` in any first-party recording. The
`ACTION6` on row 175 killed the board; row 176 is a `RESET` that executed. A
falsified-prediction/observed-correction pair with **nothing to argue about**: no reviewer can
say the player should have undone instead, because there was no undo to take. Compare the bp35
material, where every death-recovery is entangled with an undo that was available, cost a move,
and sometimes failed — see
[`2026-09-15-bp35-undo-costs-a-move.md`](2026-09-15-bp35-undo-costs-a-move.md).

Five further `RESET`s on level 8 (rows 269, 294, 311, 365, 386) follow **no death at all**. The
board was alive and the plan was judged unwinnable. On a game with undo those would be ambiguous
— abandoning a plan versus stepping back through it. Here they cannot be anything but the
former.

This run is in `datasets/decision-steps/first-party-replays.json` under guid
`129ddf21-d7ba-4ca0-9577-0cea2af042b6`: WIN, 8 levels, 415 actions, 6 resets, score 76.389.
(Cited by guid rather than by row number on purpose — that file's rows are sorted by `game_id`,
so an index moves whenever a row is added ahead of it.)

---

## 4. What this means for the harness comparison

Stated as claims about our own side, with what was and was not measured marked:

1. **"Prefer undo over RESET" is not a prompt to tune down on 19 of 25 games; it is a prompt to
   delete.** An agent holding it either wastes a turn submitting an action the API will reject,
   or — worse — treats RESET as a last resort on a game where RESET is the *first* resort. The
   `lp85` run spends 6 of its 415 actions on RESET and wins.
2. **Any harness rule phrased over the action set needs a per-game resolution step.** The action
   set is not a constant of the platform. It ranges from `[6]` (`ft09`, `lp85`, `r11l`, `s5i5`,
   `tn36`, `vc33`) to `[1,2,3,4,5,6,7]` (`ar25`) across the same 25 games.
3. **Where undo does exist it is not free, so the rule is not simply right on the other 6
   either.** On `bp35` an error costs one move from the level budget and undoing it costs
   another, while RESET refunds the whole budget — measured in the bp35 finding, not re-derived
   here.
4. **Not measured:** whether Retrodict actually submits `ACTION7` to a game that does not offer
   it, and what the API returns when it does. That is a live-API question and no request was
   made for this document. The claim here is about what the 25 sources offer, which is checkable
   offline and is checked above.
5. **Not measured:** the *other* 24 games' recovery economics. Only `bp35` has had its budget
   arithmetic read. Whether RESET refunds a level budget on `lp85` or `ka59` is unknown and is
   not assumed from `bp35`.

---

## 5. Method note

Derived twice on purpose, because the first method is known to under-report.

1. **Static:** grep each of the 25 sources for `available_actions`, `ACTION7`, `STORES_UNDO` and
   `undo`, then read the declaration in context. Resolves 24 of 25; `cn04` has no declaration.
2. **Runtime:** `data.available_actions` from every row of all 9 live-build recordings on disk.
   Runtime wins on disagreement. There was one disagreement to win — `cn04`, where static had no
   answer at all — and eight exact agreements.

The 16 builds with neither a recording nor an ambiguity rest on the static read **plus** the
zero-hit `GameAction.ACTION7` grep, which is the part that makes the negative safe: the declared
list says what is offered, and the absent dispatch branch says the game could not have handled
it if it were.

The lineup itself was enumerated from `datasets/decision-steps/current-builds.json`, not from any
prior list, so a build that entered or left the live 25 would change this document rather than
be silently inherited by it.
