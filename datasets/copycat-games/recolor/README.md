<!--
Author: Claude Opus 5.5 (Bubba sub-agent)
Date: 05-October-2026
PURPOSE: What the RECOLOR tier of copycat games is, how each copy is proven, and how to use the
package. Travels with the package into sonpham-org/arc-3 (datasets/copycat-games/recolor/).
SRP/DRY check: Pass -- the full copycats (new maps) are described in ../README.md; this covers
only the colour-only tier and points there for the shared packaging format.
-->

# Recolor copies (colour-only tier)

The slightest possible copy of each public ARC-AGI-3 game: **the same rule code, the same level
maps, the same sprites, the same HUD and the same winning moves. Only the displayed colours are
changed**, by one fixed permutation of the 16 ARC colours per game. Every colour the game shows
moves, and no two colours merge.

What it is for (Son, 4-Oct-2026): the cheapest generalisation test. Train on a game, then play
its recolor copy. Nothing changes except colour, so if the score drops, the model learned colours
rather than mechanics, and training needs colour mix-up. The full copycats in `../` test
the harder step (new maps).

## Not a yardstick until a human has played it

Every entry in `manifest.json` has `reviewed: false`. A copy is **not** a yardstick -- do not
report scores on it as evidence of anything -- until a human (the Boss or Son) has played it and
set `reviewed` to `true`. Previews (original left, copy right, every level start) are in
`previews/` to make that review quick. Entries with a non-empty `reviewer_hint` (Compass Dye and
Reaching Lurch's copies, cr82 and rr1l) kept the least of their original contrast between
touching colours; look at those closely.

## What is here

18 copies, one for each public game that is not held out. All 18 are `verified: true`.

```
environment_files/<id>/v1/<id>.py, metadata.json   # drop-in for arc_agi / taaf environments_dir
solutions/<id>.json                                # winning line per level (= the original's line)
previews/<id>/L<n>_original_vs_recolor.png         # level start, original left, copy right
manifest.json                                      # per copy: palette, checks, reviewed flag
```

Same formats as the full copycats (see `../README.md`). `metadata.json` carries `tier: recolor`
and the tags `copycat`, `recolor`.

**Ids.** The original id with its second letter changed to `r`: ls20 -> lr20, ft09 -> fr09. The
held-out seven's copies use `z` instead (vc33 -> vz33), so a test-only id is never one letter away
from a trainable one. Every id was checked against all existing game and copycat ids.

## How each copy is proven (`verified: true` needs all three)

1. **Engine.** The original game's recorded winning line (arc-explainer human-reasoning
   release), cut per level, is played from RESET through a fresh copy: level k clears exactly on
   the last action of segment k, and the run ends in WIN.
2. **Colour only, frame by frame.** The original and the copy are stepped side by side through
   the whole line, and every frame the copy returns, animation frames included, equals the
   original's frame with the palette applied. That proves the maps, sprites, HUD and timing are
   untouched.
3. **Loader.** The packaged folder is scanned by arc_agi's offline Arcade (what Son's harness
   uses), the game is made by id, the same line reaches WIN with the right level count, and the
   loader's last frame is the recoloured original's.

The palette is applied to the frames the game hands back and nowhere else, so rules that read
sprite colours see exactly what the original sees. Readability: colour pairs that touch on
screen keep their brightness contrast and colour difference (capped), and all shown colours
stay distinct; the score is in `palette_check`.

**Not changed, on purpose:** sprite drawings and HUD position. Several games' rules read sprite
pixels, so redrawing is a per-game job, and this tier is meant to test colour alone.

## Held out

The seven held-out public games' recolor copies are **test only** and live apart, in
`datasets/test-only-games/` (game folders next to the others; manifest and previews in
`datasets/test-only-games/recolor-heldout/`). They ship with no solution file, because their
line would be the held-out original's own winning line. as66 is not one of the 25 public games
and has no recorded line, so it has no recolor copy.

## Rebuild

Canonical source: `arc3games/copycats/recolor/build_recolor.py` in
`sonpham-org/autoresearch-arena`. Run with the ARCEngine venv:
`~/GitHub/arc-explainer/external/ARCEngine/.venv/bin/python build_recolor.py` (all 25) or with
game codes. The palette search has a fixed seed per game, so a rebuild gives the same copies.
