"""Upload the daniel-draft lab code and create one lab VM (G4 Spot, golden image) running dlab_startup.sh (2-Oct-2026).

    C:/Python312/python.exe launch_dlab.py --run daniel-draftcap-a-1002 [--name arc3-dlab-1002a] [--steps 3500]
                                           [--max-run 21600s] [--zones a,b,...] [--upload-only]

Code -> gs://.../daniel-draft/code/: this folder's build/package scripts + the lobotomy/mtp trainer files.
"""
import argparse
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
MTP = Path(r"D:\codex-work\arc3-sglang-parking\gcp\controllers\sglang-scored\lobotomy\mtp")
DD = "gs://cellens-ai-artifacts/arc3-duck/daniel-draft"
# gcloud.cmd cannot be launched from a Python subprocess on this machine; call gcloud.py directly.
GCLOUD = [r"C:\python312\python.exe",
          r"C:\Users\celle\AppData\Local\Google\Cloud SDK\google-cloud-sdk\lib\gcloud.py"]
CODE = [HERE / "build_daniel_ckpt.py", HERE / "package_daniel_draft.py",
        MTP / "train_draft.py", MTP / "verify_draft.py", MTP / "draft_torch.py", MTP / "capture_io.py"]

ap = argparse.ArgumentParser()
ap.add_argument("--run", required=True, help="the capture run id (daniel-base/runs/<run>)")
ap.add_argument("--name", default="arc3-dlab-1002a")
ap.add_argument("--steps", default="3500")
ap.add_argument("--max-run", default="21600s")
ap.add_argument("--zones", default="us-east5-b,us-east5-c,us-south1-a,us-west4-a,us-west1-a,us-east4-b,us-east4-c,"
                                   "us-south1-b,us-west1-b,europe-west4-a")  # us-central1 reserved for RL (Son, 4-Oct)
ap.add_argument("--upload-only", action="store_true")
ap.add_argument("--startup", default="dlab_startup.sh", help="startup script in this folder")
a = ap.parse_args()


def run(args):
    print("$ gcloud " + " ".join(args), flush=True)
    return subprocess.run(GCLOUD + args, capture_output=True, text=True)


if b"\r" in (HERE / a.startup).read_bytes():
    sys.exit(f"{a.startup} has CR bytes; the lab VM needs LF files")
LF = Path(tempfile.mkdtemp(prefix="dlab-code-"))  # the checkout may have CRLF .py files: upload LF copies
for p in CODE:
    (LF / p.name).write_bytes(p.read_bytes().replace(b"\r\n", b"\n"))
    r = run(["storage", "cp", "-q", str(LF / p.name), f"{DD}/code/{p.name}"])
    if r.returncode:
        sys.exit(r.stderr[-2000:])
print("UPLOADED", DD + "/code/", flush=True)
if a.upload_only:
    sys.exit(0)

for zone in a.zones.split(","):
    r = run(["compute", "instances", "create", a.name, "--project=cellensml", f"--zone={zone}",
             "--machine-type=g4-standard-48", "--image=arc3-sglang-sm120-recovery-20260926", "--image-project=cellensml",
             "--boot-disk-size=400GB", "--boot-disk-type=hyperdisk-balanced", "--provisioning-model=SPOT",
             "--instance-termination-action=DELETE", f"--max-run-duration={a.max_run}", "--scopes=cloud-platform",
             "--labels=purpose=arc3-daniel-draft,owner-task=claude-daniel-draft",
             f"--metadata=dlab-run={a.run},dlab-steps={a.steps}",
             f"--metadata-from-file=startup-script={HERE / a.startup}"])
    if r.returncode == 0:
        print(f"LAUNCHED {a.name} in {zone}; results -> {DD}/results/{a.run}/", flush=True)
        sys.exit(0)
    out = (r.stderr or r.stdout).strip()
    print(f"{zone} -> {out.splitlines()[-1][:200] if out else r.returncode}", flush=True)
sys.exit("no zone had capacity")
