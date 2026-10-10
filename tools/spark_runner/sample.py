#!/usr/bin/env python3
"""
Author: Claude Opus 5.5 (Bubba)
Date: 06-October-2026
PURPOSE: Play ONE sample of a Spark runner job, in its own process (the harness keeps sampling settings in module
  globals, so one process per sample keeps samples from leaking into each other):
    1. Environment = the 31.63 notebook's gameplay flags (notebook_env.json written by build_harness.py): Franzen's
       setup cell for the "daniel" variant, plus Son's port cell (noborder, temperature 0.6) for "son". Server address
       and model id point at the two-Spark Flash-Next server. Priority scheduling and the warm-up RESET are off: one
       game per process, nothing to schedule.
    2. Start (spec["start"]), four kinds:
         - "checkpoint" (EXACT): an exact level-start checkpoint (checkpoints.py). The game is replayed from RESET
           through the harness's own _execute_action with the recorded automatic flags and checked against the saved
           board hash, level and action count; then the harness agent's and session's own saved attributes are put
           back (conversation, retained functions, world model, ledgers, runtime-state history, counters). The first
           request the sample sends is compared with the saved request body and the result recorded per sample.
         - "snapshot" (REBUILT): today's stuck-level snapshot: replay its action line, refuse to play if the board,
           level or action count differ, then hand the agent the conversation rebuilt from the site's transcripts and
           the retained functions. Labelled "conversation rebuilt" (unless the snapshot is a bare game start).
         - "reset": play from the first RESET (harvest runs).
         - "replay" (NO CONTEXT, spec["context"] == "none", added 6-Oct): replay to the level's start (an exact
           checkpoint's actions or the verified winning line, replays.py), check level, action count and board, then
           clear what the replay left in the session (runtime-state history re-seeded with the current frame only, last
           action and animation record dropped). The agent is a fresh one: the first request is a new game's first
           turn at that board (system prompt + the normal first prompt, the real step and level), nothing carried.
           These samples write no checkpoints.
    3. Play with session.play(), the harness's own loop, with narrow hooks:
         - prompt profile (prompt_profiles.py; spec["prompt_profile"], "dedup" when absent, recorded in result.json):
           installed after the start is in place (so a restored checkpoint cannot bring back another profile's
           system prompt). dedup: the standing manual is the system prompt, said once;
         - _build_user_prompt: dedup = the harness's turn message without its standing lines, plus the slot's
           mode instructions as the last block; original = the mode's delta (modes.py) applied to the prompt the
           harness built, or a slot's instructions put where the original built-in modes put theirs;
         - _chat_completion / build_chat_payload: temperature, thinking on/off, reasoning effort of the slot;
         - _tool_steps and _yield_tokens: tool-call limit and thinking budget of the slot;
         - step_env: the slot's action budget (a batch is cut to what is left; nothing past it executes);
         - should_stop: stop when the target level is cleared, the game ends, or the sample's action/turn/time cap
           is hit;
         - _execute_action: every engine action is logged (name, data, automatic) from RESET.
       A "turn" is one opener prompt; a yield continuation of the same turn keeps the same slot. When the scheme
       runs out, Stock (with the Stock settings the page sent) plays every later turn.
    4. Exact capture (every sample, Play and harvest): at the start of the first turn after a level was completed,
       the agent's and session's state are saved and the turn's request body is captured as it is posted. When that
       turn runs under a non-Stock slot, or the sample stops right after the clear, the Stock request for that turn is
       built without sending it (the post is intercepted), and the saved state is put back. Checkpoints written by a
       sample that started from a rebuilt snapshot are kept but marked as not exact lineage, so they are never chosen.
    5. Trajectory under <job>/samples/<k>/: transcript.txt (the harness's own transcript), turns.jsonl (per turn:
       mode, settings, how the delta applied, actions, level, tokens), viewer.json (frames), progress.json while
       running, result.json at the end, first_request.json.gz for an exact start.
  9-Oct-2026: spec["env_overrides"] (optional) is applied over the notebook flags; the level-start sprint
  (tools/level_sprint/sprint.py) uses it for harness-flag variants. Runner jobs never set it.
  Usage: sample.py <job_dir> <sample_index>   (reads <job_dir>/spec.json; written by server.py or level_sprint)
         sample.py --verify-all <snapshots dir>   (replay check of every snapshot, no model; writes verified.json)
         sample.py --verify-checkpoint <checkpoint dir> <out dir>   (replay + state restore check, no model)
         sample.py --render-first <game> <level> <variant> <out dir>   (No-context start + its first request, no model)
         sample.py --render-all <out dir> [variant]   (the same for every trainable game and level; render-checks.json)
         (render_requests.py runs main() itself with a scripted stand-in for the model: previews and the dedup check)
SRP/DRY check: Pass - no harness logic is copied; everything runs through the bundle's ToolAgent and
  _HarnessGameSession. Mode text math lives in modes.py, checkpoint storage in checkpoints.py, queueing in server.py.
"""
from __future__ import annotations

import copy
import gzip
import hashlib
import json
import os
import pickle
import sys
import threading
import time
import traceback
import types
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import checkpoints  # noqa: E402
import prompt_profiles  # noqa: E402
from modes import apply_delta, build_delta, insert_original, instructions_from_template  # noqa: E402

