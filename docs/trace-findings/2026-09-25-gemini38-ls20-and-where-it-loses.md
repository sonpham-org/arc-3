<!--
Author: Claude Opus 5.5
Date: 25-September-2026
PURPOSE: Where Gemini 3.8 Flash fails, including where it fails worse with its memory kept
(Provider Adapter). Part 1 lines Gemini's six runs per game up against our own Flash-Next runs,
read from the ARC3 Railway database. Parts 2-4 read every Gemini run on ls20 (Locksmith), bp35
(Buoyant Pontoons) and lf52 (Leapfrog) from the replay frames and the model's reasoning. Part 5 is
tr87 and vc33. Part 6 is what the failures have in common.
Updated 25-Sep-2026 (Claude Opus 5.5): added bp35, lf52 and part 6; re-read and corrected part 1.
SRP/DRY check: Pass. Mechanics are cited to arc-explainer/shared/arc3Games/{ls20,bp35,lf52}.ts and
to 2026-09-15-ls20-lives-and-the-filtered-reset.md, not restated. The memory-kept win on g50t is
2026-09-25-gemini38-slippery7-kept-memory.md.
-->

# Gemini 3.8 Flash: where it loses

**Sources.** Gemini: the 150 public replays behind https://arcprize.org/results/google-gemini-3-8-flash
(recorded 10-Sep-2026), 25 games × high/medium/low × plain ("Standard") and memory-kept
("Provider Adapter"). Ours: `arc3_game_scores` joined to `arc3_runs` in the ARC3 Railway Postgres,
read-only, every run whose model id contains `Flash-Next` (373–399 runs per game, 14-Aug to
25-Sep-2026). Our runs are time-capped per game and take fewer actions than Gemini's (median 81 on
bp35, 137 on lf52, 207 on ls20), so this compares outcomes, not equal effort.

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

On the fifteen games not listed, Gemini's memory-kept median is ahead of our median.

Our typical run is level with or ahead of Gemini's memory-kept runs on tr87, bp35, lf52 and vc33
(one of its three vc33 runs cleared nothing in 35 actions). On ls20 its memory-kept runs clear one
more level than our median, but that is two of seven, and its plain high run scored about twice
its memory-kept high run there. Against its plain runs we are also ahead on tu93, ft09, sb26, re86
and g50t.

## 2. ls20 (Locksmith), all six runs

| run | levels | actions | lives lost | resets on purpose | game overs | actions on level 2 |
|---|---|---|---|---|---|---|
| plain high | 2 | 271 | 1 | 4 | 0 | 103 |
| plain medium | 1 | 207 | 3 | 0 | 0 | — |
| plain low | 1 | 650 | 12 | 0 | 4 | not cleared |
| memory kept high | 2 | 629 | 13 | 0 | 4 | 241 |
| memory kept medium | 2 | 642 | 17 | 0 | 5 | 252 |
| memory kept low | 1 | 641 | 20 | 0 | 6 | not cleared |

Lives and the step meter are read from the frames: the three pips at the right of row 61 and the
meter cells in the same row. No run cleared the third level.

