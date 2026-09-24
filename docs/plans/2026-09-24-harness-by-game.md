<!--
Author: Claude Fable 5.1, for Son Pham
Date: 24-September-2026
PURPOSE: Son, 24-Sep: "analyze what harness is good at what games and why." Per-harness x per-game
analysis over every Flash-Next 25-game run since 8-Sep (104 published, read from the site's railway
Postgres) plus the 27 unpublished 20-24 Sep runs (GCS summaries), plus the four hard-seven one-wave
arms and the 264-minute runs that finished tonight. Names the game regimes, which harness family wins
each, the clock effect per game, and what it implies for the router.
SRP/DRY check: Pass. Data assembly is gcp/controllers/cv5-cr-clock/analysis/{build_dataset,analyze}.py (reproducible from the
DB and bucket); the harness census (adaptive-thinking-mode-router.md s8) and the intensive-harness
program doc are cited, not restated. Numbers are means of per-run values; n is stated per cell.
-->

# What harness is good at what game, and why

**Data.** 131 Flash-Next runs: 104 published 25-game runs since 8-Sep (site DB, `arc3_runs` /
`arc3_game_scores`), 21 unpublished complete 25-game runs from 20-24 Sep (GCS `summary.txt`), the
264-minute runs that finished tonight, and the four hard-seven one-wave arms. Per-game score is the
harness's score on that game (0-100, RHAE-style); "mean" is the 25-game mean. Families are grouped by
run name; n per cell is 1-5, so **a per-game winner with a margin under ~10 points is noise** (sb26's
per-run sd alone is 33). The robust claims below are the ones that hold across related families and
across the clock lift.

## 1. The games sort into four regimes

Observed over all 126 runs (levels/total, mean score, sd, actions per cleared level, full clears):

| regime | games | mean score | actions / level | what the data says |
|---|---|---|---|---|
| **S: obvious mechanic, execute** | ft09 (52, 20 full clears), sb26 (34, 20 clears), lp85 (37, 5), ar25 (29, 3), re86 (31, 0 - a wall at level 6/8) | 29-52 | **19-48** | cleared fast once seen; the whole variance is whether the harness lets the model *go* |
| **A: plan, then execute a long exact sequence** | r11l (14, sd 15), vc33 (22), tr87 (18, sd 19), cn04 (7), cd82 (8), tu93 (16) | 7-22 | 22-75 | bimodal per run: either the plan is right and the level falls in ~20-40 actions, or it isn't and nothing happens. Scores swing 0 -> 100 between runs of the same family |
| **B: explore to discover the mechanic** | dc22 (10), su15 (9), sc25 (10), ka59 (11), m0r0 (11), s5i5 (7), sp80 (5), wa30 (3.8), tn36 (3.7), g50t (3.9) | 4-11 | **88-156** | every level costs a hundred-plus actions of probing; progress is roughly linear in clock |
| **W: walls** | ls20 (2.6, 221 act/level), lf52 (2.7, 98), bp35 (1.1, 88), sk48 (0.4, **659**) | <3 | 88-659 | no harness has cleared more than 3-4 levels; the best ever single scores are 10.7 / 5.5 / 5.8 / 8.3 |

The hard seven Son named (bp35, g50t, lf52, ls20, sk48, tn36, wa30) are the three worst B games plus
all four walls. That matters for the router: **the hard seven are two different problems** - B games
respond to clock and to re-observation, walls respond to nothing we have except (once) symbolic search.

## 2. Which family wins which game (132 min, families with n >= 2)

The matrix is in `gcp/controllers/cv5-cr-clock/analysis/analyze.py` section C; the per-game winners with their margin over the median family:

