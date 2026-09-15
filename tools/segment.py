#!/usr/bin/env python3.13
"""
Author: Claude Opus 5 (Bubba)
Date: 15-September-2026 (rule 6, level_advance, same day)
PURPOSE: Pass A of step 4 - cut one replay recording into candidate decision-step records with
every DERIVABLE field measured from the recording plus the per-game dispatch table, and every
judgment field deliberately absent. Reads
datasets/decision-steps/v0/recordings/<game_id>/<guid>.ndjson and
datasets/decision-steps/dispatch/<game_id>.json; writes
datasets/decision-steps/v0/episodes/<game_id>__<guid>__<slug>.candidate.jsonl. A candidate is
NOT schema-valid on purpose - it is missing required fields, validate.py does not collect
`*.candidate.jsonl` from a directory walk, and the pattern is gitignored, so an unfinished
record cannot be mistaken for a finished one. Plan: docs/plans/2026-09-15-step4-segment-and-
label-execution.md section 2 and 3; contract: datasets/decision-steps/SCHEMA.md.
SRP/DRY check: Pass - tools/replay_scrape.py pulls recordings, validate.py checks records, the
dispatch tables hold the source citations. This only segments and fills what is measurable, and
reimplements none of those three.

WHAT IS FILLED AND WHAT IS NOT
==============================
The execution plan's section 2 splits the record into a derivable half and a judgment half. Five
fields are named in neither list; the side each was assigned to is marked (*) and is a decision
of this tool, not a reading of the plan.

  FILLED (measured, never guessed)          | ABSENT (passes D and E)
  ------------------------------------------|--------------------------------------
  schema_version                            | tier                      (*)
  game_id                                   | memory_in
  source.{kind,recording_guid,row_index}    | decision.memory_out
  segment.{id,boundary_reason}              | decision.rationale
  level                                     | decision.expected_observation
  frame_ref.{recording_guid,row_index,field}| corrected_decision
  ascii (always null)                       | outcome.expectation_held  (*)
  last_action                          (*)  | action_role
  last_result                          (*)  |
  decision.action                      (*)  |
  outcome.observed                          |
  action_role_source                        |
  rationale_provenance                      |

`tier` and `outcome.expectation_held` need a mind: both depend on whether the step is being
labelled as a failed probe, which is a reading of intent, not a measurement. The other three are
mechanical - the previous row's action id, that action's measured effect, and this row's action
id.

THE RULES, AND WHAT SETTLED EACH
================================
Every rule below was checked against the four hand-built records in
bp35-0a0ad940__c935ca1b-dfee-4be1-9574-bf4cc80c5b89__l5-death-undo-reset-00.jsonl.

1. The WINDOW is an input, not a derivation. The hand-built bp35 episode opens at row 213, and
   row 212 is an ordinary ACTION3 with no state change - nothing in the recording marks 213 as a
   start. Where an episode begins is an editorial choice; this tool takes it as --rows and
   derives only where the cuts fall inside it and what each cut's reason is.

2. A CUT happens after a boundary-event row; the new segment carries that event as its
   boundary_reason. The first segment of a window carries the event on the row before the
   window, or `episode_start` when there is none.

3. A ROW WITH AN EMPTY FRAME LIST IS NOT A BOUNDARY EVENT. Every boundary_reason names a state
   change, and those rows changed nothing - the engine emitted no frames and the session API does
   not count them. This is what keeps the failed ACTION7 at row 215 inside the recovery segment
   instead of cutting a third one, and it is the same fact SCHEMA.md already records about rows
   215, 370, 390, 572 and 807.

4. frame_ref points at the nearest PRECEDING row with a non-empty frame list - never at the
   decision row itself, and never at one of the empty-frame rows. Row 216's frame_ref is 214,
   not 215.

5. outcome.observed counts cells that differ between frame[-1] of the frame_ref row and
   frame[-1] of the decision row. When the decision row's own frame list is empty there is no
   number and the text says so.

6. A LEVEL TRANSITION IS `level_advance`, and it outranks the frame-delta heuristics. A row
   whose levels_completed is higher than the last settled row's completed a level; the next
   segment opens with `level_advance`. This closed a gap that was previously refused outright,
   and the refusal was hiding two wrong answers rather than one: across the 40 transitions in
   the six live-build recordings on disk, the frame-delta heuristics would have called 25 of
   them `extent_change` - a cn04 word about a held part, not about a new level being laid out -
   and would have seen no boundary at all on the other 15, letting a segment run straight
   through a level change. Neither is survivable at volume.

   WHERE IT SITS IN THE PRIORITY ORDER IS A DECISION, NOT A MEASUREMENT. It is below
   death/reset/undo and above camera_shift/extent_change. Nothing observed ties: all 40
   transition rows carry ACTION1-ACTION6 with state NOT_FINISHED or WIN, never RESET, never
   ACTION7, never GAME_OVER. So the ordering against the hard events is unfalsified AND
   unexercised - it is this tool's choice for a row that has never occurred, flagged the same
   way the row/col reading of `args` is.

   A FALL in levels_completed is refused, not labelled. It is unobserved in all 40 transitions,
   and it should be impossible - RESET restores the level's opening snapshot, it does not
   un-complete a level. If one ever appears, the row schema means something other than what
   this tool reads, and that is worth stopping for.

A KNOWN READABILITY GAP THIS CHANGE MAKES VISIBLE
=================================================
`level` is levels_completed, a COUNT, so during play of the Nth level it reads N-1. Until
level_advance existed no episode could span a level boundary, so the ambiguity never showed up
inside one file. Now a multi-level episode carries it in plain sight: the records before the cut
read one lower than the records after. Unchanged here - it is flagged in SCHEMA.md and it is a
schema question, not a segmenter bug.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_RECORDINGS = REPO_ROOT / "datasets" / "decision-steps" / "v0" / "recordings"
DEFAULT_DISPATCH = REPO_ROOT / "datasets" / "decision-steps" / "dispatch"
DEFAULT_EPISODES = REPO_ROOT / "datasets" / "decision-steps" / "v0" / "episodes"

# Must equal schema.json's schema_version const. The 0.2 bump migrated every fixture and
# record but left this at "0.1", so pass A emitted records validate.py rejected on the
# version alone. scripts/test_segment.py asserts the two agree.
SCHEMA_VERSION = "0.2"
FRAME_FIELD = "data.frame"
CANDIDATE_SUFFIX = ".candidate.jsonl"

# How far back frame_ref may look for a non-empty frame before giving up. The longest run of
# empty-frame rows observed on any recording on disk is 1; 16 is headroom, not a guess.
MAX_FRAME_LOOKBACK = 16

# Heuristic thresholds for the two frame-delta boundary reasons the plan's section 2 names.
# Both sit BELOW death/reset/undo in priority, so they cannot affect a row that already carries
# a hard event. They are the weakest thing this tool emits and pass D should confirm them.
WHOLE_BOARD_FRACTION = 0.25


@dataclass
class Row:
    index: int
    action: str | None
    x: int | None
    y: int | None
    state: str | None
    levels_completed: int | None
    frame_count: int
    frame: list[list[int]] | None  # frame[-1], loaded only inside the requested range


def load_rows(path: Path, frame_lo: int, frame_hi: int) -> list[Row]:
    """Stream the NDJSON once. Metadata for every row; the settled frame only for
    [frame_lo, frame_hi], because a full recording holds far more grid than is ever needed."""
    rows: list[Row] = []
    with path.open() as handle:
        for index, line in enumerate(handle):
            data = json.loads(line)["data"]
            frames = data.get("frame") or []
            action_input = data.get("action_input") or {}
            payload = action_input.get("data") or {}
            keep = frame_lo <= index <= frame_hi and bool(frames)
            rows.append(
                Row(
                    index=index,
                    action=action_input.get("id"),
                    x=payload.get("x"),
                    y=payload.get("y"),
                    state=data.get("state"),
                    levels_completed=data.get("levels_completed"),
                    frame_count=len(frames),
                    frame=frames[-1] if keep else None,
                )
            )
    return rows


def is_degenerate(row: Row) -> bool:
    """A row the engine answered with no frames at all. It changed nothing, the session API does
    not count it, and SCHEMA.md forbids pointing a frame_ref at it."""
    return row.frame_count == 0


def cells_changed(a: Row, b: Row) -> int | None:
    if a.frame is None or b.frame is None:
        return None
    return sum(
        1
        for row_a, row_b in zip(a.frame, b.frame)
        for cell_a, cell_b in zip(row_a, row_b)
        if cell_a != cell_b
    )


def painted_cells(row: Row) -> int | None:
    if row.frame is None:
        return None
    return sum(1 for line in row.frame for cell in line if cell != 0)


def colour_histogram(row: Row) -> dict[int, int] | None:
    if row.frame is None:
        return None
    histogram: dict[int, int] = {}
    for line in row.frame:
        for cell in line:
            histogram[cell] = histogram.get(cell, 0) + 1
    return histogram


def frame_ref_row(rows: list[Row], index: int) -> int:
    """Rule 4: nearest preceding row with a non-empty frame list."""
    for candidate in range(index - 1, max(-1, index - 1 - MAX_FRAME_LOOKBACK), -1):
        if candidate >= 0 and not is_degenerate(rows[candidate]):
            return candidate
    raise ValueError(
        f"row {index}: no row with a non-empty frame list within {MAX_FRAME_LOOKBACK} rows "
        f"before it, so no frame_ref can be written"
    )


def previous_settled(rows: list[Row], index: int) -> int | None:
    """The last row before `index` that actually rendered something, used for level deltas.
    Degenerate rows report levels_completed 0 regardless of the real level and must be skipped."""
    for candidate in range(index - 1, -1, -1):
        if not is_degenerate(rows[candidate]):
            return candidate
    return None


def level_delta(rows: list[Row], previous: int, index: int) -> int | None:
    """levels_completed on settled row `index` against settled row `previous`, or None when
    either row does not report it. Callers must pass settled rows: a degenerate row reports 0
    regardless of the real level."""
    before, after = rows[previous].levels_completed, rows[index].levels_completed
    if before is None or after is None:
        return None
    return after - before


def boundary_event(rows: list[Row], index: int) -> str | None:
    """Rules 2, 3 and 6. Returns the boundary_reason this row's event would give the NEXT
    segment, or None when the row is not a boundary. Priority is
    death > reset > undo > level_advance > frame deltas; rule 6 records that the placement of
    level_advance in that order is a decision no observed row exercises."""
    row = rows[index]
    if is_degenerate(row):
        return None  # rule 3: no frames emitted, so no state change, so no boundary
    previous = previous_settled(rows, index)

    if row.state == "GAME_OVER" and (previous is None or rows[previous].state != "GAME_OVER"):
        return "death"
    if row.action == "RESET":
        return "reset"
    if row.action == "ACTION7":
        return "undo"

    if previous is None:
        return None

    delta = level_delta(rows, previous, index)
    if delta is not None and delta > 0:
        return "level_advance"

    changed = cells_changed(rows[previous], row)
    if changed is None:
        return None
    total = len(row.frame) * len(row.frame[0]) if row.frame else 0
    if total and changed >= WHOLE_BOARD_FRACTION * total:
        # A whole-board delta that conserves the colour histogram exactly is the viewport
        # moving; one that does not is the board's extent changing.
        if colour_histogram(rows[previous]) == colour_histogram(row):
            return "camera_shift"
        if painted_cells(rows[previous]) != painted_cells(row):
            return "extent_change"
    return None


def check_levels_monotonic(rows: list[Row], start: int, end: int) -> None:
    """Rule 6's refusal. A RISE in levels_completed is labelled `level_advance`; a FALL is
    refused, because it is unobserved in all 40 transitions on disk and RESET restores a level's
    opening snapshot rather than un-completing it. The window before the first row is scanned
    too, since that row can open the first segment."""
    previous = previous_settled(rows, start)
    for index in range(start, end + 1):
        if is_degenerate(rows[index]):
            continue
        if previous is not None and (level_delta(rows, previous, index) or 0) < 0:
            raise SystemExit(
                f"segment.py: levels_completed FALLS at row {index} "
                f"(row {previous}: {rows[previous].levels_completed} -> row {index}: "
                f"{rows[index].levels_completed}), which is unobserved in every recording on "
                f"disk.\n"
                f"  A rise is `level_advance`; a fall has no reading this tool trusts, because "
                f"RESET restores a level's opening snapshot and does not un-complete a level.\n"
                f"  Refused rather than labelled: check the recording before segmenting it."
            )
        previous = index


def cut_segments(rows: list[Row], start: int, end: int) -> list[tuple[list[int], str]]:
    """Rule 2. Returns [(row indices, boundary_reason)] in window order."""
    opening = None
    for candidate in range(start - 1, max(-1, start - 1 - MAX_FRAME_LOOKBACK), -1):
        if candidate < 0:
            break
        event = boundary_event(rows, candidate)
        if event is not None:
            opening = event
        break  # only the row immediately before the window can open the first segment
    segments: list[tuple[list[int], str]] = []
    current: list[int] = []
    reason = opening or "episode_start"
    for index in range(start, end + 1):
        current.append(index)
        event = boundary_event(rows, index)
        if event is not None and index < end:
            segments.append((current, reason))
            current, reason = [], event
    if current:
        segments.append((current, reason))
    return segments


def describe_outcome(rows: list[Row], index: int) -> str:
    """Rule 5. Numbers, not prose - the plan's section 2 is explicit about that."""
    row = rows[index]
    if is_degenerate(row):
        return (
            f"the engine returned an empty frame list (data.frame: []) on row {index}; no cells "
            f"changed, state {rows[frame_ref_row(rows, index)].state} -> {row.state}, and the "
            f"session API does not count this row"
        )
    reference = frame_ref_row(rows, index)
    changed = cells_changed(rows[reference], row)
    before, after = rows[reference], row
    parts = [
        f"{changed} cells changed between the settled frame of row {reference} and that of "
        f"row {index}",
        f"state {before.state} -> {after.state}",
        f"levels_completed {before.levels_completed} -> {after.levels_completed}",
        f"painted cells {painted_cells(before)} -> {painted_cells(after)}",
        f"the row carries {row.frame_count} frames against {before.frame_count} on row {reference}",
    ]
    return "; ".join(parts)


