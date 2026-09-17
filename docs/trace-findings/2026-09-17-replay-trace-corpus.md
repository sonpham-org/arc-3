<!--
Author: Claude Opus 5 (Bubba sub-agent)
Date: 2026-09-17
PURPOSE: Method + results for the first frame-level pull of ARC-3 replay recordings from
arcprize.org. Maps the public API surface, records what was enumerated and pulled, and answers
the Boss's question — are agent reasoning traces coherent or nonsense — with measured numbers.
SRP/DRY check: Pass — no prior workspace doc covers /api/recordings or frame-level data; prior
arc3 docs cover scorecard metadata only.
-->

# ARC-3 replay trace corpus — first frame-level pull

**Date:** 17-Sep-2026 · **Author:** Claude Opus 5 (Bubba sub-agent)
**Scripts:** `tools/replay_scrape.py bulk`, `tools/replay_reasoning_report.py`
**Corpus:** `datasets/decision-steps/v0/recordings/` (gitignored) · **Report JSON:** `datasets/decision-steps/replay-reasoning-report.json`

---

## 1. API surface

Read-only GET only. No POST/PUT/DELETE was issued; no game session was opened or reset.

Every `/api/` path the arcprize.org front-end references, recovered by downloading the Next.js
chunks for `/scorecards`, `/platform/scorecards`, `/leaderboard` and the replay-player chunk
`8855-01cccd64897e42a6.js` and grepping for `"/api/`:

| Path | Auth | Use |
|---|---|---|
| `/api/sessions/<session_guid>` | **none** | session metadata: tags, `ai_agent`, `model`, `runner`, `config`, `card_id`, `environments[].runs[]` with `level_actions` / `level_baseline_actions` |
| `/api/recordings/<game_id>/<session_guid>` | **none** | the recording — JSONL, one object per line, `data.frame` + `data.action_input` |
| `/api/games/<game_id>` | cookie or key | `default_fps` only |
| `/api/user` | cookie | current user |
| `/api/user/scorecards?sort_by=&limit=&at=` | cookie | **own** scorecards, paginated |
| `/api/user/keys`, `/api/user/keys/<id>` | cookie | API key list (returns `key_id`, not the secret) |
| `/api/scorecard/<card_id>`, `/api/scorecard/open`, `/api/scorecard/close` | X-API-Key | live play-session scorecard; POST for open/close |
| `/api/public-scorecard/open` | none | POST, anonymous card creation — not used here |

`/replay/<session_guid>` is the public share URL; the player resolves it through
`/api/sessions/<guid>`.

### Enumeration: there is no public listing of agent sessions

Verified negatives:

