"""Mid-tree rollout driver, inside Daniel's notebook harness (imports the patched bundle's inference + taaf).

Author: Claude Opus 5.5 (3-Oct-2026, Son: "sampling from the middle of the tree and then roll out").

Each TRY of a JOB (rollout_core.py documents the job) is one game session of the real harness:
  RolloutSession (solver._HarnessGameSession) + RolloutAgent (tool_agent.ToolAgent), built the way the solver's
  _play_one builds them, in a job dir of its own (requests.jsonl, artifacts/, transcripts/, prompts/).
  1. restore the GAME: the engine replays the logged moves (replay_actions: straight to the engine, each tagged with
     its logged turn; replay_exact: through the harness itself, see 2). At the origin the board hash, level and
     action count are checked against the tree node (and, with a request log, against the logged opener's image).
  2. restore the HARNESS + CONTEXT: replay_exact re-runs every turn before the origin with a fake model that returns
     the logged reply and usage of each call (rl/fork_replay.py), so kept functions, summaries, resume flags, guards
     and coach counters are rebuilt by the harness's own code. Each rebuilt request is compared with the logged one
     (clock readings masked); the first divergence ends the try (status 'diverged', with the diff). A yield is
     reproduced where the log shows one (the next call resumes the same turn). replay_actions starts a fresh agent.
  3. play LIVE from the origin: the real model, the job's coach policy (ARC3_COACH hooks from variants/coach), until
     the origin's level is cleared, a game over (stop_on_game_over), the move budget, the turn cap or the token cap.
  4. write the try: result.json, rollout.jsonl (universal-tree records, rollout_core.rollout_records) beside the
     harness's own logs.
The coach: when its hooks are in the bundle, every try gets a Coach of its own before the first turn. It observes
from the game start; it is silent (stock) before the origin, or replays the source's logged decisions for a coached
source; from the origin turn on it plays the job's spec. ARC3_COACH must be set (any non-off value) for the hooks
to run at all: bind() sets it to 'policy' when the bundle has them.

RL ROLLOUT SERVER (3-Oct-2026, Son: "take advantage of the high throughput in the 10 lanes to do sampled rollouts off
policy"). A sibling job (pick_nodes.py) is one node + K tries, each with an ASSIGNED first mode (try 0 = stock, the
anchor). serve() fills the lanes with siblings of the same node together (10 lanes = 2 nodes x 5), so the server's
radix cache holds their shared context once:
  run_node(): restore the node ONCE (replay_exact, in <job>/restore/), then at the origin, before its first request:
    - pin the current policy (ARC3_COACH_POLICY=@file is re-read here: a new version reaches the next node),
    - warm the cache: the logged origin request without the coach line, max_tokens 1 (every sibling then reuses it),
    - per sibling, as a lane comes free (the parent reaps its own finished siblings while it waits): copy the restore
      dir to <job>/k<k>/ and os.fork() that child. A child moves every path of the
      session / agent / solver / coach from restore/ to k<k>/ (relocate(); leftovers are reported), gets fresh locks,
      no priority gate, its own coach log, stdout and coach RNG, plays its assignment at the origin decision and the
      policy after it, writes result.json + rollout.jsonl + master.jsonl.gz and exits (os._exit). The parent waits
      (killing children past the deadline + grace), gives each lane back as its child exits, and ends its own session
      without a request.
  Forking is the fast path on Linux (the notebook). Without os.fork (Windows) or with ARC3_ROLLOUT_FORK=0 it falls back
  to K independent replays of the same node (each restores on its own; a lane is taken at the origin).
  Why fork is safe here: the harness posts with requests.post (a new HTTP session per call: nothing to reset), its
  python tool sandbox is a new subprocess per call, request / event / state files are opened per write (no handle
  survives a turn), and the fork happens at the very start of analyze() (no turn state in flight). What a fork does
  NOT copy is other threads: their locks may be held at the fork, so the child replaces every module lock it can reach
  (_reset_after_fork) and never prints to the kernel's stream (stdout, stderr and stream log handlers go to a file).
Per try the result carries: assignment (mode, cap, design_prob, policy_prob), policy_version, restore_s, first_live
(prompt_tokens, cached_tokens when the server reports them (--enable-cache-report), latency, /metrics deltas when the
server exposes them (--enable-metrics)), fork info. Stop rule: the job's (move budget from the picker, turn cap 60,
no stop at a game over) plus the run deadline.
"""
from __future__ import annotations

import asyncio
import copy
import json
import os
import random
import re
import shutil
import sys
import threading
import time
import traceback
import types
import urllib.request
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from pathlib import Path, PurePath
from typing import Any, Callable

import arcengine
import requests
import taaf.game
import taaf.game_api
from inference.agent import tool_agent as ta
from inference.agent.runtime_state import RUNTIME_STATE_FILENAME
from inference.framework import solver as sv

import rollout_core as core

try:
    from inference.utils import arc3_coach as _coach_mod  # present when the coach port cell ran
except ImportError:                                          # pragma: no cover - bundle without the coach
    _coach_mod = None
try:
    from inference.agent.vision_context import ARC_COLOR_MAP as PALETTE
except ImportError:                                          # pragma: no cover
    PALETTE = None
try:
    from inference.utils import arc3_state as state_mod      # the port cell's copy (the turn hook uses it too)
except ImportError:                                          # pragma: no cover - port cell without the state hook
    import arc3_state as state_mod

_PRINT_LOCK = threading.Lock()


def log(msg: str) -> None:
    with _PRINT_LOCK:
        print(f"[gtree-rollout {time.strftime('%H:%M:%S')}] {msg}", flush=True)


class RolloutDivergence(RuntimeError):
    """The replayed harness built a request the log does not have (or made a call the log does not have)."""


# ------------------------------------------------------------------------------------------------ lanes, metrics
class Lanes:
    """The server's concurrent sessions. A node in the fork path takes one lane per sibling as lanes come free and
    gives each back when that sibling exits (4-Oct: holding all K until the slowest sibling ended left ~36% of lane
    time idle in rl2 round 2); it reaps its own children while it waits, so no node waits on lanes only it can free."""

    def __init__(self, n: int):
        self.n, self.free = int(n), int(n)
        self.cond = threading.Condition()

    def acquire(self, k: int, stop: Callable[[], bool] | None = None) -> bool:
        k = min(int(k), self.n)
        with self.cond:
            while self.free < k:
                if stop is not None and stop():
                    return False
                self.cond.wait(timeout=5)
            self.free -= k
            return True

    def try_acquire(self, k: int = 1) -> bool:
        with self.cond:
            if self.free < k:
                return False
            self.free -= k
            return True

    def release(self, k: int) -> None:
        with self.cond:
            self.free = min(self.n, self.free + min(int(k), self.n))
            self.cond.notify_all()


_METRICS_STATE = {"ok": None}
_METRIC_RE = re.compile(r"^(sglang[:_][A-Za-z0-9_:]+?)(\{[^}]*\})?\s+([-+0-9.eE]+|NaN)\s*$")
WANT_METRICS = ("prompt_tokens_total", "cached_tokens_total", "generation_tokens_total", "num_requests_total",
                "cache_hit_rate")


def scrape_metrics(base_url: str | None) -> dict | None:
    """SGLang's Prometheus counters (summed over labels) when the server has --enable-metrics; None otherwise (and
    the endpoint is not asked again after one failure)."""
    if not base_url or _METRICS_STATE["ok"] is False:
        return None
    url = base_url.rstrip("/")
    url = (url[:-3] if url.endswith("/v1") else url) + "/metrics"
    try:
        with urllib.request.urlopen(url, timeout=3) as r:
            text = r.read().decode("utf-8", "replace")
    except Exception:                            # noqa: BLE001 - optional
        _METRICS_STATE["ok"] = False
        return None
    out: dict[str, float] = {}
    for line in text.splitlines():
        m = _METRIC_RE.match(line)
        if m and any(m.group(1).endswith(w) for w in WANT_METRICS):
            try:
                out[m.group(1)] = out.get(m.group(1), 0.0) + float(m.group(3))
            except ValueError:
                pass
    _METRICS_STATE["ok"] = True
    return out


def metrics_delta(a: dict | None, b: dict | None) -> dict | None:
    if a is None or b is None:
        return None
    return {k: round(b[k] - a.get(k, 0.0), 3) for k in b if not k.endswith("cache_hit_rate")} | \
        {k: b[k] for k in b if k.endswith("cache_hit_rate")}


def usage_summary(usage: dict | None) -> dict:
    u = usage or {}
    det = u.get("prompt_tokens_details") or {}
    return {"prompt_tokens": u.get("prompt_tokens"), "completion_tokens": u.get("completion_tokens"),
            "cached_tokens": det.get("cached_tokens", u.get("cached_tokens"))}


# ------------------------------------------------------------------------------------------------ fork helpers
def _swap(v: Any, old: str, new: str) -> tuple[Any, bool]:
    """v with the old directory prefix replaced by new (Paths and short strings only)."""
    if isinstance(v, PurePath):
        s = str(v)
        if s == old or s.startswith(old + os.sep) or s.startswith(old + "/"):
            return type(v)(new + s[len(old):]), True
    elif isinstance(v, str) and len(v) < 4096 and (v == old or v.startswith(old + os.sep) or v.startswith(old + "/")):
        return new + v[len(old):], True
    return v, False


