"""Local fidelity test for the RL try runner: no model, no GPU.

Builds the try runner exactly as derive_tries.py does (the seed arm's runner preamble + try_driver.py), with the
/opt/arc3 paths pointed at local copies, queues moments whose source is a finished (or growing) seed-run transcript,
and runs it in replay-only mode. Every try must rebuild the game exactly up to its fork turn (turn-by-turn action
numbers match the transcript, then the action count and level at the switch match the moment) and stop there.

Windows differences are patched exactly as gcp/controllers/live-injection/local_fork_test.py does (sandbox bootstrap
through a file, no process groups, token counts estimated, rmtree tolerant, PosixPath).

usage: <harness venv python> local_try_test.py <seed arm dir> <bundle dir> <env files dir> <work dir> \
           <game_id>:<fork_step>:<level>:<transcript path> [...]
"""
import json
import os
import re
import runpy
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
CTRL = HERE.parent
arm, bundle, env_files, work = (Path(x) for x in sys.argv[1:5])
wanted = [w.split(":", 3) for w in sys.argv[5:]]
TAIL = ('asyncio.run(bm.run(soft_end_time=soft_end, runtime_environment=target, minimal_diagnostics=False))\n'
        'print("V12 RUN COMPLETE")\n')

startup = (arm / "startup.sh").read_text(encoding="utf-8")
harness = startup[startup.index("cd /opt/arc3/ARC3-Inference"):startup.index("PYCHAMPION")] + "\n" + \
    "\n".join(l for l in startup.splitlines() if l.startswith("export ARC3_ROLLING_HALF_CHECKPOINT")
              or l.startswith("export ARC3_HALF_CONTEXT_SWAP=") or l.startswith("export ARC3_MAX_RUNTIME")
              or l.startswith("export ARC3_BENCHMARK_CONCURRENCY"))
for line in harness.splitlines():
    if line.startswith("export "):
        for m in re.finditer(r'([A-Z0-9_]+)=("[^"]*"|\S*)', line[7:]):
            k, v = m.group(1), m.group(2).strip('"')
            if "$" not in v:
                os.environ[k] = v
    elif line.startswith("unset "):
        for k in line[6:].split():
            os.environ.pop(k, None)
os.environ.setdefault("ARC3_MAX_RUNTIME_S_PER_GAME", "7920")
os.environ.setdefault("ARC3_BENCHMARK_CONCURRENCY", "25")
os.environ["LOCAL_ANALYZER_MODEL_ID"] = os.environ["INFERENCE_ANALYZER_MODEL"] = "RadixArk/Qwen3.8-Flash-Next-NVFP4"

if work.exists():
    shutil.rmtree(work, ignore_errors=True)
work.mkdir(parents=True)
pack = work / "_pack"
pack.mkdir()
for f in (HERE / "rl_reward.py", HERE / "rl_tree.py", HERE / "lake.py", CTRL / "branch-replay" / "branch_parse.py",
          CTRL.parent / "arc3_firestore_scores.py", CTRL.parent / "arc3_minute_score_observer.py"):
    shutil.copy(f, pack / f.name)
qroot = work / "_queue"
for game_id, step, level, tpath in wanted:
    mid = f"local-{game_id[:4]}-t{int(step):04d}"
    job = {"moment_id": mid, "game_id": game_id, "fork_step": int(step), "level": int(level), "n": 1,
           "transcript_uri": str(Path(tpath).resolve()), "policy_id": "base", "harness_id": "local",
           "source_episode_id": None, "human": [],
           "moment": {"id": mid, "game": game_id[:4], "level": int(level), "human_actions": 10,
                      "level_actions_before": 0, "campaign": "localtest", "ref_remaining_tokens": 0}}
    (qroot / "jobs").mkdir(parents=True, exist_ok=True)
    (qroot / "jobs" / f"{mid}.json").write_text(json.dumps(job))

runner = (arm / "runner.py").read_text(encoding="utf-8")
assert runner.endswith(TAIL), "seed runner tail drift"
for old, new in (('BUNDLE = Path("/opt/arc3/bundle")', 'BUNDLE = Path(os.environ["ARC3_BUNDLE_DIR"])'),
                 ('WORKING = Path("/opt/arc3/work")', 'WORKING = Path(os.environ["ARC3_WORK_DIR"])'),
                 ('ENV_FILES = "/opt/arc3/environment_files"', 'ENV_FILES = os.environ["ARC3_ENV_FILES"]')):
    assert runner.count(old) == 1, old
    runner = runner.replace(old, new)
