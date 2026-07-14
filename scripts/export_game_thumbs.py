"""Generate per-game board thumbnails for the scoreboard.

Usage: python scripts/export_game_thumbs.py [reference-run-name]

Takes each game's FIRST frame (the initial board) from the reference run's
exported viewer data and writes a 64x64 PNG per game to
docs/static/img/games/<game_id>.png. Games are shared across runs, so one
set of thumbnails serves every row; re-run when a new game appears.
"""

import json
import re
import sys
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
REF_RUN = sys.argv[1] if len(sys.argv) > 1 else "20260714_150500_v12-corrected-grafts"
DATA = ROOT / "docs" / "data" / REF_RUN
OUT = ROOT / "docs" / "static" / "img" / "games"
OUT.mkdir(parents=True, exist_ok=True)

overview = json.loads((DATA / "run-overview.json").read_text())
palette = [
    tuple(int(v) for v in re.findall(r"\d+", c)) for c in overview["arc_palette"]
]
char_to_rgb = dict(zip(overview["color_chars"], palette))

count = 0
for i, game in enumerate(overview["games"]):
    frames = json.loads((DATA / f"game-{i}-frames.json").read_text())
    board = next((f["board_ascii"] for f in frames["frames"] if f.get("board_ascii")), None)
    if not board:
        print(f"skip {game['game_id']}: no board")
        continue
    rows = board.splitlines()
    img = Image.new("RGB", (len(rows[0]), len(rows)))
    img.putdata([char_to_rgb.get(ch, (0, 0, 0)) for row in rows for ch in row])
    img.save(OUT / f"{game['game_id']}.png", optimize=True)
    count += 1
print(f"{count} thumbnails -> {OUT}")
