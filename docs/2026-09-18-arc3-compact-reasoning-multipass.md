<!--
Author: Claude Opus 5 (Bubba sub-agent, label arc3-style-multipass)
Date: 18-September-2026
PURPOSE: Multi-pass repeat of the 17-Sep compact-reasoning A/B on gx10-a108. Records why a
single pass cannot measure this harness change, the pass budget and schedule actually used,
the per-pass guards, the analysis plan (per-arm spread, sb26-excluded delta, paired per-game
test), the results, and an explicit not-verified list.
SRP/DRY check: Pass -- docs/2026-09-17 covers the single-pass run and is cited, not repeated.
Measurement reuses ARC3-Inference/scripts/style_analyze.py unchanged; only the cross-run
aggregation (multipass_compare.py) is new.
-->

# ARC-3 compact reasoning: multi-pass A/B on a108 (18-Sep-2026)

**Status:** RUNNING. Driver launched 2026-09-18 11:34:33 ET, 4 passes, ETA ~12:00 ET 19-Sep.
Results land in §6; §1-§5 and §7 are fixed at launch.

## 1. Why this run exists

The 17-Sep single-pass A/B ([docs/2026-09-17-arc3-style-experiment.md](2026-09-17-arc3-style-experiment.md))
reported compact 59.24 vs baseline 38.79, +20.46. That delta is not trustworthy, for reasons
already established in that write-up:

- **One game carried it.** `sb26-7fbdac44` moved +23.37 on its own. Drop it and the delta is
  **-2.91**, and levels go from +4 to +1.
- **`sb26` is a jackpot game.** In the 4-pass massdata run it scored 2.78 at one level in four
  of five observed runs, then 27.78 at four levels in the fifth, with nothing changed.
- **Seed variance swamps the effect.** Four identical passes of the same config scored
  53.0 / 57.4 / 82.6 / 50.9 — sd ≈ 20.8% of the mean.

A single pass per arm therefore cannot measure a harness change of this size. This run's job
is to decide, with repeats, whether compact reasoning plays **better** or only **faster**.

Already established and not re-litigated here: the **efficiency** half is solid and paired —
+43% actions, -32% tokens/action, 19 of 25 games improved, median per-game ratio 0.56, driven
by fragmentation (responses 425 → 771, +81%, with aggregate output flat). **Format compliance
was partial**: 1 of 25 games met the <400-char instruction at its median, and the
wait/hmm/actually ban was essentially ignored (13 games better, 12 worse).

### 1.1 A result that falls out of re-analysing the old data

Running the new paired test over the 17-Sep run's own artifacts, *before any new pass*:

```
PAIRED per-game mean score, 25 games paired:
  mean per-game difference (compact - baseline): +0.818
  games compact better: 8   tied: 11   worse: 6
  two-sided sign-flip p = 0.5860  (200k permutations, seed 0)
  paired mean per-game LEVELS difference: +0.160, sign-flip p = 0.5181
```

So the headline +20.46 was **already non-significant** under a test that removes between-game
variance, on its own data. That is not a new measurement — it is the old measurement, analysed
paired instead of as two scalar sums.

## 2. Design

### 2.1 Pass budget: 3 per arm, 4 new passes, ~24 h

A 25-game pass at the pinned operating point takes 6 h 00 m (both existing runs ended at
exactly 6 h 00 m; all games terminate `gave_up` on the per-game clock). The budget question is
therefore how many 6 h slots to spend.

**Two existing runs are valid draws and are reused rather than re-run:**

| run | arm | clock | conc | passes | games |
|---|---|---|---|---|---|
| `20260915_230835_qwen38-27b-baseline-25g` | baseline | 90 min/game | 7 | 1 | 25 |
| `20260917_081554_qwen38-27b-compact-25g` | compact | 90 min/game | 7 | 1 | 25 |

Their `run_config.json` were re-diffed for this run (not taken on trust from the prior
write-up): **identical in every field except `generated_at` and the two kernel-slug strings
derived from the run name**, same 25 games in the same order. Both ran against vLLM PID
765547, whose 2 d 13 h uptime spans both. So n=3 per arm costs **4 new passes ≈ 24 h**, not 6.