runner = runner[:-len(TAIL)] + (HERE / "try_driver.py").read_text(encoding="utf-8")
(work / "_runner.py").write_text(runner, encoding="utf-8")

os.environ.update({"ARC3_BUNDLE_DIR": str(bundle), "ARC3_WORK_DIR": str(work), "ARC3_ENV_FILES": str(env_files),
                   "ARC3_TRY_PACK": str(pack), "ARC3_TRY_CAMPAIGN": "localtest", "ARC3_TRY_VM": "local",
                   "ARC3_TRY_LANES": "4", "ARC3_TRY_DEADLINE_MIN": "240", "ARC3_TRY_POLL_S": "2",
                   "ARC3_TRY_LOCAL_ROOT": str(qroot), "ARC3_TRY_REPLAY_ONLY": "1", "ARC3_TRY_EXIT_WHEN_IDLE": "1"})
for repo in sorted((bundle / "src").iterdir(), reverse=True):
    for candidate in (repo / "src", repo):
        if candidate.is_dir():
            sys.path.insert(0, str(candidate))
from inference.agent import python_tool_sandbox as m  # noqa: E402
_bs = Path(tempfile.gettempdir()) / "bootstrap_try.py"
_bs.write_text(m._SANDBOX_BOOTSTRAP, encoding="utf-8")
_Popen = subprocess.Popen


class _P(_Popen):
    def __init__(self, args, *a, **kw):
        if isinstance(args, list) and len(args) >= 4 and args[3] == "-c":
            args = [args[0], "-I", "-S", str(_bs)]
        super().__init__(args, *a, **kw)


m.subprocess.Popen = _P
_env = m._sandbox_env
m._sandbox_env = lambda: {**_env(), **{k: os.environ[k] for k in ("SYSTEMROOT", "TEMP", "TMP") if os.environ.get(k)}}
from inference.agent import full_context_tokens as fct  # noqa: E402


def _count(self, messages, tools, thinking):
    n = len(json.dumps(tools or [])) // 4
    for msg in messages:
        c = msg.get("content")
        if isinstance(c, str):
            n += len(c) // 3
        elif isinstance(c, list):
            for part in c:
                n += len(str(part.get("text", ""))) // 3 if part.get("type") == "text" else 1100
        n += len(str(msg.get("reasoning") or msg.get("reasoning_content") or "")) // 3 + len(json.dumps(msg.get("tool_calls") or [])) // 3
    return n


fct.FullContextTokens.count = _count
os.killpg = lambda pid, sig: os.kill(pid, sig)
from inference.agent import tool_agent as _ta  # noqa: E402
_rsp = _ta.run_sandboxed_python
_ta.run_sandboxed_python = lambda *a, **k: _rsp(*a, **{**k, "timeout_seconds": max(int(k.get("timeout_seconds") or 30), 120)})
_rm = shutil.rmtree
shutil.rmtree = lambda *a, **k: _rm(*a, **{**k, "ignore_errors": True})
import pathlib  # noqa: E402
pathlib.PosixPath = pathlib.WindowsPath
started = time.time()
try:
    runpy.run_path(str(work / "_runner.py"), run_name="__main__")
except SystemExit as exc:
    print("runner exit:", exc)
print(f"\n=== RESULTS ({time.time() - started:.0f}s)")
bad = 0
for p in sorted((qroot / "results").glob("*.json")):
    r = json.loads(p.read_text(encoding="utf-8"))
    ok = r.get("status") == "done" and r.get("stop_reason") == "replay_done" and r.get("prefix_ok")
    bad += not ok
    print("OK  " if ok else "FAIL", r.get("try_id") or p.stem, r.get("status"), "stop=", r.get("stop_reason"),
          "prefix_ok=", r.get("prefix_ok"), "switch=", r.get("switch"), "wall=", r.get("wall_s"), (r.get("error") or "")[:300])
print("FAILED" if bad or not list((qroot / "results").glob("*.json")) else "ALL TRIES REPLAYED EXACTLY")
