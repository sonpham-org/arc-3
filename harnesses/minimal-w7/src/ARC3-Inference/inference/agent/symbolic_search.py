"""Bounded declarative state search for model-authored game hypotheses.

The language is intentionally small: scalar state variables, predicate guards,
and deterministic effects.  It is expressive enough for grids, switches,
inventory, counters, and short patrol phases without executing model-authored
host code.  Search is advisory; the game-action controller remains responsible
for checking every real transition before entering cheap execution mode.
"""
from __future__ import annotations

import heapq
import json
import re
from typing import Any


MAX_VARIABLES = 24
MAX_ACTIONS = 24
MAX_PREDICATES = 48
MAX_EFFECTS = 24
MAX_OBSERVATIONS = 128
MAX_NODES = 20_000
MAX_DEPTH = 64
_NAME = re.compile(r"^[A-Za-z][A-Za-z0-9_-]{0,31}$")
_SCALAR_TYPES = (str, int, bool)


class SymbolicModelError(ValueError):
    """The declarative model is malformed or exceeds a safety bound."""


def _scalar(value: Any, label: str) -> str | int | bool:
    if type(value) not in _SCALAR_TYPES:
        raise SymbolicModelError(f"{label} must be a string, integer, or boolean")
    if isinstance(value, str) and (len(value) > 80 or any(ord(c) < 32 for c in value)):
        raise SymbolicModelError(f"{label} string must be one line of at most 80 characters")
    if type(value) is int and not -1_000_000 <= value <= 1_000_000:
        raise SymbolicModelError(f"{label} integer is outside -1000000..1000000")
    return value


def _name(value: Any, label: str) -> str:
    if not isinstance(value, str) or not _NAME.fullmatch(value):
        raise SymbolicModelError(f"{label} must match {_NAME.pattern}")
    return value


def _state(value: Any, label: str) -> dict[str, str | int | bool]:
    if not isinstance(value, dict) or len(value) > MAX_VARIABLES:
        raise SymbolicModelError(f"{label} must be an object with at most {MAX_VARIABLES} variables")
    result: dict[str, str | int | bool] = {}
    for raw_key, raw_value in value.items():
        key = _name(raw_key, f"{label} variable")
        result[key] = _scalar(raw_value, f"{label}.{key}")
    return result


def _predicates(value: Any, variables: set[str], label: str) -> list[dict[str, Any]]:
    if value is None:
        return []
    if not isinstance(value, list) or len(value) > MAX_PREDICATES:
        raise SymbolicModelError(f"{label} must be a list with at most {MAX_PREDICATES} predicates")
    result = []
    for raw in value:
        if not isinstance(raw, dict) or set(raw) != {"var", "op", "value"}:
            raise SymbolicModelError(f"each {label} predicate needs var, op, and value")
        var = _name(raw["var"], f"{label} variable")
        if var not in variables:
            raise SymbolicModelError(f"{label} references unknown variable {var}")
        op = raw["op"]
        if op not in {"eq", "ne", "lt", "le", "gt", "ge", "in", "not_in"}:
            raise SymbolicModelError(f"unsupported predicate operator {op}")
        if op in {"in", "not_in"}:
            if not isinstance(raw["value"], list) or not 1 <= len(raw["value"]) <= 32:
                raise SymbolicModelError(f"{label} {op} value must be a non-empty list")
            parsed_value: Any = [_scalar(item, f"{label} membership value") for item in raw["value"]]
        else:
            parsed_value = _scalar(raw["value"], f"{label} comparison value")
        result.append({"var": var, "op": op, "value": parsed_value})
    return result


def _emit(value: Any) -> dict[str, Any]:
    if isinstance(value, str):
        value = {"action": value}
    if not isinstance(value, dict) or not isinstance(value.get("action"), str):
        raise SymbolicModelError("action emit must be an action string or object")
    allowed = {"action", "row", "col"}
    if not set(value) <= allowed:
        raise SymbolicModelError("action emit contains unknown fields")
    result = {"action": value["action"].strip().upper()}
    if not result["action"]:
        raise SymbolicModelError("action emit name is empty")
    for key in ("row", "col"):
        if key in value:
            if type(value[key]) is not int or not 0 <= value[key] < 64:
                raise SymbolicModelError(f"action emit {key} must be an integer in 0..63")
            result[key] = value[key]
    return result


