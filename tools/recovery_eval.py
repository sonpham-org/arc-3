#!/usr/bin/env python3.13
"""
Author: Claude Opus 5
Date: 16-September-2026
PURPOSE: The recovery eval of docs/plans/2026-09-15-step5-prove-it-moves-a-score.md section 3, run
against any OpenAI-compatible model server. One question per fork that tools/find_retries.py finds
in a human recording: the player stood on a board, chose X, and that attempt failed; later the
player stood on the same board, chose Y, and the level cleared. The model is put on that board and
asked for one action, twice over:
  with_history  the prompt also says what X was, what X visibly did, and that the attempt failed
  no_history    the board and the action menu only
The model's answer is then played on the real game: the recording is replayed in the offline engine
up to the fork, the answer is applied, and the resulting board is compared with the boards X and Y
leave. So two clicks a cell apart on one object count as the same choice, exactly as the fork finder
counts them. Each answer lands in one bucket: repeated_failed, matched_win, no_effect, other,
not_offered, unparsed, no_answer. The number the eval exists for is the repeated_failed rate with
history against without it: a model that learns from a refuted choice repeats it less when told.
Three subcommands:
  build  freeze the questions (both prompts, the actions X and Y, engine checks) to items.jsonl
  ask    send them to a server, k samples each, appending raw replies to responses.jsonl
  score  play every answer in the engine and write scored.jsonl and summary.json
The prompt never shows Y, a pass-D record's rationale or action_role, or anything from game source.
SRP/DRY check: Pass - find_retries.py finds the forks, frame_evidence.py renders boards and diffs,
inference/agent/action_names.py names actions the way the harness names them to the model, and
inference/utils/openai_compat.py builds the request the harness sends. This only turns forks into
questions, asks them, and scores the answers in the engine.
"""
from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import json
import os
import re
import sys
import time
import urllib.request
from collections import Counter, defaultdict
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
REPO_ROOT = TOOLS.parent
sys.path.insert(0, str(TOOLS))
sys.path.insert(0, str(REPO_ROOT / "ARC3-Inference"))

from find_retries import forks, same_board  # noqa: E402
from frame_evidence import DEFAULT_RECORDINGS, Recording, diff_grids, render  # noqa: E402
from inference.agent.action_names import to_engine_action, to_model_action  # noqa: E402
from inference.utils.grid_utils import ARC_COLOR_LEGEND  # noqa: E402
from inference.utils.openai_compat import build_chat_payload, build_headers  # noqa: E402

EVAL_DIR = REPO_ROOT / "datasets" / "decision-steps" / "v0" / "recovery-eval"
EPISODES = REPO_ROOT / "datasets" / "decision-steps" / "v0" / "episodes"
CONDITIONS = ("with_history", "no_history")
BUCKETS = ("repeated_failed", "matched_win", "no_effect", "other", "not_offered", "unparsed", "no_answer")
PROMPT_VERSION = "recovery-eval-v0.1"

#: Sampling the Qwen3.8-27B baseline pinned (a108 configs/a108.qwen38.baseline.json, analyzer block),
#: so the eval samples the model the way the harness does.
PINNED_SAMPLING = {"temperature": 1.0, "top_p": 0.95, "top_k": 20, "thinking": True}

SYSTEM_PROMPT = (
    "You are playing a turn-based game on a 64x64 grid of coloured cells. Nobody tells you the rules "
    "or the goal: you learn them from what your actions do to the board. A game is a series of levels, "
    "cleared one at a time. Each turn you choose one action."
)

ACTION_HELP = {
    "ACTION1": "UP", "ACTION2": "DOWN", "ACTION3": "LEFT", "ACTION4": "RIGHT", "ACTION5": "SPACE",
    "ACTION6": "MOUSE (click one cell; give row and col)",
    "ACTION7": "ACTION7 (its meaning is not fixed across games)",
}


# ---------------------------------------------------------------------------------------------
# build


def model_action_text(action_input: dict) -> str:
    """An engine action as the harness names it to the model: RIGHT, or MOUSE row=40 col=32."""
    name = to_model_action(action_input["id"])
    data = action_input.get("data") or {}
    if "x" in data and "y" in data:
        return f"{name} row={data['y']} col={data['x']}"
    return name


def board_sha(grid: list[list[int]]) -> str:
    return hashlib.sha256(json.dumps(grid).encode()).hexdigest()[:16]


def menu(available: list[int]) -> list[str]:
    """Engine action names offered on the fork board. RESET is not offered: the question is which
    move to make from this board, and a RESET is not a move from it."""
    return [f"ACTION{i}" for i in sorted(available) if 1 <= i <= 7]