def action_object(row: Row) -> dict:
    """`args` is emitted as {row: y, col: x}. The recording carries x and y; the schema and the
    plan's section 6 example carry row and col. row=y / col=x is the only reading consistent
    with that example, and it is an ASSUMPTION - no record in the acceptance set uses a
    cell-addressed action, so nothing here verifies it."""
    action: dict = {"action": row.action}
    if row.x is not None and row.y is not None:
        action["args"] = {"row": row.y, "col": row.x}
    return action


def run_ended_on(rows: list[Row], index: int) -> bool:
    """Did the action on row `index` end the run?

    A FLIP to GAME_OVER, not the mere presence of it. Rows 215, 370, 390, 572 and 807 of the
    bp35 recording all sit at GAME_OVER because the run was already over when they were
    submitted; reading the state alone would call each of them a fresh death and put five
    run-ending markers on one death. The transition is the event.

    Schema 0.2 added this. Before it, a record taken after a death read exactly like an ordinary
    step - which in a corpus built to teach recovery after being wrong is the one thing it must
    never be unable to say.
    """
    if index <= 0:
        return False  # row 0 is the boot marker; nothing precedes it to have ended
    return rows[index].state == "GAME_OVER" and rows[index - 1].state != "GAME_OVER"


def last_result(rows: list[Row], index: int) -> dict:
    """The measured effect of the action on row `index`."""
    row = rows[index]
    if is_degenerate(row):
        # A degenerate row changed no board, but it can still be the row that killed the run,
        # so run_ended is measured here too rather than defaulted with the rest.
        return {"board_changed": False, "level_changed": False,
                "run_ended": run_ended_on(rows, index)}
    reference = frame_ref_row(rows, index)
    changed = cells_changed(rows[reference], row)
    return {
        "board_changed": bool(changed),
        "level_changed": rows[reference].levels_completed != row.levels_completed,
        "run_ended": run_ended_on(rows, index),
    }


