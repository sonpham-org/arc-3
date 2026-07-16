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
Not started. `../README.md` has the build rules. Validated score: n/a.
