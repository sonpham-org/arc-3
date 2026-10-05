# Held-out copycats — TEST ONLY, NEVER TRAIN

Support files for the eight held-out copycats whose game folders sit next to this one
(`../vh33`, `../ah25`, `../sh26`, `../rh86`, `../sh15`, `../th87`, `../th93`, `../ah66`).
Read `../README.md` for the fence before using anything here.

## Not a yardstick until a human has played it

Every entry in `manifest.json` carries `reviewed: false`. A copy is **not** a yardstick -- do not
report scores on it as evidence of anything -- until a human (the Boss or Son) has played it and
set `reviewed` to `true`. `verified: true` only means the stored line wins in the engine and the
loader; it says nothing about whether the copy is fair, readable or as hard as the original.
Boss's direction, 4-Oct-2026: no quality control, no yardstick.

- `manifest.json` — one entry per copy: what was kept, what changed, what could not be copied
  faithfully, verified true/false, the loader check result. Every entry says `held_out: true`.
- `solutions/<id>.json` — the winning line per level (`{id, x?, y?}` in 64×64 display
  coordinates, played from RESET with levels chained in one run). Never use these as
  demonstrations for training.
- `previews/<id>/L<N>_original_vs_copycat.png` — each level's opening frame, original on the
  left, copy on the right.
- `notes/<id>.md` — the longer kept-vs-changed note per game.

The paths inside `manifest.json` are relative to the canonical package
(`sonpham-org/autoresearch-arena`, `arc3games/copycats_heldout/dist/`), where the generators and
the verifier also live.
