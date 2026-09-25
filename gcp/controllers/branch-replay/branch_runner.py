"""Branch-replay runner (replaces v12_run.py on the VM; also runs locally in replay-only mode).

Son, 25-Sep: "For each level that it solves: assume N turns. For i in 1..N: replay until finishing turn i,
generate traces from turn i+1 onward with the same prompt but with high, medium and low thinking. Measure
action efficiency (remaining actions) and token efficiency."

Mechanics: a fresh offline game + a fresh ToolAgent per job. For the first `replay_through_step` solver turns
the agent's `_chat_completion` returns the RECORDED responses (thinking, content, tool calls) parsed from the
original transcript; the recorded python snippets run in the real sandbox against the real engine, so the
game, the runtime state, the tool results and the persistent history are rebuilt exactly (turn yields and
request errors are re-played too, so turn boundaries match). Then the agent switches to live requests with a
per-request reasoning-effort override and plays until the level is cleared or a cap is hit.

The preamble (bundle path, pickles, environment asserts, 7 games) is the pinned runner's so runtime_probe.attest
still sees the same benchmark object; only `bm.run(...)` is replaced by the branch driver.
"""

import asyncio
import json
import os
import pickle
import sys
from datetime import datetime, timedelta
from pathlib import Path

BUNDLE = Path(os.environ.get("ARC3_BUNDLE_DIR", "/opt/arc3/bundle"))
WORKING = Path(os.environ.get("ARC3_WORK_DIR", "/opt/arc3/work"))
ENV_FILES = os.environ.get("ARC3_ENV_FILES", "/opt/arc3/environment_files")
WORKING.mkdir(parents=True, exist_ok=True)

os.environ["MPLBACKEND"] = "Agg"
os.environ["TAAF_RUN_AS_SUBMISSION"] = "0"
os.environ["TAAF_MINIMAL_DIAGNOSTICS"] = "0"
os.environ["ONLY_RESET_LEVELS"] = "true"
os.environ.setdefault("RECORDINGS_DIR", str(WORKING / "server_recording"))

# Bundled repos importable, exactly like the notebook's cell 8.
for repo in sorted((BUNDLE / "src").iterdir(), reverse=True):
    for candidate in (repo / "src", repo):
        if candidate.is_dir():
            sys.path.insert(0, str(candidate))

with open(BUNDLE / "deploy_target.pkl", "rb") as fh:
    target = pickle.load(fh)
target.actual_run_as_submission = False
target.is_competition_rerun = False

with open(BUNDLE / "benchmark_initial.pkl", "rb") as fh:
    bm = pickle.load(fh)
bm.job_dir = WORKING
bm.solver.max_runtime_s_per_game = float(os.environ["ARC3_MAX_RUNTIME_S_PER_GAME"])
bm.solver.concurrency = int(os.environ["ARC3_BENCHMARK_CONCURRENCY"])
bm.solver.save_request_logs = False
assert bm.solver.max_runtime_s_per_game == 7920.0
assert bm.solver.concurrency == 7
assert bm.solver.save_request_logs is False
assert os.environ["ARC3_HISTORY_MODE"] == "full_context"
assert os.environ["LOCAL_ANALYZER_CONTEXT_WINDOW"] == "102985"
assert os.environ["ARC3_ACTION_CAP"] == "14"
assert os.environ["ARC3_POST_LEVEL_UNCAPPED_TURNS"] == "0"
assert "ARC3_SAME_CONTEXT_LEVEL_REFLECTION_ENABLED" not in os.environ
print(
    "Experimental runtime lock: 7 workers, 7920 seconds/game, hard-seven only, "
    "cap14, full_context102985, reflection dormant, request logs off; BRANCH REPLAY driver"
)

# --- cell 14, offline branch, WITHOUT the 4-game interactive truncation ------
import arc_agi  # noqa: E402
import taaf.game_api  # noqa: E402

spec = taaf.game_api.ArcadeSpec(operation_mode=arc_agi.OperationMode.OFFLINE, environments_dir=ENV_FILES)
arcade = arc_agi.Arcade(operation_mode=arc_agi.OperationMode.OFFLINE, environments_dir=ENV_FILES)
game_ids = [e.game_id for e in arcade.available_environments]
_subset = os.environ.get("ARC3_GAME_SUBSET", "").strip()
if _subset:
    _want = {t.strip().lower() for t in _subset.replace(",", " ").split() if t.strip()}
    game_ids = [g for g in game_ids if g[:4].lower() in _want or g.lower() in _want]
    print(f"[subset] ARC3_GAME_SUBSET={_subset!r} -> {len(game_ids)} games: {game_ids}")
