"""Assemble the Games tab's static asset bundle: manifest + game source + thumbnails.

Three catalog sources, all sharing the same environment_files/<code>/<version>/
layout and the same ARCBaseGame/arcengine model:

  official     the 25 ARC-AGI-3 public games (this repo's environment_files/)
  custom       the games built in the sibling repo /home/son/GitHub/arc-agi-3
  redbluepill  the ~252-game arc-interactive catalog, cloned from
               github.com/theredbluepill/arc-interactive

Outputs:
  docs/static/games/manifest.json          catalog for the Games page
  docs/static/games/src/<game_id>/<file>.py  game source, fetched by the
                                              in-browser Pyodide worker
  docs/static/img/games/<game_id>.png      thumbnail

Game *codes* collide across sources (cr01, ft09, ls20, pt01, vc33 exist in both
our catalog and arc-interactive, as different games), but full game_ids do not
— theirs carry a version suffix (`ft09-9ab2447a` vs our `ft09-0d8bbf25`). So
everything here keys on game_id, never on the bare code.

The bespoke "ab" (Angry Birds) custom game is excluded — it has its own
standalone canvas engine, not the generic ARCBaseGame/arcengine model this
script (and the Games page) assumes.

Usage: /home/son/anaconda3/bin/python scripts/build_games_manifest.py
(needs the `arcengine` package for thumbnails and tile_scale detection)
"""

import ast
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OFFICIAL_DIR = ROOT / "environment_files"
SIBLING_DIR = Path("/home/son/GitHub/arc-agi-3/environment_files")
REDBLUEPILL_DIR = Path("/home/son/GitHub/arc-interactive/environment_files")
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


def collect_entry(version_dir: Path, category: str) -> tuple[dict, Path] | None:
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
        "category": category,
        # Kept for backwards compatibility with anything still reading the old
        # two-way split; `category` is the field to use.
        "official": category == "official",
    }
    desc = (meta.get("description") or "").strip()
    if desc:
        entry["description"] = desc
    return entry, py_path


def collect_source(base_dir: Path, category: str, *, skip_codes=frozenset(),
                   skip_ids=frozenset(), latest: bool) -> list[tuple[dict, Path]]:
    """Collect every game under an environment_files/ tree."""
    out = []
    if not base_dir.exists():
        print(f"  ! {base_dir} not found, skipping {category}")
        return out
    for code_dir in sorted(base_dir.iterdir()):
        if not code_dir.is_dir() or code_dir.name in skip_codes:
            continue
        version_dirs = sorted(
            d for d in code_dir.iterdir() if d.is_dir() and d.name != "__pycache__"
        )
        if not version_dirs:
            continue
        result = collect_entry(version_dirs[-1 if latest else 0], category)
        if result and result[0]["id"] not in skip_ids:
            out.append(result)
    return out


def main():
    print("Official 25:")
    entries = collect_source(OFFICIAL_DIR, "official", latest=False)
    for e, _ in entries:
        print(f"  {e['id']}: {e['title']}")

    official_codes = {p.name for p in OFFICIAL_DIR.iterdir() if p.is_dir()}

    print("\nCustom games:")
    custom = collect_source(
        SIBLING_DIR, "custom", latest=True,
        skip_codes=official_codes | EXCLUDE_CUSTOM_CODES,
    )
    for e, _ in custom:
        print(f"  {e['id']}: {e['title']}")
    entries += custom

    # Codes overlap between catalogs, ids do not -- dedupe on id only.
    seen_ids = {e["id"] for e, _ in entries}
    print("\nRed Blue Pill (arc-interactive):")
    redblue = collect_source(REDBLUEPILL_DIR, "redbluepill", latest=True, skip_ids=seen_ids)
    print(f"  {len(redblue)} games")
    entries += redblue

    # Copy sources.
    OUT_SRC.mkdir(parents=True, exist_ok=True)
    for entry, py_path in entries:
        dest_dir = OUT_SRC / entry["id"]
        dest_dir.mkdir(parents=True, exist_ok=True)
        (dest_dir / py_path.name).write_text(py_path.read_text())

    OUT_THUMBS.mkdir(parents=True, exist_ok=True)
    manifest = [e for e, _ in entries]

    try:
        from arcengine import ActionInput, GameAction
        from PIL import Image
    except ImportError as e:
        OUT_MANIFEST.write_text(json.dumps(manifest, indent=2) + "\n")
        print(f"\n{len(manifest)} games -> {OUT_MANIFEST}")
        print(f"Skipping thumbnails + tile_scale ({e}); rerun with the anaconda3 "
              f"interpreter (has arcengine+PIL).")
        return

    # One instantiation per game covers both jobs: the reset frame becomes the
    # thumbnail, and the camera size gives tile_scale (= the engine's integer
    # upscale factor, so the Games page knows whether tile modes have any room
    # to work in -- see docs/static/games/arc_tiles.py).
    print("\nRendering reset frames (thumbnail + tile_scale):")
    failures = []
    for entry, py_path in entries:
        want_thumb = not (OUT_THUMBS / f"{entry['id']}.png").exists()
        try:
            ns = {"__file__": str(py_path), "__name__": "arc_game_module"}
            exec(compile(py_path.read_text(), str(py_path), "exec"), ns)
            game = ns[entry["class_name"]]()
            frame_data = game.perform_action(ActionInput(id=GameAction.RESET), raw=True)
            cam = game.camera
            entry["tile_scale"] = min(64 // max(1, cam.width), 64 // max(1, cam.height))
            if want_thumb:
                grid = frame_data.frame[-1]
                rows, cols = grid.shape
                img = Image.new("RGB", (cols, rows))
                img.putdata([PALETTE[max(0, min(15, int(v)))] for row in grid for v in row])
                img.save(OUT_THUMBS / f"{entry['id']}.png", optimize=True)
        except Exception as e:
            failures.append((entry["id"], f"{type(e).__name__}: {e}"))

    tiled = sum(1 for e in manifest if e.get("tile_scale", 1) >= 2)
    print(f"  {len(entries) - len(failures)}/{len(entries)} ok, {tiled} with tile headroom (scale >= 2)")
    for gid, err in failures:
        print(f"  FAILED {gid}: {err}")

    OUT_MANIFEST.write_text(json.dumps(manifest, indent=2) + "\n")
    print(f"\n{len(manifest)} games -> {OUT_MANIFEST}")


if __name__ == "__main__":
    main()
