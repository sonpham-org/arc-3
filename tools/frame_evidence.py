#!/usr/bin/env python3.13
"""
Author: Claude Opus 5
Date: 16-September-2026
PURPOSE: Render what a replay row actually shows, as text, for the two passes that need a mind.
Pass D reads it to write a falsifiable expectation; pass E hands it to an independent reviewer
as the only evidence it gets besides the record. Four views over one recording:
  timeline  one line per row: action, state, level, frames, cells changed, change bbox
  board     the settled board of a row, in the harness's own glyphs, with a coordinate ruler
  diff      the changed region between two rows' settled boards, before and after
  evidence  everything pass E needs for one finished record, and nothing from the game source
Boards are drawn with inference.utils.grid_utils.format_grid_ascii's glyph table, so the text a
reviewer reads is the text the model is served. The settled board of a row is its last grid; a
row whose frame list is empty shows the preceding row's board, the frame_ref rule in SCHEMA.md.
SRP/DRY check: Pass - validate.py owns frame_ref checking, segment.py owns cuts and the measured
outcome string; this only renders rows for human or agent reading and computes no record field.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "ARC3-Inference"))

from inference.utils.grid_utils import ARC_COLOR_CHARS, ARC_COLOR_LEGEND  # noqa: E402

DEFAULT_RECORDINGS = REPO_ROOT / "datasets" / "decision-steps" / "v0" / "recordings"


class Recording:
    def __init__(self, recordings_dir: Path, game_id: str, guid: str) -> None:
        self.path = recordings_dir / game_id / f"{guid}.ndjson"
        self.lines = self.path.read_text(encoding="utf-8").splitlines()
        self._rows: dict[int, dict] = {}

    def __len__(self) -> int:
        return len(self.lines)

    def row(self, i: int) -> dict:
        if i not in self._rows:
            self._rows[i] = json.loads(self.lines[i])["data"]
        return self._rows[i]

    def settled(self, i: int) -> tuple[list[list[int]], int]:
        """The board a player saw after row i, and the row it actually came from."""
        j = i
        while j >= 0:
            frame = self.row(j).get("frame") or []
            if frame:
                return frame[-1], j
            j -= 1
        raise ValueError(f"no row at or before {i} carries a frame")

    def action_text(self, i: int) -> str:
        ai = self.row(i)["action_input"]
        data = ai.get("data") or {}
        if "x" in data and "y" in data:
            return f"{ai['id']}(row={data['y']},col={data['x']})"
        return ai["id"]


def glyph(v: int) -> str:
    return ARC_COLOR_CHARS[max(0, min(15, int(v)))]


def changed_cells(a: list[list[int]], b: list[list[int]]) -> list[tuple[int, int]]:
    if len(a) != len(b) or (a and len(a[0]) != len(b[0])):
        return [(r, c) for r in range(len(b)) for c in range(len(b[0]))]
    return [(r, c) for r in range(len(a)) for c in range(len(a[0])) if a[r][c] != b[r][c]]


def bbox(cells: list[tuple[int, int]]) -> tuple[int, int, int, int] | None:
    if not cells:
        return None
    rows = [r for r, _ in cells]
    cols = [c for _, c in cells]
    return min(rows), min(cols), max(rows), max(cols)


def clusters(cells: list[tuple[int, int]], gap: int = 2) -> list[list[tuple[int, int]]]:
    """Group changed cells that lie within `gap` of each other, largest group first. A HUD
    counter ticking on the board's edge and a move in the middle are two groups, not one box."""
    remaining = set(cells)
    groups: list[list[tuple[int, int]]] = []
    while remaining:
        seed = remaining.pop()
        group, frontier = [seed], [seed]
        while frontier:
            r, c = frontier.pop()
            near = [q for q in remaining if abs(q[0] - r) <= gap and abs(q[1] - c) <= gap]
            for q in near:
                remaining.discard(q)
                group.append(q)
                frontier.append(q)
        groups.append(group)
    return sorted(groups, key=len, reverse=True)


