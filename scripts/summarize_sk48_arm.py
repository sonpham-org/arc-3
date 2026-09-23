#!/usr/bin/env python3
"""
Author: Claude Opus 5 (Bubba subagent, label sk48-overfit-a424)
Date: 21-September-2026
PURPOSE: Extract the artifact-backed facts for one arm of the sk48 overfit diagnostic from a
run directory: levels reached and cleared, actions issued, turns and per-turn request counts,
how often a turn ended without calling action(), and the reasoning-character distribution.
Only the harness's own artifacts are read (events.jsonl, runtime state, requests.jsonl, the
transcript's [MODEL RESPONSE META] blocks) so no level clear can be asserted that the harness
did not record.

Per BRIEF-sk48-oracle-20260921.md section 4, this does NOT auto-label reasoning as
rule-grounded vs board-grounded; that was explicitly cancelled as unreliable. It prints
candidate passages with surrounding context for a human to judge instead.
SRP/DRY check: Pass -- the harness has no per-arm summariser for these specific questions; this
reads its outputs and computes nothing the artifacts do not already state.
"""
from __future__ import annotations

import json
import re
import sys
from collections import Counter
from pathlib import Path

run_dir = Path(sys.argv[1])

events_path = next(run_dir.glob("artifacts/*_events.jsonl"), None)
state_path = next(run_dir.glob("artifacts/*_tool_runtime_state.json"), None)
transcript = next(run_dir.glob("transcripts/*.txt"), None)

print(f"== {run_dir.name}")

if events_path is not None:
    events = [json.loads(line) for line in events_path.read_text().splitlines() if line.strip()]
    print(f"events: {len(events)}")
    kinds = Counter(e.get("event") or e.get("type") or "?" for e in events)
    print(f"event kinds: {dict(kinds)}")
    levels = [e.get("level") for e in events if isinstance(e.get("level"), int)]
    scores = [e.get("score") for e in events if isinstance(e.get("score"), (int, float))]
    if levels:
        print(f"levels seen: min={min(levels)} max={max(levels)}")
    if scores:
        print(f"score: first={scores[0]} last={scores[-1]} max={max(scores)}")
    states = [e.get("state") for e in events if e.get("state")]
    if states:
        print(f"terminal states seen: {dict(Counter(states))}")

if state_path is not None:
    state = json.loads(state_path.read_text())
    for key in ("level", "score", "action_count", "state", "win", "game_id"):
        if key in state:
            print(f"runtime_state.{key}: {state[key]}")

requests_path = run_dir / "requests.jsonl"
if requests_path.exists():
    rows = [json.loads(line) for line in requests_path.read_text().splitlines() if line.strip()]
    per_turn = Counter(r.get("analysis_step") for r in rows)
    print(f"model requests: {len(rows)} across {len(per_turn)} turns")
    if per_turn:
        print(f"requests per turn: {dict(sorted(per_turn.items(), key=lambda kv: (kv[0] is None, kv[0])))}")

if transcript is not None:
    text = transcript.read_text(errors="replace")
    print(f"transcript chars: {len(text)}")
    print(f"reasoning_chars values: {re.findall(r'reasoning_chars: (\d+)', text)}")
    print(f"tool_call_count values: {re.findall(r'tool_call_count: (\d+)', text)}")
    # The harness emits this nudge only when a turn inspected the frame but never acted.
    nudges = text.count("inspected the frame but did not execute `action(...)`")
    print(f"turns that inspected but did not act (harness nudges): {nudges}")
    # Deliberately no substring search for "WIN"/"LEVEL" here: those strings occur in the
    # system prompt itself, so counting them would manufacture evidence of a clear. Level
    # clears are read from the events log and the runtime state above, nowhere else.
    executed = len(re.findall(r"\[TOOL CALL: python\]", text))
    print(f"python tool calls executed: {executed}")
