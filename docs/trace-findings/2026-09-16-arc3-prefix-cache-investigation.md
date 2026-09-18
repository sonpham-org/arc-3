<!--
Author: Claude Opus 5 (Bubba sub-agent "arc3-prefix-cache-probe")
Date: 16-September-2026
PURPOSE: Empirical investigation of low vLLM prefix-cache hit rate on the live ARC-3 25-lane
run on a108 (qwen38-27b-nvfp4, vLLM PID 765547, port 1234). Determines whether the ARC3
inference harness mutates the prompt prefix between turns, and what actually drives the
observed hit rate. Read-only investigation; no repo edits, no a108 state changed.
SRP/DRY check: Pass — new investigation, no existing doc covers this.
-->

# ARC-3 prefix-cache investigation — a108, 16-Sep-2026

**Verdict up front:** the harness is **not** the problem. Prompts are strictly
append-only — **467 of 468** consecutive request pairs across all 25 pass-0 games
preserve the entire previous prompt as an exact prefix, and the `tools` blob is
byte-identical throughout. History trim never fires: **0 of 493** requests show a
dropped turn.

The reported "4% hit rate" is a **sampling artifact of a 120-second window** containing
roughly one prefill — not the run's hit rate. The run's real hit rate at that moment was
**~46.5%** (vLLM's sliding-1000-request metric), down from a peak of **87.4%** an hour
earlier, against a measured perfect-cache ceiling of **89.6%**.

The signature points at server-side eviction: as contexts grow the *ideal* hit rate rises,
yet the observed rate fell — 87.4% at ~53K tokens/lane to 46.5% at ~61K/lane — and a clean
low-KV-pressure window measures **76.6%** against 46.5% at high pressure. The fix is
concurrency, not prompt layout.

---

## 1. Premise corrections (evidence first)

Three premises in the brief are wrong. All three are load-bearing.

### 1.1 Request-log path
**Brief said:** `/home/son/arc3-massdata-20260916T142717Z/runs/...`
**Measured:** that directory has no `runs/`. The logs are at
`/home/son/GitHub/arc-3/ARC3-Inference/runs/20260916_102724_qwen38-27b-massdata-25g-4p/`.
Minor, but noted so the path in the brief isn't reused.

### 1.2 "4.06% hit rate"
**Reproduced, then falsified as a run-level number.** I re-ran the same
`/metrics` delta myself. **Read this table by regime, not by window length** — the run
rolled from pass 0 to pass 1 at 14:18 ET, which reset every context to ~15K and dropped
KV usage from 66% to 6%:

| # | window | regime | KV usage | queries Δ | hits Δ | rate |
|---|---|---|---|---|---|---|
| A | 120 s, ~14:12 ET | late pass 0, high pressure | 64–66% | 73,090 | 3,136 | **4.29%** |
| B | ~150 s + gap, ~14:15 ET | **straddles the 14:18 rollover** | 66% → 8% | 404,739 | 197,568 | 48.8% |
| C | ~300 s, ~14:20 ET | **post-rollover** | 8–11% | 244,240 | 174,048 | 71.3% |
| D | 300 s, 14:29:55–14:34:55 ET | pass 1, low pressure | 14.0% → 16.8% | 319,312 | 244,608 | **76.6%** |

Windows B and C are **not** evidence that "a longer window reveals the true rate" — they
are higher because contexts reset, and B's duration is not exactly 150 s (the
prefix-cache counters were only read on that command's second poll, so its delta spans an
unknown inter-command gap plus the sleep). Window D is the clean one: a single regime,
both endpoints logged.

Window A is real but is a sample of ~**one** prefill. At the time of measurement the
server ran 25 lanes at ~62K context each, with aggregate generation throughput of
**16–65 tok/s across all 25 lanes** (0.6–2.6 tok/s per lane) and
`Avg prompt throughput: 0.0 tokens/s` for minutes at a stretch. A single ~73K-token
prefill that happened to miss dominates the whole window, and its 3,136 hit tokens is
almost exactly one system prompt (12,826 chars ≈ 3.1K tokens, block-aligned to
196 × 16 = 3,136). The "4% ≈ system-prompt fraction" coincidence in the brief is real,
but it describes **one request**, not the population.

The only trustworthy in-regime number for 14:10 is vLLM's own `Prefix cache hit rate`, a
sliding window over the last 1000 requests: **46.5%**.

