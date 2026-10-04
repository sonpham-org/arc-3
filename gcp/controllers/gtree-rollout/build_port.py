"""Assemble the notebook cells for mid-tree rollouts in Daniel's notebook (build_daniel_notebook.py --early/--override).

Author: Claude Opus 5.5 (3-Oct-2026).

  C:/Python312/python.exe build_port.py --out-dir DIR [--base <coach early.py>] [--env K=V ...]
      -> DIR/early.py     port cell, right after his setup cell (patch applied, env set, nothing imported):
                          the arm's env, then (only when ARC3_ROLLOUT is set) writes the driver, rollout_core and the
                          gtree-ingest code it reuses into BUNDLE_DIR/gtree_rollout/ and puts that on sys.path.
                          --base prepends another port cell (e.g. variants/coach/early.py: border off + coach hooks),
                          so the coach's tool_agent / solver / sandbox hooks are in the bundle for the live phase.
      -> DIR/override.py  the daniel-base override (25 games, 7920 s) + rollout_driver.bind(bm): his run cell then
                          builds bm.games (for the arcade spec) and awaits bm.run, which plays the job queue instead.
Both cells are inert without ARC3_ROLLOUT. The driver subclasses the harness at runtime (RolloutAgent, RolloutSession),
so no harness source line is edited here; the coach's own anchored edits are untouched.
"""
from __future__ import annotations

import argparse
import importlib.util
from pathlib import Path

HERE = Path(__file__).resolve().parent
INGEST = HERE.parent / "gtree-ingest"
DANIEL = Path(r"D:\codex-work\daniel-base-20261001")


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


STATE_IMPORT = ("log = logging.getLogger(__name__)\n",
                "log = logging.getLogger(__name__)\n"
                "from inference.utils.arc3_state import turn_hook as _arc3_state_turn  # gtree state snapshots\n")
STATE_HOOK = ("        if not state_path.exists():\n            return None\n        self._ensure_session(state_path)\n"
              "        self._step_env_callback = step_env\n",
              "        if not state_path.exists():\n            return None\n"
              "        # gtree state snapshot at the start of a fresh turn (inert unless ARC3_STATE_SNAPSHOTS=1)\n"
              "        _arc3_state_turn(self, state_path, step_env, analysis_step)\n"
              "        self._ensure_session(state_path)\n        self._step_env_callback = step_env\n")


def payload_files() -> dict[str, str]:
    """Published path under BUNDLE_DIR/gtree_rollout -> file text (the ingest's vendor/ layout for its deps)."""
    deps = _load(INGEST / "deps.py", "_gtr_deps_probe")
    files = {"rollout_core.py": HERE / "rollout_core.py", "rollout_driver.py": HERE / "rollout_driver.py",
             "arc3_state.py": HERE / "arc3_state.py"}
    for f in ("deps.py", "gtree_build.py", "gtree_ctx.py", "gtree_store.py"):
        files[f"ingest/{f}"] = INGEST / f
    for f in ("trace_review_index.py", "fork_replay.py", "rl_reward.py", "arc3_minute_score_observer.py"):
        files[f"ingest/vendor/{f}"] = deps._find(f)
    return {k: Path(v).read_text(encoding="utf-8") for k, v in files.items()}


