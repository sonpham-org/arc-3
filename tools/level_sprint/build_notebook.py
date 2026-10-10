#!/usr/bin/env python3
"""
Author: Claude Opus 5.5 (Bubba)
Date: 09-October-2026
PURPOSE: Build the Kaggle "level-start sprint" notebook from one of Son's own notebooks, so the serving stack and the
  harness are his, cell for cell, and only the benchmark part is swapped out:
    kept verbatim  the harness patch cell, the environment cell (paths, flags, patch applied to the bundle), Son's port
                   cell (noborder, drafter, temperature, toolfast, host tier, rejection sampling), precache, the ARC
                   runtime install, the bundle import + setup commands, the SGLang launcher (Flash-Next on the RTX
                   PRO 6000, waits for health), and the system monitor
    dropped        load benchmark, customization hook, run benchmark, diagnostics, compile-cache save
    added          sprint settings (variant: extra turn instructions, harness flags, sampling settings; wall clock;
                   lanes), sprint setup (runner home copied from the sprint dataset, the patched bundle frozen as the
                   runner harness with this process's flags), wait for the server, run every lane at once
                   (tools/level_sprint/sprint.py over tools/spark_runner/sample.py), show the results table
  Writes <out>/<slug>.ipynb and kernel-metadata.json (the source notebook's inputs + the sprint dataset; RTX PRO 6000;
  internet off). Never a competition submission: nothing in it calls the gateway.
  Usage: build_notebook.py --source <Son's .ipynb> --source-meta <its kernel-metadata.json> --owner sonphamorg
                           --slug arc3-level-start-sprint --dataset sonphamorg/arc3-level-sprint --out <dir>
SRP/DRY check: Pass - serving and harness cells are copied from the source notebook, never retyped; play logic is
  sample.py's, lane logic sprint.py's. This file only selects cells and writes the sprint cells.
"""
from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path

KEEP_MARKERS = [  # cells copied verbatim, in this order (each marker must hit exactly one cell)
    "%%writefile /kaggle/harness-changes.patch",
    "setup_env = {",
    "daniel-base port cell: noborder",
    "def precache(",
    "Install the ARC runtime from the bundled competition wheels",
    "def _source_path_entries(",
    "# Paste this entire file into the launcher cell.",
    "system census, one line every 10 minutes",
]

INTRO = """# ARC-3 level-start sprint

Plays every stuck level at once, one lane per level, each from that level's start, under ONE prompt/harness variant,
with a hard wall clock (default 30 minutes of play), and prints cleared / not cleared per level plus actions used.
Son's plan, #arc-3, 9-Oct-2026: test a prompt or harness change on the stuck levels in about half an hour.

* Serving and harness: copied cell for cell from **{source}** (Flash-Next on the RTX PRO 6000, his patch, his flags).
* Lanes: `level_sprint/lanes.json` in the sprint dataset (the first level under ~80% per game in the nine-hour heatmap).
  By default (`LANE_START = "warmup"`) a lane replays the verified winning line to the level BEFORE the stuck one,
  the model clears that level and carries its own context into the stuck level. Other starts: "replay" (no context),
  "auto" (an exact saved checkpoint when one exists, else "replay").
* Your variant: edit the **Sprint settings** cell (extra turn instructions, harness flags, sampling settings).
  To change the harness itself, edit the patch cell or the port cell exactly as in your own notebook.
* Output: `/kaggle/working/sprint/results.md` and `results.json`; per lane the transcript, turns and result under
  `sprint/lanes/`; any level-start checkpoint a lane writes under `sprint/home/checkpoints/`.
* Practice only. Nothing here talks to the competition gateway or submits.

Write-up: sonpham-org/arc-3 `docs/2026-10-09-level-start-sprint.md`.
"""