def engine_citation(engine: dict, action_name: str, entry: dict) -> str:
    """A citation into the vendored engine, carrying the version so the scope is stated.

    The version matters and is not decoration. 0.9.3 is the only arcengine ever published and
    is what this repo pins, but it is NOT verifiable from here that three.arcprize.org runs it
    -- so the citation says which engine it read rather than implying it read the one that
    served the recording. vendor/README.md carries the full provenance chain.
    """
    primary = next(
        (call for call in entry["calls"] if call["role"].startswith("primary effect")), None
    )
    tail = f" -> {primary['text']}" if primary is not None else ""
    return (
        f"{engine['source_file']}:{entry['branch']['line']} {entry['branch']['text']}{tail}"
        f" [{engine['package']} {engine['version']}, engine-level: {action_name} is dispatched"
        f" by the engine, not by this game]"
    )


def citation(dispatch: dict, action_name: str) -> str:
    """action_role_source, from the dispatch table built by pass B.

    Game source first, engine second. When a game carries its own branch for an action the
    game's line is the better citation -- it is what distinguishes this build from every other
    one. Only two of the eight in-scope games carry a RESET branch, and for the other six the
    engine block is the citation, which is the whole reason arcengine was vendored: before it
    was, a RESET step could only be labelled on the two games that happen to handle it
    themselves, which is a selection effect on the exact behaviour the corpus exists to measure.
    """
    entry = dispatch["actions"].get(action_name)
    if entry is None:
        engine = dispatch.get("engine", {}).get("actions", {}).get(action_name)
        if engine is not None:
            return engine_citation(dispatch["engine"], action_name, engine)
        return (
            f"UNCITABLE: {action_name} has no dispatch branch in "
            f"{dispatch['source_file']} and none in "
            f"{dispatch.get('engine', {}).get('source_file', 'the engine')} - see "
            f"unhandled_actions in "
            f"datasets/decision-steps/dispatch/{dispatch['game_id']}.json"
        )
    if not entry["offered"]:
        return (
            f"UNCITABLE: {action_name} has a branch at {dispatch['source_file']}:"
            f"{entry['branch']['line']} but is not in this game's available_actions, so no API "
            f"call can have reached it"
        )
    primary = next(
        (call for call in entry["calls"] if call["role"].startswith("primary effect")), None
    )
    if primary is not None:
        tail = f" -> {primary['text']}"
    elif entry["calls"]:
        # No single call IS the effect: the action dispatches again on board state, as cn04's
        # ACTION5 does on sprite-stack length. Naming one of the conditional calls here would
        # be a lie by selection, so the citation stops at the branch and says why.
        tail = (
            f" (branch-dependent: {len(entry['calls'])} conditional call sites at "
            + ", ".join(f":{call['line']}" for call in entry["calls"])
            + ")"
        )
    else:
        tail = ""
    return f"{dispatch['source_file']}:{entry['branch']['line']} {entry['branch']['text']}{tail}"


