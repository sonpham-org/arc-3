#!/usr/bin/env python3
"""Build the Kaggle 55-game timing notebook from the submission template.

Goal: measure whether all 55 competition games fit in the 9h budget at the
real submission concurrency. Takes kaggle/submission-template-fastcommit.ipynb and:

  1. inserts the resource_profiler.py cell (same as build_profile_notebook.py):
     per-core CPU / RAM / GPU / disk sampled every 10s in a niced side process,
  2. rewrites the offline game list into 55 DISTINCT instances -- the 25 base
     games + 25 again + the first 5 -- each given a unique ``external_game_id``
     so the benchmark's pass-0 uniqueness check passes. A start_game monkeypatch
     forces GameRun.game_id from external_game_id, so it is robust regardless of
     whether the vendored taaf honors external_game_id inside _start_game (this
     is what broke the first two attempts: the check reads game_run.game_id),
  3. sets concurrency=28 and a 240-min per-game cap (the 9h/55/conc-28 budget),
  4. extends the offline soft-end to 8h30m so the run stops gracefully well
     inside Kaggle's 12h wall and a 9h competition budget,
  5. appends a cell that stops the profiler and prints a CSV summary.

Writes kaggle/timing-run/{arc3-timing-test-55-games.ipynb, kernel-metadata.json}.
"""
import base64
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TMPL = ROOT / "kaggle" / "submission-template-fastcommit.ipynb"
PROFILER = ROOT / "kaggle" / "resource_profiler.py"
OUTDIR = ROOT / "kaggle" / "timing-run"

nb = json.load(open(TMPL))
b64 = base64.b64encode(PROFILER.read_bytes()).decode()


def code_cell(src: str) -> dict:
    return {"cell_type": "code", "execution_count": None, "metadata": {}, "outputs": [], "source": src}


# --- profiler cell (identical wiring to build_profile_notebook.py) ---
start = (
    "# --- Resource profiler (out-of-band, ~zero overhead) ---\n"
    "# Per-core CPU / RAM / GPU / storage sampled every 10s in a SEPARATE niced\n"
    "# process, so the harness is never blocked. Writes resource_profile.csv (flushed\n"
    "# per row -> survives a hard stop). Started before the ARC install so it captures\n"
    "# setup + the whole run.\n"
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

run_src = "".join(nb["cells"][14]["source"])

# 1) 55 distinct instances in place of the plain 25-game offline list.
OLD_GAMES = "    bm.games = _offline_games(competition_env_files)"
NEW_GAMES = (
    "    # --- TIMING TEST: 55 distinct game instances (25 base + 25 + first 5) ---\n"
    "    import arc_agi as _arc\n"
    "    import taaf.game_api as _gapi\n"
    "    _spec = _gapi.ArcadeSpec(operation_mode=_arc.OperationMode.OFFLINE, environments_dir=competition_env_files)\n"
    "    _arcade = _arc.Arcade(operation_mode=_arc.OperationMode.OFFLINE, environments_dir=competition_env_files)\n"
    "    _base_ids = [ei.game_id for ei in _arcade.available_environments]\n"
    "    if not _base_ids:\n"
    '        raise RuntimeError("no offline environments found for timing test")\n'
    "    _plan = _base_ids + _base_ids + _base_ids[:5]\n"
    "    # Force GameRun.game_id from external_game_id so the benchmark's pass-0 uniqueness\n"
    "    # check (which reads game_run.game_id) sees len(games) distinct ids even for repeated\n"
    "    # env_names. Directly patches the value the check reads -> robust to taaf version.\n"
    "    _orig_start_game = _gapi.GameAPI.start_game\n"
    "    def _start_game_ext(self, session=None):\n"
    "        _st = _orig_start_game(self, session)\n"
    '        _ext = getattr(self, "external_game_id", None)\n'
    "        if _ext:\n"
    "            self.game_id = _ext\n"
    '            if getattr(self, "game_run", None) is not None:\n'
    "                self.game_run.game_id = _ext\n"
    "        return _st\n"
    "    _gapi.GameAPI.start_game = _start_game_ext\n"
    '    bm.games = [_gapi.GameAPI(env_name=_g, arcade_spec=_spec, external_game_id=f"{_g}#{_k}")\n'
    "                for _k, _g in enumerate(_plan)]\n"
    '    print("taaf.kaggle: TIMING TEST -> %d instances, %d unique external ids (base %d)"\n'
    "          % (len(bm.games), len({g.external_game_id for g in bm.games}), len(_base_ids)), flush=True)"
)
assert OLD_GAMES in run_src, "offline bm.games line not found -- template changed"
run_src = run_src.replace(OLD_GAMES, NEW_GAMES)

# 2) 8h30m soft-end (was a 15-min validation cap).
OLD_SOFT = ("    # Fast validation cap: ~15 min is plenty to prove the notebook executes.\n"
            "    soft_end = datetime.fromtimestamp(NOTEBOOK_START_EPOCH) + timedelta(seconds=900)")
NEW_SOFT = ("    # Timing test: run the full 55-game plan; stop ~30 min before Kaggle's 12h wall\n"
            "    # (and well inside a 9h competition budget) for a graceful teardown.\n"
            "    soft_end = datetime.now() + timedelta(hours=8, minutes=30)")
assert OLD_SOFT in run_src, "soft_end block not found -- template changed"
run_src = run_src.replace(OLD_SOFT, NEW_SOFT)

# 3) concurrency + per-game cap, injected right before the run call.
ANCHOR = "# Play the benchmark; teardown commands run even if the run raises."
CFG = (
    "# Timing config: real submission concurrency + a 9h-appropriate per-game cap.\n"
    "bm.solver.concurrency = 28\n"
    "bm.solver.max_runtime_s_per_game = 240 * 60\n"
    'print("taaf.kaggle: TIMING config concurrency=%d max_runtime_s_per_game=%s soft_end=%s"\n'
    "      % (bm.solver.concurrency, bm.solver.max_runtime_s_per_game, soft_end), flush=True)\n\n"
)
assert ANCHOR in run_src, "run anchor not found -- template changed"
run_src = run_src.replace(ANCHOR, CFG + ANCHOR)

nb["cells"][14]["source"] = run_src

nb["cells"].insert(3, code_cell(start))   # profiler, after the env/imports cell
nb["cells"].append(code_cell(stop))       # profiler stop + summary, last

OUTDIR.mkdir(parents=True, exist_ok=True)
json.dump(nb, open(OUTDIR / "arc3-timing-test-55-games.ipynb", "w"), indent=1)

meta = {
    "id": "sonphamorg/arc3-timing-test-55-games",
    "title": "ARC3 timing test 55 games",
    "code_file": "arc3-timing-test-55-games.ipynb",
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
print(f"built {OUTDIR}/arc3-timing-test-55-games.ipynb ({len(nb['cells'])} cells) + kernel-metadata.json")
