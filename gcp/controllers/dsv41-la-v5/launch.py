"""Launch the DeepSeek-V4.1-Flash ceiling arm on one Spot g4-standard-384 (8x RTX PRO 6000).

Mirrors the LA controller's direct-instance pattern (instance-body.json, Spot, maxRunDuration
14400 s with instanceTerminationAction DELETE, guest self-delete) with the model-side metadata
swapped. Usage:  python launch.py [--dry-run] [--zones us-central1-b,us-central1-c,...]
"""
import argparse, hashlib, json, os, secrets, subprocess, sys, time, uuid
from pathlib import Path

HERE = Path(__file__).resolve().parent
ARM = HERE / "arms" / "dsv41_la_v5_clean_return_a"
# Source VM body. On the machine that built this it was the live LA arm's own body; a fresh
# checkout has no such directory, so fall back to the equivalent copy committed with the arm.
_LA_BODY = Path(r"D:\codex-work\la-v5-clean-return132-20260921\arms\la_v5_clean_return_a\instance-body.json")
SRC_BODY = _LA_BODY if _LA_BODY.exists() else Path(__file__).resolve().parent / "arms" / "dsv41_la_v5_long" / "instance-body.json"
PROJECT = "cellensml"
BUCKET = "gs://cellens-ai-artifacts/arc3-duck"
MODEL_FLAT = f"{BUCKET}/model-flat/DeepSeek-V4.1-Flash-NVFP4"
MACHINE = "g4-standard-384"
DISK_GB = "1000"
IMAGE = "projects/deeplearning-platform-release/global/images/family/common-cu129-ubuntu-2404-nvidia-580"
GCLOUD = os.environ.get("GCLOUD", "gcloud")

def gcloud(*args, check=True, capture=True):
    env = dict(os.environ, CLOUDSDK_PYTHON=os.environ.get("CLOUDSDK_PYTHON", r"C:\python312\python.exe"))
    r = subprocess.run([GCLOUD, *args], env=env, capture_output=capture, text=True, shell=(os.name == "nt"))
    if check and r.returncode:
        raise SystemExit(f"gcloud {' '.join(args)} failed:\n{r.stderr}")
    return r.stdout.strip()