def relocate(objs: list[Any], old: Path, new: Path) -> int:
    """Move every attribute of these objects that names a path under old to the same path under new (top-level
    attributes, and the keys / values of dict and list attributes, rewritten in place so shared references follow)."""
    o, n, changed = str(old), str(new), 0
    for obj in objs:
        if obj is None or not hasattr(obj, "__dict__"):
            continue
        for key, v in list(vars(obj).items()):
            nv, ch = _swap(v, o, n)
            if ch:
                object.__setattr__(obj, key, nv)
                changed += 1
            elif isinstance(v, dict) and len(v) < 10000:
                pairs = [(_swap(k2, o, n), _swap(x, o, n)) for k2, x in v.items()]
                if any(a[1] or b[1] for a, b in pairs):
                    v.clear()
                    v.update({a[0]: b[0] for a, b in pairs})
                    changed += 1
            elif isinstance(v, list) and len(v) < 10000:
                for i, x in enumerate(v):
                    nx, ch2 = _swap(x, o, n)
                    if ch2:
                        v[i] = nx
                        changed += 1
    return changed


def find_refs(objs: list[Any], old: Path, depth: int = 3) -> list[str]:
    """Attribute paths (up to `depth` levels) still naming something under old: what relocate() could not reach."""
    o = str(old)
    hits, seen = [], set()

    def is_ref(v):
        return _swap(v, o, o + "#")[1]

    def walk(v, where, d):
        if id(v) in seen or d < 0 or len(hits) > 50:
            return
        if isinstance(v, (str, PurePath)):
            if is_ref(v):
                hits.append(where)
            return
        if isinstance(v, (int, float, bool, bytes, type(None), type, types.ModuleType, types.FunctionType,
                          types.MethodType, types.BuiltinFunctionType, threading.Thread)):
            return
        seen.add(id(v))
        if isinstance(v, dict):
            if len(v) > 5000:
                return
            for k2, x in v.items():
                if is_ref(k2):
                    hits.append(f"{where}[key {str(k2)[:80]}]")
                walk(x, f"{where}[{str(k2)[:40]}]", d - 1)
        elif isinstance(v, (list, tuple, set, frozenset)):
            if len(v) > 5000:
                return
            for i, x in enumerate(v):
                walk(x, f"{where}[{i}]", d - 1)
        elif hasattr(v, "__dict__") and not isinstance(v, type) and type(v).__module__ not in ("builtins",):
            if type(v).__name__ in ("module",):
                return
            for k2, x in list(vars(v).items()):
                walk(x, f"{where}.{k2}", d - 1)

    for i, obj in enumerate(objs):
        if obj is not None:
            walk(obj, f"<{type(obj).__name__}>", depth)
    return hits


def _redirect_output(path: Path) -> None:
    """A forked child never writes to the kernel's stream (its IO thread is not in the child)."""
    import logging
    fh = open(path, "a", buffering=1, encoding="utf-8")
    try:
        os.dup2(fh.fileno(), 1)
        os.dup2(fh.fileno(), 2)
    except OSError:
        pass
    old = (sys.stdout, sys.stderr, sys.__stdout__, sys.__stderr__)
    sys.stdout = sys.stderr = fh
    loggers = [logging.getLogger()] + [x for x in logging.Logger.manager.loggerDict.values()
                                       if isinstance(x, logging.Logger)]
    for lg in loggers:
        for h in lg.handlers:
            if isinstance(h, logging.StreamHandler) and getattr(h, "stream", None) in old:
                h.setStream(fh)


def _reset_after_fork(session: Any = None, redirect: Path | None = None) -> None:
    """Fresh module locks in a forked child (another thread may have held one at the fork) and no priority gate."""
    global _PRINT_LOCK
    _PRINT_LOCK = threading.Lock()
    if redirect is not None:
        _redirect_output(redirect)
    if _coach_mod is not None and hasattr(_coach_mod, "reset_locks_after_fork"):
        _coach_mod.reset_locks_after_fork()
    for name in ("_DIAG_LOCK", "_PRIORITY_GATE_LOCK"):
        if hasattr(ta, name):
            setattr(ta, name, threading.Lock())
    if hasattr(ta, "_PRIORITY_GATE"):
        ta._PRIORITY_GATE = None
    if session is not None:
        ev = threading.Event()
        if session.stop_event.is_set():
            ev.set()
        session.stop_event = ev
        session.solver._stop_event = ev
        session.solver._warmup_lock = threading.Lock()


def assignment_of(job: dict, k: int | None) -> dict | None:
    a = job.get("assignments") or []
    return dict(a[k]) if k is not None and 0 <= k < len(a) else None


class Group:
    """One node's siblings in the fork path: who forks, who waits, where the children go (all injectable: tests on
    Windows replace fork / waitpid / exit)."""

    def __init__(self, job: dict, ks: list[int], out_root: Path, lanes: Lanes, *, deadline: float | None = None,
                 grace_s: float = 300.0, forker: Callable[[], int] | None = None,
                 waitpid: Callable[[int, int], tuple[int, int]] | None = None,
                 kill: Callable[[int], None] | None = None, exit_fn: Callable[[int], None] | None = None,
                 real_fork: bool = True, warm: bool = True):
        self.job, self.ks, self.out_root, self.lanes = job, list(ks), Path(out_root), lanes
        self.deadline, self.grace_s, self.real_fork, self.warm = deadline, grace_s, real_fork, warm
        self.forker = forker or getattr(os, "fork", None)
        self.waitpid = waitpid or os.waitpid
        self.kill = kill or (lambda pid: os.kill(pid, 9))
        self.exit_fn = exit_fn or os._exit
        self.children: dict[int, int] = {}
        self.exit_codes: dict[int, int | None] = {}
        self.unforked: list[int] = []            # siblings never started (the deadline came before a lane)

    def child_dir(self, k: int) -> Path:
        return self.out_root / self.job["job_id"] / f"k{k}"


