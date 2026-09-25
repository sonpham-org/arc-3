# Does a level need xhigh thinking all the way? Branch replay on the LA-CR hard-7 recording

Son, 25-Sep-2026: *"Take a hard-7 run by our best harness. For each level that it solves, assume it is solved with N
turns; for i in 1..N, replay until finishing turn i, then generate traces from turn i+1 onward with the same prompt but
with high, medium and low thinking. Measure whether and how much action efficiency and token efficiency change. If an
alternative branch can, at some point in the level, switch to a more efficient thinking mode, we may be able to train a
LoRA that picks the next thinking mode and saves tokens without sacrificing quality."* Caps: *"until level solve /
spending 2x more turns / spending 2x more actions."*

Controller: `gcp/controllers/branch-replay/` (local `D:\codex-work\branch-20260925`). Method in its README: the
recording's 1,480 model responses are parsed back out of the harness transcript and replayed against fresh offline games
(no model), the game and the agent's history are rebuilt exactly, then the agent goes live with a per-request
reasoning-effort override. Per checkpoint: 2x high, 2x medium, 2x low, 1x fresh xhigh (the noise control). vLLM
prefix caching makes the seven siblings share the replayed prefix's KV, so the xhigh main branch costs nothing.

Recording: `g4run-lacr-hard7-132-w7-20260924-92964fb0e9` (LA-CR, hard seven, one wave, 7920 s per game, 4.55 mean,
11 solved levels). Plan: every turn of every solved level is a checkpoint (lf52 L2, 151 turns, gets 16 spaced ones):
178 checkpoints, 1,246 branches. Wave 1 (12 Spot VMs, 25-Sep 03:20 to 07:20 UTC) finished 695 branches over 102
checkpoints; wave 2 (8 VMs) is running the remaining 478. Sixteen checkpoints (g50t L3 from turn 26, lf52 L2 from
turn 57) are unreplayable: a recorded snippet hit the 30 s sandbox timeout after N actions and a replay under different
load runs a different N. Everything else replayed exactly: 667 of 695 prefixes byte-equal to the recording.

## Wave-1 results (695 branches, 102 checkpoints, all 11 levels)

| effort | n | solved within 2x | action ratio (median, solved) | token ratio (median, solved) | tokens per branch |
|---|---|---|---|---|---|
| xhigh control | 99 | 70% | 1.00 | 1.08 | 59.2k |
| high | 193 | 64% | 1.00 | 1.00 | 57.7k |
| medium | 183 | 69% | 0.97 | 0.99 | 52.2k |
| low | 192 | 58% | 1.02 | 0.99 | 54.2k |

Ratios are branch / recording for the remainder of the level. Token calibration: 0.332 completion tokens per generated
character, measured on the xhigh controls and applied to the recording's remaining thinking + text + code characters.

