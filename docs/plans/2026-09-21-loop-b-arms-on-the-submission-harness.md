<!--
Author: Claude Fable 5.1 (Dr. Fable), for Son Pham
Date: 21-September-2026
PURPOSE: Handoff spec for two prompt-wording arms on the exact harness behind the 7.36 Kaggle
submission (compaction v5 + clean-return): arm LB adds the one-line Loop B sentence; arm LAB adds
the Loop A deletions and the Loop B sentence. Two GCP runs each, 25 games, 132 gameplay minutes,
scored paired per game against the two existing compaction-v5-clean-return runs. Written for the
Codex task that owns the GCP controllers; this repo does not launch runs.
SRP/DRY check: Pass. The Loop A/B definitions are cited to the 11-Sep arm folder, the hard-seven
ranking to the 21-Sep session that produced it, and the measurement rules to HARNESS-NOTES §1.
Nothing here restates a mechanic or a result that lives elsewhere.
-->

# Loop B and Loop A+B on the submission harness — two runs each

> **CORRECTION 21-Sep (evening), verified against the Kaggle API (`competition_submissions`, field `url`):**
> the 7.36 submission (ref 56408939, 21-Sep 00:16 UTC) came from kernel
> `sonphamorg/arc3-flash-next-clean-return-swap50`, script version **351076929** — the
> **clean-return + search/scorer-removal + 50% swap** candidate (`kaggle-clean-return-swap50-20260919`),
> **not** compaction v5. `arc3-flash-next-compact-v5-clean-return` (351177460) has never been submitted.
> The same clean-return kernel version scored **5.54** the day before. Everything below that says
> "the 7.36 harness" therefore describes the **compaction-v5-clean-return** base, which is what the
> LB / LAB / LA arms were actually built and run on (21-Sep); their control pair
> (`compaction-v5-clean-return-{a,b}132`, 14.56 / 10.77) is the correct control for those arms, but
> the arms are one mechanism away from the shipped notebook. The shipped notebook's local 132-minute
> controls are the clean-return pair (`clean-return-{a,b}132`: 13.58 / 15.65 overall, 2.76 / 4.27 hard-seven).


**Requested by:** Son, 21-Sep-2026 ("Add Loop B and do 2 x GCP. Add Loop A + B and do 2 x GCP").
**Owner of execution:** the Codex task (`okay-bro-let-s-do-the`), which holds the W7 Spot GCP
controllers and the frozen candidate.
**Evidence base:** the 599-run hard-seven ranking built on 21-Sep from the run-history census,
the ten-day review, and 48 fresh GCS benchmark files (scratchpad `hard7-ranking.md`).

## 0. Why these two arms

Across 347 completed 25-game / 132-minute runs, the best hard-seven score is the single Loop B
retry, `g4run-loopbretry132-w7-20260912-031e516522`: **6.69** on `bp35, g50t, lf52, ls20, sk48,
tn36, wa30`, against a population mean of 1.91 and sd 0.95. It is n=1, its overall score (12.37)
was below median, and its sibling arm C with differently phrased wording scored 1.74. So the
reading is a hypothesis, not a result. It is also the cheapest untested change on the board: one
sentence, no throughput cost, no new mechanism.

The shipped 7.36 prompt still carries every sentence Loop A deleted (verified 21-Sep against
`kaggle-compact-v5-clean-return-20260919/candidate/EXPECTED_PROMPTS.json`). Loop A on its own was
flat (4 runs, hard-seven 2.34, overall 13.15), so the second arm tests whether B needs A's
deletions to work or stands alone.

## 1. Base: the exact 7.36 candidate, unchanged

Everything below is frozen and byte-identical to
`kaggle-compact-v5-clean-return-20260919/candidate` (script version 351177460), except the prompt
edits in §2. Do not carry any other pending change (no ACTION7 registration, no obs API, no RESET
or UNDO exposure, no symbolic, no cap change).

| setting | value |
|---|---|
| model / serving | `RadixArk/Qwen3.8-Flash-Next-NVFP4`, 7 lanes, context 102985 / input 94281, GCP native FP8 PLE |
| `ARC3_ACTION_CAP` / `ARC3_ACTION_CAP_MODE` | `14` / `return` |
| `ARC3_CONTEXT_COMPACTION` / `ARC3_HALF_CONTEXT_SWAP` | `1` / `1` (compaction v5, host-owned notebook at the swap) |
| `ARC3_PROMPT_ABLATE_SEARCH` | `1` |
| `ARC3_BUDGET_GUIDANCE` | `time_only` |
| games / clock | all 25, `ARC3_MAX_RUNTIME_S_PER_GAME=2061`, `ARC3_MAX_RUN_RUNTIME_MINUTES=132` |
| memory, curator, replay, execution, symbolic, prediction, obs | all off, as shipped |

**Control:** the two completed runs of this exact base,
`g4run-compaction-v5-clean-return-a132-w7-20260919-693e7fd43c` (14.56 overall, 4.93 hard-seven)
and `g4run-compaction-v5-clean-return-b132-w7-20260919-0e59b2567b` (10.77, 3.53). No new control
run is requested. If the base candidate changes for any reason before launch, the control is
invalid and two control runs must be added.

## 2. The two arms

### Arm LB — Loop B sentence only

One edit to the **system** prompt: append the block below after the last "Tool session rules"
bullet, separated by one blank line. Nothing else changes.