# ------------------------------------------------------------------------------------------------ one try's control
class TryController:
    """Shared by a try's agent and session: the phase (replay -> origin -> live), the replay cursor, the checks and
    the stop rule."""

    def __init__(self, job: dict, k: int, *, plan: core.ReplayPlan | None, facts: dict | None,
                 source_decisions: list[dict] | None = None):
        self.job, self.k, self.plan, self.facts = job, k, plan, facts or {}
        self.mode = job["mode"]
        self.origin_turn = int(self.facts.get("live_turn") or self.facts.get("turn") or job["origin"].get("turn"))
        self.phase = "replay" if self.mode == "replay_exact" else "prefix"
        self.i = 0                        # next logged call to serve
        self.turn_step: int | None = None
        self.turn_idx = 0
        self.force_yield = False
        self.verdicts: dict[str, int] = {}
        self.first_issue: dict | None = None
        self.diverged: dict | None = None
        self.aborted: str | None = None
        self.origin: dict | None = None
        self.origin_level = 0
        self.moves_at_origin = 0
        self.tokens_at_origin = 0
        self.live_turns_started = 0
        self.live_turns_done = 0
        self._last_live_step: int | None = None
        self.clear_moves: int | None = None
        self.stop_reason: str | None = None
        self.budget = 0
        self.session: sv._HarnessGameSession | None = None
        self.agent: ta.ToolAgent | None = None
        self.coach = None
        self.source_decisions = list(source_decisions or [])
        self.coach_replayed = 0
        self.t0 = time.time()
        self.origin_wall: float | None = None
        # RL rollout server
        self.assign = assignment_of(job, k)      # this try's assigned first mode (sibling jobs)
        self.assigned_done = False
        self.policy_doc: dict | None = None      # pinned for the whole try
        self.policy_version: str | None = None
        self.first_live: dict | None = None
        self.last_kw: dict | None = None         # the harness's request kwargs (tools, ...) of the last replayed call
        self.restore_s: float | None = None
        self.deadline: float | None = None
        self.on_origin: Callable[["TryController"], None] | None = None   # lane / fork hook at the origin
        self.lanes_held = 0
        self.role = "single"                     # single | parent (forks the siblings) | child
        self.group: Group | None = None
        self.parent_done = False
        self.try_dir: Path | None = None
        self.moved: tuple[Path, Path] | None = None   # (restore dir, sibling dir) until analyze() swaps its args
        self.fork: dict | None = None
        self.base_url: str | None = None
        # state snapshots: the logged origin request (from the request log, or staged from ctx_before), what was
        # restored from / captured at the origin
        self.origin_logged: list[dict] | None = (self.facts.get("origin_logged") or
                                                 (plan.seq[plan.origin_index]["messages"] if plan is not None else None))
        self.capture = os.environ.get("ARC3_ROLLOUT_CAPTURE", "1") != "0" and self.mode == "replay_exact"
        self.state: dict = {}

    # ---- failure paths -----------------------------------------------------------------------------------------
    def diverge(self, kind: str, **detail: Any) -> None:
        self.diverged = {"kind": kind, "call": self.i, **detail}
        log(f"{self.job['job_id']}.k{self.k}: DIVERGED {kind} at logged call {self.i}: {json.dumps(detail)[:600]}")
        raise RolloutDivergence(kind)

    def abort(self, why: str) -> None:
        if not self.aborted:
            self.aborted = why
            log(f"{self.job['job_id']}.k{self.k}: aborted: {why}")

    # ---- the origin ---------------------------------------------------------------------------------------------
    def reach_origin(self, session: sv._HarnessGameSession, agent: ta.ToolAgent) -> None:
        """The game and harness are at the start of the origin turn: check the state, arm the stop rule."""
        grid = sv._grid_from_state(session.game.current_state)
        info = {"turn": self.origin_turn, "seq": self.facts.get("seq") or self.job["origin"].get("seq"),
                "screen_hash": core.board_hash(grid), "level": sv._level_number(session.game),
                "actions_before": session.action_count, "levels_completed":
                    int(session.game.current_state.levels_completed), "replayed_calls": self.i}
        want = {key: self.job["origin"].get(key) if self.job["origin"].get(key) is not None else self.facts.get(key)
                for key in ("screen_hash", "level", "actions_before")}
        lead = int(self.facts.get("lead_in_origin") or 0)    # warmup RESETs inside the origin's own tree step
        if lead and want["actions_before"] is not None:
            want["actions_before"] = int(want["actions_before"]) + lead
            info["lead_in_origin"] = lead
        mism = {key: {"want": w, "got": info[key]} for key, w in want.items() if w is not None and w != info[key]}
        if self.origin_logged is not None and PALETTE is not None:
            try:
                logged = core.logged_screen_hash(self.origin_logged, PALETTE)
            except Exception as exc:                  # noqa: BLE001 - a check, not the play
                logged = f"undecodable: {exc!r}"
            info["logged_image_screen_hash"] = logged
            if logged is not None and logged != info["screen_hash"]:
                mism["logged_image_screen_hash"] = {"want": logged, "got": info["screen_hash"]}
        info["mismatch"] = mism
        self.origin = info
        self.origin_level = info["level"]
        self.moves_at_origin = session.action_count
        self.tokens_at_origin = getattr(agent, "generated_tokens", 0)
        self.origin_wall = time.time()
        bl = getattr(session.game, "base_actions_per_level", None)
        self.budget = core.move_budget(self.job["stop"], bl, self.origin_level)
        info["move_budget"] = self.budget
        self.restore_s = round(self.origin_wall - self.t0, 2)
        log(f"{self.job['job_id']}.k{self.k}: origin turn {self.origin_turn} level {info['level']} "
            f"actions {info['actions_before']} screen {info['screen_hash']} budget {self.budget} "
            f"restore {self.restore_s}s" + (f" MISMATCH {mism}" if mism else ""))
        if mism:
            self.abort(f"origin_mismatch {mism}")
            return
        agent._arc3_state_off = False            # live turns may snapshot (ARC3_STATE_SNAPSHOTS); the origin's
        agent._arc3_state_skip = self.origin_turn    # own snapshot is the one captured here
        if self.capture and self.phase == "replay":
            self.capture_origin(session, agent)
        if self.on_origin is not None:
            self.on_origin(self)

    def capture_origin(self, session: Any, agent: Any) -> None:
        """The restore cache: a replayed node is snapshotted once, so its next restore is instant (arc3_state)."""
        try:
            raw, info = state_mod.capture(session, agent, self.coach, root=self.try_dir, extra={
                "request_kw": self.last_kw, "source_rollout": self.job["source"].get("rollout_id"),
                "origin_seq": self.facts.get("seq") or self.job["origin"].get("seq"),
                "t1": self.job["origin"].get("t1"), "job": self.job["job_id"]})
            info["kind"] = "origin"
            state_mod.write(self.try_dir / "state", raw, info)
            self.state["captured"] = {k: info[k] for k in ("sha", "bytes", "ms")}
            log(f"{self.job['job_id']}: origin snapshot {info['sha'][:12]} {info['bytes'] / 1e6:.2f} MB "
                f"in {info['ms']} ms" + (f" (skipped {info['skipped']})" if any(info["skipped"].values()) else ""))
        except Exception as exc:                 # noqa: BLE001 - the restore cache is an optimisation
            self.state["capture_error"] = f"{type(exc).__name__}: {exc}"[:300]
            log(f"{self.job['job_id']}: origin snapshot failed: {self.state['capture_error']}")

    def restore_snapshot(self, session: Any, agent: Any) -> None:
        """mode 'snapshot': the session, agent, coach and engine from a state file, no turn replayed."""
        t = time.time()
        doc = state_mod.load(self.job["source"]["state"])
        info = state_mod.restore(doc, session, agent, self.coach, root=self.try_dir)
        meta = doc["meta"]
        if int(meta["analysis_step"]) != self.origin_turn:
            raise state_mod.SnapshotMismatch(f"snapshot is turn {meta['analysis_step']}, job origin {self.origin_turn}")
        if self.origin_turn == 1 and doc.get("prefix") and all(str(n).upper() == "RESET" for n, _ in doc["prefix"]):
            self.facts["lead_in_origin"] = len(doc["prefix"])   # a turn-1 snapshot after the warmup RESET
        self.last_kw = meta.get("request_kw") or self.last_kw
        self.state["restored"] = {**info, "sha": self.job["source"].get("state_ref"), "load_s": round(time.time() - t, 3)}

    # ---- the fork (one restore, K siblings) ------------------------------------------------------------------------
    def warm_cache(self) -> dict | None:
        """One max_tokens=1 request with the logged origin request minus the coach line: every sibling's first
        request then finds the shared prefix in the server's radix cache."""
        if self.origin_logged is None or self.last_kw is None or self.agent is None:
            return None
        msgs, _tail = core.split_tail(self.origin_logged)
        t = time.time()
        m0 = scrape_metrics(self.base_url)
        try:
            res = ta.ToolAgent._chat_completion(self.agent, msgs, **{**self.last_kw, "max_tokens": 1})
        except Exception as exc:                 # noqa: BLE001 - a missed warm-up only costs speed
            return {"error": f"{type(exc).__name__}: {exc}"[:300]}
        return {"latency_s": round(time.time() - t, 2), **usage_summary(getattr(res, "usage", None)),
                "metrics_delta": metrics_delta(m0, scrape_metrics(self.base_url))}

    def fork_siblings(self, _ctl: "TryController" = None) -> None:
        """At the origin, before its first request: pin the policy, warm the cache, then per sibling take one lane
        (reaping this node's finished siblings while waiting), copy the restore dir and fork. The parent stays at
        the origin untouched, so a sibling forked later starts from the same state. Returns in each child (as that
        sibling) and, in the parent, after every child exited (the parent's session then ends without a request)."""
        g = self.group
        if _coach_mod is not None and self.coach is not None:
            self.policy_doc = self.coach.pin_policy(_coach_mod.load_policy() if _coach_mod.policy_spec() else {})
            self.policy_version = self.policy_doc.get("version")
        warm = self.warm_cache() if g.warm else None
        src = self.try_dir
        t_node = time.time()
        self.fork = {"restore_s": self.restore_s, "warm": warm, "siblings": len(g.ks), "restore_dir": str(src)}
        waits: dict[int, float] = {}
        for i, k in enumerate(g.ks):
            t_lane = time.time()
            if not self.take_lane():
                g.unforked = list(g.ks[i:])
                self.abort(f"deadline before lanes were free ({len(g.unforked)} of {len(g.ks)} siblings not started)")
                break
            waits[k] = round(time.time() - t_lane, 2)
            dst = g.child_dir(k)
            shutil.rmtree(dst, ignore_errors=True)
            shutil.copytree(src, dst)
            self.fork.update(lane_wait_s=waits[k], forked_at=time.time(), fork_order=i,
                             since_origin_s=round(time.time() - t_node, 2))
            for stream in (sys.stdout, sys.stderr):
                try:
                    stream.flush()
                except Exception:                # noqa: BLE001
                    pass
            pid = g.forker()
            if pid == 0:
                self.become_child(k)
                return
            g.children[k] = pid
        log(f"{self.job['job_id']}: forked {len(g.children)} siblings {g.children} (restore {self.restore_s}s, "
            f"lane waits {waits}, warm {json.dumps(warm)[:200]})")
        self.wait_children()
        self.parent_done = True
        self.stop_reason = self.stop_reason or "forked_parent"

    def take_lane(self) -> bool:
        """One lane for the next sibling; while none is free, reap this node's own finished siblings (their lanes come
        back here). False if the deadline passes first."""
        g = self.group
        while not g.lanes.try_acquire(1):
            if g.deadline is not None and time.time() > g.deadline:
                return False
            if not self.reap_children():
                time.sleep(0.5)
        self.lanes_held += 1
        return True

    def reap_children(self) -> int:
        """Collect every exited child of this node (exit code, lane back); returns how many."""
        g = self.group
        nohang = getattr(os, "WNOHANG", 1)
        n = 0
        for k, pid in list(g.children.items()):
            if k in g.exit_codes:
                continue
            try:
                wpid, status = g.waitpid(pid, nohang)
            except ChildProcessError:
                wpid, status = pid, None
            if wpid:
                g.exit_codes[k] = (os.waitstatus_to_exitcode(status) if status is not None
                                   and hasattr(os, "waitstatus_to_exitcode") else status)
                self.give_lane()
                n += 1
        return n

    def give_lane(self) -> None:
        if self.lanes_held > 0:
            self.lanes_held -= 1
            self.group.lanes.release(1)

    def become_child(self, k: int) -> None:
        g = self.group
        dst = g.child_dir(k)
        _reset_after_fork(self.session, redirect=(dst / "child.log") if g.real_fork else None)
        old = self.try_dir
        self.role, self.k = "child", k
        self.assign, self.assigned_done = assignment_of(self.job, k), False
        objs = [self.session, self.agent, getattr(self.session, "solver", None), self.coach,
                getattr(self.session, "game", None)]
        moved = relocate(objs, old, dst)
        self.moved = (old, dst)
        self.try_dir = dst
        os.environ["ARC3_COACH_LOG"] = str(dst / "coach-decisions.jsonl")
        if self.coach is not None:
            self.coach.rng = random.Random(f"{self.job['job_id']}:{k}:{os.getpid()}:{time.time_ns()}")
        if self.agent is not None:
            self.agent._diag_name = f"g{k:02d}"
        self.fork = dict(self.fork or {}, child_pid=os.getpid(), relocated=moved,
                         leftover_refs=find_refs(objs, old), child_start=time.time())
        if self.fork["leftover_refs"]:
            log(f"{self.job['job_id']}.k{k}: paths still under the restore dir: {self.fork['leftover_refs'][:8]}")

    def wait_children(self) -> None:
        """Wait for every child; each exited child's lane goes back at once, not when the slowest sibling ends."""
        g = self.group
        hard = (g.deadline + g.grace_s) if g.deadline is not None else None
        while True:
            self.reap_children()
            pending = {k: pid for k, pid in g.children.items() if k not in g.exit_codes}
            if not pending:
                break
            if hard is not None and time.time() > hard:
                for k, pid in pending.items():
                    try:
                        g.kill(pid)
                    except OSError:
                        pass
                    log(f"{self.job['job_id']}.k{k}: killed (pid {pid}) past the deadline")
                hard = None
            if pending:
                time.sleep(0.5)

    # ---- agent hooks ---------------------------------------------------------------------------------------------
    def begin_turn(self, agent: ta.ToolAgent, step: int | None) -> None:
        self.turn_step, self.turn_idx, self.force_yield = step, 0, False
        if self.phase == "replay" and step is not None and int(step) >= self.origin_turn:
            if int(step) != self.origin_turn or getattr(agent, "_resume_after_yield", False):
                self.diverge("turn_order", got_step=step, origin_turn=self.origin_turn)
            if self.i != self.plan.origin_index:
                self.diverge("call_count", replayed=self.i, logged_before_origin=self.plan.origin_index)
            self.reach_origin(self.session, agent)
            self.phase = "origin"
        if self.phase in ("origin", "live") and step is not None and step != self._last_live_step:
            self._last_live_step = step
            self.live_turns_started += 1

    def end_turn(self, result: Any) -> None:
        if self.phase in ("origin", "live") and result is not None and getattr(result, "step_executed", False):
            self.live_turns_done += 1

    def chat(self, agent: ta.ToolAgent, messages: list[dict], kw: dict, real: Callable) -> Any:
        self.turn_idx += 1
        if self.phase == "replay":
            self.last_kw = dict(kw)
            return self._replay_call(messages)
        if self.phase == "origin":
            self.phase = "live"
            send = messages
            if self.origin_logged is not None and self.mode != "replay_actions":
                if self.plan is not None:
                    rec = self.plan.seq[self.plan.origin_index]
                    if (self.turn_step, self.turn_idx) != (rec["step"], rec["idx"]):
                        self.diverge("origin_call", got=[self.turn_step, self.turn_idx],
                                     logged=[rec["step"], rec["idx"]])
                elif self.turn_idx != 1:
                    self.diverge("origin_call", got=[self.turn_step, self.turn_idx], logged=[self.origin_turn, 1])
                verdict, send, tails = core.origin_request(messages, self.origin_logged)
                self._tally(verdict, "origin")
                self.origin["request_verdict"] = verdict["verdict"]
                self.origin["tails"] = tails
                if not self.same(verdict):
                    self.diverge("origin_messages", **verdict)
            self.origin["context_digest"] = core.digest(send)
            self.origin["context_messages"] = len(send)
            t = time.time()
            m0 = scrape_metrics(self.base_url)
            res = real(send, **kw)
            self.first_live = {"latency_s": round(time.time() - t, 2), **usage_summary(getattr(res, "usage", None)),
                               "metrics_delta": metrics_delta(m0, scrape_metrics(self.base_url)),
                               "tail": core.split_tail(send)[1].strip()[:80]}
            self.log_reply(res)
            return res
        res = real(messages, **kw)
        self.log_reply(res)
        return res

    def log_reply(self, res: Any) -> None:
        """Every live reply into <try>/replies.jsonl (4-Oct, RL v1 trains on tries): Daniel's harness logs requests
        but not replies, so a reply is only seen inside the NEXT request and a try's last reply (the clearing turn,
        when it cleared) would never reach training."""
        if self.try_dir is None:
            return
        try:
            msg = getattr(res, "message", None)
            row = {"analysis_step": self.turn_step, "request_index_within_turn": self.turn_idx,
                   "finish_reason": getattr(res, "finish_reason", None),
                   "message": msg if isinstance(msg, dict) else None, "usage": getattr(res, "usage", None)}
            with open(self.try_dir / "replies.jsonl", "a", encoding="utf-8") as fh:
                fh.write(json.dumps(row, default=str) + "\n")
        except Exception as exc:                 # noqa: BLE001 - a missing reply only costs that turn's training
            log(f"{self.job['job_id']}.k{self.k}: reply not logged: {exc!r}"[:300])

    def same(self, verdict: dict) -> bool:
        """Exact up to clock readings and image encoding; 'near' (a few characters) only if the job tolerates it."""
        v = verdict["verdict"]
        return v in core.SAME or (v == "near" and bool(self.job.get("replay_tolerate_near")))

    def _tally(self, verdict: dict, where: str) -> None:
        v = verdict["verdict"]
        self.verdicts[v] = self.verdicts.get(v, 0) + 1
        if v not in core.SAME and self.first_issue is None:
            self.first_issue = {"where": where, "call": self.i, **verdict}

    def _replay_call(self, messages: list[dict]) -> Any:
        plan = self.plan
        if self.i >= plan.origin_index:
            self.diverge("extra_call", step=self.turn_step, idx=self.turn_idx)
        rec = plan.seq[self.i]
        if (self.turn_step, self.turn_idx) != (rec["step"], rec["idx"]):
            self.diverge("call_order", got=[self.turn_step, self.turn_idx], logged=[rec["step"], rec["idx"]])
        verdict = core.compare(core.roundtrip(messages), rec["messages"])
        self._tally(verdict, f"step {rec['step']} idx {rec['idx']}")
        if not self.same(verdict):
            self.diverge("messages", step=rec["step"], idx=rec["idx"], **verdict)
        i = self.i
        self.i += 1
        if rec["failed"]:
            kind = plan.failure_kind(i)
            if kind == "context_overflow":
                raise requests.RequestException("replayed: maximum context length exceeded")
            if kind == "timeout_yield":
                raise requests.exceptions.ReadTimeout("replayed: read timeout")
            raise requests.RequestException("replayed: request failed")
        if plan.yields_after(i):
            self.force_yield = True
        return ta._ChatCompletionResult(message=copy.deepcopy(rec["reply"]), finish_reason=rec["finish_reason"] or "",
                                        usage=copy.deepcopy(rec["usage"]), served_by="gtree-replay")

    # ---- the coach -------------------------------------------------------------------------------------------------
    def install_coach(self, session: sv._HarnessGameSession, agent: ta.ToolAgent) -> None:
        """A Coach for this session, observing from the game start; decide() is wrapped to play stock (or the
        source's logged decisions) before the origin and the job's spec from it."""
        if _coach_mod is None or not _coach_mod.policy_spec():
            if core.coach_spec(self.job) or self.source_decisions:
                raise RuntimeError("the job needs the turn coach but its hooks are not active (coach port cell + "
                                   "ARC3_COACH)")
            return
        key = str(session.state_path)
        c = _coach_mod.Coach(key)
        c.spec, c.from_action, c.cap_override = "", 0, ""
        live_spec = core.coach_spec(self.job)
        live_cap = self.job["coach"].get("cap")
        original = c.decide
        if hasattr(c, "pin_policy"):             # one policy version per try (an @file is re-read here)
            self.policy_doc = c.pin_policy(_coach_mod.load_policy() if live_spec == "policy" else {})
            self.policy_version = self.policy_doc.get("version")
        elif self.assign:
            raise RuntimeError("sibling jobs need the RL coach (arc3_coach with pin_policy / assign_next)")

        def decide(extra=None):
            step = int((extra or {}).get("step") or 0)
            if step >= self.origin_turn:
                c.spec = live_spec
                c.cap_override = "" if live_cap is None else str(live_cap).lower()
                if self.assign and not self.assigned_done:      # the branch: this try's assigned first mode
                    self.assigned_done = True
                    a = self.assign
                    c.assign_next(a["mode"], cap="mode" if a.get("cap") in (None, "mode") else a["cap"],
                                  meta={"design_prob": a.get("design_prob"),
                                        "cap_design_prob": a.get("cap_design_prob"), "job": self.job["job_id"],
                                        "try": self.k, "anchor": bool(a.get("anchor")),
                                        "picker_policy_prob": a.get("policy_prob")})
            elif self.source_decisions:
                if self.coach_replayed >= len(self.source_decisions):
                    self.diverge("coach_decisions_exhausted", step=step)
                d = self.source_decisions[self.coach_replayed]
                self.coach_replayed += 1
                want = int((d.get("features") or {}).get("actions_total") or 0)
                if want != c.actions_total:
                    self.diverge("coach_actions_total", step=step, logged=want, rebuilt=c.actions_total)
                c.spec = f"force:{d['mode']}"
                c.cap_override = "none" if d.get("cap") is None else str(d["cap"])
            else:
                c.spec = ""
            return original(extra)

        c.decide = decide
        agent.__dict__.setdefault("_arc3_coaches", {})[key] = c
        agent._arc3_coach_current = c
        self.coach = c

    # ---- session hooks ---------------------------------------------------------------------------------------------
    def before_loop(self, session: sv._HarnessGameSession) -> None:
        agent = session.analyzer
        self.install_coach(session, agent)
        if self.mode == "snapshot":
            try:
                self.restore_snapshot(session, agent)
            except Exception as exc:             # noqa: BLE001 - the try ends; run_node may fall back to a replay
                self.abort(f"snapshot restore failed: {type(exc).__name__}: {exc}"[:500])
                return
            session.analysis_step = self.origin_turn    # as the loop will set it, for the checks and the capture
            self.reach_origin(session, agent)
            session.analysis_step = self.origin_turn - 1
            self.phase = "origin"
            return
        if self.mode == "replay_exact":
            for _ in range(int(self.facts.get("lead_resets") or 0)):
                session._execute_auto_reset()
            return
        # replay_actions: the logged moves straight to the engine, each under its logged turn number
        batch: list[dict] = []
        batch_turn = None
        for a in self.facts["prefix"]:
            session.analysis_step = a["turn"]
            if a["automatic"]:
                session._execute_auto_reset()
                continue
            action = arcengine.ActionInput(id=arcengine.GameAction.from_name(a["name"]), data=dict(a["data"]))
            payload = session._execute_action(action, batch_index=1, batch_size=1, generated_tokens=0)
            if a["turn"] != batch_turn:
                self._observe(batch)
                batch, batch_turn = [], a["turn"]
            batch.append(payload)
        self._observe(batch)
        session.analysis_step = self.origin_turn - 1
        self.reach_origin(session, agent)
        self.phase = "origin"                    # the next request is the origin's (a fresh context, not compared)

    def _observe(self, batch: list[dict]) -> None:
        """The coach's counters for one replayed turn (one synthetic batch: the turn's moves as one action call)."""
        if self.coach is None or not batch:
            return
        p = dict(batch[-1], executed_count=len(batch), stopped_early=False)
        p["game_over"] = any(x.get("game_over") for x in batch)
        self.coach.observe(p)

    def should_stop(self, session: sv._HarnessGameSession) -> bool:
        if self.aborted or self.diverged or self.parent_done:
            return True
        if self.deadline is not None and time.time() > self.deadline and not self.stop_reason:
            self.stop_reason = "deadline"
            return True
        if self.phase not in ("origin", "live") or self.origin is None:
            return False
        if self.stop_reason:
            return True
        st = session.game.current_state
        moves = session.action_count - self.moves_at_origin
        if int(st.levels_completed) >= self.origin_level or st.raw.state == arcengine.GameState.WIN:
            self.clear_moves = moves
            self.stop_reason = "cleared"
        elif self.job["stop"].get("stop_on_game_over", True) and st.raw.state == arcengine.GameState.GAME_OVER:
            self.stop_reason = "game_over"
        elif moves >= self.budget:
            self.stop_reason = "move_budget"
        elif self.live_turns_done >= int(self.job["stop"].get("turn_cap") or 10**9):
            self.stop_reason = "turn_cap"
        elif self.job["stop"].get("token_cap") and self.agent is not None and \
                self.agent.generated_tokens - self.tokens_at_origin >= int(self.job["stop"]["token_cap"]):
            self.stop_reason = "token_cap"
        return self.stop_reason is not None

    # ---- the result ------------------------------------------------------------------------------------------------
    def result(self) -> dict:
        s, a = self.session, self.agent
        moves = (s.action_count - self.moves_at_origin) if (s is not None and self.origin) else None
        status = ("diverged" if self.diverged else "aborted" if self.aborted else
                  "no_origin" if self.origin is None else "forked_parent" if self.parent_done else
                  "deadline" if self.stop_reason == "deadline" else "done")
        return {"job": self.job["job_id"], "try": self.k, "mode": self.mode, "status": status, "role": self.role,
                "round": self.job.get("round"), "assignment": self.assign, "policy_version": self.policy_version,
                "restore_s": self.restore_s, "first_live": self.first_live, "fork": self.fork, "state": self.state,
                "try_dir": str(self.try_dir) if self.try_dir else None,
                "stop_reason": self.stop_reason or (status if status != "done" else "ended"),
                "cleared": bool(self.clear_moves is not None), "moves_to_clear": self.clear_moves,
                "moves": moves, "turns": self.live_turns_started, "turns_done": self.live_turns_done,
                "tokens": (a.generated_tokens - self.tokens_at_origin) if (a is not None and self.origin) else None,
                "origin": self.origin, "replay": {"calls": self.i, "verdicts": self.verdicts,
                                                  "first_issue": self.first_issue,
                                                  "coach_decisions_replayed": self.coach_replayed},
                "diverged": self.diverged, "aborted": self.aborted,
                "run_state": s.game.game_run.state if s is not None and s.game.game_run else None,
                "levels_completed": int(s.game.current_state.levels_completed) if s is not None else None,
                "state_path": str(s.state_path) if s is not None else None,
                "coach_log": os.environ.get("ARC3_COACH_LOG") if self.coach is not None else None,
                "wall_s": round(time.time() - self.t0, 1),
                "live_wall_s": round(time.time() - self.origin_wall, 1) if self.origin_wall else None}


