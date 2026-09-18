<!--
Author: Claude Opus 5 (Bubba)
Date: 17-September-2026
PURPOSE: One page per game for the three members of the slippery seven that had no mechanic
write-up anywhere in the repo — dc22, m0r0, tr87 — naming the single mechanic that defines
each, cited to file:line in its own source. Closes the documentation hole named in
2026-09-17-the-slippery-seven.md §7. Also records what the 27B actually did on all twelve
passes of the mass-data run, and offers a labelled hypothesis about which part of each
mechanic the smaller model is failing on.
SRP/DRY check: Pass — this is the "what is this game actually doing" layer for the three
games that lacked one, in the same form as 2026-09-12-bottom-seven-what-each-one-is.md. It
does not restate the model comparison, the per-pass score table or the Kaggle arm numbers;
those live in 2026-09-17-the-slippery-seven.md and are cited, not copied.
-->

# dc22, m0r0, tr87: what each one actually is

Line numbers are into `docs/static/games/src/<id>/<id>.py`. The population statistics, the
Flash-Next vs 27B comparison and the per-arm Kaggle table are in
`2026-09-17-the-slippery-seven.md` and are not repeated here.

## dc22 — reach the exit across a floor that a switch rewrites

The win check is the simplest in the three: `smxyfelexa` (`:10869`) returns
`self.qnnpcoyzd.x == self.hfuqkxulm.x and self.qnnpcoyzd.y == self.hfuqkxulm.y`. Player on
goal. Everything hard is in the floor.

Available actions are `[1, 2, 3, 4, 6]` (`:9948`) — four directions plus click, and a move is
two grid cells, not one (`ndiyvmxxey = 2`, `:9852`).

Every floor tile's name ends in a digit, and `lcdavdtabp` (`:10401`) cycles that digit inside
a family whose size is counted per base name into `usmccgsno` (`:10015`). A tile is therefore
one of N states. **`ACTION6` on a lever advances every tile that shares the lever's letter to
its next state at once.** The levers are sprites tagged `buezna` carrying a single-character
tag — `a`, `b`, `c`, `d` (`:1652`, `:1665`, `:1678`, `:1704`, `:1717`); the click resolves the
lever, takes its one-character tag, and `ilvrmetiiv` (`:10274`) collects every sprite anywhere
on the board carrying that letter. The group is then rewritten at `:10673-10686`: the current
tile is set `REMOVED` and its successor is set `INTANGIBLE` when tagged `omvz`, `INVISIBLE`
when tagged `inzejtible`, `INTANGIBLE` when tagged `buezna`, and `TANGIBLE` otherwise.

Those interaction modes are the floor. The ground test `sxnzvaqltp` (`:10384`) returns a
sprite **only** when that sprite's `_interaction == InteractionMode.INTANGIBLE` (`:10396`) —
intangible is standable floor, tangible is wall, removed is open air. When the test comes back
`None` under the player the game sets `guspipewt = True` (`:10813-10816`) and falls, and the
fall is charged through `ykevdpbntc` (`:9890`), which is `current_steps -= 20`. Ordinary
actions are charged one at a time by `ncuydqtllw` (`:9885`). The budget comes from each level's
`StepCounter`: 128, then 192 three times, then 512, then 1024 (`:9622`, `:9647`, `:9677`,
`:9709`, `:9752`, `:9830`). One misjudged click costs twenty of them.

One further consequence of a click: if the player is standing on a tile in the group being
cycled, `pmmrygpdgl` finds the paired tile and the player is moved to it
(`:10669-10672`). **The switch can relocate you.**

Distinct thing: **the click is non-local — it retargets floor anywhere on the board, and the
same click can move you and open a hole under you.**

## m0r0 — one key, four bodies, four sign-flipped frames

Four tokens, named `pikgci-toljda-leklkn`, `pikgci-toljda-rivmdg`, `pikgci-boweok-leklkn`,
`pikgci-boweok-rivmdg` (`:56`, `:66`, `:76`, `:86`). A direction key moves all four in the
same step, each through its own sign transform (`:793-801`):

| token | applied |
|---|---|
| `toljda-leklkn` | `(+dx, +dy)` |
| `toljda-rivmdg` | `(-dx, +dy)` |
| `boweok-leklkn` | `(+dx, -dy)` |
| `boweok-rivmdg` | `(-dx, -dy)` |

Two mirror axes, so one keypress is four simultaneous moves in four different frames. Each is
resolved independently by `jpwxcqabja` (`:852`), which reverts that token alone on contact with
a wall (`wahtyt`, `:861`), a block (`xbso`, `:866`) or a closed gate — so the four
desynchronise as soon as one of them is stopped and the others are not. That desynchronisation
*is* the puzzle: symmetric motion can only be broken by geometry.

