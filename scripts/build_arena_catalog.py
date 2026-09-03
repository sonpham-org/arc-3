#!/usr/bin/env python3
"""
Restore the `arena` game rows in docs/static/games/manifest.json.

build_games_manifest.py regenerates the manifest wholesale from three source
directories, which drops every row it does not know about. build_ai_generated_catalog.py
already re-adds the research games after such a rebuild; this does the same job for the
hand-authored `arena` set. Run it after any wholesale rebuild:

    python3 scripts/build_games_manifest.py
    python3 scripts/build_ai_generated_catalog.py
    python3 scripts/build_arena_catalog.py

The games themselves are vendored in this repo under docs/static/games/src/gNNN/, so this
script needs nothing outside the checkout. Rows are derived, not hand-maintained: the id
comes from the directory name and class_name is parsed out of the module, because a
class_name that disagrees with the file is the one error nothing downstream catches -- it
surfaces in the player's browser as a Python NameError.

These rows deliberately carry no tags and no description, and their title is the id. The
set is a blind human baseline: a player is meant to infer the rules from the frame, so
naming the mechanic on the card would spend the data point before the first move.
"""

from __future__ import annotations

import ast
import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
GAMES = REPO / "docs" / "static" / "games"
MANIFEST = GAMES / "manifest.json"
IMG = REPO / "docs" / "static" / "img" / "games"

CATEGORY = "arena"
DEFAULT_FPS = 10
TILE_SCALE = 4


def arena_rows() -> list[dict]:
    rows = []
    for d in sorted(GAMES.glob("src/g[0-9][0-9][0-9]")):
        gid = d.name
        module = d / f"{gid}.py"
        if not module.is_file():
            sys.exit(f"{gid}: expected {module.relative_to(REPO)}")
        tree = ast.parse(module.read_text(encoding="utf-8"))
        classes = [n.name for n in tree.body if isinstance(n, ast.ClassDef)]
        want = "G" + gid[1:]
        if want not in classes:
            sys.exit(f"{gid}: {module.name} defines {classes}, not {want}")
        if not (IMG / f"{gid}.png").is_file():
            print(f"warning: {gid} has no thumbnail", file=sys.stderr)
        rows.append({
            "id": gid,
            "title": gid,
            "class_name": want,
            "src_file": f"{gid}.py",
            "default_fps": DEFAULT_FPS,
            "category": CATEGORY,
            "official": False,
            "tile_scale": TILE_SCALE,
        })
    return rows


def main() -> int:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    kept = [r for r in manifest if r.get("category") != CATEGORY]
    rows = arena_rows()
    if not rows:
        sys.exit("no arena games found under docs/static/games/src/gNNN/")
    # indent=1 and ensure_ascii=False reproduce this file's existing formatting byte for
    # byte, so a rerun that changes nothing shows an empty diff.
    MANIFEST.write_text(json.dumps(kept + rows, indent=1, ensure_ascii=False),
                        encoding="utf-8")
    print(f"{len(rows)} arena rows restored ({len(kept)} other rows untouched)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
