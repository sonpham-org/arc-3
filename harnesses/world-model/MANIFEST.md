# world-model — STUB (not built yet)

A **different harness**, not a toggle: an OPINE-World-style agent that synthesizes the
game's dynamics as **verifiable executable Python** and plans by searching the verified
program — the paradigm that scored 20/25 won, mean 78.4 (vs our baseline ≈1.21).
Ref: https://david-courtis.github.io/opine-world/

This gets its **own folder / own loop** because it doesn't share the graft agent loop.

## Core idea to build
- A world-modeler that writes `T(state, action) -> next_state` in Python and **admits a
  candidate only when it exactly replays the whole transition buffer** (`T̂(s,a)=s′` for
  every observed transition).
- **Plan by simulating** candidate action sequences inside the verified `T` (zero real
  actions spent) — "search the verified program."
- Object-centric state with persistent tracking keys (our `segmentation` hashes are ~κ)
  and abstracted effects (`x:12→15` → `'x'`) so dynamics generalize across objects/levels.
- Uncertainty-driven exploration (`ontology error η`): act where the model mispredicts.

## Two ways to prototype (decide before building)
1. **Light / on baseline (competition-legal, offline Qwen):** an env-toggle
   `WORLD_MODEL_SYNTH=1` that prompts the existing agent to maintain + exact-replay-verify
   a Python `T` in its `world_model` and plan by simulating. Cheap to try; Qwen-27B may
   only partially manage the code synthesis. Would live as a `frame-full`-style patch.
2. **Full / new loop (research, needs a stronger reasoning model):** a two-agent
   actor + world-modeler over a shared replay buffer, full source here. Higher ceiling;
   pair with a stronger local model (gemma/nemotron track). Not Kaggle-legal if it needs
   a frontier API model.

## Status
**Native core WORKS** (`native/`): OPINE's synthesize->exact-replay-verify->CEGIS
loop reproduced in our own code, plain chat-completions (no codex/Responses). On
`ls20` with gpt-oss it admits a correct `transition_function` at 12/12 exact-replay
in 1 round. Runs on any /v1/chat/completions -> ready for our Qwen3.6 via vLLM.
Still to build: planner (plan-by-simulation) + full act/verify/plan loop. The
run-theirs path (`opine-port/`) is shelved -- codex<->vLLM Responses is incompatible.

### Prior status
# Status
**In progress — "run theirs first, then port" (Track B).** OPINE's own code runs
in scratchpad; `opine-port/` records the patch that makes it run on our local
models (its backends were hard-wired to hosted OpenAI/Anthropic). codex↔Ollama
transport proven; backend patched + unit-verified. Next: smoke-run the loop on
`ls20` with gpt-oss:20b (free, on the 4090), then repoint to our Qwen on a PRO
6000 via `OPINE_CODEX_BASE_URL`. Native reimplementation in this folder is the
step after understanding the live loop. Validated score: n/a.

See `opine-port/README.md` for the run recipe and the key integration facts.
