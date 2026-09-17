<!--
Author: Claude Opus 5 (Bubba)
Date: 17-September-2026
PURPOSE: Boss's ARC-3 scorecard inventory, re-pulled 17-Sep 12:24 EDT, SEPTEMBER-2026 only.
Answers: which of the 25 pinned duck games still lack a COMPLETE (won) human game from him.
Supersedes INVENTORY-SEPT-20260916-1340.md, which predates six wins (ar25/s5i5/sb26/su15/tu93
on 16-Sep, vc33 on 17-Sep).
SRP/DRY check: Pass — same puller and same filter rules as the 16-Sep doc; this is a refresh,
not a new method.
-->

# Boss ARC-3 inventory — SEPTEMBER ONLY — 17-Sep-2026 12:24 EDT

Puller: `tools/pull_boss_scorecards.py`.
Raw: `boss-cards-20260917T122423.json`, `boss-runs-20260917T122423.json`.
50 cards, 172 runs, 0 fetch failures.

## Method (unchanged from 16-Sep — see that doc for why)

- Date filter is `open_at` from the card **detail**, never `published_at` from the list.
- A run is REAL only if `actions > 0` AND `levels_completed > 0`.
- "Complete game" = a run with `state == WIN`.
- Window: list endpoint caps at 50 cards; this pull spans 2026-01-07 → 2026-09-17, so every
  September card is inside it. Nothing September-dated fell off the bottom.

152 September run rows; 33 are real; 18 of those are wins across 17 distinct games
(g50t has two September wins, 13-Sep and 15-Sep).

## WON in September (17 games)

ar25, bp35, cd82, cn04, dc22, ft09, g50t, ka59, lp85, ls20, m0r0, r11l, s5i5, sb26, su15,
tu93, vc33

New since the 16-Sep 13:40 inventory (6):

- s5i5 `s5i5-18d95033` — WIN, 8L, 507a, opened 2026-09-16 17:44Z
- ar25 `ar25-0c556536` — WIN, 8L, 887a, opened 2026-09-16 18:58Z
- sb26 `sb26-7fbdac44` — WIN, 8L, 143a, opened 2026-09-16 19:20Z
- su15 `su15-1944f8ab` — WIN, 9L, 293a, opened 2026-09-16 19:33Z
- tu93 `tu93-0768757b` — WIN, 9L, 297a, opened 2026-09-16 19:48Z
- vc33 `vc33-5430563c` — WIN, 7L, 575a, opened 2026-09-17 14:51Z

**vc33 build note:** this win is on `vc33-5430563c`, which the 16-Sep doc identified as the
LIVE build. The old Feb GAME_OVER sat on the dead build. vc33 is now properly covered.

## STILL MISSING A COMPLETE GAME (8)

Played in September, never won (7):

- sk48 `sk48-d8078629` — GAME_OVER, 6L, 889a, 11-Sep — closest to a win
- tn36 `tn36-ef4dde99` — GAME_OVER, 5L, 335a, 14-Sep
- sc25 `sc25-635fd71a` — GAME_OVER, 4L, 246a, 12-Sep
- lf52 `lf52-271a04aa` — NOT_FINISHED, 2L, 187a, 12-Sep
- wa30 `wa30-ee6fef47` — NOT_FINISHED, 1L, 36a, 11-Sep
- re86 `re86-8af5384d` — NOT_FINISHED, 1L, 22a, 12-Sep
- sp80 `sp80-589a99af` — NOT_FINISHED, 1L, 13a, 02-Sep (and 6a, 11-Sep)

Never cleared a level, ever (1):

- tr87 `tr87-cd924810` — only real run in the whole account is 0 levels / 24 actions,
  02-Sep. Five more September opens, all zero-action. This is still a cold start.

## Cutoff

Newest card on the account: 2026-09-17T15:18:44Z (`last_update`). That is the vc33 session.
