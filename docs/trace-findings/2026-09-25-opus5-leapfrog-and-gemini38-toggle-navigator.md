# Opus 5 on Leapfrog, Gemini 3.8 Flash on Toggle Navigator, and Gemini 3.8 Flash's results

Author: Claude Opus 5.5 (Bubba). Date: 25-September-2026. Asked by the Boss (#arc-3, 14:02 ET).
Sources: three.arcprize.org /api/sessions + /api/recordings; ARC Explainer write-ups
~/GitHub/arc-explainer/shared/arc3Games/tn36.ts and lf52.ts (mechanics traced against the game source).

## Opus 5 on Leapfrog (replay 5d0b7a9c...): 1 of 10 levels, 419 actions
- Level 1 (peg solitaire) solved in 14 actions: it correctly wrote "GAME: PEG SOLITAIRE, click peg, click landing".
- Level 2 adds rail carts moved by the arrow keys; per the write-up, a peg must HOP ONTO an empty cart and ride it to the
  other room. Opus instead re-imagined the game: the cart became "the ball", the goal became "push the ball into the socket",
  the big room's pegs became "decoys", and it wrote "ACTION6/7 useless". It never clicked a peg again on purpose.
- It then spent ~400 actions and 9 resets on geometry (rail rows, 6-cell steps, "jammed" states) for a wrong goal.
- Failure in one line: when a new level adds a mechanic, it threw away the mechanic that won level 1 instead of asking how the
  two combine, and it declared a button useless after testing it in the wrong context.

## Gemini 3.8 Flash on Toggle Navigator (replay 716e3de8..., config high, provider adapter): 6 of 7 levels
- Levels 1-5 each at the capped (better than human baseline) efficiency score; level 6 slow (~150 actions); level 7 not solved
  (game over).
- What it did right, from its reasoning summaries:
  1. Level 1: a very long first think (~47k reasoning tokens on the first turn), then a clear run/observe loop: each column
     is a step, a run plays them left to right, failed runs snap back.
  2. Level 2 (step 54): "The four boxes at the bottom left are, without a doubt, a dictionary of the directional commands."
     It clicked a demo tab to watch its preset program play on the left panel and read off which switch pattern means which
     instruction. From then on it wrote programs as instruction lists ("Col 0: SHRINK, Col 1: LEFT, Col 2-5: DOWN"),
     verified the switch pattern column by column, and only then pressed run.
  3. It treated the demo panel as a codebook, not as scenery; that is exactly the part the write-up says unlocks the game
     (tabs load preset programs; the left panel has no target and does not count toward winning).
- Where it slowed: the level-6/7 bank split and six-instruction chain; it re-tested encodings for many actions.

## Gemini 3.8 Flash, best config per game (6 configs each)
Wins: Axis Reflectors*, Functional Tiles, Loop and Pull, Mirror Rendezvous, Reaching Lurch, Reach Emblems*, Sliding
Indicator, Sequence Belt*, Sucking Up*, Volume Control*. Near: Ghost Twin 6/7, Warehouse 7/9, Kick Away 6/7, Toggle
Navigator 6/7, Deck Control 5/6, Sigil Caster 5/6, Streaming Purple 5/6. Weak: Buoyant Pontoons 1/9, Leapfrog 1/10,
Toggle Runes* 1/6, Locksmith 2/7, Skewer Kebabs 4/8, Trail Unwind* 5/9. (* held out for us: read-only.)
Caveat: best of six configs per game flatters it; single configs are lower. Provider-adapter configs dominate the best runs.
Worth reading next for us: its Ghost Twin 6/7 and Warehouse 7/9 runs (both on our hard lists).
