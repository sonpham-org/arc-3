# Plan: restore a complete set of shortest winning paths for the 25 public games

Written 5-Oct-2026 21:59 ET by Bubba (Claude Opus 5.5), at the Boss's request (#arc-3), for the Boss and Son.
Status: PLAN, awaiting go from the Boss / Son.

## Goal
Every level of all 25 public games has one verified winning path that is as short as we can get it.
The paths are recorded per level with their source, and they are clean teacher data for Son's training
and the reference for the harness audit (Sprint 1). The held-out fence stays intact.

## What we have (checked 5-Oct)
- Recorded winning lines for all 25 originals, from the arc-explainer human-reasoning release (the source
  the copycat builders use, `original_solution()` in autoresearch-arena/arc3games/copycats/copycat_core.py).
- 18 of them are packaged in this repo, identical to the original lines, under
  datasets/copycat-games/recolor/solutions/.
- The other 7 (vc33, ar25, sb26, re86, su15, tr87, tu93) have **no solution files on purpose**. Their copies
  are test-only (datasets/test-only-games), so their lines must never enter training.
- The new human-records page (docs/human-records.html, 5-Oct) gives the fewest actions in any published
  human win per game.

## Our 18 lines against the human record (total actions to win)
Close to the record (within about 10%): ft09, s5i5, cd82, cn04, g50t, dc22, bp35, lf52, sc25.
Clearly longer: sk48 (387 vs 213), tn36 (148 vs 85), sp80 (129 vs 86), lp85 (109 vs 79), ka59 (325 vs 242),
m0r0 (231 vs 179), r11l (71 vs 57), ls20, wa30.
Training on the long ones teaches slow routes, and Kaggle scores action efficiency.

## Steps
1. **Pull the record-holders' winning replays** from the official ARC-AGI-3 human leaderboard for every game
   where ours is longer (we already did this for bp35 and g50t in September; see
   docs/trace-findings/2026-09-13-*). Respect the source; read only what the site publishes.
2. **Cut each replay into per-level segments and replay each through the offline loader** (arc_agi offline
   Arcade, the loader taaf uses) until it reaches the level clear. Any segment that does not replay is
   dropped, not patched.
3. **Keep the shortest verified path per level**, not per game. Levels can come from different sources.
   Record the source and the action count for each level.
4. **Package it** as datasets/winning-paths/ (one file per game: levels, actions, source per level,
   verified=true), with a README and a summary table against the human records.
5. **Hand it to Son** as teacher data (executed actions only), and use it for the Sprint 1
   representation/action-space audit.

## Decision for the Boss and Son
The 7 held-out games: keep them held out (no paths built), or end the holdout for the final push and add
their paths too. The plan above keeps them held out unless Son says otherwise.

## Owners
- Bubba (helper agent): steps 1–4, on the Mac Mini CPU only. No GPU and no Kaggle hours.
- Son: the holdout decision, and how the paths enter training (SFT seed, RL reference, or both).
