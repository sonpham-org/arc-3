"""Single-game, N-pass GCP runner: play ONE game many times for a robust score.

Same faithful flow as v12_run.py (unpickle the deploy target + benchmark, install
the taaf_grafts composite, offline env files), but restrict bm.games to ONE game
(ARC3_SINGLE_GAME) and run it ARC3_N_PASSES times (default 25). That yields a
distribution of scores for that single game -> mean +/- variance, which is what
you need to characterise a noisy game (e.g. ft09's 0<->24 swing) instead of the
±1.0 lottery a single all-25 pass gives.

Env:
  ARC3_SINGLE_GAME   game id or prefix, e.g. "ft09" (matches "ft09-0d8bbf25")
  ARC3_N_PASSES      how many times to play it (default 25)
"""

import asyncio
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

TARGET_GAME = os.environ.get("ARC3_SINGLE_GAME", "").strip()
N_PASSES = int(os.environ.get("ARC3_N_PASSES", "25") or "25")

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

try:
    from taaf_grafts.composite import install

    install(bm, flags={"efficiency": True, "retry_guard": True, "shortcircuit": True})
except Exception as exc:  # noqa: BLE001
    print(f"[taaf_grafts] graft failed, running stock: {type(exc).__name__}: {exc}")

import arc_agi  # noqa: E402
import taaf.game_api  # noqa: E402

spec = taaf.game_api.ArcadeSpec(operation_mode=arc_agi.OperationMode.OFFLINE, environments_dir=ENV_FILES)
arcade = arc_agi.Arcade(operation_mode=arc_agi.OperationMode.OFFLINE, environments_dir=ENV_FILES)
game_ids = [e.game_id for e in arcade.available_environments]
assert game_ids, f"no offline environments under {ENV_FILES}"

if TARGET_GAME:
    matches = [g for g in game_ids if g == TARGET_GAME or g.split("-")[0] == TARGET_GAME
               or g.startswith(TARGET_GAME)]
    assert matches, f"ARC3_SINGLE_GAME={TARGET_GAME!r} not found in {game_ids}"
    game_ids = matches[:1]  # exactly one game
    print(f"single-game mode: {game_ids[0]} x {N_PASSES} passes")
else:
    print(f"WARNING: ARC3_SINGLE_GAME unset -- running all {len(game_ids)} games x {N_PASSES}")

bm.games = [taaf.game_api.GameAPI(env_name=g, arcade_spec=spec) for g in game_ids]
bm.n_passes = N_PASSES
bm.game_weights = None
print(f"games: {len(bm.games)} | passes: {bm.n_passes} | solver: {type(bm.solver).__name__}")

soft_end = datetime.now() + timedelta(hours=11, minutes=20)
asyncio.run(bm.run(soft_end_time=soft_end, runtime_environment=target, minimal_diagnostics=False))
print("SINGLE-GAME RUN COMPLETE")
