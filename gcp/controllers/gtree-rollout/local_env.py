"""Local test bench for the rollout driver: Daniel's patched harness on Windows, no GPU, no model.

Author: Claude Opus 5.5 (3-Oct-2026).

  prepare_bundle(dst)   copy of his patched bundle (arc3-franzen-review-20260930/daniel-patched: the original Tufa
                        bundle + the nb-latest harness-changes.patch, identical to the notebook's cell 2) with the
                        coach arms' port cell (border off + coach hooks; the fork-dev source play ran border-off)
                        and our port cell applied, exactly as the notebook cells would
  notebook_env()        his setup cell's env (cell 4 setup_env, priority scheduling on) + the env lines around it
  windows()             the Windows differences, as gcp/controllers/rl/local_try_test.py and
                        live-injection/local_fork_test.py patch them: sandbox bootstrap through a file, no process
                        groups, rmtree tolerant, PosixPath, sandbox host timeout 120 s
  solver_template()     bm.solver from his pickled benchmark with his cell-16 settings + the daniel-base override
  StubModel             an OpenAI-compatible /v1/chat/completions on 127.0.0.1 that answers every request with one
                        fixed python tool call, and records what it was sent
"""
from __future__ import annotations

import http.server
import itertools
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
from pathlib import Path

HERE = Path(__file__).resolve().parent
PATCHED = Path(r"D:\codex-work\arc3-franzen-review-20260930\daniel-patched")
NOTEBOOK = Path(r"D:\codex-work\daniel-base-20261001\nb-latest\arc-agi-3-milestone-2-solution.ipynb")
# the coach arms' port cell (variants/coach/build_early.py output): border rule off (variants/noborder) + coach hooks
COACH_EARLY = Path(r"D:\codex-work\daniel-base-20261001\variants\coach\early.py")
ENV_FILES = Path(r"D:\codex-work\_branch\code\environment_files")


def _load(path: Path, name: str):
    import importlib.util
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


HARNESS_SECTIONS = ("noborder", "temperature", "toolfast", "throughput-scaling bench")   # edit the bundle / set env
SERVER_SECTIONS = ("hot-token map", "tuned MTP drafter", "QSA ring widening")             # launcher / wheel only


def harness_cell(build_dir: Path, out: Path) -> Path:
    """The harness half of a scored build's port cell (its '# --- ' sections that edit the bundle or set harness env;
    the server-side ones need the Kaggle wheelhouse) + the coach hooks, as build_rl_notebook.py composes them: what the
    rollout server's bundle gets, testable on Windows (4-Oct: coach hooks on top of toolfast had never run)."""
    text = (Path(build_dir) / "port_cell.py").read_text(encoding="utf-8")
    sections, cur = [], None
    for line in text.splitlines(keepends=True):
        if line.startswith("# --- "):
            cur = [line]
            sections.append(cur)
        elif cur is not None:
            cur.append(line)
    keep, unknown = [], []
    for sec in sections:
        head = sec[0].lower()
        if any(k in head for k in HARNESS_SECTIONS):
            keep.append("".join(sec))
        elif not any(k.lower() in head for k in SERVER_SECTIONS):
            unknown.append(sec[0].strip())
    if unknown:
        raise ValueError(f"port cell sections neither harness nor server (classify them): {unknown}")
    be = _load(Path(r"D:\codex-work\daniel-base-20261001\variants\coach\build_early.py"), "_le_coach_build")
    cell = be.arm_cell("".join(keep), {}, True)
    compile(cell, str(out), "exec")
    Path(out).write_text(cell, encoding="utf-8", newline="\n")
    return Path(out)


def prepare_bundle(dst: Path, *, base_cell: Path | None = COACH_EARLY, env: dict | None = None) -> Path:
    """A fresh bundle at dst with a base port cell (default the coach arms' cell: the six border-off switches + the
    coach hooks) and our port cell applied after it, as build_port.py --base composes them."""
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(PATCHED, dst)
    ns = {"os": os, "sys": sys, "Path": Path, "BUNDLE_DIR": dst}
    if base_cell is not None:
        exec(compile(base_cell.read_text(encoding="utf-8"), str(base_cell), "exec"), ns)
    sys.path.insert(0, str(HERE))
    import build_port
    os.environ.update(env or {})
    exec(compile(build_port.early_cell({}), "gtree_port", "exec"), ns)
    return dst


