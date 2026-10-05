#!/usr/bin/env python3
"""Put the trainable copycat games on the Games page (static catalog + publish inputs).

Author: Claude Opus 5.5 (Bubba sub-agent)
Date: 04-October-2026
PURPOSE: Son asked (4-Oct-2026) for the copycats in datasets/copycat-games/ to be playable on
arc3.sonpham.net like every other game. This copies each verified copycat's source into
docs/static/games/src/<id>-v1/, renders its reset-frame thumbnail and measures tile_scale
exactly as scripts/build_games_manifest.py does, and appends (or refreshes) one manifest entry
per copycat in family "copycat", so the page can show them as their own "Copycats" category
with the original game named in the description. It also replaces the site's old ws04 build
with the repaired one from datasets/copycat-games (levels 5 and 7 were unwinnable).

With --traces DIR it also writes each copycat's stored winning line as an arc3-trace/1 file,
the input scripts/vet_game.py needs before scripts/publish_game_versions.py will upload it.

Never touches datasets/test-only-games/: those held-out copies are fenced off the site
(see datasets/test-only-games/README.md). Only manifest entries marked verified are added.

SRP/DRY check: Pass -- build_games_manifest.py regenerates the whole catalog from Son's local
sibling repos (paths that only exist on his machine), so it cannot be run for an append; the
render/tile_scale lines here mirror its loop. Params and sprites are not written here: the
repo's generators (measure_game_params.py, measure_game_sprites.py) read the published heads
from the live trees API, so they run after publication.

  python3.13 scripts/add_copycats_to_site.py [--traces scratch/copycat-traces]
"""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COPYCATS = ROOT / "datasets" / "copycat-games"
GAMES = ROOT / "docs" / "static" / "games"
THUMBS = ROOT / "docs" / "static" / "img" / "games"
FAMILY = "copycat"
# Same palette as build_games_manifest.py / vet_game.py (ARC-3 board colours 0-15).
PALETTE = [
    (255, 255, 255), (204, 204, 204), (153, 153, 153), (102, 102, 102), (51, 51, 51), (0, 0, 0),
    (229, 58, 163), (255, 123, 204), (249, 60, 49), (30, 147, 255), (136, 216, 241), (255, 220, 0),
    (255, 133, 27), (146, 18, 49), (79, 204, 48), (163, 86, 214),
]


def render(py_path: Path, class_name: str, thumb: Path) -> int:
    """Reset the game once: write the thumbnail, return tile_scale (build_games_manifest.py)."""
    from arcengine import ActionInput, GameAction
    from PIL import Image

    ns = {"__file__": str(py_path), "__name__": "arc_game_module"}
    exec(compile(py_path.read_text(), str(py_path), "exec"), ns)
    game = ns[class_name]()
    frame_data = game.perform_action(ActionInput(id=GameAction.RESET), raw=True)
    cam = game.camera
    grid = frame_data.frame[-1]
    rows, cols = grid.shape
    img = Image.new("RGB", (cols, rows))
    img.putdata([PALETTE[max(0, min(15, int(v)))] for row in grid for v in row])
    img.save(thumb, optimize=True)
    return min(64 // max(1, cam.width), 64 // max(1, cam.height))


def trace_of(solution: dict) -> dict:
    """datasets/copycat-games/solutions/<id>.json -> scripts/vet_game.py's arc3-trace/1."""
    def one(a):
        n = int(a["id"].removeprefix("ACTION"))
        return [6, int(a["x"]), int(a["y"])] if n == 6 else n
    return {"format": "arc3-trace/1", "levels": [{"actions": [one(a) for a in lv]} for lv in solution["levels"]]}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--traces", type=Path, help="also write arc3-trace/1 files here for vet_game.py")
    args = parser.parse_args()

    catalog = json.loads((GAMES / "manifest.json").read_text())
    by_id = {e["id"]: i for i, e in enumerate(catalog)}
    package = json.loads((COPYCATS / "manifest.json").read_text())
    added = refreshed = 0
    for game in package["games"]:
        if not game.get("verified"):
            print(f"skip {game['copycat_id']}: not verified")
            continue
        code, original = game["copycat_id"], game["original_id"]
        env = COPYCATS / "environment_files" / code / "v1"
        meta = json.loads((env / "metadata.json").read_text())
        game_id = meta["game_id"]
        dest = GAMES / "src" / game_id
        dest.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(env / f"{code}.py", dest / f"{code}.py")
        entry = {
            "id": game_id,
            "title": code.upper(),
            "class_name": meta["class_name"],
            "src_file": f"{code}.py",
            "description": f"Copycat of {original.upper()}: same rules and level order, new maps, colours and art.",
            "tags": [t for t in meta.get("tags", []) if t != "copycat"],
            "default_fps": meta.get("default_fps", 5),
            "category": FAMILY,
            "official": False,
            "copycat_of": original,
            "tile_scale": render(dest / f"{code}.py", meta["class_name"], THUMBS / f"{game_id}.png"),
        }
        if game_id in by_id:
            catalog[by_id[game_id]] = entry
            refreshed += 1
        else:
            by_id[game_id] = len(catalog)
            catalog.append(entry)
            added += 1
        if args.traces:
            args.traces.mkdir(parents=True, exist_ok=True)
            solution = json.loads((COPYCATS / "solutions" / f"{code}.json").read_text())
            (args.traces / f"{code}.trace.json").write_text(json.dumps(trace_of(solution)) + "\n")

    # The repaired Locksmith reskin replaces the site's older ws04 (same id, new bytes).
    ws04 = GAMES / "src" / "ws04-v1" / "ws04.py"
    shutil.copyfile(COPYCATS / "environment_files" / "ws04" / "v1" / "ws04.py", ws04)
    render(ws04, "Ws04", THUMBS / "ws04-v1.png")

    (GAMES / "manifest.json").write_text(json.dumps(catalog, indent=1, ensure_ascii=False) + "\n")
    print(f"copycats: {added} added, {refreshed} refreshed; ws04-v1 replaced with the repaired build")


if __name__ == "__main__":
    main()
