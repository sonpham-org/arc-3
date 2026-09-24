"""Arm E: prediction-checked actions where the MODEL writes the check, and the host proves it is substantial.

Son, 24-Sep: "prediction-checked by forcing the harness to write code to check itself. And the check has
to be substantial (not just return True)."

Applied to a candidate tree (three constant-only edits, so the selftests' prompt identity test still
holds -- it re-executes the assembling functions against installed constants):

  python_tool_sandbox.py  ->  `expect(check)` registers a callable `check(before, actions, after, result)
                              -> bool`. `action(...)` requires a registered check, runs it on the real
                              transition, and ALSO on a counterfactual (after := before, result := no-change)
                              which a substantial check must reject. Verdicts ride on `action_result`
                              under `prediction_check`; a failed or trivial check interrupts the batch via
                              the existing _ActionSequenceInterrupted path, so the model sees exactly why.
  tool_agent._PYTHON_TOOL_DESCRIPTION  ->  one added sentence describing `expect(...)`.
  prompts.PYTHON_ADDENDUM              ->  one added bullet with the rule.

Usage: python patch_selfcheck.py <candidate_src_root>   (…/src/ARC3-Inference)
"""
import re, sys
from pathlib import Path

SANDBOX_HOOK = r'''
        _prediction_check = {"fn": None, "verdicts": []}

        def expect(check):
            # Register the predicate the next action(...) must satisfy: check(before, actions, after, result) -> bool.
            # (No triple quotes here: this code lives inside the sandbox bootstrap string.)
            if not callable(check):
                raise TypeError("expect() needs a callable check(before, actions, after, result) -> bool")
            _prediction_check["fn"] = check
            return {"registered": True}

        def _run_check(fn, before, actions, after, result):
            try:
                value = fn(before, actions, after, result)
            except Exception as exc:  # a crashing check is a failed check, never a passed one
                return None, "check raised " + _sanitize_exception(exc)[:160]
            if isinstance(value, bool):
                return value, None
            return None, "check must return a bool, got " + type(value).__name__

        def _judge_prediction(before, actions, after, result):
            fn = _prediction_check["fn"]
            if fn is None:
                return {"status": "missing", "detail": "no expect(check) registered before action()"}
            real, real_err = _run_check(fn, before, actions, after, result)
            if real_err:
                return {"status": "invalid", "detail": real_err}
            # Substantiality: the same check must REJECT a world where the action did nothing.
            null_result = dict(result or {})
            null_result.update({"board_changed": False, "reward": 0, "level_completed": False})
            cf, cf_err = _run_check(fn, before, actions, before, null_result)
            if cf_err:
                return {"status": "invalid", "detail": "counterfactual: " + cf_err}
            if cf is True and real is True:
                return {"status": "trivial", "detail": "check accepts both the real transition and a no-op; it tests nothing"}
            if real is False:
                return {"status": "failed", "detail": "predicted transition did not occur"}
            return {"status": "passed", "detail": "check rejected the no-op and accepted the real transition"}

'''

SANDBOX_ACTION_OLD = '''        def action(actions):
            normalized_actions = _normalize_actions(actions)
            _send({"type": "action", "actions": normalized_actions})
            reply = _recv()
            if reply.get("type") == "action_error":
                raise RuntimeError(str(reply.get("error", "action failed")))
            if reply.get("type") != "action_result":
                raise RuntimeError("Invalid action response from sandbox host.")
            action_result = reply.get("action_result") or {}
            action_results.append(action_result)
            _refresh_state(reply.get("state") or {})
            if reply.get("interrupt_execution"):
                raise _ActionSequenceInterrupted(
                    str(action_result.get("stop_detail") or "Action sequence stopped")
                )
            return action_result
'''