RUNNER_HOME = Path(os.environ.get("ARC3_RUNNER_HOME", Path.home() / "arc3-runner"))
HARNESS = Path(os.environ.get("ARC3_RUNNER_HARNESS", RUNNER_HOME / "harness"))
ENV_DIR = Path(os.environ.get("ARC3_RUNNER_ENVIRONMENTS", RUNNER_HOME / "environment_files"))
# Off in the runner: they only make sense for many games sharing one process and one server queue.
DROP_KEYS = ("ARC3_WARMUP_ACTION_GAMES", "ARC3_MAX_ACTIVE_STREAMS", "ARC3_PRIORITY_REFRESH_QUEUE", "ARC3_PRIORITY_PACE",
             "ARC3_PRIORITY_TAIL_FADE", "ARC3_PRIORITY_TAIL_FADE_FRACTION", "ARC3_PRIORITY_TAIL_LOOKUP",
             "ARC3_PRIORITY_SCORE_NORMALIZATION", "ARC3_HICACHE_GB")


def write_json(path: Path, payload) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=1, default=str))
    tmp.replace(path)


def board_ascii(grid, color_chars: str) -> str:
    return "\n".join("".join(color_chars[int(v)] for v in row) for row in grid)


def setup_environment(spec: dict) -> dict:
    flags = json.loads((HARNESS / "notebook_env.json").read_text())
    env = dict(flags["daniel"])
    if spec["variant"] == "son":
        env.update(flags["son_port"])
    # Level-start sprint variants (tools/level_sprint, 9-Oct-2026): harness flag overrides; runner jobs have none.
    env.update({k: str(v) for k, v in (spec.get("env_overrides") or {}).items()})
    for k in DROP_KEYS:
        env.pop(k, None)
    base_url = spec["model"]["base_url"]
    env.update({
        "LOCAL_ANALYZER_BASE_URL": base_url, "OPENAI_BASE_URL": base_url,
        "LOCAL_ANALYZER_MODEL_ID": spec["model"]["model_id"], "INFERENCE_ANALYZER_MODEL": spec["model"]["model_id"],
        "LOCAL_ANALYZER_PROVIDER": "vllm", "OPENAI_PROVIDER": "vllm", "LOCAL_ANALYZER_API_KEY": "EMPTY",
        "MPLBACKEND": "Agg", "TAAF_RUN_AS_SUBMISSION": "0", "TAAF_MINIMAL_DIAGNOSTICS": "1",
        "ONLY_RESET_LEVELS": "true", "ARC3_HTTP_RETRY_INITIAL_SECONDS": "120", "OMP_NUM_THREADS": "1",
    })
    for k in DROP_KEYS:
        os.environ.pop(k, None)
    os.environ.update({k: str(v) for k, v in env.items()})
    return env


def import_harness():
    for repo in sorted((HARNESS / "src").iterdir(), reverse=True):
        for cand in (repo / "src", repo):
            if cand.is_dir() and str(cand) not in sys.path:
                sys.path.insert(0, str(cand))
    sys.dont_write_bytecode = True
    import arc_agi  # noqa: F401
    import taaf.game  # noqa: F401
    import taaf.game_api  # noqa: F401
    from inference.agent import tool_agent as ta
    from inference.framework import solver as sv
    return ta, sv


ACTION_LOG: list[dict] = []   # every engine action this process executed, from the first RESET


class DryStop(BaseException):
    """Raised by the post interceptor to stop a dry build right before the request would go out. BaseException so
    the harness's ordinary error handling (which rolls a failed turn back and retries) never swallows it."""


def grid_hash(sv, game) -> str:
    return hashlib.sha256(json.dumps(sv._grid_from_state(game.current_state)).encode()).hexdigest()


def start_session(spec: dict, out: Path, k: int):
    """Fresh game in the offline engine and a harness session around it, at the first frame (nothing played)."""
    setup_environment(spec)
    ta, sv = import_harness()
    import arc_agi
    import taaf.game
    import taaf.game_api
    with open(HARNESS / "benchmark_initial.pkl", "rb") as fh:
        bm = pickle.load(fh)
    solver = bm.solver
    solver.job_dir = out
    solver.max_runtime_s_per_game = float(spec["caps"]["max_minutes"]) * 60.0
    solver.analyzer_timeout = 900.0
    solver.concurrency = 1
    solver.max_actions_per_game = None
    solver.save_request_logs = False
    arcade_spec = taaf.game_api.ArcadeSpec(operation_mode=arc_agi.OperationMode.OFFLINE,
                                           environments_dir=str(ENV_DIR))
    game = taaf.game_api.GameAPI(env_name=spec["game_id"], arcade_spec=arcade_spec)
    game.start_game(taaf.game.RunSession())
    agent = solver._make_analyzer(game, 0, None)
    stem = solver._run_stem(game.game_run.game_id, k)
    session = sv._HarnessGameSession(
        solver=solver, game=game, analyzer=agent, game_index=0, pass_index=k,
        state_path=solver._artifacts_dir() / f"{stem}_{sv.RUNTIME_STATE_FILENAME}",
        transcript_path=out / "transcript.txt", analysis_html_relpath=f"solver_analysis/{stem}.html",
        stop_event=threading.Event(), viewer_data_path=out / "viewer.json")
    original_execute = session._execute_action

    def execute(self, action, **kw):
        ACTION_LOG.append({"name": action.id.name, "data": dict(action.data or {}),
                           "automatic": bool(kw.get("automatic", False))})
        return original_execute(action, **kw)
    session._execute_action = types.MethodType(execute, session)
    session.seed_initial_history()
    return solver, game, agent, session, sv, ta


