"""
Author: Claude Opus 5 (Bubba)
Date: 12-September-2026
PURPOSE: Generate the Kaggle notebooks for the sparse-deletion prompt A/B experiment.
Takes the duck harness notebook (keithtyser/duck-qwen3-8-anim-base, which serves
Qwen3.8-Flash-Next-NVFP4 on an RTX PRO 6000) as the chassis and rewrites exactly three
things: the run-shape cell (7 bottom-seven lanes x N passes, per-game and total caps),
the game-selection/audit gates in the run cell (they hard-require all 25 games x 1 pass),
and an inserted arm-provenance cell that hashes the assembled system prompt and asserts
the arm's prompt text is what we think it is inside the running process.
Consumes: /tmp/duckbase/duck-qwen3-8-anim-base.ipynb. Emits notebooks + kernel-metadata
next to this file.
SRP/DRY check: Pass - one generator for every arm; arms differ only by the ARMS table
below, so control and variant can never drift in anything except the bundle + label.
"""

import copy
import json
import pathlib
import sys

HERE = pathlib.Path(__file__).parent
BASE_NB = pathlib.Path("/tmp/duckbase/duck-qwen3-8-anim-base.ipynb")

# The seven lowest-scoring public games (mean score across the 163 FlashNext runs).
# Exactly 7 lanes, which is the run shape Son's 132-minute job is built around.
BOTTOM_SEVEN = (
    "sk48-d8078629",
    "bp35-0a0ad940",
    "ls20-9607627b",
    "g50t-5849a774",
    "lf52-271a04aa",
    "wa30-ee6fef47",
    "tn36-ef4dde99",
)

# Games we already solve, plus four mid-table games: the null check. If the deletion
# arm moves these, the effect is not the one being claimed.
NULL_CHECK = (
    "cd82-fb555c5d",
    "lp85-305b61c3",
    "sb26-7fbdac44",
    "cn04-2fe56bfb",
    "r11l-495a7899",
    "sc25-635fd71a",
    "ka59-38d34dbb",
)

CONTROL_BUNDLE = "keithtyser/duck-qwen38-nvfp4-mtp-vllm-smoke-v1"
SPARSE_BUNDLE = "markbarney/taaf-duck-sparse-deletion"

# Strings the control prompt asserts and the deletion arm asserts are gone.
DELETED_PROBES = ("DON'T DO THIS", "remaining-steps bar", "64 x 64", "puzzle")

# job id -> (title, kernel slug, bundle dataset, games, n_passes, per-game s, budget s)
ARMS = {
    "job0-smoke": ("ARC3 job0 smoke", "arc3-job0-smoke", CONTROL_BUNDLE,
                   BOTTOM_SEVEN[:2], 1, 600, 5400, "A-control"),
    "job1-control": ("ARC3 job1 control", "arc3-job1-control", CONTROL_BUNDLE,
                     BOTTOM_SEVEN, 4, 2061, 7920, "A-control"),
    "job2-sparse": ("ARC3 job2 sparse deletion", "arc3-job2-sparse", SPARSE_BUNDLE,
                    BOTTOM_SEVEN, 4, 2061, 7920, "B-sparse-deletion"),
    "job3-null": ("ARC3 job3 null check", "arc3-job3-null", SPARSE_BUNDLE,
                  NULL_CHECK, 4, 2061, 7920, "B-sparse-deletion"),
}

RUNTIME_DATASETS = ["keithtyser/qwen38-flash-next-vllm-nvfp4-runtime-v1"]
MODEL_SOURCES = ["keithtyser/qwen3-8-flash-next-nvfp4/PyTorch/radixark-modelopt-fp4/1"]
DOCKER = ("gcr.io/kaggle-private-byod/python@sha256:"
          "57e612b484cf3df5026ee4dcc3cb176974b22b2bc0937fb1e16132a8be4cb13c")


def shape_cell(games, n_passes, per_game_s, budget_s, arm):
    """Replaces the duck notebook's fixed public-25 settings cell."""
    return f'''# Experiment run shape. Replaces the duck notebook's public-25 settings cell, which
# pinned 7920s per game against a 32400s notebook budget and hard-raised on anything else.
ARM_LABEL = {arm!r}
EXP_GAME_IDS = {json.dumps(list(games), indent=4)}
EXP_N_PASSES = {n_passes}
EXP_PER_GAME_S = {per_game_s}
EXP_BUDGET_S = {budget_s}

bm.solver.max_runtime_s_per_game = float(EXP_PER_GAME_S)
bm.solver.analyzer_timeout = 900.0
# One concurrent lane per game, so the passes run as {n_passes} sequential waves of
# {len(games)} rather than all {len(games) * n_passes} game-runs sharing the card at once.
bm.solver.concurrency = len(EXP_GAME_IDS)
bm.solver.max_actions_per_game = None
bm.solver.save_request_logs = False
target.max_runtime_s = float(EXP_BUDGET_S)
print(
    f'EXP_SETTINGS arm={{ARM_LABEL}} lanes={{len(EXP_GAME_IDS)}} passes={{EXP_N_PASSES}} '
    f'per_game_s={{bm.solver.max_runtime_s_per_game}} budget_s={{target.max_runtime_s}} '
    f'concurrency={{bm.solver.concurrency}}',
    flush=True,
)
'''


