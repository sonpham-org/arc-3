"""Export a run's viewer JSON for the static site.

Usage: python scripts/export_viewer_data.py logs/<run-dir> [...]

Writes docs/data/<run-name>/{run-overview.json, game-N.json,
game-N-frames.json, game-N-step-M.json} -- the exact contract of
docs/static/js/api.js, mirroring the live viewer server's endpoints.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "ARC3-Inference"))

from viewer.data import (  # noqa: E402
    load_game_frames,
    load_game_shell_payload,
    load_game_step_payload,
    load_run_overview,
)

OUT_BASE = Path(__file__).resolve().parents[1] / "docs" / "data"


def export_run(run_dir: Path) -> None:
    out = OUT_BASE / run_dir.name
    out.mkdir(parents=True, exist_ok=True)
    overview = load_run_overview(run_dir=run_dir)
    (out / "run-overview.json").write_text(json.dumps(overview))
    n_files = 1
    for i, _game in enumerate(overview.get("games", [])):
        shell = load_game_shell_payload(run_dir=run_dir, game_index=i)
        (out / f"game-{i}.json").write_text(json.dumps(shell))
        frames = load_game_frames(run_dir=run_dir, game_index=i)
        (out / f"game-{i}-frames.json").write_text(json.dumps(frames))
        n_files += 2
        # step_count can overshoot what the artifact actually holds; export
        # sequentially until the loader says there is no such step.
        s = 0
        while True:
            try:
                payload = load_game_step_payload(run_dir=run_dir, game_index=i, step_index=s)
            except FileNotFoundError:
                break
            (out / f"game-{i}-step-{s}.json").write_text(json.dumps(payload))
            n_files += 1
            s += 1
    print(f"{run_dir.name}: {n_files} files -> {out}")


if __name__ == "__main__":
    for arg in sys.argv[1:]:
        export_run(Path(arg))