SETTINGS = '''# ---- Sprint settings: the only cell to edit for a prompt / flag variant ----
WALL_MINUTES = 30          # play time per lane (the model server's startup is not counted)
MAX_TURNS = 0              # 0 = no turn cap; the wall clock is the limit
MAX_ACTIONS = 1000         # per lane, a safety net
ONLY_GAMES = ""            # e.g. "sk48,lf52" to run a subset; "" = every lane in lanes.json
# Lane start for every lane. "warmup" (default since 9-Oct): replay to the level BEFORE, the model clears it and carries
# its own context into the stuck level (the clock covers both). "replay": stuck level with no context (the first stock
# control did this and cleared 0 of 11 in 30 min). "auto": an exact saved checkpoint if one exists, else "replay".
LANE_START = "warmup"
LANES_FILE = None          # None = level_sprint/lanes.json from the dataset; or a path to your own
VARIANT = {
    "name": "stock",               # shows in the results table
    "variant": "son",              # Son's wording (the port cell's flags apply either way in this notebook)
    "prompt_profile": "original",  # the prompts exactly as this notebook's harness builds them
    "instructions": "",            # extra text added to every turn message (where the built-in modes put theirs)
    "settings": {},                # sampling overrides: temperature, thinking, effort, thinking_budget, tool_calls, actions
    "env": {},                     # harness flag overrides, e.g. {"ARC3_FRAME_DIFF_HINT": "0"}
}
'''

SETUP = '''# ---- Sprint setup: runner home, harness, paths ----
import glob, json, os, shutil, subprocess, sys
from pathlib import Path

_hits = sorted(glob.glob("/kaggle/input/**/level_sprint/sprint.py", recursive=True))
if not _hits:
    raise FileNotFoundError("sprint dataset not attached (expected level_sprint/sprint.py under /kaggle/input)")
SPRINT_DATA = Path(_hits[0]).parent.parent
SPRINT_DIR = WORKING_DIR / "sprint"
SPRINT_HOME = SPRINT_DIR / "home"
shutil.rmtree(SPRINT_DIR, ignore_errors=True)
SPRINT_HOME.mkdir(parents=True)
for _name in ("solutions", "replays", "checkpoints"):   # writable copy: lanes may write new checkpoints
    shutil.copytree(SPRINT_DATA / "home" / _name, SPRINT_HOME / _name)
# Kaggle unpacks .gz files on upload; the runner's checkpoint loader reads request.json.gz and state.pkl.gz.
import gzip
for _f in list((SPRINT_HOME / "checkpoints").rglob("*")):
    if _f.is_file() and _f.name in ("request.json", "state.pkl"):
        with open(_f, "rb") as _a, gzip.open(f"{_f}.gz", "wb") as _b:
            shutil.copyfileobj(_a, _b)
        _f.unlink()
os.environ.update({
    "ARC3_RUNNER_HOME": str(SPRINT_HOME),
    "ARC3_RUNNER_HARNESS": str(BUNDLE_DIR),                       # Son's bundle, patched + toolfast by the cells above
    "ARC3_RUNNER_ENVIRONMENTS": str(SPRINT_DATA / "home" / "environment_files"),   # the files the replays were checked on
    "ARC3_SPRINT_RUNNER_CODE": str(SPRINT_DATA / "spark_runner"),
})
SPRINT_PY = [sys.executable, str(SPRINT_DATA / "level_sprint" / "sprint.py")]
# The harness flags are this process's environment after the setup and port cells: freeze them for the lanes.
subprocess.run(SPRINT_PY + ["freeze-env", str(BUNDLE_DIR)], check=True)
(SPRINT_DIR / "variant.json").write_text(json.dumps(VARIANT, indent=1))
LANES_PATH = Path(LANES_FILE) if LANES_FILE else SPRINT_DATA / "level_sprint" / "lanes.json"
_only = (["--only", ONLY_GAMES] if ONLY_GAMES else []) + (["--start", LANE_START] if LANE_START else [])
subprocess.run(SPRINT_PY + ["plan", "--lanes", str(LANES_PATH), "--variant", str(SPRINT_DIR / "variant.json")] + _only,
               check=True)
'''