def replay(session, sv, actions: list[dict]) -> None:
    for a in actions:
        if "data" in a:
            data = a["data"]
        else:   # snapshot format
            data = {"x": a["col"], "y": a["row"]} if a["name"] == "ACTION6" else {}
        action = sv.arcengine.ActionInput(id=sv.arcengine.GameAction.from_name(a["name"]), data=data)
        session._execute_action(action, batch_index=1, batch_size=1, generated_tokens=0, flush_viewer_payload=False,
                                automatic=a.get("automatic", a["name"] == "RESET"))


def replay_to_snapshot(spec: dict, snap: dict, out: Path, k: int, flush=lambda **kw: None):
    """Start the game in the offline engine and replay the snapshot's action line through the harness's own
    _execute_action. Raises if the board, level or action count differ from the recorded run."""
    solver, game, agent, session, sv, ta = start_session({**spec, "game_id": snap["game_id"]}, out, k)
    flush(status="replaying")
    replay(session, sv, snap["actions"])
    exp = snap["expected"]
    got_board = board_ascii(sv._grid_from_state(game.current_state), exp["color_chars"])
    got = {"level": sv._level_number(game), "action_count": session.action_count,
           "board_sha256": hashlib.sha256(got_board.encode()).hexdigest()}
    if (got["level"], got["action_count"], got["board_sha256"]) != (exp["level"], exp["action_count"], exp["board_sha256"]):
        raise RuntimeError(f"snapshot replay mismatch: expected {exp}, engine gave {got}")
    return solver, game, agent, session, sv, ta


def restore_checkpoint(spec: dict, cp: dict, out: Path, k: int, flush=lambda **kw: None):
    """Exact start: replay the checkpoint's actions from RESET, check the board, then put the harness's own saved
    agent and session state back."""
    meta = cp["meta"]
    solver, game, agent, session, sv, ta = start_session({**spec, "game_id": meta["game_id"]}, out, k)
    flush(status="replaying")
    replay(session, sv, cp["actions"])
    got = {"level": sv._level_number(game), "action_count": session.action_count, "board_sha256": grid_hash(sv, game)}
    exp = {"level": meta["level"], "action_count": meta["actions_to_reach"], "board_sha256": meta["board_sha256"]}
    if got != exp:
        raise RuntimeError(f"checkpoint replay mismatch: expected {exp}, engine gave {got}")
    agent._ensure_session(session.state_path)
    checkpoints.restore_state(cp["state"], agent, session)
    # Saved at the start of a turn, after the harness had already counted that turn; play() counts it again.
    session.analysis_step = max(0, int(session.analysis_step) - 1)
    return solver, game, agent, session, sv, ta


def replay_clean(spec: dict, start: dict, out: Path, k: int, flush=lambda **kw: None):
    """No-context start: replay to the level's start (exact checkpoint actions or the verified winning line, from
    replays.start_for), check level, action count and board, then clear everything the replay left in the session, so
    the first turn is built exactly as a new game's first turn, at this board: the runtime-state history (the model
    reads it as `history` and the prompt builder reads it) is re-seeded with the current frame only, and the last
    action and animation record are dropped. The agent is the fresh one start_session made: no messages, no retained
    functions, no world model or ledgers. analysis_step stays 0, so play() counts this as turn 1."""
    solver, game, agent, session, sv, ta = start_session(spec, out, k)
    flush(status="replaying")
    replay(session, sv, start["actions"])
    exp = start.get("expected") or {"level": 1, "action_count": 0, "board_sha256": None}
    got = {"level": sv._level_number(game), "action_count": session.action_count, "board_sha256": grid_hash(sv, game)}
    if exp["board_sha256"] is None:
        got["board_sha256"] = None
    if got != {k2: exp[k2] for k2 in ("level", "action_count", "board_sha256")}:
        raise RuntimeError(f"replay to the level start did not match: expected {exp}, engine gave {got}")
    session.history_entries = []
    session.seed_initial_history()
    session.last_engine_action = None
    session.animation_record = None
    session.analysis_step = 0
    agent._last_step_summary = None
    return solver, game, agent, session, sv, ta


