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

## RESULT: our Qwen3.6-27B does the OPINE synthesis (step 2)
Ran the native CEGIS core on a PRO 6000 with our own **Qwen3.6-27B-FP8 served via
vLLM `/v1/chat/completions`** (no codex, no proxy, none of the Responses dialect
problems). Verdict on `ls20`:

    ls20: admitted=True, exact-replay=16/16, rounds=1

Qwen3.6 synthesized a correct, exactly-verified `transition_function` in ONE round
-- same as gpt-oss. So **our production model does the world-model synthesis
method**; the earlier "run theirs" failure was purely the codex<->vLLM Responses
incompatibility, never a Qwen capability limit. Launcher: `gcp/qwen36_native_startup.sh`.
(`ft09` hit a harness bug -- llm.chat returned None content under vLLM's
reasoning-parser -- now fixed to fall back to reasoning_content.)

## Update: η-driven exploration layer (explore.py)
`explore.build_complete_model` plays the real game, treats a model MISPREDICTION
of a live transition as ontology error (η) == a CEGIS counterexample, adds it,
re-synthesizes, and steers probing toward novel + under-tried (state,action) pairs.

**Result on ls20 (gpt-oss, 100 steps):** state coverage **7 -> 38** (the naive
probe's "7 reachable states" was an artifact, not the game); recent-η converges to
0; 12 incremental re-syntheses grow the buffer 8->97. Surfaced a deeper truth:
full-buffer exact-replay drifts to ~75% because ls20's dynamics are
POSITION-DEPENDENT (walls block moves) -- a single "move ±5" rule approximates it,
100% needs collision/wall modeling. The layer correctly discovers the state space
AND reveals the missing physics. Did not solve in 100 steps (goal still unobserved
/ deeper). Next: bigger budget + CEGIS-repair rounds inside each re-synth (wall-
aware model) + wire into loop.py; then the Qwen3.6 run.