def sha(p: Path): return hashlib.sha256(p.read_bytes()).hexdigest()

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--zones", default="us-central1-b,us-central1-c,us-central1-f,europe-west1-b,europe-west1-c,us-east4-b,us-east4-c")
    ap.add_argument("--suffix", default=secrets.token_hex(5))
    ap.add_argument("--arm", default="dsv41_la_v5_clean_return_a")
    args = ap.parse_args()
    global ARM
    ARM = HERE / "arms" / args.arm
    armcfg = json.loads((ARM / "ARM.json").read_text()) if (ARM / "ARM.json").exists() else {}

    cfg = json.loads((ARM / "CONFIG_FLAGS.json").read_text())
    cfg_sha = sha(ARM / "CONFIG_FLAGS.json")
    startup = (ARM / "startup.sh").read_text(encoding="utf-8")
    assert f"cap-compact132/{cfg_sha}/CONFIG_FLAGS.json" in startup, "startup does not reference this CONFIG_FLAGS receipt"
    delete_request_id = (ARM / "DELETE_REQUEST_ID").read_text().strip()
    assert delete_request_id in startup

    # Preconditions in GCS
    if not args.dry_run:
        gcloud("storage", "ls", f"{MODEL_FLAT}/.complete")
        cfg_obj = f"{BUCKET}/code/cap-compact132/{cfg_sha}/CONFIG_FLAGS.json"
        if subprocess.run([GCLOUD, "storage", "ls", cfg_obj], capture_output=True, shell=(os.name == "nt"),
                          env=dict(os.environ, CLOUDSDK_PYTHON=r"C:\python312\python.exe")).returncode:
            gcloud("storage", "cp", str(ARM / "CONFIG_FLAGS.json"), cfg_obj)
            print("uploaded", cfg_obj)
        for key, local in (("runner_object", "runner.py"), ("probe_object", "runtime_probe.py")):
            if key in armcfg:
                assert sha(ARM / local) == armcfg[key.replace("_object", "_sha256")]
                assert armcfg[key.replace("_object", "_sha256")] in startup   # runner is fetched via metadata; its hash is pinned in the startup
                gcloud("storage", "cp", str(ARM / local), armcfg[key]); print("uploaded", armcfg[key])

    body = json.loads(SRC_BODY.read_text())
    run_id = f"{armcfg.get('run_id_prefix', 'g4run-dsv41flash-la-v5-clean-return-a132-w8x')}-{time.strftime('%Y%m%d')}-{args.suffix}"
    name = f"{armcfg.get('instance_prefix', 'arc3-g4-dsv41flash-la-v5-cr-a')}-{args.suffix}"
    vm_life = str(armcfg.get("vm_lifetime_seconds", 14400))
    body["name"] = name
    body["labels"].update({"arc3-matrix": "dsv41-la-v5cr", "arc3-profile": "dsv41-la-v5-clean-return-a",
                           "config-id": cfg["config_id"][:20], "owner-task": "claude-ceiling-run"})
    disk = body["disks"][0]
    disk["initializeParams"]["diskSizeGb"] = DISK_GB
    disk["initializeParams"]["sourceImage"] = IMAGE
    body["scheduling"]["maxRunDuration"] = {"seconds": vm_life}

    meta = {i["key"]: i["value"] for i in body["metadata"]["items"]}
    for k in ("arc3-golden-runtime-image", "arc3-golden-runtime-image-id", "arc3-model-mirror-prefix",
              "arc3-converter-object", "arc3-ple-patch-object", "arc3-ple-patch-sha256", "arc3-ple-base-sha256",
              "arc3-retention-overlay-object", "arc3-retention-overlay-sha256", "arc3-retention-base-sha256",
              "arc3-scheduler-overlay-object", "arc3-scheduler-overlay-sha256", "arc3-scheduler-base-sha256"):
        meta.pop(k, None)
    meta.update({
        "arc3-mig": name, "arc3-run-id": run_id, "arc3-feature-arm": "dsv41_la_v5_clean_return_a",
        "arc3-config-id": cfg["config_id"], "arc3-delete-request-id": delete_request_id,
        "arc3-model-flat-prefix": MODEL_FLAT, "arc3-model-id": cfg["recipe"]["model"]["id"],
        "arc3-model-revision": cfg["recipe"]["model"]["revision"],
        "arc3-serving-profile": "dsv41flash-tp8-w7-c102985-132", "arc3-matrix-arm": "dsv41flash-la-v5-w7-c102985-132",
        "arc3-serving-max-num-batched-tokens": "16384", "arc3-serving-tensor-parallel": "8",
        "arc3-parent-run-id": "g4run-la-v5-clean-return-a132-w7-20260921-a6a2145506",
        "arc3-repeat-of-run": "", "install-nvidia-driver": "True",
        "arc3-hard-lifetime-seconds": vm_life,
        "startup-script": startup,
    })
    if armcfg:
        meta.update({"arc3-feature-arm": armcfg["arm"], "arc3-runner-object": armcfg["runner_object"], "arc3-runner-sha256": armcfg["runner_sha256"],
                     "arc3-harness-concurrency": str(armcfg["lanes"]), "arc3-serving-max-num-seqs": str(armcfg["lanes"]),
                     "arc3-max-runtime-s-per-game": str(armcfg["game_seconds"]), "arc3-max-run-runtime-minutes": str(armcfg["suite_minutes"]),
                     "arc3-duration-class-minutes": str(armcfg["suite_minutes"]),
                     "arc3-serving-profile": f"dsv41flash-tp8ep8-w{armcfg['lanes']}-c102985-{armcfg['suite_minutes']}"})
        body["labels"]["arc3-profile"] = armcfg["arm"].replace("_", "-")
    body["metadata"]["items"] = [{"key": k, "value": v} for k, v in sorted(meta.items())]

    token = None if args.dry_run else gcloud("auth", "print-access-token")
    import urllib.request, urllib.error
    last_err = None
    for zone in args.zones.split(","):
        region = zone.rsplit("-", 1)[0]
        b = json.loads(json.dumps(body))
        b["machineType"] = f"zones/{zone}/machineTypes/{MACHINE}"
        b["disks"][0]["initializeParams"]["diskType"] = f"zones/{zone}/diskTypes/hyperdisk-balanced"
        (ARM / "instance-body.json").write_text(json.dumps(b, indent=2))
        print(f"== {zone}: {name} run_id={run_id} machine={MACHINE} disk={DISK_GB}GB spot maxRun={vm_life}s")
        if args.dry_run:
            print("dry run: body written to", ARM / "instance-body.json"); return
        req = urllib.request.Request(
            f"https://compute.googleapis.com/compute/v1/projects/{PROJECT}/zones/{zone}/instances?requestId={uuid.uuid4()}",
            data=json.dumps(b).encode(), method="POST",
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                op = json.load(r)
        except urllib.error.HTTPError as e:
            last_err = e.read().decode(); print("insert refused:", last_err[:600]); continue
        # poll the zone operation
        for _ in range(60):
            time.sleep(5)
            st = json.loads(gcloud("compute", "operations", "describe", op["name"], "--zone", zone, "--format=json"))
            if st.get("status") == "DONE":
                if st.get("error"):
                    last_err = json.dumps(st["error"]); print("operation error:", last_err[:800]); break
                print("CREATED", name, "in", zone)
                (ARM / "STATUS.json").write_text(json.dumps({
                    "run_id": run_id, "instance": name, "zone": zone, "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                    "config_id": cfg["config_id"], "config_flags_sha256": cfg_sha, "startup_sha256": hashlib.sha256(startup.encode()).hexdigest(),
                    "bucket_prefix": f"{BUCKET}/{run_id}/", "delete_request_id": delete_request_id}, indent=2))
                return
        if last_err and any(k in last_err for k in ("ZONE_RESOURCE_POOL_EXHAUSTED", "QUOTA_EXCEEDED", "resourceNotFound", "UNSUPPORTED_OPERATION")):
            continue
        break
    raise SystemExit(f"no zone accepted the instance; last error: {last_err}")

if __name__ == "__main__":
    main()