def prompts(rec: Recording, fork: dict, level: int, win_levels: int, offered: list[str]) -> dict[str, str]:
    board = rec.settled(fork["win_row"] - 1)[0]
    head = [
        f"You are on level {level + 1} of {win_levels}.",
        "",
        "THE BOARD NOW. One character per cell. The two header lines give the column index (tens, "
        "then units) and each line starts with its row index; both run 0-63.",
        f"Glyphs: {ARC_COLOR_LEGEND}",
        render(board),
    ]
    tail = [
        "",
        "ACTIONS YOU CAN TAKE NOW: " + "; ".join(ACTION_HELP[a] for a in offered) + ".",
        "",
        "Choose your next single action. Think as long as you need, then end your reply with exactly "
        "one line in one of these forms:",
        "ACTION: LEFT",
        "ACTION: MOUSE row=12 col=40",
    ]
    before = rec.settled(fork["failed_row"] - 1)[0]
    after = rec.settled(fork["failed_row"])[0]
    effect = diff_grids(before, after, "What it changed", "Before it:", "After it:")
    if "too large to crop" in effect:
        effect += "\nThe whole board after it:\n" + render(after)
    ending = ("when the game ended in GAME_OVER" if fork["failed_end"] == "died"
              else "when you pressed RESET to restart the level")
    later = fork["failed_moves"] - fork["fork_index"] - 1
    history = [
        "",
        "WHAT HAPPENED EARLIER ON THIS LEVEL.",
        f"In an earlier attempt at this level you reached this same board and chose "
        f"{model_action_text(rec.row(fork['failed_row'])['action_input'])}.",
        effect,
        f"That attempt went on for {later} more move(s) that changed the board, and ended {ending}, "
        "without clearing the level. You are now back on this board in a new attempt.",
    ]
    return {
        "with_history": "\n".join(head + history + tail),
        "no_history": "\n".join(head + tail),
    }


def record_index() -> dict[tuple[str, int], str]:
    """(recording guid, decision row) -> episode file, for records that survived pass E."""
    out = {}
    for path in sorted(EPISODES.glob("*.jsonl")):
        for line in path.read_text().splitlines():
            r = json.loads(line)
            out[(r["source"]["recording_guid"], r["source"]["row_index"])] = path.name
    return out


def build(recordings_dir: Path, environments_dir: Path | None) -> tuple[list[dict], list[str]]:
    items, notes, seen = [], [], {}
    records = record_index()
    engine = Engine(environments_dir) if environments_dir else None
    for game_dir in sorted(p for p in recordings_dir.iterdir() if p.is_dir()):
        if game_dir.name.startswith("as66"):  # withdrawn from the live lineup; not an eval game
            continue
        for path in sorted(game_dir.glob("*.ndjson")):
            rec = Recording(recordings_dir, game_dir.name, path.stem)
            for fork in forks(rec):
                item_id = f"{game_dir.name}__{path.stem[:8]}__row{fork['win_row']}"
                if fork["repeats_earlier_choice"]:
                    notes.append(f"skip {item_id}: an earlier failed attempt already made the winning choice here")
                    continue
                fork_row = fork["win_row"] - 1
                board = rec.settled(fork_row)[0]
                failed_ai = rec.row(fork["failed_row"])["action_input"]
                win_ai = rec.row(fork["win_row"])["action_input"]
                key = (game_dir.name, board_sha(board), json.dumps(failed_ai), json.dumps(win_ai))
                if key in seen:
                    notes.append(f"skip {item_id}: same board and same two choices as {seen[key]}")
                    continue
                seen[key] = item_id
                row = rec.row(fork_row)
                offered = menu(row["available_actions"])
                item = {
                    "item_id": item_id,
                    "prompt_version": PROMPT_VERSION,
                    "game_id": game_dir.name,
                    "recording_guid": path.stem,
                    "level": row["levels_completed"],
                    "win_levels": row["win_levels"],
                    "fork_row": fork_row,
                    "board_sha": board_sha(board),
                    "offered": offered,
                    "failed": {"row": fork["failed_row"], "action_input": strip(failed_ai),
                               "text": model_action_text(failed_ai), "attempt_end": fork["failed_end"]},
                    "win": {"row": fork["win_row"], "action_input": strip(win_ai), "text": model_action_text(win_ai)},
                    "record": records.get((path.stem, fork["win_row"])),
                    "system": SYSTEM_PROMPT,
                    "prompts": prompts(rec, fork, row["levels_completed"], row["win_levels"], offered),
                }
                if engine:
                    item["engine_check"] = engine.check(item, rec)
                items.append(item)
    return items, notes


