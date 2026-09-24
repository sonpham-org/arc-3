"""Local smoke test of the patched sandbox for one v2 arm: real subprocess, fake host handlers.

usage: python smoke_v2.py <patched_src_root> <arm>
"""
import importlib.util
import json
import sys
from pathlib import Path

root = Path(sys.argv[1]).resolve()
arm = sys.argv[2]
sys.path.insert(0, str(root))
spec = importlib.util.spec_from_file_location("ptsb", root / "inference/agent/python_tool_sandbox.py")
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
import os, subprocess, tempfile
# Windows: 42k-char `-c` exceeds the command-line limit; the VM (Linux) has no such limit. Run the bootstrap from a file here.
_bs = Path(tempfile.gettempdir()) / f"bootstrap_{arm}.py"
_bs.write_text(m._SANDBOX_BOOTSTRAP, encoding="utf-8")
_Popen = subprocess.Popen
class _P(_Popen):
    def __init__(self, args, *a, **kw):
        if isinstance(args, list) and len(args) >= 4 and args[3] == "-c":
            args = [args[0], "-I", "-S", str(_bs)]
        super().__init__(args, *a, **kw)
m.subprocess.Popen = _P
_orig_env = m._sandbox_env
m._sandbox_env = lambda: {**_orig_env(), **{k: os.environ[k] for k in ("SYSTEMROOT", "TEMP", "TMP", "PATHEXT", "COMSPEC") if k in os.environ}}


def frame(pos, step):
    g = [[0, 0, 0], [0, 0, 0], [0, 0, 0]]
    g[1][pos] = 1
    return {"ascii": "\n".join("".join(str(v) for v in r) for r in g), "step": step, "level": 1, "shape": [3, 3], "grid": g}


pos = 1
history = [{"action": "", "frame": frame(0, 0)}, {"action": "RIGHT", "frame": frame(1, 1)}]


def state():
    return {"current_frame": history[-1]["frame"], "history": history, "valid_actions": ["LEFT", "RIGHT"],
            "last_action_result": {"executed": True, "board_changed": True}}


def act(actions):
    global pos
    for a in actions:
        if a["action"] == "RIGHT":
            pos = min(2, pos + 1)
        elif a["action"] == "LEFT":
            pos = max(0, pos - 1)
        history.append({"action": a["action"], "frame": frame(pos, len(history))})
    return {"action_result": {"executed": True, "board_changed": True}, "state": state(), "interrupt_execution": False}


def run(code):
    r = m.run_sandboxed_python(code=code, timeout_seconds=20, initial_state=state(), action_handler=act, store_key="game-x")
    out = (r.get("stdout") or "").strip()
    err = r.get("error")
    print("---", (err or "ok")[:400])
    if out:
        print(out[:1200])
    return r


if arm == "execution_v2":
    run("print(sorted(store)); save(code='def predict(f, a):\\n    g=[list(r) for r in f._grid]\\n    c=g[1].index(1)\\n    n=min(2,c+1) if a==\"RIGHT\" else max(0,c-1)\\n    g[1][c]=0; g[1][n]=1\\n    return g\\n'); print(verify(predict))")
    run("print('predict' in globals(), store.get('verify'))\nprint(action(['RIGHT']))")            # auto-check passes (pos 1->2)
    run("save(code='def predict(f, a):\\n    return [(0,0,7)]\\n')\nprint(verify(predict))\naction(['LEFT'])")  # mismatch halts
    run("action(['LEFT','LEFT'])")  # batch gate: fidelity 0 -> cut to 1
elif arm == "memory_v2":
    run("print(rule('r1', 'the 1 moves right on RIGHT', 'lambda t: (t.after_frame._grid[1].index(1) == min(2, t.before_frame._grid[1].index(1)+1)) if t.action==\"RIGHT\" else None'))")
    run("print(rules())\nprint(rule('bad', 'board never changes', 'lambda t: t.after_frame._grid == t.before_frame._grid'))")
    run("action(['LEFT'])\nprint(rules()['bad']['status'], rules()['r1']['support'])")
    run("print(drop('bad')); print(sorted(rules()))")
elif arm == "symbolic_v2":
    run("save(code='def encode(f):\\n    return {\"x\": f._grid[1].index(1)}\\ndef step(s, a):\\n    if a==\"RIGHT\": return {\"x\": min(2, s[\"x\"]+1)}\\n    if a==\"LEFT\": return {\"x\": max(0, s[\"x\"]-1)}\\n    return None\\n'); print(replay())")
    run("print(plan(lambda s: s['x']==0, max_depth=5))")
    run("print(action(['LEFT']))")  # auto-check ok
    run("print(action(['LEFT','LEFT']))")  # gate: replay had only 1 transition -> cut to 1
    run("print(replay()); print(action(['RIGHT','RIGHT']))")  # now >=3 transitions and fidelity 1 -> batch allowed
print("store:", json.dumps(m._CODE_STORES.get("game-x", {}))[:300])
