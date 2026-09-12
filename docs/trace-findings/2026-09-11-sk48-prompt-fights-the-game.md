# sk48 ("Skewer Kebabs") — the system prompt argues against the game's own mechanic

Third companion doc. Four traces now: `astra-fctx-comb-w5-r4` (2 levels),
`sym264-w5` (2), `sym264-w7` (0), `cleanrem132-w11-r3` (1 level, score 1.615).

## The mechanic, restated

A rigid segmented rod extends and retracts from a magenta head. Blocks are **skewered**
onto it — trapped against a wall and pierced — after which they travel with the rod. The
strip along the bottom of the screen is the **required order**. The rod is solid and can
push things. Access is tip-only, so a loaded rod behaves as a stack.

Level 4 makes the stack explicit: the rod arrives pre-loaded and two ceiling-mounted rods
each demand a different sub-sequence, so the load must be split and transferred in an
order that fights the unload order. Level 5 asks for an alternating target (red, blue,
red) drawn from a run of three blues already on the rod and three loose reds.

## The collision

Two lines in the live system prompt, quoted from the `cleanrem132-w11-r3` trace:

> In many games, a long horizontal or vertical line near an edge is a timer or
> remaining-steps bar. ... do not get distracted by it or treat it as core gameplay state
> unless there is concrete evidence that it interacts with the puzzle mechanics.

> A common failure mode is to mistake a segmented edge bar for clickable puzzle pieces. If
> a repeated strip of small blocks sits flush against the top, bottom, left, or right
> border and actions only change that strip while the interior board stays the same,
> classify it as HUD/timer state, not as an object to click through segment by segment.
> **DON'T DO THIS!**

sk48 puts **four** long segmented strips on screen:

| element | what it is | what the prompt's prior suggests |
|---|---|---|
| the rod | the entire mechanic | segmented strip of small blocks |
| vertical bar at cols 13–14 | unknown, near the left edge | "long vertical line near an edge" |
| bottom strip | the required order — the goal | "repeated strip flush against the bottom border" |
| row 53 separator | genuinely a timer bar | correctly a timer bar |

One of the four is what the rule is for. The rule fires on the other three.

It fires observably. `sym264-w5`, mid-run:

> Also there's a vertical segmented bar at col 13-14, rows 14-35 — like a "ruler" perhaps
> indicating a target length? **Or maybe that's a HUD (a remaining-steps bar)**

And the bottom strip — the goal specification — is downgraded to decoration by two of
four runs (see `2026-09-11-sk48-mental-models.md`), in the exact vocabulary the prompt
supplies: legend, palette, HUD.

**Care with this claim.** The literal wording requires *flush against a border* and
*actions only change that strip*, and the rod is mid-board, so no run cited the rule to
dismiss the rod itself. The problem is the prior, not the letter: the prompt spends two
emphatic paragraphs, one ending in `DON'T DO THIS!`, teaching that long segmented lines
are not gameplay — to an agent about to play a game that is entirely a long segmented
line. `cleanrem132-w11-r3` is the counter-example worth noting: it committed early —

> The bar is a legend explaining the mechanic: "collect in this order."

— and cleared a level.

## Level transitions are not reliably noticed

Checked each run's thinking on the turn its level counter advanced, for any mention of
the level changing:

| run | level 1→2 at | mentions the transition that turn |
|---|---|---|
| `cleanrem132-w11-r3` | step 22 | yes (3) — "Level 1 completed with chain R@2,N@3,b@4" |
| `astra-fctx-comb` | step 17 | yes (2) — "my model's grip relation for level 2 ... Let me recheck" |
| `sym264-w5` | step 24 | **no (0)** |

`sym264-w5` — one of only two runs in 363 to clear two levels — is mid beam-search on a
now-stale start state when the level changes, and does not register it:

> The beam search found a 28-action solution ... Wait — but the start state I used was
> (6,1,...)

The other two notice, but notice while still reasoning in level-1 terms, re-checking a
carried model rather than re-grounding.

## What this suggests

Three things, in order of cheapness:

1. **Scope the HUD warning.** It is stated as a general visual prior and it is wrong for
   at least one official game. Gate it on evidence ("if actions change only that strip and
   nothing else for N turns") rather than on appearance.
2. **Make a level change a hard re-ground.** An explicit signal that the level advanced,
   and an instruction to re-derive the objective rather than carry the previous level's
   rule set, would have caught `sym264-w5` planning against a dead state.
3. **Nothing in any of the four traces forms a stack.** Level 4 needs ordered carriage
   with tip-only access; level 5 needs interleaving two colour runs. The metaphors reached
   — pen, tongue, impaling wire — none carry an ordering discipline. If the difficulty
   curve is a stack-sorting curve, the ceiling is not perception.

Caveat as ever: four traces, one game.
