"""Exact replay of a logged play in Daniel's notebook harness, for forks (RL plan 9i).

Son 2-Oct: "the context is not the same ... you should still branch them". A fork restarts one logged play at one
turn with the model's context exactly as it was, then lets the model go on several times. His notebook logs every
model call (requests.jsonl, save_request_logs=True): a "request" row with the exact messages sent (a json copy of the
very list passed to the model call, after his context trimming) and a "response" row with the server's usage and
finish reason. The reply itself is the last assistant message of the next request (true across trims: a reply is
always followed by its tool results in the next request). Rolling summaries, the one unlogged call, are off in his
notebook.

So replaying a play is: at every model call, check the harness rebuilt the same messages, then hand back the
recorded reply with its recorded usage (his trimmer calibrates on prompt_tokens and his turn yield counts
completion_tokens, so the usage must be the original's). The model's own tool outputs sometimes print clock readings
(elapsed_seconds and the like) that a replay cannot reproduce; those numbers are masked in the comparison, and the
first live request of a fork is sent with the exact logged messages, so the fork decides on the original context.

Pure Python (no harness imports): fork_driver.py uses it inside the notebook; tests run it on a logged play.
"""
from __future__ import annotations

import difflib
import json
import re
from pathlib import Path
from typing import Any

# clock readings the model's code can print: "elapsed_seconds': 48.39", "time_remaining_seconds": 7871.6, ...
CLOCK = re.compile(r"((?:elapsed|remaining|time_left|time_remaining|run_elapsed|suite_remaining|game_remaining)"
                   r"[_a-z]*['\"]?\s*[:=]\s*)-?\d+(?:\.\d+)?")


def load_sequence(path: Path | str) -> list[dict[str, Any]]:
    """Every model call of a play, in order: {step, idx, action, messages, usage, finish_reason, reply, failed}."""
    seq: list[dict[str, Any]] = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            if not line.strip():
                continue
            r = json.loads(line)
            ev = r.get("event")
            if ev == "request":
                seq.append({"step": int(r["analysis_step"]), "idx": int(r.get("request_index_within_turn") or 1),
                            "action": r.get("action"), "messages": r["messages"], "usage": None,
                            "finish_reason": None, "reply": None})
            elif ev == "response" and seq and seq[-1]["step"] == int(r["analysis_step"]) \
                    and seq[-1]["idx"] == int(r.get("request_index_within_turn") or 1):
                seq[-1]["usage"] = r.get("usage")
                seq[-1]["finish_reason"] = r.get("finish_reason") or ""
    for a, b in zip(seq, seq[1:]):
        if a["usage"] is not None:   # answered: its reply leads the tool results in the next request
            a["reply"] = next((m for m in reversed(b["messages"]) if m.get("role") == "assistant"), None)
    for r in seq:
        r["failed"] = r["usage"] is None and r["finish_reason"] is None
    return seq


def _text(messages: list[dict[str, Any]]) -> str:
    return json.dumps(messages, ensure_ascii=False, sort_keys=True)


def masked(messages: list[dict[str, Any]]) -> str:
    return CLOCK.sub(r"\1#", _text(messages))


def compare(sent: list[dict[str, Any]], logged: list[dict[str, Any]]) -> dict[str, Any]:
    """How the messages the harness rebuilt differ from the logged ones, message by message (prompts run to
    hundreds of KB, so never one big diff).
    exact: identical; clock: identical once clock readings are masked; near: same shape and at most 3 messages
    differ, each by under 1% of its characters (e.g. a printed set in another order); diverged: anything else (a
    different board, a different action, a different number of messages)."""
    if sent == logged:
        return {"verdict": "exact"}
    shape = [(m.get("role"), bool(m.get("tool_calls"))) for m in sent] == \
            [(m.get("role"), bool(m.get("tool_calls"))) for m in logged]
    diffs = []
    for i, (x, y) in enumerate(zip(sent, logged)):
        if x != y:
            mx, my = masked([x]), masked([y])
            if mx != my:
                diffs.append((i, mx, my))
    if shape and not diffs:
        return {"verdict": "clock"}
    detail: dict[str, Any] = {"sent_n": len(sent), "logged_n": len(logged), "messages_differing": len(diffs)}
    near = shape and len(diffs) <= 3
    for i, mx, my in diffs[:3]:
        ratio = difflib.SequenceMatcher(None, mx[:20000], my[:20000]).quick_ratio()
        near = near and ratio >= 0.99 and abs(len(mx) - len(my)) <= 0.01 * max(len(mx), len(my))
        k = next((j for j, (p, q) in enumerate(zip(mx, my)) if p != q), min(len(mx), len(my)))
        detail.setdefault("first", {"message": i, "ratio": round(ratio, 4), "sent": mx[max(0, k - 60):k + 120],
                                    "logged": my[max(0, k - 60):k + 120]})
    return {"verdict": "near" if near else "diverged", **detail}


def fork_points(seq: list[dict[str, Any]], levels: list[tuple[int, int]]) -> list[int]:
    """Analysis steps where each level starts in this play: the first step whose action count reached the level's
    first action. levels: [(level, first action number)] from the play's event log."""
    out = []
    for _level, first_action in levels:
        step = next((r["step"] for r in seq if r["idx"] == 1 and int(r["action"] or 0) >= first_action), None)
        if step is not None and step not in out:
            out.append(step)
    return out
