<!--
Author: Claude Opus 5 (Bubba)
Date: 16-September-2026
PURPOSE: Write-up of the ARC-3 SFT trace-extraction work: what the extractor does, two
alignment/identity bugs found and fixed, the frame-fidelity verification against captured
request logs, and the measured corpus stats for the 27B baseline and massdata runs. Records
four premise corrections against the assigning brief so they are not re-litigated.
SRP/DRY check: Pass — the code and its docstrings live in sonpham-org/arc-3
ARC3-Inference/distill/; this file is the measurement record and the findings narrative.
-->

# ARC-3 SFT trace extraction — 16-Sep-2026

PR: **sonpham-org/arc-3 #30** — https://github.com/sonpham-org/arc-3/pull/30 — open, not merged.
Branch `feat/sft-extraction-pipeline`, based on `origin/main` @ `0d5ec40de`. The repo has no
`.github/workflows/`, so there is no CI to report. The CHANGELOG hook did not renumber or
rewrite the entry — the 59 added lines went in verbatim.

## Headline

The extraction pipeline now works and is verified against ground truth. It is **not** the
bottleneck. The whole corpus available today — the finished 25-game baseline plus both
completed-and-in-progress massdata passes — is **381 trainable assistant turns across 41
records**. The first-LoRA target in the brief is 2–5K turns. Four full massdata passes plus
the baseline project to roughly **600–700 turns**, still 3–8× short. The cap is the solve
rate (11–12 of 25 games clearing exactly one level), not the extractor.

## What the extractor reads — a correction to the brief's framing

The brief describes this as a pipeline over "rollout request logs". It is not. `extract_sft.py`
reads `runs/<run>/artifacts/*_events.jsonl` and `*_viewer_data.json`, and regenerates the board
images from the `board` grids. The request logs are the wrong input for the job: the level-credit
metadata the filter depends on (`levels_completed`, `actions_per_level`, per-event `level`)
exists only in `artifacts/`, and request records are cumulative — each replays the whole
conversation, so ar25 p0 has 620 image parts across 50 records for a 24-frame game.

The request logs are still valuable, just in a different role: as a **fidelity oracle**. That is
what `distill/verify_frames.py` (new in this PR) uses them for.

## Premise checks

**1. "Known API drift: `frame_to_png_bytes` vs `frame_to_png_data_url`." — not present.**
Both exist in the current tree: `frame_to_png_bytes` at `ARC3-Inference/inference/agent/vision_context.py:153`,
`frame_to_png_data_url` at `:172`. The extractor imports the former and ran clean on first
invocation against `origin/main` @ `0d5ec40de`. Nothing to fix.

**2. "Inline base64 PNGs in the request logs" — confirmed, no exceptions.**
Scanned every `*_requests.jsonl` in both runs: 25 files / 928 records / 8,520 image parts in the
baseline, 50 files / 1,783 records / 16,735 image parts in massdata. **Zero files with zero
images.** The multimodal observations are present throughout. The old `ascii: null` decision-step
corpus problem does not recur here.

**3. "~233 usable turns, 23.9% yield, 11 of 25 games" — reproduced exactly, but it is not a
turn count.**

`sum(actions_per_level[:levels_completed])` over the baseline gives 233, and 233/973 = 23.9%,
with the same 11 games in the same order and the same per-game values the brief listed
(ls20 42, re86 29, vc33 29, sp80 26, s5i5 24, su15 23, ar25 20, cn04 16, sb26 12, r11l 7, lp85 5).
That figure is an **environment-action** count. The extractor's trainable output from the same
11 games is **12 records / 113 assistant turns**. Both numbers are right; they are different
units, roughly 2:1. No disagreement, and the extractor was not changed to chase 233.

**4. "The teaching half is the bottleneck" — the solve rate is.** See Headline and Corpus below.

## Two bugs found and fixed

### Off-by-one in the board observation (the significant one)

`_analysis_events` attached each analysis event's **own** `board` to that event's user message.
The board stored on an analysis event is the state that event's actions *produced* — the
outcome, not the observation. The model was therefore going to be trained on "here is the board
after your move; now choose the move", which is exactly the train/serve skew the module docstring
claims to avoid.

Verified against the captured request logs, not inferred:

- In every game checked, the **step-1 request carries exactly one image and it is the `initial`
  event's board**, never `analysis[0].board`. (In 2 of 4 spot-checked games the first action did
  not change the board, so the wrong pairing coincidentally matched — which is why this survived.)
- The full observation sequence is `[initial.board, analysis[0].board, analysis[1].board, …]`,
  with decision step *k* seeing element *k*.

