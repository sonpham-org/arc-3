<!--
Author: Claude Opus 5
Date: 21-September-2026
PURPOSE: Records the result of a perception probe on sk48 (Skewer Kebabs), testing whether the
reference-skewer strip survives into the tool agent's `.segmentation` view. Companion to
2026-09-21-shown-target-games.md and 2026-09-17-the-slippery-seven.md.
SRP/DRY check: Pass — findings doc only; the measurement lives in scripts/sk48_segmentation_probe.py
and the segmenter itself is imported from inference/utils/segmentation.py, not reimplemented.
-->

# sk48 segmentation probe — the model *is* handed the target

**Date:** 21-September-2026
**Probe:** `scripts/sk48_segmentation_probe.py`
**Verdict: hypothesis FALSIFIED.** The reference strip survives into `.segmentation` intact on all
eight levels. Colors are correct, positions are recoverable, and per-skewer bead order is
recoverable. sk48's 0.00 is not explained by the target being invisible.

## The hypothesis under test

sk48's win condition is shown, not stated: a strip below the play area holds one or more
*reference skewers*, each a handle plus the bead colors that skewer needs, in order. The ARC-3 tool
agent never sees the board as a picture unless `MULTIMODAL_CONTEXT=current_grid`; it writes Python
against `current_frame`, which exposes only `.ascii`, `.segmentation`, `.step`, `.level`
(`ARC3-Inference/inference/agent/tool_agent.py:220`), and the prompt tells it to treat
`.segmentation` as the PRIMARY view and `.ascii` as for "a small specific region" only
(`tool_agent.py:224`, repeated at `:2329`).

So the hypothesis was: the strip is merged, dropped, or stripped of bead order in `.segmentation`,
the model therefore cannot read the target at all, and no prompt wording could ever have fixed
sk48 — which would explain why both the oracle test and the sparse-deletion arm failed to move it.

Each of those three claims is false. Details below.

## Method

Grids come from the game's own source through arcengine — instantiate, `set_level(n)`,
`camera.render(current_level.get_sprites())` — the path
`arc-explainer/scripts/arc3/render_public_demo_levels.py` is already verified against. No PNG
inversion was needed; route (a) in the task worked. Source:
`external/ARCEngine/environment_files/sk48/d8078629/sk48.py`, 8 levels.

Segmentation is the harness's **own** `segment_layer()` from
`ARC3-Inference/inference/utils/segmentation.py:76`, with `ARC_COLOR_CHARS = 'WwgGcBMPRbSYOrNp'`
from `inference/utils/grid_utils.py`. Deliberately not a reimplementation — the question is what
the model actually receives. This is the same call the sandbox makes at
`agent/python_tool_sandbox.py:139`.

Node dicts carry no bounding box, only `boundary` corner points, so the probe derives bboxes the
way a model would have to. The strip is located from the full-width gray divider row, not a
hardcoded index. Requires a Python with match-statement support for arcengine (used 3.13; system
3.9 cannot import it).

Sprites are classified by **footprint, not color**, because color is ambiguous in sk48: purple is a
handle in lvl 6–8 and never a bead, and blue is a bead in both zones. A bead is a 4×4 block; a
handle is a 6×6 footprint; a 2×2 blob is a handle identity marker.

## Per-level result

Every level: one full-width gray divider at **row 53**, strip at rows 54–63, all beads accounted
for, order recovered.

| Lvl | Nodes | ≤2px nodes | Reference skewers recovered from segmentation alone |
|-----|-------|-----------|-----------------------------------------------------|
| 1 | 46 | 20 | M-handle → R, N, b |
| 2 | 56 | 24 | M-handle → R, O, b, N |
| 3 | 75 | 42 | M-handle → R, O, b, N |
| 4 | 111 | 66 | B-handle(Y marker) → R, O · B-handle(S marker) → b, N |
| 5 | 61 | 28 | M-handle → R, b, R |
| 6 | 97 | 40 | M-handle → b, b, b · p-handle → R, R, R |
| 7 | 95 | 40 | M-handle → b, N, b · p-handle → R, N, R |
| 8 | 68 | 32 | M-handle → b, N · p-handle → R, O |

Cross-checked against the rendered PNGs and the Boss's screenshots: lvl1 reads red→green→blue in
both; lvl6 reads magenta/blue×3 plus purple/red×3 in both; lvl4's two black handles carry a yellow
and a sky-blue marker in both; `lvl8-human-win-0921.png` shows the pink skewer holding blue+green
and the purple one holding red+orange, matching the probe's `b, N` / `R, O`. The probe is not
fooling itself.

### Answers to the four questions asked

**1. Do the reference skewers appear as distinct segmentation objects?** Yes, on all 8 levels. Every
reference bead is its own connected component with its own node id — e.g. lvl1 strip is nodes 28
(`R`), 29 (`N`), 30 (`b`), each 16 px at rows 57–60. Nothing is merged with the strip background;
nothing is dropped.

**2. Are bead COLOR and ORDER recoverable from segmentation alone?** Yes to both. Color is the node's
`color` char directly. Order comes from bbox columns: beads sit at a regular ~6-column pitch, so
ordering a run by column gives the sequence. **One caveat that matters:** order must be read
*outward from the handle*, not left-to-right globally, and which beads belong to which skewer needs
the run structure. This is where the real difficulty sits — see below.

