"""Did the server stay alive to the end of a Daniel-base run? (2-Oct-2026, daniel-draft)
A dead server leaves the notebook playing on and exiting rc 0 with a frozen score (Reverse-flow thread, bf16kv-b OOM).
Per run: OOM / traceback / scheduler-exception lines in serve.log, last decode time, finish time, gap.
  python dead_server_check.py RUN [RUN ...]
"""
import re
import subprocess
import sys
from datetime import datetime

G = [r"C:\python312\python.exe", r"C:\Users\celle\AppData\Local\Google\Cloud SDK\google-cloud-sdk\lib\gcloud.py"]
B = "gs://cellens-ai-artifacts/arc3-duck/daniel-base/runs"
BAD = re.compile(r"out of memory|OutOfMemoryError|Traceback|Scheduler hit an exception|Received sigquit from a child", re.I)
for run in sys.argv[1:]:
    log = subprocess.run(G + ["storage", "cat", f"{B}/{run}/working/serve.log"], capture_output=True).stdout.decode("utf-8", "replace")
    ph = subprocess.run(G + ["storage", "cat", f"{B}/{run}/phases.tsv"], capture_output=True).stdout.decode("utf-8", "replace")
    bad = [l for l in log.splitlines() if BAD.search(l) and "server_args=" not in l and "sitecustomize" not in l]
    dec = re.findall(r"^\[(\S+ \S+)\] Decode batch", log, re.M)
    fin = [l.split("\t") for l in ph.strip().splitlines() if "finish" in l]
    last = datetime.strptime(dec[-1], "%Y-%m-%d %H:%M:%S") if dec else None
    end = datetime.strptime(fin[-1][0], "%Y-%m-%dT%H:%M:%SZ") if fin else None
    gap = (end - last).total_seconds() / 60 if (last and end) else None
    print(f"{run:34s} bad_lines {len(bad):3d} | last decode {last} | finish {end} {fin[-1][2] if fin else ''} | gap "
          f"{'%.0f min' % gap if gap is not None else '?'}" + (f" | first bad: {bad[0][:160]}" if bad else ""))
