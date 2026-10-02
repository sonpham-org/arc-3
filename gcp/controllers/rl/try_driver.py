# ===================================================================================================================
# RL try driver (plan: docs/plans/2026-10-01-rl-on-burst-games.md §0b step 2). derive_tries.py appends this file to
# the source arm's own runner preamble in place of `asyncio.run(bm.run(...))`, so the bundle, the environment checks,
# the 25 games and the server are exactly the source arm's (Combo A clone with request logs on).
#
# A JOB is one forkable moment: a seed run's game at the start of solver turn `fork_step`, plus how many tries.
# Each try rebuilds the game exactly by replaying the source transcript's recorded replies for every turn before the
# fork (the recorded python runs in the real sandbox against the real engine, each replayed turn capped at the actions
# it really ran), then plays live with the stock agent until the level in progress clears, or the turn cap, token
# cap or the source's game clock runs out. Every try keeps the harness's own request log (exact prompts + replies).
#
# Queue (GCS, or a local dir for tests): <root>/jobs/<moment_id>.json written by the session; <root>/claims/<moment_id>
# created once (no-overwrite) by the VM that runs it; <root>/results/<try_id>.json; <root>/status/<vm>.json;
# <root>/events/<try_id>.jsonl.gz (the try's frames and turn transcripts, for the review page).
# Each finished try also writes its rl_tries doc (reward = the scorer's level formula) and its lake episode.
# ===================================================================================================================
import copy  # noqa: E402
import gzip  # noqa: E402
import re  # noqa: E402
import subprocess  # noqa: E402
from dataclasses import dataclass, field  # noqa: E402
import threading  # noqa: E402
import time  # noqa: E402
import traceback  # noqa: E402
from concurrent.futures import ThreadPoolExecutor  # noqa: E402

import requests  # noqa: E402
from inference.agent import tool_agent as ta  # noqa: E402
from inference.framework import solver as sv  # noqa: E402

TRY_PACK = Path(os.environ.get("ARC3_TRY_PACK", "/opt/arc3/trypack"))
sys.path.insert(0, str(TRY_PACK))
import branch_parse  # noqa: E402
import lake  # noqa: E402
import rl_tree as rt  # noqa: E402

CAMPAIGN = os.environ["ARC3_TRY_CAMPAIGN"]
VM = os.environ["ARC3_TRY_VM"]
LANES = int(os.environ.get("ARC3_TRY_LANES", str(bm.solver.concurrency)))
TURN_CAP = int(os.environ.get("ARC3_TRY_TURN_CAP", "40"))
TOKEN_CAP_X = float(os.environ.get("ARC3_TRY_TOKEN_CAP_X", "1.5"))        # x the reference's remaining tokens; 0 = off
TOKEN_CAP_MIN = int(os.environ.get("ARC3_TRY_TOKEN_CAP_MIN", "20000"))
COLD_STARTS = threading.Semaphore(int(os.environ.get("ARC3_TRY_COLD_STARTS", "1")))   # fork prompts prefilled at once
FIRST_WAIT_S = float(os.environ.get("ARC3_TRY_FIRST_WAIT_S", "1200"))     # followers wait at most this for the leader
LIVE_RETRIES = int(os.environ.get("ARC3_TRY_LIVE_RETRIES", "3"))
LIVE_RETRY_S = float(os.environ.get("ARC3_TRY_LIVE_RETRY_S", "30"))
DEADLINE_S = float(os.environ.get("ARC3_TRY_DEADLINE_MIN", "180")) * 60.0
POLL_S = float(os.environ.get("ARC3_TRY_POLL_S", "30"))
REPLAY_ONLY = os.environ.get("ARC3_TRY_REPLAY_ONLY", "0") == "1"          # local fidelity test: no model
LOCAL_ROOT = os.environ.get("ARC3_TRY_LOCAL_ROOT", "")                     # tests: a directory instead of GCS
WRITE_INDEX = os.environ.get("ARC3_TRY_WRITE_INDEX", "1") == "1" and not REPLAY_ONLY
EXIT_WHEN_IDLE = os.environ.get("ARC3_TRY_EXIT_WHEN_IDLE", "0") == "1"
REPLAY_TOOL_TIMEOUT_S = int(os.environ.get("ARC3_TRY_REPLAY_TOOL_TIMEOUT_S", "60"))
ROOT = LOCAL_ROOT or f"gs://cellens-ai-artifacts/arc3-rl/tries/{CAMPAIGN}"
# "[RUNTIME BUDGET]\n... time left 5593s (game ...)": the game time left at the start of a turn (transcript grammar)
BUDGET_RE = re.compile(r"\[RUNTIME BUDGET\]\n[^\n]*?time left (\d+)s")
OUT = WORKING / "tries"
for _sub in ("src", "results", "lake"):
    (OUT / _sub).mkdir(parents=True, exist_ok=True)
