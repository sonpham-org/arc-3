#!/usr/bin/env python3
"""Play a game one action at a time from the command line, as a first-time player would.

Author: Claude Opus 5, 19-September-2026
Purpose: the evolution loop's cold-start test. A coordinator starts a session on a source file;
a tester who has not seen the source, the solution or any notes then plays it through this
tool using only the ordinary controls and the rendered screen, exactly like the site's player
(arrows/WASD = up/down/left/right, Space = ACTION5, click = ACTION6, X = ACTION7, R = reset,
plus Undo). Every command replays the session log in arcengine and writes the current screen
as a PNG (8x, with a light coordinate grid for aiming clicks) and, when the last action
animated, a strip of its frames. The log records timings, resets and undos for the QC report.

  python scripts/play_game.py start --session s01-cold-a --source path/to/game.py
  python scripts/play_game.py look  --session s01-cold-a
  python scripts/play_game.py act   --session s01-cold-a right
  python scripts/play_game.py act   --session s01-cold-a click --x 31 --y 20
  python scripts/play_game.py undo  --session s01-cold-a
  python scripts/play_game.py reset --session s01-cold-a
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from vet_game import PALETTE, find_game_classes, load_class  # noqa: E402

CONTROLS = {"up": 1, "down": 2, "left": 3, "right": 4, "space": 5, "click": 6, "x": 7}
NAMES = {v: k for k, v in CONTROLS.items()}
DEFAULT_DIR = Path(os.environ.get("ARC3_PLAY_DIR", Path.home() / ".arc3-play"))


def session_paths(directory: Path, name: str) -> tuple[Path, Path, Path]:
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,80}", name):
        raise SystemExit("session names are letters, digits, dash, underscore")
    directory.mkdir(parents=True, exist_ok=True)
    return directory / f"{name}.json", directory / f"{name}.png", directory / f"{name}-anim.png"


def render(frame, path: Path, grid: bool = True) -> None:
    from PIL import Image, ImageDraw

    image = Image.new("RGB", (64, 64))
    image.putdata([PALETTE[int(v)] for v in frame.flatten()])
    image = image.resize((512, 512), Image.NEAREST)
    if grid:
        margin = 22
        canvas = Image.new("RGB", (512 + margin, 512 + margin), (255, 255, 255))
        canvas.paste(image, (margin, margin))
        draw = ImageDraw.Draw(canvas)
        for k in range(0, 64, 8):
            p = margin + k * 8
            draw.line([(p, margin), (p, margin + 511)], fill=(128, 128, 128))
            draw.line([(margin, p), (margin + 511, p)], fill=(128, 128, 128))
            draw.text((p + 2, 4), str(k), fill=(0, 0, 0))
            draw.text((2, p + 2), str(k), fill=(0, 0, 0))
        image = canvas
    image.save(path)


def render_strip(frames, path: Path) -> None:
    from PIL import Image

    frames = frames[:12]
    strip = Image.new("RGB", (len(frames) * 132 - 4, 128), (40, 40, 40))
    for i, frame in enumerate(frames):
        tile = Image.new("RGB", (64, 64))
        tile.putdata([PALETTE[int(v)] for v in frame.flatten()])
        strip.paste(tile.resize((128, 128), Image.NEAREST), (i * 132, 0))
    strip.save(path)


def replay(session: dict):
    from arcengine import ActionInput, GameAction

    source = Path(session["source"]).read_text(encoding="utf-8")
    if hashlib.sha256(source.encode("utf-8")).hexdigest() != session["sha256"]:
        raise SystemExit("the game changed since this session started; start a fresh session")
    game = load_class(source, session["class_name"])()
    result = game.perform_action(ActionInput(id=GameAction.RESET), raw=True)
    for entry in session["log"]:
        if entry["do"] == "reset":
            result = game.perform_action(ActionInput(id=GameAction.RESET), raw=True)
        else:
            data = {"x": entry["x"], "y": entry["y"]} if entry["action"] == 6 else {}
            result = game.perform_action(ActionInput(id=GameAction.from_id(entry["action"]), data=data), raw=True)
    return game, result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("command", choices=["start", "look", "act", "undo", "reset"])
    parser.add_argument("control", nargs="?", choices=sorted(CONTROLS))
    parser.add_argument("--session", required=True)
    parser.add_argument("--source", type=Path, help="start only: the game file")
    parser.add_argument("--x", type=int)
    parser.add_argument("--y", type=int)
    parser.add_argument("--dir", type=Path, default=DEFAULT_DIR)
    args = parser.parse_intermixed_args(argv)
    record, png, anim = session_paths(args.dir, args.session)

    if args.command == "start":
        if record.exists():
            raise SystemExit("that session exists; pick a new name")
        if not args.source:
            raise SystemExit("start needs --source")
        source = args.source.read_text(encoding="utf-8")
        import ast

        classes = find_game_classes(ast.parse(source))
        if len(classes) != 1:
            raise SystemExit(f"expected one game class, found {classes}")
        session = {"source": str(args.source.resolve()), "class_name": classes[0], "sha256": hashlib.sha256(source.encode("utf-8")).hexdigest(),
                   "started_at": time.time(), "log": [], "undos": 0, "first_change_s": None, "level1_cleared_s": None}
        record.write_text(json.dumps(session, indent=1), encoding="utf-8")
    session = json.loads(record.read_text(encoding="utf-8"))
    game, before = replay(session)
    elapsed = round(time.time() - session["started_at"], 1)
    result = before
    if args.command == "act":
        if args.control is None:
            raise SystemExit(f"act needs a control: {', '.join(sorted(CONTROLS))}")
        action = CONTROLS[args.control]
        if action not in [int(a) for a in game._available_actions]:
            print(json.dumps({"refused": f"'{args.control}' is not a control in this game", "controls": [NAMES[int(a)] for a in game._available_actions if int(a) in NAMES]}))
            return 1
        entry = {"do": "act", "action": action, "t": elapsed}
        data = {}
        if action == 6:
            if args.x is None or args.y is None or not (0 <= args.x < 64 and 0 <= args.y < 64):
                raise SystemExit("click needs --x and --y in 0..63 (the grid labels on the screen image)")
            entry.update(x=args.x, y=args.y)
            data = {"x": args.x, "y": args.y}
        from arcengine import ActionInput, GameAction

        result = game.perform_action(ActionInput(id=GameAction.from_id(action), data=data), raw=True)
        session["log"].append(entry)
        changed = any(not (f == before.frame[-1]).all() for f in result.frame)
        if changed and session["first_change_s"] is None:
            session["first_change_s"] = elapsed
    elif args.command == "reset":
        from arcengine import ActionInput, GameAction

        result = game.perform_action(ActionInput(id=GameAction.RESET), raw=True)
        session["log"].append({"do": "reset", "t": elapsed})
        changed = True
    elif args.command == "undo":
        acts = [i for i, e in enumerate(session["log"]) if e["do"] == "act"]
        if not acts:
            print(json.dumps({"refused": "nothing to undo"}))
            return 1
        session["log"] = session["log"][: acts[-1]]
        session["undos"] += 1
        game, result = replay(session)
        changed = True
    else:
        changed = False
    if result.levels_completed >= 1 and session["level1_cleared_s"] is None:
        session["level1_cleared_s"] = elapsed
    record.write_text(json.dumps(session, indent=1), encoding="utf-8")
    render(result.frame[-1], png)
    animated = len(result.frame) > 1 and args.command == "act"
    if animated:
        render_strip(result.frame, anim)
    state = getattr(result.state, "name", str(result.state))
    print(json.dumps({
        "screen": str(png),
        "animation": str(anim) if animated else None,
        "frames_in_last_action": len(result.frame) if args.command == "act" else None,
        "screen_changed": changed if args.command == "act" else None,
        "state": state,
        "level": min(result.levels_completed + 1, result.win_levels),
        "levels_cleared": result.levels_completed,
        "levels_total": result.win_levels,
        "controls": [NAMES[int(a)] for a in game._available_actions if int(a) in NAMES] + ["undo", "reset"],
        "actions_taken": sum(1 for e in session["log"] if e["do"] == "act"),
        "resets": sum(1 for e in session["log"] if e["do"] == "reset"),
        "undos": session["undos"],
        "elapsed_seconds": elapsed,
    }, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