| game | winner | score | 2nd | median | reading |
|---|---|---|---|---|---|
| ft09 | **LA-CR** | 100 | LB-CR 86 | 56 | S-regime: deleting the Loop-A "default loop" bullet lets the model act; every Loop-deletion family is above median here |
| sb26 | **LAB-v5** 93 / LA-CR 90 / compaction no-cap 88 | | | 38 | same; the three winners share "act without the loop bullet, keep context" - clean-return alone gets 35 |
| ar25, lp85 | LAB-v5 / LA-CR / no-cap (all 41.7 = 5/8 levels) | | | 33 | ceiling at level 5 for everyone at 132; the 264 runs clear it (100) |
| re86 | LA-CR 41.7, reset-compaction 41.7 | | | 31 | wall at level 6 for every harness ever (0 full clears in 126 runs) |
| **cn04** | **no-cap** | 25.4 | swap50 10 | 4.3 | A-regime: uninterrupted batches |
| **r11l** | **no-cap** | 31.0 | LAB-v5 29 | 12 | A-regime; at 264 no-cap solves it (100). LA-v5 gets 4.8 - the return cap *hurts* here |
| **vc33** | **no-cap** | 28.6 | reset-middle 28 | 20 | A-regime; no-cap 264: 75 |
| **tr87** | **compaction no-cap** | 59.5 | no-cap 50 | 11 | A-regime and long: cap-free batches plus compaction. LA-CR scores **0** on tr87 |
| **cd82** | **compaction no-cap** | 26.7 | swap50 25 | 7 | same pair again |
| tu93 | cv5-CR 22 / cleanrem 21 | | | 13 | compaction families; at 264 cv5-CR gets 62 (7/9) |
| **dc22** | **clean-return** | 17.6 | reset-middle 14.5 | 8.5 | B-regime: the return cap re-observes every 14 actions |
| **su15** | **clean-return** | 13.4 | reset-compaction 13.3 | 7.8 | B-regime |
| **wa30** | **clean-return** | 11.1 | cleanrem 7.6 | 2.5 | B-regime, hard-seven |
| ka59 | reset-middle 19.8 / cleanrem 19.2 | | | 10.6 | RESET-as-strategy games |
| sc25 | LAB-CR 20 / reset-middle 19 | | | 11 | same |
| s5i5 | LAB-CR 12.5 / clean-return 11 | | | 6 | B |
| g50t | **cv5-CR** 10.7 | | no-cap 7 | 3.4 | hard-seven B; compaction v5 keeps the exploration record across swaps |
| sk48 | **cv5-CR** 4.2 | | LA-v5 1.4 | 0.0 | wall; cv5-CR's 4.2 is the best any 132 run has done |
| tn36, lf52 | LA-CR 7.1 / 4.5 | | | 3.3 / 2.9 | hard-seven; margins are within noise |
| ls20 | mtrsym (symbolic) 8.2 | | LA-v5 5.7 | 2.4 | wall; symbolic search is the only thing that has ever moved it (see s4) |

Three families cover the board:

1. **Loop-deletion + clean-return (LA-CR, LAB-v5)** owns the S regime. Mean 18.6 / 17.7, best all-25
   at 132, and it gets there by clearing ft09, sb26, ar25, lp85, re86 faster - not by doing anything on
   the hard games (hard-7 3.7 / 3.3, median). LA-CR's tr87 = 0 and r11l = 9.5 show its failure mode:
   when the level needs a long exact sequence, the return cap keeps cutting the batch and the
   loop-free prompt re-plans from scratch each time.
2. **No-cap (with or without compaction)** owns the A regime: cn04, r11l, vc33, tr87, cd82 - every
   game where a correct plan is 20-40 actions long. That is exactly why no-cap264 is the site's best
   run (32.02): at 264 it takes r11l 100, vc33 75, dc22 47, sc25 32, sb26 88. Its weakness is the B
   regime (hard-7 1.2-2.4 at 132): with no cap it burns actions blind.
3. **Clean-return (cap 14, return) and its compaction variant (cv5-CR)** own the B regime and are the
   only families that score on the walls: clean-return wins dc22, su15, wa30; cv5-CR wins g50t, sk48,
   tu93. Their all-25 means are the *worst* of the three (15.1 / 12.7) because the same return cap that
   re-observes on a hard game interrupts an obvious one. clean-return's hard-7 4.14 is the highest
   n>=2 number at 132.

So the census's "compaction-v5-CR is worst overall and best on the hard seven" is not a paradox: it is
one mechanism (interrupt-and-re-observe) with opposite signs in the S and B regimes.

## 3. What the clock buys, per game (132 -> 264, same family)

