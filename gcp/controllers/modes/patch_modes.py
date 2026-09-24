"""Per-turn mode switching on a shared, minimal system prompt.

Son, 25-Sep: "we simplify system prompt and try to switch mode in user prompt":

    System prompt (small, fixed)  ->  User prompt (+ this turn's mode paragraph)  ->  Response  ->  ...

The shared system prompt is the solver arm's (the five prompt surfaces deleted via ARC3_PROMPT_ABLATE_*,
set by the derive). Everything an arm used to add to the system prompt becomes a short paragraph the host
appends to the LAST user message of each request and strips again from the persistent history, exactly
like the [Runtime budget] reminder (budget_reminder.py) -- so the prefix cache is never touched and old
paragraphs do not pile up in the context. The host enforces the mode through the sandbox payload (action
cap, expect() requirement), so the text and the behaviour always agree.

Modes (ModeRouter, appended to inference/agent/budget_reminder.py -- the bundle file set is fixed):
  act     no paragraph, cap 14, no requirement            (= the solver arm)
  verify  expect(check) before every action, cap 14       (= the selfcheck arm's mechanism)
  probe   one action per call, name the control under test, keep the untested-control list, write the
          level's goal spec; RESET is fine
  batch   predictions have held: up to 8 actions per call, expect() each, halts on first mismatch
  router  rule-based per-turn choice from host state: probe at the start of each level and after a
          long stall, verify otherwise, batch once the last three expect() verdicts passed

ARC3_TURN_MODE=act|verify|probe|batch|router selects the fixed mode or the router (exported by the
startup after the bundled selftests, like ARC3_PREDICTION_CHECK, so the selftests see legacy behaviour).

Applied to a candidate tree: the router appended to budget_reminder.py, tool_agent.py hooks (init/reset, request assembly, action
bookkeeping, sandbox payload), the sandbox action() with expect() + cap, and ONE constant-only sentence in
the python tool description. The prompt identity selftest re-executes the assembling functions against
installed constants, so it still holds.

Usage: python patch_modes.py <candidate_src_root>
"""
import sys
from pathlib import Path

