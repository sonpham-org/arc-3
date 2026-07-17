"""Ontology-error (η) driven exploration: build a COMPLETE world model.

The plain CEGIS core admits a model that exactly-replays a FIXED shallow probe --
which can be correct-but-incomplete (it never saw the dynamics it didn't probe).
This layer fixes that: it plays the real game, and whenever the current model
MISPREDICTS a live transition (a surprise == ontology error == a CEGIS
counterexample from reality), it adds that transition and re-synthesizes. Action
selection is steered toward (a) states the model predicts are novel and (b)
under-probed (state, action) pairs -- so probing concentrates where the model is
uncertain or wrong. Converges when the model predicts everything reachable
(η -> 0) or the goal is reached during exploration.

Reuses the native CEGIS core (wm.synthesize / wm.verify) and env; no codex.
"""
from __future__ import annotations

import copy

import wm
from wm import canon


def _sig(state):
    return tuple(canon(state))


def build_complete_model(env, actions, budget=200, resynth_every=8,
                         max_synths=30, log=print):
    """Actively explore to build the most complete verified transition model we
    can within `budget` real steps. Returns the model + buffer + stats, and flags
    if the goal was reached during exploration."""
    buffer = []
    seen_pairs = set()
    visited = {_sig(env.extract_state())}
    tries = {}
    recent_surprise = []
    model_fn = None
    model_code = None
    new_since_synth = 0
    n_synths = 0
    solved = False
    step = 0

    for step in range(budget):
        state = env.extract_state()
        ssig = _sig(state)

        # --- action selection: novelty (per model) minus how often already tried ---
        best_a, best_score = actions[0], None
        for a in actions:
            tried = tries.get((ssig, a), 0)
            bonus = 0
            if model_fn is not None:
                try:
                    pred = model_fn(copy.deepcopy(state), a)
                    if _sig(pred) not in visited:
                        bonus = 10          # model thinks this leads somewhere new
                except Exception:
                    bonus = 6               # model errors here -> worth probing
            score = bonus - tried
            if best_score is None or score > best_score:
                best_score, best_a = score, a
        a = best_a
        tries[(ssig, a)] = tries.get((ssig, a), 0) + 1

        # --- execute in the real game ---
        before = state
        after, reward, done = env.step(a)
        asig = _sig(after)

        # --- η: did the current model mispredict this real transition? ---
        surprise = False
        if model_fn is not None:
            try:
                surprise = _sig(model_fn(copy.deepcopy(before), a)) != asig
            except Exception:
                surprise = True
        recent_surprise = (recent_surprise + [1 if surprise else 0])[-25:]

        pair = (ssig, a)
        if pair not in seen_pairs or surprise:
            buffer.append({"state": before, "action": a, "next_state": after, "reward": reward})
            seen_pairs.add(pair)
            new_since_synth += 1
            if surprise:
                model_fn = None            # stale -> force re-synthesis
        visited.add(asig)

        if reward > 0 or done:
            solved = True
            log(f"[explore] REWARD at step {step+1}: goal reached during exploration.")
            break

        # --- (re)synthesize when the model is stale and enough new data arrived ---
        if model_fn is None and new_since_synth >= resynth_every and len(buffer) >= 4 and n_synths < max_synths:
            code = wm.synthesize(buffer, actions)
            passed, total, _ = wm.verify(code, buffer)
            eta = sum(recent_surprise) / max(1, len(recent_surprise))
            log(f"[explore] step {step+1}: resynth {passed}/{total} exact | buffer={len(buffer)} "
                f"| states={len(visited)} | η(recent-surprise)={eta:.2f}")
            n_synths += 1
            new_since_synth = 0
            if passed == total:
                try:
                    model_fn = wm._sandbox_exec(code)
                    model_code = code
                except Exception:
                    model_fn = None

    eta = sum(recent_surprise) / max(1, len(recent_surprise))
    log(f"[explore] done: solved={solved} steps={step+1} states={len(visited)} "
        f"buffer={len(buffer)} synths={n_synths} final-η={eta:.2f}")
    return {"solved": solved, "model_code": model_code, "buffer": buffer,
            "states_visited": len(visited), "steps": step + 1,
            "eta": eta, "n_synths": n_synths}