def render_first_request(game_code: str, level: int, variant: str, out: Path) -> dict:
    """Offline check of a No-context start (no model): replay to the level start, then let the harness build its first
    request and stop it right before it is sent. Reports the message roles, retained functions and the level and step
    the first user prompt shows; writes the body to <out>/first_request.json.gz."""
    import replays
    start = replays.start_for(game_code, level, variant)
    if start is None:
        return {"ok": False, "game": game_code, "level": level, "error": "no verified replay"}
    env_dir = ENV_DIR / game_code
    game_id = next((json.loads(p.read_text()).get("game_id") for p in env_dir.glob("*/metadata.json")), None)
    spec = {"variant": variant, "game_id": game_id, "caps": {"max_minutes": 40},
            "model": {"base_url": "http://127.0.0.1:9/v1", "model_id": "none"}}
    out.mkdir(parents=True, exist_ok=True)
    _, game, agent, session, sv, ta = replay_clean(spec, start, out, 0)
    import requests as requests_mod
    captured = {}

    def post(url, *a, **kw):
        if str(url).endswith("/chat/completions"):
            captured["body"] = copy.deepcopy(kw.get("json"))
            raise DryStop()
        raise RuntimeError(f"unexpected request to {url}")
    requests_mod.post = post
    try:
        session.play()
    except DryStop:
        pass
    body = captured.get("body")
    if not body:
        return {"ok": False, "game": game_code, "level": level, "error": "the harness sent no request"}
    with gzip.open(out / "first_request.json.gz", "wt", encoding="utf-8") as fh:
        json.dump(body, fh)
    msgs = body.get("messages") or []
    roles = [m.get("role") for m in msgs]

    def text(m):
        c = m.get("content")
        return c if isinstance(c, str) else " ".join(p.get("text", "") for p in c or [] if isinstance(p, dict))
    user = text(msgs[-1]) if msgs else ""
    images = sum(1 for m in msgs if isinstance(m.get("content"), list)
                 for p in m["content"] if isinstance(p, dict) and p.get("type") == "image_url")
    step = session.action_count + 1
    checks = {
        "only_system_and_one_user": roles == ["system", "user"],
        "no_kept_functions": not getattr(agent, "_kept_functions", {}),
        "history_is_one_frame": len(session.history_entries) == 1,
        # the harness's own state line; a new game's first turn reads "Current state: step 1, level 1."
        "level_and_step_in_prompt": f"Current state: step {step}, level {level}." in user,
        "board_is_replayed_board": grid_hash(sv, game) == (start["expected"] or {}).get("board_sha256", grid_hash(sv, game)),
    }
    return {"ok": all(checks.values()), "game": game_code, "level": level, "source": start["source"],
            "roles": roles, "images": images, "step_shown": step, "checks": checks, "user_prompt_head": user[:400]}


def verify(snapshot_file: Path, out: Path) -> dict:
    """Replay-only check used by verify_snapshots: no model call."""
    snap = json.loads(snapshot_file.read_text())
    spec = {"variant": "son", "caps": {"max_minutes": 40},
            "model": {"base_url": "http://127.0.0.1:9/v1", "model_id": "none"}}
    out.mkdir(parents=True, exist_ok=True)
    try:
        replay_to_snapshot(spec, snap, out, 0)
        return {"ok": True, "game": snap["game"], "actions": len(snap["actions"]), "level": snap["expected"]["level"]}
    except Exception as exc:
        return {"ok": False, "game": snap["game"], "error": f"{type(exc).__name__}: {exc}"}


def slot_instructions(slot: dict) -> str:
    """A slot's turn instructions. Slots sent before the dedup profile carry the full template instead
    (prompt + stock_template): their instructions are the lines they added to Stock."""
    if slot.get("instructions") is not None:
        return slot["instructions"]
    if slot.get("prompt") and slot.get("stock_template"):
        return instructions_from_template(slot["mode"], slot["stock_template"], slot["prompt"])
    return ""


def settings_are_stock(s: dict) -> bool:
    """The Stock settings the page sends and harvest uses (modes.json, stock.settings)."""
    want = checkpoints.STOCK_SETTINGS
    return all((s.get(k) if s.get(k) is not None else None) == want[k] for k in want)