assert game_ids, f"no offline environments under {ENV_FILES}"
assert len(game_ids) == 7, f"hard-seven experiment requires 7 games, got {len(game_ids)}"
bm.games = [taaf.game_api.GameAPI(env_name=g, arcade_spec=spec) for g in game_ids]
bm.n_passes = 1
bm.game_weights = None
print(f"games: {len(bm.games)} | solver: {type(bm.solver).__name__}")

# The submission branch caps the whole run at start + 11h20m; game budgets
# One wave: 7 lanes x 7 hard games, 7920 s each = the whole 132-minute suite per game.
soft_end = datetime.now() + timedelta(hours=11, minutes=20)

# =====================================================================================================
# Branch driver
# =====================================================================================================
import copy  # noqa: E402
import threading  # noqa: E402
import time  # noqa: E402
import traceback  # noqa: E402
from concurrent.futures import ThreadPoolExecutor  # noqa: E402
from dataclasses import dataclass, field  # noqa: E402
from typing import Any  # noqa: E402

import requests  # noqa: E402
from inference.agent import tool_agent as ta  # noqa: E402
from inference.framework import solver as sv  # noqa: E402
from inference.utils.openai_compat import build_chat_payload  # noqa: E402

PACK = Path(os.environ.get("ARC3_BRANCH_PACK", "/opt/arc3/branchpack"))
OUT = WORKING / "branch"
OUT.mkdir(parents=True, exist_ok=True)
GAME_S = float(os.environ["ARC3_MAX_RUNTIME_S_PER_GAME"])
LANES = int(os.environ.get("ARC3_BRANCH_LANES", os.environ["ARC3_BENCHMARK_CONCURRENCY"]))
DEADLINE_S = float(os.environ.get("ARC3_BRANCH_DEADLINE_MIN", "185")) * 60.0
SHARD = os.environ.get("ARC3_BRANCH_SHARD", "").strip()          # "k/n" or ""
REPLAY_ONLY = os.environ.get("ARC3_BRANCH_REPLAY_ONLY", "0") == "1"   # local fidelity test: no model
HIGH_TEMPLATE_PATH = os.environ.get("ARC3_HIGH_CHAT_TEMPLATE", "/opt/arc3/high-chat-template.jinja")
T0 = time.monotonic()
_results_lock = threading.Lock()
_log_lock = threading.Lock()


def logline(msg: str) -> None:
    with _log_lock:
        print(f"[branch {time.strftime('%H:%M:%S')}] {msg}", flush=True)


class ReplayDivergence(RuntimeError):
    pass


