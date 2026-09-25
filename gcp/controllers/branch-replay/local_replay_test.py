"""Local fidelity test: replay every recorded game end to end with NO model (ARC3_BRANCH_REPLAY_ONLY=1) and
check that the rebuilt action sequence equals the recording. Reproduces the startup's harness environment
from the arm's startup.sh, points the runner at the extracted bundle + environment files, and patches the
sandbox for Windows (the 40k-char `-c` bootstrap exceeds the command-line limit; the VM is Linux).

usage: <venv python> local_replay_test.py <arm_dir> <pack_dir> <work_dir> [game-prefix ...]
"""
import json, os, re, subprocess, sys, tempfile, runpy
from pathlib import Path

arm, pack, work = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
only = sys.argv[4:]
BUNDLE = Path(r"D:\codex-work\_branch\bundle"); ENV_FILES = Path(r"D:\codex-work\_branch\code\environment_files")

startup = (arm / "startup.sh").read_text(encoding="utf-8")
harness = startup[startup.index("cd /opt/arc3/ARC3-Inference"):startup.index("PYCHAMPION")] + "\n" + \
    "\n".join(l for l in startup.splitlines() if l.startswith("export ARC3_ROLLING_HALF_CHECKPOINT") or l.startswith("export ARC3_HALF_CONTEXT_SWAP="))
for line in harness.splitlines():
    if line.startswith("export "):
        for m in re.finditer(r'([A-Z0-9_]+)=("[^"]*"|\S*)', line[7:]):
            k, v = m.group(1), m.group(2).strip('"')
            if "$" in v: continue
            os.environ[k] = v
    elif line.startswith("unset "):
        for k in line[6:].split(): os.environ.pop(k, None)
os.environ["LOCAL_ANALYZER_MODEL_ID"] = os.environ["INFERENCE_ANALYZER_MODEL"] = "RadixArk/Qwen3.8-Flash-Next-NVFP4"
os.environ.update({"ARC3_BUNDLE_DIR": str(BUNDLE), "ARC3_WORK_DIR": str(work), "ARC3_ENV_FILES": str(ENV_FILES),
                   "ARC3_BRANCH_PACK": str(work / "pack"), "ARC3_BRANCH_REPLAY_ONLY": "1", "ARC3_BRANCH_LANES": "7",
                   "ARC3_BRANCH_DEADLINE_MIN": "120"})
for k in ("SYSTEMROOT", "TEMP", "TMP"):
    os.environ.setdefault(k, os.environ.get(k, ""))

# replay-only plan: one job per game, replay through its last recorded turn
work.mkdir(parents=True, exist_ok=True)
(work / "pack" / "turns").mkdir(parents=True, exist_ok=True); (work / "pack" / "actions").mkdir(exist_ok=True)
plan = []
for tp in sorted((pack / "turns").glob("*.json")):
    gid = tp.stem
    if only and gid[:4] not in only: continue
    turns = json.loads(tp.read_text(encoding="utf-8")); acts = json.loads((pack / "actions" / f"{gid}.json").read_text(encoding="utf-8"))
    (work / "pack" / "turns" / tp.name).write_text(tp.read_text(encoding="utf-8"), encoding="utf-8")
    (work / "pack" / "actions" / tp.name).write_text(json.dumps(acts), encoding="utf-8")
    plan.append({"job_id": f"{gid[:4]}-fullreplay", "group": gid, "group_index": len(plan), "game_id": gid, "level": 0, "i": 0, "n_turns": len(turns),
                 "replay_through_step": max(t["step"] for t in turns), "live_from_step": None, "effort": "xhigh",
                 "expected_action_count": len(acts), "expected_levels_completed": 99, "orig_remaining_actions": 0, "orig_remaining_turns": 0,
                 "orig_remaining_chars": 0, "orig_segment_wall_s": None, "time_left_s": None, "action_cap_extra": 0, "turn_cap": 0, "time_cap_s": 60})
(work / "pack" / "plan.json").write_text(json.dumps(plan), encoding="utf-8")
res = work / "branch" / "results.jsonl"
if res.exists(): res.unlink()

for repo in sorted((BUNDLE / "src").iterdir(), reverse=True):
    for candidate in (repo / "src", repo):
        if candidate.is_dir(): sys.path.insert(0, str(candidate))
from inference.agent import python_tool_sandbox as m  # noqa: E402
_bs = Path(tempfile.gettempdir()) / "bootstrap_branch.py"; _bs.write_text(m._SANDBOX_BOOTSTRAP, encoding="utf-8")
_Popen = subprocess.Popen
class _P(_Popen):
    def __init__(self, args, *a, **kw):
        if isinstance(args, list) and len(args) >= 4 and args[3] == "-c": args = [args[0], "-I", "-S", str(_bs)]
        super().__init__(args, *a, **kw)
m.subprocess.Popen = _P
_env = m._sandbox_env
m._sandbox_env = lambda: {**_env(), **{k: os.environ[k] for k in ("SYSTEMROOT", "TEMP", "TMP") if os.environ.get(k)}}

# no vLLM locally: estimate token counts (chars/3.5 + image placeholders) instead of POST /tokenize
from inference.agent import full_context_tokens as fct  # noqa: E402
def _count(self, messages, tools, thinking):
    n = len(json.dumps(tools or [])) // 4
    for m in messages:
        c = m.get("content")
        if isinstance(c, str): n += len(c) // 3
        elif isinstance(c, list):
            for part in c:
                n += len(str(part.get("text", ""))) // 3 if part.get("type") == "text" else 1100
        n += len(str(m.get("reasoning") or m.get("reasoning_content") or "")) // 3 + len(json.dumps(m.get("tool_calls") or [])) // 3
    return n
fct.FullContextTokens.count = _count
# Windows has no process groups: the sandbox's timeout kill path calls os.killpg; also give snippets a longer
# wall clock here (Windows pipe I/O makes the replayed action loops several times slower than on the VM).
os.killpg = lambda pid, sig: os.kill(pid, sig)
from inference.agent import tool_agent as _ta  # noqa: E402
_rsp = _ta.run_sandboxed_python
_ta.run_sandboxed_python = lambda *a, **k: _rsp(*a, **{**k, "timeout_seconds": 600})
import shutil
_rm = shutil.rmtree
shutil.rmtree = lambda *a, **k: _rm(*a, **{**k, "ignore_errors": True})   # Windows file-lock race on the sandbox temp dir
import pathlib
pathlib.PosixPath = pathlib.WindowsPath   # the bundle pickles carry PosixPath; Windows cannot instantiate it
runpy.run_path(str(Path(__file__).with_name("branch_runner.py")), run_name="__main__")
print("\n=== RESULTS")
for line in res.read_text(encoding="utf-8").splitlines():
    r = json.loads(line)
    print(r["job_id"], r["status"], "stop=", r.get("stop_reason"), "prefix_ok=", r.get("prefix_ok"), "mismatch_at=", r.get("prefix_mismatch_at"),
          "actions=", r.get("final_action_count"), "/", r["expected_action_count"], "levels=", r.get("final_levels_completed"), "replay_requests=", r.get("replay_requests"),
          "wall=", r.get("wall_s"), (r.get("error") or "")[:300])