def main(job_dir: Path, k: int) -> int:
    spec = json.loads((job_dir / "spec.json").read_text())
    out = job_dir / "samples" / str(k)
    out.mkdir(parents=True, exist_ok=True)
    start = spec.get("start") or {"kind": "snapshot", "path": spec["snapshot_path"]}
    started = time.time()
    progress = {"sample": k, "status": "starting", "turn": 0, "mode": None, "actions": 0, "level": None,
                "levels_cleared": 0, "started": started, "updated": started}

    def flush(**kw):
        progress.update(kw, updated=time.time())
        write_json(out / "progress.json", progress)

    flush()
    # Jobs from before the No-context option (6-Oct) have no context field: they carried context.
    context = spec.get("context", "carried")
    # Jobs queued before prompt profiles (6-Oct) have no field: they run under the current default and say so.
    profile = spec.get("prompt_profile") or prompt_profiles.DEFAULT_PROFILE
    result = {"prompt_profile": profile, "prompt_profile_from_spec": bool(spec.get("prompt_profile")),"sample": k, "game": spec["game"], "stuck_level": spec["stuck_level"], "variant": spec["variant"],
              "kind": spec.get("kind", "play"), "context": context, "start_kind": None, "outcome": "error",
              "levels_cleared": 0, "actions_used": 0, "turns": 0, "modes_run": [], "conversation_exact": False,
              "seconds": 0, "error": None, "checkpoints_written": []}
    try:
        cp = None
        if start["kind"] == "replay":
            # No context: the board at the level start, a new game's first turn, nothing carried over
            solver, game, agent, session, sv, ta = replay_clean(spec, start, out, k, flush)
            exact_lineage = False   # its checkpoints (capture is off for these jobs anyway) must never be chosen
            result.update(start_kind="replay", replay_source=start.get("source"),
                          start_checkpoint=start.get("checkpoint"), conversation_exact=True)
        elif start["kind"] == "checkpoint":
            cp = checkpoints.load(start["path"])
            solver, game, agent, session, sv, ta = restore_checkpoint(spec, cp, out, k, flush)
            exact_lineage = bool(cp["meta"].get("exact_lineage"))
            result.update(start_kind="exact", start_checkpoint=cp["meta"]["id"], conversation_exact=exact_lineage)
        elif start["kind"] == "reset":
            solver, game, agent, session, sv, ta = start_session(spec, out, k)
            exact_lineage = True
            result.update(start_kind="reset", conversation_exact=True)
        else:
            snap = json.loads(Path(start["path"]).read_text())
            solver, game, agent, session, sv, ta = replay_to_snapshot(spec, snap, out, k, flush)
            # a bare game start (no actions, no turns) is the same as a RESET start
            exact_lineage = not snap["actions"] and not snap["turns"]
            result.update(start_kind="reset" if exact_lineage else "rebuilt",
                          conversation_exact=bool(snap["conversation"]["exact"]) or exact_lineage)
            agent._ensure_session(session.state_path)
            agent._history_messages = [m for t in snap["turns"] for m in t["messages"]]
            if ta._persistent_functions():
                agent._kept_functions = dict(snap.get("retained_functions") or {})
        result["replay_verified"] = True
        result.update(prompt_profiles.install(profile, ta, agent))
        start_actions = session.action_count
        start_completed = int(game.current_state.levels_completed)
        start_tokens = agent.generated_tokens
        if spec.get("kind") == "harvest":
            target_completed = int(game.number_of_levels)
        else:
            target_completed = int(spec["stuck_level"]) - 1 + int(spec["caps"]["levels_to_play"])

        # ---- per-turn scheduling hooks
        stock_slot = spec["stock"]
        scheme = spec["scheme"]
        capture_slot = {"key": "__capture_stock__", "mode": "stock", "name": "Stock", "instructions": "",
                        "settings": dict(checkpoints.STOCK_SETTINGS)}
        # Per slot: its turn instructions (dedup, or original with an instructions slot), or for an old-style slot
        # in the original profile the template delta, exactly as before.
        deltas, instr = {}, {}
        for slot in scheme + [stock_slot, capture_slot]:
            key = slot["key"]
            instr[key] = slot_instructions(slot)
            if profile == "original" and slot.get("instructions") is None and slot.get("prompt"):
                deltas[key] = build_delta(slot["mode"], slot["stock_template"], slot["prompt"])
        base_tool_steps, base_yield_tokens = agent._tool_steps, agent._yield_tokens
        state = {"turn": 0, "slot": None, "slot_index": -1, "actions_in_turn": 0, "delta_report": None,
                 "turn_started_actions": start_actions, "turn_started_tokens": start_tokens}
        cap = {"enabled": spec.get("capture", True) and context == "carried", "done_completed": start_completed, "pending": None,
               "dry": False, "dry_body": None, "in_analyze": False, "clear_action_count": None,
               "compare": cp["request"] if cp else None}
        turns_log = open(out / "turns.jsonl", "a", encoding="utf-8")

        def slot_is_stock(slot) -> bool:
            empty = deltas[slot["key"]].empty if slot["key"] in deltas else not instr[slot["key"]].strip()
            return empty and settings_are_stock(slot["settings"])

        def apply_slot_limits(slot):
            s = slot["settings"]
            agent._tool_steps = int(s["tool_calls"]) if s.get("tool_calls") else base_tool_steps
            agent._yield_tokens = int(s["thinking_budget"]) if s.get("thinking_budget") else base_yield_tokens

        def close_turn():
            if state["slot"] is None:
                return
            rec = {"turn": state["turn"], "slot_index": state["slot_index"], "mode": state["slot"]["mode"],
                   "settings": state["slot"]["settings"], "delta": state["delta_report"],
                   "actions": session.action_count - state["turn_started_actions"],
                   "level_after": sv._level_number(game),
                   "levels_completed_after": int(game.current_state.levels_completed),
                   "generated_tokens": agent.generated_tokens - state["turn_started_tokens"],
                   "t": round(time.time() - started, 1)}
            turns_log.write(json.dumps(rec) + "\n")
            turns_log.flush()

        def begin_turn():
            close_turn()
            idx = state["turn"]
            slot = scheme[idx] if idx < len(scheme) else stock_slot
            state.update(turn=idx + 1, slot=slot, slot_index=idx if idx < len(scheme) else -1, actions_in_turn=0,
                         delta_report=None, turn_started_actions=session.action_count,
                         turn_started_tokens=agent.generated_tokens)
            apply_slot_limits(slot)
            if slot["mode"] not in result["modes_run"]:
                result["modes_run"].append(slot["mode"])
            flush(status="playing", turn=state["turn"], mode=slot["mode"],
                  actions=session.action_count - start_actions, level=sv._level_number(game),
                  levels_cleared=int(game.current_state.levels_completed) - start_completed)

        # ---- exact capture
        def snapshot_now() -> dict:
            blob, skipped = checkpoints.capture_state(agent, session)
            completed = int(game.current_state.levels_completed)
            return {"blob": blob, "skipped": skipped, "level": completed + 1, "actions": copy.deepcopy(ACTION_LOG),
                    "tokens": agent.generated_tokens, "board": grid_hash(sv, game),
                    "actions_into_level": (session.action_count - cap["clear_action_count"]
                                           if cap["clear_action_count"] is not None else None)}

        def save_checkpoint(snap: dict, body: dict, how: str) -> None:
            try:
                d = checkpoints.save(
                    game=spec["game"], game_id=game.game_run.game_id, level=snap["level"], variant=spec["variant"],
                    request_body=body, state_blob=snap["blob"], skipped=snap["skipped"], actions=snap["actions"],
                    meta={"exact_lineage": exact_lineage, "context": context, "source_job": job_dir.name, "source_sample": k,
                          "source_kind": spec.get("kind", "play"), "start_kind": result["start_kind"],
                          "parent_checkpoint": result.get("start_checkpoint"), "tokens_to_reach": snap["tokens"],
                          "actions_into_level": snap["actions_into_level"], "board_sha256": snap["board"],
                          "captured": how, "model_id": spec["model"]["model_id"], "prompt_profile": profile,
                          "stock_settings": checkpoints.STOCK_SETTINGS,
                          "notebook_env": {k2: os.environ.get(k2) for k2 in sorted(os.environ)
                                           if k2.startswith(("ARC3_", "LOCAL_ANALYZER_", "MULTIMODAL_", "EXPOSE_"))
                                           and "KEY" not in k2},
                          "levels_total": int(game.number_of_levels)})
                result["checkpoints_written"].append({"level": snap["level"], "id": d.name, "how": how,
                                                      "actions_to_reach": len(snap["actions"])})
            except Exception as exc:  # noqa: BLE001 - a failed save must not end the sample; it is recorded
                result.setdefault("checkpoint_errors", []).append(f"{type(exc).__name__}: {exc}")

        def dry_build(args, kwargs, snap: dict) -> dict | None:
            """Build the Stock request for this turn without sending it, then put the saved state back."""
            saved_slot = state["slot"]
            size = session.transcript_path.stat().st_size if session.transcript_path.exists() else 0
            state["slot"] = capture_slot
            apply_slot_limits(capture_slot)
            cap.update(dry=True, dry_body=None)
            try:
                original_analyze(*args, **{**kwargs, "should_stop": lambda: False})
            except DryStop:
                pass
            finally:
                cap["dry"] = False
                checkpoints.restore_state(snap["blob"], agent, session)
                if session.transcript_path.exists():
                    with open(session.transcript_path, "r+b") as fh:
                        fh.truncate(size)
                state["slot"] = saved_slot
                if saved_slot is not None:
                    apply_slot_limits(saved_slot)
                state["delta_report"] = None
            return cap["dry_body"]

        def maybe_capture(args, kwargs, *, at_end: bool = False) -> None:
            completed = int(game.current_state.levels_completed)
            run = game.game_run
            if not cap["enabled"] or completed <= cap["done_completed"] or run is None or run.state != "playing" \
                    or completed >= int(game.number_of_levels) or sv._is_engine_game_over(game):
                return
            cap["done_completed"] = completed
            snap = snapshot_now()
            if not at_end and slot_is_stock(state["slot"]):
                cap["pending"] = snap        # captured as the real request goes out
                return
            body = dry_build(args, kwargs, snap)
            if body is not None:
                save_checkpoint(snap, body, "dry")
            else:
                result.setdefault("checkpoint_errors", []).append(f"level {snap['level']}: dry build sent nothing")

        import requests as requests_mod
        real_post = requests_mod.post

        def post(url, *a, **kw):
            body = kw.get("json")
            if isinstance(body, dict) and str(url).endswith("/chat/completions"):
                if cap["dry"]:
                    cap["dry_body"] = copy.deepcopy(body)
                    raise DryStop()
                if cap["pending"] is not None:
                    snap, cap["pending"] = cap["pending"], None
                    save_checkpoint(snap, copy.deepcopy(body), "natural")
                if cap["compare"] is not None:
                    saved, cap["compare"] = cap["compare"], None
                    with gzip.open(out / "first_request.json.gz", "wt", encoding="utf-8") as fh:
                        json.dump(body, fh)
                    diff = checkpoints.diff_requests(saved, body)
                    diff["first_slot_is_stock"] = slot_is_stock(state["slot"] or stock_slot)
                    # a checkpoint saved under another prompt profile cannot be byte-equal; say so next to the answer
                    diff["saved_profile"] = (cp["meta"].get("prompt_profile") or "original") if cp else None
                    diff["profile"] = profile
                    result["first_request"] = diff
            return real_post(url, *a, **kw)
        requests_mod.post = post

        original_execute = session._execute_action

        def execute(self, action, **kw):
            before = int(game.current_state.levels_completed)
            payload = original_execute(action, **kw)
            if int(game.current_state.levels_completed) > before:
                cap["clear_action_count"] = session.action_count
            return payload
        session._execute_action = types.MethodType(execute, session)

        original_analyze = agent.analyze

        def analyze(self, *a, **kw):
            if not getattr(self, "_resume_after_yield", False):
                begin_turn()
                maybe_capture(a, kw)
            cap["in_analyze"] = True
            try:
                out_ = original_analyze(*a, **kw)
            finally:
                cap["in_analyze"] = False
            # A turn counts toward the turn cap only once it has finished: not a retryable failure, and not
            # yielding into a continuation of the same turn. should_stop also runs mid-turn, so it must not
            # look at the turn that is still in progress.
            if out_ is not None and not getattr(out_, "retryable_failure", False) \
                    and not getattr(self, "_resume_after_yield", False):
                state["turns_done"] = state["turn"]
            return out_
        agent.analyze = types.MethodType(analyze, agent)

        original_build = agent._build_user_prompt

        def build_user_prompt(self, *a, **kw):
            text = original_build(*a, **kw)
            slot = state["slot"] or stock_slot
            key = slot["key"]
            if profile == "dedup":
                new, report = prompt_profiles.turn_message(self, text, slot.get("name") or slot["mode"], instr[key])
            elif key in deltas:
                new, report = apply_delta(deltas[key], text)
            else:
                new, report = insert_original(text, spec["variant"], instr[key])
            state["delta_report"] = report
            return new
        agent._build_user_prompt = types.MethodType(build_user_prompt, agent)

        original_payload = ta.build_chat_payload

        def build_chat_payload(**kw):
            s = (state["slot"] or stock_slot)["settings"]
            if s.get("temperature") is not None:
                kw["temperature"] = float(s["temperature"])
            if s.get("thinking") is not None:
                kw["thinking"] = bool(s["thinking"])
            return original_payload(**kw)
        ta.build_chat_payload = build_chat_payload

        original_template_kwargs = agent._harness_template_kwargs

        def harness_template_kwargs(self):
            kw = original_template_kwargs()
            s = (state["slot"] or stock_slot)["settings"]
            effort = s.get("effort")
            # the harness's own step-down ladder (after a truncated reply) still wins over the slot's effort
            if effort and effort != "default" and "reasoning_effort" not in kw:
                kw["reasoning_effort"] = effort
            if s.get("thinking") is not None:
                kw["enable_thinking"] = bool(s["thinking"])
            return kw
        agent._harness_template_kwargs = types.MethodType(harness_template_kwargs, agent)

        original_step_env = session.step_env

        def step_env(self, arguments):
            budget = (state["slot"] or stock_slot)["settings"].get("actions")
            if budget is None or str(arguments.get("query") or "") == "animation":
                return original_step_env(arguments)
            left = int(budget) - state["actions_in_turn"]
            if left <= 0:
                return self._error_payload(
                    f"The action budget for this turn ({budget}) is used up; no action was executed. "
                    "End this turn; the next turn starts a new budget.")
            args = dict(arguments)
            cut = False
            if isinstance(args.get("actions"), list) and len(args["actions"]) > left:
                args["actions"] = args["actions"][:left]
                cut = True
            before = self.action_count
            payload = original_step_env(args)
            state["actions_in_turn"] += self.action_count - before
            if cut and isinstance(payload, dict):
                payload["action_budget_note"] = (f"Only the first {left} action(s) of the batch ran: this turn's "
                                                 f"action budget is {budget}.")
            return payload
        session.step_env = types.MethodType(step_env, session)

        original_should_stop = session.should_stop
        cap_actions = int(spec["caps"]["max_actions"])
        # Turn cap (added 6-Oct): the main per-sample limit, so a sample gets the same number of model turns
        # however busy the cluster is. The time cap stays as a safety net. Older specs have no max_turns.
        cap_turns = int(spec["caps"].get("max_turns") or 0)

        def stop_now() -> bool:
            if original_should_stop():
                return True
            if int(game.current_state.levels_completed) >= target_completed:
                return True
            if cap_turns and state.get("turns_done", 0) >= cap_turns:
                return True
            return session.action_count - start_actions >= cap_actions

        def should_stop(self):
            stop = stop_now()
            if stop and not cap["in_analyze"] and not cap["dry"]:
                # Stopping right after a clear: there is no next turn to capture from, so build its Stock request
                # the way the harness's loop would (count the turn, write the runtime state) without sending it.
                completed = int(game.current_state.levels_completed)
                if cap["enabled"] and completed > cap["done_completed"]:
                    self.analysis_step += 1
                    self.write_runtime_state()
                    kwargs = {"valid_actions": sv._engine_action_names(game), "step_env": self.step_env,
                              "transcript_path": self.transcript_path, "analysis_step": self.analysis_step,
                              "request_timeout_seconds": self.request_timeout_seconds()}
                    try:
                        maybe_capture((self.state_path, self.action_count), kwargs, at_end=True)
                    finally:
                        self.analysis_step -= 1
            return stop
        session.should_stop = types.MethodType(should_stop, session)

        flush(status="playing")
        session.play()
        close_turn()
        turns_log.close()

        completed = int(game.current_state.levels_completed)
        run = game.game_run
        cleared = completed - start_completed
        used = session.action_count - start_actions
        if completed >= target_completed:
            outcome = "cleared" if spec.get("kind") != "harvest" else "won"
        elif run is not None and str(run.state) in ("won",):
            outcome = "won"
        elif used >= cap_actions:
            outcome = "action_cap"
        elif cap_turns and state.get("turns_done", 0) >= cap_turns:
            outcome = "turn_cap"
        elif session.runtime_limit_reached():
            outcome = "time_cap"
        elif run is not None and (run.solver_note or "").startswith(("error", "analyzer failed")):
            outcome = "error"
            result["error"] = run.solver_note
        else:
            outcome = "stopped"
        result.update(outcome=outcome, levels_cleared=cleared, actions_used=used, turns=state["turn"],
                      final_level=sv._level_number(game), generated_tokens=agent.generated_tokens - start_tokens,
                      solver_note=getattr(run, "solver_note", None))
        flush(status="done", actions=used, levels_cleared=cleared, level=sv._level_number(game))
    except Exception as exc:  # recorded, never hidden: the job page shows it per sample
        result["error"] = f"{type(exc).__name__}: {exc}"
        (out / "error.txt").write_text(traceback.format_exc())
        flush(status="error", error=result["error"])
    result["seconds"] = round(time.time() - started, 1)
    write_json(out / "result.json", result)
    return 0 if result["outcome"] != "error" else 1


