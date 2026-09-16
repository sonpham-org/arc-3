#!/usr/bin/env python3.13
"""
Author: Claude Opus 5
Date: 16-September-2026
PURPOSE: Find the decisions a recovery eval can be built on, mechanically, from one recording. A
level is split into attempts: a new attempt starts where the level starts, after a RESET, or after
a death. For the attempt that CLEARED the level, compare its action list with every earlier failed
attempt on the same level and find the fork: the first move where the winning attempt chose
differently from the failed attempt that followed it longest. Because a game replays identically
from the same opening, identical prefixes put the player on the identical board, and the fork is
a same-board, different-choice decision observed on tape. Two moves count as the same choice when
they leave the same board, so equivalent clicks a cell apart do not fake a fork -- "last time, from here, you chose X
and that attempt failed; this time Y, and the level cleared". Reports the fork row, both choices,
a board-equality check, and which failed attempt it is measured against.
Rows whose state is GAME_OVER or whose frame list is empty are not choices (dead boards and
refused requests), and a move that changed no cell is not a step; both are skipped when listing an
attempt's moves.
SRP/DRY check: Pass - frame_evidence.py renders boards; segment.py cuts records. This only
selects rows, and writes no record field.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from frame_evidence import DEFAULT_RECORDINGS, Recording, changed_cells  # noqa: E402


#: Cells two boards may differ by and still be "the same board": a step counter drawn on the grid
#: ticks on moves that do nothing else, so two attempts that walked into a wall a different number
#: of times differ by a few counter cells and are otherwise the same position.
COUNTER_TOLERANCE = 4


def same_board(a: list[list[int]], b: list[list[int]]) -> bool:
    return len(a) == len(b) and len(changed_cells(a, b)) <= COUNTER_TOLERANCE


def attempts(rec: Recording) -> list[dict]:
    out, moves, start = [], [], 0
    for i in range(1, len(rec)):
        d, p = rec.row(i), rec.row(i - 1)
        if d["levels_completed"] > p["levels_completed"] and p["state"] != "GAME_OVER":
            moves.append(i)
            out.append({"start": start, "moves": moves, "end": "cleared", "end_row": i, "level": p["levels_completed"]})
            moves, start = [], i
            continue
        if d["action_input"]["id"] == "RESET":
            ended = "died" if p["state"] == "GAME_OVER" else "reset"
            out.append({"start": start, "moves": moves, "end": ended, "end_row": i, "level": d["levels_completed"]})
            moves, start = [], i
            continue
        if d["state"] == "GAME_OVER" or not d.get("frame"):
            continue
        # A move that changed no more than a counter tick (a walk into a wall) is not a step along
        # the attempt; aligning on it would fake a fork one move early.
        if same_board(rec.settled(i)[0], rec.settled(i - 1)[0]):
            continue
        moves.append(i)
    return out


def forks(rec: Recording) -> list[dict]:
    found = []
    tries = attempts(rec)
    for k, win in enumerate(tries):
        if win["end"] != "cleared":
            continue
        failed = [a for a in tries[:k] if a["level"] == win["level"] and a["end"] != "cleared" and a["moves"]]
        if not failed:
            continue
        win_acts = [rec.action_text(i) for i in win["moves"]]
        best = None
        for a in failed:
            acts = [rec.action_text(i) for i in a["moves"]]
            j = 0
            # Same choice = same resulting board, not same action text: two clicks a cell apart on
            # one object are one choice, and a blocked move equals a no-op of another name.
            while (
                j < min(len(acts), len(win_acts))
                and same_board(rec.settled(a["moves"][j])[0], rec.settled(win["moves"][j])[0])
            ):
                j += 1
            if j >= len(acts) or j >= len(win_acts):
                continue
            if best is None or j > best[0]:
                best = (j, a, acts)
        if best is None:
            continue
        j, a, acts = best
        b_fail, b_win = rec.settled(a["moves"][j] - 1)[0], rec.settled(win["moves"][j] - 1)[0]
        # Every earlier choice made from this same board, in any failed attempt. If one of them
        # left the board the winning choice leaves, the winning move is not a change of choice at
        # all -- the difference lies in something the board does not show -- so it is flagged.
        after_win = rec.settled(win["moves"][j])[0]
        earlier = []
        for f in failed:
            for i in f["moves"]:
                if same_board(rec.settled(i - 1)[0], b_win):
                    earlier.append({"row": i, "action": rec.action_text(i), "attempt_end": f["end"],
                                    "same_result_as_win": same_board(rec.settled(i)[0], after_win)})
        found.append({
            "level": win["level"], "fork_index": j,
            "win_row": win["moves"][j], "win_action": win_acts[j], "win_start": win["start"], "cleared_at": win["end_row"],
            "failed_row": a["moves"][j], "failed_action": acts[j], "failed_start": a["start"],
            "failed_end": a["end"], "failed_end_row": a["end_row"], "failed_moves": len(acts),
            "earlier_failed_attempts": len(failed),
            "board_diff": len(changed_cells(b_fail, b_win)) if len(b_fail) == len(b_win) else None,
            "earlier_choices_here": earlier,
            "repeats_earlier_choice": any(e["same_result_as_win"] for e in earlier),
        })
    return found


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("--game-id", required=True)
    p.add_argument("--guid", required=True)
    p.add_argument("--recordings-dir", type=Path, default=DEFAULT_RECORDINGS)
    args = p.parse_args(argv)
    rec = Recording(args.recordings_dir, args.game_id, args.guid)
    for f in forks(rec):
        print(
            f"level {f['level']}: fork after {f['fork_index']} shared moves -- winning row {f['win_row']} "
            f"{f['win_action']} (attempt from row {f['win_start']}, cleared at {f['cleared_at']}) vs failed row "
            f"{f['failed_row']} {f['failed_action']} (attempt from row {f['failed_start']}, {f['failed_end']} at "
            f"{f['failed_end_row']} after {f['failed_moves']} moves; {f['earlier_failed_attempts']} failed attempt(s) "
            f"on this level); boards differ by {f['board_diff']}"
            + ("; REPEATS an earlier choice from this board" if f["repeats_earlier_choice"] else "")
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
