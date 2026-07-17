"""The solver: turn a verified world model into cleared levels.

Grounded, no goal-guessing. Build the best wall-aware transition model we can
(multi-round CEGIS on a wall-hitting probe), then use it to EXPLORE the real game
efficiently: from the current state, plan (in simulation, free) the shortest path
to a real state we have not visited yet, walk it on the real game, and repeat --
resetting the level (action 0) when the move budget runs out. A step that yields
reward == the level is solved (and the goal is discovered, not hypothesized). Live
mispredictions are ontology-error counterexamples that trigger re-synthesis.
"""
from __future__ import annotations

import copy
from collections import deque

import wm
from wm import canon


def _sig(s):
    return tuple(canon(s))


def build_wall_aware_model(env, actions, reps=3, runlen=6, rounds=6, log=print):
    """Probe by running each direction into walls (generates block transitions),
    then multi-round CEGIS. Returns (model_fn, code, buffer, exact_frac)."""
    buf = []
    for _ in range(reps):
        for a in actions:
            for _ in range(runlen):
                before = env.extract_state()
                after, r, done = env.step(a)
                buf.append({"state": before, "action": a, "next_state": after, "reward": r})
                if env.is_over():
                    env.step(0)
    blocked = sum(1 for t in buf if _sig(t["state"]) == _sig(t["next_state"]))
    log(f"[solve] probe buffer={len(buf)} ({blocked} blocked/wall transitions)")
    code, best = None, (0, len(buf), [], None)
    for rnd in range(rounds):
        code = wm.synthesize(buf, actions,
                             counterexamples=best[2] if rnd else None,
                             prev_code=best[3] if (rnd and best[0] > 0) else None)
        p, t, cx = wm.verify(code, buf)
        log(f"[solve] model round {rnd+1}: exact-replay {p}/{t} ({100*p//max(1,t)}%)")
        if p >= best[0]:
            best = (p, t, cx, code)
        if p == t:
            break
    fn = None
    try:
        fn = wm._sandbox_exec(best[3])
    except Exception as e:
        log(f"[solve] best model won't load: {e}")
    return fn, best[3], buf, best[0] / max(1, best[1])


def _plan_to_unvisited(model_fn, start_state, actions, visited, max_nodes=20000):
    """BFS in the model for the shortest action path to a state not in `visited`."""
    start = _sig(start_state)
    q = deque([(start_state, [])])
    seen = {start}
    nodes = 0
    while q and nodes < max_nodes:
        state, path = q.popleft()
        for a in actions:
            nodes += 1
            try:
                nxt = model_fn(copy.deepcopy(state), a)
            except Exception:
                continue
            if not isinstance(nxt, list):
                continue
            k = _sig(nxt)
            if k in seen:
                continue
            if k not in visited:
                return path + [a]      # a real state the model thinks is new
            seen.add(k)
            q.append((nxt, path + [a]))
    return None


def solve_level(env, actions, model_fn, max_steps=600, log=print):
    """Model-guided frontier exploration of the REAL game until reward."""
    visited = {_sig(env.extract_state())}
    cxs = []
    steps = 0
    while steps < max_steps:
        if env.is_over():
            env.step(0)
        state = env.extract_state()
        plan = _plan_to_unvisited(model_fn, state, actions, visited)
        if not plan:
            # model thinks nothing new is reachable from here; jog with each action
            plan = actions
        for a in plan:
            if steps >= max_steps:
                break
            before = env.extract_state()
            try:
                pred = _sig(model_fn(copy.deepcopy(before), a))
            except Exception:
                pred = None
            after, reward, done = env.step(a)
            steps += 1
            asig = _sig(after)
            if pred is not None and pred != asig:
                cxs.append({"state": before, "action": a, "next_state": after})  # η counterexample
            visited.add(asig)
            if reward > 0 or done:
                log(f"[solve] REWARD at step {steps}: level SOLVED (goal discovered).")
                return {"solved": True, "steps": steps, "visited": len(visited), "cxs": cxs}
            if env.is_over():
                env.step(0)
                break
    log(f"[solve] no reward in {steps} steps; {len(visited)} states visited, {len(cxs)} live mispredicts")
    return {"solved": False, "steps": steps, "visited": len(visited), "cxs": cxs}


def solve_game(env, actions=None, model_steps_reps=3, explore_steps=600, log=print):
    acts = actions or [a for a in env.available_actions() if a not in (0, 7)]
    env.reset()
    model_fn, code, buf, frac = build_wall_aware_model(env, acts, reps=model_steps_reps, log=log)
    log(f"[solve] wall-aware model exact-replay {frac*100:.0f}%")
    if model_fn is None:
        return {"solved": False, "stage": "model", "model_frac": frac}
    env.step(0)  # reset level for a clean solve budget
    res = solve_level(env, acts, model_fn, max_steps=explore_steps, log=log)
    res.update({"model_frac": frac, "stage": "solve"})
    return res