MODE_ROUTER_SRC = r'''

# ---------------------------------------------------------------------------- per-turn mode router
# (patch_modes.py) Per-turn mode paragraph + host gates. Lives in this module because the bundle's file
# set is fixed by its release manifest; it reuses the reminder mechanics above (inject into the request
# copy, strip from the persistent history).
from collections import deque

MODES = ("act", "verify", "probe", "batch")
_LINE = re.compile(r"\n\[Turn mode: [a-z]+\][^\n]*(?=\n|$)|\A\[Turn mode: [a-z]+\][^\n]*(?:\n|$)")

PARAGRAPHS = {
    "act": "",
    "verify": (
        "[Turn mode: verify] Before every action(...) call expect(check) with a concrete predicate on the next frame "
        "(a cell colour, an object position, board_changed, level_completed). The host runs it on the real transition "
        "and on a no-op counterfactual; a wrong or trivial prediction stops the batch and tells you why. Up to 14 actions per call."
    ),
    "probe": (
        "[Turn mode: probe] One action this turn. First list every distinct object or glyph on the board you have NOT yet "
        "acted on, then test exactly one of them and say what you expect to change. Write the goal for this level in one line "
        "(what the frame looks like when solved) before acting toward it. RESET is acceptable to return to a known state."
    ),
    "batch": (
        "[Turn mode: batch] Your recent predictions held. You may send up to 8 actions per call; call expect(check) before "
        "each action and the batch halts on the first mismatch. Re-inspect the board when it does."
    ),
}
GATES = {
    "act": {"action_cap": 14, "prediction_required": False},
    "verify": {"action_cap": 14, "prediction_required": True},
    "probe": {"action_cap": 1, "prediction_required": False},
    "batch": {"action_cap": 8, "prediction_required": True},
}


def strip_modes(messages):
    copied = deepcopy(messages)
    for message in copied:
        if not isinstance(message, dict) or message.get("role") != "user":
            continue
        content = message.get("content")
        if isinstance(content, str):
            message["content"] = _LINE.sub("", content)
        elif isinstance(content, list):
            parts = []
            for part in content:
                if isinstance(part, dict) and part.get("type") == "text" and isinstance(part.get("text"), str):
                    part["text"] = _LINE.sub("", part["text"])
                    if not part["text"] and set(part) == {"type", "text"}:
                        continue
                parts.append(part)
            message["content"] = parts
    return copied


class ModeState:
    """Host-side facts the router decides on. Reset per game."""

    def __init__(self):
        self.actions_since_level = 0
        self.turns_since_level = 0
        self.levels = 0
        self.verdicts = deque(maxlen=8)      # "passed" / "failed" / "trivial" / "invalid" / "missing"
        self.turns = 0
        self.history = []                   # (turn, mode) for the transcript

    def note_actions(self, executed: int, level_completed: bool):
        self.actions_since_level += max(0, int(executed))
        if level_completed:
            self.levels += 1
            self.actions_since_level = 0
            self.turns_since_level = 0
            self.verdicts.clear()

    def note_verdicts(self, statuses):
        for s in statuses:
            if s:
                self.verdicts.append(str(s))

    def note_turn(self, mode: str):
        self.turns += 1
        self.turns_since_level += 1
        self.history.append((self.turns, mode))


class ModeRouter:
    def __init__(self, policy: str = "act"):
        if policy not in MODES and policy != "router":
            raise ValueError(f"unknown ARC3_TURN_MODE {policy!r}")
        self.policy = policy
        self.mode = policy if policy in MODES else "probe"

    @classmethod
    def from_env(cls):
        return cls(os.environ.get("ARC3_TURN_MODE", "act").strip().lower() or "act")

    # ---- policy -------------------------------------------------------------------------------
    def decide(self, state: ModeState) -> str:
        if self.policy in MODES:
            return self.policy
        recent = list(state.verdicts)
        if state.turns_since_level < 6:
            return "probe"                                         # start of every level: inventory + goal spec
        if len(recent) >= 3 and all(v == "passed" for v in recent[-3:]):
            return "batch"
        stalled = state.actions_since_level > 80 and not any(v == "passed" for v in recent[-5:])
        if stalled and state.turns_since_level % 4 == 0:
            return "probe"                                         # every 4th turn of a stall: go back to probing
        return "verify"

    def gates(self) -> dict:
        return dict(GATES[self.mode])

    # ---- request assembly -----------------------------------------------------------------------
    def prepare(self, messages, state: ModeState):
        self.mode = self.decide(state)
        state.note_turn(self.mode)
        copied = strip_modes(messages)
        line = PARAGRAPHS[self.mode]
        emitted = False
        if line:
            user = next((m for m in reversed(copied) if isinstance(m, dict) and m.get("role") == "user"), None)
            if user is not None:
                content = user.get("content")
                if isinstance(content, str):
                    user["content"] = content + "\n" + line
                    emitted = True
                elif isinstance(content, list):
                    content.append({"type": "text", "text": line})
                    emitted = True
        return copied, {"mode": self.mode, "policy": self.policy, "emitted": emitted, "text": line or None,
                        "actions_since_level": state.actions_since_level, "turns_since_level": state.turns_since_level,
                        "verdicts": list(state.verdicts)}
'''

# ------------------------------------------------------------------------------------------ tool_agent hooks
IMPORT_OLD = "from inference.agent.budget_reminder import BudgetReminder, strip_reminders\n"
IMPORT_NEW = "from inference.agent.budget_reminder import BudgetReminder, strip_reminders, ModeRouter, ModeState, strip_modes\n"