# ------------------------------------------------------------------------------------------------ harness subclasses
class RolloutAgent(ta.ToolAgent):
    _gtr: TryController

    def analyze(self, state_path, action_num, valid_actions=None, step_env=None, transcript_path=None,
                analysis_step=None, transcript_updated=None, request_timeout_seconds=None, should_stop=None):
        ctl = self._gtr
        try:
            ctl.begin_turn(self, analysis_step)
        except RolloutDivergence:
            return None
        if ctl.parent_done or ctl.aborted:       # the forking parent (its siblings played) or a failed origin
            return None
        if ctl.moved is not None:                # a sibling forked inside this very call: its arguments still name
            old, new = map(str, ctl.moved)       # the restore dir (the session passes them each turn from then on)
            state_path = _swap(state_path, old, new)[0]
            transcript_path = _swap(transcript_path, old, new)[0]
            ctl.moved = None

        def stop() -> bool:
            if ctl.force_yield:                  # the logged turn yielded here: same exit as the clock/token yield
                return True
            return bool(should_stop()) if should_stop is not None else False

        res = super().analyze(state_path, action_num, valid_actions=valid_actions, step_env=step_env,
                              transcript_path=transcript_path, analysis_step=analysis_step,
                              transcript_updated=transcript_updated, request_timeout_seconds=request_timeout_seconds,
                              should_stop=stop)
        ctl.end_turn(res)
        return res

    def _chat_completion(self, messages, **kw):
        return self._gtr.chat(self, messages, kw, lambda m, **k: ta.ToolAgent._chat_completion(self, m, **k))


