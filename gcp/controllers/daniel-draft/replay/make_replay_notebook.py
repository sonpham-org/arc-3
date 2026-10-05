"""Build the replay notebook: Daniel's notebook up to his server launch, with our capture hook, then a replay cell
instead of the games (4-Oct-2026, Slice and dice; Son: "all these ideas improve with a better drafter, and that needs
more data").

  python make_replay_notebook.py --out nb-replay/<label> [--runs r1,r2] [--games ar25,ft09] [--skip-games ...]
                                 [--workers 8] [--max-requests N] [--max-gb 900] [--minutes 900] [--no-upload]

Cells: his setup -> port cell = make_capture_cell.py's cell (border-off env, his wheel with our V6 capture hook in a
/tmp shadow wheelhouse) writing to /kaggle/capture (a host mount the replay runner syncs to GCS) with a big byte/time
budget -> his precache / install / import cells -> his launcher (unchanged: fp8 KV, 10 slots, 8192 chunks, his
drafter) -> replay_cell.py -> end (every later cell is dropped, so no game is played).
The runner is replay_vm_startup.sh (daniel-run-vm-startup.sh + the request logs mounted at /kaggle/replay).
"""
import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
DD = HERE.parent
sys.path.insert(0, str(DD))
import make_capture_cell as C  # noqa: E402
import make_hicache_notebook as H  # noqa: E402  (BUILDER, SOURCE, GCLOUD, LAUNCH_ANCHOR)

RP = "gs://cellens-ai-artifacts/arc3-duck/daniel-draft/replay"


def src(c):
    return "".join(c["source"]) if isinstance(c["source"], list) else c["source"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--runs", default="", help="comma list of run ids to replay (default: every run mounted)")
    ap.add_argument("--games", default="", help="comma list of game ids (short, e.g. ar25) to replay (default: all)")
    ap.add_argument("--skip-games", default="")
    ap.add_argument("--workers", type=int, default=8, help="games replayed at once (each strictly in order)")
    ap.add_argument("--max-requests", type=int, default=0, help="per game (0 = all); for a quick pilot")
    ap.add_argument("--minutes", default="900")
    ap.add_argument("--max-gb", default="900")
    ap.add_argument("--no-upload", action="store_true")
    ap.add_argument("--run-games", default="", help="per run game filter: run=g1/g2;run2=g3 (on top of --games)")
    ap.add_argument("--run-max-requests", default="", help="per run request cap per game: run=N;run2=M")
    ap.add_argument("--aux-layers", default="", help="multi-depth capture (blockdraft/make_aux_capture_cell.py): hc rows "
                    "= [layer 47 | the streams after these layers], e.g. 11,23,35 (4x bytes per row)")
    ap.add_argument("--memfrac", type=float, default=0.0, help="his --mem-fraction-static (0 = his 0.96); the aux "
                    "capture needs GPU headroom for the widened rows")
    a = ap.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)
    b64 = __import__("base64").b64encode(C.PATCH.read_bytes()).decode()
    cell = (C.CELL.replace("__PATCH_B64__", repr(b64)).replace("__MINUTES__", str(a.minutes))
            .replace("__MAX_GB__", str(a.max_gb)))
    old = "_os.environ['ARC3_MTP_CAPTURE'] = '/kaggle/working/mtp-capture'"
    assert cell.count(old) == 1
    cell = cell.replace(old, "_os.environ['ARC3_MTP_CAPTURE'] = '/kaggle/capture'  # replay: host mount, synced by the runner")
    if a.aux_layers:  # the same edits as blockdraft/make_aux_capture_cell.py (whose main() writes a 30-min cell)
        sys.path.insert(0, str(DD / "blockdraft"))
        import make_aux_capture_cell as AX
        edits = {
            AX.Q4: [(AX.Q4_LOOP_ANCHOR, AX.Q4_LOOP_NEW, 1), (AX.Q4_HELPER_ANCHOR, AX.Q4_HELPER + AX.Q4_HELPER_ANCHOR, 1)],
            "sglang/srt/speculative/eagle_worker_v2.py": [(AX.EW_PREFILL_OLD, AX.EW_PREFILL_NEW, 1),
                                                          (AX.EW_DECODE_OLD, AX.EW_DECODE_NEW, 1),
                                                          (AX.EW_HELPER_ANCHOR, AX.EW_HELPER + AX.EW_HELPER_ANCHOR, 1)]}
        add = AX.CELL_ADD.replace("__AUX_EDITS__", repr(edits)).replace("__LAYERS__", a.aux_layers)
        assert cell.count(AX.CELL_ANCHOR) == 1
        cell = cell.replace(AX.CELL_ANCHOR, AX.CELL_ANCHOR + add)
    compile(cell, "capture_cell", "exec")
    (a.out / "capture_cell.py").write_text(cell, encoding="utf-8", newline="\n")
    base = a.out / "base"
    subprocess.run([sys.executable, str(H.BUILDER), "--source", str(H.SOURCE), "--early", str(a.out / "capture_cell.py"),
                    "--compile-threads", "1", "--out", str(base)], check=True, capture_output=True)
    nb = json.loads((base / "notebook.ipynb").read_text(encoding="utf-8"))
    hits = [i for i, c in enumerate(nb["cells"]) if c["cell_type"] == "code" and H.LAUNCH_ANCHOR in src(c)]
    assert len(hits) == 1, hits
    li = hits[0]
    if a.memfrac:
        ls = src(nb["cells"][li])
        assert ls.count("    MEMFRAC=0.96,\n") == 1
        nb["cells"][li]["source"] = ls.replace("    MEMFRAC=0.96,\n", f"    MEMFRAC={a.memfrac},  # replay --memfrac\n")
    cfg = {"runs": [r for r in a.runs.split(",") if r], "games": [g for g in a.games.split(",") if g],
           "skip_games": [g for g in a.skip_games.split(",") if g], "workers": a.workers,
           "max_requests": a.max_requests or None,
           "run_games": {kv.split("=")[0]: kv.split("=")[1].split("/") for kv in a.run_games.split(";") if kv},
           "run_max_requests": {kv.split("=")[0]: int(kv.split("=")[1]) for kv in a.run_max_requests.split(";") if kv}}
    rc = (HERE / "replay_cell.py").read_text(encoding="utf-8").replace("__CFG__", repr(cfg))
    compile(rc, "replay_cell", "exec")
    del nb["cells"][li + 1:]
    nb["cells"].append({"cell_type": "code", "execution_count": None, "id": "daniel-draft-replay", "metadata": {},
                        "outputs": [], "source": rc})
    data = (json.dumps(nb, indent=1, ensure_ascii=False) + "\n").encode("utf-8")
    (a.out / "notebook.ipynb").write_bytes(data)
    sha = hashlib.sha256(data).hexdigest()
    obj = f"{RP}/notebooks/{sha[:12]}/notebook.ipynb"
    (a.out / "BUILD.json").write_text(json.dumps({"cfg": cfg, "minutes": a.minutes, "max_gb": a.max_gb,
                                                  "aux_layers": a.aux_layers, "memfrac": a.memfrac or 0.96,
                                                  "launcher_cell": li, "cells": len(nb["cells"]),
                                                  "notebook_sha256": sha, "gcs_object": obj}, indent=1))
    if not a.no_upload:
        subprocess.run(H.GCLOUD + ["storage", "cp", "-q", str(a.out / "notebook.ipynb"), obj], check=True)
    print(obj)


if __name__ == "__main__":
    main()
