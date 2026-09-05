# Flash-Next champion metadata + CPU toolkit + reminder crossover

This archive descends from the immutable recovered Kaggle champion and combines
three previously isolated mechanisms:

- visual-transition `metadata` mode: compact action, returned-frame count,
  changed-frame count, and sampled timeline-position labels are delivered
  immediately before the next reasoning request; no raw transition PNGs are
  added and legacy ASCII storyboard/region inspection remains available;
- the optional CPU vision toolkit, bounded per-game cache, and persistent
  helper registry;
- the compact advisory runtime/token reminder. It reports the fresh minimum of
  game/suite remaining time and cumulative backend-reported generated tokens
  against the 108,000-token soft target. It never imposes a cutoff.

It preserves the scored runtime contract: Flash-Next revision
`7b719225242aacd3dbd3f9407468c2ee9a9d2594`, 32,768 analyzer context,
fixed-30 retained assistant turns, 22 workers, 6,480 seconds per game,
132-minute suite boundary, strict cumulative action cap 14, PLU0, no replay,
no reflection, no refinement, no Dynamic Slack, and the persistent top-six
GPU world-model curator.

Validation: both source trees compile; the 136-test toolkit regression suite,
11 reminder unit tests, and six visual-transition tests pass; a metadata-mode
activation smoke verifies simultaneous timeline metadata, legacy region
guidance, `vision.help`, persistent helpers, and a live reminder instance.