SANDBOX_ACTION_NEW = '''        def action(actions):
            normalized_actions = _normalize_actions(actions)
            if _prediction_check["fn"] is None:
                raise RuntimeError(
                    "Register a substantial prediction first: expect(lambda before, actions, after, result: ...) "
                    "must be called before action(...)."
                )
            before_frame = runtime_globals.get("current_frame")
            _send({"type": "action", "actions": normalized_actions})
            reply = _recv()
            if reply.get("type") == "action_error":
                raise RuntimeError(str(reply.get("error", "action failed")))
            if reply.get("type") != "action_result":
                raise RuntimeError("Invalid action response from sandbox host.")
            action_result = reply.get("action_result") or {}
            _refresh_state(reply.get("state") or {})
            verdict = _judge_prediction(before_frame, normalized_actions, runtime_globals.get("current_frame"), action_result)
            action_result = dict(action_result)
            action_result["prediction_check"] = verdict
            _prediction_check["verdicts"].append(verdict["status"])
            _prediction_check["fn"] = None  # one registration per action; re-arm deliberately
            action_results.append(action_result)
            if reply.get("interrupt_execution"):
                raise _ActionSequenceInterrupted(
                    str(action_result.get("stop_detail") or "Action sequence stopped")
                )
            if verdict["status"] != "passed":
                # The host renders stdout in preference to action results, so say it where the model will read it.
                print("[prediction check " + verdict["status"].upper() + "] " + verdict["detail"])
                raise _ActionSequenceInterrupted(
                    "prediction check " + verdict["status"] + ": " + verdict["detail"]
                    + ". Re-inspect the refreshed board and register a new expect(...) before acting again."
                )
            return action_result
'''

SANDBOX_GLOBALS_OLD = '''        runtime_globals["action"] = action
        runtime_globals["remember"] = remember
'''
SANDBOX_GLOBALS_NEW = '''        runtime_globals["action"] = action
        runtime_globals["remember"] = remember
        runtime_globals["expect"] = expect
'''

TOOL_DESC_OLD = '''    "fields are rejected. Use `print(...)` for compact output or assign to `result`."
)'''
TOOL_DESC_NEW = '''    "fields are rejected. Use `print(...)` for compact output or assign to `result`. "
    "Before every `action(...)` you must register a prediction with `expect(check)`, where "
    "`check(before, actions, after, result) -> bool` reads frames (`.ascii`, `.segmentation`, `.level`) and "
    "`result` (`board_changed`, `reward`, `level_completed`). The host runs it on the real transition and on a "
    "no-op counterfactual; a check that accepts both is rejected as trivial, and a failed or trivial check stops "
    "the batch and reports why."
)'''

ADDENDUM_OLD = '''    "- Use `print(...)` or `result` for short decision-oriented output. Call `action(...)` inside Python; batch a reliable sequence or call it repeatedly in a loop, checking refreshed state after each'''
ADDENDUM_NEW = '''    "- Every `action(...)` must be preceded by `expect(check)`: write a concrete predicate on what the next frame or result will show (a cell color, an object moving, `reward`, `level_completed`). It must be false for a frame that did not change; the host verifies that and halts the batch on a wrong or empty prediction, so predict only what you can justify.\\n"
    "- Use `print(...)` or `result` for short decision-oriented output. Call `action(...)` inside Python; batch a reliable sequence or call it repeatedly in a loop, checking refreshed state after each'''


def sub_once(text: str, old: str, new: str, label: str) -> str:
    n = text.count(old)
    assert n == 1, f"{label}: expected exactly one match, found {n}"
    return text.replace(old, new)


def apply(root: Path) -> dict:
    agent = root / "inference" / "agent"
    sb = agent / "python_tool_sandbox.py"
    s = sb.read_text(encoding="utf-8")
    s = sub_once(s, SANDBOX_ACTION_OLD, SANDBOX_HOOK + SANDBOX_ACTION_NEW, "sandbox action()")
    s = sub_once(s, SANDBOX_GLOBALS_OLD, SANDBOX_GLOBALS_NEW, "sandbox globals")
    sb.write_text(s, encoding="utf-8", newline="\n")
    ta = agent / "tool_agent.py"
    t = ta.read_text(encoding="utf-8")
    t = sub_once(t, TOOL_DESC_OLD, TOOL_DESC_NEW, "tool description constant")
    ta.write_text(t, encoding="utf-8", newline="\n")
    pr = agent / "prompts.py"
    p = pr.read_text(encoding="utf-8")
    p = sub_once(p, ADDENDUM_OLD, ADDENDUM_NEW, "PYTHON_ADDENDUM bullet")
    pr.write_text(p, encoding="utf-8", newline="\n")
    return {"changed": [str(x.relative_to(root)) for x in (sb, ta, pr)]}


if __name__ == "__main__":
    print(apply(Path(sys.argv[1]).resolve()))