1. **It spends every life and never resets on purpose.** Five of the six runs ride each life until
   the meter runs out, lose all three, get a game over, and start the level again. The one run that
   reset on purpose (plain high) did it four times, with the meter nearly empty and lives in hand.
   It lost one life in the whole run and cleared level 2 in under half the actions of the
   memory-kept high run. Its per-turn notes carry the meter count every turn ("4 steps
   remaining"). This matches the Boss's ls20 note of 15-Sep: agents do badly because they don't use
   reset to keep their lives.
2. **It replays the same failed route, life after life.** Memory-kept low walked the same route,
   about 22 moves each time (to the rotation tile, bounce on it, meter empty), roughly fifteen
   times in a row on level 2. Memory-kept medium opened level 3 with the same move string five
   times. After each death the reasoning says the timer ran out and it must be quicker, then it
   does the same thing again.
3. **Its plans don't fit the meter.** From level 2 a move costs two meter units, so a life is 21
   moves. The memory-kept high run works this out on level 3 ("21 actions per charge") and plans a
   21-move route, then spends its lives finding out the route is wrong instead of testing pieces
   of it. Memory-kept low used a refill ring in only 5 of its 27 lives.
4. **Level 3's launch pad is never understood, and the map drifts.** Across its lives on level 3
   the memory-kept high run calls the pad a "sweeper", an "elevator drop" to avoid, and a
   "crusher/piston trap". The door moves in its head from the bottom right, to "Door 1" at the top
   left, to "8 up and 1 left". By its last life it believes the shape tile flips the key
   differently depending on which side you step onto it from.
5. **It blames its earlier self.** After a death it writes "the previous agent messed up the key
   rotation" and "a prior assistant got stuck", then re-derives the plan.

Its reading of the rotation tile is not the problem. It describes it as alternating vertical and
horizontal flips; for the level 2 key that gives the same three shapes as three quarter turns, and
it counts the three presses correctly.

## 3. bp35 (Buoyant Pontoons), all six runs

| run | levels | actions | deaths (game overs) |
|---|---|---|---|
| plain high / medium / low | 0 / 0 / 0 | 105 each | 1 each |
| memory kept high | 1 | 334 | 13 |
| memory kept medium | 1 | 257 | 30 |
| memory kept low | 1 | 277 | 11 |

The plain runs never clear level 1: each ends at 105 actions after one death. The memory-kept
runs clear level 1 and then die on level 2 over and over; medium died 30 times in about 240
actions. Level 2 is where the spikes arrive (purple blocks with a yellow-and-white stripe; being
carried into one kills you).

1. **It never identifies the spike as the killer.** Memory-kept high and medium never use the word
   "spike" in any turn. Memory-kept low first says "spike" after 134 turns. Instead they explain
   the deaths as physics: the "creature" is pulled up "with fatal velocity" and "crashes into a
   ceiling", so a death means "slamming into an indestructible ceiling". The frames show a row of spikes just above the open space the ball slides into.
2. **Because the cause is wrong, the check is wrong.** Just before one death the memory-kept medium
   run checks the rows above the block, sees open water, and concludes "no ceiling nearby … a
   completely safe move". The spike row sits just beyond the water it checked. It breaks the block
   and slides up into the spikes.
3. **It repeats the fatal click.** About half of memory-kept medium's thirty deaths come within two
   or three actions of a restart, almost all by clicking the same block straight above the start.
   One of those turns says it clicks there because the summary of its earlier turns ("the
   compaction summary/hint") said to.
4. **It invents a story instead of reading the pieces.** Across one run: a creature with a tongue,
   then a harpoon, then "chicks in cages" to rescue, then a turtle and a jellyfish, with the goal
   moving from the chicks to "Screen 2" to an amber object at the top.
5. **The scrolling view confuses its coordinates.** The medium run notices the view moving early
   on, but keeps mixing screen rows with map rows; after about twenty deaths it is still working
   out that "those rows we were seeing weren't the absolute coordinates".

None of the six runs reached level 4, where the pull first has to be flipped.

## 4. lf52 (Leapfrog), all six runs

Every run clears level 1 (peg solitaire) at a perfect score in about ten actions, then spends the
rest of the game, about 400 actions, on level 2 without clearing it. Level 2 adds a rail cart that
the arrow keys move; the solve is to hop a peg onto the empty cart and ride it to the other room.

1. **No run ever puts a peg on the cart.** Across all six runs and about 2,400 level-2 turns, the
   idea that a peg rides the cart comes up in a handful of turns and is dropped each time. The
   closest are memory-kept medium ("the cart is supposed to manipulate these pegs … the color on
   the cart itself reflects what it's carrying") and memory-kept low ("clicking the block tried to
   move it into the cart … the cart should dock"). Neither is acted on.
2. **Two ways to fail, depending on which half it latches onto.**
   - *Pegs only.* Memory-kept high makes 312 clicks and about 80 arrow presses on level 2. It calls
     the board a "circuit-themed peg solitaire" and a "PICO-8 breadboard" (in about three quarters
     of its level-2 turns), keeps hopping pegs on the top board into dead ends, and keeps clicking
     the restart button and the "lightbulb". It never works out that the arrows move the cart.
   - *Cart only.* Plain high finds by turn 46 that the arrows move the cart and then drives it
     around the track for hundreds of moves as "a cart carrying ore" to "storage slots". Plain
     medium and low also spend most of their level-2 moves on the arrows, several arrow presses
     for every click.
3. **Each half works; it never joins them.** Bubba found the same pattern in Opus 5's lf52 replay
   today (the cart became "the ball" and the pegs "decoys"): when a level adds a mechanic, the
   model either ignores it or drops the one that won the previous level, instead of asking how
   the two combine.

## 5. tr87 (Toggle Runes), all six runs

tr87 is held out: read here, never trained on. The plain runs never clear level 1 (each stops at
270 actions, mostly cycling one glyph with Up). All three memory-kept runs clear level 1 and then
spend about 300 actions on level 2 without clearing it.

1. **It chases the tilt.** Every glyph gets a random quarter turn when the level loads, and the
   tilt means nothing. Gemini treats it as the rule: rotation, flips or tilt come up in 30 to 43
   percent of memory-kept turns, and the high run decides on level 2 that "all the rules are
   rotated 270 degrees". It treats the dictionary wall like an old ARC transformation task,
   numbering "Rules 1–6" and "sub-boxes" and turning each glyph into rows of 1s and 0s.
2. **It never sees level 2's one new idea.** On level 2 a dictionary entry can turn one glyph into
   two or three, so the answer row is longer than the phrase. No run says so in more than four
   turns; they keep matching glyph for glyph.
3. **It loses the thread.** The high run builds a catalogue of cycle orders (P0, P1, "P_plus") that
   it loses after compaction, calls the board a "Sudoku puzzle" late on, and ends by reading the
   move-budget strip as if it were a clue.

Our prompt's two goal-panel lines ("find the goal panel first"; "make the board match the
example") took tr87 from nothing to about three levels a pass in the 24-Sep practice runs.

## 5b. vc33 (Volume Control), all six runs

Five of the six runs clear levels 1–3 fast (six to thirty clicks a level). Level 4 adds gates in the
walls: a gate turns orange only when the liquid on both sides is exactly level with it, and
clicking it sends the riders across. Only the memory-kept high run got past it, and that run went
on to win all seven levels. The other four spent about 300 clicks on level 4 and never cleared it.

1. **It never finds the gate's condition.** The stuck runs talk about gates, locks or valves in 14
   to 42 percent of level-4 turns. The plain high run even calls it a canal lock, which is close.
   But none of them sets both sides level on purpose; they pump one pair back and forth
   ("I will click Button 5 … the next logical step") and reset about a dozen times.
2. **The story drifts off the screen.** The memory-kept low run starts level 4 with "beams and
   sections" and ends talking about "a data anomaly" in rows of zeros. The winning run passes
   through its own drift too ("optimize some kind of broadcast matrix") but gets there.
3. **One run never starts.** The memory-kept medium run spent its 35 actions on level 1 unsure
   whether a click takes column-then-row or row-then-column, and the run stopped there with nothing.

## 6. What the failures have in common

- **A wrong cause survives.** On bp35 speed kills, not spikes. On lf52 the cart is cargo, not a
  ferry. On ls20 it blames the timer but never shortens the route or resets to save a life. Once the explanation is wrong, more
  thinking and more memory make the run more consistent, not more correct.
- **Failure teaches nothing.** On ls20 and bp35 it dies, writes a post-mortem, and does the same
  thing next life; on lf52 it circles level 2 for four hundred actions. Kept memory keeps the plan,
  and the plan was the problem.
- **It narrates, it doesn't test.** On these three games it rarely spends one cheap action to check
  a single idea (break a different block after dying under the striped row, put one peg on the
  cart, reset with lives in hand). It plans long sequences and finds out at the end that they fail.
- **It distrusts its own notes.** The memory-kept runs compact their history about every seven
  turns overall, and about every three on bp35. The model then reads its own earlier conclusions as
  "the previous agent" and either overrules them or follows them blindly (bp35's fatal click).
- **It reads the board as numbers.** More than half its memory-kept turns reason in row and column
  ranges. On bp35, the one scrolling game it got far enough into, that is where it loses its place.
