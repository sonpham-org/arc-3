"""Upload the spectree code and create the spectree lab VM (3-Oct-2026; pattern of lab/launch_dlab.py).

    C:/Python312/python.exe launch_spectree.py [--name arc3-spectree-1003] [--run daniel-bench-kv4cap-1003]
                                               [--max-run 14400s] [--zones ...] [--upload-only]
Code -> gs://.../daniel-draft/spectree/code/ (spectree_sim.py + the lobotomy/mtp files it imports + build_daniel_ckpt.py
+ the ARC hot map). Jobs: edit gs://.../daniel-draft/spectree/plan.txt (see spectree_worker.sh).
"""
import argparse
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
MTP = Path(r"D:\codex-work\arc3-sglang-parking\gcp\controllers\sglang-scored\lobotomy\mtp")
ST = "gs://cellens-ai-artifacts/arc3-duck/daniel-draft/spectree"
GCLOUD = [r"C:\python312\python.exe",
          r"C:\Users\celle\AppData\Local\Google\Cloud SDK\google-cloud-sdk\lib\gcloud.py"]
CODE = [HERE / "spectree_sim.py", HERE / "segment_sim.py", HERE.parent / "lab" / "build_daniel_ckpt.py", MTP / "train_draft.py",
        MTP / "draft_torch.py", MTP / "capture_io.py", MTP / "assets" / "arc-hot-64k.json"]

ap = argparse.ArgumentParser()
ap.add_argument("--name", default="arc3-spectree-1004")
ap.add_argument("--run", default="daniel-bench-kv4cap-1003")
ap.add_argument("--max-run", default="14400s")
ap.add_argument("--zones", default="us-west1-b,us-south1-b,us-east5-b,"
                                   "us-east1-b,europe-west4-a")
ap.add_argument("--upload-only", action="store_true")
a = ap.parse_args()
assert a.name.startswith("arc3-spectree-"), a.name


def run(args):
    print("$ gcloud " + " ".join(args), flush=True)
    return subprocess.run(GCLOUD + args, capture_output=True, text=True)


startup = HERE / "spectree_worker.sh"
if b"\r" in startup.read_bytes():
    sys.exit("spectree_worker.sh has CR bytes; the VM needs LF files")
LF = Path(tempfile.mkdtemp(prefix="spectree-code-"))
for p in CODE:
    (LF / p.name).write_bytes(p.read_bytes().replace(b"\r\n", b"\n"))
    r = run(["storage", "cp", "-q", str(LF / p.name), f"{ST}/code/{p.name}"])
    if r.returncode:
        sys.exit(r.stderr[-2000:])
print("UPLOADED", ST + "/code/", flush=True)
if a.upload_only:
    sys.exit(0)

for zone in a.zones.split(","):
    r = run(["compute", "instances", "create", a.name, "--project=cellensml", f"--zone={zone}",
             "--machine-type=g4-standard-48", "--image=arc3-sglang-sm120-recovery-20260926", "--image-project=cellensml",
             "--boot-disk-size=400GB", "--boot-disk-type=hyperdisk-balanced", "--provisioning-model=SPOT",
             "--instance-termination-action=DELETE", f"--max-run-duration={a.max_run}", "--scopes=cloud-platform",
             "--labels=purpose=arc3-daniel-draft,owner-task=claude-spectree",
             f"--metadata=st-run={a.run}", f"--metadata-from-file=startup-script={startup}"])
    if r.returncode == 0:
        print(f"LAUNCHED {a.name} in {zone}; results -> {ST}/results/", flush=True)
        sys.exit(0)
    out = (r.stderr or r.stdout).strip()
    print(f"{zone} -> {out.splitlines()[-1][:200] if out else r.returncode}", flush=True)
sys.exit("no zone had capacity")
