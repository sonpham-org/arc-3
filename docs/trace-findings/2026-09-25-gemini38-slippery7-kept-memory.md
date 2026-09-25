<!--
Author: Claude Opus 5.5
Date: 25-September-2026
PURPOSE: What Gemini 3.8 Flash's public ARC-AGI-3 replays say about the slippery seven, read
from the model's own reasoning in both of ARC Prize's harnesses (Standard and Provider Adapter),
with g50t as the worked case. Holds the per-game level table, an action-matched comparison, the
g50t turn-by-turn contrast, the caveats, and the one harness change it points at.
SRP/DRY check: Pass. Mechanics are cited to arc-explainer/shared/arc3Games/g50t.ts, the game list
to 2026-09-17-the-slippery-seven.md, the "stop re-deriving the mechanic" call to
docs/prolong/README.md. Bubba's first pass on this model (tn36 codebook, best-of-six per game) is
~/bubba-workspace/docs/2026-09-25-opus5-leapfrog-and-gemini38-toggle-navigator.md and is not
restated.
-->

# Gemini 3.8 Flash on the slippery seven: the harness that keeps its thinking wins

**Source.** All 150 public replays linked from
https://arcprize.org/results/google-gemini-3-8-flash (25 games × high/medium/low × 2 harnesses),
pulled 25-Sep-2026 through `arcprize.org/api/sessions/<guid>` and
`arcprize.org/api/recordings/<game>/<guid>`. Runs were recorded 10-Sep-2026. Only the
slippery seven are analysed here. tr87 is held out: read for analysis only, never trained on.

**What the two harnesses are** (ARC Prize, GPT-6 Astra post): Standard lets the model carry
forward only the notes it writes in its visible answer. Provider Adapter "preserves opaque
reasoning state between requests and uses compaction for longer conversations". In the
recordings this shows directly: Standard turns carry only an `output` string (often just the
action name); Adapter turns carry a reasoning summary and the model's input stays at roughly
180k–360k tokens a turn.

## 1. Levels, same model, same effort, both harnesses

| game | effort | Standard levels / actions | Adapter levels at Standard's action count | Adapter final levels / actions |
|---|---|---|---|---|
| g50t | high | 0 / 390 | 5 | 6 / 929 |
| g50t | medium | 0 / 390 | 2 | 2 / 1104 |
| g50t | low | 0 / 390 | 1 | 1 / 983 |
| tn36 | high | 2 / 168 | 5 | 6 / 567 |
| tn36 | medium | 2 / 179 | 4 | 5 / 481 |
| tn36 | low | 2 / 46 | 3 | 3 / 235 |
| m0r0 | high | 2 / 1268 | 5 | 5 / 1346 |
| m0r0 | medium | 2 / 1221 | 6 | 6 / 1011 (win) |
| m0r0 | low | 2 / 1126 | 3 | 3 / 332 |
| sc25 | high | 3 / 222 | 5 | 5 / 394 |
| sc25 | medium | 3 / 535 | 4 | 4 / 799 |
| sc25 | low | 3 / 484 | 3 | 5 / 845 |
| sk48 | high | 1 / 549 | 3 | 4 / 1493 |
| sk48 | medium | 1 / 561 | 1 | 3 / 1364 |
| sk48 | low | 1 / 911 | 2 | 2 / 1192 |
| dc22 | high | 4 / 1324 | 4 | 5 / 1820 |
| dc22 | medium | 1 / 552 | 4 | 4 / 2010 |
| dc22 | low | 3 / 741 | 4 | 4 / 2026 |
| tr87 | high | 0 / 270 | 1 | 1 / 321 |
| tr87 | medium | 0 / 270 | 1 | 1 / 331 |
| tr87 | low | 0 / 270 | 1 | 1 / 348 |

**Caveat, and why it does not explain the gap.** Standard runs stop at a fixed action count per
game (g50t exactly 390 at all three efforts, tr87 exactly 270), while Adapter runs play two to
three times longer. So the final columns are not a fair race. The middle column is: it counts
the Adapter's levels at the moment it had used as many actions as the Standard run got in
total. The Adapter is ahead or level in all 21 pairs, and ahead in 18. Output tokens are
similar between the two (g50t high: 11.7M Standard, 9.8M Adapter), so this is not "the Adapter
thought harder".

## 2. g50t, turn by turn

Mechanic (from `g50t.ts`): the fifth action sends you back to the start and spawns a ghost that
replays your last run move for move; ghosts hold plates open; a timer kills you at 130 actions.

**Adapter, high effort.** Turn 8, right after its first fifth-action press, the reasoning says it
is "100% time based recording". Turn 13 it plans "four right steps, then an ACTION5 to commit
Phase 1", and resets to do it. Turn 19 it has the full model: the earlier run replays as a clone
while "we (Clone 2) are free to act concurrently". Level 1 falls at action 30, level 2 at 77. The
word "clone" appears in almost every turn after that; it rides one hypothesis to six levels.

**Standard, high effort.** It pressed the fifth action 31 times and never named the mechanic.
Its stated picture of the game changes every few dozen turns and never accumulates:

- turn 14: a hydraulic machine where the fifth action "ran Block 1's simulation" (closest it came)
- turn 27: a delivery track with a delivery station
- turn 100: "testing ACTION5 to see if it switches the active selection"
- turn 156: a shell game, "identify which spot/cup contains the target"
- turn 288: an ice-sliding maze where "ACTION5 = LEFT"
- turn 322: five chambers, one per action button
- turn 389: ice-sliding maze again

At turns 75, 129 and 248 it is back to "test ACTION1 to discover the action mapping". It timed
out on level 1 three times and ended with nothing. It spent about as many tokens thinking as the
Adapter run; it kept almost none of it.

## 3. The other six

- **tn36, m0r0, sc25, dc22:** same direction, smaller and less dramatic. tn36 is the codebook
  story in Bubba's note: once the Adapter run decided the demo panel was a dictionary of
  commands, it kept using it.
- **sk48:** the Standard run flips between an "elevator with an arm" and "a traverser on tracks";
  the Adapter run gets further but still only 2–4 of 8.
- **tr87:** one level with the Adapter, none without, at every effort. Its Standard run holds a
  steady and roughly right story (a cipher-matching puzzle) and still fails; this is a reading
  problem, not a memory problem. Kept memory is not a universal fix.
- Effort still matters on g50t: the Adapter at low and medium effort got only one or two levels.
  Memory lets a good insight survive; it does not produce the insight.

## 4. What it means for our harness

This is the g50t-shaped proof of a call already made in `docs/prolong/README.md`: stop
re-deriving the mechanic every turn.

Our Kaggle harness already keeps the model's thinking between turns (`preserve_thinking`), but
with a 32k–64k window it runs `half_context_swap`, which, when full, keeps the first message and
drops the oldest half of the turns with no summary. On g50t the discovery happens early (the
Adapter had it by turn 8–19). In our harness that is exactly the part the first swap throws
away, and the model is left in the Standard harness's position: fresh thinking, no memory of
what the fifth action does.

The change it points at: keep a short standing "what I know about this game" note that the model
updates, and write it into the part of the conversation the swap never drops. g50t is the test
game: five baseline passes on it already exist, and our harness clears 0–2 of its 7 levels.
