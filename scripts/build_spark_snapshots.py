#!/usr/bin/env python3
"""
Author: Claude Opus 5.5 (Bubba)
Date: 06-October-2026
PURPOSE: Build the Spark runner's starting points ("snapshots"), one small JSON per game, written to
  datasets/spark-runner-snapshots/<game>.json plus an index.json (kept out of docs/static on purpose: the site
  serves docs/static to anyone without sign-in, and these hold verbatim model transcripts from Son's runs). A snapshot is the state a recorded stock run of the
  Franzen-notebook line was in at the end of the turn in which it first reached the game's stuck level
  (docs/static/data/stuck-levels.json):
    - actions: the exact engine action line (including the automatic RESETs after a game over) from the run's
      game-N-frames.json, so the offline arc_agi engine replays to the same board; expected board, level and
      action count are stored so the runner can refuse a snapshot whose replay does not match.
    - turns: the model's conversation rebuilt from the run's per-turn transcripts (game-N-step-M.json on the site's
      volume): opener prompt, thinking, assistant text, python tool calls and the rendered tool results. The site
      keeps transcripts, not the exact request bodies, so this is a reconstruction (board images and the harness's
      raw tool-result JSON are not in it). Older turns are dropped once the kept text passes a size cap, the same way
      the harness drains its own history.
    - retained_functions: top-level Python functions the model defined in those tool calls (last definition wins),
      the harness's ARC3_PERSISTENT_FUNCTIONS_SCOPE=game memory, re-derived with ast.
  Games stuck at level 1 get a snapshot with no actions and no turns: the stuck point is the start of the game.
  Inputs (read-only copies pulled from the arc3-viewer volume with `railway ssh ... tar | base64`):
    <runs-dir>/<run>/run-overview.json and <runs-dir>/<run>/files/game-N*.json for the seven 2-Oct runs.
  Usage: python3 scripts/build_spark_snapshots.py --runs-dir <dir> --plan <plan.json> [--out datasets/spark-runner-snapshots]
SRP/DRY check: Pass - stuck levels come only from stuck-levels.json (scripts/stuck_levels_tally.py builds it); the
  runner (tools/spark_runner) consumes these files and does the replay check; nothing here talks to a model.
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOL_CALL_RE = re.compile(r"<parameter=code>\n?(.*?)\n?</parameter>", re.S)
# Kept conversation text per snapshot. The harness drains its history at ARC3_CONTEXT_DRAIN_TOKENS = 58k tokens;
# at ~3.5 characters per token that is ~200k characters, so older turns beyond this would have been drained anyway.
MAX_TURN_CHARS = 200_000


def board_sha(ascii_board: str) -> str:
    return hashlib.sha256(ascii_board.encode()).hexdigest()


def engine_action(frame: dict) -> dict:
    name = frame["action_name"]
    if name == "ACTION6":
        click = frame.get("click") or {}
        m = re.match(r"MOUSE\(row=(\d+), col=(\d+)\)", frame.get("action_display") or "")
        row = click.get("row", int(m.group(1)) if m else None)
        col = click.get("col", int(m.group(2)) if m else None)
        if row is None or col is None:
            raise ValueError(f"click without coordinates at frame {frame.get('frameIndex')}")
        return {"name": name, "row": int(row), "col": int(col)}
    return {"name": name}


def tool_code(markup: str) -> str:
    m = TOOL_CALL_RE.search(markup)
    return m.group(1) if m else markup.strip()


def turn_messages(sections: list[dict], turn_no: int) -> list[dict]:
    """One recorded turn's transcript sections -> chat messages in the harness's history shape."""
    out: list[dict] = []
    current: dict | None = None
    calls = 0
    for s in sections:
        label, text = s.get("label", ""), s.get("content", "")
        if label in ("SYSTEM PROMPT", "ANALYZER STATUS", "MODEL RESPONSE META"):
            continue
        if label == "USER PROMPT":
            current = None
            out.append({"role": "user", "content": text})
        elif label == "THINKING":
            if current is None or current.get("tool_calls") or current.get("reasoning_content"):
                current = {"role": "assistant", "content": None}
                out.append(current)
            current["reasoning_content"] = text
        elif label == "ASSISTANT":
            if current is None or current.get("tool_calls"):
                current = {"role": "assistant", "content": None}
                out.append(current)
            current["content"] = text
        elif label.startswith("TOOL CALL"):
            if current is None or (current.get("tool_calls") and out[-1] is not current):
                current = {"role": "assistant", "content": None}
                out.append(current)
            calls += 1
            call_id = f"snap-{turn_no}-{calls}"
            current.setdefault("tool_calls", []).append({
                "id": call_id, "type": "function",
                "function": {"name": "python", "arguments": json.dumps({"code": tool_code(text)})},
            })
        elif label.startswith("TOOL RESULT"):
            last_call = None
            for m in reversed(out):
                if m.get("tool_calls"):
                    last_call = m["tool_calls"][-1]["id"]
                    break
            out.append({"role": "tool", "tool_call_id": last_call or f"snap-{turn_no}-0", "content": text})
            current = None
    return out


def retained_functions(codes: list[str]) -> dict[str, str]:
    kept: dict[str, str] = {}
    for code in codes:
        try:
            tree = ast.parse(code)
        except SyntaxError:
            continue
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                src = ast.get_source_segment(code, node)
                if src:
                    kept[node.name] = src
    return kept


def build_one(game: dict, plan: dict, runs_dir: Path, color_chars: str) -> dict:
    code, stuck = game["game"], game["stuck_level"]
    run, idx = plan["run"], plan["index"]
    files = runs_dir / run / "files"
    frames = json.loads((files / f"game-{idx}-frames.json").read_text())["frames"]
    game_id = frames and json.loads((files / f"game-{idx}-frames.json").read_text())["game_id"]
    if stuck == 1:
        cut = 0
        through_step = 0
    else:
        first = next(i for i, f in enumerate(frames) if int(f.get("level") or 0) >= stuck)
        through_step = int(frames[first].get("analysis_step") or 0)
        cut = max(i for i, f in enumerate(frames) if f["type"] == "action" and int(f.get("analysis_step") or 0) <= through_step)
    actions = [engine_action(f) for f in frames[1:cut + 1]]
    end = frames[cut]
    level_actions = sum(1 for f in frames[1:cut + 1] if int(f.get("level") or 0) >= stuck) - (1 if stuck > 1 else 0)

    turns: list[dict] = []
    codes: list[str] = []
    if through_step:
        steps = {}
        for p in files.glob(f"game-{idx}-step-*.json"):
            st = json.loads(p.read_text())["step"]
            if st.get("analysisStep") is not None and (st.get("localContext") or {}).get("sections"):
                steps[int(st["analysisStep"])] = st
        for n in sorted(k for k in steps if k <= through_step):
            sections = steps[n]["localContext"]["sections"]
            msgs = turn_messages(sections, n)
            for m in msgs:
                for c in m.get("tool_calls") or []:
                    codes.append(json.loads(c["function"]["arguments"])["code"])
            turns.append({"analysis_step": n, "level": steps[n].get("level"), "messages": msgs})
    total = 0
    kept_from = len(turns)
    for i in range(len(turns) - 1, -1, -1):
        size = len(json.dumps(turns[i]["messages"]))
        if total + size > MAX_TURN_CHARS and i < len(turns) - 1:
            break
        total += size
        kept_from = i
    dropped = kept_from
    turns = turns[kept_from:]

    return {
        "kind": "arc3-spark-snapshot", "version": 1, "game": code, "game_id": game_id, "nickname": game["nickname"],
        "stuck_level": stuck, "levels": game["levels"],
        "source": {
            "kind": "stock_run" if stuck > 1 else "game_start",
            "line": "Franzen-notebook line, stock prompt (Son's GCP run, 2-Oct-2026)",
            "run": run, "game_index": idx, "through_analysis_step": through_step,
        },
        "actions": actions,
        "expected": {
            "level": int(end.get("level") or 1), "score": int(end.get("score") or 0), "state": end.get("state"),
            "action_count": len(actions), "actions_into_stuck_level": max(0, level_actions),
            "board_sha256": board_sha(end["board_ascii"]), "color_chars": color_chars,
        },
        "conversation": {
            "exact": False,
            "note": ("Rebuilt from the run's stored per-turn transcripts: prompts, thinking, python calls and the "
                     "rendered tool results. Board images and the raw tool-result JSON are not stored on the site, "
                     "so this is close to, not byte-identical with, what the model saw."
                     if through_step else "Stuck at level 1: play starts from the beginning of the game, no history."),
            "turns_total": dropped + len(turns), "turns_dropped_oldest": dropped,
        },
        "turns": turns,
        "retained_functions": retained_functions(codes),
        "built": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs-dir", type=Path, required=True)
    ap.add_argument("--plan", type=Path, required=True, help="game -> {run, index} chosen from the runs' overviews")
    ap.add_argument("--out", type=Path, default=ROOT / "datasets/spark-runner-snapshots")
    args = ap.parse_args()
    stuck = json.loads((ROOT / "docs/static/data/stuck-levels.json").read_text())
    plan = json.loads(args.plan.read_text())
    args.out.mkdir(parents=True, exist_ok=True)
    index = []
    for g in stuck["games"]:
        if not g.get("stuck_level") or g["game"] not in plan or not plan[g["game"]].get("run"):
            continue
        p = plan[g["game"]]
        overview = json.loads((args.runs_dir / p["run"] / "run-overview.json").read_text())
        snap = build_one(g, p, args.runs_dir, overview.get("color_chars") or "")
        (args.out / f"{g['game']}.json").write_text(json.dumps(snap, separators=(",", ":")))
        index.append({"game": g["game"], "game_id": snap["game_id"], "nickname": g["nickname"],
                      "stuck_level": g["stuck_level"], "levels": g["levels"], "source": snap["source"],
                      "actions": len(snap["actions"]), "turns": len(snap["turns"]),
                      "turns_dropped_oldest": snap["conversation"]["turns_dropped_oldest"],
                      "retained_functions": len(snap["retained_functions"]),
                      "conversation_exact": False, "bytes": (args.out / f"{g['game']}.json").stat().st_size})
        print(g["game"], g["stuck_level"], len(snap["actions"]), "actions", len(snap["turns"]), "turns",
              len(snap["retained_functions"]), "functions", index[-1]["bytes"], "bytes")
    (args.out / "index.json").write_text(json.dumps({
        "kind": "arc3-spark-snapshots", "built": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "verified": False, "snapshots": index}, indent=1))


if __name__ == "__main__":
    main()
