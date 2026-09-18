#!/usr/bin/env python3.13
"""
Author: Claude Opus 5 (Bubba subagent)
Date: 18-September-2026
PURPOSE: Dry build of both oracle-test arms' prompts, with no model, no server and no game
engine, proving four things before a single GPU second is spent
(docs/plans/2026-09-18-oracle-test-plan.md section 6 step 2):

  1. With ARC3_ORACLE_RULES_DIR set, every game's first user turn carries its OWN rulebook,
     headed with the treatment marker, ahead of the frame.
  2. With it unset, no user turn carries the marker -- arm B is untouched.
  3. The block is re-sent on later turns, not only the first, which is what makes it survive
     _trim_messages_for_context dropping the oldest history block.
  4. scripts/check_oracle_marker.sh returns the expected counts on the prompt logs both arms
     produce, using the real writer (tool_agent._write_prompt_log_snapshot).
  5. The block is stripped from turns filed into history, so exactly ONE copy is in context
     at a time and arm O is not silently trading real history for repeated rulebook text.
  6. What that stripping costs the server's prefix cache, as a measured number rather than an
     assertion: scripts/test_prefix_stability.py exercises _trim_messages_for_context
     directly and so never sees this path.

Prompts are written into a temporary run tree shaped like a real one
(<run>/artifacts/<game>_p0_tool_runtime_state.json, <run>/prompts/<game>_p0.log) so the guard
runs against the same paths it will on a108.

Usage:
  python3.13 scripts/test_oracle_injection.py                    # slippery seven
  python3.13 scripts/test_oracle_injection.py --games ar25,cd82
SRP/DRY check: Pass -- the only test of the oracle injection. It drives tool_agent's own
prompt builder and prompt-log writer rather than restating either.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace

_PKG_ROOT = Path(__file__).resolve().parents[1]
if str(_PKG_ROOT) not in sys.path:
    sys.path.insert(0, str(_PKG_ROOT))

from inference.agent import oracle_rules  # noqa: E402
from inference.agent.tool_agent import ToolAgent, _write_prompt_log_snapshot  # noqa: E402

REPO_ROOT = _PKG_ROOT.parent
DEFAULT_RULES_DIR = REPO_ROOT / "datasets" / "explainer-games" / "rulebooks"
SLIPPERY_SEVEN = ["dc22", "g50t", "m0r0", "sc25", "sk48", "tn36", "tr87"]
GUARD = _PKG_ROOT / "scripts" / "check_oracle_marker.sh"

# Stand-ins for the real content hashes; only the leading code is read.
_FAKE_BUILD = {code: f"{code}-{i:08x}" for i, code in enumerate(SLIPPERY_SEVEN, start=1)}


def _agent() -> ToolAgent:
    """A ToolAgent with only the attributes the prompt path touches.

    __init__ opens no sockets, but it does want a model endpoint and a run config; the
    prompt builder needs neither, and building one by hand keeps this test free of any
    serving dependency.
    """
    agent = ToolAgent.__new__(ToolAgent)
    agent._oracle_rules_block = ""
    agent._oracle_rules_state_path = None
    agent._summarized_knowledge = {}
    agent._summarized_knowledge_lines = lambda: []
    agent._context_budget_tokens = 32768 - 4096 - 512
    return agent


def _history_keeps_one_copy(agent: ToolAgent, turns: list[str], marker: str) -> tuple[int, int]:
    """(copies in the retained history, copies in the live request) after a few turns.

    Drives the real _persistent_history_messages, which is the only path by which a turn
    becomes history.
    """
    messages: list[dict] = [{"role": "system", "content": "(system)"}]
    for i, text in enumerate(turns):
        messages.append({"role": "user", "content": text})
        messages.append({"role": "assistant", "content": f"(assistant turn {i})"})
    history = agent._persistent_history_messages(messages, tools=None)
    in_history = sum(
        str(m.get("content", "")).count(marker) for m in history
    )
    in_request = sum(str(m.get("content", "")).count(marker) for m in [*history, {"role": "user", "content": turns[-1]}])
    return in_history, in_request


def _turn(agent: ToolAgent, state_path: Path, action_num: int) -> str:
    agent._ensure_oracle_rules(state_path)
    return ToolAgent._build_user_prompt(
        agent,
        action_num,
        valid_actions=["UP", "DOWN", "LEFT", "RIGHT"],
        current_frame=SimpleNamespace(step=action_num, level=1),
        history_entries=[],
        previous_step_summary=None,
    )


def _build_arm(run_root: Path, games: list[str], rules_dir: Path | None) -> dict[str, list[str]]:
    """Render turns 0 and 5 per game and write each game's prompt log. Returns the turns."""
    (run_root / "artifacts").mkdir(parents=True, exist_ok=True)
    if rules_dir is None:
        os.environ.pop("ARC3_ORACLE_RULES_DIR", None)
    else:
        os.environ["ARC3_ORACLE_RULES_DIR"] = str(rules_dir)

    turns: dict[str, list[str]] = {}
    for code in games:
        stem = f"{_FAKE_BUILD.get(code, code)}_p0"
        state_path = run_root / "artifacts" / f"{stem}_tool_runtime_state.json"
        state_path.write_text("{}", encoding="utf-8")
        agent = _agent()
        rendered = [_turn(agent, state_path, n) for n in (0, 5)]
        turns[code] = rendered
        # Shape the snapshot the way analyze() does: the retained history (which has been
        # through _persistent_history_messages, so arm O's is already stripped) followed by
        # the live user turn. Writing the raw turns instead would show the guard two copies
        # of a block a real run only ever sends once.
        agent._context_budget_tokens = 32768 - 4096 - 512
        history = agent._persistent_history_messages(
            [
                {"role": "system", "content": "(system prompt omitted in the dry build)"},
                {"role": "user", "content": rendered[0]},
                {"role": "assistant", "content": "(assistant turn omitted)"},
            ],
            tools=None,
        )
        # The real writer, so the guard reads the real rendering. Mode "w": the log holds
        # the latest snapshot, which is what the guard greps on a live run.
        _write_prompt_log_snapshot(
            run_root / "prompts" / f"{stem}.log",
            model_id="dry-run",
            base_url="dry-run",
            display_action_num=5,
            analysis_step=5,
            request_index=0,
            messages=[
                {"role": "system", "content": "(system prompt omitted in the dry build)"},
                *history,
                {"role": "user", "content": rendered[1]},
            ],
            tools=[],
            tool_choice=None,
            transcript="(dry build)",
        )
    return turns


