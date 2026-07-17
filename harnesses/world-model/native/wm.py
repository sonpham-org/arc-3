"""Native world-model core: the OPINE method reproduced in our own code.

Given observed (state, action, next_state) transitions from a real ARC game, ask
the LLM to SYNTHESIZE an executable `transition_function(state, action_id)`, then
ADMIT it only if it reproduces every observed transition EXACTLY (CEGIS). On a
mismatch, feed the counterexamples back and re-synthesize. No codex, no Responses
API -- plain chat-completions (llm.chat), so it runs on our Qwen3.6 via vLLM.

State is object-centric: a list of {name, tags, x, y, w, h} records.
"""
from __future__ import annotations

import json

import llm

SAFE_MODULES = {"copy", "math", "collections", "itertools", "functools"}


def canon(state):
    """Order-independent canonical form for exact comparison."""
    return sorted((str(o.get("name", "")), int(o.get("x", 0)), int(o.get("y", 0)),
                   int(o.get("w", 0)), int(o.get("h", 0))) for o in state)


def collect_transitions(env, n=12, actions=None):
    """Probe the game to gather transitions. Cycles the available actions (a
    simple diverse probe) and records every (state, action, next_state)."""
    acts = actions or [a for a in env.available_actions() if a not in (0, 7)]
    buf = []
    for i in range(n):
        a = acts[i % len(acts)]
        before = env.extract_state()
        after, reward, done = env.step(a)
        buf.append({"state": before, "action": a, "next_state": after, "reward": reward})
        if done:
            break
    return buf


def _sandbox_exec(code):
    """Exec synthesized code with a restricted namespace; return its
    transition_function. Allows only a safe import whitelist."""
    import builtins as _b

    def _imp(name, *a, **k):
        root = name.split(".")[0]
        if root in SAFE_MODULES:
            return _b.__import__(name, *a, **k)
        raise ImportError(f"import '{name}' not allowed in synthesized model")

    safe_builtins = {k: getattr(_b, k) for k in (
        "range", "len", "int", "float", "str", "bool", "list", "dict", "tuple",
        "set", "min", "max", "abs", "sum", "sorted", "enumerate", "zip", "map",
        "filter", "any", "all", "isinstance", "getattr", "setattr", "dict",
        "reversed", "round", "print", "Exception", "ValueError", "KeyError",
    )}
    safe_builtins["__import__"] = _imp
    ns = {"__builtins__": safe_builtins}
    exec(compile(code, "<synth_model>", "exec"), ns, ns)
    fn = ns.get("transition_function")
    if not callable(fn):
        raise ValueError("no transition_function defined")
    return fn


def verify(code, buffer):
    """Exact-replay: run T on every transition; return (passed, total, counterexamples)."""
    try:
        fn = _sandbox_exec(code)
    except Exception as e:
        return 0, len(buffer), [{"error": f"model failed to load: {e}"}]
    passed, cxs = 0, []
    import copy as _copy
    for t in buffer:
        try:
            pred = fn(_copy.deepcopy(t["state"]), t["action"])
        except Exception as e:
            cxs.append({"action": t["action"], "error": str(e)})
            continue
        if isinstance(pred, list) and canon(pred) == canon(t["next_state"]):
            passed += 1
        else:
            cxs.append({
                "action": t["action"],
                "state": t["state"],
                "expected_next": t["next_state"],
                "got_next": pred if isinstance(pred, list) else repr(pred)[:200],
            })
    return passed, len(buffer), cxs


SYNTH_SYS = (
    "You are a world-model synthesizer for a grid game. You are given observed "
    "transitions and must write ONE Python function that reproduces them EXACTLY.\n"
    "State is a list of object records: {'name': str, 'tags': list, 'x': int, "
    "'y': int, 'w': int, 'h': int}. Actions are integers.\n"
    "Write `def transition_function(state, action_id):` that returns the NEW state "
    "(same list-of-records format). Deep-copy the input; do not mutate it. Infer "
    "which object(s) move and the rule for each action from the data. Only `copy`, "
    "`math`, `collections`, `itertools`, `functools` may be imported.\n"
    "Return ONLY a ```python code block."
)


def _diff_summary(t):
    """Compact per-transition summary: which objects moved."""
    b = {o["name"]: (o["x"], o["y"]) for o in t["state"]}
    a = {o["name"]: (o["x"], o["y"]) for o in t["next_state"]}
    moved = {n: [b[n], a[n]] for n in a if n in b and b[n] != a[n]}
    return {"action": t["action"], "moved": moved, "reward": t.get("reward", 0)}


def synthesize(buffer, actions, counterexamples=None, prev_code=None):
    diffs = [_diff_summary(t) for t in buffer]
    sample_state = buffer[0]["state"] if buffer else []
    user = (
        f"Actions available: {actions}\n"
        f"Initial state has {len(sample_state)} objects. Example objects: "
        f"{json.dumps(sample_state[:6])}\n\n"
        f"Observed transitions (which objects moved per action):\n"
        f"{json.dumps(diffs, indent=1)}\n"
    )
    if prev_code and counterexamples:
        user += (
            f"\nYour PREVIOUS model was:\n```python\n{prev_code}\n```\n"
            f"It FAILED these transitions (counterexamples). For each: the state, the "
            f"action, what you predicted, and the correct next state:\n"
            f"{json.dumps(counterexamples[:4], default=str)[:3000]}\n"
            f"Fix the rule so ALL observed transitions replay exactly.\n"
        )
    reply = llm.chat([{"role": "system", "content": SYNTH_SYS},
                      {"role": "user", "content": user}], max_tokens=8192)
    return llm.extract_code(reply)


def cegis(env, n_transitions=12, max_rounds=3, log=print):
    """Collect transitions, then synthesize->verify->repair until admitted."""
    buf = collect_transitions(env, n=n_transitions)
    actions = [a for a in env.available_actions() if a not in (0, 7)]
    log(f"[wm] collected {len(buf)} transitions on actions {actions}")
    code, best = None, (0, len(buf), [])
    for r in range(max_rounds):
        code = synthesize(buf, actions,
                          counterexamples=best[2] if r else None,
                          prev_code=code if r else None)
        passed, total, cxs = verify(code, buf)
        log(f"[wm] round {r+1}: exact-replay {passed}/{total} "
            f"({100*passed//max(1,total)}%), {len(cxs)} counterexamples")
        best = (passed, total, cxs)
        if passed == total:
            log("[wm] ADMITTED: model replays the full buffer exactly.")
            return {"code": code, "passed": passed, "total": total, "admitted": True, "rounds": r + 1}
    return {"code": code, "passed": best[0], "total": best[1], "admitted": False, "rounds": max_rounds}