INIT_OLD = '''        self._budget_reminder = BudgetReminder() if os.environ.get("ARC3_BUDGET_REMINDER_ENABLED") == "1" else None
'''
INIT_NEW = INIT_OLD + '''        self._mode_router = ModeRouter.from_env()
        self._mode_state = ModeState()
'''
RESET_OLD = '''            if self._budget_reminder is not None:
                self._budget_reminder = BudgetReminder()
            self._last_step_summary = None
'''
RESET_NEW = '''            if self._budget_reminder is not None:
                self._budget_reminder = BudgetReminder()
            self._mode_state = ModeState()
            self._last_step_summary = None
'''
REQUEST_OLD = '''                request_messages = self._trim_messages_for_context(request_messages, tools=tools)
                if self._execution_mode is not None:
                    request_messages = self._execution_mode.refresh_messages(request_messages)
                    # Carry forward any context trimming, never the injected
                    # checkpoint. This keeps the persistent/KV prefix clean.
                    messages = self._execution_mode.strip_messages(request_messages)
                else:
                    messages = request_messages
                if self._budget_reminder is not None:
                    messages = strip_reminders(messages)
'''
REQUEST_NEW = '''                # Per-turn mode paragraph: appended to the request copy of the last user message and
                # stripped from the persistent history below, like the runtime-budget reminder.
                request_messages, mode_info = self._mode_router.prepare(request_messages, self._mode_state)
                request_messages = self._trim_messages_for_context(request_messages, tools=tools)
                if self._execution_mode is not None:
                    request_messages = self._execution_mode.refresh_messages(request_messages)
                    # Carry forward any context trimming, never the injected
                    # checkpoint. This keeps the persistent/KV prefix clean.
                    messages = self._execution_mode.strip_messages(request_messages)
                else:
                    messages = request_messages
                if self._budget_reminder is not None:
                    messages = strip_reminders(messages)
                messages = strip_modes(messages)
                append_transcript("TURN MODE", json.dumps(mode_info))
'''
ACTION_OLD = '''            compact_payload = self._compact_action_result(raw_payload)
'''
ACTION_NEW = '''            compact_payload = self._compact_action_result(raw_payload)
            self._mode_state.note_actions(
                len(raw_payload.get("executed_actions") or []) or int(bool(raw_payload.get("executed"))),
                bool(raw_payload.get("level_completed")),
            )
'''
SANDBOX_CALL_OLD = '''            workspace_handler=_handle_workspace if self._programmatic_workspace is not None else None,
        )
'''
SANDBOX_CALL_NEW = '''            workspace_handler=_handle_workspace if self._programmatic_workspace is not None else None,
            mode_gates=self._mode_router.gates(),
        )
'''
RESULTS_OLD = '''        action_results = [
            item
            for item in sandbox_result.get("action_results") or []
            if isinstance(item, dict)
        ]
'''
RESULTS_NEW = RESULTS_OLD + '''        self._mode_state.note_verdicts(
            (item.get("prediction_check") or {}).get("status") for item in action_results
        )
'''
TOOL_DESC_OLD = '''    "fields are rejected. Use `print(...)` for compact output or assign to `result`."
)'''
TOOL_DESC_NEW = '''    "fields are rejected. Use `print(...)` for compact output or assign to `result`. "
    "`expect(check)` registers a prediction `check(before, actions, after, result) -> bool` for the next "
    "`action(...)`; the turn's mode line says when it is required and how many actions a call may send."
)'''

# ------------------------------------------------------------------------------------------ sandbox
HOST_SIG_OLD = '''    workspace_handler: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
) -> dict[str, Any]:
'''
HOST_SIG_NEW = '''    workspace_handler: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
    mode_gates: dict[str, Any] | None = None,
) -> dict[str, Any]:
'''
HOST_PAYLOAD_OLD = '''                "workspace_enabled": workspace_handler is not None,
            },
'''
HOST_PAYLOAD_NEW = '''                "workspace_enabled": workspace_handler is not None,
                "mode_gates": dict(mode_gates or {}),
            },
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
SANDBOX_ACTION_NEW = r'''        # ---- per-turn mode gates (patch_modes.py): action cap and expect() requirement come from the host
        _gates = dict(initial.get("mode_gates") or {})
        _prediction_check = {"fn": None, "verdicts": [], "required": bool(_gates.get("prediction_required")),
                             "cap": int(_gates.get("action_cap") or 0), "sent": 0}

        def expect(check):
            # Register the predicate the next action(...) must satisfy: check(before, actions, after, result) -> bool.
            if not callable(check):
                raise TypeError("expect() needs a callable check(before, actions, after, result) -> bool")
            _prediction_check["fn"] = check
            return {"registered": True}

        def _run_check(fn, before, actions, after, result):
            try:
                value = fn(before, actions, after, result)
            except Exception as exc:
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

        def action(actions):
            normalized_actions = _normalize_actions(actions)
            cap = _prediction_check["cap"]
            if cap and _prediction_check["sent"] + len(normalized_actions) > cap:
                allowed = max(0, cap - _prediction_check["sent"])
                if allowed == 0:
                    raise _ActionSequenceInterrupted(
                        "This turn's mode allows " + str(cap) + " action(s) per call; the limit is reached. Read the refreshed board and act next turn."
                    )
                print("[mode cap] this turn allows " + str(cap) + " action(s) per call; sending the first " + str(allowed) + ".")
                normalized_actions = normalized_actions[:allowed]
            if _prediction_check["fn"] is None and _prediction_check["required"]:
                raise RuntimeError(
                    "This turn's mode requires a prediction first: call expect(lambda before, actions, after, result: ...) "
                    "before action(...)."
                )
            before_frame = runtime_globals.get("current_frame")
            _send({"type": "action", "actions": normalized_actions})
            reply = _recv()
            if reply.get("type") == "action_error":
                raise RuntimeError(str(reply.get("error", "action failed")))
            if reply.get("type") != "action_result":
                raise RuntimeError("Invalid action response from sandbox host.")
            action_result = reply.get("action_result") or {}
            _prediction_check["sent"] += len(normalized_actions)
            _refresh_state(reply.get("state") or {})
            verdict = None
            if _prediction_check["fn"] is not None or _prediction_check["required"]:
                verdict = _judge_prediction(before_frame, normalized_actions, runtime_globals.get("current_frame"), action_result)
                action_result = dict(action_result)
                action_result["prediction_check"] = verdict
                _prediction_check["verdicts"].append(verdict["status"])
                _prediction_check["fn"] = None
            action_results.append(action_result)
            if reply.get("interrupt_execution"):
                raise _ActionSequenceInterrupted(
                    str(action_result.get("stop_detail") or "Action sequence stopped")
                )
            if verdict is not None and verdict["status"] != "passed":
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


