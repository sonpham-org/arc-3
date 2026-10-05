"""Watch many Daniel-base runs at once (3-Oct-2026, daniel-draft context grid): prints phase changes, finishes, failures
and VMs that vanish (Spot preemption), one line each; exits when every run has finished or vanished, or after --minutes.

  python fleet_watch.py --prefix daniel-ctx- --vm-prefix arc3-dctx- [--every 180] [--minutes 28]
"""
import argparse
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor

G = [r"C:\python312\python.exe", r"C:\Users\celle\AppData\Local\Google\Cloud SDK\google-cloud-sdk\lib\gcloud.py"]
B = "gs://cellens-ai-artifacts/arc3-duck/daniel-base/runs"


def run(args, timeout=120):
    try:
        r = subprocess.run(G + args, capture_output=True, timeout=timeout)
        return r.returncode, r.stdout.decode("utf-8", "replace"), r.stderr.decode("utf-8", "replace")
    except subprocess.TimeoutExpired:
        return 1, "", "timeout"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--prefix", required=True)
    ap.add_argument("--vm-prefix", required=True)
    ap.add_argument("--every", type=int, default=180)
    ap.add_argument("--minutes", type=float, default=28)
    a = ap.parse_args()
    end = time.time() + a.minutes * 60
    last, gone, done = {}, set(), set()
    first = True
    while time.time() < end:
        rc, _, err = run(["auth", "print-access-token"], 60)
        if rc:
            print("GCLOUD AUTH EXPIRED: ask Son to run gcloud.cmd auth login", flush=True)
            time.sleep(600)
            continue
        _, out, _ = run(["storage", "ls", f"{B}/"])
        runs = sorted(l.rstrip("/").rsplit("/", 1)[-1] for l in out.split() if f"/{a.prefix}" in l)
        _, vms, _ = run(["compute", "instances", "list", f"--filter=name~^{a.vm_prefix}", "--format=value(name,status)"])
        vm_state = dict(l.split()[:2] for l in vms.strip().splitlines() if l.strip())
        with ThreadPoolExecutor(16) as ex:
            phases = dict(zip(runs, ex.map(lambda r: run(["storage", "cat", f"{B}/{r}/phases.tsv"])[1], runs)))
        for r in runs:
            lines = [l for l in phases[r].strip().splitlines() if l.strip()]
            ph = lines[-1].split("\t")[-1] if lines else "?"
            vm = a.vm_prefix + r[len(a.prefix):]
            if ph != last.get(r) and (first or any(k in ph for k in ("server_", "finish", "failed"))):
                if not first or "finish" in ph or "failed" in ph:
                    print(f"{r}: {ph}", flush=True)
            last[r] = ph
            if "finish" in ph or "failed" in ph:
                done.add(r)
            elif vm not in vm_state and r not in gone and vm_state:
                print(f"{r}: VM {vm} GONE at phase '{ph}' (preempted?)", flush=True)
                gone.add(r)
        if first:
            counts = {}
            for r in runs:
                counts[last[r]] = counts.get(last[r], 0) + 1
            print(f"watching {len(runs)} runs: {counts}", flush=True)
            first = False
        if runs and len(done | gone) == len(runs):
            print("ALL RUNS FINISHED OR GONE", flush=True)
            return
        time.sleep(a.every)


if __name__ == "__main__":
    sys.exit(main())
