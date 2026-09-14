<!--
Author: Sherlock
Date: 13-September-2026
PURPOSE: Specify the visual-first prompt arm requested by Mark: use the supplied grid image
to form and check game-mechanic hypotheses; reserve ASCII/segmentation for exact measurement.
This is a separate experiment from glyph replacement and first-turn text withholding, so a
result can be attributed to a persistent evidence-priority policy rather than a changed alphabet
or temporary lack of text.
SRP/DRY check: Pass — the existing arm documents define bundle construction; this records only
the hypothesis, exact prompt policy, and success criterion for the visual-first arm.
-->

# Visual-first — image for mechanics, text for measurement

## Hypothesis

The agent is over-reading the ASCII/segmentation representation: it measures grids and derives
coordinate-heavy explanations before it has identified the objects, interaction, or goal that are
already visually apparent. That produces lengthy reasoning about a wrong world model. The attached
grid image is a direct view of the same current frame and should carry the first pass of inference.

## One prompt change

Append exactly this policy to the visual-game guidance:

> Use the grid image as the primary view for identifying objects, mechanics, and whether your
> hypothesis still fits. Use ASCII or segmentation only when you need exact coordinates, counts,
> line/grid geometry, or to resolve a visual ambiguity.

This does **not** hide or alter the text board, its colour legend, its glyph alphabet, the solver
loop, valid actions, or the model. Text remains available for the cases where it is useful.

## Keep the arms separate

- **Glyph arm:** distinct all-capital glyphs; asks whether encoding itself helps.
- **Image-first arm:** withholds text only until the first action; asks whether the initial
  hypothesis improves when it must come from the image.
- **Visual-first arm:** text remains available from the start; asks whether a persistent priority
  rule prevents premature grid arithmetic and preserves image-grounded hypotheses.

Do not add the visual-first sentence to either glyph or image-first. Combining them turns a
positive result into an attribution problem.

## Readout

Primary outcome is **levels completed per game**, especially repeated level-2-or-higher clears on
games that currently plateau at level 0 or 1. A small score or token-count movement alone is not
evidence that the world model improved. Record input-token counts as provenance, but do not tune
the arm for token compression.

## Preflight

Before launch, verify in the assembled system prompt that the exact policy is present only in this
arm. Confirm that the current grid image remains attached to the first user turn. The glyph legend
must remain derived from its character table whenever a glyph arm is used; visual-first itself does
not change that table.