```
Loop guidance:
Inspect the latest state, update your understanding, choose and execute a valid action or short sequence, then evaluate the result.
```

This is the sentence from `D:/codex-work/loop-variants132-20260911/arms/b132/prompt.diff`,
verbatim.

### Arm LAB — Loop A deletions + Loop B sentence

Arm LB's addition, plus the Loop A deletions, applied to the shipped prompt text. Every deletion
below is quoted from the shipped `EXPECTED_PROMPTS.json` so the diff can be asserted byte-exact.

**system, Game overview — replace**

```
- You are called repeatedly over the course of a run. Treat each turn as one observe-plan-act cycle: re-understand the current state from the newest frame, update your working world model in Python, choose the next best action or short sequence against the goal as currently understood, execute it, and expect to re-evaluate on the next turn from the updated state.
```
with
```
- You are called repeatedly over the course of a run.
```

**system, Python tool guidance — delete these two bullets entirely**

```
- Keep a compact world model: entities, action effects, likely goal, uncertainties, and shortest reliable plan. Probe only when evidence can distinguish hypotheses.
- Default loop: summarize objects, infer the desired change, choose a probe or plan, execute it with `action(...)`, then check `last_action_result` and the refreshed board. Match objects using color, shape hash, overlap, proximity, area, and edge contact.
```
and re-add the two factual fragments they carried as their own bullets, so no capability
description is lost:
```
- Probe only when evidence can distinguish hypotheses.
- Match objects using color, shape hash, overlap, proximity, area, and edge contact.
```

**system, Python tool guidance — replace**

```
- After every action, distinguish gameplay change from a timer/progress-bar-only change. Stop immediately on `level_completed`, `done`, `game_over`, or `run_complete` and re-ground next turn.
```
with
```
- Stop immediately on `level_completed`, `done`, `game_over`, or `run_complete` and re-ground next turn.
```

**system, Python tool guidance — replace**

```
- Use `print(...)` or `result` for short decision-oriented output. Call `action(...)` inside Python; batch a reliable sequence or call it repeatedly in a loop, checking refreshed state after each call.
```
with
```
- Use `print(...)` or `result` for short decision-oriented output. Call `action(...)` inside Python.
```

**first_user — delete the line**

```
Ground on `current_frame` in Python before acting.
```

**retry — replace the whole surface** with

```
You have not acted yet. Use the `python` tool to access available observations or execute valid actions via `action(actions)`. When calling `python`, emit exactly the tool-call format shown elsewhere in this prompt for this model. Use only that format; do not add markdown fences, prose wrappers, or alternate tool-call syntax. Do not quote or place tool-call markup inside explanatory text; when you decide to call the tool, emit the tool call itself.
```

The **tool** description and the **user** turn are unchanged. (The 11-Sep arm also trimmed one
clause in the tool description; the shipped tool text has already lost the clause that trim
targeted, so there is nothing to apply.)

The original Loop A also flipped `ARC3_INPUT_ACCESS=1`. **Do not.** The obs API stays off; this
spec tests wording only.

## 3. Runs

| arm | runs | run-id stem | budget |
|---|---:|---|---|
| LB | 2 | `g4run-loopb-v5-clean-return132-w7-<date>-<hash>` | 132 gameplay minutes, 25 games |
| LAB | 2 | `g4run-loopab-v5-clean-return132-w7-<date>-<hash>` | 132 gameplay minutes, 25 games |

Four Spot VMs, one scored attempt each, no automatic replacement, no Kaggle action. Same
hyperdisk lifecycle rules as the 19-Sep controllers. Expected prompts rendered by the real prompt
probe and re-attested on the VM; the runtime probe must assert the `Loop guidance:` block is
present and, for LAB, that the deleted strings are absent from every rendered surface.

If the seven-game × 4-pass mode is preferred for cost, set `ARC3_GAME_SUBSET` to the seven and
`n_passes=4`; then the control must also be re-run as a seven-game arm, because the two existing
25-game controls are not comparable to a subset run.

## 4. How to read it (pre-registered)

Per HARNESS-NOTES §1: no arm total is a result on its own.

1. **Primary:** for each arm, pair its two runs' per-game means against the two control runs'
   per-game means. Count games improved / same / worse using a 0.5-point threshold. Report
   `sb26`, `g50t` and `tn36` on their own lines; one level on either of the last two moves the
   hard-seven mean by 1.5.
2. **Hard-seven:** mean over `bp35, g50t, lf52, ls20, sk48, tn36, wa30`, and the summed levels
   cleared on those seven, per run. The control pair is 4.93 / 3.53 and 10 / 8 levels.
3. **Overall:** mean of 25 `final_score`s. Control pair 14.56 / 10.77.
4. **Efficiency proxies:** actions per game and generated tokens per action, from
   `benchmark.json`. These are lower-variance than score and are where a wording change shows
   first.
5. **Decision rule.** LB or LAB is worth a third and fourth run if both of its runs beat both
   controls on hard-seven levels **and** it is not worse on overall by more than 2 points. If LAB
   beats LB on the same rule, the deletions matter; if they tie, ship the sentence alone. If
   neither clears the rule, the 6.69 was a roll and Loop B is retired.

## 5. What this does not test

- Whether the sentence helps on the semi-private set. The local seven are a proxy for a failure
  shape (cannot start; clears level 1, never deepens), not for Kaggle's games.
- Cap 10 / 12 / 14 in `return` mode, and the per-game time reallocation policy. Both are separate
  arms and should not be folded into these four runs.
