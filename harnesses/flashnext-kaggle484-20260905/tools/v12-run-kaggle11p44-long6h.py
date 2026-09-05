"""GCP runner for the locked ARC3 Kaggle 11.44 RTDv12 baseline.

The bundle pickle stores an older 28-worker/7,920-second scheduler. The scored
Kaggle notebook overrides it after unpickling, so this runner must do the same
and fail closed if the exact 22-worker/21,600-second lock is not established.
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
bm.solver.max_runtime_s_per_game = float(os.environ["ARC3_MAX_RUNTIME_S_PER_GAME"])
bm.solver.concurrency = int(os.environ["ARC3_BENCHMARK_CONCURRENCY"])
bm.solver.save_request_logs = False
assert bm.solver.max_runtime_s_per_game == 21600.0
assert bm.solver.concurrency == 22
assert bm.solver.save_request_logs is False
assert os.environ["ARC3_ACTION_CAP"] == "14"
assert os.environ["ARC3_POST_LEVEL_UNCAPPED_TURNS"] == "0"
assert "ARC3_SAME_CONTEXT_LEVEL_REFLECTION_ENABLED" not in os.environ
print(
    "Kaggle 11.44 runtime lock: 22 workers, 21600 seconds/game, "
    "cap14, fixed30, reflection dormant, request logs off"
)

# --- cell 14, offline branch, WITHOUT the 4-game interactive truncation ------
import arc_agi  # noqa: E402
import taaf.game_api  # noqa: E402

spec = taaf.game_api.ArcadeSpec(operation_mode=arc_agi.OperationMode.OFFLINE, environments_dir=ENV_FILES)
arcade = arc_agi.Arcade(operation_mode=arc_agi.OperationMode.OFFLINE, environments_dir=ENV_FILES)
game_ids = [e.game_id for e in arcade.available_environments]
# Optional subset for fast iteration A/Bs: ARC3_GAME_SUBSET="r11l tn36 sb26 ..." (space/comma list of
# 4-char game prefixes or full ids). No-op when unset -> full 25-game suite, so this is safe for every
# other run that never sets it.
_subset = os.environ.get("ARC3_GAME_SUBSET", "").strip()
if _subset:
    _want = {t.strip().lower() for t in _subset.replace(",", " ").split() if t.strip()}
    game_ids = [g for g in game_ids if g[:4].lower() in _want or g.lower() in _want]
    print(f"[subset] ARC3_GAME_SUBSET={_subset!r} -> {len(game_ids)} games: {game_ids}")
assert game_ids, f"no offline environments under {ENV_FILES}"
assert len(game_ids) == 25, f"exact baseline requires 25 games, got {len(game_ids)}"
bm.games = [taaf.game_api.GameAPI(env_name=g, arcade_spec=spec) for g in game_ids]
bm.n_passes = 1
bm.game_weights = None
print(f"games: {len(bm.games)} | solver: {type(bm.solver).__name__}")

# The submission branch caps the whole run at start + 11h20m; game budgets
# (440 min) end far earlier for a 25-game single pass, but keep it faithful.
soft_end = datetime.now() + timedelta(hours=11, minutes=20)

asyncio.run(bm.run(soft_end_time=soft_end, runtime_environment=target, minimal_diagnostics=False))
print("V12 RUN COMPLETE")