**Rejected: n=2 per arm (1 new pass each, 12 h).** It produces a spread and essentially no
discriminating power. It is the fallback if the run must be cut short, and would be reported
as "cannot distinguish", not as an answer.

### 2.2 Rejected: running the two arms concurrently

Running both arms at once (7 lanes each, 14 total) would have halved wall clock and matched
time-of-day perfectly. It was rejected because **the contention bias correlates with the
treatment**: the compact arm's mechanism is +81% more requests, so under contention it pays
the queueing/TTFT tax ~81% more times per game. That systematically suppresses the treatment's
action count — the dependent variable. Two supporting reasons: a108 showed **8 GB available
with 7 GB already in swap**, so a second harness process tree risks host swap thrash on a
wall-clock-bound measurement; and 14 lanes is outside the swept operating point that
`_pin` in `configs/a108.qwen38.baseline.json` declares mandatory.

### 2.3 Schedule: arms alternate across time of day

Time-of-day was NOT-VERIFIED item #3 last time (baseline ran 23:08-05:08, compact 08:15-14:15).
Running new passes block-sequentially would re-confound it, so the driver alternates:

| pass | arm | slot (ET) |
|---|---|---|
| (reused) `20260915_230835` | baseline | 23:08-05:08, night |
| (reused) `20260917_081554` | compact | 08:15-14:15, day |
| P1 `qwen38-27b-mp-compact-p1` | compact | ~11:34-17:40, day |
| P2 `qwen38-27b-mp-baseline-p1` | baseline | ~17:40-23:45, evening |
| P3 `qwen38-27b-mp-compact-p2` | compact | ~23:45-05:50, night |
| P4 `qwen38-27b-mp-baseline-p2` | baseline | ~05:50-11:55, morning |

Each arm ends up with one night slot, one daytime slot and one intermediate slot. Residual
imbalance is reported in §6 from the recorded start/end times, not assumed away.

### 2.4 Operating point (unchanged, pinned)

`configs/a108.qwen38.baseline.json` verbatim: 90 min/game, `concurrent_jobs` 7, `n_passes` 1,
context 102 985, temp 1.0 / top_p 0.95 / top_k 20, thinking on, multimodal `current_grid`
upscale 4, environments `/home/son/flash-next-work/environment_files-11p44`, and
`--kaggle-duck-public-harness` self-selecting the 25 official duck games. The only difference
between arms is the env var `ARC3_REASONING_STYLE=compact`, which does not appear in
`run_config.json` at all — so "identical except `generated_at` + name-derived slugs" is the
correct parity claim, and the driver asserts it per pass.

Four separate one-pass runs were used rather than one `n_passes=3` run: each is self-contained
and resumable (a failure costs 6 h, not 18), each produces an artifact identical in shape to
the two reused runs, and it keeps the scheduling control §2.3 needs.

## 3. Per-pass guards

`ARC3-Inference/scripts/run_style_multipass.sh` records, for every pass, into
`~/arc3-multipass-20260918/guards/ledger.txt`:

1. **vLLM PID 765547 uptime and `/health` before and after** the pass. If the server dies
   mid-experiment the passes either side are not comparable and that must be visible, not
   discovered in the aggregate.
2. **The value of `ARC3_REASONING_STYLE`** as the pass launches.
3. **Treatment-marker count in the prompt logs**: games whose prompt log contains
   `Reasoning style (MANDATORY)`. Expect 25 for compact passes, 0 for baseline passes. A
   missing `export` in one of four launches is the single most likely way this run produces a
   confidently wrong number, so it is checked every pass, not once.
4. **`run_config.json` parity** against the reused compact pass, ignoring only `generated_at`
   and the two name-derived kernel slugs.

## 4. Analysis plan (fixed before results)

`ARC3-Inference/scripts/multipass_compare.py`, over `style_table.json` from
`style_analyze.py` (unchanged from 17-Sep, so both arms are measured by the same code path
that produced the published baseline numbers).

- **Every pass reported individually**, then per-arm mean, sample sd, min, max, CV.
- **Overlap test**: if the arms' per-pass ranges intersect on a metric, the arms are not
  distinguishable on it at this pass count, and that is what gets reported.
- **Delta computed twice: all 25 games, and excluding `sb26-7fbdac44`.** Mandatory — that one
  exclusion flipped the prior result's sign.