T0 = time.monotonic()
STOP = threading.Event()
_lock = threading.Lock()


def log(msg: str) -> None:
    with _lock:
        print(f"[try {time.strftime('%H:%M:%S')}] {msg}", flush=True)


def time_left_s() -> float:
    return DEADLINE_S - (time.monotonic() - T0)


# ----------------------------------------------------------------------------------------------------- queue
def _q_path(rel: str) -> str:
    return f"{ROOT.rstrip('/')}/{rel}"


def q_list(sub: str) -> list[str]:
    if LOCAL_ROOT:
        d = Path(LOCAL_ROOT) / sub
        return sorted(p.name for p in d.glob("*.json")) if d.is_dir() else []
    r = subprocess.run(["gcloud", "storage", "ls", _q_path(sub) + "/"], capture_output=True, text=True, timeout=120)
    return sorted(Path(l.strip()).name for l in r.stdout.splitlines() if l.strip().endswith(".json"))


def q_get(rel: str) -> bytes | None:
    if LOCAL_ROOT:
        p = Path(LOCAL_ROOT) / rel
        return p.read_bytes() if p.exists() else None
    r = subprocess.run(["gcloud", "storage", "cat", _q_path(rel)], capture_output=True, timeout=120)
    return r.stdout if r.returncode == 0 else None


def q_put(rel: str, data: bytes, *, create_only: bool = False) -> bool:
    if LOCAL_ROOT:
        p = Path(LOCAL_ROOT) / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        if create_only:
            try:
                with open(p, "xb") as fh:
                    fh.write(data)
                return True
            except FileExistsError:
                return False
        p.write_bytes(data)
        return True
    tmp = OUT / "results" / f".up{threading.get_ident()}"
    tmp.write_bytes(data)
    extra = ["--if-generation-match=0"] if create_only else []
    r = subprocess.run(["gcloud", "storage", "cp", *extra, str(tmp), _q_path(rel)], capture_output=True, text=True,
                       timeout=120)
    if r.returncode == 0:
        return True
    if create_only and ("412" in r.stderr or "precondition" in r.stderr.lower()):
        return False
    raise RuntimeError(f"gcloud cp {rel}: {r.stderr.strip()[-300:]}")


# ----------------------------------------------------------------------------------------------------- source
def load_source(job: dict) -> tuple[list[dict], dict]:
    """Recorded turns before the fork turn (parsed with the harness's transcript grammar) and the fork turn's facts
    (action number at its start, game time left). The source transcript is a finished seed-run game."""
    local = OUT / "src" / f"{job['moment_id']}.txt"
    if not local.exists():
        raw = q_get_abs(job["transcript_uri"])
        if raw is None:
            raise RuntimeError(f"no transcript at {job['transcript_uri']}")
        local.write_bytes(raw)
    text = local.read_text(encoding="utf-8")
    heads = list(branch_parse._HEADER.finditer(text))
    idx = next((i for i, h in enumerate(heads) if int(h.group(1)) == int(job["fork_step"])), None)
    if idx is None:
        raise RuntimeError(f"fork step {job['fork_step']} not in the transcript (last {heads[-1].group(1) if heads else None})")
    end = heads[idx + 1].start() if idx + 1 < len(heads) else len(text)
    m = BUDGET_RE.search(text[heads[idx].end():end])
    prior = OUT / "src" / f"{job['moment_id']}.upto.txt"
    prior.write_text(text[:heads[idx].start()], encoding="utf-8")
    turns = branch_parse.turns_to_json(branch_parse.parse_transcript(prior)) if idx else []
    bad = [t["step"] for t in turns if t["outcome"] in ("truncated", "error", "unknown")]
    if bad:
        raise RuntimeError(f"unreplayable turns before the fork: {bad[:5]}")
    return turns, {"action_at_start": int(heads[idx].group(2)), "time_left_s": int(m.group(1)) if m else None,
                   "turns_before": idx}