class ReplayAgent(ta.ToolAgent):
    """ToolAgent whose first N solver turns come from a recording; then live with an effort override."""

    def __init__(self, job: dict, turns: list[dict], **kw):
        super().__init__(**kw)
        self.job = job
        self.effort = job["effort"]
        self.turns = [t for t in turns if t["step"] <= job["replay_through_step"]]
        self.turn_idx = 0
        self.req_idx = 0
        self.replaying = len(self.turns) > 0
        self.live = False
        self.session: "BranchSession | None" = None
        self._yield_cfg = self._yield_seconds
        self._pending_error = False
        self.live_requests: list[dict] = []
        self.replay_requests = 0
        self.switch: dict | None = None
        self.notes: list[str] = []

    # ---- turn boundary hooks --------------------------------------------------------------------
    def analyze(self, state_path, action_num, *a, **kw):
        self._yield_seconds = self._yield_cfg
        analysis_step = kw.get("analysis_step")
        if self.replaying:
            if self.turn_idx >= len(self.turns):
                self._switch_to_live(action_num)
            else:
                t = self.turns[self.turn_idx]
                if analysis_step is not None and t["step"] != analysis_step:
                    raise ReplayDivergence(f"turn {self.turn_idx}: recorded step {t['step']} vs live {analysis_step}")
                if t["action_at_start"] != ta._display_action_number(action_num):
                    raise ReplayDivergence(
                        f"turn {self.turn_idx} step {t['step']}: recorded action {t['action_at_start']} vs live {ta._display_action_number(action_num)}")
                tl = next((r["time_left_s"] for r in t["requests"] if r.get("time_left_s") is not None), None)
                if tl is not None and self.session is not None:
                    self.session.set_clock(tl)
                self.req_idx = 0
        if self.live and self.session is not None and analysis_step is not None:
            self.session.live_steps.add(int(analysis_step))
            self.session.live_turns = len(self.session.live_steps)
        result = super().analyze(state_path, action_num, *a, **kw)
        if self.replaying and self.turn_idx < len(self.turns):
            t = self.turns[self.turn_idx]
            if self.req_idx != len(t["requests"]):
                raise ReplayDivergence(f"turn step {t['step']}: consumed {self.req_idx}/{len(t['requests'])} recorded requests")
            self.turn_idx += 1
            self._pending_error = False
        return result

    def _switch_to_live(self, action_num: int) -> None:
        self.replaying = False
        self.live = True
        sess = self.session
        self.switch = {
            "action_count": sess.action_count if sess else None,
            "levels_completed": int(sess.game.current_state.levels_completed) if sess else None,
            "elapsed_s": round(time.monotonic() - T0, 1),
            "history_messages": len(self._history_messages),
            "generated_tokens_before": self.generated_tokens,
        }
        if sess is not None:
            sess.on_switch(self.job)
        logline(f"{self.job['job_id']}: replay done (actions={self.switch['action_count']}, levels={self.switch['levels_completed']}); live effort={self.effort}")

    # ---- model calls ------------------------------------------------------------------------------
    def _chat_completion(self, messages, *, tools, request_timeout_seconds=None, max_output_tokens_override=None,
                         thinking_override=None, temperature_override=None):
        if self.replaying:
            t = self.turns[self.turn_idx]
            if self._pending_error:
                self._pending_error = False
                raise requests.RequestException("replayed request_error")
            if self.req_idx >= len(t["requests"]):
                raise ReplayDivergence(f"turn step {t['step']}: live asked for request {self.req_idx + 1}, recorded {len(t['requests'])}")
            r = t["requests"][self.req_idx]
            self.req_idx += 1
            self.replay_requests += 1
            if self.req_idx == len(t["requests"]):
                if t["outcome"].startswith("yield"):
                    self._yield_seconds = 1e-6
                elif t["outcome"] == "request_error":
                    self._pending_error = True
            message = {"role": "assistant", "content": r["content"] or None, "reasoning_content": r["reasoning"],
                       "tool_calls": copy.deepcopy(r["tool_calls"])}
            return ta._ChatCompletionResult(message=message, finish_reason=r["finish_reason"], usage=None)
        if REPLAY_ONLY:
            raise RuntimeError("replay-only mode reached a live request")
        payload = build_chat_payload(
            provider=self._model.provider, model=self._model.model_id, messages=messages,
            max_tokens=(max(1, int(max_output_tokens_override)) if max_output_tokens_override is not None else self._max_output_tokens),
            temperature=(float(temperature_override) if temperature_override is not None else ta._LOCAL_ANALYZER_TEMPERATURE),
            top_p=ta._LOCAL_ANALYZER_TOP_P, top_k=ta._LOCAL_ANALYZER_TOP_K,
            thinking=(bool(thinking_override) if thinking_override is not None else bool(ta._LOCAL_ANALYZER_ENABLE_THINKING)),
            tools=tools, tool_choice=ta._request_tool_choice(tools), seed=ta._LOCAL_ANALYZER_SEED)
        # ---- reasoning effort override (the Qwen3.8 template: xhigh = careful sentence [default],
        # medium = no sentence, low = brief; 'high' = served template copy with a milder sentence) ----
        if self.effort in ("medium", "low"):
            kwargs = payload.setdefault("chat_template_kwargs", {})
            kwargs["reasoning_effort"] = self.effort
        elif self.effort == "high":
            payload["chat_template"] = HIGH_TEMPLATE
        elif self.effort != "xhigh":
            raise RuntimeError(f"unknown effort {self.effort}")
        started = time.monotonic()
        response = requests.post(f"{self._model.base_url.rstrip('/')}/chat/completions", headers=self._headers(), json=payload,
                                 timeout=request_timeout_seconds if request_timeout_seconds is not None else self._timeout)
        try:
            response.raise_for_status()
        except requests.HTTPError as exc:
            detail = response.text.strip()
            if 400 <= response.status_code < 500 and not ta._is_context_length_error(exc) and "context" not in detail.lower():
                # a malformed request would otherwise be retried forever by the solver (1 s backoff); fail the job instead
                raise RuntimeError(f"live request rejected ({response.status_code}): {detail[:300]}") from exc
            raise requests.RequestException(f"{exc} | response: {detail}" if detail else f"{exc}") from exc
        body = response.json()
        choices = body.get("choices", [])
        if not choices:
            raise requests.RequestException("server returned no choices")
        choice = choices[0]
        msg = choice.get("message", {}) or {}
        usage = body.get("usage") or {}
        self.live_requests.append({
            "elapsed_s": round(time.monotonic() - started, 2), "finish_reason": choice.get("finish_reason"),
            "prompt_tokens": usage.get("prompt_tokens"), "completion_tokens": usage.get("completion_tokens"),
            "cached_tokens": (usage.get("prompt_tokens_details") or {}).get("cached_tokens"),
            "reasoning_chars": len(ta._extract_reasoning_text(msg)), "content_chars": len(ta._normalize_message_content(msg.get("content", ""))),
            "tool_calls": len(msg.get("tool_calls") or []),
            "tool_arg_chars": sum(len(str((c.get("function") or {}).get("arguments") or "")) for c in (msg.get("tool_calls") or []) if isinstance(c, dict)),
            "action_count": self.session.action_count if self.session else None,
        })
        return ta._ChatCompletionResult(message=msg, finish_reason=str(choice.get("finish_reason", "") or ""), usage=body.get("usage"))


