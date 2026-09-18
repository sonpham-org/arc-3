<!--
Author: Claude Opus 5 (Bubba)
Date: 18-September-2026
PURPOSE: Cold-start orientation for a reviewer with no prior context (written for a Fable-5
session, "Dr. Fable"). Inventories every live ARC-3 workstream: where the code and data are by
absolute path, what each strand actually established, what is unverified, and which assets are
sitting unused. Written because the assistant reporting on this work had been narrating strands
in isolation and had lost track of the game-mechanics corpus entirely.
SRP/DRY check: Pass — this is an index and a verdict sheet; every strand's detail lives in the
dated write-up cited beside it, and none of that detail is restated here.
-->

# ARC-3 state of play — 18-Sep-2026

Cold-start notes. Nothing below is assumed known. Every claim is tagged **[verified]** (checked
against a file, a process or the GitHub API while writing this) or **[unverified]**.

---

## 0. The correction that prompted this document

Two things stated in Discord on 18-Sep-2026 at 11:40 ET were wrong, and are corrected here
before anything builds on them:

1. **"Multipass driver PID 943028 alive 5h45m."** Wrong. `ps -eo lstart,etime` on `gx10-a108`
   shows that process started **11:34:33 ET on 18-Sep**, six minutes before the claim.
   **[verified]**
2. **"Four passes, done ~noon Friday."** Wrong — 18-Sep *is* Friday. Pass 1's own log shows a
   5,400 s per-game budget, so a pass is ~1.5 h and four passes land **late afternoon 18-Sep**,
   not noon. **[verified]**

The more serious omission: the asset in §1 was not mentioned at all in any recent report,
despite being the single most complete thing in this project.

---

## 1. The game-mechanics corpus — the most complete asset, and the least used

**Repo:** `82deutschmark/arc-explainer` · **Local:** `/Users/macmini/GitHub/arc-explainer`
**Path:** `shared/arc3Games/*.ts` · **Rendered:** `https://arc3.markbarney.net/arc3/games/<id>`
(e.g. `/dc22`)

26 per-game metadata modules for the 25-game ARC-3 public demo set plus `as66`, the withdrawn
26th game. 25 of the 26 carry a `mechanicsBreakdown`: **553 structured mechanic entries, 527 of
them citing a specific line range in the game's own Python source** (`dc22.py:10663-10708`).
`as66.ts` is the only game without one — it is the withdrawn game, see
`trace-findings/2026-09-15-as66-the-withdrawn-26th-game.md`. **[verified]**

Each module carries: `description`, `simpleExplanation`, `mechanicsExplanation` (prose),
`mechanicsBreakdown[]` (`category` ∈ controls/goal/pieces/hazards/budget/feedback,
`introducedOnLevel`, `source`), `actionMappings`, `levelCount`, `humanDifficulty` /
`aiDifficulty`, `levelScreenshots`, `resources` (ARC Prize replay URLs), and a `notes` field
that records corrections with dates. `dc22.ts` is the reference example: it has a source-read
pass, an adversarial re-verification that overturned an earlier "never kills you" claim, and a
live-play confirmation. **[verified]**

**Why this matters and why it is flagged:** nothing in the inference or training pipeline reads
these files. The harness prompts (§2) do not inject per-game mechanics; the SFT corpus (§4) does
not use them as targets or as grounding. Whether they *should* be injected is a live design
question with a fairness dimension (see `trace-findings/2026-09-11-priors-vs-the-25.md` and
`2026-09-13-arm-c-mechanics-possibility.md`) — but the corpus existing and being ignored should
be a deliberate choice, not an oversight.

### 1b. Adjacent, also unused

- `shared/arc3Games/humanPlay.generated.json` — **50 recorded human runs by the Boss across all
  25 games**, cutoff 2026-06-18, each with `guid`, `cardId`, `state` (WIN / GAME_OVER /
  NOT_FINISHED), `levelsCompleted`, per-level `actions`, `resets`, `score`, and
  `levelBaselineActions`. Many are full WINs (`ar25` 8/8, `cn04` 6/6 at score 100, `dc22` 6/6,
  `wa30` 9/9). This is summary telemetry, not frame-level traces — but the GUIDs are the key
  into the replay corpus in §5, i.e. a path to human demonstration data for a corpus that is
  currently starving (§4). **[verified]**
- `shared/arc3Games/humanDifficulty.ts` — human-vs-AI difficulty ratings, 416 lines. **[verified]**

---

## 2. The agent harness and the site

