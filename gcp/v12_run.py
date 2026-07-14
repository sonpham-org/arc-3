"""Faithful GCP reproduction of thtennant/arc3-duck-v12 (Kaggle score 1.28).

Mirrors the notebook's TRUE_SUBMISSION-equivalent flow, not our make-interactive
path: unpickle THEIR deploy target and benchmark, install the taaf_grafts
composite exactly as cell 12 does, point bm.games at the offline competition
environment files (all 25 -- the notebook's 4-game truncation is interactive-
mode-only), and run. Server (vllm 0.19 + vrfai) is started by the startup
script beforehand, same as the bundle's setup_commands would.
"""

import asyncio
import json
import os
import pickle
import sys
from datetime import datetime, timedelta
from pathlib import Path

BUNDLE = Path("/opt/arc3/bundle")
WORKING = Path("/opt/arc3/work")
ENV_FILES = "/opt/arc3/environment_files"
WORKING.mkdir(parents=True, exist_ok=True)

os.environ["MPLBACKEND"] = "Agg"
os.environ["TAAF_RUN_AS_SUBMISSION"] = "0"
os.environ["TAAF_MINIMAL_DIAGNOSTICS"] = "0"
os.environ["ONLY_RESET_LEVELS"] = "true"
os.environ.setdefault("RECORDINGS_DIR", str(WORKING / "server_recording"))

# Bundled repos importable, exactly like the notebook's cell 8.
for repo in sorted((BUNDLE / "src").iterdir(), reverse=True):
    for candidate in (repo / "src", repo):
        if candidate.is_dir():
            sys.path.insert(0, str(candidate))

with open(BUNDLE / "deploy_target.pkl", "rb") as fh:
    target = pickle.load(fh)
target.actual_run_as_submission = False
target.is_competition_rerun = False

with open(BUNDLE / "benchmark_initial.pkl", "rb") as fh:
    bm = pickle.load(fh)
bm.job_dir = WORKING

# --- cell 12: the graft, verbatim semantics ----------------------------------
try:
    from taaf_grafts.composite import install

    install(bm, flags={"efficiency": True, "retry_guard": True, "shortcircuit": True})
except Exception as exc:  # noqa: BLE001
    print(f"[taaf_grafts] graft failed, running stock: {type(exc).__name__}: {exc}")

# --- cell 14, offline branch, WITHOUT the 4-game interactive truncation ------
import arc_agi  # noqa: E402
import taaf.game_api  # noqa: E402

spec = taaf.game_api.ArcadeSpec(operation_mode=arc_agi.OperationMode.OFFLINE, environments_dir=ENV_FILES)
arcade = arc_agi.Arcade(operation_mode=arc_agi.OperationMode.OFFLINE, environments_dir=ENV_FILES)
game_ids = [e.game_id for e in arcade.available_environments]
assert game_ids, f"no offline environments under {ENV_FILES}"
bm.games = [taaf.game_api.GameAPI(env_name=g, arcade_spec=spec) for g in game_ids]
bm.n_passes = 1
bm.game_weights = None
print(f"games: {len(bm.games)} | solver: {type(bm.solver).__name__}")

# The submission branch caps the whole run at start + 11h20m; game budgets
# (132 min) end far earlier for a 25-game single pass, but keep it faithful.
soft_end = datetime.now() + timedelta(hours=11, minutes=20)

asyncio.run(bm.run(soft_end_time=soft_end, runtime_environment=target, minimal_diagnostics=False))
print("V12 RUN COMPLETE")