@dataclass
class BranchSession(sv._HarnessGameSession):
    job: dict = field(default_factory=dict)
    target_levels: int = 0
    live_started_at: float | None = None
    live_action_start: int = 0
    action_cap_abs: int | None = None
    live_deadline: float | None = None
    live_turns: int = 0
    live_steps: set = field(default_factory=set)
    turn_cap: int | None = None
    stop_reason: str = ""

    def set_clock(self, time_left_s: float) -> None:
        # Make timing_payload() report the original run's remaining time at this point.
        self.started_at = time.monotonic() - (self.solver.max_runtime_s_per_game - float(time_left_s))

    def budget_status(self) -> dict[str, float | None]:
        # The original showed "time left Ns (game Ns, suite Ns)" with game == suite (one wave).
        rem = self.timing_payload()["time_remaining_seconds"]
        return {"game_remaining_seconds": rem, "suite_remaining_seconds": rem}

    def on_switch(self, job: dict) -> None:
        if job.get("time_left_s") is not None:
            self.set_clock(job["time_left_s"])
        self.live_started_at = time.monotonic()
        self.live_action_start = self.action_count
        # Son, 25-Sep: "Each branch plays until level solve / spending 2x more turns / spending 2x more actions"
        self.action_cap_abs = self.action_count + int(job["action_cap_extra"])
        self.turn_cap = int(job["turn_cap"])
        self.live_deadline = time.monotonic() + float(job["time_cap_s"])      # VM-budget safety net only
        self.target_levels = int(job["expected_levels_completed"]) + 1

    def runtime_limit_reached(self) -> bool:
        # The emulated game clock is display-only; the branch is bounded by its own caps + the VM deadline.
        return False

    def should_stop(self) -> bool:
        run = self.game.game_run
        if run is None or run.state != "playing":
            self.stop_reason = self.stop_reason or "run_not_playing"; return True
        if self.stop_event.is_set():
            self.stop_reason = self.stop_reason or "stop_event"; return True
        if sv._is_run_complete(self.game):
            self.stop_reason = self.stop_reason or "run_complete"; return True
        if time.monotonic() - T0 >= DEADLINE_S:
            self.stop_reason = self.stop_reason or "vm_deadline"; return True
        ag = self.analyzer
        if REPLAY_ONLY and ag.turn_idx >= len(ag.turns):
            self.stop_reason = self.stop_reason or "replay_done"; return True
        if self.live_started_at is not None:
            if int(self.game.current_state.levels_completed) >= self.target_levels:
                self.stop_reason = self.stop_reason or "solved"; return True
            if self.action_cap_abs is not None and self.action_count >= self.action_cap_abs:
                self.stop_reason = self.stop_reason or "action_cap"; return True
            if self.turn_cap is not None and self.live_turns >= self.turn_cap:
                self.stop_reason = self.stop_reason or "turn_cap"; return True
            if self.live_deadline is not None and time.monotonic() >= self.live_deadline:
                self.stop_reason = self.stop_reason or "time_cap"; return True
        return False