def strip(action_input: dict) -> dict:
    data = action_input.get("data") or {}
    return {"id": action_input["id"], "data": {k: data[k] for k in ("x", "y") if k in data}}


# ---------------------------------------------------------------------------------------------
# engine


class Engine:
    """Replays a recording in the offline engine and plays one candidate action from the fork board.
    ONLY_RESET_LEVELS=true is the pin the harness runs under; with it every recording on disk
    replays frame for frame."""

    def __init__(self, environments_dir: Path) -> None:
        os.environ["ONLY_RESET_LEVELS"] = "true"
        import logging

        from arc_agi import Arcade, OperationMode
        from arcengine import GameAction

        quiet = logging.getLogger("recovery_eval.arcade")  # the arcade logs a line per game load
        quiet.setLevel(logging.WARNING)
        self.GameAction = GameAction
        self.arcade = Arcade(operation_mode=OperationMode.OFFLINE, environments_dir=str(environments_dir), logger=quiet)
        self._rows: dict[tuple[str, str], list[dict]] = {}
        self._cache: dict[tuple[str, str], dict] = {}

    def _prefix(self, game_id: str, guid: str, recordings_dir: Path) -> list[dict]:
        if (game_id, guid) not in self._rows:
            path = recordings_dir / game_id / f"{guid}.ndjson"
            self._rows[(game_id, guid)] = [json.loads(l)["data"]["action_input"] for l in path.read_text().splitlines()]
        return self._rows[(game_id, guid)]

    def play(self, item: dict, action_input: dict | None, recordings_dir: Path = DEFAULT_RECORDINGS) -> dict:
        """Board, state and level after replaying up to the fork and then playing action_input
        (None plays nothing and returns the fork board itself)."""
        cache_key = (item["item_id"], json.dumps(action_input, sort_keys=True))
        if cache_key in self._cache:
            return self._cache[cache_key]
        env = self.arcade.make(item["game_id"])
        if env is None:
            raise RuntimeError(f"no build for {item['game_id']} under the environments dir")
        board, state, levels = None, None, None
        steps = self._prefix(item["game_id"], item["recording_guid"], recordings_dir)[: item["fork_row"] + 1]
        if action_input is not None:
            steps = steps + [action_input]
        for ai in steps:
            frame = env.step(self.GameAction[ai["id"]], data=ai.get("data") or {})
            if frame is None:
                continue
            state, levels = frame.state.name, frame.levels_completed
            # a refused request returns no frame; the board a player sees is still the last one drawn
            board = grid_of(frame) or board
        out = {"board": board, "state": state, "levels": levels}
        self._cache[cache_key] = out
        return out

    def check(self, item: dict, rec: Recording) -> dict:
        """The engine must stand on the recorded fork board, and must leave the recorded boards for
        both recorded choices, or no answer to this item can be scored."""
        fork = self.play(item, None)["board"]
        win = self.play(item, item["win"]["action_input"])["board"]
        failed = self.play(item, item["failed"]["action_input"])["board"]
        return {
            "fork_board_exact": fork == rec.settled(item["fork_row"])[0],
            "win_result_exact": win == rec.settled(item["win"]["row"])[0],
            "failed_result_same_board": same_board(failed, rec.settled(item["failed"]["row"])[0]),
            "failed_and_win_differ": not same_board(failed, win),
        }


def grid_of(frame) -> list[list[int]] | None:
    if frame is None or not frame.frame:
        return None
    g = frame.frame[-1]
    return g.tolist() if hasattr(g, "tolist") else [list(r) for r in g]


# ---------------------------------------------------------------------------------------------
# ask


ANSWER = re.compile(r"ACTION:\s*([A-Za-z0-9_]+)(?:[\s,(]+row\s*=\s*(\d+)[\s,]+col\s*=\s*(\d+))?", re.IGNORECASE)


def parse_answer(content: str | None) -> dict | None:
    """The last `ACTION: X` line of a reply, as an engine action_input; None when there is none.
    An unknown action name comes back with id None so the scorer can tell unparsed from absent."""
    matches = list(ANSWER.finditer(content or ""))
    if not matches:
        return None
    m = matches[-1]
    engine = to_engine_action(m.group(1))
    if engine is None or engine == "RESET":
        return {"id": None, "raw": m.group(0)}
    if engine == "ACTION6":
        if m.group(2) is None:
            return {"id": None, "raw": m.group(0)}
        return {"id": engine, "data": {"x": int(m.group(3)), "y": int(m.group(2))}}
    return {"id": engine, "data": {}}


