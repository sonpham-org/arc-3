#!/usr/bin/env python3
"""Build the Kaggle resource-profiling notebook from the submission template.

Takes kaggle/submission-template-fastcommit.ipynb and:
  1. inserts a cell (right after setup) that writes + starts resource_profiler.py
     as a separate niced process sampling every 10s -> resource_profile.csv,
  2. caps offline gameplay at 10 minutes from run start,
  3. appends a cell that stops the profiler and prints a CSV summary.
Writes kaggle/profile-run/{arc3-resource-profile.ipynb, kernel-metadata.json}.
"""
import base64
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TMPL = ROOT / "kaggle" / "submission-template-fastcommit.ipynb"
PROFILER = ROOT / "kaggle" / "resource_profiler.py"
OUTDIR = ROOT / "kaggle" / "profile-run"

nb = json.load(open(TMPL))
b64 = base64.b64encode(PROFILER.read_bytes()).decode()


def code_cell(src: str) -> dict:
    return {"cell_type": "code", "execution_count": None, "metadata": {}, "outputs": [], "source": src}


start = (
    "# --- Resource profiler (out-of-band, ~zero overhead) ---\n"
    "# Per-core CPU / RAM / GPU / storage sampled every 10s in a SEPARATE niced\n"
    "# process, so the harness is never blocked. Writes resource_profile.csv (flushed\n"
    "# per row -> survives a hard stop). Started before the ARC install so it captures\n"
    "# setup + the run.\n"
    "import base64 as _b64, os as _os, sys as _sys, subprocess as _sp\n"
    f'_PROFILER_B64 = "{b64}"\n'
    '_prof_path = WORKING_DIR / "resource_profiler.py"\n'
    "_prof_path.write_bytes(_b64.b64decode(_PROFILER_B64))\n"
    '_PROFILE_CSV = WORKING_DIR / "resource_profile.csv"\n'
    '_profiler = _sp.Popen([_sys.executable, str(_prof_path), "--out", str(_PROFILE_CSV),\n'
    '                       "--interval", "10", "--disk", "/kaggle/working"],\n'
    "                      stdout=_sp.DEVNULL, stderr=_sp.STDOUT, preexec_fn=lambda: _os.nice(19))\n"
    'print("taaf.kaggle: resource profiler pid=%d interval=10s -> %s" % (_profiler.pid, _PROFILE_CSV), flush=True)\n'
)

stop = (
    "# --- Stop the profiler and summarize the capture ---\n"
    "try:\n"
    "    _profiler.terminate(); _profiler.wait(timeout=15)\n"
    "except Exception as _e:\n"
    "    print('profiler stop:', _e)\n"
    "import csv as _csv\n"
    "try:\n"
    "    _rows = list(_csv.DictReader(open(_PROFILE_CSV)))\n"
    "    print('resource_profile.csv: %d samples (~%d s)' % (len(_rows), len(_rows) * 10))\n"
    "    def _pa(c):\n"
    "        v = [float(r[c]) for r in _rows if r.get(c) not in (None, '')]\n"
    "        return (max(v) if v else 0.0, sum(v) / len(v) if v else 0.0)\n"
    "    for _c in ['cpu_total_pct','ram_pct','ram_used_gb','gpu0_util_pct','gpu0_mem_used_mb','disk_used_pct','disk_write_mbps','sampler_cpu_s']:\n"
    "        if _rows and _c in _rows[0]:\n"
    "            _pk, _av = _pa(_c); print('  %-18s peak=%.1f avg=%.1f' % (_c, _pk, _av))\n"
    "except Exception as _e:\n"
    "    print('profile summary failed:', _e)\n"
)

# Cap gameplay at 10 minutes from run start (template default is 900s from notebook start).
OLD = ("    # Fast validation cap: ~15 min is plenty to prove the notebook executes.\n"
       "    soft_end = datetime.fromtimestamp(NOTEBOOK_START_EPOCH) + timedelta(seconds=900)")
NEW = ("    # Profiling run: cap gameplay at 10 minutes from run start.\n"
       "    soft_end = datetime.now() + timedelta(minutes=10)")
run_src = "".join(nb["cells"][14]["source"])
assert OLD in run_src, "soft_end block not found in cell 14 -- template changed"
nb["cells"][14]["source"] = run_src.replace(OLD, NEW)

nb["cells"].insert(3, code_cell(start))   # after the env/imports cell
nb["cells"].append(code_cell(stop))       # last cell

OUTDIR.mkdir(parents=True, exist_ok=True)
json.dump(nb, open(OUTDIR / "arc3-resource-profile.ipynb", "w"), indent=1)

meta = {
    "id": "sonphamorg/arc3-resource-profile",
    "title": "ARC3 resource profile (10min)",
    "code_file": "arc3-resource-profile.ipynb",
    "language": "python",
    "kernel_type": "notebook",
    "is_private": True,
    "enable_gpu": True,
    "enable_tpu": False,
    "enable_internet": False,
    "dataset_sources": [
        "driessmit1/arc3-vllm-h100-wheelhouse-v3",
        "jeroencottaar/taaf-kaggle-source-share",
        "driessmit1/vrfai-qwen3-6-27b-fp8-hf-snapshot",
    ],
    "competition_sources": ["arc-prize-2026-arc-agi-3"],
    "kernel_sources": [],
    "model_sources": [],
    "docker_image": "gcr.io/kaggle-private-byod/python@sha256:57e612b484cf3df5026ee4dcc3cb176974b22b2bc0937fb1e16132a8be4cb13c",
    "machine_shape": "NvidiaRtxPro6000",
}
json.dump(meta, open(OUTDIR / "kernel-metadata.json", "w"), indent=2)
print(f"built {OUTDIR}/arc3-resource-profile.ipynb ({len(nb['cells'])} cells) + kernel-metadata.json")