def notebook_env(base_url: str) -> dict[str, str]:
    """His cell 4: setup_env (USE_PRIORITY_SCHEDULING) and the env lines set around it, the server URL replaced."""
    nb = json.loads(NOTEBOOK.read_text(encoding="utf-8"))
    src = "".join(nb["cells"][4]["source"])
    block = src[src.index("setup_env = {"):src.index("os.environ.update({k: str(v)")]
    ns = {"SERVER_BASE_URL": base_url, "SERVED_MODEL_NAME": "flashnext", "USE_PRIORITY_SCHEDULING": True}
    exec(block, ns)
    env = {k: str(v) for k, v in ns["setup_env"].items()}
    env.update({"ARC3_WARMUP_ACTION_GAMES": "1", "ARC3_HTTP_RETRY_INITIAL_SECONDS": "0", "MPLBACKEND": "Agg",
                "TAAF_RUN_AS_SUBMISSION": "0", "TAAF_MINIMAL_DIAGNOSTICS": "0", "ONLY_RESET_LEVELS": "true"})
    return env


def put_on_path(bundle: Path) -> None:
    for repo in sorted((bundle / "src").iterdir(), reverse=True):
        for candidate in (repo / "src", repo):
            if candidate.is_dir():
                sys.path.insert(0, str(candidate))
    sys.path.insert(0, str(bundle / "gtree_rollout"))
    os.environ["GTREE_INGEST_DIR"] = str(bundle / "gtree_rollout" / "ingest")


def windows() -> None:
    from inference.agent import python_tool_sandbox as m
    bs = Path(tempfile.gettempdir()) / "bootstrap_gtree_rollout.py"
    bs.write_text(m._SANDBOX_BOOTSTRAP, encoding="utf-8")
    popen = subprocess.Popen

    class _P(popen):
        def __init__(self, args, *a, **kw):
            if isinstance(args, list) and len(args) >= 4 and args[3] == "-c":
                args = [args[0], "-I", "-S", str(bs)]
            kw.pop("start_new_session", None)
            super().__init__(args, *a, **kw)

    m.subprocess.Popen = _P
    env = m._sandbox_env
    m._sandbox_env = lambda: {**env(), **{k: os.environ[k] for k in ("SYSTEMROOT", "TEMP", "TMP") if os.environ.get(k)}}
    os.killpg = lambda pid, sig: os.kill(pid, sig)
    from inference.agent import tool_agent as ta
    rsp = ta.run_sandboxed_python
    ta.run_sandboxed_python = lambda *a, **k: rsp(*a, **{**k, "timeout_seconds": max(int(k.get("timeout_seconds") or 30), 120)})
    rm = shutil.rmtree
    shutil.rmtree = lambda *a, **k: rm(*a, **{**k, "ignore_errors": True})
    import pathlib
    pathlib.PosixPath = pathlib.WindowsPath


def solver_template(bundle: Path):
    import pickle
    with open(bundle / "benchmark_initial.pkl", "rb") as fh:
        bm = pickle.load(fh)
    s = bm.solver
    s.analyzer_timeout = 900.0           # his cell 16
    s.max_actions_per_game = None
    s.save_request_logs = True
    s.concurrency = 25                   # daniel-base override
    s.max_runtime_s_per_game = 7920
    return s


def arcade_spec(env_dir: Path = ENV_FILES):
    import arc_agi
    import taaf.game_api
    return taaf.game_api.ArcadeSpec(operation_mode=arc_agi.OperationMode.OFFLINE, environments_dir=str(env_dir))


class StubModel:
    """POST /v1/chat/completions -> one python tool call running `code`; every request body is kept."""

    def __init__(self, code: str, completion_tokens: int = 64):
        self.code, self.completion_tokens = code, completion_tokens
        self.requests: list[dict] = []
        self.lock = threading.Lock()
        self.ids = itertools.count(1)
        stub = self

        class H(http.server.BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def do_GET(self):
                self.send_response(200)
                self.end_headers()
                self.wfile.write(b'{"data": []}')

            def do_POST(self):
                body = json.loads(self.rfile.read(int(self.headers.get("Content-Length") or 0)))
                with stub.lock:
                    stub.requests.append(body)
                    n = next(stub.ids)
                prompt = len(json.dumps(body.get("messages") or [])) // 4
                reply = {"id": f"stub-{n}", "object": "chat.completion", "model": body.get("model"),
                         "choices": [{"index": 0, "finish_reason": "tool_calls", "message": {
                             "role": "assistant", "content": None, "reasoning_content": f"Stub turn {n}.",
                             "tool_calls": [{"id": f"call_stub_{n}", "type": "function", "function": {
                                 "name": "python", "arguments": json.dumps({"code": stub.code})}}]}}],
                         "usage": {"prompt_tokens": prompt, "completion_tokens": stub.completion_tokens,
                                   "total_tokens": prompt + stub.completion_tokens}}
                data = json.dumps(reply).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

        self.server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), H)
        self.url = f"http://127.0.0.1:{self.server.server_address[1]}/v1"
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def close(self):
        self.server.shutdown()