- `/api/scorecard/<card_id>` for a foreign card → `401 NOT_AUTHORIZED` unauthenticated, and
  `401` with the Boss's session cookie. With `X-API-Key: <key_id>` it returns `404 card_id not
  found` for a foreign card **and equally for one of the Boss's own cards**. No authorization
  hole found. *(Unverified inference: the symmetric 404 hints the endpoint is scoped to live
  play sessions rather than being a reader — but `key_id` is an identifier, not the key secret,
  so the 404 may simply be the invalid-key path. Not established either way.)*
- `/api/user/scorecards` is own-user only.
- `/api/scorecards`, `/api/public-scorecard/<id>`, `/api/leaderboard` → 404.
- `/leaderboard` and `/competitions/arc-agi-3-preview-agents{,/archive}` contain zero session
  guids.
- Session guids are UUIDv4 — not enumerable by scan, and scanning would be abusive anyway.

**What does work:** ARC publishes `/replay/<guid>` links inline in its own pages. Fetching all
72 URLs in `sitemap.xml` and grepping for `/replay/<uuid>` yields **281 distinct session
guids** — 250 from `blog/arc-agi-3-human-dataset`, 21 from
`blog/arc-agi-3-preview-30-day-learnings`, 7 from `blog/arc-agi-3-gpt-5-5-opus-4-7-analysis`,
3 elsewhere. That is the enumeration, and it is a curated ARC selection, not a census.

Added to that: the Boss's own 171 runs via `pull_boss_scorecards.py` (56 with `actions > 0`),
plus the one hand-copied `gpt-6-astra` session `150eaeb5` pulled in a follow-up pass. Total
**337 sessions, 337 metadata records fetched, 0 failures.**

## 2. What was pulled

All 337 enumerated sessions yielded a recording: **337 files, 9.67 GB**, zero fetch failures. Disk after: 105 GiB free.

> Disk note: the brief's two caps (≤30 GB corpus, ≥100 GiB free) are incompatible on this box —
> it started at 116 GiB free. The script enforces both and would have stopped early; it did not
> need to. Size scales with actions at ~14 KB/action measured (the vc33 sample's 52 KB/action is
> a large-frame outlier).

| Class | Sessions | Actions |
|---|---|---|
| Human | 295 | 174,339 |
| Scripted baseline bots | 21 | 187,787 |
| LLM agents | 21 | 4,422 |

**The three-way split matters and is the main correction to the brief's framing.** 21 of the 42
`ai_agent=true` sessions are ARC's *scripted* preview baselines — `blindsquirrel`,
`guidedrandom`, `heuristicagent`, `action`, `dslagent`, `playzeroagent`, `tomasengine`. They
populate `action_input.reasoning` too, but with telemetry, not language:

```
'Type: arrow, Chance: 1.00'
'Action model selected 4 (prob: 0.503)'
'Randomly chose untested edge 15 from group 0 with [{17, 18, 13, 15}, ...]'
```

41,839 of the corpus's 41,973 non-null "reasoning texts" are these strings. Counting them as
model reasoning is what makes the traces look like nonsense in aggregate. They are excluded
from every number below.

## 3. The numbers — LLM agents only

**21 sessions, 4,422 actions.** Small sample; treat per-model rows as anecdotes with receipts.

| Model | Runner | Sess | Actions | Has `reasoning` envelope | Non-null summary text | Median summary chars | Median `reasoning_tokens` | Frame-change rate |
|---|---|---|---|---|---|---|---|---|
| claude-opus-4-7 | benchmark_agent | 6 | 1,879 | 1,868 | **0** | — | 0 (not reported) | 0.860 |
| gpt-6-astra | benchmark_agent | 3 | 1,473 | 1,469 | 24 (1.6%) | 439 | 516 | 0.999 |
| gpt-5-nano (Boss's gold-agent) | — | 9 | 848 | 0 | 0 | — | — | **0.099** |
| crest-alpha | benchmark_agent | 1 | 111 | 110 | 110 (100%) | 11,252 | 7,450 | 1.000 |
| gemini-3.1-pro-preview | benchmark_agent | 1 | 108 | 107 | 0 | — | 0 (not reported) | 0.851 |
| gpt-5-nano-2025-08-07 | arc-explainer | 1 | 3 | 0 | 0 | — | — | 0.000 |
| *(human, for reference)* | | 295 | 174,339 | 0 | 0 | — | — | 0.966 |

Corpus-wide LLM totals: **3,554** actions carry a reasoning envelope; **134 (3.8%)** carry
non-null summary text; **1,445** carry a null summary *with non-zero `reasoning_tokens`*.

## 4. Coherence verdict

**The traces are not nonsense. The overwhelming problem is that they are not shown.**

Three findings, separated as the Boss asked:

**(a) Withheld ≠ absent.** 1,445 `gpt-6-astra` actions report `usage.output_tokens_details.
reasoning_tokens` > 0 (median 516, max 9,374) while `reasoning` is `null`. That is direct
proof the model reasoned and the OpenAI Responses API declined to emit a summary. It is not
evidence of bad reasoning; it is evidence of a lossy channel. For `claude-opus-4-7` and
`gemini-3.1-pro-preview` the field is present but always `0` and the text always null — the
harness records an envelope and no content, so for those two models **we have no visibility at
all** and any claim about their reasoning quality would be unverified.

**(b) Where the text IS shown, it is coherent.** All 134 shown summaries are unique — no
repetition loop. Median length 9,614 chars, minimum 329. 94 of 134 (70%) name the action they
then emit. The content is grounded in the actual frame: grid coordinates, tile-code hypotheses,
frame-delta observations, hypothesis revision. Verbatim, `crest-alpha`:

> "I'm considering a horizontally moving enemy or obstacle that shifts right each turn.
> Specifically, it seems to start on row 61/62 after a reset that begins from col13 to 54. Then
> it shifts right incrementally every tick…"

That is a model reading the board, not word salad. The Boss's impression of mush most likely
came from the scripted-bot strings in §2 and from the very short OpenAI summaries.

**(c) Play competence is measurable independently of the text, and the good models are good.**
Actions used vs ARC's human baseline, restricted to levels the run actually **cleared**
(`i < levels_completed`): LLM median **0.48×** baseline (n=26 levels), **22 of 26** under
baseline. Humans on the same metric: median **0.81×** (n=166).

> Data note: `level_actions` is censored at exactly **5× baseline** — that is the per-level
> action cap. Across the corpus, no uncleared level ever exceeds 5.0× and eight sit exactly on
> it. Including uncleared levels therefore manufactures a pile of 5.0 ratios that measure the
> cap, not the agent; the filter above excludes them.

The sharpest case is `gpt-6-astra`, which is also the model whose reasoning is 98.4% hidden:

| Game | Result | Levels | Actions | Human baseline (same levels) |
|---|---|---|---|---|
| vc33-5430563c | **WIN** | 7 | 196 | 447 |
| s5i5-18d95033 | **WIN** | 8 | 242 | 638 |
| wa30-ee6fef47 | GAME_OVER (score 80) | 8 | 1,032 | 1,428 |

(`wa30`'s 1,032 is the run total including a post-GAME_OVER retry; the per-level sum for the
eight levels it cleared is 629 against the 1,428 baseline.)

It wins in well under half the human action budget with essentially no wasted moves
(frame-change rate 0.999). Competence is not in doubt; the trace is simply redacted.

By contrast `claude-opus-4-7` cleared 0–1 levels on 6 games, blowing past baseline on every one
(e.g. 275 actions on `cd82` level 1 vs a 55-action baseline). That *is* poor play — but with
zero visible reasoning we cannot attribute it to bad reasoning from this data.

The Boss's own `gpt-5-nano` gold-agent runs are the genuine failure mode: **90.1% of its actions
changed nothing on screen** (frame-change rate 0.099, vs 0.966 for humans). No reasoning is
recorded for those runs at all, so the harness is not capturing it.

### Summary

- "Are the traces coherent?" — Yes, where visible. 134/134 unique, median ~9.6k chars, grounded
  in the frame, 70% action-consistent.
- "Is there a lot of it?" — No. **3.8%** of LLM agent actions expose any reasoning text.
- "Is the model reasoning badly?" — Not the strong ones. `gpt-6-astra` wins at ~0.4× the human
  action budget while showing almost nothing. The visible-text scarcity is a provider/harness
  artifact, not a reasoning failure.
- Biggest caveat: **21 LLM sessions / 4,422 actions.** ARC publishes no agent-session
  enumeration, so this is the curated set ARC chose to link plus the Boss's own runs. Any
  per-model conclusion here is a data point, not a study.

## 5. Reproduce

```bash
# metadata only, with a size projection and no downloads
python3 tools/replay_scrape.py bulk --guid-file datasets/decision-steps/scorecards/site-replay-guids.txt \
  --runs-file datasets/decision-steps/scorecards/runs-20260917T074156.json --meta-only

# pull (resumable, skips what is on disk, stops at the disk caps)
python3 tools/replay_scrape.py bulk --guid-file datasets/decision-steps/scorecards/guids-agent.txt --cap-gb 18
python3 tools/replay_scrape.py bulk --guid-file datasets/decision-steps/scorecards/guids-human.txt --cap-gb 18

# analyse
python3 tools/replay_reasoning_report.py --out datasets/decision-steps/replay-reasoning-report.json
```