def early_cell(env: dict[str, str], base: str | None = None) -> str:
    files = payload_files()
    parts = []
    if base:
        parts += [base.rstrip("\n"), ""]
    parts.append("# --- gtree-rollout port cell (gcp/controllers/gtree-rollout/build_port.py): mid-tree rollouts ---")
    if env:
        parts += [f"os.environ[{k!r}] = {v!r}" for k, v in env.items()]
    parts.append(f'''import sys as _gtr_sys
from pathlib import Path as _GtrPath
_GTR_FILES = {files!r}
_GTR_STATE_EDITS = {[STATE_IMPORT, STATE_HOOK]!r}
if os.environ.get("ARC3_ROLLOUT") or os.environ.get("ARC3_STATE_SNAPSHOTS"):
    # state snapshots (arc3_state.py): the module into inference/utils, a hook at the top of ToolAgent.analyze
    import py_compile as _gtr_pyc
    _GTR_INF = _GtrPath(BUNDLE_DIR) / "src" / "ARC3-Inference" / "inference"
    (_GTR_INF / "utils" / "arc3_state.py").write_text(_GTR_FILES["arc3_state.py"], encoding="utf-8")
    _gtr_ta = _GTR_INF / "agent" / "tool_agent.py"
    _gtr_text = _gtr_ta.read_text(encoding="utf-8")
    assert "_arc3_state_turn" not in _gtr_text, "tool_agent.py already has the state hook"
    for _gtr_old, _gtr_new in _GTR_STATE_EDITS:
        assert _gtr_text.count(_gtr_old) == 1, ("state hook anchor", _gtr_old[:60], _gtr_text.count(_gtr_old))
        _gtr_text = _gtr_text.replace(_gtr_old, _gtr_new)
    _gtr_ta.write_text(_gtr_text, encoding="utf-8")
    _gtr_pyc.compile(str(_gtr_ta), doraise=True)
    _gtr_pyc.compile(str(_GTR_INF / "utils" / "arc3_state.py"), doraise=True)
    print("gtree state port: arc3_state.py written, analyze hooked; ARC3_STATE_SNAPSHOTS =",
          repr(os.environ.get("ARC3_STATE_SNAPSHOTS", "")))
if os.environ.get("ARC3_ROLLOUT"):
    assert not any(m.startswith(("inference", "taaf")) for m in _gtr_sys.modules), "harness imported before the port cell"
    _GTR_ROOT = _GtrPath(BUNDLE_DIR) / "gtree_rollout"
    for _gtr_rel, _gtr_text in _GTR_FILES.items():
        (_GTR_ROOT / _gtr_rel).parent.mkdir(parents=True, exist_ok=True)
        (_GTR_ROOT / _gtr_rel).write_text(_gtr_text, encoding="utf-8")
        compile(_gtr_text, str(_GTR_ROOT / _gtr_rel), "exec")
    _gtr_sys.path.insert(0, str(_GTR_ROOT))
    os.environ.setdefault("GTREE_INGEST_DIR", str(_GTR_ROOT / "ingest"))
    print("gtree-rollout port: driver written to", _GTR_ROOT, "| jobs", os.environ.get("ARC3_ROLLOUT_JOBS"),
          "| coach", repr(os.environ.get("ARC3_COACH", "")))
else:
    print("gtree-rollout port: ARC3_ROLLOUT unset, inert")''')
    return "\n".join(parts) + "\n"


def override_cell() -> str:
    base = _load(DANIEL / "build_daniel_notebook.py", "_gtr_bdn").BASE_OVERRIDE
    return base.rstrip("\n") + '''
# --- gtree-rollout: the run cell's `await bm.run(...)` plays the job queue (rollout_driver.bind) ---
if os.environ.get("ARC3_ROLLOUT"):
    import rollout_driver as _gtr_driver
    _gtr_driver.bind(bm)
'''


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--base", help="a port cell to run first (e.g. variants/coach/early.py)")
    ap.add_argument("--env", action="append", default=[], help="K=V set in the port cell (e.g. ARC3_ROLLOUT=1)")
    a = ap.parse_args()
    env = dict(e.split("=", 1) for e in a.env)
    out = Path(a.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    early = early_cell(env, Path(a.base).read_text(encoding="utf-8") if a.base else None)
    override = override_cell()
    for name, text in (("early.py", early), ("override.py", override)):
        compile(text, name, "exec")
        (out / name).write_text(text, encoding="utf-8", newline="\n")
        print(out / name, len(text))


if __name__ == "__main__":
    main()
