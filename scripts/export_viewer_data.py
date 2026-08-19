"""Export a run's viewer JSON for the static site.

Usage: python scripts/export_viewer_data.py logs/<run-dir> [...]

Writes docs/data/<run-name>/{run-overview.json, game-N.json,
game-N-frames.json, game-N-step-M.json} -- the exact contract of
docs/static/js/api.js, mirroring the live viewer server's endpoints.
"""

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
viewer_roots = [
    Path(os.environ["ARC3_INFERENCE_DIR"]) if os.environ.get("ARC3_INFERENCE_DIR") else None,
    ROOT / "ARC3-Inference",
]
viewer_root = next((path for path in viewer_roots if path and (path / "viewer").is_dir()), None)
if viewer_root is None:
    raise RuntimeError(
        "Could not locate ARC3-Inference/viewer; set ARC3_INFERENCE_DIR or materialize ARC3-Inference"
    )
sys.path.insert(0, str(viewer_root))

from viewer.data import (  # noqa: E402
    load_game_frames,
    load_game_shell_payload,
    load_game_step_payload,
    load_run_overview,
)

OUT_BASE = ROOT / "docs" / "data"
RESUME = os.environ.get("ARC3_EXPORT_RESUME", "").strip().lower() in {"1", "true", "yes"}


def export_run(run_dir: Path) -> None:
    # GCP archive downloads keep the gameplay artifact tree under ``runs/``
    # alongside startup/resource/sidecar evidence.  Preserve the stable outer
    # archive name as the public run id while pointing the viewer loader at the
    # nested gameplay root.
    # Synced GCS archives can contain a lightweight root-level benchmark copy
    # as well as the complete gameplay tree under ``runs/``.  Prefer the
    # nested tree whenever it exists; the root copy alone has no viewer
    # artifacts and would otherwise export an empty overview.
    source_dir = run_dir
    if (source_dir / "runs" / "benchmark.json").exists():
        source_dir = source_dir / "runs"
    out = OUT_BASE / run_dir.name
    out.mkdir(parents=True, exist_ok=True)
    overview_path = out / "run-overview.json"
    if RESUME and overview_path.exists():
        overview = json.loads(overview_path.read_text())
    else:
        overview = load_run_overview(run_dir=source_dir)
        overview_path.write_text(json.dumps(overview))
    n_files = 1
    for i, _game in enumerate(overview.get("games", [])):
        shell_path = out / f"game-{i}.json"
        if not (RESUME and shell_path.exists()):
            shell = load_game_shell_payload(run_dir=source_dir, game_index=i)
            shell_path.write_text(json.dumps(shell))
        frames_path = out / f"game-{i}-frames.json"
        if not (RESUME and frames_path.exists()):
            frames = load_game_frames(run_dir=source_dir, game_index=i)
            frames_path.write_text(json.dumps(frames))
        n_files += 2
        # step_count can overshoot what the artifact actually holds; export
        # sequentially until the loader says there is no such step.
        s = 0
        while True:
            step_path = out / f"game-{i}-step-{s}.json"
            if RESUME and step_path.exists():
                n_files += 1
                s += 1
                continue
            try:
                payload = load_game_step_payload(run_dir=source_dir, game_index=i, step_index=s)
            except FileNotFoundError:
                break
            # Avoid O(turns^2) static exports for transcript-only historical
            # runs.  The trace page reconstructs cumulative context lazily by
            # fetching each prior turn's compact local transcript.  Exact
            # request snapshots remain embedded and are never rewritten.
            step = payload.get("step") if isinstance(payload, dict) else None
            if isinstance(step, dict):
                context = step.get("context") if isinstance(step.get("context"), dict) else {}
                if context and not context.get("hasExactModelContext"):
                    step["contextReconstruction"] = {
                        "kind": "prior_step_transcripts",
                        "throughStep": s,
                    }
                    if isinstance(step.get("localContext"), dict):
                        step["context"] = step["localContext"]
            step_path.write_text(json.dumps(payload))
            n_files += 1
            s += 1
    print(f"{run_dir.name}: {n_files} files -> {out}")


if __name__ == "__main__":
    for arg in sys.argv[1:]:
        export_run(Path(arg))
