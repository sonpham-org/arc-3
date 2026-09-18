#!/usr/bin/env python3
# Author: Claude Opus 5 (Bubba)
# Date: 18-September-2026
# PURPOSE: Convert the Boss's human ARC-3 replay recordings
#   (`datasets/decision-steps/v0/recordings/<game>-<build>/<guid>.ndjson`) into the exact
#   SFT record shape `distill/extract_sft.py` already emits, so human demonstrations and
#   model rollouts land in one corpus the distill trainer (`distill/sft_batch.py`) can eat
#   unchanged. Drives the harness's own transcript reconstructor
#   (`inference.tools.traces._messages_from_sections`), the harness's own user-prompt
#   builder (`inference.agent.tool_agent.ToolAgent._build_user_prompt`), the harness's
#   own system prompt (`tool_agent._build_system_prompt`) and the harness's own board
#   renderer (via `extract_sft._ImageStore` / `_attach_images`) to avoid train/serve skew.
#   Run identity (which guid cleared which level) comes from arc-explainer's
#   `shared/arc3Games/humanPlay.generated.json`.
# SRP/DRY check: Pass -- no message format, no prompt text and no PNG encoder is
#   re-implemented here; all four are imported from the serving path. This module only
#   segments recordings into runs, cuts them into levels, prunes failed attempts, aligns
#   the observation chain, windows each level to the serve-time history depth, and emits.
#   `extract_sft.py` is not modified. The window size is not a guess: it is read off
#   `tool_agent._PERSISTENT_HISTORY_ASSISTANT_TURNS`, the serving path's own bound.
"""Human replay recordings -> `extract_sft.py` SFT records.

WHAT A RECORDING IS
    One JSON object per line, `{"timestamp", "data"}`. `data` carries `game_id`, `state`,
    `levels_completed`, `win_levels`, `action_input {id, data, reasoning}`, `guid`,
    `full_reset`, `available_actions` and `frame`. `frame` is the ANIMATION frame list for
    that one action (1..372 entries observed); `frame[-1]` is the settled board.

THE FOUR THINGS THAT WOULD SILENTLY POISON THE CORPUS, AND WHAT IS DONE ABOUT THEM

  1. OBSERVATION ALIGNMENT. The board stored on row k is the board row k's action
     PRODUCED. Proven empirically, game-agnostically, over all 18 recordings: group the
     non-full `RESET` rows by level; in all 28 groups with more than one reset, every
     reset row carries a byte-identical 64x64 board (the level's start state), and 0 of
     119 reset rows carry the board that existed immediately before the reset. If the
     stored board were the observation, a reset row would carry whatever the player had
     flailed into; it never does. Therefore decision step k observes row k-1's settled
     board, and the chain seeds from the leading `full_reset` row's board.

  2. TRAIN/SERVE SKEW. Messages are not hand-rolled. A per-step transcript is synthesized
     in the harness's own labeled-section format and handed to `_messages_from_sections`,
     the same reconstructor `extract_sft.py` drives. The system prompt is
     `_build_system_prompt()` verbatim. The user prompt is `_build_user_prompt()` verbatim,
     called with a shim whose only job is to report an empty knowledge ledger (that method
     touches no other attribute of `self`). The assistant turn is a `python` tool call in
     the qwen3_coder markup the harness emits, whose code is the `action([...])` call the
     harness executes. There is NO reasoning and NO assistant text on a human turn -- the
     Boss's per-move rationale was never recorded and is not invented here.

     KNOWN, DELIBERATE ASYMMETRY: the serve-time `python` tool takes two parameters,
     `code` and `world_model`, and the user prompt demands the ledger before acting. A
     human demo has no ledger, so these records emit `code` only. That is the single
     largest gap between a human record and a model record in this corpus.

  3. RESETS AND DEATHS. Two distinct things wear the word "reset":
       - `full_reset: true` restarts the whole GAME. One `<guid>.ndjson` can therefore hold
         several attempts; `humanPlay.generated.json` splits them into separate `runs`
         entries (only s5i5/850dee42 does this: runIndex 1 GAME_OVER, runIndex 2 WIN).
         Segments are split on these rows and the winning segment is selected by an exact
         predicate, not by runIndex.
       - `action_input.id == "RESET"` with `full_reset: false` restarts the current LEVEL.
     A third marker exists and is not called a reset: a row with `state: GAME_OVER` and an
     EMPTY `frame` (7 rows across the 18 recordings). The player died; the next row is a
     level `RESET`.
     Both level-restart markers END A FAILED ATTEMPT. Moves made before them did not lead
     to the clear, so within each level only the suffix after the LAST marker is kept, and
     the marker row itself is dropped too (keeping it would demonstrate "reset here" while
     hiding the failure that motivated it). This is a deliberate loss of rows.

  4. LEVEL BOUNDARIES. A row whose `levels_completed` reaches the current level number is
     the action that cleared it. Empty-frame death rows report `levels_completed: 0`
     spuriously and are excluded from the count. With that one exclusion the per-level row
     counts reproduce `humanPlay.generated.json`'s `levelActions[]` EXACTLY for all 18
     recordings, and `resets` matches the non-full RESET count exactly for all 18. The
     converter asserts both and fails loudly on a mismatch.

  5. RECORD LENGTH vs SERVE-TIME HISTORY. A whole cleared level can run to hundreds of
     moves; at serve time the agent never sees that. `ToolAgent._persistent_history_messages`
     carries at most `_PERSISTENT_HISTORY_ASSISTANT_TURNS` (= 30) assistant turns into the
     next request, and everything older is folded into the knowledge ledger and evicted. So
     by default each level record is cut to the LAST `--window-turns` decision steps, the
     last of which is the move that cleared the level. `--whole-level` restores the
     un-windowed PR #48 behaviour without a code edit.

     A second, looser bound also exists at serve time and is NOT what sets the default: the
     request is first trimmed to `_context_budget_tokens` (LOCAL_ANALYZER_CONTEXT_WINDOW
     32768 - reply reserve 512 - safety 512 = 31,744), dropping to a 0.6 low-water mark of
     19,046 once it overflows. That bound is token-based and environment-driven; the 30-turn
     bound is a hard module constant and is applied after it. `--window-turns` honours the
     turn bound; section 8 of the write-up reports how the windowed corpus sits against the
     token bound.

Usage:
    MULTIMODAL_CONTEXT=current_grid python distill/recordings_to_sft.py \
        --recordings-dir ../datasets/decision-steps/v0/recordings \
        --human-play ~/GitHub/arc-explainer/shared/arc3Games/humanPlay.generated.json \
        --out ../scratch/sft_human.jsonl --images-dir ../scratch/sft_human_images
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Iterator

_PKG_ROOT = Path(__file__).resolve().parents[1]
if str(_PKG_ROOT) not in sys.path:
    sys.path.insert(0, str(_PKG_ROOT))

# The harness reads its multimodal/frame/reasoning switches from the environment at call
# time. A bare shell leaves MULTIMODAL_CONTEXT unset, which silently strips the "User turns
# include an attached image" block out of the system prompt while this module still attaches
# one image per user turn. Default it on here; an explicit env value still wins.
os.environ.setdefault("MULTIMODAL_CONTEXT", "current_grid")

from inference.agent.action_names import to_model_action  # noqa: E402
from inference.agent.tool_agent import (  # noqa: E402
    ToolAgent,
    _build_system_prompt,
    MULTIMODAL_CONTEXT_ADDENDUM,
    # The serve-time history depth. Imported, not copied, so a change to the serving
    # path moves the corpus with it instead of silently drifting from it.
    _PERSISTENT_HISTORY_ASSISTANT_TURNS as SERVE_HISTORY_ASSISTANT_TURNS,
)
from inference.tools.traces import _messages_from_sections  # noqa: E402

from extract_sft import _ImageStore, _attach_images, _count_assistant_turns  # noqa: E402


# --------------------------------------------------------------------------- #
# Recording rows
# --------------------------------------------------------------------------- #
def _load_rows(path: Path) -> list[dict[str, Any]]:
    """The `data` payload of every well-formed line, in file order.

    Some recordings in this tree begin with a scorecard header line that has no `data`
    key (e.g. tu93-0768757b/8ad67f0c-677c...). None of the 18 winning recordings do, but
    the guard is cheap and the alternative is a KeyError mid-corpus.
    """
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            data = obj.get("data")
            if isinstance(data, dict):
                rows.append(data)
    return rows


def _settled_board(row: dict[str, Any]) -> list | None:
    """`frame[-1]`, the settled board, or None when the engine returned no frame."""
    frame = row.get("frame")
    if not isinstance(frame, list) or not frame:
        return None
    board = frame[-1]
    if not isinstance(board, list) or not board:
        return None
    return board


def _is_death(row: dict[str, Any]) -> bool:
    """A GAME_OVER row with no frame: the level attempt failed. Not billed as an action."""
    return _settled_board(row) is None


def _is_level_reset(row: dict[str, Any]) -> bool:
    return str(row.get("action_input", {}).get("id") or "") == "RESET" and not row.get("full_reset")


def _is_clearing_move(row: dict[str, Any], level: int) -> bool:
    """The move that advanced `levels_completed` past `level` -- the last move of the level.

    `cut_levels` closes a level on exactly this condition, so it always holds for the last
    row of `LevelCut.rows`. It is re-checked on `LevelCut.kept[-1]` before windowing,
    because a window is defined as "the N turns ENDING AT the clearing move": if pruning
    or filtering ever removed that move, every windowed record would end one move early and
    nothing in the counts would show it.
    """
    return _settled_board(row) is not None and int(row.get("levels_completed") or 0) >= level


def _billable(rows: list[dict[str, Any]]) -> int:
    """Actions as the ARC-3 scorecard counts them: every row but the leading full reset,
    minus the frameless death rows."""
    return sum(1 for r in rows[1:] if not _is_death(r))


def _segments(rows: list[dict[str, Any]]) -> list[list[dict[str, Any]]]:
    """Split a session file into one segment per full game reset."""
    starts = [i for i, r in enumerate(rows) if r.get("full_reset")]
    if not starts:
        return []
    out: list[list[dict[str, Any]]] = []
    for k, start in enumerate(starts):
        end = starts[k + 1] if k + 1 < len(starts) else len(rows)
        out.append(rows[start:end])
    return out


def select_win_segment(rows: list[dict[str, Any]], run: dict[str, Any]) -> list[dict[str, Any]]:
    """The one segment that is this `runs[]` entry. Exact predicate, no index heuristic.

    `runIndex` happens to equal the segment index on all 18 recordings, but it falls back
    silently to segment 0 whenever it does not, which is precisely how a corpus gets
    poisoned without anybody noticing. Match on the two facts the export actually asserts:
    terminal state and billable action count.
    """
    want_actions = int(run["actions"])
    want_state = str(run["state"])
    matches = [
        seg
        for seg in _segments(rows)
        if str(seg[-1].get("state") or "") == want_state and _billable(seg) == want_actions
    ]
    if len(matches) != 1:
        raise ValueError(
            f"{run['gameId']}-{run['build']} runIndex={run['runIndex']}: expected exactly one "
            f"segment with state={want_state} and {want_actions} billable actions, found "
            f"{len(matches)}"
        )
    return matches[0]


# --------------------------------------------------------------------------- #
# Level cutting + failed-attempt pruning
# --------------------------------------------------------------------------- #
class LevelCut(SimpleNamespace):
    level: int
    rows: list[dict[str, Any]]          # every row billed to this level, in order
    kept: list[dict[str, Any]]          # the successful attempt only
    observations: list[list]            # observation board per row in `kept`


def cut_levels(segment: list[dict[str, Any]], *, prune: bool = True) -> list[LevelCut]:
    """Split the winning segment into levels and prune each level's failed attempts.

    The observation chain is threaded across the WHOLE segment before any pruning, so a
    pruned level still starts from the board the player actually saw.
    """
    seed = _settled_board(segment[0])
    if seed is None:
        raise ValueError("segment does not start with a framed full-reset row")

    cuts: list[LevelCut] = []
    level = 1
    rows: list[dict[str, Any]] = []
    obs: list[list] = []
    prev_board = seed

    for row in segment[1:]:
        rows.append(row)
        obs.append(prev_board)
        board = _settled_board(row)
        if board is not None:
            prev_board = board
            if _is_clearing_move(row, level):
                cuts.append(_prune(level, rows, obs, prune=prune))
                level += 1
                rows, obs = [], []
    # Anything after the last clear is the tail of an unfinished level: dropped, because
    # `only_solved` semantics keep levels 1..levels_completed and nothing beyond.
    return cuts


def _prune(level: int, rows: list[dict[str, Any]], obs: list[list], *, prune: bool = True) -> LevelCut:
    """Keep only the suffix after the last failed-attempt marker on this level.

    `prune=False` keeps every framed row (the marker rows themselves are always dropped:
    a death row has no board to show, and a `RESET` demonstration without the visible
    failure that motivated it is a lie about the state the player was in).
    """
    start = 0
    if prune:
        for i, row in enumerate(rows):
            if _is_level_reset(row) or _is_death(row):
                start = i + 1
    kept = [(r, o) for r, o in zip(rows[start:], obs[start:]) if not _is_death(r) and not _is_level_reset(r)]
    return LevelCut(
        level=level,
        rows=rows,
        kept=[r for r, _ in kept],
        observations=[o for _, o in kept],
    )


# --------------------------------------------------------------------------- #
# Transcript synthesis (fed to the harness's own reconstructor)
# --------------------------------------------------------------------------- #
_TOOL_CALL_MARKUP = (
    "<tool_call>\n<function=python>\n<parameter=code>\n{code}\n</parameter>\n</function>\n</tool_call>"
)


class _LedgerShim:
    """The two attributes `_build_user_prompt` reads off `self`, both deliberately empty.

    A human demo carries no knowledge ledger, and inventing one would be the fabricated
    prose the brief forbids. `_oracle_rules_block` is the oracle arm's injected rulebook
    (`inference.agent.oracle_rules`); human demonstrations must never carry it, because
    this builder's output IS training data and the rulebook is the answer key. Declared
    here rather than read defensively so that a future field added to the user prompt
    fails loudly instead of silently dropping out of the corpus."""

    _oracle_rules_block = ""

    def _summarized_knowledge_lines(self) -> list[str]:
        return []


def _action_call_code(row: dict[str, Any]) -> tuple[str, str]:
    """`(model action label, the python the harness would have executed)`."""
    engine_id = str(row.get("action_input", {}).get("id") or "")
    label = to_model_action(engine_id)
    if label == "MOUSE":
        data = row.get("action_input", {}).get("data") or {}
        row_idx = int(data.get("y", 0))
        col_idx = int(data.get("x", 0))
        return label, (
            f"action([{{'action': 'MOUSE', 'row': {row_idx}, 'col': {col_idx}}}])"
        )
    return label, f"action(['{label}'])"


def _valid_actions(row: dict[str, Any]) -> list[str]:
    ids = row.get("available_actions") or []
    return [to_model_action(f"ACTION{int(i)}") for i in ids if isinstance(i, int)]


def _step_summary(row: dict[str, Any], label: str, level: int) -> dict[str, Any]:
    """The `previous_step_summary` the harness would have carried into the next turn."""
    return {
        "executed_count": 1,
        "executed_actions": [label],
        "run_complete": str(row.get("state") or "") == "WIN",
        "level_transition": bool(row.get("_level_transition")),
        "game_over": str(row.get("state") or "") == "GAME_OVER",
        "level": level,
    }


def _tool_result(row: dict[str, Any], label: str, board_changed: bool, cleared: bool) -> str:
    """The `action(...)` result dict, restricted to keys a recording can actually support.

    `reward` and the animation summary are omitted rather than guessed: the recording does
    not carry `number_of_levels` per-step reward scaling, and inventing numbers here would
    teach the model a value that never appears at serve time.
    """
    state = str(row.get("state") or "")
    return json.dumps(
        {
            "executed": True,
            "action_name": str(row.get("action_input", {}).get("id") or ""),
            "action_display": label,
            "state": state,
            "score": int(row.get("levels_completed") or 0),
            "valid_actions": _valid_actions(row),
            "board_changed": board_changed,
            "done": state == "WIN",
            # solver.py: `just_won_level and raw_state != WIN` -- the action that ends
            # the RUN reports run_complete/done, not level_completed.
            "level_completed": cleared and state != "WIN",
            "game_over": state == "GAME_OVER",
            "run_complete": state == "WIN",
        },
        ensure_ascii=True,
    )


def build_events(
    cut: LevelCut,
    *,
    system_prompt: str,
    action_offset: int,
    incoming_summary: dict[str, Any] | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any] | None]:
    """One `_messages_from_sections` event per kept decision step.

    `incoming_summary` is the previous level's last step summary. Without it the first turn
    of every level after the first renders "No previous action sequence was captured.",
    where the harness would have said "You have progressed to a new level!".
    """
    events: list[dict[str, Any]] = []
    prev_summary: dict[str, Any] | None = incoming_summary
    for i, (row, observation) in enumerate(zip(cut.kept, cut.observations)):
        label, code = _action_call_code(row)
        action_num = action_offset + i
        current_frame = SimpleNamespace(step=action_num, level=cut.level)
        user_prompt = ToolAgent._build_user_prompt(
            _LedgerShim(),
            action_num,
            valid_actions=_valid_actions(row),
            current_frame=current_frame,
            history_entries=[],
            previous_step_summary=prev_summary,
        )
        board = _settled_board(row)
        cleared = _is_clearing_move(row, cut.level)
        transcript = "\n".join(
            [
                "[SYSTEM PROMPT]",
                system_prompt,
                "",
                "[USER PROMPT]",
                user_prompt,
                "",
                "[TOOL CALL: python]",
                _TOOL_CALL_MARKUP.format(code=code),
                "",
                "[TOOL RESULT: python]",
                _tool_result(row, label, board != observation, cleared),
                "",
            ]
        )
        events.append(
            {
                "analysis_step": i + 1,
                "action_num": action_num,
                "transcript": transcript,
                "level": cut.level,
                "grid": observation,
            }
        )
        row["_level_transition"] = cleared
        prev_summary = _step_summary(row, label, cut.level)
    return events, prev_summary


def window_events(
    events: list[dict[str, Any]],
    *,
    window_turns: int,
) -> list[dict[str, Any]]:
    """The last `window_turns` decision steps, ending at the level's clearing move.

    Sliced AFTER `build_events` has run over the whole level, never during it. Each event's
    user prompt is built from the previous step's summary, so the first turn of a window
    still reports the action that actually preceded it -- exactly as a serve-time request
    does after the older turns have been evicted. Slicing inside the build loop would
    instead make the first windowed turn claim "no previous action sequence was captured",
    which is true of a level start and false of a mid-level window.

    `window_turns <= 0` means no window. The count is inclusive of the clearing move, which
    is how `ToolAgent._keep_recent_history_turns` counts: it keeps N assistant messages in
    total, the newest one included.
    """
    if window_turns <= 0 or len(events) <= window_turns:
        return events
    return events[-window_turns:]


# --------------------------------------------------------------------------- #
# Record building
# --------------------------------------------------------------------------- #
def _human_runs(human_play: Path) -> list[dict[str, Any]]:
    payload = json.loads(human_play.read_text(encoding="utf-8"))
    return [r for r in payload.get("runs", []) if str(r.get("state")) == "WIN"]


def build_records(
    *,
    recordings_dir: Path,
    human_play: Path,
    store: _ImageStore,
    system_prompt: str,
    exclude_games: frozenset[str] = frozenset(),
    prune_failed_attempts: bool = True,
    window_turns: int = SERVE_HISTORY_ASSISTANT_TURNS,
    stats: dict[str, Any] | None = None,
) -> Iterator[dict[str, Any]]:
    missing: list[str] = []
    for run in sorted(_human_runs(human_play), key=lambda r: (r["gameId"], r["runIndex"])):
        game_id = f"{run['gameId']}-{run['build']}"
        path = recordings_dir / game_id / f"{run['guid']}.ndjson"
        if not path.exists():
            missing.append(f"{game_id}/{run['guid'][:8]}")
            continue
        if run["gameId"].lower() in exclude_games:
            continue

        rows = _load_rows(path)
        segment = select_win_segment(rows, run)

        level_resets = sum(1 for r in segment if _is_level_reset(r))
        if level_resets != int(run["resets"]):
            raise ValueError(
                f"{game_id}: recording has {level_resets} level resets, export says {run['resets']}"
            )

        cuts = cut_levels(segment, prune=prune_failed_attempts)
        recorded = [len(c.rows) - sum(1 for r in c.rows if _is_death(r)) for c in cuts]
        expected = [int(n) for n in run["levelActions"][: len(recorded)]]
        if recorded != expected:
            raise ValueError(
                f"{game_id}: per-level action counts {recorded} != export levelActions {expected}"
            )
        if len(cuts) != int(run["levelsCompleted"]):
            raise ValueError(
                f"{game_id}: cut {len(cuts)} levels, export says {run['levelsCompleted']} cleared"
            )

        action_offset = 0
        carried: dict[str, Any] | None = None
        for cut in cuts:
            events, carried = build_events(
                cut,
                system_prompt=system_prompt,
                action_offset=action_offset,
                incoming_summary=carried,
            )
            action_offset += len(cut.rows)
            if not events:
                continue
            if not _is_clearing_move(cut.kept[-1], cut.level):
                raise ValueError(
                    f"{game_id} L{cut.level}: last kept row is not the clearing move, so a "
                    f"window ending at it would end early"
                )
            windowed = window_events(events, window_turns=window_turns)
            messages, _links = _messages_from_sections(windowed)
            if not messages or _count_assistant_turns(messages) == 0:
                continue
            n_images = _attach_images(messages, store)
            if stats is not None:
                stats.setdefault("dropped_rows", 0)
                stats.setdefault("windowed_rows", 0)
                stats["dropped_rows"] += len(cut.rows) - len(cut.kept)
                # Counted apart from the prune: the prune drops moves that did not lead to
                # the clear, the window drops moves that did but that serve time would have
                # evicted. Folding them together would hide which decision costs what.
                stats["windowed_rows"] += len(events) - len(windowed)
            yield {
                # The guid, not runIndex, is what makes this unique: sb26-7fbdac44 has TWO
                # winning runs that both carry runIndex 0 (different cards, different guids).
                "id": f"human/{game_id}/{run['guid'][:8]}/L{cut.level}",
                "game_id": game_id,
                "pass_index": int(run["runIndex"]),
                "run": "human",
                "level": cut.level,
                "solved": True,
                "level_actions": expected[cut.level - 1],
                "num_messages": len(messages),
                "num_assistant_turns": _count_assistant_turns(messages),
                "num_images": n_images,
                "messages": messages,
            }
    if stats is not None:
        stats["missing_recordings"] = missing


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    p.add_argument("--recordings-dir", required=True)
    p.add_argument("--human-play", required=True, help="arc-explainer humanPlay.generated.json")
    p.add_argument("--out", required=True)
    p.add_argument("--images-dir", default=None)
    p.add_argument("--upscale", type=int, default=4, help="Match extract_sft.py's default.")
    p.add_argument("--style", choices=["plain", "outline"], default="plain")
    p.add_argument("--inline-images", action="store_true")
    p.add_argument(
        "--tool-output-tokens",
        type=int,
        default=1024,
        help="LOCAL_ANALYZER_TOOL_OUTPUT_TOKENS the serving run uses; shapes one system-prompt line.",
    )
    p.add_argument("--exclude-games", default=None, help="Comma-separated bare game codes to drop.")
    p.add_argument(
        "--keep-failed-attempts",
        action="store_true",
        help="Keep the moves made before a level RESET or death. Off by default: those moves "
        "did not lead to the clear, so they are not demonstrations of solving the level.",
    )
    p.add_argument(
        "--window-turns",
        type=int,
        default=SERVE_HISTORY_ASSISTANT_TURNS,
        help="Keep only the last N decision steps of each level, ending at the clearing "
        f"move. Default {SERVE_HISTORY_ASSISTANT_TURNS} = tool_agent."
        "_PERSISTENT_HISTORY_ASSISTANT_TURNS, the number of assistant turns the serving "
        "path carries into the next request.",
    )
    p.add_argument(
        "--whole-level",
        action="store_true",
        help="Emit the whole cleared level in one record, as before windowing. Off by "
        "default: a record longer than the serve-time history trains on a context the "
        "model never sees.",
    )
    p.add_argument("--stats-only", action="store_true")
    args = p.parse_args(argv)
    if args.whole_level:
        args.window_turns = 0
    elif args.window_turns <= 0:
        p.error("--window-turns must be positive; use --whole-level to disable windowing")
    return args


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    out_path = Path(args.out)
    images_dir = (
        Path(args.images_dir) if args.images_dir else out_path.with_name(out_path.stem + "_images")
    )
    system_prompt = _build_system_prompt(tool_output_tokens=args.tool_output_tokens)
    if MULTIMODAL_CONTEXT_ADDENDUM.strip() not in system_prompt:
        raise SystemExit(
            "system prompt has no multimodal block but every user turn carries an image -- "
            "set MULTIMODAL_CONTEXT=current_grid"
        )

    store = _ImageStore(images_dir, args.upscale, args.style, args.inline_images)
    exclude = frozenset(
        c.strip().lower() for c in (args.exclude_games or "").split(",") if c.strip()
    )
    stats: dict[str, Any] = {}
    per_game: dict[str, dict[str, int]] = {}
    totals = {"records": 0, "turns": 0, "images": 0}

    fh = None if args.stats_only else out_path.open("w", encoding="utf-8")
    try:
        for rec in build_records(
            recordings_dir=Path(args.recordings_dir),
            human_play=Path(args.human_play).expanduser(),
            store=store,
            system_prompt=system_prompt,
            exclude_games=exclude,
            prune_failed_attempts=not args.keep_failed_attempts,
            window_turns=args.window_turns,
            stats=stats,
        ):
            totals["records"] += 1
            totals["turns"] += rec["num_assistant_turns"]
            totals["images"] += rec["num_images"]
            bucket = per_game.setdefault(rec["game_id"], {"records": 0, "turns": 0, "actions": 0})
            bucket["records"] += 1
            bucket["turns"] += rec["num_assistant_turns"]
            bucket["actions"] += int(rec["level_actions"] or 0)
            if fh is not None:
                fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
    finally:
        if fh is not None:
            fh.close()

    print("=" * 72)
    print(f"records (cleared levels) : {totals['records']}")
    print(f"assistant turns          : {totals['turns']}")
    print(f"user turns with an image : {totals['images']}  (unique PNGs {store.count})")
    print(f"rows dropped as failed attempts : {stats.get('dropped_rows', 0)}")
    if args.window_turns > 0:
        print(
            f"rows dropped outside the {args.window_turns}-turn window : "
            f"{stats.get('windowed_rows', 0)}"
        )
    else:
        print("window                          : none (--whole-level)")
    if stats.get("missing_recordings"):
        print(f"runs with no recording on disk  : {', '.join(stats['missing_recordings'])}")
    print("-" * 72)
    print(f"{'game':16s} {'records':>8s} {'turns':>7s} {'billed':>7s} {'kept%':>7s}")
    for game, b in sorted(per_game.items()):
        pct = (b["turns"] / b["actions"] * 100.0) if b["actions"] else 0.0
        print(f"{game:16s} {b['records']:8d} {b['turns']:7d} {b['actions']:7d} {pct:6.1f}%")
    if not args.stats_only:
        print(f"\nwrote  : {out_path}")
        if not args.inline_images:
            print(f"images : {images_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
