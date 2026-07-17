"""Click-aware, general world model + solver.

The movement-only core (wm.py) can't touch point-and-click games (tn36/vc33/lp85:
actions [0,6,7]). Here actions are dicts {'id','x','y'} -- directional OR a CLICK
(id 6) at (x,y) -- and the synthesized `transition_function(state, action)` models
GENERAL object changes (appear/disappear/recolor/move), not just one moving agent.
Same CEGIS contract: admit only on exact replay. Runs on plain chat (llm.chat).
"""
from __future__ import annotations

import copy
import json

import llm
from wm import SAFE_MODULES, canon


def _changed(t):
    """Objects that differ between state and next_state (exact-tuple multiset diff),
    plus the action (with click coords). This is the signal the model learns from."""
    bc, ac = canon(t["state"]), canon(t["next_state"])
    from collections import Counter
    cb, ca = Counter(bc), Counter(ac)
    removed = list((cb - ca).elements())
    added = list((ca - cb).elements())
    return {"action": t["action"], "removed": removed[:10], "added": added[:10]}


GEN_SYS = (
    "You synthesize an EXACT world model for a grid game. Given observed transitions, "
    "write ONE Python function reproducing them all exactly.\n"
    "State is a list of object records {'name','tags','x','y','w','h'}. An action is a "
    "dict {'id': int, 'x': int|None, 'y': int|None}. id 1-5 are directional; id 6 is a "
    "CLICK at (x,y).\n"
    "Write `def transition_function(state, action):` returning the NEW state (same "
    "format). Deep-copy input; never mutate it. Model GENERAL effects -- objects may "
    "move, appear, disappear, or change (name/size) -- especially: a CLICK usually "
    "affects the object located AT (x,y) (find the object whose box contains x,y and "
    "apply the observed change). Infer the rule from the removed/added object records "
    "per action. Only copy, math, collections, itertools, functools importable. "
    "Return ONLY a ```python code block."
)


def collect_general(env, n=28):
    """Probe with the generalized candidate actions (directional + salient clicks)."""
    buf = []
    for i in range(n):
        state = env.extract_state()
        cands = env.candidate_actions(state)
        a = cands[i % len(cands)] if cands else {"id": 0, "x": None, "y": None}
        after, r, done = env.apply(a)
        buf.append({"state": state, "action": a, "next_state": after, "reward": r})
        if env.is_over():
            env.step(0)
    return buf


def _sandbox_general(code):
    import builtins as _b

    def _imp(name, *a, **k):
        if name.split(".")[0] in SAFE_MODULES:
            return _b.__import__(name, *a, **k)
        raise ImportError(name)
    sb = {k: getattr(_b, k) for k in (
        "range", "len", "int", "float", "str", "bool", "list", "dict", "tuple",
        "set", "min", "max", "abs", "sum", "sorted", "enumerate", "zip", "map",
        "filter", "any", "all", "isinstance", "getattr", "reversed", "round",
        "Exception", "ValueError", "KeyError")}
    sb["__import__"] = _imp
    ns = {"__builtins__": sb}
    exec(compile(code, "<gen_model>", "exec"), ns, ns)
    fn = ns.get("transition_function")
    if not callable(fn):
        raise ValueError("no transition_function")
    return fn


def verify_general(code, buffer):
    try:
        fn = _sandbox_general(code)
    except Exception as e:
        return 0, len(buffer), [{"error": f"load: {e}"}]
    passed, cxs = 0, []
    for t in buffer:
        try:
            pred = fn(copy.deepcopy(t["state"]), copy.deepcopy(t["action"]))
        except Exception as e:
            cxs.append({"action": t["action"], "error": str(e)})
            continue
        if isinstance(pred, list) and canon(pred) == canon(t["next_state"]):
            passed += 1
        else:
            cxs.append({"action": t["action"], "removed_expected": _changed(t)["removed"],
                        "added_expected": _changed(t)["added"]})
    return passed, len(buffer), cxs


def synthesize_general(buffer, counterexamples=None, prev_code=None):
    rows = [_changed(t) for t in buffer if _changed(t)["removed"] or _changed(t)["added"]]
    noops = sum(1 for t in buffer if not _changed(t)["removed"] and not _changed(t)["added"])
    sample = buffer[0]["state"][:8] if buffer else []
    user = (
        f"Example objects: {json.dumps(sample)}\n"
        f"{noops} observed actions changed NOTHING (no-ops). Transitions that DID "
        f"change something (action + removed/added object records):\n{json.dumps(rows)[:6500]}\n"
    )
    if prev_code and counterexamples:
        user += (f"\nPrevious model:\n```python\n{prev_code}\n```\nFAILED:\n"
                 f"{json.dumps(counterexamples[:5], default=str)[:3000]}\nFix it.\n")
    reply = llm.chat([{"role": "system", "content": GEN_SYS},
                      {"role": "user", "content": user}], max_tokens=8192)
    return llm.extract_code(reply)


def cegis_general(env, n=28, rounds=5, log=print):
    buf = collect_general(env, n=n)
    changed = sum(1 for t in buf if _changed(t)["removed"] or _changed(t)["added"])
    log(f"[gen] buffer={len(buf)} ({changed} state-changing actions)")
    code, best = None, (0, len(buf), [], None)
    for r in range(rounds):
        code = synthesize_general(buf, counterexamples=best[2] if r else None,
                                  prev_code=best[3] if (r and best[0] > 0) else None)
        p, t, cx = verify_general(code, buf)
        log(f"[gen] round {r+1}: exact-replay {p}/{t} ({100*p//max(1,t)}%)")
        if p >= best[0]:
            best = (p, t, cx, code)
        if p == t:
            break
    return {"code": best[3], "passed": best[0], "total": best[1],
            "admitted": best[0] == best[1], "buffer": buf}


def explore_general(env, model_fn, max_steps=400, log=print):
    """Model-guided novelty exploration with generalized (click) actions until reward."""
    visited = {tuple(canon(env.extract_state()))}
    for step in range(max_steps):
        if env.is_over():
            env.step(0)
        state = env.extract_state()
        cands = env.candidate_actions(state)
        # prefer an action the model predicts leads somewhere novel
        choice = None
        for a in cands:
            try:
                pred = model_fn(copy.deepcopy(state), copy.deepcopy(a))
                if isinstance(pred, list) and tuple(canon(pred)) not in visited:
                    choice = a
                    break
            except Exception:
                continue
        if choice is None:
            choice = cands[step % len(cands)] if cands else {"id": 0, "x": None, "y": None}
        _, reward, done = env.apply(choice)
        visited.add(tuple(canon(env.extract_state())))
        if reward > 0 or done:
            log(f"[gen] REWARD at step {step+1}: SOLVED via click exploration.")
            return {"solved": True, "steps": step + 1, "visited": len(visited)}
    return {"solved": False, "steps": max_steps, "visited": len(visited)}