def ask_one(base_url: str, api_key: str, model: str, item: dict, condition: str, k: int,
            max_tokens: int, timeout: int) -> dict:
    messages = [{"role": "system", "content": item["system"]},
                {"role": "user", "content": item["prompts"][condition]}]
    payload = build_chat_payload(provider="vllm", model=model, messages=messages, max_tokens=max_tokens,
                                 temperature=PINNED_SAMPLING["temperature"], top_p=PINNED_SAMPLING["top_p"],
                                 top_k=PINNED_SAMPLING["top_k"], thinking=PINNED_SAMPLING["thinking"])
    payload["n"] = k
    request = urllib.request.Request(
        base_url.rstrip("/") + "/chat/completions", data=json.dumps(payload).encode(),
        headers=build_headers(provider="vllm", api_key=api_key), method="POST",
    )
    started = time.monotonic()
    with urllib.request.urlopen(request, timeout=timeout) as resp:
        body = json.loads(resp.read())
    return {
        "item_id": item["item_id"], "condition": condition, "prompt_version": item["prompt_version"],
        "model": body.get("model", model), "sampling": {**PINNED_SAMPLING, "max_tokens": max_tokens, "n": k},
        "started_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time() - (time.monotonic() - started))),
        "seconds": round(time.monotonic() - started, 1),
        "usage": body.get("usage"),
        "choices": [{
            "content": c["message"].get("content"),
            "reasoning": c["message"].get("reasoning_content") or c["message"].get("reasoning"),
            "finish_reason": c.get("finish_reason"),
        } for c in body.get("choices", [])],
    }


# ---------------------------------------------------------------------------------------------
# score


def classify(engine: Engine, item: dict, choice: dict) -> dict:
    answer = parse_answer(choice.get("content"))
    if answer is None:
        return {"bucket": "no_answer" if choice.get("finish_reason") == "length" or not choice.get("content") else "unparsed",
                "answer": None}
    if answer["id"] is None:
        return {"bucket": "unparsed", "answer": answer.get("raw")}
    text = model_action_text(answer)
    if answer["id"] not in item["offered"] or not all(0 <= v <= 63 for v in answer["data"].values()):
        return {"bucket": "not_offered", "answer": text}
    result = engine.play(item, answer)
    fork = engine.play(item, None)["board"]
    failed = engine.play(item, item["failed"]["action_input"])["board"]
    win = engine.play(item, item["win"]["action_input"])["board"]
    if same_board(result["board"], fork):
        bucket = "no_effect"
    elif same_board(result["board"], failed):
        bucket = "repeated_failed"
    elif same_board(result["board"], win):
        bucket = "matched_win"
    else:
        bucket = "other"
    return {"bucket": bucket, "answer": text, "state_after": result["state"]}


def summarize(scored: list[dict], items: list[dict]) -> dict:
    per_item: dict[str, dict[str, Counter]] = defaultdict(lambda: {c: Counter() for c in CONDITIONS})
    for s in scored:
        per_item[s["item_id"]][s["condition"]][s["bucket"]] += 1
    totals = {c: Counter() for c in CONDITIONS}
    for counts in per_item.values():
        for c in CONDITIONS:
            totals[c].update(counts[c])

    def rates(counter: Counter) -> dict:
        n = sum(counter.values())
        return {"n": n, **{b: counter[b] for b in BUCKETS},
                "repeated_failed_rate": round(counter["repeated_failed"] / n, 3) if n else None,
                "matched_win_rate": round(counter["matched_win"] / n, 3) if n else None}

    order = [i["item_id"] for i in items if i["item_id"] in per_item]
    return {
        "items": len(order),
        "by_condition": {c: rates(totals[c]) for c in CONDITIONS},
        "per_item": {i: {c: rates(per_item[i][c]) for c in CONDITIONS} for i in order},
    }


def table(summary: dict) -> str:
    lines = ["| item | with history: repeat / win / other | no history: repeat / win / other |", "|---|---|---|"]

    def cell(r: dict) -> str:
        rest = r["n"] - r["repeated_failed"] - r["matched_win"]
        return f"{r['repeated_failed']} / {r['matched_win']} / {rest} (n={r['n']})"

    for item_id, conds in summary["per_item"].items():
        lines.append(f"| {item_id} | {cell(conds['with_history'])} | {cell(conds['no_history'])} |")
    b = summary["by_condition"]
    lines.append(f"| **all** | {cell(b['with_history'])} | {cell(b['no_history'])} |")
    return "\n".join(lines)


