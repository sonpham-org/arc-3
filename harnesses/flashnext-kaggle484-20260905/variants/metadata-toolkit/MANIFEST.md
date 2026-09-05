# Flash-Next champion metadata + CPU toolkit crossover

This archive descends from the immutable recovered Kaggle champion and combines
two previously isolated mechanisms:

- visual-transition `metadata` mode: compact action, returned-frame count,
  changed-frame count, and sampled timeline-position labels are delivered
  immediately before the next reasoning request; no raw transition PNGs are
  added and legacy ASCII storyboard/region inspection remains available;
- the optional CPU vision toolkit, bounded per-game cache, and persistent
  helper registry from `arc3-kaggle484-cpu-toolkit-20260905.tgz`.

It preserves the scored runtime contract: Flash-Next revision
`7b719225242aacd3dbd3f9407468c2ee9a9d2594`, 32,768 analyzer context,
fixed-30 retained assistant turns, 22 workers, 6,480 seconds per game,
132-minute suite boundary, strict cumulative action cap 14, PLU0, no replay,
no reflection, no refinement, no Dynamic Slack, and the persistent top-six
GPU world-model curator. The budget reminder is absent.

Validation: both source trees compile; the 136-test toolkit regression suite
passes; the six visual-transition tests pass in their intended replace-mode
contract; and a metadata-mode activation smoke verifies simultaneous timeline
metadata, legacy region guidance, `vision.help`, and persistent helpers.
