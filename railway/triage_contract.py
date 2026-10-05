"""Shared, evidence-bound contract for the offline judge and the review publication API.

Author: Codex
Date: 2026-10-05
Purpose: Validate cited trace diagnoses, enforce held-out fences, and derive stable routing
and identities. No model output is a training approval or an automatic reward.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

SHA = re.compile(r"^[0-9a-f]{64}$")
GAME = re.compile(r"^[a-z0-9]{4}$")
BUILD = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,99}$")
# Union of the review and SFT fences, plus published test-only copy/recolor identities.
# Environment settings may add exclusions, never subtract these safeguards.
FENCED = frozenset("lf52 tn36 re86 dc22 su15 vc33 ar25 sb26 tr87 tu93 as66 "
                   "vh33 ah25 sh26 rh86 sh15 th87 th93 ah66 az25 rz86 sz26 sz15 tz87 tz93 vz33 "
                   "aq25 rr86 sr26 sr15 tq87 tr93 vr33".split())
CATEGORIES = frozenset(("reference_conflict", "contradiction", "unsupported_certainty",
                        "repeated_experiment", "plan_action_mismatch", "missing_evidence"))
MAX_PACKET_BYTES = 100_000


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def fenced_game(game):
    code = str(game).split("-", 1)[0].lower()
    extra = set(re.split(r"[,\s]+", os.environ.get("ARC3_REVIEW_FENCED", "")))
    # The deployed API uses the constant fence; local authoring adds newly registered test games.
    folder = Path(__file__).resolve().parents[1] / "datasets" / "test-only-games"
    return code in FENCED or code in extra or (folder / code).is_dir()


def _text(value, name, limit=4000, empty=False):
    if not isinstance(value, str) or "\x00" in value or len(value) > limit or (not empty and not value.strip()):
        raise ValueError(f"invalid {name}")
    return value


def _integer(value, name, low=0, high=1_000_000):
    if isinstance(value, bool) or not isinstance(value, int) or not low <= value <= high:
        raise ValueError(f"invalid {name}")
    return value


def validate_packet(value):
    if not isinstance(value, dict) or len(canonical(value)) > MAX_PACKET_BYTES:
        raise ValueError("invalid or oversized evidence packet")
    game = value.get("game")
    if not isinstance(game, str) or not GAME.fullmatch(game) or fenced_game(game):
        raise ValueError("game is invalid or held out")
    build = value.get("build")
    if not isinstance(build, str) or not BUILD.fullmatch(build):
        raise ValueError("invalid build")
    out = {"game": game, "build": build,
           "level": _integer(value.get("level"), "level", 1, 1000),
           "path_id": _text(value.get("path_id"), "path_id", 240),
           "step": _integer(value.get("step"), "step")}
    for key in ("trace_sha256", "reference_sha256"):
        if not isinstance(value.get(key), str) or not SHA.fullmatch(value[key]):
            raise ValueError(f"invalid {key}")
        out[key] = value[key]
    if not isinstance(value.get("context_complete"), bool):
        raise ValueError("context_complete must be explicit")
    out["context_complete"] = value["context_complete"]
    ids = set()
    for key in ("evidence", "reference"):
        rows = value.get(key)
        if not isinstance(rows, list) or not 1 <= len(rows) <= 120:
            raise ValueError(f"{key} must contain 1..120 cited passages")
        out[key] = []
        for row in rows:
            if not isinstance(row, dict):
                raise ValueError(f"invalid {key} passage")
            rid = _text(row.get("id"), "passage id", 120)
            if rid in ids:
                raise ValueError("duplicate evidence reference")
            ids.add(rid)
            out[key].append({"id": rid, "text": _text(row.get("text"), "passage text", 40_000),
                             "kind": _text(row.get("kind"), "passage kind", 80)})
    for board in ("start", "before", "after"):
        if value.get(board) is None:
            continue
        rows = value[board]
        if not isinstance(rows, list) or len(rows) != 64 or any(
                not isinstance(r, str) or not re.fullmatch(r"[0-9a-fA-F]{64}", r) for r in rows):
            raise ValueError(f"invalid {board} board")
        out[board] = rows
    if value.get("notes_url"):
        url = _text(value["notes_url"], "notes_url", 1000)
        parsed = urlparse(url)
        if parsed.scheme not in ("https", "http") or not parsed.netloc or parsed.username or parsed.password:
            raise ValueError("unsafe notes_url")
        out["notes_url"] = url
    if value.get("omissions") is not None:
        omissions = value["omissions"]
        if not isinstance(omissions, list) or len(omissions) > 30:
            raise ValueError("invalid omissions")
        out["omissions"] = [_text(x, "omission", 1000) for x in omissions]
    return out


def _citation(value, sources, name, required):
    if value is None and not required:
        return None
    if not isinstance(value, dict) or value.get("ref") not in sources:
        raise ValueError(f"{name} must cite a supplied passage")
    quote = _text(value.get("quote"), f"{name} quote", 2000)
    if quote not in sources[value["ref"]]:
        raise ValueError(f"{name} quote is absent from its source")
    return {"ref": value["ref"], "quote": quote}


def validate_assessment(packet, value):
    packet = validate_packet(packet)
    if not isinstance(value, dict):
        raise ValueError("assessment must be an object")
    status = value.get("status")
    if status not in ("issue", "no_issue", "insufficient_context"):
        raise ValueError("invalid assessment status")
    if value.get("category") not in CATEGORIES:
        raise ValueError("invalid category")
    evidence = {r["id"]: r["text"] for r in packet["evidence"]}
    reference = {r["id"]: r["text"] for r in packet["reference"]}
    out = {"status": status, "category": value["category"]}
    for key in ("summary", "alternative", "human_question", "next_action"):
        out[key] = _text(value.get(key, ""), key, 2000, empty=key in ("human_question", "next_action"))
    for key in ("claim", "support"):
        out[key] = _citation(value.get(key), evidence, key, status == "issue")
    out["reference"] = _citation(value.get("reference"), reference, "reference", status == "issue")
    if value.get("solver_knew") not in ("yes", "no", "unknown"):
        raise ValueError("invalid solver_knew")
    out["solver_knew"] = value["solver_knew"]
    if value.get("impact") not in ("high", "medium", "low"):
        raise ValueError("invalid impact")
    out["impact"] = value["impact"]
    route = value.get("route")
    if route not in ("human", "assistant", "discard"):
        raise ValueError("invalid route")
    if status == "no_issue":
        route = "discard"
    elif status == "insufficient_context" or not packet["context_complete"] or value["category"] in (
            "reference_conflict", "missing_evidence"):
        route = "assistant"
    elif status == "issue" and (out["claim"]["quote"] == out["support"]["quote"] or
                               out["claim"]["ref"] == out["support"]["ref"] or
                               next(r["kind"] for r in packet["evidence"] if r["id"] == out["claim"]["ref"]) == "solver_system"):
        route = "assistant"
    if route == "human" and out["impact"] == "low":
        route = "discard"
    if route == "human" and (not out["human_question"].strip() or not out["next_action"].strip()):
        raise ValueError("human review needs a question and a next action")
    out["route"] = route
    return out


def make_item(packet, assessment, judge, *, created_at=None):
    packet = validate_packet(packet)
    assessment = validate_assessment(packet, assessment)
    if not isinstance(judge, dict):
        raise ValueError("judge must identify the model and prompt")
    judge = {k: _text(judge.get(k), k, 120) for k in ("model", "prompt_version")}
    identity = digest({"packet": packet, "judge": judge})
    # Conservative grouping: identical cited claim and reference, never semantic guesses.
    # Trace identity is omitted so repeat occurrences do not become repeat human homework.
    cluster = digest({"game": packet["game"], "build": packet["build"], "level": packet["level"],
                      "reference_sha256": packet["reference_sha256"], "judge": judge,
                      "category": assessment["category"],
                      "claim": (assessment["claim"] or {}).get("quote"),
                      "support": (assessment["support"] or {}).get("quote"),
                      "reference": (assessment["reference"] or {}).get("quote"),
                      # Never merge unrelated missing-evidence diagnoses just because both lack citations.
                      "uncited_context": None if assessment["claim"] else digest(packet["evidence"])})
    priority = {"high": 300, "medium": 200, "low": 100}[assessment["impact"]]
    if assessment["solver_knew"] == "yes":
        priority += 20
    item = {**{k: packet[k] for k in ("game", "build", "level", "path_id", "step", "trace_sha256", "reference_sha256")},
            "id": identity, "cluster_key": cluster, "judge": judge, "packet": packet,
            "assessment": assessment, "route": assessment["route"], "priority": priority,
            "created_at": created_at or datetime.now(timezone.utc).isoformat(), "training_approved": False}
    return item


def validate_item(value):
    if not isinstance(value, dict):
        raise ValueError("item must be an object")
    created = _text(value.get("created_at"), "created_at", 80)
    when = datetime.fromisoformat(created.replace("Z", "+00:00"))
    if when.tzinfo is None:
        raise ValueError("created_at needs a timezone")
    expected = make_item(value.get("packet"), value.get("assessment"), value.get("judge"), created_at=created)
    for key in expected:
        if key == "training_approved" and key not in value:
            continue
        if value.get(key) != expected[key]:
            raise ValueError(f"item {key} does not match its evidence and assessment")
    return expected
