#!/usr/bin/env python3
"""Turn finished decision-step records into training examples the distiller can eat.

This is the bridge the corpus was missing. Steps 1-4 built a labelling machine whose output
nothing downstream read: ARC3-Inference/distill/extract_sft.py has never heard of
datasets/decision-steps/, so a finished record was a document, not training data.

WHAT THIS IS FOR, because it decides every design choice below. The distiller's own SFT builder
rejection-samples the harness's play and keeps only turns on SOLVED levels -- so it structurally
throws away every moment where a player was wrong and then fixed it. That moment is the one
thing the decision-step corpus holds and nothing else in the tree can produce. Examples carrying
it are marked `teaches_recovery` so a training mix can weight them; that flag is the payload.

FIDELITY, stated rather than assumed. A record is human play, so there is no model turn to
replay -- the assistant turn here is SYNTHESISED from the annotated rationale. Two things are
therefore taken from the harness rather than invented, because getting them wrong is train/serve
skew:
  * the board is rendered by inference.utils.grid_utils.format_grid_ascii, the same function
    that renders it at serve time, and the user turn matches RuntimeState.__str__'s layout;
  * actions are emitted in MODEL vocabulary via inference.agent.action_names (LEFT, not
    ACTION3). Records store engine names; the model has never seen one.
The system prompt is NOT taken from the harness: the live prompt is bound to the Python-sandbox
tool loop and is config-dependent. --system-prompt pins it to whatever the actual fine-tune
uses. The built-in default is a stand-in and says so in the output's `system_prompt_source`.

SRP/DRY check: Pass - validate.py owns schema and frame resolution (its FrameResolver.resolve is
used here, not reimplemented), segment.py owns segmentation, this owns only the record -> example
conversion.

Usage:
    python3.13 tools/build_sft.py --out /tmp/decision_sft.jsonl
    python3.13 tools/build_sft.py --out /tmp/x.jsonl --stats-only
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Iterator

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "datasets" / "decision-steps"))
sys.path.insert(0, str(REPO_ROOT / "ARC3-Inference"))

from validate import CANDIDATE_SUFFIX, FrameResolver  # noqa: E402
from inference.agent.action_names import ENGINE_TO_MODEL_ACTION, to_model_action  # noqa: E402
from inference.utils.grid_utils import ARC_COLOR_LEGEND, format_grid_ascii  # noqa: E402

DEFAULT_EPISODES = REPO_ROOT / "datasets" / "decision-steps" / "v0" / "episodes"
DEFAULT_RECORDINGS = REPO_ROOT / "datasets" / "decision-steps" / "v0" / "recordings"
MANIFESTS = (
    REPO_ROOT / "datasets" / "decision-steps" / "published-replays.json",
    REPO_ROOT / "datasets" / "decision-steps" / "first-party-replays.json",
)

#: Stand-in only. The real fine-tune must pass --system-prompt with the config it ships.
DEFAULT_SYSTEM_PROMPT = (
    "You are playing a grid puzzle game. Each turn you see the current board and choose one "
    "action. State what you expect the board to do before you act, then act. If the board does "
    "not do what you expected, say so and change your plan.\n\n"
    f"Board colours: {ARC_COLOR_LEGEND}"
)

#: The judgment fields. A candidate from segment.py has none of them and must never train.
JUDGMENT_FIELDS = ("rationale", "expected_observation")


#: Engine action names as they appear in ANNOTATOR PROSE. Annotators write records against the
#: game source, which speaks ACTION1..ACTION7, but the model has only ever seen UP/LEFT/MOUSE and
#: so on. Showing it "ACTION3 moves left" in the same turn where it must answer "LEFT" is exactly
#: the train/serve skew this bridge exists to avoid, and it is easy to miss because the prose
#: reads fine. Found by a test, not by review. ACTION7 and RESET map to themselves and so are
#: left alone by construction.
_ENGINE_TOKEN_RE = re.compile(r"\bACTION[1-7]\b")


def to_model_vocab(text: str) -> str:
    """Rewrite engine action names in free text into the labels the model actually uses."""
    return _ENGINE_TOKEN_RE.sub(lambda m: ENGINE_TO_MODEL_ACTION.get(m.group(0), m.group(0)), text)


def solved_levels_by_guid(manifests: tuple[Path, ...] = MANIFESTS) -> dict[str, int]:
    """run guid -> how many levels that run actually completed."""
    solved: dict[str, int] = {}
    for path in manifests:
        if not path.is_file():
            continue
        blob = json.loads(path.read_text(encoding="utf-8"))
        for run in blob.get("replays") or blob.get("runs") or []:
            guid = run.get("guid")
            if isinstance(guid, str):
                solved[guid] = run.get("levels_completed") or 0
    return solved


def level_was_solved(record: dict, solved: dict[str, int]) -> bool | None:
    """Did the player go on to COMPLETE the level this record was taken on?

    This is the cull, and it is the same rule the distiller already applies to its own play
    (extract_sft.py keeps turns whose level <= levels_completed). Keeping a losing run wholesale
    would train the model to lose. Throwing the whole run away instead is the opposite mistake:
    a player who cleared four levels and then died on the fifth produced four levels of good
    material, and 37% of the eligible published material sits in runs that never won.

    So the unit is the LEVEL, not the run. A stumble on a level that was then cleared is a
    recovery that demonstrably worked. A stumble on the level the player died on is flailing,
    and it teaches flailing.

    `level` is levels_completed, a COUNT, so a record written during play of the Nth level reads
    N-1. The level being played was cleared if the run's final count ever got past it.
    Returns None when the run is in neither manifest and the question cannot be answered.
    """
    guid = (record.get("source") or {}).get("recording_guid")
    level = record.get("level")
    if guid not in solved or not isinstance(level, int):
        return None
    return solved[guid] > level


def _action_text(action: dict[str, Any]) -> str:
    """Render an action the way the model is required to emit it."""
    label = to_model_action(action.get("action"))
    args = action.get("args")
    if isinstance(args, dict) and "row" in args and "col" in args:
        return f"{label}({args['row']},{args['col']})"
    return label


def _user_turn(record: dict, grid: list[list[int]]) -> str:
    """The board, laid out as RuntimeState.__str__ lays it out, plus what the player knew."""
    rows = len(grid)
    cols = max((len(r) for r in grid), default=0)
    parts = [
        f"Level: {record.get('level')}",
        f"Grid shape: {rows} x {cols}",
        f"Grid contents:\n{format_grid_ascii(grid)}",
    ]
    memory = record.get("memory_in") or {}
    if memory.get("goal"):
        parts.append(f"Goal: {to_model_vocab(memory['goal'])}")
    if memory.get("known_mechanics"):
        parts.append("What you have established:\n" + "\n".join(f"- {to_model_vocab(m)}" for m in memory["known_mechanics"]))
    if memory.get("hypotheses"):
        parts.append("Working hypotheses:\n" + "\n".join(f"- {to_model_vocab(h)}" for h in memory["hypotheses"]))
    if memory.get("current_plan"):
        parts.append(f"Current plan: {to_model_vocab(memory['current_plan'])}")
    last = record.get("last_action")
    if isinstance(last, dict) and last.get("action"):
        result = record.get("last_result") or {}
        changed = "the board changed" if result.get("board_changed") else "the board did not change"
        line = f"Your last action was {_action_text(last)} and {changed}."
        if result.get("run_ended"):
            line += " That action ENDED THE RUN - the board is dead and will not respond to ordinary moves."
        parts.append(line)
    return "\n\n".join(parts)


def _assistant_turn(record: dict) -> str:
    """Reasoning then action. The expectation is stated BEFORE the action, on purpose --
    that ordering is what makes the following tool result able to refute it."""
    decision = record.get("decision") or {}
    lines = [to_model_vocab(decision.get("rationale", "").strip())]
    if decision.get("expected_observation"):
        lines.append(f"I expect: {to_model_vocab(decision['expected_observation'].strip())}")
    plan = (decision.get("memory_out") or {}).get("current_plan")
    if plan:
        lines.append(f"Plan after this: {to_model_vocab(plan.strip())}")
    lines.append(f"Action: {_action_text(decision.get('action') or {})}")
    return "\n\n".join(p for p in lines if p)


def _tool_turn(record: dict) -> str:
    """What the next frame actually showed, and the verdict on the expectation."""
    outcome = record.get("outcome") or {}
    observed = to_model_vocab(str(outcome.get("observed", "")).strip())
    held = outcome.get("expectation_held")
    if held is True:
        verdict = "That matches what you expected."
    elif held is False:
        verdict = "That does NOT match what you expected. Revise your model of this game."
    else:
        verdict = "Whether this matches your expectation was not determined."
    return f"{observed}\n\n{verdict}"


def is_finished(record: dict) -> bool:
    """A record trains only if a mind filled the judgment fields."""
    decision = record.get("decision") or {}
    return all(str(decision.get(f) or "").strip() for f in JUDGMENT_FIELDS)


def build_example(
    record: dict,
    grid: list[list[int]],
    system_prompt: str,
    prompt_source: str,
    solved: bool | None = None,
) -> dict:
    decision = record.get("decision") or {}
    outcome = record.get("outcome") or {}
    corrected = record.get("corrected_decision")
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": _user_turn(record, grid)},
        {"role": "assistant", "content": _assistant_turn(record)},
        {"role": "tool", "content": _tool_turn(record)},
    ]
    # The payload. A falsified expectation is the signal the big pipeline cannot produce; when a
    # verified correction follows it, the example teaches the whole recover-after-being-wrong arc.
    # A falsified expectation only teaches recovery if the player then RECOVERED -- which the
    # level being cleared afterwards is the evidence for. Without this gate the flag also marks
    # the death spiral on the level the player never solved, and weighting a training mix
    # towards those would teach exactly the behaviour the corpus exists to remove.
    falsified = outcome.get("expectation_held") is False and solved is not False
    if falsified and isinstance(corrected, dict):
        messages.append({"role": "assistant", "content": _assistant_turn({"decision": corrected})})
    source = record.get("source") or {}
    return {
        "id": f"{record.get('game_id')}/{source.get('recording_guid')}/{source.get('row_index')}",
        "game_id": record.get("game_id"),
        "level": record.get("level"),
        "tier": record.get("tier"),
        "segment_id": (record.get("segment") or {}).get("id"),
        "expectation_held": outcome.get("expectation_held"),
        "level_was_solved": solved,
        "teaches_recovery": bool(falsified),
        "has_verified_correction": bool(falsified and isinstance(corrected, dict)),
        "action": _action_text(decision.get("action") or {}),
        "action_role_source": record.get("action_role_source"),
        "rationale_provenance": record.get("rationale_provenance"),
        "system_prompt_source": prompt_source,
        "num_messages": len(messages),
        "messages": messages,
    }


def iter_records(episodes_dir: Path) -> Iterator[tuple[Path, int, dict]]:
    """Finished records only. Candidates are skipped the way validate.py skips them."""
    for path in sorted(episodes_dir.glob("*.jsonl")):
        if path.name.endswith(CANDIDATE_SUFFIX):
            continue
        for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if line.strip():
                yield path, lineno, json.loads(line)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--episodes-dir", type=Path, default=DEFAULT_EPISODES)
    p.add_argument("--recordings-dir", type=Path, default=DEFAULT_RECORDINGS)
    p.add_argument("--out", type=Path, help="Output JSONL (omit with --stats-only).")
    p.add_argument("--system-prompt-file", type=Path, help="Pin the system prompt to the fine-tune's own.")
    p.add_argument(
        "--keep-unsolved",
        action="store_true",
        help="Keep records from levels the player never cleared. Off by default: those are the "
             "flailing, and training on them teaches flailing.",
    )
    p.add_argument("--stats-only", action="store_true")
    args = p.parse_args(argv)
    if not args.out and not args.stats_only:
        p.error("--out is required unless --stats-only")

    if args.system_prompt_file:
        system_prompt = args.system_prompt_file.read_text(encoding="utf-8")
        prompt_source = str(args.system_prompt_file)
    else:
        system_prompt, prompt_source = DEFAULT_SYSTEM_PROMPT, "build_sft.py:DEFAULT_SYSTEM_PROMPT (stand-in)"

    resolver = FrameResolver(args.recordings_dir)
    solved_by_guid = solved_levels_by_guid()
    examples, skipped, failures, unsolved = [], 0, [], 0
    for path, lineno, record in iter_records(args.episodes_dir):
        if not is_finished(record):
            skipped += 1
            continue
        try:
            grid = resolver.resolve(record)
        except ValueError as exc:
            failures.append(f"{path.name}:{lineno}: {exc}")
            continue
        solved = level_was_solved(record, solved_by_guid)
        if solved is False and not args.keep_unsolved:
            unsolved += 1
            continue
        examples.append(build_example(record, grid, system_prompt, prompt_source, solved))

    recovery = [e for e in examples if e["teaches_recovery"]]
    print(f"examples:          {len(examples)}")
    print(f"  teach recovery:  {len(recovery)} ({sum(e['has_verified_correction'] for e in recovery)} with a verified correction)")
    print(f"  games:           {len({e['game_id'] for e in examples})}")
    print(f"unfinished skipped:{skipped}")
    print(f"unsolved culled:   {unsolved}")
    if failures:
        print(f"UNRESOLVED ({len(failures)}):")
        for f in failures:
            print(f"  {f}")

    if args.out and not args.stats_only:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        with args.out.open("w", encoding="utf-8") as fh:
            for e in examples:
                fh.write(json.dumps(e, ensure_ascii=False) + "\n")
        print(f"wrote {len(examples)} examples to {args.out}")
    # An unresolved reference means a record points at a board nobody can see. Fail loudly.
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
