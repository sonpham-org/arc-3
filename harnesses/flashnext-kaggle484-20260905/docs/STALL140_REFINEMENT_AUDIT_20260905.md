# Stall-140 and refinement audit — 2026-09-05

This audit reads the immutable 25-game benchmark artifacts rather than inferring results from the minute observer. `Full games solved` means the game reached its terminal success state; `positive games` means only that its score was greater than zero.

## Final seed-1 performance and work

| Arm | Mean score | Full games solved | Positive games | Levels | Actions | Generated tokens | Total game-lane time | Mean game time | Median game time |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Baseline | 13.3086415498 | 1 | 23 | 50 | 3,377 | 2,511,967 | 166,311.25 s | 6,652.45 s | 6,480.59 s |
| Stall-140 | 11.0891756507 | 0 | 21 | 46 | 3,725 | 2,484,333 | 154,556.03 s | 6,182.24 s | 6,480.38 s |
| Baseline + Dynamic Slack | 9.2644296339 | 0 | 23 | 45 | 4,643 | 2,766,770 | 189,230.26 s | 7,569.21 s | 7,682.62 s |
| Stall-140 + Dynamic Slack | 11.8239168726 | 0 | 22 | 53 | 3,526 | 2,833,721 | 180,328.73 s | 7,213.15 s | 7,680.66 s |
| Reflection V3 | 7.2334907160 | 0 | 22 | 40 | 3,155 | 2,739,653 | 166,489.65 s | 6,659.59 s | 6,480.66 s |
| Refinement | 4.8910047554 | 0 | 21 | 30 | 3,136 | 2,736,003 | 166,513.67 s | 6,660.55 s | 6,480.55 s |

## What Stall-140 actually did

The 140-action threshold fired on 10 games: `cd82`, `dc22`, `ft09`, `g50t`, `ls20`, `sb26`, `sc25`, `sk48`, `su15`, and `wa30`.

Across all 25 games, Stall-140 lost 55.4866 score-sum versus baseline, or 2.21946 mean-score points. It used 27,634 fewer generated tokens and returned 11,755.23 game-lane seconds (3.265 hours).

On the 15 games where the threshold did not fire:

| Metric | Baseline | Stall-140 | Delta from Stall-140 |
|---|---:|---:|---:|
| Score sum | 159.0904 | 214.5423 | +55.4519 |
| Levels | 30 | 36 | +6 |
| Actions | 1,841 | 2,003 | +162 |
| Generated tokens | 1,521,763 | 1,641,965 | +120,202 |
| Game-lane time | 98,727.34 s | 98,667.00 s | -60.34 s |

The 10 threshold games used 147,836 fewer tokens under Stall-140. Of that reduction, 120,202 tokens (81.31%) appeared on the 15 non-threshold games, while total suite generation was still 27,634 tokens lower. This is genuine token redistribution, but not a clean causal time reallocation: non-threshold lane time did not rise. vLLM continuously batches all admitted requests, and standalone Stall-140 has no explicit slack allocator.

The danger is real. The threshold-game score sum fell from 173.6256 to 62.6871 (-110.9385), overwhelming the gain elsewhere. In particular, `ft09` went from a full 100-point solve under baseline to 47.619 after Stall-140 stopped it after four levels. Large additional losses included `sb26` (27.778 to 3.667), `sc25` (18.862 to 0), `wa30` (13.333 to 2.046), and `cd82` (4.001 to 0). An unconditional 140-action kill rule should not be adopted.

Dynamic Slack is the component that explicitly reallocates returned lane-seconds. Stall-140 + Dynamic Slack beat Baseline + Dynamic Slack in both available matched runs: +2.55949 mean points in seed 1 and +0.71131 in seed 2. This does not rescue standalone Stall-140: it trailed baseline in the final seed-1 run and in the current seed-2 snapshot.

The completed second Dynamic Slack replicate adds the requested solve/time data:

| Arm | Mean score | Full games solved | Positive games | Levels | Actions | Generated tokens | Total game-lane time | Mean game time | Median game time |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Baseline + Dynamic Slack r2 | 9.6380185038 | 0 | 23 | 47 | 3,531 | 2,573,278 | 170,003.29 s | 6,800.13 s | 6,480.90 s |
| Stall-140 + Dynamic Slack r2 | 10.3493310592 | 0 | 23 | 48 | 3,571 | 2,709,563 | 181,335.09 s | 7,253.40 s | 7,680.54 s |

In this replicate the combined arm gained 0.71131 mean points and one level while consuming 136,285 more generated tokens and 11,331.80 more lane-seconds (3.148 hours). In seed 1 it gained more score and levels while using 66,951 more tokens but 8,901.53 fewer lane-seconds. Thus the score advantage over Baseline + Dynamic Slack replicated, but the amount and direction of wall-clock redistribution did not; two samples are not enough to call it stable.

## Why refinement was weak

The refinement arm requested 1,445 multipass operations, but only 228 completed (15.78%). Another 1,214 (84.01%) were skipped because the four refinement slots were saturated, and three drafts failed. The experiment was therefore a bottlenecked hybrid, not refinement on every requested hard turn.

Completed refinement work added 558,583 auxiliary draft-and-critic tokens beyond the benchmark's main generation count. The mean auxiliary phase took 62.135 seconds; a completed full multipass took 129.228 seconds on average. Despite that extra work, the arm finished with 30 levels, zero complete games, and mean 4.8910, versus baseline's 50 levels, one complete game, and mean 13.3086. The weak seed-1 result is genuine, but the mechanism tested was capacity-starved and latency-heavy.

## Safer progress-weighted slack proposal

Do not let a raw action threshold kill a game that is making verified level progress. Treat the scheduler as an admission/deadline allocator; a game thread does not exclusively occupy the GPU because vLLM multiplexes active requests.

For active game `i`, define a momentum weight:

```text
m_i = (1 - exp(-levels_i / 1.5))
      * exp(-actions_since_progress_i / 120)
      * exp(-seconds_since_progress_i / 900)
w_i = 0.25 + 2.75 * m_i
```

Recompute after every verified level and every 180 seconds. Allocate returned slack in 180-second quanta proportional to `w_i`, capped at 1,200 bonus seconds per game. Reset both no-progress counters after a verified level.

A conservative donor gate is: donate only when `levels_i == 0`, at least 200 actions have occurred on the same level, and at least 45 minutes have elapsed without verified progress. Never hard-stop a game after it has solved a level; simply stop giving it bonus when momentum decays. Test this against exact baseline and existing Dynamic Slack for at least two matched seeds before adoption.
