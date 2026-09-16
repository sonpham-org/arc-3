"""
Author: Claude Opus 5
Date: 16-September-2026
PURPOSE: Prove the arm-I RESET guard behaves as specified by driving the shipped solver
against a real offline game, rather than trusting a string match on the patch. Loads
_HarnessGameSession out of a built bundle directory, starts ls20 through TAAF's GameAPI
exactly as the Kaggle notebook does (offline Arcade, ONLY_RESET_LEVELS=true), and calls
step_env the way the tool agent does. Also runs the opening RESET against arm B's bundle,
which is the evidence that RESET was hidden, not blocked, in arms A-H.
Usage: python test_reset_guard.py <bundle-I dir> <bundle-B dir> <environment_files dir>
Needs arcengine==0.9.3, arc_agi, imageio, numpy, pydantic on the interpreter.
SRP/DRY check: Pass - build_bundles.py owns the patch; this only exercises what it built.
"""

import os
import subprocess
import sys
import tempfile
import threading
from pathlib import Path

GAME = "ls20-9607627b"


def open_session(bundle: Path, env_dir: Path, work: Path):
    sys.dont_write_bytecode = True  # never leave __pycache__ inside an upload directory
    os.environ["ONLY_RESET_LEVELS"] = "true"  # notebook cell 3 pins this before any game
    sys.path[:0] = [str(bundle / "src/ARC3-Inference"), str(bundle / "src/tufa-arc-agi-framework/src")]
    import arc_agi
    import taaf.game_api
    from inference.framework import solver as solver_module

    spec = taaf.game_api.ArcadeSpec(
        operation_mode=arc_agi.OperationMode.OFFLINE, environments_dir=str(env_dir)
    )
    game = taaf.game_api.GameAPI(env_name=GAME, arcade_spec=spec)
    game.start_game()
    solver = solver_module.HarnessSolver(label="reset-guard-test")
    session = solver_module._HarnessGameSession(
        solver=solver,
        game=game,
        analyzer=None,
        game_index=0,
        pass_index=0,
        state_path=work / "state.json",
        transcript_path=work / "transcript.txt",
        analysis_html_relpath="analysis.html",
        stop_event=threading.Event(),
        viewer_data_path=work / "viewer.json",
    )
    return solver_module, session


def step(session, *names):
    return session.step_env({"actions": [{"action": name} for name in names]})


def check(label, condition, detail=""):
    print(f"{'PASS' if condition else 'FAIL'}  {label}{'  ' + str(detail) if detail else ''}")
    if not condition:
        raise SystemExit(1)


def run_arm_i(bundle, env_dir, work):
    module, s = open_session(bundle, env_dir, work)
    check("guard constant is 20", module._RESET_MIN_ACTION_GAP == 20)

    menu = s.model_action_names()
    check("opening: RESET absent from menu", "RESET" not in menu, menu)
    before = s.action_count
    r = step(s, "RESET")
    check("opening: RESET refused", r.get("executed") is False and r.get("stop_reason") == "reset_rate_limited", r.get("error"))
    check("opening: refusal spends no action", s.action_count == before)

    step(s, "UP")
    check("after one move: RESET offered", "RESET" in s.model_action_names())
    r = step(s, "RESET")
    check("after one move: RESET executes", r.get("executed") is True and r.get("action_name") == "RESET")
    check("RESET is a level reset, not a full restart", s.game.current_state.raw.full_reset is False)
    check("RESET counts as an action", s.action_count == 2, s.action_count)
    check("payload menu hides RESET right after RESET", "RESET" not in r.get("valid_actions", []), r.get("valid_actions"))

    r = step(s, "RESET")
    check("twice in a row: refused", r.get("stop_reason") == "reset_rate_limited" and r.get("executed") is False, r.get("error"))

    # Last model RESET is action 2. Any 20 consecutive actions may hold one RESET, so actions
    # 2..21 are one window and action 22 is the first RESET position allowed.
    for _ in range(17):
        step(s, "LEFT" if s.action_count % 2 else "RIGHT")
    check("17 moves later (next would be action 20): refused", s.reset_refusal() is not None, s.reset_refusal())
    r = step(s, "UP", "RESET", "DOWN")
    check("batch hits the window: executes the move, stops at RESET",
          r.get("executed_count") == 1 and r.get("stop_reason") == "reset_rate_limited" and "stop_detail" in r,
          {k: r.get(k) for k in ("executed_count", "stop_reason", "stop_detail")})
    check("next would be action 21, same window: still refused", s.action_count == 20 and s.reset_refusal() is not None, s.action_count)
    step(s, "DOWN")
    check("next would be action 22: RESET offered", "RESET" in s.model_action_names(), s.action_count)
    r = step(s, "RESET", "UP")
    check("batch RESET then move: both execute", r.get("executed_count") == 2, r.get("executed_actions"))

    # The harness auto-reset blocks an immediate model RESET but does not use the window.
    for _ in range(19):
        step(s, "LEFT" if s.action_count % 2 else "RIGHT")
    positions = list(s.model_reset_positions)
    s._execute_auto_reset()
    check("auto-reset does not record a model RESET", s.model_reset_positions == positions)
    check("right after auto-reset: model RESET refused", s.reset_refusal() is not None)
    step(s, "UP")
    check("one move after auto-reset: RESET offered", s.reset_refusal() is None, s.reset_refusal())
    check("guard counted every refused request (opening, in a row, batch)", s.reset_refusals == 3, s.reset_refusals)
    s.game.finish_game()


def run_arm_b(bundle, env_dir, work):
    module, s = open_session(bundle, env_dir, work)
    check("arm B: RESET absent from menu", "RESET" not in s.model_action_names() if hasattr(s, "model_action_names")
          else "RESET" not in module._engine_action_names(s.game))
    step(s, "UP")
    r = step(s, "RESET")
    check("arm B: a typed RESET executes anyway (hidden, not blocked)", r.get("executed") is True and r.get("action_name") == "RESET")
    s.game.finish_game()


if __name__ == "__main__":
    if len(sys.argv) == 5:  # child process: one bundle per interpreter, so imports never mix
        arm, bundle, env_dir = sys.argv[1], Path(sys.argv[2]), Path(sys.argv[3])
        with tempfile.TemporaryDirectory() as work:
            (run_arm_i if arm == "I" else run_arm_b)(bundle, env_dir, Path(work))
        sys.exit(0)
    bundle_i, bundle_b, env_dir = sys.argv[1:4]
    for arm, bundle in (("I", bundle_i), ("B", bundle_b)):
        print(f"--- arm {arm}: {bundle}")
        subprocess.run([sys.executable, __file__, arm, bundle, env_dir, "child"], check=True)
    print("all reset-guard checks passed")