### 1.3 "Eviction is ruled out — 35% of the pool is free"
**This inference does not hold.** In vLLM v1, `kv_cache_usage_perc` is
`1 - free_block_queue.num_free_blocks / num_gpu_blocks`, and the free-block queue
**contains cached-but-unreferenced blocks**. "35% free" is therefore not idle headroom;
it is the *entire budget available to retain prefix cache for every lane that is between
turns*. Likewise `num_preemptions_total = 0` only rules out running-request preemption,
not LRU eviction of cached blocks. Eviction is not ruled out by either metric.

---

## 2. The empirical divergence measurement (the job as briefed)

Method: for each pair of consecutive `event: "request"` records in a game's
`*_requests.jsonl`, serialize each `messages` element with
`json.dumps(m, sort_keys=True, ensure_ascii=False)`, then test whether the earlier
request's message list is an exact element-wise prefix of the later one, and find the
first differing message index and character offset.

### 2.1 Three games in detail (as briefed: ≥3 pairs, ≥2 games)

`bp35-0a0ad940_p0` — 26 requests, 25 pairs:

| pair | nmsg | step | prompt chars | 1st-diff msg idx | 1st-diff char | % of prompt |
|---|---|---|---|---|---|---|
| 0→1 | 2→6 | 1→1 | 17,394 | 2 (append) | 17,394 | 100.0% |
| 1→2 | 6→10 | 1→1 | 28,787 | 6 (append) | 28,787 | 100.0% |
| 2→3 | 10→13 | 1→2 | 39,290 | 10 (append) | 39,290 | 100.0% |
| 3→4 | 13→17 | 2→2 | 50,535 | 13 (append) | 50,535 | 100.0% |
| … | … | … | … | … | … | … |
| 23→24 | 84→88 | 11→11 | 284,170 | 84 (append) | 284,170 | 100.0% |
| 24→25 | 88→89 | 11→11 | 292,262 | **1 (user)** | **12,823** | **4.4%** |

`ls20-9607627b_p0` — 29 requests, 28 pairs: **all 28 = 100.0%** (pure append).
`cn04-2fe56bfb_p0` — 13 requests, 12 pairs: **all 12 = 100.0%** (pure append).

"100.0%" means the first divergence is at the *end* of the old prompt — i.e. the new
request is the old one with messages appended and nothing changed. This is the ideal
shape for prefix caching.

### 2.1b The append boundary, quoted

`bp35` pair 3→4 (nmsg 13→17), a representative pure-append pair. Messages 0–12 are
byte-identical between the two requests (verified element-wise), and the new request
simply continues:

**OLD — tail of message 12 (`user`, the multimodal frame), last 220 chars:**
```
…vsBGMH9ALCAAEgTAGnmAjGauUBwRgIgTQCk2QdgBPsAsIAASBMAaQIgTQCkCYA0AZBmLhDjmAsEGxEAaQIgzVwgRjAXCBYQ
AGkCIM39AIzgfgBYQACkCYA0c4EYzVwgOCMBkCYA0uwDMIJ9AFhAAKQJgLTLX7//4+4PP/z2zcJ3BbbnCkCaAEgTAGn/A7Hu
nJPllrtIAAAAAElFTkSuQmCC"}}]}
```

**NEW — message 13, the first appended message (`assistant`), first 220 chars:**
```
{"role": "assistant", "reasoning": "With a single RIGHT press, the player moved 6 columns
to the right (from column 20 to column 26). It's not a 1-cell movement — it's either a
fixed 6-cell step, or continuous movement u…
```

There is no divergence before this point. That is what "100.0%" means in the table above.

### 2.1c The `tools` array is also prefix-stable

The `messages` diff alone is not the wire prompt — Qwen's chat template renders the
`tools` definitions into the system block, so churn there would break the prefix at
position ~0. Checked separately:

| game | requests | distinct `tools` blobs | blob length |
|---|---|---|---|
| bp35-0a0ad940 | 26 | **1** | 1,144 |
| ls20-9607627b | 29 | **1** | 1,144 |
| cn04-2fe56bfb | 13 | **1** | 1,144 |

Byte-identical throughout, despite `self._tools(state_path)` being state-parameterized at
`tool_agent.py:2021`. The wire prefix is stable, not just the message list. This is also
consistent with the 3,136-token (= exactly one system block) hit observed in window A.

### 2.2 Full sweep — all 25 pass-0 games