**3. Same for the interior playable beads (contrast control)?** Yes, equally well, and the contrast is
informative rather than a failure. Interior beads are the same 4×4 16 px nodes; the difference is
purely arrangement. In lvl1 the interior beads are stacked vertically in one column (rows 19, 25,
31) while the reference is horizontal, so the model must match a vertical set against a horizontal
target. In lvl6 the interior has one horizontal run (row 27: b,b,b) and one vertical run (rows 33,
39, 45: R,R,R), matching the two reference skewers. The board is not harder to segment than the
strip — it is harder to *align* with the strip.

**4. Total object count, and is the strip distinguishable from the HUD?** 46–111 nodes per level, which
is small and readable, not a haystack. **sk48's 64×64 frame contains no HUD or timer bar at all** —
the "LEVEL 4 / 8" text, HELP and RESET buttons visible in the Boss's screenshots are the web
player's chrome, outside the grid the model receives. The strip is separated by a structurally
unique signature: the only full-width single-color row in the frame. It is trivially distinguishable
from anything the prompt calls a HUD, because there isn't one to confuse it with.

## What the probe found instead

Three things that are real, none of which is the hypothesis.

**The `.ascii` escape hatch is open.** `.ascii` is a full public attribute of `FrameView`
(`python_tool_sandbox.py:127`). The prompt *steers away* from broad ascii reads, but nothing
prevents slicing rows 54–63 — ten rows, the cheapest possible read of the target. So the strongest
form of "no prompt wording change could have fixed sk48" is false: the target is one ten-row string
slice away, and that route is open on every level.

(Aside, not load-bearing: the raw grid is also physically present in-sandbox as `FrameView._grid`
(`:133`), the sandbox does not filter underscore attributes, and `getattr` is an allowed builtin
(`:79`). But `tool_agent.py:224` flatly tells the model "The raw numeric grid is not available," so
the model has no reason to reach for it. Counting this as an available route would be unfair; the
`.ascii` route needs no such trick.)

**Skewer grouping is the actual perception difficulty.** Colors and per-skewer order are present, but
*which beads belong to which skewer* requires reading the shaft, and the shaft is where segmentation
genuinely degrades: it arrives as 20–66 one-pixel alternating-gray nodes (all of the ≤2px nodes in
the table are shaft dashes). Evidence this is hard and not merely tedious: this probe's first
grouping heuristic — assign each bead to the nearest handle — got lvl6 **wrong**, stealing the last
blue bead for the purple skewer, because the second handle sits in the gap between the two runs. It
took a run-then-adjacency rule to fix. That error happened with the full ascii in hand.

**Handles carry identity markers, and the containment tree does not help find them.** Each handle has
a 2×2 center whose color keys that reference skewer to a specific playable skewer — lvl4's yellow
and sky-blue markers are how you know which target is which. Segmentation preserves these as nodes.
But the 6×6 handle ring is **broken where the shaft attaches** (verified in raw ascii, e.g. lvl6
rows 215–216 col 10 are shaft dashes, not ring), so the interior is not topologically enclosed and
`children` assigns it no parent. Nesting has to be recovered geometrically. Two related shape
subtleties: a bead may render as a 12 px ring around a 2×2 center — a marker inside the bead, **not**
occlusion (lvl5 node 43, `b` with a `W` center, which *is* an enclosed child); and lvl4's handles are
solid 6×6 blocks colored black, the same value as the play-area background, separable in the strip
only because the strip background is charcoal. What the marker means mechanically —
already-placed, currently-selected, or identity-only — was **not** determined by this probe; only
that segmentation preserves it.

## What a human sees vs. what the model is handed

A human gets the strip as one glance: two little skewers at the bottom, each a colored handle with
colored beads on a stick, and the board above holding partial skewers to be completed. The grouping
question never arises — proximity along a visible stick answers it pre-attentively.

The model gets 46–111 typed, positioned objects. Every fact needed is in there: the beads, their
colors, their coordinates, the divider, the handles, the markers. What it does not get is the
*grouping* for free. It has to reconstruct "these three beads are on that handle's stick" from a
cloud of one-pixel gray dashes, and get it right for two skewers at once in six of eight levels.

That is a reasoning-and-bookkeeping failure surface, not a blindness one.

## Consequence

Stop attributing sk48's 0.00 to an unreadable target. The target is readable, by two independent
routes, and a ten-row `.ascii` slice reads it outright. The oracle test and sparse-deletion arm
failing to move sk48 needs a different explanation — on this evidence the candidates are
shaft-following / skewer grouping, and aligning a vertical interior arrangement against a
horizontal reference, not perception loss in `.segmentation`.

This sits well with the human datapoint from the same day: the Boss beat sk48 on 21-Sep, all 8
levels, but it took **856 actions** (replay `7f07c3de-ec0a-412c-a710-2e19b3303581`, see
`2026-09-17-the-slippery-seven.md`). A player who can read the target at a glance still needed a
long grind — which is what a bookkeeping-and-sequencing game looks like, not a game whose target is
hidden.

Worth noting what this probe did **not** test: only opening frames (`set_level(n)`, nothing moved).
Whether the strip stays this clean mid-episode, once a skewer is partially loaded and beads are in
motion, is untested and is the obvious next probe.

## Reproduce

```
python3.13 scripts/sk48_segmentation_probe.py --levels 1-8
python3.13 scripts/sk48_segmentation_probe.py --levels 6 --ascii    # the two-skewer level
```