| family | 132 -> 264 | games that moved | games that did not |
|---|---|---|---|
| clean-return | 15.1 -> 25.1 | ar25 17->58, ft09 36->96, lp85 37->100, su15 13->57, **tn36 5->27, g50t 4->21**, s5i5 11->28, sc25 13->23 | bp35, lf52, ls20, sk48, wa30 flat; **sb26 35->4, r11l 21->5** (regressions, n=1) |
| no-cap | 16.9 -> 32.0 | r11l 31->100, vc33 29->75, sb26 21->88, dc22 9->47, sc25 2->32, cn04 25->48, ka59 14->27, lp85 40->100, ft09 56->100 | tr87 50->4, tu93 19->4 (n=1 regressions), the walls |
| compaction no-cap | 17.8 -> 23.9 (n=2 each) | ar25, tu93 16->49, vc33 21->48, ka59 10->31, r11l 10->26, lp85 41->75 | tr87 60->16, sb26 88->67, cd82 27->13 |
| cv5-CR | 12.7 -> 29.3 | ar25 22->100, lp85 35->100, sb26 31->87, tu93 22->62, cn04 5->48, ka59 2->33, m0r0 9->40, r11l 10->45, re86 28->42, ft09 56->33(!) | **the hard seven: 4.2 -> 3.8**; dc22 14->0, sc25 1->0 |

Two robust patterns. **(a)** Doubling the clock roughly doubles the mean for every family, and the
gain lands in the S and A games: the 4-wave schedule gives each game ~34 minutes, and S/A games that
were one plan away from clearing get that plan. **(b)** The walls do not move with clock in any family
(bp35 0-4, lf52 2-4, sk48 0-7, ls20 5-8 across all 264 runs). The one exception is clean-return 264's
tn36 27 / g50t 21 - the source of its hard-7 9.92, which no other 264 run reproduces (3.7-5.9) and
which is why the replicate is queued.

cv5-CR's 264 run is the sharpest case: **+16.6 points, none of it on the hard seven.** Its compaction
keeps medium games coherent over 60+ minutes (tu93, ka59, m0r0, r11l, cn04 all moved 20-40 points), but
the hard games it was best at with 34 minutes did not improve with 70. So "compaction is good for hard
games" is the wrong lesson from the 132 census; the right one is "compaction is good for *long*
games, and at 132 the hard games were the only long ones."

## 4. The hard seven with the whole clock (one wave, 132 min per game)

| arm (flags on cv5-CR) | 7-game mean | levels | actions | per game (score/levels) |
|---|---|---|---|---|
| **solver** (loop/priors/transition/coords/search deleted) | **9.13** | 17 | 3,440 | bp35 10.0/3, g50t 9.2/2, lf52 5.2/3, ls20 2.4/2, sk48 0/0, tn36 25.6/4, wa30 11.4/3 |
| execution (memory + evidence-gated lease) | 8.32 | **19** | 2,857 | bp35 2.7/2, g50t 8.8/2, lf52 4.1/3, ls20 2.7/2, sk48 2.8/1, tn36 22.1/5, wa30 15.0/4 |
| symbolic (memory + symbolic search) | 8.29 | 14 | 3,247 | bp35 7.4/3, g50t 10.7/2, lf52 1.8/1, **ls20 29.0/4**, sk48 0.2/1, tn36 3.6/1, wa30 5.3/2 |
| memory | 5.46 | 12 | 3,692 | bp35 8.2/3, g50t 10.7/2, lf52 1.8/1, ls20 2.4/1, sk48 0/0, tn36 10.7/2, wa30 4.4/3 |
| *same harness, 4-wave 132 (n=2)* | 4.23 | 9 | 1,006 | |
| *clean-return 264 (4-wave)* | 9.92 | 15 | 2,542 | tn36 26.9/4, g50t 21.4/3, wa30 13.3/3 |

What the whole clock does: **tn36 responds to everything** (22-26 for solver/exec/CR264 versus 3.7 in
the field), **g50t and bp35 respond to any memory or solver variant** (9-11 / 7-10), **wa30 responds to
exec** (15.0 / 4 levels, the best wa30 ever), and **ls20 responded to exactly one thing in 131 runs:
symbolic search** (29.0 / 4 levels; the previous best was 10.7). ls20 is the 221-actions-per-level
game: a long deterministic sequence, which is what a CPU search over a scalar state model is for. sk48
(659 act/level) responded to nothing; exec's 2.8 / 1 level is the second-best sk48 ever.

