#!/usr/bin/env python3.13
"""
Author: Claude Opus 5 (Bubba subagent)
Date: 18-September-2026
PURPOSE: Render one plain-text rulebook per public ARC-AGI-3 game from
datasets/explainer-games/games.json (fetched by tools/fetch_explainer_games.py). These are
the treatment text for the oracle test, docs/plans/2026-09-18-oracle-test-plan.md: the
harness variant harnesses/oracle-rules/ reads this directory via $ARC3_ORACLE_RULES_DIR and
injects the matching file into every user turn.

What goes in, per plan section 2: the `newRules` of every level, in level order, as plain
sentences, grouped under the level each rule starts on. That is all. Explicitly left out:

  - images (`level.images`)                -- the arm is text
  - the Boss's play notes (`observations`, -- a separate arm if this one moves; mixing them
    `observationsAnyLevel`)                   in would make the effect unattributable
  - run data (`runs`, `arcBaselineActions`) -- not rules
  - code citations (`rule.source`)         -- file:line refs to game source the agent cannot
                                              read, and a claim about provenance rather than
                                              a rule
  - rule categories (`rule.category`)      -- structure the plan did not authorise; one
                                              change between arms means the rule text only
  - the game's prose fields (`description`, `plainEnglish`, `controls`, `officialTitle`)
                                           -- editorial summaries, not the per-level rules

as66 is excluded by construction: the endpoint never serves it (it is the test-only game,
datasets/test-only-games/README.md). This script asserts that rather than assuming it.

Output is written under datasets/explainer-games/, which is gitignored -- these files carry
the answer key to the public 25 and are derived data, re-renderable from the fetch.

Usage:
  python3.13 tools/render_rulebooks.py                       # all 25 -> datasets/explainer-games/rulebooks/
  python3.13 tools/render_rulebooks.py --game dc22 --stdout  # eyeball one
SRP/DRY check: Pass -- fetching is tools/fetch_explainer_games.py's job and the injection is
the harness's; this only reshapes newRules into text. No other renderer of this data exists.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_GAMES_JSON = REPO_ROOT / "datasets" / "explainer-games" / "games.json"
DEFAULT_OUT_DIR = REPO_ROOT / "datasets" / "explainer-games" / "rulebooks"

# The test-only game. It must never appear in a rulebook set: the oracle arm plays the
# public 25 only (plan section 3), and as66 is never trained on or mixed in.
TEST_ONLY_GAME = "as66"


def render_rulebook(game: dict) -> str:
    """One game's newRules, level order, plain sentences, grouped by level.

    Each rule is emitted verbatim from `rule.text`, with a full stop added only when the
    source sentence lacks terminal punctuation -- the write-ups are already prose and
    rewriting them here would put this script between arc-explainer and the experiment.
    """
    blocks: list[str] = []
    for level in sorted(game["levels"], key=lambda lv: int(lv["level"])):
        rules = [str(rule.get("text") or "").strip() for rule in level.get("newRules") or []]
        rules = [text for text in rules if text]
        if not rules:
            continue
        lines = [f"Level {int(level['level'])}:"]
        for text in rules:
            if text[-1] not in ".!?":
                text += "."
            lines.append(f"- {text}")
        blocks.append("\n".join(lines))
    return "\n\n".join(blocks) + "\n"


def _load_games(path: Path) -> list[dict]:
    if not path.exists():
        sys.exit(
            f"{path} not found. Run `python3.13 tools/fetch_explainer_games.py` first "
            "(it needs the arc3 admin token; see that script's docstring)."
        )
    data = json.loads(path.read_text(encoding="utf-8"))
    games = data.get("games")
    if games is None:
        games = [data]
    if not games:
        sys.exit(f"{path} holds no games")
    return games


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--games-json", type=Path, default=DEFAULT_GAMES_JSON)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--game", help="render one game id (e.g. dc22) instead of all")
    parser.add_argument(
        "--stdout",
        action="store_true",
        help="print the rulebook(s) instead of writing files, for eyeballing",
    )
    args = parser.parse_args()

    games = _load_games(args.games_json)
    ids = [str(g["gameId"]).strip().lower() for g in games]
    if TEST_ONLY_GAME in ids:
        sys.exit(
            f"{args.games_json} contains {TEST_ONLY_GAME}, the test-only game. It must never "
            "get a rulebook; refusing rather than fencing it silently."
        )
    if args.game:
        wanted = args.game.strip().lower()
        games = [g for g in games if str(g["gameId"]).strip().lower() == wanted]
        if not games:
            sys.exit(f"no game {args.game!r} in {args.games_json} (have: {', '.join(sorted(ids))})")

    if args.stdout:
        for game in games:
            print(f"===== {game['gameId']} =====")
            print(render_rulebook(game))
        return

    args.out_dir.mkdir(parents=True, exist_ok=True)
    total_chars = 0
    for game in games:
        text = render_rulebook(game)
        out_path = args.out_dir / f"{str(game['gameId']).strip().lower()}.txt"
        out_path.write_text(text, encoding="utf-8")
        total_chars += len(text)
        rule_count = sum(len(lv.get("newRules") or []) for lv in game["levels"])
        print(f"{game['gameId']}: {len(game['levels'])} levels, {rule_count} rules, {len(text)} chars -> {out_path.name}")
    print(f"{len(games)} rulebooks, {total_chars} chars total -> {args.out_dir}")


if __name__ == "__main__":
    main()