def _effects(value: Any, variables: set[str]) -> list[dict[str, Any]]:
    if not isinstance(value, list) or not value or len(value) > MAX_EFFECTS:
        raise SymbolicModelError(f"effects must contain 1..{MAX_EFFECTS} entries")
    result = []
    for raw in value:
        if not isinstance(raw, dict) or set(raw) != {"var", "op", "value"}:
            raise SymbolicModelError("each effect needs var, op, and value")
        var = _name(raw["var"], "effect variable")
        if var not in variables:
            raise SymbolicModelError(f"effect references unknown variable {var}")
        op = raw["op"]
        if op not in {"set", "add", "sub", "toggle", "copy"}:
            raise SymbolicModelError(f"unsupported effect operator {op}")
        if op == "copy":
            parsed_value: Any = _name(raw["value"], "copy source")
            if parsed_value not in variables:
                raise SymbolicModelError(f"copy references unknown variable {parsed_value}")
        elif op == "toggle":
            if raw["value"] is not True:
                raise SymbolicModelError("toggle effect value must be true")
            parsed_value = True
        else:
            parsed_value = _scalar(raw["value"], "effect value")
            if op in {"add", "sub"} and type(parsed_value) is not int:
                raise SymbolicModelError(f"{op} effect value must be an integer")
        result.append({"var": var, "op": op, "value": parsed_value})
    return result


def normalize_spec(value: Any) -> dict[str, Any]:
    """Validate and return a canonical JSON-safe simulator specification."""
    if not isinstance(value, dict):
        raise SymbolicModelError("symbolic model must be an object")
    allowed = {"name", "scope", "start", "goal", "invariants", "actions", "observations"}
    unknown = set(value) - allowed
    if unknown:
        raise SymbolicModelError("unknown symbolic model fields: " + ", ".join(sorted(unknown)))
    name = _name(value.get("name", "model"), "symbolic model name")
    scope = value.get("scope", "level")
    if scope not in {"game", "level"}:
        raise SymbolicModelError("symbolic model scope must be game or level")
    start = _state(value.get("start"), "start")
    variables = set(start)
    goal = _predicates(value.get("goal"), variables, "goal")
    if not goal:
        raise SymbolicModelError("goal must contain at least one predicate")
    invariants = _predicates(value.get("invariants", []), variables, "invariants")
    raw_actions = value.get("actions")
    if not isinstance(raw_actions, list) or not 1 <= len(raw_actions) <= MAX_ACTIONS:
        raise SymbolicModelError(f"actions must contain 1..{MAX_ACTIONS} rules")
    actions = []
    seen = set()
    for raw in raw_actions:
        allowed_action = {"id", "emit", "when", "effects", "cost"}
        if not isinstance(raw, dict) or not set(raw) <= allowed_action:
            raise SymbolicModelError("invalid symbolic action fields")
        action_id = _name(raw.get("id"), "symbolic action id")
        if action_id in seen:
            raise SymbolicModelError(f"duplicate symbolic action id {action_id}")
        seen.add(action_id)
        cost = raw.get("cost", 1)
        if type(cost) is not int or not 1 <= cost <= 100:
            raise SymbolicModelError("symbolic action cost must be an integer in 1..100")
        actions.append({
            "id": action_id,
            "emit": _emit(raw.get("emit", action_id)),
            "when": _predicates(raw.get("when", []), variables, f"action {action_id} guard"),
            "effects": _effects(raw.get("effects"), variables),
            "cost": cost,
        })
    observations = []
    raw_observations = value.get("observations", [])
    if not isinstance(raw_observations, list) or len(raw_observations) > MAX_OBSERVATIONS:
        raise SymbolicModelError(f"observations must contain at most {MAX_OBSERVATIONS} entries")
    for raw in raw_observations:
        if not isinstance(raw, dict) or set(raw) != {"before", "action", "after"}:
            raise SymbolicModelError("each observation needs before, action, and after")
        action_id = _name(raw["action"], "observation action")
        if action_id not in seen:
            raise SymbolicModelError(f"observation references unknown action {action_id}")
        before = _state(raw["before"], "observation before")
        after = _state(raw["after"], "observation after")
        if set(before) != variables or set(after) != variables:
            raise SymbolicModelError("observation states must contain exactly the start variables")
        observations.append({"before": before, "action": action_id, "after": after})
    return {
        "name": name,
        "scope": scope,
        "start": start,
        "goal": goal,
        "invariants": invariants,
        "actions": actions,
        "observations": observations,
    }


