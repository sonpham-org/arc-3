<!--
Author: Claude Opus 5 (Bubba)
Date: 13-September-2026
PURPOSE: Record arm G (visual-first) as built and queued, the one place it deliberately
departs from Sherlock's specification, and a live-dataset drift caught before job 6 ran.
SRP/DRY check: Pass — Sherlock's 2026-09-13-visual-first-experiment.md owns the hypothesis
and success criterion; this records only the build, the deviation, and the drift.
-->

# Arm G built, and the glyph bundle that was shipping the wrong alphabet

## One deliberate deviation from the spec

Sherlock's `2026-09-13-visual-first-experiment.md` specifies the policy be **appended** to
the visual-game guidance and that it "does not alter the text board" guidance. Arm G as
built **replaces** two existing lines instead, at `prompts.py`:

- `"Use current_frame.segmentation as your primary view of the board"` (stated twice,
  once in the raw-grid paragraph and once in the tool bullets)
- the companion `"use current_frame.ascii only to read a small, specific region"`

Appending to an unedited prompt would leave the assembled system prompt asserting that the
image is primary and that `segmentation` is primary, two paragraphs apart. That is not the
intervention; it is a contradiction, and the model would be free to resolve it either way.
The replacement text keeps both tools available and keeps their measurement role explicit,
which is the substance of the spec. Recorded as a deviation rather than folded in silently.

Separation holds: G changes no alphabet (that is D) and withholds nothing (that is E).
Arm marker `measuring instruments, not the board`, exclusive to G, asserted in-process
before any game runs.

## The glyph bundle was live with the wrong alphabet

The Boss replaced the mnemonic glyph set with an arbitrary one, his own letters and order,
`QWRTYSDFGHKZXCVB`. `build_bundles.py` took the change. Two things did not:

1. **`build_notebooks.py` kept its own copy of the table** — `GLYPH_CHARS =
   "WHGDCBMKRTSYFVZX"` — and the arm-D provenance marker `H=light gray`. `H` is not in the
   new set. Job 6 would have booted vLLM for nine minutes and then raised on its own
   assertion. Fixed by importing the table from `build_bundles.py`; there is now one copy.
2. **The uploaded dataset was never re-versioned.** `markbarney/taaf-duck-glyph-consonants`
   was still serving `("white", "W"), ("light gray", "H"), ...` — verified by pulling
   `grid_utils.py` back out of the live dataset, not by trusting the local build. Re-pushed
   with `-r zip`; re-verified from the live dataset as `("white", "Q")`.

Same shape as the arm-E dataset break: the local bundle was right and the thing Kaggle
would actually run was not. Verifying the built tree is not verifying the shipped tree.

## Queue

job7 image-first (QUEUED on the card) → job8 commit-prompt → job6 glyphs → job9 visual-first.
Every one is 7 bottom-seven lanes x 4 passes, 1980s per game, 7920s budget. Readout is
levels completed on passes 0-2, per Sherlock's criterion.
