"""Local smoke test of the mode patch: sandbox gates (cap, expect requirement) with a fake host, and the
router's prepare/strip round trip + policy. usage: python smoke_modes.py <patched_src_root>"""
import importlib.util, json, os, subprocess, sys, tempfile
from pathlib import Path

root = Path(sys.argv[1]).resolve(); sys.path.insert(0, str(root))
spec = importlib.util.spec_from_file_location("ptsb", root / "inference/agent/python_tool_sandbox.py")
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
# Windows: the 40k-char `-c` bootstrap exceeds the command-line limit; the VM is Linux. Run it from a file here.
_bs = Path(tempfile.gettempdir()) / "bootstrap_modes.py"; _bs.write_text(m._SANDBOX_BOOTSTRAP, encoding="utf-8")
_Popen = subprocess.Popen
class _P(_Popen):
    def __init__(self, args, *a, **kw):
        if isinstance(args, list) and len(args) >= 4 and args[3] == "-c": args = [args[0], "-I", "-S", str(_bs)]
        super().__init__(args, *a, **kw)
m.subprocess.Popen = _P
_env = m._sandbox_env
m._sandbox_env = lambda: {**_env(), **{k: os.environ[k] for k in ("SYSTEMROOT", "TEMP", "TMP") if k in os.environ}}

def frame(pos, step):
    g = [[0, 0, 0], [0, 0, 0], [0, 0, 0]]; g[1][pos] = 1
    return {"ascii": "\n".join("".join(str(v) for v in r) for r in g), "step": step, "level": 1, "shape": [3, 3], "grid": g}
pos = 1; history = [{"action": "", "frame": frame(0, 0)}, {"action": "RIGHT", "frame": frame(1, 1)}]
def state(): return {"current_frame": history[-1]["frame"], "history": history, "valid_actions": ["LEFT", "RIGHT"], "last_action_result": {"executed": True}}
def act(actions):
    global pos
    for a in actions:
        pos = min(2, pos + 1) if a["action"] == "RIGHT" else max(0, pos - 1)
        history.append({"action": a["action"], "frame": frame(pos, len(history))})
    return {"action_result": {"executed": True, "board_changed": True}, "state": state(), "interrupt_execution": False}
def run(code, gates):
    r = m.run_sandboxed_python(code=code, timeout_seconds=20, initial_state=state(), action_handler=act, mode_gates=gates)
    print(f"--- gates={gates} -> {(r.get('error') or 'ok')[:160]} | {(r.get('stdout') or '').strip()[:200]} | verdicts={[x.get('prediction_check',{}).get('status') for x in r.get('action_results') or []]}")

print("== act: legacy, no cap notice for 3 actions")
run("print(action(['LEFT','RIGHT','LEFT'])['executed'])", {"action_cap": 14, "prediction_required": False})
print("== probe: cap 1 cuts a batch of 3 to 1")
run("action(['RIGHT','RIGHT','RIGHT']); print('after', current_frame._grid[1])", {"action_cap": 1, "prediction_required": False})
print("== verify: action without expect is refused")
run("action(['LEFT'])", {"action_cap": 14, "prediction_required": True})
print("== verify: correct expect passes")
run("expect(lambda b,a,af,r: af._grid[1].index(1)==max(0,b._grid[1].index(1)-1) and af._grid!=b._grid); print(action(['LEFT'])['prediction_check'])", {"action_cap": 14, "prediction_required": True})
print("== verify: trivial expect halts")
run("expect(lambda b,a,af,r: True); action(['RIGHT'])", {"action_cap": 14, "prediction_required": True})

print("== router: prepare/strip round trip and policy")
spec2 = importlib.util.spec_from_file_location("mr", root / "inference/agent/budget_reminder.py"); mr = importlib.util.module_from_spec(spec2); spec2.loader.exec_module(mr)
st = mr.ModeState(); router = mr.ModeRouter("router")
msgs = [{"role": "system", "content": "S"}, {"role": "user", "content": "frame 1"}]
seq = []
for turn in range(12):
    req, info = router.prepare(msgs, st); seq.append(info["mode"])
    assert mr.strip_modes(req) == msgs, "strip must restore the persistent history"
    if turn == 6: st.note_actions(90, False)
    if turn >= 7: st.note_verdicts(["passed"])
print("router modes over 12 turns:", seq)
assert seq[:6] == ["probe"] * 6 and "verify" in seq and seq[-1] == "batch", seq
fixed = mr.ModeRouter("verify"); req, info = fixed.prepare(msgs, mr.ModeState()); assert "[Turn mode: verify]" in req[-1]["content"] and "[Turn mode" not in mr.strip_modes(req)[-1]["content"]
print("router OK")