**Repo:** `sonpham-org/arc-3` (hyphen) · **Local:** `/Users/macmini/GitHub/arc-3` (one clone only)
Serves `arc3.sonpham.net` via Railway service `arc3-viewer`. Harness *and* site are the same repo.

Prompts live in `ARC3-Inference/inference/agent/tool_agent.py`: system prompt ~line 422, retry
coaching ~line 2237, per-turn injection ~line 1347. Prose blocks in `agent/prompts.py`.
**[unverified — line numbers carried from the channel topic, not re-checked while writing this]**

`try-harder-harness` is a separate nudge library and is **not** the ARC-3 agent. Do not conflate.

---

## 3. Compact-reasoning A/B — the live experiment

**Write-up:** `docs/compact-reasoning-style-experiment.md` (merged) · **PR:** #43, open

Round 1 (17-Sep, `gx10-a108`, Qwen3.8-27B-NVFP4, 25 games) measured **+43% environment actions at
the same wall clock and the same token spend**, tokens/action −32%, 19 of 25 games improved. That
part holds.

The **score** headline from that run does not. Re-analysed paired by game: **+20.46 aggregate,
p=0.59, compact better on 8 games, worse on 6, tied on 11.** The original comparison summed two
totals instead of pairing — a single jackpot game carried it. More efficient play is shown;
*better* play is not. **[verified — the re-analysis is the content of PR #43]**

**Now running:** `~/arc3-multipass-20260918/driver.sh` on `gx10-a108` (`son@100.118.4.20`),
PID 943028, started 11:34:33 ET 18-Sep. Four passes alternating arms —
P1 compact, P2 baseline, P3 compact, P4 baseline — so time-of-day cannot bias the result. Per-game
budget 5,400 s ⇒ ~1.5 h/pass ⇒ finishes late afternoon 18-Sep. Logs in
`~/arc3-multipass-20260918/logs/P{1..4}.log`; the driver writes a ledger with vLLM health, a
treatment-marker count (expect 25 for compact arms, 0 for baseline) and a config-parity diff
against the reference run config. **[verified]**

---

## 4. SFT corpus and LoRA distillation — pipeline works, corpus does not

**Write-ups:** `trace-findings/2026-09-16-arc3-sft-extraction.md`,
`2026-09-17-arc3-lora-round1.md`, `2026-09-17-lora-gradient-rootcause.md`,
`2026-09-16-a424-lora-step-measurement.md`, `2026-09-16-a108-training-stack.md`
**Code:** `ARC3-Inference/distill/` · **Box:** `gx10-a424` (`son@100.106.31.61`), NVIDIA GB10,
121.63 GiB unified · **Base:** `/home/son/models/Qwen3.8-27B-BF16`

Two honest verdicts, both load-bearing:

- **The corpus is the bottleneck, not the extractor.** The entire corpus available today —
  finished 25-game baseline plus both massdata passes — is **381 trainable assistant turns
  across 41 records**. Target was 2–5K. Four full massdata passes project to ~600–700. The cap
  is the solve rate (11–12 of 25 games clearing exactly one level), not extraction. **[verified —
  from the write-up; numbers not independently re-measured today]**
- **LoRA round 1 completed and taught nothing.** 8/8 steps, 1.20 h, adapter saved, pipeline
  verified end to end — **no learning signal in the loss, and the adapter was never evaluated.**
  **[verified]**

**Round 2 is code-complete and unrun**, pushed 18-Sep as branch `feat/arc3-lora-round2-eval`
(commit `9e7b306eb`, no PR opened yet). It exists to make the measurement round 1 skipped:

| file | role |
|---|---|
| `distill/sft_batch.py` | the *single* shared encode→mask→chunked-CE path. Extracted from the trainer so trainer and evaluator score with identical code — two drifting copies of a label mask produce a "loss delta" that is arithmetic, not learning. Chunked CE is required: naive CE over the 27B vocab OOMs at ~20K tokens on 121 GiB. |
| `distill/eval_lora.py` | held-out evaluator. Loads the 27B once, toggles arms via PEFT multi-adapter so every arm sees a bit-identical batch; reports **paired** per-record deltas (with ~40 records the between-record spread swamps any plausible effect); includes a generation round-trip. |
| `distill/train_lora.py` | now imports that shared path instead of its own copy. |
| `distill/extract_sft.py` | held-out game selection (`--only-games`) for the test fence. |
| `scripts/decision_steps_to_chat.py` | decision-step v0 → chat messages. Note: `ascii` is null in all 11 v0 records, so the prompt is structured memory only — there is no board observation in-record, only `frame_ref` pointers. |

---

## 5. Replay / decision-step corpora

Moved out of the personal workspace into this repo on 17-Sep (PR #39, merged). **[verified]**

- `datasets/decision-steps/v0/recordings/<game_id>/<guid>.ndjson` — frame-level replay corpus
- `datasets/vendor-coherence/` — vendor replay coherence data
- `tools/replay_scrape.py` (bulk), `tools/pull_boss_scorecards.py`,
  `tools/replay_reasoning_report.py`, `tools/harvest_replays.py`, `tools/distill_reasoning.py`,
  `tools/analyze_coherence.py`, `tools/coherence_on_corpus.py`
- `tools/arc3/pull_replays.py` was a duplicate of `replay_scrape.py` and was **deleted**. Do not
  rebuild it.

Findings: `trace-findings/2026-09-17-replay-trace-corpus.md`,
`2026-09-17-vendor-replay-coherence.md`, `2026-09-17-boss-scorecard-inventory.md`.

---

## 6. Kaggle prompt-arm matrix

`trace-findings/2026-09-15-arc3-kaggle-arm-matrix.md` — 11 arms (job0–job10, user `markbarney`),
completed 12–14 Sep. Per-arm aggregates, per-game scores, pass-level variance, two comparability
traps, and a verdict on whether any arm's lead is distinguishable from noise. Raw numbers
included so nobody re-downloads from Kaggle. Related: `2026-09-16-jobs-11-12-reset-guard-result.md`,
`2026-09-17-seed-variance-and-the-sb26-jackpot.md`.

**Recurring pattern across §3 and §6:** every apparent lead measured so far has collapsed under
pairing or seed variance. Treat any new single-pass headline as noise until it is paired.

---

## 7. PR status — checked live, 18-Sep

| PR | subject | state |
|---|---|---|
| #43 | multipass repeat of the compact A/B | **OPEN** |
| #4 | context matrix / CPU KV resume audit | **DRAFT** (5-Sep, stale) |
| #30 | SFT extraction pipeline | merged 17-Sep |
| #35 | SFT game exclusion | merged 17-Sep |
| #39 | scorecard + replay tooling from workspace | merged 18-Sep |
| #41, #42 | seed variance; dc22/m0r0/tr87 mechanics | merged 18-Sep |

`feat/arc3-lora-round2-eval` — pushed, **no PR yet**. **[verified via `gh` while writing]**

Earlier write-ups describe #30 and #35 as "open, not merged". **Those write-ups are stale; the
table above is live.** Re-check with `gh pr view <n>` rather than trusting any prose.

---

## 8. Where things live — one table

| what | where |
|---|---|
| Agent harness + Son's site | `sonpham-org/arc-3` → `~/GitHub/arc-3` (single clone, branch `main`) |
| Game mechanics corpus + our site | `82deutschmark/arc-explainer` → `~/GitHub/arc-explainer`, `shared/arc3Games/`, rendered at `arc.markbarney.net` / `arc3.markbarney.net` |
| Game authoring + differentiation loop | `~/GitHub/autoresearch-arena/arc3games/` (`differentiate.py`, `verify_*.py`, `dist/`, `game-ideas/ledger.jsonl`) |
| Redbluepill games | `theredbluepill/arc-interactive` |
| Training box (LoRA/SFT) | `gx10-a424`, `son@100.106.31.61`, GB10 121.63 GiB |
| Inference box (harness runs) | `gx10-a108`, `son@100.118.4.20` |
| Dated findings | `~/GitHub/arc-3/docs/trace-findings/` |
| Runbooks | `~/bubba-workspace/docs/*arc3*` |

Deleted 10-Sep, do not recreate: `~/GitHub/arc-3-tmp`, `arc-3-main`, `arc3-site` — all dupes.

---

## 9. What a reviewer should push on

1. **The §1 corpus is unconnected to everything else.** 527 source-cited mechanic entries and 50
   human runs exist; neither feeds the prompts or the training corpus. Is that deliberate?
2. **§4 is stalled on data, not code.** 381 turns against a 2–5K target. The human-play GUIDs in
   §1b are the most plausible route to more, and no one has tried to walk them into the §5 replay
   corpus.
3. **§3 needs its multipass result before any style conclusion is stated anywhere.** Late 18-Sep.
4. **Round 2 must actually run.** Code is on `feat/arc3-lora-round2-eval`; until it runs, round 1's
   adapter is still unevaluated.
5. **Re-verify any number quoted from a write-up before reusing it.** §7 shows prose going stale
   inside 24 hours.
