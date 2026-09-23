<!--
Author: Claude Opus 5 (Bubba)
Date: 21-September-2026
PURPOSE: The pass the Boss asked for on 21-Sep: which of the official ARC-3 games put a target
on screen that the player is meant to reproduce, sorted by what form the target takes, and
crossed against the games the 27B on a108 scores zero on. Exists because the live system prompt
has a rule for REJECTING a display as the goal and no rule for READING one as the goal, and the
lane set for any prompt arm testing that gap has to come from the write-ups rather than a guess.
Source for every classification: the simpleExplanation / mechanicsBreakdown fields in
82deutschmark/arc-explainer shared/arc3Games/<game>.ts, which are cited to each game's own Python.
SRP/DRY check: Pass - no existing doc classifies the set by goal-presentation. The zero-score
column is read from 2026-09-17-the-slippery-seven.md §2 and not recomputed here.
-->

# Which ARC-3 games show you the answer

**21-September-2026.** Boss's observation, checked against the write-ups: it is most of the set,
and it concentrates in the games we lose.

## 1. The two forms

The distinction matters because only the first form collides with the prompt's HUD rules.

**A — a separate reference display.** The spec sits off the play area, in a strip, corner, or
wall. It never interacts mechanically. It is exactly the shape the system prompt's "false goals"
line tells the model to discount.

| game | where the target is shown |
|---|---|
| `sk48` Skewer Kebabs | reference skewers in the strip below the board, bead colors in order |
| `sb26` Sequence Belt | goal row of colors across the top |
| `cd82` Compass Dye | reference pattern in the corner |
| `sc25` Sigil Caster | clicking a spell icon shows that spell's sigil |
| `tr87` Toggle Runes | the phrase, plus the dictionary wall of rune-pairs |
| `ls20` Locksmith | each door shows a picture of the key it wants |

**B — a target drawn on the board.** An outline, dot, or pin marks the wanted position, shape,
size, rotation, or color. Same "match the thing shown" demand, but in the play area, so the HUD
rules do not fire on it.

`tn36` (target outline: spot, size, rotation and color) · `ka59` (gray outline frames a piece must
fit exactly) · `re86` (target dots, matched by color) · `lp85` (yellow targets, four corner dots) ·
`ar25` (yellow target squares) · `s5i5` (hollow-diamond pins) · `r11l` (the colors its target
wants) · `vc33` (each rider level with the stripe of its own color) · `cn04` (printed marks line
up with matching marks) · `as66` (the exit's required color) · `sp80` (yellow cups)

Not a shown-target game: `bp35`, `dc22`, `ft09`, `g50t`, `lf52`, `m0r0`, `su15`, `tu93`, `wa30`.

## 2. The cross that makes it worth running

`2026-09-17-the-slippery-seven.md` §2: seven games score a flat 0.00 on all four passes of the
27B mass-data run on a108 — `dc22`, `g50t`, `m0r0`, `sc25`, `sk48`, `tn36`, `tr87`.

**Four of those seven show you the target**: `sc25`, `sk48`, `tr87` (form A) and `tn36` (form B).
The three that do not — `dc22`, `g50t`, `m0r0` — fail for reasons already documented elsewhere
(hidden ghost-replay mechanic, mirrored control, encoded panel).

Scope caveat, kept from `2026-09-18-never-cleared-scope-and-failure-audit.md` §0: no game of the
25 has never cleared a level across all models. These zeros are the 27B-on-a108 scope only. On the
Astra run `cd82` and `sb26` were won outright, which is the point — the target games are winnable,
and this model does not read the target.

## 3. Lane set for an additive prompt arm

Form A is the arm's subject, because form A is what the prompt argues against. Six lanes:
`sk48`, `sb26`, `cd82`, `sc25`, `tr87`, `ls20`. Three of the six are current zeros, which gives the
arm somewhere to move; `cd82` and `sb26` are the null-check, because a model that already reads
those displays should not change.

Form B games are the second lane set if form A moves, not a substitute for it.

## 4. What is not established here

- That the model fails to read the display. §2 shows the correlation; the mechanism is asserted
  from the prompt text, not measured in traces. A per-trace count of whether the reference strip
  is ever mentioned would settle it and has not been run.
- Whether an added line helps. The `sparse-deletion` MANIFEST's own argument cuts both ways: a
  substitute rule is still a claim, and any claim is wrong on the games it does not cover. Nine
  games in this set show no target at all.