WAIT = '''# ---- Wait for the model server (the launcher cell stops waiting after its own deadline) ----
import time, urllib.request
_t = time.time()
while True:
    if proc.poll() is not None:
        show_log_tail()
        raise RuntimeError("model server exited before the sprint started")
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{SERVED_MODEL_PORT}/health", timeout=5) as _r:
            if _r.status == 200:
                break
    except Exception:
        pass
    if time.time() - _t > 30 * 60:
        show_log_tail()
        raise RuntimeError("model server not healthy 30 minutes after the launcher cell")
    time.sleep(5)
print(f"server healthy ({int(time.time() - NOTEBOOK_START_TIME)} s after notebook start)")
'''

RUN = '''# ---- Run every lane at once ----
_cmd = SPRINT_PY + ["run", "--lanes", str(LANES_PATH), "--variant", str(SPRINT_DIR / "variant.json"),
                    "--out", str(SPRINT_DIR), "--base-url", SERVER_BASE_URL, "--model-id", SERVED_MODEL_NAME,
                    "--wall-minutes", str(WALL_MINUTES), "--max-turns", str(MAX_TURNS),
                    "--max-actions", str(MAX_ACTIONS)] + _only
print(" ".join(_cmd), flush=True)
_p = subprocess.Popen(_cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
for _line in _p.stdout:
    print(_line, end="", flush=True)
_p.wait()
print("sprint exit code", _p.returncode)
'''

SHOW = '''from IPython.display import Markdown, display
_md = SPRINT_DIR / "results.md"
display(Markdown(_md.read_text() if _md.exists() else "no results.md: see the run cell's output"))
'''


def code_cell(src: str) -> dict:
    return {"cell_type": "code", "execution_count": None, "metadata": {}, "outputs": [], "source": src}


def md_cell(src: str) -> dict:
    return {"cell_type": "markdown", "metadata": {}, "source": src}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", type=Path, required=True)
    ap.add_argument("--source-meta", type=Path, required=True)
    ap.add_argument("--owner", required=True)
    ap.add_argument("--slug", required=True)
    ap.add_argument("--title", default="ARC3 Level-Start Sprint")
    ap.add_argument("--dataset", required=True)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()
    nb = json.loads(args.source.read_text())
    code = [c for c in nb["cells"] if c["cell_type"] == "code"]
    cells = [md_cell(INTRO.format(source=args.source.stem))]
    for marker in KEEP_MARKERS:
        hits = [c for c in code if marker in "".join(c["source"])]
        if len(hits) != 1:
            raise SystemExit(f"expected one source cell with {marker!r}, found {len(hits)}")
        c = copy.deepcopy(hits[0])
        c["outputs"], c["execution_count"] = [], None
        cells.append(c)
    cells += [md_cell("## Sprint"), code_cell(SETTINGS), code_cell(SETUP), code_cell(WAIT), code_cell(RUN),
              code_cell(SHOW)]
    out_nb = {"cells": cells, "metadata": nb.get("metadata", {}), "nbformat": nb.get("nbformat", 4),
              "nbformat_minor": nb.get("nbformat_minor", 5)}
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / f"{args.slug}.ipynb").write_text(json.dumps(out_nb, indent=1))
    meta = json.loads(args.source_meta.read_text())
    meta.update({"id": f"{args.owner}/{args.slug}", "title": args.title, "code_file": f"{args.slug}.ipynb",
                 "is_private": True, "enable_gpu": True, "enable_internet": False,
                 "machine_shape": "NvidiaRtxPro6000"})
    meta.pop("id_no", None)
    meta["dataset_sources"] = sorted(set(meta.get("dataset_sources", [])) | {args.dataset})
    (args.out / "kernel-metadata.json").write_text(json.dumps(meta, indent=2))
    print(f"wrote {args.out / (args.slug + '.ipynb')} ({len(cells)} cells) and kernel-metadata.json")


if __name__ == "__main__":
    main()