class RolloutSession(sv._HarnessGameSession):
    _gtr: TryController

    def should_stop(self) -> bool:
        return super().should_stop() or self._gtr.should_stop(self)

    def _play_inner(self) -> None:
        try:
            self._gtr.before_loop(self)
        except Exception as exc:                 # noqa: BLE001 - the try ends, the record says why
            self._gtr.abort(f"restore failed: {type(exc).__name__}: {exc}")
            log(traceback.format_exc()[-1500:])
        super()._play_inner()


# ------------------------------------------------------------------------------------------------ one try
_ARCADE_SESSION = taaf.game.RunSession(record_intermediate_states=False)


def prepare(job: dict) -> tuple[dict, dict | None, core.ReplayPlan | None, list[dict]]:
    """A job's checked form, origin facts (from the event log when given), replay plan and coach decisions."""
    job = core.normalize_job(job)
    src = job["source"]
    if job["mode"] == "snapshot":            # no logs replayed: the origin is the snapshot's turn start
        o = job["origin"]
        facts = {"turn": int(o["turn"]), "seq": o.get("seq"), "live_turn": int(o["turn"]), "lead_resets": 0,
                 "origin_logged": json.loads(Path(src["origin_messages"]).read_text(encoding="utf-8"))
                 if src.get("origin_messages") else None}
        return job, facts, None, []
    facts = core.origin_facts(job, core.read_lines(src["events"])) if src.get("events") else None
    if facts is None:
        facts = {"turn": int(job["origin"]["turn"]), "seq": job["origin"].get("seq")}
    plan = None
    if job["mode"] == "replay_exact":
        plan = core.load_plan(src["requests"], facts["turn"])
        facts.setdefault("lead_resets", core.lead_resets_from_requests(plan.seq))
        if src.get("events") is None:
            facts["lead_resets"] = core.lead_resets_from_requests(plan.seq)
        # the warmup RESET (the notebook's first game(s): an automatic RESET at turn 0) is segmented INTO the play's
        # first step, so a turn-1 origin's event prefix is empty and misses it, while the request log (first request
        # at action 2) shows it. Replay it, and expect it in the origin's action count, which the tree step does not
        # carry (3-Oct pilot: every ar25 root try diverged on "No previous action sequence was captured. / step 2")
        lead = core.lead_resets_from_requests(plan.seq)
        if lead > int(facts.get("lead_resets") or 0):
            facts["lead_in_origin"] = lead - int(facts.get("lead_resets") or 0)
            facts["lead_resets"] = lead
    decisions = []
    if src.get("coach_log"):
        key = f"{job['game_id']}_p{job['pass']}_{RUNTIME_STATE_FILENAME}"
        decisions = [r for r in (json.loads(x) for x in core.read_lines(src["coach_log"]) if x.strip())
                     if str(r.get("game", "")).endswith(key)]
        decisions.sort(key=lambda r: r.get("decision") or 0)
        decisions = [d for d in decisions if int((d.get("features") or {}).get("step") or 0) < facts["turn"]] \
            if decisions and all("step" in (d.get("features") or {}) for d in decisions) else decisions
    return job, facts, plan, decisions


