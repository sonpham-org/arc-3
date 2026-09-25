<!--
Author: Claude Opus 5.5
Date: 25-September-2026
PURPOSE: Where Gemini 3.8 Flash fails, and fails worse with its memory kept (Provider Adapter).
Part 1 lines Gemini's six runs per game up against our own Flash-Next runs, read from the ARC3
Railway database. Part 2 is ls20 (Locksmith), all six Gemini runs, traced from the replay frames
(lives, step meter, resets, per-life move strings) and the model's reasoning.
SRP/DRY check: Pass. ls20 mechanics are cited to arc-explainer/shared/arc3Games/ls20.ts and to
2026-09-15-ls20-lives-and-the-filtered-reset.md, not restated. The memory-kept win on g50t is
2026-09-25-gemini38-slippery7-kept-memory.md.
-->

# Gemini 3.8 Flash: where it loses, and ls20 in detail

**Sources.** Gemini: the 150 public replays behind https://arcprize.org/results/google-gemini-3-8-flash
(recorded 10-Sep-2026). Ours: `arc3_game_scores` joined to `arc3_runs` in the ARC3 Railway
Postgres, read-only, every run whose model id contains `Flash-Next` (373–399 runs per game,
14-Aug to 25-Sep-2026). Our runs are time-capped per game and play far fewer actions than
Gemini's, so this compares outcomes, not equal effort.

## 1. Our typical run against Gemini's six

Levels cleared. "Ours" is the median over all our Flash-Next runs of that game.

| game | ours median (best) | Gemini plain: high, medium, low | Gemini memory kept: high, medium, low |
|---|---|---|---|
| tr87 | 1 (5) | 0, 0, 0 | 1, 1, 1 |
| bp35 | 1 (3) | 0, 0, 0 | 1, 1, 1 |
| lf52 | 1 (4) | 1, 1, 1 | 1, 1, 1 |
| vc33 | 3 (6) | 3, 3, 3 | 7, 0, 3 |
| ls20 | 1 (4) | 2, 1, 1 | 2, 2, 1 |
| tu93 | 3 (7) | 2, 2, 0 | 5, 4, 4 |
| ft09 | 4 (6) | 2, 2, 2 | 6, 6, 6 |
| sb26 | 3 (8) | 1, 1, 1 | 8, 8, 2 |
| re86 | 4 (6) | 4, 2, 2 | 8, 6, 8 |
| g50t | 1 (4) | 0, 0, 0 | 6, 2, 1 |

(Games not listed: Gemini's memory-kept runs are ahead of our typical run on all of them.)

Our typical run is level with or ahead of Gemini's memory-kept runs on tr87, bp35, lf52 and
vc33 (one of its three vc33 runs cleared nothing in 35 actions). On ls20 Gemini's memory-kept
runs clear one more level than our typical run, but that is still only two of seven, and its
plain high run scores twice its memory-kept high run there. Against its plain runs we are also
ahead on tu93, ft09, sb26, re86 and g50t.

## 2. ls20, all six Gemini runs

| run | levels | actions | lives lost | resets on purpose | game overs | actions on level 2 |
|---|---|---|---|---|---|---|
| plain high | 2 | 271 | 1 | 4 | 0 | 103 |
| plain medium | 1 | 207 | 3 | 0 | 0 | — |
| plain low | 1 | 650 | 12 | 0 | 4 | stuck |
| memory kept high | 2 | 629 | 13 | 0 | 4 | 241 |
| memory kept medium | 2 | 642 | 17 | 0 | 5 | 252 |
| memory kept low | 1 | 641 | 20 | 0 | 6 | stuck |

Lives and the step meter are read from the frames: the three pips at the right of row 61 and
the meter cells in the same row. No run cleared the third level.

**What goes wrong.**

1. **It spends every life and never resets on purpose.** Five of the six runs ride each life
   until the meter runs out, lose all three, get a game over, and start the level again. The one
   run that reset on purpose (plain, high) did it with the meter nearly empty and all three lives
   left, four times. It lost one life in the whole run and cleared level 2 in under half the
   actions of the memory-kept high run. That run's per-turn notes carry the meter count every
   turn ("4 steps remaining"). This is the Boss's own ls20 note from 15-Sep: agents do badly
   because they don't use reset to keep their lives.
2. **It replays the same failed route, life after life.** Memory-kept low walked the same route,
   about 22 moves each time (to the rotation tile, bounce on it, meter empty), roughly fifteen
   times in a row on level 2. Memory-kept medium opened level 3 with the same move string five
   times. Each time the reasoning after a death says the timer ran out and it must be quicker,
   and then it does the same thing again.
3. **Its plans don't fit the meter.** From level 2 a move costs two meter units, so a life is 21
   moves. The memory-kept high run works this out on level 3 ("21 actions per charge") and plans
   a 21-move route, but it spends the lives finding out the route is wrong instead of testing
   pieces of it. Memory-kept low used a refill ring in only 5 of 27 lives.
4. **Level 3's launch pad is never understood, and the level map drifts.** Across its lives on
   level 3 the high run calls the pad a "sweeper", an "elevator drop" to avoid, and a
   "crusher/piston trap". The door moves in its head from the bottom right, to "Door 1" at the
   top left, to "8 up and 1 left". By its last life it believes the shape tile flips the key
   differently depending on which side you step onto it from.
5. **It blames its earlier self.** After a death it writes "the previous agent messed up the key
   rotation" and "a prior assistant got stuck", then re-derives the plan. Kept memory is kept,
   but the model does not trust it, so it doesn't build up.

Its reading of the key tile is not the problem. It describes the rotation tile as alternating
vertical and horizontal flips; for the level 2 key that gives the same three shapes as three
quarter turns, and it counts the three presses correctly.

## 3. tr87, briefly

tr87 is held out: read here, never trained on. Gemini's memory-kept high run treats the
dictionary wall like an old ARC transformation task. It numbers "Rules 1–6" and "sub-boxes",
turns every 5×5 glyph into rows of 1s and 0s, and on level 2 decides "all the rules are rotated
270 degrees". It builds a catalogue of cycle orders (P0, P1, "P_plus") that it loses track of
after its context is compacted. Our prompt's two goal-panel lines ("find the goal panel first";
"make the board match the example") took Toggle Runes from nothing to about three levels a pass
on 24-Sep.

## 4. What it says

Kept memory fixes forgetting. It does not fix a bad plan, and on ls20 it helps a bad plan
survive: the model keeps its route and its confidence, burns lives on it, and reads its own
earlier attempts as someone else's mistakes. The plain high run did best because it looked at
the meter every turn and reset before the meter ran out.