# ---------------------------------------------------------------------------------------------


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(l) for l in path.read_text().splitlines() if l.strip()] if path.exists() else []


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("--items", type=Path, default=EVAL_DIR / "items.jsonl")
    p.add_argument("--recordings-dir", type=Path, default=DEFAULT_RECORDINGS)
    p.add_argument("--environments-dir", type=Path, default=os.environ.get("ARC3_ENVIRONMENTS_DIR"),
                   help="game builds, <game>/<build>/ (the exact 25 are ~/flash-next-work/environment_files-11p44 on a108)")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("build", help="freeze the questions to --items")
    a = sub.add_parser("ask", help="send the questions to a model server")
    a.add_argument("--run-dir", type=Path, required=True)
    a.add_argument("--base-url", required=True)
    a.add_argument("--model", required=True)
    a.add_argument("--api-key-file", type=Path, help="else $RECOVERY_EVAL_API_KEY")
    a.add_argument("--k", type=int, default=4, help="samples per item per condition")
    a.add_argument("--max-tokens", type=int, default=32768)
    a.add_argument("--workers", type=int, default=2)
    a.add_argument("--timeout", type=int, default=7200)
    a.add_argument("--only", nargs="*", help="item_ids to ask; default all")
    s = sub.add_parser("score", help="play every answer in the engine")
    s.add_argument("--run-dir", type=Path, required=True)
    args = p.parse_args(argv)

    if args.cmd == "build":
        items, notes = build(args.recordings_dir, args.environments_dir)
        args.items.parent.mkdir(parents=True, exist_ok=True)
        args.items.write_text("".join(json.dumps(i) + "\n" for i in items))
        for n in notes:
            print(n)
        bad = [i["item_id"] for i in items if "engine_check" in i and not all(i["engine_check"].values())]
        print(f"{len(items)} items written to {args.items}; {sum(1 for i in items if i['record'])} carry a pass-E record"
              + ("" if args.environments_dir else "; NOT engine-checked (no --environments-dir)")
              + (f"; ENGINE CHECK FAILED: {bad}" if bad else ""))
        return 1 if bad else 0

    items = read_jsonl(args.items)
    args.run_dir.mkdir(parents=True, exist_ok=True)
    responses_path = args.run_dir / "responses.jsonl"

    if args.cmd == "ask":
        api_key = (args.api_key_file.read_text().strip() if args.api_key_file
                   else os.environ.get("RECOVERY_EVAL_API_KEY", ""))
        done = {(r["item_id"], r["condition"]) for r in read_jsonl(responses_path)}
        todo = [(i, c) for i in items for c in CONDITIONS  # both conditions of an item stay adjacent
                if (not args.only or i["item_id"] in args.only) and (i["item_id"], c) not in done]
        print(f"asking {len(todo)} (item, condition) pairs, k={args.k}, {len(done)} already done", flush=True)
        with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as pool:
            futures = {pool.submit(ask_one, args.base_url, api_key, args.model, i, c, args.k, args.max_tokens,
                                   args.timeout): (i, c) for i, c in todo}
            for fut in concurrent.futures.as_completed(futures):
                i, c = futures[fut]
                try:
                    row = fut.result()
                except Exception as exc:  # a failed request is reported and left to a re-run, never recorded as an answer
                    print(f"FAILED {i['item_id']} {c}: {type(exc).__name__}: {exc}", flush=True)
                    continue
                with responses_path.open("a") as out:
                    out.write(json.dumps(row) + "\n")
                tokens = (row.get("usage") or {}).get("completion_tokens")
                print(f"{i['item_id']} {c}: {len(row['choices'])} choices, {tokens} completion tokens, "
                      f"{row['seconds']}s, finish={[ch['finish_reason'] for ch in row['choices']]}", flush=True)
        return 0

    if not args.environments_dir:
        p.error("score needs --environments-dir (or $ARC3_ENVIRONMENTS_DIR)")
    engine = Engine(args.environments_dir)
    by_id = {i["item_id"]: i for i in items}
    scored = []
    for row in read_jsonl(responses_path):
        item = by_id[row["item_id"]]
        for n, choice in enumerate(row["choices"]):
            scored.append({"item_id": row["item_id"], "condition": row["condition"], "sample": n,
                           "finish_reason": choice.get("finish_reason"), **classify(engine, item, choice)})
    (args.run_dir / "scored.jsonl").write_text("".join(json.dumps(s) + "\n" for s in scored))
    summary = summarize(scored, items)
    (args.run_dir / "summary.json").write_text(json.dumps(summary, indent=1) + "\n")
    print(table(summary))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
