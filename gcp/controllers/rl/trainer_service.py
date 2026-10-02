"""Trainer service for the RL loop (plan: docs/plans/2026-10-01-rl-on-burst-games.md §0b steps 1 and 4).

Runs on the training VM after setup. Polls a GCS job folder and runs each job once, in order:
  gs://cellens-ai-artifacts/arc3-rl/trainer/<service>/jobs/<job_id>.json      submitted by the session
  gs://cellens-ai-artifacts/arc3-rl/trainer/<service>/out/<job_id>/...        logs, CHECK.json / ADAPTER.json / MERGE_REPORT
  gs://cellens-ai-artifacts/arc3-rl/trainer/<service>/status.json              heartbeat (job running, GPU memory)
A job = {"cmd": "check" | "train" | "merge" | "shell", "args": {...}}:
  check  lora_train.py check   (args: records glob in GCS, steps, rank, alpha, lr, gpu_gib)
  train  lora_train.py train   (args: records glob, epochs, limit, accum, lr, rank, alpha, init_adapter (gs://))
  merge  merge_lora.py         (args: adapter (gs://), checkpoint (gs:// prefix), out (gs:// prefix), stochastic, mult)
  shell  one command line (for setup checks only)
Records and adapters are copied from GCS to local disk first; outputs are copied back. One job at a time.

Usage (VM): python trainer_service.py --service train4-1001 --model /opt/m/bf16 --hf /opt/m/bf16 --work /opt/m/work
"""
from __future__ import annotations

import argparse
import json
import shlex
import subprocess
import sys
import threading
import time
from pathlib import Path

ROOT = "gs://cellens-ai-artifacts/arc3-rl/trainer"
HERE = Path(__file__).resolve().parent


def sh(cmd: list[str] | str, log: Path | None = None, check: bool = False) -> int:
    if isinstance(cmd, str):
        cmd = ["bash", "-lc", cmd]
    with (open(log, "a", encoding="utf-8") if log else open("/dev/null", "w")) as fh:
        p = subprocess.run(cmd, stdout=fh if log else None, stderr=subprocess.STDOUT if log else None)
    if check and p.returncode:
        raise RuntimeError(f"{cmd} -> {p.returncode}")
    return p.returncode


def gls(prefix: str) -> list[str]:
    p = subprocess.run(["gcloud", "storage", "ls", prefix], capture_output=True, text=True)
    return [l.strip() for l in p.stdout.splitlines() if l.strip()] if p.returncode == 0 else []


def gcat(uri: str) -> str:
    return subprocess.run(["gcloud", "storage", "cat", uri], capture_output=True, text=True, check=True).stdout


def gput(local: Path, uri: str) -> None:
    sh(["gcloud", "storage", "cp", "-r", str(local), uri])


def heartbeat(service: str, state: dict) -> None:
    gpu = subprocess.run(["nvidia-smi", "--query-gpu=index,memory.used,utilization.gpu", "--format=csv,noheader"],
                         capture_output=True, text=True).stdout.strip().splitlines()
    body = json.dumps(dict(state, gpus=gpu, at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())))
    subprocess.run(["gcloud", "storage", "cp", "-", f"{ROOT}/{service}/status.json"], input=body, text=True,
                   capture_output=True)


def fetch_records(glob_uri: str, dest: Path) -> str:
    dest.mkdir(parents=True, exist_ok=True)
    sh(["gcloud", "storage", "cp", glob_uri, str(dest)], check=True)
    return str(dest / "*.jsonl.gz")


class LogMirror:
    """Copy the running job's logs to GCS every `every` seconds (progress is visible while the job runs): job.log
    and the trainer's train_log.jsonl, each with a <file>.mtime.json sidecar (train_log.jsonl gains a line when a
    record finishes, so its mtime dates the latest record for the live page)."""

    def __init__(self, out: Path, uri: str, every: float = 60.0, names=("job.log", "train_log.jsonl")):
        self.out, self.uri, self.every, self.names = out, uri.rstrip("/"), every, names
        self.seen: dict[str, float] = {}
        self.stop = threading.Event()
        self.thread = threading.Thread(target=self._run, daemon=True)

    def _run(self):
        while not self.stop.wait(self.every):
            for n in self.names:
                f = self.out / n
                if not f.exists() or self.seen.get(n) == f.stat().st_mtime:
                    continue
                mtime = f.stat().st_mtime
                subprocess.run(["gcloud", "storage", "cp", str(f), f"{self.uri}/{n}"], capture_output=True)
                side = json.dumps({"file": n, "mtime": int(mtime), "at": int(time.time())})
                subprocess.run(["gcloud", "storage", "cp", "-", f"{self.uri}/{n}.mtime.json"], input=side, text=True,
                               capture_output=True)
                self.seen[n] = mtime

    def __enter__(self):
        self.thread.start()
        return self

    def __exit__(self, *exc):
        self.stop.set()


def run_job(job_id: str, job: dict, a) -> int:
    out = Path(a.work) / "out" / job_id
    out.mkdir(parents=True, exist_ok=True)
    log = out / "job.log"
    with LogMirror(out, f"{ROOT}/{a.service}/out/{job_id}"):
        return _run_job(job_id, job, a, out, log)