def verify_checkpoint(path: Path, out: Path) -> dict:
    """Replay + restore check of one checkpoint, no model call."""
    cp = checkpoints.load(path)
    spec = {"variant": cp["meta"]["variant"], "caps": {"max_minutes": 40},
            "model": {"base_url": "http://127.0.0.1:9/v1", "model_id": "none"}}
    out.mkdir(parents=True, exist_ok=True)
    try:
        _, game, agent, session, sv, _ = restore_checkpoint(spec, cp, out, 0)
        return {"ok": True, "id": cp["meta"]["id"], "level": cp["meta"]["level"], "actions": session.action_count,
                "history_messages": len(agent._history_messages), "kept_functions": len(agent._kept_functions)}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "id": cp["meta"]["id"], "error": f"{type(exc).__name__}: {exc}"}


if __name__ == "__main__":
    if sys.argv[1] == "--verify":
        print(json.dumps(verify(Path(sys.argv[2]), Path(sys.argv[3]))))
        sys.exit(0)
    if sys.argv[1] == "--verify-checkpoint":
        print(json.dumps(verify_checkpoint(Path(sys.argv[2]), Path(sys.argv[3]))))
        sys.exit(0)
    if sys.argv[1] == "--render-first":   # <game> <level> <variant> <out dir>: No-context first request, no model
        print(json.dumps(render_first_request(sys.argv[2], int(sys.argv[3]), sys.argv[4], Path(sys.argv[5]))))
        sys.exit(0)
    if sys.argv[1] == "--render-all":   # <out dir> [variant]: every trainable game and level, one process each
        import subprocess
        import replays
        folder, variant = Path(sys.argv[2]), (sys.argv[3] if len(sys.argv) > 3 else "son")
        rows = []
        for g, info in sorted(replays.summary()["games"].items()):
            for lv in range(1, int(info["levels"] or 0) + 1):
                r = subprocess.run([sys.executable, __file__, "--render-first", g, str(lv), variant, str(folder / f"{g}-{lv}")],
                                   capture_output=True, text=True, timeout=900)
                try:
                    v = json.loads(r.stdout.strip().splitlines()[-1])
                except (IndexError, json.JSONDecodeError):
                    v = {"ok": False, "game": g, "level": lv, "error": (r.stderr or r.stdout)[-300:]}
                v.pop("user_prompt_head", None)
                rows.append(v)
                print(g, lv, v.get("ok"), v.get("source"), v.get("error", ""), flush=True)
        write_json(folder / "render-checks.json", rows)
        sys.exit(0 if all(v.get("ok") for v in rows) else 1)
    if sys.argv[1] == "--verify-all":   # every snapshot in a folder, one process each; writes verified.json there
        import subprocess
        from datetime import datetime, timezone
        folder = Path(sys.argv[2])
        results = {}
        for entry in json.loads((folder / "index.json").read_text())["snapshots"]:
            g = entry["game"]
            r = subprocess.run([sys.executable, __file__, "--verify", str(folder / f"{g}.json"), f"/tmp/arc3v/{g}"],
                               capture_output=True, text=True, timeout=900)
            try:
                v = json.loads((r.stdout.strip().splitlines() or ["{}"])[-1])
            except json.JSONDecodeError:
                v = {"ok": False, "game": g, "error": (r.stderr or r.stdout)[-300:]}
            v["checked"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
            results[g] = v
            print(g, v.get("ok"), v.get("error", ""), flush=True)
        write_json(folder / "verified.json", results)
        sys.exit(0 if all(v.get("ok") for v in results.values()) else 1)
    sys.exit(main(Path(sys.argv[1]), int(sys.argv[2])))
