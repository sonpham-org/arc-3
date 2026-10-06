#!/usr/bin/env python3
"""
Author: Claude Opus 5.5 (Bubba)
Date: 06-October-2026
PURPOSE: Build the harness the Spark runner plays with, exactly the way Son's 31.63 notebook
  (sonphamorg/arc3-daniel-sb-t06-toolfast-rs-hicache11-kq8-ct1) builds it on Kaggle:
    1. copy Franzen's unchanged source bundle (Kaggle dataset dfranzen/taaf-kaggle-source-bundle-copy),
    2. `git apply --include=ARC3-Inference/*` the notebook's harness-changes.patch (its %%writefile cell),
    3. run Son's toolfast edit block from his port cell (CPU-only edits to runtime_state.py, tool_agent.py,
       python_tool_sandbox.py; each anchor must match exactly once, as in the notebook),
    4. write notebook_env.json: the gameplay environment of the notebook's setup cell (`setup_env`, plus the
       priority block) and of Son's port cell (noborder flags and temperature 0.6). Serving-only keys stay in the
       file for the record; the runner overrides server address and model id.
  The runner then imports this tree exactly like the notebook does (every <repo>/src or <repo> on sys.path).
  Usage: build_harness.py --bundle <downloaded dataset dir> --notebook <31.63 .ipynb> --out <harness dir>
SRP/DRY check: Pass - patch text, edit anchors and flag values are read out of the notebook itself, never retyped;
  the notebook stays the single source. Serving tricks (drafter, hot map, rejection sampling, host cache) are the
  server's business (two-Spark cluster), not this harness's.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
from pathlib import Path


def cell_sources(notebook: Path) -> list[str]:
    nb = json.loads(notebook.read_text())
    return ["".join(c["source"]) for c in nb["cells"] if c["cell_type"] == "code"]


def find_cell(cells: list[str], marker: str) -> str:
    hits = [c for c in cells if marker in c]
    if len(hits) != 1:
        raise SystemExit(f"expected exactly one notebook cell containing {marker!r}, found {len(hits)}")
    return hits[0]


def block(text: str, start: str, end_marker: str | None) -> str:
    i = text.index(start)
    j = text.index(end_marker, i) if end_marker else len(text)
    return text[i:j]


def notebook_env(setup_cell: str, port_cell: str) -> dict:
    # The setup cell's dict literals reference two notebook variables; give them stand-ins the runner replaces.
    scope = {"SERVER_BASE_URL": "http://127.0.0.1:1234/v1", "SERVED_MODEL_NAME": "flashnext",
             "USE_PRIORITY_SCHEDULING": True}
    exec(block(setup_cell, "setup_env = {", "\nif USE_PRIORITY_SCHEDULING"), scope)
    exec(block(setup_cell, "if USE_PRIORITY_SCHEDULING", "\nos.environ.update"), scope)
    base = {k: str(v) for k, v in scope["setup_env"].items()}
    for line in setup_cell.splitlines():   # top-of-cell os.environ['X'] = 'Y' lines (warmup, retry grace)
        m = re.match(r"os\.environ\['([A-Z0-9_]+)'\] = '([^']*)'$", line.strip())
        if m:
            base[m.group(1)] = m.group(2)
    port_scope: dict = {}
    exec(block(port_cell, "NOBORDER = {", "\n_before"), port_scope)
    son = dict(port_scope["NOBORDER"])
    m = re.search(r"os\.environ\['LOCAL_ANALYZER_TEMPERATURE'\] = '([0-9.]+)'", port_cell)
    if not m:
        raise SystemExit("temperature port line not found")
    son["LOCAL_ANALYZER_TEMPERATURE"] = m.group(1)
    m = re.search(r"os\.environ\['ARC3_MAX_ACTIVE_STREAMS'\] = '([0-9]+)'", port_cell)
    if m:
        son["ARC3_MAX_ACTIVE_STREAMS"] = m.group(1)
    return {"daniel": base, "son_port": son}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--bundle", type=Path, required=True)
    ap.add_argument("--notebook", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()
    cells = cell_sources(args.notebook)
    patch_cell = find_cell(cells, "%%writefile /kaggle/harness-changes.patch")
    setup_cell = find_cell(cells, "setup_env = {")
    port_cell = find_cell(cells, "daniel-base port cell, part 2: toolfast")

    if args.out.exists():
        shutil.rmtree(args.out)
    shutil.copytree(args.bundle, args.out)
    patch = args.out / "harness-changes.patch"
    patch.write_text(patch_cell.split("\n", 1)[1] + "\n")
    subprocess.run(["git", "apply", "--include=ARC3-Inference/*", "-v", str(patch)], cwd=args.out / "src", check=True)

    toolfast = block(port_cell, "# --- daniel-base port cell, part 2: toolfast", "\n# --- port: host tier")
    exec(compile(toolfast, "toolfast-cell", "exec"), {"Path": Path, "BUNDLE_DIR": args.out, "os": os})

    env = notebook_env(setup_cell, port_cell)
    env["source"] = {"notebook": args.notebook.name, "bundle": "dfranzen/taaf-kaggle-source-bundle-copy"}
    (args.out / "notebook_env.json").write_text(json.dumps(env, indent=1))
    print("harness built:", args.out, "| daniel flags:", len(env["daniel"]), "| son port flags:", env["son_port"])


if __name__ == "__main__":
    main()
