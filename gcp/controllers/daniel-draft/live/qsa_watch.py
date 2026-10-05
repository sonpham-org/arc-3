"""Watch the QSA ring runs + decode profiles (3-Oct-2026, daniel-draft): one line per event — phase changes (server
ready / finish / failed), VM gone, a server crash in serve.log, the qsa_check.json summary, the profile log.
  python qsa_watch.py RUN [RUN ...] [--every 120] [--minutes 30]
"""
import argparse
import json
import re
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor

G = [r"C:\python312\python.exe", r"C:\Users\celle\AppData\Local\Google\Cloud SDK\google-cloud-sdk\lib\gcloud.py"]
B = "gs://cellens-ai-artifacts/arc3-duck/daniel-base/runs"
CRASH = re.compile(r"Traceback|NotImplementedError|Scheduler hit an exception|crashed with exit code|OutOfMemoryError|"
                   r"CUDA error|illegal memory|AssertionError")


def gs(args, timeout=120):
    try:
        r = subprocess.run(G + args, capture_output=True, timeout=timeout)
        return r.returncode, r.stdout.decode("utf-8", "replace")
    except subprocess.TimeoutExpired:
        return 1, ""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("runs", nargs="+")
    ap.add_argument("--every", type=int, default=120)
    ap.add_argument("--minutes", type=float, default=30)
    a = ap.parse_args()
    end = time.time() + a.minutes * 60
    seen = {}
    while time.time() < end:
        if gs(["auth", "print-access-token"], 60)[0]:
            print("GCLOUD AUTH EXPIRED: ask Son to run gcloud.cmd auth login", flush=True)
            time.sleep(600)
            continue
        _, vms = gs(["compute", "instances", "list", "--filter=name~^arc3-d(bench|ctx)-", "--format=value(name,status)"])
        vm = dict(l.split()[:2] for l in vms.strip().splitlines() if l.strip())

        def probe(run):
            _, ph = gs(["storage", "cat", f"{B}/{run}/phases.tsv"])
            last = ph.strip().splitlines()[-1].split("\t")[-1] if ph.strip() else "?"
            _, qc = gs(["storage", "cat", f"{B}/{run}/working/qsa_check.json"])
            _, plog = gs(["storage", "cat", f"{B}/{run}/working/profile/log.txt"])
            _, bat = gs(["storage", "cat", f"{B}/{run}/working/ba_test.json"])
            _, k4t = gs(["storage", "cat", f"{B}/{run}/working/kv4_test.json"])
            _, k4h = gs(["storage", "cat", f"{B}/{run}/working/kv4h_test.json"])
            crash = ""
            if "server_ready" in last or "finish" in last or "failed" in last or "server" in last:
                _, log = gs(["storage", "cat", f"{B}/{run}/working/serve.log"], 180)
                m = CRASH.search(log)
                if m:
                    i = m.start()
                    crash = log[max(0, i - 200): i + 400].replace("\n", " | ")[-500:]
            return run, last, qc, plog, crash, bat, k4t, k4h

        with ThreadPoolExecutor(8) as ex:
            res = list(ex.map(probe, a.runs))
        for run, last, qc, plog, crash, bat, k4t, k4h in res:
            s = seen.setdefault(run, {})
            if last != s.get("phase") and any(k in last for k in ("server_", "finish", "failed", "notebook")):
                print(f"{run}: {last}", flush=True)
            s["phase"] = last
            if qc.strip() and not s.get("qc"):
                try:
                    d = json.loads(qc)
                    acc = [round(x, 2) for x in d.get("accept_len", []) if x]
                    print(f"{run}: QSA CHECK ring {d.get('ring')} steps {d.get('spec_steps')}: cached-vs-fresh mean|dlp| "
                          f"{d.get('mean_abs_dlp'):.4f}, top1 agree {d.get('top1_agree'):.3f}, n {d.get('n')}, "
                          f"gen {d.get('gen_seconds')} s, accept {acc}", flush=True)
                except Exception as e:
                    print(f"{run}: qsa_check.json unreadable {e!r}", flush=True)
                s["qc"] = True
            for tag, txt in (("KV4 TEST", k4t), ("KV4 HOST TEST", k4h)):
                if txt.strip() and not s.get(tag):
                    print(f"{run}: {tag} {txt.strip().splitlines()[-1][:300]}", flush=True)
                    s[tag] = True
            if bat.strip() and not s.get("bat"):
                try:
                    d = json.loads(bat.strip().splitlines()[-1])
                    rows = d.get("rows", [])
                    print(f"{run}: BA TEST ok={d.get('ok')} " + "; ".join(
                        f"{r['tokens']}t k0={r['k0']} skew={r['skew']}: {r['experts_before']}->{r['experts_after']}"
                        for r in rows if r.get("skew")), flush=True)
                except Exception as e:
                    print(f"{run}: ba_test.json unreadable {e!r}: {bat[:200]}", flush=True)
                s["bat"] = True
            if plog.strip() and plog != s.get("plog"):
                print(f"{run}: PROFILE {plog.strip().splitlines()[-1][:200]}", flush=True)
                s["plog"] = plog
            if crash and not s.get("crash"):
                print(f"{run}: CRASH in serve.log: {crash}", flush=True)
                s["crash"] = True
            name = ("arc3-dctx-" + run.replace("daniel-ctx-", "")) if run.startswith("daniel-ctx-") else ("arc3-dbench-" + run.replace("daniel-bench-", ""))
            if vm and name not in vm and "finish" not in last and not s.get("gone"):
                print(f"{run}: VM {name} GONE at '{last}'", flush=True)
                s["gone"] = True
        if all(("finish" in seen[r].get("phase", "") or seen[r].get("gone")) for r in a.runs):
            print("ALL DONE", flush=True)
            return
        time.sleep(a.every)


if __name__ == "__main__":
    sys.exit(main())