def q_get_abs(uri: str) -> bytes | None:
    if uri.startswith("gs://"):
        r = subprocess.run(["gcloud", "storage", "cat", uri], capture_output=True, timeout=300)
        return r.stdout if r.returncode == 0 else None
    p = Path(uri)
    return p.read_bytes() if p.exists() else None


# ----------------------------------------------------------------------------------------------------- agent
class ReplayDivergence(RuntimeError):
    pass


_GATES: dict = {}
_GATES_LOCK = threading.Lock()


def _gate(moment_id: str) -> dict:
    with _GATES_LOCK:
        return _GATES.setdefault(moment_id, {"lock": threading.Lock(), "event": threading.Event(), "leader": None})


def _retryable(exc: Exception) -> bool:
    """Server-side or connection failures are worth retrying; a 4xx (e.g. context length) is not."""
    s = str(exc)
    return any(k in s for k in ("Connection", "RemoteDisconnected", "timed out", "Internal Server Error",
                                "500 ", "502 ", "503 ", "504 "))


class TryAgent(ta.ToolAgent):
    """Replays the source's recorded replies for every turn before the fork, then plays live, unchanged."""

    def __init__(self, job: dict, turns: list[dict], **kw):
        super().__init__(**kw)
        self.job = job
        self.turns = [t for t in turns if t["step"] < int(job["fork_step"])]
        nxt = [t["action_at_start"] for t in self.turns[1:]] + [int(job["action_at_start"])]
        self.recorded_actions = [n - t["action_at_start"] for t, n in zip(self.turns, nxt)]
        self._python_timeout_cfg = self._python_timeout
        self._yield_cfg = self._yield_seconds
        self._action_limit_cfg = None
        self.turn_idx = 0
        self.req_idx = 0
        self.replaying = bool(self.turns)
        self.live = False
        self.session = None
        self._pending_error = False
        self.switch = None
        self.live_tokens = 0
        self.live_requests = 0
        self.usage_rows: list[dict] = []
        self.cur_step = None

    def analyze(self, state_path, action_num, *a, **kw):
        self._yield_seconds = self._yield_cfg
        step = kw.get("analysis_step")
        self.cur_step = step
        if self.replaying:
            if self.turn_idx >= len(self.turns):
                self._switch_to_live()
            else:
                t = self.turns[self.turn_idx]
                if step is not None and t["step"] != step:
                    raise ReplayDivergence(f"turn {self.turn_idx}: recorded step {t['step']} vs live {step}")
                if t["action_at_start"] != ta._display_action_number(action_num):
                    raise ReplayDivergence(f"step {t['step']}: recorded action {t['action_at_start']} vs "
                                           f"{ta._display_action_number(action_num)}")
                tl = next((r["time_left_s"] for r in t["requests"] if r.get("time_left_s") is not None), None)
                if tl is not None and self.session is not None:
                    self.session.set_clock(tl)
                if self.session is not None:
                    if self._action_limit_cfg is None:
                        self._action_limit_cfg = self.session.turn_action_limit
                    self.session.turn_action_limit = (self.session.turn_actions_executed
                                                      + max(0, self.recorded_actions[self.turn_idx]))
                    self._python_timeout = REPLAY_TOOL_TIMEOUT_S
                self.req_idx = 0
        if self.live and self.session is not None and step is not None:
            self.session.live_steps.add(int(step))
        result = super().analyze(state_path, action_num, *a, **kw)
        if self.replaying and self.turn_idx < len(self.turns):
            t = self.turns[self.turn_idx]
            if self.req_idx != len(t["requests"]):
                raise ReplayDivergence(f"step {t['step']}: consumed {self.req_idx}/{len(t['requests'])} recorded requests")
            self.turn_idx += 1
            self._pending_error = False
        return result

    def _switch_to_live(self) -> None:
        self.replaying = False
        self.live = True
        sess = self.session
        self._python_timeout = self._python_timeout_cfg
        if sess is not None and self._action_limit_cfg is not None:
            sess.turn_action_limit = self._action_limit_cfg
        self.switch = {"action_count": sess.action_count if sess else None,
                       "levels_completed": int(sess.game.current_state.levels_completed) if sess else None,
                       "elapsed_s": round(time.monotonic() - T0, 1)}
        if sess is not None:
            sess.on_switch(self.job)
        log(f"{self.job['try_id']}: replay done ({self.switch}); live")

    def _chat_completion(self, messages, **kw):
        if self.replaying:
            t = self.turns[self.turn_idx]
            if self._pending_error:
                self._pending_error = False
                raise requests.RequestException("replayed request_error")
            if self.req_idx >= len(t["requests"]):
                raise ReplayDivergence(f"step {t['step']}: live asked for request {self.req_idx + 1}, "
                                       f"recorded {len(t['requests'])}")
            r = t["requests"][self.req_idx]
            self.req_idx += 1
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
        res = self._first_live(messages, **kw) if self.live_requests == 0 else self._live_call(messages, **kw)
        self.live_requests += 1
        usage = res.usage or {}
        self.live_tokens += int(usage.get("completion_tokens") or 0)
        # The harness's own request log carries no usage on this bundle (checked 1-Oct): keep the server's counts per
        # request in the try result, so the exact-token render check (render.py profiles) can run on every try.
        self.usage_rows.append({"step": self.cur_step, "n": self.live_requests, "finish": res.finish_reason,
                                "usage": usage})
        return res

    def _live_call(self, messages, **kw):
        """One live request, retried through short server outages (2-Oct: 500s, then dropped connections, when 16 tries
        went live at once with 60-100k-token prompts and the server restarted)."""
        delay = LIVE_RETRY_S
        for attempt in range(LIVE_RETRIES + 1):
            try:
                return super()._chat_completion(messages, **kw)
            except requests.RequestException as exc:
                if attempt >= LIVE_RETRIES or not _retryable(exc):
                    raise
                log(f"{self.job['try_id']}: live request failed ({str(exc)[:90]}); retry {attempt + 1} in {delay:.0f}s")
                t0 = time.monotonic()
                time.sleep(delay)
                self._refund(time.monotonic() - t0)
                delay *= 2
        raise RuntimeError("unreachable")

    def _first_live(self, messages, **kw):
        """The fork's first live request. All tries of a moment send the same prompt here: one leader sends it first
        (one cold start at a time per VM), the others wait for its reply and then hit the prefix cache. The time spent
        waiting is given back to the try's game clock."""
        gate = _gate(self.job["moment_id"])
        with gate["lock"]:
            leader = gate["leader"] is None
            if leader:
                gate["leader"] = self.job["try_id"]
        t0 = time.monotonic()
        if not leader:
            gate["event"].wait(timeout=FIRST_WAIT_S)
            self._refund(time.monotonic() - t0)
            return self._live_call(messages, **kw)
        try:
            with COLD_STARTS:
                self._refund(time.monotonic() - t0)
                return self._live_call(messages, **kw)
        finally:
            gate["event"].set()

    def _refund(self, seconds: float) -> None:
        if self.session is not None and seconds > 0.5 and getattr(self.session, "started_at", None) is not None:
            self.session.started_at += seconds


