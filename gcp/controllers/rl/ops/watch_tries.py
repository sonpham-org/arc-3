"""Watch an RL try campaign: one line per change (VM state, busy lanes, tries done / valid / cleared, results);
exits when every VM is gone or idle-and-done, as soon as one VM is lost (stopped/deleted before its deadline), or
after --max-min. Usage: C:/Python312/python.exe watch_tries.py --campaign rl-1002a --max-min 55"""
import argparse
import json
import re
import subprocess
import sys
import time
from pathlib import Path

GCLOUD = [sys.executable, r"C:\Users\celle\AppData\Local\Google\Cloud SDK\google-cloud-sdk\lib\gcloud.py"]
ARMS = Path(r"D:\codex-work\arc3-sglang-parking\gcp\controllers\sglang-scored\arms")
ROOT = "gs://cellens-ai-artifacts/arc3-rl/tries"


def g(*args):
    p = subprocess.run(GCLOUD + list(args), capture_output=True, text=True)
    return p.stdout if p.returncode == 0 else ""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--campaign", required=True)
    ap.add_argument("--max-min", type=float, default=55)
    a = ap.parse_args()
    arms = sorted(p.name for p in ARMS.glob(f"rltry_{a.campaign.replace('-', '')}_vm*"))
    t0, last = time.time(), {}
    while time.time() - t0 < a.max_min * 60:
        lines = []
        lost = 0
        for arm in arms:
            st = json.loads((ARMS / arm / "STATUS.json").read_text()) if (ARMS / arm / "STATUS.json").exists() else {}
            inst, zone = st.get("instance") or st.get("instance_name"), st.get("zone")
            vs = g("compute", "instances", "describe", inst, "--zone", zone, "--format=value(status)").strip() \
                if inst and zone else "not-launched"
            if inst and vs in ("", "TERMINATED", "STOPPED", "SUSPENDED"):
                lost += 1
            lines.append(f"{arm[-3:]} {zone or '-'} {vs or 'GONE'}")
        status = []
        for name in g("storage", "ls", f"{ROOT}/{a.campaign}/status/").split():
            try:
                s = json.loads(g("storage", "cat", name))
                status.append(f"{s['vm'][-3:]}: busy {s['busy']} {s['stats']} {s['minutes_left']}min")
            except Exception:  # noqa: BLE001
                pass
        res = [n for n in g("storage", "ls", f"{ROOT}/{a.campaign}/results/").split() if n.endswith(".json")]
        claims = len([n for n in g("storage", "ls", f"{ROOT}/{a.campaign}/claims/").split() if n.endswith(".json")])
        line = " | ".join(lines) + f" || claims {claims} results {len(res)} || " + " ; ".join(status)
        if line != last.get("l"):
            print(time.strftime("%H:%M"), line, flush=True)
            last["l"] = line
        if lost:
            print("VM LOST", flush=True)
            return 2
        time.sleep(90)
    print("watch window ended (re-arm)", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