def sub_once(text: str, old: str, new: str, label: str) -> str:
    n = text.count(old)
    assert n == 1, f"{label}: expected exactly one match, found {n}"
    return text.replace(old, new)


def apply(root: Path) -> dict:
    agent = root / "inference" / "agent"
    br = agent / "budget_reminder.py"
    br.write_text(br.read_text(encoding="utf-8").rstrip("\n") + "\n" + MODE_ROUTER_SRC, encoding="utf-8", newline="\n")
    compile(br.read_text(encoding="utf-8"), "budget_reminder.py", "exec")
    ta = agent / "tool_agent.py"
    t = ta.read_text(encoding="utf-8")
    for old, new, label in ((IMPORT_OLD, IMPORT_NEW, "import"), (INIT_OLD, INIT_NEW, "init"), (RESET_OLD, RESET_NEW, "per-game reset"),
                            (REQUEST_OLD, REQUEST_NEW, "request assembly"), (ACTION_OLD, ACTION_NEW, "action bookkeeping"),
                            (SANDBOX_CALL_OLD, SANDBOX_CALL_NEW, "sandbox call"), (RESULTS_OLD, RESULTS_NEW, "verdict bookkeeping"),
                            (TOOL_DESC_OLD, TOOL_DESC_NEW, "tool description constant")):
        t = sub_once(t, old, new, label)
    ta.write_text(t, encoding="utf-8", newline="\n")
    sb = agent / "python_tool_sandbox.py"
    s = sb.read_text(encoding="utf-8")
    for old, new, label in ((HOST_SIG_OLD, HOST_SIG_NEW, "host signature"), (HOST_PAYLOAD_OLD, HOST_PAYLOAD_NEW, "host payload"),
                            (SANDBOX_ACTION_OLD, SANDBOX_ACTION_NEW, "sandbox action"), (SANDBOX_GLOBALS_OLD, SANDBOX_GLOBALS_NEW, "sandbox globals")):
        s = sub_once(s, old, new, label)
    sb.write_text(s, encoding="utf-8", newline="\n")
    # the bootstrap must still compile once dedented
    import importlib.util
    spec = importlib.util.spec_from_file_location("ptsb_check", sb)
    mod = importlib.util.module_from_spec(spec)
    sys.path.insert(0, str(root))
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    compile(mod._SANDBOX_BOOTSTRAP, "<bootstrap>", "exec")
    compile(t, "tool_agent.py", "exec")
    return {"changed": ["inference/agent/budget_reminder.py (+ModeRouter)", "inference/agent/tool_agent.py", "inference/agent/python_tool_sandbox.py"]}


if __name__ == "__main__":
    print(apply(Path(sys.argv[1]).resolve()))