def run_try(job: dict, k: int, solver_tmpl: sv.HarnessSolver, spec: taaf.game_api.ArcadeSpec, out_root: Path, *,
            lane: int = 0, prepared: tuple | None = None, write_records: bool = True,
            allow_fenced: bool = False, lanes: Lanes | None = None, deadline: float | None = None) -> dict:
    """One try: a fresh game and harness session in <out_root>/<job_id>/k<k>/, restored and played on. With lanes,
    the try takes one lane at the origin (restoring holds none) and gives it back at the end."""
    job, facts, plan, decisions = prepared or prepare(job)
    try_dir = Path(out_root) / job["job_id"] / f"k{k}"
    ctl = TryController(job, k, plan=plan, facts=facts, source_decisions=decisions)
    ctl.deadline = deadline
    if lanes is not None:
        def take(c: TryController) -> None:
            if lanes.acquire(1, stop=lambda: deadline is not None and time.time() > deadline):
                c.lanes_held = 1
            else:
                c.abort("deadline before a lane was free")
        ctl.on_origin = take
    try:
        _play_session(ctl, job, try_dir, solver_tmpl, spec, lane)
    finally:
        if lanes is not None and ctl.lanes_held:
            lanes.release(ctl.lanes_held)
    return _finish_try(ctl, job, k, write_records=write_records, allow_fenced=allow_fenced)


def _finish_try(ctl: TryController, job: dict, k: int, *, write_records: bool = True,
                allow_fenced: bool = False) -> dict:
    """result.json, and for a finished try rollout.jsonl + master.jsonl.gz (+ its contexts in gtree-store/)."""
    try_dir = ctl.try_dir
    res = ctl.result()
    (try_dir / "result.json").write_text(json.dumps(res, indent=1, default=str), encoding="utf-8")
    if write_records and res["status"] == "done":
        try:
            rec = core.rollout_records(job, try_dir, k, res, allow_fenced=allow_fenced)
            core.write_records(rec, try_dir / "rollout.jsonl")
            core.write_master(rec, try_dir / "master.jsonl.gz")
            (try_dir / "state_refs.jsonl").write_text("".join(json.dumps(x) + "\n" for x in rec["state_refs"]),
                                                     encoding="utf-8")
            res["records"] = {"steps": len(rec["steps"]), "t1_match": rec["report"]["t1_match"],
                              "rollout_id": rec["rollout"]["id"], "publishable": core.publishable(rec),
                              "master": "master.jsonl.gz", "master_name": core.master_name(rec)}
        except Exception as exc:                 # noqa: BLE001
            res["records"] = {"error": f"{type(exc).__name__}: {exc}", "trace": traceback.format_exc()[-1500:]}
        (try_dir / "result.json").write_text(json.dumps(res, indent=1, default=str), encoding="utf-8")
    log(f"{job['job_id']}.k{k}: {res['status']} stop={res['stop_reason']} cleared={res['cleared']} "
        f"moves={res['moves']} turns={res['turns']} tokens={res['tokens']} replay={res['replay']['verdicts']} "
        f"assigned={(res.get('assignment') or {}).get('mode')} policy={res.get('policy_version')} "
        f"first_live={json.dumps(res.get('first_live'))[:160]} wall={res['wall_s']}s")
    return res


def _play_session(ctl: TryController, job: dict, try_dir: Path, solver_tmpl, spec, lane: int) -> None:
    """A fresh game + harness session in try_dir, restored and played by ctl (the try's whole life)."""
    if try_dir.exists():
        shutil.rmtree(try_dir, ignore_errors=True)
    try_dir.mkdir(parents=True, exist_ok=True)
    ctl.try_dir = try_dir
    solver = copy.deepcopy(solver_tmpl)
    solver.job_dir = try_dir
    solver.save_request_logs = True
    solver._warmup_remaining, solver._warmup_lock = 0, threading.Lock()   # never the Kaggle warmup RESET here
    game = taaf.game_api.GameAPI(env_name=job["game_id"], arcade_spec=spec)
    try:
        game.start_game(_ARCADE_SESSION)
        run = game.game_run
        stem = solver._run_stem(run.game_id, job["pass"])
        agent = RolloutAgent(model=solver.model, timeout=solver.analyzer_timeout, save_request_logs=True,
                             dispatch_index=lane, api_key=solver._local_server_api_key or None,
                             base_url=solver._local_server_base_url or None, provider=None)
        agent._gtr = ctl
        agent._arc3_state_off = job["mode"] == "replay_exact"     # no turn snapshots while replaying the prefix
        session = RolloutSession(solver=solver, game=game, analyzer=agent, game_index=lane, pass_index=job["pass"],
                                 state_path=solver._artifacts_dir() / f"{stem}_{RUNTIME_STATE_FILENAME}",
                                 transcript_path=solver._transcripts_dir() / f"{stem}.txt",
                                 analysis_html_relpath=f"solver_analysis/{stem}.html",
                                 stop_event=solver._stop_event,
                                 viewer_data_path=solver._artifacts_dir() / f"{stem}_viewer_data.json")
        session._gtr = ctl
        ctl.session, ctl.agent = session, agent
        ctl.base_url = getattr(getattr(agent, "_model", None), "base_url", None)
        session.play()
    except Exception as exc:                     # noqa: BLE001 - the record says why
        ctl.abort(f"session failed: {type(exc).__name__}: {exc}")
        log(traceback.format_exc()[-2000:])
        if game.game_run is not None:
            try:
                solver._finish_after_error(game, exc)     # (a child's solver was relocated in place)
            except Exception:                    # noqa: BLE001
                pass


# ------------------------------------------------------------------------------------------------ one node, K siblings
def fork_available() -> bool:
    return hasattr(os, "fork") and os.environ.get("ARC3_ROLLOUT_FORK", "1") != "0"


def run_node(job: dict, solver_tmpl, spec, out_root: Path, **kw) -> list[dict]:
    """All K tries of one sibling job (_run_node). A snapshot job whose state file does not restore falls back to
    replaying the source's request log, when the job names one."""
    res = _run_node(job, solver_tmpl, spec, out_root, **kw)
    src = job.get("source") or {}
    failed = [r for r in res if "snapshot restore failed" in str(r.get("aborted") or r.get("stop_reason") or "")]
    if job.get("mode") == "snapshot" and failed and len(failed) == len(res) and src.get("requests") \
            and Path(str(src["requests"])).exists():
        log(f"{job['job_id']}: {failed[0].get('aborted') or failed[0].get('stop_reason')}; falling back to replay_exact")
        kw.pop("prepared", None)
        res = _run_node(dict(copy.deepcopy(job), mode="replay_exact"), solver_tmpl, spec, out_root, **kw)
        for r in res:
            r["snapshot_fallback"] = True
    return res


def _run_node(job: dict, solver_tmpl, spec, out_root: Path, *, lanes: Lanes, fork: bool | None = None,
              deadline: float | None = None, group_kw: dict | None = None, write_records: bool = True,
              allow_fenced: bool = False, prepared: tuple | None = None) -> list[dict]:
    """All K tries of one sibling job. fork: restore once in <job>/restore/ and fork the K siblings at the origin
    (Linux); else K independent restores (each takes a lane at its origin). Returns the K results in try order."""
    prepared = prepared or prepare(job)
    job = prepared[0]
    ks = list(range(job["tries"]))
    out_root = Path(out_root)
    fork = fork_available() if fork is None else fork
    if not fork:
        with ThreadPoolExecutor(max_workers=len(ks), thread_name_prefix=f"gtr-{job['job_id'][-12:]}") as pool:
            futs = [pool.submit(run_try, job, k, solver_tmpl, spec, out_root, lane=k, prepared=prepared,
                                write_records=write_records, allow_fenced=allow_fenced, lanes=lanes,
                                deadline=deadline) for k in ks]
            return [f.result() for f in futs]
    _job, facts, plan, decisions = prepared
    g = Group(job, ks, out_root, lanes, deadline=deadline, **(group_kw or {}))
    ctl = TryController(job, None, plan=plan, facts=facts, source_decisions=decisions)
    ctl.role, ctl.group, ctl.deadline = "parent", g, deadline
    ctl.on_origin = ctl.fork_siblings
    try:
        _play_session(ctl, job, out_root / job["job_id"] / "restore", solver_tmpl, spec, 0)
    except BaseException:
        if ctl.role == "child":
            g.exit_fn(3)
        raise
    finally:
        if ctl.role == "parent" and ctl.lanes_held:
            lanes.release(ctl.lanes_held)
    if ctl.role == "child":                      # a sibling's play ended: write it down and leave
        code = 0
        try:
            _finish_try(ctl, job, ctl.k, write_records=write_records, allow_fenced=allow_fenced)
        except BaseException:                    # noqa: BLE001
            code = 4
            try:
                log(traceback.format_exc()[-1500:])
            except Exception:                    # noqa: BLE001
                pass
        finally:
            g.exit_fn(code)
    parent = ctl.result()
    (out_root / job["job_id"] / "restore" / "result.json").write_text(json.dumps(parent, indent=1, default=str),
                                                                      encoding="utf-8")
    results = []
    for k in ks:
        p = g.child_dir(k) / "result.json"
        if p.exists():
            r = json.loads(p.read_text(encoding="utf-8"))
        elif k in g.unforked:
            r = {"job": job["job_id"], "try": k, "status": "not_started",
                 "stop_reason": "deadline before a lane was free", "cleared": False,
                 "assignment": assignment_of(job, k)}
        else:
            r = {"job": job["job_id"], "try": k, "status": "child_failed" if g.children else parent["status"],
                 "stop_reason": parent.get("aborted") or parent.get("stop_reason"), "cleared": False,
                 "assignment": assignment_of(job, k)}
        r["exit_code"] = g.exit_codes.get(k)
        results.append(r)
    return results


def run_job(job: dict, solver_tmpl, spec, out_root: Path, *, lanes: int = 1, **kw) -> list[dict]:
    """K tries of one job; each restores from scratch (a fresh game, harness and coach)."""
    prepared = prepare(job)
    k_n = prepared[0]["tries"]
    if lanes <= 1:
        return [run_try(job, k, solver_tmpl, spec, out_root, lane=0, prepared=prepared, **kw) for k in range(k_n)]
    with ThreadPoolExecutor(max_workers=lanes, thread_name_prefix="gtree-try") as pool:
        futs = [pool.submit(run_try, job, k, solver_tmpl, spec, out_root, lane=k % lanes, prepared=prepared, **kw)
                for k in range(k_n)]
        return [f.result() for f in futs]