PROVENANCE_CELL = f'''# Arm provenance. The accelerator taught us that a requested thing is not a delivered
# thing, so nothing about this run is assumed: the card, the served model, and the exact
# assembled system prompt are all hashed into this log, and the arm asserts its own
# prompt text before a single game is played.
import hashlib
import subprocess

import inference.agent.prompts as _prompts
from inference.agent.tool_agent import _build_system_prompt

_prompts_src = pathlib.Path(_prompts.__file__).read_text()
_system_prompt = _build_system_prompt(tool_output_tokens=4096)
print(f'ARM_PROVENANCE arm={{ARM_LABEL}}', flush=True)
print(f'ARM_PROVENANCE prompts_py_sha256={{hashlib.sha256(_prompts_src.encode()).hexdigest()}}')
print(f'ARM_PROVENANCE system_prompt_chars={{len(_system_prompt)}} '
      f'sha256={{hashlib.sha256(_system_prompt.encode()).hexdigest()}}')
_probes = {DELETED_PROBES!r}
for _probe in _probes:
    print(f'ARM_PROVENANCE probe={{_probe!r}} present={{_probe in _system_prompt}}')

# The whole experiment is this difference. If it is not true in this process, stop here
# rather than spend two hours producing a number that means nothing.
if ARM_LABEL == 'B-sparse-deletion':
    _wrong = [p for p in _probes if p in _system_prompt]
    if _wrong:
        raise RuntimeError(f'Deletion arm still carries {{_wrong}} in its system prompt.')
else:
    _missing = [p for p in _probes if p not in _system_prompt]
    if _missing:
        raise RuntimeError(f'Control arm is missing {{_missing}} from its system prompt.')

print(subprocess.run(
    ['nvidia-smi', '--query-gpu=name,memory.total,driver_version', '--format=csv,noheader'],
    capture_output=True, text=True, check=False).stdout.strip(), flush=True)
'''


def patch_run_cell(src, n_lanes):
    """Loosen the run cell's all-25-games/one-pass gates onto the experiment's shape."""
    subs = [
        ("bm.games = [offline_by_id[game_id] for game_id in PUBLIC_GAME_IDS]",
         "bm.games = [offline_by_id[game_id] for game_id in EXP_GAME_IDS]"),
        ("    if len(bm.games) != 25:\n"
         "        raise RuntimeError(f'Expected 25 public games, got {len(bm.games)}.')",
         "    if len(bm.games) != len(EXP_GAME_IDS):\n"
         "        raise RuntimeError(f'Expected {len(EXP_GAME_IDS)} games, got {len(bm.games)}.')"),
        ("    print(f'PUBLIC25_SELECTION games={len(bm.games)} passes=1', flush=True)",
         "    print(f'EXP_SELECTION games={len(bm.games)} passes={EXP_N_PASSES}', flush=True)"),
        ("bm.n_passes = 1", "bm.n_passes = EXP_N_PASSES"),
        ("        if len(public_runs) != 25 or public_run_ids != list(PUBLIC_GAME_IDS):",
         "        expected_run_ids = list(EXP_GAME_IDS) * EXP_N_PASSES\n"
         "        if public_run_ids != expected_run_ids:"),
        ("                f'Public run coverage changed: count={len(public_runs)} ids={public_run_ids}.'",
         "                f'Run coverage changed: count={len(public_runs)} ids={public_run_ids} '\n"
         "                f'expected={expected_run_ids}.'"),
        ("            f'PUBLIC25_AUDIT runs=25 actions={total_actions} score_path={score_path}',",
         "            f'EXP_AUDIT runs={len(public_runs)} actions={total_actions} '\n"
         "            f'score_path={score_path}',"),
    ]
    for old, new in subs:
        if old not in src:
            raise SystemExit(f"run-cell anchor missing:\n{old}")
        src = src.replace(old, new, 1)
    return src


def build(job):
    title, slug, bundle, games, n_passes, per_game_s, budget_s, arm = ARMS[job]
    nb = copy.deepcopy(json.loads(BASE_NB.read_text()))
    cells = nb["cells"]

    # Cell 13 is the settings cell, cell 15 the run cell (verified by anchor text).
    if "PUBLIC25_SETTINGS" not in "".join(cells[13]["source"]):
        raise SystemExit("cell 13 is not the settings cell")
    if "PUBLIC_GAME_IDS" not in "".join(cells[15]["source"]):
        raise SystemExit("cell 15 is not the run cell")

    cells[13]["source"] = shape_cell(games, n_passes, per_game_s, budget_s, arm).splitlines(True)
    cells[15]["source"] = patch_run_cell("".join(cells[15]["source"]), len(games)).splitlines(True)
    cells.insert(14, {"cell_type": "code", "metadata": {}, "execution_count": None,
                      "outputs": [], "source": PROVENANCE_CELL.splitlines(True)})

    nb_path = HERE / f"{slug}.ipynb"
    nb_path.write_text(json.dumps(nb, indent=1))
    (HERE / f"{slug}.kernel-metadata.json").write_text(json.dumps({
        "id": f"markbarney/{slug}",
        "title": title,
        "code_file": f"{slug}.ipynb",
        "language": "python",
        "kernel_type": "notebook",
        "is_private": True,
        "enable_gpu": True,
        "enable_tpu": False,
        "enable_internet": False,
        "dataset_sources": [bundle] + RUNTIME_DATASETS,
        "kernel_sources": [],
        "competition_sources": ["arc-prize-2026-arc-agi-3"],
        "model_sources": MODEL_SOURCES,
        "docker_image": DOCKER,
        # PascalCase, and only delivered because the competition is attached above.
        "machine_shape": "NvidiaRtxPro6000",
    }, indent=2))
    print(f"{job}: {nb_path.name} arm={arm} lanes={len(games)} passes={n_passes} bundle={bundle}")


if __name__ == "__main__":
    for job in (sys.argv[1:] or list(ARMS)):
        build(job)