def _matches(state: dict[str, Any], predicates: list[dict[str, Any]]) -> bool:
    for predicate in predicates:
        left = state[predicate["var"]]
        right = predicate["value"]
        op = predicate["op"]
        try:
            ok = {
                "eq": lambda: left == right,
                "ne": lambda: left != right,
                "lt": lambda: left < right,
                "le": lambda: left <= right,
                "gt": lambda: left > right,
                "ge": lambda: left >= right,
                "in": lambda: left in right,
                "not_in": lambda: left not in right,
            }[op]()
        except TypeError:
            return False
        if not ok:
            return False
    return True


def _apply(state: dict[str, Any], action: dict[str, Any]) -> dict[str, Any] | None:
    if not _matches(state, action["when"]):
        return None
    result = dict(state)
    original = dict(state)
    for effect in action["effects"]:
        var, op, value = effect["var"], effect["op"], effect["value"]
        if op == "set":
            result[var] = value
        elif op == "copy":
            result[var] = original[value]
        elif op == "toggle":
            if type(result[var]) is not bool:
                return None
            result[var] = not result[var]
        else:
            if type(result[var]) is not int:
                return None
            result[var] = result[var] + value if op == "add" else result[var] - value
        if type(result[var]) is not type(original[var]):
            return None
        try:
            result[var] = _scalar(result[var], f"derived state {var}")
        except SymbolicModelError:
            return None
    return result


def _key(state: dict[str, Any]) -> str:
    return json.dumps(state, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def validate_observations(spec: dict[str, Any]) -> dict[str, Any]:
    actions = {action["id"]: action for action in spec["actions"]}
    mismatches = []
    for index, observation in enumerate(spec["observations"]):
        predicted = _apply(observation["before"], actions[observation["action"]])
        if predicted != observation["after"]:
            mismatches.append({
                "index": index,
                "action": observation["action"],
                "predicted": predicted,
                "observed": observation["after"],
            })
    return {
        "ok": not mismatches,
        "validated": len(spec["observations"]) - len(mismatches),
        "total": len(spec["observations"]),
        "mismatches": mismatches[:8],
    }


def search_symbolic_model(
    value: Any,
    *,
    max_nodes: int = 5_000,
    max_depth: int = 32,
    min_observations: int = 1,
) -> dict[str, Any]:
    """Validate observations and perform bounded deterministic uniform-cost search."""
    spec = normalize_spec(value)
    max_nodes = min(MAX_NODES, max(1, int(max_nodes)))
    max_depth = min(MAX_DEPTH, max(0, int(max_depth)))
    min_observations = min(MAX_OBSERVATIONS, max(0, int(min_observations)))
    validation = validate_observations(spec)
    if not validation["ok"] or validation["validated"] < min_observations:
        return {
            "ok": False,
            "status": "model_not_validated",
            "model": spec["name"],
            "validation": validation,
            "required_observations": min_observations,
        }
    if not _matches(spec["start"], spec["invariants"]):
        return {"ok": False, "status": "invalid_start", "model": spec["name"], "validation": validation}
    actions = spec["actions"]
    start = spec["start"]
    start_key = _key(start)
    frontier: list[tuple[int, int, str, list[str], list[dict[str, Any]]]] = [
        (0, 0, start_key, [], [start])
    ]
    best = {start_key: 0}
    expanded = 0
    while frontier and expanded < max_nodes:
        cost, depth, state_key, path, states = heapq.heappop(frontier)
        if cost != best.get(state_key):
            continue
        state = states[-1]
        expanded += 1
        if _matches(state, spec["goal"]):
            by_id = {action["id"]: action for action in actions}
            return {
                "ok": True,
                "status": "solved",
                "model": spec["name"],
                "model_scope": spec["scope"],
                "validation": validation,
                "cost": cost,
                "depth": depth,
                "expanded": expanded,
                "rule_ids": path,
                "actions": [by_id[action_id]["emit"] for action_id in path],
                "states": states,
            }
        if depth >= max_depth:
            continue
        for action in actions:
            next_state = _apply(state, action)
            if next_state is None or not _matches(next_state, spec["invariants"]):
                continue
            next_key = _key(next_state)
            next_cost = cost + action["cost"]
            if next_cost >= best.get(next_key, 1 << 60):
                continue
            best[next_key] = next_cost
            heapq.heappush(
                frontier,
                (next_cost, depth + 1, next_key, [*path, action["id"]], [*states, next_state]),
            )
    return {
        "ok": False,
        "status": "budget_exhausted" if frontier else "no_plan",
        "model": spec["name"],
        "validation": validation,
        "expanded": expanded,
        "max_nodes": max_nodes,
        "max_depth": max_depth,
    }
