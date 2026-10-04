"""Stage a rollout queue for one VM: copy each job's source logs from GCS and rewrite its paths for the container.

Author: Claude Opus 5.5 (3-Oct-2026). Runs on the VM host (not in the notebook: the container has no network).

  python3 stage_jobs.py <gs://.../queue/<campaign>> <local root>      # writes <root>/jobs/*.json, <root>/src/...
The container mounts <root> read-only at /kaggle/rollout, so every path in a staged job starts with /kaggle/rollout.
A job whose logs cannot be fetched is left out (listed in <root>/stage-report.json). Held-out games are refused.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

FENCED = {"lf52", "tn36", "re86", "dc22", "su15", "as66"}
MOUNT = "/kaggle/rollout"


def gs(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["timeout", "600", "gcloud", "storage", *args], capture_output=True, text=True)


def main(queue: str, root: str) -> int:
    root_p = Path(root)
    (root_p / "jobs").mkdir(parents=True, exist_ok=True)
    (root_p / "src").mkdir(parents=True, exist_ok=True)
    r = gs("cp", "-r", f"{queue.rstrip('/')}/jobs/*", str(root_p / "incoming"))
    if r.returncode != 0:
        print(r.stderr[-1000:])
        return 1
    report = {"staged": [], "skipped": []}
    fetched: dict[str, str] = {}
    for f in sorted((root_p / "incoming").glob("*.json")):
        job = json.loads(f.read_text())
        if job["game_id"].split("-")[0] in FENCED:
            report["skipped"].append({"job": job["job_id"], "why": "fenced"})
            continue
        ok = True
        for key in ("requests", "events", "coach_log"):
            uri = (job.get("source") or {}).get(key)
            if not uri:
                continue
            if uri not in fetched:
                rel = uri.split("://", 1)[-1]
                dst = root_p / "src" / rel
                dst.parent.mkdir(parents=True, exist_ok=True)
                if gs("cp", uri, str(dst)).returncode != 0:
                    ok = False
                    report["skipped"].append({"job": job["job_id"], "why": f"fetch {uri}"})
                    break
                fetched[uri] = f"{MOUNT}/src/{rel}"
            job["source"][key] = fetched[uri]
        if ok:
            (root_p / "jobs" / f.name).write_text(json.dumps(job, indent=1))
            report["staged"].append(job["job_id"])
    (root_p / "stage-report.json").write_text(json.dumps(report, indent=1))
    print(f"staged {len(report['staged'])} jobs, skipped {len(report['skipped'])}")
    return 0 if report["staged"] else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1], sys.argv[2]))