The arms differ more per game than in total: solver 9.13 and exec 8.32 are indistinguishable at n=1,
but solver's win is bp35 + lf52 and exec's is wa30 + tn36 + levels (19). The v2 arms (execution_v2,
memory_v2, symbolic_v2, running now) test whether making those mechanisms *executable and
history-verified* moves the walls rather than just the B games.

## 5. Why - the mechanism behind each family

- **Loop A deletion** removes the "default loop: summarize objects, infer the desired change, choose a
  probe or searched plan" bullet. On S games the model already sees the mechanic; the bullet makes it
  narrate a plan for a turn or two before acting, and on a 34-minute budget that is 10-20% of the game.
  On B games the bullet was doing real work (it is the exploration procedure), so LA loses nothing on
  the hard seven but also gains nothing. LAB (also deleting the world-model bullet) is the same with
  more variance.
- **The action cap.** Cap-14-return interrupts every batch to re-observe. That is the *right* thing when
  the model's plan is a guess (B regime: dc22, su15, wa30) and the *wrong* thing when it is a computed
  sequence (A regime: r11l, vc33, cn04, tr87). No-cap is the mirror image. Legacy cap (interrupt without
  the "return" semantics) sits between them and is the site's second-best run at 264, which says the
  cap *mode* matters less than whether long sequences are allowed at all.
- **Compaction (v5 summarised swap vs plain 50% drop).** Pays on long games: every compaction family's
  264 gain is in tu93, ka59, cn04, m0r0, r11l - games that need 40-80 minutes of coherent context. It
  costs on S games at 132 (cv5-CR ft09 56, sb26 31, ar25 22 - all below median) because the swap
  fires while the model is mid-solution and the summary loses concrete coordinates; at 264 those games
  have time to recover (ar25 100, sb26 87). Swap fraction (30/50/70) is second-order.
- **Memory / execution lease / symbolic.** Neutral-to-negative on the 25 at 132 (feat132 arms 10-14)
  because the S/A games do not need a persistent model. On the hard seven with a full clock they are
  worth +4 to +5 points each over the base, and symbolic search is the only recorded way through
  ls20. These are hard-game tools and should be routed, not global.
- **RESET-oriented variants (reset-middle, reset-compaction)** win ka59 and sc25, the two games where
  restarting a level is cheaper than repairing it. Nowhere else.

## 6. What this says for the router (program item 5)

The per-game winner is predictable from cheap, early features, which is the router's premise:

| signal in the first ~40 actions of a game | regime | route to |
|---|---|---|
| a level clears in < 40 actions | S | Loop-A-deleted prompt, no return cap, thinking as-is |
| the model's plan is >= 10 actions and its first 3 expectations confirm | A | no-cap batches, compaction on |
| > 100 actions, no level, expectations failing | B | return cap 14, memory on, give the game the clock (one-wave scheduling) |
| B for > 150 actions and the frame transitions are deterministic | W | symbolic / executable-model search |

Equivalently: the three families are not competitors, they are the three arms of one policy, and the
25-game mean has been hiding that because it weights S games (4-5 of 25, 20-100 points each) over the
hard seven (< 10 points each). A router that picks LA-no-cap on S/A and clean-return-memory on B/W
would, on tonight's numbers, take no-cap264's S/A games (r11l 100, vc33 75, sb26 88) *and* the one-wave
hard-seven arms' B games (tn36 25, wa30 15, ls20 29) - roughly 38-40 mean at 264 versus the 32 record.
That is the target the RL scheme (item 4) should be scored against.

## Caveats

n = 1-5 per cell; per-game sd is 5-33 points; the 264 rows are n = 1 except compaction no-cap (2) and
cleanrem (2). tr87 / tu93 / sb26 regress between paired runs of the same family by 40-50 points, so
single-game claims about those three are unreliable. The walls' numbers are robust precisely because
they are all near zero. The hard-seven arm results are one run each; the v2 arms and the clean-return
264 replicate (launched 24-Sep) are the next data points.
