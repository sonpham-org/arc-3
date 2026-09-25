# Claude Opus 5 (ARC Prize official runs): where it fails, and why

Author: Claude Opus 5.5 (Bubba). Date: 25-September-2026.
Asked by the Boss (#arc-3, 13:37 ET): "Look at the others... what is going wrong on the tasks it performs poorly on?"
Source: https://arcprize.org/results/anthropic-claude-opus-5 (config anthropic-claude-opus-5-high, published Jul-2026).
Session metadata from three.arcprize.org/api/sessions/<guid>; recordings from
three.arcprize.org/api/recordings/<game>/<guid> (JSONL; per-step `action_input.reasoning.output`).
Session JSONs saved in (Bubba workspace, arc3-kaggle/opus5-replays/). Held-out games are read-only evidence, never training data.

## Scores per game (levels cleared / levels in game)
Perfect or near: Functional Tiles, Loop and Pull, Reaching Lurch, Sliding Indicator, Axis Reflectors*, Volume Control*, Sequence Belt* (7/8).
Middle: Reach Emblems* 6/8, Streaming Purple 5/6, Deck Control 4/6, Coded Notches 4/6, Toggle Runes* 4/6, Mirror Rendezvous 3/6.
Poor: Warehouse 3/9, Kick Away 3/7, Sucking Up* 3/9, Skewer Kebabs 2/8, Toggle Navigator 2/7, Locksmith 2/7, Trail Unwind* 2/9,
Leapfrog 1/10, Compass Dye 1/6, **Buoyant Pontoons 0, Ghost Twin 0, Sigil Caster 0** (all three ended in game over).
(* = on our held-out list.)
The poor list is essentially the Flash-Next bottom seven (Skewer Kebabs, Buoyant Pontoons, Locksmith, Ghost Twin, Leapfrog,
Warehouse, Toggle Navigator) plus Sigil Caster: our hard games are hard for the frontier model too.

## What goes wrong (read from the three zero-score recordings)
Every turn it keeps a "notes to carry forward" block, as in its winning games. The notes are the failure point:
1. **Wrong model stamped "confirmed".** Buoyant Pontoons: "Confirmed model (stable)" that ACTION7 spawns clusters and clicks
   dissolve them, "never use RESET"; ~35 steps later it discovers ACTION3 moves the ship, with ~26 actions left. Sigil Caster:
   solves six "rounds" of a 4-click shape puzzle with success flashes, but levels stay at zero and it never questions the model.
2. **Missing the time dimension.** Sigil Caster: only on its last turns does it notice the game plays a demo in a set ORDER
   (N, W, E, S) and it must replicate the sequence. Ghost Twin: argues with itself about whether its piece rises or falls,
   and only sees the second (ghost) piece near the end. Buoyant Pontoons: early misreading of which animation frame is "now".
3. **No "is this working?" check.** Progress signals (level counter unchanged, step bar draining) are noted but never trigger
   "my model is wrong, test something else".
4. **Budget burn.** Step/doom bars are read correctly and ignored strategically; all three zero games end in game over.
5. **Notes reset instead of accumulate after a life is lost.** Ghost Twin rebuilds the whole map description from scratch
   repeatedly (hundreds of actions, contradictory notes across lives).

## What it means for us
- Its winning habit (running notes + naming the rule) is necessary, not sufficient: on hard games it names the WRONG rule
  and then defends it. The fix is a falsification check: "levels haven't moved in N actions despite my 'success' -> the
  model is wrong, list what I haven't tested."
- Temporal games (Ghost Twin, Sigil Caster's demo order) are the common wall for Opus 5, Flash-Next and OpenMind's agent.
