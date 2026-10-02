"""Watch the 4 RL seed runs: exits when all are finished, or as soon as one VM is lost (stopped/deleted before its
run finished). Prints one line per change. Usage: C:/Python312/python.exe watch_seeds.py [--max-min 55]"""
import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

ARMS = Path(r"D:\codex-work\arc3-sglang-parking\gcp\controllers\sglang-scored\arms")
NAMES = [f"cr_sgl_c99k_w25_s19_g7920_giantrlseed{x}1001" for x in "abcd"]
GCLOUD = [sys.executable, r"C:\Users\celle\AppData\Local\Google\Cloud SDK\google-cloud-sdk\lib\gcloud.py"]
sys.path.insert(0, r"D:\codex-work\arc3-sglang-parking\gcp\controllers\rl")
import rl_tree as rt  # noqa: E402


def vm_status(name: str, zone: str) -> str:
    p = subprocess.run(GCLOUD + ["compute", "instances", "describe", name, "--zone", zone, "--format=value(status)"],
                       capture_output=True, text=True)
    return p.stdout.strip() or "GONE"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-min", type=float, default=55)
    a = ap.parse_args()
    store = rt.FirestoreStore()
    last = {}
    t0 = time.time()
    while time.time() - t0 < a.max_min * 60:
        done = 0
        for n in NAMES:
            st = json.loads((ARMS / n / "STATUS.json").read_text())
            run, inst, zone = st.get("run_id"), st.get("instance") or st.get("instance_name"), st.get("zone")
            doc = store.get("arc3_runs", run) if run else None
            vs = vm_status(inst, zone) if inst and zone else "?"
            line = (f"{n[-15:]} vm={vs} status={(doc or {}).get('status')} min={(doc or {}).get('minute')} "
                    f"all25={(doc or {}).get('all25')} levels={(doc or {}).get('levels')}")
            if last.get(n) != line:
                print(time.strftime("%H:%M"), line, flush=True)
                last[n] = line
            if (doc or {}).get("status") == "finished":
                done += 1
            elif vs in ("TERMINATED", "STOPPED", "GONE") and (doc or {}).get("minute"):
                print("LOST", n, vs, flush=True)
                return 2
        if done == len(NAMES):
            print("ALL FINISHED", flush=True)
            return 0
        time.sleep(120)
    print("watch window ended (re-arm)", flush=True)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
