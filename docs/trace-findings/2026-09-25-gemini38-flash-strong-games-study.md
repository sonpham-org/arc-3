<!--
Author: Claude Opus 5.5 (Bubba)
Date: 25-September-2026
PURPOSE: Why Gemini 3.8 Flash does well on ARC-AGI-3 games that are hard for us (Ghost Twin, Warehouse, Kick Away,
Sigil Caster, Deck Control, Toggle Navigator), read from its reasoning summaries in ARC Prize's public replays, with
Opus 5 and Gemini's own standard-harness runs as contrast. Asked by the Boss in #arc-3, 25-Sep-2026 14:09 ET.
Per-game sections were written by two helper agents from the raw recordings; numbers checked against the session API.
Companion doc (Ghost Twin turn by turn, both harnesses): 2026-09-25-gemini38-slippery7-kept-memory.md.
SRP/DRY check: Pass. Mechanics cited to arc-explainer/shared/arc3Games/<code>.ts.
-->

# Gemini 3.8 Flash on its strong games: what it does that we don't

## Headline
Finding the rules is not what separates the good runs. Every run, Gemini's and Opus's, finds each game's key rule
almost at once. What decides the score is whether the rule SURVIVES: a new level, a restart, a budget-out. The
provider-adapter runs keep the model's own condensed summary of its reasoning (compaction fires every ~10-14 steps at
~180k tokens) and keep playing the rule; the standard runs and Opus carry only hand-written notes and meet the same
rule again as if new.

## Its habits (recur across games)
1. **One test per control, stated as a prediction, checked on the board** (Warehouse steps 1-4; Deck Control presses
   each button once and writes down the two states it causes before planning).
2. **Judges by what its own piece did, not by the widget** ("it shrank to fit perfectly").
3. **Reads demos and legends as codebooks** (Toggle Navigator tabs; Sigil Caster's opening spell demo, which it
   called a "Simon Says" memory game: wrong story, right clicks, five levels under the human baseline).