def render(grid: list[list[int]], r0: int = 0, c0: int = 0, r1: int | None = None, c1: int | None = None) -> str:
    r1 = len(grid) - 1 if r1 is None else r1
    c1 = len(grid[0]) - 1 if c1 is None else c1
    header = "      " + "".join(str((c // 10) % 10) if c % 10 == 0 else " " for c in range(c0, c1 + 1))
    header2 = "      " + "".join(str(c % 10) for c in range(c0, c1 + 1))
    lines = [header, header2]
    for r in range(r0, r1 + 1):
        lines.append(f"{r:>4}  " + "".join(glyph(grid[r][c]) for c in range(c0, c1 + 1)))
    return "\n".join(lines)


def timeline_line(rec: Recording, i: int) -> str:
    d = rec.row(i)
    n_frames = len(d.get("frame") or [])
    if i == 0:
        change = "start"
    else:
        before, _ = rec.settled(i - 1)
        after, src = rec.settled(i)
        cells = changed_cells(before, after)
        groups = clusters(cells) if len(cells) <= 1500 else [cells]
        boxes = [bbox(g) for g in groups[:3]]
        change = f"changed={len(cells)}" + "".join(
            f" [{len(g)}@r{b[0]}-{b[2]},c{b[1]}-{b[3]}]" for g, b in zip(groups, boxes)
        ) + (f" +{len(groups) - 3} more groups" if len(groups) > 3 else "")
        if src != i:
            change += f" (no frame; shows row {src})"
    return f"{i:>5}  {rec.action_text(i):<24} {d['state']:<13} levels={d['levels_completed']} frames={n_frames:<3} {change}"


def diff_text(rec: Recording, i: int, j: int, pad: int = 2) -> str:
    before, _ = rec.settled(i)
    after, _ = rec.settled(j)
    cells = changed_cells(before, after)
    if not cells:
        return f"rows {i} -> {j}: no cell changed"
    h, w = len(after), len(after[0])
    groups = clusters(cells) if len(cells) <= 1500 else [cells]
    out = [f"rows {i} -> {j}: {len(cells)} cells changed in {len(groups)} group(s)"]
    for n, group in enumerate(groups[:4], start=1):
        box = bbox(group)
        r0, c0 = max(0, box[0] - pad), max(0, box[1] - pad)
        r1, c1 = min(h - 1, box[2] + pad), min(w - 1, box[3] + pad)
        out.append(f"group {n}: {len(group)} cells, rows {box[0]}-{box[2]} cols {box[1]}-{box[3]}")
        if (r1 - r0 + 1) * (c1 - c0 + 1) > 1400:
            out.append("  (too large to crop usefully; compare the whole boards)")
            continue
        out.append(f"BEFORE (row {i}):")
        out.append(render(before, r0, c0, r1, c1))
        out.append(f"AFTER (row {j}):")
        out.append(render(after, r0, c0, r1, c1))
    if len(groups) > 4:
        out.append(f"... {len(groups) - 4} smaller group(s) not drawn")
    return "\n".join(out)


def level_start(rec: Recording, i: int) -> int:
    """First row of the level being played at row i (after the last levels_completed rise)."""
    level = rec.row(i)["levels_completed"]
    j = i
    while j > 0 and rec.row(j - 1)["levels_completed"] >= level and rec.row(j - 1)["state"] != "WIN":
        if rec.row(j - 1)["levels_completed"] < level:
            break
        j -= 1
    return j


def evidence(rec: Recording, record: dict, history_limit: int = 60) -> str:
    before_row = record["frame_ref"]["row_index"]
    decision_row = record["source"]["row_index"]
    start = level_start(rec, before_row)
    lo = max(start, before_row - history_limit + 1)
    parts = [
        f"GLYPHS: {ARC_COLOR_LEGEND}",
        f"Rows are zero-based lines of the recording. A MOUSE/ACTION6 click at (row=r, col=c) addresses board cell [r][c].",
        "",
        f"LEVEL HISTORY up to the board the decision was taken on (level play began at row {start}"
        + (f"; showing the last {history_limit} rows" if lo > start else "") + "):",
    ]
    parts += [timeline_line(rec, k) for k in range(lo, before_row + 1)]
    painted = lambda grid: sum(1 for line in grid for cell in line if cell != 0)  # segment.py's definition
    parts += [
        "",
        f"THE DECISION (row {decision_row}), and what it did:",
        timeline_line(rec, decision_row),
        f"painted cells (value not 0, glyph not W): {painted(rec.settled(before_row)[0])} before -> "
        f"{painted(rec.settled(decision_row)[0])} after",
        "",
        f"BOARD BEFORE THE DECISION (settled board of row {before_row}):",
        render(rec.settled(before_row)[0]),
        "",
        f"BOARD AFTER THE DECISION (settled board of row {decision_row}):",
        render(rec.settled(decision_row)[0]),
        "",
        "CHANGED REGION:",
        diff_text(rec, before_row, decision_row),
    ]
    return "\n".join(parts)


def parse_rows(text: str) -> tuple[int, int]:
    if ":" in text:
        a, b = text.split(":", 1)
        return int(a), int(b)
    return int(text), int(text)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("view", choices=("timeline", "board", "diff", "evidence"))
    p.add_argument("--game-id")
    p.add_argument("--guid")
    p.add_argument("--rows", help="A:B inclusive (timeline, diff) or a single row (board)")
    p.add_argument("--record", type=Path, help="evidence: an episode .jsonl")
    p.add_argument("--line", type=int, default=0, help="evidence: zero-based line in --record")
    p.add_argument("--recordings-dir", type=Path, default=DEFAULT_RECORDINGS)
    args = p.parse_args(argv)

    if args.view == "evidence":
        record = json.loads(args.record.read_text(encoding="utf-8").splitlines()[args.line])
        rec = Recording(args.recordings_dir, record["game_id"], record["source"]["recording_guid"])
        print(evidence(rec, record))
        return 0

    rec = Recording(args.recordings_dir, args.game_id, args.guid)
    a, b = parse_rows(args.rows)
    if args.view == "timeline":
        for i in range(a, min(b, len(rec) - 1) + 1):
            print(timeline_line(rec, i))
    elif args.view == "board":
        grid, src = rec.settled(a)
        print(f"settled board of row {a}" + (f" (row {a} has no frame; this is row {src})" if src != a else ""))
        print(render(grid))
    else:
        print(diff_text(rec, a, b))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