def run_queue(jobs: list[dict], solver_tmpl, spec, out_root: Path, *, lanes: int, deadline: float | None = None,
              **kw) -> dict:
    """Every try of every job over `lanes` concurrent sessions (tries of one job share the job's preparation)."""
    out_root = Path(out_root)
    out_root.mkdir(parents=True, exist_ok=True)
    work, summary = [], {"jobs": len(jobs), "tries": 0, "results": [], "errors": []}
    for job in jobs:
        try:
            p = prepare(job)
        except Exception as exc:                 # noqa: BLE001 - a bad job is skipped and reported
            summary["errors"].append({"job": job.get("job_id"), "error": f"{type(exc).__name__}: {exc}"})
            continue
        work += [(p, k) for k in range(p[0]["tries"])]
    lock = threading.Lock()

    def one(item, lane):
        p, k = item
        if deadline is not None and time.time() > deadline:
            return {"job": p[0]["job_id"], "try": k, "status": "skipped_deadline"}
        r = run_try(p[0], k, solver_tmpl, spec, out_root, lane=lane, prepared=p, **kw)
        with lock:
            summary["tries"] += 1
            summary["results"].append({x: r.get(x) for x in ("job", "try", "status", "stop_reason", "cleared",
                                                             "moves", "turns", "tokens", "wall_s")})
            (out_root / "summary.json").write_text(json.dumps(summary, indent=1), encoding="utf-8")
        return r

    with ThreadPoolExecutor(max_workers=max(1, lanes), thread_name_prefix="gtree-try") as pool:
        list(pool.map(lambda x: one(x[1], x[0] % max(1, lanes)), enumerate(work)))
    (out_root / "summary.json").write_text(json.dumps(summary, indent=1), encoding="utf-8")
    return summary


def load_jobs(path: str | Path) -> list[dict]:
    """A directory of <job>.json files, or one .jsonl file."""
    p = Path(path)
    if p.is_dir():
        return [json.loads(f.read_text(encoding="utf-8")) for f in sorted(p.glob("*.json"))]
    return [json.loads(x) for x in p.read_text(encoding="utf-8").splitlines() if x.strip()]


# ------------------------------------------------------------------------------------------------ the server loop
def _round_of(p: Path) -> int:
    head = p.name.split("-", 1)[0]
    return int(head) if head.isdigit() else 0


def _brief(x: Any, n: int = 300) -> Any:
    """A small copy of a failure detail for the summary (long strings cut)."""
    if isinstance(x, dict):
        return {k: _brief(v, n) for k, v in list(x.items())[:16]}
    if isinstance(x, list):
        return [_brief(v, n) for v in x[:8]]
    if isinstance(x, str) and len(x) > n:
        return x[:n] + "..."
    return x