@dataclass
class TrySession(sv._HarnessGameSession):
    job: dict = field(default_factory=dict)
    target_levels: int = 0
    live_started_at: float | None = None
    live_action_start: int = 0
    live_steps: set = field(default_factory=set)
    stop_reason: str = ""

    def set_clock(self, time_left_s: float) -> None:
        self.started_at = time.monotonic() - (self.solver.max_runtime_s_per_game - float(time_left_s))

    def budget_status(self) -> dict:
        rem = self.timing_payload()["time_remaining_seconds"]
        return {"game_remaining_seconds": rem, "suite_remaining_seconds": rem}

    def on_switch(self, job: dict) -> None:
        if job.get("time_left_s") is not None:
            self.set_clock(job["time_left_s"])
        self.live_started_at = time.monotonic()
        self.live_action_start = self.action_count
        self.target_levels = int(self.game.current_state.levels_completed) + 1

    def should_stop(self) -> bool:
        run = self.game.game_run
        if run is None or run.state != "playing":
            self.stop_reason = self.stop_reason or "run_not_playing"; return True
        if self.stop_event.is_set() or STOP.is_set():
            self.stop_reason = self.stop_reason or "stop_event"; return True
        if sv._is_run_complete(self.game):
            self.stop_reason = self.stop_reason or "run_complete"; return True
        ag = self.analyzer
        if REPLAY_ONLY and ag.turn_idx >= len(ag.turns):
            self.stop_reason = self.stop_reason or "replay_done"; return True
        if self.live_started_at is not None:
            if int(self.game.current_state.levels_completed) >= self.target_levels:
                self.stop_reason = self.stop_reason or "cleared"; return True
            if self.runtime_limit_reached():
                self.stop_reason = self.stop_reason or "clock"; return True
            if len(self.live_steps) >= TURN_CAP:
                self.stop_reason = self.stop_reason or "turn_cap"; return True
            if ag.live_tokens >= self.job["token_cap"]:
                self.stop_reason = self.stop_reason or "token_cap"; return True
        return False


