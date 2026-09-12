"""Persistent semantic game memory with an optional evidence-gated execution lease.

The model owns a small semantic record and updates it through ``remember(...)``
inside the existing Python tool. The host owns observation bindings, evidence,
the plan cursor, phase changes, and safety exits. Invalid memory updates are
reported to the model but never block an otherwise valid investigation action.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import time
from collections import OrderedDict, deque
from pathlib import Path
from typing import Any

from inference.agent.action_names import to_model_action
from inference.agent.symbolic_search import normalize_spec, validate_observations


CHECKPOINT_PREFIX = "Game memory checkpoint: "
MAX_RULES = 6
MAX_UNCERTAINTIES = 4
MAX_PLAN_STEPS = 8
MAX_RULE_CHARS = 160
MAX_NOTE_CHARS = 120
MAX_STATE_CHARS = 280
MAX_GOAL_CHARS = 180
MAX_PLAN_NOTE_CHARS = 120
MAX_EXPECTATION_CHARS = 180
MAX_CHECK_CELLS = 8
# This includes ``CHECKPOINT_PREFIX``. The semantic state is richer internally;
# request-time rendering is deliberately small enough to remain cheap at every
# decision boundary.
MAX_CHECKPOINT_CHARS = 2400
MAX_SYMBOLIC_MODEL_BYTES = 24_000
DEFAULT_CONFIRMATIONS = 2
DEFAULT_LEASE_ACTIONS = 3
MAX_MODEL_HOST_INT = 2_147_483_647
_ID = re.compile(r"^[a-z][a-z0-9_-]{0,31}$")
_ACTIONS = {"UP", "DOWN", "LEFT", "RIGHT", "SPACE", "MOUSE", "RESET", "ACTION7"}


MEMORY_TOOL_DESCRIPTION = (
    "Python exposes remember(**updates) for a bounded persistent game model. "
    "It returns acceptance and host phase status; invalid updates fail open."
)


def _env_int(name: str, default: int, minimum: int, maximum: int) -> int:
    try:
        value = int(os.environ.get(name, str(default)))
    except (TypeError, ValueError):
        value = default
    return min(maximum, max(minimum, value))


def _digest(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()
    return hashlib.sha256(encoded).hexdigest()[:16]


def _text(value: Any, limit: int, label: str, *, empty: bool = False) -> str:
    if (
        not isinstance(value, str)
        or len(value) > limit
        or any(ord(char) < 32 or 0xD800 <= ord(char) <= 0xDFFF for char in value)
    ):
        raise ValueError(f"{label} must be a single line of at most {limit} characters")
    value = value.strip()
    if not value and not empty:
        raise ValueError(f"{label} must not be empty")
    return value


def _identifier(value: Any, label: str) -> str:
    if not isinstance(value, str) or not _ID.fullmatch(value):
        raise ValueError(f"{label} must match {_ID.pattern}")
    return value


def _action(value: Any) -> dict[str, Any]:
    if isinstance(value, str):
        value = {"action": value}
    if not isinstance(value, dict) or not isinstance(value.get("action"), str):
        raise ValueError("plan action must be a string or action object")
    name = to_model_action(value["action"])
    expected = {"action", "row", "col"} if name == "MOUSE" else {"action"}
    if set(value) != expected or name not in _ACTIONS:
        raise ValueError("invalid plan action fields")
    result: dict[str, Any] = {"action": name}
    if name == "MOUSE":
        for key in ("row", "col"):
            if type(value[key]) is not int or not 0 <= value[key] < 64:
                raise ValueError("MOUSE plan coordinates must be integers in 0..63")
            result[key] = value[key]
    return result


def _actions(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, (str, dict)):
        value = [value]
    if not isinstance(value, (list, tuple)) or not value:
        raise ValueError("actions must contain at least one grounded action")
    return [_action(item) for item in value]


def _frame_id(frame: Any) -> str | None:
    if frame is None:
        return None
    try:
        return _digest(frame.grid)
    except (OverflowError, TypeError, ValueError):
        return None


def _model_host_int(value: Any) -> int | None:
    """Bound untrusted runtime counters before they reach model-facing JSON."""
    if type(value) is int and 0 <= value <= MAX_MODEL_HOST_INT:
        return value
    return None


def _observation(frame: Any) -> dict[str, Any]:
    if frame is None:
        return {"level": None, "step": None, "frame": None}
    return {
        "level": _model_host_int(frame.level),
        "step": _model_host_int(frame.step),
        "frame": _frame_id(frame),
    }


class ExecutionMode:
    """Per-game CPU state. The historical name keeps integration changes small."""

    def __init__(self, *, execution_enabled: bool = True) -> None:
        self.execution_enabled = bool(execution_enabled)
        self.required_confirmations = _env_int(
            "ARC3_EXECUTION_CONFIRMATIONS", DEFAULT_CONFIRMATIONS, 1, 5
        )
        self.lease_actions = _env_int(
            "ARC3_EXECUTION_LEASE_ACTIONS", DEFAULT_LEASE_ACTIONS, 1, 8
        )
        self.path: Path | None = None
        self.mode = "investigate"
        self.confirmed_rules: OrderedDict[str, dict[str, Any]] = OrderedDict()
        self.uncertainties: OrderedDict[str, dict[str, Any]] = OrderedDict()
        self.current_state = ""
        self.goal = ""
        self.symbolic_model: dict[str, Any] | None = None
        self.plan: list[dict[str, Any]] = []
        self.cursor = 0
        self.expected_next: dict[str, Any] | None = None
        self.expected_binding: dict[str, Any] | None = None
        self.ready = False
        self.revision = 0
        self.epoch = 0
        self.level: int | None = None
        self.step: int | None = None
        self.frame_id: str | None = None
        self.confirmation_scope: str | None = None
        self.confirmation_evidence: list[str] = []
        self.lease_remaining = 0
        self.pending: dict[str, Any] | None = None
        self.recent_frames: deque[str] = deque(maxlen=8)
        self.request_index = 0
        self._response_execution_guard = False
        self.last_status = "new_game"

    def _log(self, event: str, **data: Any) -> None:
        if self.path is None:
            return
        payload = {
            "version": 2,
            "time": time.time(),
            "event": event,
            "phase": self.mode,
            "epoch": self.epoch,
            "level": self.level,
            "step": self.step,
            **data,
        }
        try:
            log_path = self.path.with_name(self.path.stem + "_game_memory.jsonl")
            with log_path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(payload, ensure_ascii=True) + "\n")
        except (OSError, TypeError, ValueError):
            pass

    def bind(self, path: Path) -> None:
        path = path.resolve()
        if self.path == path:
            return
        enabled = self.execution_enabled
        if self.path is not None:
            self.leave("new_game")
        self.__init__(execution_enabled=enabled)
        self.path = path
        self._log("session", execution_enabled=self.execution_enabled)

    def _set_mode(self, mode: str, reason: str) -> None:
        previous = self.mode
        self.mode = mode
        self.last_status = reason
        if previous != mode:
            self._log("phase", previous=previous, next=mode, reason=reason)

    def leave(self, reason: str, *, audit: bool = False) -> None:
        self.lease_remaining = 0
        self._set_mode("confirm" if audit and self.expected_next else "investigate", reason)

    def _clear_confidence(self) -> None:
        self.confirmation_scope = None
        self.confirmation_evidence = []

    def invalidate(self, reason: str) -> None:
        """Return to full reasoning after an unreliable request/tool boundary."""
        self.ready = False
        self._clear_confidence()
        self.leave(reason)

    def boundary(self, reason: str) -> None:
        previous_epoch = self.epoch
        self.leave(reason)
        self.epoch += 1
        self.confirmed_rules = OrderedDict(
            (key, value) for key, value in self.confirmed_rules.items() if value["scope"] == "game"
        )
        self.uncertainties = OrderedDict(
            (key, value) for key, value in self.uncertainties.items() if value["scope"] == "game"
        )
        self.current_state = ""
        self.goal = ""
        # Transition mechanics may transfer, but the simulator's start state,
        # goal binding, and invariants are grounded to the old board.  Keep
        # cross-level mechanics in confirmed_rules and require a fresh spec.
        self.symbolic_model = None
        self.plan = []
        self.cursor = 0
        self.expected_next = None
        self.expected_binding = None
        self.ready = False
        self._clear_confidence()
        self.recent_frames.clear()
        if self.pending is not None:
            self.pending["boundary"] = reason
        self.revision += 1
        self._log("boundary", reason=reason, previous_epoch=previous_epoch)

    def observe(self, frame: Any) -> None:
        if frame is None:
            self.leave("missing_frame")
            return
        observed_level = _model_host_int(frame.level)
        observed_step = _model_host_int(frame.step)
        if self.level is not None and observed_level != self.level:
            self.boundary("level_changed")
        elif self.step is not None and (observed_step is None or observed_step < self.step):
            self.boundary("step_reset")
        self.level = observed_level
        self.step = observed_step
        self.frame_id = _frame_id(frame)

    def _status(self, *, accepted: bool, error: str | None = None) -> dict[str, Any]:
        return {
            "accepted": accepted,
            "error": error,
            "phase": self.mode,
            "ready": self.ready,
            "confirmations": len(self.confirmation_evidence),
            "confirmations_needed": max(0, self.required_confirmations - len(self.confirmation_evidence)),
            "cursor": self.cursor,
            "lease_remaining": self.lease_remaining,
            "revision": self.revision,
        }

    @staticmethod
    def _append_evidence(values: list[dict[str, Any]], evidence: dict[str, Any]) -> list[dict[str, Any]]:
        result = [dict(value) for value in values]
        if evidence.get("frame") and all(value.get("frame") != evidence["frame"] for value in result):
            result.append(dict(evidence))
        return result[-4:]

    def _rules(self, value: Any, frame: Any) -> OrderedDict[str, dict[str, Any]]:
        if not isinstance(value, list) or len(value) > MAX_RULES:
            raise ValueError(f"confirmed_rules must be a list with at most {MAX_RULES} entries")
        result: OrderedDict[str, dict[str, Any]] = OrderedDict()
        evidence = _observation(frame)
        for raw in value:
            if not isinstance(raw, dict) or not set(raw) <= {"id", "rule", "scope", "evidence_note"}:
                raise ValueError("invalid confirmed rule fields")
            key = _identifier(raw.get("id"), "confirmed rule id")
            if key in result:
                raise ValueError("duplicate confirmed rule id")
            rule = _text(raw.get("rule"), MAX_RULE_CHARS, "confirmed rule")
            scope = raw.get("scope", "game")
            if scope not in {"game", "level"}:
                raise ValueError("confirmed rule scope must be game or level")
            note = _text(raw.get("evidence_note", ""), MAX_NOTE_CHARS, "evidence_note", empty=True)
            old = self.confirmed_rules.get(key)
            old_evidence = old["evidence"] if old and old["rule"] == rule and old["scope"] == scope else []
            result[key] = {
                "id": key,
                "rule": rule,
                "scope": scope,
                "evidence_note": note,
                "evidence": self._append_evidence(old_evidence, evidence),
            }
        return result

    def _questions(self, value: Any, frame: Any) -> OrderedDict[str, dict[str, Any]]:
        if not isinstance(value, list) or len(value) > MAX_UNCERTAINTIES:
            raise ValueError(f"uncertainties must be a list with at most {MAX_UNCERTAINTIES} entries")
        result: OrderedDict[str, dict[str, Any]] = OrderedDict()
        evidence = _observation(frame)
        for raw in value:
            allowed = {"id", "hypothesis", "next_test", "scope", "evidence_note"}
            if not isinstance(raw, dict) or not set(raw) <= allowed:
                raise ValueError("invalid uncertainty fields")
            key = _identifier(raw.get("id"), "uncertainty id")
            if key in result:
                raise ValueError("duplicate uncertainty id")
            hypothesis = _text(raw.get("hypothesis"), MAX_RULE_CHARS, "uncertainty hypothesis")
            next_test = _text(raw.get("next_test", ""), MAX_NOTE_CHARS, "next_test", empty=True)
            scope = raw.get("scope", "level")
            if scope not in {"game", "level"}:
                raise ValueError("uncertainty scope must be game or level")
            note = _text(raw.get("evidence_note", ""), MAX_NOTE_CHARS, "evidence_note", empty=True)
            old = self.uncertainties.get(key)
            old_evidence = old["evidence"] if old and old["hypothesis"] == hypothesis and old["scope"] == scope else []
            result[key] = {
                "id": key,
                "hypothesis": hypothesis,
                "next_test": next_test,
                "scope": scope,
                "evidence_note": note,
                "evidence": self._append_evidence(old_evidence, evidence),
            }
        return result

    def _checks(self, value: Any, frame: Any) -> dict[str, Any]:
        if value is None:
            return {}
        allowed = {"level", "reward", "board", "min_changed_cells", "max_changed_cells", "cells"}
        if not isinstance(value, dict) or not set(value) <= allowed:
            raise ValueError("invalid expected_next checks")
        result: dict[str, Any] = {}
        for key, choices in {
            "level": {"same", "advance", "any"},
            "reward": {"zero", "positive", "nonzero", "any"},
            "board": {"same", "changed", "any"},
        }.items():
            if key in value:
                if value[key] not in choices:
                    raise ValueError(f"invalid {key} expectation")
                result[key] = value[key]
        for key in ("min_changed_cells", "max_changed_cells"):
            if key in value:
                if type(value[key]) is not int or not 0 <= value[key] <= 4096:
                    raise ValueError(f"{key} must be an integer in 0..4096")
                result[key] = value[key]
        if "min_changed_cells" in result and "max_changed_cells" in result:
            if result["min_changed_cells"] > result["max_changed_cells"]:
                raise ValueError("min_changed_cells exceeds max_changed_cells")
        if "cells" in value:
            cells = value["cells"]
            if not isinstance(cells, list) or not 1 <= len(cells) <= MAX_CHECK_CELLS:
                raise ValueError(f"cells needs 1..{MAX_CHECK_CELLS} [row,col,color] entries")
            parsed = []
            seen = set()
            for cell in cells:
                if not isinstance(cell, list) or len(cell) != 3 or any(type(x) is not int for x in cell):
                    raise ValueError("expected cells must be [row,col,color] integers")
                row, col, color = cell
                if frame is None or not (0 <= row < len(frame.grid) and 0 <= col < len(frame.grid[row])):
                    raise ValueError("expected cell is outside the current frame")
                if not 0 <= color < 16 or (row, col) in seen:
                    raise ValueError("invalid or duplicate expected cell")
                seen.add((row, col))
                parsed.append([row, col, color])
            result["cells"] = parsed
        return result

    def _expectation(self, value: Any, frame: Any) -> dict[str, Any] | None:
        if value is None:
            return None
        if not isinstance(value, dict) or not set(value) <= {"summary", "checks"}:
            raise ValueError("expected_next accepts only summary and checks")
        summary = _text(value.get("summary", ""), MAX_EXPECTATION_CHARS, "expected_next summary", empty=True)
        checks = self._checks(value.get("checks", {}), frame)
        if not summary and not checks:
            raise ValueError("expected_next needs a summary or check")
        return {"summary": summary, "checks": checks}

    def _plan(self, value: Any, frame: Any) -> list[dict[str, Any]]:
        if not isinstance(value, list) or len(value) > MAX_PLAN_STEPS:
            raise ValueError(f"plan must be a list with at most {MAX_PLAN_STEPS} steps")
        result = []
        for raw in value:
            if isinstance(raw, str):
                raw = {"action": raw}
            if not isinstance(raw, dict) or not set(raw) <= {"action", "why", "expect"}:
                raise ValueError("invalid plan step fields")
            step = {"action": _action(raw.get("action"))}
            if "why" in raw:
                step["why"] = _text(raw["why"], MAX_PLAN_NOTE_CHARS, "plan why", empty=True)
            if "expect" in raw:
                step["expect"] = self._expectation(raw["expect"], frame)
            result.append(step)
        return result

    @staticmethod
    def _informative(expectation: dict[str, Any] | None) -> bool:
        if not expectation:
            return False
        checks = expectation.get("checks") or {}
        if checks.get("cells") or "min_changed_cells" in checks or "max_changed_cells" in checks:
            return True
        if checks.get("board") in {"same", "changed"}:
            return True
        if checks.get("level") == "advance":
            return True
        return checks.get("reward") in {"positive", "nonzero"}

    def _scope(self) -> str:
        return _digest({
            "epoch": self.epoch,
            "goal": self.goal,
            "rules": [(key, entry["rule"]) for key, entry in self.confirmed_rules.items()],
            "plan": [step["action"] for step in self.plan],
            "symbolic_model": _digest(self.symbolic_model) if self.symbolic_model else None,
        })

    def _eligible(self) -> bool:
        return (
            self.execution_enabled
            and self.ready
            and bool(self.goal)
            and self.cursor < len(self.plan)
            and self._informative(self.expected_next)
            and len(self.confirmation_evidence) >= self.required_confirmations
        )

    def _enter_if_eligible(self) -> None:
        if not self._eligible():
            return
        self.lease_remaining = self.lease_actions
        self.recent_frames.clear()
        if self.frame_id:
            self.recent_frames.append(self.frame_id)
        self._set_mode("execute", "evidence_gate_passed")
        self._log("entry", cursor=self.cursor, lease=self.lease_remaining)

    def remember(self, updates: Any, frame: Any) -> dict[str, Any]:
        """Atomically apply a model patch. Rejections are deliberately fail-open."""
        try:
            self.observe(frame)
            if not isinstance(updates, dict):
                raise ValueError("remember updates must be an object")
            allowed = {
                "confirmed_rules", "uncertainties", "current_state", "goal",
                "symbolic_model", "plan", "expected_next", "ready",
            }
            unknown = set(updates) - allowed
            if unknown:
                raise ValueError("unknown remember fields: " + ", ".join(sorted(unknown)))

            rules = self.confirmed_rules
            questions = self.uncertainties
            current_state = self.current_state
            goal = self.goal
            symbolic_model = self.symbolic_model
            plan = self.plan
            cursor = self.cursor
            expected = self.expected_next
            ready = self.ready

            if "confirmed_rules" in updates:
                rules = (
                    OrderedDict()
                    if updates["confirmed_rules"] is None
                    else self._rules(updates["confirmed_rules"], frame)
                )
            if "uncertainties" in updates:
                questions = (
                    OrderedDict()
                    if updates["uncertainties"] is None
                    else self._questions(updates["uncertainties"], frame)
                )
            overlap = set(rules) & set(questions)
            if overlap:
                raise ValueError("ids cannot be both confirmed and uncertain: " + ", ".join(sorted(overlap)))
            if "current_state" in updates:
                raw = updates["current_state"]
                current_state = "" if raw is None else _text(raw, MAX_STATE_CHARS, "current_state", empty=True)
            if "goal" in updates:
                raw = updates["goal"]
                goal = "" if raw is None else _text(raw, MAX_GOAL_CHARS, "goal", empty=True)
            if "symbolic_model" in updates:
                symbolic_model = (
                    None if updates["symbolic_model"] is None
                    else normalize_spec(updates["symbolic_model"])
                )
                if symbolic_model is not None:
                    encoded = json.dumps(symbolic_model, separators=(",", ":"), ensure_ascii=True).encode()
                    if len(encoded) > MAX_SYMBOLIC_MODEL_BYTES:
                        raise ValueError(
                            f"symbolic_model exceeds {MAX_SYMBOLIC_MODEL_BYTES} canonical bytes"
                        )
            plan_changed = False
            if "plan" in updates:
                plan = [] if updates["plan"] is None else self._plan(updates["plan"], frame)
                cursor = 0
                plan_changed = plan != self.plan
            expectation_changed = False
            if "expected_next" in updates:
                expected = self._expectation(updates["expected_next"], frame)
                expectation_changed = expected != self.expected_next
            elif plan_changed:
                expected = plan[0].get("expect") if plan else None
            if "ready" in updates:
                if type(updates["ready"]) is not bool:
                    raise ValueError("ready must be true or false")
                ready = updates["ready"]

            old_scope = self._scope()
            self.confirmed_rules = OrderedDict((key, dict(item)) for key, item in rules.items())
            self.uncertainties = OrderedDict((key, dict(item)) for key, item in questions.items())
            self.current_state = current_state
            self.goal = goal
            symbolic_changed = symbolic_model != self.symbolic_model
            self.symbolic_model = json.loads(json.dumps(symbolic_model)) if symbolic_model else None
            self.plan = [dict(step) for step in plan]
            self.cursor = min(cursor, len(self.plan))
            self.expected_next = dict(expected) if expected else None
            self.expected_binding = _observation(frame) if self.expected_next else None
            self.ready = ready
            self.revision += 1
            new_scope = self._scope()
            if plan_changed or expectation_changed or symbolic_changed or new_scope != old_scope:
                self._clear_confidence()
                self.confirmation_scope = new_scope

            if self.pending is not None:
                self.pending["remembered"] = True
            if self._response_execution_guard:
                if self.pending is not None:
                    self.pending["withdrawn"] = True
                self.ready = False
                self.leave("model_requested_replan")
            elif not self.ready:
                self.leave("memory_updated")
            elif self._informative(self.expected_next):
                self._set_mode("confirm", "awaiting_evidence")
                self._enter_if_eligible()
            else:
                self.leave("memory_updated_without_checkable_expectation")
            self._log("memory_update", accepted=True, fields=sorted(updates), revision=self.revision)
            return self._status(accepted=True)
        except (KeyError, TypeError, ValueError) as exc:
            self.last_status = "memory_update_rejected"
            self._log("memory_update", accepted=False, error=str(exc)[:240])
            return self._status(accepted=False, error=str(exc)[:240])

    def _render_plan(self) -> list[dict[str, Any]]:
        result = []
        for step in self.plan:
            item = {"action": step["action"]}
            if step.get("why"):
                item["why"] = step["why"]
            result.append(item)
        return result

    def _symbolic_summary(self) -> dict[str, Any] | None:
        if self.symbolic_model is None:
            return None
        validation = validate_observations(self.symbolic_model)
        return {
            "name": self.symbolic_model["name"],
            "scope": self.symbolic_model["scope"],
            "digest": _digest(self.symbolic_model),
            "variables": list(self.symbolic_model["start"]),
            "actions": [action["id"] for action in self.symbolic_model["actions"]],
            "observations_validated": validation["validated"],
            "observations_total": validation["total"],
            "consistent": validation["ok"],
        }

    def checkpoint(self) -> str:
        # Keep the action skeleton and the active step's rationale. Per-step
        # expectations live in host memory and ``expected_next`` is canonical.
        plan = []
        for index, step in enumerate(self.plan):
            item = {"action": step["action"]}
            if index == self.cursor and step.get("why"):
                item["why"] = step["why"]
            plan.append(item)

        cursor = _model_host_int(self.cursor)
        confirmations = _model_host_int(len(self.confirmation_evidence))
        confirmations_needed = _model_host_int(
            max(0, self.required_confirmations - len(self.confirmation_evidence))
        )
        host = {
            "phase": self.mode if self.mode in {"investigate", "confirm", "execute"} else "investigate",
            "ready": self.ready if type(self.ready) is bool else False,
            "confirmations": confirmations,
            "confirmations_needed": confirmations_needed,
            "lease_remaining": _model_host_int(self.lease_remaining),
            "revision": _model_host_int(self.revision),
            "epoch": _model_host_int(self.epoch),
            "level": _model_host_int(self.level),
            "step": _model_host_int(self.step),
            "frame": self.frame_id if isinstance(self.frame_id, str) and re.fullmatch(r"[0-9a-f]{16}", self.frame_id) else None,
            "status": (
                self.last_status
                if isinstance(self.last_status, str)
                and len(self.last_status) <= 64
                and not any(0xD800 <= ord(char) <= 0xDFFF for char in self.last_status)
                else "host_state_sanitized"
            ),
        }
        value: dict[str, Any] = {
            "confirmed_rules": [],
            "uncertainties": [],
            "current_state": self.current_state,
            "goal": self.goal,
            "symbolic_model": self._symbolic_summary(),
            "plan": plan,
            "cursor": cursor,
            "expected_next": self.expected_next,
            "host": host,
        }

        def render(candidate: dict[str, Any]) -> str:
            return json.dumps(candidate, separators=(",", ":"), ensure_ascii=False)

        def fits(candidate: dict[str, Any]) -> bool:
            return len(CHECKPOINT_PREFIX) + len(render(candidate)) <= MAX_CHECKPOINT_CHARS

        # Lists are model-ordered full replacements. Retain their tail first so
        # newly discovered/high-priority entries survive deterministic pruning.
        rules = [
            {
                "id": key,
                "rule": entry["rule"],
                "scope": entry["scope"],
                "support": _model_host_int(len(entry["evidence"])),
            }
            for key, entry in self.confirmed_rules.items()
        ]
        questions = [
            {
                "id": key,
                "hypothesis": entry["hypothesis"],
                "next_test": entry["next_test"],
                "scope": entry["scope"],
            }
            for key, entry in self.uncertainties.items()
        ]
        rule_index = len(rules) - 1
        question_index = len(questions) - 1
        while rule_index >= 0 or question_index >= 0:
            if rule_index >= 0:
                candidate = dict(value)
                candidate["confirmed_rules"] = [rules[rule_index], *value["confirmed_rules"]]
                if fits(candidate):
                    value = candidate
                rule_index -= 1
            if question_index >= 0:
                candidate = dict(value)
                candidate["uncertainties"] = [questions[question_index], *value["uncertainties"]]
                if fits(candidate):
                    value = candidate
                question_index -= 1

        rendered = render(value)
        if len(CHECKPOINT_PREFIX) + len(rendered) > MAX_CHECKPOINT_CHARS:
            # Accepted internal state must never make inference fail. This
            # fallback retains every control-critical field, but shortens their
            # model-facing descriptions and shows only the active plan action.
            checks = dict((self.expected_next or {}).get("checks") or {})
            if "cells" in checks:
                checks["cells"] = checks["cells"][:2]
            active_plan = plan[self.cursor:self.cursor + 1] if self.cursor < len(plan) else []
            value = {
                "confirmed_rules": [],
                "uncertainties": [],
                "current_state": self.current_state[:128],
                "goal": self.goal[:128],
                "symbolic_model": self._symbolic_summary(),
                "plan": active_plan,
                "cursor": cursor,
                "expected_next": (
                    {
                        "summary": str((self.expected_next or {}).get("summary", ""))[:96],
                        "checks": checks,
                    }
                    if self.expected_next
                    else None
                ),
                "host": value["host"],
            }
            rendered = render(value)
        if len(CHECKPOINT_PREFIX) + len(rendered) > MAX_CHECKPOINT_CHARS:
            value = {
                "confirmed_rules": [],
                "uncertainties": [],
                "current_state": self.current_state[:64],
                "goal": self.goal[:64],
                "symbolic_model": self._symbolic_summary(),
                "plan": active_plan,
                "cursor": cursor,
                "expected_next": (
                    {
                        "summary": str((self.expected_next or {}).get("summary", ""))[:64],
                        "checks": {
                            key: checks[key]
                            for key in ("level", "reward", "board", "min_changed_cells", "max_changed_cells")
                            if key in checks
                        },
                    }
                    if self.expected_next
                    else None
                ),
                "host": {
                    key: value["host"][key]
                    for key in ("phase", "ready", "confirmations", "confirmations_needed", "lease_remaining", "epoch", "level", "step", "frame")
                },
            }
            rendered = render(value)
        if len(CHECKPOINT_PREFIX) + len(rendered) > MAX_CHECKPOINT_CHARS:
            # A fixed-shape last resort makes the size contract total even if
            # future internal fields drift beyond the validated model schema.
            value = {
                "confirmed_rules": [],
                "uncertainties": [],
                "current_state": "",
                "goal": "",
                "symbolic_model": None,
                "plan": [],
                "cursor": cursor,
                "expected_next": None,
                "host": {
                    key: host[key]
                    for key in ("phase", "ready", "confirmations", "confirmations_needed", "lease_remaining", "epoch", "level", "step", "frame")
                },
            }
            rendered = render(value)
        result = CHECKPOINT_PREFIX + rendered
        if len(result) <= MAX_CHECKPOINT_CHARS:
            return result
        # This literal contains no data-dependent value and is therefore an
        # unconditional valid-JSON, UTF-8-safe size postcondition.
        return CHECKPOINT_PREFIX + (
            '{"confirmed_rules":[],"uncertainties":[],"current_state":"",'
            '"goal":"","plan":[],"cursor":null,"expected_next":null,'
            '"host":{"phase":"investigate","ready":false}}'
        )

    def extend_schema(self, tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
        tools[0]["function"]["description"] += " " + MEMORY_TOOL_DESCRIPTION
        return tools

    @staticmethod
    def _strip_checkpoint_content(content: Any) -> Any:
        if isinstance(content, str):
            if content.startswith(CHECKPOINT_PREFIX):
                return ""
            return content.split("\n\n" + CHECKPOINT_PREFIX, 1)[0]
        if isinstance(content, list):
            result = []
            for part in content:
                if not isinstance(part, dict) or part.get("type") != "text":
                    result.append(part)
                    continue
                text = str(part.get("text", ""))
                if text.startswith(CHECKPOINT_PREFIX):
                    continue
                cleaned = text.split("\n\n" + CHECKPOINT_PREFIX, 1)[0]
                if cleaned != text:
                    replacement = dict(part)
                    replacement["text"] = cleaned
                    result.append(replacement)
                else:
                    result.append(part)
            return result
        return content

    def strip_messages(self, messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Return history without host-injected or assistant-echoed checkpoints."""
        result = []
        for message in messages:
            role = message.get("role")
            if role not in {"user", "tool", "assistant"}:
                result.append(message)
                continue

            # The host only injects into content, but a model can echo the
            # checkpoint through any assistant text field accepted by our
            # OpenAI-compatible adapters. Tool arguments and results remain
            # untouched model/tool data.
            fields = ("content", "reasoning", "reasoning_content") if role == "assistant" else ("content",)
            replacement = message
            changed = False
            for field in fields:
                if field not in message:
                    continue
                original = message.get(field)
                cleaned = self._strip_checkpoint_content(original)
                if cleaned == original:
                    continue
                if not changed:
                    replacement = dict(message)
                    changed = True
                replacement[field] = cleaned
            if not changed:
                result.append(message)
                continue
            cleaned_content = replacement.get("content")
            if (
                role in {"user", "tool"}
                and (cleaned_content == "" or cleaned_content is None or cleaned_content == [])
                and set(message) <= {"role", "content"}
            ):
                continue
            result.append(replacement)
        return result

    def refresh_messages(self, messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Build a one-checkpoint request view without contaminating history."""
        result = self.strip_messages(messages)
        checkpoint = self.checkpoint()
        if not result or result[-1].get("role") not in {"user", "tool"}:
            return [*result, {"role": "user", "content": checkpoint}]
        latest = dict(result[-1])
        content = latest.get("content")
        if isinstance(content, str):
            latest["content"] = (content + "\n\n" if content else "") + checkpoint
        elif isinstance(content, list):
            latest["content"] = [*content, {"type": "text", "text": checkpoint}]
        else:
            return [*result, {"role": "user", "content": checkpoint}]
        result[-1] = latest
        return result

    def prepare(self, arguments: dict[str, Any], frame: Any) -> None:
        self.observe(frame)
        self.pending = {
            "epoch": self.epoch,
            "action_calls": 0,
            "action_context": None,
            "failure": None,
            "executed": False,
            "remembered": False,
            "withdrawn": False,
            "execution_guard": self.mode == "execute" or self._response_execution_guard,
        }
        self._log("tool_prepared", execution_guard=self.pending["execution_guard"])

    def _planned_action(self) -> dict[str, Any] | None:
        return self.plan[self.cursor]["action"] if self.cursor < len(self.plan) else None

    def before_action(self, actions: list[dict[str, Any]], frame: Any) -> None:
        normalized = _actions(actions)
        pending = self.pending
        if pending is None:
            if self.mode == "execute":
                self.leave("uncovered_action")
                raise ValueError("execution action is outside a prepared tool call")
            return
        pending["action_calls"] += 1
        guard = bool(pending["execution_guard"])
        planned = self._planned_action()
        binding_ok = self.expected_binding == _observation(frame)
        single = len(normalized) == 1 and pending["action_calls"] == 1
        action_ok = planned is None or (single and normalized[0] == planned)
        if guard:
            if pending["withdrawn"]:
                self.leave("replan_before_action")
                raise ValueError("resume investigation before another action")
            if not single or planned is None or not action_ok or not binding_ok or not self._informative(self.expected_next):
                pending["failure"] = "uncovered_execution_action"
                self.leave("uncovered_execution_action")
                raise ValueError("execution requires one stored, bound, checkable plan action")
        if single and action_ok and binding_ok and self.expected_next is not None:
            pending["action_context"] = {
                "before": frame,
                "actions": normalized,
                "expected": json.loads(json.dumps(self.expected_next)),
                "scope": self._scope(),
            }
        elif self.expected_next is not None:
            pending["failure"] = "expectation_not_bound" if not binding_ok else "expectation_action_mismatch"

    def _evaluate(self, context: dict[str, Any], result: dict[str, Any], frame: Any) -> tuple[str, list[str]]:
        before = context["before"]
        expected = context["expected"]
        checks = expected.get("checks") or {}
        if not self._informative(expected) or frame is None or not result.get("executed"):
            return "uncheckable", ["missing observable result"]
        failures = []
        level = checks.get("level")
        if level == "same" and frame.level != before.level:
            failures.append("level changed")
        elif level == "advance" and frame.level <= before.level:
            failures.append("level did not advance")
        reward = result.get("reward")
        reward_check = checks.get("reward")
        if reward_check != "any" and reward_check is not None and not isinstance(reward, (int, float)):
            return "uncheckable", ["reward unavailable"]
        if reward_check == "zero" and reward != 0:
            failures.append("reward was not zero")
        elif reward_check == "positive" and not reward > 0:
            failures.append("reward was not positive")
        elif reward_check == "nonzero" and reward == 0:
            failures.append("reward was zero")
        changed = _frame_id(before) != _frame_id(frame)
        if checks.get("board") == "same" and changed:
            failures.append("board changed")
        elif checks.get("board") == "changed" and not changed:
            failures.append("board did not change")
        diff_count = sum(
            1
            for row in range(min(len(before.grid), len(frame.grid)))
            for col in range(min(len(before.grid[row]), len(frame.grid[row])))
            if before.grid[row][col] != frame.grid[row][col]
        )
        if "min_changed_cells" in checks and diff_count < checks["min_changed_cells"]:
            failures.append("too few changed cells")
        if "max_changed_cells" in checks and diff_count > checks["max_changed_cells"]:
            failures.append("too many changed cells")
        for row, col, color in checks.get("cells", []):
            if row >= len(frame.grid) or col >= len(frame.grid[row]) or frame.grid[row][col] != color:
                failures.append(f"cell {row},{col} mismatch")
        return ("mismatch", failures) if failures else ("matched", [])

    def _advance(self, frame: Any) -> None:
        self.cursor += 1
        if self.cursor < len(self.plan):
            next_expect = self.plan[self.cursor].get("expect")
            self.expected_next = dict(next_expect) if next_expect else None
            self.expected_binding = _observation(frame) if self.expected_next else None
        else:
            self.expected_next = None
            self.expected_binding = None

    def after_action(self, result: dict[str, Any], frame: Any) -> None:
        pending = self.pending
        executed = bool(result.get("executed"))
        names = result.get("executed_actions") or [result.get("action_display") or ""]
        boundary_reason = None
        if executed and any(str(name).strip().upper() == "RESET" for name in names):
            boundary_reason = "reset"
        elif result.get("level_completed") or result.get("run_complete") or result.get("game_over") or result.get("done"):
            boundary_reason = "level_or_terminal"

        if pending is not None:
            pending["executed"] |= executed
            if result.get("error") or not executed:
                pending["failure"] = "action_error"
                if pending["execution_guard"]:
                    self.ready = False
                    self._clear_confidence()
                    self.leave("action_error")
            context = pending.get("action_context")
            if context is not None and executed:
                verdict, failures = self._evaluate(context, result, frame)
                evidence = _digest({
                    "before": _frame_id(context["before"]),
                    "actions": context["actions"],
                    "after": _frame_id(frame),
                })
                if verdict == "matched":
                    if self.confirmation_scope != context["scope"]:
                        self.confirmation_scope = context["scope"]
                        self.confirmation_evidence = []
                    if evidence not in self.confirmation_evidence:
                        self.confirmation_evidence.append(evidence)
                    was_execution = bool(pending["execution_guard"])
                    self._advance(frame)
                    self.last_status = "expectation_matched"
                    self._log(
                        "expectation", verdict=verdict, evidence=evidence,
                        confirmations=len(self.confirmation_evidence), cursor=self.cursor,
                    )
                    if was_execution:
                        self.lease_remaining = max(0, self.lease_remaining - 1)
                        if self.cursor >= len(self.plan):
                            self.ready = False
                            self.leave("plan_exhausted")
                        elif self.lease_remaining <= 0:
                            self.ready = False
                            self._clear_confidence()
                            self.leave("lease_expired", audit=True)
                        elif not self._informative(self.expected_next):
                            self.ready = False
                            self.leave("next_expectation_uncheckable")
                    elif self.cursor >= len(self.plan):
                        self.ready = False
                        self.leave("plan_exhausted")
                    else:
                        self._set_mode("confirm", "expectation_matched")
                        self._enter_if_eligible()
                else:
                    pending["failure"] = "expectation_" + verdict
                    self.ready = False
                    self._clear_confidence()
                    self.leave("expectation_" + verdict)
                    self._log("expectation", verdict=verdict, failures=failures[:8])
            elif executed and pending["execution_guard"]:
                pending["failure"] = pending.get("failure") or "expectation_uncheckable"
                self.ready = False
                self._clear_confidence()
                self.leave("expectation_uncheckable")

        if boundary_reason:
            self.boundary(boundary_reason)
            if frame is not None:
                self.level, self.step, self.frame_id = frame.level, frame.step, _frame_id(frame)
            return
        self.observe(frame)
        if executed and frame is not None and self.mode == "execute":
            identity = _frame_id(frame)
            if identity:
                self.recent_frames.append(identity)
                if self.recent_frames.count(identity) >= 3:
                    self.ready = False
                    self._clear_confidence()
                    self.leave("repeated_visible_state")

    def finish(self, *, error: str | None, step_executed: bool) -> None:
        pending, self.pending = self.pending, None
        if pending is None:
            return
        failure = error or pending.get("failure")
        if failure:
            self.invalidate("python_error" if error else str(failure))
            self._log("tool_failure", reason=str(failure)[:160])
        elif pending["execution_guard"] and not step_executed and not pending["withdrawn"]:
            self.invalidate("execute_no_action")
        self._log(
            "tool_finished", step_executed=step_executed,
            remembered=pending["remembered"], failure=str(failure)[:160] if failure else None,
        )

    def validate_response(self, tool_calls: Any, finish_reason: str) -> bool:
        if finish_reason in {"length", "content_filter", "error"} or not isinstance(tool_calls, list) or not tool_calls:
            self.invalidate("incomplete_or_no_tool_response")
            return False
        if self._response_execution_guard and len(tool_calls) != 1:
            self.invalidate("multiple_tools_in_execution_response")
            return False
        try:
            for call in tool_calls:
                function = call["function"]
                if function["name"] != "python":
                    raise ValueError("unknown tool")
                arguments = function["arguments"]
                arguments = json.loads(arguments) if isinstance(arguments, str) else arguments
                if not isinstance(arguments, dict) or not isinstance(arguments.get("code"), str) or not arguments["code"].strip():
                    raise ValueError("invalid Python arguments")
        except (KeyError, TypeError, ValueError):
            self.invalidate("malformed_tool_response")
            return False
        return True

    def invoke(self, callback: Any, messages: Any, **kwargs: Any) -> Any:
        request_mode = self.mode
        self._response_execution_guard = request_mode == "execute"
        self.request_index += 1
        index = self.request_index
        if request_mode == "execute":
            kwargs["thinking_override"] = False
        started = time.monotonic()
        self._log(
            "request", request=index, request_mode=request_mode,
            thinking_override=kwargs.get("thinking_override"),
        )
        try:
            result = callback(messages, **kwargs)
        except Exception as exc:
            self._log(
                "response", request=index, request_mode=request_mode,
                error=type(exc).__name__, elapsed=time.monotonic() - started,
            )
            self.invalidate("request_error")
            raise
        usage = result.usage if isinstance(result.usage, dict) else {}

        def count(*keys: str) -> int | None:
            for key in keys:
                if type(usage.get(key)) is int:
                    return max(0, usage[key])
            return None

        details = usage.get("completion_tokens_details") or usage.get("output_tokens_details") or {}
        reasoning = details.get("reasoning_tokens") if isinstance(details, dict) else None
        self._log(
            "response", request=index, request_mode=request_mode,
            elapsed=time.monotonic() - started, finish_reason=result.finish_reason,
            prompt_tokens=count("prompt_tokens", "input_tokens"),
            completion_tokens=count("completion_tokens", "output_tokens", "generated_tokens"),
            reasoning_tokens=reasoning if type(reasoning) is int else None,
            total_tokens=count("total_tokens"),
        )
        return result


def self_test() -> dict[str, Any]:
    from types import SimpleNamespace

    frame = SimpleNamespace(grid=((1, 0),), step=0, level=1)
    controller = ExecutionMode(execution_enabled=False)
    accepted = controller.remember(
        {
            "confirmed_rules": [{"id": "move", "rule": "RIGHT moves the token", "scope": "game"}],
            "uncertainties": [{"id": "goal", "hypothesis": "reach the edge", "next_test": "move right"}],
            "current_state": "token at the left",
            "goal": "reach the right edge",
            "plan": [{"action": "RIGHT"}],
            "expected_next": {"summary": "token moves", "checks": {"board": "changed"}},
        },
        frame,
    )
    assert accepted["accepted"] and controller.mode != "execute"
    assert len(controller.checkpoint()) <= MAX_CHECKPOINT_CHARS
    return {"status": "ok", "execution_enabled": controller.execution_enabled}