def serve(jobs_dir: str | Path, solver_tmpl, spec, out_root: Path, *, lanes: int = 10, deadline: float | None = None,
          restorers: int | None = None, poll_s: float = 30.0, keep_rounds: int | None = 2,
          fork: bool | None = None, once: bool = False, stop_file: str | Path | None = None,
          group_kw: dict | None = None, write_records: bool = True, allow_fenced: bool = False) -> dict:
    """The rollout server: watch jobs_dir (round-*/NNNN-PPPPP-<job>.json, staged by the VM host while the notebook
    runs) and play every sibling job, `restorers` nodes in flight (restoring holds no lane; at the origin a node takes
    one lane per sibling as lanes come free). Oldest kept round first, priority order inside a round: the learner refills only when the queue
    runs low, so a new round lands behind the previous round's last jobs, which are played, not dropped (3-Oct pilot:
    newest-round-only dropped every round's tail and only the first four games of the alphabet were ever played).
    keep_rounds: only the newest that many rounds are played; an older round's unstarted jobs are dropped (a stale
    backlog, e.g. a new VM in an old campaign, never replays; None / 0 = keep every round). Ends at the deadline, at
    stop_file, or (once) when the queue is empty."""
    out_root = Path(out_root)
    out_root.mkdir(parents=True, exist_ok=True)
    L = Lanes(lanes)
    use_fork = fork_available() if fork is None else fork
    restorers = restorers or max(1, lanes // 5) + 2   # one node more than the lanes hold: its siblings fill lanes
                                                      # that a straggling sibling of another node leaves free
    summary = {"lanes": lanes, "restorers": restorers, "fork": use_fork, "keep_rounds": keep_rounds,
               "started_at": time.time(), "nodes": 0, "tries": 0, "cleared": 0, "results": [], "errors": [],
               "skipped_old_round": [], "skipped_fenced": []}
    lock = threading.Lock()
    started: set[str] = set()
    running: dict[str, int] = {}                 # job id -> tries, while the node is in flight

    def stopping() -> bool:
        return bool((deadline is not None and time.time() > deadline) or (stop_file and Path(stop_file).exists()))

    def save() -> None:
        summary["updated_at"] = time.time()
        live = list(running.values())           # nodes in flight (restoring or playing): the status page's "running"
        summary["running"] = {"nodes": len(live), "tries": sum(live), "jobs": sorted(running)}
        tmp = out_root / "summary.json.tmp"
        tmp.write_text(json.dumps(summary, indent=1, default=str), encoding="utf-8")
        os.replace(tmp, out_root / "summary.json")

    def node(job: dict) -> None:
        t = time.time()
        jid = str(job.get("job_id"))
        with lock:
            running[jid] = int(job.get("tries") or len(job.get("assignments") or []) or 1)
            save()
        try:
            res = run_node(job, solver_tmpl, spec, out_root, lanes=L, fork=use_fork, deadline=deadline,
                           group_kw=group_kw, write_records=write_records, allow_fenced=allow_fenced)
        except Exception as exc:                 # noqa: BLE001 - a bad node is reported, the server goes on
            with lock:
                running.pop(jid, None)
                summary["errors"].append({"job": job.get("job_id"), "error": f"{type(exc).__name__}: {exc}"[:500],
                                          "trace": traceback.format_exc()[-1200:]})
                save()
            return
        o, src = job.get("origin") or {}, job.get("source") or {}
        with lock:
            running.pop(jid, None)
            summary["nodes"] += 1
            for r in res:
                summary["tries"] += 1
                summary["cleared"] += bool(r.get("cleared"))
                row = {
                    "job": r.get("job"), "try": r.get("try"), "status": r.get("status"),
                    "mode": (r.get("assignment") or {}).get("mode"), "stop": r.get("stop_reason"),
                    "cleared": r.get("cleared"), "moves_to_clear": r.get("moves_to_clear"), "turns": r.get("turns"),
                    "tokens": r.get("tokens"), "policy": r.get("policy_version"), "restore_s": r.get("restore_s"),
                    "first_prompt": (r.get("first_live") or {}).get("prompt_tokens"),
                    "first_cached": (r.get("first_live") or {}).get("cached_tokens"),
                    "exit": r.get("exit_code"), "node_wall_s": round(time.time() - t, 1),
                    # the restart point: the learner blocks it when its restore fails (diverged / aborted)
                    "node": o.get("t1"), "source": src.get("rollout_id"), "seq": o.get("seq")}
                if r.get("status") not in ("done", None):       # why it failed, readable later (3-Oct: ar25)
                    row["diverged"] = _brief(r.get("diverged"))
                    row["aborted"] = _brief(r.get("aborted"))
                    mism = (r.get("origin") or {}).get("mismatch")
                    if mism:
                        row["origin_mismatch"] = _brief(mism)
                summary["results"].append(row)
            save()

    pool = ThreadPoolExecutor(max_workers=restorers, thread_name_prefix="gtr-node")
    active: dict = {}
    log(f"server: jobs {jobs_dir} -> {out_root}, lanes {lanes}, restorers {restorers}, fork {use_fork}, "
        f"deadline {time.strftime('%H:%M:%S', time.localtime(deadline)) if deadline else None}")
    try:
        while True:
            files = [p for p in sorted(Path(jobs_dir).rglob("*.json")) if not p.name.startswith(".")] \
                if Path(jobs_dir).exists() else []
            todo = [p for p in files if p.name not in started]
            if keep_rounds and files:
                kept = sorted({_round_of(p) for p in files})[-int(keep_rounds):]
                for p in [p for p in todo if _round_of(p) < kept[0]]:
                    started.add(p.name)
                    summary["skipped_old_round"].append(p.name)
                todo = [p for p in todo if _round_of(p) >= kept[0]]
            todo.sort(key=lambda p: (_round_of(p), p.name))      # oldest kept round first, then priority
            while todo and len(active) < restorers and not stopping():
                p = todo.pop(0)
                started.add(p.name)
                try:
                    job = json.loads(p.read_text(encoding="utf-8"))
                except (OSError, ValueError) as exc:
                    started.discard(p.name)              # half-staged: try again next scan
                    log(f"server: {p.name} unreadable ({exc}); later")
                    continue
                if str(job.get("game_id", "")).split("-")[0] in core.FENCED and not allow_fenced:
                    summary["skipped_fenced"].append(p.name)
                    continue
                active[pool.submit(node, job)] = p.name
            if not active and (once or stopping()):
                break
            if active:
                done, _ = wait(list(active), timeout=poll_s, return_when=FIRST_COMPLETED)
                for f in done:
                    active.pop(f, None)
            else:
                time.sleep(max(0.1, min(poll_s, (deadline - time.time()) if deadline else poll_s)))
    finally:
        pool.shutdown(wait=True)
        summary["ended_at"] = time.time()
        save()
    log(f"server done: {summary['nodes']} nodes, {summary['tries']} tries, {summary['cleared']} cleared, "
        f"{len(summary['errors'])} errors")
    return summary


def serve_sessions(solver_tmpl, spec, out_root: Path, *, lanes: int, end: float, ctl: str | Path = "/kaggle/rollout/ctl",
                   sess_root: str | Path = "/kaggle/rollout/sess", url: str | None = None,
                   restorers: int | None = None, poll_s: float = 30.0, keep_rounds: int | None = 2) -> dict:
    """One server for many RL rounds (4-Oct-2026, hot-swap; gcp/controllers/rl/box/README.md). The box host writes
    ctl/next.json = {"session": <campaign>, "delta": <delta.safetensors path or null>}; this wakes the server
    (hotswap.py wake), applies the delta when it is new (hotswap.py apply: the round's merged LoRA weights in place),
    serves the session's jobs (serve(): sess/<campaign>/jobs -> out_root/<campaign>, ends at sess/<campaign>/STOP,
    which the host mirrors from the campaign's STOP) and writes out_root/_sessions/<campaign>.json (the host's signal
    that the session is over). The server stays awake for the next session (the box trains on other cards);
    ARC3_ROLLOUT_SLEEP=1 also puts it to sleep between sessions (hotswap.py sleep: needs --enable-memory-saver). ctl/END or `end` ends the loop. A failed wake or apply ends it too: the weights may be half
    updated, so the host restarts the container rather than serve a wrong model."""
    import subprocess
    url = url or os.environ.get("ARC3_SERVER_URL", "http://127.0.0.1:8001")
    ctl, sess_root, out_root = Path(ctl), Path(sess_root), Path(out_root)
    marks = out_root / "_sessions"
    marks.mkdir(parents=True, exist_ok=True)
    helper = Path(__file__).with_name("hotswap.py")
    py = os.environ.get("ARC3_SGL_PYTHON", "/tmp/sgl-intel/venv/bin/python")   # the server's venv: torch, safetensors
    py = py if Path(py).exists() else sys.executable
    awake, applied, served = True, None, []

    def hs(*args: str) -> dict:
        # output to a file, never a pipe: apply starts torch's shm manager, a daemon that inherits the helper's
        # stdout, so a pipe never reaches EOF and subprocess.run(capture_output=True) waited forever (4-Oct box test)
        logf = marks / f".hotswap-{args[0]}.log"
        with open(logf, "w", encoding="utf-8") as fo:
            p = subprocess.run([py, str(helper), *args], stdout=fo, stderr=subprocess.STDOUT, timeout=3600)
        text = logf.read_text(encoding="utf-8", errors="replace")
        lines = [ln for ln in text.splitlines() if ln.startswith("{")]
        try:
            res = json.loads(lines[-1]) if lines else {}
        except ValueError:
            res = {"ok": False}
        res["rc"] = p.returncode
        if p.returncode:
            res["out"] = text[-800:]
        log(f"hotswap {args[0]}: {json.dumps(res)[:400]}")
        return res

    def mark(name: str, doc: dict) -> None:
        tmp = marks / f"{name}.json.tmp"
        tmp.write_text(json.dumps(doc, indent=1, default=str), encoding="utf-8")
        os.replace(tmp, marks / f"{name}.json")

    log(f"sessions: control {ctl}, sessions {sess_root} -> {out_root}, server {url}, "
        f"until {time.strftime('%H:%M:%S', time.localtime(end))}")
    while time.time() < end and not (ctl / "END").exists():
        try:
            nxt = json.loads((ctl / "next.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            time.sleep(10)
            continue
        sess = str(nxt.get("session") or "")
        if not sess or (marks / f"{sess}.json").exists():
            time.sleep(10)
            continue
        info: dict = {"session": sess, "delta": nxt.get("delta"), "asked_at": time.time()}
        if not awake:
            r = hs("wake", url)
            info["wake"] = r
            if not r.get("ok"):
                info["error"] = "wake failed"
                mark(sess, info)
                break
            awake = True
        delta = nxt.get("delta")
        if delta and delta != applied:
            r = hs("apply", str(delta), url)
            info["apply"] = r
            if r.get("rc"):
                info["error"] = "apply failed"
                mark(sess, info)
                break
            applied = delta
        info.update(model=applied, started_at=time.time())
        mark(f"{sess}.started", info)
        summ = serve(sess_root / sess / "jobs", solver_tmpl, spec, out_root / sess, lanes=lanes, deadline=end,
                     restorers=restorers, poll_s=poll_s, keep_rounds=keep_rounds, stop_file=sess_root / sess / "STOP")
        info.update(nodes=summ["nodes"], tries=summ["tries"], cleared=summ["cleared"], ended_at=time.time())
        if os.environ.get("ARC3_ROLLOUT_SLEEP") == "1":   # off by default: the 4-Oct box keeps its play cards awake
            r = hs("sleep", url)
            info["sleep"] = r
            awake = not r.get("ok")
        served.append(sess)
        mark(sess, info)
    return {"sessions": served, "awake": awake, "model": applied}


def bind(bm: Any, *, jobs: str | None = None, out: str | None = None, lanes: int | None = None) -> None:
    """Notebook override cell: replace bm.run with the rollout queue (same signature, so his run cell is unchanged:
    it builds bm.games for the spec, then awaits bm.run). Inert unless ARC3_ROLLOUT is set."""
    if not os.environ.get("ARC3_ROLLOUT"):
        log("ARC3_ROLLOUT unset: bm.run left alone")
        return
    server = os.environ["ARC3_ROLLOUT"].strip().lower() == "server"
    jobs = jobs or os.environ.get("ARC3_ROLLOUT_JOBS", "/kaggle/rollout/jobs")
    out = out or os.environ.get("ARC3_ROLLOUT_OUT", "/kaggle/working/gtree-rollout")
    lanes = int(lanes or os.environ.get("ARC3_ROLLOUT_LANES", "0") or 0) or \
        (10 if server else int(bm.solver.concurrency))          # server: his 10 server slots
    if _coach_mod is not None and not _coach_mod.policy_spec():
        os.environ["ARC3_COACH"] = "policy"      # master switch for the coach hooks; each try sets its own spec
    os.environ.setdefault("ARC3_COACH_LOG", str(Path(out) / "coach-decisions.jsonl"))
    if server:
        # the lanes are the admission control now; his gate (over-admission 11) would hold children's slots
        os.environ["ARC3_MAX_ACTIVE_STREAMS"] = "0"
        os.environ.setdefault("ARC3_COACH_POLICY", "@/kaggle/rollout/policy/current.json")
    budget_s = float(os.environ.get("ARC3_ROLLOUT_BUDGET_S", "7200") or 7200)

    async def run(soft_end_time=None, runtime_environment=None, minimal_diagnostics=False):
        solver = copy.deepcopy(bm.solver)
        solver.runtime_environment = runtime_environment
        solver.soft_end_time = soft_end_time
        solver.minimal_diagnostics = False
        spec = bm.games[0].arcade_spec
        deadline = soft_end_time.timestamp() if soft_end_time is not None else None
        if server and os.environ.get("ARC3_ROLLOUT_SESSIONS") == "1":
            # hot-swap sessions: one server for many rounds; his run's soft end (his game budget) does not apply
            end = time.time() + budget_s
            log(f"rollout sessions: out {out}, lanes {lanes}, budget {budget_s:.0f}s, fork {fork_available()}")
            res = await asyncio.to_thread(
                serve_sessions, solver, spec, Path(out), lanes=lanes, end=end,
                restorers=int(os.environ.get("ARC3_ROLLOUT_RESTORERS", "0") or 0) or None,
                poll_s=float(os.environ.get("ARC3_ROLLOUT_POLL_S", "30")),
                keep_rounds=int(os.environ.get("ARC3_ROLLOUT_KEEP_ROUNDS", "2") or 0) or None)
            log(f"rollout sessions done: {res}")
            return
        if server:
            deadline = min(x for x in (deadline, time.time() + budget_s) if x is not None)
            log(f"rollout server: jobs {jobs} -> {out}, lanes {lanes}, budget {budget_s:.0f}s, fork "
                f"{fork_available()}, policy {os.environ.get('ARC3_COACH_POLICY')}")
            summary = await asyncio.to_thread(
                serve, jobs, solver, spec, Path(out), lanes=lanes, deadline=deadline,
                restorers=int(os.environ.get("ARC3_ROLLOUT_RESTORERS", "0") or 0) or None,
                poll_s=float(os.environ.get("ARC3_ROLLOUT_POLL_S", "30")),
                keep_rounds=int(os.environ.get("ARC3_ROLLOUT_KEEP_ROUNDS", "2") or 0) or None,
                stop_file=os.environ.get("ARC3_ROLLOUT_STOP_FILE", "/kaggle/rollout/STOP"))
            log(f"rollout server done: {summary['nodes']} nodes, {summary['tries']} tries")
            return
        todo = load_jobs(jobs)
        log(f"queue: {len(todo)} jobs from {jobs} -> {out}, lanes {lanes}")
        summary = await asyncio.to_thread(run_queue, todo, solver, spec, Path(out), lanes=lanes, deadline=deadline)
        log(f"queue done: {summary['tries']} tries, {len(summary['errors'])} job errors")

    bm.run = run
    log(f"bound ({'server' if server else 'queue'}): jobs {jobs}, out {out}, lanes {lanes}, coach hooks "
        f"{'on' if _coach_mod else 'absent'}")