By position in the level (first / middle / last third of the level's turns):

| effort | early: solved, actions, tokens/branch | middle: solved, actions, tokens/branch | late: solved |
|---|---|---|---|
| xhigh | 72%, 1.00, 71.1k | 63%, 0.98, 36.5k | 2/2 |
| high | 64%, 1.00, 67.3k | 61%, 1.00, 39.3k | 4/4 |
| medium | 67%, 0.97, 63.6k | 71%, 0.96, 27.7k | 4/4 |
| low | 56%, 1.10, 66.9k | 61%, 1.00, 29.8k | 4/5 |

Per level (solve rate by effort; median action ratio of solved branches):

| game | level | turns | recorded actions | human | xhigh | high | medium | low |
|---|---|---|---|---|---|---|---|---|
| bp35 | 1 | 16 | 41 | 21 | 10/10 (0.96) | 16/20 (0.83) | 20/20 (0.88) | 14/20 (1.05) |
| g50t | 1 | 18 | 37 | 78 | 6/11 (1.21) | 14/22 (1.42) | 11/22 (1.13) | 10/22 (1.42) |
| g50t | 2 | 10 | 31 | 175 | 6/6 (1.00) | 11/12 (1.00) | 12/12 (1.00) | 12/12 (1.00) |
| g50t | 3 | 40 | 195 | 179 | 7/10 (1.28) | 9/17 (1.04) | 11/17 (1.05) | 12/18 (1.09) |
| lf52 | 1 | 11 | 13 | 32 | 5/7 (1.00) | 11/12 (0.92) | 11/12 (0.92) | 8/12 (1.05) |
| lf52 | 2 | 151 | 707 | 81 | 7/7 (0.59) | 7/14 (0.37) | 8/13 (0.19) | 9/14 (0.37) |
| ls20 | 1 | 10 | 31 | 22 | 4/6 (0.79) | 9/12 (1.06) | 8/12 (0.83) | 8/12 (0.81) |
| ls20 | 2 | 26 | 231 | 123 | 6/13 (0.98) | 16/26 (0.98) | 16/26 (0.95) | 14/26 (1.01) |
| sk48 | 1 | 35 | 133 | 61 | 0/8 | 2/16 (0.63) | 1/12 (0.65) | 2/15 (0.99) |
| wa30 | 1 | 23 | 50 | 71 | 14/14 (1.13) | 25/28 (1.02) | 22/26 (0.98) | 19/28 (1.16) |
| wa30 | 2 | 35 | 281 | 119 | 4/7 (0.46) | 4/14 (0.51) | 6/11 (0.99) | 4/13 (0.94) |

Charts: `docs/static/branch-replay/branch_ratio_wave1.png` (ratio vs checkpoint position, per effort) and
`branch_ratio_wave1_per_level.png`.

## Reading

1. **The recording is 70% reproducible.** A fresh xhigh sample from the same state clears the level within the 2x caps
   at 70% of checkpoints. sk48 L1 is 0 of 8: the recorded solve was a fluke. That 30% is the noise floor for every
   comparison below; nothing else in the table is bigger than it.
2. **high and medium are not worse than xhigh.** Solve rates 64% and 69% against 70%; median action ratio 1.00 and 0.97;
   tokens per branch 3% and 12% lower. Low is worse: 58% solved, 10% more actions early in a level.
3. **The effort knob barely changes token volume.** The Qwen3.8 template implements medium as "no thinking sentence" and
   low as "keep it brief"; per-branch tokens move by at most 12% overall, 24% in the middle third of a level. The
   spread between two samples at the same checkpoint and effort is far larger than that. This is the main finding for
   the LoRA idea: there is little to route between, because the settings do not produce distinct behaviours on this
   model. A router would be choosing between near-identical distributions.
4. **Where cheaper branches win, it is the recording that lost.** lf52 L2 (707 recorded actions against a human 81) is
   beaten by every effort at 0.2 to 0.6 of the recorded actions; wa30 L2 likewise at 0.5. g50t L1 and wa30 L1 go the
   other way: every effort, including the xhigh control, needs more actions than the recording. Efficiency is a
   property of the sample, not of the effort setting.
5. **Oracle switch value is sampling variance.** At 68 of 98 checkpoints some cheaper branch solved with no more actions
   than the recording; picking those would cut remaining-level tokens by 34%. But the xhigh control alone would give a
   comparable "saving" by resampling, so this is best-of-n, not routing.

What a switch policy could still exploit: the middle third, where medium solves as often as xhigh (71% vs 63%) at
0.96 of the actions and 24% fewer tokens. That is one bin of one recording and inside the noise floor; wave 2 adds the
remaining mid- and late-level checkpoints and will say whether it holds.

## Sibling results from the same night

- Act mode hard-7 replicate #2 `g4run-modes-hard7-act-132-w7-20260925-43772c5cb5` = 6.42 / 14 levels against #1's
  10.06: act sits with solver (9.13 / 4.73), LA-CR (9.04 / 4.55) and CR (8.43 / 4.75).
- MTP with a forced KV pool (`lacr-serving-variants` mtp3): 13.5 GiB OOMs at load, 13.0 GiB OOMs on the first request.
  The drafter costs 5.2 GiB; 7 lanes at 103k need 721k KV tokens and MTP leaves 463k. See that controller's README.
- Thinking-effort ladder on all 25 at 132 min: medium 8.97 / 8.31, cv5 high 13.70 / 13.52, LA-CR high 10.85 / 15.14,
  against LA-CR xhigh 18.01 / 19.24. Every reduction loses.
