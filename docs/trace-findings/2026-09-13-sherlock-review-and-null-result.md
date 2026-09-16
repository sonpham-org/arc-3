<!--
Author: Claude Opus 5 (Bubba)
Date: 13-September-2026
PURPOSE: Record Sherlock's adversarial review of arms D/E/F before any of them spent a
GPU slot, the three fixes applied, a fourth defect found while applying them (Kaggle
derives kernel slugs from the title, so the queue was tracking a kernel that does not
exist), and the job3-vs-job5 null check, which did not come back null.
SRP/DRY check: Pass - the arm definitions live in build_bundles.py / build_notebooks.py
and are not restated here; this records the review and the numbers only.
-->

# Sherlock's adversarial pass, the fixes, and the null check

## 1. Arm E (image-first) — withheld board cannot be bypassed

Sherlock's verdict: no additional renderer reads `grid`. `FrameView` uses it only for
`.segmentation`, which the patch gates. On the first tool call `history`, `previous_frame`,
`transitions`, and `last_animation` have no prior frame, so none of them can leak the board.

Applied anyway (hygiene, his call): the withheld payload now carries `"grid": None` rather
than `[]`, and the sandbox guard tests `self._grid is None`. A genuinely empty board can
therefore never be confused with a withheld one, including by code poking the private
attribute. `normalize_grid(None)` already returns `()`, same as it did for `[]`, so nothing
downstream changes.

`build_bundles.py` now probes all four coupled edits for arm E (payload `grid` is None,
the call site requests withholding, the sandbox guard, the prompt line) and fails the build
if an ungated `_ascii_frame_view_payload(refreshed_frame)` call site survives. Previously a
single marker stood in for the whole three-file change.

**Shipped-vs-repo note:** job 7 launched at 00:47 ET with the bundle version built *before*
the `None` change, i.e. with `"grid": []`. Per Sherlock's own finding that is not a
practical bypass, so the run was left alone rather than killed and re-pushed. The uploaded
arm-E dataset and this repo therefore differ by that one literal until job 7 lands.

## 2. Arm D (glyphs) — it is an encoding intervention, not a pure visual swap

Sherlock tokenized job 1's actual pass-0 boards with the Qwen3.8 Flash tokenizer:

- all seven games: 1,522,282 → 1,509,891 tokens, **-0.8%**
- `ls20` **-6.4%**, `wa30` **+0.8%**, the rest roughly -0.4% to -1.3%

So the consonant set also moves context budget and runtime, and any gain cannot be
attributed to the loss of case-pairs alone. Recorded in the ARMS table so the arm cannot be
written up as a pure perception test. Input tokens are measured two ways rather than by
patching the harness mid-experiment: `vllm:prompt_tokens_total` is already dumped per job
in `vllm-metrics-final.prom`, and per-game counts come post-hoc off the transcripts with
the same tokenizer, for control and arm D alike.

## 3. Arm F — renamed to "commit prompt"

Level transition is readable exactly when needed (`action()` returns `level_completed`, the
next prompt says "You have progressed to a new level", the runner stops a batch on
transition), so the signal the arm's text points at is real.

But the harness enforces no action cap, so this arm tests whether *telling* the model to
commit changes behavior — not commit-and-execute as a mechanism. Renamed throughout:
label `F-commit-prompt`, title "ARC3 job8 commit prompt", slug `arc3-job8-commit-prompt`.
A bounded-plan mechanism is a separate arm, not this one.

## 4. Found while applying the above: Kaggle ignores the metadata id

Kaggle derives the kernel slug from the **title** and silently ignores a `kernel-metadata`
id that does not match, warning only on push. Job 7 was pushed as `arc3-job7-imagefirst`
and landed at `arc3-job7-image-first-turn`, so every later `kernels status` and
`kernels output` call looked up a kernel that does not exist — the queue would have watched
that slot forever and never reported it. Same latent break on job 6.

`build_notebooks.py` now derives the slug from the title (`title_slug()`), so the recorded
id is the id Kaggle will use. Queue state and the runner's default queue corrected.

## 5. The null check did not come back null

Job 3 (arm B) against job 5 (control) on the same seven lanes, passes 0-2:

| game | control levels | arm B levels | control score | arm B score |
|---|---|---|---|---|
| cd82 | 1, 2, 1 | 1, 2, 0 | 4.29 | 1.87 |
| cn04 | 1, 1, 1 | 1, 1, 1 | 4.76 | 4.76 |
| ka59 | 2, 1, 1 | 2, 1, 1 | 5.15 | 5.41 |
| lp85 | 1, 1, 4 | 3, 3, 5 | 9.76 | 24.91 |
| r11l | 1, 2, 1 | 1, 1, 2 | 7.94 | 7.94 |
| sb26 | 1, 1, 1 | 1, 1, 1 | 2.78 | 2.78 |
| sc25 | 0, 0, 2 | 0, 0, 2 | 2.22 | 0.53 |
| **total** | **26** | **30** | 5.27 mean | 6.89 mean |

Five of seven lanes are flat or within one pass of flat: cn04, sb26 are bit-identical,
ka59 and r11l identical in levels, sc25 identical in levels. That is the null behaviour the
check was for.

**lp85 is not flat.** It goes 1,1,4 → 3,3,5, +6 levels, and carries essentially the whole
arm-B gain on this lane set. lp85 is one of the three games the pre-registered prediction
said should *not* move. So the prediction is wrong as stated: the deletion arm is not
confined to the bottom seven.

Two readings, and the data here cannot separate them. Either the deletion helps wherever a
false prior was doing damage — lp85 included — or one lane got lucky three passes running.
cd82's -1 level and sc25's score drop cut the other way and are the same size.

What this does rule out: it is not "arm B only looks good because the bottom seven are
noisy." The two lanes it does move, it moves in level clears, not score drift.
