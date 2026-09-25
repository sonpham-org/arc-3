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

## Results (both waves: 1,173 branches, 167 checkpoints, all 11 levels)

Wave 2 (8 VMs, 07:00 to 10:45 UTC) finished the remaining 478 branches. 1,135 of 1,173 prefixes replayed byte-equal;
the 38 non-exact ones are the checkpoints past a timeout-truncated snippet (excluded). Token calibration: 0.334
completion tokens per generated character on the 162 xhigh controls.

| effort | n | solved within 2x | action ratio (median, solved) | token ratio (median, solved) | tokens per branch |
|---|---|---|---|---|---|
| xhigh control | 162 | 72% | 1.00 | 1.00 | 45.2k |
| high | 323 | 68% | 1.00 | 1.01 | 42.6k |
| medium | 323 | 71% | 1.00 | 1.00 | 39.9k |
| low | 327 | 67% | 1.00 | 0.91 | 39.7k |

By position in the level (first / middle / last third of its turns): solved, median action ratio, tokens per branch.

| effort | early | middle | late |
|---|---|---|---|
| xhigh | 71%, 1.00, 71.4k | 66%, 1.00, 38.6k | 80%, 1.00, 10.5k |
| high | 65%, 1.00, 67.1k | 62%, 1.00, 37.0k | 82%, 1.00, 10.0k |
| medium | 66%, 0.98, 65.5k | 74%, 1.00, 32.1k | 75%, 1.00, 9.0k |
| low | 56%, 1.10, 66.5k | 66%, 1.00, 30.8k | 86%, 1.00, 8.0k |

Per level (solve rate by effort; median action ratio of solved branches):

| game | level | turns | recorded actions | human | xhigh | high | medium | low |
|---|---|---|---|---|---|---|---|---|
| bp35 | 1 | 16 | 41 | 21 | 17/17 (0.92) | 27/34 (0.94) | 33/34 (0.87) | 27/34 (1.00) |
| g50t | 1 | 18 | 37 | 78 | 11/18 (1.00) | 25/36 (1.24) | 23/36 (1.00) | 23/36 (1.05) |
| g50t | 2 | 10 | 31 | 175 | 10/10 (1.00) | 19/20 (1.00) | 20/20 (1.00) | 20/20 (1.00) |
| g50t | 3 | 40 | 195 | 179 | 8/11 (1.25) | 11/21 (1.05) | 14/21 (1.05) | 15/22 (1.08) |
| lf52 | 1 | 11 | 13 | 32 | 9/12 (1.14) | 18/22 (1.00) | 19/22 (1.00) | 14/22 (1.00) |
| lf52 | 2 | 151 | 707 | 81 | 7/7 (0.59) | 7/14 (0.37) | 8/13 (0.19) | 9/14 (0.37) |
| ls20 | 1 | 10 | 31 | 22 | 6/10 (0.81) | 14/20 (1.00) | 14/20 (0.90) | 15/20 (1.00) |
| ls20 | 2 | 26 | 231 | 123 | 14/25 (0.99) | 34/52 (1.00) | 33/52 (1.00) | 32/51 (1.00) |
| sk48 | 1 | 35 | 133 | 61 | 5/16 (1.05) | 11/32 (0.88) | 13/32 (0.88) | 13/33 (0.98) |
| wa30 | 1 | 23 | 50 | 71 | 23/23 (1.03) | 43/46 (1.00) | 40/45 (1.00) | 37/46 (1.00) |
| wa30 | 2 | 35 | 281 | 119 | 6/13 (0.47) | 11/26 (0.69) | 12/28 (0.98) | 14/29 (0.90) |

Charts: `docs/static/branch-replay/branch_ratio_final.png` (ratio vs checkpoint position, per effort) and
`branch_ratio_final_per_level.png`. Raw tables: `gcp/controllers/branch-replay/RESULTS_final.md`.

## Reading

1. **The recording is 72% reproducible.** A fresh xhigh sample from the same state clears the level within the 2x caps
   at 72% of checkpoints (early 71%, middle 66%, late 80%). sk48 L1 is 5 of 16. That is the noise floor for every
   comparison below, and nothing between the effort settings is bigger than it.
2. **high, medium and low all match xhigh on actions once the level is under way.** Median action ratio is 1.00 for
   every setting in the middle and last thirds; the recording's own remaining path is reproduced. Solve rates 68%,
   71%, 67% against 72%. The only place a setting loses is low in the first third of a level (56% solved, 10% more
   actions): brief thinking hurts while the mechanics are still being discovered, not afterwards.
3. **Tokens move little with the knob.** Per-branch tokens: xhigh 45.2k, high 42.6k, medium 39.9k, low 39.7k, i.e. at most
   12% overall and 24% in the last third. The Qwen3.8 template implements medium as "no thinking sentence" and low as
   "keep it brief"; the model's thinking length barely responds. The sample-to-sample spread at one checkpoint is far
   larger. This is the main obstacle for the routing-LoRA idea: there is little distinct behaviour to route between.
4. **Where cheaper branches win big, the recording had lost.** lf52 L2 (707 recorded actions vs a human 81) is beaten
   by every effort at 0.2 to 0.6 of the recorded actions, and by the xhigh control at 0.59; wa30 L2 likewise. g50t L1 and
   L3 go the other way for every setting including the control. Efficiency is a property of the sample, not the setting.
5. **The oracle switch value (39% of remaining-level tokens at 127 of 164 checkpoints) is best-of-n, not routing.**
   Resampling at xhigh yields the same kind of saving.

What survives as a usable rule: after the first third of a level, dropping to medium (or even low) costs nothing in
actions or solve rate and saves 15 to 25% of the tokens for that remainder; in the first third, keep xhigh. On this
recording the whole-level saving of such a rule is about 10 to 12%, inside one run's sampling variance. Worth encoding
as a fixed schedule rather than a learned router.

## Sibling results from the same night

- Act mode hard-7 replicate #2 `g4run-modes-hard7-act-132-w7-20260925-43772c5cb5` = 6.42 / 14 levels against #1's
  10.06: act sits with solver (9.13 / 4.73), LA-CR (9.04 / 4.55) and CR (8.43 / 4.75).
- MTP with a forced KV pool (`lacr-serving-variants` mtp3): 13.5 GiB OOMs at load, 13.0 GiB OOMs on the first request.
  The drafter costs 5.2 GiB; 7 lanes at 103k need 721k KV tokens and MTP leaves 463k. See that controller's README.
- Thinking-effort ladder on all 25 at 132 min: medium 8.97 / 8.31, cv5 high 13.70 / 13.52, LA-CR high 10.85 / 15.14,
  against LA-CR xhigh 18.01 / 19.24. Every reduction loses.
