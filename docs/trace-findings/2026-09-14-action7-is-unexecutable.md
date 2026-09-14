<!--
Author: Claude Opus 5 (Bubba)
Date: 14-September-2026
PURPOSE: Record that ACTION7 is advertised in valid_actions but cannot be executed by the
baseline harness our arms A-G run on, that the agent does try it and is refused, and that
a fix for this already exists in-repo at harnesses/action7-anim/. Corrects the "never
pressed" claim in 2026-09-13-bp35-human-win-replay.md.
SRP/DRY check: Pass — the bp35 replay doc records the human side; this records the harness
defect. The action7-anim MANIFEST describes the fix but not its effect on our arm results.
-->

# ACTION7 is advertised and unexecutable

## The defect

`inference/agent/action_names.py:7` maps ACTION1–6 and RESET. **ACTION7 is absent.**

- `to_model_action("ACTION7")` falls back to the raw string, so ACTION7 **is listed in
  `valid_actions`** on every step of every game that exposes it.
- `to_engine_action("ACTION7")` finds it in neither table and returns `None`, so
  `solver.py:617` rejects the call with `Unknown action at index 1: 'ACTION7'`.

The agent is offered a control it cannot invoke, and the refusal message names an index
rather than the fact that the action is unsupported.

## The agent does try it

Across bp35 in jobs 4, 7 and 8 (12 passes, 613 committed actions), **ACTION7 appears zero
times in the committed action history** — but the transcripts contain 22 call-shaped
`action(['ACTION7'])` attempts, every one answered with `Unknown action at index 1`.

The agent then reasons itself out of the mechanic. Direct quotes from the bp35
transcripts:

> `"Unknown action" — so it's invalid despite being listed in valid_actions.`
> `Unknown action"). So the real actions are LEFT, RIGHT, MOUSE.`
> `maybe the action name must be exactly 'ACTIO...`

This corrects `2026-09-13-bp35-human-win-replay.md`, which recorded ACTION7 as never
pressed. It was pressed and refused. The conclusion drawn there — that we ignore a verb
the human uses 35 times from level 1 — still stands, but the cause is the harness, not
the agent's curiosity.

## Blast radius

Every game exposing ACTION7 is handicapped. bp35 and lf52 are in our bottom seven; the
action7-anim MANIFEST names tn36, vc33, lp85 and ar25 as well. bp35's human replay shows
undo carrying 3.4% of a winning run, concentrated in the hard levels.

**Arms A through G all inherit this defect.** They are a fair comparison with each other
— the flaw is symmetric — but none of them is a fair evaluation of hypothesis testing on
a game whose experimental instrument is a reversible action.

## The fix already exists in this repo

`harnesses/action7-anim/patch/action7-anim.diff` adds the neutral round-trip
`"ACTION7": "ACTION7"` plus one prompt line stating ACTION7 is executable and its meaning
is game-specific — explicitly *not* asserting it means undo. It is ported from the public
1.47 `agi-duck-harness-dark-agi-ver` notebook and is already written up as a real bug fix.

That patch also carries a second, unrelated change (always-visible animation metadata).
Shipping both at once would put two variables in one arm.

## What to run

**Arm H — ACTION7 round-trip only**, stacked on the deletion arm like every other arm:
the `action_names.py` one-line map entry and the single ACTION7 prompt line, and nothing
from the animation half of the patch. Same bottom-seven lanes, same 1980s cap, n=4.

Prediction, registered before the run: the gain, if any, lands on bp35, lf52 and tn36,
and the four games that do not expose ACTION7 do not move.
