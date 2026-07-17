# native/ — OPINE's world-model method, reproduced in our own code

The OPINE paradigm (synthesize an executable world model, admit it only when it
reproduces every observed transition EXACTLY, then plan by simulating it),
rebuilt natively so it runs on **our** models via plain `/v1/chat/completions`.
No codex, no Responses API — which is what killed the "run their code on Qwen"
path (see `../opine-port/`, codex↔vLLM Responses dialect incompatibility).

## Files
- `env.py` — faithful arcengine driver (`reset`/`step`/`extract_state`). Engine
  plumbing, not the method; object-centric state = list of `{name,tags,x,y,w,h}`.
  Validated: `ls20` loads 127 objects, arrows move the player ±5 (the true dynamics).
- `llm.py` — minimal OpenAI-compatible chat client. `WM_LLM_BASE_URL` /
  `WM_LLM_MODEL` select the backend (Ollama for dev, our Qwen3.6 vLLM for prod).
- `wm.py` — **the method**: `collect_transitions` → `synthesize` (LLM writes
  `transition_function`) → `verify` (exact-replay against the buffer, returns
  counterexamples) → `cegis` (repair loop, admits at 100%).

## Validated (local dev, free, gpt-oss:20b via Ollama)
```
[wm] collected 12 transitions on ls20, actions [1,2,3,4]
[wm] round 1: exact-replay 12/12 (100%) -> ADMITTED in 1 round
```
Synthesized a correct `transition_function` (identifies the mover, exact ±5
deltas). Beats OPINE's own codex-harness gpt-oss run (92%), because the native
loop uses a clean object-centric state and plain chat.

## Run it
```
# dev (free, local):
PYTHONPATH=native:<opine>/src WM_LLM_BASE_URL=http://localhost:11434/v1 \
  WM_LLM_MODEL=gpt-oss:20b python -c "import env,wm; wm.cegis(env.ArcEnv('ls20', '<repo>/environment_files'))"

# prod (our Qwen3.6-27B on a PRO 6000 vLLM, on-instance, no tunnel):
WM_LLM_BASE_URL=http://127.0.0.1:1234/v1 WM_LLM_MODEL=vrfai/Qwen3.6-27B-FP8 ...
```
Needs `arcengine` importable (the game engine) — dev uses the vendored opine venv;
a prod run bundles it like the other GCP runs.

## Next (not built yet)
- **planner**: search the admitted `transition_function` for an action sequence to
  the goal (plan-by-simulation, zero real actions) — the payoff half.
- **full loop**: act → synthesize → verify → plan → execute, across levels, with
  ontology-error η to steer probing.
- **Qwen3.6 run**: point `WM_LLM_*` at our Qwen on a PRO 6000 and compare its
  synthesis quality to gpt-oss (the "does our model do the method" question,
  finally answerable without the codex wall).

## Update: goal refinement + grounded exploration (step 1)
Added `planner.explore_for_reward` (novelty-search the real game via the verified
model, no goal guessing) and an iterative goal-hypothesis loop in `loop.py`
(hypothesize is_goal -> plan -> validate on real game -> feed failure back).

**Honest finding on ls20:** the transition model admits at 16/16, but grounded
exploration reaches only **7 distinct states** (none winning), and goal-guessing
(even with negative feedback) doesn't crack it. Root cause: **exact-replay of a
shallow 16-move probe admits an INCOMPLETE model** -- correct for what it saw
("player moves ±5") but blind to the hidden dynamics ls20's win needs. This is
exactly the problem OPINE's ontology-error η targets (probe where the model is
uncertain to discover new dynamics). The harness correctly *surfaces* the
incompleteness; fully solving needs the η-driven exploration layer (future work):
richer/uncertainty-driven probing to build a COMPLETE model, then plan/explore.

What definitively works today: synthesize -> exact-replay verify -> admit (the
CEGIS core), plan-by-simulation, and grounded exploration + validation -- all
native, on plain chat-completions.
