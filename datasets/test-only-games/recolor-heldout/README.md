<!--
Author: Claude Opus 5.5 (Bubba sub-agent)
Date: 05-October-2026
PURPOSE: Fence and guide for the HELD-OUT recolor copies (TEST ONLY, NEVER TRAIN). Travels into
sonpham-org/arc-3 as datasets/test-only-games/recolor-heldout/README.md.
SRP/DRY check: Pass -- the recolor method and proofs are described once, in
arc3games/copycats/recolor/README.md (datasets/copycat-games/recolor/README.md on arc-3); this
file only says what is here and what must never happen to it.
-->

# Held-out recolor copies -- TEST ONLY, NEVER TRAIN

Colour-only copies of the seven held-out public games: same rules, same maps, same sprites, same
HUD; only the displayed colours are permuted. Method and proofs: see the recolor README in the
copycat-games package (`datasets/copycat-games/recolor/README.md` on arc-3).

| original | copy |
|---|---|
| ar25 | aq25 |
| re86 | rr86 |
| sb26 | sr26 |
| su15 | sr15 |
| tr87 | tq87 |
| tu93 | tr93 |
| vc33 | vr33 |

## The fence

- **Never train on these** -- not the game files, their frames, any replay of them, or the
  previews. They exist only to measure a model on an unseen colouring of the held-out games.
- Training-data extractors must also exclude these ids:
  `aq25,rr86,sr26,sr15,tq87,tr93,vr33`.
- Every manifest entry says `held_out: true` and `usage: TEST ONLY -- NEVER TRAIN`, every game
  file starts with the same warning, and every `metadata.json` is tagged `test-only-never-train`.
- **No solution files**, on purpose: a recolor copy's winning line is the held-out original's own
  winning line. The proof that every level is winnable is in `manifest.json` (engine, frame-by-frame
  and loader checks, all passed); the builder replays the originals' recorded lines to make it.

## Not a yardstick until a human has played it

Every entry has `reviewed: false` until the Boss or Son has played it and set it to `true`.
Previews (original left, copy right) are in `previews/`.
