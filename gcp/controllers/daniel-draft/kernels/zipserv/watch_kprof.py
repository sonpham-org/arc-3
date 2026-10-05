"""Watch one bench run and reap its VM (4-Oct-2026, Kernel optimizations thread).
One stdout line per event: phase changes, pre-script results (pre_*.json), profile log lines, serve.log crash, VM gone,
gcloud auth expiry. On finish: waits for the VM to stop, deletes it by exact name, prints DONE and exits.
State persists in a JSON file so a re-armed watch does not repeat events.
  python watch_kprof.py RUN VM ZONE [--every 90] [--minutes 29]
"""
import argparse
import json
import re
import subprocess
import time
from pathlib import Path

G = [r"C:\python312\python.exe", r"C:\Users\celle\AppData\Local\Google\Cloud SDK\google-cloud-sdk\lib\gcloud.py"]
B = "gs://cellens-ai-artifacts/arc3-duck/daniel-base/runs"
CRASH = re.compile(r"Traceback|Scheduler hit an exception|crashed with exit code|OutOfMemoryError|CUDA error|"
                   r"illegal memory|exit code -9")


def gs(args, timeout=120):
    try:
        r = subprocess.run(G + args, capture_output=True, timeout=timeout)
        return r.returncode, r.stdout.decode("utf-8", "replace")
    except subprocess.TimeoutExpired:
        return 1, ""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("run")
    ap.add_argument("vm")
    ap.add_argument("zone")
    ap.add_argument("--every", type=int, default=90)
    ap.add_argument("--minutes", type=float, default=29)
    ap.add_argument("--pre", default="", help="pre-script stem whose pre_<stem>.json to report once it has a verdict")
    a = ap.parse_args()
    sf = Path(__file__).with_name(f".watch_{a.run}.json")
    s = json.loads(sf.read_text()) if sf.exists() else {}
    end = time.time() + a.minutes * 60

    def say(msg):
        print(f"{time.strftime('%H:%M', time.gmtime())}Z {a.run}: {msg}", flush=True)

    while time.time() < end:
        if gs(["auth", "print-access-token"], 150)[0]:
            s["auth_fail"] = s.get("auth_fail", 0) + 1
            if s["auth_fail"] >= 2:   # one slow token refresh is not an expiry
                say("GCLOUD AUTH EXPIRED: Son needs to run gcloud.cmd auth login")
            time.sleep(120)
            continue
        s["auth_fail"] = 0
        _, ph = gs(["storage", "cat", f"{B}/{a.run}/phases.tsv"])
        last = ph.strip().splitlines()[-1].split("\t")[-1] if ph.strip() else "?"
        if last != s.get("phase"):
            say(f"phase {last}")
            s["phase"] = last
        _, pj = gs(["storage", "cat", f"{B}/{a.run}/working/pre_exp_hist.json"])
        if pj.strip() and not s.get("pre"):
            for ln in pj.strip().splitlines():
                try:
                    d = json.loads(ln)
                except Exception:
                    continue
                if d.get("stage") == "device":
                    say(f"DEVICE {json.dumps({k: v for k, v in d.items() if k != 't'})}")
                if d.get("stage") == "summary" and d.get("group") in ("target_all", "target_big_ge8MB", "drafter_all"):
                    say(f"HIST {d['group']}: {d['gb']} GB, cover7 {d['cover7_byte_weighted']}, "
                        f"{d['bits_per_weight']} bits/weight, saves {d['saved_gb']} GB, min {d['min_cover7']}")
                if d.get("stage") == "done":
                    say(f"HIST done ({d.get('tensors')} tensors) in {d.get('t')} s")
            s["pre"] = True
        if a.pre and not s.get("pre2"):
            _, pj2 = gs(["storage", "cat", f"{B}/{a.run}/working/pre_{a.pre}.json"])
            lines = [l for l in pj2.strip().splitlines() if l.startswith("{")]
            if any('"verdict"' in l for l in lines):
                for l in lines:
                    if any(k in l for k in ('"verdict"', '"dispatch"', '"hc_combine_time"', '"error"', '"accuracy"',
                                             '"timing_cold"', '"graph_replay"', '"bitwise"')):
                        say("PRE " + l[:300])
                s["pre2"] = True
        _, plog = gs(["storage", "cat", f"{B}/{a.run}/working/profile/log.txt"])
        if plog.strip() and plog != s.get("plog"):
            new = plog[len(s.get("plog", "")):] if plog.startswith(s.get("plog", "")) else plog
            for ln in new.strip().splitlines()[-3:]:
                say(f"PROFILE {ln[:200]}")
            s["plog"] = plog
        if any(k in last for k in ("server", "finish", "failed")) and not s.get("crash"):
            _, log = gs(["storage", "cat", f"{B}/{a.run}/working/serve.log"], 180)
            m = CRASH.search(log)
            if m:
                say("CRASH in serve.log: " + log[max(0, m.start() - 200): m.start() + 300].replace("\n", " | ")[-450:])
                s["crash"] = True
        rc, st = gs(["compute", "instances", "describe", a.vm, "--zone", a.zone, "--format=value(status)"])
        st = st.strip()
        if rc and "finish" not in last and not s.get("gone"):
            say(f"VM {a.vm} GONE (Spot?) at phase '{last}'")
            s["gone"] = True
        sf.write_text(json.dumps(s))
        # Terminal = the runner's own "finish <reason>" phase only. ("server_server_failed attempt_1" is NOT terminal:
        # the runner retries in a fresh container. 4-Oct: matching "failed" here deleted a serving attempt 2.)
        if last.startswith("finish") or s.get("gone"):
            if not rc:
                waited = 0
                while st != "TERMINATED" and waited < 900:
                    time.sleep(30)
                    waited += 30
                    st = gs(["compute", "instances", "describe", a.vm, "--zone", a.zone, "--format=value(status)"])[1].strip()
                if st == "TERMINATED":   # never delete a VM that is still running
                    drc, _ = gs(["compute", "instances", "delete", a.vm, "--zone", a.zone, "--quiet"], 300)
                    say(f"VM {a.vm} {'deleted' if drc == 0 else 'DELETE FAILED'}")
                else:
                    say(f"VM {a.vm} still {st} 15 min after finish: NOT deleted, check by hand")
            say("DONE")
            return
        time.sleep(a.every)
    say("watch window over (re-arm)")


if __name__ == "__main__":
    main()
