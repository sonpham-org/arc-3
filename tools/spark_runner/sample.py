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
    2. Import the patched bundle exactly as the notebook does, unpickle its benchmark for the solver, start the game
       in the offline arc_agi engine, then replay the snapshot's action line through the harness's own
       _execute_action (so history, frames and animation records are the harness's own) and refuse to play if the
       board, level or action count differ from what the recorded run had at that point.
    3. Give the agent the snapshot's rebuilt conversation and retained functions, then play with session.play(),
       the harness's own loop, with five narrow hooks:
         - _build_user_prompt: the scheduled mode's delta (modes.py) is applied to the prompt the harness built;
         - _chat_completion / build_chat_payload: temperature, thinking on/off, reasoning effort of the slot;
         - _tool_steps and _yield_tokens: tool-call limit and thinking budget of the slot;
         - step_env: the slot's action budget (a batch is cut to what is left; nothing past it executes);
         - should_stop: stop when the target level is cleared, the game ends, or the sample's action/time cap is hit.
       A "turn" is one opener prompt; a yield continuation of the same turn keeps the same slot. When the scheme
       runs out, Stock (with the Stock settings the page sent) plays every later turn.
    4. Trajectory under <job>/samples/<k>/: transcript.txt (the harness's own transcript: every prompt, thinking,
       tool call and tool result), turns.jsonl (per turn: mode, settings, how the delta applied, actions, level,
       tokens), viewer.json (frames), progress.json while running, result.json at the end.
  Usage: sample.py <job_dir> <sample_index>   (reads <job_dir>/spec.json; written by server.py)
         sample.py --verify-all <snapshots dir>   (replay check of every snapshot, no model; writes verified.json)
SRP/DRY check: Pass - no harness logic is copied; everything runs through the bundle's ToolAgent and
  _HarnessGameSession. Mode text math lives in modes.py, queueing in server.py.
"""
from __future__ import annotations

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
from modes import apply_delta, build_delta  # noqa: E402

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


def replay_to_snapshot(spec: dict, snap: dict, out: Path, k: int, flush=lambda **kw: None):
    """Start the game in the offline engine and replay the snapshot's action line through the harness's own
    _execute_action. Raises if the board, level or action count differ from the recorded run."""
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
    game = taaf.game_api.GameAPI(env_name=snap["game_id"], arcade_spec=arcade_spec)
    game.start_game(taaf.game.RunSession())
    agent = solver._make_analyzer(game, 0, None)
    stem = solver._run_stem(game.game_run.game_id, k)
    session = sv._HarnessGameSession(
        solver=solver, game=game, analyzer=agent, game_index=0, pass_index=k,
        state_path=solver._artifacts_dir() / f"{stem}_{sv.RUNTIME_STATE_FILENAME}",
        transcript_path=out / "transcript.txt", analysis_html_relpath=f"solver_analysis/{stem}.html",
        stop_event=threading.Event(), viewer_data_path=out / "viewer.json")
    flush(status="replaying")
    session.seed_initial_history()
    for a in snap["actions"]:
        data = {"x": a["col"], "y": a["row"]} if a["name"] == "ACTION6" else {}
        action = sv.arcengine.ActionInput(id=sv.arcengine.GameAction.from_name(a["name"]), data=data)
        session._execute_action(action, batch_index=1, batch_size=1, generated_tokens=0,
                                flush_viewer_payload=False, automatic=a["name"] == "RESET")
    exp = snap["expected"]
    got_board = board_ascii(sv._grid_from_state(game.current_state), exp["color_chars"])
    got = {"level": sv._level_number(game), "action_count": session.action_count,
           "board_sha256": hashlib.sha256(got_board.encode()).hexdigest()}
    if (got["level"], got["action_count"], got["board_sha256"]) != (exp["level"], exp["action_count"], exp["board_sha256"]):
        raise RuntimeError(f"snapshot replay mismatch: expected {exp}, engine gave {got}")
    return solver, game, agent, session, sv, ta


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


def main(job_dir: Path, k: int) -> int:
    spec = json.loads((job_dir / "spec.json").read_text())
    out = job_dir / "samples" / str(k)
    out.mkdir(parents=True, exist_ok=True)
    snap = json.loads(Path(spec["snapshot_path"]).read_text())
    started = time.time()
    progress = {"sample": k, "status": "starting", "turn": 0, "mode": None, "actions": 0, "level": None,
                "levels_cleared": 0, "started": started, "updated": started}

    def flush(**kw):
        progress.update(kw, updated=time.time())
        write_json(out / "progress.json", progress)

    flush()
    result = {"sample": k, "game": spec["game"], "stuck_level": spec["stuck_level"], "variant": spec["variant"],
              "outcome": "error", "levels_cleared": 0, "actions_used": 0, "turns": 0, "modes_run": [],
              "conversation_exact": snap["conversation"]["exact"], "seconds": 0, "error": None}
    try:
        solver, game, agent, session, sv, ta = replay_to_snapshot(spec, snap, out, k, flush)
        start_actions = session.action_count
        start_completed = int(game.current_state.levels_completed)
        target_completed = int(spec["stuck_level"]) - 1 + int(spec["caps"]["levels_to_play"])
        result["replay_verified"] = True

        # ---- conversation and retained functions from the snapshot
        agent._ensure_session(session.state_path)
        history = [m for t in snap["turns"] for m in t["messages"]]
        agent._history_messages = history
        if ta._persistent_functions():
            agent._kept_functions = dict(snap.get("retained_functions") or {})

        # ---- per-turn scheduling hooks
        stock_slot = spec["stock"]
        scheme = spec["scheme"]
        deltas = {}
        for slot in scheme + [stock_slot]:
            key = slot["key"]
            if key not in deltas:
                deltas[key] = build_delta(slot["mode"], slot["stock_template"], slot["prompt"])
        base_tool_steps, base_yield_tokens = agent._tool_steps, agent._yield_tokens
        state = {"turn": 0, "slot": None, "slot_index": -1, "actions_in_turn": 0, "delta_report": None,
                 "turn_started_actions": start_actions, "turn_started_tokens": 0}
        turns_log = open(out / "turns.jsonl", "a", encoding="utf-8")

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
            s = slot["settings"]
            agent._tool_steps = int(s["tool_calls"]) if s.get("tool_calls") else base_tool_steps
            agent._yield_tokens = int(s["thinking_budget"]) if s.get("thinking_budget") else base_yield_tokens
            if slot["mode"] not in result["modes_run"]:
                result["modes_run"].append(slot["mode"])
            flush(status="playing", turn=state["turn"], mode=slot["mode"],
                  actions=session.action_count - start_actions, level=sv._level_number(game),
                  levels_cleared=int(game.current_state.levels_completed) - start_completed)

        original_analyze = agent.analyze

        def analyze(self, *a, **kw):
            if not getattr(self, "_resume_after_yield", False):
                begin_turn()
            return original_analyze(*a, **kw)
        agent.analyze = types.MethodType(analyze, agent)

        original_build = agent._build_user_prompt

        def build_user_prompt(self, *a, **kw):
            text = original_build(*a, **kw)
            slot = state["slot"]
            new, report = apply_delta(deltas[slot["key"]], text)
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

        def should_stop(self):
            if original_should_stop():
                return True
            if int(game.current_state.levels_completed) >= target_completed:
                return True
            return self.action_count - start_actions >= cap_actions
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
            outcome = "cleared"
        elif run is not None and str(run.state) in ("won",):
            outcome = "won"
        elif used >= cap_actions:
            outcome = "action_cap"
        elif session.runtime_limit_reached():
            outcome = "time_cap"
        elif run is not None and (run.solver_note or "").startswith(("error", "analyzer failed")):
            outcome = "error"
            result["error"] = run.solver_note
        else:
            outcome = "stopped"
        result.update(outcome=outcome, levels_cleared=cleared, actions_used=used, turns=state["turn"],
                      final_level=sv._level_number(game), generated_tokens=agent.generated_tokens,
                      solver_note=getattr(run, "solver_note", None))
        flush(status="done", actions=used, levels_cleared=cleared, level=sv._level_number(game))
    except Exception as exc:  # recorded, never hidden: the job page shows it per sample
        result["error"] = f"{type(exc).__name__}: {exc}"
        (out / "error.txt").write_text(traceback.format_exc())
        flush(status="error", error=result["error"])
    result["seconds"] = round(time.time() - started, 1)
    write_json(out / "result.json", result)
    return 0 if result["outcome"] != "error" else 1


if __name__ == "__main__":
    if sys.argv[1] == "--verify":
        print(json.dumps(verify(Path(sys.argv[2]), Path(sys.argv[3]))))
        sys.exit(0)
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
