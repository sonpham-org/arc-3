"""Training records for the next model of the RL box's continuous loop (4-Oct-2026, Son: "nothing stops training from
just filling in"; rl/box/README.md). The game servers play without pause and the trainer trains back to back, so
each training job takes the tries that are ready at that moment ("a cut"):
  - every campaign's tries and job files are mirrored to <state>/tries/<campaign>, <state>/jobs/<campaign>;
  - a job (one restart point, K sibling tries) is ready when all its tries have a result.json, or when its newest result
    is older than --stale-min (a sibling that will never finish: a lost server, a STOP);
  - ready jobs not used by an earlier cut, of a training game (--games), not the test slice (pick.class 'test'), are
    hard-linked into <state>/cuts/<name>/<campaign>/...; try_records.py scores each try against its siblings and
    select_records.py keeps --budget records (half better, half worse than their siblings' mean);
  - the used jobs are recorded in <state>/used_jobs.txt only after the records are written.
Exit 0 with records in --out; exit 75 when fewer than --min records come out (the caller retries later; nothing is
marked used).
  /opt/rl/venv/bin/python cut_records.py --campaigns v1c0-1004,v1r1-1004 --state /opt/m/work/c --name c001 \
      --out /opt/m/work/records/c001 --games bp35,cn04,... --budget 48 --min 16
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

GS = "gs://cellens-ai-artifacts/arc3-gtree/v1/rl"
HERE = Path(__file__).resolve().parent


def mirror(campaign: str, state: Path) -> None:
    for sub in ("tries", "jobs"):
        d = state / sub / campaign
        d.mkdir(parents=True, exist_ok=True)
        subprocess.run(["gcloud", "storage", "rsync", "-r", f"{GS}/{campaign}/{sub}", str(d)],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def job_specs(state: Path, campaign: str) -> dict[str, dict]:
    out = {}
    for f in (state / "jobs" / campaign).rglob("*.json"):
        try:
            j = json.loads(f.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if j.get("job_id"):
            out[str(j["job_id"])] = j
    return out


def job_dirs(state: Path, campaign: str) -> dict[str, list[Path]]:
    """job id -> its directories under tries/<campaign>/<vm>/<job id> (one per server that played some of it)."""
    out: dict[str, list[Path]] = {}
    root = state / "tries" / campaign
    if root.exists():
        for vm in root.iterdir():
            if vm.is_dir():
                for jd in vm.iterdir():
                    if jd.is_dir():
                        out.setdefault(jd.name, []).append(jd)
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--campaigns", required=True, help="comma list of rollout campaigns (tries of the current models)")
    ap.add_argument("--state", required=True)
    ap.add_argument("--name", required=True, help="this cut's name (the training job)")
    ap.add_argument("--out", required=True, help="records dir for lora_train.py")
    ap.add_argument("--games", required=True, help="comma list of training games")
    ap.add_argument("--budget", type=int, default=48)
    ap.add_argument("--min", type=int, default=16)
    ap.add_argument("--stale-min", type=float, default=20.0)
    a = ap.parse_args()
    state = Path(a.state)
    state.mkdir(parents=True, exist_ok=True)
    games = set(a.games.split(","))
    used_f = state / "used_jobs.txt"
    used = set(used_f.read_text().split()) if used_f.exists() else set()
    cut = state / "cuts" / a.name
    shutil.rmtree(cut, ignore_errors=True)
    now = time.time()
    picked, skipped = [], {"used": 0, "test": 0, "game": 0, "unripe": 0, "no_spec": 0}
    for c in [c for c in a.campaigns.split(",") if c]:
        mirror(c, state)
        specs = job_specs(state, c)
        for jid, dirs in job_dirs(state, c).items():
            if jid in used:
                skipped["used"] += 1
                continue
            spec = specs.get(jid)
            if spec is None:
                skipped["no_spec"] += 1
                continue
            if (spec.get("pick") or {}).get("class") == "test":
                skipped["test"] += 1
                continue
            if str(spec.get("game_id", "")).split("-")[0] not in games:
                skipped["game"] += 1
                continue
            results = [p for d in dirs for p in d.glob("k*/result.json")]
            want = int(spec.get("tries") or len(spec.get("assignments") or []) or 1)
            newest = max((p.stat().st_mtime for p in results), default=0)
            if len(results) < want and (not results or now - newest < a.stale_min * 60):
                skipped["unripe"] += 1
                continue
            for d in dirs:
                dst = cut / c / d.parent.name / d.name
                dst.parent.mkdir(parents=True, exist_ok=True)
                subprocess.run(["cp", "-al", str(d), str(dst)], check=True)
            picked.append(jid)
    report = {"name": a.name, "jobs": len(picked), "skipped": skipped}
    if not picked:
        print(json.dumps({**report, "records": 0, "result": "no ready jobs"}), flush=True)
        return 75
    cands = state / "cuts" / f"{a.name}.candidates.jsonl.gz"
    tries_args = [x for c in sorted(p.name for p in cut.iterdir()) for x in ("--tries", str(cut / c))]
    subprocess.run([sys.executable, str(HERE / "try_records.py"), *tries_args, "--out", str(cands), "--modes", "stock",
                    "--campaign", a.name, "--report", str(state / "cuts" / f"{a.name}.report.json")], check=True)
    out = Path(a.out)
    shutil.rmtree(out, ignore_errors=True)
    sel = subprocess.run([sys.executable, str(HERE / "select_records.py"), "--in", str(cands), "--out", str(out),
                          "--budget", str(a.budget)], check=True, capture_output=True, text=True)
    n = len(list(out.glob("*.jsonl.gz")))
    report.update(records=n, selected=json.loads(sel.stdout.strip().splitlines()[-1]))
    if n < a.min:
        shutil.rmtree(out, ignore_errors=True)
        print(json.dumps({**report, "result": f"fewer than {a.min} records"}), flush=True)
        return 75
    with open(used_f, "a", encoding="utf-8") as fh:
        fh.write("\n".join(picked) + "\n")
    (state / "cuts" / f"{a.name}.json").write_text(json.dumps(report, indent=1), encoding="utf-8")
    print(json.dumps(report), flush=True)
    return 0


if __name__ == "__main__":
    os.umask(0o022)
    raise SystemExit(main())