def load_pack() -> tuple[list[dict], dict[str, list[dict]], dict[str, list[dict]]]:
    plan = json.loads((PACK / "plan.json").read_text(encoding="utf-8"))
    if SHARD:
        k, n = (int(x) for x in SHARD.split("/"))
        plan = [j for j in plan if int(j.get("group_index", 0)) % n == k]   # whole checkpoint groups per VM: siblings share the KV prefix
    turns = {p.stem: json.loads(p.read_text(encoding="utf-8")) for p in (PACK / "turns").glob("*.json")}
    actions = {p.stem: json.loads(p.read_text(encoding="utf-8")) for p in (PACK / "actions").glob("*.json")}
    return plan, turns, actions


def run_job(job: dict, turns: list[dict], actions: list[dict], solver: Any, run_session: Any) -> dict:
    job_id = job["job_id"]
    started = time.monotonic()
    rec: dict[str, Any] = {"job_id": job_id, **{k: job[k] for k in job if k != "job_id"}, "status": "started",
                           "started_at": datetime.utcnow().isoformat() + "Z"}
    game = taaf.game_api.GameAPI(env_name=job["game_id"], arcade_spec=spec)
    agent = None
    session = None
    try:
        game.start_game(run_session)
        agent = ReplayAgent(job, turns, model=solver.model, timeout=solver.analyzer_timeout, save_request_logs=False)
        stem = job_id
        session = BranchSession(
            solver=solver, game=game, analyzer=agent, game_index=0, pass_index=0,
            state_path=solver._artifacts_dir() / f"{stem}_{sv.RUNTIME_STATE_FILENAME}",
            transcript_path=solver._transcripts_dir() / f"{stem}.txt",
            analysis_html_relpath=f"solver_analysis/{stem}.html",
            stop_event=threading.Event(), viewer_data_path=solver._artifacts_dir() / f"{stem}_viewer_data.json",
            job=job)
        agent.session = session
        if not agent.replaying:          # i = 0 at level 1: nothing to replay, live from the first turn
            agent._switch_to_live(0)
        session.play()
        run = game.game_run
        # ---- fidelity: the replayed prefix must reproduce the recorded action sequence -------------
        replayed = [h.action for h in session.history_entries[1:]]
        exp_n = int(job["expected_action_count"])
        rec_actions = [a["a"] for a in actions[: exp_n]]
        switch_actions = agent.switch["action_count"] if agent.switch else session.action_count
        prefix_ok = replayed[:exp_n] == rec_actions and switch_actions == exp_n and len(replayed) >= exp_n
        rec.update({
            "status": "done", "stop_reason": session.stop_reason, "prefix_ok": prefix_ok,
            "prefix_mismatch_at": next((k for k, (x, y) in enumerate(zip(replayed[:exp_n], rec_actions)) if x != y), None) if not prefix_ok else None,
            "switch": agent.switch, "replay_requests": agent.replay_requests,
            "final_levels_completed": int(game.current_state.levels_completed), "final_action_count": session.action_count,
            "live_actions": session.action_count - session.live_action_start if session.live_started_at else None,
            "live_turns": session.live_turns, "live_requests": len(agent.live_requests),
            "live_completion_tokens": sum(int(r["completion_tokens"] or 0) for r in agent.live_requests),
            "live_prompt_tokens": sum(int(r["prompt_tokens"] or 0) for r in agent.live_requests),
            "live_cached_tokens": sum(int(r["cached_tokens"] or 0) for r in agent.live_requests),
            "live_reasoning_chars": sum(r["reasoning_chars"] for r in agent.live_requests),
            "live_content_chars": sum(r["content_chars"] for r in agent.live_requests),
            "live_tool_arg_chars": sum(r.get("tool_arg_chars", 0) for r in agent.live_requests),
            "live_wall_s": round(time.monotonic() - session.live_started_at, 1) if session.live_started_at else None,
            "solved": int(game.current_state.levels_completed) >= int(job["expected_levels_completed"]) + 1,
            "live_action_displays": [h.action for h in session.history_entries[1:]][exp_n:][:400],
            "requests": agent.live_requests,
            "final_score": run.final_score if run is not None else None,
            "wall_s": round(time.monotonic() - started, 1),
        })
    except Exception as exc:  # noqa: BLE001
        rec.update({"status": "error", "error": f"{type(exc).__name__}: {exc}", "traceback": traceback.format_exc()[-3000:],
                    "switch": getattr(agent, "switch", None), "replay_requests": getattr(agent, "replay_requests", None),
                    "final_action_count": session.action_count if session is not None and game.game_run is not None else None,
                    "wall_s": round(time.monotonic() - started, 1)})
        try:
            if game.game_run is not None and game.game_run.final_score is None:
                game.game_run.state = "crashed"; game.finish_game()
        except Exception:  # noqa: BLE001
            pass
    with _results_lock:
        with open(OUT / "results.jsonl", "a", encoding="utf-8") as fh:
            fh.write(json.dumps(rec, ensure_ascii=True) + "\n")
    logline(f"{job_id}: {rec['status']} stop={rec.get('stop_reason')} prefix_ok={rec.get('prefix_ok')} solved={rec.get('solved')} "
            f"live_actions={rec.get('live_actions')} (orig {job['orig_remaining_actions']}) tokens={rec.get('live_completion_tokens')} wall={rec.get('wall_s')}s")
    return rec