The goal is collision, not arrival. Any two tokens ending a step on the same cell are added to
`okpvcjupabr` and set `INTANGIBLE` (`:834-837`); two tokens that swapped adjacent cells are
placed on the midpoint between them and count as having met (`:821-826`). When no unfinished
token remains the level ends (`:848-849`). Nothing marks a target square, because there is no
target square.

`ACTION6` clicking a `mosdlc` block selects it and sets `pyhtlpzlmnr = False` (`:722`), after
which arrows drive that one block alone; clicking anywhere else returns to collective mode
(`:738`). `mosdlc` is tagged `xbso` (`:50`) — the same tag `jpwxcqabja` blocks on — so **the
blocks you can push are the walls you use to break the symmetry.** Coloured gates `gayktr-*`
open while a token stands on the matching `unobxw-*` plate (`xxlavvheeu`, `:878`, setting
`REMOVED` at `:906` and `TANGIBLE` at `:908`).

The hazard is severe. Any token finishing a step on a `spswjz` tile (`:806-809`) triggers an
animation that restores **every** sprite tagged `sys_click` to the position captured at
`on_set_level` (`:686`, restored at `:703`). All four tokens carry `sys_click` (`:59`, `:69`,
`:79`, `:89`) and so does `mosdlc` (`:50`): one touch snaps the entire board back to its
opening layout. Already-merged pairs stay merged, but all positional progress is gone. The
budget is 150 actions (`:664`, `:708`, `:710`), and it is not refunded.

Distinct thing: **you control a symmetry group, not a piece — and the win condition is the
pieces meeting each other, not reaching anywhere.**

## tr87 — edit a string until it is a correct translation under on-screen rewrite rules

Available actions are `[1, 2, 3, 4]` (`:886`) — no click, no undo, no reset.

The board holds a source row (`zvojhrjxxm`) and a target row (`ztgmtnnufb`), split at
`:899-903`, plus a set of rewrite rules. Each rule is anchored on an `iqrduxrukrk` separator
sprite: the code walks left from the separator to collect the left-hand side and right from it
to collect the right-hand side (`:905-918`). So the rules are literally drawn on the board as
`LHS → RHS` pairs.

`bsqsshqpox` (`:1022`) is the win check and it is a parser. It walks the source row from index
zero, and at each position tries every rule until one LHS matches there — `iwbhnvdaao`
(`:1085`) is a plain by-name sequence match. On a match it requires that rule's RHS to appear
at the current position of the target row; if it does not, the whole check returns `False`
(`:1073`). Both cursors advance by the matched lengths. If no rule matches at a position, it
returns `False` (`:1082`). It returns `True` (`:1083`) only when the source row is consumed
end to end and every emitted RHS lined up against the target row exactly.

The player's two verbs: `ACTION3`/`ACTION4` move a cursor along the editable sequence
(`:975-980`), and `ACTION1`/`ACTION2` cycle the glyph under the cursor by one, modulo
`kjgicbtgrt = 7` (`wpbnovjwkv`, `:1002`; constant at `:860`). Seven presses return a cell to
where it started. The budget is 128 actions for levels 1–5 and 256 for level 6 (`:945`), and
running it to zero is a loss (`:999`).

Later levels move the goalposts rather than enlarge the board. Under `alter_rules` (`:787`)
the cursor no longer selects a cell of the target row but a whole side of a rule, and
`ACTION1`/`ACTION2` cycle every glyph in that side together (`:985-987`) — **you edit the
grammar instead of the string.** Under `double_translation` (`:733`) a rule's output is looked
up through a second rule before it is checked, and under `tree_translation` every symbol of an
RHS must itself expand through another rule (`:1043-1057`, double at `:1058-1071`). Level 6 sets all three at once
(`:851-853`).

Distinct thing: **the thing you edit is not the thing that is checked** — you type into the
target row while the win test parses the source row against the rules, and the test is a
single bare boolean with no partial credit.

## What the 27B actually did — hypothesis, not finding

Counted from `artifacts/*_events.jsonl` in
`20260916_102724_qwen38-27b-massdata-25g-4p` on gx10-a108, all four passes each.

Start with the fact that reframes the rest: **`game_over` is zero and `run_status` is
`playing` in all twelve passes.** None of the three ever reached its own loss condition. tr87
pass 1 spent 126 actions against a 128 budget (`:945`) and stopped two short; m0r0 peaked at
41 against 150 (`:710`). dc22's remaining budget cannot be read off its action count — a fall
costs 20 steps (`:9890`) where an ordinary action costs 1 (`:9885`), and the events' `state`
field carries only `NOT_FINISHED` rather than the counter `_get_hidden_state` (`:10872`)
exposes, so how much of dc22's 128 was left is unknown. The wall clock ended these runs, not
the game. **Every pass of all three was still on level 1 when it stopped.**

| game | p0 | p1 | p2 | p3 | dominant action |
|---|---|---|---|---|---|
| `dc22` | 86 | 31 | 41 | 69 | `ACTION6` 43 / 9 / 17 / 27 — half of every pass |
| `m0r0` | 36 | 32 | 41 | 24 | arrows, spread across all four |
| `tr87` | 28 | 126 | 87 | 26 | `ACTION1` 25 / 54 / 69 / 20 |

