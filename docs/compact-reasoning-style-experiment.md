<!--
Author: Claude Opus 5 (Bubba sub-agent, label arc3-style-experiment)
Date: 17-September-2026
PURPOSE: A/B experiment on gx10-a108 testing whether forcing a compact, Astra-shaped
reasoning format buys more environment ACTIONS out of the same wall clock for
Qwen3.8-27B-NVFP4 on the 25 public ARC-3 duck games. Records the code change
(env-flag gated), the launch, the measurement method, the paired per-game results,
and an explicit list of what was NOT verified.
SRP/DRY check: Pass - new experiment, no existing write-up covers it. Reuses the
baseline run's own aggregate.py field definitions rather than inventing metrics.
-->

# ARC-3 compact-reasoning A/B on a108 (17-Sep-2026)

**Status:** COMPLETE. Run finished 2026-09-17 14:15 ET.

**One-line verdict:** the compact format bought **+43% more environment actions at the
same wall clock and the same token spend** (tokens/action -32%, 19 of 25 games improved) —
but the apparent score gain rests entirely on one game, so **better play is not shown**.

## 1. Hypothesis

Measured over the 25-game baseline, this model's reasoning blocks average ~5,380
characters and 88.5% of them contain "wait"/"hmm"/"actually". Every game terminates
`gave_up` on the per-game runtime clock, not on losing, and the runs use a small
fraction of the available action budget. Tokens-per-action is therefore the binding
constraint, and it is attackable in the prompt at zero GPU cost.

**Claim under test:** instructing the model to emit terse, Astra-shaped reasoning
blocks raises the number of environment actions taken within the same wall clock.

**Win condition is levels cleared, not actions.** More actions at worse per-action
quality is a loss, and is reported as the headline if that is what happened.

## 2. What was changed (code)

Branch/PR: `sonpham-org/arc-3` (see §8).

The experiment arm is gated behind a single env var so the control path stays
reachable and the A/B is switchable without a second checkout. This mirrors the
existing `inference/agent/frame_mode.py` / `ARC3_FRAME_MODE` precedent in the repo.

- **New** `inference/agent/reasoning_style.py` - `ARC3_REASONING_STYLE`,
  `compact` = treatment, unset/anything-else = baseline.
- `inference/agent/prompts.py` - appended `COMPACT_REASONING_ADDENDUM` (system prompt)
  and `COMPACT_REASONING_TURN_REMINDER` (per-turn).
- `inference/agent/tool_agent.py` - 3 lines of injection at 2 sites:
  `_build_system_prompt` (addendum) and `_build_user_prompt` (per-turn reminder,
  appended last so it is the freshest instruction in the turn). The retry-coaching
  path was deliberately left untouched - it is a rare recovery path and verbosity
  is not its failure mode.

The instruction text requires: blocks under 400 chars, compact notation not prose,
no `wait`/`hmm`/`actually`/`let me reconsider`, each conclusion stated once, analysis
pushed into the `python` tool call, and gives the Astra example verbatim as the
required shape.

### Control arm proven untouched

`_build_system_prompt()` was rendered under both arms and compared:

- baseline arm: 12,359 chars; compact arm: 13,212 chars; delta = **+853 chars, append-only**
- an unrecognized flag value (`BASELINE`) renders **byte-identical** to the baseline arm
- the baseline-arm system prompt appears **verbatim in the 15-Sep baseline run's own
  prompt log**, and the string `Reasoning style (MANDATORY)` is absent from that log

That last check is the important one: it proves the control arm reproduces the exact
prompt that produced the comparison data.

## 3. IMPORTANT - the brief's baseline numbers belong to a different run

The task brief asked to compare against run `20260915_230835_qwen38-27b-baseline-25g`
p0, quoting "sum 53.03, 16 levels cleared, 12 of 25 games scoring, 973 env actions".

Those figures are not all from that run. Read from the run artifacts:

| source | score sum | scoring games | levels | actions | clock |
|---|---|---|---|---|---|
| `20260915_230835_..._baseline-25g` (**named in brief**) | **38.79** | **11** | **12** | **973** | 90 min/game, conc 7, 1 pass |
| `20260916_102724_..._massdata-25g-4p` **pass 0** | **53.03** | **12** | **16** | 1,182 | 230 min/game, conc 25, 4 passes |

`38.79 / 11 / 12` is confirmed by two independent artifacts that agree to rounding:
the harness's own `evaluation.json` (38.79) and the baseline report's
`artifacts/FINAL_baseline_results.json` (38.78). The brief's `973 actions` matches the
baseline run; its `53.03 / 16 / 12` matches massdata pass 0.

**Comparator used: the named baseline run, 38.79 / 11 / 12 / 973.** Massdata p0 ran a
2.6x longer per-game clock at 3.6x the concurrency, so comparing a 90-minute run against
it would violate the brief's own matched-clock requirement.

## 4. Run configuration (matched)

Launched 2026-09-17 08:15:54 ET, run dir
`~/GitHub/arc-3/ARC3-Inference/runs/20260917_081554_qwen38-27b-compact-25g`.

```
cd ~/GitHub/arc-3/ARC3-Inference
export ARC3_REASONING_STYLE=compact
make interactive CONFIG_PATH=configs/a108.qwen38.baseline.json \
  AGENT=duck-harness KAGGLE_DUCK_PUBLIC_HARNESS=true \
  RUN_NAME=qwen38-27b-compact-25g GAME= GAME_TAGS= EXCLUDE_GAME_TAGS=
```

`--kaggle-duck-public-harness` self-selects the 25 official duck games and refuses to be
combined with `--game`/`--include-tags`; that is how the baseline got its game set, so
the set is pinned by construction rather than by re-resolving tags.

**Config parity is proven, not assumed:** the new run's `run_config.json` diffed against
the baseline's is identical in every field except `generated_at` and the two kernel-slug
strings derived from the run name. Same 25 games in the same order, 90 min/game,
concurrency 7, 1 pass, temperature 1.0, same vLLM server.

**Treatment injection confirmed live:** the new run's prompt logs contain
`Reasoning style (MANDATORY)` (system) and `Reasoning style: keep your reasoning block`
(per-turn).

## 5. Measurement method

`~/arc3-style-20260917/style_analyze.py`, run identically over both run dirs.

- **reasoning text**: the `reasoning` field of each `response_message` in
  `<game>_p0_requests.jsonl` - the server's own output, not a reconstruction.
  Verified complete: 425 responses in the jsonl vs 425 `analyzer request end` lines
  in the baseline run log. Nothing is sampled or truncated.
- **reasoning tokens**: exact, via the `Qwen3.8-27B-NVFP4` tokenizer.
- **generated tokens**: summed server `usage.completion_tokens`, same as `aggregate.py`.
- **actions**: `sum(benchmark.json actions_per_level)`, same as `aggregate.py`.
- **levels / score**: `evaluation.json` per game (`levels_completed`, `score`).
- **self-talk**: regex `\b(wait|hmm+|actually)\b`, case-insensitive, per block.

**Parser validated against the baseline's published numbers before use:** it reproduces
973 actions, 5,379.9 mean reasoning chars (report: ~5,300), and 88.47% self-talk
(report: 88%). A parser that could not reproduce the known numbers would not be trusted
on fresh data.

## 6. Results

### 6.1 Wave 1 interim (7 of 25 games complete, recorded 09:58 ET)

Recorded for durability while the run continued. Superseded by the final table below
if one is present.