# ----------------------------------------------------------------------------------------------------- tries
solver = copy.deepcopy(bm.solver)
solver.job_dir = WORKING
solver.soft_end_time = None
solver.runtime_environment = target
solver.minimal_diagnostics = False
run_session = taaf.game.RunSession(record_intermediate_states=False)
STATS = {"moments": 0, "tries": 0, "valid": 0, "cleared": 0, "errors": 0}
BUSY = [0]
STORE = rt.FirestoreStore() if WRITE_INDEX else None


def _find(stem: str, suffix: str) -> Path | None:
    hits = sorted(WORKING.rglob(f"{stem}*{suffix}"))
    return hits[0] if hits else None


def finish_try_records(job: dict, rec: dict) -> None:
    """rl_tries doc (reward) + lake episode of the live part (request log rows from the fork turn on)."""
    moment = job["moment"]
    tdoc = rt.new_try(moment=moment, policy=job["policy_id"], kind="plain", index=job["index"], vm=VM,
                      campaign=CAMPAIGN)
    tdoc["id"] = job["try_id"]
    out = rec["outcome"]
    tdoc = rt.finish_try(tdoc, moment=moment, cleared=bool(out["cleared"]), try_actions=int(out["actions"] or 0),
                         turns=int(rec.get("live_turns") or 0), tokens=int(rec.get("live_tokens") or 0),
                         over_token_cap=rec.get("stop_reason") == "token_cap", finish=str(rec.get("stop_reason")))
    tdoc["valid"] = bool(out["valid"])
    stage = OUT / "lake"
    reqlog = _find(job["try_id"], "_requests.jsonl")
    if reqlog is not None:
        rows = [json.loads(l) for l in reqlog.read_text(encoding="utf-8").splitlines() if l.strip()]
        rows = [r for r in rows if int(r.get("analysis_step") or 0) >= int(job["fork_step"])]
        header = {"episode_id": lake.episode_id("rl_try", job["try_id"]),
                  "source": {"kind": "rl_try", "try_id": job["try_id"], "moment_id": job["moment_id"], "vm": VM},
                  "game": {"id": job["game_id"], "version": None}, "harness": {"id": job["harness_id"]},
                  "policy": {"id": job["policy_id"]}, "teacher": "none",
                  "parent": {"episode_id": job.get("source_episode_id"), "turn": int(job["fork_step"])},
                  "fenced": rt.is_fenced(job["game_id"])}
        # frames of the live part (the review page and the lake replay show them); the prefix is the source's
        evlog = _find(job["try_id"], "_events.jsonl")
        sw = int((rec.get("switch") or {}).get("action_count") or 0)
        events = [e for e in (json.loads(l) for l in evlog.read_text(encoding="utf-8").splitlines() if l.strip())
                  if e.get("type") == "action" and int(e.get("action_num") or 0) > sw] if evlog is not None else []
        lines = lake.episode_lines(header, rows, lake.LocalBlobs(stage), events=events, human=job.get("human") or [],
                                   first_level=int(job["level"]))
        uri = lake.episode_uri(header["episode_id"], "rl_try")
        lake.write_episode(stage, uri, lines)
        tdoc["payload_uri"] = f"{lake.LAKE_ROOT}/{uri}"
    if STORE is not None:
        STORE.put("rl_tries", tdoc)
    rec["try_doc"] = {k: tdoc.get(k) for k in ("id", "reward", "cleared", "try_actions", "tokens", "finish", "payload_uri")}


