"""State snapshots of one game session of Daniel's harness: restore a turn start without replaying the game.

Author: Claude Opus 5.5 (3-Oct-2026, Son: "make restores confident and fast with STATE SNAPSHOTS instead of
replaying every time").

A SNAPSHOT is the harness's per-game state at the start of a fresh turn, i.e. at the entry of ToolAgent.analyze for
that turn (the same point a rollout's origin is restored to), one gzip'd pickle, content-addressed:
  gs://cellens-ai-artifacts/arc3-gtree/v1/state/<sha256 of the file>.pkl.gz      (step records: state_ref = sha)
  meta      game id, pass, analysis_step (the turn), action count, level, screen hash, system-prompt sha, sizes
  agent     every ToolAgent field except the per-process ones (AGENT_SKIP): the context (_history_messages, kept as
            the agent holds it: the request is built from it by trims, summaries and stripped control keys, so it
            cannot be rebuilt from a logged request), _kept_functions (retained function SOURCES: his REPL keeps no
            variables), _last_step_summary, resume / yield flags, turn and session token counters, noop / guard /
            death ledgers, reasoning-effort rung, retained notices, world-model bookkeeping, the system prompt (checked
            on restore: a different harness build or env refuses the snapshot)
  session   history_entries (the frames behind the runtime-state file), viewer_events (the event log), analysis_step,
            last action, token baselines, animation record, move-cap counters, elapsed clock
  run       taaf GameRun bookkeeping (history with token / wallclock costs, actions per level, levels, state)
  prefix    the game's actions in order (name, display): the ENGINE is restored by replaying them through
            GameAPI.execute_action. GameAPI refuses pickling after start (taaf R11.05) and its environment wrapper does
            not pickle, so the engine itself is never stored; replaying moves costs milliseconds, no model calls.
  coach     the turn coach's counters (not its RNG, pin or assignment: each try sets its own)
  transcript the transcript file's bytes
Files the session derives from its fields (runtime-state JSON, event-log sidecar, viewer payload) are rewritten on
restore by the session's own writers. The server's KV cache is not stored (a re-prefill is 10-20 s and siblings share
it through the radix cache). Paths under the run directory are stored relative and land in the restoring try's dir.

turn_hook() is the per-turn writer for normal runs (inert unless ARC3_STATE_SNAPSHOTS=1): the port cell puts it at
the top of ToolAgent.analyze, before the agent touches anything for the turn; it writes <job_dir>/state/<sha>.pkl.gz
and one line per snapshot to <job_dir>/state/index.jsonl (game, pass, turn, actions, sha, bytes, ms).
No harness import at module level: this file is written into the bundle (inference/utils/arc3_state.py) and also
imported by the rollout driver.
"""
from __future__ import annotations

import gzip
import hashlib
import json
import logging
import os
import pickle
import threading
import time
from pathlib import Path, PurePath
from typing import Any

VERSION = 1
AGENT_SKIP = frozenset({"_gtr", "_arc3_coaches", "_arc3_coach_current", "_model", "_api_key", "_step_env_callback",
                        "_save_request_logs", "_timeout", "_arc3_state_off", "_arc3_state_skip"})
SESSION_KEYS = ("history_entries", "viewer_events", "analysis_step", "last_engine_action", "token_baseline",
                "game_token_baseline", "animation_record", "_arc3_move_cap", "_arc3_turn_moves")
RUN_KEYS = ("history", "actions_per_level", "levels_completed", "state", "started_at", "solver_note",
            "solver_analysis_html", "final_generated_tokens", "final_uncached_input_tokens", "final_wallclock_seconds")
COACH_SKIP = frozenset({"decide", "rng", "_pinned", "_assign", "game_key", "spec", "from_action", "cap_override"})
PATH_MARK = "\x00run\x00"
_log = logging.getLogger(__name__)
_WARNED: set[str] = set()
_LOCK = threading.Lock()