4. **Plans on a clock with a controllable ghost** (Ghost Twin, below).
5. **Treats its compacted summary as a fallible witness** and overrules it when the frame disagrees.
6. **Names mechanics early; the name steers play.** Good names ("tether", "cannon", "curling") play cleanly; a wrong
   name ("teleporter" on Kick Away's last level) is chased with full confidence.
Shared blind spot: budget bars. Both Gemini and Opus read a draining step bar as progress at times.

## 1. Ghost Twin (replay 323ceca8, provider adapter, 6 of 7 levels)
Level actions vs the game's baseline (session API): 30 vs 78, 47 vs 175, 161 vs 179, 31 vs 230, 85 vs 96, 240 vs 54,
last level 335 (not cleared). Its reading of the game:
- It works out that the interact action commits a recording and a CLONE replays the recorded moves ("Clone 2"), and
  from then on treats the clone as something it programs.
- It schedules the clone by time step ("at t=11 it performs ACTION4 ... at t=12 another ACTION4 into the goal
  enclosure") and times the live piece against it; it parks the clone on a switch ("Clone 2 is permanently standing on
  Switch A") to hold a gate open while the live piece walks through.
- Before every move it re-reads the exact cells on the path ("column 43 is 5, walkable") and only then moves.
- Level 3 is the one it struggled on (161 actions, near the baseline); level 4 then takes 31 actions against a baseline
  of 230 because the clone-on-switch plan carries straight over.
Opus 5 on the same game (9ec9ae2e, 0 levels) argued about which way its piece moves and saw the ghost only near the
end; Gemini's standard-harness runs keep re-deriving it. Turn-by-turn contrast: 2026-09-25-gemini38-slippery7-kept-memory.md, section 2.

## What to try in our harness (Son's prompt, Flash-Next on Kaggle)
1. **Carry the model's own condensed reasoning across turns**, not only its visible notes: a rolling summary of its
   last turns' thinking, refreshed every ~10 steps, fed back each turn. This is the single biggest lever in the data.
2. **Show the playback frames after each action by default** (our model called Toggle Navigator's run button
   "decorative" because it only compared the settled before/after boards).
3. **A persistent rule card that survives level changes and resets**, with an explicit "these rules held last level;
   check them first on the new one" line.
4. **Budget line:** "the bar that shrinks with every action is your remaining moves, not progress."

---

## 2. Warehouse and Kick Away (helper findings)


Read-only study, 25-Sep-2026 (Claude Opus 5.5, subagent). Recordings downloaded from the ARC Prize API into
`~/bubba-workspace/arc3-kaggle/gemini38-replays/` (`wa-*.jsonl`, `ka-*.jsonl`, digests `*-digest.txt`, session
metadata `sess-<guid>.json`). Not committed. Every per-level number below is from the session API
(`level_actions`, `level_baseline_actions`) or counted from the recording; step numbers are recording line
indices (step 0 = initial RESET).

**Compaction check (from the raw recordings, `state.harness_compaction`):** Warehouse provider-adapter run: 208
compaction events; Kick Away provider-adapter run: 277. Both Standard-harness runs: zero. In the provider-adapter
runs compaction fires roughly every 10-14 steps once the context reaches roughly 175-185k tokens (Warehouse step
13: compaction input 185,513 tokens, then step 14 drops to 28,644; Kick Away steps 8 and 21: 182,793 and
175,119). After the first compaction the visible output shrinks to
just the action, but the thought summary keeps quoting "the summary" / "the plan provided" — the compaction text
is acting as the rulebook and plan carrier.

---

## 1. Warehouse

Runs: provider-adapter high `c9c874f7` (7/9), Standard high `49da413c` (4/9), Opus 5 Standard high `086c9f8f` (3/9).

| Level | Budget | Baseline | Gemini PA | Gemini Std | Opus 5 |
|---|---|---|---|---|---|
| 1 | 200 | 71 | **41** | 59 | 44 |
| 2 | 70 | 119 | **70** | 353 | 67 |
| 3 | 100 | 183 | **76** | 282 | 276 |
| 4 | 100 | 98 | **57** | 91 | 490 (fail) |
| 5 | 125 | 368 | **107** | 1387 (fail) | — |
| 6 | 75 | 68 | 140 (64 on the winning attempt) | — | — |
| 7 | 125 | 79 | 232 (106 on the winning attempt) | — | — |
| 8 | 150 | 442 | 1833 (fail, 12 budget-outs) | — | — |

Gemini PA: 14 resets, **every one a budget-out** (state GAME_OVER on the previous step, checked for all 14),
none voluntary. Levels 1-5 all under the game's own action baseline (`level_baseline_actions`).

### How it discovered the mechanics (level 1)
- Steps 1-4: one test per arrow, each stated as a prediction and checked. Step 3 already reads facing from the
  sprite: "the zero 'head' is at the top when the player is moving up, and at the bottom when moving down."
- Step 6 identifies the budget bar unprompted: "It has to be a step counter!"
- Step 7 predicts a Sokoban push; step 8 sees it fail and pivots in one move, using the cue it had just noticed
  (the faced crate's outline turning colour 3): "Box D became highlighted in green when the player faced it, but
  moving UP did not move through or push the block. This indicates an interact/action button." It presses
  Action 5 once, sees the outline turn black (step 9: "Is this an 'attached' state? Is the box now GRABBED?"),
  moves once to test (step 10), and releases on target (step 11). The full grab-drag-release cycle is found in
  four actions.
- Steps 13-26: routes the other two crates with explicit path planning, e.g. step 25 compares two routes and
  picks the one "one less step". Level 1 cleared at step 41, against a 71 baseline.

### Levels 2-5: watch first, then exploit the helper
- Step 43: the orange helper appears to move on its own ("Did I make that happen somehow?"). Step 46 chooses a
  move *because* it keeps the player out of the way and lets it watch: "Moving right ... allows me to observe
  Object 12's actions." Step 48: "Object 12 is a helper bot, a forklift, a pusher!"
- Step 60 designs an action to be informative either way: "If Bot 12 grabs Box 1 ... its border will turn 5. If
  it doesn't grab it ... So, I will immediately know what Bot 12 does, either way!" Its theory (the helper patrols
  one row and collects crates left on the row above) is over-fitted — the source says the helper walks the
  shortest path to any loose crate — but it was good enough to feed crates to the helper. Level 2 cleared at
  step 111 with one pixel of budget bar left (step 110), 70 actions against a 70-move budget.
- Level 3 (the speckled line nobody can cross): step 112 notices "Bot 12 is at the opposite side of col 8 as the
  other boxes!"; step 113: "I *have* to get the boxes from the player's side onto Col 8 for Bot 12 to pull them
  into the target zone!" After placing them it deliberately idles by walking into the wall (step 160: "Given
  that Bot 12 appears to be on track, the player's role is now secondary"). 76 actions against 183.
- Levels 4 and 5: 57 vs 98 and 107 vs 368, both first attempt.

### What it got wrong, and how it recovered
- **Wrong cost model.** Step 60: "That confirms it, Action5 did *not* count as a step." The game source says
  every action costs one, Action 5 and blocked moves included; the bar is 64 pixels wide for budgets of 70-200,
  so single actions sometimes don't move it visibly. This belief underpins its habit of "free" idling by
  bumping walls (step 160 onward), which was harmless on level 3 but costly later.
- **Level 6 thief misread, then fixed on the retry.** First attempt it took the purple thief for a delivery
  bot running a "box-swapping puzzle" (step 358: "Bot 15 will take Box 1 to Area B, and Player
  needs to move Box 2 to Area A"), waited for it to finish, then found by experiment that Action 5 on the stalled
  thief removes it (step 368: "Bot 15 has vanished / been collected"). Budget ran out at step 426. On the retry
  it watched the thief push the crate out of the bay (step 432: "Critical Discovery: Entity 15 pushed the West
  box!"), removed it again at step 442, and at step 466 reframed the goal correctly: "we need to retrieve Box 2
  from the starting chamber and bring it into Target Zone A alongside Box 1." The winning attempt took 64
  actions against a 68 baseline — the cleanest "reuse prior work" example in either game. Along the way it also
  formalised the carry rule (step 448: "ACTION5 established a rigid tether: Box 1 maintains an offset ... and
  moves along with the player!").
- **Level 8: the lesson was found once and not kept.** Two helpers and two thieves. First attempt, step 771:
  "If we destroy them, the Cyan robots continue to load the docks!"; steps 791-793 it intercepts and removes the
  second thief ("Those hostile White robots are finally gone"). Counting thief pixels (colour 15, 16 px per thief)
  in each frame: the count reaches zero only in that first attempt (step 792). In three later attempts it halves
  at some point; in the other nine it never drops below 28 (partial occlusion, not a removal), and every later
attempt ends with both thieves on the board (count back at 32).
  Why the first attempt still failed: after removing the thieves it spent its last ~70 moves pacing the top
  corridor waiting for the helpers (step 836: "a safe spot to exploit"), instead of hauling crates itself — the
  level-3 "let the helper do it" habit, applied where the helpers were too slow. Later attempts drift into a
  "factory" story with shifting names (Robot, AGV, Crane, Shuttle, Worker) — step 1152: "This is a fully
  automated system, according to the level description"; step 2400: "The player will wait one turn ... to
  observe the top crane." Compaction carried plans forward within an attempt; it did not carry this episodic
  lesson across resets. 1833 actions, never cleared.

### Habits that made it work
Predict-then-check on every early action; pivot on a single contradiction (step 8); read visual state cues
(outline colours) as mechanic evidence; spend actions to *watch* autonomous agents before acting; design
experiments whose outcome is informative either way (step 60); write multi-step plans with step counts and
then execute them tersely across compactions (step 27: "A plan has been provided; let's verify and refine").

### Contrast: Gemini Standard (4/9)
Same model, same mechanics discovered, not held. Level 1 took 59 because it re-tested grab mid-level: steps
27-34 walk into Box 1 three times, grab, walk, press Action 5 again (releasing it), walk into it again, grab
again. Level 2 has four budget-outs in a row (steps 130, 201, 272, 343), mostly spent "observing the cart"
(step 90, 110, 240). All 17 of its resets are budget-outs. The telling pattern is re-surprise: after the
level-5 budget-outs it repeatedly announces the bar as a new discovery — step 1038: "So the bottom bar IS THE
LEVEL TIMER!", again at steps 1290 and 1794; step 1900: "HOLY COW! THE FORKLIFT CAN MOVE IN ALL FOUR DIRECTIONS
WHILE CARRYING THE PALLET!", which it knew on level 1. Verdict: **discovered, not held.**

### Contrast: Opus 5 (3/9)
Opus played levels 1-2 as well as the best Gemini run (44, 67) with clean carried notes ("Controls: ...
**5 = grab/release**", step 44). It diverged on level 3: it judged the speckled line solid after one blocked
press, then burned an attempt testing drop slots ("Falsified — never retry: (12,7), (9,7) ...", step 200). After
a reset it found the helper delivers across the line (step 250: "The loop is fully autonomous — I just need to
stay out of its way") and parked at the west wall for about twenty steps — the same idle Gemini used. Then at
step 385 it lost confidence in a correct model: "My '🏆🏆🏆🏆 4 delivered' scoreboard was invented. Nothing has
been delivered ... I retconned it into a 'bay filling up'." The level cleared two steps later from the helper's
delivery, but the self-critique had thrown away its rulebook: step 389 on level 4 reads "Full movement set now
decoded ... ACTION5 still untested." Level 4 then cost 490 actions over nine voluntary resets, each with a new
theory (step 583 "I sealed myself in"; step 800 treats the helpers as "drifting HUD (ignore)"; step 811 "boxes
pushed onto the dither ring are LOST"). Verdict: **discovered, then discarded under self-doubt; never modelled
the level-4 helpers.**

---

## 2. Kick Away

Runs: provider-adapter medium `809e0821` (6/7), Standard high `fd354a1f` (1/7), Opus 5 Standard high `d1343ad7` (3/7).

| Level | Budget | Baseline | Gemini PA | Gemini Std | Opus 5 |
|---|---|---|---|---|---|
| 1 | 100 | 28 | **21** | 26 | 40 |
| 2 | 127 | 109 | 143 | 545 (fail) | 244 |
| 3 | 100 | 51 | 64 | — | 62 |
| 4 | 127 | 51 | 144 | — | 255 (unfinished; session state NOT_FINISHED) |
| 5 | 100 | 33 | 85 | — | — |
| 6 | 150 | 132 | 245 | — | — |
| 7 | 200 | 326 | 1630 (fail) | — | — |

Gemini PA: 13 resets — 8 voluntary (steps 111, 251, 289, 583, 886, 1269, 1276, 1848), 5 budget-outs, all of
those on level 7. **Only level 1 beat the baseline.** This is not an efficiency story: what the provider adapter
bought here was getting through levels it played slowly, not playing them well.

### How it discovered the mechanics
- Steps 1-6: drives its box right repeatedly into the other piece and watches the animation frames. Step 4:
  "The Block '5' just slides right through it in Frames 2,3,4, and 5 and stops at Frames 6 ... It's like a
  sliding puzzle, but with momentum." It saw the knock by accident but named it immediately.
- Step 7 tests the click: "What if clicking Block 5 switches control to it?" Step 11 pins the step size ("Every
  single action is a 3-unit shift"); step 13 finds that frame outlines are passable. Level 1 cleared at step 21
  (baseline 28).
- Level 2, step 80, generalises the rule after seeing a chain knock: "This is a billiard/curling mechanic;
  *pushing* an adjacent block makes it *slide* until it hits an obstacle." Step 92 quotes the rule back from the
  compaction summary verbatim ("the inactive block is launched / pushed and slides across empty floor until it
  hits an obstacle"), and by step 201 it has the distance right: "the block only slides five tiles forward"
  (five 3-cell steps, the source's ~15 cells). The purple band it calls "ice" — close to the truth (knocked
  pieces cross it, driven ones don't).

### Hypotheses, tests, and budget control
- Step 111, the reset decision is arithmetic, not frustration: "the remaining moves (19) are mathematically
  insufficient to complete the level from the current state ... I need a reset", followed by a full plan. The
  retry took 53 actions. (Opus does the same kind of budget reset, so this habit is shared, not the
  differentiator.)
- Level 3 (two yellow blocks, one green box): it uses the knock on purpose — step 201: "pushing Shape 2 *once*
  to the right from cols 20-28 will land it into Socket 2."
- Level 5 (bombs): it reads the fuse from the in-turn animation frames and counts it. Step 379: "Turns 0 to 4:
  Color 12 fills ... At full fill (Turn 4), a flush of color 12 shoots down the tube". Step 405: "the side
  cannon is just one more turn away from being fully charged". Its "cannon" is the right model: a bomb fills one
  row per press and then blasts one way. 85 actions against 33, but first attempt.

### What it got wrong
- **Level 7: metaphor without physics.** The same naming habit that worked ("curling", "cannon") produced a
  story with no basis. After a bomb blast knocked a piece away, step 1269: "Where did it go? ... that's the lower
  teleporter pad! Did it get *teleported*?"; step 1276 builds a whole plan on "avoiding the teleporter
  altogether". There is no teleporter in the game. Level 7 then burned 1630 actions over nine resets, several
  voluntary with fresh plans (step 886 "Cart", step 1848 "That initial '15' wall messed me up big time"),
  never clearing.

### Habits that made it work
Uses the in-turn animation frames as evidence, not just the final frame; names a mechanic early and then
refines it with numbers (from "slides until it hits something" to "five tiles"); keeps the rule in the
compaction summary where later turns re-read it; resets on a counted budget shortfall with a written plan.

### Contrast: Gemini Standard (1/7)
**Discovered at step 8 and lost.** Step 8: "Pushing the sliding block ... caused it to slide horizontally across
the corridor and through the barrier (color 15) until it collided with the structure." By level 2 the rule is
gone and replaced by its opposite — step 137: "CONFIRMED: Color 15 is an impassable barrier / wall to BOTH Block
A and Block E! Color 15 cannot be crossed by ANY block!" Every budget-out is greeted as news (step 138: "LOOK
AT WHAT RESET DID! THIS IS INCREDIBLE!"; similar at 266, 394, 522). It asks the right question only at the end
(step 566: "WHAT IF PIECES CAN BE PUSHED INTO ROOM 2 BY ANOTHER PIECE?") and sees it happen at step 570 ("PIECE
B PUSHED PIECE C!"), one step before the run stopped at 571 actions.

### Contrast: Opus 5 (3/7)
Also **discovered early and lost, twice.** Level 1 notes, step 11: "Key `5` slides until blocked ... `15` band
blocks the PLAYER but the key slides through". At the level change the notes are rewritten and the rule
disappears — step 41: "Bands ... are `15` (unknown if passable — must test later!)". Level 2 then runs through
four voluntary resets and invented mechanics (step 67: "TELEPORT ON ROW/COLUMN ALIGNMENT"; step 167 "third
failed hypothesis"; step 193 "the level looks unwinnable") before the knock is re-found around step 250
("selected + direction → adjacent piece slides"), 244 actions for the level. On level 4 it is lost again and
re-found as news at step 372: "CRITICAL DISCOVERY ... Blocks SLIDE like on ice". It ended on level 4 with
another wrong conclusion (step 601: "ACTION6 never transfers control" — it had tried to select the plus-shaped
block, which isn't selectable).

---

## 3. What the two games say together

1. **The provider adapter's edge here is retention, not discovery.** All three runs of each game found the key
   mechanic early (Warehouse grab: Gemini PA step 8, Standard within level 1, Opus within level 1; Kick Away
   knock: PA step 4, Standard step 8, Opus step 11). The Standard-harness runs then lost it at a level boundary
   or a reset and paid for rediscovery; the provider-adapter runs re-read it from the compaction summary.
2. **Both models rename mechanics rather than derive them, and the name does the work.** When the metaphor
   matches the physics ("tether", "curling", "cannon") execution is clean; when it doesn't ("box-swap puzzle",
   "factory", "teleporter") the model executes confidently into nothing. Opus shows the reverse failure too:
   throwing out a correct model in a burst of self-criticism (Warehouse step 385).
3. **Compaction carries plans and rules, not episodic lessons across resets.** Warehouse level 8 (thief removal
   found once, not repeated in twelve retries) and Kick Away level 7 (a fresh story each retry) are where both
   provider-adapter runs stopped.
4. **Watching is a double-edged habit.** Idling to observe the Warehouse helper won levels 2-3; the same idle
   (on a wrong belief that some actions are free) wasted the first level-8 attempt.


---

## 3. Sigil Caster, Deck Control, Toggle Navigator (helper findings)


Author: Claude Opus 5.5 (Bubba sub-agent). Date: 25-September-2026. Read-only analysis.

Sources: three.arcprize.org `/api/sessions/<guid>` (level_actions, level_baseline_actions, level_scores, state)
and `/api/recordings/<game_id>/<guid>` (per-step JSONL). Replays saved (uncommitted) in
`~/bubba-workspace/arc3-kaggle/gemini38-replays/`. Ground truth: `~/GitHub/arc-explainer/shared/arc3Games/{sc25,dc22,tn36}.ts`.
"Step N" = line N of the recording (step 0 is the opening RESET). The level-clear step found in each recording
matches the API `level_actions` in every case below (e.g. Sigil Caster clears at steps 24/29/47/79/144 = 24, 5, 18, 32, 65 actions).

## Harness facts seen in the data (all three provider-adapter runs)

- Provider-adapter runs carry a Gemini thought summary on every step; the standard-harness Gemini runs carry **none**
  (`reasoning` is null on 219/219, 1321/1321 and 168/168 steps) even though they bill large reasoning-token counts
  (e.g. standard Sigil Caster: 19,079 / 21,733 / 36,591 / 60,278 reasoning tokens at steps 1, 3, 11, 57). In the standard
  runs the only thing carried forward is the short `output` note. Opus 5 has no `reasoning` field either; its `output`
  is a long "carry forward" notes block. So claims about standard Gemini and Opus below rest on their notes only.
- Compaction is constant, not occasional: the frames push context to roughly 180-200k tokens within a handful of turns,
  and the harness compacts. Sigil Caster: 54 compactions in 394 steps; Deck Control: 213 in 1820; Toggle Navigator: 119 in 567.
  The model treats the compacted summary as a separate witness ("the summary", "the previous agent", "the last agent") and
  overrules it when the frame disagrees (examples cited per game; the quotes carry the claim, no tally is given because a keyword
  count also catches the many places where it agrees with the summary).

---

## 1. Sigil Caster (sc25-635fd71a)

| Level | Baseline | Gemini PA high (b11374ef) | Gemini Standard high (1830d41f) | Opus 5 Standard high (c136ac3c) |
|---|---|---|---|---|
| 1 | 36 | **24** | 32 | 180, never cleared |
| 2 | 6 | **5** | 11 | - |
| 3 | 32 | **18** | 28 | - |
| 4 | 83 | **32** | 151, never cleared | - |
| 5 | 143 | **65** | - | - |
| 6 | 50 | 250, never cleared | - | - |
| Result | | 5/6, GAME_OVER, 4 resets, level_scores 115 x5 | 3/6, GAME_OVER, 4 resets | 0/6, GAME_OVER, 4 resets |

### How the winning run discovered the mechanic
Level 1 is the cleanest example of the pattern across all three games: **right dots, wrong reason, level cleared.**
- The free first action plays a demo of the grow/shrink sigil being drawn dot by dot (top, left, right, bottom). Gemini
  saw it and misread it as a Simon-Says input sequence: "the game appears to be a Simon Says / sequence repetition puzzle
  where each direction corresponds to one of the cardinal cells" (step 2). Steps 2-6 enter that imagined sequence with arrows.
- Step 7 it drops the idea on evidence, and explicitly overrules the compacted summary: "The summary confused me a little,
  as it assumed the D-pad was mapped to the 3x3 grid... The numbers were not mapped to the 3x3 grid. They were mapped to
  directions." From here arrows = movement.
- Steps 8-11 it walks left, and before each move checks the destination cells ("When the block reaches columns 19-22, there
  is an issue! ... rows 21 and 22 ... a GAP!", step 9) — a prediction made before it is hit.
- Blocked at the narrow neck (step 12), it tests rotations (13-14), then turns to the grid: "what if there's a button that
  changes the board in some way?!" (15). Clicks east, north, west, south "to activate all nodes / complete the circuit"
  (18-20) — the exact grow/shrink sigil, lit for the wrong reason.
- Step 21 it reads the result from the frames and ties it to the obstacle: "The player block *shrinks*! It becomes a 2x2 block
  ... Holy cow, it shrank to fit perfectly!" Level cleared in 24 actions against 36.

### Levels 2-5: building a codebook of "combos"
It never uses the word spell. It names the spell icons "Panels" and the sigils "combos" and reuses them as a lookup table:
"Panel 1 shrink combo" (57), "3-button firing sequence" (35), "Panel 2 (Teleport)" (138). Wrong story, but operationally the
same as the true rule (light exactly this pattern -> effect), so every sequence it entered was correct.
- Level 2 (5 vs 6): copies the pattern shown on the grid (steps 25-27), teleports, walks up.
- Level 3 (18 vs 32): first fireball flies left because it last moved left (33). Step 37 it diagnoses it from the frames and
  derives the facing rule: "COLOR 9 IS THE FRONT OF THE SHIP! Every direction I move, color 9 faces that direction" (38).
  It also cross-checks the compaction summary against frames: "what did the previous agent mean when it said the projectile shot
  upwards? I need to check the exact previous moves" (37). Moves right, fires, target gone (41).
- Level 4 (32 vs 83): "The 4x4 projectile hit the wall above the corridor entrance ... cannot fit into the 2-tile high corridor
  while the player is at 4x4 size. I will now input the shrink combo" (57) — composes two spells (shrink, then fire).
- Level 5 (65 vs 143): teleports while small and fails, then explains why: "Why Teleport Failed at 2x2: The destination pad ...
  is strictly a 4x4 pad" (126) — the true rule is small wizards go to purple pads, big ones to yellow. It walks back, grows,
  teleports (132-139), clears at 144.

### Level 6: where it broke (250 actions, 4 game-overs, baseline 50)
Level 6 adds two big pads visited in turn. It did find a working partial line in one life (Box A destroyed at 292: "The laser
has successfully destroyed Box A, and Barrier 13 has vanished") but ran out of budget at 303. The failure is state loss
across compaction and resets, visible in how it keeps re-deriving the budget bar:
- "the last agent seemingly MISINTERPRETED that timer! It looks more like the turn limit timer" (200);
- "Up: `ACTION1` - no timer" (368) and two steps later "each action drains one row of the timer bar" (370). Arrows do count:
  the right-edge bar drops on arrow-only steps (level 1 steps 5-13: 60, 58, 58, 56, 54, 54, 52, 50, 50 pixels; level 6 steps
  369-371: 62, 62, 60). This follows the corrected sc25.ts (16-Sep), which says every move counts; the older trace doc
  2026-09-12-sc25-sigil-caster-six-runs.md says arrows are free and is contradicted by these frames;
- "Nothing happens, and the timer is empty, but I'm still alive" (366), the step that ended the game;
- "The summary said to return to 'Pad 1,' but I didn't see a 'Pad 1'" (356).
The combo codebook survived every compaction; the level-specific plan and the budget model did not.

### Contrasts
- **Gemini, Standard harness (3/6).** Same Simon-Says misreading at steps 2-8 ("Simon Says puzzle. Demonstration sequence in Turn 1:
  Top, Left, Right, Bottom"). At step 21 it misattributes its own shrink: "The cannon fired ... The obstacle on the track
  (originally 4x4) took damage and was reduced to a 2x2 block", then spends steps 25-29 re-entering the plus pattern for "5 full combo
  completions". It recovers enough to clear three levels, but its carried notes shrink to one-line narration ("I will click the
  center button at (30, 55)") and level 4 turns into re-learning: "I will test ACTION1 to see if it controls the entity's movement"
  at step 181, deep in level 4. The patterns are treated as door codes, never as shrink-then-fire. Discovered the codes, never held
  what they did.
- **Opus 5 (0/6).** It drew the correct grow/shrink sigil in its first life (steps 13-16) and then cast it over and over as
  "rounds" of a reproduce-the-shape puzzle: "Winning click sequence (per round)" (21), "Round 8 completed" (45). It read the
  wizard, which was shrinking and growing under it, as a progress marker ("Progress marker (10/9 block) keeps shifting/shrinking
  — appears to be a counter; keep going", 29) and the budget bar as progress ("likely nearly done", 45). It never walked the
  wizard after a cast. Four game-overs; 163 of its 180 actions were grid clicks. The clearest line: "'Levels completed' stays 0; ignore."
  (178). It discovered the casting and threw away the one signal that would have told it casting wasn't the goal.

---

## 2. Deck Control (dc22-fdcac232)

| Level | Baseline | Gemini PA high (dca57f83) | Gemini Standard high (22657662) | Opus 5 Standard high (70a3565a) |
|---|---|---|---|---|
| 1 | 59 | **24** | 45 | 47 |
| 2 | 102 | **45** | 45 | 48 |
| 3 | 67 | 65 | **50** | 100 |
| 4 | 98 | 71 | 73 | 82 |
| 5 | 324 | **1520** (cleared) | 1111, never cleared | 286, never cleared |
| 6 | 578 | 95, not cleared | - | - |
| Result | | 5/6, level_scores 115/115/106.2/115/4.5 | 4/6, GAME_OVER, 3 game-overs on L5 | 4/6, **NOT_FINISHED** (recording stops at step 563) |

On levels 1-4 the harness made little difference: standard Gemini matched or beat provider-adapter on levels 2-3, was two actions behind on level 4,
and Opus was close. Everything separating the runs happens on level 5 (the claw level), and the thing that separates them is how each read
the step bar on the bottom row.

### Levels 1-4: probe each control once, write a state table, then plan the route
- Level 1: first click on the maroon button (step 5) is read correctly as a floor toggle: "This action seems to switch two blocks
  between solid and checkerboard patterns" (6). Step 15 it tests the teal switch remotely, step 16 flips maroon back, walks home.
- Level 2 is the template: it clicks each panel button once at the start (25, 26, 27) and records both states by name — "State 9A /
  9B", "State 6A: horizontal path SOLID 7; vertical path WALL" (27) — then rules one object out by test: "`ACTION6 17 53` did nothing,
  confirming that *that* floor switch ... is the key. The avatar *must* physically step on it" (28). 45 actions against 102.
- Knowledge carries across levels through compaction: on level 5 it recalls "In Level 4 ... a bridge had to be constructed by
  triggering a control multiple times" (207) and presses the bridge button four times in a row (206-209).

### Level 5: 1520 actions, 4 game-overs, and the step bar read as a reward
Level 5's budget is 512 steps on a 64-pixel bar (about 8 steps per pixel; a fall costs 20). Gemini called the filling bar
"milestones" and treated it as progress — 582 mentions across level 5:
- "I need to understand why Milestone 24 hasn't triggered" (358);
- "Milestone 64 was awarded for being here" (590) — two steps before the first game-over, with the budget exhausted;
- after the game-over it blames a button, not the budget: "Button 2 could be a trap" (595); "Was it a self-destruct or did it move
  Shuttle 2 into a wall, causing the crash?" (595);
- "The goal here is to get from our current battery state (33) to 64!" (1300).
Because the bar moves once every several steps, it also concluded clicks were free: "ACTION6 costs zero pips ... I can test each
with NO penalty!" (1651).

What changed in the final life (steps 1447-1725): it counted the bar as a budget ("We are at Level 5 of 5 with 26 turns remaining
(38 pips consumed)", 1696). Checked against the frame: 38 of 64 pixels were filled at 1695, so it **read the bar accurately**; what it
got wrong was the scale, treating one pixel as one turn when level 5 spends about eight steps per pixel (249 actions since the reset,
plus falls at 20 each, is consistent with ~39 pixels). True remaining budget was roughly 200 steps, not 26: **conservative by about
eightfold, in the safe direction**, and it cleared 29 steps later. The standard run also counted pixels correctly and called them rewards. It
had also found the claw: "D-Pad Button 4 ... is a plunger / stamper actuator!" (1623), lowered the crane (1659-1661), and walked down
the crane arm as floor: "Continue traversing DOWN across the crane arm toward Portal 2 chamber" (1676-1682) — that is the level's key
mechanic (the carried pillar is floor). It also caught its compacted summary being wrong twice: "The previous summary was wrong,
completely backwards!" (446) and "I have to correct the summary" (595).
The level still scored only 4.5: the win came from persistence through four lives, not efficiency.

Level 6 (95 actions): it was probing the cross of tiles that make the claw buttons appear ("The avatar acts as the directional
selector inside Chamber 6", 1816). The recording's last step (1820) is NOT_FINISHED with the bar only 14/64 used; the session is
marked GAME_OVER, so the stop looks like a run limit, not the game's budget (not verified).

### Contrasts
- **Gemini, Standard harness.** Same misreading, carried to the end. It farmed the bar: "Current progress: 35/64 (row 63)" (850)
  through "64/64 pips completed! Progress bar is 100% full" (625 in its first life; again 966), cycling the sliding platform to "score
  points" (849: "When the platform reaches cols 24-29, it scores a point on the progress bar"). Then the game ended (969) and it got
  it right: "Row 63 is a 64-step timeout timer, not a progress bar" (974). Twenty steps later the correction was gone: "Progress check:
  row 63 now has six 3s" (994), and by the end it is clicking "to continue advancing the mechanism and increasing the progress bar"
  (1221). At 968-969 it even re-read the whole screen as "5 levels stacked vertically" with its avatar as "Creature 4". It discovered
  the truth once and could not keep it; its carry-forward note was the only memory it had.
- **Opus 5.** Read the bar correctly at first ("Step/penalty bar ... each action +1, each death +2", 317), then reversed itself on the
  coarse movement: "Row 63 bar has stayed at 34 `3`s for several actions => it is NOT a per-action counter. Action budget appears
  loose" (377). Its notes are the most precise of the three (a full "machine diagram" of the panel at 497), and by the last step it had
  the key idea: "pieces carry the avatar ... stand on the pinwheel and shift it up, riding it" (563). The recording ends there with
  state NOT_FINISHED and no loss, after 286 level-5 actions (why it stopped is not in the data). Its level-3 cost (100
  vs 67) was its only clear inefficiency.

---

## 3. Toggle Navigator (tn36-ef4dde99), short; see 2026-09-25-opus5-leapfrog-and-gemini38-toggle-navigator.md for levels 1-5

| Level | Baseline | Gemini PA (716e3de8) | Gemini Standard (df10c72d) | Opus 5 (86560d9a) |
|---|---|---|---|---|
| 1-5 | 32/72/26/40/30 | 12/41/13/16/20 | 8/30/then 130 on L3, not cleared | 13/140/then 130 on L3, not cleared |
| 6 | 55 | 155 | - | - |
| 7 | 62 | 310, not cleared | - | - |
| Result | | 6/7, GAME_OVER | 2/7, **NOT_FINISHED** | 2/7, GAME_OVER |

New beyond the earlier note:
- **Inferring a mechanic from impossibility.** On level 6 it guessed the save squares before seeing them work: "Could one of the special
  tiles be a checkpoint, meaning it *saves* your progress after 6 steps? Then you can re-program for the remaining moves" (110), and
  later explains where the idea came from: "It was impossible to solve the maze in a single 6-step loop, and the checkpoint idea was
  born from this understanding" (232). Level 6 still cost 155 against 55 (resets at 184 and 187).
- Level 7 (beam emitters that fire after the third instruction): it modelled the beam timing per step ("Step 0: UP to (5, 4) (Laser
  Off)", 291; "fire cleanly from emitter (6, 3) into receiver (1, 3) without hitting the robot", 320), ran out of clicks at 379
  ("I've got a limited budget (2 red indicators are left)", 377), reset, and never cleared.
- **Standard Gemini** never settled the switch encoding on level 3: it treated the demo tabs as a tool palette ("Box 1 ... selects the
  UP tool", 68; "the bottom row of boxes forms the command palette", 79), briefly got close ("Left side: Preview/Help window that
  visualizes the behavior of the currently selected command", 80), then re-derived contradictory encodings (97, 109, 110) and even
  swapped start and goal (92). The recording stops NOT_FINISHED at 168.
- **Opus 5** re-framed level 3 as a quiz: "Answer boxes ... A/B/C/D", "Rule verified 45x", and read the click-budget bar as score:
  "Track score via where the `3` block starts in row 1; it grows leftward by 1 per correct answer" (200). Game over at 214.

---

## Recurring habits (all three games)

1. **Operational models beat correct-sounding ones.** Gemini's winning models were often wrong in story but right in action
   (Sigil Caster "combos", the Simon-Says detour that still ended on the right dots). Opus built cleaner stories that optimized the wrong goal.
2. **Read the effect off the board, not off the widget.** Gemini's breakthroughs come from looking at what the wizard / avatar did after a
   click (Sigil Caster 21, 38; Deck Control 6, 27). Opus on Sigil Caster watched the grid's success flash and missed the wizard changing size.
3. **Probe each control once, name its states, then plan** (Deck Control level 2; Sigil Caster's panel codebook).
4. **Overrule the summary when the frame disagrees.** Provider-adapter Gemini treats the compaction summary as a fallible witness and
   corrects it (Sigil Caster 7, 37, 200, 220; Deck Control 446, 595). Standard Gemini has only its own terse notes and loses corrections
   (Deck Control 974 -> 994).
5. **The budget bar is the common failure for everyone.** Deck Control (both Gemini runs), Toggle Navigator and Sigil Caster (Opus), and
   Sigil Caster level 6 (Gemini) all misread a spending bar as progress or as free. The provider-adapter Deck Control run survived by
   finally holding a conservative reading, not a correct one.
6. **Where provider-adapter still fails:** long levels whose plan must survive many compactions and resets (Sigil Caster 6, Deck Control
   5's first three lives, Toggle Navigator 7). The general codebook survives compaction; level-specific plans and budget counts do not.

Caveat: these are single best-of-six runs; efficiency on the cleared levels is strong, but Deck Control level 5 shows a win bought with
volume (1520 actions, level score 4.5).