def run_try(job: dict, turns: list[dict]) -> dict:
    started = time.monotonic()
    rec: dict = {"try_id": job["try_id"], "moment_id": job["moment_id"], "vm": VM, "status": "started"}
    game = taaf.game_api.GameAPI(env_name=job["game_id"], arcade_spec=spec)
    agent = session = None
    try:
        game.start_game(run_session)
        agent = TryAgent(job, turns, model=solver.model, timeout=solver.analyzer_timeout,
                         save_request_logs=not REPLAY_ONLY)
        stem = job["try_id"]
        session = TrySession(
            solver=solver, game=game, analyzer=agent, game_index=0, pass_index=0,
            state_path=solver._artifacts_dir() / f"{stem}_{sv.RUNTIME_STATE_FILENAME}",
            transcript_path=solver._transcripts_dir() / f"{stem}.txt",
            analysis_html_relpath=f"solver_analysis/{stem}.html",
            stop_event=threading.Event(), viewer_data_path=solver._artifacts_dir() / f"{stem}_viewer_data.json",
            job=job)
        agent.session = session
        if not agent.replaying:
            agent._switch_to_live()
        session.play()
        note = str(getattr(game.game_run, "solver_note", "") or "")
        if note.startswith("error:"):
            raise RuntimeError(note)
        exp_n = int(job["action_at_start"]) - 1
        sw = agent.switch["action_count"] if agent.switch else session.action_count
        lv = (agent.switch or {}).get("levels_completed", int(game.current_state.levels_completed))
        prefix_ok = sw == exp_n and lv == int(job["level"]) - 1     # replay-only stops before the switch
        live_actions = session.action_count - session.live_action_start if session.live_started_at else None
        cleared = session.stop_reason == "cleared"
        rec.update({"status": "done", "stop_reason": session.stop_reason, "prefix_ok": prefix_ok, "switch": agent.switch,
                    "cleared": cleared, "live_actions": live_actions, "live_turns": len(session.live_steps),
                    "live_requests": agent.live_requests, "live_tokens": agent.live_tokens, "usage": agent.usage_rows,
                    "final_levels_completed": int(game.current_state.levels_completed),
                    "wall_s": round(time.monotonic() - started, 1)})
    except Exception as exc:  # noqa: BLE001
        STATS["errors"] += 1
        rec.update({"status": "error", "error": f"{type(exc).__name__}: {exc}", "traceback": traceback.format_exc()[-3000:],
                    "switch": getattr(agent, "switch", None), "wall_s": round(time.monotonic() - started, 1)})
    finally:
        try:
            if game.game_run is not None and game.game_run.final_score is None:
                if game.game_run.state == "playing":
                    game.game_run.state = "cancelled"
                game.finish_game()
        except Exception:  # noqa: BLE001
            pass
    rec["outcome"] = {"valid": rec["status"] == "done" and bool(rec.get("prefix_ok")),
                      "cleared": bool(rec.get("cleared")), "actions": rec.get("live_actions") if rec.get("cleared") else None}
    if rec["outcome"]["valid"] and not REPLAY_ONLY:
        try:
            finish_try_records(job, rec)
        except Exception as exc:  # noqa: BLE001
            rec["record_error"] = f"{type(exc).__name__}: {exc}"
    STATS["tries"] += 1
    STATS["valid"] += int(rec["outcome"]["valid"])
    STATS["cleared"] += int(rec["outcome"]["cleared"])
    evlog = _find(job["try_id"], "_events.jsonl")
    if evlog is not None and not REPLAY_ONLY:           # frames + turn transcripts: the review page replays these
        try:
            q_put(f"events/{job['try_id']}.jsonl.gz", gzip.compress(evlog.read_bytes()))
        except Exception as exc:  # noqa: BLE001
            rec["events_error"] = f"{type(exc).__name__}: {exc}"
    q_put(f"results/{job['try_id']}.json", json.dumps(rec, default=str).encode())
    log(f"{job['try_id']}: {rec['status']} stop={rec.get('stop_reason')} prefix_ok={rec.get('prefix_ok')} "
        f"cleared={rec.get('cleared')} live_actions={rec.get('live_actions')} tokens={rec.get('live_tokens')} "
        f"wall={rec.get('wall_s')}s")
    return rec