class SnapshotMismatch(RuntimeError):
    """The snapshot does not belong to this game / harness build, or the restored engine is not where it was."""


def enabled() -> bool:
    return os.environ.get("ARC3_STATE_SNAPSHOTS", "").strip().lower() in ("1", "true", "yes", "on")


# ------------------------------------------------------------------------------------------------ paths
def _tok(v: Any, root: str) -> Any:
    if isinstance(v, PurePath) and (str(v) == root or str(v).startswith(root + os.sep) or str(v).startswith(root + "/")):
        return (PATH_MARK, type(v).__name__, str(v)[len(root):].lstrip("/\\"))
    if isinstance(v, str) and len(v) < 4096 and (v == root or v.startswith(root + os.sep) or v.startswith(root + "/")):
        return (PATH_MARK, "str", v[len(root):].lstrip("/\\"))
    return v


def _untok(v: Any, root: Path) -> Any:
    if isinstance(v, tuple) and len(v) == 3 and v[0] == PATH_MARK:
        p = root / v[2] if v[2] else root
        return str(p) if v[1] == "str" else p
    return v


def board_hash(grid: Any) -> str:
    """trace_review_index.board_hash (the tree's screen id)."""
    board = [list(map(int, row)) for row in grid]
    return hashlib.sha1(json.dumps(board, separators=(",", ":")).encode()).hexdigest()[:12]


def _grid(session: Any) -> Any:
    from inference.framework import solver as sv  # noqa: PLC0415 (harness, lazy)
    return sv._grid_from_state(session.game.current_state)


def _level(session: Any) -> int:
    from inference.framework import solver as sv  # noqa: PLC0415
    return int(sv._level_number(session.game))


# ------------------------------------------------------------------------------------------------ capture
def _fields(obj: Any, skip: frozenset, root: str) -> dict:
    return {k: _tok(v, root) for k, v in vars(obj).items() if k not in skip and not k.startswith("_gtr")}


def _drop_unpicklable(d: dict) -> list[str]:
    bad = []
    for k in list(d):
        try:
            pickle.dumps(d[k], protocol=pickle.HIGHEST_PROTOCOL)
        except Exception:                        # noqa: BLE001
            bad.append(k)
            d.pop(k)
    return bad


def gzip_level() -> int:
    """ARC3_STATE_GZIP (default 3: a mid-game 5 MB pickle -> ~0.8 MB in ~0.1 s; 6 saves 15% for twice the time)."""
    try:
        return min(9, max(1, int(os.environ.get("ARC3_STATE_GZIP", "3"))))
    except ValueError:
        return 3


