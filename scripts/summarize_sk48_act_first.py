#!/usr/bin/env python3
"""
Author: Claude Opus 5 (Bubba subagent)
Date: 21-September-2026
PURPOSE: Read one sk48 act-first run dir and report, per environment action, what the model
actually did: the action(...) calls it executed, whether the board changed, how many requests
the turn cost, and whether the model was thinking. Exists to answer the act-first arm's four
deliverable questions from the transcript rather than by eye.
SRP/DRY check: Pass -- scripts/summarize_sk48_arm.py summarizes scores for the overfit arm;
this one summarizes per-action behaviour, which that script does not do.
"""
import json, re, sys
from pathlib import Path

run = Path(sys.argv[1])

# per-turn request/thinking facts from the request log
turns = {}
rl = run / "requests.jsonl"
if rl.exists():
    for line in rl.read_text(errors="replace").splitlines():
        try:
            rec = json.loads(line)
        except Exception:
            continue
        if rec.get("event") != "response":
            continue
        a = rec.get("action")
        t = turns.setdefault(a, {"requests": 0, "reasoning_chars": 0, "actions": []})
        t["requests"] += 1

# action calls + board deltas from the transcript
tx = next((run / "transcripts").glob("*_p0.txt"), None)
text = tx.read_text(errors="replace") if tx else ""

cur = None
for block in re.split(r"\n--- ", text):
    m = re.match(r"(?:.*?)action=(\d+)", block)
    if m:
        cur = int(m.group(1))
        turns.setdefault(cur, {"requests": 0, "reasoning_chars": 0, "actions": []})
    if cur is None:
        continue
    for call in re.findall(r"action\(\s*(\[[^\]]*\])\s*\)", block):
        turns[cur]["actions"].append(call.strip())
    if "THINKING" in block[:40]:
        turns[cur]["reasoning_chars"] += len(block)

print(f"run: {run.name}")
print(f"{'act':>4} {'reqs':>5} {'thinking':>9}  actions")
for a in sorted(k for k in turns if isinstance(k, int)):
    t = turns[a]
    acts = ", ".join(dict.fromkeys(t["actions"])) or "(none)"
    print(f"{a:>4} {t['requests']:>5} {('yes' if t['reasoning_chars'] else 'no'):>9}  {acts[:90]}")

st = run / "summary.txt"
if st.exists():
    print("\n" + st.read_text().strip())