- **Paired per-game test** on per-game mean score across passes, 25 pairs. Between-game
  variance (scores span 0 to 26) drops out of a paired test entirely; this is where the power
  is. Significance by two-sided sign-flip randomisation, 200 000 permutations, seed 0, with
  the Phipson-Smyth +1 correction. Same test on levels.
- **Per-game per-pass score distribution**, which answers the sb26 question directly: is the
  jackpot *rate* higher under compact, or was it one roll? `2.78 / 2.78 / 26.14` under compact
  is a completely different finding from `26 / 26 / 26`.
- **Efficiency metrics per pass** (actions, tokens/action, responses, reasoning length,
  self-talk), so we learn whether the efficiency win — the half currently believed — is itself
  stable across seeds.

**The massdata run's 4 passes are NOT pooled into the baseline arm.** 230 min/game at
concurrency 25 is a different operating point. It is cited only as the sd estimate that
justifies the pass count.

### 4.1 Tool validated against known numbers before use

`multipass_compare.py` run over the two reused passes reproduces the 17-Sep published table
exactly: baseline 38.79 / 11 scoring / 12 levels / 973 actions / 873.6 tok-per-action / 425
responses, compact 59.24 / 13 / 16 / 1389 / 595.1 / 771, and excluding `sb26` the arms are
36.01 → 33.10 (**-2.91**) with actions 902 → 1264. A tool that could not reproduce the known
numbers would not be trusted on fresh data.

## 5. Code state on a108

a108 has no git checkout; the record is checksums. The three files are byte-identical to those
recorded on 17-Sep (`tool_agent.py` `91f3439c…`, `prompts.py` `c119604b…`,
`reasoning_style.py` `76899e00…`), and the pre-change originals remain as
`*.bak-pre-compact-20260917`. With `ARC3_REASONING_STYLE` unset the system prompt renders
byte-identical to the original — confirmed again for this run by the absence of
`Reasoning style (MANDATORY)` from all 25 prompt logs of the reused baseline pass, and its
presence in all 25 of the reused compact pass.

**The drift caveat has grown and is restated, not inherited.** The 17-Sep write-up put a108 at
~416 diff lines behind main. Re-measured today by diffing a108's `inference/` tree against
`origin/main` (commit `4d92a21f0`): **1 303 diff lines across 6 changed files, with
`common_themes.py` and `frame_mode.py` present on main and absent on a108.** So a108 has not
moved — main has. Behaviour of this change on current main remains **unmeasured**.

`reasoning_style.py` on `origin/main` is **byte-identical** to a108's copy: PR #36 merged
2026-09-18 09:01 ET, so the treatment code itself is the same on both sides. The surrounding
harness is not.

## 6. Results

*(pending — the driver writes here when the four passes land)*

## 7. What is NOT verified

1. **n=3 per arm is still small.** With per-pass sd ≈ 20% of the mean, the arm-mean comparison
   can only rule out large effects. The paired per-game test carries the power; the arm-sum
   comparison is reported for completeness and should not be read as the test.
2. **Behaviour on current main is unmeasured.** a108 is 1 303 diff lines from `origin/main`
   (§5). Only `reasoning_style.py` is known identical.
3. **Time of day is balanced, not controlled.** Each arm gets one night, one day and one
   intermediate slot; thermal and background-load differences within those slots are not
   measured. No thermal throttling check is run.
4. **The two reused passes ran 2-3 days before the new ones.** Same server process, same
   config, but wider elapsed time than within the new block.
5. **Action quality is counted, not judged.** "More actions" says nothing about whether the
   extra actions are informative probes or flailing. Unchanged from 17-Sep.
6. **No injection-site ablation and no intermediate format arm.** The system-prompt addendum
   and the per-turn reminder are still introduced together, and only one instruction text is
   tested.
7. **`levels_completed` is taken from `evaluation.json` as authoritative** and not re-derived
   from the event streams.
8. **Reasoning-block token counts** come from the local tokenizer without the chat template;
   they measure block content, not billed tokens. Billed figures use the server's `usage`.
9. **The sign-flip test assumes games are exchangeable under the null**, which is the standard
   paired assumption; it does not model within-game across-pass correlation beyond averaging.
10. **No check for competing GPU load throughout each 6 h pass** — only PID/health at the
    boundaries.