Fixed in `_analysis_events` by walking the whole ordered event list and handing each record its
predecessor board. Built before level grouping, so the first level-2 step correctly takes its
observation from the level-1 group. `traces.py` is untouched — it only reads `event["grid"]`,
so the distill-local seam is the whole fix.

Regression after the fix, as expected: records / assistant turns / contributing games unchanged
at **12 / 113 / 11**; unique rendered images moved **73 → 69** (the `initial` board joins the
dedup set, the last event's board leaves it). That delta is the fingerprint that it landed.

### Record-`id` collision across passes

`build_records` globs all `*_viewer_data.json`, which on a multi-pass run matches `_p0_` and
`_p1_` alike, and `game_id` carries no pass suffix — so `ar25 p0 L1` and `ar25 p1 L1` emitted the
**same `id`**, and the "games with solved data" counter deduped two real trajectories into one.
Only bites on multi-pass runs, i.e. exactly the massdata corpus. Fixed: `pass_index` is now part
of the `id` and a first-class record field, and the counter is per `(game, pass)`.

## Frame fidelity — measured, not assumed

`run_config.json` for these runs has **no multimodal block at all**, so the extractor's
`--upscale 4 --style plain` defaults (sourced from a stale docstring reference to an older
`a108.qwen36` config) were unverified. The new `distill/verify_frames.py` settles it by decoding
the captured base64 PNGs and comparing them to regenerated frames.

**Compare pixels, never bytes.** The serving path and Pillow choose different PNG encoder
settings for the same raster: identical images come out at different file sizes (946 B vs 957 B
for the same 256×256 frame). Byte comparison reports 0/17 on frames that are pixel-identical.

Sweep over `upscale ∈ {1,2,3,4,6,8} × style ∈ {plain, outline}`:

| setting | prefix-identical frames |
|---|---|
| `--upscale 4 --style plain` | 55/58 |
| every other combination | 0/58 |

`upscale=4, style=plain` is uniquely correct. The module docstring's `FIDELITY CAVEAT`
("`save_request_logs: false`, so exact image bytes are not stored") is stale for these runs and
has been rewritten.

Full verification. Coverage is complete: request logs were pulled for all 25 baseline games and
for both passes of all 14 games that contribute a massdata record, which is **every one of the
355 image parts in the combined corpus**.

| run | game-passes checked | all frames | **corpus frames** |
|---|---|---|---|
| `20260915_230835_…baseline-25g` | 25 | 399/415 (96.1%) | **102/102 (100.0%)** |
| `20260916_102724_…massdata-25g-4p` | 28 | 480/511 (93.9%) | **251/253 (99.2%)** |
| **combined corpus** | 53 | — | **353/355 (99.4%)** |

**353 of the 355 frames that enter the training corpus are pixel-identical to what the model
saw.** The two exceptions are isolated single frames: `sp80-589a99af_p0` chain index 12
(analysis step 9) and `tu93-0768757b_p0` chain index 1 (step 2). Both sit in games where the
harness's captured image count differs from the analysis-event count, and in both the frames
before and after the bad one match. Cause not established — flagging it rather than claiming it
is understood. It is 0.6% of the corpus.

Most divergence is outside the corpus entirely: of the 16 baseline and 31 massdata all-frame
mismatches, all but those two fall in games or levels the rejection sampler discards. The pattern
is the harness emitting fewer images than there were analysis events (e.g. cn04: 11 captured vs
13 chain entries, with one duplicate frame omitted mid-sequence), which shifts the tail.

One measurement caveat on the massdata p1 columns: p1 is the live run, and the `artifacts/` copy
was taken before the request-log copy, so `captured > chain` for every p1 game. That is copy
skew, not a defect — the corpus-frame column compares only positions present in both, and every
p1 game scores clean there.

## Emitted record schema

One JSONL record per `(run, game, pass, level)`:

```
id                  str   "<run>/<game_id>/p<pass>/L<level>"
game_id             str
pass_index          int
run                 str
level               int
solved              bool
level_actions       int   env actions spent on this level (for later advantage weighting)
num_messages        int
num_assistant_turns int   the trainable unit
num_images          int
messages            list  OpenAI chat format
```

Message shapes: `system` → `{role, content}`. `user` → `{role, content}` where the first user
message of each decision turn has `content` as a parts list `[{type: "text", …},
{type: "image_url", image_url: {url: "data:image/png;base64,…"}}]`; later user messages inside
the same turn are plain text, matching the serving path (the harness sends one image per turn,
on the first prompt). `assistant` → `{role, reasoning, tool_calls}` — `content` is legitimately
absent on 56 of 113 baseline assistant messages because the model emitted reasoning plus a tool
call and no prose; all 113 carry `reasoning`. `tool` → `{role, content, tool_call_id}`.

**The board observation lives in the `image_url` part of the user message.** Images survive: 355
image parts across the 41-record combined corpus. There is no `ascii` field and the board is not
duplicated as text — `board_ascii` exists in the events but is not what the model was shown, and
is not emitted.

## Corpus, measured

Yield, per pass (env actions at cleared levels ÷ total env actions):

| run / pass | actions | at cleared levels | yield | games contributing | zero-contribution |
|---|---|---|---|---|---|
| baseline p0 | 973 | 233 | **23.9%** | 11/25 | 14 |
| massdata p0 (complete) | 1,182 | 411 | **34.8%** | 12/25 | 13 |
| massdata p1 (in progress) | 875 | 267 | **30.5%** | 12/25 | 13 |

Massdata beats the baseline on yield, by roughly 7–11 points.

Trainable output:

| corpus | records | assistant turns | image parts |
|---|---|---|---|
| baseline p0 | 12 | 113 | 102 |
| massdata p0 | 16 | 144 | — |
| massdata p1 (partial) | 13 | 124 | — |
| **combined** | **41** | **381** | **355** |

Levels: L1 ×35, L2 ×6. Fifteen distinct games contribute across all three passes; **10 of the 25 contribute zero
turns in every pass so far** (bp35, dc22, g50t, ka59, m0r0, sc25, sk48, tn36, tr87, wa30).

Token distribution — text measured with the Qwen3.8-27B tokenizer, images counted separately:

```
text tokens (measured)  : 1,270,599
image tokens (estimate) :    22,720   @ 64/frame
total (estimate)        : 1,293,319

per-record total tokens: min 10,483 | p25 20,592 | median 34,829 | p75 42,496 | p90 46,292 | max 53,258
records over 65,536 tokens: 0 / 41 (0.0%)
```

**Nothing exceeds the ~64K trainer budget.** The largest record is 53,258 tokens, 81% of the
limit. Note that this is per *level-granularity record*, not per turn; a record is a whole
level's multi-turn trajectory.

The image figure is an estimate, flagged as such in the tool: 64 tokens/frame is arithmetic from
the geometry this corpus actually contains (256×256 at a 16 px patch with 2×2 spatial merge =
(256/16)²/4), not a measured server number. Base64 payloads are deliberately excluded from the
text count — tokenizing them would inflate every record into fiction.

**The 64K conclusion does not depend on that estimate.** The largest record is 53,258 tokens
carrying 27 image parts. At 256 tokens/frame — four times the estimate — it reaches ~58.4K, still
under the limit. "Zero records exceed the trainer budget" holds wherever the true vision-token
constant lands. The text count is raw content plus reasoning plus tool-call arguments, without
chat-template scaffolding or special tokens; at 20–40 messages per record that is a few hundred
tokens, nowhere near the ~12K of headroom.

## The projection worth acting on

Massdata p0, complete, produced 144 assistant turns. Four full passes at that rate ≈ 576, plus
the baseline's 113 ≈ **600–700 trainable turns** when the live run finishes. Against the 2–5K
target that is **3–8× short**, and no extractor change closes the gap: 11–12 of 25 games clearing
exactly one level each is the ceiling.

More passes do surface some new games, but with clear diminishing returns. Measured overlap:
massdata p0 and p1 contribute 12 games each and **share 10** — union 14. Adding the baseline's 11
lifts the all-run union to **15 of 25 games**. So the second pass bought 2 new games and the
baseline bought 1 more; the same ~10 games carry every pass. Extrapolating, passes 2 and 3 should
add turns but few new games, and the 10 games that have never cleared a level (bp35, dc22, g50t,
ka59, m0r0, sc25, sk48, tn36, tr87, wa30) are unlikely to start.

If 2–5K turns is a real requirement, the lever is game count and difficulty spread, or accepting
lower-credit data (e.g. partial-level credit, or `--keep-unsolved` with down-weighting), not the
pipeline.

## Reproducing

```bash
cd ARC3-Inference
python3 distill/extract_sft.py --run-dir <run> --out corpus.jsonl --inline-images
python3 distill/verify_frames.py --run-dir <run>            # needs save_request_logs: true
python3 distill/verify_frames.py --run-dir <run> --sweep    # find upscale/style
python3 distill/corpus_stats.py --corpus corpus.jsonl --tokenizer <tokenizer.json>
```

Working data on this Mac: `~/bubba-workspace/arc3-sft/` (copied artifacts and request logs,
emitted corpora, tokenizer). a108 was read-only throughout; no process or run directory touched.