```
EXCLUDED, still in flight (7): ['ar25-0c556536', 'ka59-38d34dbb', 'm0r0-492f87ba', 'sc25-635fd71a', 'sp80-589a99af', 'tu93-0768757b', 'vc33-5430563c']
paired games: 7   UNPAIRED (excluded): ['cd82-fb555c5d', 'dc22-fdcac232', 'ft09-0d8bbf25', 'g50t-5849a774', 'ls20-9607627b', 're86-8af5384d', 's5i5-18d95033', 'sb26-7fbdac44', 'sk48-d8078629', 'su15-1944f8ab', 'tr87-cd924810']

GAME             RSN_CHARS b>c          SELFTALK b>c     ACTIONS b>c      TOK/ACT b>c        LEVELS b>c   SCORE b>c       
bp35-0a0ad940    4795 > 2462            95% > 74%        22 > 58          1694 > 551         0 > 0        0.00 > 0.00     
cn04-2fe56bfb    4871 > 1813            83% > 42%        20 > 39          1148 > 755         1 > 1        4.76 > 4.76     
lf52-271a04aa    4289 > 2358            89% > 80%        13 > 27          2468 > 1199        0 > 1        0.00 > 1.82     
lp85-305b61c3    7480 > 5863            86% > 93%        8 > 13           2586 > 2421        1 > 1        2.78 > 2.78     
r11l-495a7899    7351 > 2173            91% > 80%        7 > 57           4310 > 561         1 > 0        4.76 > 0.00     
tn36-ef4dde99    4101 > 3503            96% > 96%        65 > 41          585 > 779          0 > 0        0.00 > 0.00     
wa30-ee6fef47    7682 > 3482            93% > 80%        30 > 51          1254 > 518         0 > 1        0.00 > 2.22     

  levels cleared: compact better  2   unchanged  4   compact worse  1
           score: compact better  2   unchanged  4   compact worse  1
   actions taken: compact better  6   unchanged  0   compact worse  1

AGGREGATES over the 7 paired games only (both columns, same games):
METRIC                               BASELINE        COMPACT        DELTA
reasoning_chars_mean                     5341           2734        -2606
reasoning_tokens_mean                    1718            847         -872
selftalk_frac_pooled                   0.9189         0.7462      -0.1727
content_chars_mean                         80            137          +58
toolarg_chars_mean                        620            546          -74
output_chars_mean                        6040           3418        -2622
reasoning_blocks                          111            197          +86
llm_responses                             111            197          +86
total_actions                             165            286         +121
tokens_per_action_overall                1326            754         -572
total_generated_tokens                 218792         215637        -3155
levels_cleared                              3              4           +1
scoring_games                               3              4           +1
score_sum                               12.30          11.58        -0.72
```

### 6.2 Final — all 25 games, paired

