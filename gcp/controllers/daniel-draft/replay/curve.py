"""Summarize lab job logs (4-Oct-2026): python curve.py <vm>:<job> ... -> per job: rows, evals (step: RS tokens kept per
check), sec/step."""
import json
import subprocess
import sys

GC = [r"C:\python312\python.exe", r"C:\Users\celle\AppData\Local\Google\Cloud SDK\google-cloud-sdk\lib\gcloud.py"]
RP = "gs://cellens-ai-artifacts/arc3-duck/daniel-draft/replay/results"
for spec in sys.argv[1:]:
    vm, job = spec.split(":")
    txt = subprocess.run(GC + ["storage", "cat", f"{RP}/arc3-drep-{vm}/{job}.log.jsonl"], capture_output=True,
                         text=True).stdout
    ev, info, sps, msteps = [], {}, None, None
    for l in txt.splitlines():
        try:
            d = json.loads(l)
        except ValueError:
            continue
        if d.get("event") == "data":
            info = {"train_rows": d.get("train_rows"), "hold_rows": d.get("holdout_rows")}
            msteps = d.get("config", {}).get("msteps")
        elif d.get("event") == "eval":
            ev.append((d["step"], d.get("served_rs_expected_tokens_per_step")))
        elif d.get("event") == "train":
            sps = d.get("sec_per_step")
    best = max((e[1] for e in ev if e[1] is not None), default=None)
    print(f"{vm}:{job} msteps={msteps} {info} sec/step={sps} best={best} evals={ev}")
