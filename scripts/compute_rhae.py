"""
Author: Claude Opus 5 (Bubba)
Date: 14-September-2026
PURPOSE: Compute RHAE (relative human action efficiency) for the ARC-3 prompt-ablation arms
from downloaded Kaggle job output. Reads per-pass agent action counts out of each run's
`artifacts/<game_id>_p<N>_viewer_data.json` (`actions_per_level`, `levels_completed`) and the
human-baseline denominator out of the ARCEngine environment metadata
(`environment_files/<game>/<hash>/metadata.json` -> `baseline_actions`). Before reporting any
RHAE number it reconstructs each pass's official `final_score` from those same two inputs via
the repo's own scoring rule (ARC3-Inference/inference/tools/traces.py compute_level_score /
compute_game_score) and compares against the recorded `final_score` -- that reconstruction is
the evidence that the baseline vectors used here are the ones the engine actually scored with.
Emits a validation report, a per-arm RHAE table, and a per-arm/per-game breakdown.
SRP/DRY check: Pass -- no existing script computes RHAE or resolves baselines from environment
metadata; scoring constants and formulas are taken from traces.py rather than re-invented, and
this script does not duplicate traces.py's trace-export role.
NOTE (17-Sep-2026, on landing): written 14-Sep and left untracked in a /tmp worktree; committed
unchanged apart from this note. Its `rhae_level` is an unweighted, cap-1.0 per-level efficiency.
That is NOT the paper's RHAE (arXiv:2603.24621 §4.1: cap 115%, levels weighted by index,
environment score capped at the weighted share of levels cleared) -- the validation half above
is the one that matches the paper. See docs/arc-agi-3-paper-reading.md. The job names in ARMS
are the jobs 1-10 prompt ablations; point --runs-root at their downloaded output.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

# Scoring constants, verbatim from ARC3-Inference/inference/tools/traces.py
PER_LEVEL_SCORE_CAP = 115.0
GAME_SCORE_CAP = 100.0

GAMES = [
    "bp35-0a0ad940",
    "g50t-5849a774",
    "lf52-271a04aa",
    "ls20-9607627b",
    "sk48-d8078629",
    "tn36-ef4dde99",
    "wa30-ee6fef47",
]

# job dir name -> (arm letter, arm label)
ARMS = {
    "arc3-job1-control": ("A", "control"),
    "arc3-job2-sparse-deletion": ("B", "deletion"),
    "arc3-job4-mechanics-possibility": ("C", "mechanics-possibility"),
    "arc3-job5-null-control": ("A'", "null-control (re-run of A)"),
    "arc3-job6-glyph-consonants": ("D", "glyph-consonants"),
    "arc3-job7-image-first-turn": ("E", "image-first-turn"),
    "arc3-job8-commit-prompt": ("F", "commit-prompt"),
    "arc3-job9-visual-first": ("G", "visual-first"),
    "arc3-job10-action7-roundtrip": ("H", "action7-roundtrip"),
}


def load_baselines(env_root: Path) -> dict[str, list[int]]:
    """Resolve baseline_actions per game_id from ARCEngine environment metadata."""
    out: dict[str, list[int]] = {}
    for meta in sorted(env_root.rglob("metadata.json")):
        try:
            data = json.loads(meta.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        gid = str(data.get("game_id", ""))
        if gid not in GAMES:
            continue
        baselines = data.get("baseline_actions")
        if isinstance(baselines, list) and baselines:
            out[gid] = [int(x) for x in baselines]
    return out


def compute_level_score(*, baseline_actions: int, agent_steps: int) -> float:
    if agent_steps <= 0 or baseline_actions <= 0:
        return 0.0
    return min(float((baseline_actions / agent_steps) ** 2) * 100.0, PER_LEVEL_SCORE_CAP)


def compute_game_score(level_scores: list[tuple[int, float]]) -> float:
    total_weight = sum(level for level, _ in level_scores)
    if total_weight <= 0:
        return 0.0
    raw = sum(score * level for level, score in level_scores) / total_weight
    completed_weight = sum(level for level, score in level_scores if score > 0.0)
    return min(raw, completed_weight / total_weight * GAME_SCORE_CAP)


def rhae_level(baseline_actions: int, agent_steps: int) -> float:
    """Agreed RHAE per completed level: min(baseline / agent, 1) ** 2."""
    if agent_steps <= 0 or baseline_actions <= 0:
        return 0.0
    return min(baseline_actions / agent_steps, 1.0) ** 2


def read_pass(job_dir: Path, game_id: str, p: int) -> dict | None:
    f = job_dir / "artifacts" / f"{game_id}_p{p}_viewer_data.json"
    if not f.is_file():
        return None
    return json.loads(f.read_text(encoding="utf-8"))


def main() -> int:
    ap = argparse.ArgumentParser(description="Compute RHAE across ARC-3 prompt-ablation arms.")
    ap.add_argument("--runs-root", default=str(Path.home() / "arc3-job-output"))
    ap.add_argument(
        "--env-root",
        default=str(Path.home() / "GitHub/arc-explainer/external/ARCEngine/environment_files"),
    )
    ap.add_argument("--passes", type=int, default=3, help="number of passes to include (p0..p{n-1})")
    ap.add_argument("--json-out", default=None)
    args = ap.parse_args()

    runs_root = Path(args.runs_root)
    baselines = load_baselines(Path(args.env_root))

    print("== baseline denominators (source: ARCEngine environment metadata) ==")
    missing = [g for g in GAMES if g not in baselines]
    for g in GAMES:
        print(f"{g:18s} {baselines.get(g)}")
    if missing:
        print(f"MISSING BASELINES: {missing}")
        return 2

    # --- validation: reconstruct official final_score for every (arm, game, pass) ---
    print("\n== validation: reconstructed final_score vs recorded final_score ==")
    checked = matched = 0
    saturated = unsaturated = unsat_matched = 0
    mismatches: list[str] = []
    for job in sorted(ARMS):
        job_dir = runs_root / job
        if not job_dir.is_dir():
            continue
        for game_id in GAMES:
            for p in range(args.passes):
                d = read_pass(job_dir, game_id, p)
                if d is None:
                    continue
                apl = d["actions_per_level"]
                done = int(d["levels_completed"])
                total = int(d["total_levels"])
                base = baselines[game_id]
                if len(base) < total:
                    mismatches.append(
                        f"{job}/{game_id}/p{p}: baseline list len {len(base)} < total_levels {total}"
                    )
                    continue
                level_scores: list[tuple[int, float]] = []
                for idx in range(total):
                    steps = apl[idx] if idx < len(apl) else 0
                    score = (
                        compute_level_score(baseline_actions=base[idx], agent_steps=steps)
                        if idx < done
                        else 0.0
                    )
                    level_scores.append((idx + 1, score))
                recon = compute_game_score(level_scores)
                recorded = float(d["final_score"])
                checked += 1
                # Saturated == the game cap binds, so the reconstruction is insensitive to
                # the baseline values and is NOT a test of them. Track the two branches apart.
                completed_weight = sum(l for l, s in level_scores if s > 0.0)
                total_weight = sum(l for l, _ in level_scores)
                cap = completed_weight / total_weight * GAME_SCORE_CAP if total_weight else 0.0
                raw = (
                    sum(s * l for l, s in level_scores) / total_weight if total_weight else 0.0
                )
                is_sat = done > 0 and raw >= cap - 1e-9
                ok = abs(recon - recorded) < 1e-6
                if ok:
                    matched += 1
                else:
                    mismatches.append(
                        f"{job}/{game_id}/p{p}: recon={recon!r} recorded={recorded!r} "
                        f"apl={apl} done={done}"
                    )
                if done == 0:
                    continue
                if is_sat:
                    saturated += 1
                else:
                    unsaturated += 1
                    unsat_matched += int(ok)

    print(f"checked={checked} matched={matched} mismatched={len(mismatches)}")
    print(
        f"of the {saturated + unsaturated} passes with >=1 completed level: "
        f"{saturated} saturated (game cap binds; NOT a test of the baselines), "
        f"{unsaturated} unsaturated (discriminating), {unsat_matched} of those matched"
    )
    for m in mismatches:
        print("  MISMATCH", m)

    # --- RHAE ---
    print("\n== RHAE per arm (unweighted mean over completed levels, p0..p%d) ==" % (args.passes - 1))
    rows = []
    detail: dict[str, dict] = {}
    for job, (arm, label) in sorted(ARMS.items(), key=lambda kv: kv[1][0]):
        job_dir = runs_root / job
        if not job_dir.is_dir():
            rows.append((arm, label, None, 0, None, None, "OUTPUT NOT ON DISK"))
            continue
        effs: list[float] = []
        per_game: dict[str, list[float]] = {}
        per_pass: dict[int, list[float]] = {}
        for game_id in GAMES:
            per_game[game_id] = []
            for p in range(args.passes):
                d = read_pass(job_dir, game_id, p)
                if d is None:
                    continue
                apl = d["actions_per_level"]
                done = int(d["levels_completed"])
                base = baselines[game_id]
                for idx in range(done):
                    e = rhae_level(base[idx], apl[idx])
                    effs.append(e)
                    per_game[game_id].append(e)
                    per_pass.setdefault(p, []).append(e)
        n = len(effs)
        mean = sum(effs) / n if n else None
        rows.append(
            (
                arm,
                label,
                mean,
                n,
                min(effs) if effs else None,
                max(effs) if effs else None,
                "",
            )
        )
        detail[arm] = {
            "label": label,
            "job": job,
            "n_completed_levels": n,
            "rhae": mean,
            "per_game": {g: v for g, v in per_game.items()},
            "per_pass": {str(k): v for k, v in sorted(per_pass.items())},
        }

    print(f"{'arm':4s} {'label':28s} {'RHAE':>7s} {'n_lvl':>6s} {'min':>6s} {'max':>6s}  note")
    for arm, label, mean, n, lo, hi, note in rows:
        ms = f"{mean:.4f}" if mean is not None else "  n/a"
        los = f"{lo:.3f}" if lo is not None else "  n/a"
        his = f"{hi:.3f}" if hi is not None else "  n/a"
        print(f"{arm:4s} {label:28s} {ms:>7s} {n:>6d} {los:>6s} {his:>6s}  {note}")

    print("\n== per-game RHAE (mean over completed levels in that game; '-' = no clears) ==")
    hdr = "arm  " + "".join(f"{g.split('-')[0]:>8s}" for g in GAMES)
    print(hdr)
    for arm in sorted(detail):
        cells = []
        for g in GAMES:
            v = detail[arm]["per_game"][g]
            cells.append(f"{sum(v)/len(v):8.3f}" if v else f"{'-':>8s}")
        print(f"{arm:4s} " + "".join(cells))

    print("\n== completed-level counts per arm per game ==")
    print(hdr)
    for arm in sorted(detail):
        cells = [f"{len(detail[arm]['per_game'][g]):8d}" for g in GAMES]
        print(f"{arm:4s} " + "".join(cells))

    if args.json_out:
        Path(args.json_out).write_text(
            json.dumps(
                {
                    "baselines": baselines,
                    "passes": args.passes,
                    "validation": {
                        "checked": checked,
                        "matched": matched,
                        "saturated": saturated,
                        "unsaturated": unsaturated,
                        "unsaturated_matched": unsat_matched,
                        "mismatches": mismatches,
                    },
                    "arms": detail,
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        print(f"\nwrote {args.json_out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