def branch_main() -> None:
    global HIGH_TEMPLATE
    plan, turns, actions = load_pack()
    done = set()
    if (OUT / "results.jsonl").exists():
        for line in (OUT / "results.jsonl").read_text(encoding="utf-8").splitlines():
            try:
                done.add(json.loads(line)["job_id"])
            except Exception:  # noqa: BLE001
                pass
    todo = [j for j in plan if j["job_id"] not in done]
    HIGH_TEMPLATE = None
    if any(j["effort"] == "high" for j in todo) and not REPLAY_ONLY:
        HIGH_TEMPLATE = Path(HIGH_TEMPLATE_PATH).read_text(encoding="utf-8")
        assert "Reasoning effort is set to high." in HIGH_TEMPLATE, "high template not prepared"
    logline(f"pack={PACK} shard={SHARD or 'all'} jobs={len(plan)} todo={len(todo)} lanes={LANES} deadline={DEADLINE_S/60:.0f}min replay_only={REPLAY_ONLY}")
    (OUT / "plan_shard.json").write_text(json.dumps(todo), encoding="utf-8")
    solver = copy.deepcopy(bm.solver)
    solver.job_dir = WORKING
    solver.soft_end_time = None
    solver.runtime_environment = target
    solver.minimal_diagnostics = False
    run_session = taaf.game.RunSession(record_intermediate_states=False)
    summary = {"started": datetime.utcnow().isoformat() + "Z", "jobs": len(todo), "done": 0, "errors": 0, "skipped_deadline": 0}
    with ThreadPoolExecutor(max_workers=LANES) as pool:
        futures = []
        for job in todo:
            futures.append(pool.submit(_guarded, job, turns[job["game_id"]], actions[job["game_id"]], solver, run_session))
        for f in futures:
            r = f.result()
            if r is None:
                summary["skipped_deadline"] += 1
            elif r.get("status") == "error":
                summary["errors"] += 1
            else:
                summary["done"] += 1
    summary["ended"] = datetime.utcnow().isoformat() + "Z"
    (OUT / "summary.json").write_text(json.dumps(summary, indent=1), encoding="utf-8")
    logline(f"all jobs finished: {summary}")


def _guarded(job, turns, actions, solver, run_session):
    if time.monotonic() - T0 >= DEADLINE_S:
        with _results_lock:
            with open(OUT / "results.jsonl", "a", encoding="utf-8") as fh:
                fh.write(json.dumps({"job_id": job["job_id"], "status": "skipped_deadline"}) + "\n")
        return None
    return run_job(job, turns, actions, solver, run_session)


HIGH_TEMPLATE: str | None = None
branch_main()
print("V12 RUN COMPLETE")