def capture(session: Any, agent: Any, coach: Any = None, *, root: str | Path | None = None,
            extra: dict | None = None) -> tuple[bytes, dict]:
    """(file bytes, info) of the session's state now. Call at a turn start (analyze entry, not resuming)."""
    t0 = time.perf_counter()
    root_s = str(root if root is not None else session.solver.job_dir)
    agent_f = _fields(agent, AGENT_SKIP, root_s)
    sess = {k: getattr(session, k) for k in SESSION_KEYS if hasattr(session, k)}
    sess["elapsed"] = time.monotonic() - float(session.started_at)
    run = session.game.game_run
    run_f = {k: getattr(run, k) for k in RUN_KEYS if hasattr(run, k)}
    run_f["elapsed"] = (time.monotonic() - run.started_at_monotonic) if run.started_at_monotonic else None
    prefix = []
    for e in session.viewer_events:
        if e.get("type") == "action":
            prefix.append((str(e.get("action_name") or "").upper(), e.get("action_display")))
    coach_f = _fields(coach, COACH_SKIP, root_s) if coach is not None else {}
    tpath = Path(session.transcript_path)
    transcript = tpath.read_bytes() if tpath.exists() else b""
    grid = _grid(session)
    meta = {"version": VERSION, "game_id": run.game_id, "pass": int(session.pass_index),
            "analysis_step": int(session.analysis_step), "action_count": len(run.history),
            "level": _level(session), "levels_completed": int(run.levels_completed),
            "screen_hash": board_hash(grid), "resume_after_yield": bool(getattr(agent, "_resume_after_yield", False)),
            "system_prompt_sha": hashlib.sha256(str(getattr(agent, "_system_prompt", "")).encode()).hexdigest(),
            "created": time.time(), "skipped": {"agent": [], "coach": []}, **(extra or {})}
    doc = {"meta": meta, "agent": agent_f, "session": sess, "run": run_f, "prefix": prefix, "coach": coach_f,
           "transcript": transcript}
    try:
        data = pickle.dumps(doc, protocol=pickle.HIGHEST_PROTOCOL)
    except Exception:                            # noqa: BLE001 - leave out what does not pickle, and say so
        meta["skipped"] = {"agent": _drop_unpicklable(agent_f), "coach": _drop_unpicklable(coach_f)}
        data = pickle.dumps(doc, protocol=pickle.HIGHEST_PROTOCOL)
    raw = gzip.compress(data, gzip_level(), mtime=0)
    sha = hashlib.sha256(raw).hexdigest()
    info = {"sha": sha, "bytes": len(raw), "ms": round((time.perf_counter() - t0) * 1000, 1),
            **{k: meta[k] for k in ("game_id", "pass", "analysis_step", "action_count", "level", "screen_hash")},
            "skipped": meta["skipped"]}
    return raw, info


def write(out_dir: str | Path, raw: bytes, info: dict) -> Path:
    """<out_dir>/<sha>.pkl.gz (write-once) + a line in <out_dir>/index.jsonl."""
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    p = out / f"{info['sha']}.pkl.gz"
    if not p.exists():
        tmp = p.with_name(p.name + f".{os.getpid()}.tmp")
        tmp.write_bytes(raw)
        os.replace(tmp, p)
    with _LOCK, open(out / "index.jsonl", "a", encoding="utf-8") as fh:
        fh.write(json.dumps({**info, "t": time.time()}) + "\n")
    return p


def load(path_or_bytes: str | Path | bytes) -> dict:
    raw = path_or_bytes if isinstance(path_or_bytes, bytes) else Path(path_or_bytes).read_bytes()
    doc = pickle.loads(gzip.decompress(raw))
    if doc.get("meta", {}).get("version") != VERSION:
        raise SnapshotMismatch(f"snapshot version {doc.get('meta', {}).get('version')} != {VERSION}")
    return doc


# ------------------------------------------------------------------------------------------------ restore
def _action_input(name: str, display: str | None):
    import re
    import arcengine  # noqa: PLC0415 (harness)
    data = {}
    if name == "ACTION6":
        m = re.match(r"^MOUSE\(row=(\d+), col=(\d+)\)$", str(display or ""))
        if not m:
            raise SnapshotMismatch(f"click without coordinates in the prefix: {display!r}")
        data = {"x": int(m.group(2)), "y": int(m.group(1))}
    return arcengine.ActionInput(id=arcengine.GameAction.from_name(name), data=data)