def start_moment(name: str, pool: ThreadPoolExecutor) -> bool:
    moment_job = json.loads(q_get(f"jobs/{name}"))
    mid = moment_job["moment_id"]
    try:
        turns, info = load_source(moment_job)
    except Exception as exc:  # noqa: BLE001
        if q_put(f"claims/{mid}.json", json.dumps({"vm": VM, "error": str(exc)}).encode(), create_only=True):
            q_put(f"results/{mid}._error.json", json.dumps({"vm": VM, "error": f"{type(exc).__name__}: {exc}"}).encode())
        log(f"moment {mid}: cannot start {type(exc).__name__}: {exc}")
        return False
    if not q_put(f"claims/{mid}.json", json.dumps({"vm": VM, "at": time.time()}).encode(), create_only=True):
        return False
    m = moment_job["moment"]
    ref = m.get("ref_remaining_tokens") or 0
    base = {**moment_job, "action_at_start": info["action_at_start"],
            "time_left_s": moment_job.get("time_left_s") or info["time_left_s"],
            # 2-Oct: at 1.5x the transcript-estimated reference, 37 of 48 ls20 tries were cut off after 3-10 turns
            "token_cap": max(TOKEN_CAP_MIN, int(TOKEN_CAP_X * ref)) if TOKEN_CAP_X > 0 else 10 ** 12}
    n = int(moment_job.get("n", 8))
    STATS["moments"] += 1
    log(f"moment {mid}: {moment_job['game_id']} step {moment_job['fork_step']} level {m['level']} -> {n} tries "
        f"(token cap {base['token_cap']})")
    for i in range(n):
        job = dict(base, index=i, try_id=f"{mid}.{CAMPAIGN}.{i:02d}")
        with _lock:
            BUSY[0] += 1
        pool.submit(_guarded, job, turns)
    return True


def _guarded(job, turns):
    try:
        return run_try(job, turns)
    finally:
        with _lock:
            BUSY[0] -= 1


def push_lake() -> None:
    if REPLAY_ONLY or LOCAL_ROOT:
        return
    subprocess.run(["gcloud", "storage", "rsync", "-r", str(OUT / "lake"), lake.LAKE_ROOT], capture_output=True,
                   timeout=900)


def try_main() -> None:
    log(f"campaign={CAMPAIGN} vm={VM} lanes={LANES} turn_cap={TURN_CAP} token_cap={TOKEN_CAP_X}x deadline="
        f"{DEADLINE_S/60:.0f}min replay_only={REPLAY_ONLY} root={ROOT}")
    pool = ThreadPoolExecutor(max_workers=max(1, LANES))
    idle = 0
    last_push = time.monotonic()
    while time_left_s() > 0:
        try:
            claimed = {n for n in q_list("claims")}
            for name in q_list("jobs"):
                with _lock:
                    free = LANES - BUSY[0]
                if name in claimed:
                    continue
                need = int(json.loads(q_get(f"jobs/{name}") or b"{}").get("n", 8))
                if free < need or time_left_s() < 1200:
                    break
                start_moment(name, pool)
            q_put(f"status/{VM}.json", json.dumps({"vm": VM, "busy": BUSY[0], "stats": STATS,
                                                    "minutes_left": round(time_left_s() / 60, 1),
                                                    "at": time.time()}).encode())
            if time.monotonic() - last_push > 600:
                push_lake()
                last_push = time.monotonic()
        except Exception as exc:  # noqa: BLE001
            log(f"scheduler: {type(exc).__name__}: {exc}")
        with _lock:
            busy = BUSY[0]
        idle = idle + 1 if (EXIT_WHEN_IDLE and busy == 0 and STATS["moments"]) else 0
        if idle >= 3:
            break
        STOP.wait(POLL_S)
    log("deadline or idle: stopping")
    STOP.set()
    pool.shutdown(wait=True, cancel_futures=True)
    push_lake()
    (OUT / "summary.json").write_text(json.dumps({**STATS, "minutes": round((time.monotonic() - T0) / 60, 1)}))
    log(f"done: {STATS}")


try_main()
print("V12 RUN COMPLETE")