```
pairs: 468   pure-append: 467   mutated: 1
  MUT ('bp35-0a0ad940', pair 24, nmsg 88->89, first-diff msg idx 1, 4.4%)
```

**99.79% of consecutive request pairs preserve the full prefix.** The hypothesis in the
brief — that the harness re-renders the ledger / re-numbers tool payloads / changes
tokens early in the sequence — is **refuted by measurement**.

### 2.3 The one genuine mutation, quoted

`bp35` pair 24→25, message index 1 (role `user`), first differing char at offset 12,823
of a 292,262-char prompt (4.4%). Message[1] is replaced wholesale, and its serialized
length collapses from 4,583 to 425 chars:

**OLD** (multimodal opening user message — text + base64 frame image):
```
{"content": [{"text": "No previous sequence has been executed yet.\nCurrent state: step 1,
level 1.\nValid actions right now: LEFT, RIGHT, MOUSE, ACTION7.\nOnly tool: `python`. It
receives `current_frame`, `previous_frame`, `history …
```

**NEW** (a short plain-string nudge):
```
{"content": "The previous `python` call inspected the frame but did not execute
`action(...)`. Reply with a `python` tool call only; do not write assistant text before
it. Do not print another broad segmentation dump. In the code, c…
```

This is a nudge/retry path that rebuilds the message list with the opening multimodal
user message displaced. It costs the whole prompt after the system block — but it fired
**once in 468 pairs**, so its contribution to the aggregate hit rate is negligible
(~0.2% of pairs × ~95% of a prompt ≈ 0.2 percentage points). It is a real latent bug in
prompt construction and worth fixing on principle, but it is **not** the cause of
anything measured here.

---

## 3. Is history trim / compaction firing? — **No. Zero times.**

Measured directly: across all 493 `event: "request"` records in all 25 pass-0 games,
message-list length is **monotonically non-decreasing in every single game**.

```
total requests 493   non-monotonic 0
```

A compaction (`_compact_history_into_ledger`, `tool_agent.py:2015`) or a trim
(`_drop_oldest_history_block`, `tool_agent.py:1919`) necessarily shortens the history,
which would show as a drop in message count. It never happens.

Why it never fires, from the code (local clone
`~/GitHub/arc-3/ARC3-Inference/inference/agent/tool_agent.py`, read-only):

- `tool_agent.py:1066-1069` — `_context_budget_tokens = max(1024, _LOCAL_ANALYZER_CONTEXT_WINDOW - reply_reserve - safety_margin)`.
- `tool_agent.py:2019-2021` — compaction only runs when the untrimmed request exceeds `_context_budget_tokens`.
- `tool_agent.py:1907-1909` — the trim short-circuits and returns the untouched history when the estimate is under budget.
- `tool_agent.py:180` — `_CONTEXT_TRIM_LOW_WATER = 0.6` (the 60% low-water mark named in the brief).

Measured largest pass-0 prompt: ~**75K** tokens, against `--max-model-len 102985`.
Games end (or the pass rolls over) before the budget is reached. **Candidate (c) in the
brief is dead.**

Worth calling out: the comment block at `tool_agent.py:1911-1916` shows whoever wrote
the trim already understood this exact failure mode and designed the low-water mark
specifically to avoid prefix churn. That code is doing its job.

---

## 4. What is actually happening

### 4.1 Measured facts

- **KV pool:** `GPU KV cache size: 2,387,249 tokens`;
  `Maximum concurrency for 102,985 tokens per request: 23.18x`
  (server log, 09-15 21:41:21). The run uses **`CONCURRENT_JOBS=25`**
  (`/home/son/arc3-massdata-20260916T142717Z/launch.sh`).
  **This is *not* meaningful oversubscription, and I want to be explicit about that**,
  because it is the obvious-looking wrong answer: vLLM's 23.18x figure is derived at
  `--max-model-len 102985`, and §3 establishes the run never gets near that — observed
  peak context is ~**75K**. At 75K the running-set ceiling is 2,387,249 / 75,000 ≈
  **31.8 lanes**. Twenty-five lanes fit the *running* set with ~20% headroom. The problem
  is not that requests don't fit; it is how much room is left over to *retain* cache.
- **Hit-rate trajectory** (vLLM sliding-1000-request metric, from the server log):

  | time (ET) | running | KV usage | ~ctx/lane | prefix hit |
  |---|---|---|---|---|
  | 10:34 | 25 | 11.0% | ~10K | 31.7% |
  | 11:34 | 25 | 35.0% | ~33K | 58.1% |
  | 12:14 | 25 | 45.4% | ~43K | 79.0% |
  | **13:14** | 27 | 59.8% | ~53K | **87.4%  ← peak** |
  | 13:40 | 25 | 62.6% | ~60K | 63.2% |
  | 14:00 | 24 | 60.7% | ~60K | 51.3% |
  | 14:10 | 25 | 64.4% | ~61K | **46.5%  ← time of the "4%" reading** |
  | 14:18 | 24 | **6.1%** | ~6K | 46.3% (lagging window) |

- **Two pressure regimes, measured directly** (each a clean single-regime `/metrics`
  delta with both endpoints logged):

  | regime | KV usage | hit rate |
  |---|---|---|
  | late pass 0, high pressure (sliding window, 14:10) | 64% | **46.5%** |
  | pass 1, low pressure (300 s, 14:29:55→14:34:55) | 14.0% → 16.8% | **76.6%** |

- **The 14:18 cliff is a pass rollover, not a fix.** All 25 `*_p1_requests.jsonl` files
  were created 14:18:02–14:24:30; the `*_p0_*` files stopped. Aggregate generation
  throughput jumped from 16–65 tok/s to **142–175 tok/s** — a ~3–8× speedup purely from
  shorter contexts.
- **Ceiling available:** across pass 0, 464 responses requested **15,001,045** prompt
  tokens; with a perfect cache only the final context of each game need ever be computed —
  **1,556,834** tokens. **Ideal hit rate = 89.6%.** Observed at end of pass 0: **46.5%.**

### 4.2 Inferred (stated as inference, not measurement)

Prompts are 467/468 pure appends, the `tools` blob is byte-stable, and trim never fires.
The prefix being *sent* is therefore stable, so every miss beyond the first turn of a game
is the server dropping blocks it had already computed. The remaining mechanism is **LRU
eviction of cached-but-unreferenced KV blocks**.

The strongest evidence is a **direction-of-effect** argument, and it does not depend on
any capacity model:

> As a conversation grows, each turn appends a *smaller fraction* of the total prompt.
> The **ideal** hit rate therefore **rises** monotonically with context length. Observed
> hit rate did the opposite — it rose to 87.4% at ~53K/lane and then **fell to 46.5% at
> ~61K/lane**, while the ideal was still climbing. Two effects pointing opposite ways;
> something is destroying cache that the harness is faithfully offering.

The pressure comparison agrees: **76.6% at 14% KV usage vs 46.5% at 64%**. (Note this
comparison is confounded — the low-pressure sample also has short contexts, which *lowers*
its ideal ceiling. It is biased **against** the eviction reading and still comes out 30
points ahead of the high-pressure sample.)

**The mechanism is temporal, not a static capacity shortfall.** An earlier draft of this
doc argued a `25L running + 25L retained ≤ pool` break-even at L ≈ 47.7K. That is wrong
and I am striking it: a matched prefix is *re-referenced*, not duplicated, so a lane never
needs two copies. The measured `kv_cache_usage` confirms it — 65% ≈ 1.55M ≈ 25 × 62K is
essentially all running set, with only a handful of lanes between turns at any instant.
What actually bites is **dwell time**: at 0.6–2.6 tok/s per lane a single turn takes
roughly 10–30 minutes, so a lane's retained prefix must survive tens of minutes of 24
other lanes' allocation churn against a free pool that at 64% usage holds only ~835K
tokens ≈ 11 lane-prefixes. Long gaps plus a cache smaller than the lane count is the
classic LRU round-robin thrash pattern.

**I did not verify this mechanism directly.** vLLM exports no eviction counter, and I did
not run a controlled low-concurrency A/B because the box is live and this was read-only.
**Unverified.**

### 4.3 A precision limit on every ratio in this doc

`prefix_cache_queries_total` (133M) and `prompt_tokens_total` (33M) do not reconcile with
`queries − hits = tokens computed`. vLLM appears to count queries per *scheduling* event,
so chunked prefills may be counted more than once. Every hit-rate figure here — 46.5%,
76.6%, and the comparison against the 89.6% ceiling — is `hits/queries` and therefore is a
**relative indicator**, not a literal "fraction of prompt served from cache." The
trajectory and the pressure comparison are sound because they use the same metric on both
sides. The 89.6% ceiling is computed independently from the harness's own
`usage.prompt_tokens` and does not share this caveat, but comparing it *against* a
`hits/queries` number does.

## 5. Recommendation

**Do not move anything in the prompt.** There is nothing to move — the prefix is already
stable, `tools` included, and `tool_agent.py:1911-1916` shows the trim was explicitly
designed to protect it. Reordering the ledger to the tail would be a no-op.

The lever is **how much of the pool is left free to retain cache**, which means trading
lanes for hit rate. Stated **directionally** — I could not A/B this on a live box:

1. **Reduce `CONCURRENT_JOBS` from 25 to ~16–18.** At 25 lanes × ~61K the free pool is
   ~835K ≈ 11 lane-prefixes, fewer than the 25 lanes cycling through it. At 16 lanes ×
   75K the running set is ~1.2M and the free pool ~1.19M ≈ 15.9 lane-prefixes, which is
   on the order of the lane count rather than half of it. The measured **89.6% ceiling**
   is the honest headroom statement; how much of the 46.5% → 89.6% gap this recovers is
   **not something I can predict from these measurements**, and I am deliberately not
   repeating the "+35 to +43 points" estimate an earlier draft carried, because it
   inherited the broken capacity model.
   Second-order benefit, measured: the 14:18 rollover showed **3–8× aggregate generation
   throughput** at short contexts, so fewer/shorter-lived lanes are not obviously a
   throughput loss.
2. **If you want this settled rather than argued:** one pass at `CONCURRENT_JOBS=16` on
   the same games, comparing the sliding-window hit rate at matched context length
   (~60K/lane). That controls the confound in §4.2 and takes one pass to answer. This is
   the measurement I could not make read-only.
3. **Lower `--max-model-len`** toward the observed ~75K ceiling. Does not change pool
   size, but reduces worst-case allocation and raises vLLM's own concurrency estimate.
   Secondary.
4. **Fix the message[1] displacement** on the nudge/retry path (the `bp35` pair 24→25
   case). Worth ~0.2 points — do it for correctness, not for the cache.

**Honest bottom line:** the divergence the brief went looking for is not there. The
harness builds a clean append-only prompt, `tools` is byte-stable, and the trim logic
never fires. The cache is being lost on the server side, and the signature — ideal hit
rate rising with context length while observed hit rate falls — points at eviction under
KV pressure. The "25 > 23.18 oversubscribed" framing is a red herring at this context
length and should not be used as the argument.

---

## Appendix — what was measured vs. inferred

**Measured (reproduced on a108, read-only):**
- 467/468 consecutive pass-0 request pairs are pure prefix-preserving appends; the single
  exception is `bp35` pair 24→25, diverging at 4.4% of the prompt.
- `tools` array byte-identical across all requests in 3 games (1 distinct blob each).
- 0/493 pass-0 requests show a message-count drop → history trim never fired.
- KV pool 2,387,249 tokens; vLLM max concurrency 23.18x **at max-model-len 102,985**;
  observed peak context ~75K → running-set ceiling ~31.8 lanes; run uses 25.
- Hit-rate trajectory 31.7% → 87.4% (13:14, ~53K/lane) → 46.5% (14:10, ~61K/lane).
- Window A (120 s, high pressure) reproduces at 4.29%; window D (300 s, low pressure,
  both endpoints logged) = 76.6%.
- Pass 0 requested 15.00M prompt tokens; perfect-cache floor 1.56M → **89.6% ceiling**.
- Pass rollover at 14:18; generation throughput 16–65 → 142–175 tok/s.

**Inferred:**
- LRU eviction of cached blocks under KV pressure causes the 89.6% → 46.5% gap.
- Mechanism is dwell-time driven (10–30 min turns vs a free pool holding ~11
  lane-prefixes), not a static 2× capacity shortfall.

**Unverified:**
- Direct observation of block eviction (vLLM exports no eviction counter).
- Any controlled low-concurrency A/B — not run; the box is live and this was read-only.
- The magnitude of recovery from reducing `CONCURRENT_JOBS`.

**Known precision limit:** all hit-rate percentages are `hits/queries`, and
`queries_total` does not reconcile with `prompt_tokens_total` — treat them as relative
indicators (see §4.3).

**Actions taken on a108:** SSH reads, `curl` to `/metrics`, `grep` of the server log,
`python3` parse of request logs. **Nothing was started, stopped, edited, or reconfigured.**
No repo file was modified; no PR opened.
