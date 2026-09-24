<!--
Author: Claude Fable 5.1, for Son Pham
Date: 23-September-2026
PURPOSE: Son's five-part program of 23-Sep: (1) what the most intensive public ARC-AGI-3 harnesses do
and which parts transfer to a 7-lane Flash-Next box; (2) a hard-seven, one-wave, full-clock run so a
harness gets all the time a hard game needs; (3) the RHAE-vs-token efficiency trade-off those runs
expose; (4) an RL scheme that switches an intensive harness down when it is safe; (5) a cheap LoRA
router that picks harness parts from the context so far. Records what is launched, what is queued,
and the design constraints already known.
SRP/DRY check: Pass. The 264/396 clock controller is gcp/controllers and cv5-cr-396-20260923 (cited);
the harness census is plans/2026-09-23-adaptive-thinking-mode-router.md §8 (cited, not restated);
the field notes are summarised here with sources, the full reading lives in the memory note.
-->

# Intensive harness → router: the program

**Requested by:** Son, 23-Sep-2026, five parts. Model: Fable 5.1 from this point.

## 1. What the field's intensive harnesses actually do

| harness | mechanism | budget / cost | result (public 25) | status |
|---|---|---|---|---|
| Executable world model ([2605.05138](https://arxiv.org/html/2605.05138v1)) | coding agent keeps `state_io` / `engine` / `planner` Python; **replay verifier** checks the model reproduces recorded frames; **plan executor** simulates then acts, halts on first mismatch; refactor loop as an MDL bias | $34–$620 per run; 1,500 actions/level cap | 7/25 games solved, mean RHAE 32.6 %, 106/209 levels; huge run-to-run variance (cn04 62 % vs 0.01 %) | paper, self-reported |
| Its ablation ([2607.15439](https://arxiv.org/html/2607.15439v2)) | textual WM → +executable → +simplification → +verification, 4 model settings | verification costs **1.8–3.3×** the tokens of textual | **verification ranked first in all 4 settings** (+0.6 to +8.6 RHAE); *executable* is the weakest piece (textual beat it at gpt-5.5, 58.9 vs 51.2); **reasoning effort dominated every variant**; hard levels need 300–578 human actions | paper |
| Arcgentica ([Symbolica](https://www.symbolica.ai/blog/arc-agi-3), [repo](https://github.com/symbolica-ai/ARC-AGI-3-Agents)) | orchestrator never sees a grid; **explorer** (acts, diffs), **theorist** (text only, no actions), **tester** (tight action budget), **solver**; shared `memories` DB of confirmed facts + marked hypotheses; retire a saturated agent, spawn fresh with a summary | ~800 actions/game; $1,005 for 25 games | 36.08 %, 7/25 games, 113/182 levels | repo public, self-reported |
| OY1 ([repo](https://github.com/OYLabsAI/arc-agi-3-api-harness)) | **exact frame recall**, **evidence-linked notes**, **prediction-checked batches** of ≤8 actions, batch halts on mismatch or level change | $415, 153M tokens, 6 h 48 m (GPT-6 Astra) | 25/25, 183/183 levels | self-reported, public only |
| Schema ([site](https://schema-harness.github.io/), [HN](https://news.ycombinator.com/item?id=48935905)) | program-as-world-model, verify against history, plan by search; cheap model first, escalate below 80 % | ~$25k / 25 games on GPT-5.6 Sol; "burn 100k tokens thinking" | 98.98 % RHAE (Opus 4.8 / Fable 5) | self-reported; critics: public-only, tool-building |

Two conclusions for us. **Every 90 %+ number is a frontier model on the public set, self-reported.**
And the component that the only controlled study found to matter — **verification: predict, act,
compare, stop on mismatch** — is exactly the one that is cheap to add to our loop, because the harness
already emits `expected_observation` per turn (the decision-step schema's falsifiable field). The
expensive parts (a full executable world model, an orchestrator hierarchy) are what the ablation found
*least* load-bearing. The transferable order is therefore: prediction-checked action batches →
ledger-replay verifier → evidence-linked notes → subagent context isolation.

## 2. The hard-seven, one-wave, full-clock run — launched

`g4run-cv5cr-hard7-264-w7-20260923-d85c029903`, us-central1-c, Spot. Base:
`compaction_v5_clean_return_a` (19-Sep) byte-for-byte; 7 lanes × 7 games = one wave; **15,840 s per
game** (7.7× the 132-class 2061); 264-minute suite; 21,600 s VM. Preflight 45/45 (`verify_396.py`).

Why this base: the 23-Sep census (`adaptive-thinking-mode-router.md` §8.1) has it worst overall and
**best on the hard seven** — 4.20 score/1k actions, 9.0 levels, the only 132-minute arm more efficient
on the hard seven than on the easy games. Not comparable to any 25-game mean; compare per game against
the same seven rows of the 132 pair and the 264 clean-return run (9.92 / 15 levels).

Also running: `g4run-cv5cr264-w7-20260923-09c0d3183d` (25 games, 264 min) — at minute 41: 3.94 mean,
18 levels, 907 actions.

## 3. RHAE-efficiency vs token-efficiency

RHAE = Σ per level (human actions ÷ agent actions)² capped at 1.15. The hard-seven full-clock run and
the 264 run give, per game, actions and generated tokens against levels cleared, so both efficiencies
fall out of the same artifacts. What we already know (§8.2 of the census): tokens per action sit in a
630–740 band for every arm, so today the two efficiencies rank harnesses identically — **the arms differ
in decision quality, not verbosity.** An intensive mode (verification, subagents) breaks that
equivalence on purpose: it spends 2–3× tokens per action to spend fewer actions per level. That is the
trade-off the router prices.

## 4. RL: switch the intensive harness down when it is safe

Design constraints already known: global effort knobs were neutral-or-worse; thinking-off was
catastrophic (3,095 actions, 0 levels); **compaction is stateful** (switching in is fine, switching out
does not restore dropped context), Loop A/B deletions are stateless prompt text. So the action space
is per-turn *parts* — {verification on/off, thinking HIGH/MEDIUM, compaction retain fraction, subagent
isolation on/off} — with fail-open to the intensive setting. Reward: RHAE-weighted levels per token,
scored on the hard seven. Labels come from checkpoint branching (teacher-forced single-turn first,
divergent rollouts on a ~400-turn sample), as in `adaptive-thinking-mode-router.md` §4.

## 5. The router

Order: prior → GBM probe on cheap features (turns since level clear, frames since change, last
expectation confirmed?, repeat-state count, tokens the last reply used) → **LoRA head on the policy's
own hidden states over the context so far** only if the probe plateaus. Must decide *before* the reply
it governs, cost < 50 ms, fail open. It predicts a configuration, never content, so it does not reopen
the no-teacher call.

## Queue

1. swap-30 and swap-70 at 264 on the cv5-CR base (both; the 10-Sep sweep was n=1 on an older family and
   its overall and hard-seven rankings were inverted — 70 % best overall / worst h7, 50 % the reverse).
   Code arms: `half_context_swap.py:186` is `target = budget // 2`, hash-frozen; swap-70 also needs
   `live_half_swap_gate.py:41` (`<= budget // 2`) relaxed or it dies at the gate.
2. LA-CR at 264 and hard-seven-only, for the three-way at length.
3. Prediction-checked action batches as the first "intensive part" (the harness already has the field).

## 24-Sep: what actually ran, and the v2 arms

**hard7-264 collapsed and was redone.** `…-d85c029903` lost its vLLM engine at minute 31 (`RPC call to
sample_tokens timed out` → EngineDeadError under 7 × ~94k contexts) and the harness spun against the dead
server for hours at 0.48 / 5 levels. Relaunched as `g4run-cv5cr-hard7-264-w7-20260923-7c19c6eb63` with a
watchdog in the startup (probe `/v1/models` every 60 s, restart the container after 3 misses, log
`SERVER_RESTARTS`); the same watchdog is now in every derive. Details: `gcp/controllers/cv5-cr-clock/README.md`.

**Five flag arms on the hard seven, 132 min, one wave** — launched 23/24-Sep:
execution `…-ce7843057b`, memory `…-d5d8b2be9d`, symbolic `…-5aac84d4fc`, solver `…-92b391fd79`,
selfcheck `…-e58ade7fe2` (third launch: the first two died in the bundled selftests, which call `action()`
without `expect()`; the requirement is now switched on by `ARC3_PREDICTION_CHECK=1` exported after the
last selftest). At minute ~75 the four survivors sat at 1.2–1.6 mean / 10–14 levels / 131–170 act per
level, within noise of each other; the 132-minute cv5-CR base cleared 9.0 hard-seven levels in total.

**LA-CR at 264** (queue item 2) — `g4run-lacr264-w7-20260923-8367f8ff09`, `la_clean_return_a`
byte-for-byte, 4,122 s per game, 4 waves. Son: "be open-minded that LA-CR might not be better than CR" —
at 132 it leads all-25 but trails both CR bases on the hard seven, so the 264 three-way (CR 25.07 / 81
levels, cv5-CR, LA-CR) is genuinely open.

**Items 1–3, own take (v2 arms).** Son: "reuse the flag but have your own take and build on these things."
The flag arms give the model *declarative* memory (text rules, a JSON scalar spec, an `expected_next`
check). The v2 arms keep the same flags and add, in the Python sandbox, a host-persistent per-game
**code store** (`store`, `save(**fields)`; `save(code=src)` re-executes each snippet, so helpers survive
context rotation) plus one executable primitive that is **replayed against the full recorded history**:

| arm | builds on | primitive | verification |
|---|---|---|---|
| execution_v2 | memory+execution lease | `predict(before_frame, action) -> grid \| cells \| None`; `verify(predict)` replays it over every transition | every action auto-checked against `predict`; mismatch halts the batch; batches > 1 need fidelity ≥ 0.8 on ≥ 3 transitions |
| memory_v2 | memory | `rule(id, text, holds)`: a predicate over one transition, stored with the model's text | replayed at every snippet start; the first counterexample **revokes** the rule and is printed — memory cannot keep what the history contradicts |
| symbolic_v2 | memory+symbolic | `encode(frame)` / `step(state, action)` as plain Python; `replay()`; `plan(goal, max_depth)` bounded BFS from the current state | each action auto-checked against `step∘encode`; same batch gate from `replay()` |

This is the ablation paper's result ("verification first, executable weakest") turned into a design: the
executable model is optional and cheap (a few lines of Python), the verification is mandatory and host-run.
Built by `patch_v2.py` (sandbox + host store + constant-only prompt edits), smoke-tested locally against a
fake host, preflight 72/72 each. Launched 24-Sep on the hard seven, 132 min, one wave; run ids in the
controller README once the VMs report.
