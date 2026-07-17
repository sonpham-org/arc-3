"""Plan-by-simulation over the verified world model.

Once `wm.cegis` admits a `transition_function` that exactly replays the observed
buffer, we (1) ask the LLM to HYPOTHESIZE the goal as `is_goal(state) -> bool`
(the win condition -- often unobserved during probing, so it is a hypothesis),
and (2) BFS over the verified transition function to find an action sequence that
reaches a goal state -- spending ZERO real actions to search. The plan is then
validated against the real game; any divergence is a counterexample for the next
synthesis round. This is OPINE's plan-by-search half, native.
"""
from __future__ import annotations

import copy
import json
from collections import deque

import llm
from wm import _sandbox_exec, canon

GOAL_SYS = (
    "You infer the WIN CONDITION of a grid game from its objects and dynamics. "
    "State is a list of {'name','tags','x','y','w','h'}. Write "
    "`def is_goal(state):` returning True iff `state` is a solved/winning board. "
    "Base it on object relationships you can infer (e.g. the movable object "
    "reaching/overlapping a target or door object). Only `copy`,`math` importable. "
    "Return ONLY a ```python code block."
)


def synthesize_goal(buffer, actions, transition_code, failed=None):
    sample = buffer[0]["state"] if buffer else []
    names = sorted({o["name"] for o in sample})
    movers = sorted({o["name"] for t in buffer
                     for o in t["next_state"]
                     if o["name"] in {p["name"] for p in t["state"]}
                     and (o["x"], o["y"]) != next(((p["x"], p["y"]) for p in t["state"]
                                                   if p["name"] == o["name"]), (o["x"], o["y"]))})
    # Give the model the full object layout (positions) so it can reason about
    # which target the movable object should reach.
    layout = [{"name": o["name"], "x": o["x"], "y": o["y"], "w": o["w"], "h": o["h"]}
              for o in sample]
    user = (
        f"Object names on the board: {names}\n"
        f"Objects observed to MOVE under actions: {sorted(movers)} (these are the "
        f"agent-controlled pieces; everything else is scenery/targets/walls).\n"
        f"Full initial layout (name,x,y,w,h): {json.dumps(layout)}\n"
        f"The synthesized transition model is:\n```python\n{transition_code}\n```\n"
        f"Hypothesize the win condition as is_goal(state)."
    )
    if failed:
        user += (
            "\n\nEARLIER GOAL HYPOTHESES THAT WERE WRONG (the planned route reached "
            "the described board but the real game did NOT advance the level -- so "
            "these conditions are NOT the win condition; hypothesize a DIFFERENT one):\n"
            + json.dumps(failed[-4:], default=str)[:2500]
        )
    reply = llm.chat([{"role": "system", "content": GOAL_SYS},
                      {"role": "user", "content": user}], max_tokens=4096)
    return llm.extract_code(reply)


def load_is_goal(code):
    # same restricted sandbox as wm, but fetch is_goal instead of transition_function
    import wm
    import builtins as _b

    def _imp(name, *a, **k):
        if name.split(".")[0] in wm.SAFE_MODULES:
            return _b.__import__(name, *a, **k)
        raise ImportError(name)
    sb = {k: getattr(_b, k) for k in (
        "range", "len", "int", "float", "str", "bool", "list", "dict", "tuple",
        "set", "min", "max", "abs", "sum", "sorted", "enumerate", "zip", "map",
        "filter", "any", "all", "isinstance", "getattr", "reversed", "round")}
    sb["__import__"] = _imp
    ns = {"__builtins__": sb}
    exec(compile(code, "<goal>", "exec"), ns, ns)
    fn = ns.get("is_goal")
    if not callable(fn):
        raise ValueError("no is_goal defined")
    return fn


def plan(transition_fn, is_goal_fn, start_state, actions, max_depth=20, max_nodes=50000):
    """BFS over the verified transition function to a goal state. Returns the
    action list, or None if no plan found within the budget."""
    if is_goal_fn(start_state):
        return []
    seen = {tuple(canon(start_state))}
    q = deque([(start_state, [])])
    nodes = 0
    while q and nodes < max_nodes:
        state, path = q.popleft()
        if len(path) >= max_depth:
            continue
        for a in actions:
            nodes += 1
            try:
                nxt = transition_fn(copy.deepcopy(state), a)
            except Exception:
                continue
            if not isinstance(nxt, list):
                continue
            key = tuple(canon(nxt))
            if key in seen:
                continue
            try:
                if is_goal_fn(nxt):
                    return path + [a]
            except Exception:
                pass
            seen.add(key)
            q.append((nxt, path + [a]))
    return None


def explore_for_reward(env, transition_fn, actions, budget=250, log=print):
    """Grounded goal discovery: don't GUESS the unobserved goal -- find it. Use the
    verified transition model to always step toward a state we haven't visited yet
    (novelty search), playing the REAL game, until it advances the level (reward).
    Returns (solved, steps, visited_count). No goal hypothesis needed.
    """
    visited = {tuple(canon(env.extract_state()))}
    for step in range(budget):
        state = env.extract_state()
        # prefer an action whose predicted result is novel; else round-robin
        choice = None
        for a in actions:
            try:
                nxt = transition_fn(copy.deepcopy(state), a)
            except Exception:
                continue
            if isinstance(nxt, list) and tuple(canon(nxt)) not in visited:
                choice = a
                break
        if choice is None:
            choice = actions[step % len(actions)]  # stuck: cycle to jog loose
        _, reward, done = env.step(choice)
        visited.add(tuple(canon(env.extract_state())))
        if done or reward > 0:
            log(f"[explore] REWARD at step {step+1}: level advanced (goal found by exploration).")
            return True, step + 1, len(visited)
    return False, budget, len(visited)


def execute_plan(env, plan_actions, log=print):
    """Run the plan on the REAL game. Returns (advanced, steps, reward_total)."""
    total = 0.0
    for i, a in enumerate(plan_actions):
        _, r, done = env.step(a)
        total += r
        if done:
            log(f"[plan] real game: level advanced at step {i+1}/{len(plan_actions)}")
            return True, i + 1, total
    return False, len(plan_actions), total
