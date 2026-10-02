"""Queue one shell job on the trainer service: python submit_job.py <job_id> "<command>" [--service train4-1002]
The command runs in bash on the trainer VM; it should write into /opt/m/work/out/<job_id>/ (copied back to GCS)."""
import json
import subprocess
import sys
from pathlib import Path

GCLOUD = [sys.executable, r"C:\Users\celle\AppData\Local\Google\Cloud SDK\google-cloud-sdk\lib\gcloud.py"]
args = sys.argv[1:]
service = "train4-1002"
if "--service" in args:
    i = args.index("--service")
    service = args[i + 1]
    del args[i:i + 2]
job_id, command = args
local = Path(__file__).with_name(f"job-{job_id}.json")
local.write_text(json.dumps({"cmd": "shell", "args": {"command": command}}))
dst = f"gs://cellens-ai-artifacts/arc3-rl/trainer/{service}/jobs/{job_id}.json"
p = subprocess.run(GCLOUD + ["storage", "cp", str(local), dst], capture_output=True, text=True)
print(("queued " if p.returncode == 0 else "FAILED ") + dst)