What this suggests, per game — none of it is established:

- **tr87.** `board_changed` is `True` on **100%** of actions in all four passes. Every glyph
  cycle changes the picture, and `bsqsshqpox` is a bare boolean consulted only inside the
  `ACTION1`/`ACTION2` branch (`:993`), so nothing between "wrong" and "solved" is ever
  reported. Dense visible change, zero gradient. And across all four passes **every board
  state was distinct** — 267 actions, 267 distinct `board_ascii` frames, zero repeats. The
  model was not stuck in a loop; it was generating novel wrong strings indefinitely, with
  nothing in the feedback to say which of them were closer.
- **dc22.** `ACTION6` is roughly half of every pass, and it is exactly the action whose effect
  is not where the click is: it rewrites tiles anywhere sharing a letter, can relocate the
  player (`:10669-10672`) and can charge 20 steps by opening air underfoot (`:9890`). Half the
  actions spent on the one verb whose consequence is invisible at the point of use.
- **m0r0.** `board_changed` is `True` on about 88% of actions — the tokens are moving. Moving
  is not converging when one key drives four mirrored frames. The exact opening frame recurs
  1–3 times per pass, which is what a `spswjz` hazard reset (`:703`) would look like — but see
  not-verified 11.

The shared shape, which is the same one `2026-09-12-bottom-seven-what-each-one-is.md` found in
its own seven:

| game | what you manipulate | what is evaluated |
|---|---|---|
| `dc22` | a lever, here | floor tiles, anywhere with that letter |
| `m0r0` | one direction key | four bodies meeting each other |
| `tr87` | the target row (or the rules) | a parse of the *source* row |

In all three the object of action and the object of evaluation are different objects. This is
a restatement of the mechanics above, not an explanation of the model gap.

## Not verified

1. **No Flash-Next traces were read.** The Flash-Next / 27B comparison in
   `2026-09-17-the-slippery-seven.md` §3 is aggregate means over `runs-index.json`. Nothing
   here narrows *why* Flash-Next scores 9.10 / 9.82 / 13.46 where the 27B scores near zero;
   this doc describes the 27B's failure shape only. §9.7 of that doc stays open.
2. **Whether the prompt shown to the model described any of these mechanics** was not checked.
   A model cannot exploit mirrored frames or a letter-keyed lever group it was never told
   about, and that alternative was not ruled out.
3. **Every traced pass stopped on level 1**, so all per-level flag behaviour is source-read and
   was never observed executing: tr87 `alter_rules` (`:787`), `tree_translation` and
   `double_translation` (`:733`, `:851-853`), and dc22 levels 2–6 including the 512 and 1024
   budgets.
4. **"Clock, not cap" is inferred from absent `game_over` and `run_status == playing`**, not
   from measured per-action latency. No timing data was pulled.
5. **dc22's `piyqze` plate** (`:10849-10857`) sets matching `buezna` levers to `INTANGIBLE`. It
   is *not* verified that this disables them: the click resolver `xodizggcom` skips `REMOVED`
   and `INVISIBLE` but not `INTANGIBLE`, and `ilvrmetiiv` (`:10274`) filters only `REMOVED`, so
   an intangible lever may still be clickable and still be collected into its group. The
   intended effect is unconfirmed.
6. **dc22's `brixto` carried-bridge subsystem** (`:10581-10600`) was read only far enough to
   confirm it exists. It is not described above and was never seen in a trace.
7. **tr87's LHS boundary** — whether the glyph sitting on the separator cell itself belongs to
   the left-hand side — was not pinned down; the walk at `:909-912` starts from the sprite at
   the separator's own position.
8. **m0r0's `ACTION5`** is listed in `available_actions` (`:671`) and appears 1–2 times per
   pass, but no branch of `step` handles it: it leaves both deltas at zero, so it moves
   nothing while still consuming one of the 150 actions. It runs the pairing block (`:811-845`)
   only in collective mode; with a `mosdlc` selected the individual-mode branch at `:768`
   returns first and the pairing block never executes. Whether that is intended was not checked against any other game.
9. **The Boss's human wins on dc22 and m0r0** (`2026-09-17-boss-scorecard-inventory.md`) were
   not pulled and replayed. They would show the intended solution path directly and would be
   the cheapest check on everything above.
11. **m0r0 hazard contact was not confirmed.** The count above is a proxy: frames whose
    `board_ascii` equals the opening frame's. That is consistent with a `spswjz` reset, but a
    token wandering back to its start would look identical, and the frame stream includes
    non-action frames (41–60 frames against 24–41 actions). No hazard event was identified
    directly.
10. **No claim is made that these three mechanics are harder than the other 22.** The three
    were written up because they had no page, not because a difficulty ranking put them here.