def restore(doc: dict, session: Any, agent: Any, coach: Any = None, *, root: str | Path | None = None) -> dict:
    """Put a fresh, started session (its play() has begun: before the turn loop) into the snapshot's state.
    Engine: the prefix replayed through GameAPI.execute_action (checked: action count + screen hash). Then the run's
    bookkeeping, the session's and agent's fields, the coach's counters, and the files the session derives from them.
    The next turn the session's loop starts is the snapshot's turn (analysis_step is set one below)."""
    t0 = time.perf_counter()
    meta = doc["meta"]
    run = session.game.game_run
    if run.game_id != meta["game_id"] or int(session.pass_index) != int(meta["pass"]):
        raise SnapshotMismatch(f"snapshot of {meta['game_id']} p{meta['pass']}, session {run.game_id} "
                               f"p{session.pass_index}")
    want_sp = meta["system_prompt_sha"]
    have_sp = hashlib.sha256(str(getattr(agent, "_system_prompt", "")).encode()).hexdigest()
    if want_sp != have_sp:
        raise SnapshotMismatch("system prompt differs: the snapshot is from another harness build or env")
    if len(run.history):
        raise SnapshotMismatch(f"the session already made {len(run.history)} moves")
    t_engine = time.perf_counter()
    for name, display in doc["prefix"]:
        session.game.execute_action(_action_input(name, display), generated_tokens=0, uncached_input_tokens=0)
    engine_ms = (time.perf_counter() - t_engine) * 1000
    grid = _grid(session)
    if len(run.history) != meta["action_count"] or board_hash(grid) != meta["screen_hash"]:
        raise SnapshotMismatch(f"engine after the prefix: {len(run.history)} moves, screen {board_hash(grid)}; "
                               f"snapshot {meta['action_count']} moves, screen {meta['screen_hash']}")
    rootp = Path(root if root is not None else session.solver.job_dir)
    for k, v in doc["run"].items():
        if k == "elapsed":
            if v is not None:
                run.started_at_monotonic = time.monotonic() - float(v)
            continue
        setattr(run, k, v)
    s = dict(doc["session"])
    session.started_at = time.monotonic() - float(s.pop("elapsed"))
    for k, v in s.items():
        object.__setattr__(session, k, v)
    session.analysis_step = int(meta["analysis_step"]) - 1      # the loop's += 1 makes it the snapshot's turn
    for k, v in doc["agent"].items():
        setattr(agent, k, _untok(v, rootp))
    if coach is not None:
        for k, v in doc["coach"].items():
            setattr(coach, k, _untok(v, rootp))
    tp = Path(session.transcript_path)
    tp.parent.mkdir(parents=True, exist_ok=True)
    tp.write_bytes(doc.get("transcript") or b"")
    session.write_runtime_state()
    session._viewer_events_flushed = 0           # rewrites the event-log sidecar from the restored events
    session.write_viewer_payload()
    return {"restore_ms": round((time.perf_counter() - t0) * 1000, 1), "engine_ms": round(engine_ms, 1),
            "moves": len(doc["prefix"]), "turn": meta["analysis_step"], "screen_hash": meta["screen_hash"]}


# ------------------------------------------------------------------------------------------------ per-turn hook
def turn_hook(agent: Any, state_path: Any, step_env: Any, analysis_step: Any) -> None:
    """At the top of ToolAgent.analyze for a fresh turn (the port cell's hook). Never raises."""
    if not enabled() or getattr(agent, "_arc3_state_off", False) or getattr(agent, "_resume_after_yield", False):
        return
    if analysis_step is not None and getattr(agent, "_arc3_state_skip", None) == analysis_step:
        return
    try:
        every = max(1, int(os.environ.get("ARC3_STATE_EVERY", "1") or 1))   # every Nth turn (disk / upload volume)
    except ValueError:
        every = 1
    if analysis_step is not None and int(analysis_step) % every:
        return
    session = getattr(step_env, "__self__", None)
    if session is None or not hasattr(session, "viewer_events"):
        return
    try:
        root = session.solver.job_dir or Path(state_path).parent
        out = os.environ.get("ARC3_STATE_DIR") or str(Path(root) / "state")
        raw, info = capture(session, agent, getattr(agent, "_arc3_coach_current", None), root=root)
        write(out, raw, info)
    except Exception as exc:                     # noqa: BLE001 - a snapshot must never cost the game
        key = type(exc).__name__
        if key not in _WARNED:
            _WARNED.add(key)
            _log.warning("arc3_state: snapshot failed (%s: %s); the game goes on", key, str(exc)[:300])