def build_record(
    rows: list[Row],
    index: int,
    game_id: str,
    guid: str,
    segment_id: str,
    boundary_reason: str,
    dispatch: dict,
) -> dict:
    reference = frame_ref_row(rows, index)
    row = rows[index]
    record = {
        "schema_version": SCHEMA_VERSION,
        "game_id": game_id,
        "source": {"kind": "human_replay", "recording_guid": guid, "row_index": index},
        "segment": {"id": segment_id, "boundary_reason": boundary_reason},
        "level": rows[reference].levels_completed,
        "frame_ref": {
            "recording_guid": guid,
            "row_index": reference,
            "field": FRAME_FIELD,
        },
        "ascii": None,
        "last_action": None,
        "last_result": None,
        "decision": {"action": action_object(row)},
        "outcome": {"observed": describe_outcome(rows, index)},
        "action_role_source": citation(dispatch, row.action or ""),
        "rationale_provenance": "annotated",
    }
    if index > 0:
        record["last_action"] = action_object(rows[index - 1])
        record["last_result"] = last_result(rows, index - 1)
    return record


def parse_window(text: str) -> tuple[int, int]:
    try:
        start_text, end_text = text.split(":", 1)
        start, end = int(start_text), int(end_text)
    except ValueError:
        raise SystemExit(f"segment.py: --rows wants START:END, got {text!r}")
    if start < 0 or end < start:
        raise SystemExit(f"segment.py: --rows {text} is not a forward window")
    return start, end


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Cut a recording into candidate decision-step records (pass A)."
    )
    parser.add_argument("--game-id", required=True)
    parser.add_argument("--guid", required=True)
    parser.add_argument(
        "--rows", required=True, metavar="START:END",
        help="inclusive zero-based row window. Editorial: see rule 1 in the module docstring.",
    )
    parser.add_argument(
        "--segment-prefix", required=True,
        help="segment ids are <prefix>-NN. The hand-built records use semantic names "
             "(approach, recovery) which are an annotator's reading, not a measurement.",
    )
    parser.add_argument("--slug", help="episode filename slug; defaults to <prefix>-<start>-<end>")
    parser.add_argument("--recordings-dir", type=Path, default=DEFAULT_RECORDINGS)
    parser.add_argument("--dispatch-dir", type=Path, default=DEFAULT_DISPATCH)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_EPISODES)
    parser.add_argument("--stdout", action="store_true", help="print records instead of writing")
    args = parser.parse_args(argv)

    start, end = parse_window(args.rows)
    recording = args.recordings_dir / args.game_id / f"{args.guid}.ndjson"
    if not recording.is_file():
        raise SystemExit(
            f"segment.py: no recording at {recording}\n"
            f"  pull it with: python3.13 tools/replay_scrape.py guid {args.guid}"
        )
    table_path = args.dispatch_dir / f"{args.game_id}.json"
    if not table_path.is_file():
        raise SystemExit(
            f"segment.py: no dispatch table at {table_path}\n"
            f"  pass B builds one per game; a record cannot cite source without it"
        )
    dispatch = json.loads(table_path.read_text())

    rows = load_rows(recording, max(0, start - MAX_FRAME_LOOKBACK), end)
    if end >= len(rows):
        raise SystemExit(
            f"segment.py: --rows {args.rows} runs past the recording, which has {len(rows)} rows"
        )
    check_levels_monotonic(rows, start, end)

    records = []
    for ordinal, (indices, reason) in enumerate(cut_segments(rows, start, end)):
        segment_id = f"{args.segment_prefix}-{ordinal:02d}"
        for index in indices:
            records.append(
                build_record(rows, index, args.game_id, args.guid, segment_id, reason, dispatch)
            )

    lines = [json.dumps(record) for record in records]
    if args.stdout:
        print("\n".join(lines))
    else:
        slug = args.slug or f"{args.segment_prefix}-{start}-{end}"
        out_path = args.out_dir / f"{args.game_id}__{args.guid}__{slug}{CANDIDATE_SUFFIX}"
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text("\n".join(lines) + "\n")
        print(f"wrote {len(records)} candidate record(s) to {out_path}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
