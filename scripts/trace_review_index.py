"""Trace review: shared points in a run's games (nodes) and the paths forward from them, for human raters.

Author: Claude Opus 5.5 (2-Oct-2026, Son: "show the moves up until this point alongside the reasoning, then LEFT
and RIGHT paths forward; let humans rate and annotate; keep sampling the splitting paths").

A node is a game state that several plays reach. Today: the start of a level. Every repeat of a game starts level
L from the same board (checked 2-Oct on re86: levels 1-6 identical across 5 repeats), so the repeats of a panel run
are already different paths forward from one point. A path is one play's turns from the node to the end of that
level (cleared, or the play ended inside it). Fork nodes (one logged turn, K sampled next turns) come from the fork
sampler later and use the same shapes.

  python scripts/trace_review_index.py <run dir: local path or gs://.../working> --run <run id> --model base \
      --out <dir>     -> <dir>/index.json (nodes, paths, splits) + <dir>/paths/<path id>.json (turn content)

Input per play: artifacts/<game>_p<pass>_events.jsonl (the ARC3-Inference viewer event log): one "initial" event,
one "action" event per action (board after it, level, level_completed, analysis_step) and one "analysis" event per
model turn (its transcript: [SYSTEM PROMPT] [USER PROMPT] [MODEL RESPONSE META] (raw tool calls) [THINKING] ...).
Path content: the start board, then per turn its thinking, its tool call code, and its actions, each with the board
after it as a diff against the previous board (rows replaced). Game ids only, never titles.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

SECTION = re.compile(r"^\[([A-Z][A-Z _]+)\]\s*$", re.M)
FENCED = {"lf52", "tn36", "re86", "dc22", "su15", "as66"}   # held-out / test-only: never shown for rating by default


def board_hash(board) -> str:
    return hashlib.sha1(json.dumps(board, separators=(",", ":")).encode()).hexdigest()[:12]


def rows(board) -> list[str]:
    """A 64x64 board of 0-15 as 64 hex strings."""
    return ["".join("0123456789abcdef"[int(v)] for v in row) for row in board]


def sections(transcript: str) -> dict[str, str]:
    marks = list(SECTION.finditer(transcript or ""))
    out = {}
    for i, m in enumerate(marks):
        end = marks[i + 1].start() if i + 1 < len(marks) else len(transcript)
        out.setdefault(m.group(1), transcript[m.end():end].strip())
    return out


def tool_code(meta: str) -> list[str]:
    """The code of each python tool call in a [MODEL RESPONSE META] block (raw_tool_calls JSON)."""
    i = meta.find("raw_tool_calls:")
    if i < 0:
        return []
    j = meta.find("[", i)
    try:
        calls, _ = json.JSONDecoder().raw_decode(meta[j:])
    except (ValueError, json.JSONDecodeError):
        return []
    out = []
    for c in calls:
        args = (c.get("function") or {}).get("arguments") or ""
        try:
            args = json.loads(args)
        except (ValueError, json.JSONDecodeError):
            pass
        out.append(args.get("code", json.dumps(args)) if isinstance(args, dict) else str(args))
    return out


def read_play(lines):
    initial, actions, turns = None, [], {}
    for line in lines:
        if not line.strip():
            continue
        e = json.loads(line)
        t = e.get("type")
        if t == "initial":
            initial = e
        elif t == "action":
            actions.append(e)
        elif t == "analysis":
            turns[int(e.get("analysis_step") or 0)] = e.get("transcript") or ""
    return initial, actions, turns


def segments(initial, actions):
    """[(level, start board, [actions in this level], cleared)] in play order."""
    out, level, start, cur = [], int(initial.get("level") or 1), initial["board"], []
    for a in actions:
        cur.append(a)
        if str(a.get("level_completed")).lower() == "true":
            out.append((level, start, cur, True))
            level, start, cur = level + 1, a["board"], []
    if cur or not out:
        out.append((level, start, cur, False))
    return out


def path_content(level, start, acts, turns):
    """Turn-by-turn content of one level segment: thinking, code, actions with board diffs."""
    steps = []
    for a in acts:
        s = int(a.get("analysis_step") or 0)
        if not steps or steps[-1] != s:
            steps.append(s)
    prev = rows(start)
    out_turns = []
    for s in steps:
        sec = sections(turns.get(s, ""))
        moves = []
        for a in (x for x in acts if int(x.get("analysis_step") or 0) == s):
            cur = rows(a["board"])
            moves.append({"n": int(a.get("action_num") or 0), "action": a.get("action_display") or a.get("action_name"),
                          "changed": str(a.get("board_changed")).lower() == "true",
                          "level_up": str(a.get("level_completed")).lower() == "true",
                          "diff": {str(r): cur[r] for r in range(len(cur)) if cur[r] != prev[r]}})
            prev = cur
        out_turns.append({"step": s, "thinking": sec.get("THINKING", ""), "said": sec.get("ASSISTANT", ""),
                          "code": tool_code(sec.get("MODEL RESPONSE META", "")), "moves": moves})
    return {"level": level, "start": rows(start), "turns": out_turns}


def index_run(run_dir: Path, run_id: str, model: str, include_fenced: bool):
    plays = sorted(run_dir.glob("artifacts/*_events.jsonl"))
    nodes, paths = {}, []
    contents = {}
    for f in plays:
        m = re.match(r"([a-z0-9]{4})-[0-9a-f]+_p(\d+)_events\.jsonl$", f.name)
        if not m:
            continue
        game, ps = m.group(1), int(m.group(2))
        if game in FENCED and not include_fenced:
            continue
        initial, actions, turns = read_play(f.read_text(encoding="utf-8").splitlines())
        if initial is None:
            continue
        earlier = []
        for level, start, acts, cleared in segments(initial, actions):
            if not acts:
                continue
            nid = f"{game}:L{level}:{board_hash(start)}"
            pid = f"{run_id}:{game}_p{ps}:L{level}"
            nodes.setdefault(nid, {"id": nid, "kind": "level_start", "game": game, "level": level, "paths": [],
                                   "meta": {"start": rows(start)}})
            steps = sorted({int(a.get("analysis_step") or 0) for a in acts})
            paths.append({"id": pid, "node": nid, "run": run_id, "play": f"{game}_p{ps}", "model": model,
                          "level": level, "cleared": cleared, "turns": len(steps), "actions": len(acts),
                          "first_action": int(acts[0].get("action_num") or 0),
                          "last_action": int(acts[-1].get("action_num") or 0),
                          # this play's earlier levels: what the rater opens under "how they got here"
                          "meta": {"earlier": list(earlier)}})
            nodes[nid]["paths"].append(pid)
            contents[pid] = path_content(level, start, acts, turns)
            earlier.append(pid)
    return nodes, paths, contents


def splits_for(nodes, paths_by_id):
    """Pairs of paths from the same node to show side by side. Pairs that ended differently (one cleared the level,
    one did not; or very different action counts) first: those are the comparisons a rater learns the most from."""
    out = []
    for n in nodes.values():
        ps = [paths_by_id[p] for p in n["paths"]]
        for i in range(len(ps)):
            for j in range(i + 1, len(ps)):
                a, b = ps[i], ps[j]
                contrast = (a["cleared"] != b["cleared"]) * 2 + abs(a["actions"] - b["actions"]) / max(a["actions"], b["actions"], 1)
                out.append({"id": f"{n['id']}~{a['play']}~{b['play']}", "node": n["id"], "paths": [a["id"], b["id"]],
                            "priority": round(contrast, 3)})
    return sorted(out, key=lambda s: -s["priority"])


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("run_dir", help="local copy of a run's working/ dir (artifacts/*_events.jsonl)")
    ap.add_argument("--run", required=True, help="run id, e.g. daniel-p5train-base-a-1002")
    ap.add_argument("--model", required=True, help="model label of the run: base, r0, r1, ...")
    ap.add_argument("--out", required=True)
    ap.add_argument("--include-fenced", action="store_true", help="also index held-out games (never for training)")
    args = ap.parse_args()
    out = Path(args.out)
    (out / "paths").mkdir(parents=True, exist_ok=True)
    nodes, paths, contents = index_run(Path(args.run_dir), args.run, args.model, args.include_fenced)
    by_id = {p["id"]: p for p in paths}
    splits = splits_for({k: v for k, v in nodes.items() if len(v["paths"]) > 1}, by_id)
    for pid, c in contents.items():
        (out / "paths" / (pid.replace(":", "__") + ".json")).write_text(json.dumps(c, separators=(",", ":")), encoding="utf-8")
    (out / "index.json").write_text(json.dumps({"run": args.run, "model": args.model, "nodes": list(nodes.values()),
                                                "paths": paths, "splits": splits}, indent=1), encoding="utf-8")
    shared = sum(len(n["paths"]) > 1 for n in nodes.values())
    print(f"{len(paths)} paths, {len(nodes)} nodes ({shared} reached by 2+ plays), {len(splits)} pairs")
    return 0


if __name__ == "__main__":
    sys.exit(main())