def _run_job(job_id: str, job: dict, a, out: Path, log: Path) -> int:
    args = job.get("args") or {}
    py = sys.executable
    common = ["--model", a.model, "--hf", a.hf, "--gpus", str(args.get("gpus", a.gpus)), "--attn", str(args.get("attn", "")),
              "--gpu-gib", str(args.get("gpu_gib", a.gpu_gib)), "--rank", str(args.get("rank", 32)),
              "--alpha", str(args.get("alpha", 64)), "--lr", str(args.get("lr", 2e-5))]
    if job["cmd"] in ("check", "train"):
        recs = fetch_records(args["records"], Path(a.work) / "records" / job_id)
        cmd = [py, str(HERE / "lora_train.py"), job["cmd"], *common, "--records", recs, "--out", str(out)]
        cmd += [str(x) for x in args.get("extra", [])]          # e.g. ["--fast", "1", "--ladder", "30000,60000"]
        if job["cmd"] == "check":
            cmd += ["--steps", str(args.get("steps", 3))]
        else:
            cmd += ["--epochs", str(args.get("epochs", 1)), "--accum", str(args.get("accum", 8)),
                    "--limit", str(args.get("limit", 0))]
            if args.get("init_adapter"):
                local = Path(a.work) / "init" / job_id
                local.mkdir(parents=True, exist_ok=True)
                sh(["gcloud", "storage", "cp", "-r", args["init_adapter"].rstrip("/") + "/*", str(local)], check=True)
                cmd += ["--init-adapter", str(local)]
        rc = sh(cmd, log)
    elif job["cmd"] == "merge":
        adapter = Path(a.work) / "merge" / job_id / "adapter"
        ck = Path(a.work) / "ckpt" / Path(args["checkpoint"].rstrip("/")).name
        dst = Path(a.work) / "merge" / job_id / "merged"
        adapter.mkdir(parents=True, exist_ok=True)
        sh(["gcloud", "storage", "cp", "-r", args["adapter"].rstrip("/") + "/*", str(adapter)], check=True)
        if not ck.exists():
            ck.mkdir(parents=True, exist_ok=True)
            sh(["gcloud", "storage", "cp", "-r", args["checkpoint"].rstrip("/") + "/*", str(ck)], check=True)
        cmd = [py, str(HERE / "merge_lora.py"), "--adapter", str(adapter), "--checkpoint", str(ck), "--out", str(dst),
               "--mult", str(args.get("mult", 1.0))] + (["--stochastic"] if args.get("stochastic") else []) \
            + (["--expect-identical"] if args.get("expect_identical") else [])
        rc = sh(cmd, log)
        if rc == 0 and args.get("out"):
            sh(["gcloud", "storage", "rsync", "-r", str(dst), args["out"].rstrip("/")], log)
        sh(["cp", str(dst / "MERGE_REPORT.json"), str(out)])
    elif job["cmd"] == "shell":
        rc = sh(args["command"], log)
    else:
        raise ValueError(job["cmd"])
    (out / "EXIT").write_text(str(rc))
    gput(out, f"{ROOT}/{a.service}/out/")
    return rc


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--service", required=True)
    ap.add_argument("--model", required=True)
    ap.add_argument("--hf", required=True)
    ap.add_argument("--work", required=True)
    ap.add_argument("--gpus", type=int, default=4)
    ap.add_argument("--gpu-gib", type=int, default=88)
    ap.add_argument("--poll", type=int, default=60)
    a = ap.parse_args()
    done = set(Path(a.work, "done.txt").read_text().split()) if Path(a.work, "done.txt").exists() else set()
    while True:
        jobs = sorted(u for u in gls(f"{ROOT}/{a.service}/jobs/") if u.endswith(".json"))
        todo = [u for u in jobs if Path(u).stem not in done]
        if not todo:
            heartbeat(a.service, {"state": "idle", "done": sorted(done)[-5:]})
            time.sleep(a.poll)
            continue
        uri = todo[0]
        job_id = Path(uri).stem
        job = json.loads(gcat(uri))
        heartbeat(a.service, {"state": "running", "job": job_id, "cmd": job.get("cmd")})
        t0 = time.time()
        try:
            rc = run_job(job_id, job, a)
        except Exception as e:  # noqa: BLE001  (a bad job must not kill the service)
            rc = -1
            Path(a.work, "out", job_id).mkdir(parents=True, exist_ok=True)
            Path(a.work, "out", job_id, "ERROR.txt").write_text(repr(e))
            gput(Path(a.work, "out", job_id), f"{ROOT}/{a.service}/out/")
        done.add(job_id)
        Path(a.work, "done.txt").write_text("\n".join(sorted(done)) + "\n")     # newline-terminated: appends stay lines
        heartbeat(a.service, {"state": "finished", "job": job_id, "rc": rc, "sec": round(time.time() - t0)})


if __name__ == "__main__":
    raise SystemExit(main())
