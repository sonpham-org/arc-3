<!--
Author: Claude Opus 5.5 (Bubba)
Date: 06-October-2026
PURPOSE: For Son (#arc-3, 6-Oct 00:17 ET): per game, the level our harness clears reliably and the level where it starts to get stuck, from recorded run data only. Feeds the "Stuck levels" tab of the Mode explorer page. Data: docs/static/data/stuck-levels.json, built by scripts/stuck_levels_tally.py.
SRP/DRY check: Pass - a written view of stuck-levels.json; rerun the script to refresh, do not hand-edit numbers here.
-->

# Stuck levels per game (6-Oct-2026)

Son asked which level each game is cleared reliably through, and where the model starts to struggle, because
those are the points where a different per-turn prompt (a mode, or a scheme of modes) should take over from Stock.

## Definitions

- **Safe through L**: every level from 1 to L was cleared in at least 90% of runs.
- **Stuck at L + 1**: the first level that misses the 90% bar. "None" means every level clears in 90% of runs.
- **Soft**: the stuck level still clears in three runs out of four or more. It missed the bar by a run or two.
- **Clock**: the runs that stopped at the stuck level spent a median of 150+ actions on it. That looks like
  grinding until time ran out, not a wall at the first move.

## Where the numbers come from

- **Main column: Franzen-notebook line, stock prompt, 11 runs.** Son's GCP runs of Daniel Franzen's public
  notebook with Son's tuned draft head, all 25 games, the 132-minute suite: the seven 2-Oct cache and draft
  variants published to the site, and the four 3-Oct no-coach runs of his submission-shaped build
  (`sbt06hic11`, the base of the 31.63 notebook). Same harness and per-turn prompt as the 28.94 and 31.63
  notebooks; serving settings differ from run to run. These are not Kaggle runs.
- **Side column: same line with the RL2 mode coach on, 14 runs.** Not the stock prompt, so never pooled.
- **Side column: older line, 22 runs.** Son's earlier harness (the 18.99 line: pruned Flash-Next on SGLang)
  at full context, 27-Sep to 1-Oct.
- Read off the site's storage (per-run overview files and the RL2 explore files) and the local run summaries.
  Runs that died before the clock ran out are left out.

## Caveats

- **Eleven runs is thin.** At this size the 90% bar means at most one miss, so a single bad run moves a
  game's stuck level. Read the median next to it.
- **The per-level rates are a survival curve, not independent trials.** A run that cleared four levels
  cleared levels one to four in order, so rates can only fall level by level.
- **GCP is not Kaggle.** The suite runs 25 games on a 132-minute clock; the competition runs about 110 hidden
  games on a 9-hour shared clock. Where the clock flag is set, more time alone may move the stuck level.
- **Not used:** Kaggle submissions report one total, no per-game levels. Son's later Franzen-line runs
  (4-Oct on, the score-climb page) have totals only on the site, so they are not in this tally.

## The tally, hardest first

| Game | Levels | Safe through | Stuck at | Clear rate at stuck level | Median levels | Older line safe / n | Coach on safe |
|---|---|---|---|---|---|---|---|
| Skewer Kebabs (sk48) | 8 | 0 | 1 | 8/11 | 1 | 0 / 22 | 0 / 14 |
| Ghost Twin (g50t) | 7 | 0 | 1 | 7/11 | 1 | 0 / 22 | 0 / 14 |
| Buoyant Pontoons (bp35) | 9 | 1 | 2 | 1/11 | 1 | 1 / 22 | 1 / 14 |
| Warehouse Associates (wa30) | 9 | 1 | 2 | 6/11 | 2 | 1 / 22 | 1 / 14 |
| Toggle Navigator (tn36) | 7 | 1 | 2 | 5/11 | 1 | 1 / 22 | 1 / 14 |
| Coded Notches (cn04) | 6 | 1 | 2 | 5/11 | 1 | 1 / 22 | 1 / 14 |
| Streaming Purple (sp80) | 6 | 1 | 2 | 7/11 | 3 | 1 / 22 | 1 / 14 |
| Leapfrog (lf52) | 10 | 2 | 3 | 8/11 | 3 | 1 / 22 | 1 / 14 |
| Sliding Indicator (s5i5) | 8 | 2 | 3 | 6/11 | 3 | 2 / 22 | 1 / 14 |
| Kick Away (ka59) | 7 | 2 | 3 (soft) | 9/11 | 5 | 2 / 22 | 2 / 14 |
| Deck Control (dc22) | 6 | 2 | 3 | 8/11 | 4 | 2 / 22 | 2 / 14 |
| Sucking Up (su15) | 9 | 3 | 4 (clock) | 8/11 | 6 | 3 / 22 | 3 / 14 |
| Locksmith (ls20) | 7 | 3 | 4 (soft, clock) | 9/11 | 4 | 1 / 22 | 1 / 14 |
| Reach Emblems (re86) | 8 | 5 | 6 | 8/11 | 6 | 5 / 22 | 5 / 14 |
| Mirror Rendezvous (m0r0) | 6 | 4 | 5 (soft) | 9/11 | 5 | 1 / 22 | 0 / 14 |
| Compass Dye (cd82) | 6 | 4 | 5 (soft) | 9/11 | 6 | 2 / 22 | 3 / 14 |
| Functional Tiles (ft09) | 6 | 4 | 5 | 7/11 | 6 | 4 / 22 | 4 / 14 |
| Reaching Lurch (r11l) | 6 | 4 | 5 (soft) | 9/11 | 6 | 1 / 22 | 1 / 14 |
| Sigil Caster (sc25) | 6 | 4 | 5 (soft, clock) | 9/11 | 6 | 2 / 22 | 3 / 14 |
| Toggle Runes (tr87) | 6 | 5 | 6 (soft) | 9/11 | 6 | 4 / 22 | 4 / 14 |
| Trail Unwind (tu93) | 9 | 8 | 9 | 7/11 | 9 | 5 / 22 | 5 / 14 |
| Axis Reflectors (ar25) | 8 | 8 | none, all clear | - | 8 | 7 / 22 | 7 / 14 |
| Loop and Pull (lp85) | 8 | 8 | none, all clear | - | 8 | 7 / 22 | 8 / 14 |
| Sequence Belt (sb26) | 8 | 8 | none, all clear | - | 8 | 4 / 22 | 8 / 14 |
| Volume Control (vc33) | 7 | 7 | none, all clear | - | 7 | 4 / 22 | 3 / 14 |

No game is safe through a higher level on the older line or with the coach on than on the Franzen line's
stock prompt. The games that need a different prompt soonest are Skewer Kebabs and Ghost Twin (level 1
already misses the bar), then Buoyant Pontoons, Warehouse Associates, Toggle Navigator, Coded Notches and
Streaming Purple (level 2).
