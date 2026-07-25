"""Assemble the Games tab's static asset bundle: manifest + game source + thumbnails.

Collects the 25 official ARC-AGI-3 public games (this repo's environment_files/)
plus the custom games built in the sibling repo (/home/son/GitHub/arc-agi-3,
same environment_files/ layout, disjoint game codes) into:
  docs/static/games/manifest.json          catalog for the Games page
  docs/static/games/src/<game_id>/<file>.py  game source, fetched by the
                                              in-browser Pyodide worker
  docs/static/img/games/<game_id>.png      thumbnail (official 25 already
                                              have one from export_game_thumbs.py;
                                              this only fills in the customs)

The bespoke "ab" (Angry Birds) custom game is excluded — it has its own
standalone canvas engine, not the generic ARCBaseGame/arcengine model this
script (and the Games page) assumes.

Usage: /home/son/anaconda3/bin/python scripts/build_games_manifest.py
(needs the `arcengine` package, only for rendering custom-game thumbnails)
"""

import ast
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OFFICIAL_DIR = ROOT / "environment_files"
SIBLING_DIR = Path("/home/son/GitHub/arc-agi-3/environment_files")
OUT_SRC = ROOT / "docs" / "static" / "games" / "src"
OUT_MANIFEST = ROOT / "docs" / "static" / "games" / "manifest.json"
OUT_THUMBS = ROOT / "docs" / "static" / "img" / "games"

EXCLUDE_CUSTOM_CODES = {"ab"}  # bespoke standalone game, out of scope for now

# Canonical ARC-3 board palette (values 0-15) -- verified against a recorded
# run's own arc_palette/color_chars (docs/data/*/run-overview.json) and
# against the arc-agi-3 sibling repo's constants.py COLOR_MAP. Same array is
# duplicated in docs/static/js/games-play.js for pixel-identical rendering.
PALETTE = [
    (255, 255, 255), (204, 204, 204), (153, 153, 153), (102, 102, 102),
    (51, 51, 51), (0, 0, 0), (229, 58, 163), (255, 123, 204),
    (249, 60, 49), (30, 147, 255), (136, 216, 241), (255, 220, 0),
    (255, 133, 27), (146, 18, 49), (79, 204, 48), (163, 86, 214),
]


def find_game_class(source: str) -> str | None:
    """Return the name of the one class in `source` that subclasses ARCBaseGame."""
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            base_names = [b.id for b in node.bases if isinstance(b, ast.Name)]
            if "ARCBaseGame" in base_names:
                return node.name
    return None


def collect_entry(version_dir: Path, official: bool) -> tuple[dict, Path] | None:
    meta_path = version_dir / "metadata.json"
    if not meta_path.exists():
        return None
    meta = json.loads(meta_path.read_text())
    py_files = [p for p in version_dir.glob("*.py")]
    if not py_files:
        print(f"  skip {version_dir}: no .py file")
        return None
    py_path = py_files[0]
    class_name = find_game_class(py_path.read_text())
    if not class_name:
        print(f"  skip {version_dir}: no ARCBaseGame subclass found in {py_path.name}")
        return None
    game_id = meta["game_id"]
    entry = {
        "id": game_id,
        "title": meta.get("title", game_id),
        "class_name": class_name,
        "src_file": py_path.name,
        "tags": meta.get("tags", []),
        "default_fps": meta.get("default_fps", 6),
        "official": official,
    }
    return entry, py_path


def main():
    entries = []

    print("Official 25:")
    for code_dir in sorted(OFFICIAL_DIR.iterdir()):
        if not code_dir.is_dir():
            continue
        version_dirs = sorted(d for d in code_dir.iterdir() if d.is_dir() and d.name != "__pycache__")
        if not version_dirs:
            continue
        result = collect_entry(version_dirs[0], official=True)
        if result:
            entries.append(result)
            print(f"  {result[0]['id']}: {result[0]['title']}")

    official_codes = {p.name for p in OFFICIAL_DIR.iterdir() if p.is_dir()}

    print("\nCustom games:")
    for code_dir in sorted(SIBLING_DIR.iterdir()):
        code = code_dir.name
        if not code_dir.is_dir() or code in official_codes or code in EXCLUDE_CUSTOM_CODES:
            continue
        version_dirs = sorted(d for d in code_dir.iterdir() if d.is_dir() and d.name != "__pycache__")
        if not version_dirs:
            continue
        result = collect_entry(version_dirs[-1], official=False)  # latest version
        if result:
            entries.append(result)
            print(f"  {result[0]['id']}: {result[0]['title']}")

    # Copy sources, write manifest.
    OUT_SRC.mkdir(parents=True, exist_ok=True)
    manifest = []
    for entry, py_path in entries:
        dest_dir = OUT_SRC / entry["id"]
        dest_dir.mkdir(parents=True, exist_ok=True)
        (dest_dir / py_path.name).write_text(py_path.read_text())
        manifest.append(entry)
    OUT_MANIFEST.write_text(json.dumps(manifest, indent=2) + "\n")
    print(f"\n{len(manifest)} games -> {OUT_MANIFEST}")

    # Thumbnails: skip games that already have one (the official 25).
    OUT_THUMBS.mkdir(parents=True, exist_ok=True)
    missing = [(e, p) for e, p in entries if not (OUT_THUMBS / f"{e['id']}.png").exists()]
    if not missing:
        print("All thumbnails already present.")
        return

    try:
        from arcengine import ActionInput, GameAction
        from PIL import Image
    except ImportError as e:
        print(f"\nSkipping thumbnail generation ({e}); run with the anaconda3 "
              f"interpreter (has arcengine+PIL) to fill in the {len(missing)} missing thumbnails.")
        return

    print(f"\nGenerating {len(missing)} thumbnails:")
    for entry, py_path in missing:
        try:
            ns = {"__file__": str(py_path)}
            exec(compile(py_path.read_text(), str(py_path), "exec"), ns)
            game = ns[entry["class_name"]]()
            frame_data = game.perform_action(ActionInput(id=GameAction.RESET), raw=True)
            grid = frame_data.frame[-1]
            rows, cols = grid.shape
            img = Image.new("RGB", (cols, rows))
            img.putdata([PALETTE[max(0, min(15, int(v)))] for row in grid for v in row])
            img.save(OUT_THUMBS / f"{entry['id']}.png", optimize=True)
            print(f"  {entry['id']}: ok")
        except Exception as e:
            print(f"  {entry['id']}: FAILED ({e})")


if __name__ == "__main__":
    main()