def prefix_reuse(block: str, turns: int = 40) -> tuple[float, int]:
    """(mean shared-prefix fraction, turns whose previous request survived intact).

    Stripping the block on the way into history means the message the model saw last turn is
    re-sent one block shorter, so the PREVIOUS REQUEST is never an intact prefix of the next
    one -- the divergence is always at its final message. What matters is how much of it
    still is, which is what the fraction reports. Mirrors the simulation in
    scripts/test_prefix_stability.py, with the oracle block added.
    """
    agent = ToolAgent.__new__(ToolAgent)
    agent._context_budget_tokens = 31744
    agent._reply_reserve_tokens = 512
    agent._oracle_rules_block = block
    system = {"role": "system", "content": "You are a coding agent. " * 200}
    history: list[dict] = []
    prev_sent: list[dict] | None = None
    shares: list[float] = []
    intact = 0
    for turn in range(turns):
        live = {"role": "user", "content": f"{block}\nTurn {turn}: board state. " * 1}
        sent = agent._trim_messages_for_context([system, *history, live], tools=None)
        if prev_sent is not None:
            n = 0
            for a, b in zip(prev_sent, sent):
                if a != b:
                    break
                n += 1
            shares.append(n / len(prev_sent))
            if n >= len(prev_sent):
                intact += 1
        prev_sent = sent
        history = agent._strip_oracle_block_from_history(list(sent[1:]))
        history.append({"role": "assistant", "content": f"Analysis for turn {turn}. " * 40})
        history.append({"role": "tool", "tool_call_id": f"c{turn}", "content": f"Result {turn}. " * 40})
    return (sum(shares) / len(shares) if shares else 0.0), intact


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--rules-dir", type=Path, default=DEFAULT_RULES_DIR)
    parser.add_argument("--games", default=",".join(SLIPPERY_SEVEN))
    args = parser.parse_args()
    games = [g.strip().lower() for g in args.games.split(",") if g.strip()]
    marker = oracle_rules.ORACLE_RULES_HEADING

    if not args.rules_dir.is_dir():
        print(
            f"{args.rules_dir} does not exist. Run `python3.13 tools/render_rulebooks.py` first.",
            file=sys.stderr,
        )
        return 2

    failures: list[str] = []
    with tempfile.TemporaryDirectory(prefix="oracle-dry-") as tmp:
        root = Path(tmp)
        o_root = root / "20260919_000000_dry-oracle-p0"
        b_root = root / "20260919_000000_dry-armb-p0"
        o_turns = _build_arm(o_root, games, args.rules_dir)
        b_turns = _build_arm(b_root, games, None)

        for code in games:
            rulebook = (args.rules_dir / f"{code}.txt").read_text(encoding="utf-8").strip()
            first_rule = rulebook.splitlines()[1].lstrip("- ").strip()
            for n, text in zip((0, 5), o_turns[code]):
                if text.count(marker) != 1:
                    failures.append(f"O {code} turn {n}: marker appears {text.count(marker)}x, want 1")
                if not text.startswith(marker):
                    failures.append(f"O {code} turn {n}: block is not first in the user turn")
                if first_rule not in text:
                    failures.append(f"O {code} turn {n}: its own level-1 rule text is missing")
            # Each game gets ITS rulebook, not a neighbour's.
            for other in games:
                if other == code:
                    continue
                other_rule = (
                    (args.rules_dir / f"{other}.txt").read_text(encoding="utf-8").strip().splitlines()[1]
                ).lstrip("- ").strip()
                if other_rule in o_turns[code][0]:
                    failures.append(f"O {code}: carries {other}'s rules")
            for n, text in zip((0, 5), b_turns[code]):
                if marker in text:
                    failures.append(f"B {code} turn {n}: treatment marker present in the control arm")

        print(f"games: {len(games)}  ({', '.join(games)})")
        o_chars = sum(len(t[0]) for t in o_turns.values()) / len(games)
        b_chars = sum(len(t[0]) for t in b_turns.values()) / len(games)
        print(f"mean first-turn user prompt: arm B {b_chars:,.0f} chars -> arm O {o_chars:,.0f} chars")
        print(f"block re-sent on turn 5 as well as turn 0: "
              f"{all(marker in t[1] for t in o_turns.values())}")

        # Re-sent every turn, but only ONE copy is ever in the request: the live one.
        for code in games:
            agent = _agent()
            agent._oracle_rules_block = oracle_rules.render_block(
                (args.rules_dir / f"{code}.txt").read_text(encoding="utf-8").strip()
            )
            in_history, in_request = _history_keeps_one_copy(
                agent, [o_turns[code][0], o_turns[code][1], o_turns[code][1]], marker
            )
            if in_history != 0:
                failures.append(f"O {code}: {in_history} rulebook copies retained in history, want 0")
            if in_request != 1:
                failures.append(f"O {code}: {in_request} rulebook copies in the live request, want 1")
        print("rulebook copies in a 3-turn request: 1 live, 0 retained in history")

        biggest = max(games, key=lambda c: (args.rules_dir / f"{c}.txt").stat().st_size)
        block = oracle_rules.render_block(
            (args.rules_dir / f"{biggest}.txt").read_text(encoding="utf-8").strip()
        )
        share, intact = prefix_reuse(block)
        print(
            f"prefix cache, 40 turns with the largest rulebook ({biggest}, {len(block):,} chars): "
            f"mean {share:.1%} of the previous request reused, {intact} turns reused whole"
        )
        if share < 0.90:
            failures.append(f"prefix reuse {share:.1%} is below 90%; the strip is costing too much")

        for label, run_root, expect in (("O", o_root, str(len(games))), ("B", b_root, "0")):
            print(f"--- guard, arm {label} (expect {expect}) ---")
            result = subprocess.run(
                [str(GUARD), str(run_root), expect], capture_output=True, text=True
            )
            sys.stdout.write(result.stdout)
            sys.stderr.write(result.stderr)
            if result.returncode != 0:
                failures.append(f"guard failed on arm {label}")

    if failures:
        print("\nFAILURES:", file=sys.stderr)
        for f in failures:
            print(f"  {f}", file=sys.stderr)
        return 1
    print("\nall oracle injection checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
