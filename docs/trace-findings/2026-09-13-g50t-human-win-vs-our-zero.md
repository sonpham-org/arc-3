<!--
Author: Claude Opus 5 (Bubba)
Date: 13-September-2026
PURPOSE: Compare a human WIN replay of g50t (7/7 levels, score 89.39) against our job-1
control arm, which scored 0.000 on all four passes of the same game. Establishes that the
rewind verb (ACTION5) is used sparsely but from the very first level by a human, and that
level 5 is the difficulty wall for humans as well.
SRP/DRY check: Pass — new artifact (human replay guid 4f0689d0), not covered by
2026-09-13-job1-control-baseline.md, which records our side only.
-->

# g50t — a human WIN against our four zeros

Replay: <https://arcprize.org/replay/4f0689d0-7d06-4be7-91ac-31cb9a800b85>
Pulled via the two undocumented endpoints (`/api/sessions/<guid>`,
`/api/recordings/g50t-5849a774/<guid>`). 73.6 MB NDJSON, 534 rows. Human-tagged,
published 2026-09-13 18:20 UTC.

## Result

**WIN, 7 of 7 levels, 533 actions, 9 resets, score 89.39.**

| Level | Actions | Baseline | Level score (of 115) |
|---|---|---|---|
| 1 | 43 | 78 | 115 |
| 2 | 67 | 175 | 115 |
| 3 | 68 | 179 | 115 |
| 4 | 55 | 230 | 115 |
| 5 | **173** | **96** | **30.79** |
| 6 | 62 | 54 | 75.86 |
| 7 | 65 | 67 | 106.25 |

Levels 1–4 come in at roughly a quarter to a third of baseline. Level 5 is the only
level played *over* baseline, by 80%, and it is the only level that lost most of its
credit. Level 5 is a wall for a human who already understands the game.

For contrast, our job-1 control arm scored **0.000 on all four passes** of this game
(`2026-09-13-job1-control-baseline.md`), and the earlier astra-grid2 run spent 279
actions on level 1 and 295 on level 2 before cancelling.

## ACTION5 is sparse, and it is used immediately

ACTION5 — the rewind — accounts for **25 of 533 actions, 4.7%**. It is not a move you
spam. But it appears on **every single level**, and the human reaches for it at global
action **16**, still on level 1.

Per-level first use: L1 @16, L2 @45, L3 @122, L4 @193, L5 @246, L6 @412, L7 @480.

Per-level ACTION5 counts: 2, 5, 2, 3, 7, 3, 3.

Our best prior g50t trace did not use the word "rewind" until **step 73 of 109**, already
on level 2 and roughly 380 actions in, having first called the mechanic a "teleport," a
"motion blur trail," "animation debris," and "a second player."

That is the whole gap in one number: the verb that costs 5% of a winning human's actions,
and is present from action 16, is the verb our agent spends hundreds of actions failing to
name.

## RESET is a tool, not a failure

9 resets, at global actions 0, 26, 57, 73, 78, 202, 295, 417, 476, 489 — spread across the
whole session, clustered where a level was being learned (three inside the first 80
actions). A human resets to re-read a level cheaply. This is consistent with the r11l human
WIN, which also carried 7 resets at score 100.

## What this supports

1. The bimodal read holds. g50t is not an unwinnable game or a long game; it is a 533-action
   game with a 7-level ladder that a human clears in half an hour. We score zero on it four
   times running.
2. Level 5 costing a *human* 173 actions against a 96 baseline says the difficulty curve is
   real and steep at 5, not just an agent artifact — same shape as r11l, where exactly one
   run of 363 ever cleared level 5.
3. Naming the rewind verb early is worth more than any efficiency gain. This is the
   strongest single argument for arm C (mechanics-possibility), which includes
   "a solved thing may come un-solved" and "what you control may change" — both of which
   are rewind-shaped.

Raw session summary and recording retained at `/tmp/g50t_sess.json`,
`/tmp/g50t_rec.ndjson` on the Mac Mini (not committed; 73.6 MB).
