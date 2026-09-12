<!--
Author: Claude Opus 5 (Bubba)
Date: 12-September-2026
PURPOSE: One page per game for the seven weakest of the official 25, naming the single
mechanic that makes each one hard, each cited to its own source. Companion to
2026-09-12-bottom-seven-and-the-moving-frame.md, which holds the population statistics and
the camera finding. This file is the "what is this game actually doing" layer, and it is the
input to the synthetic-composition write-up in autoresearch-arena.
SRP/DRY check: Pass — sk48, wa30, bp35 and g50t have deeper single-game docs on this branch;
this does not restate their traces, only the one mechanic each and the line that proves it.
-->

# The bottom seven: what each one actually is

Line numbers are into `docs/static/games/src/<id>/<id>.py`.

## sk48 — ordered carriage with tip-only access

Two paired skewers extend segment by segment, threading colored items as they grow. The win
check walks your rod and compares the threaded colour sequence against the partner rod's,
item for item. Access is at the tip only, so the load is a stack: what went on last comes off
first. Level 4 onward asks you to transfer a load between two skewers in a *different* order
than you can unload it.

Distinct thing: **the goal is a sequence, held inside a carried object, with LIFO access.**
Nothing else in the 25 has ordered inventory. Also: `ACTION6` transfers control between
skewers rather than actuating anything, and `ACTION7` is a free undo.

## bp35 — a camera that follows you up a shaft

`bp35.py:4028` sets `camera.rczgvgfsfb = (0, player.grid_y * 6 - 36)`. x is pinned, y tracks
the player. The game then adds the offset back to interpret a click (`:4269`).

Distinct thing: **the frame is a moving window, so two frames are in different coordinate
systems.** A chaser below gains only when you fail to rise, which is what makes the scroll
load-bearing rather than decorative.

## ls20 — a carried attribute vector, rewritten by the floor

The player carries three independent attributes. A lock opens only when you stand on it *and*
all three match that lock's spec — `bejndxqqzf` (`:2018`) is a three-way equality. Every lock
in the level must be satisfied, and each is consumed when it is (`pbznecvnfr`, `:2020`).
Transform tiles rewrite one attribute as you walk through them.

Distinct thing: **the same tile helps or hurts depending on what you are currently carrying.**
Also `aqygnziho = 3` (`:1821`, reset in `on_set_level`): three lives per level, which nothing
tells the agent about.

## g50t — your own past run, replayed against you

`ACTION5` is rewind (`:2802` → `pmlawcgvcp`). The grey thing is a replaying ghost of your last
attempt. The timer advances one cell per *two* counted actions (`tmwgfkaqxj`), and actions
consumed by an animation are not counted at all (`step`, `:2782`).

Distinct thing: **time is both the resource and the manipulable.** Rewinding is how you
progress and how you create the hazard.

## lf52 — scrolling rooms with a ferry, and a budget in a different unit

`_get_valid_actions` (`:5852`) builds camera-corrected click coordinates by subtracting
`camera.cdpcbbnfdp` (`:5859`) — horizontal scroll. Peg-jump elimination inside rooms, a cart
on a rail between them. `STORES_UNDO = True` (`:144`) puts `ACTION7` in the action list.

Distinct thing: **multi-room traversal where the rooms are not all on screen.** The budget
counter ticks only on committed moves (`:5255`, `:5313`) with a +20 penalty (`:5783`) against
caps of 64 / 320 / 640 (`:5749-5758`), so the budget and the action count are different
numbers.

## wa30 — a contested board, not a puzzle

Two factions with different goal squares (`wyzquhjerd` yours, `lqctaojiby` theirs). Both move
after every single one of your actions. A crate counts only while it is on your goal and held
by nobody, so a rival can lift a finished crate off your square. Standing on a rival and
pressing SPACE deletes it from the board permanently.

Distinct thing: **another agent pursues its own goal state and can un-do your completed
work.** Level 1 is a puzzle; from level 2 it is a game with an opponent.

## tn36 — the controls are an encoded number

`qaeirkuwro` (`:1933`) is `sum(1 << i for i, m in enumerate(switches) if m.on)`. Clicking
toggles bits; the assembled integer is an opcode that moves, rotates or scales a token.
Several registers form a word (`vkuvtkaerv`, `:1980`), and a panel tagged read-only
(`rpqwgvzwdv`, `rawolunrbj` returns False at `:2009`) displays the target encoding you are
trying to match.

Distinct thing: **you never touch the thing you are moving.** The control surface is a value
to be composed, and the reference panel is a spec, not scenery.

## The common shape

Six of the seven put the thing that decides the level *outside* the current board picture:

| game | where the deciding state lives |
|---|---|
| sk48 | the ordered load on the rod |
| bp35 | off-screen, above and below the window |
| ls20 | three attributes carried by the player |
| g50t | the previous run |
| lf52 | other rooms, off-screen |
| wa30 | the rivals' intentions |
| tn36 | a number encoded in a switch bank |

Every prompt line we ship describes the *board*. Not one of these seven is decided by it.