Run finished 14:15 ET (5 h 59 m wall clock, vs the baseline's 6 h 00 m). All 25 games
terminal, all 25 paired. Harness overall score 2.3698.

```
paired games: 25

GAME             RSN_CHARS b>c          SELFTALK b>c     ACTIONS b>c      TOK/ACT b>c        LEVELS b>c   SCORE b>c       
ar25-0c556536    5075 > 3894            84% > 91%        34 > 55          1096 > 635         1 > 1        2.78 > 1.61     
bp35-0a0ad940    4795 > 2462            95% > 74%        22 > 58          1694 > 551         0 > 0        0.00 > 0.00     
cd82-fb555c5d    7442 > 5938            85% > 94%        23 > 29          1410 > 1137        0 > 0        0.00 > 0.00     
cn04-2fe56bfb    4871 > 1813            83% > 42%        20 > 39          1148 > 755         1 > 1        4.76 > 4.76     
dc22-fdcac232    4718 > 3948            86% > 83%        20 > 83          1862 > 419         0 > 0        0.00 > 0.00     
ft09-0d8bbf25    6981 > 4084            82% > 91%        28 > 32          988 > 1090         0 > 1        0.00 > 4.76     
g50t-5849a774    4774 > 4726            87% > 88%        3 > 19           8773 > 1560        0 > 0        0.00 > 0.00     
ka59-38d34dbb    3653 > 3442            85% > 89%        49 > 33          731 > 1024         0 > 1        0.00 > 2.57     
lf52-271a04aa    4289 > 2358            89% > 80%        13 > 27          2468 > 1199        0 > 1        0.00 > 1.82     
lp85-305b61c3    7480 > 5863            86% > 93%        8 > 13           2586 > 2421        1 > 1        2.78 > 2.78     
ls20-9607627b    6237 > 1721            75% > 83%        42 > 115         912 > 298          1 > 1        0.98 > 3.57     
m0r0-492f87ba    6068 > 3334            94% > 79%        137 > 42         274 > 819          0 > 1        0.00 > 3.31     
r11l-495a7899    7351 > 2173            91% > 80%        7 > 57           4310 > 561         1 > 0        4.76 > 0.00     
re86-8af5384d    4378 > 5102            86% > 92%        30 > 36          1252 > 694         1 > 1        2.23 > 1.72     
s5i5-18d95033    6141 > 691             95% > 20%        29 > 56          1450 > 645         1 > 0        1.93 > 0.00     
sb26-7fbdac44    4757 > 3676            81% > 84%        71 > 125         551 > 301          1 > 4        2.78 > 26.14    
sc25-635fd71a    6710 > 2672            91% > 94%        20 > 111         1372 > 306         0 > 0        0.00 > 0.00     
sk48-d8078629    5643 > 3708            95% > 85%        43 > 43          893 > 812          0 > 0        0.00 > 0.00     
sp80-589a99af    5508 > 5732            80% > 88%        40 > 77          784 > 440          1 > 0        4.76 > 0.00     
su15-1944f8ab    3828 > 2256            93% > 81%        53 > 139         790 > 265          1 > 1        2.03 > 2.22     
tn36-ef4dde99    4101 > 3503            96% > 96%        65 > 41          585 > 779          0 > 0        0.00 > 0.00     
tr87-cd924810    6550 > 4025            85% > 83%        54 > 17          606 > 2175         0 > 0        0.00 > 0.00     
tu93-0768757b    10925 > 3377           100% > 77%       102 > 54         296 > 608          0 > 0        0.00 > 0.00     
vc33-5430563c    4798 > 2403            89% > 92%        30 > 37          1267 > 895         2 > 1        8.99 > 1.75     
wa30-ee6fef47    7682 > 3482            93% > 80%        30 > 51          1254 > 518         0 > 1        0.00 > 2.22     

  levels cleared: compact better  6   unchanged 15   compact worse  4
           score: compact better  8   unchanged 11   compact worse  6
   actions taken: compact better 19   unchanged  1   compact worse  5

AGGREGATES over the 25 paired games only (both columns, same games):
METRIC                               BASELINE        COMPACT        DELTA
reasoning_chars_mean                     5380           2770        -2610
reasoning_chars_median                   4630           2245        -2385
reasoning_tokens_mean                    1710            855         -855
reasoning_tokens_median                  1443            654         -789
selftalk_frac_pooled                   0.8847         0.7160      -0.1687
content_chars_mean                        159             77          -82
toolarg_chars_mean                        667            509         -158
output_chars_mean                        6205           3356        -2849
reasoning_blocks                          425            771         +346
llm_responses                             425            771         +346
total_actions                             973           1389         +416
tokens_per_action_overall                 874            595         -278
total_generated_tokens                 849974         826617       -23357
levels_cleared                             12             16           +4
scoring_games                              11             13           +2
score_sum                               38.79          59.24       +20.46
```

(Medians are pooled over all reasoning blocks in each run, the same way the mean is,
so the two columns are the same statistic. All 25 games are paired, so these aggregates
and each run's own summary agree.)

### 6.3 Verdict

**The efficiency claim is confirmed, and it is broad.** At the same wall clock, on the
same server, for essentially the same token spend (826,617 vs 849,974 generated tokens,
-2.7%), the compact arm took **1,389 environment actions vs 973, +43%**. Tokens per
action fell **874 -> 595, -32%**. This is not carried by outliers: **19 of 25 games
improved** on tokens-per-action, median per-game ratio 0.56. The mechanism is visible
and is the one predicted: mean reasoning block 5,380 -> 2,770 chars, 1,710 -> 855 tokens.

**The mechanism is fragmentation, not reduction — and that matters.** Per response, all
three output channels shrank and none absorbed the others: reasoning 5,380 -> 2,770 chars,
assistant `content` 159 -> 77, tool-call arguments 667 -> 509, total output per response
6,205 -> 3,356 (-46%). So the verbosity did **not** relocate into the code argument; that
check passed.

But in aggregate nothing was saved. Total output chars are flat (2.64M -> 2.59M), as are
generated tokens (849,974 -> 826,617, -2.7%), because responses rose 425 -> 771 (+81%).
The model spent the **same budget across 81% more turns**. That is precisely why
tokens-per-action improved while total spend stayed pinned, and it is the honest
description of what the prompt bought: not cheaper thinking, but thinking chopped into
more, smaller units, each of which gets to act.

**The quality claim is NOT established. This is the headline caveat.** The +20.46 score
gain is one game:

| | score | levels | actions |
|---|---|---|---|
| all 25 games | 38.79 -> 59.24 (**+20.46**) | 12 -> 16 | 973 -> 1,389 |
| excluding `sb26-7fbdac44` | 36.01 -> 33.10 (**-2.91**) | 11 -> 12 | 902 -> 1,264 |

`sb26` alone moved +23.37 (2.78 -> 26.14, 1 level -> 4). Drop that single game and the
score delta goes **negative**. Levels go from +4 to +1. Per-game the record is mixed:
levels better in 6, unchanged in 15, worse in 4; score better in 8, unchanged in 11,
worse in 6. Four games lost ground on levels: `r11l`, `s5i5` and `sp80` each lost the
single level they had cleared in the baseline, and `vc33` dropped 2 -> 1.

So: **more actions per unit clock, clearly. Better play, not shown.** With n=25, one
pass, and temperature 1.0, this data cannot separate "compact reasoning helps solving"
from "one game got lucky."

**The format only half took.** Length roughly halved, but:

- the instruction said blocks under 400 chars; **1 of 25 games** met that at its median.
  Per-game median reasoning length ranged 97 to 6,592 chars, overall median 3,111.
- the ban on `wait`/`hmm`/`actually` was largely **ignored**: 88.5% -> 71.6% pooled, and
  per game it is a coin flip — **13 of 25 improved, 12 got worse**. Several games went up
  (`ar25` 84% -> 91%, `cd82` 85% -> 94%, `s5i5` is the one real success at 95% -> 20%).

That the efficiency win is this large while compliance is this partial is the interesting
part: the headroom found here is a fraction of what full compliance would give.

**Hypothesis for the next ablation, not a finding (n=3 per side):** the three games with
the highest baseline action counts (`m0r0` 137, `tu93` 102, `tn36` 65) all regressed under
compact, while the largest gains came from games that were action-starved at baseline
(`r11l` 7 -> 57, `g50t` 3 -> 19, `sc25` 20 -> 111). If compact reasoning rescues games stuck
deliberating and hurts games that were already acting, that is testable and would change
how the flag should be applied.

## 7. What was NOT verified

Stated plainly, because several of these bound the conclusion:

1. **No repeat runs.** One pass, temperature 1.0, 25 games, each arm run once. Nothing
   here separates effect from sampling noise, and no significance test was run or is
   meaningful on n=1 per cell. **Do not cite this as a trend.**
2. **The score result is one game.** See 6.3. `sb26-7fbdac44` accounts for more than the
   entire aggregate gain. It was not investigated — I did not read its transcript to see
   whether the compact run found a genuine strategy or got a favourable roll.
3. **Arms ran at different times of day** (baseline 23:08-05:08, compact 08:15-14:15).
   Same box, same idle server, no competing GPU process observed at launch, but I did not
   monitor for contention throughout the 6 hours, and I did not check thermal throttling.
4. **The two arms were not run against identical code.** They ran against the same a108
   snapshot, which is ~416 diff lines behind `sonpham-org/arc-3` main. The PR is a port of
   the change onto current main and its behaviour there is **unmeasured**.
5. **No ablation of the two injection sites.** System-prompt addendum and per-turn
   reminder were introduced together; their individual contributions are unknown.
6. **No intermediate format arm.** Only baseline vs this one instruction text. Nothing
   tells us which clause did the work, or whether a milder or stricter version does better.
7. **Action quality was not inspected.** "More actions" is counted, not judged. I did not
   check whether the extra actions are informative probes or flailing.
8. **`levels_completed` semantics** are taken from `evaluation.json`/`benchmark.json` as
   authoritative. The baseline report warns that the event-stream `score` field is a
   truncated weighted score, not a level count; I avoided that field, but I did not
   independently re-derive level counts from the event streams.
9. **The brief's quoted baseline (53.03/16/12) was not used** — see section 3. If the
   intended comparator really was massdata pass-0, this whole comparison is against the
   wrong arm, and the clock would not match either.
10. **Tokenizer token counts** for reasoning blocks come from the local
    `Qwen3.8-27B-NVFP4` tokenizer without the chat template; they measure block content,
    not billed tokens. Billed figures use the server's own `usage`.

## 8. Code delivery

- **PR:** https://github.com/sonpham-org/arc-3/pull/36 (branch
  `feat/compact-reasoning-style`, base `main`). Contains exactly 3 files, 56 insertions,
  0 deletions. An earlier push of this branch accidentally carried an unrelated unmerged
  distill/LoRA commit; it was rebased onto `origin/main` and force-pushed, and the PR now
  shows only the 3 intended files.
- The local `~/GitHub/arc-3` checkout was restored to exactly the state I found it in:
  branch `feat/sft-exclude-games`, with its uncommitted `distill/train_lora.py` edits
  intact (md5 `de70ad9c1d8c43e9324381a6d47034e5`, verified identical before and after my
  branch work). My temporary worktree and local branches were removed.
  **Note:** by 14:40 another agent had moved that checkout on — it is now on
  `feat/scorecard-and-replay-tooling-from-workspace` and `feat/sft-exclude-games` no
  longer exists locally. That is not my change and does not affect PR #36, which lives on
  the remote branch `feat/compact-reasoning-style`.

### a108 file state (no git on that box, so checksums are the record)

| file | pre-change md5 | post-change md5 |
|---|---|---|
| `inference/agent/tool_agent.py` | `e3a943a0e099b094f84b7f13118dea06` | `91f3439c41877c7f1180923c6422ce26` |
| `inference/agent/prompts.py` | `831045bfaf9937ed5dba97f3cb453277` | `c119604b4ad8d338119d17ba79ce522a` |
| `inference/agent/reasoning_style.py` | (new file) | `76899e0072c5c40f406d57c700245cdb` |

Pre-change originals are preserved on a108 as
`tool_agent.py.bak-pre-compact-20260917` and `prompts.py.bak-pre-compact-20260917`.
**a108 is left with the patched files in place**, which is safe: with
`ARC3_REASONING_STYLE` unset the system prompt is byte-identical to the original, so any
future run there reproduces baseline behaviour unless the flag is set deliberately.

### Artifacts

- compact run dir: `~/GitHub/arc-3/ARC3-Inference/runs/20260917_081554_qwen38-27b-compact-25g`
- workdir: `~/arc3-style-20260917/` — `style_analyze.py`, `style_compare.py`,
  `artifacts/baseline_table.json`, `artifacts/compact_table.json`, `logs/compact25.log`

## 9. Machine state on exit

- **vLLM PID 765547 is ALIVE**, uptime 1 d 16 h 58 m (unbroken since the 15-Sep baseline),
  `/health` returns 200. It was never restarted and no server flag was changed, so the
  baseline comparability the `_pin` block protects is intact.
- **a424 (100.106.31.61) was never contacted.** Every remote command in this task went to
  `son@100.118.4.20` (a108). No ssh, ping, or API call was issued to a424 at any point.

